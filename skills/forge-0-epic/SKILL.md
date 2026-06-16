---
name: forge-0-epic
description: "Create or edit a forge epic: decompose a large change into discrete member features with dependencies, charters, and structured contracts, producing epic-manifest.json + EPIC.md. Re-run on an existing epic to enter edit mode (add/remove/reorder features, change dependencies). Use when the user runs /feature-forge:forge-0-epic or explicitly asks to start/modify an epic. Do NOT trigger for single-feature PRD work (that is forge-1-prd) or for general project planning outside forge."
metadata:
  argument-hint: "<epic-name>"
---

# forge-0-epic — Epic Decomposition & Orchestration

Create an epic — a named grouping of related forge features with declared dependencies
and shared contracts — through a structured decomposition interview, OR edit an existing
epic. The manifest is the source of truth; EPIC.md mirrors it. All graph/validation work
is delegated to `scripts/epic-manifest.py`.

This skill **composes** JSON and **issues** helper commands. It NEVER eyeballs a dependency
graph for cycles, NEVER hand-rolls a manifest write where a mutator exists, and NEVER asks a
question in inline prose — every question goes through `AskUserQuestion`.

## Prerequisites

Read and follow `references/shared-conventions.md` for:
- the **Feature Name Requirement** (applied here to the *epic* name — see below),
- the **User Input Protocol** (the AskUserQuestion guardrail — all questions go through the tool),
- **Configuration Reading**, and
- the **Git Commit Protocol**.

**Epic name handling.** The single positional argument is the **epic** name (not a feature).
If no name is given, STOP and ask for one — do not guess. Convert multi-word input to a single
kebab-case token. The name must satisfy `SAFE_NAME_RE` (`^[a-z0-9]+(?:-[a-z0-9]+)*$`); the
helper rejects unsafe names. Member feature names are elicited later, in the interview.

**Force mode.** `--force` is honored as in shared-conventions: skip pipeline-state prerequisite
checks but still load any on-disk artifacts.

**Config values read** (defaults from shared-conventions): `specsDir` (default `./specs`),
`gitCommitAfterStage` (default true), `commitPrefix` (default `forge`).

**Helper invocation.** Every helper call uses the convention from 01 §2.2 — the absolute
plugin path and the configured specs dir:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" <subcommand> ... --specs-dir "{specsDir}"
```

`${CLAUDE_PLUGIN_ROOT}` resolves to the installed plugin root. Pass `--specs-dir "{specsDir}"`
on every invocation.

---

## Step 0 — Dispatch Detection

Resolve the epic subtree path `{specsDir}/{epic}/` and decide which branch to run.

1. **Collision check — is this name already a standalone feature?** If `{specsDir}/{epic}/`
   exists and directly contains a `.pipeline-state.json` of its own (i.e. it is itself a
   *feature* directory, not an epic root), STOP. Surface verbatim:
   > `{epic}` is already a standalone feature, not an epic. Choose a different epic name or
   > relocate the feature.

2. **Manifest existence probe** — does this epic already have a manifest?

   ```bash
   test -f "{specsDir}/{epic}/epic-manifest.json" && echo EXISTS || echo NEW
   ```

   - **NEW** (no `epic-manifest.json`) → **Creation branch** (Step C1 onward).
   - **EXISTS** → **Edit branch** (§ Edit Mode below).

3. **Pre-flight epic-name uniqueness (creation only).** Before composing anything for a NEW
   epic, confirm the epic name itself does not collide with any existing feature or epic:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" check-name "{epic}" --specs-dir "{specsDir}"
   ```

   - Exit `0` → the name is free; proceed to C1.
   - Exit `1` (`duplicate-name`) → STOP and surface the helper's finding **verbatim**; ask
     (via `AskUserQuestion`) for a different epic name, then re-run check-name.
   - Exit `2` (unsafe name) → STOP and surface the finding; ask for a corrected name.

---

## Creation Branch

### Step 1 — Branch Setup (optional)

If `gitCommitAfterStage` is true and the project uses git, use `AskUserQuestion`:
"Create a `forge/{epic}` branch for this epic? (Recommended — keeps epic work isolated.)"
If yes, create and checkout the branch before proceeding.

### Step C1 — Epic Framing Interview

