# Verification Report: stage-exit-coverage (impl, round 4)

Date: 2026-07-31
Pipeline Stage: forge-5-loop (complete, v1)
Mode: impl — served production stage `forge-5-loop`
Method: clean-room `forge-verifier` re-verification in require-clean mode, over the fix pass recorded in `VERIFY-impl-2026-07-31-round3.md` (commits `cb577d4` + `b469674`). Every number below was re-derived with an instrument different from the one the fix pass used; every changed prose hunk was read as prose and word-diffed; every guard touched was accepted only on a **mutation going red**, run on `shutil.copytree` copies under `/tmp`. Nothing in the repository was modified by the verification.

Artifacts Reviewed:
- `specs/stage-exit-coverage/.verification/VERIFY-impl-2026-07-31-round3.md` (findings + Fix Progress + Deviations)
- `specs/stage-exit-coverage/.pipeline-state.json`
- `git diff b709422..HEAD` (13 files, +224/−53) and `git diff 99e63e6..HEAD`
- `scripts/check-spec-purity.py`, `scripts/validate.sh`, `scripts/forge-session.py`
- `skills/forge-fix/SKILL.md`, `skills/forge-verify/SKILL.md`, `skills/forge-{1-prd,2-tech,3-specs,4-backlog}/SKILL.md`
- `tests/test_capability_determination_prose.py`, `tests/test_state_verb_call_sites.py`, `tests/test_check_spec_purity.py`
- all six `adapters/*/skills/forge-fix/` mirrors

Checks Executed: 23 of 23 (19 pass, 2 fail, 2 not-applicable)

## Summary

- **Total findings: 5** — 1 error, 0 gaps, 1 inconsistency, 3 improvements.
- **Seven of the eight round-3 findings are genuinely resolved** (V-001, V-002, V-003, V-004, V-005, V-006, V-008), each re-measured independently.
- **V-007 is NOT resolved.** Its replacement assertion is vacuous in exactly the way the assertion it replaced was vacuous, and in exactly the way round-3's V-002 was: the searched literal sits on the assert line itself. The round-3 Fix Progress claim "Mutation-verified: replacing only the module-level `ALL_SURFACES = _capability_surfaces()` with a hardcoded literal goes RED" does not hold — the mutation used was roster-*shrinking*, so the red came from a different assertion. This is the round's one error and the fourth consecutive round in which a defect ships under a fully green suite.
- **Both deliberate deviations are SOUND**, and both of the fix pass's stated justifications reproduce exactly under independent measurement. Neither leaves the defect its finding named open. Details in the deviation verdicts below.
- **The gate is confirmed, not taken on report.** Every claimed number reproduced to the digit, including the two back-to-back 1802/2 runs.
- **Pipeline state is correct**, including the `notes` edit: word-level diff of the `notes` string shows exactly one word changed (`12/8-line` → `12/3-line`), identical word count (163 → 163), and every other top-level key byte-identical.
- **No prose damage.** Zero de-indented docstring continuations across all four changed Python files (`tokenize` sweep of every STRING/COMMENT token for `^\s{0,3}[.,;:—–\-)\]]\s`), zero merged words over 224 added lines, zero column-0 punctuation. The last two rounds' signature failure mode did not recur.

### Gate (re-run independently, not taken on report)

| Check | Claimed | Measured | Result |
|---|---|---|---|
| `python3 scripts/build-adapters.py --check` | exit 0, no drift | exit **0** | CONFIRMED |
| `bash scripts/validate.sh` run 1 | exit 0, `All checks passed!` | exit **0**, `All checks passed!` | CONFIRMED |
| `bash scripts/validate.sh` run 2 (back-to-back) | exit 0, `All checks passed!` | exit **0**, `All checks passed!` | CONFIRMED |
| Full suite, run 1 | 1802 passed / 2 skipped | **1802 passed, 2 skipped** (239.64s) | CONFIRMED |
| Full suite, run 2 | 1802 passed / 2 skipped | **1802 passed, 2 skipped** (239.84s) | CONFIRMED |
| `find tests/fixtures -name '__pycache__' -o -name '*.pyc' \| wc -l` after run 1 | 0 | **0** | CONFIRMED |
| …after run 2 | 0 | **0** | CONFIRMED |
| `ruff check scripts/ eval/` | clean | exit **0**, `All checks passed!` | CONFIRMED |
| `python3 scripts/check-spec-purity.py` | exit 0 | exit **0**, `spec-purity: PASS — 0 violations` | CONFIRMED |
| `ruff check tests/` | 19 cosmetic | **19 errors**, itemized; **none** in any of the four files this pass changed except a pre-existing `test_check_spec_purity.py:272` outside every diff hunk | CONFIRMED |
| `ruff check tests/ --select F841,F541` | clean | `All checks passed!` | CONFIRMED |
| `git status --porcelain` before and after both runs | clean | empty, all three times | CONFIRMED |

### Pipeline state (re-derived)

| Property | Expected | Measured |
|---|---|---|
| `stages.forge-verify-impl.status` | `findings-applied` | `findings-applied` ✓ |
| `.commitHash` | full 40-hex of `cb577d4` | `cb577d473ce8b72dff6281218c79db9edb83fee6`; `git rev-parse cb577d4` returns the same string, length 40 ✓ |
| `.verifiedStageVersion` | absent | absent ✓ |
| `.verifiedAt` | (implied) absent | absent ✓ — shape is byte-for-byte the same as the round-2 `findings-applied` entry at `886270d` |
| `notes` | `12/3`, nothing else lost | one word replaced, 163 → 163 words, all other keys equal ✓; and the value is accurate — `LOOKBEHIND = 12`, `LOOKAHEAD = 3` |

