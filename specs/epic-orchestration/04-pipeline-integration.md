# 04 — Pipeline Integration Points

> Every edit that grafts epic-awareness into the **existing** plugin surfaces:
> the two new `shared-conventions.md` blocks, the `pipeline-state-schema.json` patch,
> and the conditional epic-aware blocks added to each stage skill, the navigator,
> forge-verify, forge-fix, the verification checklists, and `agents/forge-researcher.md`.
>
> This document specifies *exactly what to add and where to anchor it*. It does **not**
> redefine shared types — those live in `00-core-definitions.md` (manifest schema,
> `Finding`, `DerivedStatus`, completion rule, name-safety constants). The deterministic
> helper subcommands (`resolve`, `validate`, `check-name`, `render-status`, mutators)
> are the public surface defined in `02-manifest-helper-cli.md`; here they are *consumed*.
>
> **The REQ-COMPAT-01 invariant governs this entire document:** every epic-aware block
> below is **gated on epic membership** — i.e. on the resolved feature's
> `.pipeline-state.json` carrying an `epic` back-pointer (or, for the navigator, on an
> `epic-manifest.json` being present). When that gate is false, the skill's behavior is
> **byte-for-byte unchanged** from today. No edit below alters a standalone code path.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-DIR-03 | Centralized name→directory resolution | 3, 5, 6, 7, 8, 9, 10, 11 |
| REQ-CTX-01 | Inject EPIC.md + charter + direct completed deps' PRD/tech-spec | 4, 5 |
| REQ-CTX-02 | Surface contract obligations (exposes/consumes) | 4, 5 |
| REQ-STATE-01 | `epic` back-pointer in pipeline state; manifest wins | 2 |
| REQ-COMPAT-01 | Additive; standalone unchanged (gating invariant) | 2, 3–11 (all) |
| REQ-COMPAT-02 | No migration for existing flat features / state files | 2 |
| REQ-COMPAT-03 | rauf/backlog unchanged; per-feature backlog independence | 6 |
| REQ-ORCH-01 | Completion-for-orchestration drives gate + handoff | 7 |
| REQ-ORCH-02 | Completion handoff: announce, identify next, offer PRD | 7 |
| REQ-ORCH-03 | Serial selection among unblocked features | 7 |
| REQ-ORCH-04 | Dependency gate before loop with explicit confirmation | 7 |
| REQ-ORCH-05 | Epic lifecycle verbs without mutating member states | 8 |
| REQ-VIS-01 | Epic dashboard from render-status | 8 |
| REQ-VIS-02 | 2-tier no-arg discovery with rollup | 8 |
| REQ-VERIFY-01 | forge-verify epic mode (CHECK-E01..E08) | 9 |
| REQ-DOCS-01 | Epic-level doc offer when all members complete | 10 |
| REQ-OBS-01 | Handoff/manifest writes committed via git protocol | 7 |

---

## 1. Integration Map

The table below indexes every modified file to its section here and to the gating
condition that preserves REQ-COMPAT-01. Each modified-file row matches
`tech-spec.md §2.2` and `01-architecture-layout.md §1.2`.

| File | Section | Epic gate (else unchanged) |
|------|---------|----------------------------|
| `references/shared-conventions.md` (Feature Directory Resolution block) | 3 | none — resolver returns the flat path for standalone names (REQ-COMPAT-01/02) |
| `references/shared-conventions.md` (Epic Context Injection block) | 4 | resolved feature's `.pipeline-state.json` has an `epic` key |
| `references/pipeline-state-schema.json` | 2 | additive optional fields only |
| `skills/forge-1-prd/SKILL.md` | 5.1 | `epic` back-pointer present |
| `skills/forge-2-tech/SKILL.md` | 5.2 | `epic` back-pointer present |
| `skills/forge-3-specs/SKILL.md` | 5.3 | `epic` back-pointer present |
| `skills/forge-4-backlog/SKILL.md` | 6 | `backlogDir` configured (subpath); resolution always |
| `skills/forge-5-loop/SKILL.md` | 7 | `epic` back-pointer present |
| `skills/forge/SKILL.md` | 8 | `epic-manifest.json` present / named-epic arg |
| `skills/forge-verify/SKILL.md` | 9 | `epic` mode selected |
| `skills/forge-verify/references/verification-checklists.md` | 9 | append-only `## Epic Mode Checklist` |
| `skills/forge-6-docs/SKILL.md` | 10 | feature is epic member AND all members complete |
| `skills/forge-fix/SKILL.md` | 11 | resolution always (standalone path unchanged) |
| `agents/forge-researcher.md` | 11 | glob widening; flat-only trees see no new matches |

All helper invocations use the established plugin-root convention
(`01-architecture-layout.md §2.2`):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" <subcommand> … --specs-dir "<specsDir>"
```

---

## 2. `pipeline-state-schema.json` Patch (REQ-STATE-01, REQ-COMPAT-02)

Three **additive** edits to `references/pipeline-state-schema.json`. All are optional /
enum-extension only — an existing flat `.pipeline-state.json` validates **unchanged**, so
**no migration is required** (REQ-COMPAT-02). The contract these schema edits realize is
defined in `00-core-definitions.md §3`; this section is the concrete schema diff.

### 2.1 Add the optional `epic` back-pointer property

Under the top-level `properties` object, add (alongside `feature`, `notes`, etc.):

```json
"epic": {
  "type": "string",
  "description": "Back-pointer to the owning epic's name. Absent for standalone features. The epic-manifest.json is canonical on conflict (REQ-STATE-01)."
}
```

It is **not** added to the schema's top-level `required` array — absence means
"standalone feature".

### 2.2 Extend the `currentStage` enum

Add two members to the existing `currentStage.enum` (line 27 of the current file):

```json
"enum": ["forge-1-prd", "forge-2-tech", "forge-3-specs", "forge-4-backlog",
         "forge-5-loop", "forge-6-docs", "complete",
         "forge-verify-prd", "forge-verify-tech", "forge-verify-specs",
         "forge-verify-backlog", "forge-verify-impl",
         "forge-0-epic", "forge-verify-epic"]
