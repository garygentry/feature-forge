# 03 — `forge-0-epic` Stage (Creation + Edit) & EPIC.md Sync Contract

> The `forge-0-epic` stage is a prose Claude Code skill (`skills/forge-0-epic/SKILL.md`).
> It owns epic **creation** (a decomposition interview producing the manifest, `EPIC.md`,
> and one charter per feature) and epic **edit mode** (add / remove / reorder features and
> change dependencies). All deterministic work — schema validation, acyclicity, name
> uniqueness, path containment, atomic writes — is delegated to `scripts/epic-manifest.py`
> (see 02-manifest-helper-cli.md). The skill **composes** JSON and **issues** helper
> commands; it never eyeballs a dependency graph for cycles and never hand-rolls a manifest
> write.
>
> This document specifies the skill's frontmatter, step structure, the AskUserQuestion
> interview, the exact helper invocations, the EPIC.md generation/sync contract, the
> pipeline-state writes, and error handling. It does not redefine shared types — the
> manifest schema (00 §2), finding taxonomy (00 §4), name safety (00 §6), completion rule
> (00 §7), and subtree layout (01 §4.1) are referenced, not restated.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-EPIC-01 | Dedicated epic-creation stage via structured interview | 1, 4 |
| REQ-EPIC-02 | Manifest records name/description/status/ordered features/dependsOn/narrative pointer | 4.5, 5 |
| REQ-EPIC-03 | Structured `exposes`/`consumes` contracts; EPIC.md narrative | 4.4, 6 |
| REQ-EPIC-04 | Per-feature charter only — no full PRD at creation | 4.3, 5 |
| REQ-EPIC-05 | Acyclic graph validated at creation and after every edit | 4.6, 7.3 |
| REQ-EPIC-06 | Edit mode: add/remove/reorder/change-deps; warn on in-flight/completed | 7 |
| REQ-DIR-01 | Self-contained epic subtree | 5 |
| REQ-DIR-04 | Globally unique feature names; duplicate rejected | 4.2, 7.2 |
| REQ-STATE-01 | Member states carry `epic` back-pointer | 5 |
| REQ-OBS-01 | Mutations bump `updatedAt`; commit per git-commit-after-stage | 8 |
| REQ-ROBUST-02 | Corrupt/invalid manifest → surface findings verbatim, refuse mutation | 9 |
| REQ-ROBUST-03 | Atomic manifest writes (delegated to helper) | 5, 7 |
| REQ-SEC-02 | Name/path containment (delegated to helper) | 4.2, 9 |
| REQ-VERIFY-01 | EPIC.md-vs-manifest drift is a verify check (CHECK-E06) | 6.4 |

---

## 1. Skill Frontmatter (REQ-EPIC-01)

`skills/forge-0-epic/SKILL.md` opens with YAML frontmatter consistent with the other
`forge-N-stage` skills (cf. `forge-1-prd/SKILL.md`):

```yaml
---
name: forge-0-epic
description: "Create or edit a forge epic: decompose a large change into discrete member features with dependencies, charters, and structured contracts, producing epic-manifest.json + EPIC.md. Re-run on an existing epic to enter edit mode (add/remove/reorder features, change dependencies). Use when the user runs /feature-forge:forge-0-epic or explicitly asks to start/modify an epic. Do NOT trigger for single-feature PRD work (that is forge-1-prd) or for general project planning outside forge."
argument-hint: "<epic-name>"
---
```

The skill takes a single positional argument: the **epic** name (kebab-case single token).
This is the only stage whose argument names an epic rather than a feature; member feature
names are elicited during the interview.

The skill body begins:

```markdown
# forge-0-epic — Epic Decomposition & Orchestration

Create an epic — a named grouping of related forge features with declared dependencies
and shared contracts — through a structured decomposition interview, OR edit an existing
epic. The manifest is the source of truth; EPIC.md mirrors it. All graph/validation work
is delegated to scripts/epic-manifest.py.
```

---

## 2. Prerequisites & Shared Conventions

