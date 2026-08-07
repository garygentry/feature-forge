# Verification Report: loop-recovery (prd) — RE-VERIFY (scoped, round 2)
Date: 2026-08-05
Pipeline Stage: forge-1-prd — scoped re-verify after fix commit 526119329d8d2885cd3fa89d54a3fc674c6d184f (verify entry was `findings-applied`)
Artifacts Reviewed:
- `specs/loop-recovery/PRD.md` (post-fix)
- `specs/loop-recovery/.verification/VERIFY-prd-2026-08-05.md` (prior report, V-001..V-013)
- Fix delta (`git show 5261193`)
- Grounding: `tests/test_always_loaded_surface.py`, `scripts/validate.sh`, `.github/actions/quality-gate/action.yml`, `tests/test_stage_constants_parity.py`

Scope: 13 of 13 prior findings re-confirmed against acceptance evidence + delta scan of the fix's 145 changed lines. Results: **13/13 RESOLVED, 0 UNRESOLVED, 3 new advisory observations, 0 blocking.**

## Prior Findings — Confirmation

- **V-001 — RESOLVED.** REQ-DEC-01 Notes (untracked run-local, survives session end/clear); REQ-OUT-03 clean-tree exclusion clause; OQ-2 annotated settled.
- **V-002 — RESOLVED.** REQ-TREE-02 Notes (best-effort runner-native attribution, unattributed-set fallback, §5 permission not spent); §5 mirrors.
- **V-003 — RESOLVED.** REQ-UNB-02 per-item test authoritative; REQ-UNB-03 partial = failed recovery, naming movers/non-movers; REQ-OUT-03 aligned.
- **V-004 — RESOLVED.** OQ-4 added; REQ-CLU-01 Notes bound the deferral.
- **V-005 — RESOLVED.** REQ-DEC-06 (every branch records, unapplied re-surfaced); REQ-REL-02 generalized to failed unblock operations.
- **V-006 — RESOLVED.** §4.5 REQ-SEC-01 (no secrets solicited, no credential material, actor field session/actor only).
- **V-007 — RESOLVED.** All six §4 NFRs P0; 37 REQ IDs / 37 Priority lines, 1:1.
- **V-008 — RESOLVED.** REQ-COMPAT-02 exemption rewritten (detection silent on clean tree; decision only on dirty tree); SC 4 scoped to clean-tree happy path.
- **V-009 — RESOLVED.** REQ-DEC-07 (append-only re-decision, latest-entry unapplied set, backlog-lifetime retention, consolidated items independently re-decidable).
- **V-010 — RESOLVED.** SC 1 names the fixture-backlog replay vehicle (3 roots, 13-deep chain, one shared cause).
- **V-011 — RESOLVED.** §5 bullets marked MUST / MUST / SHOULD-prefer / MUST. (See V-014 for an over-claim the rewrite introduced.)
- **V-012 — RESOLVED.** §4.6 REQ-PERF-01 (P2), linear topology computation, explicit no-further-targets position.
- **V-013 — RESOLVED.** §1 names the backlog-author actor.

Delta integrity: all 37 REQ references resolve (0 dangling); OQ-1..4 defined; new IDs unique; §3 ordering note still covers every family; no contradictions introduced.

## New Findings (all advisory)

### V-014: §5's "(parity tests enforce all three)" over-claims the enforcement mechanism
- **Severity:** inconsistency
- **Location:** PRD.md §5 "Canon/adapter discipline (MUST)"
- **Issue:** Only the constants obligation is a parity test. Ruff is enforced by `scripts/validate.sh` step 7b (SKIPs locally when ruff is absent) and CI's Quality Gate; adapter regen by the adapter-src verify + `tests/test_build_adapters.py`. A tech-spec author would look for a parity test covering lint and find none.
- **Suggested fix:** Replace the parenthetical with the per-obligation gate list (adapter-src verify in CI + `tests/test_build_adapters.py`; the ruff step in `scripts/validate.sh` and CI's Quality Gate, local step skippable; `tests/test_stage_constants_parity.py` for the constants).
- **Checklist:** CHECK-P13 (delta scan of the V-011 fix)

### V-015: REQ-DEC-01's "never dirty the working tree" holds only if the record is git-*ignored*, not merely untracked
- **Severity:** improvement
- **Location:** PRD.md §3.1 REQ-DEC-01 Notes; §7 OQ-2
- **Issue:** An untracked-but-not-ignored file shows as `??` in `git status --porcelain` and would read as a dirty tree. The property holds today only because `**/.rauf/*` (#195) matches the proposed location — but OQ-2 defers the location, so a tech spec landing the record outside an ignored path silently falsifies the note. Decision 1 is not re-litigated; this is the note's stated *reason*, one word wide.
- **Suggested fix:** "Because it is untracked **and git-ignored**…"; add to OQ-2 that the chosen location MUST fall under an existing ignore rule.
- **Checklist:** CHECK-P08 (delta scan of the V-001 fix)

### V-016: Two residual wording infelicities in newly written clauses
- **Severity:** improvement
- **Location:** PRD.md §4.4 REQ-COMPAT-02; §3.1 REQ-DEC-07; §4.5 REQ-SEC-01
- **Issue:** (a) REQ-COMPAT-02's "beyond the Step 2a depth line" exempts from a category (prompts/decisions) the depth line never belonged to. (b) REQ-DEC-07's "undecided-or-unapplied" — a decision record holds only decided entries. (c) REQ-SEC-01's "repo-visible" reads as a factual claim contradicting the untracked position.
- **Suggested fix:** (a) "…no new required *operator decisions*; the only new happy-path output is the Step 2a depth line of REQ-TOPO-03." (b) "the latest unapplied entry per item". (c) "non-sensitive" in place of "repo-visible". Editorial only.
- **Checklist:** CHECK-P08, CHECK-P15 (delta scan of the V-008/V-009/V-006 fixes)

## Fix Execution Plan

### User Decisions Required
None — the six prior decisions stand and are not reopened. V-014/V-015/V-016 are one-clause editorial corrections requiring no position call.

### Execution Steps

#### Step 1: Correct the §5 enforcement claim
- **Files:** PRD.md (§5)
- **Addresses:** V-014
- **Action:** Replace "(parity tests enforce all three)" with the per-obligation gate list per V-014.
- **Depends on:** none

#### Step 2: Tighten the durability note's stated reason
- **Files:** PRD.md (§3.1, §7)
- **Addresses:** V-015
- **Action:** "untracked **and git-ignored**" in REQ-DEC-01 Notes; OQ-2 gains "chosen location must fall under an existing ignore rule".
- **Depends on:** none

#### Step 3: Editorial cleanup of three new clauses
- **Files:** PRD.md (§3.1, §4.4, §4.5)
- **Addresses:** V-016
- **Action:** Apply the three rewordings verbatim; re-check the 37/37 Priority-to-ID count afterward.
- **Depends on:** none

**Verdict: advisory-only — recorded as `passed` with this report attached.** The three advisories stay discoverable for whoever next touches the PRD; V-015 is carried into forge-2-tech via the pipeline `notes` field alongside OQ-2.
