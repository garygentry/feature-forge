# Progress — context-efficiency

## Item 001 — extract six per-mode checklists + findings-template.md

- All seven files were produced by `sed -n 'START,ENDp'` over the monolith, so the
  extracted bodies are provably byte-identical to their source spans. Every mode file
  has a **fixed 6-line header** (title, blank, one-sentence preamble carrying the
  `Execute EVERY check — do not skip.` directive verbatim, blank, the source-L5
  stack-profile blockquote verbatim, blank); `findings-template.md` has a 4-line header.
  Re-verify a span with:
  `diff <(tail -n +7 <mode>.md) <(sed -n 'S,Ep' verification-checklists.md)`
  (`tail -n +5` for findings-template.md). Useful for item 002/003 if the files are
  ever regenerated.
- CHECK-ID counting: use `sort -u`. Raw occurrence counts are higher for impl (28 vs
  23) and epic (13 vs 10) because CHECK-I21/I22 and CHECK-E06/E07 are cross-referenced
  in surrounding prose — those cross-references are part of the verbatim text.
- Creating files under a skill's own `references/` makes `adapters/` stale immediately:
  `build-adapters.py _emit_bundle` copies the whole dir into all **six** bundles
  (claude, codex, copilot, cursor, gemini, pi). Regenerating added 6×7 = 42 adapter
  files here. `build-adapters.py --check` (validate.sh step 6b) catches this; pytest
  does not.
- `.venv-adapters` already existed and was reused; `bash scripts/validate.sh` is green.

## Item 002 — switch consumers to the split checklists, delete the monolith

### R1 measured net instruction-token delta (spec 06 §7.5 row "R1", §7.2 method)

Baseline of record: `specs/context-efficiency/.reference/REMEASURE-0.13.0.md`.
Method: `wc -l` / `wc -w` over the canonical surface, prose at ~1.3 tok/word.

Targeted invocation — **a `forge-verifier` leaf subagent**. Before it loaded the whole
`references/verification-checklists.md` (477 L / 4,755 w ≈ **6,182 tok**); after R1 it
loads exactly one mode file:

| mode | after (L / w / tok) | net delta |
|---|---|---|
| prd | 31 / 286 / 372 | **−5,810** |
| tech | 35 / 308 / 400 | **−5,782** |
| specs | 64 / 662 / 861 | **−5,321** |
| backlog | 97 / 1,112 / 1,446 | **−4,736** |
| impl | 48 / 1,094 / 1,422 | **−4,760** |
| epic | 79 / 804 / 1,045 | **−5,137** |

Per-leaf band **−4.7k … −5.8k tok**, i.e. 99–109% of the re-measured −4.8k…−5.9k claim
(108–132% of the original −4.4k PRD claim). The parent orchestrator also improves: its
Step-4/Step-6 template read is now `references/findings-template.md` (157 L / 859 w ≈
1,117 tok) instead of the same 6,182-tok monolith → **−5,065 tok**.

Costs, correctly attributed: `forge-verify/SKILL.md` body 263→265 L, 2,554→2,580 w
(**+34 tok** — the six literal mode citations); `agents/forge-verifier.md` 122 L,
1,077→1,108 w (**+40 tok**). Net reduction holds on every mode.

### Learnings

- **Never write the brace-enumeration citation form.** `build-adapters.py`'s fan-out
  regex character class has no comma, so `{prd,tech,…}.md` captures one bogus token and
  resolves nothing. Step 3 names all six paths as separate literals; `{mode}.md` is the
  only brace form in canon (it matches, since the class holds `{`/`}`/`/`).
- The repo's interactive `rm` alias silently no-ops in a non-tty tool call — the file
  survived and only `ls` revealed it. Use `command rm -f` for canon deletions.
- Two of the three repointed tests sliced a mode section using the *next mode's* `##`
  heading as terminator. Those headings now live in sibling files; a `str.split()` on a
  missing terminator returns the whole remainder, so the tests would have stayed green
  while asserting over a wider slice. Both now slice to EOF explicitly.