The skill's **Prerequisites** section (mirroring `forge-1-prd` Step "Prerequisites") states:

> Read and follow `references/shared-conventions.md` for the epic-name validation, the
> AskUserQuestion guardrail, configuration reading, and the Git Commit Protocol before
> proceeding.

Name handling reuses the shared **Feature Name Requirement** block verbatim, applied to the
epic name: if no name is given, STOP and ask; convert multi-word input to kebab-case; the
name must satisfy `SAFE_NAME_RE` (00 §6). Force mode (`--force`) is honored as in
shared-conventions (skip pipeline-state prerequisite checks, still load on-disk artifacts).

Config values read (defaults from shared-conventions §"Configuration Reading"): `specsDir`,
`gitCommitAfterStage`, `commitPrefix`. `${CLAUDE_PLUGIN_ROOT}` and `--specs-dir` are passed
to every helper call per 01 §2.2.

---

## 3. Step Structure Overview

The skill is one file handling two modes. Mode is selected by a **dispatch detection** step,
then control flows into the matching branch:

| Step | Name | Mode | Reqs |
|------|------|------|------|
| 0 | Read config & dispatch detection | both | REQ-EPIC-01/06 |
| 1 | Branch setup (optional) | both | REQ-OBS-01 |
| **Creation branch** | | | |
| C1 | Epic framing interview (name + description + goal) | create | REQ-EPIC-01/02 |
| C2 | Feature-list interview | create | REQ-EPIC-01 |
| C3 | Per-feature charter + contracts interview | create | REQ-EPIC-03/04 |
| C4 | Dependency-edge interview | create | REQ-EPIC-02/05 |
| C5 | Compose manifest JSON → helper `validate` | create | REQ-EPIC-02/05, REQ-DIR-04 |
| C6 | Generate EPIC.md from manifest | create | REQ-EPIC-03 |
| C7 | Create member subdirectories + back-pointer states | create | REQ-DIR-01, REQ-STATE-01 |
| C8 | Review, pipeline state, commit | create | REQ-OBS-01 |
| **Edit branch** | | | |
| E1 | Load + validate existing manifest (refuse if invalid) | edit | REQ-ROBUST-02 |
| E2 | Choose edit operation (AskUserQuestion) | edit | REQ-EPIC-06 |
| E3 | Apply via helper mutator (re-validated) | edit | REQ-EPIC-05/06 |
| E4 | Impact warning (in-flight / completed features) | edit | REQ-EPIC-06 |
| E5 | Patch affected EPIC.md sections | edit | REQ-EPIC-03 |
| E6 | Pipeline state, commit | edit | REQ-OBS-01 |

Step 0 and Step 1 are shared; the branch is chosen at the end of Step 0.

---

## 4. Creation Flow

### 4.0 Step 0 — Dispatch detection

The skill resolves the epic subtree path `{specsDir}/{epic}/` and checks for the manifest:

```bash
# Existence probe — does this epic already have a manifest?
test -f "{specsDir}/{epic}/epic-manifest.json" && echo EXISTS || echo NEW
```

- **NEW** (no `epic-manifest.json`) → **creation branch** (C1…).
- **EXISTS** → **edit branch** (E1…), §7.

If `{specsDir}/{epic}/` exists but is itself a *feature* directory (has a
`.pipeline-state.json` of its own), STOP: the name collides with a standalone feature.
Surface: "`{epic}` is already a standalone feature, not an epic. Choose a different epic
name or relocate the feature." (Re-uses the distinction rule in 01 §4.3.)