```

### 2.3 Add the two new `stages` keys

Under `properties.stages.properties`, add:

```json
"forge-0-epic":      { "$ref": "#/definitions/stageEntry" },
"forge-verify-epic": { "$ref": "#/definitions/verifyEntry" }
```

`forge-0-epic` reuses `stageEntry` (it produces artifacts: the manifest, `EPIC.md`,
member subdirs). `forge-verify-epic` reuses `verifyEntry` (its `findingsFile` is the
epic-mode report; see §9). No new `definitions` are needed.

**Conflict rule (REQ-STATE-01):** the schema does not enforce manifest⇆back-pointer
consistency — that is a runtime check. When a feature's `epic` names an epic whose
manifest does not list it (or vice versa), **the manifest wins**; the inconsistency is
reported by forge-verify epic mode `CHECK-E07` (§9), never silently repaired.

> `references/forge-config-schema.json` needs **no change** — `stack` / `testCommand` /
> `typeCheckCommand` are already present (`01-architecture-layout.md §1.2` note).

---

## 3. shared-conventions.md — Feature Directory Resolution block (REQ-DIR-03)

Add a new `## Feature Directory Resolution` block to
`references/shared-conventions.md`, sited **immediately after the `## Configuration
Reading` section** (so `specsDir` is already defined) and **before `## Pipeline State
Protocol`**. Every stage skill already reads shared-conventions for config; this block
becomes the single place that turns a bare feature name into a directory.

### 3.1 Prose to add

> ## Feature Directory Resolution
>
> Before any file I/O against a feature's artifacts, resolve its directory through the
> deterministic helper rather than hardcoding `{specsDir}/{feature}/`. This makes flat
> (`{specsDir}/{feature}/`) and nested (`{specsDir}/{epic}/{feature}/`) layouts both
> resolve from a bare feature name (REQ-DIR-03), with standalone features behaving
> exactly as today.
>
> ```bash
> resolvedFeatureDir=$(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" \
>   resolve "<feature>" --specs-dir "<specsDir>")
> ```
>
> - **Exit 0:** stdout is the absolute feature directory. Use it everywhere this skill
>   previously wrote `{specsDir}/{feature}/`.
> - **Exit ≥ 1:** the helper prints an actionable finding (`not-found`, `ambiguous`,
>   `unsafe-name`, `path-escape` — see `00-core-definitions.md §4`). **STOP** and surface
>   the message verbatim. Do not fall back to a guessed path.
>
> **Resolution algorithm (summary; full spec in `02-manifest-helper-cli.md §4`):**
> 1. Reject the name if unsafe (path separator, `..`, absolute, or failing
>    `SAFE_NAME_RE`) — before any filesystem access.
> 2. If `{specsDir}/{name}/.pipeline-state.json` exists → return that flat path.
> 3. Else if exactly one `{specsDir}/*/{name}/.pipeline-state.json` exists → return that
>    nested path.
> 4. More than one match anywhere → `ambiguous` error listing all matching paths
>    (uniqueness violation, REQ-DIR-04).
> 5. Zero matches → `not-found` error.
>
> A directory counts as a **feature** only if it directly contains a
> `.pipeline-state.json` (the *feature-shaped-dir bound*, `00-core-definitions.md §6`).
> Non-feature subtrees (`.verification/`, `tests/`, fixture dirs, and the epic root
> itself — which holds `epic-manifest.json` but no `.pipeline-state.json`) are therefore
> never matched as features.
>
> **Compatibility:** for a standalone feature the resolver returns its flat path with no
> epic logic engaged (REQ-COMPAT-01/02). A pre-existing latent name collision is reported
> for manual cleanup by the navigator / forge-verify epic mode (CHECK-E08), not by
> aborting an unrelated command whose name resolves to exactly one dir (tech-spec §3.4).

### 3.2 How each skill consumes it

Each stage skill's prose changes from `{specsDir}/{feature}/…` to
`{resolvedFeatureDir}/…` after calling the block. The literal anchor edits are in §5–§11.
Skills already invoke `${CLAUDE_PLUGIN_ROOT}/scripts/…` helpers (e.g. forge-verify
calls `validate-traceability.py`, `forge-verify/SKILL.md:259`), so the invocation
convention is established and unchanged.

---

## 4. shared-conventions.md — Epic Context Injection block (REQ-CTX-01/02)

Add a second new block, `## Epic Context Injection`, **immediately after the Feature
Directory Resolution block** (§3). It is invoked by forge-1/2/3 only (see §5); placing it
in shared-conventions keeps the load algorithm in one bounded, deterministic place.

### 4.1 Prose to add