- `references/vendor-construct-inventory.md` (the REQ-VND-03 audit artifact) names each
  file holding a `${CLAUDE_PLUGIN_ROOT}` occurrence — the epic bash recipe's prelude moved
  with the split, so that row was repointed to `verification-checklists/epic.md`. No test
  pins it; it goes stale silently. Worth re-grepping on any future reference-file move.

## Item 003 — `tests/_forge_paths.py` + the R1 checklist-split drift guard

### Mutation-test evidence (AC 2 / AC 3)

Recorded here as well as in the commit message, since a transient experiment leaves no
trace. Each mutation was applied to canon, the guard run, then the file restored and
confirmed byte-identical with `git diff --stat` (empty).

1. **Deleted the `CHECK-S38` line from `verification-checklists/specs.md`** → 3 failures:
   - `test_mode_checklist_is_complete_and_contiguous[specs]`:
     `AssertionError: specs.md: expected 38 contiguous CHECK-S IDs, found 37`
   - `test_split_preserves_the_full_check_inventory`:
     `AssertionError: split inventory drifted from 130 unique CHECK-IDs: {'prd': 15, 'tech': 17, 'specs': 37, 'backlog': 27, 'impl': 23, 'epic': 10}`
   - `test_skill_expected_count_table_matches_the_files`:
     `AssertionError: SKILL expected-count table says specs: 38 checks, but specs.md holds 37`
   The third failing *for free* is the point of reading the table against the counted
   values: a deletion is caught by the file guard **and** by the table guard.
2. **`forge-verify/SKILL.md` table drift, `backlog: 27 checks` → `26`** →
   `AssertionError: SKILL expected-count table says backlog: 26 checks, but backlog.md holds 27`
3. **Table re-hedged, `impl: 23 checks` → `impl: ~23 checks`** →
   `AssertionError: SKILL expected-count table still hedges impl with '~' — the split made the totals exact`
   (item 002 dropped the `~`; the regex captures an optional `~` so the hedge is caught
   rather than silently matching the digits.)

A renumber-in-place (`CHECK-S38` → `CHECK-S99`) also goes red, on the contiguity list
comparison rather than the length one.

### Learnings

- **Contiguity alone is not a removal guard.** Deleting the *highest* ID (S38) leaves
  `01..37` perfectly contiguous. The guard needs a frozen expected count too — so
  `EXPECTED` holds one hardcoded count per mode (the REQ-R1-05 inventory) and the SKILL
  table is compared against counts *read back out of the files*. That is the "no number
  hardcoded in two places" split: one frozen inventory, one derived comparison.
- `_ids()` unique-s deliberately. Raw `CHECK-I` occurrences in `impl.md` are 28 (not 23)
  and `CHECK-E` in `epic.md` are 13 (not 10) because I21/I22 and E06/E07 are
  cross-referenced in surrounding prose — those cross-references are part of the verbatim
  moved text, so `sort -u` / `set()` is mandatory, not a convenience.
- `tests/` has no `__init__.py`, so pytest's default `prepend` import mode puts `tests/`
  on `sys.path` and a bare `from _forge_paths import …` resolves. The leading underscore
  also keeps the module out of collection. Items 004/005/007–010/014–016 can import it
  the same way.
- `tests/` is **not** in `validate.sh`'s `RUFF_TARGETS` (`scripts/ eval/` only), so ruff
  does not lint the guards. Keep them tidy by hand.
- Restoring a mutated canon file: `command cp -f` (the repo's interactive `cp`/`rm`
  aliases no-op in a non-tty tool call — same gotcha item 002 hit with `rm`).

## Item 004 — gate the navigator's `process-overview.md` read (R3)

### R3 measured net instruction-token delta (spec 06 §7.5 row "R3", §7.2 method)

