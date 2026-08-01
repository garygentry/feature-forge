# Verification Report: stage-exit-coverage (impl, round 5)

Date: 2026-08-01
Pipeline Stage: forge-5-loop (complete, v1)
Mode: impl — served production stage `forge-5-loop`
Method: clean-room `forge-verifier` re-verification in require-clean mode, **five parallel instances** over disjoint CHECK-ID slices, run against the round-4 fix pass recorded in `VERIFY-impl-2026-07-31-round4.md` (commits `5b375f7` + `6a767ab`). Every claim was re-derived with an instrument different from the one the fix pass used. Nothing in the repository was modified by the verification.

Artifacts Reviewed:
- `specs/stage-exit-coverage/.verification/VERIFY-impl-2026-07-31-round4.md` (Findings, Fix Execution Plan, Fix Progress, both disclosed deviations)
- `specs/stage-exit-coverage/.pipeline-state.json` (at `21f1c34`, `5b375f7`, HEAD)
- `git diff 21f1c34..HEAD` (107 files, +260/−135: 96 adapter mirrors, 11 non-adapter)
- `tests/test_capability_determination_prose.py`, `tests/test_state_verb_call_sites.py`, `tests/test_check_spec_purity.py`, `tests/test_stage_exit_protocol.py`, `tests/test_auto_verify.py`, `tests/test_gate_pytest_reachability.py`
- `scripts/check-spec-purity.py`, `scripts/forge-session.py`, `scripts/build-adapters.py`, `scripts/validate.sh`
- `references/shared-conventions.md`, `references/stage-exit-protocol.md`, `references/stacks/python.md`, `references/pipeline-state-schema.json`
- `skills/forge-{0-epic,1-prd,2-tech,3-specs,4-backlog,5-loop,6-docs,verify,fix}/SKILL.md`
- `specs/stage-exit-coverage/{01-architecture-layout.md,00-core-definitions.md,03-verification-state.md,07-testing-strategy.md,backlog.json}`
- all 96 changed adapter mirrors across the six adapter trees

Checks Executed: 23 of 23 (14 pass, 6 fail, 3 not-applicable)

## Summary

- **Total findings: 13** — 2 errors, 2 gaps, 1 inconsistency, 8 improvements.
- **All five round-4 findings are genuinely resolved.** Each was re-measured independently by mutation, and — for the first time in five rounds — **every red landed at the intended assertion's own line number AND on the intended clause id**. The round-4 error (V-001, the third-generation vacuous assertion) is closed: the mandatory roster-**preserving** mutation reds at the derivation assertion while the floor assertion stays silent, which is exactly the acceptance round 4 demanded and round 3 failed to produce.
- **Both of the fix pass's disclosed deviations are SOUND**, independently reproduced, and neither leaves the defect its finding named open. Details in the deviation verdicts below.
- **No guard-quality defect was found this round.** That breaks a four-round streak. The dimension that owns guard quality (CHECK-I17) returned **pass**, with only two residual blind spots filed as `improvement`.
- **The recurring failure mode did recur, in prose.** Both errors are false claims in documentation written or cemented by this pass: `CALL_SPAN`'s stated measurement does not hold against canon (V-001), and the module docstring credits the c1a/c1b split with catching a mutation that is still green (V-002). Mechanical sweeps were clean — zero de-indented docstring continuations, zero merged words, zero column-0 punctuation across all four changed Python files — so this is semantic drift, invisible to all 1808 tests.
- **The gate is confirmed, not taken on report.** Independently re-run twice back-to-back on a healthy disk: exit 0 both times, `All checks passed!` both times, **1808 passed / 2 skipped** both times, zero `tests/fixtures` bytecode after each, clean tree after each.
- **The +6 test delta was re-derived by node-ID set difference, not from totals**: 1804 → 1810 collected, the added set is exactly control 3a-ii × six surfaces, and the removed set is **empty** — nothing was lost or renamed.
- **Pipeline state is correct and byte-reproducible from the canonical writer**, including the owed round-4 `findings-reported` transition the fix pass discovered missing.

### Gate (re-run independently, not taken on report)

| Check | Claimed | Measured | Result |
|---|---|---|---|
| `python3 scripts/build-adapters.py --check` | exit 0 | exit **0** | CONFIRMED |
| `bash scripts/validate.sh` run 1 | exit 0, `All checks passed!` | exit **0**, `All checks passed!` | CONFIRMED |
| `bash scripts/validate.sh` run 2 (back-to-back) | exit 0, `All checks passed!` | exit **0**, `All checks passed!` | CONFIRMED |
| Full suite, run 1 | 1808 passed / 2 skipped | **1808 passed, 2 skipped** (214.41s) | CONFIRMED |
| Full suite, run 2 | 1808 passed / 2 skipped | **1808 passed, 2 skipped** (226.91s) | CONFIRMED |
| Suite delta vs round 4 | +6 = control 3a-ii × 6 surfaces | **+6**, re-derived by node-ID set difference (1804 → 1810 collected); added set exactly the six 3a-ii parametrizations; **removed set empty** | CONFIRMED |
| `find tests/fixtures -name '__pycache__' -o -name '*.pyc' \| wc -l` after each run | 0 | **0**, both runs | CONFIRMED |
| `ruff check scripts/ eval/` | clean | exit **0**, `All checks passed!` | CONFIRMED |
| `python3 scripts/check-spec-purity.py` | exit 0 | exit **0**, `spec-purity: PASS — 0 violations` | CONFIRMED |
| `ruff check tests/` | 19 | **19 errors**; the one in a touched file (`test_check_spec_purity.py:273` E501) confirmed pre-existing by running ruff against a `git show 21f1c34:` copy — same error at `:272`, shifted one line by the added `import warnings` | CONFIRMED |
| `ruff check tests/ --select F841,F541` | clean | `All checks passed!` | CONFIRMED |
| `git status --porcelain` | empty | empty, before and after every run | CONFIRMED |
| Adapter regeneration | clean, all six trees | **96/96 files at exactly `1/1`**, all `M`, no `A`/`D`/`R`; **3 distinct added lines** across all 96; 72/72 `shared-conventions.md` mirrors byte-identical to canon with exactly one hit each; 24/24 authoring-skill mirrors with correct filename convention, intact frontmatter, correct per-adapter `AskUserQuestion` transformation | CONFIRMED |
| All 29 `CITATION_GRANDFATHERED` annotations exact | 29/29 | **29/29**, re-derived with an independent tuple parser + per-file `findall`; `pytest -W always` emits **zero** warnings, which independently corroborates it | CONFIRMED |

### Pipeline state (re-derived)

| Property | Expected | Measured |
|---|---|---|
| `stages.forge-verify-impl.status` | `findings-applied` | `findings-applied` ✓ |
| `.findingsFile` | round-4 report | `.verification/VERIFY-impl-2026-07-31-round4.md` ✓ |
| `.findingsCount` | 5 | 5 ✓ |
| `.commitHash` | full 40-hex of `5b375f7` | `5b375f7eb275fb264f0d4b3a7c948308cc13fb98`; `git rev-parse` agrees, length 40 ✓ |
| `.verifiedStageVersion` | absent | absent ✓ (`findings-applied` deliberately clears it; the writer actively **refuses** `--verified-stage-version` on that status) |
| `.verifiedAt` | absent | absent ✓ |
| everything else | undisturbed | all 6 non-`stages` top-level keys byte-identical to `21f1c34`; `notes` byte-identical (1156 chars); stage-key list and order identical; `forge-verify-impl` is the **only** changed stage entry ✓ |

**The owed-transition story checks out, and was mandatory rather than discretionary.** Reproduced on a scratch copy of the state at `21f1c34`: writing `findings-applied` with round-4 metadata directly is rejected exit **2** with the `does not match the recorded report` error, so the owed `findings-reported` write was forced by the validator. Replaying the stated sequence produces an entry **identical to HEAD's in every key, key order, and value except the `fixedAt` timestamp**, and `--verified-stage-version 1` is the only accepted value (`forge-5-loop.version` is 1). The pre-fix ledger was genuinely malformed — it carried round-3's `findingsFile`/`findingsCount: 8` alongside `commitHash: 8597a818…`, the round-4 *findings* commit, describing a state that never existed. The rewrite heals it.

### Round-4 finding disposition (each independently re-measured)