Pre-flight global uniqueness of the **epic** name itself is checked before creation:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" check-name "{epic}" --specs-dir "{specsDir}"
```

Exit `1` (duplicate) → STOP and surface the helper's finding verbatim (REQ-DIR-04).

### 4.1 Step 1 — Branch setup (optional)

Mirrors `forge-1-prd` Step 1 branch setup: if `gitCommitAfterStage` is true and the project
uses git, `AskUserQuestion`: "Create a `forge/{epic}` branch for this epic? (Recommended —
keeps epic work isolated.)" If yes, create and checkout before proceeding.

### 4.2 Step C1 — Epic framing interview (REQ-EPIC-01/02, REQ-DIR-04)

Output context as text (what an epic is, that decomposition will follow), then
`AskUserQuestion` for:
1. **Epic goal / problem** — the overarching change being decomposed (free text → becomes
   EPIC.md "Overall Goal" and seeds `description`).
2. **One-paragraph description** — confirmed/edited summary → manifest `description`.

The epic `name` is the validated CLI argument (§2). No further name prompt.

### 4.3 Step C2 — Feature-list interview (REQ-EPIC-01)

Drive a decomposition dialogue. Output analysis (how the goal might split, right-sizing
guidance: each feature should be a single pipeline-sized unit, not item-level interleaved —
cf. PRD Out of Scope), then `AskUserQuestion` to elicit the candidate feature list. Probe:
"Is any of these two features really one?" and "Is any one of these really two?" Iterate
until the user confirms the set.

For **each** proposed feature name, before accepting it into the set, enforce global
uniqueness (REQ-DIR-04):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" check-name "{feature}" --specs-dir "{specsDir}"
```

Exit `1` → reject that name with the helper's finding verbatim and re-prompt for a
different name. Names must also satisfy `SAFE_NAME_RE` (00 §6); the helper rejects unsafe
names with an `unsafe-name` finding (REQ-SEC-02) — surface and re-prompt.

### 4.4 Step C3 — Per-feature charter + structured contracts (REQ-EPIC-03/04)

For each confirmed feature, run a focused `AskUserQuestion` batch (one feature at a time,
2–3 questions per call per the pacing guidance in shared-conventions) eliciting:

- **Charter** — a single paragraph: scope statement + contract obligations. This is a
  *charter only*, NOT a PRD (REQ-EPIC-04). The skill MUST NOT conduct a full
  requirements interview here; full PRDs are authored just-in-time by `forge-1-prd` when
  the feature becomes actionable. If the user starts dictating detailed requirements,
  redirect: "That's PRD-level detail — `forge-1-prd` will capture it when this feature is
  ready. For the charter I just need the one-paragraph scope and what it must expose/consume."
- **`exposes`** — zero or more structured contracts this feature provides to dependents.
  Each is a `Contract` object (00 §2.3): `{ "name", "kind", "summary" }` where `kind` ∈
  `function | type | endpoint | module | event` (REQ-EPIC-03).
- **`consumes`** — zero or more structured contracts this feature relies on. Each is a
  `ConsumedContract` (00 §2.4): `{ "from", "name", "summary" }`, where `from` is a sibling
  feature name in this epic.

The skill collects these into Python-free plain JSON objects per feature. It does **not**
free-form the contracts in prose — the structured arrays are the source; EPIC.md renders
them as prose later (§6).

### 4.5 Step C4 — Dependency-edge interview (REQ-EPIC-02/05)

For each feature, `AskUserQuestion`: "Which sibling features must be complete before this
one can build?" → populates `dependsOn: [names]`. Seed suggestions from the `consumes[]`
collected in C3 (a `consumes.from` X strongly implies `dependsOn` X) and offer them as the
default, but let the user confirm — `dependsOn` is the authoritative edge set.

The `features[]` array order is the user-declared sequence (00 §2.1: order is **not** a
dependency ordering). Preserve the order the user listed them in C2 unless they ask to
reorder.

### 4.6 Step C5 — Compose & validate the manifest (REQ-EPIC-02/05, REQ-DIR-04, REQ-SEC-02)

The skill composes the full `epic-manifest.json` per the 00 §2 schema, setting:
- `schemaVersion: 1`, `epic`, `description`, `status: "active"`, `narrativeDoc: "EPIC.md"`.
- `createdAt` and `updatedAt` to the current ISO-8601 UTC timestamp.
- `features[]` in declared order, each with `name`, `charter`, `dependsOn`, `exposes`,
  `consumes`. **No per-feature `status` field** (REQ-STATE-02 — including it makes the
  manifest fail validation, 00 §2.6).

