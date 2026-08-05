# Verification Report: verify-test-debt (tech) — round 2
Date: 2026-08-03
Pipeline Stage: forge-2-tech (complete, v1); forge-verify-tech: findings-applied
Scope: RE-VERIFY per PRD C-04 — confirms the round-1 report's findings. The full 17-check
tech sweep ran in round 1 and is not repeated.
Prior report: .verification/VERIFY-tech-2026-08-03.md (11 findings, 5 blocking)

## Round-1 finding resolution

| ID | Verdict |
|---|---|
| V-001 body-cap measurement | RESOLVED — measured table reproduces exactly; open-risk blockquote and canon-deleting fallback removed |
| V-002 `_validated_findings_file` label | RESOLVED — defaulted `label` param; 5 branch messages and 1 call site confirmed in source |
| V-003 structural region | RESOLVED — fence-block bound, all 3 measurements reproduce, residual declared, mutation control added |
| V-004 hash roster | RESOLVED (deviated, correctly) — fix found both sub-families; 9 sites / 5 loops confirmed, no sixth loop exists |
| V-005 call-sites arithmetic | RESOLVED — 10 → 9, both deletions named |
| V-006 fourth guard test | RESOLVED — declared in PROTECTS with reconciling paragraph |
| V-007 dedup units | PARTIAL — units declared, After column not recomputed → V-012 |
| V-008 ordering invariant | RESOLVED — two-case data flow in §6.1, §7 amended |
| V-009 gate-selection roster | RESOLVED — 6 confirmed, unit pinned; PRD ×6 is correct |
| V-010 REQ-COV-07 placement | RESOLVED — moved to test_stage_exit.py |
| V-011 test-count table | RESOLVED (numeric residual → V-013) |

## Summary
- Total findings: 4
- Errors: 1 · Inconsistencies: 3 · Gaps: 0 · Improvements: 0

Blocking: V-012.

### Verified correct this round (recorded so a later round does not re-litigate)
- §3.1 body-cap table reproduces against `check_body_size`'s own rule. `check-spec-purity.py` PASS, 0 violations.
- §3.14 hash roster exact and complete: 9 sites, 5 hand-rolled loops, no sixth anywhere in `tests/`.
- §3.14 gate-selection roster exact: 6 under the section header, 1 already parametrized. PRD ×6 confirmed.
- §3.5 all three measurements reproduce independently: heading 34/34 green + 12/34 detection; fence-block 34/34 + 20/34; call-line 33/34 with the single false failure at `shared-conventions.md:348`. Naive heading detection yields exactly the 2 predicted false failures. The `state-artifact` regression replays: heading-blind, fence-detects.
- "2 of 34 fenced calls literally carry `--epic`" reproduces.
- §3.8 helper claims exact: 5 branch-specific messages, all hardcoding `--findings-file`, 1 call site. §5's example is a byte-exact label substitution.
- §8.2 per-file figures reproduce by `pytest --collect-only`: 43 / 102 (67+18+17) / 10 / suite 1842.
- No `§10.2 item N` cross-reference exists anywhere, so deleting old item 1 orphaned nothing.

## Findings

### V-012: §8.2's dedup After column (3) contradicts §3.14's "do not merge the five hash loops" — correct value is 7
- **Severity:** error
- **Location:** §8.2 dedup row and the Units paragraph below it
- **Issue:** §3.14 now says 5 hand-rolled hash loops are parametrized **in place, one per test**, and explicitly forbids merging them (it would delete `test_epic_commit_2_rejects_a_short_or_malformed_hash_before_mutation`'s epic-target coverage). §8.2's After column still read 3, which is only reachable by collapsing the five into one. Correct: 5 hash + 1 corrupt + 1 gate = **7**. This is the unresolved half of V-007 — the Before column was recomputed, the After column was not; and it reproduces V-005's failure shape in the adjacent row.
- **Status:** FIXED — row now reads 7, Units paragraph restated with per-family arithmetic.

### V-013: "approximately neutral in collected items" is inverted; expected suite total understated
- **Severity:** inconsistency
- **Issue:** Parametrizing a hand-rolled loop **expands** 1 collected item into N. Measured: `_ACCEPTED_HASHES` = 3 entries, `_REJECTED_HASHES` = 10, so the five hash loops go 5 → 2×3 + 3×10 = 36, a delta of **+31**, not ≈0. Expected suite total is therefore ≈1781, not ≈1750. Also "the 4 already-parametrized sites" undercounts — there are 6 (4 hash, 1 corrupt, 1 gate).
- **Status:** FIXED — expansion stated, total corrected to ≈1781, count corrected to 6.

### V-014: §3.15 cites "§3.1's open risk", which the V-001 fix deleted
- **Severity:** inconsistency
- **Status:** FIXED — now reads "(§3.1, measured — both affected skills are under the cap)".

### V-015: §3.1's File-lines column off by one against `wc -l` (302/306 vs 301/305)
- **Severity:** inconsistency
- **Issue:** 302/306 is `len(text.split("\n"))`, counting the trailing empty split artifact; the Body column drops it, so the two columns used different units. No decision rests on this column.
- **Status:** FIXED — now 301/305, matching `wc -l` and the Body column's unit.

## Trial observation (REQ-TRIAL-03 material)

Across both rounds, every substantive claim the fix pass introduced (body cap, hash roster,
gate roster, all three §3.5 measurements, the helper's message count and call site)
reproduced exactly on independent re-derivation. The round-1 fix's one deviation from the
prescribed remedy (9 hash sites rather than the prescribed 5) was strictly better than the
prescription.

The one genuinely new defect in round 2 (V-012) is a count that the fix's **own correction**
invalidated in a different section — the same shape as round 1's V-005/V-007 pair. Pattern
worth recording: *when a fix corrects a roster's arity, the summary table that consumes that
roster is the defect site, not the roster.*

Zero findings across both rounds landed in comments, docstrings, or test narration — the
failure mode that produced rounds 5–9 of the stage-exit-coverage epic did not recur.