| Finding | Verdict | Independent evidence |
|---|---|---|
| **V-001** (third-generation vacuous roster assertion) | **RESOLVED** | The mandatory **roster-PRESERVING** mutation — the module-level assignment replaced with a hand-kept list naming the *same six* paths read from disk — goes **RED at the derivation assertion** (`isinstance(<ast.List>, ast.Call)` is False). Run over the whole module that is the **only** failure: **the floor assertion did NOT fire**, because the roster stayed at 6. This is the acceptance round 4 demanded and round 3 failed to produce, and the first time in three rounds this assertion has been shown to bite. It also fails safe on three further probes: a differently-named hand-kept call → RED at the derivation assertion; a wrapped call `sorted(_capability_surfaces())` → RED; a plain `Assign` without the annotation → RED on the binding-count assertion. Two contrived shadowing paths stay green — filed as V-007. |
| **V-002** (stale sub-clause counts and guard banners) | **RESOLVED** | Every *number* was re-counted: no sentence says "two" or "three" sub-clauses anywhere in the module. `:106` reads "four required sub-clauses", `_assert_clauses_in`'s docstring "its four required sub-clauses", the Guard 1 banner "states every clause", the Guard 2 banner "(control 3 split per sub-clause)", the `CLAUSES` lead-in dropped "three", control 3a-i reads "(c)'s four obligations". What survived is the *word* "half" in nine places — filed as V-005. |
| **V-003** (clause c1 merged gate and dispatch) | **RESOLVED**, stronger than claimed | Measured per surface with the raised clause id captured. Dispatch→print misreading: **RED on all six**, every one on `clause (c1b)`. Gate-half deletion: **RED on all six**, every one on `clause (c1a)` — the Fix Progress claimed only three surfaces for the gate half; it is in fact all six. Both mutations also bite the shared rule in `references/shared-conventions.md` § Verify Capability, so the surface `forge-5-loop`/`forge-6-docs` defer to is pinned as well. `pytest.raises(match=r"clause \(c1[ab]\)")` makes the clause id part of the assertion, so a mutation tripping the *wrong* clause would red the control itself — the split is genuinely clause-pinned, not merely "the test fails". |
| **V-004** (lookahead pin relative to an unpinned constant) | **RESOLVED** | `CALL_SPAN = 8` + `LOOKAHEAD = 8` → **RED at `:183`**, the new assertion, exactly as claimed. Each of the three assertions was also shown to bite **independently at its own line**: `LOOKBEHIND = 13` alone → RED at `:178`; `CALL_SPAN = 8` alone → RED at `:183`; `LOOKAHEAD = 4` alone → RED at `:188`. The *number* pinned is wrong against canon — filed as V-001 — but the pin itself does what V-004 asked. |
| **V-005** (grandfather ceiling blind upward) | **RESOLVED** | Inflating `"eval/README.md",  # 1` → `# 9999`: exit **0** (correct — a ceiling is blind upward by design) with the warning **visible in `pytest -q` output** naming the entry. Lowering `"scripts/build-adapters.py",  # 83` → `# 2`: **RED at the hard gate**. Unmutated baseline passes with **no** warning. Nothing swallows it: the repo has no `pytest.ini`/`pyproject.toml`/`setup.cfg`/`tox.ini`, `tests/conftest.py` sets no filter, and `scripts/validate.sh` runs a bare `python3 -m pytest tests -q`, which prints the warnings summary. The warning's *attribution* is wrong — filed as V-009. |

### Deviation verdicts

**Deviation 1 — `c1a` accepts a third phrasing, `"presented through the Step 6 gate"`. SOUND.**
Independently confirmed by two instances. `forge-fix`'s capability paragraph contains `presented through the Step 6 gate` and does **not** contain `presented through the gate` (the longer string is not a superstring of the shorter), so without the addition `c1a` matched `forge-fix` on nothing and the module went red on six tests at baseline. Judged against the module's own bar: it carries the clause's **meaning** plus a disambiguating qualifier naming which of `forge-fix`'s two numbered steps hosts the gate — unlike `"choice 2 omitted"`, which stated the gate's option *count* and carried no obligation at all. Rewriting `forge-fix`'s sentence into the misreading c1a exists to prevent removes it and goes **RED on `clause (c1a)`**. And it is not a free match: the three c1a fragments **partition the six surfaces disjointly** — `presented through the gate` → `forge-verify` only; `presented through the Step 6 gate` → `forge-fix` only; `reuse the Standard Verify Gate block for consent` → the four authoring stages. No fragment matches a surface it was not written for, no surface is unmatched, and each lives inside the capability paragraph.

**Deviation 2 — round-4 V-003's literal acceptance mutation (i) stays GREEN. SOUND; the disclosure is accurate.**
Reproduced by two instances: relabelling `*Verify now* (recommended)` → `*Print the verify command for the user to run later* (recommended)` and changing nothing else leaves all four authoring stages **GREEN**, while the semantically equivalent rewrite goes **RED on `clause (c1b)`** on all six. The fix pass's argument holds and neither instance could refute it: after the amendment the obligation lives in its own clause, so the mutant reads `*Print the verify command…* (recommended) — on which the clean-room forge-verifier is **dispatched on the affirmative choice**, never merely printed…` — the obligation is still stated, adjacently, and the text contradicts itself on one line. The prescribed alternative is also **structurally unavailable**: `forge-verify` and `forge-fix` render no option label in their capability paragraphs at all (`*Verify now*` occurs **0 times** in each), so it cannot become a uniform `c1b` fragment; pinning it would mean an authoring-stage-only shape token, the `"choice 2 omitted"` regression Decision 1 chose option (b) to eliminate. Deviating was correct. The residual is filed as V-008, and the false *description* of this measurement in the module docstring is filed as V-002.

---

## Findings

### V-001: `CALL_SPAN`'s stated measurement is false — canon's longest fenced `state-*` call is 4 lines, not 3, and this pass hard-pinned the wrong number with a new assertion

