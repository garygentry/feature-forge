# Verification Report: stage-exit-coverage (impl)

Date: 2026-07-31
Pipeline Stage: forge-5-loop (complete, v1)
Mode: impl — served production stage `forge-5-loop`
Method: five parallel `forge-verifier` instances over disjoint CHECK-ID slices, merged and deduped here.

Artifacts Reviewed:
- `specs/stage-exit-coverage/` — `PRD.md`, `tech-spec.md`, `00`–`07` implementation specs, `backlog.json` (32 items, 375 acceptance criteria), `.pipeline-state.json`
- `scripts/` — `forge-session.py`, `epic-manifest.py`, `forge-bootstrap.py`, `build-adapters.py`, `check-spec-purity.py`, `validate.sh`
- `skills/` — all nine exit skills plus `forge/`, and their `references/`
- `references/` — `stage-exit-protocol.md`, `shared-conventions.md`, `pipeline-state-schema.json`, `epic-manifest-schema.json`, `forge-config-schema.json`, `stacks/python.md`
- `adapters/{claude,codex,copilot,cursor,gemini,pi}/` (generated mirrors), `installer/`, `eval/`, `tests/`, `README.md`, `ruff.toml`

Checks Executed: **23 of 23** — 17 pass, 5 fail, 1 not-applicable.

| Dimension | CHECK-IDs | Result |
|---|---|---|
| (1) Requirement coverage vs specs | I01–I07 | 7 pass |
| (2) Integration correctness | I08–I12 | 5 pass |
| (3) Testing | I16–I17 | 2 fail |
| (4) Code quality & docs | I13–I15, I18–I20 | 4 pass, 2 fail |
| (5) Runnability | I21–I23 | 1 pass, 1 fail, 1 n/a |

## Summary

- Total findings: 18
- Errors: 1
- Gaps: 3
- Inconsistencies: 4
- Improvements: 9
- Not-applicable (advisory): 1

The implementation is substantially correct. All 32 backlog items are `done`, every recorded invariant holds, the adapter mirror shows no drift, `ruff check scripts/ eval/` is clean, and the loop's own reported gate result (37 PASS / 0 FAIL) was independently reproduced on the tree as committed. The findings below are concentrated in three places: a reproducible test-suite idempotency defect (V-001), two skill call sites that hand-author state the feature exists to script (V-002), and two mandated test guards that never landed (V-003, V-004).

## Invariants confirmed (no findings)

Each was verified against evidence, not asserted:

| Invariant | Result | Evidence |
|---|---|---|
| No `scripts/forge_json.py`; loader mirrored into both flat scripts | HOLDS | `find` returns no match. Loader block SHA-256 identical between `forge-session.py:1147` and `forge-bootstrap.py:810`, and across all six adapter pairs. `test_no_shared_json_module_was_extracted` asserts it cannot appear; `test_this_guard_is_not_skippable` bans `skipif`/`importorskip`. |
| `RUNTIME_HELPERS` exactly six entries | HOLDS | `ast.literal_eval` of the tuple in `build-adapters.py` → 6. Every emitted `adapters/*/scripts/` holds exactly those six files. |
| No locking / leasing / optimistic versioning (PRD REQ-REL-04) | HOLDS | `_commit_state` retains temp-file → flush/fsync → `os.replace`. Item 007 ships a guard asserting that sequence "with no lock, lease, version check, retry, or backoff". |
| Item 024's coverage guard is not vacuous | HOLDS | `tests/test_stage_exit_protocol.py:55-95` extracts `EXIT_STAGES` from `scripts/forge-session.py` by regex + `ast.literal_eval`. Three closing guards: `test_the_extraction_is_not_vacuous` feeds a mutated copy with `forge-fix` deleted and asserts the comparison breaks; `test_exit_stages_is_the_runtime_tuple_derived_from_the_extracted_alias` pins `EXIT_STAGES = get_args(ExitStage)`; `test_coverage_is_an_allow_list_not_a_forge_name_prefix_scan` proves it is an allow-list. |
| `stageNoun` retained, not duplicated | HOLDS | Exactly one key (`forge-session.py:503`) and one emission site (`:3798`). |
| `--epic` sentence inside the 12/8-line window | HOLDS | 32 call sites, all covered. Nearest-`--epic` offset distribution `{-5: 24, +4: 4, +1: 2, -6: 1, -10: 1}` — max lookbehind consumed is 10 of 12, so the window is load-bearing, not slack. |
| Adapter mirror has no drift | HOLDS | `build-adapters.py --check` exit 0. Five of six mirrors byte-identical to canon; `adapters/pi/` differs only by the anchored `/feature-forge:` → `/skill:` substitution (269,724 → 269,460 bytes = exactly the rewrite delta), and the generator raises if a helper differs by more than that. |
| Review-filed fixes 031 / 032 landed correctly | HOLDS | `epic-manifest.py:1424` now calls `_validate_dict` *before* the no-op comparison at `:1428` (032). `forge-session.py:3013-3073` `_promote_reconcile` re-derives the continuation with a distinct non-advancing branch (031). Both carry regression tests. |

Also confirmed clean: no unresolved `TODO`/`FIXME`/stub markers in the changed surface; `pytest --collect-only` → 1747 tests, zero collection errors; every one of 16 CLI verbs has at least one non-test caller; all nine `EXIT_STAGES` dispatch successfully when exercised live against a scratch specs dir.

---

## Findings

### V-001: `bash scripts/validate.sh` cannot be run twice — the suite poisons its own committed fixture tree

- **Severity:** error
- **Location:** `tests/fixtures/minimal-canon/` (and `expected-adapters/*/scripts/`); assertion at `tests/test_build_adapters.py:142`, root cause in `hash_tree` at `tests/test_build_adapters.py:90-102`
- **Issue:** On the tree exactly as committed the gate passes. Running it once creates 28 `__pycache__/*.pyc` files inside the committed fixture tree — 4 under `tests/fixtures/minimal-canon/scripts/` and 4 under each of the six `expected-adapters/*/scripts/`. From that point every subsequent run fails, because `test_matches_committed_snapshot` compares a freshly built `adapters/` (from which the generator correctly excludes `__pycache__`, asserted at `test_build_adapters.py:203-215`) against the now-polluted `expected-adapters/` snapshot.

  Independently reproduced during this verification:

  ```
  E       AssertionError: assert {'GENERATION-...748bbae', ...} == {'GENERATION-...748bbae', ...}
  E         Omitting 155 identical items, use -vv to show
  E         Right contains 24 more items:
  E         {'claude/scripts/__pycache__/epic-manifest.cpython-310.pyc': '76eb76a6...',
  E          'claude/scripts/__pycache__/forge-bootstrap.cpython-310.pyc': '938fa08e...',
  tests/test_build_adapters.py:142: AssertionError
  FAILED tests/test_build_adapters.py::test_matches_committed_snapshot
  ```

  Because `FAIL: epic-manifest pytest suite` increments `ERRORS` (`scripts/validate.sh:214-215`), the whole gate then exits 1. This breaks the "`bash scripts/validate.sh` passes" acceptance criterion carried by items 029, 031, and 032 for any agent who runs it after the first time, and violates spec `07-testing-strategy.md` §9's rule that no temporary debris remains. `adapters/` itself is protected (the probe runs with `-B`, and `test_no_new_file_appears_under_an_adapter_scripts_dir` guards it); the fixture tree has neither protection.

  **Correction to note:** `.gitignore` *does* already cover `__pycache__/` and `*.pyc` (lines 32–33), so the debris is invisible to `git status` — the tree reads clean. That is precisely what makes this easy to miss: the pollution is git-ignored but still visible to `hash_tree`'s `rglob`.