It writes the composed JSON to the manifest path, then validates:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" validate "{epic}" --specs-dir "{specsDir}" --json
```

- Exit `0` → proceed to C6.
- Exit `1` → the manifest is malformed (cycle, dangling ref, duplicate name, schema
  violation, unsafe name). Surface every `findings[]` entry **verbatim** (00 §4), do NOT
  proceed, and loop back into the relevant interview step to correct (e.g. a `cycle`
  finding → re-open C4 dependency editing; a `duplicate-name` → re-open C2). Acyclicity is
  thus validated at creation via the helper, never by the LLM (REQ-EPIC-05).

> The skill writes the JSON the helper then validates. For the *initial* creation write the
> skill may write the file directly (atomic guarantee is only required for in-place
> mutation of an existing manifest, REQ-ROBUST-03); all subsequent edits go through the
> helper mutators, which write atomically. If the helper exposes a creation/init path, the
> skill SHOULD prefer it; if not (tech-spec §2.3 lists only mutators), the skill writes the
> composed JSON then `validate`s as above.

### 4.7 Step C6 — Generate EPIC.md

Generate `{specsDir}/{epic}/EPIC.md` from the validated manifest per the §6 contract.

### 4.8 Step C7 — see §5 (member subdirectory creation).

### 4.9 Step C8 — see §8 (review, pipeline state, commit).

---

## 5. Member Subdirectory Creation (REQ-DIR-01, REQ-STATE-01)

After the manifest validates and EPIC.md is written, the skill creates one subdirectory per
member feature so the navigator and the resolver can see them before any stage runs
(01 §4.1). For each `features[].name`:

1. Create `{specsDir}/{epic}/{feature}/`.
2. Write `{specsDir}/{epic}/{feature}/.pipeline-state.json` conforming to
   `references/pipeline-state-schema.json`, carrying:
   - `epic`: `"{epic}"` — the back-pointer (00 §3, REQ-STATE-01).
   - `currentStage`: `"forge-1-prd"` (the next actionable stage for the member; the epic
     stage itself is recorded in `stages`, see below).
   - `stages["forge-0-epic"]`: `{ "status": "complete", "version": 1, "completedAt": <ts> }`
     — recording that the epic stage seeded this member (00 §3 adds `forge-0-epic` to the
     `stages` keys and the `currentStage` enum).
   - All other stages absent/pending, exactly as a freshly-initialized standalone feature.

The member subtree holds the **same** artifact set a standalone feature holds (01 §4.1);
only `.pipeline-state.json` exists at creation. No PRD/specs are authored here (REQ-EPIC-04).

The epic subtree is now self-contained (REQ-DIR-01): manifest + EPIC.md +
one subdirectory per member.

---

## 6. EPIC.md Generation / Sync Contract (REQ-EPIC-03, REQ-VERIFY-01)

### 6.1 Document structure

`EPIC.md` is the human-readable mirror of the manifest. The skill generates it from the
validated manifest with this structure:

```markdown
# {epic} — Epic

## Overall Goal
{the epic goal from C1 / manifest description, expanded into the narrative}

## Decomposition Rationale
{why the change was split this way; right-sizing notes; ordering rationale}

## Features
{for each feature, in manifest order:}

### {feature.name}
{feature.charter, as prose}

**Depends on:** {comma-separated dependsOn, or "nothing"}

#### Contracts
**Exposes:**
- `{exposes[i].name}` ({exposes[i].kind}) — {exposes[i].summary}
{… or "Nothing exposed." if empty}

