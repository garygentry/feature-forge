# Verification Report: stage-exit-coverage (impl, round 3)

Date: 2026-07-31
Pipeline Stage: forge-5-loop (complete, v1)
Mode: impl — served production stage `forge-5-loop`
Method: clean-room `forge-verifier` re-verification in require-clean mode, over the fix pass recorded in `VERIFY-impl-2026-07-31-round2.md` (commits `886270d` + `5bee461`). Every measurement below was re-derived independently — with patterns and methods deliberately different from the ones the fix pass used — and every changed prose hunk was read as prose and word-diffed.

Artifacts Reviewed:
- `specs/stage-exit-coverage/.verification/VERIFY-impl-2026-07-31-round2.md`
- `specs/stage-exit-coverage/.pipeline-state.json`
- `git diff 99e63e6..HEAD` (29 files, +590/-182)
- `scripts/forge-session.py`, `scripts/epic-manifest.py`, `scripts/check-spec-purity.py`
- `skills/forge-fix/SKILL.md`, `skills/forge-{1-prd,2-tech,3-specs,4-backlog,verify}/SKILL.md`
- `references/shared-conventions.md`, `references/stage-exit-protocol.md`
- `tests/test_capability_determination_prose.py`, `tests/test_state_verb_call_sites.py`, `tests/test_check_spec_purity.py`, `tests/test_forge_bootstrap.py`, `tests/test_stage_exit.py`
- all six `adapters/*/scripts/` and `adapters/*/skills/forge-fix/` mirrors

Checks Executed: 23 of 23 (18 pass, 3 fail, 2 not-applicable)

## Summary

- **Total findings: 8** — 2 errors, 1 gap, 0 inconsistencies, 5 improvements
- **All 10 round-2 findings are genuinely resolved** (N-1…N-5, V-003, V-005, V-009, V-011, V-017) — each re-measured independently, see "Round-2 finding disposition" below.
- **Both recorded user decisions were implemented as decided.** Decision 1 (V-009): the file-level ratchet landed as Rule 7 and genuinely red-gates. Decision 2 (V-017): option (b) only — `ruff.toml` is untouched (last modified in `81c9a53`, an unrelated earlier feature), F841/F541 are clean, and exactly **19** cosmetic hits remain.
- **Pipeline state is correct**: `stages.forge-verify-impl` = `findings-applied`, `commitHash` = `886270dff897fc807e8377084433c79d9d640ad2` (the full hash of `886270d`), `verifiedStageVersion` absent (cleared).
- **The whole gate is confirmed, not taken on report.** Every number the fix pass claimed reproduced exactly.
- **Two of the eight findings are defects the fix pass introduced that no round-2 finding named** (V-001, V-002) — found by the same method that surfaced N-1…N-5: reading the changed prose by eye and re-deriving every claim with a different instrument than the one that produced it. Both are *invisible to the full gate*: V-001 lives in skill prose, V-002 is a test that cannot fail.

### Gate (re-run independently, not taken on report)

| Check | Claimed | Measured | Result |
|---|---|---|---|
| `bash scripts/validate.sh` run 1 | exit 0 | exit **0**, `All checks passed!` | CONFIRMED |
| `bash scripts/validate.sh` run 2 (back-to-back) | exit 0 | exit **0**, `All checks passed!` | CONFIRMED |
| Full suite | 1789 passed / 2 skipped | run 1 **1789 passed, 2 skipped** (312.21s); run 2 **1789 passed, 2 skipped** (283.82s) | CONFIRMED |
| `tests/fixtures` bytecode after run 1 | zero | **0** | CONFIRMED |
| `tests/fixtures` bytecode after run 2 | zero | **0** | CONFIRMED |
| `python3 scripts/build-adapters.py --check` | no drift | exit **0** | CONFIRMED |
| `ruff check scripts/ eval/` | clean | exit **0**, `All checks passed!` | CONFIRMED |
| `python3 scripts/check-spec-purity.py` | — | exit **0**, `spec-purity: PASS — 0 violations` | CONFIRMED |
| `ruff check tests/` | 19 cosmetic remain | **19 errors**, F841/F541 clean | CONFIRMED |
| Working tree after both runs | — | clean (`git status --porcelain` empty) | CONFIRMED |

### Round-2 finding disposition (each re-measured, not taken on report)

