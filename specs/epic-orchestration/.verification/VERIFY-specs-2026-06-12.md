# Verification Report: epic-orchestration (specs)
Date: 2026-06-12
Pipeline Stage: forge-3-specs (complete) → forge-verify-specs
Artifacts Reviewed: PRD.md, tech-spec.md, 00-core-definitions.md, 01-architecture-layout.md, 02-manifest-helper-cli.md, 03-forge-0-epic-stage.md, 04-pipeline-integration.md, 05-testing-strategy.md, TRACEABILITY.md

Method: deterministic traceability scan (`validate-traceability.py`) + 5 parallel `forge-verifier` subagents over disjoint dimension groups (types/contracts, architecture/cross-ref, coverage/traceability, testing, integration/edge/errors). All 38 specs-mode checks executed.

## Summary
- Total findings: 8
- Gaps: 5
- Inconsistencies: 0
- Improvements: 1
- Errors: 2

Deterministic traceability: 32 requirements, 0 uncovered, 0 orphaned references — clean. The semantic findings below are the gaps the script cannot judge. Overall the spec suite is strong (per-REQ coverage tables in every doc, valid Python type defs, consistent error/exit-code model); the issues are localized.

## Findings

### V-001: Two broken section references in 00-core-definitions.md point into the wrong section of 02
- **Severity:** error
- **Location:** 00-core-definitions.md §7 (line 330) and §8 (lines 347–348)
- **Issue:** Both outbound references locating `render-status` / the completion predicate / the derived-sets output object in 02-manifest-helper-cli.md are wrong:
  - §7 line 330: "implemented once in `render-status` (02-manifest-helper-cli.md §5)" — but 02 §5 is "Resolution & Uniqueness." The completion predicate lives in **02 §8.1**; the `render-status` subcommand is at **02 §6.4** with status derivation in **02 §8**.
  - §8 lines 347–348: "the full `render-status` output object … is defined in 02-manifest-helper-cli.md §5.4" — there is no §5.4 in 02. The render-status JSON output object is at **02 §8.4**.
- **Suggested fix:** In 00 §7 line 330 change "02-manifest-helper-cli.md §5" → "02-manifest-helper-cli.md §8.1 (predicate) / §6.4 (`render-status` subcommand)". In 00 §8 line 348 change "02-manifest-helper-cli.md §5.4" → "02-manifest-helper-cli.md §8.4".
- **References:** 02-manifest-helper-cli.md §6.4 (line 644), §8.1 (line 801), §8.4 (line 906)
- **Checklist:** CHECK-S15

### V-002: `add-feature` test invocation omits the required `--charter` option
- **Severity:** error
- **Location:** 05-testing-strategy.md §3.1 `test_valid_manifest_round_trip`
- **Issue:** The test calls `run_cli("add-feature", epic, "metrics", "--specs-dir", str(specs))` and asserts `returncode == 0`. But 02 §7.1 specifies `add-feature <epic> <name> --charter TEXT [...]` with `--charter` **required**. Since `main()` uses argparse (02 §9), a missing required option yields a usage error → **exit 2** (00 §9), not exit 0. The test would fail against a spec-conformant helper, and the round-trip never exercises a successful add.
- **Suggested fix:** Add the charter arg: `run_cli("add-feature", epic, "metrics", "--charter", "Metrics collection leaf feature.", "--specs-dir", str(specs))`, keeping the `returncode == 0` assertion. Optionally add a negative case asserting omission of `--charter` yields exit 2 (reinforces §3.13).
- **References:** 02-manifest-helper-cli.md §7.1 (line 715), §9; 00-core-definitions.md §9
- **Checklist:** CHECK-S37

### V-003: `forge-verify-epic` stage-entry persistence location is unspecified (dangling cross-reference)
- **Severity:** gap
- **Location:** 04-pipeline-integration.md §9.4; 03-forge-0-epic-stage.md §8.2
- **Issue:** 04 §9.4 requires recording the `forge-verify-epic` stage entry (`status = findings-reported|passed`, plus `findingsFile`/`findingsCount`/`verifiedAt`) but defers WHERE it persists: "Where epic-level stage state is persisted … is settled by `02`/`03`." Neither 02 nor 03 settles it. 03 §8.2 states the epic subtree has no `.pipeline-state.json` of its own and only handles the `forge-0-epic` entry in member states. There is no member-agnostic home for an epic-wide verify result, so an implementer of forge-verify epic mode has no defined target file.
- **Suggested fix:** Add a subsection to 03 §8.2 (or new §8.4) defining the home for the `forge-verify-epic` stage entry. Recommended: a dedicated epic-level marker `{specsDir}/{epic}/.epic-state.json` (analogous to `.pipeline-state.json`) or an epic-scoped `verification` block — pick one, define its schema, and update 04 §9.4 to reference it instead of deferring. Resolve the dangling "settled by 02/03" sentence.
- **References:** 04 §9.4, 03 §8.2, 00-core-definitions.md §3, 01-architecture-layout.md §4.3
- **Checklist:** CHECK-S22, CHECK-S25, CHECK-S26

