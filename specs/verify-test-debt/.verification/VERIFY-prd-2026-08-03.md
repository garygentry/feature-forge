# Verification Report: verify-test-debt (prd)

Date: 2026-08-03
Pipeline Stage: forge-1-prd (complete v1)
Round: 1
Verifier: clean-room `forge-verifier` subagent
Verdict: **ADVISORY-ONLY** → `passed` with report attached

Artifacts Reviewed:
- `specs/verify-test-debt/PRD.md` (v1)
- `specs/verify-test-debt/.pipeline-state.json`
- `plans/remediation-stage-exit-coverage.md` (R-10..R-13, T1-T4, C8, D7)
- `skills/forge-1-prd/references/prd-template.md`
- Repo evidence: `scripts/forge-session.py`, `eval/run-compliance-eval.py`,
  `tests/test_capability_determination_prose.py`, `tests/test_stage_exit_protocol.py`,
  `tests/test_state_verb_call_sites.py`, `tests/test_auto_verify.py`,
  `tests/test_state_schema_conformance.py`, `tests/test_stage_constants_parity.py`,
  `tests/test_compliance_eval.py`, `adapters/`

Checks Executed: 15 of 15 (8 pass, 7 fail, 0 not-applicable)

---

## Factual Verification Ledger

Every repo claim in the PRD was probed live rather than trusted. **All hold.**

| PRD claim | Verdict | Evidence |
|---|---|---|
| Suite baseline 1840 passed / 2 skipped | TRUE | `pytest tests/ -q` → `1840 passed, 2 skipped` |
| `ruff check tests/` = 19 errors | TRUE | `Found 19 errors.`; `ruff check scripts/ eval/` → clean |
| `test_capability_determination_prose.py` = 43 tests, 651 lines | TRUE | `wc -l` → 651; `--collect-only -q` → 43 collected (13 `def test_`, parameterized) |
| 67 mutation controls in `test_stage_exit_protocol.py` | TRUE | 7 `*_fails_the_guard` functions collecting 18+9+9+9+9+9+4 = 67; positive tests = 102−67 = 35 |
| `state-complete --version 0` accepted at write | TRUE | live probe → rc 0, state holds `"version": 0` |
| Read path rejects `<1`, poisoning a later verify | TRUE | `state-verify` → `Error: forge-1-prd.version must be a positive integer; got 0`, exit 2 |
| `state-artifact --path` has no containment check | TRUE | `--path ../../../etc/passwd` → rc 0, written verbatim into `artifacts` |
| Containment already applied to findings-file paths | TRUE | `forge-session.py:4942` |
| LOOKBEHIND / LOOKAHEAD / CALL_SPAN machinery exists | TRUE | `test_state_verb_call_sites.py:58,59,89`; window applied at `:147` |
| `inspect.getsource` meta-test on another test's wording | TRUE | `test_state_verb_call_sites.py:225` |
| Six surfaces restate the capability rule | TRUE | 6 restating; 3 without prose (`forge-0-epic`, `-5-loop`, `-6-docs`); 9 canonical exit sites / 10 contract paths |
| `forge-0-epic` hole encoded in a test constant (D7) | TRUE | `SURFACES_WITHOUT_PROSE` at `:181`, excluded at `:300` |
| Six adapter mirrors (C-01) | TRUE | `adapters/{claude,codex,copilot,cursor,gemini,pi}` |
| `forge-verify` at its 300-line cap (C-05) | TRUE | `MAX_BODY_LINES = 300`; SKILL.md 305 lines incl. frontmatter |
| Key-**order** pin (REQ-BRIT-06) | TRUE | `test_state_schema_conformance.py:414` |
| chmod test lacks root-uid skip guard (REQ-BRIT-01) | TRUE | `test_auto_verify.py:843`; siblings guard at `test_stage_exit.py:2802`, `test_effective_config.py:472` |
| Source-text assertions duplicating runtime checks (REQ-TRIM-07) | TRUE | `test_stage_constants_parity.py:253-256, 266` |
| No TBD/TODO placeholders | TRUE | grep → none |

