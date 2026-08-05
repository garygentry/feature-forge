# Verification Report: verify-test-debt — scoped v1→v2 amendment delta
Date: 2026-08-03
Pipeline Stage: forge-1-prd v2, forge-2-tech v2
Scope: DELTA ONLY — the v1→v2 amendment. tech-spec §2–§9 was verified `passed` at v1
(round 3) and was not re-reviewed. Nothing from the three prior reports, §8.4 (declared
non-goals) or §10.2 (recorded positions) is re-filed.

## Summary
- Total findings: 11 — Errors 2 · Inconsistencies 4 · Improvements 5 · Gaps 0
- Blocking: V-001, V-002. **Both fixed.**

## Blocking

### V-001: REQ-TRIAL-02 lost its per-stage scoping — as written it stopped every later stage
- **Severity:** error · **Status:** FIXED
- The `≥1` correction also deleted "across consecutive verify rounds at a single stage".
  Read literally, clause (b) compared against the previous round *anywhere in the feature*:
  the first blocking round of any later stage would satisfy `≥1 ≥ 0` (every stage ends at
  zero) and trip the stop, and `forge-2-tech` round 1 (5 blocking, preceded by the
  advisory-only PRD round at 0) would itself have been misclassified.
- **Fix:** restored scoping and made all three counting rules explicit and named —
  the `≥1` qualifier, scope of **one stage at one stage version**, and **outstanding**
  rather than newly-filed counting (V-008).

### V-002: the remediation plan still instructed a fresh session to halt the feature
- **Severity:** error · **Status:** FIXED
- `plans/remediation-stage-exit-coverage.md` still declared Phase 3 **STOPPED** and GATE-P3
  **FAILED** under the superseded round-count rule, and carried superseded rosters in R-11
  and R-13.
- **Fix:** success metric, GATE-P3 status, phase row, running totals and both work items
  reconciled to the amended rules; Session Log entry appended recording the option-(b)
  decision.

## Advisories (all applied)

| ID | Sev | Issue |
|---|---|---|
| V-003 | inconsistency | REQ-TRIM-03 still mandated the `--epic`-in-fence mechanism §8 disclaimed — corrected to the structural block scan |
| V-004 | inconsistency | §6 and §2 carried pre-v2 premises (`resolver_line_identical` assertion; round-count-only user story) |
| V-005 | inconsistency | Stale citations: §3.9's "REQ-TRIAL-01's 2-round budget"; §10.3's "(REQ-TRIAL-01..03)" heading |
| V-006 | inconsistency | §3.13/§3.14/§10.1 described PRD v1's premises in the present tense — retensed to name v1 |
| V-007 | improvement | "five of fifteen" (§8.2) vs "five of seventeen" (§10.3) — disambiguated by denominator |
| V-008 | improvement | "produces" vs "outstanding" undefined; changes the stop round on real data — **adopted** as counting rule 3 |
| V-009 | improvement | PRD §8's derived figures lacked the REQ-TRIAL-06 declaration the same commit created — added |
| V-010 | improvement | REQ-TRIAL-01 measures floor-compliance, not churn incidence — **adopted**, advisory-narration series added to REQ-TRIAL-04 |
| V-011 | improvement | v2 provenance pointed at a commit predating the worktree edits — resolved by committing and re-recording |

## Found by the author, past the verifier

A **third** counting defect, not filed by the verifier: this delta round itself recorded 2
blocking findings after round 3's 0. Under the rule as then written (`≥1` and `≥ previous`)
that would have tripped the stop — even though it verifies a **new stage version** rather
than re-verifying v1. Resolved by scoping convergence per **stage version** (counting rule
2), so a version bump starts a fresh sequence.

## Retro-classification, verified against real reports

| Case | Blocking sequence | Under amended REQ-TRIAL-02 |
|---|---|---|
| `verify-test-debt` forge-2-tech v1 | 5 → 1 → 0 | **passes** (round 3 resolves) |
| `stage-exit-coverage` impl | 4 → 2 → 3 | **still fails at round 3** |

The amendment preserves the behavior it must preserve. The second row is measured from
that epic's own reports, not asserted.

## Trial record (REQ-TRIAL-04)

| Stage / version | Rounds | Narration churn | Convergence |
|---|---|---|---|
| forge-2-tech v1 | 3 | **0 / 17** | 5 → 1 → 0 |
| forge-2-tech v2 (amendment) | 1 | **0 / 11** | 2 blocking, fixed |

Zero narration-churn findings in any round of either cycle.