### V-004: Empty epic (`features: []`) edge case is unhandled in render-status, handoff, and docs-offer
- **Severity:** gap
- **Location:** 02-manifest-helper-cli.md §8.3 (`render_status`); 04-pipeline-integration.md §7.2 step 3, §10
- **Issue:** The schema permits a zero-member epic (`features` required but may be empty; all members removable via `remove-feature`). No spec defines behavior. `render_status` yields `rollup {complete:0,total:0}`, `nextCommand:null`. The handoff (§7.2 step 3) and docs-offer (§10) gate on `rollup.complete == rollup.total`, which is `0 == 0 → True` for an empty epic — so an empty epic is reported "fully complete," potentially offering `forge-6-docs` for an epic with no features (vacuous-truth bug).
- **Suggested fix:** In 02 §8.3 specify the zero-feature return shape. In 04 §7.2 step 3 and §10 change the completion gate from `rollup.complete == rollup.total` to `rollup.total > 0 AND rollup.complete == rollup.total` so an empty epic never triggers docs-offer/completion. Have the navigator/handoff treat `total == 0` as "empty epic — add features."
- **References:** 02 §8.3, §8.4, 04 §7.2, §10, 00-core-definitions.md §2.1
- **Checklist:** CHECK-S28, CHECK-S29

### V-005: Self-dependency (`dependsOn` includes own name) not explicitly classified or rejected
- **Severity:** gap
- **Location:** 02-manifest-helper-cli.md §4 (`find_cycle`), §6.2 (validate invariant 5); 00-core-definitions.md §2.6
- **Issue:** A feature whose `dependsOn` lists its own `name` is a degenerate self-loop. `find_cycle` would plausibly detect the GRAY back-edge and reconstruct path `["X","X"]`, but this behavior is never stated or tested, and it is ambiguous whether a self-edge should be a `cycle` finding or rejected as a distinct validation error. Edge-case behavior is left implicit.
- **Suggested fix:** Add an explicit invariant to 00 §2.6 and 02 §6.2: a feature's `dependsOn` MUST NOT contain its own `name`; reported as a `cycle` finding with message `cycle: X → X`. Add a `self-dep` fixture to 05-testing-strategy.md asserting `find_cycle` returns `["X","X"]` and `validate` exits 1. If a distinct finding code is preferred, define it in 00 §4.1.
- **References:** 02 §4 (lines 369–378), §6.2, 00 §2.6, 05-testing-strategy.md
- **Checklist:** CHECK-S18, CHECK-S30

### V-006: REQ-COMPAT-03 rauf / backlog-schema-invariance half is covered only by passing mention
- **Severity:** gap
- **Location:** TRACEABILITY.md row REQ-COMPAT-03; 04-pipeline-integration.md §6; 01-architecture-layout.md
- **Issue:** REQ-COMPAT-03 (P0) has two obligations: (a) per-feature backlogs stay independent / deps resolved at feature granularity, and (b) the loop-runner contract (rauf) and the backlog **schema** require no changes. Part (a) is substantively covered (04 §6.2 per-feature `{backlogDir}/{feature}/` rule). Part (b) is only asserted in passing ("rauf itself is unchanged" prose + §11 item 11) with no section demonstrating *why* no rauf/schema change is needed. 01-architecture-layout.md is cited but contains no rauf-contract-invariance section — the "passing mention" pattern CHECK-S38 targets.
- **Suggested fix:** Add §6.3 "rauf / backlog-schema invariance" to 04-pipeline-integration.md stating: the backlog at `{resolvedFeatureDir or {backlogDir}/{feature}}/backlog.json` uses the unmodified existing schema; rauf is invoked with the same per-feature backlog-path contract as today; epic dependency resolution completes before the loop launches (§7.1 gate) and never reaches rauf — so runner contract and schema are provably unchanged. Cross-link from §11 item 11. Reconcile the TRACEABILITY.md REQ-COMPAT-03 row if the 01 citation gains no substantive backing section.
- **References:** PRD.md REQ-COMPAT-03; 04 §6.2, §11 item 11; 01-architecture-layout.md; tech-spec §5.7
- **Checklist:** CHECK-S01, CHECK-S38

