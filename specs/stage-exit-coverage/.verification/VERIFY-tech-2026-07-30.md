# Verification Report: stage-exit-coverage (tech)
Date: 2026-07-30
Pipeline Stage: forge-2-tech
Artifacts Reviewed: `specs/stage-exit-coverage/.pipeline-state.json`, `specs/stage-exit-coverage/PRD.md`, `specs/stage-exit-coverage/tech-spec.md`, `scripts/forge-session.py`, `scripts/epic-manifest.py`, `scripts/forge-bootstrap.py`, `scripts/build-adapters.py`

## Summary
- Total findings: 4
- Gaps: 2
- Inconsistencies: 1
- Improvements: 0
- Errors: 1
- Checks executed: 17 of 17
- Results: 7 pass, 10 fail, 0 not-applicable
- Passed: CHECK-T01, CHECK-T04, CHECK-T09, CHECK-T11, CHECK-T14, CHECK-T15, CHECK-T17
- Failed: CHECK-T02, CHECK-T03, CHECK-T05, CHECK-T06, CHECK-T07, CHECK-T08, CHECK-T10, CHECK-T12, CHECK-T13, CHECK-T16

## Findings

### V-001: Proposed shared JSON helper is not importable by its stated Python module name
- **Severity:** error
- **Location:** `specs/stage-exit-coverage/tech-spec.md`, sections 2.1, 3.9, 5.3, 6.1, and 6.2
- **Issue:** The design names the new shared module `scripts/forge-json.py` while requiring `forge-session.py` and `forge-bootstrap.py` to import its API. A hyphenated filename cannot be referenced by ordinary Python import syntax. The specification defines no `importlib`-based loader, so the shared import contract is not implementable as written.
- **Suggested fix:** Rename the importable module to `scripts/forge_json.py`, then update `RUNTIME_HELPERS`, the module tree, integration references, tests, and adapter-copy assertions. If a hyphenated executable is required, keep a thin `forge-json.py` CLI wrapper that imports `forge_json`, while the underscore module remains the shared implementation.
- **References:** `scripts/build-adapters.py` (`RUNTIME_HELPERS`); `scripts/forge-session.py` (`_load_config`); `scripts/forge-bootstrap.py` (existing `json.loads` configuration reads)
- **Checklist:** CHECK-T05, CHECK-T08, CHECK-T13, CHECK-T16

### V-002: Served-stage inference has no serialized metadata input
- **Severity:** gap
- **Location:** `specs/stage-exit-coverage/tech-spec.md`, sections 3.2 and 5.1
- **Issue:** Section 3.2 says an omitted `--served-stage` is inferred from “verify mode metadata,” but neither the proposed `stage_exit(...)` signature nor the `stage-exit` CLI accepts a verify mode, findings report, or equivalent authoritative metadata. The existing `VERIFY_TOKEN_BY_STAGE` map can reverse a token only after a token is supplied; it cannot obtain that token from the proposed request. This leaves PRD requirement REQ-ROUTE-02 without an implementable decision path, especially for direct `forge-fix` invocation.
- **Suggested fix:** Add a typed inference input such as `--verify-mode {epic,prd,tech,specs,backlog,impl}` and a corresponding `verify_mode` function parameter. Define precedence as explicit `--served-stage` first, then unique mode mapping, otherwise exit 2. Specify how `forge-fix` obtains and passes the mode from the selected findings report, and add tests for every mapping, conflicts, missing metadata, and ambiguous metadata.
- **References:** `specs/stage-exit-coverage/PRD.md` (REQ-ROUTE-01..03); `scripts/forge-session.py` (`VERIFY_TOKEN_BY_STAGE`)
- **Checklist:** CHECK-T03, CHECK-T06, CHECK-T07, CHECK-T10, CHECK-T16

### V-003: Unified state writer cannot preserve epic-scoped verification state
- **Severity:** inconsistency
- **Location:** `specs/stage-exit-coverage/tech-spec.md`, sections 3.2, 3.7, 5.2, 6.1, and 6.2
- **Issue:** Section 3.2 requires epic verification to remain epic-scoped, while sections 3.7 and 6.2 say all verify/fix transitions use `state-verify`, which maps through `VERIFY_TOKEN_BY_STAGE` and writes through `_load_state_for_write(...)`. The actual map has no `forge-0-epic` entry, and `_load_state_for_write` targets a feature `.pipeline-state.json`, not the epic `.epic-state.json`. A direct epic verify/fix therefore cannot use the proposed unified writer without failing or writing the wrong state file.
- **Suggested fix:** Define an explicit epic branch in `state-verify`: accept `forge-0-epic`, strictly resolve the epic root, mutate `stages.forge-verify-epic` in `.epic-state.json` atomically, and never call the member-feature writer. Alternatively, retain a separately named epic writer and document it as the sole exception to the unified writer. Update the function/CLI contract, schema integration, error handling, and tests for pass, findings, applied, skipped, ambiguous names, and write failures.
- **References:** `specs/stage-exit-coverage/PRD.md` (REQ-ROUTE-01..06, REQ-STATE-03, REQ-SEC-01); `scripts/forge-session.py` (`VERIFY_TOKEN_BY_STAGE`, `_load_state_for_write`); `scripts/epic-manifest.py` (epic-state handling)
- **Checklist:** CHECK-T02, CHECK-T03, CHECK-T05, CHECK-T06, CHECK-T07, CHECK-T08, CHECK-T10, CHECK-T12, CHECK-T16