> ## Epic Context Injection
>
> After resolving the feature directory, check the feature's `.pipeline-state.json` for
> an `epic` back-pointer. **If absent, skip this block entirely** (standalone feature —
> REQ-COMPAT-01). **If present**, load exactly the following context, and nothing
> transitive (REQ-CTX-01):
>
> 1. **`{specsDir}/{epic}/EPIC.md`** — the epic narrative, including the per-feature
>    Contracts sections.
> 2. **This feature's `charter`** — read from `{specsDir}/{epic}/epic-manifest.json`
>    (the `features[]` entry whose `name` matches), together with its `exposes` and
>    `consumes` arrays. These are the feature's **contract obligations** (REQ-CTX-02):
>    what it must expose to dependents and what it consumes from dependencies.
> 3. **Direct completed dependencies only** — for each `name` in this feature's
>    `dependsOn`, resolve that sibling's directory and, **only if it is
>    complete-for-orchestration** (`00-core-definitions.md §7`), load its `PRD.md` and
>    `tech-spec.md`.
>
> **Do NOT load** transitive (indirect) dependencies' specs. Indirect contracts reach
> this feature only through the *direct* deps' Contracts sections in `EPIC.md`. This
> bounds context size and keeps the injected set deterministic (REQ-CTX-01).
>
> To obtain the manifest contracts and the live completion status of each dependency in
> one deterministic call, run `render-status` and read the per-feature `status` and the
> `consumes`/`exposes` arrays rather than re-deriving them:
>
> ```bash
> python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" \
>   render-status "<epic>" --specs-dir "<specsDir>" --json
> ```
>
> If `render-status` exits ≥ 1, surface its findings and proceed with **only** EPIC.md +
> charter (a corrupt manifest must not silently inject stale dep specs — REQ-ROBUST-02).

### 4.2 Determinism note

The injected set is a pure function of the manifest + each dependency's
`.pipeline-state.json` at read time. A dependency that is *not yet*
complete-for-orchestration contributes **nothing** to the injected context (its specs are
not yet trustworthy), exactly matching the "build against reality" goal (PRD User
Stories §2). This is the same completion predicate used by the §7 gate and handoff,
implemented once in `render-status`.

---

## 5. forge-1 / forge-2 / forge-3 — Resolution + Context Injection (REQ-CTX-01/02, REQ-DIR-03)

All three skills already open with `## Prerequisites` instructing them to read
shared-conventions. Each gains (a) a resolution call and (b) a context-injection call at
its existing artifact-loading step, plus depth-2 glob widening in forge-2/forge-3.

### 5.1 forge-1-prd (`skills/forge-1-prd/SKILL.md`)

- **Anchor — Step 1 ("Read Configuration and Check State"), the line `Set the working
  directory: {specsDir}/{feature}/`** (`forge-1-prd/SKILL.md:21`): replace with a call to
  the Feature Directory Resolution block, setting `{resolvedFeatureDir}`. **Caveat:** at
  PRD time a brand-new standalone feature may have *no* directory yet; resolution is
  expected to fail `not-found` for a never-started standalone feature, in which case
  forge-1 creates `{specsDir}/{feature}/` as today. For an **epic member**, the directory
  already exists (created empty by forge-0-epic with an `epic` back-pointer,
  `01-architecture-layout.md §4.1`), so resolution succeeds and yields the nested path.
- **Anchor — beginning of Step 2 ("Examine Existing Context"),
  `forge-1-prd/SKILL.md:24`**: after resolving, invoke the **Epic Context Injection**
  block (§4) so EPIC.md + charter + completed direct-dep specs are in context **before the
  interview** (Step 3). Add a sentence: "If this feature is an epic member, the injected
  charter's `exposes`/`consumes` are requirement inputs — every contract obligation must
  appear as a REQ in the PRD."
- Replace remaining `{specsDir}/{feature}/` literals (Step 4 write path, Step 6 state
  path) with `{resolvedFeatureDir}/`.

### 5.2 forge-2-tech (`skills/forge-2-tech/SKILL.md`)

- **Anchor — Step 1 ("Validate Prerequisites"), `forge-2-tech/SKILL.md:17`**: resolve the
  directory first; read `{resolvedFeatureDir}/.pipeline-state.json` and
  `{resolvedFeatureDir}/PRD.md`.
- **Context injection — after reading the PRD (end of Step 1)**: invoke the Epic Context
  Injection block (§4). Then, in the **forge-researcher dispatch (Step 2, "Delegate to
  forge-researcher Subagent", `forge-2-tech/SKILL.md:25`)**, add to the dispatch prompt:
  "If this feature belongs to an epic, also account for these epic contracts: {paste this
  feature's `consumes` and the `exposes` of its direct deps}, and the completed
  dependency tech-specs at {paths}. Do not re-research transitive deps." This threads epic
  context into the researcher without changing the agent's behavior (the agent just
  receives extra focus material).
- **Glob widening — Manual Research fallback, item 5 (`forge-2-tech/SKILL.md:55`):**
  change `Check {specsDir}/*/tech-spec.md` to **`Check {specsDir}/*/tech-spec.md` and
  `{specsDir}/*/*/tech-spec.md` (depth-2, to find nested epic members)**, subject to the
  feature-shaped-dir bound (§5.4).
- Replace remaining `{specsDir}/{feature}/` literals (Step 5 write, Step 7 state) with
  `{resolvedFeatureDir}/`.

### 5.3 forge-3-specs (`skills/forge-3-specs/SKILL.md`)

- **Anchor — Step 1 ("Validate Prerequisites"), `forge-3-specs/SKILL.md:19`**: resolve
  first; read state, `PRD.md`, `tech-spec.md` from `{resolvedFeatureDir}/`.
