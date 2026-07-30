# Verification Report: stage-exit-coverage (tech)
Date: 2026-07-30
Pipeline Stage: forge-2-tech
Artifacts Reviewed: `specs/stage-exit-coverage/.pipeline-state.json`, `specs/stage-exit-coverage/PRD.md`, `specs/stage-exit-coverage/tech-spec.md`, `forge.config.json`, `references/pipeline-state-schema.json`, `references/epic-manifest-schema.json`, `skills/forge-0-epic/references/edit-mode.md`, `scripts/forge-session.py`, `scripts/epic-manifest.py`, `scripts/forge-bootstrap.py`, `scripts/build-adapters.py`

## Summary
- Total findings: 2
- Gaps: 2
- Inconsistencies: 0
- Improvements: 0
- Errors: 0
- Checks executed: 17 of 17
- Results: 9 pass, 8 fail, 0 not-applicable
- Passed: CHECK-T01, CHECK-T04, CHECK-T05, CHECK-T09, CHECK-T11, CHECK-T13, CHECK-T14, CHECK-T15, CHECK-T17
- Failed: CHECK-T02, CHECK-T03, CHECK-T06, CHECK-T07, CHECK-T08, CHECK-T10, CHECK-T12, CHECK-T16

## Prior-Finding Confirmation

- Prior V-001: **Resolved** — the helper is consistently named `scripts/forge_json.py` and distributed through `RUNTIME_HELPERS`.
- Prior V-002: **Resolved** — `verify_mode`/`--verify-mode`, mappings, precedence, conflict handling, and caller metadata sources are specified.
- Prior V-003: **Resolved as originally reported** — `state-verify` now has an explicit atomic `.epic-state.json` write branch. Current V-001 identifies a separate read/freshness gap.
- Prior V-004: **Resolved** — `findings-applied` clears `verifiedStageVersion`, and the test plan covers interruption before re-verification.

## Findings

### V-001: Epic verification has no authoritative revision or read-side freshness contract
- **Severity:** gap
- **Location:** `specs/stage-exit-coverage/tech-spec.md`, sections 3.7, 4.1, 5.2, and 6.1–6.3
- **Issue:** The revised design correctly writes epic verification into `.epic-state.json`, but still defines pending idempotency and terminal freshness using `scheduledStageVersion` and `verifiedStageVersion`, described as the production stage's integer `version`. An epic root has no `.pipeline-state.json` or epic-scoped `forge-0-epic` stage version: `forge-0-epic` versions exist only in member states, while epic edits mutate `epic-manifest.json`. The specification also defines no epic-specific read branch for `stage_exit()` or freshness classifiers; the cited `_resolve_feature_dir` path reads `.pipeline-state.json`, so it cannot observe debt written to `.epic-state.json`. Epic scheduling therefore has no promised revision input, repeated exits cannot apply the idempotency rule, and routing may fail to observe pending or completed epic verification.
- **Suggested fix:** Define one canonical epic artifact revision and the complete read/write path. Recommended: add an integer manifest revision initialized at epic creation and incremented by every manifest/edit-mode mutation; use it for epic `scheduledStageVersion` and `verifiedStageVersion`, with explicit legacy fallback behavior. Specify that `stage_exit`, epic freshness classification, debt/status rendering, and terminal result handling read `.epic-state.json` and compare against that revision—never a member stage version. Add tests for first scheduling, same-revision idempotency, manifest edits making verification stale, pending visibility, pass replacement, and legacy manifests.
- **References:** `skills/forge-0-epic/references/edit-mode.md` (“Pipeline state”); `references/epic-manifest-schema.json`; `scripts/forge-session.py` (`_resolve_feature_dir`, `_verify_state_for`, `stage_exit`); `specs/stage-exit-coverage/PRD.md` (REQ-DEBT-01..06, REQ-REL-01/03, REQ-SEC-01)
- **Checklist:** CHECK-T03, CHECK-T06, CHECK-T07, CHECK-T08, CHECK-T10, CHECK-T12, CHECK-T16

