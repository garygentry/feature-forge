# Verification Report: verify-fix-sweep (specs)
Date: 2026-08-11
Pipeline Stage: forge-3-specs (complete, v1)
Artifacts Reviewed: PRD.md, tech-spec.md, 00-core-definitions.md, 01-architecture-layout.md, 02-fix-sweep-script.md, 03-forge-fix-integration.md, 04-verification-checks.md, 05-testing-strategy.md, TRACEABILITY.md; live-tree corroboration of skills/forge-fix/SKILL.md, skills/forge-verify/SKILL.md, the three checklist files, findings-template.md, references/stage-exit-protocol.md, scripts/build-adapters.py, scripts/check-spec-purity.py, and the six pinned test files.

Run shape: five parallel clean-room verifier instances (types/contracts S09–S13+S18–S21; architecture/non-functional S05–S08+S27–S32; coverage/cross-reference S01–S04+S14–S17+S38; testing S33–S37; integration S22–S26). Executed 38 of 38 checks. Results: 23 pass, 15 fail, 0 not-applicable. Deterministic gate: `validate-traceability.py` 16/16 covered, 0 orphans.

**Not re-filed (already recorded):** tech-spec's stale SKILL.md line range "43–48" (live: 40–48) is already an open advisory (V-102) in `.verification/VERIFY-tech-2026-08-10-round2.md`; the specs suite anchors by quoted text and is unaffected. Likewise V-101/V-103 there remain tech-spec-local; the specs suite does not inherit them (V-023 below adds the loop-closing TRACEABILITY note for V-103).

## Summary
- Total findings: 28
- Gaps: 5
- Inconsistencies: 13
- Improvements: 10
- Errors: 0
- Blocking (errors + gaps): 5 — report records findings-reported

## Findings

### V-001: Re-run suppression silently accepts a failed `FIXED` disposition
- **Severity:** gap
- **Location:** 03-forge-fix-integration.md §4.4, §4.6 (paste block), §4.7; 02-fix-sweep-script.md §4.6
- **Issue:** The re-run matches already-dispositioned hits by `(file, matched text)` and declares them "needs no second disposition". That identity is exactly the signature of a **failed `FIXED`**: if the agent's edit missed the occurrence, the second sweep re-reports the identical `(file, needle)` and the rule classifies it as handled — so a survivor recorded as `FIXED` can still be present at pass close, violating REQ-SWEEP-04 (P0) and reproducing the feature's own defect class inside the mechanism built to catch it. 02 §4.6 compounds this: one hit per `(file, needle)` is justified by "a second occurrence in the same file is always fixed by the same edit", which nothing verifies. The suppression is correct for `JUSTIFIED`/`FALSE-POSITIVE` (they legitimately re-appear); only `FIXED` is mishandled.
- **Suggested fix:** Make the re-run disposition-aware in all three places: (1) 03 §4.4 — a re-run hit whose first-block disposition was `JUSTIFIED`/`FALSE-POSITIVE` needs no second disposition; a re-run hit whose disposition was **`FIXED` is a failed fix** — re-disposition it (correct now within the single re-run) or close `failed`; never leave it recorded as `FIXED`. (2) 03 §4.6 paste block — same clause in the shipped prose. (3) 03 §4.7 — add row: "Re-run re-reports a hit dispositioned `FIXED` | exit 1 on second run | fix did not land: correct now, or record and stop | `failed` if still surviving". (4) 02 §4.6 — soften the rationale to "…normally fixed by the same edit; when it is not, the re-run's `FIXED` re-report is what catches it (03 §4.4)". Optionally add the new clause's literal to 05 §2.11's protection set (deliberate extension of the declared meta-guard contract).
- **References:** PRD REQ-SWEEP-04; 00-core-definitions.md §7.2, §8.1–§8.2
- **Checklist:** CHECK-S21, CHECK-S18

### V-002: End-of-file checklist placement silently de-fangs two existing Runnability guards; 05 §3 prescribes only a comment refresh
- **Severity:** gap
- **Location:** 05-testing-strategy.md §3 (rows test_dev_runtime_smoke.py, test_smoke_command.py); upstream rationale 04-verification-checks.md §5.2
- **Issue:** Both tests slice impl.md as `text.split("### Runnability", 1)[1]` — to end of file. Appending `### Work-Order Cardinality` (I24) and `### Internal Consistency` (I25) after `### Runnability` grows that slice, and I24's guaranteed literals (`not-applicable`, `never a hard fail`) then satisfy the very assertions that today prove CHECK-I21/I22 degrade — deleting I21/I22's degradation clause would no longer fail the test. `test_i23_present_and_advisory`'s CHECK-I23 sub-slice degrades the same way (3 of 5 assertions become satisfiable from I24's prose). 04 §5.2 and 05 §3 reason only in the "stays green" direction; nothing detects the effectiveness regression.
- **Suggested fix:** (Decision D3, default (a).) In 05 §3, replace "refresh the stale comment" for both files with a behavioral edit: terminate the slices at the next heading (`.split("\n### ", 1)[0]`) in `_runnability()`, `test_runnability_checks_degrade_gracefully()`, and the I23 sub-slice; update the comments to say the slice is heading-terminated because impl.md gained sections after Runnability. Extend 05 §8's mutation checkbox: "Removing any single canon edit **or any CHECK-I21/I22/I23 degradation clause** fails at least one guard." Alternative (b), also recorded in 04 §5.2: insert both new impl sections *before* `### Runnability` so the slices stay byte-identical.
- **References:** tests/test_dev_runtime_smoke.py:33–50; tests/test_smoke_command.py:60–79; 04 §3.2, §5.3
- **Checklist:** CHECK-S34

