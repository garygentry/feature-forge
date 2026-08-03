# Verification Report: verify-test-debt (tech) — round 3
Date: 2026-08-03
Pipeline Stage: forge-2-tech (complete, v1)
Scope: RE-VERIFY per PRD C-04. The full 17-check tech sweep ran in round 1 and is not repeated.
Prior reports: VERIFY-tech-2026-08-03.md (11 findings, 5 blocking) · VERIFY-tech-round2-2026-08-03.md (4 findings, 1 blocking)

> **Trial note.** PRD REQ-TRIAL-01 capped this feature at 2 verify rounds per stage and
> REQ-TRIAL-02 makes reaching a third round the failure condition. This round was authorized
> deliberately, accepting that consequence, to obtain a clean-room confirmation of the round-2
> fixes rather than self-certifying them. The trial outcome is recorded separately; this report
> answers only whether the artifact is correct.

## Round-2 finding resolution

| ID | Verdict |
|---|---|
| V-012 dedup After column | RESOLVED — reads 7 (5 hash + 1 corrupt + 1 gate), consistent with §3.14's no-merge rule |
| V-013 inverted expansion / suite total | RESOLVED — expansion stated, 36 items, +31, 6 already-parametrized sites, ≈1781 |
| V-014 stale "§3.1's open risk" citation | RESOLVED — zero occurrences of "open risk" in the document |
| V-015 File-lines column | RESOLVED — 301 / 305, matching `wc -l` and the Body column's unit |

## Summary
- Total findings: 2
- Errors: 0 · Gaps: 0 · Inconsistencies: 2 · Improvements: 0
- **Blocking: none. This report is advisory-only.**

**Verdict: `passed`** (advisory findings attached).

### Verified correct (recorded so a later round does not re-litigate)
- `_ACCEPTED_HASHES` = 3 entries, `_REJECTED_HASHES` = 10. Five hand-rolled loops (2 accepted, 3 rejected) → 2×3 + 3×10 = 36 collected, delta +31. §8.2's arithmetic is exact.
- `_VERB_INVOCATIONS` holds exactly 8 verbs, so §8.2's "± up to +7 more" caveat is exact.
- §3.1 reproduces against `check_body_size`'s own rule: 301/295/2749 and 305/299/4365. `check-spec-purity.py` PASS, 0 violations.
- Collection baselines unchanged: suite 1842; prose file 43; `test_stage_exit_protocol.py` 102 (= 67 + 18 + 17); `test_state_verb_call_sites.py` 10.
- §8.2 suite arithmetic: 1842 − 39 − 60 − 1 + 7 + 1 + 31 = 1781.
- §3.5 canon re-derived with no drift: 34 fenced `state-*` calls; 2 literally carry `--epic`.
- §3.14 rosters exact: 5 hand-rolled hash loops + 4 already-parametrized; 6 gate tests under the section header; REQ-BRIT-04 = 5 sites / 11 comparisons.
- Traceability intact: 43 of 43 PRD REQ-* IDs traced, zero orphans either direction; all 7 constraints referenced; every §N.N cross-reference resolves; no `§10.2 item N` reference survives the round-1 renumbering.

## Findings

### V-016: §8.2's implementation-warning blockquote understates the defect history it cites
- **Severity:** inconsistency
- **Issue:** The blockquote claimed each round produced "exactly one defect of this shape". Checked against both reports, §8.2 was the location of **five of the fifteen** findings — round 1: V-005 (error), V-007, V-011; round 2: V-012 (error), V-013. The operative instruction was correct; only the supporting count was wrong. No arithmetic depended on it.
- **Status:** FIXED — restated as five of fifteen, with all five enumerated.

### V-017: §3.14's corrupt-file row used a different counting unit from its sibling rows
- **Severity:** inconsistency
- **Issue:** The hash row ("9 sites") and gate row ("6 sites") state family totals including already-parametrized sites; the corrupt-file row's "3 sites" counted hand-rolled only. The family total is 4 (3 hand-rolled + 1 already-parametrized). It was also the only family neither enumerated by name nor pinned by counting unit — the same shape as round 1's V-009 against the gate family. No arithmetic depended on it; §8.2 correctly uses hand-rolled counts throughout.
- **Status:** FIXED — row restated as 4 sites with the three hand-rolled tests named, family boundary pinned (`test_load_state_for_write_refuses_a_non_object_state_file` explicitly excluded), and §10.1 updated.

## Trial record (REQ-TRIAL-03 material)

| Round | Findings | Blocking | In comments/docstrings/narration |
|---|---|---|---|
| 1 | 11 | 5 | 0 |
| 2 | 4 | 1 | 0 |
| 3 | 2 | **0** | 0 |

Blocking findings converged 5 → 1 → 0. **Zero findings in any round landed in comments,
docstrings, or test narration** — the failure mode that produced rounds 5–9 of the
stage-exit-coverage epic (11 of 12 blocking findings in narration) did not recur once.

Every substantive factual claim introduced by a fix pass reproduced exactly on independent
re-derivation across all three rounds. One fix deviated from its prescribed remedy (finding
9 hash sites where 5 were prescribed) and the deviation was strictly better.

The recurring defect shape was structural, not narrative: **a summary table left stale by a
correction made elsewhere in the document.** Five of fifteen findings landed in §8.2 alone.
The rosters were correct every time. Recorded pattern: *when a fix corrects a roster's arity,
the summary table consuming that roster is the defect site, not the roster.*
