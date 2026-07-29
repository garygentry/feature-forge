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

## Item 011 — shared-conventions.md's five touch points + the stage-exit deferred-decisions rule

Converted per spec 03 §13.3, following its before/after blocks literally. Six edits
land in `references/shared-conventions.md` (five touch points + the Pipeline State
Protocol header, see below) and one in `references/stage-exit-protocol.md`.

### The sixth shared-conventions edit was NOT in the item's list of five

`## Pipeline State Protocol` L186 read *"Write pipeline state conforming to
`references/pipeline-state-schema.json`. Always update `updatedAt` when modifying
pipeline state."* Spec 03 §13.3 never mentions it and the item enumerates five touch
points — but AC 1 is broader than the five ("**no site** in shared-conventions.md
instructs hand-editing `.pipeline-state.json`, except the ledger exclusions"), and that
line is not in the R4 exclusion ledger. Leaving it would have contradicted the five
converted sites *and* the verbs, which refresh `updatedAt` themselves. It is now the
file's anti-instruction ("written by the `state-*` verbs … never by hand") and carries
spec 03 §14's verb-failure convention, which the five new call sites need: each is a
subprocess that can exit 2 where a hand-edit could not fail at all. Recorded here
because a future reader comparing the item text to the diff will find a sixth hunk.

### Fences cannot go inside a numbered/bulleted list

check-spec-purity Rule 5 pins `BOOTSTRAP_PRELUDE` **byte-identical**, so an indented
prelude (as a fence nested in a list item requires) is a Rule 5 violation, and a
column-0 fence mid-list restarts the numbering. Both touch points that live in a list
therefore keep the invocation **inline in backticks** inside the list item and place
one column-0 fence **after** the list:
- Branch Reconciliation `adopt-current` → one `state-branch` fence after the three
  `action` bullets.
- Git Commit Protocol steps 2/3 → one fence after step 5, carrying **both**
  `state-complete` calls behind a single prelude (the sanctioned one-prelude-many-
  commands form; `epic-manifest-subcommands.md` has the same shape).

### Where each verb call is emitted

`state-branch` is cited twice and fenced twice (Branch Setup + Branch Reconciliation).
Branch Setup's copy carries the load-bearing timing qualifier: the call is emitted
**after Feature Directory Resolution and the Entry Stamp**, not at the Branch Setup
block, which runs before the feature directory may exist. Verified by running
`state-branch` as the *first* verb against a bare `specs/demo/` — it succeeds thanks to
item 007's field seeding, so the ordering rule is about the *directory*, not the state
file.

### L245's `--resumable` needs `--version` anyway

`--version` is `required=True` on the subparser, so the L245 recovery command exits 2
without it even though `--resumable` never writes it. The prose says so explicitly —
this is the kind of detail that only shows up when someone actually runs the documented
recovery.

### §9 behavior-preservation record

`specs/context-efficiency/.verification/BEHAVIOR-PRESERVATION-R4-item-011-2026-07-29.md`.
Uses §9's sanctioned **reduced substitute for R4** (one authoring stage + a deliberately
failed Commit 1), named explicitly, plus an exhaustive static surface diff — justified
because this item edits only shared protocol text and converts no skill body.

Two method notes worth reusing for items 012/013, which owe the same §9 record:
- **Section-granular diff is the strongest cheap evidence.** Split both files on `##`
  at the baseline and in the worktree and compare byte-for-byte. Result here: 10 of 15
  shared-conventions sections and 5 of 6 stage-exit sections are byte-identical,
  including `User Input Protocol` (surfaces 1+2), `Stage-Completion Re-check` (4b) and
  `Standard block` (6+7). Then `git diff -U0 | grep '^-'` and read **every** removed
  line — all 16 here are JSON-authoring mechanics.
- **The `--resumable` control only discriminates on the right fixture.** Comparing
  `--resumable` against a bare `--status in-progress` shows no difference if the
  Commit-1 `state-complete` write already landed with the same values. The
  discriminating fixture is a stage **complete at v1 with a recorded `commitHash`**,
  re-entered for v2: `--resumable` leaves version=1/completedAt/commitHash intact while
  the bare form writes version=2, restamps `completedAt` and resets `commitHash` to
  null. My first two assertion attempts were wrong about the *fixture*, not the verb.

### Gotcha (re-hit)

The repo's interactive `cp` alias hangs a non-tty tool call on an overwrite prompt —
it burned a 2-minute timeout here. `command cp -f`, as items 002/003/009 already noted
for `rm`/`cp`.

### Gates

`python3 -m pytest tests` 638 passed / 2 skipped, with
`tests/test_stage_exit_protocol.py` green **unchanged** (it asserts the stage-exit
DIRECTIVES, not the deferred-decisions block). `check-spec-purity` PASS including
Rule 5 on all five new preludes. Adapters restaged **130** paths — both edited files
are bundle-root shared references fanned out to ~11 skills × 6 targets, the widest
blast radius of any canon edit in this feature so far. `bash scripts/validate.sh` PASS.

## Item 012 — the five authoring skill bodies

Converted per spec 03 §13.1/§11.2. Body lines before → after (frontmatter stripped):
forge-0-epic **292 → 292** (cap 300), forge-1-prd 148 → 164, forge-2-tech 209 → 226,
forge-3-specs 162 → 178, forge-4-backlog 159 → 168. All five well under 5000 words.

### `forge-0-epic` was NOT deferred — its only state write is a ledger EXCLUSION

The item's DEFER clause was **not** needed, because forge-0-epic has nothing convertible:

- Its **only** `.pipeline-state.json` authoring is Step C7's member-stub write (L224–232),
  which is the ledger's exclusion 3(i) in `03-state-verbs.md §11.2` — *"the Member State
  Example (creation C7) member-subdir stub write"*. The ledger cites `references/edit-mode.md`
  (where the *example* lives), but its rationale — *"none of the seven verbs writes the `epic`
  back-pointer a brand-new member stub needs"* plus *"forge-0-epic also has only 8 body lines
  of headroom"* — is plainly reasoning about the SKILL.md instruction too. **Item 013's
  repo-wide census must name `skills/forge-0-epic/SKILL.md` Step C7 alongside the
  `edit-mode.md` site**, or the census AC goes red on a site nobody could convert.
- The conversion map's *"member `branch` writes → `state-branch`"* row has **no
  counterpart in the body**: `grep -n branch` over forge-0-epic finds only the epic-scope
  Branch Setup invocation (L95–97) and the creation/edit dispatch words. Members inherit the
  epic branch, and each member's own `forge-1-prd` records it through shared-conventions'
  Branch Setup — already converted in item 011. Nothing to do.
- Net edit: **one in-place sentence extension at L234** (0 added lines) marking the C7 write
  as a sanctioned exception to the Pipeline State Protocol. 292/300 preserved exactly.

### `currentStage` advancement is dropped — the one REQ-BEHAV-02 flag

Every converted completion step carried a `Set currentStage to <next stage>` bullet.
`state-complete` does **not** write `currentStage`, and spec 03 §13.1's authoritative
after-block omits it; no verb can set it to an arbitrary value (`state-enter` would also
stamp the target stage `in-progress`). So it is gone from all four bodies, per spec.

Impact is display-only and arguably a correction: `next_stage()` (L320–336) derives "what
runs next" from `stages[].status` and its docstring says it is *"intentionally distinct
from the stored `currentStage` field"*; `render-status` uses `currentStage` for display
only (L495–498). The field is documented as *"where the pipeline IS"* (schema O1), which
the old bullet already contradicted by setting it to where the pipeline is **going**.
Flagged in the §9 record for owner review rather than silently adapted.

### Fence placement — the item-011 list rule bites again, differently

Item 011's finding (a fence cannot sit inside a numbered/bulleted list: an indented prelude
breaks Rule 5 byte-identity, a column-0 fence mid-list restarts numbering) applies to all
four Step 6/7 completion blocks. Resolution: items 1–4 name the verb inline
(*"run `state-complete` (below)"*), and **one** column-0 fence sits between the last list
item and the existing *"Close this stage with the Scripted Stage Exit"* paragraph, carrying
the `state-complete` **and** `state-note` calls behind a single prelude — the sanctioned
one-prelude-many-commands form. The two epic-backflow paragraphs and forge-3-specs'
incremental-tracking paragraph are **not** lists, so each takes its own fence directly.

Deliberately kept item 2 (*"Offer a note — don't force one …"*) **byte-identical**: spec
§13.1 says it "is unchanged", and §13.2 lists it as a frozen statement. The `state-note`
mechanic is named in the fence intro instead of edited into the frozen sentence.

### Removing the schema citation UNSHIPS the schema from four bundles

Dropping `references/pipeline-state-schema.json` from the four authoring bodies removes it
from their adapter bundles — `git status` shows 24 deletions
(`adapters/*/skills/forge-{1-prd,2-tech,3-specs,4-backlog}/references/pipeline-state-schema.json`).
That is correct and is REQ-R4-01's whole point, but note the fan-out is **one level deep**:
`shared-conventions.md` (bundled into every skill) still *mentions* the schema in its
Pipeline State Protocol paragraph, and that mention does **not** re-ship the file. It is
descriptive prose, not a read instruction, so nothing breaks — but item 016's citation
guard scans skill **bodies** only, so a dangling citation inside a bundled reference would
not be caught. Worth knowing before any future reference-file move.

### §9 behavior-preservation

`specs/context-efficiency/.verification/BEHAVIOR-PRESERVATION-R4-item-012-2026-07-29.md`.
§9's named **reduced substitute for R4** (one authoring stage + a deliberately failed
Commit 1), plus a section-granular static diff: **73 of 81 sections byte-identical**, 8
changed, and all 29 removed lines are JSON-authoring mechanics. Every call site this item
introduces was run end-to-end against a temp fixture; both resulting states (standalone and
nested epic member) validate with zero findings via `tests/_state_schema.py`.

The `--resumable` assertion the AC asks for needs the **entered-but-not-completed** fixture
(not item 011's complete-at-v1 one): clone that state twice, run `--resumable` on A and a
bare `--status in-progress` on B — A stays `{status, startedAt}` only, B gains `completedAt`
**and** `version`. That is the pair that proves the two in-progress callers stay distinct.

### Gates

`python3 -m pytest tests` 638 passed / 2 skipped · `check-spec-purity` PASS (Rule 5 green on
all 7 new preludes) · `build-adapters.py --check` exit 0 · `bash scripts/validate.sh` PASS.
Adapters restaged 55 paths (5 bodies × 6 targets × {SKILL.md, .md, .mdc} minus non-emitting
combinations, plus the 24 schema deletions).

## Item 013 — forge-5-loop, forge-6-docs, the navigator, forge-verify (R4's last conversions)

Two real conversions (`forge-5-loop` ×2, `forge-6-docs` ×1, navigator ×1), one
sanctioned relocation to pay for them, and two deliberate-exclusion notes. R4 is now
complete.

### `forge-verify` had NOTHING to convert — and that is the correct outcome

The conversion map's row *"production-stage entry/exit stamps it authors (NOT the
verifyEntry)"* has **no counterpart in the body**. `grep`ping `forge-verify/SKILL.md`
for every state write finds exactly two, both `verifyEntry` class (Step 6's
`stages.forge-verify-*` write and the epic-mode `.epic-state.json` write) — plus one
**read** of a production entry at L228 (`verifiedStageVersion` = the covered stage's
`version`), which is not a write. verify is not a production stage, so it never stamps
one. The AC is satisfied vacuously; the edit made here is a **prose-only** exclusion note
so a future census reads the omission as deliberate rather than missed. Same shape as
item 012's finding that `forge-0-epic`'s only state write was already a ledger exclusion.