### Round-3 finding disposition (each independently re-measured)

| Finding | Verdict | Independent evidence |
|---|---|---|
| **V-001** (forge-fix clause-(c) describes an unreachable directive path) | **RESOLVED** | The `runInStageVerify` / `verifyGate: none` / `choice 2 omitted` / "persisted as an explicit `skipped`" sentence is gone. The replacement at `skills/forge-fix/SKILL.md:110` reads: *"An auto-verify or re-verify directive under a no-unsolicited-dispatch bar is presented through the Step 6 gate and dispatched on the affirmative choice — never skipped, and never resolved by closing with an outcome that advances the pipeline."* Checked against the same skill: Step 6's gate is real and its affirmative choices dispatch clean-room; "never resolved by closing with an outcome that advances the pipeline" agrees with the Step 7 outcome table (`applied` → no advancement; only `reverified` advances) and with Step 6's own "`applied` is not `reverified`". No reference to a directive value a branch stage cannot emit. Word-diff of the hunk shows a clean sentence swap, no fragment left behind. All six mirrors carry the sentence exactly once (`grep -c` = 1 on each); `build-adapters.py --check` exit 0. Mutation M12: deleting the sentence turns controls 3a, 3b and 3c RED on `skills/forge-fix/SKILL.md`. |
| **V-002** (window-message guard vacuous) | **RESOLVED** | `tests/test_state_verb_call_sites.py:182` now reads `inspect.getsource(test_every_state_verb_call_site_carries_the_epic_instruction)`. The two searched literals live in the *guarding* test's own body, not the guarded function's, so the self-satisfaction path is closed. Mutation M1: reverting Guard 1's message at `:139-143` to lookbehind-only wording turns the test **RED** at `:183` (it stayed green before). |
| **V-003** (`tech-spec.md §N` not matched) | **RESOLVED**, with a sound deviation | `_SPEC_CITATION_RE` branch 3 is now `\btech-spec(?:\.md)?\s*§`. Probed directly: `see tech-spec.md §3.4` → **True** (was False), `see tech-spec §3.4` → True, `see tech-spec.md  §3.4` → True. Mutation M5: reverting the branch turns the new parametrize case `"the tech-spec.md §3.4 rules govern this"` **RED**. The bare-filename branch was withheld — verdict below. |
| **V-004** (clause (c) admits its own misreading) | **RESOLVED**, with a sound deviation | Both stated reasons reproduce exactly. **(i)** The finding's prescribed c1 list `("dispatched on the affirmative", "presented through the gate")` is satisfied by **0 of the 4** authoring stages (True only on `forge-verify` and `forge-fix`) — it would have red-gated four compliant surfaces. **(ii)** The finding's merged c2 stays **GREEN on all 4** authoring stages under its own mutation (a) (`"is never grounds to skip verification"` → `"IS grounds to skip verification entirely"`), because `"never grounds to fence the production successor"` in the same sentence keeps matching; the shipped split c2 goes **RED on all 4**. `"choice 2 omitted"` is gone from `CLAUSES` entirely. Controls 3a/3b/3c are each parametrized over all 6 surfaces and each bites (M4, M12). Residual looseness is V-003 below — a different hole in c1, not a re-opening of this one. |
| **V-005** (`LOOKAHEAD` 8× its need; docstring claims an absent measurement) | **RESOLVED** | `LOOKAHEAD = 3`. Re-derived from canon with an independent walker: **34** call sites; max lookbehind distance actually used = **10** (`references/shared-conventions.md:348`); exactly **2** sites are not covered by lookbehind alone (`skills/forge-1-prd/SKILL.md:116` and `skills/forge-2-tech/SKILL.md:110`, both `state-ecr`), and both carry `--epic` at distance **1** below. So the true minimum is `LOOKAHEAD >= 2`; 3 is 1 line of margin. The constant comment (`:47-57`) and the pin docstring (`:156-161`) now state both measurements — "10 lines above and 1 line below" — and both are **correct**. See V-004 below for the one weakening in how the pin is expressed. |
| **V-006** (`check-spec-purity.py` annotation reads 21 vs a real 24) | **RESOLVED and generalized** | Re-derived **all 29** annotations against the live pattern with an independent loader: **29 of 29 exact**, zero mismatches, list sorted, deduped, every path exists and is still dirty. `scripts/check-spec-purity.py` is annotated **25** and measures **25**. The optional ceiling was implemented — see the new-guard audit below. |
| **V-007** (tautological roster assertion) | **NOT RESOLVED** | The replacement is vacuous in the same way. See finding V-001 below. |
| **V-008** (false "seven rules from tech-spec.md §3.4" claim) | **RESOLVED** | `scripts/check-spec-purity.py:4-8` now reads "Enforces the seven rules enumerated in the ``Rule`` enum below — six from the original spec-purity contract plus rule 7, the shipped-artifact self-containment ratchet added by finding V-009"; the `Rule` enum docstring (`:277-282`) likewise points at the per-member provenance comments and states "there is no single spec section that enumerates all seven". Neither site cites `§3.4` any more. The two surviving `tech-spec §3.3` citations at `:38` and `:890` are pre-existing, unrelated, and inside the file's grandfathered debt. Both reworded docstrings read correctly as prose. |