- **Suggested fix:** Two parts.
  1. Clear the debris: `find tests/fixtures/minimal-canon -name __pycache__ -type d -exec rm -rf {} +`
  2. Make it un-recurrable: in `tests/test_build_adapters.py`, inside `hash_tree`'s `for path in sorted(root.rglob("*")):` loop (line ~98), insert `if "__pycache__" in path.parts or path.suffix == ".pyc": continue` before the `if path.is_file():` branch, and extend the docstring to note bytecode is excluded because the generator is separately asserted never to emit it. Add a regression test that writes a `.pyc` under a **copied** fixture's `expected-adapters/claude/scripts/__pycache__/` and asserts `hash_tree` ignores it.

  Verify by running `bash scripts/validate.sh` **twice in succession** — both runs must exit 0.
- **References:** `scripts/validate.sh:210-216`, `:384-393`; `tests/test_build_adapters.py:90-102`, `:139-142`, `:202-215`; `specs/stage-exit-coverage/07-testing-strategy.md` §8.2, §9
- **Checklist:** CHECK-I16

### V-002: `state-verify --status skipped` is mandated in two skills but has no scripted call site there

- **Severity:** gap
- **Location:** `skills/forge-5-loop/SKILL.md` Step 5b (line ~268); `skills/forge-4-backlog/SKILL.md` Step 6 item 4 (line ~150)
- **Issue:** The feature's central invariant, stated verbatim in `skills/forge-verify/SKILL.md` Step 6 and `references/shared-conventions.md`, is: *"Never hand-author a verify entry. Every `stages.forge-verify-*` transition is written by the `state-verify` verb."* Two skills still instruct a bare state mutation with no invocation:
  - `forge-5-loop` Step 5b: *"On **skip**, record `stages.forge-verify-impl.status` as `"skipped"` (mirrors `forge-4-backlog`'s skip handling)"* — the string `state-verify` appears nowhere in that file.
  - `forge-4-backlog` Step 6: *"…record `stages.forge-verify-backlog.status` as `"skipped"` in pipeline state."* — likewise absent.

  This is the walking-skeleton shape at the skill layer: the `skipped` write path is defined, tested, and reachable from exactly one caller (`skills/forge-6-docs/SKILL.md:53` has a correct fenced invocation), while two of the three mandated sites are prose. An agent following `forge-5-loop` Step 5b literally will hand-edit JSON — the exact failure this feature exists to eliminate. It also breaks the `--outcome skipped` precondition in `forge-verify` Step 7 ("*and that skip was persisted via `state-verify --status skipped`*"), and `forge-5-loop`'s "mirrors `forge-4-backlog`'s skip handling" cross-reference points at a site that is itself unwired, so neither end of the relationship holds.

  This branch was live during this very verification: had the impl-verify offer been declined, `forge-5-loop` Step 5b would have directed a hand-authored state write.
