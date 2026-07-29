# Backlog Verification Checklist

Detailed checklist for the **backlog** verification mode, loaded by the `forge-verifier` leaf subagent dispatched for that mode. Execute EVERY check — do not skip.

> **Stack-specific details:** When a stack profile exists at `references/stacks/{stack}.md`, load it alongside this checklist for language-specific check criteria (e.g., what "valid syntax" means, what the type check command is, how module exports work).

## Backlog Mode Checklist

### Schema Compliance
- [ ] **CHECK-B01**: backlog.json is valid JSON
- [ ] **CHECK-B02**: Every item has all required fields: id, type, priority, title, description, acceptanceCriteria, status, dependsOn, specReferences
- [ ] **CHECK-B03**: All `id` values are unique
- [ ] **CHECK-B04**: All `type` values are valid (feature, bugfix, chore, etc.)
- [ ] **CHECK-B05**: All `priority` values are valid numbers
- [ ] **CHECK-B06**: All `status` values are valid (pending, in-progress, complete, etc.)

### Spec Coverage
- [ ] **CHECK-B07**: Every implementation spec document is referenced by at least one backlog item
- [ ] **CHECK-B08**: Every P0 PRD requirement is covered by at least one backlog item's acceptance criteria
- [ ] **CHECK-B09**: No backlog item references a spec file that doesn't exist
- [ ] **CHECK-B10**: specReferences paths are valid relative paths to actual files

### Task Quality
- [ ] **CHECK-B11**: Each item is scoped to be completable in a single rauf loop iteration
- [ ] **CHECK-B12**: Descriptions are detailed enough for a fresh agent with no prior context
- [ ] **CHECK-B13**: Acceptance criteria are objectively verifiable (not subjective like "works well")
- [ ] **CHECK-B14**: Each item specifies what files to create or modify

### Dependency Ordering
- [ ] **CHECK-B15**: `dependsOn` references are valid item IDs
- [ ] **CHECK-B16**: No circular dependencies exist
- [ ] **CHECK-B17**: Foundation items (types, scaffold) have no dependencies
- [ ] **CHECK-B18**: Items that depend on types/interfaces reference the item that creates them
- [ ] **CHECK-B19**: Priority ordering is consistent with dependency ordering (dependencies should have equal or higher priority)

### Completeness
- [ ] **CHECK-B20**: There is an item for the initial package scaffold
- [ ] **CHECK-B21**: There is an item for shared types and error hierarchy
- [ ] **CHECK-B22**: There are items for each major subsystem
- [ ] **CHECK-B23**: There are items for integration wiring (not just isolated subsystems)
- [ ] **CHECK-B24**: There are items for tests (or testing is included in each feature item's acceptance criteria)
- [ ] **CHECK-B25**: No large items that try to do too many things (should be broken down)

### Generated-Artifact Freshness
- [ ] **CHECK-B26**: **Generated-artifact freshness vs. `testCommand` `--check` gates** (#145). When a
  project's configured `testCommand` (forge.config.json) gates on **staleness of generated artifacts**
  — sub-commands of the shape `<generator> --check` / `--verify` / `:check` that fail if a checked-in
  generated file is out of date with its source — every backlog item that regenerates *one* gated
  artifact must regenerate (and commit) **all** the sibling artifacts those same `--check` gates
  depend on, or the item will pass locally yet red-gate on the stale-generated check. Verify
  heuristically:
  1. **Enumerate the gates.** String-scan `testCommand` for `--check`-style freshness sub-commands and
     collect the generator/artifact each one guards (e.g. `build-benchmarks --check` guards
     `partner-program-benchmarks`). If the command shape is unrecognized (no parseable `--check`
     tokens), this check is **advisory / not-applicable** — never a hard fail.
  2. **A gate with no regenerator.** If a `--check` gate guards an artifact that **no** backlog item
     regenerates, and some item edits that artifact's *source*, flag a `gap`: the source change will
     trip the freshness gate with nothing scheduled to refresh the output.
  3. **Partial regeneration.** If an item regenerates a proper subset of the artifacts gated by the
     `--check` set it touches (e.g. runs `build-partner-programs` + `build-analysis` but the gate also
     covers `build-benchmarks`), flag an `inconsistency` naming the missing generator(s) and
     recommending they be added to that item's execute + commit sequence. Same posture as the authoring
     guidance in `forge-4-backlog` / rauf `author-backlog`: enumerate the whole `--check`-gated set, not
     just the artifact the item is "about".

### Artifact Lifecycle Consistency
- [ ] **CHECK-B27**: **No test item forcing a lifecycle transition another item forbids** (#150).
  *Advisory heuristic — keyword/artifact-name based; **not-applicable** when no lifecycle vocabulary is
  present, **never** a hard fail.* A **lifecycle state** (draft / published / released / approved /
  reviewed / signed-off / gated) is a downstream-project concept forge does not itself track — but a
  backlog can still encode a **contradiction** about one named artifact: item A pins artifact `X` as
  *draft* / *unpublished* / *unreviewed* while item B asserts (in its acceptance criteria or a test it
  adds) that `X` is *published* / *released* / *approved*, with **no** publishing/review item for `X`
  anywhere in B's dependency closure. That leaves a **test/e2e item as the only thing forcing the
  transition** — and since the autonomous loop can neither publish a package nor stand in for a human
  reviewer, asked to make such a test green it **fabricates** the publication or sign-off (a provenance
  defect a `--review` pass has caught in the wild). Verify heuristically:
  1. **Find lifecycle assertions.** Scan item titles/descriptions/`acceptanceCriteria` for a named
     artifact paired with a lifecycle-state keyword — earlier states (`draft` / `unpublished` /
     `pending review` / `unreleased`) vs later states (`published` / `released` / `approved` / `live` /
     `signed-off` / `gated`). If **no** item carries such vocabulary, this check is **not-applicable**.
  2. **Pair by artifact name.** Group assertions that reference the **same named artifact**. A pair
     where one item requires the *earlier* state and another asserts the *later* state is a candidate.
  3. **Check the dependency closure.** If the later-state item has **no** publish / review / human-gated
     item for that artifact in its transitive `dependsOn`, flag an `inconsistency`: name the artifact,
     both items, and recommend either (a) adding a `dependsOn` on an explicit human-gated publish/review
     item that legitimately produces the state, or (b) re-asserting the state via a dev-build / fixture
     path — never letting a test item be the sole driver of the transition (mirrors the authoring
     guidance in `forge-4-backlog` / rauf `author-backlog`). **Report, do not repair.**

  > **Anti-pattern (visible even where the heuristic can't fire):** a test/e2e item whose pass condition
  > is "artifact `X` is published / approved / reviewed" while the backlog contains no human-gated
  > publish or review item producing that state. The autonomous loop cannot publish or sign off on
  > behalf of a human; asked to make such a test green it will **fabricate** the published/reviewed
  > provenance. Any item asserting a human-gated lifecycle state must trace — via `dependsOn` — to the
  > item that legitimately produces it, or assert the state through a dev-build / fixture path instead.

