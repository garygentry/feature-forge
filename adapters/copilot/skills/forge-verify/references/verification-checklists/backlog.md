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

### Dependency Topology
- [ ] **CHECK-B28**: **Fragile dependency topology — a single root gates a large fraction of the
  backlog, or the chain is deep** (#194). *Advisory heuristic — severity `improvement`, **never**
  `error`/`gap`, and it **never blocks**. **not-applicable** when no trigger fires or the graph is
  trivial (0–1 items, or no dependsOn edges at all).* A backlog where one root item gates most of
  the tree, or whose critical chain is deep relative to its size, has a single point of near-total
  failure: one defect in that root (or anywhere on the long chain) strands the dependent subtree —
  the loop-recovery incident was 3 roots gating 81% of 16 items down a 13-deep chain, and it passed
  both authoring and verification without comment. Verify by computing, never by eyeballing:
  1. **Compute the topology.** Feed the runner's item array to the scripted metric:

     ```
     rauf backlog list . --backlog {resolvedBacklogDir} --json | python3 "$R/scripts/forge-session.py" backlog-topology --items-stdin --json
     ```

     Read `itemCount`, `rootCount`, `roots[].gatedCount`, `maxChainDepth`, and `warnings`. If
     `itemCount <= 1` or there are no `dependsOn` edges, this check is **not-applicable**.
  2. **Read the warnings, do not re-derive them.** The metric applies the fixed thresholds
     (`single-root-fanout` when any root gates ≥50% of items; `chain-depth` when `maxChainDepth`
     ≥50% of item count). If `warnings` is empty, record **pass** (topology computed, no fragile
     shape). Do not invent a different threshold — the constants are canonical
     (`forge-session.py`).
  3. **Report each fired warning as one `improvement` finding.** For `single-root-fanout`, name the
     root and its `gatedCount`/`itemCount` ("root 1 gates 13/16 items") and suggest splitting that
     root's subtree or introducing an intermediate. For `chain-depth`, name
     `maxChainDepth`/`itemCount` and suggest flattening. **Report, do not repair** — this is a
     heads-up to the author, never a blocking gate. Cite the metric output the claim was derived
     from.

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

### Work-Order Cardinality

> **When this fires:** only when the backlog, or an artifact the backlog derives from,
> **declares an enumerated per-item work list that claims to cover a set**. A backlog
> with no such list yields **not-applicable** — absence of a declared list is never a
> hard fail. The defect this catches is not a wrong item; it is a **missing** one, and
> a missing entry is invisible to every reader who checks the entries that are present.

- [ ] **CHECK-B29**: **A declared per-item work list covers the whole set it claims — name what is missing** (#170).
  *Heuristic with a mechanical method — **not-applicable** when no enumerated per-item work
  list is declared anywhere in the backlog or the artifacts it derives from; absence is
  **never a hard fail**. A true omission is a `gap` (blocking): an unreviewed member is
  missing coverage.* When the backlog — or an artifact it derives from, such as a
  hand-authored work order, a per-item review sheet, a "one entry per item" table in a
  plan the backlog cites, or a stated total in a summary line — declares an enumerated
  list **claiming coverage of a set**, the list's cardinality must be **re-derived from
  the actual member set** and never trusted from the list's own header, its numbering, or
  a stated total. In the incident behind this check a hand-authored work order enumerated
  **15 of 16** artifacts; it passed authoring and a full review, and the dropped
  sixteenth would have been published unreviewed. Verify by re-deriving, never by
  eyeballing:
  1. **Find the declared lists.** Scan the backlog and the artifacts it cites for an
     enumerated list that claims coverage of a nameable set — one entry per backlog item,
     per spec document, per requirement id, per generated artifact, per file to touch. The
     coverage claim reads as "one per …", "all …", "every …", "each …", or as a stated
     total ("16 artifacts", "covers the full set"). If **no** such list exists, this check
     is **not-applicable** — record it and move on.
  2. **Re-derive the member set from its own source of record.** Build the actual set
     independently of the list: backlog items from `backlog.json`, spec documents from the
     spec directory listing, requirement ids from the PRD, artifacts from the paths the
     items name. Count what you built; do not adopt any count the list asserts about
     itself.
  3. **Difference both directions and name every discrepancy.** Report each member of the
     re-derived set that has **no** entry in the declared list **by name** — the item id,
     file path, or requirement id — never as a count delta ("one short", "off by one"),
     which hands the reader back exactly the derivation this check just performed. Report
     the reverse direction too: a list entry naming something absent from the re-derived
     set is a stale entry.
  4. **Severity, and what to report.** A named omission is a `gap`. A stale entry, or a
     stated total that disagrees with a list whose membership is nevertheless complete, is
     an `inconsistency`. Every finding names the list, the source of record the set was
     re-derived from, and each missing or stale member by name. **Report, do not repair** —
     authoring the missing entry belongs to the fix pass.

