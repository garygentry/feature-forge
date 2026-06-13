# Verification Report: epic-orchestration (specs) — re-verification (r2)
Date: 2026-06-12
Pipeline Stage: forge-3-specs (complete) → forge-verify-specs (re-verify after fix pass)
Artifacts Reviewed: PRD.md, tech-spec.md, 00-core-definitions.md, 01-architecture-layout.md, 02-manifest-helper-cli.md, 03-forge-0-epic-stage.md, 04-pipeline-integration.md, 05-testing-strategy.md, TRACEABILITY.md

Method: deterministic traceability scan + 5 parallel `forge-verifier` subagents (same dimension split as round 1), each tasked to (a) confirm the corresponding round-1 fix held and (b) hunt for regressions the fix pass introduced. This report supersedes the round-1 report `VERIFY-specs-2026-06-12.md` (whose 8 findings are all CONFIRMED RESOLVED below).

## Round-1 fix confirmation
All 8 prior findings verified resolved:
- **V-001** (broken 00 §7/§8 refs) → fixed; refs now resolve to 02 §8.1/§6.4/§8.4. ✓
- **V-002** (`add-feature` test missing `--charter`) → fixed; matches 02 §7.1, exit 0 correct. ✓
- **V-003** (epic-state persistence home) → `.epic-state.json` defined in 03 §8.2. ✓ (residual ref bug — see V-001 below)
- **V-004** (empty-epic) → 02 §8.3 + gated `rollup.total > 0 AND complete == total` in 04 §7.2/§10. ✓
- **V-005** (self-dependency) → invariant in 00 §2.6 + 02 §6.2; `find_cycle` self-loop returns `["x","x"]`, test added. ✓
- **V-006** (REQ-COMPAT-03 invariance) → substantive 04 §6.3 added. ✓
- **V-007** (untyped render-status output) → `RenderStatus`/`Rollup` TypedDicts in 02 §8.4. ✓ (not propagated to 01 skeleton — see V-003 below)
- **V-008** (member torn-read) → documented in 02 §8.2. ✓

Deterministic traceability: 32 requirements, 0 uncovered, 0 orphaned — clean.

## Summary
- Total findings: 5
- Gaps: 1
- Inconsistencies: 3
- Improvements: 0
- Errors: 1

Four are mechanical leftovers/regressions from the fix pass; one (V-005) is a genuine unspecified-mechanism gap. Coverage and testing dimensions are otherwise clean.

## Findings

### V-001: `.epic-state.json` atomic-write cross-reference points to the wrong 02 section
- **Severity:** error
- **Location:** 03-forge-0-epic-stage.md §8.2 (`.epic-state.json` block, "Writers use the same atomic-write helper as the manifest (02 §3.2)")
- **Issue:** Introduced by the V-003 fix. 02 §3.2 is `load_manifest` (the read path); the atomic-write helper `atomic_write` is defined in **02 §3.3**. The cross-reference lands an implementer on the loader, not the writer. (Flagged independently by both the cross-reference and integration verifiers.)
- **Suggested fix:** Change "(02 §3.2)" → "(02 §3.3 `atomic_write`)" in 03 §8.2.
- **References:** 02-manifest-helper-cli.md §3.2 (`load_manifest`), §3.3 (`atomic_write`)
- **Checklist:** CHECK-S15, CHECK-S19, CHECK-S26

### V-002: 04 §6.3 cross-link labels the target "§11" but means the Verification section's item 11
- **Severity:** inconsistency
- **Location:** 04-pipeline-integration.md §6.3 (final sentence: "asserted in the §11 compatibility verification (item 11)")
- **Issue:** Introduced by the V-006 fix. Heading **§11** is "forge-fix + forge-researcher — Resolution & Glob Widening" (subsections §11.1/§11.2, no numbered items). The intended target is **item 11 of the document's unnumbered `## Verification` section** ("Compatibility (REQ-COMPAT-01/02/03)…"). The "§11" label collides with the real §11 heading and misdirects the reader.
- **Suggested fix:** Change "asserted in the §11 compatibility verification (item 11)" → "asserted in this document's Verification section, item 11 (Compatibility, REQ-COMPAT-01/02/03)." Do not call it "§11."
- **References:** 04 §6.3; 04 `## Verification` item 11; 04 §11 heading
- **Checklist:** CHECK-S15