### V-003: No test pins the git-failure-vs-skip classification — the branch that justifies the feature's only code duplication
- **Severity:** gap
- **Location:** 05-testing-strategy.md §2.5, §2.8, §4
- **Issue:** 02 §3 duplicates a git helper precisely because `_git_output`'s "any failure → None" cannot distinguish skip (exit 0) from failure (exit 2). Of the five classification rows (git-dir→skip; show-toplevel fail→exit 2; HEAD→skip; diff→exit 2; ls-files→exit 2), 05 tests only the two skip rows. No test exercises a bare repo, a failing diff/ls-files, or an absent git binary (`GIT_UNAVAILABLE`), though this branch decides whether forge-fix closes `failed` or advances after a NOT-RUN notice. §4's target "every exit-code row per subcommand" is unmet for sweep's exit-2 row; §2.1 omits `GIT_UNAVAILABLE`/`GIT_TIMEOUT_SECONDS` from pinned constants.
- **Suggested fix:** Add §2.5.1 "Git-failure classification (00 §10, 02 §3)" with four tests: non-repo probe returns a code, not an exception; empty `PATH` → `GIT_UNAVAILABLE` and full sweep still emits skip shape exit 0; bare repo (`git init --bare`) → exit 2, one `Error:` stderr line, empty stdout; monkeypatched failing `ls-files` in a valid repo → `UsageError` → exit 2. Add the two constants to §2.1; add a §4 bullet discharging all five rows by named tests.
- **References:** 02 §3 (WARNING + table), §4.1, §4.4; 00 §6.3, §10
- **Checklist:** CHECK-S34, CHECK-S36

### V-004: 05 §2.11's declared-exhaustive guard set drops three literals/guards that 03 §11 and 04 §5.3 declare guaranteed
- **Severity:** gap
- **Location:** 05-testing-strategy.md §2.11
- **Issue:** §2.11 declares itself the complete protection set, but omits: (1) the literal `by name` for CHECK-B29/I24 — the literal encoding the motivating named-omissions property; (2) 03 §11's guard that `## Step 6: Re-verify Gate` is **byte-identical** to pre-change content (heading survival alone does not detect a body edit — the whole content of C-1); (3) 03 §11's guard that `references/stage-exit-protocol.md` is unmodified with its "Step 6" citation resolving. (03 §11's remaining items are legitimately discharged by §6's gates.)
- **Suggested fix:** Add `by name` to the B29/I24 literal bullet. Add two forge-fix guard bullets: byte-identity pin of `## Step 6:` through the next `## ` heading (module constant captured pre-change), and stage-exit-protocol.md unmodified + citation present. Walk 03 §11 and 04 §5.3 item-for-item against the resulting list.
- **References:** 03 §11; 04 §5.3; 00 §9
- **Checklist:** CHECK-S34

### V-005: The RUNTIME_HELPERS change requires an adapters regeneration that 05 §3/§6/§8 never state
- **Severity:** gap
- **Location:** 05-testing-strategy.md §3 (test_build_adapters.py row), §6, §8
- **Issue:** `tests/test_build_adapters.py::test_no_new_file_appears_under_an_adapter_scripts_dir` asserts each committed bundle's `scripts/` equals `RUNTIME_HELPERS`. Adding `"fix-sweep.py"` makes it fail for every target until `python3 scripts/build-adapters.py` runs and the regenerated tree is committed. §6's gate mentions regen only parenthetically; §8's "pytest green end-to-end" checkbox is unachievable as written. A missing step in the definition of done.
- **Suggested fix:** Add to §3 a row/note requiring the regeneration + commit; insert `python3 scripts/build-adapters.py` as the first §6 gate line; reword §8's checkbox to "…and adapters regenerated".
- **References:** 01 §5.1; tests/test_build_adapters.py:1044–1072
- **Checklist:** CHECK-S34

### V-006: The pinned-test count is stated incompatibly across 01, 04, and 05 (four/five/six), and 01 §7 double-counts the adapters row
- **Severity:** inconsistency
- **Location:** 01-architecture-layout.md §1 (workstream 3), §7 (first checkbox); 04-verification-checks.md §1 (out-of-scope bullet), §8 ("Consumed by"); 05-testing-strategy.md header blockquote, §8 (last checkbox)
- **Issue:** Re-derivation: five test files are edited (01 §2 rows 9–13); four of them move with 04's numeric edits (04 §5.2's table); the sixth row in 05 §3 (`test_adapter_host_neutrality.py`) is a deliberate no-edit. Against that: 01 §1 says "six pinned tests updated" (workstream 3 moves four); 04 §1/§8 say "five" where §5.2 lists four; 05's header says "six updated" and §8 says "All six §3 edits applied" while §6 says "5 updated pins"; 01 §7 says "the 15 inventory rows (plus regenerated adapters/**)" — row 15 *is* adapters. tech-spec §6.5 ("five files updated") and 05 §3's six-row table are correct for the sets they name.
- **Suggested fix:** Normalize: 01 §1 → "four pinned tests updated in lockstep (§2 rows 10–13)"; 01 §7 → "exactly inventory rows 1–14, plus row 15's regenerated adapters/**"; 04 §1 → "the **four** pinned test files… (a fifth, tests/test_build_adapters.py, moves with the RUNTIME_HELPERS edit on the other chain)"; 04 §8 → "the four pinned-count test edits"; 05 header → "five existing pinned tests updated (a sixth is listed in §3 as needing no edit)"; 05 §8 → "All five §3 edits applied (the sixth row is a deliberate no-edit row) and adapters regenerated". Do not alter 05 §3's six-row table or TRACEABILITY delta #2.
- **References:** 01 §2 rows 9–13; 04 §5.2; 05 §3, §6; tech-spec §6.5; TRACEABILITY.md delta #2
- **Checklist:** CHECK-S06, CHECK-S08, CHECK-S15, CHECK-S22, CHECK-S25, CHECK-S34