- **Context injection — after reading PRD + tech-spec (end of Step 1)**: invoke the Epic
  Context Injection block (§4).
- **Glob widening — Step 2, item 3 (`forge-3-specs/SKILL.md:27`):** change
  `{specsDir}/*/[0-9][0-9]-*.md` to also include `{specsDir}/*/*/[0-9][0-9]-*.md`
  (depth-2), subject to the feature-shaped-dir bound (§5.4).
- **forge-spec-writer threading — Step 4b ("Domain fan-out",
  `forge-3-specs/SKILL.md:68`):** add to the per-writer dispatch prompt's input list:
  "the relevant `EPIC.md` Contracts section(s) for this feature, and the `tech-spec.md`
  of each completed direct dependency at {paths} — so the doc is written against real
  upstream contracts, not guesses (REQ-CTX-01/02)." Each writer still authors only its one
  assigned file; this is additive context, no behavioral change.
- Replace remaining `{specsDir}/{feature}/` literals (Step 5 `TRACEABILITY.md`, Step 7
  state) with `{resolvedFeatureDir}/`.

### 5.4 Glob scoping — the feature-shaped-dir bound (applies to 5.2, 5.3, §11)

The widened depth-2 globs MUST be constrained to **feature-shaped directories** — a
directory is treated as a feature only if it directly contains a `.pipeline-state.json`
(`00-core-definitions.md §6`). Otherwise a depth-2 pattern would match non-feature
subtrees that legitimately hold matching filenames (e.g. `tests/fixtures/…/tech-spec.md`,
a numbered file under `.verification/`). Two acceptable implementations (specify either in
the skill prose):

1. **Filter glob results** to paths whose **parent directory also contains
   `.pipeline-state.json`**; or
2. **Delegate listing to the helper** — `epic-manifest.py` already applies this bound for
   resolution/uniqueness, so a skill may enumerate members via `render-status` rather than
   globbing the filesystem directly.

Standalone (flat-only) trees gain **no** new matches from the widened glob — there are no
depth-2 feature dirs — so REQ-COMPAT-01 holds.

---

## 6. forge-4-backlog — Resolution + per-feature backlog subpath (REQ-DIR-03, REQ-COMPAT-03)

`skills/forge-4-backlog/SKILL.md` already resolves a "backlog directory" in its
`## Prerequisites` (`forge-4-backlog/SKILL.md:23`). Two edits:

### 6.1 Central directory resolution

- **Anchor — Step 1 ("Validate Prerequisites"), `forge-4-backlog/SKILL.md:33`**: resolve
  the feature directory via the §3 block first; read state / specs from
  `{resolvedFeatureDir}/`. Replace the Step 2 spec-load literals
  (`forge-4-backlog/SKILL.md:40-43`) with `{resolvedFeatureDir}/`.

### 6.2 `backlogDir` resolution rule (REQ-COMPAT-03, tech-spec §5.7)

Replace the existing `## Prerequisites` backlog-dir resolution
(`forge-4-backlog/SKILL.md:23-26`) and Step 5/Step 7 references with this rule:

> Resolve the **backlog directory** `{backlogDir}`:
> - **`backlogDir` unset (default):** the backlog lives at the resolved feature directory
>   — **`{resolvedFeatureDir}/backlog.json`** — for both flat and nested features, exactly
>   as today.
> - **`backlogDir` configured:** compose a **per-feature subpath** —
>   **`{backlogDir}/{feature}/`** — so each epic member's backlog stays independent. A
>   bare shared `backlogDir` would collide across a multi-feature epic and violate
>   REQ-COMPAT-03; the `{feature}` segment prevents that. Standalone features under a
>   configured `backlogDir` likewise resolve to `{backlogDir}/{feature}/`, which is
>   backward-compatible because each standalone feature name is already unique.

This is the **single** place the rule is implemented; forge-5-loop's backlog-file check
(`forge-5-loop/SKILL.md:84-90`) and forge-verify's backlog-mode load must use the same
composed path. rauf itself is unchanged: backlogs remain per-feature, dependencies are
resolved only at feature granularity before the loop launches (REQ-COMPAT-03, tech-spec
§5.7). The shared-conventions default note
(`shared-conventions.md:48`) gains a parenthetical: "(when `backlogDir` is configured,
forge-4 composes `{backlogDir}/{feature}/`)."

> **Cross-edit:** forge-5-loop Step 1e/2b (`forge-5-loop/SKILL.md:84-111`) currently uses
> `{backlogDir}/backlog.json` when configured. Update both to the composed
> `{backlogDir}/{feature}/backlog.json` so the loop reads the same file forge-4 wrote.

---

## 7. forge-5-loop — Dependency Gate + Handoff (REQ-ORCH-01/02/03/04, REQ-OBS-01)

`skills/forge-5-loop/SKILL.md` gains a new gate sub-step and a new terminal step. Both are
gated on the `epic` back-pointer; absent → unchanged (REQ-COMPAT-01).

### 7.0 Resolution

- **Anchor — Step 1 ("Validate Prerequisites"), Step 1a `forge-5-loop/SKILL.md:43-45`:**
  resolve the feature directory via §3 first; read
  `{resolvedFeatureDir}/.pipeline-state.json`. All later `{specsDir}/{feature}/` literals
  (1e backlog path, Step 3a/Step 5 state writes) use `{resolvedFeatureDir}/`.

### 7.1 Dependency gate — new **Step 1b-epic** (REQ-ORCH-04)

