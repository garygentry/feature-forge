# Verification Report: loop-recovery (tech — scoped re-verify, round 2)
Date: 2026-08-05
Pipeline Stage: forge-2-tech (`forge-verify-tech` = `findings-applied`, fix commit `5a5ce13`)
Artifacts Reviewed: `specs/loop-recovery/tech-spec.md` (post-fix), `specs/loop-recovery/.verification/VERIFY-tech-2026-08-05.md`, `specs/loop-recovery/PRD.md`, `specs/loop-recovery/.pipeline-state.json`, `git show 5a5ce13`; spot-verified against `scripts/{forge-session.py,check-spec-purity.py}`, `references/stage-exit-protocol.md`, `skills/forge-5-loop/SKILL.md`, `skills/forge-verify/SKILL.md`, `skills/forge-4-backlog/SKILL.md`, `skills/forge-verify/references/verification-checklists/backlog.md`, `tests/{test_stage_exit.py,test_stage_exit_protocol.py,test_lifecycle_artifact_check.py,test_compliance_eval.py,_state_schema.py}`, `eval/run-compliance-eval.py`, `docs/architecture/stage-exit-coverage/{cli-reference.md,architecture.md}`, `specs/verify-test-debt/{backlog.json,.rauf/state.json,.rauf/archive/20260804-151825-events.ndjson}`, and rauf sources `/home/gary/workspace/rauf/packages/{core/src/backlog.ts,loop/src/runner.ts,cli/src/backlog-commands.ts}` + `/home/gary/workspace/rauf/CHANGELOG.md`
Checks Executed: scoped re-verify — 11 of 11 prior findings confirmed + full delta-scan of the fix commit's 239 changed tech-spec lines (not a fresh 17-check sweep, per `references/stage-exit-protocol.md` § "Re-verify scope and convergence")

## Prior Findings — Confirmation