**Completeness against R-10..R-13:** no work item and no acceptance evidence is
unrepresented. R-10→REQ-GUARD-01..07; R-11→REQ-TRIM-01..07; R-12's seven T3 gaps
→REQ-COV-01..07 one-for-one, plus C8→REQ-FIX-01 and the containment decision
→REQ-SEC-01 (fix+test branch chosen); R-13→REQ-BRIT-01..07; GATE-P3→REQ-TRIAL-01..03.
R-11's "runtime measurably reduced" is deliberately declined by REQ-QUAL-04 with a
stated reason — a justified deviation, correctly recorded, not a finding.

**Cross-cutting positions all recorded:** concurrency (REQ-CONC-01, naming CHECK-S27),
failure modes (REQ-COV-01/07, REQ-OBS-01), scope boundaries (§6), non-goals
(REQ-GUARD-06), accessibility/scalability (§4.5, N/A with reason).

---

## Summary

- Total findings: 10
- **Errors: 0**
- **Gaps: 0**
- Inconsistencies: 4 (V-001, V-002, V-007, V-008)
- Improvements: 6 (V-003, V-004, V-005, V-006, V-009, V-010)

---

## Findings

### V-001 — OQ-03 contradicts REQ-COV-03's MUST; "never checked" premise imprecise
- **Severity:** inconsistency
- **Location:** §3.3 (REQ-COV-03), §7 (OQ-03)
- **Issue:** REQ-COV-03 mandates at P1 that `resolver_line_identical` "MUST be asserted",
  while OQ-03 leaves open whether it should assert or merely record. A P1 MUST cannot
  rest on an unresolved open question. Separately, "currently computed and never
  checked" is imprecise: the criterion **is** consumed — `run-compliance-eval.py:1715`
  places it in the criteria dict and `:1883` computes `compliant=all(criteria.values())`,
  so a False value does fail the run. What is genuinely absent is (a) any *test* naming
  it and (b) a criterion **key-set pin** for the prelude scorer (unlike `BRANCH_CRITERIA`,
  pinned at `:1452` and in `test_compliance_eval.py:1429-1430`). Substantive nuance:
  `byte_identical` strictly implies `resolver_line_identical`, so the criterion has
  **zero marginal effect** on `compliant` today — the real reason OQ-03 exists.
- **Resolution:** Reword REQ-COV-03 to the test-level requirement (key-set pin + a named
  test exercising the distinguishing case) and drop the false premise; rescope OQ-03 so
  either answer satisfies REQ-COV-03.
- **Checklist:** CHECK-P04, CHECK-P15

### V-002 — §3.3's "only these three" contradicts REQ-FIX-02 and §6
- **Severity:** inconsistency
- **Location:** §3.3 lead-in, cross-reading §6 bullet 3
- **Issue:** §3.3 says "Three behavior changes are in scope, and only these three" then
  lists REQ-FIX-01, REQ-SEC-01, REQ-FIX-02. REQ-FIX-02 is not a behavior change — it is
  an open-ended policy authorizing further ones, so the sentence's own third item
  falsifies its "only these three" claim. §6 states it correctly, so the PRD contradicts
  itself across sections. Real consequence: an implementer or verifier can read "only
  these three" as forbidding exactly the fix REQ-FIX-02 mandates.
- **Resolution:** "Two product behavior changes are in scope by name (REQ-FIX-01,
  REQ-SEC-01). REQ-FIX-02 is a standing policy governing any further defect the coverage
  backfill uncovers; it is not a third named change. No other behavior change is in scope."
- **Checklist:** CHECK-P15, CHECK-P03

### V-003 — REQ-FIX-02 unbounded, no escape valve against the REQ-TRIAL-01 round budget
- **Severity:** improvement
- **Location:** §3.3 (REQ-FIX-02) vs §3.6 (REQ-TRIAL-01/02)
- **Issue:** REQ-FIX-02 obliges in-feature fixing of *any* uncovered defect, unbounded by
  size or severity, while REQ-TRIAL-01 caps the feature at ≤2 verify rounds per stage.
  The backfill targets exactly the areas that produced the plan's MAJOR C1 and HIGH C2,
  so a defect of that size forces either a scope blow-out or a metric violation — and a
  blow-out mid-trial contaminates the measurement.