- **Suggested fix:** Add a fenced invocation at both sites, modeled on the `forge-6-docs` L48-58 block — portable-root prelude, then:
  ```
  python3 "$R/scripts/forge-session.py" state-verify \
    --feature "{feature}" --stage {forge-5-loop | forge-4-backlog} \
    --status skipped --specs-dir "{specsDir}"
  ```
  followed by the sentence *"Add `--epic "{epic}"` when this feature is an epic member — required, per the Pipeline State Protocol in `references/shared-conventions.md`."* (it must sit inside `tests/test_state_verb_call_sites.py`'s 12/8-line window or `validate.sh` red-gates), plus the exit-2 rule. Keep `forge-5-loop`'s "(mirrors `forge-4-backlog`'s skip handling)" cross-reference — after this fix it becomes true.

  Then extend `tests/test_state_verb_call_sites.py` with a guard asserting that any canon skill whose prose records a `forge-verify-*` status of `skipped` also carries a `state-verify --status skipped` fence, seeded with the three known sites and including a non-vacuity assertion. Both skills are mirrored into `adapters/*/skills/`, so re-run `python3 scripts/build-adapters.py` afterward or `validate.sh` step 6b will red-gate on drift.
- **References:** `skills/forge-6-docs/SKILL.md:48-58` (the correct pattern); `skills/forge-verify/SKILL.md` Step 7 outcome table; `references/shared-conventions.md` §"`state-verify`"; `tests/test_state_verb_call_sites.py`
- **Checklist:** CHECK-I22

### V-003: The capability-determination prose guard mandated by 07 §6.2 — with three named negative controls — never landed

- **Severity:** gap
- **Location:** `tests/` (no such test exists); prose under guard lives in `skills/forge-1-prd/SKILL.md:165`, `skills/forge-2-tech/SKILL.md:226`, `skills/forge-3-specs/SKILL.md:169`, `skills/forge-4-backlog/SKILL.md:167`, `skills/forge-verify/SKILL.md`, `skills/forge-fix/SKILL.md`, `references/shared-conventions.md`
- **Issue:** Spec `07-testing-strategy.md` §6.2 requires a canon test asserting, for every direct/outer skill's exit closure, that the capability prose (a) states clause (b) as *permitted dispatch, not a listed tool*, (b) states that a consent-gated dispatch with a question mechanism is `interactive` — with `manual` reserved for *no question mechanism **and** no permitted dispatch* — and (c) states that an auto-verify directive under a no-unsolicited-dispatch bar goes through the gate and is dispatched on the affirmative. It further requires **three negative controls that must fail the guard**: rewrite the clause to tool-presence wording; downgrade the consent case to `manual`; delete the auto-path-through-gate sentence.

  The spec flags this as the highest-risk item in the feature: *"the one contract in the feature that has already been misread once, is prose-only, and degrades silently — a model self-reporting `manual` merely prints a copy-paste command, so nothing else catches it."*

  The prose is present in all seven canon files, but **no test asserts any of it.** Greps across `tests/` for `"not a listed tool"`, `"permitted dispatch"`, `"Standard Verify Gate"`, `"Verify now"`, `"Skip for now"`, `"choice 2 omitted"`, `"unsolicited"`, and `"consent"` all return zero hits. `tests/test_stage_exit_protocol.py::_assert_exit_contract` — the natural home, as it already reads each covered skill's canon surface — checks the stamp, `owner:` tokens, the terminal-print instruction, sentinel absence, and the outcome domain, but nothing about capability. Every capability test in `tests/test_stage_exit.py` exercises the *given* `--verify-capability` value, which §8.1 explicitly calls only half the contract: *"Without both, this line would claim coverage the suite does not have."* The "100% host/capability behavior coverage" claim in §8.1 is therefore currently unsupported.
- **Suggested fix:** Add `tests/test_capability_determination_prose.py` (stdlib only, unskippable, asserting against `skills/` and `references/`, never `adapters/`). Derive the surface list from `test_stage_exit_protocol.CANONICAL_EXIT_SITES` filtered to skills that pass `--verify-capability`, so it cannot become a second hand-maintained roster. Assert the three clause fragments per surface using short fragments that survive rewording (`"permitted** dispatch, not a listed tool"`, `` "`interactive`, not `manual`" ``, `"choice 2 omitted"`, `"never grounds to fence the production successor"`). Factor into `_assert_capability_prose(surface, where)` so the three spec-mandated negative controls can call it on mutated **copies** (never repository writes), each asserting it raises. Include a `test_this_guard_is_not_skippable` matching `tests/test_state_verb_call_sites.py:173-178`, and a non-vacuity floor asserting at least 6 surfaces were checked.
- **References:** `specs/stage-exit-coverage/07-testing-strategy.md` §6.2, §8.1, §3.4; `04-skill-integration.md` §3.2/§3.3; `02-stage-exit-routing.md` §4/§5.1; REQ-EXIT-07
- **Checklist:** CHECK-I17

### V-004: 07 §3.4's "advertised-then-unavailable dispatch" scenario is only one-third asserted

- **Severity:** gap
- **Location:** `tests/test_auto_verify.py:816-845` (`test_an_interrupted_dispatch_leaves_the_marker_readable_from_a_new_process`)
- **Issue:** Spec §3.4 specifies three assertions for a payload that advertised `runInStageVerify: true` and then hit `CLEAN_ROOM_UNAVAILABLE` or a non-answer: **(a)** the persisted `auto-verify-pending` debt is still readable and unresolved; **(b)** a fresh `stage-exit --verify-capability manual` yields a verify-first payload whose `primaryCommand` **is** the verify command; **(c)** the earlier payload's `deferredCommand`/`nextCommand` never becomes primary. The spec notes this mode is otherwise uncovered: *"the §7.2 negative for 'recovery incorrectly advancing to production' does not cover this … the stale-payload-reuse mode is otherwise untested."*

  The landed test covers (a) thoroughly. Its second half (lines 843-845) re-runs `stage-exit` but passes **no** `--verify-capability` and asserts only `verifyState` and `autoVerifyDebtRecorded` — it never asserts `primaryCommand`, so (b) is unproven under the specified `manual` capability and (c) is not asserted at all. `CLEAN_ROOM_UNAVAILABLE` appears nowhere in `tests/`. The failure this guards against — a stale payload's deferred production command being promoted after a dispatch silently failed — is exactly the dropped-pipeline-thread mode the feature exists to prevent.
- **Suggested fix:** Extend that test, or add a sibling `test_an_advertised_but_unavailable_dispatch_never_promotes_the_deferred_command`. After the first `_exit_ok(...)` captures `first = payload["directives"]`, perform no `state-verify`, then run `_exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech", "--verify-capability", "manual")` and assert: `second["primaryCommand"] == "/feature-forge:forge-verify widget"`, `second["primaryCommand"] != first["deferredCommand"]`, `second["verifyGate"] == "manual-print"`, and that `first["deferredCommand"]` does not appear inside a fence in `payload["nextSteps"]`.
- **References:** `specs/stage-exit-coverage/07-testing-strategy.md` §3.4; `04-skill-integration.md` §3.2; REQ-REL-02; `skills/forge-verify/SKILL.md` (require-clean sentinel path)
- **Checklist:** CHECK-I17

### V-005: Shipped runtime scripts carry ~146 spec-document provenance citations, violating the loop's own self-containment rule

- **Severity:** inconsistency
- **Location:** `scripts/forge-session.py` (118 spec-doc citations added); `scripts/epic-manifest.py` (+23); `eval/run-compliance-eval.py` (+5)
- **Issue:** The governing rule — shipped in this very commit set at `skills/forge-5-loop/SKILL.md:305` — states that artifacts the loop writes into the target repo *"must be **self-contained**: they must NOT reference feature-forge spec files … Specs are pre-implementation inputs that may be archived or deleted once the feature ships."* Measured against base `9a663e1`:

  | File | Base | HEAD | Delta |
  |---|---|---|---|
  | `scripts/forge-session.py` | 0 | 118 | **+118** |
  | `scripts/epic-manifest.py` | 71 | 94 | +23 |
  | `scripts/forge-bootstrap.py` | 49 | 49 | 0 (pre-existing, excluded) |
  | `eval/run-compliance-eval.py` | 0 | 5 | +5 |

  Three citation forms leaked: full spec filenames (e.g. `forge-session.py:268` `#: automatic verification (03-verification-state.md §5.3)`), numeric shorthand (104 occurrences of `NN §X.Y`, e.g. `:5079` `# --- Target selection: epic before the token map (03 §3.2). ---`), and `tech-spec §` citations (`:2711`, `:3110`).

  The sharpest instance is `scripts/forge-session.py:5020-5024`, in `state_verify`'s public docstring, which does not merely cite the spec but delegates normative authority to it:

  > *See the `03-verification-state.md` §3.3 matrix for which metadata each status requires and which it forbids — the matrix is authoritative, not this docstring.*

  Once `specs/stage-exit-coverage/` is archived, all ~146 references become dangling pointers, and this docstring in particular points a maintainer at nothing while explicitly disclaiming its own accuracy.

  The counterexamples prove the rule was achievable: `references/stage-exit-protocol.md` (416 lines rewritten), `references/shared-conventions.md` (+61 lines), and `eval/README.md` (+87 lines) all ship with **zero** such citations. The prose surfaces stayed clean; the Python surfaces did not.

  Deliberately excluded from this finding: pre-existing citations in `forge-bootstrap.py` and the 71 baseline citations in `epic-manifest.py`; citations in `backlog.json` and `specs/**` (correct by design); and uses in `skills/forge-3-specs/SKILL.md`, `skills/forge-4-backlog/SKILL.md`, and `findings-template.md` that name `00-core-definitions.md` as a *generated output filename convention*, not provenance.
- **Suggested fix:** Strip the spec **coordinates** while preserving the **substance** already written beside them — mechanically, delete the parenthetical, keep the sentence: `# --- Metadata validation that needs no state (03 §3.3). ---` → `# --- Metadata validation that needs no state. ---`. Work from:
  ```
  grep -nE '\b0[0-7] §[0-9]|0[0-7]-(core-definitions|architecture-layout|stage-exit-routing|verification-state|skill-integration|config-and-distribution|compliance-and-coverage|testing-strategy)\.md|tech-spec §'
  ```
  Three cases carry load-bearing content and need rewriting rather than deletion:
  1. `forge-session.py:5020-5024` — rewrite `state_verify`'s docstring to state the metadata matrix itself (or point at the shipped `references/pipeline-state-schema.json`), and delete the "the matrix is authoritative, not this docstring" clause outright. Shipped code must not disclaim its own contract in favor of an archivable file.
  2. `forge-session.py:305` (`07-testing-strategy.md §3 asserts the literal`) → name the shipped guard: `tests/test_stage_exit.py asserts the literal`.
  3. `forge-session.py:2711`, `:3110` (`tech-spec §3.5 forbids`) → restate the constraint directly, e.g. "dependency and completion derivation belong to `epic-manifest.py`; duplicating them here is forbidden."

  Then re-run `python3 scripts/build-adapters.py` so the six verbatim script copies pick up the edits.
- **References:** `skills/forge-5-loop/SKILL.md:305` (the rule); `references/stage-exit-protocol.md`, `eval/README.md` (compliant counterexamples); base commit `9a663e1`
- **Checklist:** CHECK-I13, CHECK-I19

### V-006: The `stage-exit` synopsis in `forge-session.py`'s module docstring — the tool's own `--help` output — omits every flag this feature added

- **Severity:** inconsistency
- **Location:** `scripts/forge-session.py` lines 16–17 (module docstring, rendered as argparse's `description`)
- **Issue:** The synopsis still reads:
  ```
  python3 forge-session.py stage-exit --feature F --stage S [--specs-dir DIR] \
      [--config FILE] [--epic E] [--next-feature N] [--host claude|generic] [--json]
  ```
  The parser at lines 5450–5480 additionally accepts `--owner`, `--outcome`, `--verify-mode`, `--served-stage`, and `--verify-capability` — all five introduced by this feature (item 010), and all five required of the nine skills. It also still says `--host claude|generic` while `EXIT_HOSTS` (line 2042) is now `("claude", "generic", "pi")`. Confirmed by running `python3 scripts/forge-session.py --help`: the stale line prints as the top-level description, immediately above a `stage-exit --help` that lists all five flags. The sibling `state-verify` synopsis (lines 38–40) *was* updated correctly, making this an isolated miss on the one verb the feature reworked most. Anyone reading `--help` to learn the exit contract sees a signature that cannot produce a valid owner-aware exit.
- **Suggested fix:** Replace the two-line synopsis with:
  ```
  python3 forge-session.py stage-exit --feature F --stage S [--owner direct|nested] \
      [--outcome O] [--verify-mode M] [--served-stage S] \
      [--verify-capability interactive|manual] [--specs-dir DIR] [--config FILE] \
      [--epic E] [--next-feature N] [--host claude|generic|pi] [--json]
  ```
  Optionally add a parity guard in `tests/test_stage_constants_parity.py` asserting every `p_exit.add_argument("--…")` long option appears in `__doc__`, so the synopsis cannot drift again. Regenerate adapters afterward.
- **References:** `scripts/forge-session.py:5450-5480` (`p_exit` registration), `:2042` (`EXIT_HOSTS`), `:38-40` (the correctly-updated `state-verify` synopsis); `02-stage-exit-routing.md` §2.2
- **Checklist:** CHECK-I09, CHECK-I22 *(flagged independently by the integration and runnability dimensions; merged here)*

### V-007: `autoVerifyStages` is documented as a hard "config error" but shipped as a non-fatal advisory

- **Severity:** inconsistency
- **Location:** `README.md` line 368 and `references/forge-config-schema.json` (`properties.autoVerifyStages.description`), versus `references/stage-exit-protocol.md` §"`invalidAutoVerifyKeys` (non-empty)" (lines 208–212) and `scripts/forge-session.py:283-291`
- **Issue:** The two config surfaces a user actually reads both promise a hard failure — `README.md`: *"an unknown key is a **config error**, surfaced by the navigator, not a silent no-op"*; the schema: *"a typo (e.g. 'forge-1-prod') is a **schema error**, not a silent no-op."* The shipped behavior is the opposite. `references/stage-exit-protocol.md:212` states flatly *"They never fail the exit"*, and the implementing comment at `forge-session.py:285-287` is explicit that this is intentional: *"WITHOUT failing the exit: an ignored config key is an advisory, not a usage error."* There is no runtime schema validation (the project forbids `jsonschema` at runtime), so the schema's "schema error" claim never fires either. A user who mistypes `autoVerifyStages: {"forge-1-prod": false}` is told to expect a failure, gets a warning and a silently-unapplied override, and reasonably concludes the override took effect.

  The README wording predates this loop, but the loop implemented the advisory semantics at the `stage-exit` boundary and shipped a second, contradicting authoritative document — so the contradiction is now between two live surfaces rather than latent.
- **Suggested fix:** Reword both documentation surfaces to match shipped behavior; change no code, as the fail-open behavior is the deliberate, spec-backed choice.
  - `README.md:368` → "an unknown key is **ignored with a warning**, never silently — the navigator and every scripted stage exit print one line per offending key (in sorted order), and the exit still succeeds."
  - `forge-config-schema.json` → "…so a typo (e.g. `forge-1-prod`) is reported as an ignored key rather than silently taking no effect. It does not fail the command."

  Leave `README.md:368`'s "five verify-capable stages (`forge-1-prd`…`forge-5-loop`)" clause alone — it is correct, since `_invalid_auto_verify_keys` validates against the 5-entry `VERIFY_TOKEN_BY_STAGE`, not the 6-entry `VERIFY_STAGES`.
- **References:** `scripts/forge-session.py:283-291`, `:1233-1246`, `:227-239`; `references/stage-exit-protocol.md:208-212`; `skills/forge/SKILL.md:44,91` (navigator wording, which correctly says "they are ignored")
- **Checklist:** CHECK-I20, CHECK-I18

### V-008: 07 §4.4 names a must-keep test that landed under a different name

- **Severity:** inconsistency
- **Location:** `specs/stage-exit-coverage/07-testing-strategy.md` §4.4 line 558; landed test at `tests/test_state_schema_conformance.py:680`
- **Issue:** §4.4 says *"Keep `test_the_contract_digest_ignores_prose_but_not_structure` intact — it is the negative control that makes the digest meaningful, and an implementer told merely to 'replace' the digest may delete it alongside (REQ-DEBT-06)."* No test by that name exists. The negative control **did** land, and is stronger than specified — `test_the_contract_comparison_ignores_prose_but_not_structure` proves prose edits move neither the digest nor the `verifyEntry` object, that dropping an enum value outside `verifyEntry` does move the digest, and that an unintended fourth edit inside `verifyEntry` does fail the object comparison. Only the name drifted (`digest` → `comparison`, correctly reflecting the split into a digest half plus a parsed-object half). The risk is narrow but exactly what the sentence was written to prevent: a reader grepping the spec-named symbol finds nothing and concludes the guard was deleted.
- **Suggested fix:** In §4.4, rename to `test_the_contract_comparison_ignores_prose_but_not_structure` and append: "(the digest was split into a digest over the contract outside `verifyEntry` plus a parsed-object comparison of `verifyEntry` itself; the negative control covers both halves)." Also update the surrounding sentence, which still says `PRE_R4_SCHEMA_CONTRACT_SHA256` — the constant is now `SCHEMA_CONTRACT_OUTSIDE_VERIFY_ENTRY_SHA256` and was deliberately not re-pinned.
- **References:** `tests/test_state_schema_conformance.py:490-712`; REQ-DEBT-06
- **Checklist:** CHECK-I17

### V-009: No repository gate prevents spec-citation leakage from recurring

- **Severity:** improvement
- **Location:** `scripts/check-spec-purity.py`, rules 1–6
- **Issue:** The repo already runs a purity gate over canonical surfaces on every `bash scripts/validate.sh`, and this feature extended it (Rule 6, the `$R`-binding companion to Rule 5). But no rule covers the self-containment constraint that `skills/forge-5-loop/SKILL.md:305` states as a hard requirement — which is exactly why V-005 could grow from 0 to 118 citations in a single script across 32 unattended commits without anything going red. The gate's charter (mechanically enforceable canon invariants over `skills/`, `scripts/`, `references/`) fits this rule precisely.
- **Suggested fix:** Add Rule 7: fail when any file under `scripts/`, `references/`, `skills/`, or `eval/` matches `\b0[0-9]-[a-z-]+\.md\b`, `\b0[0-9] §[0-9]`, or `\btech-spec §`, with an explicit allowlist for the legitimate generated-filename-convention uses in `skills/forge-3-specs/SKILL.md`, `skills/forge-4-backlog/SKILL.md`, and `skills/forge-verify/references/findings-template.md`. Follow the Rule 5 / Rule 6 signature and the `0 ok / 1 canon-error|drift / 2 usage` exit split; add coverage in `tests/test_check_spec_purity.py`. Land this only after V-005's cleanup, or it fails immediately.
- **References:** V-005; `scripts/check-spec-purity.py` Rule 5/6 as the structural template
- **Checklist:** CHECK-I13

### V-010: "On exit 2 nothing was recorded" is stated unqualified, but `stage-exit` can persist debt before an exit 2

- **Severity:** improvement
- **Location:** `skills/forge-verify/SKILL.md` line 249, `skills/forge-fix/SKILL.md` line 87; `references/stage-exit-protocol.md` lines 62–65
- **Issue:** For `state-verify` the guarantee is genuinely airtight and was confirmed: every mode-exclusivity, metadata, containment, and staleness check in `state_verify` (`forge-session.py:5045-5190`) raises `UsageError` **before** the single `_commit_state` call, and `_write_state` is mkstemp + fsync + `os.replace` with the temp file unlinked on failure. The wording around it is the problem. First, the same sentence asserts both *"nothing was recorded"* and *"authoritative state is unknown"* — a definite guarantee and a claim that the guarantee cannot be relied on. Second, the guarantee is scoped to `state-verify`, but `references/stage-exit-protocol.md:62-65` describes `stage-exit`'s exit-2 behavior in adjacent terms without noting that `stage-exit` has a **deliberate** pre-payload write: `forge-session.py:3549-3557` schedules the `auto-verify-pending` debt marker at the scheduling boundary before the payload exists, so a later `UsageError` on the same call exits 2 with that debt already durable. That is correct fail-safe design, but a skill author generalizing "exit 2 → nothing was recorded" to `stage-exit` could retry or roll back on a false assumption.
- **Suggested fix:** Two edits. (1) In both skill bodies, replace "— authoritative state is unknown, so no success block may be printed" with "— the verify entry is unchanged, so no success block may be printed." (2) After `references/stage-exit-protocol.md:65`, add: "An exit 2 from `stage-exit` itself is **not** a no-write guarantee: the `auto-verify-pending` debt marker is persisted at the scheduling boundary *before* the payload is built, deliberately, so an interrupted exit still leaves the verification obligation durable on disk. Do not retry on the assumption that nothing landed — the marker is idempotent and the re-run will read it."
- **References:** `scripts/forge-session.py:3549-3557`, `:3995-4032`, `:5045-5190`, `:560-567`
- **Checklist:** CHECK-I14

### V-011: The call-site guard's window bounds are unpinned, and its failure message describes only half the window

- **Severity:** improvement
- **Location:** `tests/test_state_verb_call_sites.py:44-53` and `:110-114`
- **Issue:** Not a correctness defect — the guard works, and the window is genuinely exercised (max lookbehind consumed is 10 of 12). Two durability weaknesses. First, the module's own comment records a real historical hole (*"at 20 the window reached past a block's own mandate into the PRECEDING block's … Widening this re-opens that hole"*), but nothing enforces the bound: a future edit raising `LOOKBEHIND` to 20 to "fix" a red test would silently restore the hole with every test still green. Second, the failure message says "within {LOOKBEHIND} lines above", but `_call_sites` builds an asymmetric window `lines[index-12 : index+8]` — 4 of the 32 sites are satisfied by an `--epic` occurrence **below** the call line (offset +4), so the message misdescribes how the guard actually passed.
- **Suggested fix:** Add `test_the_window_is_no_wider_than_the_measured_maximum` asserting `LOOKBEHIND <= 12 and LOOKAHEAD <= 8`, with a comment pointing at the documented regression; optionally compute the maximum offset actually consumed across `_call_sites()` and assert `LOOKBEHIND <= max_used + 3` so slack cannot accumulate. Reword the assertion message to "within {LOOKBEHIND} lines above or {LOOKAHEAD} lines below".
- **References:** `references/shared-conventions.md` (Pipeline State Protocol, `--epic` mandate); `07-testing-strategy.md` §6.2
- **Checklist:** CHECK-I17

### V-012: 57 acceptance criteria assert command *history* rather than an inspectable artifact state

- **Severity:** improvement
- **Location:** `specs/stage-exit-coverage/backlog.json` — all 32 items; the recurring AC pair about `build-adapters.py` having been run and about `validate.sh` output
- **Issue:** 318 of 375 acceptance criteria are directly code-readable. The remaining 57 (15%, spread across all 32 items) are past-tense process assertions. The `build-adapters` half has a sound artifact-level proxy — `build-adapters.py --check` exits 0, confirmed — so it is verifiable in practice. The `validate.sh` half is not: its second clause (*"if it shows `SKIP: pytest not installed`, `python3 -m pytest tests -q` was run explicitly and passed"*) leaves no trace on disk, so a reviewer cannot distinguish "the suite ran green" from "the suite was skipped and the fallback silently was not run." The escape hatch is currently dormant — pytest is importable here, so `scripts/validate.sh:212` takes the `PASS` branch — which is why this is an improvement rather than a gap. It matters for future features generated from the same AC template, where a CI image without pytest would make roughly a third of every item's ACs vacuously satisfiable.
- **Suggested fix:** Either (a) preferred — replace the conditional clause in the backlog AC template with the artifact-level assertion alone ("`bash scripts/validate.sh` output shows `PASS: epic-manifest pytest suite`") and add a one-time guard asserting `importlib.util.find_spec("pytest") is not None`, so the SKIP branch can never be reached silently; or (b) cheaper — make `scripts/validate.sh`'s `SKIP: pytest not installed` branch (line ~218) a hard failure, which makes the first clause the only reachable outcome and lets the conditional be deleted. Apply the chosen wording to the backlog AC template so future features inherit it. Do not touch item `status` or `completedAt` fields.
- **References:** `scripts/validate.sh:212`, `:218`; `01-architecture-layout.md` §6
- **Checklist:** CHECK-I07, CHECK-I05

### V-013: `01-architecture-layout.md` §2 "Complete File Layout" omits two test files the implementation modified

- **Severity:** improvement
- **Location:** `specs/stage-exit-coverage/01-architecture-layout.md` §2, `tests/` block (lines 95–107)
- **Issue:** §2 is titled a *Complete* File Layout and its own Verification checkbox reads "Every path in §2 is accounted for by the implementation diff." The forward direction holds; the reverse does not. `git diff 9a663e1..HEAD` modifies `tests/test_doctor.py` (+62) and `tests/test_rank_features.py` (+63), neither of which appears in §2. These are not incidental — item 008's AC requires the auto-pending diagnostic sentence in navigator, `rank-features`, and `doctor` output, and the added tests assert exactly that. The code is correct and the ACs are met; only the spec's inventory is incomplete.
- **Suggested fix:** Add two rows to the `tests/` block in the existing two-column style — `test_doctor.py  M  auto-pending label in doctor output` and `test_rank_features.py  M  auto-pending obligation in rank rows`. Alternatively, if §2 lists only files whose *ownership* the document fixes, soften the heading to "Primary File Layout" and note that read-side diagnostic tests inherit their changes from §4's classifier consumers.
- **References:** `01-architecture-layout.md` §2 and §Verification; `backlog.json` item 008 AC 6; `03-verification-state.md` §5.3
- **Checklist:** CHECK-I01, CHECK-I05

### V-014: Item 018's "anywhere under `skills/`" AC is met in substance but catches a pre-existing out-of-scope reference

- **Severity:** improvement
- **Location:** `skills/forge-0-epic/references/edit-mode.md` line 63; `skills/forge-0-epic/SKILL.md` line 268
- **Issue:** Item 018's AC reads *"no `.epic-state.json` write recipe, `tempfile.mkstemp` call, or `os.replace` snippet survives anywhere under `skills/`."* The substantive requirement is satisfied: `grep -rn "tempfile\|mkstemp" skills/` returns nothing, the `.epic-state.json` write recipe now routes through `state-verify`, and the base-commit line at `edit-mode.md:172` was correctly removed. Two `os.replace` mentions remain. `forge-0-epic/SKILL.md:268` is harmless — it describes `epic-manifest.py`'s internal atomicity, is not an instruction, and is byte-identical at base. `edit-mode.md:63` is the substantive one: it still instructs flipping an `epicChangeRequests[]` item from `open` to `applied` *"using the same atomic temp-file + `os.replace` write the skill uses for any state edit."* It predates the loop, targets a member `.pipeline-state.json` field rather than `.epic-state.json`, and there is genuinely no verb for it — `state-ecr` only *appends* an open request (`cmd_state_request`), with no status-flip mode. This is residue from the prior `epic-orchestration` feature that item 018's broadly-worded AC happens to catch, not a defect this loop introduced.
- **Suggested fix:** For this feature, (a) narrow item 018's AC to its intended scope — "…survives under `skills/forge-verify/` or `skills/forge-fix/`" — so it stops reporting pre-existing out-of-scope residue. Optionally (b) file a follow-up item to add an `--apply`/`--status` mode to `state-ecr` and replace the hand-rolled write instruction, which would let the AC be honored literally. (a) is the correct action here; (b) is a genuine future improvement, not a defect in this feature.
- **References:** `backlog.json` item 018 AC 8; `skills/forge-0-epic/references/edit-mode.md:61-67`; `scripts/forge-session.py:4735` (`cmd_state_request`); base commit `9a663e1`
- **Checklist:** CHECK-I05

### V-015: `--status auto-verify-pending` is exposed on the `state-verify` CLI but no skill or reference ever passes it

- **Severity:** improvement
- **Location:** `scripts/forge-session.py:5610` (`--status` domain = `VERIFY_RESULT_STATUSES`)
- **Issue:** `VERIFY_RESULT_STATUSES` derives from `get_args(VerifyStatus)` minus `pending`, so `auto-verify-pending` is an accepted `--status` value. Grepping all of `skills/` and `references/` for it returns zero hits. The value is not orphaned at runtime — `stage_exit` writes it internally (observed: a bare `stage-exit --stage forge-0-epic` produced `.epic-state.json` with `forge-verify-epic.status: "auto-verify-pending"`) — so this is **not** a walking-skeleton gap. But it does mean an operator can hand-schedule debt through a path no skill takes and no fence documents, which weakens the "one writer for scheduling" story. A judgment call, not a defect: the uniform derivation from `VerifyStatus` is defensible and arguably preferable to a hand-listed carve-out.
- **Suggested fix:** Either (a) document in `references/shared-conventions.md` §"`state-verify`" that `auto-verify-pending` is written only by `stage-exit`'s scheduling boundary and is exposed for repair/inspection, not skill use; or (b) if the specs intend it to be exit-owned exclusively, subtract it from `VERIFY_RESULT_STATUSES` alongside `pending` and note why. (a) is lower-risk and preserves the derived-not-listed property the surrounding code values.
- **References:** `scripts/forge-session.py:387-393`, `:258-261` (`_VERIFY_RESOLVED`, which deliberately excludes it)
- **Checklist:** CHECK-I22

### V-016: The rewritten protocol's canonical stamp hardcodes `--host claude` above prose insisting the host varies

- **Severity:** improvement
- **Location:** `references/stage-exit-protocol.md` line 87 (inside the `scripted-stage-exit-stamp` fence) versus lines 98–132 (§"Host and capability determination")
- **Issue:** The stamp reads `… --specs-dir "{specsDir}" --host claude --verify-capability "{verify-capability}"`. Every other varying token in that line is a placeholder; `--host` alone is a literal. Forty lines below, the same newly-written file insists the host varies: *"a capable Pi session is `--host pi --verify-capability interactive`."* A reader of the pi bundle sees both, at `adapters/pi/references/stage-exit-protocol.md:87` and `:129`.

  Verified **not** a functional defect and **not** a regression: `scripts/build-adapters.py:776,878` translates `--host claude` → `--host generic`/`--host pi` in skill **bodies**, and the emitted bodies are correct (`adapters/pi/skills/forge-1-prd/SKILL.md:171` has `--host pi`). `references/` subtrees are copied verbatim by explicit design, documented at `tests/test_adapter_host_neutrality.py:10-16`. The literal was present at base. This is a readability observation about newly-authored prose; declining it is legitimate.
- **Suggested fix:** Prefer (b): leave the literal and add a one-line note under the fence — "The stamp is shown with `--host claude`; the adapter build substitutes `pi`/`generic` per target, and §'Host and capability determination' below governs the value." Option (a) — changing the literal to `--host {host}` and adding `{host}` to the stamp-slot paragraph — is riskier, since `tests/test_stage_exit_protocol.py` compares stamp sites byte-for-byte and the generator keys its substitution on the literal string `--host claude`.
- **References:** `scripts/build-adapters.py:773-776,858,876-878`; `tests/test_adapter_host_neutrality.py:10-16`; `references/stage-exit-protocol.md:36-38`
- **Checklist:** CHECK-I15, CHECK-I18

### V-017: Four substantive ruff violations in `tests/`, a dependent module outside the configured lint scope

- **Severity:** improvement
- **Location:** `tests/test_forge_bootstrap.py:733`, `tests/test_stage_exit.py:2362`, plus 18 E501s across `tests/`; scope decision in `ruff.toml`
- **Issue:** `ruff.toml` documents that `scripts/*.py` and `eval/*.py` are the lint targets and that `tests/` and generated `adapters/` are excluded; `validate.sh` step 7b and the CI quality gate both run only `ruff check scripts/ eval/`. `tests/` is nonetheless a real dependent (it imports `forge-session.py` via `importlib`), and running ruff over it out of band surfaces 21 violations: 18 E501, 1 E402, 1 **F841** (`test_forge_bootstrap.py:733` — `worker = tmp_path / "packages" / "worker"` assigned and never used; the test asserts on the literal `"packages/worker"` instead, so the binding is dead), and 1 **F541** (`test_stage_exit.py:2362` — an f-string with no placeholder). Several sit in files this feature modified. None affects correctness and none blocks the gate; this is a pre-existing documented scope decision, not a loop regression. Flagged so the decision stays conscious.
- **Suggested fix:** Either (a) leave as-is and add one sentence to `ruff.toml`'s comment recording *why* `tests/` is excluded, or (b) delete the dead binding and drop the two no-placeholder `f` prefixes — the only two non-cosmetic hits. Do **not** widen the lint target to `tests/` without also fixing the 18 E501s, or `validate.sh` will red-gate.
- **References:** `ruff.toml`; `scripts/validate.sh` step 7b; `.github/actions/quality-gate/action.yml` step 4
- **Checklist:** CHECK-I12

### V-018: `smokeCommand` is `null` — no end-to-end smoke exists for the one surface `validate.sh` cannot reach

- **Severity:** not-applicable (advisory, per the CHECK-I21 degradation rule)
- **Location:** `forge.config.json` line 11
- **Issue:** Per CHECK-I21 this is advisory, not a failure — nothing was run and nothing fabricated. But it bites unusually hard here. The project's `testCommand` (`bash scripts/validate.sh`) is entirely static + pytest, and every step invokes the scripts as `python3 "$REPO_ROOT/scripts/…"` from the **source checkout**. The path a real user hits is different: `forge-root.sh` resolution from an *installed* location, then `python3 "$R/scripts/forge-session.py"`. `skills/forge-5-loop/SKILL.md` §Gotchas documents exactly this divergence — a source checkout is not on the discovery list, so the helper exits "cannot locate plugin root." That is this project's analogue of the module-graph-identity failure mode CHECK-I21 names: the graph the gate exercises is not the graph the request path loads.
- **Suggested fix (for the user to configure — do not auto-apply):** Add `scripts/smoke.sh` and set `"smokeCommand": "bash scripts/smoke.sh"`. It should drive one happy path end-to-end through the installed surface in a throwaway `TMPDIR`:
  1. Stage the repo into a temp dir laid out as an install (e.g. `$TMP/.claude/skills/feature-forge/`), resolve through the real prelude, and assert `$R` is non-empty and points at the staged install, not the checkout.
  2. `state-enter` → `state-complete` → `stage-exit --stage forge-1-prd --verify-capability manual`; assert exit 0 and that stdout's last line is exactly `─ forge: end of stage ─`.
  3. `state-verify --stage forge-1-prd --status passed --findings-count 0 --verified-stage-version 1`, then `stage-exit --stage forge-verify --owner direct --outcome passed --verify-mode prd`; assert exit 0.
  4. Assert the resulting `.pipeline-state.json` validates against `references/pipeline-state-schema.json`.

  Consider an `--host pi` variant, since `EXIT_HOSTS` now carries three hosts. Do not wire it into `validate.sh` — the smoke is CHECK-I21's surface, not the test gate's.
- **References:** `scripts/validate.sh`; `scripts/forge-root.sh`; `references/forge-config-schema.json`; `tests/test_smoke_command.py`; `skills/forge-5-loop/SKILL.md` §Gotchas
- **Checklist:** CHECK-I21

---

## Fix Execution Plan

### User Decisions Required

1. **Do test files fall under the self-containment rule (V-005)?** `tests/*.py` carries ~53 spec citations, ~30 added by this loop. Arguments both ways: tests ship in the repo and outlive the specs, which argues for stripping; but a test docstring citing the spec section it pins is the clearest statement of *what invariant it protects*, and `skills/forge-5-loop/SKILL.md:305` names only "source code, generated `SKILL.md`/agent files, configs, code comments." **Recommendation: leave tests as-is**, and scope V-005 and V-009's Rule 7 to `scripts/`, `references/`, `skills/`, `eval/`.
2. **`REQ-*` identifiers: strip or keep (V-005)?** `forge-session.py` went 0 → 72 `REQ-XXX-NN` references. These trace to `PRD.md`, equally archivable, but they name a *requirement* rather than a document coordinate and are the project's traceability spine. **Recommendation: keep them**, and exclude `REQ-` from Rule 7's pattern.
3. **V-012:** choose (a) tighten the backlog AC template plus a `find_spec("pytest")` guard, or (b) make `validate.sh`'s missing-pytest branch fatal. (b) changes repository-wide gate behavior.
4. **V-014:** choose (a) narrow item 018's AC (correct for this feature), or (b) additionally file a follow-up for a `state-ecr` status-flip mode.
5. **V-015:** choose (a) document the CLI exposure, or (b) narrow the enum. Default (a).
6. **V-016 is optional** and documented-by-design; declining is legitimate. If taken, prefer option (b).

### Execution Steps

#### Step 1: Clear the fixture debris and make it un-recurrable
- **Files:** `tests/fixtures/minimal-canon/**/__pycache__/` (delete), `tests/test_build_adapters.py`
- **Addresses:** V-001
- **Action:** `find tests/fixtures/minimal-canon -name __pycache__ -type d -exec rm -rf {} +`. In `hash_tree`'s `rglob` loop, insert `if "__pycache__" in path.parts or path.suffix == ".pyc": continue` before the `if path.is_file():` branch, and extend the docstring to explain why. Add a regression test that writes a `.pyc` under a **copied** fixture and asserts `hash_tree` ignores it. `.gitignore` already covers `__pycache__/` and `*.pyc` (lines 32–33) — no change needed there. Verify with `bash scripts/validate.sh` run **twice in succession**; both must exit 0.
- **Depends on:** none — **do this first**, or any later step's gate run will show a red suite and be misattributed.

#### Step 2: Wire the two missing `state-verify --status skipped` call sites
- **Files:** `skills/forge-5-loop/SKILL.md` (Step 5b), `skills/forge-4-backlog/SKILL.md` (Step 6 item 4)
- **Addresses:** V-002
- **Action:** Replace the bare prose instruction at each site with a fenced invocation copied structurally from `skills/forge-6-docs/SKILL.md:48-58` — portable-root prelude, the `state-verify … --status skipped` call, the `--epic` sentence (must sit inside the 12/8-line window), and the exit-2 rule. Keep forge-5-loop's "(mirrors `forge-4-backlog`'s skip handling)" cross-reference.
- **Depends on:** Step 1

#### Step 3: Add the guard that keeps the skip fence from being dropped again
- **Files:** `tests/test_state_verb_call_sites.py`
- **Addresses:** V-002
- **Action:** Assert that any canon skill whose prose records a `forge-verify-*` status of `skipped` also contains a `state-verify --status skipped` invocation in the same file. Seed with the three known sites; include a non-vacuity assertion in the negative-test style of `tests/test_stage_exit_protocol.py`.
- **Depends on:** Step 2

#### Step 4: Add the capability-determination prose guard with its three negative controls
- **Files:** new `tests/test_capability_determination_prose.py`
- **Addresses:** V-003
- **Action:** Per V-003's suggested fix. Import `CANONICAL_EXIT_SITES` from `tests/test_stage_exit_protocol.py` and filter to surfaces containing `--verify-capability`, so the roster is derived rather than hand-maintained. Factor assertions into `_assert_capability_prose(surface, where)` so the three negative controls operate on mutated copies. Include `test_this_guard_is_not_skippable` and a non-vacuity floor of at least 6 surfaces.
- **Depends on:** Step 1

#### Step 5: Complete the advertised-then-unavailable dispatch coverage
- **Files:** `tests/test_auto_verify.py`
- **Addresses:** V-004
- **Action:** Per V-004's suggested fix — capture the first payload's directives, then assert properties (b) and (c) on a fresh `stage-exit --verify-capability manual`. Place immediately after `test_an_interrupted_dispatch_leaves_the_marker_readable_from_a_new_process`.
- **Depends on:** Step 1

#### Step 6: Strip spec-document coordinates from shipped Python
- **Files:** `scripts/forge-session.py`, `scripts/epic-manifest.py`, `eval/run-compliance-eval.py`
- **Addresses:** V-005
- **Action:** Per V-005's suggested fix. Most are mechanical parenthetical deletions driven by the grep given there. Handle the three load-bearing cases individually, starting with `forge-session.py:5020-5024`. Leave `REQ-*` IDs and `tests/` untouched pending Decisions 1 and 2. Do not touch `scripts/forge-bootstrap.py` (no new citations).
- **Depends on:** Decisions 1 and 2

#### Step 7: Refresh the `stage-exit` synopsis
- **Files:** `scripts/forge-session.py` (module docstring, lines 16–17)
- **Addresses:** V-006
- **Action:** Replace with the corrected synopsis from V-006. Optionally add the `p_exit`-options-appear-in-`__doc__` parity guard to `tests/test_stage_constants_parity.py`. Verify with `python3 scripts/forge-session.py --help`.
- **Depends on:** none

#### Step 8: Correct the documentation contradictions
- **Files:** `README.md` (line 368), `references/forge-config-schema.json`, `skills/forge-verify/SKILL.md` (line 249), `skills/forge-fix/SKILL.md` (line 87), `references/stage-exit-protocol.md` (after line 65), `specs/stage-exit-coverage/07-testing-strategy.md` §4.4, `specs/stage-exit-coverage/01-architecture-layout.md` §2
- **Addresses:** V-007, V-008, V-010, V-013
- **Action:** Apply each finding's suggested wording. All are text-only; no code changes. `tests/test_stage_exit_protocol.py` asserts the stamp block, not surrounding prose, so the protocol paragraph addition is safe — verify anyway.
- **Depends on:** none

#### Step 9: Apply the decided backlog and spec AC adjustments
- **Files:** `specs/stage-exit-coverage/backlog.json`; possibly `scripts/validate.sh`, `references/shared-conventions.md`
- **Addresses:** V-012, V-014, V-015
- **Action:** Apply the user's choices from Decisions 3, 4, and 5. Do not modify item `status` or `completedAt` — all 32 items remain `done`.
- **Depends on:** Decisions 3, 4, 5

#### Step 10: Regenerate adapters and re-run the gate
- **Files:** `adapters/**` (generated)
- **Addresses:** V-002, V-005, V-006, V-007, V-010
- **Action:** Run `python3 scripts/build-adapters.py`, confirm the six copies change in lockstep with canon, then `bash scripts/validate.sh` **twice** — both must exit 0 and print `PASS: epic-manifest pytest suite` (a `SKIP` is not a pass). Then `ruff check scripts/ eval/`. Expect the test count to rise by roughly 12–16 from Steps 3, 4, 5.
- **Depends on:** Steps 1–9

#### Step 11 (optional, gated on Step 6 landing): Add the spec-purity Rule 7
- **Files:** `scripts/check-spec-purity.py`, `tests/test_check_spec_purity.py`
- **Addresses:** V-009
- **Action:** Per V-009, scoped per Decisions 1 and 2, with the three allowlist entries. The gate red-fails until V-005's cleanup has landed, so sequence it last.
- **Depends on:** Step 6, Step 10

#### Step 12 (deferred — needs user decision): Configure a smoke command
- **Files:** `forge.config.json`, new `scripts/smoke.sh`
- **Addresses:** V-018
- **Action:** Only after the user accepts. Implement the four-phase installed-surface smoke described in V-018. Do not wire it into `validate.sh`.
- **Depends on:** user decision

#### Step 13 (optional): Clarify the stamp's `--host` literal
- **Files:** `references/stage-exit-protocol.md`
- **Addresses:** V-016
- **Action:** Apply option (b) — the one-line note under the fence. Do not modify the fenced line itself unless option (a) is chosen deliberately.
- **Depends on:** Decision 6