Baseline of record: `specs/context-efficiency/.reference/REMEASURE-0.13.0.md` (§R3 row:
`−1.72k` re-measured, 101% of the `−1.7k` PRD claim).
Method: `wc -l` / `wc -w` over the canonical surface, prose at ~1.3 tok/word.

Targeted invocation — **a routine navigator status/dashboard render**. It no longer
loads `references/process-overview.md` (143 L / 1,326 w ≈ **1,724 tok**, unchanged
file). Cost: the navigator body grew 3,936 → 3,967 w (227 L, unchanged) for the gating
clause — **+40 tok**, paid on *every* invocation.

**Net on the targeted invocation: −1,684 tok** (98% of the −1.72k baseline claim).
On an architecture/"how does forge work" question the file still loads, so that path is
**+40 tok** — the correct attribution: R3 trades a small always-paid cost for removing a
large cost from the overwhelmingly common path.

### Learnings

- The gating clause was placed at the **top of `### 2. Determine Context`**, not left in
  `### 1. Read Configuration`. §1 is unconditional setup — any read instruction there is
  paid by every invocation regardless of how it is worded, so re-wording *in place* would
  have satisfied a naive grep while changing nothing. The gate has to live where the
  navigator classifies the request.
- The guard asserts **sentence-scoped**, not window-scoped. Spec 06 §3.3's sketch used a
  400-char window before the citation, which passes if an *unrelated* conditional happens
  to sit in the preceding paragraph — and §2's neighbourhood is full of `**If a feature
  name is provided**` branches, so that heuristic was live-fire false-positive-prone here.
  `_citing_sentences()` splits on `". "` and requires the gating cue **and** the
  architecture-topic cue inside the same sentence as the citation.
- Presence and conditionality are **two independent guards**, deliberately. A citation
  reintroduced as a bare imperative keeps the fan-out guard green while restoring the
  unconditional load; a moved read-site with the literal path dropped keeps the
  conditionality guard green while silently unshipping the file from the non-Claude
  adapter bundles. Neither alone is coverage.
- Mutation-tested by reverting the clause to the verbatim pre-R3 line
  `For pipeline architecture details, read \`references/process-overview.md\`.` → 2 of 4
  tests red (`test_the_unconditional_setup_read_is_gone`,
  `test_every_citation_sits_inside_a_how_it_works_conditional`), restored with
  `command cp -f`.
- Editing one skill body restages **6** adapter files (one per target) — the navigator
  body is copied into every bundle. `process-overview.md` itself is a *shared* reference,
  fanned out by citation: it still resolves 3× per target after the move, confirming the
  literal-citation requirement did its job.

## Item 005 — `effective-config` subcommand + the shared stdlib schema validator

Per the item's own notes: **no per-stage token saving is claimed for R5.** The
188-session corpus shows `forge-config-schema.json` was read 1× total, so R5's
justification here is deterministic default resolution (REQ-R5-02), not a token
figure. The consumer swap and its measured static delta belong to item 006.

### Learnings

- **`tests/_state_schema.py` is the R4 dependency this item quietly carries.**
  Items 008/009/010/014 import `validate_state` from it, so it was written and
  red-tested against the *state* schema now, not just the config one — validated
  clean against all three real `.pipeline-state.json` files in `specs/`, and
  proven to go red on a missing `required`, a bad `enum`, a wrong `type`, and an
  `additionalProperties: false` violation.
- **Where `additionalProperties: false` actually lives in the state schema:**
  only on `deferredDecisions[].items` and `epicChangeRequests[].items`. Neither
  `stageEntry`, `verifyEntry`, `stages`, nor the root sets it — so an extra key
  on a stage entry is *schema-legal* and the validator correctly stays silent.
  Item 010's "an extra key is a hard validation failure" note is true only for
  its two array shapes; do not expect the same guard on `state-enter`/`state-complete`.
