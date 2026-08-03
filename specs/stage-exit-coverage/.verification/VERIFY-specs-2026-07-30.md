# Verification Report: stage-exit-coverage (specs)
Date: 2026-07-30
Pipeline Stage: forge-3-specs
Artifacts Reviewed: `PRD.md`, `tech-spec.md`, `00-core-definitions.md`, `01-architecture-layout.md`, `02-stage-exit-routing.md`, `03-verification-state.md`, `04-skill-integration.md`, `05-config-and-distribution.md`, `06-compliance-and-coverage.md`, `07-testing-strategy.md`, `TRACEABILITY.md`, `.pipeline-state.json`, and relevant existing source/integration surfaces

## Summary
- Total findings: 6
- Gaps: 4
- Inconsistencies: 1
- Improvements: 0
- Errors: 1
- Checks executed: 38 of 38
- Results: 30 pass, 6 fail, 2 not-applicable

## Check Results

- **Pass:** CHECK-S01, CHECK-S02, CHECK-S03, CHECK-S04, CHECK-S05, CHECK-S06, CHECK-S07, CHECK-S08, CHECK-S09, CHECK-S10, CHECK-S11, CHECK-S12, CHECK-S16, CHECK-S18, CHECK-S19, CHECK-S20, CHECK-S21, CHECK-S22, CHECK-S23, CHECK-S24, CHECK-S25, CHECK-S26, CHECK-S28, CHECK-S29, CHECK-S30, CHECK-S31, CHECK-S33, CHECK-S34, CHECK-S36, CHECK-S37
- **Fail:** CHECK-S13, CHECK-S14, CHECK-S15, CHECK-S27, CHECK-S32, CHECK-S38
- **Not applicable:** CHECK-S17 — the project has no package exports map; its executable-path and sibling-import contract is internally consistent. CHECK-S35 — no external dependency is added; local fixtures and fault-injection policy are still specified.
- **Deterministic traceability validator:** passed with 54 requirements, 8 numbered implementation specs, no uncovered requirements, and no orphaned requirement references. The authored `TRACEABILITY.md` nevertheless has the completeness and semantic-citation defects below.

## Findings

### V-001: Structured contract fields lack field-level documentation
- **Severity:** gap
- **Location:** `00-core-definitions.md`, sections 4 and 6; `04-skill-integration.md`, section 2.2; `06-compliance-and-coverage.md`, sections 2.1, 3.2, and 4.1; `07-testing-strategy.md`, section 2.2
- **Issue:** `EpicReconcile`, `StageExitDirectives`, `StageExitPayload`, `VerifyEntry`, `RenderStatus`, `CanonicalExitSite`, `ExpectedCommand`, `BranchScenario`, `BranchFixture`, `CommandEvidence`, `ParsedTranscript`, and `SessionCliResult` have class-level summaries but bare field annotations. Important field semantics, nullability, and value domains are absent at their declarations.
- **Suggested fix:** Add an adjacent explanatory comment to every field in the listed `TypedDict`, `NamedTuple`, and dataclass declarations. Document meaning, allowed nullability, and semantic distinctions without changing the declared shapes.
- **References:** Python stack profile; `00-core-definitions.md` sections 4 and 6; `06-compliance-and-coverage.md` sections 3.2 and 4.1
- **Checklist:** CHECK-S13

### V-002: Runner-contract layout names a nonexistent root file
- **Severity:** inconsistency
- **Location:** `tech-spec.md`, sections 2 and 3.11; `01-architecture-layout.md`, section 2
- **Issue:** The layouts name root-level `references/runner-contract.md`, but the repository contains only `skills/forge-5-loop/references/runner-contract.md`. The architecture document later acknowledges the skill-local file and warns against creating a duplicate, leaving conflicting ownership instructions.
- **Suggested fix:** Replace root-level `references/runner-contract.md` references with `skills/forge-5-loop/references/runner-contract.md`. Remove conditional path-resolution wording and identify the existing skill-local file as the sole source.
- **References:** `PRD.md` REQ-CAP-01 and REQ-FOLLOW-01; `04-skill-integration.md` section 6.3; `07-testing-strategy.md` section 6.2
- **Checklist:** CHECK-S14