**Consumes:**
- `{consumes[i].name}` from `{consumes[i].from}` — {consumes[i].summary}
{… or "Nothing consumed." if empty}
```

### 6.2 The mirror rule

`EPIC.md` **mirrors the manifest** — the manifest is the source of truth (tech-spec §3.2,
00 §1). The per-feature **Contracts** sections render each feature's `exposes`/`consumes`
arrays as prose, one bullet per contract entry, preserving `name`, `kind`/`from`, and
`summary`. The narrative goal and decomposition rationale are the only prose that does not
have a 1:1 manifest counterpart (the manifest holds only the one-paragraph `description`).

### 6.3 Generation vs. patch

- On **creation** (C6): full generation from the manifest.
- On **edit** (E5): **patch only the affected Contracts/feature sections** (the section(s)
  for the added/removed/changed feature and any feature whose `dependsOn` or `consumes`
  changed). Full regeneration happens **only on explicit user request** (resolved design
  decision; tech-spec §9). The skill offers full regeneration as an option in E5 but
  defaults to a targeted patch.

### 6.4 Drift is a verify check (REQ-VERIFY-01)

The skill keeps EPIC.md in sync whenever it writes the manifest, but **does not itself
diff** EPIC.md against the manifest. Detecting drift between EPIC.md prose and the manifest
contracts is `forge-verify` epic mode **CHECK-E06** (tech-spec §5.5, 00 references). This
document only guarantees the *generation/patch* side stays faithful; the *audit* lives in
verify.

---

## 7. Edit Mode (REQ-EPIC-06)

Entered from Step 0 when `epic-manifest.json` already exists.

### 7.1 Step E1 — Load + validate, refuse if invalid (REQ-ROBUST-02)

Before offering any edit, validate the existing manifest:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" validate "{epic}" --specs-dir "{specsDir}" --json
```

- Exit `0` → proceed to E2.
- Exit `1` or `2` → the manifest is corrupt or invalid (hand-edited, `corrupt-json`,
  `cycle`, `dangling-ref`, `duplicate-name`, etc.). Surface **every** finding verbatim
  (00 §4) and **refuse all mutation** until the user repairs the manifest (REQ-ROBUST-02).
  The skill does not attempt automatic repair; it tells the user what is wrong and stops.

### 7.2 Step E2 — Choose operation

`AskUserQuestion` offering the edit operations, each mapping to a helper mutator
(tech-spec §2.3):

| Operation | Helper subcommand |
|-----------|-------------------|
| Add a feature | `add-feature` |
| Remove a feature | `remove-feature` |
| Reorder features | `reorder` |
| Change a dependency edge | `set-dep` |
| Change epic lifecycle status | `set-status` |

For **add-feature**, first run `check-name` (as in §4.3) so no new duplicate is introduced
(REQ-DIR-04), and elicit the new feature's charter + `exposes`/`consumes` + `dependsOn`
exactly as in C3/C4.

### 7.3 Step E3 — Apply via helper mutator (re-validated, REQ-EPIC-05/06)

Each mutator writes atomically (temp file + `os.replace`, REQ-ROBUST-03) and re-runs full
validation internally, refusing the write if it would introduce a cycle or dangling ref
(tech-spec §2.3). Concrete invocations:

```bash
# Add a feature. add-feature seeds an EMPTY exposes/consumes (02 §7.1); contracts for the
# new feature are populated the same way creation does — the skill composes the exposes/
# consumes into the feature's manifest entry, then re-runs `validate` (see note below).
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" add-feature "{epic}" "{feature}" \
  --charter "…" --specs-dir "{specsDir}" [--depends-on a,b]

# Remove a feature (drops its manifest entry; see §7.5 for the directory)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" remove-feature "{epic}" "{feature}" \
  --specs-dir "{specsDir}"

# Reorder the features[] sequence
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" reorder "{epic}" \
  --order "feat-a,feat-c,feat-b" --specs-dir "{specsDir}"

# Change a dependency edge
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" set-dep "{epic}" "{feature}" \
  --depends-on "config-store,token-service" --specs-dir "{specsDir}"

# Change epic lifecycle status (active|paused|abandoned|complete)
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" set-status "{epic}" \
  --status paused --specs-dir "{specsDir}"
```