### The line budget: 298 → 296, via the sanctioned verbatim relocation

Each conversion costs **+2** lines (prose line + blank + fence-open + 2-line prelude +
1-line command + fence-close = 7, replacing a 5-line hand-edit bullet list), so the two
`forge-5-loop` conversions were **+4** against **2** spare lines. Per the item's owner
decision, the lines came from **relocating** the 7-line Step-3c paragraph verbatim into
`references/runner-contract.md`'s existing `## Inform-user output template (Step 3c)`
section (−6), leaving a one-line citation so fan-out still ships the file. Net **−2**:
**296 L / 4,478 w**, 4 lines of headroom left for items 006 and 015.

Choosing *which* block to relocate matters: Step 3c was the only candidate that is
(a) a self-contained paragraph, (b) already deferring its verbatim template to
runner-contract.md, and (c) in a file the loop reads **unconditionally** — item 015 keeps
"inform-user template" among runner-contract's six always-loaded sections, so the move is
behavior-neutral. Relocating into a gated section would have been a behavior change.

**Keeping each command on ONE line is what makes the +2 achievable.** The canon style
wraps `state-complete` over 3–4 backslash-continued lines; here they are single long
lines. Same bytes to the model, 2–3 fewer lines against the cap.

### `currentStage` advancement dropped again — same flag as item 012

`forge-5-loop` Step 5 item 2 (`→ "forge-6-docs"`) and `forge-6-docs` Step 5 item 1
(`→ complete`) both vanish: `state-complete` does not write `currentStage` and spec 03
§13.1's after-block omits it. Applied consistently with item 012 rather than resolved
differently. The one visible effect is that a **finished** pipeline's dashboard now shows
`currentStage: forge-6-docs` instead of `complete` (`build_rows`, forge-session.py L495–498,
uses the stored field when truthy and only falls back to `"complete"` when it is absent).
That matches the schema's own definition of the field — *"where the pipeline IS: the most
recently started stage"* — so it reads as a correction, but it is a **user-visible display
difference** and is flagged in the §9 record for owner review, not silently adapted.

### Fence placement, third variant

Item 011 found a fence cannot sit inside a list; item 012 put it **after** the numbered
list. `forge-6-docs` Step 5 needed a third answer: its list ends with a long multi-bullet
item 4, so an after-the-list fence would sit at the section boundary, far from the item 1
it serves. The fence goes **before** the list instead, with item 1 saying "the
`state-complete` call above". Pick whichever end of the list keeps the fence adjacent to
the item that runs it.

### Repo-wide R4 census — result

Across `skills/` and `references/`, every remaining hit classifies into the ledger:
- **schema citations (7):** `shared-conventions.md` L186 (anti-instruction, item 011),
  `forge/SKILL.md` L53 + `forge-verify/SKILL.md` L222 (each precedes an excluded write,
  retained by name), `forge-0-epic/SKILL.md` L225 + `edit-mode.md` L256 (C7 member stub),
  `edit-mode.md` L35 + `stage-exit-protocol.md` L158 (document field shapes).
- **hand-authoring instructions:** `forge-0-epic/SKILL.md` L224 (C7), `forge-verify`
  Step 6, `forge-fix` Step 5, `forge-4-backlog` L144, `forge-5-loop` L266/L286,
  `findings-template.md` L98–99 — all verifyEntry class; plus `edit-mode.md`'s
  Apply/Dismiss flips and `stage-exit-protocol.md`'s `deferredDecisions` flip (mutate an
  existing array item; no verb does that).
- **naive-grep false positives:** `forge-guide/SKILL.md` L165 (anti-instruction),
  `runner-contract.md` L176 + `process-overview.md` L92 + `forge-0-epic/SKILL.md` L72
  (descriptive prose). The last two were **not** in the item's list — the AC's
  "no site OTHER THAN THOSE NAMED **instructs**" wording is what makes them harmless.

`findings-template.md` L98–99 is worth noting: it is a verifyEntry-class write in a
**reference** file, not named in the item's "Known sites" list. Ledger clause (b) is
categorical ("ANY instruction to write a `stages.forge-verify-*` entry"), so it is
covered — but a census that matched only the enumerated paths would have flagged it.

### Gotchas re-hit

- The interactive `cp` alias prompts and hangs a non-tty call — `command cp -f`
  (items 002/003/009/011 all logged this).
- Removing `forge-6-docs`' schema citation **unships** the file from its bundle on all
  six targets (6 deletions in `adapters/`) — that is the measurable R4 file-load delta.

### R4 measured net instruction-token delta for item 013 (spec 06 §7.5 / §7.2 method)

Baseline of record: `specs/context-efficiency/.reference/REMEASURE-0.13.0.md`
(§R4 row: `pipeline-state-schema.json` = 191 L / 1,149 w → **−1.49k tok** word-based,
−2.75k char/4; re-measured at 100% of the PRD claim). Method: `wc -l` / `wc -w` over the
canonical surface, prose at ~1.3 tok/word.

Recorded here rather than in the commit message because the iteration agent does not
commit — the loop runner owns the commit and writes a subject-only message (same as
items 002/004/012, whose figures also live in this file).

**Static file-load delta.** Exactly one of the four bodies carried a
`pipeline-state-schema.json` read-to-author-state citation: **`forge-6-docs`**. Removing
it unships the schema from that skill's bundle on all six adapter targets (6 deletions in
`adapters/`), so a `forge-6-docs` invocation that would have read it no longer does:
**−1,494 tok**. The other two citations (`forge/SKILL.md` L53, `forge-verify` L222) are
retained **by name** in the census carve-out because each precedes a ledger-excluded
write, and `forge-5-loop` never cited the schema at all.