### V-003: Implementation specs lack explicit public-versus-internal API sections
- **Severity:** gap
- **Location:** `00-core-definitions.md` through `07-testing-strategy.md`, document-level API descriptions
- **Issue:** API information is scattered among ownership, callable, CLI, and integration sections, but none of the eight numbered specs has a clearly labeled section distinguishing user-facing or repository-importable surfaces from private helpers and test/eval-only APIs.
- **Suggested fix:** Add a concise `Public API and Internal Surface` section to every numbered spec. Identify user-facing CLI commands, repository-internal importable functions, private helpers, and test/eval-only APIs. Where a document defines no API, state that explicitly and link to the owning contract rather than duplicating signatures.
- **References:** `tech-spec.md` sections 2.1, 5, and 6; `00-core-definitions.md` sections 3–8; `01-architecture-layout.md` sections 1 and 3
- **Checklist:** CHECK-S32

### V-004: Authored traceability matrix omits REQ-A11Y-01
- **Severity:** gap
- **Location:** `TRACEABILITY.md`, PRD-to-spec matrix and Validation Summary
- **Issue:** The PRD contains 54 requirements, including `REQ-A11Y-01`, but the authored matrix has 53 rows and omits it. The Validation Summary consequently claims all 53 requirements are mapped. Implementation guidance exists, so this is a matrix-completeness gap rather than missing implementation coverage.
- **Suggested fix:** Add a `REQ-A11Y-01` row mapping implementation to `02-stage-exit-routing.md` section 5.1 and `04-skill-integration.md` sections 3.2 and 5, and verification to `07-testing-strategy.md` section 6.2. Change the total from 53 to 54.
- **References:** `PRD.md` section 4.5; deterministic validator output (`total_requirements: 54`)
- **Checklist:** CHECK-S38

### V-005: Traceability section citations point to adjacent, semantically wrong sections
- **Severity:** error
- **Location:** `TRACEABILITY.md`, PRD-to-spec matrix and Technical-Decision Coverage; `07-testing-strategy.md`, section 2.1
- **Issue:** `REQ-ROUTE-04..06` cite routing section 7 although direct verify/fix routing is section 6; `REQ-PROD-01..02` cite section 8 although loop routing is section 7; and `REQ-PROD-03..04` cite section 9 although docs routing is section 8. The technical-decision row omits loop section 7. `07-testing-strategy.md` section 2.1 cites `06-compliance-and-coverage.md` section 8 for branch helper APIs, but those APIs are defined in sections 3–5.
- **Suggested fix:** Correct the routing mappings to sections 6, 7, and 8 respectively; map the combined live routing decision to sections 7–9; and update the testing strategy to cite compliance sections 3–5.
- **References:** `02-stage-exit-routing.md` sections 6–9; `06-compliance-and-coverage.md` sections 3–5 and 8
- **Checklist:** CHECK-S15, CHECK-S38

### V-006: Concurrent targeted state writes can lose successful updates
- **Severity:** gap
- **Location:** `03-verification-state.md`, sections 3.2, 3.3, and 7.1
- **Issue:** Feature and epic writers load a complete JSON document, mutate one entry, and atomically replace the file. Atomic replacement prevents partial files, but concurrent writers can read the same original state and each replace it successfully; the later writer silently discards the earlier unrelated update. No lock, optimistic version check, compare-and-retry behavior, or enforceable single-writer invariant is defined.
- **Suggested fix:** Implement the selected portable per-state-file lock policy. Hold a sibling lock across load, validation, mutation, fsync, and replacement; use bounded acquisition, owner metadata, safe stale-lock recovery, token-checked release, and an actionable contention error. Add synchronized feature-state and epic-state tests proving unrelated updates both survive serialization and abandoned locks recover safely.
- **References:** `tech-spec.md` sections 3.7 and 7.3; `PRD.md` REQ-REL-02 and REQ-SEC-01; `07-testing-strategy.md` sections 4.2–4.3
- **Checklist:** CHECK-S27

## Fix Execution Plan

### User Decisions Required
None — the user selected portable per-state-file locking for V-006.

### Execution Steps

Apply these steps in order. Each step is self-contained — a fresh agent can execute it without prior context beyond this document.

