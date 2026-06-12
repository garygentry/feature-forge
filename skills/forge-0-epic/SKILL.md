---
name: forge-0-epic
description: "Create or edit a forge epic: decompose a large change into discrete member features with dependencies, charters, and structured contracts, producing epic-manifest.json + EPIC.md. Re-run on an existing epic to enter edit mode (add/remove/reorder features, change dependencies). Use when the user runs /feature-forge:forge-0-epic or explicitly asks to start/modify an epic. Do NOT trigger for single-feature PRD work (that is forge-1-prd) or for general project planning outside forge."
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

<!-- EDIT-MODE PLACEHOLDER — fleshed out by backlog item 012b (03 §7, §8, §9).
     Entered from Step 0 when {specsDir}/{epic}/epic-manifest.json already EXISTS. -->

Entered from Step 0 when `{specsDir}/{epic}/epic-manifest.json` already exists.

Before offering any edit, validate the existing manifest and **refuse all mutation** if it is
invalid:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" validate "{epic}" --specs-dir "{specsDir}" --json
```

- Exit `0` → proceed to offer edit operations (via `AskUserQuestion`), each mapping to a helper
  mutator: `add-feature`, `remove-feature`, `reorder`, `set-dep`, `set-status`. For
  `add-feature`, run `check-name` first and elicit charter + `exposes`/`consumes` + `dependsOn`
  exactly as in C3/C4, then populate contracts by editing the composed entry and re-running
  `validate` (no contract mutator). Surface every mutator finding verbatim; atomic refusal
  leaves the manifest byte-identical. Patch only the affected EPIC.md sections.
- Exit `1`/`2` → surface **every** finding verbatim and refuse all mutation until the user
  repairs the manifest. Never auto-repair.

> The full edit branch (operation selection E2, mutator application E3, the `render-status`
> impact warning E4 for in-flight/completed features, EPIC.md patching E5, the manual-relocation
> warning on `remove-feature`, the `.epic-state.json` note, and the error-handling table) is
> specified by item 012b and appended here.

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
