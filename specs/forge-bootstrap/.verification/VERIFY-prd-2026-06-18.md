# Verification Report: forge-bootstrap (prd)
Date: 2026-06-18
Pipeline Stage: forge-2-tech (PRD complete, verifying PRD)
Artifacts Reviewed:
- specs/forge-bootstrap/PRD.md
- specs/forge-bootstrap/.reference/CHARTER.md (source brief, context only)
- references/prd-template.md (template, context only)

## Summary
- Total findings: 3
- Gaps: 0
- Inconsistencies: 0
- Improvements: 3
- Errors: 0

Checks: Executed 15 of 15 PRD-mode checks. Results: 12 pass, 0 fail, 3 n/a.

Per-check results:
- CHECK-P01 PASS — all 8 template sections present and populated.
- CHECK-P02 PASS — no TBD/TODO; deferred items are explicit OQ-01..OQ-05.
- CHECK-P03 PASS — §6 Out of Scope has 6 concrete exclusions with rationale.
- CHECK-P04 PASS — OQ-01..OQ-05 are actionable (name the decision + blocked REQ).
- CHECK-P05 PASS — §8 success criteria are scenario-based and verifiable.
- CHECK-P06 PASS — every requirement has a unique REQ-CAT-NN ID.
- CHECK-P07 PASS — every REQ carries a P0/P1/P2 priority.
- CHECK-P08 PASS — requirements are testable; success criteria mirror them.
- CHECK-P09 PASS — forge.config/loopRunner/rauf are the skill's own produced
  artifacts, justified in §5 Constraints; CI provider held as constraint, not req.
- CHECK-P10 PASS — all 7 user-story actors map to requirements.
- CHECK-P11 N/A — interactive CLI meta-feature has no meaningful SLA; soft NFR is
  intentional (see V-001, improvement).
- CHECK-P12 PASS — REQ-SEC-01/02 explicit; security not assumed.
- CHECK-P13 PASS — §5 separates mandates from CI-provider preference.
- CHECK-P14 N/A/PASS — implicit items mostly made explicit; one gap noted (V-002).
- CHECK-P15 PASS — no blocking conflicts; one terminology tension (V-003).

## Findings

### V-001: REQ-PERF-01 uses an unquantified "promptly"
- **Severity:** improvement
- **Location:** PRD.md §4.1, REQ-PERF-01
- **Issue:** The sole performance NFR says scaffolding "SHOULD complete promptly"
  with no measurable bound (CHECK-P11). For an interactive single-shot CLI tool
  this is acceptable (no real SLA), and the one cost driver is named (toolchain
  detection + one lint/test pass), but the non-quantification is left implicit
  rather than deliberate.
- **Suggested fix:** Either add a soft bound scoped to file generation — e.g.
  "scaffolding file generation SHOULD add no perceptible delay beyond the single
  lint/test verification run, whose duration is the stack toolchain's, not
  bootstrap's" — or explicitly state that no numeric target applies because
  runtime is dominated by the external toolchain. Either makes the
  non-quantification intentional.
- **References:** PRD.md §4.1
- **Checklist:** CHECK-P11

### V-002: Pre-existing LICENSE/README handling is unspecified (implicit requirement)
- **Severity:** improvement
- **Location:** PRD.md §3.2 REQ-INPUT-05 / §3.1 REQ-GATE-04, REQ-GATE-05 / §3.3 REQ-SCAF-06
- **Issue:** REQ-GATE-04 treats an auto-generated LICENSE/README (from a fresh
  remote repo) as allowed-meta, and REQ-GATE-05 forbids modifying any pre-existing
  file. But REQ-SCAF-06 produces a LICENSE per the user's selection and
  REQ-INPUT-05 collects a license choice. The behavior when a pre-existing LICENSE
  exists *and* the user selects a different one is unspecified — honoring the new
  selection would conflict with REQ-GATE-05's "no modify." Same tension for a
  pre-existing README that REQ-SCAF-06 wants to seed. This is an implicit
  requirement that should be made explicit (CHECK-P14/P15).
- **Suggested fix:** Add a clause to REQ-INPUT-05 / REQ-SCAF-06: when an
  allowed-meta LICENSE or README already exists, bootstrap MUST NOT overwrite it
  (per REQ-GATE-05) — it skips generating that file (or seeds the interview default
  from the existing one) and notes this in the completion summary (REQ-OUT-01).
  If the resolution should be deferred, capture it instead as a new Open Question
  (OQ-06).