Output context as text (what an epic is, that a decomposition interview will follow). Then
call `AskUserQuestion` to elicit:

1. **Epic goal / problem** — the overarching change being decomposed. Becomes the EPIC.md
   "Overall Goal" narrative and seeds the manifest `description`.
2. **One-paragraph description** — a confirmed/edited summary. Becomes the manifest `description`.

The epic `name` is the validated CLI argument from Step 0 — do NOT prompt for it again.

### Step C2 — Feature-List Interview

Drive a decomposition dialogue. Output your analysis as text first (how the goal might split,
right-sizing guidance: each feature should be a single pipeline-sized unit — a unit forge-1-prd
through forge-5-loop would carry end-to-end — not item-level interleaving). Then use
`AskUserQuestion` to elicit the candidate feature list. Probe with questions like "Is any of
these two features really one?" and "Is any one of these really two?" Iterate until the user
confirms the set.

For **each** proposed feature name, before accepting it into the set, enforce global uniqueness
and name safety via the helper:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" check-name "{feature}" --specs-dir "{specsDir}"
```

- Exit `0` → accept the name.
- Exit `1` (`duplicate-name`) → reject that name; surface the finding verbatim and re-prompt
  (via `AskUserQuestion`) for a different name.
- Exit `2` (`unsafe-name`) → reject; surface the finding and re-prompt.

Never accept a feature name that has not passed `check-name` exit 0.

### Step C3 — Per-Feature Charter + Structured Contracts

For each confirmed feature, run a focused `AskUserQuestion` batch (one feature at a time,
2–3 questions per call) eliciting:

- **Charter** — a single paragraph: scope statement + contract obligations. This is a
  **charter only, NOT a PRD**. Do NOT conduct a full requirements interview here. If the user
  starts dictating detailed requirements, redirect (as context text, then continue the batch):
  > "That's PRD-level detail — `forge-1-prd` will capture it when this feature is ready. For
  > the charter I just need the one-paragraph scope and what it must expose/consume."
- **`exposes`** — zero or more structured `Contract` objects this feature provides to
  dependents. Each is `{ "name", "kind", "summary" }` where `kind` ∈
  `function | type | endpoint | module | event`.
- **`consumes`** — zero or more structured `ConsumedContract` objects this feature relies on.
  Each is `{ "from", "name", "summary" }`, where `from` is a sibling feature name in this epic.

Collect these into plain JSON objects per feature. Do NOT free-form the contracts in prose —
the structured arrays are the source of truth; EPIC.md renders them as prose later (Step C6).

### Step C4 — Dependency-Edge Interview

For each feature, use `AskUserQuestion`: "Which sibling features must be complete before this
one can build?" → populates `dependsOn: [names]`.

**Seed the suggestion from `consumes`:** a `consumes.from` X strongly implies `dependsOn` X.
Offer the union of each feature's `consumes.from` set as the default, but let the user confirm —
`dependsOn` is the authoritative edge set.

The `features[]` array order is the user-declared sequence from C2 (order is a presentation
sequence, **not** a dependency ordering). Preserve the C2 order unless the user asks to reorder.

### Step C5 — Compose & Validate the Manifest

Compose the full `epic-manifest.json` per the 00 §2 schema, setting:

- `schemaVersion`: `1`
- `epic`: `"{epic}"`
- `description`: from C1
- `status`: `"active"`
- `narrativeDoc`: `"EPIC.md"`
- `createdAt` and `updatedAt`: the **same** current ISO-8601 UTC timestamp (`createdAt == updatedAt`)
- `features[]`: in declared order, each with `name`, `charter`, `dependsOn`, `exposes`,
  `consumes`. **No per-feature `status` field** — including one makes the manifest fail
  validation (the `cached-status` finding).

Write the composed JSON to `{specsDir}/{epic}/epic-manifest.json` (creating the epic dir first).
For the *initial* creation write the skill writes the file directly — atomic guarantees are only
required for in-place mutation, which is the helper mutators' job. Then validate:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" validate "{epic}" --specs-dir "{specsDir}" --json
```