- **Severity:** error
- **Location:** `tests/test_state_verb_call_sites.py:61-71` (the `CALL_SPAN` constant comment), `:170-176` (the new pin-docstring paragraph), `:183-187` (the new `assert CALL_SPAN <= 3`); secondarily `:264-270` (`_state_verify_call_text`'s docstring)
- **Issue:** The constant comment states as measured fact: *"3 covers the longest call in canon (verb + two flag lines) without reaching into a neighbouring invocation."*

  Re-derived independently by walking all 34 `state-*` call sites across `skills/*/SKILL.md` + `references/shared-conventions.md` and counting the verb line plus its `\`-continued lines: spans are 1 (×4), 2 (×11), 3 (×13) and **4 (×6)**. Six calls in canon are verb + three flag lines:

  | Site | Verb | Span | 4th line, dropped by the flattener |
  |---|---|---|---|
  | `skills/forge-1-prd/SKILL.md:116` | `state-ecr` | 4 | `--specs-dir "{specsDir}"` |
  | `skills/forge-2-tech/SKILL.md:110` | `state-ecr` | 4 | `--specs-dir "{specsDir}"` |
  | `skills/forge-3-specs/SKILL.md:160` | `state-complete` | 4 | `--artifact "<file>" --artifact TRACEABILITY.md --specs-dir "{specsDir}"` |
  | `skills/forge-4-backlog/SKILL.md:158` | `state-complete` | 4 | `--artifact backlog.json --specs-dir "{specsDir}"` |
  | `skills/forge-6-docs/SKILL.md:197` | `state-complete` | 4 | `--artifact "<doc file>" --specs-dir "{specsDir}"` |
  | `skills/forge-verify/SKILL.md:233` | `state-verify` | 4 | `--verified-stage-version {version} --specs-dir "{specsDir}"` |

  So `" ".join(lines[index : index + CALL_SPAN])` silently truncates six invocations, including `forge-verify`'s own `state-verify` fence.

  This pass did not introduce the wrong number, but it **cemented** it and wrote new prose asserting it is measured:
  - `:183` adds `assert CALL_SPAN <= 3` — a hard gate that now prevents a maintainer from correcting `CALL_SPAN` to its true value without editing the assertion, which is precisely what `:166-168` says must not happen ("Raising either constant means re-measuring canon … not editing this assertion").
  - `:65-70` adds "raising it means re-measuring canon, exactly as raising `LOOKBEHIND` does" — endorsing a measurement that does not hold.
  - `:172-175` adds "a maintainer who adds a fenced call with three flag lines has a legitimate, self-contained reason to raise it". Canon **already contains six such calls today**; the paragraph describes as hypothetical something that is present reality.

  A third number for the same quantity sits nine lines below: `_state_verify_call_text`'s docstring says "A fenced call spans a `\`-continued line **pair**" — two. One module states the same measured quantity as 2, 3, and (in reality) 4.

  **No live guard failure today**, which is why five green rounds never surfaced it: every `--status skipped` flag `SKIP_STATUS_RE` searches for sits at offset 0 or 1, inside the 3-line flatten. The defect is that the module's stated basis for its bound is wrong, and a correct future edit is now red-gated by it.

  For contrast, the other two measurements in the same comment block **do** reproduce exactly: max lookbehind distance actually used is **10**, and exactly two sites are not covered by lookbehind (`forge-1-prd:116`, `forge-2-tech:110`), both carrying `--epic` at distance **1** below. `MIN_CALL_SITES = 34` matches a re-derived 34.
- **Suggested fix:** Re-measure, then state the truth. Two coherent options — this needs a decision, because `LOOKAHEAD <= CALL_SPAN` couples them (see User Decisions Required).

  **(a) Correct the number and decouple the window.** Set `CALL_SPAN = 4`; rewrite the comment to name the six four-line sites. Because raising `CALL_SPAN` would otherwise widen `LOOKAHEAD`'s permitted bound to 4 — the exact coupling round-4 V-004 was filed against — replace `assert CALL_SPAN <= 3` with `assert CALL_SPAN <= 4` **and** make the lookahead bound absolute: `assert LOOKAHEAD <= 3`, keeping `assert LOOKAHEAD <= CALL_SPAN` as the semantic coupling. Update `:170-176` to say FOUR assertions pin four independently-measured quantities.

  **(b) Keep `CALL_SPAN = 3` and stop calling it the longest call.** Rewrite `:61-63` to state what it actually is: a deliberate 3-line flattening window that truncates the six four-line calls, justified because every flag the flattener searches for (`--status skipped`) sits at offset 0 or 1 — and record *that* measurement, since it is the real basis. Keep `assert CALL_SPAN <= 3` but change its message to name the real invariant.

  Either way, correct `_state_verify_call_text`'s docstring so the module states one number.

  **Acceptance evidence (mandatory):** re-run the canon walker and confirm the number written into the comment equals the measured maximum span. Under (a), on a scratch copy set `CALL_SPAN = 8` and `LOOKAHEAD = 8` and confirm the pin goes RED **at the new absolute `LOOKAHEAD` assertion's line number**, not only at the `CALL_SPAN` one.
- **References:** `tests/test_state_verb_call_sites.py:47-59` (the two measurements that DO reproduce), `:129` (the `--epic` window), `:276` (`CALL_SPAN`'s flattening consumer), `:291` (`SKIP_STATUS_RE` over the flattened call); round-4 V-004 and its Step 4; `skills/forge-verify/SKILL.md:233`
- **Checklist:** CHECK-I19, CHECK-I20

### V-002: The module docstring credits the c1a/c1b split with catching a mutation that is still GREEN on all six surfaces at HEAD

- **Severity:** error
- **Location:** `tests/test_capability_determination_prose.py:30-36` (module docstring, clause (c))
- **Issue:** The paragraph reads: *"Merging any two of them into one any-of list is not enough, measured twice: inverting … (four surfaces), and **while c1a and c1b shared a list, rewriting the affirmative choice from *Verify now* into *Print the verify command for the user to run later* … left the guard green on all six.**"*

  "while c1a and c1b shared a list" is the past-tense frame the paragraph uses to say *this is what the split fixed*. It did not fix it. Probed in-process at HEAD, applying exactly the named mutation to every surface in the live roster:

  | Surface | mutation applied? | `_assert_capability_prose` |
  |---|---|---|
  | `skills/forge-1-prd/SKILL.md` | yes | **GREEN** |
  | `skills/forge-2-tech/SKILL.md` | yes | **GREEN** |
  | `skills/forge-3-specs/SKILL.md` | yes | **GREEN** |
  | `skills/forge-4-backlog/SKILL.md` | yes | **GREEN** |
  | `skills/forge-verify/SKILL.md` | **no — no-op** | GREEN |
  | `skills/forge-fix/SKILL.md` | **no — no-op** | GREEN |

  Two independent problems:

  1. **False as history.** The literal `*Verify now*` occurs **0 times** in `skills/forge-verify/SKILL.md` and **0 times** in `skills/forge-fix/SKILL.md` (once in each authoring stage). That mutation cannot have been "measured … on all six" — on two of the six it changes nothing. The measurement round-4 V-003 actually performed was *two different mutations on two different surfaces* (the option relabel on `forge-1-prd`; the clause rewrite on `forge-verify`), which this sentence collapses into one.
  2. **False as present tense.** It is still green — after the split, on all six. The fix pass knew this and said so in its own disclosed deviation, reasoning that pinning the option label would re-admit a gate-shape token. That reasoning is sound and both instances confirm it. But the module docstring — the artifact a future maintainer reads — states the opposite of a deviation note buried in a findings document, and a maintainer who trusts it will believe the label is pinned.

  The correct account already exists in the same file: control 3a-ii's docstring describes the mutation as rewriting `forge-verify`'s *clause*, which does go **RED on all six**. The module docstring and the control docstring now tell two different stories about the same measurement, and only the control's is true.
- **Suggested fix:** Rewrite the second half of the "measured twice" sentence to describe the mutation that actually goes red, and to record the deliberate non-pin:

  > "…and while c1a and c1b shared a list, rewriting the *dispatch clause* — `forge-verify`'s "dispatched on the affirmative choice" → "printed for the user" — left the untouched "presented through the gate" matching on all six. Note what is deliberately NOT pinned: relabelling only the gate's *option* (`*Verify now*` → `*Print the verify command …*`) still passes, and must. The obligation now lives in its own clause of the sentence, so relabelling the option makes the prose self-contradictory without unsaying the obligation; pinning the label would re-admit a gate-SHAPE token, which is the `"choice 2 omitted"` mistake this module removed once already."

  Do not add a test; it is prose. After editing, re-read the docstring against control 3a-ii's and confirm the two tell the same story.

  **Ground truth to re-confirm before writing:** (i) `grep -c '\*Verify now\*'` is 0 in `forge-verify` and `forge-fix`; (ii) the option relabel leaves all four authoring stages GREEN; (iii) deleting the `CLAUSES["c1b"]` fragment goes RED on `clause (c1b)` on all six.
- **References:** `tests/test_capability_determination_prose.py:391-413` (control 3a-ii, the correct account), `:133-137` (`CLAUSES["c1b"]`); round-4 V-003 and its Step-3 disclosed deviation
- **Checklist:** CHECK-I19

### V-003: `01-architecture-layout.md` §2 "Complete File Layout" omits every file the verification fix passes added or touched

- **Severity:** gap
- **Location:** `specs/stage-exit-coverage/01-architecture-layout.md`, §2 (lines 47-115)
- **Issue:** §2 is explicitly titled "Complete File Layout" and uses an `N`/`M`/`G` marker vocabulary, going so far as to list `scripts/build-adapters.py` with a `—` marker "unchanged; listed for orientation only". It is no longer complete. Diffing the feature's full commit range (`e89d8fa~1..HEAD`, excluding `adapters/` and `specs/`) against §2's list, seven files are absent:

  | File | Marker it needs | Introduced by |
  |---|---|---|
  | `tests/test_capability_determination_prose.py` | `N` | `493ce46` (round-2 fix pass) |
  | `tests/test_gate_pytest_reachability.py` | `N` | `493ce46` (round-2 fix pass) |
  | `tests/test_state_verb_call_sites.py` | `M` | `cb577d4` (round 3), `5b375f7` (round 4) |
  | `tests/test_check_spec_purity.py` | `M` | `cb577d4` (round 3), `5b375f7` (round 4) |
  | `scripts/check-spec-purity.py` | `M` | `cb577d4` (round 3), `5b375f7` (round 4) |
  | `references/forge-config-schema.json` | `M` | `493ce46` (round-2 fix pass) |
  | `README.md` | `M` | `493ce46` (round-2 fix pass) |

  The pattern is the finding: **every** unlisted file was touched by a verification fix pass and **none** by a loop/backlog commit. Fix passes have been silently widening the feature's file surface since round 2 and no round has folded the result back into the layout, so the drift compounds each round. (`.gitignore` and `forge.config.json` are also modified in the range but by the out-of-band commit `b3110b1`, not by this feature — correctly excluded.)

  The two new test modules are not trivia: they are 46 live, passing assertions and they are also absent from `07-testing-strategy.md`, which mentions neither filename. A reader of the specs cannot discover that either guard exists — including the very module this round spent most of its effort verifying.
- **Suggested fix:** Add the seven rows to §2 in their respective `scripts/`, `references/`, `tests/` blocks (and a top-level entry for `README.md`), each with the marker from the table and a short right-hand description matching the existing style. Then add the two new guard modules to `07-testing-strategy.md` alongside the other named test modules. Do **not** add `.gitignore` or `forge.config.json`.
- **References:** `specs/stage-exit-coverage/07-testing-strategy.md`; commits `493ce46`, `cb577d4`, `5b375f7`
- **Checklist:** CHECK-I01

### V-004: `findings-applied` is spec'd to clear freshness, but the read-side classifier grants `fresh` to any resolved entry whose version matches — and this feature's own state file proves it

- **Severity:** gap
- **Location:** `scripts/forge-session.py:928-946` (`verify_state`); `specs/stage-exit-coverage/03-verification-state.md` §5.1 (lines 304-330)
- **Issue:** Spec §4.2 states the rule unambiguously — step 4: "findings fixes write `findings-applied`, **which clears freshness**"; step 5: "only a subsequent `passed` result restores current `verifiedStageVersion`." The §3.3 status matrix enforces it on the **write** side, and `_write_verify_entry` correctly builds an entry with no such key. The source comment at `:2098` states the intent outright: "`applied` is NOT `reverified`: the writer clears `verifiedStageVersion`".

  But the **read** side never enforces it. `_VERIFY_RESOLVED` includes `findings-applied`, so such an entry falls through to a freshness inference based purely on key presence:

  ```python
  verified_version = entry.get("verifiedStageVersion")
  stage_version = _stage_version(state, stage)
  if (isinstance(verified_version, int) and stage_version is not None
          and verified_version == stage_version):
      return stage, "fresh"
  return stage, "stale"
  ```

  The invariant is upheld only by the writer's discipline, and any state file *not* written by the current writer defeats it. That is not hypothetical — **REQ-DEBT-06 promises exactly that case**: "Load legacy state without migration". And this feature's own `.pipeline-state.json` contains two such entries, written before items 005/006 landed the new writer: `forge-verify-specs` is `findings-applied` carrying `verifiedStageVersion: 4` against `forge-3-specs.version = 4`, and `forge-verify-backlog` is `findings-applied` carrying `verifiedStageVersion: 3` against `forge-4-backlog.version = 3`.

  Demonstrated directly against the live file, truncated so specs is the latest completed production stage:

  ```
  legacy entry present   -> ('forge-3-specs', 'fresh')
  spec-conformant shape  -> ('forge-3-specs', 'stale')
  ```

  `fresh` makes `pending_verify` return `None`, so the navigator's "verify before continuing" gate does not fire and the verification debt for a fixed-but-never-re-verified stage silently disappears — the precise failure mode this feature exists to close. It is currently masked only because `forge-verify-impl` is the latest entry and correctly reads `stale`.

  §5.1's ordered classifier rule list is the corresponding spec gap: it enumerates six rules, all about `auto-verify-pending`, and never restates the §4.2 freshness-clearing rule as a read-side obligation. The implementation matches §5.1 exactly; §5.1 is what is incomplete.
- **Suggested fix:** Three coordinated edits.
  1. `03-verification-state.md` §5.1 — add a rule before the generic resolved/version comparison: "a `findings-applied` entry never classifies `fresh`, regardless of any `verifiedStageVersion` it carries — fixes landed but were not re-verified (§4.2 step 4), and a legacy entry written before the current writer may still carry the key (REQ-DEBT-06)." Cite REQ-DEBT-05/06.
  2. `scripts/forge-session.py` `verify_state` — guard the freshness branch: `if status == "findings-applied": return stage, "stale"` immediately before the version comparison, with a comment naming §4.2 step 4 and the legacy-state reason. Mirror the guard in `_verify_state_for` and in `scripts/epic-manifest.py`'s status reader (§5.1 requires identical labels across all three; §5.2 requires manifest parity, so a partial fix creates the drift `test_stage_constants_parity.py` exists to catch).
  3. Add a regression test constructing a `findings-applied` entry **with** a matching `verifiedStageVersion`, asserting `verify_state` returns `stale` and `pending_verify` returns the stage. The docstring must state that the shape is unreachable through the current writer and arrives only via legacy state (REQ-DEBT-06), so it cannot later be "simplified" into a writer-behaviour assertion that passes vacuously. Verify it fails against the pre-fix code before accepting it.
- **References:** `03-verification-state.md` §3.3 (line 229), §4.2 (lines 287-296), §6.2 (REQ-DEBT-06); `scripts/forge-session.py:263, :2098, :4986-4993`; `specs/stage-exit-coverage/.pipeline-state.json`
- **Checklist:** CHECK-I05

### V-005: A four-way split is still narrated as "halves" in nine places, one sentence after the docstring declares FOUR obligations

- **Severity:** inconsistency
- **Location:** `tests/test_capability_determination_prose.py:26`, `:28`, `:29`, `:127`, `:372`, `:395`, `:418`, `:420`, `:439`
- **Issue:** Round-4 V-002 required removing the stale two-way framing, and Steps 2 + 3 correctly re-counted every *number*. But the word carrying the two-way framing survived. The docstring now reads:

  > "This is **FOUR** independent obligations … (c1a) the gate **half** …; (c1b) the dispatch **half** …; (c2) the no-skip **half** …; (c3) the no-advance **half** …"

  Four halves, declared four obligations, in one sentence. `:127` likewise says "The four authoring stages state the gate **half**", and the four control docstrings each announce themselves as dropping a "half", with `:420` adding "This is the **half** that had NO pin of its own".

  The applier already established the correct replacement term when fixing the site the finding named literally: `:377` reads "(c)'s **four obligations** are independently droppable" where it previously read "(c)'s two halves". The other nine instances were not swept. Documentation-only — every assertion behaves correctly — but it is the same partial-sweep pattern the last three rounds shipped: the named line was fixed, the synonym around it was not.
- **Suggested fix:** Replace "half" with "obligation" at `:26`, `:28`, `:29`, `:127`, `:372`, `:395`, `:418`, `:420`, `:439`. Keep `tests/test_state_verb_call_sites.py:176`'s "both halves of the window" — that one is genuinely two-sided (lookbehind/lookahead) and is correct. After editing, read the module docstring, the whole `CLAUSES` comment block, both guard banners and all six control docstrings end-to-end.
- **References:** `tests/test_capability_determination_prose.py:377` (the correct term, already applied at the one site round-4 V-002 named), `:108-153` (the six-key `CLAUSES` dict); round-4 V-002
- **Checklist:** CHECK-I19

### V-006: The amended canon sentence says "on which … on the affirmative choice", which is circular, and the `shared-conventions.md` variant additionally loses the referent of "the latter"

- **Severity:** improvement
- **Location:** `skills/forge-1-prd/SKILL.md:165`, `skills/forge-2-tech/SKILL.md:226`, `skills/forge-3-specs/SKILL.md:169`, `skills/forge-4-backlog/SKILL.md:178`, `references/shared-conventions.md:263` (plus the 24 regenerated adapter mirrors)
- **Issue:** *(Flagged independently by the integration and code-quality dimensions; merged here.)* The Step-3 amendment reads, on the four authoring stages:

  > "…leaving exactly two choices: *Verify now* (recommended) — **on which** the clean-room `forge-verifier` is **dispatched on the affirmative choice**, never merely printed for the user to run later — and *Skip for now*, the latter persisted as an explicit `skipped` before any advancing block."

  "on which" already denotes *Verify now*, which **is** the affirmative choice, so the clause literally states "on the affirmative choice, the verifier is dispatched on the affirmative choice." The redundancy is an artifact of bending the sentence around the guard fragment `"dispatched on the affirmative"` rather than stating the obligation in its own right.

  `references/shared-conventions.md:263` compounds it with two divergences from the four skills the same pass was aligning:
  1. the aside is **comma**-delimited, not em-dash delimited — so a sentence promising "exactly two choices" renders as a four-segment comma series, and **"the latter"** must reach back past two intervening clauses to bind to *Skip for now*;
  2. it says "**rather than** printed for the user to run later" where the four skills say "**never merely** printed for the user to run later" — a gratuitous wording split in the one sentence the pass regenerated 96 files to keep uniform.

  Documentation-only and invisible to every test: the load-bearing fragments are intact and both clauses were measured matching in-paragraph on all six surfaces, with the semantic downgrade going RED on all six.
- **Suggested fix:** Split the run-on into two sentences on all five canon surfaces, keeping `dispatched on the affirmative` adjacent and intact so `c1b` is unaffected:

  > "…so reuse the Standard Verify Gate block for consent with **choice 2 omitted**, leaving exactly two choices: *Verify now* (recommended) and *Skip for now*. The clean-room `forge-verifier` is **dispatched on the affirmative choice**, never merely printed for the user to run later; *Skip for now* is persisted as an explicit `skipped` before any advancing block."

  Apply the same split to `references/shared-conventions.md` and adopt the skills' wording verbatim so the five surfaces agree. Then `python3 scripts/build-adapters.py` and `--check`.

  Safe against every guard: no test pins the literal `"*Verify now* (recommended) and *Skip for now*"` sequence, and the replacement stays inside one blank-line-delimited paragraph, so `_capability_paragraph()` scoping is unchanged.

  **Acceptance evidence:** re-run the six-surface clause probe and confirm `c1a` and `c1b` still match **in-paragraph** on all six; re-run the dispatch→print mutation and confirm **RED at `clause (c1b)`** on all six; `build-adapters.py --check` exit 0; all 72 `adapters/**/shared-conventions.md` mirrors byte-identical to canon, exactly once.
- **References:** `references/stage-exit-protocol.md:301-316` (the full rule, whose choice 1 states the obligation cleanly); `tests/test_capability_determination_prose.py:117-137` (`CLAUSES["c1a"]`/`["c1b"]` — the fragments that must survive verbatim); `specs/stage-exit-coverage/07-testing-strategy.md` §6.2; round-4 V-003 Decision 1 option (b)
- **Checklist:** CHECK-I09, CHECK-I19

### V-007: The `ast` derivation guard is blind to two module-level shadowing paths — a later re-bind of `ALL_SURFACES`, and an alias of `_capability_surfaces`

- **Severity:** improvement
- **Location:** `tests/test_capability_determination_prose.py:474-492` (`test_the_controls_cover_every_determining_surface`)
- **Issue:** The replacement assertion is a genuine, biting structural check — the mandatory roster-preserving mutation reds at the assertion's own line, and the natural drift path is caught. Round 4 asked whether the `ast` form has a blind spot of its own; it has two, both measured GREEN on copies with bytecode caching disabled:

  | Probe | Result |
  |---|---|
  | Hand-kept `ast.List` of the same six paths (**the drift the guard exists to catch**) | **RED** at the derivation assertion ✓ |
  | Call to a differently-named hand-kept function | **RED** ✓ |
  | Wrapped call: `sorted(_capability_surfaces())` | **RED** ✓ (fails safe) |
  | Demote `AnnAssign` → plain `Assign`, still derived | **RED** at the binding-count assertion ✓ (fails safe) |
  | **Keep the derived `AnnAssign` as a decoy, then re-bind:** `ALL_SURFACES = [<six hand-kept tuples>]` above `SURFACE_IDS` | **GREEN — 43 passed** |
  | **Alias the derivation:** `_capability_surfaces = _hand_kept_surfaces` above the unchanged assignment | **GREEN — 43 passed** |

  In both green cases the controls really do run over a hand-kept list: `SURFACE_IDS` and every `parametrize` take the shadowed value, so the guard's stated property is false while the module passes. The check walks `tree.body` for `ast.AnnAssign` only, so a second `ast.Assign` binding of the same name is invisible; and it compares `func.id` textually, so rebinding that *name* is invisible too. Neither is an accident shape — both require leaving a decoy behind — and there is no live drift, which is why this is `improvement` and not `gap`. Worth closing anyway: this assertion has been rewritten three times across three rounds, and round 4 explicitly asked for these two paths to be probed.
- **Suggested fix:** Assert over **every** module-level binding of the name, and pin the callee as a `FunctionDef`:

  ```python
  bindings = [
      node
      for node in tree.body
      if (isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
          and node.target.id == "ALL_SURFACES")
      or (isinstance(node, ast.Assign)
          and any(isinstance(t, ast.Name) and t.id == "ALL_SURFACES" for t in node.targets))
  ]
  assert len(bindings) == 1, (
      f"ALL_SURFACES is bound {len(bindings)} times at module level — a later "
      "re-binding would shadow the derived roster while leaving this check green"
  )
  # ... existing isinstance(value, ast.Call) / func.id check, over bindings[0].value ...
  assert [n for n in tree.body
          if isinstance(n, ast.FunctionDef) and n.name == "_capability_surfaces"], \
      "_capability_surfaces is no longer a function definition — the name may be aliased"
  assert not [n for n in tree.body
              if isinstance(n, ast.Assign)
              and any(isinstance(t, ast.Name) and t.id == "_capability_surfaces"
                      for t in n.targets)], \
      "_capability_surfaces is re-bound at module level — the derivation name is aliased"
  ```

  Extend the comment with one sentence recording *why* the check counts bindings: a single-node check is satisfied by a decoy.

  **Acceptance evidence (mandatory, with `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, and `__pycache__` purged between runs — see the measurement-hazard note):** each of the two green probes must go RED **at the new assertion's own line number**, not at the floor and not at the existing derivation assertion. The four already-red probes must stay red at the derivation assertion. Unmutated copy: 43 passed.