**Costs, correctly attributed** (all always-paid body growth):

| Surface | Δ words | Δ tok | Net on its targeted invocation |
|---|---|---|---|
| `forge-6-docs` body | +101 | +131 | **−1,363** (−1,494 schema, +131 body) |
| `forge-5-loop` body +63 w / `runner-contract.md` +79 w | +142 | +185 | **+185** |
| `forge/SKILL.md` (navigator) | +116 | +151 | **+151** |
| `forge-verify/SKILL.md` (exclusion note only) | +83 | +108 | **+108** |

**Per §7.4, no per-stage token saving is asserted.** The 188-session corpus shows
`pipeline-state-schema.json` was read **2× total**, not per stage, so the −1,494 figure is
the static delta on the invocations where the read *does* occur — 13 of 188 transcripts
mention the file at all. Three of this item's four surfaces are net **positive** in
tokens; their justification is REQ-R4-02's **drift removal and deterministic resolution**,
which holds at any read frequency:

- the staleness cascade, the `updatedAt` refresh, `commitHash: null` and the version bump
  are now computed by `state-complete` instead of transcribed by the model;
- `forge-5-loop`'s conditional completion is a `--status` argument the skill *evaluates*,
  not a JSON shape it *authors*;
- every write is atomic and schema-conformant **by construction** (proven in the §9 record:
  zero findings from `tests/_state_schema.py` on every state these call sites produce).

SC-1's bar — "a measured net reduction, correctly attributed" — is met by R4 **as a unit**
(items 011+012+013 together remove the citation from five bodies: forge-1-prd,
forge-2-tech, forge-3-specs, forge-4-backlog, forge-6-docs); this item's own contribution
is the −1,363 on `forge-6-docs` plus the drift-removal benefit on the other three.

## Item 006 — forge-4-backlog + forge-5-loop switch to `effective-config` (R5's consumer half)

**Both consumers converted. NOTHING was deferred** — the item's DEFER clause was not
needed. Recording that explicitly, because item 015's AC says to retry a deferred
forge-5-loop edit: **there is nothing for item 015 to retry.**

### Measured line/word figures (frontmatter-stripped body, check-spec-purity Rule 4 region)

| body | before | after | cap |
|---|---|---|---|
| `forge-4-backlog/SKILL.md` | 168 L / 2,332 w | **174 L / 2,416 w** | 300 / 5000 |
| `forge-5-loop/SKILL.md` | 296 L / 4,478 w | **298 L / 4,556 w** | 300 / 5000 |

`forge-5-loop` had **4** spare lines entering this item (item 013's verbatim Step-3c
relocation bought 2 back on top of the 2 the specs measured), and the edit cost **+2**,
leaving **2 lines** for item 015 — exactly the headroom item 015's own text assumes.

### How the +2 was achieved (reusable)

The naive shape — lead-in prose, blank, fence, 2-line prelude, command, fence-close,
blank, trailing prose — is **9 lines replacing 5 = +4**, which would have landed the body
at 300/300 and left item 015 with zero headroom. Folding the trailing prose **into the
single lead-in paragraph above the fence** makes it 7 lines = **+2**. The frozen
`"No loopRunner configured — defaulting to the rauf loop runner."` sentence rides inside
that one paragraph byte-identical (only its line-wrapping changed — the paragraph is now
one long unwrapped line, which is also what the CI-only purity gate prefers).

General rule now confirmed three ways (items 011/012/013/006): **one paragraph + one
fence is the cheapest verb/subcommand call shape.** Anything that needs prose on *both*
sides of the fence costs 2 extra lines.

### R5 measured net instruction-token delta (spec 06 §7.5 row "R5", §7.2 method)

Baseline of record: `specs/context-efficiency/.reference/REMEASURE-0.13.0.md`
(§R5 row: `forge-config-schema.json` = 236 L / 2,068 w → **−2.69k tok** word-based,
−4.40k char/4; re-measured at 100% of the −2.7k PRD claim). Method: `wc -l` / `wc -w`
over the canonical surface, prose at ~1.3 tok/word.

**Static file-load delta.** Both bodies carried the file's only read-for-defaults
citation, so removing them **unships `forge-config-schema.json` from both bundles on all
six adapter targets** — 12 deletions in `adapters/`, the largest single-file unship in
this feature. An invocation of either stage that would have loaded it no longer does:
**−2,688 tok** (2,068 w × 1.3).

**Costs, correctly attributed** (always-paid body growth — the lead-in paragraph plus the
inlined two-line prelude, which neither call site could reuse since `$R` does not survive
between fences):

| Surface | Δ words | Δ tok | Net on its targeted invocation |
|---|---|---|---|
| `forge-4-backlog` body | +84 | +109 | **−2,579** |
| `forge-5-loop` body | +78 | +101 | **−2,587** |

**Per §7.4, NO per-stage token saving is asserted.** The 188-session corpus shows
`forge-config-schema.json` was read **1× total** (REMEASURE §Read-frequency table), not
once per stage, so −2,688 is the static delta on the invocations where the read *does*
occur, not a recurring per-stage figure. R5's standing justification is **REQ-R5-02
deterministic resolution / drift removal**, which holds at any read frequency:

- the 22-field default merge is now performed by `resolve_loop_runner` instead of being
  transcribed and mentally merged by the model — the "model mis-merged the defaults"
  error class is gone by construction;
- the schema stays the single source of truth (REQ-R4-03) even though no stage reads it;
- verified live in this repo, which is its own override fixture: `forge.config.json` pins
  `loopRunner.bin` to `rauf-stable`, and the call correctly emits `"bin": "rauf-stable"`
  over the schema's `"rauf"` default while every other field resolves to its default.