### V-007: `render-status` output object is a named contract but has no typed, per-field definition
- **Severity:** gap
- **Location:** 00-core-definitions.md §1 (contract table) & §8; 02-manifest-helper-cli.md §8.3 (`render_status` signature) & §8.4
- **Issue:** 00 §1 lists "render-status output" as a first-class CLI JSON contract, but unlike `Finding` and `FeatureStatus` (typed `TypedDict`s with per-field `Attributes:` docstrings), the output object is only expressed as a `-> dict` annotation (02 §8.3) and a by-example JSON blob (02 §8.4). Its fields (`epic`, `status`, `features`, `actionable`, `parallelEligible`, `rollup`, `nextCommand`) have no field-level type/documentation definition; `nextCommand` nullability and `rollup` `{complete,total}` shape are only inferable from the example. Violates CHECK-S13 (every struct field documented).
- **Suggested fix:** Add a `RenderStatus` `TypedDict` (with nested `Rollup` `TypedDict`) in 02 §8.4 with a Google-style docstring documenting every field: `epic: str`, `status: Literal["active","paused","abandoned","complete"]`, `features: list[FeatureStatus]`, `actionable: list[str]`, `parallelEligible: list[str]`, `rollup: Rollup` (`{"complete": int, "total": int}`), `nextCommand: str | None`. Change `render_status`'s return annotation from `-> dict` to `-> RenderStatus`. Optionally name the type in the 00 §1 contract row.
- **References:** 00 §1, §8; 02 §8.3 (line 868), §8.4 (lines 906–930); compare typed `FeatureStatus` (00 §5), `Finding` (00 §4.1)
- **Checklist:** CHECK-S13 (primary), CHECK-S10

### V-008: `render-status` member-state torn-read concurrency not explicitly addressed
- **Severity:** improvement
- **Location:** 02-manifest-helper-cli.md §8.2 ("Reading member state safely"); PRD REQ-ROBUST-03
- **Issue:** §8.2 downgrades a corrupt/missing member `.pipeline-state.json` to `not-started`. PRD REQ-ROBUST-03 scopes concurrency out only for *manifest* writes by the helper; member state files are written by other stage skills the helper doesn't control, so a `render-status` during a concurrent member write could hit a torn read. The try/except → `not-started` downgrade does handle this, but the spec never states that this downgrade is *also* the torn-read mitigation, leaving a reviewer unsure the case was considered.
- **Suggested fix:** Add one sentence to 02 §8.2: a partially-written member state parses as corrupt and is treated as `not-started` for that render with no effect on the rest of the dashboard; member-state writes are out of the helper's atomicity scope (REQ-ROBUST-03 covers only manifest writes). Optionally cross-reference the Pipeline State Protocol.
- **References:** 02 §8.2, PRD REQ-ROBUST-03, 04 §7
- **Checklist:** CHECK-S27

## Fix Execution Plan

### User Decisions Required
- **V-003 [RESOLVED 2026-06-12]:** persistence home for the `forge-verify-epic` stage entry → **dedicated `{specsDir}/{epic}/.epic-state.json`** (user choice). Defined in 03 §8.2.

All other fixes are documentation/spec completeness edits applyable directly.

### Execution Steps

#### Step 1: Fix broken cross-references in 00-core-definitions.md
- **Files:** specs/epic-orchestration/00-core-definitions.md
- **Addresses:** V-001
- **Checklist:** CHECK-S15
- **Action:** §7 line 330: "02-manifest-helper-cli.md §5" → "02-manifest-helper-cli.md §8.1 (predicate) / §6.4 (`render-status` subcommand)". §8 line 348: "02-manifest-helper-cli.md §5.4" → "02-manifest-helper-cli.md §8.4".
- **Depends on:** none
- **Rationale:** Pure reference correction; isolated; unblocks readers navigating to the predicate/output object.

#### Step 2: Type the render-status output object
- **Files:** specs/epic-orchestration/02-manifest-helper-cli.md (§8.3, §8.4); optionally 00-core-definitions.md §1 contract row
- **Addresses:** V-007
- **Checklist:** CHECK-S13, CHECK-S10
- **Action:** Add `RenderStatus` + nested `Rollup` `TypedDict`s with per-field docstrings in §8.4; change `render_status` return annotation to `-> RenderStatus`.
- **Depends on:** Step 1 (same files region as the §8.x refs; apply after refs are corrected to avoid churn)
- **Rationale:** Grouped with other §8 edits; establishes the typed contract the empty-epic fix (Step 3) will reference.