**Exact placement:** insert a new sub-step **between the existing `### 1b. Verification
Check` (`forge-5-loop/SKILL.md:47-51`) and `### 1c. Runner Version Gate`
(`forge-5-loop/SKILL.md:53`)**. Title it `### 1b-epic. Epic Dependency Gate`.

> ### 1b-epic. Epic Dependency Gate
>
> Read the resolved feature's `.pipeline-state.json`. **If it has no `epic` key, skip this
> sub-step entirely** (standalone feature — REQ-COMPAT-01). Otherwise:
>
> 1. Run `render-status "{epic}" --specs-dir "{specsDir}" --json`.
> 2. Find this feature's entry; read its `unmetDeps` (the direct `dependsOn` not yet
>    complete-for-orchestration per `00-core-definitions.md §7`).
> 3. **If `unmetDeps` is empty**, proceed to 1c with no prompt.
> 4. **If `unmetDeps` is non-empty**, use `AskUserQuestion` to warn (do NOT inline the
>    question as prose):
>    > "{feature} depends on {unmetDeps joined}, which are not yet complete. Running the
>    > loop now means implementing against contracts that may still change. Proceed
>    > anyway, or stop and finish the dependencies first?"
>    Require an **explicit "Proceed anyway"** choice to continue (REQ-ORCH-04). "Stop"
>    aborts before any runner setup. `--force` (shared-conventions Force Mode) also
>    bypasses this gate with the standard force warning.
> 5. If `render-status` exits ≥ 1 (corrupt manifest), surface its findings and STOP — do
>    not silently run a loop whose dependency state is unverifiable (REQ-ROBUST-02).

This gate runs **before** the runner version/setup gates so a blocked feature stops early,
before any runner side-effects.

### 7.2 Handoff — new **Step 6** (REQ-ORCH-01/02/03)

**Exact placement:** append a new `## Step 6: Epic Handoff` **after the existing
`## Step 5: Update Pipeline State` (`forge-5-loop/SKILL.md:351-363`)** — i.e. *after*
pipeline state has been written, so the just-finished feature's `forge-5-loop.status` is
already `complete` on disk when render-status reads it.

> ## Step 6: Epic Handoff
>
> **Gate:** only run this step if (a) the resolved feature's `.pipeline-state.json` has an
> `epic` key **and** (b) Step 5 set `stages.forge-5-loop.status` to `complete` (all
> backlog items done). If either is false, skip — standalone features and partial runs end
> exactly as today (REQ-COMPAT-01).
>
> 1. **Offer impl-verify first (recommended, skippable).** Per the completion rule
>    (`00-core-definitions.md §7`), a feature with `forge-verify-impl.status ==
>    findings-reported` does **not** unblock dependents. Use `AskUserQuestion` to offer:
>    "{feature}'s loop is done. Recommended: run `/feature-forge:forge-verify {feature}
>    impl` before unblocking dependents. Run it now, or skip and continue the handoff?"
>    The user may skip (then completion is judged on the §7 rule with impl-verify absent).
> 2. **Recompute and announce.** Run `render-status "{epic}" --json`. Announce the
>    feature's completion and the epic rollup (e.g. "2/4 features complete").
> 3. **Identify the next actionable feature(s).** Read `render-status`'s `actionable`
>    set (features whose every dependency is now complete and that are not themselves
>    complete) and `nextCommand`.
>    - **None actionable** (everything done, or remaining features still blocked): say so.
>      If `rollup.complete == rollup.total`, suggest `/feature-forge:forge-6-docs {feature}`
>      and note the epic-level doc offer (§10). Otherwise list what is still blocked and on
>      what. End — no prompt to start a feature that cannot start.
>    - **One or more actionable:** use `AskUserQuestion` presenting **each actionable
>      feature** as an option (plus "stop here"). Execution is **serial** — the user picks
>      exactly one (REQ-ORCH-03). Do **not** autonomously chain into the next pipeline
>      (PRD Out of Scope).
> 4. **Begin the chosen feature.** For the picked feature:
>    - **PRD absent** (no `PRD.md`, or `stages.forge-1-prd` not complete): offer to author
>      it now — "Start `/feature-forge:forge-1-prd {chosen}`?" (REQ-ORCH-02). On yes, hand
>      off to forge-1-prd (which will inject epic context per §5.1).
>    - **PRD present:** point the user at the chosen feature's `nextCommand` from
>      render-status.
> 5. **Commit (REQ-OBS-01).** The Step 5 completion write (and any manifest `updatedAt`
>    bump from a `set-status` mutation, if forge-5 records member completion into the
>    manifest) is committed via the shared-conventions **Git Commit Protocol** when
>    `gitCommitAfterStage` is true: `git add {specsDir}/{epic}/` then
>    `{commitPrefix}({feature}): complete loop` — staging the epic subtree so the member
>    state change commits atomically (tech-spec §3.7). If `gitCommitAfterStage` is false,
>    skip the commit.

> **Note — Step 5's "No git commit needed" remark (`forge-5-loop/SKILL.md:363`)** refers
> to *implementation code*, which the runner commits per-item. The epic handoff's commit
> is of *pipeline state / manifest*, a distinct artifact, and applies only to epic members.

---

## 8. forge — Epic Navigator (REQ-VIS-01/02, REQ-ORCH-05, REQ-DIR-03)

`skills/forge/SKILL.md` is read-only except for `notes` / `updatedAt` / `pipelineStatus`
(its Gotchas). All edits preserve that.

### 8.1 Resolve nested names — Section 2 ("Determine Context")

- **Anchor — "If a feature name is provided", `forge/SKILL.md:21-24`:** before looking for
  `{specsDir}/{feature}/.pipeline-state.json`, first test whether the name is an **epic**:
  if `{specsDir}/{name}/epic-manifest.json` exists, render the **epic dashboard** (§8.2).
  Otherwise resolve the name via the §3 block (so a nested member name finds its dashboard
  too) and display the existing per-feature dashboard from `{resolvedFeatureDir}/`.

### 8.2 Epic dashboard (REQ-VIS-01) — new sub-section under Section 3

Add a `### Epic Dashboard` sub-section (a sibling of "Pipeline Status Dashboard",
`forge/SKILL.md:34`):