### V-007: 01 §4.2 still says "one fenced invocation block" — superseded by 03 §7's recorded two-fence resolution
- **Severity:** inconsistency
- **Location:** 01-architecture-layout.md §4.2
- **Issue:** 03 §7 resolves (and TRACEABILITY delta #1 records) that **two** runnable bash fences are required — check-spec-purity rule 6 requires each fence to bind `$R` in-fence. 01 §4.2 still carries the superseded "one fenced invocation block" parenthetical, and 01 is the document the implementer reads first.
- **Suggested fix:** Replace with "(including **two** fenced invocation blocks, one per subcommand — check-spec-purity.py rule 6 requires each shell fence to bind `$R` in-fence; projected 33 lines, see 03-forge-fix-integration.md §7)".
- **References:** 03 §7, §2; tech-spec §3.6; TRACEABILITY delta #1
- **Checklist:** CHECK-S06, CHECK-S08

### V-008: 00 §1's stdlib module list omits `bisect` and `typing` and includes an unneeded `datetime`
- **Severity:** inconsistency
- **Location:** 00-core-definitions.md §1 (first paragraph); mirror in tech-spec §9
- **Issue:** 02 §1.2 fixes the import block as `argparse, bisect, json, re, subprocess, sys, pathlib, typing` and rules out `datetime` ("dates appear only in the sweep record, which the agent writes"). 00 §1 lists `argparse, subprocess, json, re, pathlib, sys, datetime` — wrong in both directions (`bisect` is load-bearing for `line_starts`). C-3 satisfied either way; documentation drift.
- **Suggested fix:** Align 00 §1's list to 02 §1.2 exactly, append the `datetime`-deliberately-absent sentence; optionally mirror into tech-spec §9.
- **References:** 02 §1.2, §4.5; PRD C-3
- **Checklist:** CHECK-S07, CHECK-S05

### V-009: 02 §1.3 requires constants' doc comments to be "byte-aligned" with 00, then prints different ones
- **Severity:** inconsistency
- **Location:** 02-fix-sweep-script.md §1.3 vs 00 §4.3/§5.2
- **Issue:** The instruction "doc comments must stay byte-aligned with 00 §4.3/§5.2" is unsatisfiable — the comments 02 prints differ from 00's for all three constants, and nothing states which is canonical for the shipped file. (The restated-claim-disagrees-with-itself class CHECK-S39 targets.)
- **Suggested fix:** Replace with: "The **values** are byte-identical to 00 §4.3/§5.2; the `#:` doc comments in this section are the ones the shipped file carries — each cites its 00 section rather than restating the rationale, so the rationale has exactly one home." Keep 02's printed comments.
- **References:** 02 §10 (constant checkbox)
- **Checklist:** CHECK-S12

### V-010: 00 §10's error model is missing two failure classes that 02 makes normative
- **Severity:** inconsistency
- **Location:** 00-core-definitions.md §10
- **Issue:** 02 §1.4 says `UsageError` is declared "exactly as 00 §10 specifies", but 00 §10 omits (1) the bare-repo row (`rev-parse --git-dir` succeeds, `--show-toplevel` fails → `UsageError` exit 2 — 02 §3/§4.1/§6) and (2) corpus-file `OSError` skip (permission/vanished/gitlink → silently skipped, excluded from `filesScanned` — 02 §4.4/§6; 00 lists only "undecodable").
- **Suggested fix:** Extend 00 §10's "Raised for:" list with the bare-repo cause and add two classification bullets (show-toplevel failure → exit 2; corpus `OSError` → skipped, excluded from `filesScanned`).
- **References:** 02 §1.4, §3, §4.1, §4.4, §6; tech-spec §7
- **Checklist:** CHECK-S18, CHECK-S11

### V-011: Sweep-record grammar "reproduced verbatim" but the date placeholder differs (`{YYYY-MM-DD}` vs `{date}`)
- **Severity:** inconsistency
- **Location:** 03-forge-fix-integration.md §4.2/§4.6 vs 00 §7.2
- **Issue:** 00 §7.2 uses `{YYYY-MM-DD}` in both positions; the shipped paste block (and tech-spec §4.3) uses `{date}`. The "reproduced verbatim" claim is false, and the shipped grammar disagrees with canon. No guard pins the `- Sweep:` header line.
- **Suggested fix:** (Decision D1, default: align 00 §7.2 down to `{date}` with a "(ISO `YYYY-MM-DD`)" parenthetical — one-file edit matching tech-spec and shipped prose.) Alternative: change the paste block to `{YYYY-MM-DD}`. Either way keep "verbatim" only if then true.
- **References:** tech-spec §4.3; 05 §2.11
- **Checklist:** CHECK-S12

### V-012: The corpus-enumeration command is stated with and without `-z`, and the `-z` form is mis-attributed
- **Severity:** inconsistency
- **Location:** 00-core-definitions.md §5.1; 02-fix-sweep-script.md §4.4
- **Issue:** 00 §5.1 fences `git ls-files --cached --others --exclude-standard`; 02 §4.4 specifies the `-z` form and attributes it to "tech-spec §3.4's command" — which lacks `-z`. `-z` is load-bearing (NUL framing defeats quoting); an implementer reading 00 alone writes the newline-splitting form and inherits the quoting bug.
- **Suggested fix:** Add `-z` to 00 §5.1's fence with a one-line rationale; reword 02 §4.4's parenthetical to "tech-spec §3.4's command, with `-z` added here so…". Leave tech-spec unedited (upstream; the suite refines it).
- **References:** 02 §3 (decode note)
- **Checklist:** CHECK-S12

### V-013: Three forward references from 00 into 02 name the wrong subsection
- **Severity:** inconsistency
- **Location:** 00-core-definitions.md §4.3 (final para), §4.2 (final line), §5.3 (`line_starts` docstring)
- **Issue:** §4.3 cites "02 §5" for hit/extraction-order detail (that is plan-coverage; the referent is 02 §4.6); §4.2 cites "02 §3" for the parse contract (that is the git helper; referent 02 §4.2); §5.3 cites "02 §4" (imprecise; referent 02 §4.5). All resolve to existing-but-wrong sections, so existence checks miss them.
- **Suggested fix:** Repoint to §4.6, §4.2, §4.5 respectively.
- **References:** 02 §4.2, §4.3, §4.5, §4.6
- **Checklist:** CHECK-S15

### V-014: 01 §3's implementation-order graph omits the RUNTIME_HELPERS → forge-fix prerequisite that 03 declares hard
- **Severity:** inconsistency
- **Location:** 01-architecture-layout.md §3 vs 03 §8/§10
- **Issue:** 01 §3 draws row 3 (forge-fix SKILL edits) and row 8 (RUNTIME_HELPERS) as parallel siblings; 03 §8 declares row 8 a **hard prerequisite** of row 3 ("without it, both invocations fail on every non-Claude adapter"). An implementer following 01's graph can land the fences without the tuple edit; nothing fails until an adapter build runs.
- **Suggested fix:** Re-parent row 8 above row 3 in the graph (or add one explicit prerequisite sentence beneath it), citing 03 §8. Keep the single-regeneration join sentence unchanged.
- **References:** 01 §5.1; 03 §8, §10; 02 §9
- **Checklist:** CHECK-S16

### V-015: 05 §2.11 prescribes `test_no_cross_mode_leakage` as new content — it already exists
- **Severity:** inconsistency
- **Location:** 05-testing-strategy.md §2.11 (final paragraph)
- **Issue:** The described guard exists at `tests/test_verification_checklists_split.py:105–115` (parametrized, regex per mode letter), correctly attributed by 04 §5.1. Under §2's framing ("each subsection is a commented section of [test_fix_sweep.py]") an implementer authors a divergent duplicate; the one-line description also omits the actual assertion (a mode file may contain only its own letter's ids).
- **Suggested fix:** Convert to a reference to the existing test, state its real assertion, and move the paragraph into §3 beside the split-test row.
- **References:** 04 §5.1; tests/test_verification_checklists_split.py:66–74, 105–115
- **Checklist:** CHECK-S34, CHECK-S37

