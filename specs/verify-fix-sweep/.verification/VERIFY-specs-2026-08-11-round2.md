# Verification Report: verify-fix-sweep (specs — scoped re-verify, round 2)
Date: 2026-08-11
Pipeline Stage: forge-3-specs (v1); re-verify of fix commit 6a1b8e3
Scope: R-06 scoped re-verify — 28 prior-finding confirmations + fix-delta examination. The 38-check specs checklist was NOT re-run. Recorded decisions D1/D2/D3 and V-022's accepted guard treated as settled.

Deterministic gate: validate-traceability.py → 16/16 covered, 0 orphans, valid: true; 01-architecture-layout.md now carries REQ-SWEEP-01..07 + REQ-CARD-01/02/03.

## Summary
- Total findings: 6
- Gaps: 0
- Inconsistencies: 4
- Improvements: 2
- Errors: 0
- Blocking (errors + gaps): 0 — advisory-only, report records passed with this file attached

Prior-report confirmation: 26 of 28 RESOLVED; V-020 PARTIALLY (secondary "tighten 05 §2.7/§2.8 stems" clause unapplied — advisory); V-003 resolved exactly as prescribed (but see N-002). Verdict: **RE-VERIFY: PASS** — no unresolved prior finding, no new blocking defect.

## Findings (all advisory — recorded for whoever next touches these documents)

### N-001: 00 §7.2's re-run grammar still states the blanket suppression V-001 replaced
- **Severity:** inconsistency
- **Location:** 00-core-definitions.md §7.2, final grammar bullet
- **Issue:** The bullet still reads "previously dispositioned hits are matched by (file, needle) and not re-dispositioned" — after the V-001 fix, 03 §4.4/§4.6 make that suppression conditional (JUSTIFIED/FALSE-POSITIVE only; a re-reported FIXED must be re-dispositioned). Canon contradicts the normative rule; 00 was not in V-001's Location list so the fixer never opened it.
- **Suggested fix:** Amend the bullet: "…a previously dispositioned hit matched by (file, needle) needs no second disposition when its first disposition was JUSTIFIED or FALSE-POSITIVE — a re-reported FIXED is a failed fix and must be re-dispositioned (03-forge-fix-integration.md §4.4)."
- **Checklist:** CHECK-S18, CHECK-S21

### N-002: 05 §2.5.1/§4 claim all five git-classification rows discharged; the diff-HEAD row has no test
- **Severity:** inconsistency
- **Location:** 05-testing-strategy.md §2.5.1 (closing sentence), §4 (coverage bullet)
- **Issue:** The four prescribed tests cover rows 1, 2, 5 (+row 1 at helper level); §2.5 covers rows 1 and 3. No named test exercises `diff HEAD` non-zero → exit 2, so both "every row is covered" sentences are false (the prior report's own prescription paired four tests with a five-row claim).
- **Suggested fix:** Add a fifth §2.5.1 bullet: monkeypatched run_git non-zero for `diff HEAD` in a valid repo → UsageError → exit 2, `Error: git diff failed …` stderr.
- **Checklist:** CHECK-S34, CHECK-S36

### N-003: 05 §8's extended mutation checkbox is false for CHECK-I21 and CHECK-I22
- **Severity:** inconsistency
- **Location:** 05-testing-strategy.md §8 (second checkbox)
- **Issue:** "Removing … any CHECK-I21/I22/I23 degradation clause fails at least one guard" — membership assertions over the whole Runnability slice cannot isolate which check supplied a literal (`never a hard fail`/`never mid-loop` come from the preamble; `not-applicable` appears at four lines). Only I23's sub-slice is genuinely protected. D3's heading-termination remains correct and green-preserving.
- **Suggested fix:** (a) narrow the checkbox to I23 + the preamble sentence, or (b) prescribe per-check sub-slicing in the two smoke tests so the claim becomes true. (a) is line-cheap and sufficient.
- **Checklist:** CHECK-S34, CHECK-S37

### N-004: The pinned bare-repo message interpolates {repo_root}, which does not exist at the raise site
- **Severity:** inconsistency
- **Location:** 02-fix-sweep-script.md §6, §10; mirrored in 05 §2.5.1
- **Issue:** 02 §4.1 raises the bare-repo UsageError when `rev-parse --show-toplevel` FAILS — `repo_root` is assigned only on success. The message names a variable the raise site cannot have; implementers will silently substitute.
- **Suggested fix:** Use `{start_dir}` (the --repo-root value, default cwd) in all three sites and note it in 02 §4.1's Raises block.
- **Checklist:** CHECK-S20, CHECK-S12

### N-005: 05 §2.1 calls GIT_UNAVAILABLE/GIT_TIMEOUT_SECONDS "00-anchored"; they are defined only in 02 §1.3
- **Severity:** improvement
- **Location:** 05-testing-strategy.md §2.1
- **Suggested fix:** Reword to "…plus 02 §1.3's git constants"; optionally also pin VERIFICATION_EXCLUDE_LABEL == ".verification/" which §2.6 now depends on.
- **Checklist:** CHECK-S12

### N-006: D3's heading-termination not extended to the structurally identical lifecycle slice
- **Severity:** improvement
- **Location:** 05-testing-strategy.md §3 (lifecycle row); 04-verification-checks.md §5.2
- **Issue:** Once CHECK-B29 is appended to backlog.md, its `not-applicable`/`never a hard fail` literals fall inside test_b27_present_and_advisory's end-of-file slice — partial erosion of B27's guard (its fabricate/dependson/fixture assertions unaffected).
- **Suggested fix:** Heading-terminate the lifecycle slice too; update 04 §5.2 to say all three slices are heading-terminated.
- **Checklist:** CHECK-S34, CHECK-S25

## Fix Execution Plan

### User Decisions Required
None — all six are one- or two-sentence edits with stated defaults (N-002/N-003 default to their (a) options).

### Execution Steps

#### Step 1: Canon alignment in 00-core-definitions.md
- **Files:** specs/verify-fix-sweep/00-core-definitions.md
- **Addresses:** N-001
- **Action:** §7.2 final grammar bullet → disposition-aware wording per N-001, citing 03 §4.4.
- **Depends on:** none

#### Step 2: Message-shape correction in 02-fix-sweep-script.md
- **Files:** specs/verify-fix-sweep/02-fix-sweep-script.md
- **Addresses:** N-004 (part)
- **Action:** §6 + §10: {repo_root} → {start_dir} in the bare-repo shape; §4.1 Raises note.
- **Depends on:** none

#### Step 3: Testing-strategy corrections in 05-testing-strategy.md
- **Files:** specs/verify-fix-sweep/05-testing-strategy.md
- **Addresses:** N-002, N-003(a), N-004 (part), N-005, N-006 (part), V-020 residual
- **Action:** §2.1 reword; §2.5.1 fifth bullet + {start_dir}; §2.7/§2.8 assert message stems; §3 lifecycle slice heading-termination; §8 checkbox narrowed per N-003(a).
- **Depends on:** Step 2

#### Step 4: Cross-document note in 04-verification-checks.md
- **Files:** specs/verify-fix-sweep/04-verification-checks.md
- **Addresses:** N-006 (part)
- **Action:** §5.2: "the two impl slices" → "all three slices are heading-terminated".
- **Depends on:** Step 3

#### Step 5: Re-run validate-traceability.py — confirm 16/16, 0 orphans (regression check).

## Fix Progress
