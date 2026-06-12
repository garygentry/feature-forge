# Verification Report: epic-orchestration (prd)
Date: 2026-06-12
Pipeline Stage: forge-1-prd complete (PRD v1, commit recorded)
Artifacts Reviewed: specs/epic-orchestration/PRD.md (cross-referenced against forge-1-prd/references/prd-template.md and the existing forge skills directory)

## Summary
- Total findings: 7
- Gaps: 3
- Inconsistencies: 1
- Improvements: 3
- Errors: 0

## Check Tally
Executed 15 of 15 checks. Results: 10 pass, 5 fail, 0 n/a.

| Check | Result | Note |
|---|---|---|
| CHECK-P01 | pass | All 8 template sections present and populated |
| CHECK-P02 | pass | No TBD/TODO placeholders |
| CHECK-P03 | pass | Out-of-scope is specific (6 concrete exclusions) |
| CHECK-P04 | pass | Open questions are actionable |
| CHECK-P05 | pass | Success criteria are largely verifiable |
| CHECK-P06 | pass | All REQ IDs unique, REQ-CAT-NN format |
| CHECK-P07 | pass | Every requirement has a priority |
| CHECK-P08 | fail | REQ-STATE-02 / REQ-CTX-01 testability gaps → V-001, V-005 |
| CHECK-P09 | fail | Tech decisions embedded in requirements → V-002 |
| CHECK-P10 | pass | User stories cover the actors |
| CHECK-P11 | fail | NFRs not quantified → V-003 |
| CHECK-P12 | fail | Security not addressed → V-004 |
| CHECK-P13 | pass | Constraints use "must" mandate language |
| CHECK-P14 | fail | Implicit requirements unstated → V-006 |
| CHECK-P15 | pass (with note) | Tension surfaced → V-007 |

## Findings

### V-001: REQ-STATE-02 "never trusted when stale" is not objectively testable
- **Severity:** gap
- **Location:** PRD.md §3.2, REQ-STATE-02
- **Issue:** The requirement says per-feature status "must be recomputed on read and never trusted when stale." "Stale" has no definition, so there is no objective acceptance test. You cannot test "never trusted when stale" without a rule for what makes the cached value stale (timestamp mismatch? always recompute? hash compare?).
- **Suggested fix:** Replace the ambiguous clause with a concrete rule, e.g.: "The manifest must not store a cached per-feature status field at all; status is always derived from each feature's `.pipeline-state.json` at read time" — OR, if caching is desired, "a cached status is ignored whenever the feature's pipeline-state file mtime/hash differs from the value recorded alongside the cache." Pick one so an acceptance test ("edit a feature's state file, confirm the epic view reflects it without a separate refresh") is writable.
- **References:** REQ-STATE-01 (manifest-wins conflict rule), Success Criteria bullet 5 (reconstructed purely from disk state)
- **Checklist:** CHECK-P08

### V-002: Technology/implementation decisions embedded in functional requirements without constraint labeling
- **Severity:** improvement
- **Location:** PRD.md §3.1 REQ-EPIC-01, REQ-EPIC-03; §3.2 REQ-DIR-01, REQ-EPIC-02
- **Issue:** Several functional requirements bake in implementation choices that belong in Constraints or the tech spec: REQ-EPIC-01 names the stage `forge-0-epic`; REQ-EPIC-03 mandates the specific filename `EPIC.md`; REQ-DIR-01 prescribes the exact directory shape `{specsDir}/{epic}/{feature}/`; REQ-EPIC-02 fixes the `dependsOn` field name. CHECK-P09 wants requirements free of implementation decisions unless labeled as justified constraints. These are reasonable constraints, but they're stated as the requirement rather than the capability.
- **Suggested fix:** Keep the WHAT in the requirement and move the HOW to §5 Constraints (or mark inline as a constraint). E.g. REQ-EPIC-03 becomes "must produce a human-readable narrative document capturing goal, decomposition rationale, and inter-feature interface contracts" and a Constraint fixes the filename as `EPIC.md`. Similarly relocate the `forge-0-epic` stage name and the concrete directory template / `dependsOn` field name into Constraints with a one-line justification (consistency with existing layout). Quality/labeling improvement, not a correctness error.
- **References:** §5 Constraints, prd-template.md §5 ("This is where technology mandates go")
- **Checklist:** CHECK-P09

### V-003: Non-functional requirements are not quantified
- **Severity:** improvement
- **Location:** PRD.md §4 (REQ-COMPAT-*, REQ-ROBUST-*, REQ-OBS-01)
- **Issue:** No NFR carries a measurable target. CHECK-P11 asks for quantification where applicable. This is a file-driven interactive CLI feature so latency/throughput SLAs are mostly inapplicable, but two are quantifiable and currently aren't: (a) acyclicity/graph validation has no stated bound on epic size it must handle, and (b) REQ-ROBUST-01 "reconstruct full status from disk" has no stated upper bound on member-feature count it must scale to.
- **Suggested fix:** Add a bounded target where meaningful, e.g. "graph validation and dashboard reconstruction must remain correct and interactive (<1s) for epics of up to N member features (e.g. 20)." Do not manufacture latency SLAs for the interview-driven stages. Mark the rest "no quantitative target — interactive, single-user, file-bound" so the absence is deliberate.
- **References:** REQ-EPIC-05 (acyclicity validation), REQ-ROBUST-01, Success Criteria bullet 5
- **Checklist:** CHECK-P11