### V-003: Architecture skeleton still annotates `render_status -> dict` (V-007 fix not propagated)
- **Severity:** inconsistency
- **Location:** 01-architecture-layout.md §3 (module skeleton, `render_status(epic_dir, specs_dir) -> dict`)
- **Issue:** The V-007 fix introduced `RenderStatus` and changed `render_status`'s return to `-> RenderStatus` in 02 §8.3/§8.4, but the 01 skeleton still shows the exact untyped `-> dict` that V-007 set out to eliminate. The return contract is now inconsistent across 01 vs 02, and `RenderStatus`/`Rollup` are absent from the skeleton's typed-structures inventory.
- **Suggested fix:** Change the skeleton line to `render_status(epic_dir, specs_dir) -> RenderStatus   # 00 §5, §8`. Optionally add `Rollup`/`RenderStatus` to the skeleton's typed-structures comment.
- **References:** 02-manifest-helper-cli.md §8.3, §8.4; 00 §5/§8
- **Checklist:** CHECK-S10, CHECK-S12

### V-004: `derive_status` return type conflicts across three documents
- **Severity:** inconsistency
- **Location:** 01-architecture-layout.md §3 (`derive_status(feature_dir) -> DerivedStatus`) and 05-testing-strategy.md §3.7 (`test_derive_status_branches`: `status = derive_status(...); assert (status == "complete") is expect_complete`)
- **Issue:** The canonical type doc 00 §5 and the implementation signature 02 §8.1 both declare `derive_status(feature_dir: Path) -> FeatureStatus` (a TypedDict with `name`/`stage`/`status`/`blocked`/`unmetDeps`). But (a) the 01 skeleton annotates `-> DerivedStatus` (the inner coarse-status `Literal`, not the function's return shape), and (b) the 05 §3.7 test compares the whole return value against the string `"complete"` — which, against a `FeatureStatus` dict, is always `False`, so the test as written cannot pass on a spec-conformant helper. This is the same class of dict-vs-string contract bug as the earlier V-002. (Pre-existing in 01; surfaced now alongside the fix-pass review. The 05 test was not touched by round 1.)
- **Suggested fix:** Treat 00 §5 / 02 §8.1 (`-> FeatureStatus`) as canonical. (1) In 01 §3 change `-> DerivedStatus` to `-> FeatureStatus  # 00 §5` (and fix the misattributed `# §7 completion rule` comment — the §7 predicate is `is_complete_for_orchestration`). (2) In 05 §3.7 change the assertion to read the coarse field, e.g. `status = derive_status(...); assert (status["status"] == "complete") is expect_complete`, or assert against `is_complete_for_orchestration(...)` if the intent is the orchestration bool (the table's last column). Pick the one that matches the table semantics and state it.
- **References:** 00-core-definitions.md §5 (`FeatureStatus`, `DerivedStatus`), 02-manifest-helper-cli.md §8.1 (`derive_status -> FeatureStatus`, `is_complete_for_orchestration`)
- **Checklist:** CHECK-S10, CHECK-S12, CHECK-S37

### V-005: `.epic-state.json` write mechanism and its error path are unspecified for the prose writer
- **Severity:** gap
- **Location:** 03-forge-0-epic-stage.md §8.2 and 04-pipeline-integration.md §9.4 (Step 6 state write)
- **Issue:** The V-003 fix made `.epic-state.json` a real on-disk artifact written by **forge-verify epic mode** (a prose skill) and says writers "reuse the manifest atomic-write helper." But `atomic_write` (02 §3.3) is an **internal function** of `epic-manifest.py`, and the helper exposes **no CLI subcommand** that writes `.epic-state.json` (its mutators only write `epic-manifest.json`, 02 §2.3/§7). So the prose skill has no callable surface to "reuse" — the actual write mechanism and its I/O-failure handling for `.epic-state.json` are undefined.
- **Suggested fix:** In 03 §8.2 (or 04 §9.4) specify concretely how the prose skill writes the file. Recommended option (a): the skill writes `.epic-state.json` directly using the same temp-file + `os.replace` atomic pattern other prose stages use for `.pipeline-state.json`, and on I/O failure reports and leaves any prior state intact — mirroring the existing Pipeline State Protocol. (Option (b): add an `epic-state` write subcommand to 02's CLI, expanding the helper surface — less consistent with how prose stages already write their own state.) Replace the "same atomic-write helper" wording, which implies a callable entry point that does not exist.
- **References:** 02-manifest-helper-cli.md §2.3 (subcommand list — no epic-state writer), §3.3 (`atomic_write` internal), 04 §9.4, references/pipeline-state-schema.json
- **Checklist:** CHECK-S18, CHECK-S19, CHECK-S25

## Fix Execution Plan

### User Decisions Required
- **V-005 [RESOLVED 2026-06-12]:** write mechanism for `.epic-state.json` → **(a) prose skill writes it directly** via temp-file + `os.replace`, consistent with existing `.pipeline-state.json` writes; helper surface unchanged. Specified in 03 §8.2.

All other findings (V-001..V-004) are mechanical and applyable directly.

### Execution Steps

#### Step 1: Fix the two introduced cross-reference defects
- **Files:** specs/epic-orchestration/03-forge-0-epic-stage.md (§8.2); specs/epic-orchestration/04-pipeline-integration.md (§6.3)
- **Addresses:** V-001, V-002
- **Checklist:** CHECK-S15
- **Action:** In 03 §8.2 change "(02 §3.2)" → "(02 §3.3 `atomic_write`)". In 04 §6.3 change "asserted in the §11 compatibility verification (item 11)" → "asserted in this document's Verification section, item 11 (Compatibility, REQ-COMPAT-01/02/03)."
- **Depends on:** none
- **Rationale:** Both are pure reference corrections, no semantic change.

#### Step 2: Propagate the render-status type to the architecture skeleton
- **Files:** specs/epic-orchestration/01-architecture-layout.md (§3)
- **Addresses:** V-003
- **Checklist:** CHECK-S10, CHECK-S12
- **Action:** Change `render_status(epic_dir, specs_dir) -> dict` → `-> RenderStatus  # 00 §5, §8`; optionally list `Rollup`/`RenderStatus` in the typed-structures comment.
- **Depends on:** none
- **Rationale:** Completes the V-007 fix that stopped at 02.

#### Step 3: Reconcile `derive_status` return type across 01 and 05
- **Files:** specs/epic-orchestration/01-architecture-layout.md (§3); specs/epic-orchestration/05-testing-strategy.md (§3.7)
- **Addresses:** V-004
- **Checklist:** CHECK-S10, CHECK-S12, CHECK-S37
- **Action:** In 01 §3 change `derive_status(feature_dir) -> DerivedStatus` → `-> FeatureStatus  # 00 §5` and fix the `# §7 completion rule` comment. In 05 §3.7 change the assertion to `status["status"] == "complete"` (or switch to `is_complete_for_orchestration(...)` to match the table's complete-for-orchestration column) and note which semantics is intended.
- **Depends on:** none
- **Rationale:** Aligns the skeleton and the test with the canonical `-> FeatureStatus` contract; prevents a test that cannot pass.

#### Step 4: Specify the `.epic-state.json` write mechanism
- **Files:** specs/epic-orchestration/03-forge-0-epic-stage.md (§8.2); possibly specs/epic-orchestration/04-pipeline-integration.md (§9.4)
- **Addresses:** V-005
- **Checklist:** CHECK-S18, CHECK-S19, CHECK-S25
- **Action:** After the user decision, document the chosen write path. For option (a): state the prose skill writes `.epic-state.json` via temp-file + `os.replace`, lazily created, and on I/O failure reports + leaves prior state intact; replace the "reuse the helper's atomic write" wording. For option (b): add the `epic-state` subcommand to 02 §2.3/§7 and reference it.
- **Depends on:** User decision (above)
- **Rationale:** Closes the only genuine mechanism gap; needs the user's write-surface choice.

## Fix Progress

- Step 1: [APPLIED] 2026-06-12 — V-001: 03 §8.2 atomic-write ref corrected (02 §3.2 → §3.3). V-002: 04 §6.3 cross-link changed from "§11 … item 11" to "this document's Verification section, item 11".
- Step 2: [APPLIED] 2026-06-12 — V-003: 01 §3 skeleton `render_status` annotation `-> dict` → `-> RenderStatus`; Rollup/RenderStatus added to typed-structures comment.
- Step 3: [APPLIED] 2026-06-12 — V-004: 01 §3 `derive_status -> DerivedStatus` → `-> FeatureStatus` (+ added `is_complete_for_orchestration(state) -> bool` for the §7 rule); 05 §3.7 assertion changed to `feature_status["status"] == "complete"` (was comparing the dict to a string).
- Step 4: [APPLIED] 2026-06-12 — V-005 [decision (a)]: 03 §8.2 now specifies the prose stage skill writes `.epic-state.json` directly via temp-file + os.replace, reports + preserves prior state on I/O failure; removed the misleading "reuse the helper's atomic write" wording (the helper exposes no such entry point).