- **`bool` is a subclass of `int` in Python**, so a naive `isinstance(node, int)`
  passes `True` for `"type": "integer"`. `_check` special-cases it; a future
  `version: true` regression would otherwise validate clean.
- **The AC "no import of jsonschema anywhere in scripts/ or tests/" is satisfied
  for new code only.** Three pre-existing modules (`test_pipeline_state_schema.py`,
  `test_compliance_eval.py`, `test_forge_bootstrap.py`) use
  `pytest.importorskip("jsonschema")` and skip in CI by design. Removing them is
  outside this item's scope; nothing added here imports it.
- Schema resolution is cwd-independent (`Path(__file__).resolve().parent.parent /
  "references"`), verified by running the subcommand from `/tmp`: it resolved the
  bundled schema and, finding no `./forge.config.json` there, degraded to pure
  defaults at exit 0. That degrade path is deliberate — only an unreadable
  **schema** is fatal.
- Editing only `scripts/forge-session.py` restages **6** adapter files (one per
  target); `RUNTIME_HELPER` scripts are copied wholesale, so the new subcommand
  ships to every host with no citation work.
- This repo's local `forge.config.json` pins `loopRunner.bin` to `rauf-stable`
  (the `pnpm dogfood:runner` build), which makes it a live override fixture — the
  in-repo run shows `bin: "rauf-stable"` while the pure-defaults run shows `rauf`.
  Handy end-to-end confirmation that the merge direction is right.

## Item 007 — R4 shared state-write machinery

Added to `scripts/forge-session.py`: `import tempfile`, `STATE_VERB_STAGES`
(right after the existing L107 `PRODUCTION_STAGES`, derived from it), and a new
`# State writes (shared machinery for the state-* verbs)` section holding
`_now_iso`, `_write_state`, `_load_state_for_write`, `_commit_state`,
`_stage_entry` — placed between the effective-config section and `# CLI
dispatch`. No verbs, no argparse, no docstring usage lines yet (items 008–010).

### Learnings

- **`_write_state` wraps `OSError` in `UsageError`, deviating from spec 03 §3.3's
  code block** (which re-raises `OSError` and relies on `main()`'s separate
  `except OSError` arm). The item's AC pins the wrapped form and the exact
  message `atomic write to {path} failed: {exc}` (spec §6.8 agrees), so the AC
  wins. Both `tempfile.mkstemp` and the write/replace block are wrapped, so a
  failure at either point yields the same message. Exit code is 2 either way.
- **Loading the script in-process needs importlib**, not `import`: the filename is
  hyphenated. `importlib.util.spec_from_file_location(...)` at module scope gives
  `FS`, and the helper tests then run without subprocess overhead (20 tests, 0.13s).
  Items 008–010 will want the subprocess `_run()` form from spec 06 §3.5 for the
  verbs themselves — both styles can coexist in this file.
- **Monkeypatching `FS.os.replace` / `FS.os.fsync` / `FS.tempfile.mkstemp` patches
  the shared stdlib modules**, not a module-local copy — fine under pytest's
  `monkeypatch` (auto-restored), but never do it with a bare `setattr`.
- **The exit-2 / `Error:`-on-stderr half of the `_load_state_for_write` AC is
  proven through an existing UsageError path** (`effective-config --schema
  /nonexistent`), since item 007 ships no verb to drive it end-to-end. The handler
  is a single top-level `try/except` shared by every subcommand, so the verbs
  inherit it; items 008–010 assert it per verb. The direct
  `pytest.raises`-style check on `_load_state_for_write` covers the raise itself.
- **`_read_state` vs `_load_state_for_write` asymmetry is now guarded**
  (`test_read_state_downgrades_where_the_write_path_refuses`): the reader still
  downgrades corrupt → `{}` for the navigator's read-only sweep; the writer
  refuses and leaves the bytes intact. A future "simplification" that merges them
  goes red.