- **Resolution:** Add a bounded escape valve: a defect too large to fix in scope is
  recorded via `state-decision`, deferred to Phase 4, and its test asserts the *defect*
  (xfail / explicit known-defect assertion referencing the decision) rather than pinning
  wrong behavior as golden. A recorded decision is never re-filed (C-04).
- **Checklist:** CHECK-P14, CHECK-P15

### V-004 — REQ-GUARD-04's "at most 5 tests" does not name its counting unit
- **Severity:** improvement
- **Location:** §3.1 (REQ-GUARD-04), §8 criterion 1
- **Issue:** P0 acceptance turns on a number whose unit is unstated. The two units differ
  ~3x for this file: 13 `def test_` functions vs 43 collected. §1 uses the collected unit,
  which implies the target is too, but that reading is load-bearing and only inferrable.
  It materially constrains implementation: protection item 2 covers 9-10 surfaces, so a
  natural `parametrize` over the roster collects 9-10 cases and alone breaches a
  collected-≤5 budget while satisfying a functions-≤5 budget easily. Unstated, the tech
  spec picks one unit and a later verifier measures the other — costing a round, which is
  the exact failure mode REQ-TRIAL-01 measures.
- **Resolution:** State the unit in REQ-GUARD-04 and mirror in §8 criterion 1.
- **Checklist:** CHECK-P08

### V-005 — REQ-GUARD-02 permits the duplication the §2 user story exists to remove
- **Severity:** improvement
- **Location:** §3.1 (REQ-GUARD-02), §8 criterion 2, vs §2 user story 1
- **Issue:** §2 asks that the rule be "stated once in canon rather than restated six
  times... a one-file change instead of a seven-file grid update." But REQ-GUARD-02
  requires only "restate the paragraph **or** carry a pointer". An implementation that
  adds the canonical section, adds a `forge-0-epic` pointer, trims the guard, and leaves
  all six restatements untouched satisfies every requirement and criterion while
  delivering none of the story's benefit. Note the permissive wording does track R-10's
  *acceptance evidence*, and there are real operational reasons to allow inline prose (a
  stage agent determining capability at exit may not have loaded `references/`).
- **Resolution:** Either tighten to pointer-required (naming and justifying any surface
  keeping inline prose), or keep permissive and add a Notes line acknowledging the
  one-file-change benefit is therefore partial. The latter is a one-line change and a
  complete answer.
- **Checklist:** CHECK-P15, CHECK-P09

### V-006 — "the roster" in REQ-GUARD-04.3 has no defined population
- **Severity:** improvement
- **Location:** §3.1 (REQ-GUARD-04, protection items 2 and 3)
- **Issue:** The non-vacuity floor requires a roster whose population the PRD never
  defines. Not academic: today the roster is *derived* by a lead-in-phrase filter
  (`_capability_surfaces()`) that by construction matches only surfaces which **restate**
  the rule — returning 6 against `MIN_CAPABILITY_SURFACES = 6`. The moment REQ-GUARD-01/02
  convert restatements to pointers, that derivation returns fewer (potentially 0) and the
  floor either fails or is silently redefined — precisely the vacuity the requirement
  targets. The correct population is also non-obvious: 9 canonical exit sites but 10
  contract paths (one site carries two).
- **Resolution:** Name the population in the requirement (every canonical exit surface,
  derived from the shared exit table, never hand-kept) and state that the derivation must
  not be the pre-collapse "restates the rule" filter.
- **Checklist:** CHECK-P08, CHECK-P14

### V-007 — PRD names the read-path guard `_positive_int`; the symbol is `_require_positive_int`
- **Severity:** inconsistency
- **Location:** §1, fourth bullet parenthetical
- **Issue:** No symbol `_positive_int` exists in `scripts/forge-session.py`; the function
  is `_require_positive_int` (`:4876`, applied at `:4972` and `:5255`). The *behavior*
  described is exactly right and was reproduced end-to-end at the CLI, so only the symbol
  name is wrong. It matters slightly more than a typo because C-07 designates symbol names
  as *the* sanctioned locating mechanism; a wrong symbol degrades the one navigation aid
  the PRD tells readers to rely on. Recoverable (a grep still lands), hence `inconsistency`
  rather than higher under the R-05 floor.