- Exit `0` → proceed to C6.
- Exit `1` → the manifest is malformed. Surface **every** `findings[]` entry **verbatim**, do
  NOT proceed, and loop back into the relevant interview step to correct, then re-compose and
  re-validate:
  - `cycle` → re-open the dependency interview (C4).
  - `dangling-ref` → re-open C4 (bad `dependsOn`) or C3 (bad `consumes.from`).
  - `duplicate-name` / `unsafe-name` → re-open the feature-list interview (C2).
  - `cached-status` / schema violation → fix the composed JSON and re-validate.
- Exit `2` → IO/usage error (missing manifest or unreadable). Surface and STOP.

Acyclicity, uniqueness, and dangling-ref checks are thus ALWAYS performed by the helper, never
by the LLM eyeballing the graph.

> **Contracts have no mutator.** There is intentionally no `--exposes-json`/`--consumes-json`
> flag. At creation, the skill populates each feature's `exposes`/`consumes` directly in the
> composed manifest entry (above), then re-runs `validate` — exactly as described here. The
> same pattern applies after an edit-mode `add-feature` (see Edit Mode).

### Step C6 — Generate EPIC.md

Generate `{specsDir}/{epic}/EPIC.md` from the **validated** manifest. It is the human-readable
**mirror** of the manifest (the manifest is the source of truth). Use this structure:

```markdown
# {epic} — Epic

## Overall Goal
{the epic goal from C1, expanded into narrative prose}

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
{… or "Nothing exposed." if the exposes array is empty}

**Consumes:**
- `{consumes[i].name}` from `{consumes[i].from}` — {consumes[i].summary}
{… or "Nothing consumed." if the consumes array is empty}
```

**The mirror rule.** Render each feature's `exposes`/`consumes` arrays as prose, one bullet per
contract entry, preserving `name`, `kind`/`from`, and `summary`. Do not invent a contract that
is not in the manifest, and do not omit one that is. The Overall Goal and Decomposition
Rationale are the only prose without a 1:1 manifest counterpart. The skill does NOT itself diff
EPIC.md against the manifest — drift detection is `forge-verify` epic mode CHECK-E06.

### Step C7 — Create Member Subdirectories + Back-Pointer States

After the manifest validates and EPIC.md is written, create one subdirectory per member feature
so the navigator and resolver can see them before any stage runs. For each `features[].name`:

1. Create `{specsDir}/{epic}/{feature}/`.
2. Write `{specsDir}/{epic}/{feature}/.pipeline-state.json` conforming to
   `references/pipeline-state-schema.json`, carrying:
   - `epic`: `"{epic}"` — the back-pointer.
   - `currentStage`: `"forge-1-prd"` — the next actionable stage for the member.
   - `stages["forge-0-epic"]`: `{ "status": "complete", "version": 1, "completedAt": "<ts>" }`
     — recording that the epic stage seeded this member.
   - No other stages (all other stages absent/pending), exactly as a freshly-initialized
     standalone feature. **No per-feature `status` beyond the stage entry** — the member state
     holds derived stage progress only.

Example member state:

```json
{
  "epic": "{epic}",
  "currentStage": "forge-1-prd",
  "stages": {
    "forge-0-epic": { "status": "complete", "version": 1, "completedAt": "<iso-8601-utc>" }
  }
}
```

The member subtree holds the **same** artifact set a standalone feature holds; only
`.pipeline-state.json` exists at creation. No PRD/specs are authored here. The epic subtree is
now self-contained: manifest + EPIC.md + one subdirectory per member.

### Step C8 — Review, Pipeline State & Commit

1. **Review.** Present a summary (epic name, N features, dependency edges, contracts) as text,
   then use `AskUserQuestion`: "Does this epic decomposition look right? Any feature, dependency,
   or contract to change before I commit?" If the user wants changes, loop back to the relevant
   creation step, re-compose, and re-validate.

2. **Commit (Git Commit Protocol).** If `gitCommitAfterStage` is true, follow the Git Commit
   Protocol in shared-conventions:
   - Stage the whole epic subtree only: `git add {specsDir}/{epic}/` — never `git add -A`. This
     captures `epic-manifest.json`, `EPIC.md`, and all member `.pipeline-state.json` files
     atomically.
   - Commit with message `"{commitPrefix}({epic}): create epic with {N} features"`.
   - On success, capture the commit hash. On failure (pre-commit hook, conflict), report and do
     not mark complete; never use `--no-verify`/`--force`.