- **References:** `tests/test_capability_determination_prose.py:328` (the guarded assignment), `:329` (`SURFACE_IDS`, which takes the shadowed value), `:457-460` (the floor assertion that must *not* be the source of the red), `:500-505` (`test_this_guard_is_not_skippable`, the absence-asserting pattern); round-4 V-001, round-3 V-007, round-3 V-002
- **Checklist:** CHECK-I17

### V-008: The gate's affirmative-choice **label** is pinned nowhere in the suite, so it can rot into a self-contradiction while every guard stays green

- **Severity:** improvement
- **Location:** `skills/forge-{1-prd,2-tech,3-specs,4-backlog}/SKILL.md` capability paragraph; `references/shared-conventions.md` § Verify Capability; guarded (or not) by `tests/test_capability_determination_prose.py:133-137`
- **Issue:** **The round-4 deviation this arises from is SOUND and must not be reversed** — pinning `*Verify now*` into `CLAUSES` is the *wrong* fix and would re-admit the `"choice 2 omitted"` class of shape token. What remains is a narrow, measured hole elsewhere.

  Relabelling `*Verify now* (recommended)` and changing nothing else leaves all four authoring stages GREEN. That is correct *for `c1b`* — but the option label is the operative instruction for what the agent renders and does, and it is asserted **nowhere in `tests/`**: the only occurrence of `Verify now` under `tests/` is prose inside a docstring, and `tests/test_auto_verify.py` pins the *directives payload* (`verifyGate`, `primaryCommand`, `deferredCommand`) rather than the gate's rendered option text.

  So a label-only rot ships canon that says "choose *Print the command*" immediately followed by "the verifier is **dispatched on the affirmative choice**, never merely printed" — an adjacent self-contradiction, invisible to 1808 tests. Practical risk is low (option labels are not edited in isolation from the clause that glosses them, and the contradiction is on the same line), hence `improvement` and deliberately not `gap`.