### V-016: The 6→7 bump leaves `test_runtime_helpers_still_has_exactly_six_entries`'s name and docstring asserting the opposite
- **Severity:** inconsistency
- **Location:** 05-testing-strategy.md §3 (test_build_adapters.py row)
- **Issue:** The prescribed pure literal substitution leaves the function name stating a falsehood and the docstring ("No seventh helper was added…") contradicting the assertion beneath it, while the still-valid `forge_json.py`-rejected rationale goes unstated. Severity floor: narration beside correct code.
- **Suggested fix:** Extend the row: rename to `test_runtime_helpers_has_exactly_seven_entries`; rewrite the docstring (fix-sweep.py is the seventh helper, #170, 01 §5.1; `forge_json.py` stays rejected, pinned by the surviving `not in` assert). Grep for `six`/`6` near RUNTIME_HELPERS when applying.
- **References:** tests/test_build_adapters.py:1040–1055
- **Checklist:** CHECK-S34

### V-017: The third stale end-of-file comment (`test_lifecycle_artifact_check.py`) is omitted from the enumeration
- **Severity:** inconsistency
- **Location:** 05-testing-strategy.md §3 (test_lifecycle_artifact_check.py row); 04-verification-checks.md §5.2
- **Issue:** 04 §5.2 names two stale "last section" comments; the third instance is `tests/test_lifecycle_artifact_check.py:31–32` ("backlog.md ends with this section…"), made false by appending `### Work-Order Cardinality` to backlog.md. The slice's membership assertions stay green; prose-only. This is the same defect class B29/I24 are being introduced to catch.
- **Suggested fix:** Extend 05 §3's row with the comment refresh; in 04 §5.2 change "Two comments" to "Three comments" and add the file, noting its slice is membership-only and stays green.
- **References:** tests/test_lifecycle_artifact_check.py:29–39; 04 §3.1
- **Checklist:** CHECK-S25

### V-018: Block A's margin-placement rationale attributes the indented-fence failure to rule 6; it actually trips rule 5
- **Severity:** inconsistency
- **Location:** 03-forge-fix-integration.md §2 ("Placement notes that matter mechanically", first bullet)
- **Issue:** Rule 6's fence scanner (`_FENCE_OPEN_RE`, column-0 anchored) never collects an indented fence, so rule 6 cannot fire on it; what fails is rule 5 (`check_prelude_identity` — the indented second prelude line breaks byte-identity). Verified by executing `_shell_fences()` on an indented sample (returns `[]`). The margin conclusion is right; the predicted error is wrong, inviting a false workaround.
- **Suggested fix:** Rewrite the bullet to cite both rules: rule 6 requires `^R=` in every *recognized* fence; an indented fence isn't recognized at all, and its prelude trips rule 5's byte-identity as `bootstrap prelude not byte-identical to canon`. Leave §7 and §11 unchanged (already correct).
- **References:** scripts/check-spec-purity.py:130–138, 650–674, 687–716, 727–760
- **Checklist:** CHECK-S25

### V-019: `DroppedNeedles` is the only TypedDict with no per-field documentation
- **Severity:** improvement
- **Location:** 00-core-definitions.md §6.1
- **Issue:** Five of six TypedDicts carry a `Keys:` block; `DroppedNeedles` documents neither counter, though the semantics are load-bearing (below-floor needles are counted once and never reflow-tested; 02 §10 pins `belowFloor + reflowSuppressed + len(needles) == raw removed-line count`).
- **Suggested fix:** Add a `Keys:` block in the sibling style with the counted-once rule and the sum invariant.
- **References:** 02 §4.3, §10
- **Checklist:** CHECK-S13

### V-020: Only one of the four exit-2 messages has specified text
- **Severity:** improvement
- **Location:** 02-fix-sweep-script.md §2.3, §6, §10; 00 §6.3
- **Issue:** Only `Error: --min-chars must be >= 1` is pinned. Git failure, bare repo, and unreadable findings doc have no message shape, yet 03 tells the agent to "surface the `Error:` line verbatim" — the operator may receive a bare OSError repr with no indication of subcommand or git call. Tests can only assert the prefix.
- **Suggested fix:** Pin three shapes in 02 §6 (mirror in §10): `Error: git {subcommand} failed ({rc}): {first stderr line}`; `Error: repository has no working tree (bare repo): {repo_root}`; `Error: cannot read findings document: {path} ({reason})`. Tighten 05 §2.7/§2.8 to assert message stems.
- **References:** 03 §3.4, §4.7; 05 §2.7, §2.8
- **Checklist:** CHECK-S20

### V-021: An unhandled exception exits 1 — the same code the integration prose calls "normal"
- **Severity:** improvement
- **Location:** 02-fix-sweep-script.md §2.2, §3; 03-forge-fix-integration.md §4.1
- **Issue:** `main()` maps only `UsageError`/`OSError` to exit 2; any other escaping exception exits 1 — the "survivors found" code — while 03 §4.1 tells the agent "Exit 1 is normal". No rule distinguishes working from crashed.
- **Suggested fix:** Add the payload-presence discriminator: exit 1 **with** a parseable JSON payload = survivors; exit 1 with no JSON on stdout = crash → surface stderr traceback, close `failed`. Mirror into 03 §4.6/§4.7 and 02 §6 (02 §2.3's "never partial" invariant makes the discriminator sound).
- **References:** 00 §6.3; 02 §2.3
- **Checklist:** CHECK-S19

### V-022: An empty `--exclude` value silently empties the corpus and reports a false clean
- **Severity:** improvement
- **Location:** 02-fix-sweep-script.md §2.1, §4.4; 00 §5.2 rule 3
- **Issue:** `path.startswith("")` is `True`, so `--exclude ""` excludes every path: `hits: []`, exit 0 — a silent false-clean on the surface built to prevent false claims surviving. Operator-only reachability (skill prose is guarded to contain no `--exclude`), hence improvement. The `--min-chars < 1` guard is the existing precedent.
- **Suggested fix:** Reject empty/whitespace-only `--exclude` in `main()` as `UsageError("--exclude requires a non-empty path prefix")`; add the row to 02 §6 and the clause to 00 §5.2 rule 3; add the case to 05 §2.6.
- **References:** 02 §4.6 (filesScanned-evidence argument)
- **Checklist:** CHECK-S28

### V-023: Per-document Requirement Coverage tables under-report; the claimed-totals delta needs a TRACEABILITY row
- **Severity:** improvement
- **Location:** 00-core-definitions.md coverage table; 01-architecture-layout.md coverage table; TRACEABILITY.md
- **Issue:** 00's table omits REQ-CARD-02/03 though §9's heading covers them; 01's collapsed notation (`REQ-SWEEP-01..07`, `REQ-CARD-02/03`) defeats the deterministic validator (it credits 01 with only SWEEP-01 and CARD-02). Coverage is not at risk (each id carried by ≥3 docs). Loop-closer: without a TRACEABILITY "Known deltas" row recording that plan-coverage implements only `Total findings: N` (per recorded Decision 3; tech-spec §3.5's per-severity parenthetical = tech residual V-103), every future verifier re-derives that false positive.
- **Suggested fix:** Add the two REQ-CARD rows to 00's table; expand 01's collapsed ids; add TRACEABILITY "Known deltas" #4 per above; re-run validate-traceability and confirm 01 now carries SWEEP-02..07 and CARD-03.
- **References:** .verification/VERIFY-tech-2026-08-10-round2.md V-103; tech-spec §3.5 vs §4.2
- **Checklist:** CHECK-S38, CHECK-S01

### V-024: Two citations use notation that does not resolve to a heading
- **Severity:** improvement
- **Location:** 01-architecture-layout.md §1 item 1 ("tech-spec §6.8"); TRACEABILITY.md delta #1 ("The §3.6 line-estimate")
- **Issue:** tech-spec §6 has no subsections — the referent is §6 list item 8 (02 §3 cites it correctly). TRACEABILITY delta #1's "§3.6" reads as 03's §3.6 (nonexistent); referent is tech-spec §3.6.
- **Suggested fix:** "(tech-spec §6.8)" → "(tech-spec §6, item 8)"; "The §3.6 line-estimate" → "The tech-spec §3.6 line-estimate".
- **References:** tech-spec §6 item 8, §3.6
- **Checklist:** CHECK-S15

### V-025: The `excludes` payload strings are never pinned, leaving the `.verification` vs `.verification/` divergence untested
- **Severity:** improvement
- **Location:** 05-testing-strategy.md §2.6, §2.8; 00 §5.2/§6.1
- **Issue:** The constant is `".verification"` (no slash); the payload example is `[".verification/"]` (slash). No test fixes the spelling or the order of the three sources, though `excludes` is archived as milestone-2 evidence.
- **Suggested fix:** Pin exact lists in 05 §2.6 (gate + `--exclude docs/` → `[".verification/", "adapters/", "docs/"]`; bare → `[".verification/"]`), or raise the spelling against 00 §6.1 first if the bare segment is intended.
- **References:** 02 §4.4 (`applicable_excludes`); tech-spec §10
- **Checklist:** CHECK-S37

### V-026: 05 §6's definition of done lists automated gates only — milestone acceptance is unlisted
- **Severity:** improvement
- **Location:** 05-testing-strategy.md §5, §6, §8
- **Issue:** PRD §8's owner gate ("#170 is not 'done done' until the sweep runs on a real fix pass and is reviewed") and 03 §11's two behavioral confirmations appear nowhere in 05's definition of done; a reader of 05 alone concludes four green commands = done.
- **Suggested fix:** Add a §5 bullet quoting the milestone-acceptance obligations (sweep block lands in Fix Progress with one disposition token per hit; non-repo pass records NOT-RUN and closes once; archive the JSON payload) and a §6 closing line "plus the manual milestone-acceptance observation — the automated gate alone is not 'done done'."
- **References:** PRD §8 final bullet; 03 §11 "Behavioral confirmation"; tech-spec §10
- **Checklist:** CHECK-S34, CHECK-S36

### V-027: Block C's "Before committing…" is anchored after the sentence that instructs staging and committing
- **Severity:** improvement
- **Location:** 03-forge-fix-integration.md §2 (Anchor Map row C), §5.2
- **Issue:** Row C inserts after the live "…stage files… and commit…" sentence; an agent executing linearly stages and commits before reading the qualifier. The mis-ordered read reproduces exactly the defect Block C exists to prevent (out-of-feature-dir survivor fixes left uncommitted).
- **Suggested fix:** (Decision D2, default (a): move the anchor to immediately before the Git Commit Protocol paragraph, updating the placement note.) Alternative (b): keep the anchor and reword the paste block to lead with "do this before running the `git add`/commit above". Both are line-budget neutral.
- **References:** live skills/forge-fix/SKILL.md lines 65–79; 03 §5.1, §7; 00 §8.1
- **Checklist:** CHECK-S24, CHECK-S25

### V-028: 04 §4.3a's "Longest resulting line: 80 characters" is wrong (81 changed / 83 overall)
- **Severity:** improvement
- **Location:** 04-verification-checks.md §4.3a
- **Issue:** The after-form measures 83/81/42; line 1 is untouched at 83, longest changed line is 81. Decorative (no gate measures width), but it is a stated measurement — the class CHECK-S39, introduced by this very document, exists to catch. §4.3b/§4.3c measure correctly.
- **Suggested fix:** Replace with "Longest changed line: 81 characters (line 2); line 1 is untouched at 83."
- **References:** live skills/forge-verify/SKILL.md:40–42
- **Checklist:** CHECK-S25

## Fix Execution Plan

### User Decisions Required
- **D1 (V-011)** — RESOLVED 2026-08-11: `{date}` everywhere — align 00 §7.2 to `{date}` + "(ISO `YYYY-MM-DD`)"; matches tech-spec §4.3 and shipped prose.
- **D2 (V-027)** — RESOLVED 2026-08-11: move Block C's anchor before the Git Commit Protocol paragraph.
- **D3 (V-002)** — RESOLVED 2026-08-11: heading-terminate the test slices; end-of-file section placement stands.
- V-022's guard is pre-resolved by the `--min-chars` precedent (accepted).

### Execution Steps

Apply in order. Each step is self-contained — a fresh agent can execute it from this document alone.

#### Step 1: Shared-contract corrections in 00-core-definitions.md
- **Files:** specs/verify-fix-sweep/00-core-definitions.md
- **Addresses:** V-008, V-010, V-011 (per D1), V-012, V-013, V-019, V-022 (part), V-023 (part)
- **Checklist:** CHECK-S05, S07, S11, S12, S13, S15, S18, S28, S38
- **Action:** §1: replace the stdlib list with `argparse, bisect, json, re, subprocess, sys, pathlib, typing` + the `datetime`-absent sentence. §4.2/§4.3/§5.3: repoint the three forward refs to 02 §4.2/§4.6/§4.5. §5.1: add `-z` to the ls-files fence + one-line rationale. §5.2 rule 3: append "; an empty or whitespace-only prefix is rejected (exit 2), never applied". §6.1: add a `Keys:` block to `DroppedNeedles` (counted-once rule + sum invariant). §7.2: apply D1's placeholder resolution. §10: add the bare-repo cause and the corpus-`OSError` bullet. Coverage table: add REQ-CARD-02 and REQ-CARD-03 rows pointing at §9.
- **Depends on:** none

#### Step 2: Script-contract corrections in 02-fix-sweep-script.md
- **Files:** specs/verify-fix-sweep/02-fix-sweep-script.md
- **Addresses:** V-009, V-012 (part), V-020, V-021 (part), V-022 (part), V-001 (part 4)
- **Checklist:** CHECK-S12, S19, S20, S28
- **Action:** §1.3: replace the "byte-aligned" instruction with the values-identical/comments-cite rule. §2.1: add the empty-`--exclude` rejection bullet. §4.4: reword the `-z` attribution ("with `-z` added here"). §4.6: soften "always fixed by the same edit" to the conditional form pointing at 03 §4.4. §6: add rows for the three pinned exit-2 message shapes, the empty-`--exclude` UsageError, and the unexpected-exception row (traceback on stderr, empty stdout, exit 1, discriminate by absent payload); mirror the message shapes into §10's grid.
- **Depends on:** Step 1

#### Step 3: Integration-prose corrections in 03-forge-fix-integration.md
- **Files:** specs/verify-fix-sweep/03-forge-fix-integration.md
- **Addresses:** V-001 (parts 1–3), V-011 (per D1), V-018, V-021 (part), V-027 (per D2)
- **Checklist:** CHECK-S18, S19, S21, S24, S25
- **Action:** §4.4 + §4.6 paste block: add the disposition-aware re-run rule (`FIXED` re-report = failed fix → re-disposition or `failed`; `JUSTIFIED`/`FALSE-POSITIVE` re-appear legitimately). §4.7: add the failed-`FIXED` row. §4.1 + §4.6 + §4.7: add the exit-1 payload discriminator. §2 first placement bullet: correct the rule-5/rule-6 attribution. Apply D2 to row C / §5.2. Re-verify §7's projected line totals after the paste-block edits and update its table.
- **Depends on:** Step 2 (02 §4.6's wording is referenced by the new §4.4 text)

#### Step 4: Count and measurement corrections in 04-verification-checks.md
- **Files:** specs/verify-fix-sweep/04-verification-checks.md
- **Addresses:** V-006 (part), V-017 (part), V-028
- **Checklist:** CHECK-S06, S15, S25
- **Action:** §1 out-of-scope bullet: "five" → "four … (a fifth, tests/test_build_adapters.py, moves with the RUNTIME_HELPERS edit on the other chain)". §8 "Consumed by": "five" → "four". §5.2: "Two comments" → "Three comments", adding tests/test_lifecycle_artifact_check.py (membership-only slice, stays green). §4.3a: fix the line-width sentence (81 changed / 83 untouched).
- **Depends on:** none

#### Step 5: Architecture corrections in 01-architecture-layout.md
- **Files:** specs/verify-fix-sweep/01-architecture-layout.md
- **Addresses:** V-006 (part), V-007, V-014, V-023 (part), V-024 (part)
- **Checklist:** CHECK-S06, S08, S15, S16, S38
- **Action:** §1 workstream 3: "six pinned tests updated" → "four pinned tests updated in lockstep (§2 rows 10–13)". §1 item 1: "(tech-spec §6.8)" → "(tech-spec §6, item 8)". §3: re-parent row 8 above row 3 (or add the explicit prerequisite sentence) citing 03 §8. §4.2: one fence → two fences (V-007 wording). §7 first checkbox: "rows 1–14 plus row 15's regenerated adapters/**". Coverage table: expand `REQ-SWEEP-01..07` and `REQ-CARD-02/03` to spelled-out ids.
- **Depends on:** none

#### Step 6: Testing-strategy corrections in 05-testing-strategy.md
- **Files:** specs/verify-fix-sweep/05-testing-strategy.md
- **Addresses:** V-002 (per D3), V-003, V-004, V-005, V-006 (part), V-015, V-016, V-017 (part), V-025, V-026
- **Checklist:** CHECK-S34, S36, S37
- **Action:** Header blockquote: "six updated" → "five updated (a sixth listed in §3 as needing no edit)". §2.1: add `GIT_UNAVAILABLE == -1`, `GIT_TIMEOUT_SECONDS`. New §2.5.1: the four git-classification tests (V-003). §2.6: pin the exact `excludes` lists (V-025) and add the empty-`--exclude` exit-2 case (V-022). §2.11: add `by name` to the B29/I24 bullet; add the Step-6 byte-identity and stage-exit-protocol-unmodified guards; convert the cross-mode paragraph to a reference to the existing split test and move it to §3 (V-015). §3: apply D3's slice-termination rows for the two smoke tests; extend the lifecycle row with its comment refresh (V-017); extend the build-adapters row with the rename + docstring rewrite (V-016) and the regeneration requirement (V-005). §4: add the classification-coverage bullet. §5: add the milestone-acceptance bullet (V-026). §6: insert `python3 scripts/build-adapters.py` as the first gate line + the "not done done" closing line. §8: "All six §3 edits" → "All five §3 edits (the sixth row is a deliberate no-edit row) and adapters regenerated"; extend the mutation checkbox to cover I21/I22/I23 degradation clauses.
- **Depends on:** Steps 3–5 (guard literals reference their final wording)

#### Step 7: TRACEABILITY.md and the deterministic gate
- **Files:** specs/verify-fix-sweep/TRACEABILITY.md
- **Addresses:** V-023 (part), V-024 (part)
- **Checklist:** CHECK-S38, S15
- **Action:** Delta #1: "The §3.6 line-estimate" → "The tech-spec §3.6 line-estimate". Add delta #4: plan-coverage implements only `Total findings: N` per recorded Decision 3; tech-spec §3.5's per-severity parenthetical is tech residual V-103 (`.verification/VERIFY-tech-2026-08-10-round2.md`), not a specs gap. Then run `python3 scripts/validate-traceability.py specs/verify-fix-sweep/PRD.md specs/verify-fix-sweep --json` and confirm 16/16 covered, 0 orphans, and that 01 now carries REQ-SWEEP-02..07 and REQ-CARD-03.
- **Depends on:** Steps 1–6

## Fix Progress
- Step 1: [APPLIED] 2026-08-11 — 00-core-definitions.md: stdlib list corrected (bisect/typing in, datetime out), three forward refs repointed (§4.2→02 §4.2, §4.3→02 §4.6, §5.3→02 §4.5), -z added to ls-files fence, empty-prefix rejection in §5.2 rule 3, DroppedNeedles Keys block + invariant, §7.2 {date} placeholder per D1, §10 bare-repo + corpus-OSError rows, coverage table +REQ-CARD-02/03
- Step 2: [APPLIED] 2026-08-11 — 02-fix-sweep-script.md: §1.3 values-identical/comments-cite rule replaces "byte-aligned", §2.1 empty---exclude rejection bullet, §4.4 -z attribution reworded ("with -z added here"), §4.6 rationale softened to conditional + failed-FIXED pointer, §6 table gains three pinned exit-2 message shapes + --exclude row + unexpected-exception row, §10 grid mirrors the message shapes + bare-repo/--exclude rows
- Step 3: [APPLIED] 2026-08-11 — 03-forge-fix-integration.md: §4.4 + §4.6 paste block + §4.7 gain the disposition-aware re-run rule (FIXED re-report = failed fix; JUSTIFIED/FALSE-POSITIVE re-appear legitimately) and the exit-1 payload discriminator (also §4.1); §2 placement bullet corrected to cite rules 5 AND 6 with the real failure modes; Block C anchor moved before the Git Commit Protocol paragraph per D2 (anchor map row C + third placement note rewritten); §7 word projection updated, line total unchanged at 33
- Step 4: [APPLIED] 2026-08-11 — 04-verification-checks.md: §1 "five" → "four (+ build_adapters on the other chain)", §8 Consumed-by "five" → "four", §5.2 "Two comments" → "Three comments" adding test_lifecycle_artifact_check.py + D3 heading-termination note, §4.3a line-width sentence corrected (81 changed / 83 untouched)
- Step 5: [APPLIED] 2026-08-11 — 01-architecture-layout.md: coverage table ids spelled out, §1 item 1 "(tech-spec §6, item 8)", §1 workstream 3 "four pinned tests (rows 10–13)", §3 graph re-parents row 8 above row 3 + explicit prerequisite sentence, §4.2 two fences w/ 33-line projection, §7 checkbox de-duplicates the adapters row
- Step 6: [APPLIED] 2026-08-11 — 05-testing-strategy.md: header count corrected (five + one no-edit), §2.1 +GIT_UNAVAILABLE/GIT_TIMEOUT_SECONDS, new §2.5.1 four git-classification tests, §2.6 exact excludes lists + empty---exclude exit-2 case, §2.11 +`by name` literal + failed-FIXED clause guard + Step-6 byte-identity guard + stage-exit-protocol-untouched guard + cross-mode paragraph converted to a §3 reference, §3 rows rewritten per D3 (heading-terminated slices) / lifecycle comment refresh / build-adapters rename+docstring+regen requirement, §4 classification-coverage bullet, §5 milestone-acceptance bullet, §6 regen gate line + "not done done" close, §8 checkboxes corrected
- Step 7: [APPLIED] 2026-08-11 — TRACEABILITY.md: delta #1 attribution fixed ("tech-spec §3.6"), delta #4 added (claimed totals = Total findings: N only; tech-spec §3.5 parenthetical = V-103 residual); validate-traceability re-run: 16/16 covered, 0 orphans, 01 now carries REQ-SWEEP-01..07 + REQ-CARD-02/03