> **Exact flag spelling is owned by 02-manifest-helper-cli.md §7** (reconciled): the
> mutator surface is `add-feature <epic> <name> --charter TEXT [--depends-on A,B]`,
> `remove-feature <epic> <name>`, `reorder <epic> --order A,B,C`,
> `set-dep <epic> <name> --depends-on A,B`, and `set-status <epic> --status STATE`, each
> plus `[--specs-dir DIR]`. **There is intentionally no contract-setting mutator and no
> `--exposes-json`/`--consumes-json` flag** — `add-feature` seeds empty `exposes`/`consumes`
> (02 §7.1). To populate or change a feature's contracts (at creation or after an
> `add-feature` in edit mode), the skill edits the feature's `exposes`/`consumes` directly
> in the composed manifest entry and re-runs `validate` for confirmation, exactly as the
> creation flow does (§4.5–4.6). REQ-EPIC-06 requires add/remove/reorder/change-deps; it
> does not require a contract-edit mutator.

On mutator exit `1`, surface the findings verbatim and abort the edit (the manifest is
unchanged because the write was refused atomically). The skill never partially applies an
edit.

### 7.4 Step E4 — Impact warning (REQ-EPIC-06)

Before (or immediately after eliciting) a mutation that affects a feature which is **not**
`not-started`, warn the user. The skill computes affected-feature status by reading each
target feature's `.pipeline-state.json` (or, preferably, `render-status` for the live view):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" render-status "{epic}" --specs-dir "{specsDir}" --json
```

If the operation removes, reorders-around, or re-deps a feature whose derived status is
`in-progress` or `complete` (00 §5/§7), `AskUserQuestion` with an explicit warning naming
the affected in-flight/completed features and requiring confirmation before applying
(REQ-EPIC-06). Example: "`token-service` is already in-progress (forge-3-specs). Removing
`config-store`, which it consumes `JWT_SECRET` from, may invalidate its in-flight specs.
Proceed?"

### 7.5 Removed-feature directory treatment (resolved design decision)

When `remove-feature` drops a feature from the manifest, the skill:
1. **Leaves the member subdirectory in place** under `{specsDir}/{epic}/{feature}/` — it is
   NOT deleted and NOT relocated.
2. **WARNs the user** that the directory still exists and that relocation to flat specs (if
   desired) is **manual** — there is no migration tooling (consistent with PRD Out of
   Scope). Message: "Removed `{feature}` from the manifest. Its directory
   `{specsDir}/{epic}/{feature}/` is left in place; move it to `{specsDir}/{feature}/` by
   hand if you want it as a standalone feature."

A consequence the skill notes: the orphaned subdirectory still contains a
`.pipeline-state.json` with an `epic` back-pointer that the manifest no longer lists. Per
the conflict rule (REQ-STATE-01, 00 §3) **the manifest wins**; this inconsistency is
reported (non-fatally) by `forge-verify` epic mode CHECK-E07. The skill does not silently
edit the orphaned state file.

### 7.6 Step E5 — Patch EPIC.md

Per §6.3: patch the affected feature/Contracts section(s) for the added/removed/changed
features; offer full regeneration only if the user asks.

### 7.7 Step E6 — see §8.

---

## 8. Observability, Pipeline State & Commit (REQ-OBS-01)

### 8.1 `updatedAt`

Every helper mutator bumps the manifest's top-level `updatedAt` to the current ISO-8601
timestamp as part of the same atomic write (tech-spec §3.7, 00 §2.1). The skill does not
bump it manually — it is the mutator's responsibility. For the initial creation write
(§4.6) the skill sets `createdAt == updatedAt`.

### 8.2 Pipeline state

- **Epic-level:** the epic subtree has no `.pipeline-state.json` of its own (01 §4.3 — that
  is what distinguishes it from a feature) and carries **no per-feature pipeline status**.
  The epic's lifecycle lives in the manifest `status` field. The `forge-0-epic` run is
  recorded in **member** states, not in an epic-level state file.
- **Epic-level stage tracking (`.epic-state.json`):** epic-*scoped* stage entries that
  belong to no single member — currently only `forge-verify-epic` (04 §9.4) — are persisted
  in a dedicated **`{specsDir}/{epic}/.epic-state.json`**, created lazily by the first stage
  that needs it (e.g. forge-verify epic mode). It is distinct from a member
  `.pipeline-state.json`: it holds only epic-scoped stage entries, never derived per-feature
  status (so it does not violate REQ-STATE-02, which forbids *cached per-feature member
  status*). Minimal schema:

  ```jsonc
  {
    "epic": "auth-overhaul",            // matches manifest `epic`
    "stages": {
      "forge-verify-epic": {
        "status": "findings-reported",   // "findings-reported" | "passed" | "findings-applied"
        "findingsFile": ".verification/VERIFY-epic-2026-06-12.md",
        "findingsCount": 3,
        "verifiedAt": "2026-06-12T00:00:00Z"
      }
    }
  }
  ```

  Writers use the same atomic-write helper as the manifest (02 §3.2). `forge-0-epic` does
  **not** create this file (no epic-scoped stage runs during creation/edit); it appears
  only once forge-verify epic mode runs. The git-commit step (§8.3) stages the whole epic
  subtree, so `.epic-state.json` is captured automatically when present.
- **Member-level (creation):** each member's `.pipeline-state.json` records
  `stages["forge-0-epic"].status = "complete"` and `currentStage = "forge-1-prd"` (§5).
  The `forge-0-epic` key is a new member of the `currentStage` enum and `stages` keys
  (00 §3).
- **Edit mode:** edits mutate the manifest, not member pipeline states (other than the
  newly-created subdir for `add-feature`, which follows §5). The skill does not rewrite
  existing members' `stages` on an edit.

### 8.3 Commit (git-commit-after-stage protocol)

After creation (C8) and after **each** edit-mode mutation (E6), if `gitCommitAfterStage`
is true, follow the **Git Commit Protocol** in shared-conventions §"Git Commit Protocol":

1. Stage the whole epic subtree only: `git add {specsDir}/{epic}/` — never `git add -A`.
   This captures `epic-manifest.json`, `EPIC.md`, and member `.pipeline-state.json` changes
   together atomically (tech-spec §3.7).
2. Commit with message `"{commitPrefix}({epic}): <action>"`, e.g.
   `"forge(auth-overhaul): create epic with 4 features"` or
   `"forge(auth-overhaul): add feature api-gateway"` or
   `"forge(auth-overhaul): remove feature legacy-session"`.
3. On success, capture the commit hash and mark the relevant member `stages.forge-0-epic`
   complete with the hash (creation) — leave manifest as the source of record otherwise.
4. On failure (pre-commit hook, conflict), report and do not mark complete; never use
   `--no-verify`/`--force` (shared-conventions).

Because every mutation is committed, the git history of `epic-manifest.json` is the audit
trail; no separate in-manifest audit log is kept (tech-spec §3.7).

### 8.4 Closing message

After a successful creation, tell the user the next steps, mirroring the
`forge-1-prd` closing style:

> "Epic `{epic}` created with {N} features. Next steps:
>  - `/feature-forge:forge {epic}` to see the epic dashboard
>  - `/feature-forge:forge-verify {epic}` to verify the epic
>  - `/feature-forge:forge-1-prd {first-actionable-feature}` to start the first feature"

The first-actionable feature is any feature with empty `dependsOn` (or obtained from
`render-status` `actionable`).

---

## 9. Error Handling

| Condition | Helper signal | Skill behavior |
|-----------|---------------|----------------|
| Epic name duplicates an existing name | `check-name` exit 1 (`duplicate-name`) | STOP creation; surface finding; ask for a new name (REQ-DIR-04) |
| Member feature name duplicates | `check-name` exit 1 | Reject that name in C2/add; re-prompt (REQ-DIR-04) |
| Unsafe name (`/`, `..`, absolute) | `unsafe-name` / exit 2 | Reject; re-prompt (REQ-SEC-02) |
| Composed manifest has a cycle | `validate` exit 1 (`cycle`) | Surface verbatim; re-open dependency interview (REQ-EPIC-05) |
| Dangling `dependsOn`/`consumes.from` | `validate` exit 1 (`dangling-ref`) | Surface verbatim; re-open the relevant step (REQ-ROBUST-02) |
| Existing manifest corrupt/invalid (edit) | `validate` exit 1/2 (`corrupt-json`, …) | Surface ALL findings verbatim; **refuse all mutation** until repaired (REQ-ROBUST-02) |
| Mutator would introduce cycle/dangling ref | mutator exit 1 | Abort the edit; manifest unchanged (atomic refusal); surface finding |
| Edit affects in-flight/completed feature | `render-status` derived status | Warn + require confirmation before applying (REQ-EPIC-06) |
| Git commit fails | — | Report; leave state `in-progress`; never bypass hooks (shared-conventions) |

The skill **never** repairs a corrupt manifest automatically and **never** proceeds past a
gating helper exit ≥ 1 (00 §9). All findings are surfaced verbatim (00 §4).

---

## Dependencies

Must be implemented first:
- **00-core-definitions.md** — manifest schema (§2), `epic` back-pointer (§3), finding
  taxonomy (§4), derived status (§5), name/path safety (§6), completion rule (§7).
- **01-architecture-layout.md** — epic subtree layout (§4.1), epic-vs-feature distinction
  (§4.3), helper invocation convention (§2.2).
- **02-manifest-helper-cli.md** — the exact CLI surface and flag names for
  `check-name`, `validate`, `render-status`, `add-feature`, `remove-feature`, `reorder`,
  `set-dep`, `set-status`. The invocations in §4/§7 have been reconciled against 02 §7 —
  the mutator flag surface is authoritative there.

Also referenced (not strictly blocking): `references/shared-conventions.md`
(name validation, AskUserQuestion guardrail, config reading, Git Commit Protocol),
`references/pipeline-state-schema.json` (member state shape).

## Verification

An implementation matches this spec when:

- [ ] **Decompose a ≥2-feature epic** (PRD Success Criteria): running
      `/feature-forge:forge-0-epic {epic}` on a fresh name produces a valid
      `epic-manifest.json` (≥2 features with at least one `dependsOn` edge), an `EPIC.md`,
      and one member subdirectory per feature each with a `.pipeline-state.json` carrying
      the `epic` back-pointer; `epic-manifest.py validate {epic}` exits 0 and the run is
      committed (REQ-EPIC-01/02/03/04, REQ-DIR-01, REQ-OBS-01).
- [ ] **Acyclicity rejection:** composing a manifest with a `dependsOn` cycle causes
      `validate` to return a `cycle` finding that the skill surfaces verbatim and refuses
      to finalize (REQ-EPIC-05); the same holds when an edit-mode `set-dep` would create a
      cycle (mutator exit 1, manifest unchanged).
- [ ] **Duplicate-name rejection:** proposing a member feature name that already exists
      anywhere in the specs tree is rejected via `check-name` with the duplicate finding
      surfaced, and re-prompts (REQ-DIR-04). Same for a duplicate epic name.
- [ ] **EPIC.md mirrors the manifest:** every feature's `exposes`/`consumes` array appears
      as a bullet in that feature's Contracts section (no contract present in the manifest
      is missing from EPIC.md, and none is invented) — i.e. `forge-verify` epic mode
      CHECK-E06 finds no drift immediately after creation (REQ-EPIC-03, REQ-VERIFY-01).
- [ ] **Edit mode:** re-running on an existing epic enters edit mode; add/remove/reorder/
      set-dep each go through the corresponding helper mutator, re-validate, and warn when
      an in-flight/completed feature is affected; a removed feature's directory is left in
      place with a warning (REQ-EPIC-06).
- [ ] **Corrupt manifest in edit mode:** an invalid/hand-edited manifest causes the skill
      to surface findings verbatim and refuse all mutation (REQ-ROBUST-02).