### New-guard audit — `test_grandfather_list_is_sorted_deduped_and_shrinking_only`

Whether the new `# N` ceiling bites, and whether its source-parsing regex could silently match nothing. Measured on copies:

| Mutation | Result |
|---|---|
| Lower `"scripts/build-adapters.py",  # 83` to `# 2` | **RED** at `:438` — the ceiling bites |
| Strip an entry's `# N` annotation entirely | **RED** at `:433` — every entry must carry one |
| Rewrite the tuple so `CITATION_GRANDFATHERED: tuple[str, ...] = (` no longer matches the source regex | **RED** at `:420` — `assert block, "CITATION_GRANDFATHERED is no longer a parseable literal tuple"` fires. **The regex cannot silently match nothing.** |
| Inner `re.findall` matching nothing while `block` matches | Structurally impossible to pass: `annotated` would be `{}` and `assert rel in annotated` fires on the first entry |
| Inflate `"eval/README.md",  # 1` to `# 9999` | **GREEN** — the one residual, filed as V-005 below |

---

## Findings

### V-001: `test_the_controls_cover_every_determining_surface`'s replacement assertion is satisfied by its own source line — round-3 V-007 is not fixed, and the code comment claims the opposite

- **Severity:** error
- **Location:** `tests/test_capability_determination_prose.py:423-432`
- **Issue:** The tautological `SURFACE_IDS == [...]` assertion was replaced with:

  ```python
  source = read(Path(__file__).resolve())
  assert "ALL_SURFACES: Final[list[tuple[str, str]]] = _capability_surfaces()" in source, (
  ```

  The searched literal occurs on exactly two lines of the file: `:316` (the module-level assignment it is meant to guard) and **`:430`, the assert line itself**. `source` is the whole file, so the literal is present unconditionally. Deleting `:316` does not change the outcome.

  This is precisely the round-3 V-002 defect, one turn later, in the same commit that fixed V-002.

  **Measured, not reasoned.** On a `copytree` copy, replacing *only* the module-level assignment with a hardcoded literal that **preserves the roster** (the same six paths, read from disk) — i.e. exactly the drift the assertion's own message names, "the controls now run over a hand-kept list" — leaves `test_the_controls_cover_every_determining_surface` **GREEN**. Reproducing what the fix pass ran — a *shrunken* hardcoded list — goes RED, but the failure is attributable and it is not this assertion:

  ```
  >       assert len(ALL_SURFACES) >= MIN_CAPABILITY_SURFACES, (
  E       AssertionError: only 1 surfaces parametrize the negative controls (floor 6)
  E       assert 1 >= 6
  tests/test_capability_determination_prose.py:421: AssertionError
  ```

  Line 421 is the pre-existing floor assertion. The new assertion at `:430` never fires under any mutation. The round-3 Fix Progress entry for Step 5 is therefore an artifact of a roster-shrinking mutation, not evidence for the assertion under test.

  Compounding it, the comment written directly above the assertion states as fact: "*(Unlike the vacuous form, this reads for a DIFFERENT string than the one it writes.)*" That is factually incorrect — it reads for the string it writes. The round-3 finding V-007 contained the same false parenthetical, so the fix pass inherited it rather than testing it; both need correcting.

  No live drift exists today (`ALL_SURFACES` is still derived), so nothing is broken in canon — but the module now advertises a guarantee it does not provide, which is the exact charge V-007 laid against the line it replaced. The same file already contains the *correct* pattern for a test that reads its own source: `test_this_guard_is_not_skippable` (`:441-446`) asserts **absence** (`f"{banned}(" not in source`) and deliberately writes the banned tokens without their trailing `(` so it cannot satisfy itself.
- **Suggested fix:** Assert the derivation **structurally**, so the assertion's own text cannot satisfy it. Parse the module with `ast` and check the `ALL_SURFACES` assignment's value is a call to `_capability_surfaces`:

  ```python
  import ast
  tree = ast.parse(read(Path(__file__).resolve()))
  assigned = [
      node.value
      for node in tree.body
      if isinstance(node, ast.AnnAssign)
      and isinstance(node.target, ast.Name)
      and node.target.id == "ALL_SURFACES"
  ]
  assert len(assigned) == 1, "ALL_SURFACES is no longer a single module-level assignment"
  assert isinstance(assigned[0], ast.Call) and getattr(assigned[0].func, "id", None) == (
      "_capability_surfaces"
  ), (
      "ALL_SURFACES is no longer derived from the canonical exit table — the controls "
      "now run over a hand-kept list, which is the drift they exist to catch"
  )
  ```

  Delete the false parenthetical in the comment at `:427-428` — it is false — and replace it with a statement of *why* the `ast` form is used ("a substring search would be satisfied by this assertion's own source line — the V-002 defect"). If the `ast` form is judged too heavy, the acceptable lighter alternative is to build the needle at runtime from two fragments so the whole literal never appears in the file — but not a whole-file substring search for a literal the file contains twice.

  **Acceptance evidence is mandatory and must be roster-preserving:** on a copy, replace `:316` with a hardcoded literal listing the *same six* paths and confirm the test goes RED **at the derivation assertion's line number**, not at `:419`. A shrinking mutation proves nothing here.

  Consider also recording the general rule in the module docstring: a test that reads its own file may only assert **absence**, or must scope the read to something other than its own body (as `test_the_failure_message_describes_the_whole_window` now does with `inspect.getsource`).
