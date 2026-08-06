# Verification Report: loop-recovery (specs)

- **Date:** 2026-08-06
- **Pipeline stage:** forge-3-specs (complete, v1 @ 177fe9b)
- **Mode:** clean-room `forge-verifier`, require-clean, owner: nested (in-stage verify)
- **Artifacts reviewed:** PRD.md, tech-spec.md, 00–07 spec suite, TRACEABILITY.md
- **Checks executed:** 38 of 38 (35 pass, 3 advisory-only, 0 not-applicable)

## Summary

- Total findings: **3** — Gaps: 0 · Inconsistencies: 2 · Improvements: 1 · Errors: 0
- **Advisory-only — no blocking (`error`/`gap`) findings.** Requirement coverage (37/37,
  zero orphans), tech-spec fidelity (D1–D8), cross-document type/constant consistency, and
  integration-point accuracy all hold. Every spot-checked `forge-session.py` / `tests/` /
  reference-file / rauf source symbol resolves at (or adjacent to) its cited line. Carried
  tech advisories V-012 / V-015 are both discharged in `07`.
- **Disposition: all three fixes applied in the same session** (see Resolution per finding).

## Findings

### V-001 — `cmd_decision_list` docstring contradicted its own strict-parse contract
- **Severity:** inconsistency · **Location:** 02-decision-record.md §4.2 (docstring)
- **Issue:** Docstring said a corrupt record "is read tolerantly for a plain listing but
  still parsed strictly for the unapplied computation," while the code, the closing prose,
  and the §Verification checklist all require **strict** parse (exit 2) on both paths. An
  implementer could add a forbidden tolerant plain-list branch.
- **Checklist:** CHECK-S19, CHECK-S20
- **Resolution:** APPLIED — docstring replaced with the strict-always contract ("parses an
  existing record strictly (exit 2 on corruption) for both the plain and `--unapplied`
  forms — never downgrades a corrupt record to `{}`"). Code unchanged (already correct).

### V-002 — `resolved` gate condition (a) needed an explicit per-affected-item intersection
- **Severity:** improvement · **Location:** 05-recovery-procedure.md §2 step 7 (cond. 1);
  03 §3 (cond. a); verb in 02 §5.1
- **Issue:** The gate requires `decision-list --unapplied` empty "for the affected items,"
  but the verb returns the **global** latest-unapplied set with no `--item` filter. A naive
  `count == 0` on the raw payload would let an *unrelated* item's deferral suppress a
  legitimate `resolved`. Fails safe (never a false `resolved`), so improvement not gap.
- **Checklist:** CHECK-S23, CHECK-S24
- **Resolution:** APPLIED — 05 §2 step 7 condition 1 now states the procedure intersects
  the `decision-list --unapplied` payload (entries carry `itemId`) with the session's
  affected-item set and tests only that intersection for emptiness.

### V-003 — `07` mislabeled `test_stage_exit.py:3207` as the resume-routing parametrize
- **Severity:** inconsistency · **Location:** 07-testing-strategy.md §4.2 vs 03 §7.2
- **Issue:** `07` called `:3207` "the hand-listed resume/recover parametrize … on the
  resume side," but `:3207` is `test_a_non_complete_loop_outcome_still_offers_no_continuation`
  (a no-continuation invariant over all non-complete outcomes). `03 §7.2` correctly cites
  the resume-fence at `:2348`. Both hand-listed sites plus the `EXIT_OUTCOMES` mirror
  (`:626`) genuinely need `"resolved"`; the mislabel risked an implementer editing the
  wrong test for the wrong reason.
- **Checklist:** CHECK-S15, CHECK-S12
- **Resolution:** APPLIED — 07 §4.2 now enumerates the full hand-listed set requiring
  `"resolved"` (`:626` mirror, `:2348` resume-fence, `:3207` no-continuation invariant),
  correctly labels each, and notes `:2358` (recover-fence) is deliberately excluded.

## Notes

- `autoFixEligible` was false for this exit; the fixes were applied by deliberate operator
  choice (advisory-only, no design change, no user decisions), consistent with the
  dogfood constraint (PRD §5). The report is retained as the provenance record.