- **Suggested fix:** Two acceptable outcomes; **do not touch `CLAUSES["c1b"]`** under either.
  - **(a) Record and close.** Add two sentences to the module docstring's clause-(c) paragraph stating that the affirmative option *label* is deliberately unpinned — because two of the six surfaces render no option label at all, so any label fragment would be an authoring-stage-only shape token — and that the obligation is pinned by its own sentence clause instead. This converts a silent hole into a recorded decision, the device the module already uses for `SURFACES_WITHOUT_PROSE`.
  - **(b) Pin it separately, scoped to the four authoring stages.** Add a *new* test (not a `CLAUSES` entry) parametrized over the four authoring surfaces asserting the two-choice gate description names an affirmative choice whose label is a verify action. Keep it out of `CLAUSES` so the six-surface uniformity of the clause set is preserved.

  Under (b), **acceptance evidence:** the relabel mutation must go RED on each of the four authoring stages at the new test's own line, the six existing `c1a`/`c1b` controls must remain green and unchanged, and the suite total must move by exactly +4 with a node-ID diff showing four additions and zero removals.

  Note that V-002's fix already writes the substance of option (a) into the docstring; if V-002 is applied as prescribed, (a) is largely satisfied and this reduces to confirming the wording covers it.
- **References:** `tests/test_capability_determination_prose.py:34` (the label named only in prose), `:133-137` (`CLAUSES["c1b"]` — do not modify), `:164-170` (`SURFACES_WITHOUT_PROSE`, the precedent for recording a deliberate hole), `tests/test_auto_verify.py:855-905`; round-4 V-003 Decision 1 and Deviation 2
- **Checklist:** CHECK-I17

### V-009: The grandfather drift warning is attributed to pytest's own internals, not to the test that owns the maintenance action

- **Severity:** improvement
- **Location:** `tests/test_check_spec_purity.py:458-463` (`warnings.warn(..., stacklevel=2)`)
- **Issue:** Round-4 V-005's stated goal was a non-fatal drift report "so `pytest -q` output names them". The applier added `stacklevel=2`, which was **not** prescribed by the fix plan. `stacklevel=2` is the convention for a *helper* warning on behalf of its caller; this `warn` is issued directly in a test-function body, whose caller is pytest.

  **Measured, not reasoned**, with a two-case throwaway module outside the repo:

  ```
  test_w.py::test_stacklevel_two
    /home/gary/.local/lib/python3.10/site-packages/_pytest/python.py:166: UserWarning: STALE_HIGH_DEMO: annotated 9999, live 1
      result = testfunction(**testargs)

  test_w.py::test_stacklevel_one
    /tmp/.../test_w.py:7: UserWarning: STACKLEVEL_ONE_DEMO
      warnings.warn("STACKLEVEL_ONE_DEMO", stacklevel=1)
  ```

  So when an annotation goes stale-high, `validate.sh` prints the warning attributed to `_pytest/python.py:166`, echoing pytest's own source line. A maintainer sees what looks like a pytest-internal warning and gets no pointer to `tests/test_check_spec_purity.py` or to `CITATION_GRANDFATHERED`. The warning *message* is fine and still lists each entry, so this is `improvement` — the maintainer can still act. No live drift exists today (29/29 exact, zero warnings at HEAD), so nothing is currently mis-reported; the defect is that the reporting channel misfires the first time it is used.
- **Suggested fix:** Delete `stacklevel=2,`, leaving the default. Add a one-line comment: `# stacklevel left at the default: this warns about ITS OWN module's data, not on behalf of a caller, so the report must point here.`

  **Acceptance evidence (mandatory):** on a scratch copy, inflate `"eval/README.md",  # 1` to `# 9999`, run `python3 -m pytest tests/test_check_spec_purity.py -q`, and confirm (a) the test still **passes** and (b) the warnings-summary location line begins with `tests/test_check_spec_purity.py:<line of the warn call>` and echoes the `warnings.warn(` source line — **not** `_pytest/python.py`. Record the reported path, not merely "a warning appeared". Then confirm the unmutated copy emits no warning.
- **References:** round-4 V-005 and Fix Progress Step 5; `scripts/check-spec-purity.py:196-202` (the contract promising "the same test WARNS whenever an annotation reads high"); `scripts/validate.sh:211`
- **Checklist:** CHECK-I14

### V-010: The new comment cites `V-002` unqualified next to a round-qualified `round-4 V-001`, in a file where `V-001` already means a different finding

- **Severity:** improvement
- **Location:** `tests/test_capability_determination_prose.py:470-471`
- **Issue:** The comment replacing round-4 V-001's false parenthetical reads: "That is the vacuity **V-002** named, and the substring form of this very assertion shipped with it (**round-4 V-001**)." The second ID is round-qualified; the first is not, and it means *round-3* V-002. In the same file, `:106` says "(V-001)" meaning *round-3* V-001. So `V-001` now denotes two different findings in one module, disambiguated in one place and not the other.

  Unqualified IDs are a pre-existing repo-wide convention, so this is not a regression — but this specific comment mixes both conventions in one sentence, which is worse than either alone, and it is newly written this round.
- **Suggested fix:** Qualify both IDs: "That is the vacuity **round-3 V-002** named, and the substring form of this very assertion shipped with it (round-4 V-001)." Optionally qualify `:106`'s "(V-001)" as "(round-3 V-001)". Do not attempt a repo-wide sweep — out of scope.
- **References:** `tests/test_capability_determination_prose.py:106`; `scripts/check-spec-purity.py:194`
- **Checklist:** CHECK-I19

### V-011: The standing-invariant note in `.pipeline-state.json` gives a backlog item count two short of the live artifact