- **References:** PRD.md REQ-GATE-04, REQ-GATE-05, REQ-SCAF-06, REQ-INPUT-05, REQ-OUT-01
- **Checklist:** CHECK-P14, CHECK-P15

### V-003: "Clean working tree" wording conflicts with the staged-no-commit option
- **Severity:** improvement
- **Location:** PRD.md §3.3 REQ-SCAF-08, §3.8 REQ-LIFE-05/06
- **Issue:** REQ-SCAF-08 (P0) requires bootstrap to "leave the working tree clean,"
  then defines clean as "committed or intentionally staged." In git terms, a tree
  with staged-but-uncommitted changes is *not* a clean working tree. The
  parenthetical reconciles intent, but an acceptance-test author could read "clean"
  literally and assert `git status` is empty, contradicting the REQ-LIFE-05
  staged-no-commit option (CHECK-P15).
- **Suggested fix:** Reword REQ-SCAF-08 to drop "clean," e.g. "On completion,
  bootstrap MUST leave no untracked or dangling scaffold files — every produced
  file is either committed or staged per REQ-LIFE-05." This removes the ambiguity
  for test authors.
- **References:** PRD.md REQ-LIFE-05, REQ-LIFE-06
- **Checklist:** CHECK-P15

## Fix Execution Plan

### User Decisions Required
- **V-001:** [RESOLVED 2026-06-18] Declare "no numeric target (toolchain-dominated)."
- **V-002:** [RESOLVED 2026-06-18] Skip-and-keep — never overwrite a pre-existing
  allowed-meta file; seed interview defaults from it where sensible; note in summary.
  Captured as new requirement REQ-SCAF-09 (no OQ-06 needed).
- **V-003:** No decision needed (pure wording fix).

### Execution Steps

Apply in order. Each step is self-contained.

#### Step 1: Clarify REQ-PERF-01 quantification stance
- **Files:** specs/forge-bootstrap/PRD.md (§4.1)
- **Addresses:** V-001
- **Checklist:** CHECK-P11
- **Action:** Replace "SHOULD complete promptly" with either a soft bound scoped to
  file generation (excluding the toolchain lint/test pass) or an explicit statement
  that no numeric target applies because runtime is toolchain-dominated.
- **Depends on:** none (pending user decision per V-001)
- **Rationale:** Makes the deliberate non-quantification explicit so CHECK-P11 is
  unambiguously satisfied.

#### Step 2: Make pre-existing-meta-file handling explicit
- **Files:** specs/forge-bootstrap/PRD.md (§3.2 REQ-INPUT-05 or §3.3 REQ-SCAF-06; optionally §7)
- **Addresses:** V-002
- **Checklist:** CHECK-P14, CHECK-P15
- **Action:** Add a clause: when an allowed-meta LICENSE/README already exists,
  bootstrap MUST NOT overwrite it (per REQ-GATE-05); it skips or seeds the
  interview default from it and reports this in the completion summary. If deferred,
  add OQ-06 instead.
- **Depends on:** none (pending user decision per V-002)
- **Rationale:** Closes the only genuine spec gap — an interaction between the
  greenfield gate's no-modify rule and the scaffold's file generation.

#### Step 3: Disambiguate REQ-SCAF-08 "clean working tree"
- **Files:** specs/forge-bootstrap/PRD.md (§3.3 REQ-SCAF-08)
- **Addresses:** V-003
- **Checklist:** CHECK-P15
- **Action:** Reword to "leave no untracked/dangling scaffold files — every produced
  file is committed or staged per REQ-LIFE-05," dropping the word "clean."
- **Depends on:** none
- **Rationale:** Pure wording; prevents a literal-reading acceptance test from
  contradicting the staged-no-commit option.

## Fix Progress

- Step 1: [APPLIED] 2026-06-18 — REQ-PERF-01 reworded to declare no numeric target (runtime is toolchain-dominated); non-quantification now deliberate. (V-001)
- Step 2: [APPLIED] 2026-06-18 — Added REQ-SCAF-09: never overwrite a pre-existing allowed-meta LICENSE/README; skip generation, seed interview default from it, note in summary. (V-002)
- Step 3: [APPLIED] 2026-06-18 — REQ-SCAF-08 reworded from "leave the working tree clean" to "leave no untracked/dangling scaffold files — committed or staged per REQ-LIFE-05." (V-003)