#### Step 3: Handle the empty-epic edge case
- **Files:** specs/epic-orchestration/02-manifest-helper-cli.md §8.3; 04-pipeline-integration.md §7.2 step 3, §10
- **Addresses:** V-004
- **Checklist:** CHECK-S28, CHECK-S29
- **Action:** Specify the zero-feature `render_status` return; change completion gates to `rollup.total > 0 AND rollup.complete == rollup.total`; treat `total == 0` as "empty epic — add features."
- **Depends on:** Step 2 (references the now-typed `rollup`)
- **Rationale:** Touches the same render-status contract; ordered after typing it.

#### Step 4: Specify self-dependency handling
- **Files:** specs/epic-orchestration/00-core-definitions.md §2.6, §4.1; 02-manifest-helper-cli.md §6.2; 05-testing-strategy.md
- **Addresses:** V-005
- **Checklist:** CHECK-S18, CHECK-S30
- **Action:** Add invariant: `dependsOn` MUST NOT contain own `name`; report as `cycle: X → X`. Add `self-dep` test fixture asserting `find_cycle` → `["X","X"]` and `validate` exit 1.
- **Depends on:** none
- **Rationale:** Independent validation-semantics gap spanning core-defs + CLI + tests.

#### Step 5: Add rauf / backlog-schema invariance subsection
- **Files:** specs/epic-orchestration/04-pipeline-integration.md (§6, new §6.3, §11); optionally TRACEABILITY.md
- **Addresses:** V-006
- **Checklist:** CHECK-S01, CHECK-S38
- **Action:** Add §6.3 asserting unchanged backlog schema + rauf path contract + pre-loop dependency resolution; cross-link §11 item 11; reconcile the TRACEABILITY REQ-COMPAT-03 row.
- **Depends on:** none
- **Rationale:** Closes the only passing-mention traceability gap; localized to the integration doc.

#### Step 6: Define forge-verify-epic stage-entry persistence home
- **Files:** specs/epic-orchestration/03-forge-0-epic-stage.md §8.2 (or new §8.4); 04-pipeline-integration.md §9.4; possibly 00-core-definitions.md §3, 01-architecture-layout.md §4.3
- **Addresses:** V-003
- **Checklist:** CHECK-S22, CHECK-S25, CHECK-S26
- **Action:** After the user decision, define the chosen persistence target (recommended `{specsDir}/{epic}/.epic-state.json`) and its schema; update 04 §9.4 to reference it; remove the "settled by 02/03" deferral.
- **Depends on:** User decision (above)
- **Rationale:** Resolves a dangling integration contract; needs the user's persistence-model choice first.

#### Step 7: Document member-state torn-read tolerance
- **Files:** specs/epic-orchestration/02-manifest-helper-cli.md §8.2
- **Addresses:** V-008
- **Checklist:** CHECK-S27
- **Action:** Add one sentence stating the corrupt→`not-started` downgrade also tolerates concurrent torn reads; member-state writes are outside helper atomicity scope (REQ-ROBUST-03).
- **Depends on:** none
- **Rationale:** Minor clarification; lowest priority.

## Fix Progress

- Step 1: [APPLIED] 2026-06-12 — Fixed broken cross-refs in 00 §7 (→ 02 §8.1/§6.4) and 00 §8 (→ 02 §8.4). (V-001)
- Step 2: [APPLIED] 2026-06-12 — Added `RenderStatus`/`Rollup` TypedDicts with per-field docstrings in 02 §8.4; changed `render_status` return annotation to `-> RenderStatus`. (V-007)
- Step 3: [APPLIED] 2026-06-12 — Specified empty-epic (`features: []`) return in 02 §8.3; changed completion/docs gates in 04 §7.2 step 3 and §10 to `rollup.total > 0 AND rollup.complete == rollup.total`. (V-004)
- Step 4: [APPLIED] 2026-06-12 — Self-dependency invariant added to 00 §2.6 inv. 5, 02 §4 (`find_cycle` docstring) + §6.2 (`validate`); added `test_find_cycle_self_dependency` to 05 §3.3. (V-005)
- Step 5: [APPLIED] 2026-06-12 — Added 04 §6.3 "rauf / backlog-schema invariance"; cross-linked §11 item 11. (V-006)
- Step 6: [APPLIED] 2026-06-12 — Defined `{specsDir}/{epic}/.epic-state.json` (with schema) in 03 §8.2 as the home for `forge-verify-epic`; updated 04 §9.4 and §11 item 9 to reference it. (V-003)
- Step 7: [APPLIED] 2026-06-12 — Documented member-state torn-read tolerance in 02 §8.2. (V-008)
- Extra: [APPLIED] 2026-06-12 — Added required `--charter` to the `add-feature` invocation in 05 §3.1 (error finding V-002, omitted from numbered plan but applied). (V-002)
