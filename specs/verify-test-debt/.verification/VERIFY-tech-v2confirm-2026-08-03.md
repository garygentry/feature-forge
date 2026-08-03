# Verification Report: verify-test-debt — confirming round, v2 cycle
Date: 2026-08-03
Pipeline Stage: forge-1-prd v2 · forge-2-tech v2
Scope: CONFIRMING RE-VERIFY per C-04 over `.verification/VERIFY-tech-v2delta-2026-08-03.md`
(11 findings, fixes in `54a3407`). tech-spec §2–§9 technical content verified `passed` at
v1 round 3; not re-reviewed. Nothing from §8.4, §10.2 or a prior RESOLVED grading re-filed.

## Summary
- Total findings: 11 — **Errors 0 · Gaps 0** · Inconsistencies 8 · Improvements 3
- **Stage-blocking: 0. Advisory-only.**
- **Verdict: `passed`.**
- v2 cycle convergence: **2 → 0** (converged; REQ-TRIAL-02 satisfied).

## Prior-finding resolution: 11 / 11 RESOLVED
V-001 per-stage scoping · V-002 plan halt · V-003 REQ-TRIM-03 mechanism · V-004 §6/§2
premises · V-005 stale REQ-TRIAL citations · V-006 present-tense v1 premises · V-007
denominators · V-008 outstanding-counting · V-009 §8 derivation declaration · V-010
advisory-narration series · V-011 provenance. Two carried residue, re-filed below.

## Retro-classification, re-derived independently from the reports

| Case | Blocking per round | Under amended rules |
|---|---|---|
| `verify-test-debt` forge-2-tech v1 | 4err+1gap=**5** · 1err=**1** · **0** | **PASSES** |
| `stage-exit-coverage` impl | 1err+3gap=**4** · 2err=**2** · 2err+1gap=**3** | **STILL FAILS at round 3** (3 ≥ 2) |

Verdict stable under both readings of round 2's PARTIAL-graded carry (4 → 3 → 3 also fails).
The *sequence* is not stable, which is finding V-008.

## Findings (all applied)

| ID | Sev | Issue | Status |
|---|---|---|---|
| V-001 | inconsistency | **REQ-GUARD-01 (P0) still named `shared-conventions.md` as canonical**, contradicting OQ-02's v2 resolution, tech-spec §1/§2/§3.1 and the user-locked decision. forge-3-specs traces requirement text verbatim, so this would have propagated the wrong canon file. | FIXED |
| V-002 | inconsistency | tech-spec §3.5 and §1 described PRD **v1**'s REQ-TRIM-03 in the present tense, asserting the current requirement is unimplementable. | FIXED |
| V-003 | inconsistency | tech-spec §10.3 said REQ-TRIAL-04 records "per stage, three things" — v2 requires **four**, per stage **and per stage version** — and dropped REQ-TRIAL-02's stage-version scoping from its summary. | FIXED |
| V-004 | inconsistency | "five of seventeen" wrong — **six** of 17 findings landed in §8.2 (round 3's V-016 also did). Corrected in all three locations. | FIXED |
| V-005 | inconsistency | Plan's "Decisions locked" #4 still stated the ≤2-round-or-reopen rule with no amendment pointer. | FIXED |
| V-006 | inconsistency | Plan's Status header said "next stage is forge-2-tech". | FIXED |
| V-007 | inconsistency | Plan work item R-10 stale on three counts (canon file, "six surfaces become pointers", "~3 tests"). | FIXED |
| V-008 | improvement | REQ-TRIAL-02 leaves two cases undefined: a **PARTIAL** resolution is neither confirmed-resolved nor confirmed-unresolved; and the version-bump reset is unbounded, so re-authoring after each blocking round makes clause (b) unfalsifiable. | **DEFERRED** |
| V-009 | inconsistency | Plan counted forge-1-prd and forge-2-tech rounds in different units. Unit pinned; forge-1-prd restated as 1. | FIXED |
| V-010 | improvement | **REQ-TRIAL-01 cannot fail at any pre-implementation stage** — forge-1-prd/forge-2-tech author no comments, docstrings or test narration, so 0/17 is structurally guaranteed. The decisive datapoint is forge-5-loop. | **DEFERRED** |
| V-011 | improvement | REQ-TRIAL-04's four series do not measure REQ-TRIAL-06's failure mode: derived-figure defects are predominantly advisory, so the convergence sequence cannot see them. | **DEFERRED** |

## Deferred to forge-5-loop (recorded position)

V-008, V-010 and V-011 all amend REQ-TRIAL-02/04 — the rules currently governing whether
this feature proceeds. Amending them again would bump the PRD to v3 and start a third
convergence sequence, and **all three first bind at forge-5-loop**: V-010's narration axis
is not under test until code is authored; V-008's PARTIAL and version-bump cases have not
arisen; V-011's derived-figure series has nothing to collect until specs exist. They are
accepted as correct and deferred to the stage where they take effect, so a later round
resolves them against this position rather than re-filing.

## Trial record (REQ-TRIAL-04)

| Stage / version | Rounds | Narration churn | Convergence | Advisory narration |
|---|---|---|---|---|
| forge-1-prd v1 | 1 | 0 / 10 | resolved, no fix round | 0 |
| forge-2-tech v1 | 3 | 0 / 17 | 5 → 1 → 0 | 0 |
| forge-2-tech v2 | 2 | 0 / 22 | 2 → 0 | 0 |

**Caveat of record (V-010):** every narration-churn zero above is structurally guaranteed —
these stages author specification prose, not code. The measurement becomes falsifiable only
at forge-5-loop, where the original epic's churn actually occurred (11 of 12 blocking
findings, all in the impl stage). GATE-P3 is therefore **provisionally met**, not proven.