- Editing only `scripts/forge-session.py` restages **6** adapter copies (the
  script is copied wholesale into every bundle); `build-adapters.py` is silent on
  success, so check `git status`, not stdout.

## Item 008 — `state-enter` / `state-artifact` / `state-branch` / `state-note`

Added to `scripts/forge-session.py`: four `cmd_state_*` handlers + four
`_print_state_*` one-liners in a new `# State-write verbs` section (between item
007's shared machinery and `# CLI dispatch`), the shared `_emit` dispatcher, four
argparse subparsers, four `main()` dispatch branches, and the module docstring's
usage lines + a paragraph describing the verbs. `tests/test_state_verbs.py` grew
from 20 to 37 tests.

### Learnings

- **`--path` is repeatable here, deviating from spec 03 §5.1's code block**
  (which registers a scalar `required=True` `--path` and appends one). The item's
  AC pins "repeatable and de-duplicates", so the AC wins: `action="append",
  required=True, dest="paths"`, and `cmd_state_artifact` takes `paths: list[str]`.
  Items 011/012 will emit `--path` once per file, which works either way.
- **`_emit`'s printer signature forced one lambda.** Spec §11.1 fixes
  `_emit(payload, json_output, printer)` with `printer: Callable[[dict], None]`,
  but `state-artifact`'s human line needs the stage and the paths, and neither is
  derivable from the state echo (unlike `state-enter`, which can read
  `currentStage`). The dispatch therefore passes
  `lambda state: _print_state_artifact(state, args.stage, args.paths)` rather than
  inventing an echo-only `_stage` key. `state-complete` (item 009) already has a
  sanctioned echo-only key (`_cascadedStale`), so it can take the other route.
- **`Callable` was added to the existing `from typing import …` line**, not a new
  module import — item 007's "tempfile is the ONE new stdlib import" note still
  holds. Ruff's floor here is `E`/`F`/`W` only, so `UP035` (prefer
  `collections.abc.Callable`) is not active and no `# noqa` is needed.