> ### Epic Dashboard
>
> For a named epic, run `render-status "{epic}" --specs-dir "{specsDir}" --json` and render
> from its output (`00-core-definitions.md §5`, tech-spec §4.4):
> - **Epic header:** name + `status` (active | paused | abandoned | complete).
> - **Dependency graph:** each feature with its `dependsOn` (an arrow list or indented
>   tree is sufficient — the helper guarantees it is acyclic).
> - **Per-feature row:** reuse the **existing status indicators** (`forge/SKILL.md:61-70`,
>   ✅/🔄/⬜/❌/⏭️/⚠️) driven by each feature's derived `stage`/`status`; mark `blocked`
>   features and show their `unmetDeps`.
> - **Actionable vs blocked:** list the `actionable` set and the recommended
>   `nextCommand`.
> - **Rollup:** `{complete}/{total} features complete`.
>
> All of this is reconstructed **purely from disk** (the manifest + each member's
> `.pipeline-state.json`) — no in-memory state — so a fresh session renders the same
> dashboard (REQ-ROBUST-01).

### 8.3 2-tier no-arg discovery (REQ-VIS-02) — Section 2 ("If no feature name is provided")

- **Anchor — `forge/SKILL.md:26-30`:** replace the flat scan with a 2-tier listing:
  1. **Epics first.** Identify epic directories as any `{specsDir}/*/` directly containing
     `epic-manifest.json` (and **no** `.pipeline-state.json` of its own — it is never
     itself a feature, `01-architecture-layout.md §4.3`). For each, run `render-status`
     and show one rollup line: `{epic} — {complete}/{total} complete, next: {nextCommand}`.
  2. **Standalone features below.** Scan remaining `{specsDir}/*/` that directly contain a
     `.pipeline-state.json` **without** an `epic` back-pointer. Nested members'
     `.pipeline-state.json` files are **attributed to their epic, not listed as
     standalone**.
- The existing "exactly one active pipeline → show its dashboard" / "multiple → ask which"
  logic still applies *within* the standalone tier.

### 8.4 Epic lifecycle verbs (REQ-ORCH-05) — Section 6 ("Pipeline Lifecycle Commands")

Extend the existing `pause` / `resume` / `abandon` verbs (`forge/SKILL.md:91-95`) to
accept an **epic** name:

> When the argument names an **epic** (i.e. `{specsDir}/{name}/epic-manifest.json` exists):
> - `pause` / `resume` / `abandon` set the **manifest's** top-level `status`
>   (`paused` / `active` / `abandoned`) via the helper's `set-status` mutator (atomic
>   write + `updatedAt` bump, REQ-OBS-01). For `complete`, the navigator does **not** set
>   it directly — completion is derived; the manifest `status` is a lifecycle flag, not the
>   rollup.
> - **Member feature states are NOT silently mutated** (REQ-ORCH-05). Pausing/abandoning
>   an epic changes only the manifest's `status`. Before doing so, use `AskUserQuestion` to
>   make the relationship explicit: "Pausing the epic does not pause its in-flight member
>   features. {N} members are active. Pause the epic only, or also pause each member?" If
>   the user opts to pause members too, the navigator updates each member's own
>   `pipelineStatus` **individually and visibly** (one explicit action per member), never
>   as a hidden side-effect.
> - The lifecycle commit follows the Git Commit Protocol, staging `{specsDir}/{epic}/`.

---

## 9. forge-verify — Epic Mode (REQ-VERIFY-01)

A new `epic` mode in `skills/forge-verify/SKILL.md`, plus an appended checklist section.

### 9.1 Mode selection — Step 1

- **Anchor — "### Mode Selection", `forge-verify/SKILL.md:85-95`:** add an `epic` mode.
  - Explicit: `/feature-forge:forge-verify {epic} epic`.
  - Auto-detect: if the named argument resolves to an **epic directory** (has
    `epic-manifest.json`), select `epic` mode.

### 9.2 Artifact loading — Step 2

Add an `epic` block to "Load All Relevant Artifacts" (`forge-verify/SKILL.md:99`):

> **For epic mode:**
> - `{specsDir}/{epic}/epic-manifest.json`
> - `{specsDir}/{epic}/EPIC.md`
> - each member feature's `.pipeline-state.json` (for back-pointer + derived status)
> - each **completed** member's `PRD.md` + `tech-spec.md` (for contract-drift checking)

### 9.3 Dispatch — single verifier

Epic mode is a **small** checklist (8 checks). Per the skill's single-vs-parallel rule
(`forge-verify/SKILL.md:25-29`), dispatch a **single `forge-verifier`** with the feature
(epic) name and `mode=epic`. Add `epic ~8` to the per-mode totals in Step 3
(`forge-verify/SKILL.md:126`).