- **Resolution:** §1: `_positive_int` → `_require_positive_int`.
- **Checklist:** CHECK-P08

### V-008 — §8 and §3/§4 asymmetric: one criterion has no requirement, one requirement has no criterion
- **Severity:** inconsistency
- **Location:** §8 criterion 7 and §4.1; §3.6 (REQ-TRIAL-03)
- **Issue:** (1) §8 criterion 7 gates on `ruff check scripts/ eval/` clean, but no
  requirement states it — REQ-QUAL-02 covers `tests/` only. Not hypothetical: REQ-FIX-01
  and REQ-SEC-01 both modify `scripts/forge-session.py`. (2) REQ-TRIAL-03 (record the
  per-stage verify-round count in the Session Log) appears in no §8 criterion, so the
  feature could satisfy all eight criteria while omitting the trial's only durable output.
- **Resolution:** Add `REQ-QUAL-05` for `ruff check scripts/ eval/`; extend §8 criterion 8
  with the Session Log recording.
- **Checklist:** CHECK-P05

### V-009 — Several requirements prescribe mechanism rather than required property
- **Severity:** improvement
- **Location:** §3.2 (REQ-TRIM-03), §3.4 (REQ-BRIT-04, REQ-BRIT-07)
- **Issue:** Requirements-only discipline is mostly well kept, and this feature is a
  genuine edge case — its *product* is test code, so "delete the AST layer"
  (REQ-GUARD-07) really is WHAT. But three requirements specify a design the tech spec
  should own: REQ-TRIM-03 dictates the replacement mechanism, REQ-BRIT-04 the assertion
  technology, REQ-BRIT-07 the refactoring shape. REQ-BRIT-07's prescribed
  parameterization is also in direct tension with V-004, since parameterization is what
  makes collected counts balloon.
- **Resolution:** Restate each as a property; demote the named mechanism to a Notes line.
- **Checklist:** CHECK-P09

### V-010 — §5 constraints do not distinguish mandates from advisory notes
- **Severity:** improvement
- **Location:** §5 (C-01..C-07)
- **Issue:** Seven constraints in a uniform declarative voice are three different kinds of
  thing. C-01/C-05/C-06 are hard mandates; C-03/C-04 are inherited protocol facts binding
  but not this feature's to satisfy; C-02 is an operational workaround note and C-07 is
  working guidance — neither can be violated or complied with. (Substance of each verified;
  the plan's own line references have indeed drifted — T3's `:1569,1584` for
  `resolver_line_identical` are now `:1700,1715` — so C-07 is well-founded.)
- **Resolution:** Label each constraint's force, or split §5 into "Binding constraints" and
  "Working notes".
- **Checklist:** CHECK-P13

---

## Candidate findings dropped as false positives

Recorded so they are not re-raised on a later round (decision immunity, R-06):

1. **§4 NFRs carry no `Priority:` line.** Not a defect — `prd-template.md`'s §4 shape does
   not ask for one; only §3 does.
2. **REQ-QUAL-04 sets no runtime threshold.** A *justified declination*, not an
   unquantified NFR. Its stated reasoning (a machine-dependent number cannot be
   reproduced by a verifier and would reintroduce unfalsifiable-claim churn) is stronger
   than a number would have been.

## Non-goals honored

No finding was filed against REQ-GUARD-06 (exact-markdown fidelity) or REQ-CONC-01
(concurrent writers), both declared non-goals in §6 and §4.4, per the meta-guard
non-goals norm (R-08). REQ-CONC-01 is the correct one-sentence answer to CHECK-S27 and
pre-empts the failure mode where a silent PRD induces a locking protocol no requirement
asked for.

---

## Verdict

**ADVISORY-ONLY.** No `error` and no `gap`.

Per the severity floor in force (`references/stage-exit-protocol.md`;
`skills/forge-verify/SKILL.md` Step 5/6), this resolves `forge-verify-prd` as **`passed`
with the findings file attached**. It does **not** route to forge-fix and does **not**
consume a verify round against REQ-TRIAL-01.

The advisories remain discoverable here for whoever next touches the artifact — most
naturally the tech-spec author, since V-001, V-004, V-005 and V-006 each hand the tech
spec a question it will need answered anyway.