### V-004: Security considerations are absent and not explicitly waived
- **Severity:** gap
- **Location:** PRD.md §4 (no §4.x Security), §5 Constraints
- **Issue:** CHECK-P12 requires security requirements be explicit, not assumed. The PRD introduces a hand-editable manifest (REQ-ROBUST-02) and auto-loads other features' PRDs/specs as context (REQ-CTX-01). There is no statement about trust boundaries: the manifest and EPIC.md are developer-authored local files, so the realistic "security" concern is untrusted/corrupt input handling and path-traversal safety when resolving `{specsDir}/{epic}/{feature}/` and back-pointers from a hand-edited manifest. None of this is stated.
- **Suggested fix:** Add a short Security subsection (or fold into Robustness) stating the trust model explicitly: "All epic artifacts are trusted local developer files; no untrusted/network input. Manifest parsing must reject path-escaping feature names / directory references (no `..`, no absolute paths) and unknown-feature back-pointers (cf. REQ-DIR-04, REQ-ROBUST-02) to avoid resolving outside `{specsDir}`." Converts the implicit assumption into an explicit, testable requirement.
- **References:** REQ-DIR-03, REQ-DIR-04, REQ-ROBUST-02, REQ-CTX-01
- **Checklist:** CHECK-P12, CHECK-P14

### V-005: REQ-CTX-01 context-injection scope leaves "completed upstream dependency features" ambiguous for transitive deps
- **Severity:** gap
- **Location:** PRD.md §3.4, REQ-CTX-01
- **Issue:** The requirement loads "the PRDs/tech-specs of completed upstream dependency features," but doesn't state whether "upstream" means direct dependencies only or the full transitive closure. For an acceptance test (and for context-window sizing) this matters: a feature D depending on C depending on B — does authoring D load B's specs? Untestable as written and has a real cost tradeoff (context bloat vs. completeness).
- **Suggested fix:** Specify the closure explicitly, e.g. "loads the PRDs/tech-specs of all *direct* completed dependency features; transitive dependencies are surfaced via those features' own contract sections in EPIC.md, not by loading their full specs." Bounds context size and makes the requirement testable. If transitive loading is intended instead, say so and note the context-size implication.
- **References:** REQ-CTX-02 (contract obligations), REQ-EPIC-03 (EPIC.md contracts)
- **Checklist:** CHECK-P08, CHECK-P14

### V-006: Implicit concurrency/locking requirement for the manifest is unstated
- **Severity:** improvement
- **Location:** PRD.md §3.2 REQ-STATE-01/02, §4.2 Robustness
- **Issue:** The manifest is "the canonical record" mutated by creation, edits, and feature-completion handoffs (REQ-OBS-01), and the design is multi-session ("any session can reconstruct... from files"). CHECK-P14 flags implicit requirements: nothing states what happens if two sessions/commands write the manifest, or if a write is interrupted mid-update (partial/torn write leaving an invalid manifest that REQ-ROBUST-02 would then reject). The git-commit-after-stage protocol gives history but not concurrency safety.
- **Suggested fix:** Add a requirement or explicit Out-of-Scope note. Either: "Concurrent epic-mutating commands are out of scope for v1; single active session assumed" (cheapest), or a requirement that manifest writes be atomic (write-temp-then-rename) so an interrupted write never leaves a corrupt manifest. State whichever is intended.
- **References:** REQ-STATE-01, REQ-OBS-01, REQ-ROBUST-02
- **Checklist:** CHECK-P14

### V-007: Tension between REQ-EPIC-04 (just-in-time PRDs) and REQ-VERIFY-01 (contract-drift checking) is unaddressed
- **Severity:** inconsistency
- **Location:** PRD.md §3.1 REQ-EPIC-04 vs §3.6 REQ-VERIFY-01; relates to Open Question 3
- **Issue:** REQ-EPIC-04 says features get only a one-paragraph charter at creation, with full specs authored just-in-time. REQ-VERIFY-01 requires checking "contract drift (completed features' specs vs. the contracts declared in EPIC.md)." This is only tractable if EPIC.md's contracts are structured enough to diff against specs — which Open Question 3 explicitly flags as unresolved. So a P1 requirement depends on an unanswered open question: REQ-VERIFY-01 may be unimplementable depending on how the question is resolved. CHECK-P15 asks for surfacing exactly this kind of tension.
- **Suggested fix:** Cross-link the two requirements and the open question. Either resolve Open Question 3 in favor of a lightweight structured exposes/consumes format (making REQ-VERIFY-01 tractable) and update REQ-EPIC-03/REQ-VERIFY-01 to mandate it, or explicitly note in REQ-VERIFY-01 that contract-drift checking is best-effort/heuristic while EPIC.md contracts remain free-form. Add a "Depends on Open Question 3" note to REQ-VERIFY-01.
- **References:** REQ-EPIC-03, REQ-EPIC-04, REQ-VERIFY-01, Open Question 3
- **Checklist:** CHECK-P15, CHECK-P04