| Finding | Verdict | Evidence |
|---|---|---|
| **N-1** (three de-indented docstring continuations) | **RESOLVED** | All four sites (`forge-session.py:5011`, `:3376`, `:3299`, `epic-manifest.py:883`) read correctly as prose with correct 6/8/12-space continuation indentation. A `tokenize`-based scan of every STRING/COMMENT token in all three edited scripts for `^\s{0,3}[.,;:—-]\s` returns **zero** hits. |
| **N-2** (merged word `from.epic-state.json`) | **RESOLVED** | `epic-manifest.py:1296` reads `read from .epic-state.json alone`. A `\b[a-z]{3,}\.[a-z]{3,}\b` sweep over all changed lines finds no further collapse. |
| **N-3** (six backticked coordinates) | **RESOLVED** | Re-measured with a **third** pattern (any `§` plus any `0N-*.md`), not the fix pass's: `scripts/forge-session.py` HEAD = **0** rule-7 citations / **3** bare `§` — byte-identical in count to feature base `9a663e1` (0 / 3). `scripts/epic-manifest.py` = **0** (base 71). |
| **N-4** (clause (c) unfalsifiable) | **RESOLVED** | Re-ran N-4's exact mutations on copies: deleting the real clause-(c) sentence from `forge-1-prd`, `forge-verify`, and `forge-fix` now goes **RED** on all three (previously green). Paragraph scoping via `_capability_paragraph` works; the boilerplate fragment is gone. Residual looseness is V-004 below — a different hole, not a re-opening of this one. |
| **N-5** (clause (b) degradable on `forge-verify`; single-representative controls) | **RESOLVED** | The `Reserve \`manual\` for any session that may not dispatch a subagent unsolicited` rewrite now goes **RED**. Controls are `parametrize`d over all **6** roster surfaces. A 6×3 sweep (delete all fragments of each clause on each surface) plus targeted semantic inversions: **18/18 RED** for full-clause removal, and every clause-(a)/(b) inversion constructible is RED on every surface. |
| **V-003** (guard structurally sound but clauses loose) | **RESOLVED** | Closed out by N-4/N-5 above. |
| **V-005** (citation strip damaged prose) | **RESOLVED** | Word-level `difflib` of `99e63e6:scripts/forge-session.py` vs HEAD: every non-equal opcode is a coordinate deletion with the sentence retained, or one of the four punctuation repairs. No content lost, no code touched. |
| **V-009** (no ratchet) | **RESOLVED** | Rule 7 landed and **genuinely red-gates**, verified by mutation on a full repo copy, not by reading the code — see the mutation table under V-003 below. The "would have caught N-3" claim is measured and correct: `99e63e6:scripts/forge-session.py` yields exactly **6** citations under `_SPEC_CITATION_RE`. Grandfather list: 29 entries, **sorted, deduped, zero phantoms, all still dirty**. |
| **V-011** (window unpinned) | **PARTIALLY RESOLVED** | The `LOOKBEHIND <= 12` / `LOOKAHEAD <= 8` pin exists and is meaningful; the full proximity sweep (delete each of the 34 sites' `--epic`-bearing lines one at a time) found **0 undetected sole-coverage deletions**, observed max distance above = **10** vs window 12. But the *message* half of V-011 is guarded by a **vacuous test** (V-002) and `LOOKAHEAD` is 8× its measured need (V-005). |
| **V-017** (ruff tests/) | **RESOLVED** | Option (b) exactly: `ruff check tests/ --select F841,F541` clean; 19 cosmetic hits remain; `ruff.toml` unchanged. Removing `worker` in `test_forge_bootstrap.py:733` does **not** weaken the test — the only surviving reference is `assert {o["member"] …} == {"packages/worker"}` at :737, which is a string literal, not the removed binding. |

---

## Findings

### V-001: `forge-fix`'s new clause-(c) sentence describes a directive path that cannot occur on a branch stage, and contradicts the skill's own Step 6 gate

- **Severity:** error
- **Location:** `skills/forge-fix/SKILL.md:110` (Step 7, **Capability.** paragraph), mirrored into all six `adapters/*/skills/forge-fix/` copies
- **Issue:** Step 3 of the round-2 fix pass added this sentence to canon, copied verbatim from `references/shared-conventions.md` § Verify Capability (which is written for *production* stages):

  > Such a bar is never grounds to skip verification, and never grounds to fence the production successor while verification is unresolved — on the `runInStageVerify: true` path the emitted `verifyGate` stays `none`, so reuse the Standard Verify Gate block for consent with **choice 2 omitted**, leaving exactly two choices: *Verify now* (recommended) and *Skip for now*, the latter persisted as an explicit `skipped` before any advancing block.

  Two independent defects:

  1. **The path is unreachable for this stage.** `forge-fix` closes with `stage-exit --stage forge-fix` (`skills/forge-fix/SKILL.md:133`), and `forge-fix` is a **branch** stage: `_BRANCH_STAGES` is derived as `EXIT_STAGES` minus `_EXIT_PRODUCTION_STAGES` (`scripts/forge-session.py:2032`). `run_in_stage` is computed as `… and stage not in _BRANCH_STAGES` (`:3540-3545`), so `runInStageVerify` is **structurally always `False`** here. `verifyGate` is `none` for a branch exit for an entirely *different* reason (`:3576` — `stage in _BRANCH_STAGES`; the adjacent comment states "A BRANCH exit is already inside the diversion and its outcome table names the one action to take, so there is nothing left to gate"). The sentence therefore instructs an agent to key behavior off a directive value that can never be emitted, and attributes `verifyGate: none` to the wrong cause. There is also no "production successor" to fence on a branch exit — `forge-fix` routes by its outcome table.
  2. **It contradicts Step 6 of the same skill.** `skills/forge-fix/SKILL.md` Step 6 defines this skill's own gate with **three** options, and choice 2 is explicitly present ("**Re-verify now + enable auto-verify going forward**"). The new sentence says "**choice 2 omitted**, leaving exactly two choices". Worse, Step 6 says of its skip: "*Skip for now* — an explicit deferral of the re-verify. It closes as **`deferred`**, never `reverified`: … the served stage's verification stays **outstanding** until a re-verify passes". The new sentence says that skip is "persisted as an explicit `skipped`" — which would *resolve* verification, the exact opposite, and contradicts the skill's own outcome table ("`applied` is not `reverified`… only `reverified` after a passing verify permits advancement").

  This is invisible to the gate: no test asserts branch-stage capability prose against `_BRANCH_STAGES`, and the drift guard is satisfied by fragments, not semantics.

  **Note on why the fix pass did this:** `CLAUSES["c"]`'s accepted phrasings include `"choice 2 omitted"` — a mechanism token specific to production stages. `forge-fix` genuinely lacked a clause-(c) statement (N-4 said so), and the cheapest way to satisfy the fragment list was to paste the production-stage sentence. The guard rewarded the wrong repair.
- **Suggested fix:** Replace the trailing sentence at `skills/forge-fix/SKILL.md:110` (from "Such a bar is never grounds to skip verification," to the end of the paragraph) with the **branch-appropriate** phrasing already in canon at `skills/forge-verify/SKILL.md`, adjusted to name this skill's own gate:

  > An auto-verify or re-verify directive under a no-unsolicited-dispatch bar is presented through the Step 6 gate and dispatched on the affirmative choice — never skipped, and never resolved by closing with an outcome that advances the pipeline.

  This still satisfies `CLAUSES["c"]` via the `"dispatched on the affirmative"` fragment (verified: the guard stays green with this wording and goes red when the sentence is deleted). Then re-run `python3 scripts/build-adapters.py` to refresh the six mirrors.
- **References:** `scripts/forge-session.py:2032` (`_BRANCH_STAGES`), `:3540-3545` (`run_in_stage`), `:3576` (`verify_gate`); `skills/forge-fix/SKILL.md` Step 6 and the Step 7 outcome table; `skills/forge-verify/SKILL.md` **Capability.** paragraph (the correct model); `references/stage-exit-protocol.md` § "Consent variant on a `none` gate" (:303-316) and § `verifyGate: "none"` (:327)
- **Checklist:** CHECK-I14, CHECK-I19

### V-002: `test_the_failure_message_describes_the_whole_window` is vacuous — its assertion is satisfied by its own source line

- **Severity:** error
- **Location:** `tests/test_state_verb_call_sites.py:167-177`
- **Issue:** The test reads its **own file** and asserts two substrings are present:

  ```python
  source = read(Path(__file__).resolve())
  assert "lines above or " in source and "lines below" in source, (
  ```

  Both literals appear *on that very assert line*, so `source` contains them unconditionally. `"lines below"` is additionally supplied by an unrelated comment at `:57` ("its flags on `` ` ``-continued lines below"). The test can never fail. Proven by mutation: reverting Guard 1's message at `:136` back to the lookbehind-only wording that V-011 objected to leaves the assertion `True`. The `"lines above or "` string occurs exactly twice in the file — once in the message it is meant to guard (`:136`) and once in its own assertion (`:175`) — and deleting the first changes nothing.

  This is the same class of defect as round 2's root cause: a check measured with the artifact that produces it. It matters because it is the *only* guard on the message half of V-011, so V-011's message fix has no protection at all.
- **Suggested fix:** Scope the read to Guard 1's assertion rather than the whole file, and exclude the guarding test's own body. Concretely, extract the source of `test_every_state_verb_call_site_carries_the_epic_instruction` via `inspect.getsource(...)` and assert both limbs appear **in that function only**:

  ```python
  guard_src = inspect.getsource(test_every_state_verb_call_site_carries_the_epic_instruction)
  assert "lines above or " in guard_src and "lines below" in guard_src, (...)
  ```

  Then confirm the fix by re-applying the mutation above (revert `:136` to lookbehind-only wording on a copy) and checking the test goes **red**.
- **References:** `tests/test_state_verb_call_sites.py:136` (the message under guard), `:57` (the unrelated "lines below" comment that also satisfies it); round-2 finding V-011
- **Checklist:** CHECK-I17

### V-003: Rule 7's citation pattern misses `tech-spec.md §N` — the exact spelling used in the checker's own header

- **Severity:** gap
- **Location:** `scripts/check-spec-purity.py:232-236` (`_SPEC_CITATION_RE`)
- **Issue:** The ratchet genuinely holds for the forms it was built against — verified by mutation on a full `shutil.copytree` of the repo, driving `check_no_spec_citations` directly:

  | Mutation | Result |
  |---|---|
  | `# see \`02\` §3.1 for the rule` appended to `scripts/forge-session.py` (cleaned, not grandfathered) | **RED** |
  | brand-new file `skills/forge-1-prd/references/new-note.md` citing `03-verification-state.md` | **RED** |
  | brand-new file `scripts/new-helper.py` citing `` `04` §2.2 `` | **RED** |
  | `# see tech-spec.md §3.4` appended to `scripts/forge-session.py` | **GREEN — miss** |
  | `# see spec 07, §6.2` appended | **GREEN — miss** |
  | `# see spec 03 section 3.6` appended | **GREEN — miss** |

  The `tech-spec.md §N` miss is the material one, because it is **internally inconsistent** and **live in this repo**. Branch 1 (`\b0[0-9]-[a-z][a-z0-9-]*\.md\b`) catches a full spec filename with no `§` at all, but branch 3 (`\btech-spec\s*§`) requires `§` to follow `tech-spec` immediately — so `tech-spec §3.4` trips while the more explicit `tech-spec.md §3.4` does not. `scripts/check-spec-purity.py:4` itself writes `tech-spec.md §3.4`, and that instance is *not* among the citations the regex counts in that file. A regression written in the repo's own most common spelling of a tech-spec citation passes the gate.

  The comma and "section"-word misses are lower-value (no live instances), and the deliberate non-matching of a bare intra-file `§` is correct and documented.
- **Suggested fix:** Extend branch 3 to accept an optional `.md` and a following separator, and add branch coverage for the filename-only form:

  ```python
  r"|\btech-spec(?:\.md)?\s*§"
  r"|\btech-spec\.md\b"
  ```

  Re-run `python3 scripts/check-spec-purity.py` afterwards — this will newly flag files, so re-derive `CITATION_GRANDFATHERED` counts and add any newly-dirty file that predates this change (do **not** add `scripts/forge-session.py`, `scripts/epic-manifest.py`, or `eval/run-compliance-eval.py`, which must stay locked). Add a `pytest.mark.parametrize` case to `test_each_citation_form_trips_the_ratchet` in `tests/test_check_spec_purity.py` for `"the tech-spec.md §3.4 rules govern this"`.
- **References:** `scripts/check-spec-purity.py:4` (the unmatched live instance), `:222-231` (the docstring claiming "a tech-spec coordinate" is covered); `tests/test_check_spec_purity.py::test_each_citation_form_trips_the_ratchet`
- **Checklist:** CHECK-I17

### V-004: The capability guard's clause (c) still admits the misreading it exists to prevent — on all six surfaces

- **Severity:** improvement
- **Location:** `tests/test_capability_determination_prose.py:96-103` (`CLAUSES["c"]`)
- **Issue:** N-4 and N-5 are genuinely fixed (see disposition table), but a residual hole remains, of the *same shape* N-5 identified for clause (b): a fragment that carries no semantic content.

  Clause (c) is defined in the module docstring (:21-23) as two obligations — the directive "goes through the gate and is dispatched on the affirmative" **and** it is "never silently skipped, and never resolved by advancing to the production successor." The accepted fragments pin the gate half (`"dispatched on the affirmative"`) and the successor half (`"never grounds to fence the production successor"`), but **nothing pins the no-skip half**, and `"choice 2 omitted"` is a purely mechanical gate-shape token.

  Measured on copies (`_assert_capability_prose`):

  | Mutation | Surfaces | Result |
  |---|---|---|
  | invert `"is never grounds to skip verification"` → `"IS grounds to skip verification entirely"` (keeping the rest) | forge-1-prd, -2-tech, -3-specs, -4-backlog, forge-fix | **GREEN** (undetected) |
  | delete the whole "never grounds…" lead-in, keep only the `runInStageVerify` mechanism tail | same five | **GREEN** (undetected) |
  | `forge-verify`: rewrite to "may be skipped, **or** dispatched on the affirmative choice, **or** resolved by advancing to the production successor" | forge-verify | **GREEN** (undetected) |

  The module's own bar (`:69-70`) is "Every fragment must carry the clause's MEANING, so that rewriting the sentence into the misreading the clause exists to prevent breaks the match." `"choice 2 omitted"` and `"dispatched on the affirmative"` do not meet it for the no-skip obligation. This is not a regression from round 2 — the guard is materially stronger than it was — but it is the same lesson unapplied to the third half.

  This is also the mechanism that made V-001 possible: `"choice 2 omitted"` is a production-stage-only token, and admitting it as clause-(c) evidence is what let a branch stage be "repaired" by pasting production-stage prose.
- **Suggested fix:** Split clause (c) into two independently-required sub-clauses, both of which must match:
  - **c1 (gate):** any of `"dispatched on the affirmative"`, `"presented through the gate"`.
  - **c2 (no-skip / no-advance):** any of `"never grounds to skip verification"`, `"never skipped"`, `"never grounds to fence the production successor"`, `"never resolved by advancing to the production successor"`.

  Drop `"choice 2 omitted"` entirely — it is a gate-shape detail, not a clause. Adjust `_assert_clauses_in` to iterate the sub-clauses, and extend negative control 3 to delete c1's and c2's fragments in two separate parametrized passes so each is independently proven to bite on all six surfaces. Re-run the three mutations in the table above and confirm each now goes red. Note this will require `skills/forge-verify/SKILL.md` and the four authoring stages to be re-checked — all five already contain a c2 phrasing, so no canon edit should be needed beyond V-001's.
- **References:** `tests/test_capability_determination_prose.py:21-23` (the clause definition), `:69-83` (the stated fragment bar and the two fragments already removed for failing it); V-001
- **Checklist:** CHECK-I17

### V-005: `LOOKAHEAD = 8` is eight times its measured maximum, and the pin's docstring claims a measurement that does not exist

- **Severity:** improvement
- **Location:** `tests/test_state_verb_call_sites.py:52` (`LOOKAHEAD`), `:141-163` (`test_the_window_is_no_wider_than_the_measured_maximum`)
- **Issue:** The new pin is real and the lookbehind half is well-founded: re-measured across all 34 call sites in canon, the maximum distance to a site's `--epic` mandate **above** is **10**, against `LOOKBEHIND = 12` — exactly the "measured maximum plus 2 lines of margin" the comment at `:44-50` claims. The full adversarial deletion sweep (remove one `--epic`-bearing line at a time across every canon file, recompute all 34 sites, report any site whose sole coverage vanished without the guard noticing) found **0 undetected deletions**. Guard 1 bites.

  But the maximum distance **below** a call site is **1** (a single site carries `--epic` inline on the continuation line immediately after the verb), against `LOOKAHEAD = 8`. The docstring says "12/8 is the measured maximum (10 lines above at the widest real site) plus a small margin for a reworded lead-in" — it supplies a measurement for 12 and none for 8, while asserting both are measured. Given that the module's own rationale for pinning is "the window is the guard's entire discriminating power", a 7-line unjustified reach below every call site is the surface on which the *next* buried-mandate hole would open, and the docstring would not warn a future maintainer that 8 was never measured.

  No live hole exists today — hence `improvement`, not `gap`.
- **Suggested fix:** Tighten `LOOKAHEAD` to `3` (matching `CALL_SPAN`, which already documents "the longest call in canon (verb + two flag lines)") and change the pin to `assert LOOKAHEAD <= 3`. Correct the docstring at `:151-154` to state both measurements explicitly: "10 lines above and 1 line below at the widest real sites; 12/3 adds margin for a reworded lead-in and for the longest fenced call (`CALL_SPAN`)." Re-run the suite — with 34 sites and max-below of 1, nothing should regress.
- **References:** `tests/test_state_verb_call_sites.py:44-58` (`LOOKBEHIND`/`LOOKAHEAD`/`CALL_SPAN` comments); round-2 finding V-011
- **Checklist:** CHECK-I17

### V-006: `CITATION_GRANDFATHERED`'s annotation for `check-spec-purity.py` records 21; the real count at landing is 24

- **Severity:** improvement
- **Location:** `scripts/check-spec-purity.py:203`
- **Issue:** The list is documented as "listed with their count at that time" (`:192-193`). Recomputing every entry with `_SPEC_CITATION_RE` at HEAD: **28 of 29 annotations are exact**, no phantom paths, the list is sorted and deduped, and every entry is still dirty (so no entry is stale). The single mismatch is `"scripts/check-spec-purity.py",  # 21` where the actual count is **24** — the Rule 7 comment block added in this same commit introduces new citations (`03-verification-state.md`, `` `02` §3.1 ``, `03 §5.1`, `tech-spec §3.4` in the docstrings at `:159-236`), so the file was already at 24 when the annotation was written.

  Non-blocking: the annotations are documentation, not enforced by `check_no_spec_citations`, and `test_grandfather_list_is_sorted_deduped_and_shrinking_only` correctly checks only existence + still-dirty, not the number. But the whole point of the annotation is to let a reviewer see the debt shrink, and a wrong baseline makes a partial cleanup look like a regression.
- **Suggested fix:** Change `:203` to `"scripts/check-spec-purity.py",  # 24`. Optionally extend `test_grandfather_list_is_sorted_deduped_and_shrinking_only` to parse each entry's trailing `# N` annotation and assert the live count is `<= N` (never `>`), which makes the annotations self-maintaining and enforces the "shrinking only" property the test name already claims.
- **References:** `scripts/check-spec-purity.py:191-221`; `tests/test_check_spec_purity.py::test_grandfather_list_is_sorted_deduped_and_shrinking_only`
- **Checklist:** CHECK-I19

### V-007: `test_the_controls_cover_every_determining_surface`'s second assertion is tautological

- **Severity:** improvement
- **Location:** `tests/test_capability_determination_prose.py:340-348`
- **Issue:**

  ```python
  assert SURFACE_IDS == [relpath for relpath, _ in _capability_surfaces()], (
      "the controls' roster drifted from the live derived roster"
  )
  ```

  `SURFACE_IDS` is derived at import from `ALL_SURFACES = _capability_surfaces()` (`:279-280`). `_capability_surfaces()` is a pure function of files on disk, so within a single process the comparison is `f() == f()` and cannot fail short of a mid-run file edit. The stated failure mode — "the controls' roster drifted from the live derived roster" — is precisely the one it cannot detect.

  The first assertion in the same test (`len(ALL_SURFACES) >= MIN_CAPABILITY_SURFACES`) **is** meaningful and is the non-vacuity floor that matters, so the test as a whole is not worthless — but the second line advertises a guarantee it does not provide, and would silently keep passing if someone later replaced the derived `ALL_SURFACES` with a hardcoded list *at module level*, which is exactly the drift it names.
- **Suggested fix:** Either delete the second assertion (the first already carries the test), or make it assert the property actually at risk — that the parametrization is derived rather than literal:

  ```python
  source = read(Path(__file__).resolve())
  assert "ALL_SURFACES: Final[list[tuple[str, str]]] = _capability_surfaces()" in source, (
      "ALL_SURFACES is no longer derived from the canonical exit table"
  )
  ```

  (Note: unlike V-002, this reads for a *different* string than the one it writes, so it is not self-satisfying — confirm that by deleting the module-level assignment on a copy and checking the test goes red.)
- **References:** `tests/test_capability_determination_prose.py:279-280` (`ALL_SURFACES`/`SURFACE_IDS`), `:244-254` (`test_the_roster_is_derived_not_listed`, which does carry a real derivation check)
- **Checklist:** CHECK-I17

### V-008: `check-spec-purity.py` now claims seven rules come from `tech-spec.md §3.4`; no tech-spec defines them, and Rule 7 came from a verification finding

- **Severity:** improvement
- **Location:** `scripts/check-spec-purity.py:4` (module docstring) and `:257` (`Rule` enum docstring)
- **Issue:** The fix pass changed "the **six** rules from tech-spec.md §3.4" to "the **seven** rules from tech-spec.md §3.4" in both places. The `§3.4` pointer resolves nowhere: `specs/context-efficiency/tech-spec.md §3.4` is "R4 — Targeted state verbs", `specs/forge-bootstrap/tech-spec.md §3.4` is "Greenfield gate + transient resume sentinel", `specs/stage-exit-coverage/tech-spec.md §3.4` is "Compatibility-split error policy", and `specs/epic-orchestration/tech-spec.md §3.4` is "Centralized name→directory resolution". None enumerates purity rules, and none could contain a seventh — the file's own adjacent line (`:270`) correctly records Rule 7's provenance as `# rule 7 — shipped-artifact ratchet (V-009)`, a verification finding from *this* round, not a tech-spec decision.

  The dangling `§3.4` pointer is pre-existing (it was wrong at "six" too), but the fix pass propagated and strengthened the false claim by incrementing the count, and the file is grandfathered so Rule 7 will never flag its own header. Non-blocking documentation accuracy.
- **Suggested fix:** Reword `:4` to drop the citation, since the rules are self-documented in the `Rule` enum: "Stdlib-only (no pyyaml), matching scripts/epic-manifest.py. Enforces the seven rules enumerated in the `Rule` enum below — six from the original spec-purity contract plus rule 7, the shipped-artifact self-containment ratchet added by finding V-009." Apply the same edit at `:257`. This also removes two of the 24 grandfathered citations in the file, so decrement its `CITATION_GRANDFATHERED` annotation accordingly when applying V-006.
- **References:** `scripts/check-spec-purity.py:262-270` (the `Rule` enum with correct per-rule provenance); `specs/*/tech-spec.md` §3.4 headings
- **Checklist:** CHECK-I19

---

## Checks Executed

| Check | Result | Note |
|---|---|---|
| CHECK-I01 | pass | No files added or removed relative to any architecture spec; all new symbols land inside existing files. |
| CHECK-I02 | not-applicable | Python/skill-canon repo; no package.json exports map for this feature. |
| CHECK-I03 | pass | `StageExitDirectives` field set unchanged — the word-level diff of `forge-session.py` shows only comment-text opcodes. |
| CHECK-I04 | pass | No error classes added or changed. |
| CHECK-I05 | pass | Backlog unchanged; `forge-5-loop` complete at v1. |
| CHECK-I06 | pass | No pending/in-progress items. |
| CHECK-I07 | pass | |
| CHECK-I08 | pass | Suite green; `check-spec-purity.py` imports and executes standalone. |
| CHECK-I09 | pass | Rule 7 is wired: `collect_violations` → `main` → `scripts/validate.sh:150`. |
| CHECK-I10 | pass | Adapter drift check clean across all six hosts. |
| CHECK-I11 | pass | `ruff check scripts/ eval/` exit 0. |
| CHECK-I12 | pass | `build-adapters.py --check` exit 0; `validate.sh` green twice. |
| CHECK-I13 | pass | No new TODO/placeholder markers. |
| CHECK-I14 | **fail** | V-001 — `forge-fix` capability prose keys off an unreachable directive value and contradicts its own Step 6. |
| CHECK-I15 | pass | The hardcoded `99e63e6` in `test_the_ratchet_would_have_caught_the_n3_leak` is a deliberate historical fact with a skip fallback; acceptable. |
| CHECK-I16 | pass | 1789 passed / 2 skipped, reproduced on both runs. |
| CHECK-I17 | **fail** | V-002, V-003, V-004, V-005, V-007. |
| CHECK-I18 | pass | |
| CHECK-I19 | **fail** | V-006, V-008 (and V-001's skill-doc half). |
| CHECK-I20 | pass | `SELF_CONTAINMENT_SURFACES` and `CITATION_GRANDFATHERED` are documented in place, including maintenance policy. |
| CHECK-I21 | not-applicable | `smokeCommand` is `null` in `forge.config.json`. Advisory: this repo's runnable surface is exercised by `validate.sh` (adapter regeneration + 1789 tests + purity + traceability + version sync), which is a reasonable stand-in; configuring an explicit `smokeCommand` would make "clean" mean "it runs". |
| CHECK-I22 | pass | `check_no_spec_citations` has a non-test caller (`collect_violations`, reached from `main` and from `scripts/validate.sh:150`); `iter_shipped_files` likewise. |
| CHECK-I23 | not-applicable | No universal framework bootstrap entry in this stack. |

Executed 23 of 23 checks. Results: 18 pass, 3 fail, 2 not-applicable.

---

## Fix Execution Plan

### User Decisions Required

None — all eight fixes can be applied directly. V-001's replacement wording is specified verbatim and verified to keep the drift guard green while going red on deletion; V-003 and V-004 both widen existing guards and require no policy call.

One judgment worth flagging for the applier (not a decision): **apply V-004 before V-001** is *not* required, but if V-004 is applied first, `"choice 2 omitted"` stops being an accepted clause-(c) phrasing, which will red-gate `skills/forge-fix/SKILL.md` until V-001 lands. Step ordering below avoids that.

### Execution Steps

#### Step 1: Correct `forge-fix`'s capability prose
- **Files:** `skills/forge-fix/SKILL.md` (:110), then all six `adapters/*/skills/forge-fix/` mirrors via regeneration
- **Addresses:** V-001
- **Action:** In the Step 7 **Capability.** paragraph, replace everything from "Such a bar is never grounds to skip verification," through the end of the paragraph with: "An auto-verify or re-verify directive under a no-unsolicited-dispatch bar is presented through the Step 6 gate and dispatched on the affirmative choice — never skipped, and never resolved by closing with an outcome that advances the pipeline." Leave the preceding three sentences (clauses a and b) untouched. Then run `python3 scripts/build-adapters.py`. Confirm `tests/test_capability_determination_prose.py` is still green (the replacement matches `CLAUSES["c"]` via `"dispatched on the affirmative"`), and confirm deleting that new sentence on a copy goes red.
- **Depends on:** none — do this first; it is shipped canon that contradicts itself.

#### Step 2: De-vacuify the window-message guard
- **Files:** `tests/test_state_verb_call_sites.py` (:167-177)
- **Addresses:** V-002
- **Action:** Add `import inspect`, and rewrite the assertion to read `inspect.getsource(test_every_state_verb_call_site_carries_the_epic_instruction)` instead of the whole file. **Verify by mutation, not by re-running green:** on a scratch copy, revert `:136`'s message to the lookbehind-only wording and confirm the test now fails. Do not accept "suite still passes" as evidence.
- **Depends on:** none

#### Step 3: Tighten the lookahead window and correct its rationale
- **Files:** `tests/test_state_verb_call_sites.py` (:52, :141-163)
- **Addresses:** V-005
- **Action:** Set `LOOKAHEAD = 3`; change the pin to `assert LOOKAHEAD <= 3` with a message naming the same buried-mandate failure mode. Rewrite the docstring's measurement sentence to state both measured maxima explicitly (10 above, 1 below) rather than implying 8 was measured. Re-run the full suite; `test_every_state_verb_call_site_carries_the_epic_instruction` must stay green across all 34 sites.
- **Depends on:** Step 2 (same file; avoid conflicting edits)

#### Step 4: Split clause (c) and drop the mechanism token
- **Files:** `tests/test_capability_determination_prose.py` (:96-103, :181-187, :321-337)
- **Addresses:** V-004
- **Action:** Replace `CLAUSES["c"]` with two required sub-clauses — c1 accepting `("dispatched on the affirmative", "presented through the gate")` and c2 accepting `("never grounds to skip verification", "never skipped", "never grounds to fence the production successor", "never resolved by advancing to the production successor")` — and remove `"choice 2 omitted"` entirely. Update `_assert_clauses_in` to iterate sub-clauses and keep the `clause \(c\)` substring in its failure message so negative control 3's `pytest.raises(match=...)` still matches (or update the match pattern to `clause \(c[12]?\)`). Split negative control 3 into two parametrized controls, one per sub-clause, each running over all six surfaces. Then re-run these three mutations on copies and confirm each is **red**: (a) inverting `"is never grounds to skip verification"` → `"IS grounds to skip verification entirely"` on any authoring stage; (b) deleting the "never grounds…" lead-in while keeping the mechanism tail; (c) on `forge-verify`, rewriting to "may be skipped, or dispatched on the affirmative choice, or resolved by advancing to the production successor".
- **Depends on:** Step 1 (V-001 must land first, or dropping `"choice 2 omitted"` red-gates `forge-fix`)

#### Step 5: Fix the tautological roster assertion
- **Files:** `tests/test_capability_determination_prose.py` (:340-348)
- **Addresses:** V-007
- **Action:** Replace the second assertion with the source-text derivation check given in V-007's suggested fix, or delete it and keep only the floor assertion. If the source-text form is used, prove it bites by deleting the module-level `ALL_SURFACES = _capability_surfaces()` assignment on a copy.
- **Depends on:** Step 4 (same file)

#### Step 6: Close the Rule 7 pattern gap
- **Files:** `scripts/check-spec-purity.py` (:232-236, plus `CITATION_GRANDFATHERED` if counts shift), `tests/test_check_spec_purity.py`
- **Addresses:** V-003
- **Action:** Add `|\btech-spec(?:\.md)?\s*§` (replacing the existing `|\btech-spec\s*§`) and `|\btech-spec\.md\b` to `_SPEC_CITATION_RE`, and update the pattern's docstring at `:222-231` to describe the `.md` variant. Run `python3 scripts/check-spec-purity.py`; for any newly-flagged file that predates this change, add a grandfather entry with its count — but **never** for `scripts/forge-session.py`, `scripts/epic-manifest.py`, or `eval/run-compliance-eval.py`, which must stay locked. Add a parametrize case `"the tech-spec.md §3.4 rules govern this"` to `test_each_citation_form_trips_the_ratchet`.
- **Depends on:** none

#### Step 7: Correct the two documentation claims in `check-spec-purity.py`
- **Files:** `scripts/check-spec-purity.py` (:4, :203, :257), `tests/test_check_spec_purity.py`
- **Addresses:** V-006, V-008
- **Action:** Reword `:4` and `:257` to drop the dangling `tech-spec.md §3.4` citation per V-008's suggested fix. Then recompute the file's own citation count with the final `_SPEC_CITATION_RE` (post-Step 6, post-reword) and set `:203`'s annotation to that number. Optionally add the `<= annotated N` assertion to `test_grandfather_list_is_sorted_deduped_and_shrinking_only`.
- **Depends on:** Step 6 (the regex change alters the count being annotated)

#### Step 8: Regenerate and re-gate
- **Action:** `python3 scripts/build-adapters.py`, then `python3 scripts/build-adapters.py --check` (exit 0), then `bash scripts/validate.sh` **twice back-to-back** (both exit 0, both `All checks passed!`), then `find tests/fixtures -name '__pycache__' -o -name '*.pyc' | wc -l` after each run (both must be 0), then `ruff check scripts/ eval/` and `python3 scripts/check-spec-purity.py`.
- **Verification discipline:** for every guard touched in Steps 2–5, the acceptance evidence is a **mutation going red**, not the suite staying green. A green suite is what round 1 and round 2 both had while shipping broken guards.
- **Depends on:** Steps 1–7