### 9.4 Findings document path & state — Steps 4 & 6

- **Step 4 write path:** `{specsDir}/{epic}/.verification/VERIFY-epic-{YYYY-MM-DD}.md`
  (the existing format, with `{mode}=epic`).
- **Step 6 state:** record into the **epic's** tracking. Set
  `stages.forge-verify-epic.status` to `findings-reported` (or `passed` if zero findings),
  with `findingsFile` / `findingsCount` / `verifiedAt`. Per `00-core-definitions.md §3`,
  `forge-verify-epic` is a valid stage key. (Where epic-level stage state is persisted —
  in a member's state vs. an epic-level marker — is settled by `02`/`03`; this section
  records the *stage entry*, not its home file.)

### 9.5 Checklist append — `verification-checklists.md`

**Anchor:** append a new top-level section `## Epic Mode Checklist` to the **end of**
`skills/forge-verify/references/verification-checklists.md` (after `CHECK-I20`, current
file end at line 186). E01/E02/E03/E08 **delegate to the helper**; E04/E05/E06/E07 are
verifier judgment.

> ## Epic Mode Checklist
>
> Run `epic-manifest.py validate "{epic}" --specs-dir "{specsDir}" --json` once; map its
> findings to E01/E02/E03/E08. Then perform the judgment checks E04–E07 by reading the
> manifest, EPIC.md, and completed members' specs.
>
> ### Manifest Integrity (helper-delegated)
> - [ ] **CHECK-E01**: `epic-manifest.json` conforms to `epic-manifest-schema.json`
>   (delegated: `validate` reports `schema` / `corrupt-json` findings).
> - [ ] **CHECK-E02**: the `dependsOn` graph is **acyclic** (delegated: `validate`
>   reports `cycle`).
> - [ ] **CHECK-E03**: no dangling `dependsOn` / `consumes.from` — every reference names a
>   feature in `features[]` (delegated: `validate` reports `dangling-ref`).
> - [ ] **CHECK-E08**: **global name uniqueness** across the specs tree — no feature name
>   resolves to more than one feature-shaped dir (delegated: `validate` / `check-name`
>   report `duplicate-name`/`ambiguous`). Surfaced non-fatally for manual cleanup.
>
> ### Charter & Contract Coverage (verifier judgment)
> - [ ] **CHECK-E04**: **charter coverage** — every feature has a non-empty `charter`
>   stating scope **and** contract obligations (REQ-EPIC-04).
> - [ ] **CHECK-E05**: each feature has a meaningful `exposes`/`consumes` declaration —
>   flag a feature with empty contracts that the narrative implies should have them
>   (REQ-EPIC-03). (Empty is *schema-legal* but suspicious for a feature other features
>   depend on.)
> - [ ] **CHECK-E06**: **EPIC.md ⇆ manifest contract drift, for completed features only** —
>   the contracts in `EPIC.md` match the manifest `exposes`/`consumes`, and a completed
>   feature's specs actually deliver what it `exposes`. Drift between EPIC.md prose and the
>   manifest, or between the manifest and the built spec, is a finding (REQ-VERIFY-01).
> - [ ] **CHECK-E07**: **back-pointer ⇆ manifest consistency** — every member's
>   `.pipeline-state.json` `epic` value names this epic, and every `features[]` entry has a
>   matching member directory. On conflict the **manifest wins** (REQ-STATE-01); report,
>   do not auto-repair.

---

## 10. forge-6-docs — Epic-Level Doc Offer (REQ-DOCS-01)

`skills/forge-6-docs/SKILL.md`:

- **Anchor — Step 1 ("Read Context"), `forge-6-docs/SKILL.md:19`:** resolve the feature
  directory via §3; load specs/impl/state from `{resolvedFeatureDir}/`.
- **New offer — after the existing per-feature completeness check
  (`forge-6-docs/SKILL.md:29-33`), before Step 2 planning:** add an epic block:

> ### Epic-Level Documentation (epic members only)
>
> If the resolved feature has an `epic` back-pointer, run `render-status "{epic}" --json`.
> **Only if `rollup.complete == rollup.total`** (every member is
> complete-for-orchestration, `00-core-definitions.md §7`), use `AskUserQuestion` to offer:
> "All {total} features in the '{epic}' epic are complete. Generate an **epic-level
> architecture document** spanning the features, in addition to {feature}'s per-feature
> docs?" On yes, synthesize a doc at **`{docsDir}/{epic}/`** sourced from: `EPIC.md`
> narrative, each member's per-feature docs, and the manifest contracts. If not all members
> are complete, **do not offer** — the per-feature doc flow proceeds unchanged.

- The commit stages `{docsDir}/{epic}/` in addition to the existing
  `{docsDir}/{feature}/ {specsDir}/{feature}/` (`forge-6-docs/SKILL.md:147`) when the
  epic-level doc is written.

Per-feature `currentStage: complete` behavior (Step 5) is unchanged for standalone
features and for members regardless of this offer.

---

## 11. forge-fix + forge-researcher — Resolution & Glob Widening (REQ-DIR-03)

### 11.1 forge-fix (`skills/forge-fix/SKILL.md`)

- **Anchor — Step 1 ("Locate Findings Document"), item 2 (`forge-fix/SKILL.md:20`):**
  resolve the feature directory via §3, then find the most recent `VERIFY-*-*.md` in
  `{resolvedFeatureDir}/.verification/`. Replace the Step 5 state-write path
  (`forge-fix/SKILL.md:54`) with `{resolvedFeatureDir}/.pipeline-state.json`, and stage
  `{resolvedFeatureDir}/` (or `{specsDir}/{epic}/` for a member) in the commit. No other
  behavioral change — a standalone feature resolves to its flat path exactly as today.