### Notes

- The two edits are the **only** remaining read-for-defaults sites. The five surviving
  `forge-config-schema.json` citations (`forge-guide` ×2, `process-overview.md`,
  `ralph-loop-contract.md` ×3, `shared-conventions.md` L77) all **document config keys**
  rather than instructing a defaults read, so they stay — R5 removes the step, not the file.
- Fan-out is one level deep (item 012's finding, re-confirmed): `forge-5-loop` still cites
  `references/ralph-loop-contract.md`, which *mentions* the schema, and that mention does
  **not** re-ship the schema into forge-5-loop's bundle. The 12 deletions are real.
- No interactive-protocol prose changed in either body. `forge-4-backlog`'s AskUserQuestion
  gates, `forge-5-loop`'s Run-mode/agent-selection surfaces and the frozen "No loopRunner
  configured" statement are untouched; `git diff` shows exactly one changed hunk per file.

### Gates

`python3 -m pytest tests` 638 passed / 2 skipped · `check-spec-purity` PASS (Rule 5 green
on both newly inlined preludes) · `build-adapters.py --check` exit 0 · `bash
scripts/validate.sh` PASS. Adapters restaged 24 paths (12 body copies + 12 schema deletions).

## Item 015 — split `runner-contract.md`, gate `agent-selection.md` (R6)

Three agent-conditional sections moved verbatim into a new
`skills/forge-5-loop/references/agent-selection.md`; `runner-contract.md` keeps the six
always-loaded sections. Four SKILL-body pointers changed (one trim, two re-points, one
in-line augmentation). **Body 298 → 298 lines** (line-neutral, as REQ-R6-03 requires),
4,556 → 4,564 words.

### Item 006 retry — NOTHING was deferred, so there is nothing to retry

The AC's conditional ("if item 006 deferred the forge-5-loop effective-config consumer
edit, RETRY it here") does **not** fire: item 006's progress entry records both consumers
converted, with the forge-5-loop edit landing at +2 lines against 4 spare. No residual.

### R6 measured net instruction-token delta (spec 06 §7.5 row "R6", §7.2 method)

Baseline of record: `specs/context-efficiency/.reference/REMEASURE-0.13.0.md`
(§R6 row: conditional slice = 105 L / 913 w → **−1.19k tok**; re-measured at 108% of the
−1.1k PRD claim). Method: `wc -l` / `wc -w` over the canonical surface, prose at
~1.3 tok/word.

Recorded here as well as in the commit message, since the iteration agent does not commit.

**Targeted invocation — a gate-OFF loop launch** (`loopRunner.agentArgument` absent or
empty). It reads `runner-contract.md` only:

| Surface | Before | After | Δ tok |
|---|---|---|---|
| `references/runner-contract.md` | 351 L / 2,943 w | 248 L / 2,050 w | **−1,161** |
| `forge-5-loop/SKILL.md` body | 298 L / 4,556 w | 298 L / 4,564 w | **+10** |

**Net on the targeted invocation: −1,151 tok** — 97% of the −1.19k re-measured claim,
105% of the −1.1k PRD claim. The +10 is always-paid body growth (the `(e)` bullet's
catalog pointer), correctly attributed against the saving.

**Gate-ON launch: +98 tok.** It opens both files (2,050 + 961 = 3,011 w vs 2,943 w
before = +68 w = +88 tok, plus the +10 body). The delta is the new file's 6-line preamble
plus `runner-contract.md`'s reworded preamble — the split's fixed overhead. Same
attribution shape as R3: a small always-paid cost on the rarer path buys a large removal
from the common one. Note the schema default for `agentArgument` is `"--agent {agent}"`,
so **gate-on is the default posture** — a project only lands on the −1,151 path by
explicitly emptying the field. That is worth knowing before quoting R6's saving as typical.

### Learnings

- **The preamble is the tenth section nobody counts.** `runner-contract.md`'s L3–8 opening
  paragraph advertised "the **optional-flags catalog** referenced from Step 2d" — text that
  is no longer in the file. The nine-section partition test would never have caught it
  (the preamble carries no heading). It now names `agent-selection.md` *and* states inline
  that the file is read only under the gate, so the cross-reference cannot be misread as an
  unconditional read instruction on the gate-off path.
- **The `(e)` bullet is where the catalog reference had to land.** Spec 05 §3.4's trim
  resolution drops the catalog clause from the pointer above the gate but does not say who
  picks it up. `(e) Optional-flags line` already augments the confirmation's flags pointer
  when the gate is on, so appending the catalog's location there is 0 net lines and is the
  only site that is both inside the gate and about flags.
- **A "line-neutral" trim is not automatically word-neutral.** The trim removed 5 words;
  the `(e)` augmentation added 13. Rule 4 gates both, so measure words too — the body
  finished at 4,564/5,000, but a bigger augmentation with the same 0-line cost could still
  have failed the second half of the rule.
- **Extraction by absolute line span is safe here only because the spans were re-verified.**
  Spec 05 §3.2's table was written against a 341-line file; item 013's Step-3c relocation
  grew it to 351. The eight section boundaries L23/L83/L112/L153/L169 were unchanged (the
  growth is all in the last section), so the table's spans still held — but `grep -n '^#'`
  first, every time.
- Adapters: this restaged 12 modified paths and added **6** new ones — `agent-selection.md`
  reaches all six bundles including `adapters/pi/`, which is the #122/#132 failure class
  item 017 re-checks.

## Item 017 — six-target reconciliation, fixture refresh, BATCH §9 record

R1–R6 are all landed, so this item is a **verification** sweep, not a mutation. Net canon
change: **zero** — `adapters/` was already fresh and `build-adapters.py --check` exited 0
*before* any work here, because items 001/002/004/005/006/007/008/009/010/011/012/013/015
each regenerated in their own commit exactly as their ACs required. The only files this
item writes are `tests/test_agent_targets_parity.py`, a 4-line constant fix in
`tests/test_build_adapters.py`, and the batch §9 record.

### The five-vs-six drift was real, and the test constant was the only thing hiding it

`scripts/build-adapters.py` L49 has been the six-tuple since the Pi target landed in
0.13.0; `tests/test_build_adapters.py` L38 was still the **five**-tuple. Three tests
parametrize over that local copy — `test_bundle_is_self_contained`,
`test_cited_shared_references_fan_out_skill_local`, `test_forge_root_is_verbatim` — so
`adapters/pi/` had **zero** per-target coverage from any of them. Fixing the constant added
3 passing tests with no other edit: pi was correct all along, just unasserted. That is the
worst shape for a gap (silent, not red), and exactly the #122/#132 failure class.

**The drift guard had to leave `test_build_adapters.py`.** That module carries a
module-level `pytestmark = pytest.mark.skipif(not _generator_yaml_available(), …)`, so a
guard placed there no-ops in precisely the bare-`pytest tests` environment CI uses. New
module `tests/test_agent_targets_parity.py`: regex-parses the `AGENT_TARGETS = (...)`
literal out of **both** files and `ast.literal_eval`s it — never imports the generator
(hyphenated name, `import yaml` at module scope) — and carries a
`test_this_guard_is_not_skippable` that greps its own source for `skipif(` /
`importorskip(` / `pytest.skip(`, so the gate cannot be reintroduced later.

Mutation-tested: reverting L38 to the five-tuple → 2 red
(`test_test_module_declares_the_six_targets`, `test_the_two_constants_are_equal`), both
reporting the tuple diff. Restored with `command cp -f`; `git diff --stat` confirms only
the intended 4-insert/1-delete hunk.

### The gemini fixture was already fresh — the procedure still matters

Ran the real procedure rather than asserting from the green test: copy
`tests/fixtures/minimal-canon/` to a scratch dir, delete its `expected-adapters/`, build
`--root <scratch>`, then `command cp -rf` the scratch output into the fixture.
`diff -rq` scratch vs committed → **identical across all six targets**, and the post-`cp`
`git status` is empty.

Why it stays fresh under heavy canon churn: `minimal-canon` is a **self-contained** canon
tree (its own `noarg`/`with-refs` skills, a 2-line `forge-session.py` stub) with no
dependency on the real `skills/`. Confirmed by inspection — the fixture's gemini bundle
ships `noarg`/`with-refs`, the real adapter ships `forge*`. That inspection **is** the
"not by copying the real adapter" evidence: a real-adapter copy would be visible instantly
in that listing.

### Host-neutrality: census equality, not test-widening

`tests/test_adapter_host_neutrality.py` passes unchanged, and its two deliberate scope
limits (skill **bodies** only, `references` excluded; `NON_CLAUDE_TARGETS` excludes `pi`)
were **not** widened — widening goes red on ~25 pre-existing committed reference files per
target, and the only way to green it would be rewording frozen text.

The correct assertion is a **census equality** against the source span, and it holds
exactly as the item predicted:

| Move | source census | destination census | delta |
|---|---|---|---|
| R1: `verification-checklists.md` @baseline → 6 mode files + `findings-template.md` | `AskUserQuestion` ×1 | modes ×0, `findings-template.md` ×1 | **0** |
| R6: `runner-contract.md` @`c532602` → `runner-contract.md` + `agent-selection.md` | `Monitor` ×1, `AskUserQuestion` ×4 | 1+0 / 3+1 | **0** |

Reusable: import `FORBIDDEN_TOKENS` **from the test module** rather than retyping it — a
hand-copied token list is the one way this census can silently disagree with the gate.

### BATCH §9 record — method notes

`specs/context-efficiency/.verification/BEHAVIOR-PRESERVATION-BATCH-item-017-2026-07-29.md`.
SC-3 evidence for R1/R3/R5; R4/R6 re-confirmed at the combined end state.

- **Baseline is the pre-feature commit `9a29e846…`**, not the previous commit. The four
  per-unit records each diffed against their own immediate predecessor, which is right for
  a *unit* claim and wrong for a *batch* one. Result: **108/139** canon sections
  byte-identical, and every one of the 31 changed sections differs only in state-write
  mechanics, a citation target, or the two REQ-BEHAV-02 adaptations accepted at item 002.
- **The strongest single artifact is the AskUserQuestion line-set diff.** Grep every line
  in `skills/`+`references/` containing `AskUserQuestion` **or** `(recommended)`, at both
  revisions, whitespace-normalize, sort, diff. **106 lines at both; 103 byte-identical; 3
  differ** — and all 3 differ only *outside* the prompt (two epic-backflow JSON clauses →
  `state-ecr`, one `(d-model)` citation → `agent-selection.md`). Per-file counts also match
  everywhere, with the two split relocations accounting for themselves exactly. That is a
  far tighter claim than a section-level diff and takes one command.
- **Surfaces 6 and 7 reduce to md5 equality** — directive-heading set, verifyGate routing
  lines, and the sentinel/NEXT-STEPS line set are each byte-identical across the batch.
- **R1's `§9` substitute was run for real** on a large mode (backlog, 27 checks): 27 of 27
  executed, 21 pass / 0 fail / 6 n/a, deterministic pre-check
  `rauf-stable backlog validate … --json` → `{"valid": true, "findings": []}`. Named
  deviation: a **single inline verifier**, not the 4-way dispatched fan-out the skill
  prescribes for large modes — item 017 declares no `agentDelegation`, so subagent dispatch
  is not available to the iteration. Verifier count does not affect what the substitute
  measures (does a leaf loading only `backlog.md` execute the same 27 checks and render the
  same document shape). The shape claim is additionally *unfalsifiable-by-construction*:
  `findings-template.md` L5+ is byte-identical to monolith L325–477.
- Pre-split comparison artifact for the shape diff: `.verification/VERIFY-backlog-2026-07-29.md`,
  added at `ed3ab41` — **before** item 001's `ca3da53`, so it is a genuine monolith-era
  document, not a reconstruction.
- **`zsh` gotcha:** `git show $rev:path` is mangled by the `:r` history modifier
  (`$BASE:references/…` → `…60951eferences/…`). Use `"${rev}:path"`.

### Gates

`build-adapters.py` exit 0 · `--check` exit 0 · `pytest tests` **653 passed / 2 skipped**
(up 15 from the 638 recorded at item 014: +8 from item 015's
`tests/test_runner_contract_split.py`, +4 this item's parity guard, +3 the pi
parametrizations the constant fix unlocked) · `check-spec-purity` PASS ·
`bash scripts/validate.sh` PASS.

## Item 016 — the catch-all citation, body-cap and always-loaded-surface guards

Two new tests-only modules, both importing canon paths from `tests/_forge_paths.py`:
`tests/test_reference_citations.py` (guards 1+2, 6 tests) and
`tests/test_always_loaded_surface.py` (guards 3+4, 31 tests). No canon edit, so
`adapters/` was NOT restaged and no regeneration was needed — same shape as item 014,
whose ACs likewise omit the adapters criterion.

### Regex validation against the PRE-FEATURE BASELINE (AC 1)

Recorded here as well as in the commit message, since the iteration agent does not commit
(same convention as items 002/004/006/012/013/015).

Baseline commit **`9a29e846ed510c3b245876a9bf4cc73b8cb60951`** — the hash in
`specs/context-efficiency/.pipeline-state.json` under `stages['forge-4-backlog'].commitHash`,
**not** `HEAD~`. Extracted with `git archive <hash> skills references | tar -x -C /tmp/...`
so the check runs against a real tree rather than a reconstruction.

| tree | resolvable citations | templated (skipped) | misses |
|---|---|---|---|
| baseline `9a29e846` | **118** | 4 | **0** |
| current (post R1–R6) | **134** | 5 | **0** |

118/0 is exactly the figure spec 06 §5 records, so the pattern is green pre-change and any
future red is a real regression. The count moved 118 → 134 because items 002 (six literal
mode citations + `findings-template.md`), 004 and 015 (`agent-selection.md`) changed the
citation set — which is why **nothing in the guard pins a total**.

The naive `references/([A-Za-z0-9_][A-Za-z0-9_./{}*-]*)` was run against the same baseline
and produces its documented **3 false positives**, unchanged on the current tree:
`forge-2-tech: references/stack-decisions.md` ×2 (the `.agents/` and `.claude/`
project-level paths) and `forge-5-loop: references/runner-contract.md.` (sentence-final
period). Both are pinned by **fixture strings**, not live line numbers — L61/L165 will
drift, the sentences will not.

### Mutation evidence — eight mutations, all red, all restored

Every mutation was applied, the guard run, then the file restored with `command cp -f`
from a `/tmp` backup and confirmed byte-restored via an empty `git diff --stat`.

1. dangling `references/does-not-exist.md` appended to `forge/SKILL.md` →
   `test_every_citation_in_every_skill_body_resolves` red, naming the skill and path.
2. `references/agent-selection.md` citation removed from `forge-5-loop` →
   `test_every_new_or_moved_reference_file_is_still_cited` red (AC 3).
3. 3 padding lines appended to `forge-5-loop/SKILL.md` →
   `test_skill_body_is_within_the_line_cap[forge-5-loop]` red at `301 lines (cap 300)`.
4. one char added to `forge-verify`'s frontmatter description →
   `test_frontmatter_description_budget_not_increased` red at `4689 chars (ceiling 4688)`
   (AC 5 — a one-character increase is detected).
5. `session-check.sh` made to echo on the common path → silence test red.
6. `session-check.sh` `find` short-circuited to a no-op → **control** test red
   (`forge-init` absent). Mutations 5+6 are the bidirectional pair.
7. an existence check inserted around the common-path hook test →
   `test_the_hook_guards_cannot_degrade_to_a_skip` red (AC 7).
8. `CITE_RE` reverted to the naive form → forward guard red with the 3 false positives
   **and** the project-level fixture test red.

### Learnings

- **A self-scanning "cannot degrade to a skip" guard matches its own banned list.** The
  first version stored `("is_file(", "exists(", …)` and failed on its own source. Assemble
  the call form at runtime (`f"{banned}("` over bare names, item 017's precedent), and keep
  the constructs out of the prose too — the module docstring originally said "behind an
  `if hook.is_file()` skip" and tripped the same assertion. Prose says "existence check".
- **The forward citation guard is vacuous without a floor.** Every "zero unresolved"
  assertion is satisfied by a regex that matches nothing, and mutation 8 would have gone
  *green* under a pattern that simply stopped matching. `MIN_EXPECTED_CITATIONS = 100` is a
  non-vacuity floor, deliberately not the measured 134 — the AC forbids pinning a total
  because items 002/004/015 move it.
- **Forward and reverse are genuinely independent** (same argument as item 004's
  presence-vs-conditionality pair): a dangling citation is invisible to the reverse guard,
  and an unshipped file is invisible to the forward one. Neither alone is coverage.
- **`EXPECTED_SKILL_COUNT = 13` is pinned so deletion cannot create headroom.** The
  frontmatter budget is a *sum*; delete a skill and the total drops, silently licensing
  growth elsewhere. Both the description count and the skill-file count are asserted.
- **Quote-inclusive is the only defensible frontmatter measurement.** Raw = **4688**,
  quote-stripped = **4662**; adopting the stripped sum grants 26 chars of undetectable
  growth against a non-increase requirement. Re-measured on the current tree: 4688 exactly,
  unchanged from the 0.13.0 baseline (largest description `forge-guide` 528, smallest
  `forge-fix` 269).
- **Word counting mirrors `check-spec-purity` exactly** —
  `sum(len(line.split()) for line in body_lines)`, not `len(text.split())`. Current maxima:
  `forge-5-loop` **298 L / 4,564 w** (the item's predicted max), then `forge-0-epic` 292 L
  and `forge` 4,083 w. The line cap is the binding one; the word cap has ~9% headroom.
- The caps are duplicated (`MAX_BODY_LINES`/`MAX_BODY_WORDS`) rather than imported from
  `check-spec-purity.py` — hyphenated module name, and a guard that broke on an import
  error would be indistinguishable from one that passed. The same reasoning item 017 used
  for the `AGENT_TARGETS` parity guard.
- **`zsh` gotcha, re-hit:** `git archive $HASH skills references` is fine, but a bare
  `git show $rev:path` is mangled by the `:r` history modifier — item 017 logged this.

### Gates

`python3 -m pytest tests` **690 passed / 2 skipped** (up 37 from item 017's 653: 6 + 31
from the two new modules) · `ruff check scripts/ eval/` PASS · `check-spec-purity` PASS ·
`build-adapters.py --check` exit 0 (untouched — tests-only item) ·
`bash scripts/validate.sh` **PASS**.

## Item 018 — `state-*` verbs wrote the wrong feature's state for epic members

Two halves, both landed: a fail-closed write resolver in `scripts/forge-session.py`
and an unambiguous `--epic` rule threaded through every `state-*` call site in canon.

### The defect, reproduced and fixed

With `specs/api/.pipeline-state.json` (standalone) **and**
`specs/checkout/api/.pipeline-state.json` (epic member) both present:

| | before | after |
|---|---|---|
| `state-enter --feature api` (no `--epic`) | exit **0**, printed `entered forge-2-tech (in-progress) for api`, mutated the **standalone** file, left the member untouched | exit **2**, `Error: ambiguous feature 'api': 2 directories carry a state file (…) — pass --epic <epic> …`, **neither** file touched |
| same + `--epic checkout` | n/a | exit 0, member written, standalone byte-identical |
| two epics, same member name | exit 2 for the **wrong reason** (`no feature directory at …`, a nonexistent flat path) | exit 2 naming both candidates |

### `_resolve_feature_dir_for_write` is a NEW function, not a flag on the old one

Deliberately not a `strict=` parameter: `_resolve_feature_dir` (L1504) is the
**reader's** resolver and its tolerance is correct for `stage-exit`, which is
read-only and downgrades an unresolvable dir to `{}`. Widening it would have changed
that path too. The two now differ by design, and
`test_the_writer_is_not_more_permissive_than_the_canonical_resolver` pins the
asymmetry — the same shape as item 007's `_read_state` vs `_load_state_for_write`
guard, and for the same reason: a future "simplification" that merges them
reintroduces the silent cross-feature write.

The rule mirrors `epic-manifest.py resolve` step 4 (`shared-conventions.md`
"Resolution algorithm"): **more than one match anywhere → ambiguous, hard stop.**
A writer must not be more permissive than the resolver that produced
`{resolvedFeatureDir}` — that was the argument that settled the design.

Preserved unchanged (AC 5): a lone flat feature, a lone nested member, and the
**zero-candidate first-write** case (`state-branch` firing before the entry stamp
against a bare `specs/{feature}/`, item 011's finding) all still resolve from a bare
name. Only `len(candidates) > 1` raises.

### Canon: one categorical rule + 14 per-fence pointers

`--epic` cannot be hard-coded into the fences the way `state-ecr` does it: `state-ecr`
is *only* reachable on the epic-backflow path, so `{epic}` is always bound there,
while every other `state-*` fence serves standalone features too — a literal
`--epic "{epic}"` would substitute to `--epic ""` for a standalone. A bracketed
`[--epic …]` form would break the fence as runnable bash. So the AC's sanctioned
prose route was taken:

- **`shared-conventions.md` "Pipeline State Protocol"** gains the categorical rule
  ("required whenever the feature is an epic member … append it to every `state-*`
  call in this file and in every skill body"). That section is the always-loaded
  surface ~10 skills already read, so it governs every fence at once.
- Each of the 14 fence intros gains a one-clause pointer to it. **All 9 edited files
  are line-neutral or nearly so** (`git diff --numstat`: every `skills/*` file is
  n-added/n-removed) — clauses were appended to existing sentences, never as new
  lines. `forge-5-loop` stayed at its measured 298 body lines / 4,600 words, so the
  R6 headroom is intact.

### Deliberate non-edit: the spec still says `_resolve_feature_dir`

`specs/context-efficiency/03-state-verbs.md` §3.1 (table row) and §3.4 (the
`_load_state_for_write` code block, L229/L252) plus `00-core-definitions.md` §3.3
(L154/L168) all prescribe reusing `_resolve_feature_dir` on the write path — i.e.
**the spec propagated this defect**, exactly as it did for item 019's cascade. I
edited the §3.1 row and then **reverted it**: `specs/CLAUDE.md` says not to fix
spec↔code divergence unless explicitly asked, and item 018's ACs (unlike 019's,
which name the spec fix outright) are silent on the specs. Flagged here **for owner
review** rather than silently adapted — if item 019's spec-sync precedent is meant
to apply here too, four passages need the same repoint.

### Gates

`python3 -m pytest tests` **695 passed / 2 skipped** (up 5 from item 016's 690) ·
`check-spec-purity` PASS · `build-adapters.py --check` exit 0 (regenerated: the two
shared references fan out widely again) · `bash scripts/validate.sh` **PASS**.
