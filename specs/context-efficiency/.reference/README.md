# context-efficiency — Pre-Pipeline Reference Set

Input material for the forge pipeline. **Whichever stage starts this feature
(`forge-1-prd context-efficiency`, or `forge-0-epic context-efficiency` if
decomposed) should read all five documents before the interview begins.**

Reading order:

1. `CHARTER.md` — what this work is, scope/non-goals, hard constraints,
   success criteria, epic-decomposition option. Start here.
2. `AUDIT.md` — the full 2026-07-19 assessment: what already works (and must
   not regress) and the findings summary.
3. `LOAD-MAP.md` — the measured data: file sizes, per-consumer usage
   matrices, per-invocation load estimates, and the per-stage savings model
   (baseline → post-R1–R6 → post-R7, with a per-feature rollup). Baselines to
   re-measure at implementation time.
4. `RECOMMENDATIONS.md` — the seven ranked changes (R1–R7) with mechanisms,
   savings, risks, and sequencing; plus watch items W1/W2.
5. `GUARDRAILS.md` — repo-specific don't-break constraints (CI gates, adapter
   fan-out, drift-guard tests, prelude history, dual-role hazard, release
   mechanics).

These documents are the *evidence base*, not the PRD: requirements-level
decisions (which recommendations are in V1, feature vs. epic, success
thresholds) belong to the interview.