#### Step 1: Normalize the runner-contract source path
- **Files:** `specs/stage-exit-coverage/tech-spec.md`, `specs/stage-exit-coverage/01-architecture-layout.md`
- **Addresses:** V-002
- **Checklist:** CHECK-S14
- **Action:** Replace root-level runner-contract paths with `skills/forge-5-loop/references/runner-contract.md`, remove path-selection ambiguity, and state that the existing skill-local file is the sole source.
- **Depends on:** none
- **Rationale:** Correct ownership first so later API and traceability edits target the real source.

#### Step 2: Define the state-writer concurrency contract
- **Files:** `specs/stage-exit-coverage/tech-spec.md`, `specs/stage-exit-coverage/03-verification-state.md`, `specs/stage-exit-coverage/07-testing-strategy.md`
- **Addresses:** V-006
- **Checklist:** CHECK-S27
- **Action:** Specify a portable sibling lock-file protocol using exclusive creation, owner metadata, bounded acquisition, safe stale-lock recovery, and token-checked cleanup. Hold the lock across load, validation, mutation, fsync, and atomic replacement. Define actionable contention diagnostics and add synchronized feature/epic writer tests proving serialized unrelated updates both survive, live locks are not stolen, and abandoned locks recover safely.
- **Depends on:** none
- **Rationale:** The user selected portable per-state-file locking; defining it early fixes the state contract consumed by later API and test sections.

#### Step 3: Define API visibility across the numbered specs
- **Files:** `specs/stage-exit-coverage/00-core-definitions.md`, `specs/stage-exit-coverage/01-architecture-layout.md`, `specs/stage-exit-coverage/02-stage-exit-routing.md`, `specs/stage-exit-coverage/03-verification-state.md`, `specs/stage-exit-coverage/04-skill-integration.md`, `specs/stage-exit-coverage/05-config-and-distribution.md`, `specs/stage-exit-coverage/06-compliance-and-coverage.md`, `specs/stage-exit-coverage/07-testing-strategy.md`
- **Addresses:** V-003
- **Checklist:** CHECK-S32
- **Action:** Add `Public API and Internal Surface` sections that classify CLI commands, importable repository functions, private helpers, canon command surfaces, and test/eval-only APIs. Cross-reference central signatures instead of duplicating them.
- **Depends on:** Steps 1–2
- **Rationale:** Visibility declarations should reflect the final file ownership and concurrency contract.

#### Step 4: Document every structured field
- **Files:** `specs/stage-exit-coverage/00-core-definitions.md`, `specs/stage-exit-coverage/04-skill-integration.md`, `specs/stage-exit-coverage/06-compliance-and-coverage.md`, `specs/stage-exit-coverage/07-testing-strategy.md`
- **Addresses:** V-001
- **Checklist:** CHECK-S13
- **Action:** Add adjacent field comments to every listed structured type, covering meaning, nullability, and value-domain distinctions while preserving all existing type shapes.
- **Depends on:** Step 3
- **Rationale:** Field comments should describe finalized contracts and visibility boundaries.

#### Step 5: Repair semantic cross-references and complete traceability
- **Files:** `specs/stage-exit-coverage/TRACEABILITY.md`, `specs/stage-exit-coverage/07-testing-strategy.md`
- **Addresses:** V-004, V-005
- **Checklist:** CHECK-S15, CHECK-S38
- **Action:** Correct routing and compliance section citations, add the missing `REQ-A11Y-01` row, update the requirement total from 53 to 54, re-run `validate-traceability.py`, and manually confirm the authored matrix has exactly 54 rows.
- **Depends on:** Steps 1–4
- **Rationale:** Repair traceability last so all citations describe the final edited documents.

## Fix Progress