- **Severity:** improvement
- **Location:** `specs/stage-exit-coverage/.pipeline-state.json`, `notes` field, opening sentence
- **Issue:** The note opens "Specs v4, backlog v3 (30 items, 001-030)." The live `backlog.json` holds **32** items, 001-032: `031` and `032` were appended by the loop as fix items inside the `forge-5-loop` run (completed `13:30:13Z` and `13:37:41Z`, before the stage's `13:38:05Z`). `backlog.json.bak` also holds 32, so this is not a partial write. `forge-4-backlog.version` remained `3`, so the count now describes v3 inaccurately rather than describing a superseded version.

  This matters because the note is *addressed to a future regenerator* — its own text says the two traps are "worth re-checking if items are ever regenerated". A regenerator trusting "001-030" would silently drop items 031 and 032, which are the two loop-discovered defect fixes and therefore the least likely to be re-derived from the specs. Documentation drift, not a functional defect: nothing reads the count programmatically and both items are `done`.
- **Suggested fix:** Update the opening sentence to "Specs v4, backlog v3 (32 items, 001-032; 031-032 appended by forge-5-loop as fix items after backlog verification)." The notes string has **overwrite** semantics and must be rewritten via `state-note`, re-emitting the entire existing note with only that clause changed — never a hand-edit of `.pipeline-state.json`. On exit 2, surface the `Error:` line verbatim and do not claim persistence.
- **References:** `specs/stage-exit-coverage/backlog.json` (items 031, 032); commits `1bb8950`, `8d37aed`; `references/shared-conventions.md` (state-note overwrite semantics)
- **Checklist:** CHECK-I05, CHECK-I06

### V-012: `_verify_state_for` has no non-test caller — the stage-exit route inlines its logic instead, so the tests that pin routing labels through it do not exercise the shipped path

- **Severity:** improvement
- **Location:** `scripts/forge-session.py:2215-2231` (definition); `:3515-3530` (the runtime route doing the same work inline)
- **Issue:** `_verify_state_for(state, stage)` is specified as a runtime participant: `03-verification-state.md:326` states *"`_verify_state_for` applies identical labels for stage-exit routing"*, `02-stage-exit-routing.md:534` lists it under "Private helpers", and `07-testing-strategy.md:463` names it in the coverage set. But the stage-exit route does not call it — at `:3515-3530` it performs the same two steps inline (the `_EXIT_VERIFY_TOKEN` lookup, then `_classify_verify_entry`), plus the epic branch.

  **Measured with two independent instruments.** (a) `grep` finds `_verify_state_for` in `scripts/forge-session.py` at only `:2179` (a docstring mention) and `:2215` (its own `def`); every other hit is a test, a spec, or a generated adapter copy. (b) An AST sweep of all **107** top-level functions against an executable-only corpus (14 files under `scripts/`, `hooks/`, `installer/`, `eval/`, `references/`) returned exactly **one** function with no reference outside its own definition: `_verify_state_for`. The other seven candidates from a looser first pass are all dispatched by reference from `main`.

  **Why `improvement`, not `gap`:** no live defect. Both paths funnel into the single `_classify_verify_entry`, whose docstring states the intent — "Both callers must apply identical rules, so there is one implementation rather than two that can drift" — so labels agree today. What is duplicated is the thin outer layer. The consequence is a soft one of exactly the family this feature has spent five rounds fighting: `tests/test_auto_verify.py:370-486` pins stage-exit routing labels by calling `fs._verify_state_for(...)`, so those assertions can stay green while the code the CLI actually executes diverges. A signature-pinning test makes the wrapper look load-bearing when nothing at runtime depends on it.

  **Pre-existing, not introduced by this round:** `scripts/forge-session.py` does not appear in `git diff 21f1c34..HEAD` at all; `git log -S'_verify_state_for('` shows the last change at `1930875`. Prior rounds recorded CHECK-I22 as `pass` on the strength of the `check-spec-purity.py` chain alone and did not sweep `forge-session.py`. **Note the interaction with V-004:** V-004's fix explicitly requires mirroring the `findings-applied` guard into `_verify_state_for`, which is only meaningful if it is on the runtime path — so these two should be sequenced together.
- **Suggested fix:** Collapse the duplication in the direction the specs already describe: give `_verify_state_for` an optional epic-context parameter (or a sibling taking the `(entry, current)` pair the epic branch resolves), then replace `:3515-3530` so the non-epic branch reads `verify_label = _verify_state_for(state, route_stage)` and the epic branch keeps its direct `_classify_verify_entry` call with the manifest revision.

  If that reshaping is judged too invasive, the honest alternative is to stop describing it as runtime: delete `_verify_state_for`, re-point `tests/test_auto_verify.py:370-486` at the CLI subprocess boundary, and drop the three spec sentences. What is not acceptable is leaving a spec-declared routing helper the router does not call.

  **Acceptance evidence (call-path, not suite-green):** re-run the executable-corpus AST orphan sweep and confirm `_verify_state_for` is absent from the orphan set (or from the module). Then, on a scratch copy, mutate its body to return a constant wrong label and confirm at least one **CLI-subprocess** test in `tests/test_stage_exit.py` goes RED, recording the line number. A red confined to `tests/test_auto_verify.py` means the helper is still not on the runtime path and the fix is incomplete.
- **References:** `scripts/forge-session.py:2057` (`_EXIT_VERIFY_TOKEN`), `:2176-2212` (`_classify_verify_entry`), `:3507-3532`; `tests/test_auto_verify.py:370-486`; `03-verification-state.md:326`, `02-stage-exit-routing.md:534`, `07-testing-strategy.md:463`; `references/stacks/python.md:119-122`
- **Checklist:** CHECK-I22

### V-013: No `smokeCommand` is configured — advisory re-affirmed, with a narrowed rationale

- **Severity:** improvement
- **Location:** `forge.config.json`, `"smokeCommand": null`
- **Issue:** CHECK-I21 requires an advisory finding whenever `smokeCommand` is `null`. Re-assessing whether `not-applicable` remains right — **it does**, and the standing advisory should be *narrowed* rather than repeated verbatim, because as previously worded it overstates what a smoke command would buy here:

  1. **The recurring defect class is invisible to any smoke command.** All five rounds' defects were vacuous guards and stale prose. A booting-and-serving smoke test cannot detect an assertion that passes for the wrong reason. Presenting "configure a `smokeCommand`" as a remedy for the round-over-round failures would be misleading.
  2. **The "does it actually run" risk is already covered at the real boundary.** `tests/test_stage_exit.py` drives the CLI as a genuine subprocess at seven call sites, and `validate.sh` runs that suite. The shipped entrypoint was independently booted end-to-end at HEAD on both routes: a production exit returned `terminalOwnedBy: "self"` with non-null `nextSteps` and a `sentinel`; a nested branch exit returned `terminalOwnedBy: "outer"` with `nextSteps: null`; and the ownership guard failed closed as specified (exit 2).
  3. What a configured `smokeCommand` would still add is small but real: a *named, standalone* "it boots" gate not dependent on the pytest step, which `validate.sh` soft-skips when pytest is absent — the one path where a broken CLI could pass `validate.sh`.
- **Suggested fix:** Optional, non-blocking, a user decision. If configured, point it at the real entrypoint — e.g. a one-line `scripts/forge-session.py stage-exit --json` against a throwaway `--specs-dir` fixture, asserting exit 0 and a `sentinel` key. Do **not** set it to `bash scripts/validate.sh`: that is already `testCommand`, and duplicating it would make CHECK-I21 report a pass it did not earn. If left `null`, prefer this narrowed advisory so the entry is not misread as a remedy for the vacuous-guard failures.
- **References:** `forge.config.json`; `scripts/validate.sh:150-155` (step 6a, hard gate), `:210-219` (pytest step, soft-skippable); `tests/test_stage_exit.py:64`
- **Checklist:** CHECK-I21

---

## Measurement hazards encountered (read before running any acceptance mutation)

Two hazards produced false readings during this verification and will produce them again.

1. **Stale `.pyc` contamination.** The `CALL_SPAN`/`LOOKAHEAD` mutations are same-size constant edits (`3`→`8`) written within one second, so CPython's `(mtime, size)` pyc validation reuses a stale mutant's bytecode. One instance's *unmutated baseline* "failed" with `LOOKBEHIND widened to 20` before this was caught. **Run every mutation with `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, and `__pycache__` purged between runs.** A mutation campaign on this suite that edits constants in place without this is measuring the previous mutation.

2. **Disk exhaustion reads exactly like a regression.** The root filesystem hit 100% mid-verification. `validate.sh` then exited 1 with `1 failed, 1756 passed, 53 errors` — all 53 being `OSError: could not create numbered dir … in /tmp/pytest-of-gary`, and the single failure an `Errno 28 No space left on device`. This suite needs roughly **1 GB free** for `tmp_path` fixtures. **Check `df -h /` before gating.** Also prefer hardlink copies (`cp -al`, unlinking any file before rewriting it so no shared inode is truncated) over `copytree` — the repo is 592 MB and full copies are what exhausted the disk.

---

## Checks Executed

| Check | Result | Note |
|---|---|---|
| CHECK-I01 | **fail** | V-003. All 38 paths named in `01-architecture-layout.md` §2 exist, but §2 declares itself the *Complete* File Layout and omits 7 files this feature creates/modifies. |
| CHECK-I02 | not-applicable | No `package.json` anywhere in the repo; Python + markdown plugin, no exports map. |
| CHECK-I03 | pass | Every `Literal` alias, `Final` constant, `TypedDict` and quoted callable signature in `00-core-definitions.md` is present in `scripts/forge-session.py` with matching key sets and parameter lists. Round 4 did not touch `forge-session.py` at all, so nothing here could have regressed. |
| CHECK-I04 | pass | `UsageError` is the sole spec'd error class (`:681`); its handler at `:5850-5852` prints `Error: {exc}` to stderr and returns 2, matching the exit-2 contract. |
| CHECK-I05 | **fail** | V-004, V-011. 32/32 backlog items carry ACs that hold at HEAD, and both standing traps were re-confirmed empirically (item 024's guard derives `EXIT_STAGES` from canon by regex + literal-eval, not a hardcode; every `state-verify` fence keeps its `--epic` sentence inside the 12/3 window). |
| CHECK-I06 | pass | `Counter({'done': 32})` — no `pending` or `in-progress` items; every item carries a `completedAt`. |
| CHECK-I07 | pass | Every round-4 acceptance claim is re-derivable by reading/executing the code, and each was re-derived independently. Backlog ACs touching the amended prose (items 010, 011, 017, 023) all remain satisfied; none was invalidated by the amendment. |
| CHECK-I08 | pass | `import ast` and `import warnings` are stdlib and both used. All three changed test modules import and run: 87 passed. `check-spec-purity.py` imports and executes standalone, exit 0. No import path added, removed, or reordered anywhere in the diff. |
| CHECK-I09 | **fail** | V-006. Otherwise clean: `check_no_spec_citations` → `collect_violations` → `main` → `validate.sh` untouched; the amended summaries do not out-run the full rule they defer to; specs `04` §3.3 and `07` §6.2 already required the amended obligation, so the amendment **closes** a spec/impl gap rather than creating one. |
| CHECK-I10 | pass | Strongest evidence of the round, all from instruments other than `--check`: 96/96 adapter files at exactly `1/1`, all `M`; 3 unique added lines across all 96; 72/72 `shared-conventions.md` mirrors byte-identical to canon with exactly one hit each; 24/24 authoring-skill mirrors with correct filename convention, intact frontmatter, correct per-adapter `AskUserQuestion` transformation; zero surviving pre-amendment wording repo-wide; `forge-verify`/`forge-fix` mirrors correctly untouched. |
| CHECK-I11 | pass | `ruff check scripts/ eval/` exit 0. `ruff check tests/` 19 errors, count unchanged; the one in a touched file confirmed pre-existing against a `git show 21f1c34:` copy. `--select F841,F541` clean. The new `import warnings` is used, so F401 does not fire. |
| CHECK-I12 | pass | `validate.sh` exit 0 twice genuinely back-to-back on a healthy disk; both `All checks passed!`; both 1808 passed / 2 skipped; zero fixture bytecode after each; clean tree after each. An earlier attempted pair is void — see measurement hazard 2. |
| CHECK-I13 | pass | Zero TODO/FIXME/XXX/HACK/TBD/placeholder markers among the 142 added lines. The two `placeholder` hits in `check-spec-purity.py` are pre-existing descriptive prose. |
| CHECK-I14 | **fail** | V-009. The Step 4 assertion messages are accurate and name the widening path; the Step 5 hard gate is unchanged and correct; only the warning's attribution is wrong. |
| CHECK-I15 | pass | The one new literal, `assert CALL_SPAN <= 3`, is structurally what round-4 V-004 prescribed (its *value* is V-001). The 29 `# N` annotations re-derived independently: 29/29 exact, sorted, deduped. The pre-existing hardcoded `99e63e6` is unchanged and still carries its skip fallback. |
| CHECK-I16 | pass | +6 re-derived by test-node-ID **set difference** (1804 → 1810 collected), not from totals. Added set is exactly control 3a-ii × six surfaces; **removed set empty**, so nothing was lost or renamed. |
| CHECK-I17 | pass | All five round-4 findings re-verified by mutation, each red at the intended assertion's line **and** clause id. Both disclosed deviations reproduce and are SOUND. V-007 and V-008 are residual blind spots; neither re-opens the defect its round-4 finding named. **First round in five with no guard-quality defect.** |
| CHECK-I18 | pass | `README.md` present; `docs/architecture/` holds three feature dirs. `stage-exit-coverage` absent because `forge-6-docs` has not run — correct for impl-verify. |
| CHECK-I19 | **fail** | V-001, V-002, V-005, V-006, V-010. Mechanical sweeps clean (0 de-indented docstring continuations via a `tokenize` pass over every STRING/COMMENT token, 0 merged words, 0 column-0 punctuation across all 142 added lines); the failures are semantic — two newly written prose claims are false against the artifacts they describe. |
| CHECK-I20 | **fail** | V-001. The `CITATION_GRANDFATHERED` maintenance contract is **accurate** — its antecedent test is present, "the same test WARNS whenever an annotation reads high" matches the shipped code, and no `filterwarnings` config exists anywhere, so `pytest -q` does surface it non-fatally as claimed. The failure is `CALL_SPAN`, whose documented basis is a measurement that does not hold. |
| CHECK-I21 | not-applicable | `smokeCommand` is `null`. Advisory re-affirmed but narrowed — V-013. The shipped entrypoint was independently booted end-to-end on both routes; it runs. |
| CHECK-I22 | pass | `iter_shipped_files` (`:803`) → `check_no_spec_citations` (`:782`) → `collect_violations` (`:839`) → `main` (`:905`) → `__main__` (`:909`) → `validate.sh:150` step 6a, a documented hard gate. All 17 top-level functions in `check-spec-purity.py` have non-test callers. The `CITATION_GRANDFATHERED` edit is **AST-identical** to `21f1c34` (`ast.dump` sha256 matches) — comment-only, zero executable change, zero new citations, standalone exit 0. Advisory V-012 filed under the check's stated failure mode against `_verify_state_for`, outside this round's diff. |
| CHECK-I23 | not-applicable | Python stack, no universal bootstrap entry. No `pyproject.toml`, no framework startup hook, no ASGI/WSGI app object; the only non-adapter `__init__.py` is a bootstrap *template*. Heavy-marker grep hits only under `.venv/`. Unchanged by this round's diff. |

Executed 23 of 23 checks. Results: 14 pass, 6 fail, 3 not-applicable.

---

## Fix Execution Plan

### User Decisions Required

**Decision 1 (V-001) — correct `CALL_SPAN` to its measured value, or restate what it measures.** The two options are not equivalent and the applier should not pick:

- **(a) `CALL_SPAN = 4` + decouple the window.** Truthful: the constant then means what its comment says. Cost: `LOOKAHEAD <= CALL_SPAN` would permit a 4-line lookahead, re-opening exactly the coupling round-4 V-004 closed — so it must be paired with a new absolute `assert LOOKAHEAD <= 3`. Three assertions become four.
- **(b) Keep `CALL_SPAN = 3`, restate the comment.** Cheapest and changes no behaviour: the flattener genuinely only needs to reach the `--status skipped` flag, which sits at offset 0 or 1 at all three skip-recording surfaces. Cost: the constant keeps a name that does not describe canon, so the comment must explicitly say it truncates six calls on purpose, or the confusion returns.

Recommendation: **(b)**, with the truncation recorded explicitly. The 3-line window is not wrong for its actual job; only the justification written above it is. Option (a) adds a fourth assertion and widens a bound that measurement says should be 1.

**Decision 2 (V-004) — apply the classifier fix now, or spec-only and defer the code change.** The fix changes runtime classification: stages sitting at `findings-applied` will begin reading `stale` instead of `fresh`, so the navigator's "verify before continuing" gate will start firing for them. That is the spec'd intent, but it is a live behaviour change for any feature currently parked at `findings-applied`, **including `forge-bootstrap` and `epic-orchestration` in this repo**.

- **(a) Spec + code + regression test** (Steps 6–8 below). Closes the hole. Changes live navigator behaviour for three features in this repo.
- **(b) Spec edit only**, deferring the code change to a follow-up backlog item. Records the rule; leaves the hole open.

Recommendation: **(a)**. The hole is the exact failure mode this feature exists to close, and the behaviour change it causes is the *correct* behaviour — those stages genuinely have unresolved verification.

**Decision 3 (V-004) — this feature's own two legacy entries.** `forge-verify-specs` and `forge-verify-backlog` in `.pipeline-state.json` carry `verifiedStageVersion` alongside `findings-applied`. Do **not** hand-edit them — `state-verify` is the sole writer and `findings-applied` is not re-writable to drop a key. Either leave them (the new guard makes them harmless) or resolve them by an actual re-verify of the specs and backlog stages. Recommendation: **leave them**; the guard neutralises them, and re-verifying two long-settled stages is out of scope for an impl fix pass.

**Decision 4 (V-008) — record the non-pin, or pin the label separately.** Recommendation: **record** (option (a)), which V-002's fix largely writes anyway. The round-4 deviation establishing that the label cannot be pinned uniformly is sound and must not be reversed.

**Decision 5 (V-012) — fix now, or defer.** V-012 is pre-existing and outside `git diff 21f1c34..HEAD`; the reshaping touches the live stage-exit route. Recommendation: **fold it into V-004's Step 7**, since V-004's fix already requires mirroring the guard into `_verify_state_for` and that is only meaningful if the helper is on the runtime path. Doing them separately means touching the same two functions twice.

**Decision 6 (V-013) — configure a `smokeCommand` or keep it `null`.** Recommendation: **keep `null`** and re-record the narrowed advisory. Do not set it to `bash scripts/validate.sh`.

V-002, V-003, V-005, V-006, V-007, V-009, V-010 and V-011 require no policy call.

### Execution Steps

#### Step 1: Correct the module docstring's clause-(c) measurement claim
- **Files:** `tests/test_capability_determination_prose.py` (`:30-36`)
- **Addresses:** V-002, and substantially V-008 option (a)
- **Action:** Replace the second half of the "measured twice" sentence with the wording in V-002's suggested fix: describe the mutation as rewriting the *dispatch clause* (which goes RED on all six), and add the explicit note that relabelling only the gate's option is deliberately not pinned, with the reason. Do not change any fragment in `CLAUSES`.
- **Acceptance evidence:** no test change expected. Before writing, re-confirm the three ground-truth facts listed in V-002. After writing, read the docstring against control 3a-ii's docstring and confirm both describe the same mutation.
- **Depends on:** none — do this first; it is the round's clearest false claim.

#### Step 2: Sweep the residual "half" framing
- **Files:** `tests/test_capability_determination_prose.py` (`:26`, `:28`, `:29`, `:127`, `:372`, `:395`, `:418`, `:420`, `:439`)
- **Addresses:** V-005
- **Action:** Apply the nine substitutions ("half" → "obligation"). Leave `tests/test_state_verb_call_sites.py:176` alone — genuinely two-sided. Then read the module docstring, the whole `CLAUSES` comment block, both guard banners and all six control docstrings end-to-end as prose.
- **Depends on:** Step 1 (same file)

#### Step 3: Close the two shadowing blind spots in the roster-derivation guard
- **Files:** `tests/test_capability_determination_prose.py` (`:474-492`, and the comment above it)
- **Addresses:** V-007, V-010
- **Action:** Replace the `AnnAssign`-only comprehension with the binding-count form in V-007's suggested fix, and add the two `_capability_surfaces` alias assertions. Extend the comment with one sentence recording that a single-node check is satisfied by a decoy, and qualify both finding IDs per V-010.
- **Acceptance evidence (mandatory, with `PYTHONDONTWRITEBYTECODE=1`, `-p no:cacheprovider`, `__pycache__` purged between runs):** both green probes from V-007's table must go RED **at the new assertion's own line number** — not at the floor, not at the existing derivation assertion. The four already-red probes must stay red at the derivation assertion. Unmutated copy: 43 passed.
- **Depends on:** Step 2 (same file)

#### Step 4: Fix `CALL_SPAN`'s documented basis
- **Files:** `tests/test_state_verb_call_sites.py` (`:61-71`, `:170-176`, `:183-187`, `:264-270`)
- **Addresses:** V-001
- **Action:** Per Decision 1. Under **(b)**: rewrite `:61-63` to state that 3 is a deliberate flattening window truncating the six four-line calls (naming them), justified because every searched flag sits at offset 0–1; rewrite `:172-175` to drop "a maintainer who adds a fenced call with three flag lines" (canon already has six) and say instead that a *new flag on a fourth line* is the trigger to re-measure; change the assertion's message to name the real invariant; correct `_state_verify_call_text`'s "line **pair**" to "up to `CALL_SPAN` lines". Under **(a)**: set `CALL_SPAN = 4`, restate the comment with the six sites, change the pin to `<= 4`, and **add** `assert LOOKAHEAD <= 3` before `assert LOOKAHEAD <= CALL_SPAN`.
- **Acceptance evidence:** re-derive the maximum fenced-call span with an independent walker and confirm the number written into the comment equals it. Under (a), confirm `CALL_SPAN = 8` + `LOOKAHEAD = 8` reds **at the new absolute `LOOKAHEAD` assertion's line number** — record the line number.
- **Depends on:** Decision 1

#### Step 5: Point the grandfather drift warning at the test that owns it
- **Files:** `tests/test_check_spec_purity.py` (`:463`)
- **Addresses:** V-009
- **Action:** Delete `stacklevel=2,`, leaving the default. Add the one-line comment from V-009's suggested fix.
- **Acceptance evidence (mandatory):** per V-009 — the warnings-summary location line must name `tests/test_check_spec_purity.py:<warn line>`, **not** `_pytest/python.py`. Record the reported path, not merely "a warning appeared".
- **Depends on:** none

#### Step 6: Add the read-side freshness rule to the spec
- **Files:** `specs/stage-exit-coverage/03-verification-state.md` (§5.1)
- **Addresses:** V-004
- **Action:** Add the seventh classifier rule to §5.1's ordered list, before the generic resolved handling, exactly as worded in V-004's suggested fix, citing §4.2 step 4 and REQ-DEBT-05/06. Do not renumber or reword the six existing bullets.
- **Depends on:** none

#### Step 7: Enforce it in the classifier, and put the route back on its specified helper
- **Files:** `scripts/forge-session.py` (`:928-946`, `:2215-2231`, `:3515-3530`), `scripts/epic-manifest.py`
- **Addresses:** V-004, V-012
- **Action:** Per Decisions 2 and 5. Insert the `findings-applied → stale` guard before the version comparison in `verify_state`, with a comment naming §4.2 step 4 and the REQ-DEBT-06 reason. Apply the identical guard in `epic-manifest.py`'s status reader. In the same change, give `_verify_state_for` the epic-context parameter it needs and call it from `:3515-3530`'s non-epic branch, so the guard has one home rather than three and the helper regains a runtime caller.
- **Acceptance evidence (call-path, not suite-green):** re-run the executable-corpus AST orphan sweep and confirm `_verify_state_for` is no longer orphaned. On a scratch copy, mutate its body to return a constant wrong label and confirm a **subprocess** test in `tests/test_stage_exit.py` goes RED, recording the line number — a red confined to `tests/test_auto_verify.py` does not satisfy this step.
- **Depends on:** Step 6; Decisions 2 and 5

#### Step 8: Regression-test the legacy shape
- **Files:** `tests/test_state_verbs.py` (or `tests/test_auto_verify.py`)
- **Addresses:** V-004
- **Action:** Add a test constructing a `findings-applied` entry that **carries** a `verifiedStageVersion` equal to its stage's `version`, asserting `verify_state` returns `stale` and `pending_verify` returns that stage. The docstring must state the shape is unreachable through the current writer and arrives only via legacy state (REQ-DEBT-06), so it cannot later be "simplified" into a writer-behaviour assertion that passes vacuously.
- **Acceptance evidence:** confirm the test **fails** against the pre-Step-7 code before accepting it. A test that passes both before and after is asserting the writer's behaviour, not the reader's.
- **Depends on:** Step 7

#### Step 9: De-circularize the canon sentence, then regenerate
- **Files:** `skills/forge-{1-prd,2-tech,3-specs,4-backlog}/SKILL.md`, `references/shared-conventions.md` § Verify Capability, then `python3 scripts/build-adapters.py`
- **Addresses:** V-006
- **Action:** Apply the two-sentence split from V-006's suggested fix to all five canon surfaces, adopting one wording across them. Keep `dispatched on the affirmative` and `reuse the Standard Verify Gate block for consent` intact and inside the same blank-line-delimited paragraph. Regenerate adapters.
- **Acceptance evidence:** the four probes listed in V-006 — in-paragraph `c1a`/`c1b` match on all six; dispatch→print mutation RED at `clause (c1b)` on all six; `--check` exit 0; all 72 `shared-conventions.md` mirrors byte-identical to canon, exactly once.
- **Depends on:** none

#### Step 10: Restore `01-architecture-layout.md` §2 and name the new guards in the testing spec
- **Files:** `specs/stage-exit-coverage/01-architecture-layout.md` (§2), `specs/stage-exit-coverage/07-testing-strategy.md`
- **Addresses:** V-003
- **Action:** Add the seven rows from V-003's table to §2 in their respective blocks, matching the existing two-column alignment and marker vocabulary. Add `tests/test_capability_determination_prose.py` and `tests/test_gate_pytest_reachability.py` to `07-testing-strategy.md`'s enumerated module list, each with a one-line statement of what it guards. Do not add `.gitignore` or `forge.config.json`.
- **Depends on:** none

#### Step 11: Correct the item count in the standing-invariant note
- **Files:** `specs/stage-exit-coverage/.pipeline-state.json` (via `state-note` only)
- **Addresses:** V-011
- **Action:** Read the current `notes` string in full, change only "(30 items, 001-030)" to "(32 items, 001-032; 031-032 appended by forge-5-loop as fix items after backlog verification)", and re-emit the **entire** combined string through `state-note`. It overwrites, so omitting any part destroys it. On exit 2, surface the `Error:` line verbatim and do not claim persistence.
- **Depends on:** none

#### Step 12: Regenerate and re-gate
- **Action:** `python3 scripts/build-adapters.py` (Steps 7 and 9 touch canon), then `--check` (exit 0), then **check `df -h /` for ≥1 GB free**, then `bash scripts/validate.sh` **twice back-to-back** (both exit 0, both `All checks passed!`, both 1808 passed / 2 skipped plus exactly the deltas Steps 8 and — under Decision 4(b) — V-008 introduce, accounted for by node-ID set difference, not by totals), then `find tests/fixtures -name '__pycache__' -o -name '*.pyc' | wc -l` after each (both 0), then `ruff check scripts/ eval/`, `python3 scripts/check-spec-purity.py`, `ruff check tests/ --select F841,F541` (clean) and `ruff check tests/` (must stay at 19 — note `test_check_spec_purity.py:273`'s pre-existing E501 shifts if that file is edited), then `git status --porcelain` (empty).
- **Verification discipline:** for every guard touched, the acceptance evidence is a **mutation going red at the intended assertion's line number and on the intended clause id** — with bytecode caching disabled, per measurement hazard 1. For every prose edit, the evidence is the passage **re-read end-to-end as prose**, not diffed: five consecutive rounds have now shipped a false narrative around a mechanically-correct change, and the suite cannot see any of them.
- **Depends on:** Steps 1–11