- **`state-enter` does not need the spec's defensive `setdefault("feature", …)`
  / `createdAt` / `pipelineStatus` block** (§4.2's note) — item 007 moved that
  seeding into `_load_state_for_write` for *every* verb, precisely so the
  first-write `state-branch` case works. Re-adding it in the handler would be
  dead code.
- **The cross-verb invariants are table-driven** off a `_VERB_INVOCATIONS` map
  (one minimal invocation per verb). Four properties — `updatedAt` refresh,
  exit 2 on an unknown `--feature`, corrupt-file refusal with the bytes intact,
  and schema validity for a nested epic member — are each asserted once across
  all four verbs. Items 009/010 should extend that map rather than write four
  more near-identical tests per verb.
- `test_the_script_has_no_exit_1_branch` greps the whole script for `return 1` /
  `sys.exit(1)`, so it guards the 0/2 contract for every future verb too.
- Adapters: editing only `scripts/forge-session.py` restages the 6 per-target
  copies again (the script is copied wholesale); `--check` is the only gate that
  notices, pytest does not.

## Item 009 — `state-complete` (version bump, two-commit hash, staleness cascade)

Added to `scripts/forge-session.py`: `_parse_based_on`, `_CASCADE_TARGETS` +
`_cascade_staleness`, `cmd_state_complete`, `_print_state_complete`, the
subparser, the `main()` dispatch branch, and the docstring usage lines +
paragraph. `tests/test_state_verbs.py` grew from 37 to 57 tests.

### Learnings

- **`--status` is registered with `default=None`, deviating from spec 03 §6.1's
  code block** (`default="complete"`). The AC requires `--resumable --status
  complete` to exit 2, and with an argparse default of `"complete"` an explicit
  `--status complete` is indistinguishable from the flag being absent — the
  contradiction could never be detected. The handler resolves `status or
  "complete"` instead, and `cmd_state_complete`'s signature is
  `status: str | None = None`. `--resumable --status in-progress` is accepted
  (redundant, not contradictory).
- **The three branches were mutation-tested**, because schema validation cannot
  tell them apart (`stageEntry` declares `status` and `completedAt` as
  independent optional properties, so a wrongly-stamped revert validates clean):
  1. gating branch 2 on `resumable or status == "in-progress"` (the conflation
     the item warns about) → `test_partial_completion_keeps_every_completion_field`
     and `test_partial_completion_differs_from_complete_only_in_status` go red,
     reporting the discarded `basedOnVersions`/`artifacts`/`version`/`commitHash`.
  2. removing the `resumable` branch entirely (revert falls through to the
     completion write) → `test_resumable_records_only_the_status` goes red on the
     cascade (`Left contains one more item: 'forge-4-backlog'`).
  Both restored with `command cp -f` from a backup; `git diff --stat` confirmed
  the script was byte-restored.
- **The `--commit-hash` guard requires `status == "complete"`, which by
  construction excludes forge-5-loop's partial completion.** Checked whether that
  is a live conflict: `skills/forge-5-loop/SKILL.md` has zero `commitHash` /
  `rev-parse` references, so the loop stage never runs Commit 2 and the guard
  cannot strand it. No residual for item 013.
- **`_cascade_staleness` rejects `bool` explicitly** (`not isinstance(recorded,
  bool)`) — `bool` subclasses `int`, so a `basedOnVersions: {"forge-1-prd": true}`
  would otherwise compare `True < 2` and silently stale a downstream stage.
  (Item 005's progress note flagged the same trap in the validator.)
- **`_print_state_complete` takes `(state, stage, commit_hash, resumable)` via a
  dispatch lambda**, following item 008's `_print_state_artifact` precedent. The
  three branches print materially different things, and the echo alone cannot say
  which branch ran — a `commitHash`-only follow-up and a `--preserve-commit-hash`
  completion leave identical entries.
- The completion branch writes `basedOnVersions` even when no `--based-on` was
  passed (forge-1-prd records `{}`, not an absent key), matching spec §6.2.

## Item 010 — `state-decision` / `state-ecr` (the two array-appending verbs)

Added to `scripts/forge-session.py`: four enum constants next to
`STATE_VERB_STAGES`, `cmd_state_decision`, `_parse_bool`, `cmd_state_ecr`, two
printers, two subparsers, two `main()` dispatch branches, and the docstring's
usage lines + paragraph. `tests/test_state_verbs.py` grew from 57 to 72 tests.
All seven R4 verbs now exist.

### Learnings

- **The enum `choices` are module-level `Final` constants** (`DECISION_RAISED_BY`,
  `DECISION_TARGET_STAGES`, `ECR_KINDS`, `ECR_RAISED_BY`), deviating from spec 03
  §8.1/§9.1's inline literal tuples. The AC requires the choices to match
  `references/pipeline-state-schema.json` byte-for-byte, and a named constant lets
  the parity guard compare `FS.ECR_KINDS` against the parsed schema directly
  instead of regexing an `add_argument(...)` call. A *second* guard asserts each
  registration reads `choices=<CONSTANT>` — without it, someone could retype an
  inline tuple at the call site and the parity test would stay green while the CLI
  drifted.
- **`_parse_bool` is called in the DISPATCH, not inside `cmd_state_ecr`**, so a bad
  `--blocks-current` fails before `_load_state_for_write` runs and the state file is
  never created. The test asserts that non-existence, not just exit 2.
- **`additionalProperties: false` bites here and nowhere else.** These are the only
  two shapes in the state schema that set it (item 005's note), so an absent
  optional must be **absent, not null**: `state-decision` omits `rationale` /
  `targetStage` entirely rather than writing `None`, and the test asserts the exact
  key set `{question, raisedBy, raisedAt, status}` rather than just schema validity.
- **The enum asymmetry is deliberate and worth not "fixing":** `forge-5-loop` and
  `forge-6-docs` are legal `targetStage` values but can never be a decision's
  `raisedBy`; `state-ecr`'s `raisedBy` is narrower still (prd/tech only). Both are
  schema-driven, and each has a rejection test.
- **Neither printer needs a dispatch lambda** (unlike `state-artifact`/`state-complete`
  in items 008/009): the appended item is recoverable from the echoed state as
  `state["deferredDecisions"][-1]`, so the plain `Callable[[dict], None]` signature
  works.
- Adapters: `scripts/forge-session.py` is copied wholesale, so this restaged the
  same 6 per-target copies; `build-adapters.py --check` is the only gate that
  notices. `bash scripts/validate.sh` is green.

## Item 014 — the R4 schema-conformance drift guard

New file `tests/test_state_schema_conformance.py` (21 tests), deliberately kept
separate from `tests/test_state_verbs.py`: that module asserts each verb's **CLI
contract** (which fields, which rejections), this one asserts only that whatever a
verb writes **conforms to the unchanged schema**. Sections: per-verb single calls,
two realistic sequences, the two first-write edge cases, the corrupt-file refusal,
the schema-unchanged digest, and a negative control.

### Mutation-test evidence (the guard can go red)

Recorded here as well as in the commit message. Both mutations applied to
`scripts/forge-session.py`, guard run, then restored with `command cp -f` from a
`/tmp` backup and confirmed byte-restored via an empty `git diff --stat`.

1. `_stage_entry` seed `{"status": "pending"}` → `{}` (item 007's bootstrap) → 2 red:
   `test_each_verb_writes_schema_conformant_state[state-artifact]` and
   `test_state_artifact_against_a_never_entered_stage_conforms`, both reporting
   `$.stages.forge-6-docs: missing required 'status'`.
2. `state-complete --commit-hash` branch rewritten to REPLACE the entry
   (`state["stages"][stage] = {"commitHash": ...}`) — the exact lone-`commitHash`
   defect spec verification found → `test_the_authoring_sequence_conforms_after_every_step`
   red at *the fifth step*, on `missing required 'status'`.

Mutation 2 is the argument for validating after **every** step of a sequence rather
than only at the end: the first four steps stayed green, so an end-only assertion
would have caught it only by luck of which field the defect happened to drop.

### Learnings

- **`additionalProperties` is absent on `stageEntry`, so the schema cannot catch a
  *stray* key — only a *missing required* one.** Every mutation worth guarding here
  therefore has to drop `status`; adding junk to a stage entry validates clean by
  design (item 005's note). That shapes what this guard can promise: conformance,
  not completeness. The per-verb field assertions stay `test_state_verbs.py`'s job.
- **The verb-coverage test parses `add_parser("state-…")` out of the script** and
  asserts the registered set equals the covered set (plus `== 7`). Without it, an
  eighth verb could land fully unguarded while every existing test stayed green —
  the failure mode a hand-maintained parametrize list always has.
- **The schema-unchanged assertion is a hardcoded sha256, not a `git show`.** The
  digest `33a8337a…` is the blob at the pre-feature baseline commit
  `9a29e846ed510c3b245876a9bf4cc73b8cb60951`, verified identical to the working
  tree. A git-based assertion would go red in any checkout without history (and CI
  shallow-clones); the constant is git-free and its comment names the baseline.
- **The negative control matters more than usual here.** Every conformance assertion
  is `validate_state(...) == []`, which a broken validator satisfies vacuously —
  `test_the_validator_rejects_the_shapes_this_guard_exists_to_catch` hand-builds the
  two real defects plus an out-of-enum status and asserts each produces findings.
- Tests-only item: no canon edit, so `adapters/` was NOT restaged and no
  regeneration was needed (this item's ACs correctly omit the adapters criterion).
  `python3 -m pytest tests` → 638 passed / 2 skipped; `ruff check scripts/ eval/`
  and `bash scripts/validate.sh` green.