- Step 1: [APPLIED] 2026-07-30 — Removed root-level `references/runner-contract.md` from the tech-spec §2 and architecture §2 layout trees; listed `skills/forge-5-loop/references/runner-contract.md` as the sole source in both; replaced the conditional "resolve whether the canonical reference is root or skill-local" paragraph with a definitive skill-local ownership statement; qualified the bare filename in tech-spec §3.11.
- Step 2: [APPLIED] 2026-07-30 — Specified the portable per-state-file lock protocol. New `03-verification-state.md` §3.5 defines the sibling `.lock` file, `O_CREAT|O_EXCL` acquisition, owner metadata with a per-acquisition token, bounded `LOCK_TIMEOUT_S` polling on `time.monotonic()`, token-stability-double-checked stale reclamation after `LOCK_STALE_S`, token-checked release, the held region (load→validate→mutate→fsync→replace), and the single-lock ordering rule; §3.2/§3.3 now acquire before load and release after replace; §7.1 adds the actionable contention error; §7.2 covers abandoned-lock recovery; coverage table rows for REQ-STATE-03/REQ-REL-02/REQ-SEC-01 cite §3.5. `tech-spec.md` §7.3 records the decision, why `fcntl`/`msvcrt` were rejected on portability, and the rejected optimistic-versioning alternative. `07-testing-strategy.md` §4.3 adds lost-update serialization tests (real concurrent processes, forced interleaving, negative control), the lock lifecycle matrix, injectable timing constants, and parameterization over all eight `state-*` verbs.
- Step 3: [APPLIED] 2026-07-30 — Added a `Public API and Internal Surface` section to all eight numbered specs, each placed immediately before that document's Dependencies section so no existing section number shifted (every cross-reference in TRACEABILITY.md and between specs stays valid). Each classifies user-facing CLI/commands, repository-internal importable functions, private helpers, and test/eval-only APIs, cross-referencing central signatures instead of duplicating them. 01 and 07 state explicitly that they define no API and link to the owning contracts; 04 states it adds no Python API and scopes its surface to the host command forms plus `COVERED_SKILLS`; 06 states its entire surface is maintainer/CI-facing.
- Step 4: [APPLIED] 2026-07-30 — Added adjacent field comments to all twelve structured types across four specs, documenting meaning, nullability, and value domains without altering any declared shape: `EpicReconcile`, `StageExitDirectives` (25 fields), `StageExitPayload`, `VerifyEntry` (00); `RenderStatus` (04); `CanonicalExitSite`, `ExpectedCommand`, `BranchScenario`, `BranchFixture`, `CommandEvidence`, `ParsedTranscript` (06); `SessionCliResult` (07). Class docstrings now state the absent-vs-null distinction wherever `total=False` makes key absence semantically load-bearing (`StageExitDirectives`, `VerifyEntry`, `ParsedTranscript`).
- Step 5: [APPLIED] 2026-07-30 — Repaired semantic cross-references and completed the matrix. Routing citations corrected to the sections that actually hold the material: REQ-ROUTE-04..06 → §6 (§6.1 verify, §6.2 fix), REQ-PROD-01..02 → §7, REQ-PROD-03..04 → §8; the "Live epic/docs and loop outcome routing" technical-decision row now spans §7–§9. Also corrected REQ-ROUTE-01's §7 → §6 (same off-by-one, not itemized in V-005 — see note below). Added the missing `REQ-A11Y-01` row (implementation `02-stage-exit-routing.md` §5.1 and `04-skill-integration.md` §3.2/§5; verification `07-testing-strategy.md` §6.2) and changed the Validation Summary total from 53 to 54. Cited §3.5 in REQ-SEC-01's implementation column now that the lock protocol exists. `07-testing-strategy.md` §2.1 now cites `06-compliance-and-coverage.md` §3–§5 instead of §8. Re-ran `validate-traceability.py`: 54 requirements, 8 spec files, no uncovered requirements, no orphaned references; the authored matrix has exactly 54 rows, no duplicate IDs, and its ID set is identical to the PRD's.

## Post-Fix Notes

- **Beyond the plan (same defect, one row):** `REQ-ROUTE-01` cited `02-stage-exit-routing.md` §3, §7 for "explicit served stage". V-005 itemized only ROUTE-04..06, but §7 is Loop Outcome Routing and served-stage resolution lives in §3.2/§6, so this was the same off-by-one and was corrected to §3, §6. Flagged here rather than applied silently.
- **Deliberately out of scope:** `PRD.md` line 163 (REQ-CAP-01) still says run-mode detail "MUST be single-sourced in `references/runner-contract.md`" — a bare path with the same root-vs-skill-local ambiguity Step 1 fixed. The Step 1 file list covers `tech-spec.md` and `01-architecture-layout.md` only, and editing the PRD would bump `forge-1-prd` to v3 and cascade staleness across tech-spec and all eight specs for a wording clarification. Left for the next PRD revision; the implementation-facing documents are now unambiguous.