### V-002: `state-verify` cannot complete the required two-commit provenance write
- **Severity:** gap
- **Location:** `specs/stage-exit-coverage/tech-spec.md`, sections 3.7, 3.8, 5.2, 6.1–6.3, 7.4, and 8.2
- **Issue:** Section 3.8 requires verify/fix provenance writers to validate full hashes and preserve the two-commit protocol, but the exact `cmd_state_verify(...)` signature and CLI expose no `commit_hash`/`--commit-hash` input or commit-2-only transition. The data flow says all verify/fix transitions use `state-verify`, while PRD REQ-STATE-03 prohibits falling back to model-authored JSON. The initial result write can set verification state, but no specified targeted writer can later replace `commitHash: null` with the artifact commit's validated 40-character hash.
- **Suggested fix:** Extend `cmd_state_verify` and its CLI with an optional `commit_hash`/`--commit-hash` commit-2 mode for both feature and epic state. Specify guards: the initial result transition writes `commitHash: null`; commit-2 mode requires an existing applicable verify entry, validates exactly 40 hexadecimal characters before mutation, changes only `commitHash` plus the required state timestamp, and rejects conflicting result metadata. Add feature and epic tests for valid full hashes, short/non-hex rejection without mutation, missing-entry rejection, and proof that no amend path is used.
- **References:** `specs/stage-exit-coverage/PRD.md` (REQ-STATE-01/03/04); `scripts/forge-session.py` (`cmd_state_complete`, `_commit_state`); `skills/forge-fix/SKILL.md` (“Update Pipeline State and Commit”)
- **Checklist:** CHECK-T02, CHECK-T03, CHECK-T06, CHECK-T07, CHECK-T08, CHECK-T10, CHECK-T12, CHECK-T16

## Fix Execution Plan

### User Decisions Required
- V-001 — **Resolved 2026-07-30:** Use an integer `revision` in `epic-manifest.json`, initialized at creation and incremented atomically by every manifest mutation. This aligns with existing version-based freshness semantics.

### Execution Steps

Apply these steps in order. Each step is self-contained — a fresh agent can execute it without prior context beyond this document.

#### Step 1: Define epic revision and read-side verification semantics
- **Files:** `specs/stage-exit-coverage/tech-spec.md`
- **Addresses:** V-001
- **Checklist:** CHECK-T03, CHECK-T06, CHECK-T07, CHECK-T08, CHECK-T10, CHECK-T12, CHECK-T16
- **Action:** After resolving the revision-token decision, specify the canonical epic revision source, initialization/increment rules, legacy behavior, `.epic-state.json` read path, freshness comparison, pending idempotency, and affected function/CLI contracts and tests.
- **Depends on:** none
- **Rationale:** The provenance writer and freshness fields need a canonical epic revision before their epic behavior can be finalized.

#### Step 2: Complete the verify/fix provenance writer design
- **Files:** `specs/stage-exit-coverage/tech-spec.md`
- **Addresses:** V-002
- **Checklist:** CHECK-T02, CHECK-T03, CHECK-T06, CHECK-T07, CHECK-T08, CHECK-T10, CHECK-T12, CHECK-T16
- **Action:** Add `commit_hash`/`--commit-hash` to `state-verify`, define a guarded commit-2-only transition for feature and epic verification entries, and enumerate full-hash, missing-entry, conflicting-metadata, and failure-atomicity tests.
- **Depends on:** Step 1
- **Rationale:** The commit-2 path must use the final feature/epic state and revision contracts established in Step 1.

## Fix Progress

- Step 1: [APPLIED] 2026-07-30 — Defined integer epic manifest revision initialization/increment/legacy rules and the complete `.epic-state.json` read-side freshness contract.
- Step 2: [APPLIED] 2026-07-30 — Added guarded feature/epic `state-verify --commit-hash` commit-2 mode, mutation constraints, data flow, and test coverage.
