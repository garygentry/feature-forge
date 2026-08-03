# Verification Report: verify-test-debt (tech)
Date: 2026-08-03
Pipeline Stage: forge-2-tech (complete, v1); forge-verify-tech: auto-verify-pending
Artifacts Reviewed: specs/verify-test-debt/PRD.md (v1), specs/verify-test-debt/tech-spec.md (v1), scripts/forge-session.py, scripts/check-spec-purity.py, eval/run-compliance-eval.py, references/shared-conventions.md, references/stage-exit-protocol.md, skills/*/SKILL.md, tests/ (test_state_verb_call_sites.py, test_capability_determination_prose.py, test_stage_exit_protocol.py, test_state_verbs.py, test_state_schema_conformance.py, test_stage_exit.py, test_stage_constants_parity.py, test_forge_root.py, test_auto_verify.py, test_compliance_eval.py)
Checks Executed: 17 of 17 (10 pass, 6 fail, 1 not-applicable)

Check results: T01 fail · T02 fail · T03 pass · T04 pass · T05 fail · T06 pass · T07 fail · T08 pass · T09 pass · T10 fail · T11 fail · T12 pass · T13 pass · T14 pass · T15 pass · T16 pass · T17 n/a

## Summary
- Total findings: 11
- Gaps: 1
- Inconsistencies: 3
- Improvements: 3
- Errors: 4

Blocking (error/gap): V-001, V-002, V-003, V-004, V-005.

### Verified correct (recorded so a later round does not re-litigate)
- All 43 PRD `REQ-*` IDs appear in the tech spec; zero orphan IDs in either direction.
- §3.4's mutation-class table is exact: 9/9/9/18/9/4/9 = 67 collected items, confirmed by `pytest --collect-only`.
- §3.14 REQ-BRIT-04 roster is exact: 5 sites / 11 comparisons (1+1+1+3+5) across `test_forge_root.py` and `test_state_verbs.py`. PRD's "~15" correctly superseded.
- §3.13 / OQ-03 is correct: `score_prelude` returns `resolver_line_identical`; `_to_result` computes `compliant=all(criteria.values())` at `eval/run-compliance-eval.py:1883`. PRD's "computed and never checked" correctly superseded. Probe 3's `BRANCH_CRITERIA` (9 keys) is real and is the right pattern to mirror.
- §3.9's asymmetry table reproduced live: autoVerify **on** + corrupt state → exit 2, **0 bytes stdout**; autoVerify **off** → exit 0 with full payload.
- §3.10 verified by construction: `_schedule_auto_verify_debt` early-returns before `_commit_state`; `_now_iso()` is never evaluated on that path.
- §3.12's residual is real: `reconcile_command = f"/feature-forge:forge-0-epic {epic_name}"` uses the unvalidated name; `route_epic` guard and `SAFE_NAME_RE` are quoted correctly.
- §3.2's roster is exact: `SURFACES_WITHOUT_PROSE` holds exactly the 3 named entries; forge-5-loop and forge-6-docs carry pointers naming the canonical section by title; forge-0-epic carries neither.
- §3.3's deletion inventory is exact (13 test defs / 43 collected items; all named helpers, tests and constants exist). §6.3's cross-module import is real (`from test_stage_exit_protocol import CANONICAL_EXIT_SITES`, line 81).
- Baselines all confirmed: 1842 tests collected (= 1840 passed + 2 skipped), `ruff check tests/` = 19 errors, `check-spec-purity.py` = 0 violations.
- C-07 honored: the tech spec cites zero line numbers.
- §3.7's confirmed defect reproduced live: `state-complete --version 0` exits 0 and writes `"version": 0`. §3.8's reproduced live: `state-artifact --path ../escape.md` exits 0 and records `["../escape.md"]`.

## Findings

### V-001: §3.1's body-cap "negative headroom" is factually wrong; §10.2's fallback would delete canon on a false premise
- **Severity:** error
- **Location:** tech-spec.md §3.1 ("Constraint check (C-05)" paragraph and the "Open risk" blockquote); §10.2 item 1
- **Issue:** §3.1 states `skills/forge-verify/SKILL.md` is "**305 lines** — already over" and `forge-0-epic/SKILL.md` is 301, concluding "Both have negative headroom, so the forge-0-epic addition must be **one sentence**. This is the decisive reason the fix is a pointer." Those are *file* line counts. `check-spec-purity.py::check_body_size` measures the **body** — `text.split("\n")[fm.body_start_line:]`, i.e. everything after the closing frontmatter fence, minus a trailing empty split artifact. Measured with that exact rule:
  - `skills/forge-0-epic/SKILL.md`: body **295** lines / 2749 words → **+5 lines**, +2251 words of headroom.
  - `skills/forge-verify/SKILL.md`: body **299** lines / 4365 words → **+1 line**, +635 words of headroom.

  Neither file is over; neither has negative headroom. This is consistent with `python3 scripts/check-spec-purity.py` reporting `PASS — 0 violations`, which §3.1 itself cites and then reasons past. The spec's own "Open risk" poses the correct disjunction ("Either the rule counts a *body* smaller than the file … or the gate is not tripping") but resolves it the wrong way and hard-codes the wrong branch into its rationale. The consequence is decision-bearing, not cosmetic: §10.2 item 1 prescribes a pre-implementation measurement that, performed as written (file lines vs `MAX_BODY_LINES`), reproduces the same error, and its fallback action is "**the pointer replaces existing text rather than adding to it**" — deleting canonical prose to make room that already exists.
- **Suggested fix:** In §3.1, replace the "Constraint check (C-05)" paragraph with the measured values: "`check-spec-purity.py` enforces the cap on the **body** (content after the closing frontmatter fence), not the file. Measured: `forge-0-epic/SKILL.md` body = 295/300 lines and 2749/5000 words (5 lines of headroom); `forge-verify/SKILL.md` body = 299/300 lines and 4365/5000 words (1 line). `check-spec-purity.py` reports 0 violations. A one-sentence pointer in forge-0-epic fits; no capability prose may be added to forge-verify, which has one line of headroom." Delete the "Open risk" blockquote entirely — the risk is measured and closed. In §10.2, delete item 1 or restate it as resolved with the numbers above and **remove the "replaces existing text" fallback**. Keep the pointer-not-paragraph decision: it still stands on §3.1's shape-matching rationale (forge-5-loop / forge-6-docs) and on R-10's surface-collapse goal.
- **References:** scripts/check-spec-purity.py `check_body_size` (`MAX_BODY_LINES = 300`, `MAX_BODY_WORDS = 5000`); PRD C-05; tech-spec §10.2 item 1
- **Checklist:** CHECK-T02, CHECK-T16

### V-002: `_validated_findings_file` cannot be reused "verbatim" and also emit a `--path` label — §3.8, §5 and §6.1 are mutually unsatisfiable
- **Severity:** error
- **Location:** tech-spec.md §3.8 ("Decision" + "The PRD's relative/absolute concern does not apply"); §5 (API Design, second example); §6.1 (signature table row for `_validated_findings_file`); §10.2 item 2
- **Issue:** The helper's five rejection messages all **hardcode the string `--findings-file`**, and its signature is `(value: str, target_dir: Path) -> str` — there is no label parameter. Three statements in the spec cannot all hold:
  1. §6.1 lists it as "**reused verbatim** by §3.8" and §10.2 item 2 keeps its name/shape out of scope.
  2. §3.8 says "No adaptation is needed beyond looping and **the error label**" — but adapting the label *requires* adding a parameter and editing all five messages, which is not verbatim reuse.
  3. §5 states the emitted error as `Error: --path must be a relative path inside the feature directory: '../escape.md'` and claims it "follows whatever `_validated_findings_file` already emits, with the flag label substituted; it is not re-invented here." Verified live, the helper actually emits:

     `Error: --findings-file '../escape.md' contains a '..' segment; it must stay inside the feature directory (specs/demo)`

     §5's sentence matches no branch of the helper — different structure, different clause order — and the helper has **five branch-specific messages** (empty / control char / absolute / `..` segment / resolved escape), not one generic message that a value can be appended to. So §5 both re-invents the wording it says it is not re-inventing and collapses five messages into one.

  Implemented as literally specified, `state-artifact --path ../escape.md` would exit 2 naming `--findings-file`, a flag the user did not pass. That violates §7's own message shape (`{flag} {reason}; {context}`) and REQ-OBS-01's requirement that a failure identify which behavior broke.
- **Suggested fix:** Pick one and make all three sections agree. Recommended (smallest, preserves §10.2 item 2's no-rename position): add a keyword parameter — `_validated_findings_file(value: str, target_dir: Path, label: str = "--findings-file") -> str` — and replace the hardcoded `--findings-file` in all five messages with `{label}`; §3.8's loop becomes `_validated_findings_file(path, target_dir, label="--path")`. Then (a) change §6.1's row from "reused verbatim" to "reused with a new `label` parameter (default preserves the existing `--findings-file` wording, so no existing message changes)"; (b) in §3.8 replace "No adaptation is needed beyond looping and the error label" with "Adaptation is a defaulted `label` parameter plus the loop"; (c) in §5 replace the invented sentence with the real template family, e.g. `Error: --path '../escape.md' contains a '..' segment; it must stay inside the feature directory ({dir})`, and note that the helper emits one of five branch-specific messages. Add a note that the existing `--findings-file` call site and its tests must stay byte-identical (default label), so this is not a behavior change for `state-verify`.
- **References:** scripts/forge-session.py `_validated_findings_file` (five `UsageError` messages, all hardcoding `--findings-file`), sole existing call site in `cmd_state_verify`; tech-spec §7; PRD REQ-SEC-01, REQ-OBS-01
- **Checklist:** CHECK-T05, CHECK-T06, CHECK-T10

### V-003: §3.5's structural region goes blind at 22 of 34 sites, reopening the exact regression LOOKBEHIND was narrowed to close — and REQ-TRIM-04 deletes the only bound on guard width with no replacement
- **Severity:** gap
- **Location:** tech-spec.md §3.5 ("Why this is not 'a window by another name'" and "Consequent deletions")
- **Issue:** The substitution's baseline is correct (I reproduced 34/34 independently), and its *maintainability* argument is sound — headings and fence delimiters genuinely have nothing to tune, so REQ-TRIM-04's constants are genuinely deletable. But the spec argues the distinction **only** on tunability and never evaluates detection strength, where the replacement is strictly weaker.

  Mutation census (for each of the 34 sites, strip the `--epic` token belonging to that site — using the current window as the definition of "belonging" — then re-run the proposed scan): the structural region still passes at **22 of 34 sites**, because a neighbouring call's mandate elsewhere in the same `##` section keeps the region green. Only 12 sites retain per-site discrimination. Regions run 9–48 lines versus the current 15-line window, and 11 regions contain 2–3 call sites.

  Critically, this reopens a **documented, previously-fixed** hole. `tests/test_state_verb_call_sites.py`'s `LOOKBEHIND` docstring records: "at 20 the lookbehind reached past a block's own mandate into the PRECEDING block's, so deleting the `state-artifact` mandate at `shared-conventions.md:318` left the guard green on the strength of the unrelated `state-enter` mandate 17 lines up." That is why LOOKBEHIND is 12. Both calls live under the single `## Stage-Entry Guard` heading, so the structural region merges them. Replayed directly — delete the `state-artifact` paragraph's `--epic` sentence:
  - current window guard → **detects** (`shared-conventions.md:386 (state-artifact)`)
  - proposed structural scan → **blind** (passes)

  Compounding this, §3.5's consequent deletions remove `test_the_window_is_no_wider_than_the_measured_maximum` — the only test bounding the guard's discriminating width — and add nothing in its place. `MIN_CALL_SITES` / `test_the_epic_guard_is_not_vacuous` survive, but a site-count floor cannot detect an over-wide region. After this change nothing fails when the guard stops discriminating, which is precisely how the original hole shipped. Deleting the tuning tests is authorized by REQ-TRIM-04; leaving the protection they conferred uncovered is not addressed by any requirement, and this is not a declared non-goal (§8.4 does not mention it).
- **Suggested fix:** Two parts, both in §3.5.
  1. **Tighten the region so it cannot span two call sites.** Keep the structural character (no tuned integers) by adding neighbouring calls to the bounds: `lower = max(nearest enclosing heading, end of the previous fenced state-* call)`, `upper = min(next heading, start of the next fenced state-* call)`. I verified this variant: still 34/34 green on current canon, recovers the `state-artifact` case specifically, and lifts detection from 12/34 to 20/34. State the measured residual honestly rather than claiming parity.
  2. **Replace the deleted width bound with a mutation control, not a count floor.** Add one test to the trimmed file that programmatically deletes one known site's own `--epic` mandate from an in-memory copy of `shared-conventions.md` and asserts Guard 1 reports that site — the negative control that `test_the_window_is_no_wider_than_the_measured_maximum` used to provide structurally. This costs one test inside REQ-TRIM-04's budget and is the only thing that fails when the region silently widens.

  If instead the residual blindness is judged acceptable, that is a legitimate call — but it must be **recorded** in §3.5 as a declared boundary of the guard, with the measured census (`N/34`) and an explicit note that the `state-artifact`/`state-enter` incident is knowingly reopened, so a later round resolves it against a position rather than re-deriving it. Silence is what makes this blocking.
- **References:** tests/test_state_verb_call_sites.py (`LOOKBEHIND`/`LOOKAHEAD`/`CALL_SPAN` docstrings, `test_the_window_is_no_wider_than_the_measured_maximum`); references/shared-conventions.md §§ Stage-Entry Guard, Git Commit Protocol; PRD REQ-TRIM-03, REQ-TRIM-04
- **Checklist:** CHECK-T09, CHECK-T11, CHECK-T16

### V-004: §3.14's hash-matrix correction is wrong — there are 5 sites, not 4; the PRD's original figure was correct
- **Severity:** error
- **Location:** tech-spec.md §3.14 (REQ-BRIT-07 table, first row); §10.1 (superseded-figures table, second row)
- **Issue:** §3.14 states "40-hex hash casing (**4 sites**, not 5) | 2 hand-rolled loops in `test_state_verbs.py` → `parametrize`; the 2 in `test_state_schema_conformance.py` are already parametrized — **unchanged**", and §10.1 supersedes the PRD's "hash matrices ×5" with "4 sites". The repo has **five**:
  - `tests/test_state_verbs.py` — **three** hand-rolled `for label, value in _REJECTED_HASHES:` loops:
    - `test_state_complete_rejects_a_short_or_malformed_hash_before_mutation` (def at line 750)
    - `test_state_verify_commit_2_rejects_a_short_or_malformed_hash_before_mutation` (def at line 2055)
    - `test_epic_commit_2_rejects_a_short_or_malformed_hash_before_mutation` (def at line 2575)
  - `tests/test_state_schema_conformance.py` — **two** already-parametrized sites (`@pytest.mark.parametrize("value", REJECTED_HASHES)` at lines 335 and 421).

  3 + 2 = 5. The PRD's "×5" was accurate; the spec replaces a correct figure with an incorrect one and, because §10.1 declares this spec "the authority for these three rosters", the undercount is what an implementer will build to — leaving `test_epic_commit_2_rejects_a_short_or_malformed_hash_before_mutation` un-deduplicated and REQ-BRIT-07 partially unmet. (Note the two other supersessions in §10.1 are correct; only this row is wrong.)
- **Suggested fix:** In §3.14, change the first table row to "40-hex hash casing (**5 sites**) | **3** hand-rolled loops in `test_state_verbs.py` (`test_state_complete_rejects_a_short_or_malformed_hash_before_mutation`, `test_state_verify_commit_2_rejects_a_short_or_malformed_hash_before_mutation`, `test_epic_commit_2_rejects_a_short_or_malformed_hash_before_mutation`) → `parametrize` over `_REJECTED_HASHES`; the 2 in `test_state_schema_conformance.py` are already parametrized — **unchanged**". In §10.1, **delete the hash-matrix row from the superseded-figures table** and add one sentence: "The PRD's hash-matrix ×5 is confirmed correct and is not superseded." Note the three loops call three different verbs (`state-complete`, `state-verify` commit-2, epic commit-2) through different fixtures, so the parameterization is per-test, not a single merged case — say so, to prevent an over-merge that would delete the epic-target coverage.
- **References:** tests/test_state_verbs.py `_REJECTED_HASHES` (10 entries, line 83); tests/test_state_schema_conformance.py `REJECTED_HASHES` (line 302); PRD REQ-BRIT-07, PRD §8 criterion 6
- **Checklist:** CHECK-T01, CHECK-T11

### V-005: §8.2 says `test_state_verb_call_sites.py` loses 3 tests; §3.5 names exactly 2 — the table would drive an unauthorized deletion
- **Severity:** error
- **Location:** tech-spec.md §8.2 (row `test_state_verb_call_sites.py | 10 tests | **7** (−3 per REQ-TRIM-04/05)`) vs §3.5 ("Consequent deletions" and "REQ-TRIM-06 — preserved unchanged")
- **Issue:** §3.5 enumerates exactly two test deletions — `test_the_window_is_no_wider_than_the_measured_maximum` (REQ-TRIM-04) and `test_the_failure_message_describes_the_whole_window` (REQ-TRIM-05) — and explicitly preserves the rest: Guard 1 (rewritten), `test_the_epic_mandate_itself_is_still_documented`, `test_the_epic_guard_is_not_vacuous`, Guard 2's two tests, Guard 3's two tests (it states Guard 3 "keeps its protection"), and `test_this_guard_is_not_skippable`. The file has 10 tests (confirmed by collection), so the correct arithmetic is 10 − 2 = **8**, not 7 / −3. No third deletion is named anywhere in the spec. A fix agent working from the §8.2 table has a count to hit and no named target, and will delete a third test — most likely one of the two vacuity controls, which is the over-deletion risk REQ-TRIM-02 exists to prevent in the sibling file and which §3.5 explicitly guards against ("`MIN_CALL_SITES` and `test_the_epic_guard_is_not_vacuous` also survive").
- **Suggested fix:** Change the §8.2 row to `test_state_verb_call_sites.py | 10 tests | **8** (−2 per REQ-TRIM-04/05)`. Add a parenthetical naming the two deletions so the row is self-checking: "(`test_the_window_is_no_wider_than_the_measured_maximum`, `test_the_failure_message_describes_the_whole_window`)". If V-003's mutation control is adopted the row becomes `**9** (−2, +1 negative control)` — state whichever is chosen, and make §3.5 and §8.2 agree on the same number.
- **References:** tech-spec §3.5; tests/test_state_verb_call_sites.py (10 collected tests); PRD REQ-TRIM-04, REQ-TRIM-05, REQ-TRIM-06
- **Checklist:** CHECK-T11

### V-006: §3.3's fourth test sits outside REQ-GUARD-04's "exactly this protection set" and outside the file's own declared PROTECTS block
- **Severity:** inconsistency
- **Location:** tech-spec.md §3.3 (test list, "Why 4 and not 5", and the `PROTECTS`/`NON-GOALS` docstring template)
- **Issue:** REQ-GUARD-04 permits "at most 5 tests, covering **exactly** this protection set" and enumerates three protections. §3.3 delivers four tests: three mapped to the protections plus `test_this_guard_is_not_skippable`, labelled "self-check". The count is inside the cap, but "exactly this protection set" is a scope constraint the spec never addresses — §3.3 justifies the retention on repo convention ("every sibling guard in this repo carries it") without reconciling it against the requirement's word. More concretely, the `PROTECTS` block in §3.3's docstring template lists only the three protections, so the file would ship a fourth test that its own declaration does not declare. Under REQ-GUARD-05 the declaration is the thing that makes a verifier's finding admissible or inadmissible, and an undeclared test is exactly the shape that invites the next round's finding — the failure mode this feature exists to remove.
- **Suggested fix:** Keep the test (the justification is sound — a `skipif` could silently disable the file), and close the gap in the declaration. In §3.3's docstring template, add a fourth line under `PROTECTS`: "4. This guard cannot be skipped or disabled." Then add one sentence to "Why 4 and not 5": "The self-check is a fourth declared protection, not an addition to the three REQ-GUARD-04 enumerates; it protects the guard's existence rather than the rule, and REQ-GUARD-04's cap of 5 accommodates it." That makes the enumerated set and the shipped tests match, which is what REQ-GUARD-05 actually requires.
- **References:** PRD REQ-GUARD-04, REQ-GUARD-05; tests/test_capability_determination_prose.py `test_this_guard_is_not_skippable`; tests/test_always_loaded_surface.py::test_the_hook_guards_cannot_degrade_to_a_skip
- **Checklist:** CHECK-T01, CHECK-T02

### V-007: §8.2's REQ-BRIT-07 row mixes units with §3.14 — "13 → 3" counts different things in each column
- **Severity:** inconsistency
- **Location:** tech-spec.md §8.2 (row `REQ-BRIT-07 dedup | 13 sites | **3** parametrized`)
- **Issue:** The "Before" figure (13) sums all family sites under the spec's own counts (4 hash + 3 corrupt + 6 gate), including the four sites §3.14 marks "**unchanged**". The "After" figure (3) counts only the newly-parametrized replacements and silently drops those same unchanged sites. Reconciled against §3.14, the post-state is 3 (hash: 1 new + 2 unchanged) + 2 (corrupt: 1 new + 1 unchanged) + 2 (gate: 1 new + 1 unchanged) = **7**, not 3. With V-004's correction the "Before" figure is 14, not 13. As written the row reads as a 77% reduction that no requirement asked for and that §3.14 does not describe.
- **Suggested fix:** Restate the row in one unit. Either count only sites being changed — `REQ-BRIT-07 dedup | 9 hand-rolled sites | **3** parametrized (4 already-parametrized sites unchanged)` (3 hash + 3 corrupt + 5 gate = 11 under the corrected roster; recompute after V-004 and V-009 land) — or count the whole family both sides: `14 sites | 7`. Add a footnote pointing at §3.14 for the per-family breakdown so the two cannot drift again.
- **References:** tech-spec §3.14 (REQ-BRIT-07 table); PRD REQ-BRIT-07
- **Checklist:** CHECK-T11

### V-008: §3.8's snippet loads state before validating, contradicting §6.1's and §7's stated ordering invariant
- **Severity:** inconsistency
- **Location:** tech-spec.md §3.8 (code snippet) vs §6.1 ("Data flow for both new validations: **validate → load → mutate → commit**. Neither validation reads state…") and §7 ("Validation happens **before** any state load or mutation")
- **Issue:** §3.8's snippet is `target_dir = state_path.parent`, and `state_path` is produced by `_load_state_for_write(specs_dir, feature, epic)` inside `cmd_state_artifact`. The validation therefore cannot run before the load — it needs the load's return value to know what directory the path must be contained by. The real order for `--path` is **load → validate → mutate → commit**. §3.7's `--version` validation genuinely is pre-load (it needs no resolved path, and §3.7 correctly places it "before `_load_state_for_write`", mirroring `_assert_full_commit_hash`), so the two validations differ and the spec states a single invariant covering both. The safety property both sections are reaching for still holds — `_load_state_for_write` only reads, so a rejection leaves the file byte-identical — but the stated invariant is wrong for one of the two sites, and it is stated three times.
- **Suggested fix:** In §6.1, replace the data-flow sentence with: "`--version` validates **before** the load (it needs no resolved path). `--path` validates **after** the load and **before** any mutation, because its containment target is `state_path.parent`. In both cases nothing is mutated before validation and `_load_state_for_write` only reads, so a rejection leaves the state file byte-identical." Amend §7's fourth bullet to "Validation happens **before any mutation** — and before the load where the validator does not depend on the resolved path." Keep §3.8's snippet as is; it is the correct implementation.
- **References:** scripts/forge-session.py `cmd_state_artifact`, `_load_state_for_write`, `_assert_full_commit_hash`; tech-spec §3.7
- **Checklist:** CHECK-T07, CHECK-T10

### V-009: §3.14's gate-selection family count (6) is inherited from the PRD without re-derivation, unlike the two families the spec did re-derive
- **Severity:** improvement
- **Location:** tech-spec.md §3.14 (REQ-BRIT-07 table, third row)
- **Issue:** The spec re-derived the exact-stderr roster (OQ-01, correctly) and the hash family (§10.1, incorrectly — V-004), but carried the PRD's "gate-selection (×6)" through unchanged as "5 unparametrized in `test_stage_exit.py` → 1 parametrized; the 6th is already parametrized over host". A scan of `tests/test_stage_exit.py` finds roughly 17 `assert d["verifyGate"] == …` assertions and at least two parametrized ones (lines ~210 and ~1239, the latter parametrized over capability), so the stated 5+1 shape does not obviously reconcile. I did not determine the correct roster — the family boundary is genuinely ambiguous (a "gate-selection site" could be a test, an assertion, or a distinct gate outcome), which is exactly why it should be pinned in the spec rather than left to the implementer. This is flagged as unverified, not as a confirmed miscount.
- **Suggested fix:** Re-derive the family the way §3.14 re-derived REQ-BRIT-04: define the unit explicitly (recommend "test function whose sole assertion subject is the selected `verifyGate`"), enumerate the qualifying tests by name in a small table, and state which are already parametrized. If the count is not 6, note the supersession in §10.1 alongside the other rosters. Whatever the total, keep the "within-file only, never merge across files" rule from §3.14 — `test_stage_exit.py` asserts payload selection and must not be merged with capability-determination coverage.
- **References:** tests/test_stage_exit.py; PRD REQ-BRIT-07; tech-spec §3.14 (REQ-BRIT-04 roster, as the model to follow)
- **Checklist:** CHECK-T11

### V-010: §8.1 places REQ-COV-07 against its own stated placement principle
- **Severity:** improvement
- **Location:** tech-spec.md §8.1 (row REQ-COV-07 → `tests/test_state_verbs.py`)
- **Issue:** §8.1's principle is "Each test lands beside existing coverage of the same subject, reusing that file's CLI wrapper." REQ-COV-07's subject, per §3.12, is `stage_exit`'s routing degradation — `epic_name` → `route_epic` → the standalone route — which is `tests/test_stage_exit.py`'s subject (≈20 `stage-exit` references, plus the adjacent `test_docs_never_reimplements_the_epic_dependency_derivation` that §3.14 is already editing). `tests/test_state_verbs.py` covers the `state-*` verbs and touches `stage-exit` only incidentally (~6 mentions). The consequence is mild but real: a `stage_exit` regression test filed under the state-verb suite is where the next maintainer will not look, and §8.1 is explicitly "the audit trail" a verifier checks against.
- **Suggested fix:** Move the REQ-COV-07 row to `tests/test_stage_exit.py` and reuse that file's existing wrapper per §6.4. If it is deliberately kept in `test_state_verbs.py` (e.g. because the fixture that seeds an unsafe on-disk `epic` back-pointer already lives there), add a one-clause reason to the row — "kept beside the epic-back-pointer fixtures" — so the deviation from §8.1's own principle is a recorded position rather than an oversight.
- **References:** tech-spec §3.12, §6.4; tests/test_stage_exit.py; PRD REQ-COV-07
- **Checklist:** CHECK-T11

### V-011: §8.2 is titled "net test-count effect" but accounts for under half the affected file
- **Severity:** improvement
- **Location:** tech-spec.md §8.2
- **Issue:** The table covers `test_stage_exit_protocol.py`'s mutation controls (67) and stamp-verbatim tests (18) = 85 of the file's **102** collected items, omitting the remaining ~17 (including `test_the_loop_surface_covers_every_loop_outcome` and `test_the_docs_surface_covers_both_docs_outcomes`, which §3.4 explicitly names as preserved). No row states a file total or a suite total, so the table cannot be used to predict the post-change collection count — which is the one thing REQ-QUAL-01's "full suite MUST pass" check will compare against. With §8.3's baseline at 1840 passed / 2 skipped (confirmed: 1842 collected), a reader cannot derive the expected post-change number from §8.2.
- **Suggested fix:** Add an "unchanged" row for `test_stage_exit_protocol.py` (17 other items) and a bottom `**suite total**` row carrying the arithmetic: 1842 baseline − 39 (prose file) − 60 (mutation controls) − 2 (call-sites deletions) + 7 (backfill) + 1 (PRELUDE_CRITERIA test) ± the REQ-BRIT-07 dedup delta = expected post-change collection. Recompute once V-004, V-005 and V-009 settle their numbers. This turns §8.2 from a set of local deltas into the check a fix pass can actually run.
- **References:** tech-spec §8.3, §3.4; PRD REQ-QUAL-01, REQ-QUAL-04
- **Checklist:** CHECK-T11

## Fix Execution Plan

### User Decisions Required
1. **V-003 (structural region):** three admissible outcomes — (a) tighten the region bounds with neighbouring-call delimiters and add the mutation control, (b) keep the region as specified and **record** the measured detection loss as a declared boundary of the guard, or (c) tighten only, accepting 20/34. The verifier recommends (a). This is a design judgment about how much guard power REQ-TRIM-03 is willing to trade for window removal, and it should not be decided by a fix agent.
2. **V-006:** confirm the fourth test is intended to be retained (recommended) before it is added to the `PROTECTS` declaration.
3. **V-010:** confirm whether REQ-COV-07's placement in `test_state_verbs.py` is deliberate.

Everything else is mechanical and can be applied directly.

#### Step 1: Correct the body-cap measurement in §3.1 and §10.2
- **Files:** specs/verify-test-debt/tech-spec.md
- **Addresses:** V-001
- **Action:** In §3.1, rewrite the "Constraint check (C-05)" paragraph with the measured body figures (forge-0-epic 295/300 lines, 2749/5000 words, +5 lines headroom; forge-verify 299/300 lines, 4365/5000 words, +1 line) and state that `check_body_size` measures the body after the closing frontmatter fence, which is why `check-spec-purity.py` reports 0 violations. Delete the "Open risk" blockquote. In §10.2, delete item 1 (or mark it resolved with those numbers) and remove the "the pointer replaces existing text rather than adding to it" fallback. Do not change the pointer-not-paragraph decision. Re-number §10.2's remaining items if item 1 is deleted, and check no other section cross-references "§10.2 item N" by number.
- **Depends on:** none

#### Step 2: Reconcile the `_validated_findings_file` reuse across §3.8, §5, §6.1
- **Files:** specs/verify-test-debt/tech-spec.md
- **Addresses:** V-002
- **Action:** Adopt the defaulted-label approach. §3.8: change the reuse description to "a defaulted `label` parameter plus the loop" and update the snippet to pass `label="--path"`. §6.1: change the `_validated_findings_file` row's signature to `(value: str, target_dir: Path, label: str = "--findings-file") -> str` and its role to "reused with a defaulted label parameter; the default preserves every existing `--findings-file` message byte-for-byte". §5: replace the invented `--path` sentence with the real template, `Error: --path '../escape.md' contains a '..' segment; it must stay inside the feature directory ({dir})`, and note the helper emits one of five branch-specific messages (empty / control character / absolute / `..` segment / resolved escape). Add one line to §3.8 stating the existing `state-verify` call site and its tests must remain unchanged.
- **Depends on:** none

#### Step 3: Correct the hash-matrix roster
- **Files:** specs/verify-test-debt/tech-spec.md
- **Addresses:** V-004
- **Action:** §3.14 REQ-BRIT-07 table, first row → "**5 sites**", "**3** hand-rolled loops in `test_state_verbs.py`", naming `test_state_complete_rejects_a_short_or_malformed_hash_before_mutation`, `test_state_verify_commit_2_rejects_a_short_or_malformed_hash_before_mutation`, `test_epic_commit_2_rejects_a_short_or_malformed_hash_before_mutation`; note the two `test_state_schema_conformance.py` parametrized sites stay unchanged, and that the three loops exercise three different verbs/fixtures so each is parametrized in place rather than merged. §10.1: delete the hash-matrix row from the superseded-figures table and add "The PRD's hash-matrix ×5 is confirmed correct and is not superseded." Leave the other two supersessions (exact-stderr, `resolver_line_identical`) untouched — both verified correct.
- **Depends on:** none

#### Step 4: Re-derive the gate-selection family
- **Files:** specs/verify-test-debt/tech-spec.md
- **Addresses:** V-009
- **Action:** Define the counting unit explicitly, enumerate the qualifying tests in `tests/test_stage_exit.py` by name in the §3.14 table (following the REQ-BRIT-04 roster's format), and mark which are already parametrized. If the total is not 6, record the supersession in §10.1's table alongside the others. Preserve the "within-file only" rule.
- **Depends on:** none

#### Step 5: Resolve the §3.5 guard-power question
- **Files:** specs/verify-test-debt/tech-spec.md
- **Addresses:** V-003
- **Action:** Apply the user's decision from "User Decisions Required" item 1. For option (a): amend §3.5's region definition to `lower = max(nearest enclosing heading, end of the previous fenced state-* call)` / `upper = min(next heading, start of the next fenced state-* call)`; keep the fence-aware heading rule verbatim (it is correct and load-bearing — the naive scan produces exactly 2 false failures at `shared-conventions.md` lines 344 and 348); state the measured result (34/34 green, detection 20/34); add the mutation-control test to the "Consequent deletions" section as a **replacement**, describing it as deleting one known site's own `--epic` mandate from an in-memory copy and asserting Guard 1 reports that site. For option (b): add a "Declared boundary" paragraph to §3.5 recording the census (22/34 blind), naming the reopened `state-artifact`/`state-enter` incident, and add a matching bullet to §8.4. In all cases, extend "Why this is not 'a window by another name'" with one sentence acknowledging that the distinction is about tunability and that detection strength is treated separately.
- **Depends on:** Step 1 (avoids concurrent edits to the same document region only if §3.1 and §3.5 are edited in one pass; otherwise none)

#### Step 6: Fix the internal-consistency defects in §8.2 and the §6.1/§7 ordering invariant
- **Files:** specs/verify-test-debt/tech-spec.md
- **Addresses:** V-005, V-007, V-008, V-011
- **Action:** §8.2 call-sites row → `10 tests | **8** (−2 per REQ-TRIM-04/05)` naming both deletions (or `**9**` if Step 5 adds the mutation control). §8.2 REQ-BRIT-07 row → restate in one consistent unit per V-007, using the corrected rosters from Steps 3 and 4. §8.2 → add the `test_stage_exit_protocol.py` unchanged row (17 items) and a suite-total row carrying the arithmetic from the 1842 baseline. §6.1 → replace the single "validate → load → mutate → commit" invariant with the two-case statement per V-008. §7 → amend the fourth bullet to "before any mutation — and before the load where the validator does not depend on the resolved path."
- **Depends on:** Steps 3, 4, 5 (their numbers feed §8.2)

#### Step 7: Declare the fourth guard test and confirm REQ-COV-07 placement
- **Files:** specs/verify-test-debt/tech-spec.md
- **Addresses:** V-006, V-010
- **Action:** Per the user's decisions: add "4. This guard cannot be skipped or disabled." to §3.3's `PROTECTS` docstring block and one reconciling sentence to "Why 4 and not 5" citing REQ-GUARD-04's cap of 5. For §8.1, either move REQ-COV-07's row to `tests/test_stage_exit.py` or append the one-clause justification for keeping it in `test_state_verbs.py`.
- **Depends on:** user decisions 2 and 3

#### Step 8: Re-run the mechanical gates
- **Files:** none (verification only)
- **Addresses:** confirms no fix introduced a regression
- **Action:** This step edits only `specs/`, which is not a shipped surface, so no adapter regeneration is required (§3.15) — but run `python3 scripts/check-spec-purity.py` (expect `0 violations`) to confirm the spec edits added no canon citation, and re-run the V-004 roster derivation (`grep -n 'for label, value in _REJECTED_HASHES' tests/test_state_verbs.py` → expect 3 hits) to confirm the corrected figure. No test run is needed; no code changed.
- **Depends on:** Steps 1–7