### 11.2 forge-researcher (`agents/forge-researcher.md`)

- **Anchor — "### 4. Check Existing Specs and Docs", the line
  `Read specs/*/PRD.md and specs/*/tech-spec.md` (`forge-researcher.md`, Standard Research
  Protocol §4):** widen to **also** read depth-2 — `specs/*/*/PRD.md` and
  `specs/*/*/tech-spec.md` — to find nested epic members (REQ-DIR-03), subject to the
  **feature-shaped-dir bound** (§5.4): only treat a directory as a feature if it directly
  contains a `.pipeline-state.json`. Add a sentence: "An epic root (`epic-manifest.json`,
  no `.pipeline-state.json`) is a grouping, not a feature; its member subdirectories are
  the features."
- This is the only change to the agent; it remains read-only and otherwise behaves
  identically. Flat-only projects gain no new matches (REQ-COMPAT-01).

---

## Dependencies

This document depends on, and must be implemented after:

- **`00-core-definitions.md`** — manifest schema, pipeline-state additions (§3), `Finding`
  taxonomy (§4), `DerivedStatus`/`FeatureStatus` (§5), name-safety constants (§6), the
  completion rule (§7), and derived sets (§8). Referenced throughout; never redefined here.
- **`01-architecture-layout.md`** — modified-files inventory (§1.2), epic-vs-flat layout
  (§4), the plugin-root invocation convention (§2.2).
- **`02-manifest-helper-cli.md`** — the `resolve`, `validate`, `check-name`,
  `render-status`, and mutator subcommands every block above invokes. (If `02` is not yet
  written, the contracts consumed here are pinned by tech-spec §2.3 and §4.4.)
- **`03-forge-0-epic-stage.md`** — creates the manifest, `EPIC.md`, and member
  subdirectories (with `epic` back-pointers) that all resolution and context-injection here
  assume exist. The handoff (§7.2) may launch forge-0-epic's downstream stages.

This document modifies only **existing** plugin files; it ships no new helper logic of its
own (that is `02`) and no new stage skill (that is `03`).

## Verification

Concrete checks that an implementation matches this spec:

1. **Schema patch (REQ-STATE-01/COMPAT-02):** an existing flat `.pipeline-state.json` with
   no `epic` key still validates against the patched
   `pipeline-state-schema.json`; a state file with `"epic": "x"` and
   `"currentStage": "forge-verify-epic"` also validates.
2. **Resolution (REQ-DIR-03):** a flat feature and a nested member coexist under
   `{specsDir}`; running any stage skill on each resolves to the correct directory, and the
   skill reads/writes there. A duplicated bare name surfaces an `ambiguous` stop, not a
   wrong-directory write.
3. **Context injection (REQ-CTX-01/02):** running forge-1/2/3 on a member with a completed
   direct dependency loads EPIC.md + that feature's charter + the dep's PRD/tech-spec, and
   does **not** load a transitive dep's specs.
4. **Blocked-loop gate (REQ-ORCH-04):** running forge-5-loop on a member with an
   incomplete dependency fires the `AskUserQuestion` warning listing the unmet deps and
   requires an explicit "Proceed anyway"; the same loop on a feature with all deps complete
   shows **no** epic prompt.
5. **Handoff (REQ-ORCH-01/02/03):** completing a member's loop announces completion,
   offers impl-verify, and — via render-status — identifies the correct next actionable
   feature per the dependency graph (not a still-blocked one), offering to author its PRD
   if absent; multiple unblocked features are presented for serial selection.
6. **Dashboard from disk (REQ-VIS-01, REQ-ROBUST-01):** in a **fresh session** (no
   in-memory state), `/feature-forge:forge {epic}` reconstructs the full dashboard —
   per-feature stage/status, blocked vs actionable, rollup, next command — purely from the
   manifest + member `.pipeline-state.json` files. Editing a member's state file then
   re-rendering reflects the change with no refresh step (REQ-STATE-02).
7. **2-tier discovery (REQ-VIS-02):** `/feature-forge:forge` with no argument lists epics
   (with `complete/total` rollups) above standalone features; nested members are not listed
   as standalone.
8. **Lifecycle (REQ-ORCH-05):** `forge pause {epic}` sets the manifest `status` to
   `paused` and does **not** silently change any member's `pipelineStatus`; the
   relationship is surfaced via `AskUserQuestion`.
9. **Verify epic mode (REQ-VERIFY-01):** `forge-verify {epic} epic` runs CHECK-E01..E08,
   writes `{specsDir}/{epic}/.verification/VERIFY-epic-{date}.md`, and records
   `stages.forge-verify-epic`; a hand-injected cycle is caught by E02, a back-pointer
   mismatch by E07.
10. **Docs offer (REQ-DOCS-01):** forge-6-docs on a member offers the epic-level doc at
    `{docsDir}/{epic}/` **only** when every member is complete-for-orchestration.
11. **Compatibility (REQ-COMPAT-01/02/03):** in a project with **no** epics, every stage
    skill, the navigator, forge-verify, forge-fix, and forge-researcher behave
    byte-for-byte as before — no epic prompt, no new glob match, no schema-required field,
    no behavioral diff; rauf and the backlog schema are untouched.