- **References:** `tests/test_capability_determination_prose.py:316` (the guarded assignment), `:419-421` (the floor assertion that actually produced the fix pass's red), `:441-446` (`test_this_guard_is_not_skippable` — the correct self-reading pattern), `tests/test_state_verb_call_sites.py:182` (the V-002 fix, correctly scoped); round-3 V-002 and V-007; round-3 Fix Progress Step 5
- **Checklist:** CHECK-I17

### V-002: The clause-(c) split is documented as two sub-clauses in three places, and the surrounding section headers still count three clauses and three controls

- **Severity:** inconsistency
- **Location:** `tests/test_capability_determination_prose.py:101`, `:219`, `:365`; secondarily `:71`, `:239`, `:305`
- **Issue:** The fix pass deliberately split clause (c) into **three** sub-clauses (c1/c2/c3) rather than the prescribed two, and correctly documented that in the module docstring (`:23-32`, "This is THREE independent obligations… they are pinned as three independently-required sub-clauses"). Three other statements in the same file were not updated and now contradict it:

  | Line | Text | Reality |
  |---|---|---|
  | `:101` | "Clause (c) is now **two** required sub-clauses so **neither half** can go unsaid." | three sub-clauses, three thirds |
  | `:219` | `"""Assert every clause — (c) counted as its **two** required sub-clauses — is in \`scope\`."""` | three |
  | `:365` | "It is split from 3b because (c)'s **two halves** are independently droppable" | control 3a is one of three, not one of two |

  Two more are stale in the weaker sense of being pre-existing framing that the split invalidated: the Guard 1 banner at `:239` ("every determining surface states **all three clauses**" — `CLAUSES` now has five keys, a/b/c1/c2/c3) and the Guard 2 banner at `:305` ("the **three** negative controls spec 07 §6.2 mandates" — there are now five control functions: 1, 2, 3a, 3b, 3c). The Guard 1 test function was itself renamed from `..._states_all_three_clauses` to `..._states_all_the_clauses` in this pass, so the intent to stop saying "three" was there; the banner and the docstrings were missed.

  This is documentation-only — every assertion behaves correctly and the guard bites in all the ways measured above — but it is the same class of prose defect that rounds 2 and 3 both shipped: a mechanically-applied change whose surrounding narrative was not re-read, invisible to every test.
- **Suggested fix:** In `tests/test_capability_determination_prose.py`:
  - `:101` — "Clause (c) is now **three** required sub-clauses so **no** obligation can go unsaid."
  - `:219` — `"""Assert every clause — (c) counted as its three required sub-clauses — is in \`scope\`."""`
  - `:365` — "It is split from 3b and 3c because (c)'s three obligations are independently droppable: while they shared one fragment list, a surface that stated any one of them satisfied all three."
  - `:239` — "Guard 1 — every determining surface states every clause"
  - `:305` — "Guard 2 — the negative controls spec 07 §6.2 mandates (control 3 split per sub-clause)"
  - `:71` — "The clauses, each satisfied by ANY of its accepted phrasings" (drop "three")

  Do not add a test for this; it is prose. Read the whole `CLAUSES` comment block and both guard banners end-to-end after editing.
- **References:** `tests/test_capability_determination_prose.py:23-32` (the module docstring, which is correct and is the wording to align to), `:102-141` (the five-key `CLAUSES` dict), `:360-434` (controls 3a/3b/3c)
- **Checklist:** CHECK-I19

### V-003: Clause c1 merges the "gated" and "dispatched on the affirmative" obligations into one any-of list — the same defect the split was performed to remove, one level down

- **Severity:** improvement
- **Location:** `tests/test_capability_determination_prose.py:114-125` (`CLAUSES["c1"]`)
- **Issue:** c1's own description is *"an auto-verify directive under a dispatch bar goes through the gate **and is dispatched on the affirmative choice**"* — two obligations. Its fragment list is an any-of over three phrasings, and no phrasing pins the second obligation on any surface. Measured which fragment each surface actually matches, scoped to its capability paragraph:

  | Surface | c1 matched by |
  |---|---|
  | `skills/forge-1-prd/SKILL.md` | `reuse the Standard Verify Gate block for consent` |
  | `skills/forge-2-tech/SKILL.md` | `reuse the Standard Verify Gate block for consent` |
  | `skills/forge-3-specs/SKILL.md` | `reuse the Standard Verify Gate block for consent` |
  | `skills/forge-4-backlog/SKILL.md` | `reuse the Standard Verify Gate block for consent` |
  | `skills/forge-verify/SKILL.md` | `dispatched on the affirmative`, `presented through the gate` |
  | `skills/forge-fix/SKILL.md` | `dispatched on the affirmative` |

  The misreading c1 names — route the directive through the gate, then on the affirmative choice **print the command instead of dispatching** (the `manual-print` path, which the capability rule exists to keep separate) — survives on **all six** surfaces:

  | Mutation | Surface | Result |
  |---|---|---|
  | `*Verify now* (recommended)` → `*Print the verify command for the user to run later* (recommended)` | forge-1-prd | **GREEN — undetected** |
  | `presented through the gate and **dispatched** on the affirmative choice` → `presented through the gate and **printed for the user** on the affirmative choice` | forge-verify | **GREEN — undetected** |

  On `forge-verify` the mutation deletes the `dispatched on the affirmative` fragment outright, and c1 still matches because `presented through the gate` — which carries only the *gate* half — is an accepted alternative in the same any-of list. That is structurally identical to the finding round-3 V-004 made about merged c2/c3: an any-of list spanning two obligations lets either one be dropped.

  This is `improvement`, not `gap`: no live defect exists, all six surfaces currently state both halves, and the three controls all bite on deletion. Note also that the third phrasing is **not** another `"choice 2 omitted"` — see the deviation verdict below; the weakness is the merge, not that fragment.
- **Suggested fix:** Split c1 the way (c) was split, into a gate half and a dispatch half:
  - **c1a (gated):** `("presented through the gate", "reuse the Standard Verify Gate block for consent")`
  - **c1b (dispatched on the affirmative):** `("dispatched on the affirmative",)` — and, for the four authoring stages, whichever short fragment of their existing sentence carries "the affirmative choice runs the verify"; if none does, this is a **canon** amendment, not a test change, and should be raised as such rather than papered over with a mechanism token.

  Before implementing, decide the policy question in "User Decisions Required" below — the authoring stages may genuinely not state the dispatch half today, in which case the honest outcome is a one-clause canon edit on four files plus a regenerate, not a looser fragment. Acceptance evidence: both mutations in the table above must go **RED** on every surface, and control 3a must be split into 3a-i / 3a-ii, each parametrized over all six.
- **References:** `tests/test_capability_determination_prose.py:23-32` (the module docstring's three-obligation statement, which does not decompose c1), `:78-101` (the stated fragment bar and the three fragments already removed for failing it), `:126-140` (c2/c3, the pattern to follow); round-3 V-004
- **Checklist:** CHECK-I17

### V-004: The lookahead pin was made relative to `CALL_SPAN`, which is itself unpinned — widening `CALL_SPAN` silently widens the "measured maximum"

- **Severity:** improvement
- **Location:** `tests/test_state_verb_call_sites.py:64` (`CALL_SPAN`), `:168-172` (the pin)
- **Issue:** Round-3 V-005 prescribed `assert LOOKAHEAD <= 3`. What landed is `assert LOOKAHEAD <= CALL_SPAN`, with `CALL_SPAN = 3` and no assertion of its own anywhere in the module. `CALL_SPAN` has an independent job — it is the flattening span at `:256` (`" ".join(lines[index : index + CALL_SPAN])`) — so a maintainer who adds a fenced `state-*` call with three flag lines has a legitimate, self-contained reason to raise `CALL_SPAN` to 4, and would silently raise the permitted `LOOKAHEAD` with it. The companion `LOOKBEHIND` pin on the line above is absolute (`<= 12`), so the two halves of the same guard now have different strengths.

  The docstring says "Raising either constant means re-measuring canon and re-confirming the buried-mandate hole stays closed, not editing this assertion" — but for `LOOKAHEAD` the assertion no longer enforces that, because raising `CALL_SPAN` *is* editing the bound without touching the assertion.

  No live problem: canon needs `LOOKAHEAD >= 2` (two `state-ecr` sites carry `--epic` one line below), against the shipped 3. The coupling is also *conceptually* right — the window should reach to the end of the call and no further — so this is a strengthening opportunity, not a regression.
- **Suggested fix:** Keep the semantic coupling but add the absolute floor back, either as a second assertion in the same test or by pinning `CALL_SPAN` directly:

  ```python
  assert CALL_SPAN <= 3, (
      f"CALL_SPAN widened to {CALL_SPAN}: it is the LOOKAHEAD bound, so widening it "
      "widens the window past the call's own fence — re-measure canon first"
  )
  assert LOOKAHEAD <= CALL_SPAN, (...)
  ```

  Update the pin docstring at `:156-161` to state that `CALL_SPAN` is load-bearing for the window, not only for flattening. Acceptance evidence: on a copy, set `CALL_SPAN = 8` and `LOOKAHEAD = 8` and confirm `test_the_window_is_no_wider_than_the_measured_maximum` goes **RED** (today it stays green).
- **References:** `tests/test_state_verb_call_sites.py:47-59` (the constants and their measured rationale), `:163-167` (the absolute `LOOKBEHIND` pin, the shape to match), `:256` (`CALL_SPAN`'s other consumer); round-3 V-005
- **Checklist:** CHECK-I17

### V-005: The new grandfather ceiling cannot detect an inflated annotation, which misleads a reviewer in the same direction round-3 V-006 objected to

- **Severity:** improvement
- **Location:** `tests/test_check_spec_purity.py:426-440`
- **Issue:** The ceiling is a genuine, well-built guard — it bites on a lowered annotation, on a missing annotation, and on the source regex ceasing to match (all three measured RED). Its one blind spot is upward: raising an annotation above the live count is always accepted. `"eval/README.md",  # 9999` against a live count of 1 leaves the test **GREEN**, and that entry's ceiling is then permanently vacuous.

  This matters because the annotation's stated purpose (`scripts/check-spec-purity.py:189-196`) is "to let a reviewer see the debt shrink", and round-3 V-006's complaint was that a wrong baseline makes a partial cleanup look like a regression. An inflated baseline makes *outstanding* debt look already-cleaned — the same failure, mirrored. All 29 annotations are exact today, so there is nothing to correct; the gap is that nothing keeps them exact.

  Strict equality is the wrong fix — counts legitimately fall between cleanups, and that is the whole point of a ceiling — so this is `improvement`, deliberately not `gap`.
- **Suggested fix:** Keep the `<=` assertion as the hard gate and add a **non-fatal drift report** so an inflated or stale-high annotation is visible without red-gating a legitimate partial cleanup. The cheapest form that stays inside the existing test: collect `(rel, annotated, live)` for every entry where `live < annotated` and emit them with `warnings.warn` or a `print`, so `pytest -q` output names them. If a hard gate is preferred, bound the slack instead of the value — e.g. `assert annotated[rel] - live <= 5` — and document that clearing the slack means re-deriving the annotation. Either way, extend the maintenance note at `scripts/check-spec-purity.py:191-196` to say that an annotation may only be *lowered* to match a re-derived count, never raised except when the pattern widens.
- **References:** `scripts/check-spec-purity.py:186-196` (the maintenance contract), `:198-227` (the 29 entries, all currently exact), `tests/test_check_spec_purity.py:401-440`; round-3 V-006
- **Checklist:** CHECK-I19

---

## Deviation verdicts

### Deviation 1 — round-3 V-003: the bare `\btech-spec\.md\b` branch was withheld. **SOUND.**

The argument reproduces exactly. Applying the withheld branch to a widened copy of `_SPEC_CITATION_RE` and re-walking all 96 shipped files: **exactly five** files become dirty *only* under that branch, **none** of them currently grandfathered —

| File | bare hits | Representative context |
|---|---|---|
| `references/process-overview.md` | 2 | `**Output:** \`{specsDir}/{feature}/tech-spec.md\`` / `**Input:** PRD.md + tech-spec.md` |
| `skills/forge-2-tech/SKILL.md` | 5 | `Write \`{resolvedFeatureDir}/tech-spec.md\` with this structure:` / `--artifact tech-spec.md` |
| `skills/forge-6-docs/SKILL.md` | 3 | `Never link or reference \`PRD.md\`, \`tech-spec.md\`, or the numbered implementation specs` |
| `skills/forge-guide/SKILL.md` | 1 | `\| 2 \| \`forge-2-tech\` \| \`tech-spec.md\`; detects stack + test/typecheck commands \|` |
| `skills/forge/SKILL.md` | 1 | `✅ forge-2-tech    → tech-spec.md (v{n}, ⚠️ not yet verified)` |

Every one of the twelve hits names the **pipeline artifact** — the file `forge-2-tech` writes, the file `forge-6-docs` forbids linking, the file the navigator prints in a status table. None is a citation of spec content. Landing the branch would have required five new grandfather entries created solely to make brand-new violations pass, which the list's own contract at `scripts/check-spec-purity.py:186-190` explicitly forbids ("Never add a line to make a new violation pass").

**Does the applied branch close what V-003 identified?** Yes, and specifically the *material* miss: V-003's stated case was the internal inconsistency that `tech-spec §3.4` tripped while `tech-spec.md §3.4` — "the repo's own most common spelling", used in the checker's own docstring — did not. That form now trips (`True`, was `False`), and the parametrize case regresses RED when the regex is reverted. V-003 itself graded the comma and "section"-word forms "lower-value (no live instances)"; both remain open (`tech-spec.md, §3.4` → False, `tech-spec.md section 3.4` → False), unchanged from the finding's own assessment, and are not raised here.

**Does it leave a real regression path open?** One narrow one: a shipped file writing "the design is in tech-spec.md" with no coordinate would pass. That path is now documented in place (`scripts/check-spec-purity.py:243-251`) with the asymmetry against form 1 explained and the reason recorded. Given the cost — five false positives and five contract-violating grandfather entries — withholding the branch is the correct call, and should not be reversed.

### Deviation 2 — round-3 V-004: clause (c) split three ways, with a third c1 phrasing. **SOUND.**

Both stated reasons are true by measurement (table in the disposition above): the prescribed c1 list is satisfied by **0 of the 4** authoring stages, and the prescribed merged c2 stays **GREEN on all 4** under the finding's own mutation (a) while the shipped split c2 goes **RED on all 4**. Applying V-004 literally would have red-gated four compliant surfaces *and* failed to catch the mutation the finding was written to catch. Deviating was correct, and the three-way split is strictly stronger than the two-way one the finding prescribed.

**Is `"reuse the Standard Verify Gate block for consent"` a real clause-(c1) statement, or another `"choice 2 omitted"`?** It is a **real statement**, not a mechanism token. Judged by the module's own bar at `:78-79` ("rewriting the sentence into the misreading the clause exists to prevent breaks the match"):

- It is semantically about **routing the directive through a consent gate** — the c1 obligation — whereas `"choice 2 omitted"` describes only how many options that gate renders and carries no obligation at all.
- The natural misreading — drop the gate and proceed — deletes the phrase, and that goes **RED**: replacing the whole gate sentence on `forge-1-prd` with "so proceed straight to the exit" turns controls 3a, 3b and 3c red.
- It is not a free match. It occurs exactly **once** per file, **inside** the capability paragraph, on the four authoring stages only. This is the property that made the round-2 `"Standard Verify Gate first when you may not dispatch unsolicited"` fragment worthless (it lived in the DIRECTIVES boilerplate shared by all nine exit skills), and it does not hold here.
- The one attack that beats it — keeping the substring inside a negating sentence — beats **every** fragment in the module equally, including `"dispatched on the affirmative"`. It is a property of substring guards, not a property of this fragment, so it does not distinguish.

The genuine residual is narrower and is filed as V-003 above: c1 bundles the *gate* and *dispatch* obligations into one any-of list, so the gate-without-dispatch misreading survives on all six surfaces — including `forge-verify`, which has the narrative phrasing. That is a defect in the merge, not in the third phrasing, and it was not created by the deviation.

---

## Checks Executed

| Check | Result | Note |
|---|---|---|
| CHECK-I01 | pass | No files added or removed; every change lands inside existing files. |
| CHECK-I02 | not-applicable | Python/skill-canon repo; no package.json exports map for this feature. |
| CHECK-I03 | pass | `StageExitDirectives` untouched — `scripts/forge-session.py` is not in the diff at all. |
| CHECK-I04 | pass | No error classes added or changed. |
| CHECK-I05 | pass | Backlog unchanged; `forge-5-loop` complete at v1. |
| CHECK-I06 | pass | No pending/in-progress items. |
| CHECK-I07 | pass | |
| CHECK-I08 | pass | Suite green twice; `check-spec-purity.py` imports and executes standalone (exit 0). |
| CHECK-I09 | pass | Rule 7 still wired: `collect_violations` → `main` → `scripts/validate.sh` step 6a. |
| CHECK-I10 | pass | `build-adapters.py --check` exit 0; all six `forge-fix` mirrors carry V-001's sentence exactly once. |
| CHECK-I11 | pass | `ruff check scripts/ eval/` exit 0. |
| CHECK-I12 | pass | `validate.sh` exit 0 twice back-to-back, zero fixture bytecode, clean tree after each. |
| CHECK-I13 | pass | No new TODO/FIXME/placeholder markers in the diff. |
| CHECK-I14 | pass | **Round-3 V-001 resolved** — `forge-fix`'s capability prose is now branch-appropriate and agrees with its own Step 6 gate and Step 7 outcome table. |
| CHECK-I15 | pass | The hardcoded `99e63e6` in `test_the_ratchet_would_have_caught_the_n3_leak` is unchanged and still carries its skip fallback. |
| CHECK-I16 | pass | 1802 passed / 2 skipped, reproduced identically on both runs; +13 over round 3's 1789 = 12 new sub-clause controls (2 × 6 surfaces) + 1 new citation-form case, which matches exactly. |
| CHECK-I17 | **fail** | V-001, V-003, V-004. |
| CHECK-I18 | pass | |
| CHECK-I19 | **fail** | V-002, V-005. |
| CHECK-I20 | pass | `SELF_CONTAINMENT_SURFACES` and `CITATION_GRANDFATHERED` remain documented in place, and the maintenance policy was extended with the ceiling contract. |
| CHECK-I21 | not-applicable | `smokeCommand` is `null` in `forge.config.json`. Advisory unchanged from round 3: `validate.sh` is a reasonable stand-in, but configuring an explicit `smokeCommand` would make "clean" mean "it runs". |
| CHECK-I22 | pass | `check_no_spec_citations` retains its non-test caller (`collect_violations` → `main` → `validate.sh`); `iter_shipped_files` likewise. |
| CHECK-I23 | not-applicable | No universal framework bootstrap entry in this stack. |

Executed 23 of 23 checks. Results: 19 pass, 2 fail, 2 not-applicable.

---

## Fix Execution Plan

### User Decisions Required

**Decision 1 (V-003) — how to pin the "dispatched on the affirmative" obligation on the four authoring stages.** The four authoring stages state the *gate* half of c1 but arguably not the *dispatch* half; `forge-verify` and `forge-fix` state both. Two paths, and this one should not be chosen by the applier:

- **(a) Test-only.** Split c1 into c1a/c1b and accept, as c1b's phrasing on the authoring stages, whichever existing fragment of their sentence best carries "the affirmative choice runs the verify" (e.g. `*Verify now* (recommended)`). Cheapest; risks admitting another shape-token, which is the mistake `"choice 2 omitted"` already made once.
- **(b) Canon + test.** Amend the shared capability sentence in `skills/forge-{1-prd,2-tech,3-specs,4-backlog}/SKILL.md` (and the matching paragraph in `references/shared-conventions.md` § Verify Capability) so it says the affirmative choice **dispatches**, then pin `"dispatched on the affirmative"` as c1b on all six surfaces uniformly. More work and a regenerate; produces one wording across canon and a fragment that genuinely bites everywhere.

Recommendation: **(b)**. Three consecutive rounds have now shown that admitting a per-surface phrasing to avoid a canon edit is how mechanism tokens get into this guard.

Everything else can be applied directly. V-001, V-002, V-004 and V-005 require no policy call.

### Execution Steps

#### Step 1: Make the roster-derivation assertion non-vacuous
- **Files:** `tests/test_capability_determination_prose.py` (`:423-432`)
- **Addresses:** V-001
- **Action:** Replace the whole-file substring search with the `ast`-based check given in V-001's suggested fix (parse `Path(__file__)`, locate the single module-level `ALL_SURFACES` `AnnAssign`, assert its value is a `Call` to `_capability_surfaces`). Delete the parenthetical "(Unlike the vacuous form, this reads for a DIFFERENT string than the one it writes.)" at `:427-428` — it is false — and replace it with a note that a substring search would be satisfied by this assertion's own source line.
- **Acceptance evidence (mandatory, and the mutation must preserve the roster):** on a scratch copy, replace `:316` with a hardcoded literal naming **the same six** paths read from disk, and confirm `test_the_controls_cover_every_determining_surface` goes RED **at the new assertion's line number**. Do not accept a red produced at `:419` — that is the floor assertion, and it is what made the round-3 fix pass believe this was fixed. Also re-run the unmutated copy and confirm green.
- **Depends on:** none — do this first; it is the round's only error.

#### Step 2: Correct the sub-clause counts and the guard banners
- **Files:** `tests/test_capability_determination_prose.py` (`:71`, `:101`, `:219`, `:239`, `:305`, `:365`)
- **Addresses:** V-002
- **Action:** Apply the six edits tabulated in V-002's suggested fix (two → three at `:101`, `:219`, `:365`; drop the stale counts from the `:71` lead-in and the `:239`/`:305` banners). Then read the entire `CLAUSES` comment block (`:71-141`) and both guard banners end-to-end as prose, checking that no sentence still implies a two-way split.
- **Depends on:** Step 1 (same file; avoid conflicting edits)

#### Step 3: Split clause c1 into its gate and dispatch halves
- **Files:** `tests/test_capability_determination_prose.py` (`:114-125`, `:360-372`), plus — **only if Decision 1 resolves to (b)** — `skills/forge-{1-prd,2-tech,3-specs,4-backlog}/SKILL.md` and `references/shared-conventions.md` § Verify Capability, followed by `python3 scripts/build-adapters.py`
- **Addresses:** V-003
- **Action:** Replace `CLAUSES["c1"]` with `c1a` (gate: `"presented through the gate"`, `"reuse the Standard Verify Gate block for consent"`) and `c1b` (dispatch: `"dispatched on the affirmative"`, plus whatever Decision 1 settles for the authoring stages). Split control 3a into two parametrized controls, one per sub-clause, each over all six surfaces, each with its own `pytest.raises(match=r"clause \(c1[ab]\)")`. Update the module docstring's clause-(c) paragraph (`:23-32`) to describe four sub-clauses.
- **Acceptance evidence:** both mutations from V-003's table must go RED on every surface — (i) `*Verify now* (recommended)` → `*Print the verify command for the user to run later* (recommended)` on each authoring stage; (ii) `dispatched on the affirmative choice` → `printed for the user on the affirmative choice` on `forge-verify`. Both are GREEN today.
- **Depends on:** Decision 1; Step 2 (same file)

#### Step 4: Restore an absolute floor under the lookahead pin
- **Files:** `tests/test_state_verb_call_sites.py` (`:61-64`, `:156-172`)
- **Addresses:** V-004
- **Action:** Add `assert CALL_SPAN <= 3` immediately before the existing `assert LOOKAHEAD <= CALL_SPAN`, with a message naming the widening path. Extend the `CALL_SPAN` docstring at `:61-63` to record that it is load-bearing for the Guard 1 window, not only for call flattening, and extend the pin docstring at `:156-161` accordingly.
- **Acceptance evidence:** on a copy, set `CALL_SPAN = 8` and `LOOKAHEAD = 8` and confirm `test_the_window_is_no_wider_than_the_measured_maximum` goes RED. It is green today.
- **Depends on:** none

#### Step 5: Make an inflated grandfather annotation visible
- **Files:** `tests/test_check_spec_purity.py` (`:426-440`), `scripts/check-spec-purity.py` (`:186-196`)
- **Addresses:** V-005
- **Action:** Keep `assert live <= annotated[rel]` as the hard gate. Add a non-fatal drift report for entries where `live < annotated[rel]` (collect them in the loop and `warnings.warn` once with the list), or, if a hard gate is preferred, bound the slack rather than the value. Extend the maintenance comment at `scripts/check-spec-purity.py:191-196` to state that an annotation may only be lowered to a re-derived count, never raised except when `_SPEC_CITATION_RE` widens.
- **Note for the applier:** all 29 annotations are exact right now (independently re-derived at HEAD), so no annotation value needs changing in this step.
- **Depends on:** none

#### Step 6: Regenerate and re-gate
- **Action:** `python3 scripts/build-adapters.py` (only if Step 3 touched canon), then `python3 scripts/build-adapters.py --check` (exit 0), then `bash scripts/validate.sh` **twice back-to-back** (both exit 0, both `All checks passed!`, both `1802 passed` or higher with the delta accounted for control-by-control), then `find tests/fixtures -name '__pycache__' -o -name '*.pyc' | wc -l` after each run (both 0), then `ruff check scripts/ eval/`, `python3 scripts/check-spec-purity.py`, `ruff check tests/ --select F841,F541` (must stay clean) and `ruff check tests/` (must stay at 19), then `git status --porcelain` (must be empty).
- **Verification discipline:** for every guard touched in Steps 1, 3, 4 and 5, the acceptance evidence is a **mutation going red at the intended assertion's line number**, not the suite staying green and not a red anywhere in the test. Round 3's fix pass ran a mutation, saw red, and shipped a vacuous assertion because the red came from a neighbouring line. Record the line number each mutation fails at.
- **Depends on:** Steps 1–5