### V-004: Applied fixes can appear verification-fresh before required re-verification runs
- **Severity:** gap
- **Location:** `specs/stage-exit-coverage/tech-spec.md`, sections 3.2, 3.7, 4.1, 5.2, and 6.3
- **Issue:** The design routes `fix applied` to re-verification, but section 5.2 also says `findings-applied` records the current stage version. Existing `verify_state()` treats `findings-applied` with a matching `verifiedStageVersion` as fresh. If execution stops after the fix state write but before re-verification, navigator and pre-flight logic can classify the stage as resolved and advance, bypassing the required re-verify route.
- **Suggested fix:** Make the re-verification obligation durable. For fixes requiring re-verification, write `findings-applied` while clearing or omitting `verifiedStageVersion`, causing existing freshness logic to classify the verification as stale until a new `passed` write records the current stage version. Specify this transition explicitly and test interruption/resume between fix and re-verify for direct and nested paths.
- **References:** `specs/stage-exit-coverage/PRD.md` (REQ-ROUTE-04/05, REQ-REL-02); `scripts/forge-session.py` (`KNOWN_VERIFY_STATUSES`, `_VERIFY_RESOLVED`, `verify_state`)
- **Checklist:** CHECK-T02, CHECK-T03, CHECK-T07, CHECK-T10, CHECK-T12, CHECK-T16

## Fix Execution Plan

### User Decisions Required
None — all fixes can be applied directly.

### Execution Steps

Apply these steps in order. Each step is self-contained — a fresh agent can execute it without prior context beyond this document.

#### Step 1: Correct the shared JSON module contract
- **Files:** `specs/stage-exit-coverage/tech-spec.md`
- **Addresses:** V-001
- **Checklist:** CHECK-T05, CHECK-T08, CHECK-T13, CHECK-T16
- **Action:** Rename the shared importable module to `forge_json.py`; update the module layout, API references, runtime-helper list, adapter distribution, and testing descriptions. If a hyphenated executable is retained, specify it as a thin wrapper over the underscore module.
- **Depends on:** none
- **Rationale:** Establishes an implementable shared-module boundary before downstream interfaces and tests refer to it.

#### Step 2: Define authoritative branch-inference metadata
- **Files:** `specs/stage-exit-coverage/tech-spec.md`
- **Addresses:** V-002
- **Checklist:** CHECK-T03, CHECK-T06, CHECK-T07, CHECK-T10, CHECK-T16
- **Action:** Add `verify_mode`/`--verify-mode`, define its enum and precedence relative to `--served-stage`, explain how verify and fix obtain it, and specify fail-closed tests for conflicts, missing metadata, and ambiguous metadata.
- **Depends on:** none
- **Rationale:** The route contract must have a serialized source of truth before epic-specific routing and state behavior can be made precise.

#### Step 3: Specify epic-scoped verification writes
- **Files:** `specs/stage-exit-coverage/tech-spec.md`
- **Addresses:** V-003
- **Checklist:** CHECK-T02, CHECK-T03, CHECK-T05, CHECK-T06, CHECK-T07, CHECK-T08, CHECK-T10, CHECK-T12, CHECK-T16
- **Action:** Extend `state-verify` with an explicit epic-state path or document a dedicated epic writer. Define strict epic-root resolution, atomic `.epic-state.json` mutation, function and CLI signatures, failure handling, and tests across all verification outcomes.
- **Depends on:** Step 2
- **Rationale:** Epic state routing depends on the authoritative mode/served-stage decision established in Step 2.

#### Step 4: Persist the re-verification obligation after fixes
- **Files:** `specs/stage-exit-coverage/tech-spec.md`
- **Addresses:** V-004
- **Checklist:** CHECK-T02, CHECK-T03, CHECK-T07, CHECK-T10, CHECK-T12, CHECK-T16
- **Action:** Specify that `findings-applied` transitions requiring re-verification clear or omit `verifiedStageVersion`; document interruption recovery and add direct/nested resume tests proving the pipeline cannot advance before a new passing verification.
- **Depends on:** Step 3
- **Rationale:** This finalizes the state machine only after ordinary and epic-scoped state writers are fully defined.

## Fix Progress

- Step 1: [APPLIED] 2026-07-30 — Renamed the shared importable helper contract to `forge_json.py` throughout the technical specification.
- Step 2: [APPLIED] 2026-07-30 — Added serialized `verify_mode`/`--verify-mode`, deterministic precedence, caller metadata sources, and fail-closed conflict behavior.
- Step 3: [APPLIED] 2026-07-30 — Defined the explicit atomic epic-root `.epic-state.json` branch and its validation/test contract.
- Step 4: [APPLIED] 2026-07-30 — Made `findings-applied` clear `verifiedStageVersion` until a subsequent passing re-verification records freshness.