## Fix Execution Plan

### User Decisions Required
- **V-005:** [RESOLVED 2026-06-12] Direct dependencies only; transitive deps surfaced via EPIC.md contract sections.
- **V-006:** [RESOLVED 2026-06-12] Atomic writes required (write-temp-then-rename); concurrent multi-session mutation out of scope for v1.
- **V-007:** [RESOLVED 2026-06-12] Structured per-feature `exposes`/`consumes` contract format mandated in EPIC.md.
- V-001 (define "stale"), V-002, V-003, V-004 applied directly with suggested wording; V-003 bound set to 20 features.

### Execution Steps

#### Step 1: Tighten testability of state and context requirements
- **Files:** specs/epic-orchestration/PRD.md (§3.2 REQ-STATE-02, §3.4 REQ-CTX-01)
- **Addresses:** V-001, V-005
- **Checklist:** CHECK-P08, CHECK-P14
- **Action:** Rewrite REQ-STATE-02 to remove "never trusted when stale" in favor of a concrete recompute/staleness rule (per V-001). Rewrite REQ-CTX-01 to specify direct-vs-transitive dependency loading (per V-005, pending user decision).
- **Depends on:** none (V-005 needs user input first)

#### Step 2: Add Security subsection and concurrency stance
- **Files:** specs/epic-orchestration/PRD.md (§4 add §4.x Security; §3.2 or §4.2 for concurrency)
- **Addresses:** V-004, V-006
- **Checklist:** CHECK-P12, CHECK-P14
- **Action:** Add explicit trust-model/path-safety requirement (V-004) and the concurrency decision (V-006).
- **Depends on:** none (V-006 needs user decision)

#### Step 3: Quantify NFRs where meaningful
- **Files:** specs/epic-orchestration/PRD.md (§4)
- **Addresses:** V-003
- **Checklist:** CHECK-P11
- **Action:** Add a bounded epic-size target for graph validation and dashboard reconstruction; mark remaining NFRs as deliberately non-quantitative.
- **Depends on:** none

#### Step 4: Relocate implementation decisions to Constraints
- **Files:** specs/epic-orchestration/PRD.md (§3.1, §3.2, §5)
- **Addresses:** V-002
- **Checklist:** CHECK-P09
- **Action:** Move `forge-0-epic` stage name, `EPIC.md` filename, and concrete directory template / `dependsOn` field name from functional requirements into §5 Constraints with one-line justifications; leave the capability statement in the requirements.
- **Depends on:** none

#### Step 5: Resolve the EPIC-04 / VERIFY-01 tension
- **Files:** specs/epic-orchestration/PRD.md (§3.1 REQ-EPIC-03, §3.6 REQ-VERIFY-01, §7 Open Question 3)
- **Addresses:** V-007
- **Checklist:** CHECK-P15, CHECK-P04
- **Action:** Per the user's resolution of Open Question 3, either mandate a structured exposes/consumes contract format in EPIC.md (and update REQ-VERIFY-01 accordingly) or mark REQ-VERIFY-01 contract-drift as best-effort; add an explicit dependency note linking REQ-VERIFY-01 to Open Question 3.
- **Depends on:** none (needs user decision), but do after Step 4 to avoid editing §3.1 twice.

## Fix Progress
- Step 1: [APPLIED] 2026-06-12 — Rewrote REQ-STATE-02 (no cached status field; recompute on read, with acceptance test) and REQ-CTX-01 (direct deps only) [V-001, V-005]
- Step 2: [APPLIED] 2026-06-12 — Added REQ-ROBUST-03 (atomic manifest writes) and §4.4 Security/Trust Model REQ-SEC-01/02 (path-safety) [V-004, V-006]
- Step 3: [APPLIED] 2026-06-12 — Quantified REQ-ROBUST-01 (<1s for ≤20 features; other NFRs deliberately non-quantitative) [V-003]
- Step 4: [APPLIED] 2026-06-12 — Moved forge-0-epic name, EPIC.md filename, subtree layout, and dependsOn field into §5 Constraints; requirements now state capability only [V-002]
- Step 5: [APPLIED] 2026-06-12 — Mandated structured exposes/consumes in REQ-EPIC-03, cross-linked REQ-VERIFY-01, resolved Open Question 3 [V-007]