| ID | Verdict | Evidence |
|---|---|---|
| V-001 | **RESOLVED** | §6 `rauf unblock` row now states it clears `status`/`blockedReason`/`needsHuman`/`deferred`; re-read `backlog.ts` — `432-433` is exactly the "Also clears the needsHuman flag…" header comment, `462-465` and `480-483` are exactly the two `delete` blocks. D4 rebased on `humanAnswer` threading alone (§1, §3.3), 3-alternative paragraph added, degraded sub-0.14.0 path per recorded decision 1. `unblock` predating 0.6.0 is substantiated (rauf CHANGELOG `## 0.6.0` lists web *catching up* to the CLI's `unblock`). |
| V-002 | **RESOLVED** | §3.5 step 4 replaced with a new `### 1g. Stranded-Work Pre-flight` spec. Re-confirmed no forge-side dirty-tree gate exists: `forge-5-loop/SKILL.md` sub-steps are `1a`:39, `1b`:45, `1c`:80, `1d`:99, `1e`:106, `1f`:114 — none inspects the tree. `state.json` really carries `startedAt`/`currentItem`/`blockedItems` (verified against a live `.rauf/state.json`). §2 annotation updated to "PLUS … new ~5-line Step 1g". |
| V-003 | **RESOLVED** | §2 gained `references/stage-exit-protocol.md` (`:50` is exactly the `forge-5-loop` outcome-domain row), `tests/test_stage_exit_protocol.py` (`:379-388` is exactly the `for outcome in outcomes: assert f"\`{outcome}\`" in surface` block), and both `docs/architecture/stage-exit-coverage/` files (`cli-reference.md:54` = the outcome table; `architecture.md:191` = the resume/recover split prose). §3.2 now names `SKILL.md:271` (exactly the in-body ladder line) as mandatory and records the deliberate non-change to `SKILL.md:232`'s "five verbatim result-report output templates" (line exact). |
| V-004 | **RESOLVED** | Both count literals verified exact: `forge-verify/SKILL.md:33` = `**Large modes (specs 38, backlog 27, impl 23)**`, `:171` = `backlog: 27 checks`. `test_lifecycle_artifact_check.py:49-52` is exactly `test_verify_skill_backlog_total_bumped` asserting both. CHECK-B28 assigned to "dependency/ordering sanity" — correct, that is group 2 of the backlog list. §3.8 records `--probe all` per decision 2 and the eval citations are exact (`run-compliance-eval.py:9` = "Three probes:", `:55` = the usage `--probe` line, `:996` = `_BRANCH_TOP_KEYS`, `:1109-1112` = the `schemaVersion != 2` hard-fail; `test_compliance_eval.py:1953-1954` = the `--probe all` exact-equality assertion). |
| V-005 | **RESOLVED** | Re-derived with `check-spec-purity.py`'s own rule-4 measure: `forge-5-loop/SKILL.md` = **287** body lines, `forge-verify/SKILL.md` = **298**. §2 now says `287/300 body lines (per check-spec-purity.py rule 4, not wc -l)` and §3.7 reconciles PRD §5's "299/300". (`forge-4-backlog/SKILL.md` = 188 body lines, so §3.7's "~100 lines of body headroom" is also sound.) |
| V-006 | **RESOLVED as applied — but the finding was a FALSE POSITIVE**; see V-012 | The named test *does* exist: `tests/test_stage_exit.py:2341` `test_loop_accepts_exactly_the_five_loop_outcomes`, parametrized over `LOOP_OUTCOMES`. Round 1 grepped the prose word "five" and missed it inside the snake_case identifier. The replacement citations are all exact (`:626` mirror tuple, `:2305` derived set, `:2358` recover parametrize, `:2372`/`:2473` dependents, `:3207` hand-listed parametrize) — but the fix deleted a correct instruction. |
| V-007 | **RESOLVED** | §5.2 signature is now `backlog-topology (--items-json <path> \| --items-stdin) [--cluster] --json` with "it never reads `backlog.json` off disk" per recorded decision 3; §3.2's `selectable` bullet already cites the runner JSON. The new parenthetical checks out: `forge-4-backlog/SKILL.md:109` is literally `## Step 5: Validate via the loop runner`. |
| V-008 | **RESOLVED** | New §3.9 "Citation basis for every new report surface" — a 6-row table covering the pending/starvation template, failed-recovery report, `resolved` text, consolidated prompt, tree reconciliation, and the Step 2a depth line, each naming its authoritative source. |
| V-009 | **RESOLVED — and independently re-executed** | Alternatives paragraph added with under-clustering named as the chosen failure direction. The calibration claim was executed rather than trusted: rauf lands the `RAUF_NEEDS_HUMAN` text in `blockedReason` (`runner.ts:1008-1012`), the observed run's three needs-human reasons survive in `.rauf/archive/20260804-151825-events.ndjson` (items 001/002/004), and under §3.6's normalization the pairwise Jaccards are **0.547 / 0.528 / 0.641** — all ≥ 0.5, so the fixture clusters into one candidate at `CLUSTER_JACCARD_THRESHOLD = 0.5`. The claim is true. |
| V-010 | **RESOLVED** | §6 row rewritten to the `_DECISIONS_SCHEMA` load + wrapper + docstring rescope. `_state_schema.py:26-31` is exactly the `_STATE_SCHEMA`/`_CONFIG_SCHEMA` pair, and both quoted docstring phrases exist verbatim. |
| V-011 | **RESOLVED** | §4 semantics paragraph now fixes cancel-early as a deferral (`answer: null`, `deferred: true`, `question` carrying the needs-human text), no new schema field, `--answer \| --deferred` flag surface unchanged. |

Additional non-findings cleared during the delta scan: `LoopOutcome` at `forge-session.py:374` with `EXIT_OUTCOMES` deriving via `get_args` at `:398`; `test_stage_exit.py:2640-2641` asserts `set(_LOOP_ROUTE_KIND) == set(LOOP_OUTCOMES)` and `set(_LOOP_OUTCOME_TEXT) == set(NON_COMPLETE_LOOP_OUTCOMES)`, both satisfied by §3.2's specification; `rauf backlog unblock <path> [id]` matches the CLI usage string at `backlog-commands.ts:949`; §3.2's gate-(b) reasoning about gitignored `.rauf` artifacts being invisible to `git status --porcelain` is correct.

## Summary
- Total new findings: 4
- Gaps: 0
- Inconsistencies: 2
- Improvements: 2
- Errors: 0
- Unresolved prior findings: 0
- New **blocking** defects introduced by the fix: **0**

## Findings

### V-012: The fix deleted a correct §8 instruction — `test_loop_accepts_exactly_the_five_loop_outcomes` is now unnamed, so its rename obligation is unstated
- **Severity:** inconsistency
- **Location:** tech-spec.md §8 Testing Approach, the `tests/test_stage_exit.py` bullet (fix-introduced; the pre-fix text was correct)
- **Issue:** Round 1's V-006 asserted that §8's *"the 'exactly the five' test renamed and re-parametrized to six"* named a test that "does not exist". It does exist — `tests/test_stage_exit.py:2341` `def test_loop_accepts_exactly_the_five_loop_outcomes(...)`, parametrized at `:2340` over `LOOP_OUTCOMES` (= `EXIT_OUTCOMES["forge-5-loop"]` at `:2304`). Round 1 searched for the standalone word "five" and missed it inside the snake_case identifier. The fix believed the finding and replaced the sentence with an enumeration that does not mention `:2341` at all. Because `LOOP_OUTCOMES` derives from the mirrored tuple, adding `resolved` extends that test to six cases **automatically and silently** — nothing fails — so the only unmet obligation is the rename, and §8 no longer records it. Consequence is confined to a test identifier, which is why this is `inconsistency` and not blocking — but §8 is the enumerated edit list forge-3-specs will author the testing spec from.
- **Suggested fix:** In §8's `tests/test_stage_exit.py` bullet, restore the deleted target as one clause: "`test_loop_accepts_exactly_the_five_loop_outcomes` (`:2341`, parametrized over `LOOP_OUTCOMES`) picks up the sixth case automatically and must be **renamed** to `..._exactly_the_six_loop_outcomes`". Note in the findings document that V-006 was a false positive so the audit record is not misleading.
- **References:** `tests/test_stage_exit.py:2304,2340-2345,2640-2641`; prior report V-006; VERIFY-tech-2026-08-05.md Fix Progress Step 4
- **Checklist:** CHECK-T11, CHECK-T05

### V-013: §3.7's line citation for the backlog dimension groups points at the wrong lines
- **Severity:** inconsistency
- **Location:** tech-spec.md §3.7 consumer 2 — "group 2 of the backlog dimension groups at `SKILL.md:33-38`" (fix-introduced)
- **Issue:** The backlog dimension-group list in `skills/forge-verify/SKILL.md` is at **lines 43-45**. Lines 33-38 are the "Large modes … parallel dimensioned fan-out" bullet and its preamble; lines 40-42 are the **specs** group. The group *name* assigned to CHECK-B28 ("dependency/ordering sanity") is correct and genuinely group 2 — only the `:33-38` range is wrong. §2's separate `":33 backlog 27" (dimension groups)` annotation is fine: line 33 really is the count literal.
- **Suggested fix:** Change `SKILL.md:33-38` to `SKILL.md:43-45` in §3.7 consumer 2.
- **References:** `skills/forge-verify/SKILL.md:33,40-45`
- **Checklist:** CHECK-T05

### V-014: §3.8 names only the probe-list assertion — the monkeypatch tuple three lines above it must also gain the fourth probe or the unit test spawns a real driver
- **Severity:** improvement
- **Location:** tech-spec.md §3.8 Eval coverage
- **Issue:** §3.8 cites only "the exact-equality probe-list assertion in `tests/test_compliance_eval.py:1953-1954`". There are **two** three-probe lists in that one test: the assertion at `:1954`, and the monkeypatch loop at `:1949` — `for name in ("run_stage_exit_probe", "run_prelude_probe", "run_branch_probe"):` — which stubs each probe out. If only the assertion is updated, `run_loop_outcome_probe` stays un-stubbed and `ce.main(["--probe","all","--n","1"])` invokes it for real inside a unit test.
- **Suggested fix:** In §3.8, change the citation to "`tests/test_compliance_eval.py:1949` (the monkeypatch stub tuple) **and** `:1953-1954` (the exact-equality assertion)".
- **References:** `tests/test_compliance_eval.py:1945-1957`
- **Checklist:** CHECK-T11, CHECK-T04

### V-015: The clustering calibration's source strings live only in a gitignored, prunable run artifact — and the measured margin is 0.028
- **Severity:** improvement
- **Location:** tech-spec.md §3.6, the **Calibration** sentence; §8's `tests/test_decision_clustering.py` bullet
- **Issue:** §3.6 grounds `CLUSTER_JACCARD_THRESHOLD` in "the actual `blockedReason` strings of the observed verify-test-debt run". The claim is true and reproducible today — but the only surviving copy of those strings is `specs/verify-test-debt/.rauf/archive/20260804-151825-events.ndjson` (and `rauf.log`), both covered by the `**/.rauf/*` deny rule, untracked, and legitimately deletable; `specs/verify-test-debt/backlog.json` has all 16 items `done` with no `blockedReason` left. After the artifact is pruned the fixture cannot be reconstructed. Separately, the measured pairwise Jaccards are 0.547 (001↔002), **0.528** (001↔004), 0.641 (002↔004): the binding pair clears 0.5 by 0.028, so a small normalization change could silently decalibrate the constant.
- **Suggested fix:** In §8's `tests/test_decision_clustering.py` bullet, require the three `blockedReason` strings to be **vendored verbatim into the test file** (with provenance: verify-test-debt run 2026-08-04, items 001/002/004, `baseCommitHash ff9d634`). In §3.6, record the measured values — "observed pairwise Jaccard 0.53–0.64; the binding pair clears 0.5 by 0.03, so any change to the normalization rules must re-run this fixture".
- **References:** `specs/verify-test-debt/.rauf/archive/20260804-151825-events.ndjson`; `specs/verify-test-debt/backlog.json`; `/home/gary/workspace/rauf/packages/loop/src/runner.ts:1008-1017`; tech-spec §3.6, §8
- **Checklist:** CHECK-T09, CHECK-T11

Minor observation not filed as a finding: §3.7's heading says "three consumers" (skills) while §5.2's closing sentence says "All five consumers" (call sites). Both counts are internally correct at their own granularity; one clause in §3.7 ("three consuming skills, five call sites") would settle it.

## Fix Execution Plan

### User Decisions Required
None — all four findings are advisory and mechanically applicable. The three prior user decisions (V-001 degraded path, V-004 `--probe all`, V-007 runner-JSON-only) were correctly implemented and are not re-litigated.

### Execution Steps

#### Step 1: Restore the deleted §8 test target and correct two line citations
- **Files:** tech-spec.md (§8 `tests/test_stage_exit.py` bullet; §3.7 consumer 2; §3.8)
- **Addresses:** V-012, V-013, V-014
- **Action:** Add the `test_loop_accepts_exactly_the_five_loop_outcomes` (`:2341`) rename clause back into §8. Change §3.7's `SKILL.md:33-38` to `SKILL.md:43-45`. Change §3.8's eval-test citation to name both `test_compliance_eval.py:1949` and `:1953-1954`.
- **Depends on:** none

#### Step 2: Make the clustering calibration durable
- **Files:** tech-spec.md (§3.6 Calibration sentence; §8 `tests/test_decision_clustering.py` bullet)
- **Addresses:** V-015
- **Action:** Require the three source `blockedReason` strings to be vendored verbatim into the test with provenance, and record the measured Jaccard values (0.53–0.64, binding pair 0.528) as an explicit tripwire on any normalization change.
- **Depends on:** none

---

**Verdict: advisory-only — passed.** All 11 prior findings are confirmed resolved against their acceptance evidence (three per recorded user decisions, not re-filed), every load-bearing `file:line` the fix added was spot-verified exact, and the two claims the fix asserted without proof — the 287/300 body measure and the Jaccard-0.5 calibration — were independently re-derived and both hold. The fix introduced **no blocking defect**; the four new findings are two `inconsistency` and two `improvement`, none of which prevents forge-3-specs from proceeding. The one item worth the owner's eye is V-012: round 1's V-006 was a false positive and the fix deleted correct content on the strength of it — a one-clause restoration in §8.