3. **Closing message.** After a successful creation, tell the user the next steps:

   > Epic `{epic}` created with {N} features. Next steps:
   >  - `/feature-forge:forge {epic}` to see the epic dashboard
   >  - `/feature-forge:forge-verify {epic}` to verify the epic
   >  - `/feature-forge:forge-1-prd {first-actionable-feature}` to start the first feature

   The first-actionable feature is any feature with empty `dependsOn` (or the first entry of
   `render-status`'s `actionable` set).

---

## Edit Mode

Entered from Step 0 when `{specsDir}/{epic}/epic-manifest.json` already exists (the **EXISTS**
branch). The edit branch mutates the manifest **only** through helper mutators — the skill never
hand-rolls an in-place write. Every mutator is atomic (temp file + `os.replace`) and re-validates
the edited graph internally, so a refused write leaves the manifest **byte-identical**. Every
question goes through `AskUserQuestion`.

### Step E1 — Load + Validate, Refuse if Invalid

Before offering any edit, validate the existing manifest:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" validate "{epic}" --specs-dir "{specsDir}" --json
```

- Exit `0` → the manifest is well-formed; proceed to E2.
- Exit `1` or `2` → the manifest is corrupt or invalid (hand-edited, `corrupt-json`, `cycle`,
  `dangling-ref`, `duplicate-name`, `cached-status`, `unsafe-name`, …). Surface **every**
  `findings[]` entry **verbatim**, then **refuse ALL mutation** until the user repairs the
  manifest by hand. **Never auto-repair**, never offer an edit operation, and never proceed past
  this gate. Tell the user what is wrong and STOP.

### Step E2 — Choose Operation

Use `AskUserQuestion` to offer the edit operations, each mapping to one helper mutator:

| Operation | Helper subcommand |
|-----------|-------------------|
| Add a feature | `add-feature` |
| Remove a feature | `remove-feature` |
| Reorder features | `reorder` |
| Change a dependency edge | `set-dep` |
| Change epic lifecycle status | `set-status` |

For **add-feature**, first run `check-name "{feature}"` (exactly as C2) so no new duplicate is
introduced — surface a `duplicate-name`/`unsafe-name` finding verbatim and re-prompt — then
elicit the new feature's **charter** + **`exposes`/`consumes`** + **`dependsOn`** exactly as in
C3/C4.

### Step E3 — Apply via Helper Mutator (re-validated)

Issue the chosen mutator. Each writes atomically and re-runs full validation internally, refusing
the write if it would introduce a cycle, dangling ref, duplicate, or schema violation. The exact
flag surface (owned by 02 §7):

```bash
# Add a feature — seeds EMPTY exposes/consumes; contracts are populated below.
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" add-feature "{epic}" "{feature}" \
  --charter "…" --specs-dir "{specsDir}" [--depends-on a,b]

# Remove a feature (drops its manifest entry; directory is left in place — see E3 note).
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" remove-feature "{epic}" "{feature}" \
  --specs-dir "{specsDir}"

# Reorder the features[] sequence (must be an exact permutation of current member names).
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" reorder "{epic}" \
  --order "feat-a,feat-c,feat-b" --specs-dir "{specsDir}"

# Change a dependency edge (--depends-on "" clears it).
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" set-dep "{epic}" "{feature}" \
  --depends-on "config-store,token-service" --specs-dir "{specsDir}"

# Change epic lifecycle status (active|paused|abandoned|complete).
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" set-status "{epic}" \
  --status paused --specs-dir "{specsDir}"
```

- Exit `0` → the mutator wrote the manifest and bumped `updatedAt`. Proceed to E4/E5.
- Exit `1` → surface the `findings[]` **verbatim** and **abort the edit**. The manifest is
  unchanged (the write was refused atomically — byte-identical). Loop back to E2 or re-elicit.
- Exit `2` → unsafe name / missing|corrupt manifest / bad `--status` value / write failure.
  Surface and STOP.

**Contracts have no mutator.** `add-feature` seeds empty `exposes`/`consumes`. To populate the
new feature's contracts, edit its `exposes`/`consumes` arrays **directly in the composed manifest
entry** (exactly as creation C5 does), then re-run `validate "{epic}" --json` to confirm — there
is intentionally no `--exposes-json`/`--consumes-json` flag.

**remove-feature leaves the member directory in place (§7.5).** The mutator drops only the
manifest entry. The skill does **not** delete or relocate `{specsDir}/{epic}/{feature}/`. WARN the
user verbatim:

> Removed `{feature}` from the manifest. Its directory `{specsDir}/{epic}/{feature}/` is left in
> place; move it to `{specsDir}/{feature}/` by hand if you want it as a standalone feature.
> Relocation is manual — there is no migration tooling.

The orphaned subdir still holds a `.pipeline-state.json` with an `epic` back-pointer the manifest
no longer lists; per the conflict rule the **manifest wins**, and `forge-verify` epic mode
CHECK-E07 reports the inconsistency non-fatally. The skill does **not** silently edit the orphaned
state file.

### Step E4 — Impact Warning (in-flight / completed features)

Before applying — or immediately after eliciting — a mutation that affects a feature whose derived
status is **not** `not-started`, warn the user. Read the **live** status (never re-derive
completion in prose):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" render-status "{epic}" --specs-dir "{specsDir}" --json
```

If the operation removes, reorders-around, or re-deps a feature whose derived status is
`in-progress` or `complete`, use `AskUserQuestion` with an explicit warning naming the affected
in-flight/completed feature(s) and **require confirmation** before applying. Example: "`token-service`
is already in-progress (forge-3-specs). Removing `config-store`, which it consumes `JWT_SECRET`
from, may invalidate its in-flight specs. Proceed?" If `render-status` exits `≥ 1`, surface the
findings and STOP (do not mutate over an invalid graph).

### Step E5 — Patch EPIC.md

Patch **only** the affected feature/Contracts section(s) — the section(s) for the added, removed,
or changed feature and any feature whose `dependsOn`/`consumes` changed — applying the §C6 mirror
rule (one bullet per `exposes`/`consumes` entry). **Full regeneration happens only on explicit
user request**: offer it via `AskUserQuestion` but default to the targeted patch. The skill keeps
EPIC.md in sync but does not itself diff it against the manifest — drift detection is `forge-verify`
epic mode CHECK-E06.

### Step E6 — Pipeline State & Commit

Proceed to the **Observability, Pipeline State & Commit** section below. Each edit-mode mutation is
committed individually so git history is the audit trail.

---

## Observability, Pipeline State & Commit

### Manifest `updatedAt`

Every helper mutator bumps the manifest's top-level `updatedAt` to the current ISO-8601 UTC
timestamp as part of the same atomic write. The skill does **not** bump it manually in edit mode.
For the initial creation write (C5) the skill sets `createdAt == updatedAt`.

### Pipeline state

- **Epic-level:** the epic subtree has **no `.pipeline-state.json` of its own** (that is what
  distinguishes an epic root from a feature). The epic's lifecycle lives in the manifest `status`
  field. The `forge-0-epic` run is recorded in **member** states, not in an epic-level state file.
- **Member-level (creation):** each member's `.pipeline-state.json` records
  `stages["forge-0-epic"].status = "complete"` and `currentStage = "forge-1-prd"` (see C7).
- **Edit mode:** edits mutate the **manifest**, not member pipeline states — except the
  newly-created subdir for `add-feature`, which follows C7 (create the member subdir + back-pointer
  state). The skill does **not** rewrite existing members' `stages` on an edit.
- **`.epic-state.json` (lazily created, written by skills — NOT the helper):** epic-*scoped* stage
  entries that belong to no single member — currently only `forge-verify-epic` — are persisted in a
  dedicated `{specsDir}/{epic}/.epic-state.json`. It holds **only** epic-scoped stage entries,
  never derived per-feature status (so it does not violate REQ-STATE-02). `forge-0-epic` does
  **not** create this file — no epic-scoped stage runs during creation or edit; it appears only once
  `forge-verify` epic mode runs. When a skill does write it (e.g. forge-verify epic mode), it writes
  **directly** using an atomic temp-file + `os.replace` pattern — the helper exposes no subcommand
  for it. On I/O failure the skill reports and leaves any prior file intact (never a partial write).
  Minimal schema:

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

  The git-commit step below stages the whole epic subtree, so `.epic-state.json` is captured
  automatically when present.

### Git Commit Protocol

After creation (C8) **and after each edit-mode mutation (E6)**, if `gitCommitAfterStage` is true,
follow the Git Commit Protocol in shared-conventions:

1. Stage the whole epic subtree only: `git add {specsDir}/{epic}/` — **never** `git add -A`. This
   captures `epic-manifest.json`, `EPIC.md`, member `.pipeline-state.json` files, and any
   `.epic-state.json` together atomically.
2. Commit with message `"{commitPrefix}({epic}): <action>"`, e.g.
   `"forge({epic}): create epic with 4 features"`, `"forge({epic}): add feature api-gateway"`,
   `"forge({epic}): remove feature legacy-session"`, `"forge({epic}): reorder features"`,
   `"forge({epic}): set dependency on token-service"`, or `"forge({epic}): set status paused"`.
3. On success, capture the commit hash. On failure (pre-commit hook, conflict), report and do
   **not** mark complete; never use `--no-verify`/`--force`.

Because every mutation is committed, the git history of `epic-manifest.json` is the audit trail; no
separate in-manifest audit log is kept.

### Closing message

After a successful **creation**, present the next-steps message (already specified in C8). After a
successful **edit-mode mutation**, confirm the change and re-surface the dashboard pointer:

> Epic `{epic}` updated (`<action>`). Run `/feature-forge:forge {epic}` to see the refreshed
> dashboard, or re-run `/feature-forge:forge-0-epic {epic}` to make another change.

---

## Error Handling

The skill **never** repairs a corrupt manifest automatically and **never** proceeds past a gating
helper exit `≥ 1`. All findings are surfaced **verbatim**.

| Condition | Helper signal | Skill behavior |
|-----------|---------------|----------------|
| Epic name duplicates an existing name | `check-name` exit 1 (`duplicate-name`) | STOP creation; surface finding; ask for a new name via `AskUserQuestion` |
| Member feature name duplicates | `check-name` exit 1 (`duplicate-name`) | Reject that name in C2 / add-feature; surface verbatim; re-prompt |
| Unsafe name (`/`, `..`, absolute) | `check-name`/mutator exit 2 (`unsafe-name`) | Reject; surface; re-prompt |
| Composed manifest has a cycle | `validate` exit 1 (`cycle`) | Surface verbatim; re-open the dependency interview (C4); never finalize |
| Dangling `dependsOn`/`consumes.from` | `validate` exit 1 (`dangling-ref`) | Surface verbatim; re-open C4 (bad `dependsOn`) or C3 (bad `consumes.from`) |
| Corrupt/unparseable manifest (edit) | `validate` exit 1 (`corrupt-json`) | Surface ALL findings verbatim; **refuse all mutation** until repaired; never auto-repair |
| Existing manifest otherwise invalid (edit) | `validate` exit 1/2 | Surface ALL findings verbatim; **refuse all mutation** (E1) |
| Mutator would introduce cycle/dangling ref/duplicate | mutator exit 1 | Abort the edit; manifest byte-identical (atomic refusal); surface finding |
| Bad `--status` value | `set-status` exit 2 (argparse) | Surface; re-prompt via `AskUserQuestion` with the valid choices |
| Edit affects in-flight/completed feature | `render-status` derived status (`in-progress`/`complete`) | Warn naming the affected feature(s); require confirmation before applying (E4) |
| `render-status` over an invalid graph | `render-status` exit ≥ 1 | Surface findings; STOP (do not mutate over an invalid graph) |
| Git commit fails | — | Report; leave state `in-progress`; never bypass hooks (`--no-verify`/`--force`) |

---

## Gotchas

- The argument names an **epic**, not a feature — this is the only stage where that is true.
  Member feature names come from the C2 interview, each gated through `check-name`.
- Never eyeball the dependency graph for cycles. Compose the manifest, run `validate`, and
  surface findings. The helper owns acyclicity, uniqueness, dangling-ref, and schema checks.
- A charter is one paragraph, not a PRD. Redirect requirement-level detail to `forge-1-prd`.
- Contracts have no mutator: edit `exposes`/`consumes` in the composed manifest entry, then
  re-run `validate`.
- All questions go through `AskUserQuestion`. Never put a question in your text output.
