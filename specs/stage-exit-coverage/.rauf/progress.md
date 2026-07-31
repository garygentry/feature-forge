# Progress — stage-exit-coverage

## Item 001 — shared exit/verify constants + additive schema fields

Landed `00-core-definitions.md` §2 / §4 / §6 into `scripts/forge-session.py`, the
`auto-verify-pending` status into both scripts and the state schema, and rewrote the two
guards that pinned the old vocabulary.

### Gotchas for later items

- **`EXIT_STAGES` already existed** in `scripts/forge-session.py` (the five-stage
  authoring subset, `Final[tuple[str, ...]]`, used as `stage-exit --stage` argparse
  `choices`). Defining the derived nine-value `EXIT_STAGES` in the constants block
  silently shadowed it — with the whole suite still green, because the *later*
  assignment won and it was a superset. The pre-existing tuple is now
  `_STAGE_EXIT_CLI_STAGES`, documented as the interim subset the router can actually
  serve. **Item 010 owns folding it away**: once `stage_exit` handles all nine, delete
  `_STAGE_EXIT_CLI_STAGES` and point the argparse `choices` at `EXIT_STAGES`. A parity
  test asserts `set(_STAGE_EXIT_CLI_STAGES) <= set(EXIT_STAGES)` in the meantime.

- **`NEXT_STEPS_SENTINEL` was also already defined** further down, in the "Scripted Stage
  Exit" section. Same silent shadowing. Removed the lower copy; the constants-block one
  carries the original comment.

- **Ruff does NOT catch either of those.** `F811` covers redefined imports, functions,
  and classes — not plain module-scope names. `tests/test_stage_constants_parity.py`
  now has `test_each_shared_constant_is_assigned_exactly_once` covering the shared
  constants. Before adding a constant in a later item, grep for the name first.

- **`PRE_R4_SCHEMA_CONTRACT_SHA256` is gone**, replaced (per item 001) by a split guard in
  `tests/test_state_schema_conformance.py`:
  `verifyEntry` is compared as a **parsed object** against
  `PRE_STAGE_EXIT_VERIFY_ENTRY_CONTRACT` with the three intended additions reversed, and
  everything *outside* `verifyEntry` is still digest-pinned as
  `SCHEMA_CONTRACT_OUTSIDE_VERIFY_ENTRY_SHA256`. That digest is **not** a re-pin: it is
  byte-for-byte what the pre-feature schema produces (verified against `git show HEAD:`),
  so it keeps proving the rest of the schema is untouched. Item 002 changes
  `epic-manifest-schema.json`, not this one, so it should not need to move it.

- **`KNOWN_VERIFY_STATUSES` is now a multi-line set literal** in both scripts (six values
  would exceed ruff's 100-char line length on one line). The parity guard compares the two
  blocks **textually**, so keep the formatting identical in both files — reformatting one
  side alone fails `test_the_two_copies_are_byte_identical`.

- Adding `auto-verify-pending` to `KNOWN_VERIFY_STATUSES` already stops
  `epic-manifest.py::_verify_status_warnings` emitting the unknown-status warning (item
  009's first bullet is therefore satisfied as a side effect of item 001; the rest of 009
  — routing, obligation warnings, epic freshness — is still open). `_VERIFY_RESOLVED` was
  deliberately left unchanged, and a guard asserts `auto-verify-pending` stays out of it.

- The four §4/§6 TypedDicts are **byte-identical** to the spec, comments included (checked
  with a diff script). If a later item edits one, re-check against
  `specs/stage-exit-coverage/00-core-definitions.md` — the comments carry normative
  invariants that live nowhere else.

### Verification

`bash scripts/validate.sh` exit 0 with `PASS: epic-manifest pytest suite`;
`python3 -m pytest tests -q` → 730 passed, 2 skipped (both pre-existing);
`ruff check scripts/ eval/` clean; `python3 scripts/build-adapters.py --check` reports no
drift.

## Item 002 — canonical epic manifest revision

Added the required top-level `revision` to `references/epic-manifest-schema.json` and
`scripts/epic-manifest.py`, made `load_manifest` synthesize logical `1` for legacy files,
and moved the single increment into `_bump_and_write`.

### Gotchas for later items

- **`load_manifest` now MUTATES the dict it returns** (inserts `revision: 1` when the key
  is absent). It still never writes. Any later item that compares "what load_manifest
  returned" against "what is on disk" must ignore `revision` — that is exactly what the
  new `_semantic_manifest(manifest)` helper does (it drops `updatedAt` and `revision`).
  Item 006/009 read the revision via `load_manifest`, so legacy epics classify at
  revision 1 rather than erroring.

- **`_bump_and_write` re-reads the manifest from disk** to run the no-op comparison, then
  takes `current` revision from that read (falling back to 1 for a legacy/malformed
  predecessor). Order is deliberate and spec-fixed (03 §2.2): **no-op check → validate →
  bump → single `atomic_write`**. A semantic no-op therefore returns `[]` with exit 0 and
  does *not* refresh `updatedAt`; a test asserts byte equality, so do not "helpfully" add
  a timestamp refresh.

- **`bool` is an `int` subclass.** The validator explicitly rejects `True`/`False` before
  the `isinstance(int)` test — otherwise `True` validates as revision 1 and then
  arithmetic-increments to `2`. The same guard is duplicated in `_bump_and_write`'s
  `current` computation.

- **`_TOP_REQUIRED` doubles as the unknown-top-level-key allow-list**, so adding
  `revision` there covers both the required-key check and the `unknown key` check in one
  edit. No separate list exists.

- **Epic creation has no subcommand** — the manifest is composed by
  `skills/forge-0-epic/SKILL.md` Step C5, so "creation writes `revision: 1`" is a canon
  edit (a bullet in the C5 field list), pinned by a test that greps the skill body.

- **`fixture_copy` can only be called ONCE per test** (it copytrees into
  `tmp_path/<name>`; a second call raises `FileExistsError`). Loop over bad values by
  rewriting the one copied manifest in place, not by re-copying.

- Fixtures `tests/fixtures/valid-epic/auth-overhaul` and
  `tests/fixtures/status-derivation/lifecycle` now carry `revision: 1`. The other epic
  fixtures (`cyclic-epic`, `path-escape`) were deliberately left legacy — they are
  already-invalid fixtures and the synthesized-1 path keeps them producing exactly the
  findings their tests assert.

### Verification

`bash scripts/validate.sh` exit 0 with `PASS: epic-manifest pytest suite`;
`python3 -m pytest tests -q` → 747 passed, 2 skipped (both pre-existing);
`ruff check scripts/ eval/` clean; `python3 scripts/build-adapters.py --check` no drift.

## Item 003 — mirrored duplicate-aware JSON loader

Copied the 05 §2.1 `load_json_with_duplicates`/`warn_duplicate_keys` pair verbatim into
`scripts/forge-session.py` (above `_load_config`) and `scripts/forge-bootstrap.py` (above
`commit`), rewrote `_load_config` per 05 §3.1 and the bootstrap config read per 05 §3.2, and
added the `tests/test_json_loader_parity.py` drift guard. **No shared module was created** —
`RUNTIME_HELPERS` is still six entries and no new file exists under any `scripts/`.

### Gotchas for later items

- **Nested duplicates report BEFORE their container.** `object_pairs_hook` completes inner
  objects first, so `{"commitPrefix":"a","commitPrefix":"b","loopRunner":{"bin":"x","bin":"y"}}`
  warns about `bin` on the FIRST line and `commitPrefix` on the second. Item 004's ordering
  assertions must expect decoder-hook order, not source order. Do not sort or dedupe.

- **The two `#: mirrors …` comments are single-line in source but wrap in the spec.** The spec
  renders them across two lines; in both scripts they are one physical line (ruff's 100-char
  limit is not exceeded — they are 94 and 92 chars). The parity guard asserts the literal
  comment string and requires it to sit on the line immediately preceding
  `def load_json_with_duplicates(`.

- **The guard compares only from the `def` line onward** and dedents the whole block as a unit
  (`textwrap.dedent(block)`), never per line — per-line stripping would flatten the nested
  `object_from_pairs` closure and mask a real divergence. Verified by hand that inserting a
  trailing comment into ONE copy fails `test_the_two_copies_are_identical` and nothing else.

- **The `except OSError: pass` around `warn_duplicate_keys` in `_load_config` is load-bearing,
  and the two consumers diverge deliberately** (05 §3.3): session swallows the stderr write
  failure and still returns the parsed dict (so `rank-features --json | head` cannot turn a
  `BrokenPipeError` from a *diagnostic* write into exit 2), while `forge-bootstrap.py commit`
  keeps propagating it under its existing exit-2 policy. Item 004 must pin both sides.

- **`from exc` was added to the bootstrap `raise UsageError(...)`** per 05 §3.2 (the pre-existing
  line had a bare `raise`). Ruff did not require it; the spec text does.

- **Confirmed behavior matrix** (checked directly, not just via the suite): `_load_config`
  returns `{}` for missing / unreadable (chmod 0) / malformed / scalar-root / array-root, and
  returns the dict after warning otherwise; `commit` raises `UsageError` for malformed,
  unreadable, and non-object roots, and uses the LAST `commitPrefix` on a duplicate.

- **Shell gotcha for future iterations:** `cp` is aliased to `cp -i` in this environment, so a
  `cp backup original` restore hangs waiting for a prompt. Use `command cp -f`.

### Verification

`bash scripts/validate.sh` exit 0 with `PASS: epic-manifest pytest suite`;
`python3 -m pytest tests -q` → 753 passed, 2 skipped (both pre-existing);
`ruff check scripts/ eval/` clean; `python3 scripts/build-adapters.py --check` no drift (all 12
adapter copies of the two scripts regenerated).

## Item 004 — duplicate-key coverage across both copies and both CLIs

Test-only, as scoped: `scripts/` is untouched. Added the 07 §5.1 matrix (parametrized over
BOTH mirrored copies), the negative control, the real-CLI matrix, the bootstrap `commit`
rows, and the distribution-boundary loader assertions.

### Gotchas for later items

- **Only `adapters/pi/scripts/forge-session.py` differs from canon.** Verified against the
  real tree: `forge-bootstrap.py` is byte-equal on all six targets, and `forge-session.py`
  on all but Pi. Pi's single permitted divergence is the literal
  `"/feature-forge:" -> "/skill:"` replacement applied by
  `_translate_pi_support_command_strings` — **not** `translate_host_terms`, which also
  rewrites `--host claude` and `/clear` and does NOT run over runtime helpers. Using
  `translate_host_terms` to predict the Pi helper fails.

- **Executing an emitted adapter script writes `__pycache__` into `adapters/`.** That is
  drift the `--check` gate would flag. Any test that imports/execs a bundled helper must
  pass `-B` (and `-I`, so the bundle rather than the repo supplies the imports).

- **The mirrored-block extractor is now single-sourced.**
  `tests/test_json_loader_parity.py::mirrored_loader_pair` is the public alias;
  `tests/test_build_adapters.py` and `tests/test_effective_config.py` both call it.
  Do not add a third copy — a drifting extractor would silently pass.

- **`forge-bootstrap.py commit` renders the config path RELATIVE** (`forge.config.json`),
  because the CLI is invoked with target `"."` from inside the repo. Warning-line
  assertions there must not use an absolute `tmp_path`.

- **`commit` runs `git add` over `artifactsWritten` BEFORE reading the prefix.** A
  mode-000 `forge.config.json` therefore fails inside git, never reaching the loader's
  `OSError` branch. The portable way to exercise that branch at CLI level is a *directory*
  named `forge.config.json` containing one file: it stages cleanly and `read_text` raises
  `IsADirectoryError`.

- **An always-unwritable fd 2 makes CPython exit 120** flushing at shutdown, which masks
  the exit code under test. The suite injects a stderr whose *first* write raises instead
  (`test_effective_config.run_with_failing_stderr`, shared with the bootstrap module):
  the first write is the duplicate warning, and later writes still land so
  bootstrap's `Error:` line stays observable. This is what pins the 05 §3.3 asymmetry —
  session exit 0 with the advisory dropped, bootstrap exit 2.

- **Decoder-hook order, re-confirmed at CLI level.** For a config with a root duplicate
  plus nested `loopRunner`/`autoVerifyStages` duplicates, stderr order is
  `bin`, `forge-1-prd`, `autoVerify` — nested first, root last, regardless of source order.

- **Control characters in test data:** build them with `chr(7)` rather than embedding a
  raw byte, so the file stays greppable and diffable.

### Verification

`bash scripts/validate.sh` exit 0 with `PASS: epic-manifest pytest suite` and
`PASS: adapters/ matches a fresh generation (no drift)`;
`python3 -m pytest tests -q` -> 852 passed, 2 skipped (both pre-existing);
`python3 -m pytest tests/test_effective_config.py tests/test_forge_bootstrap.py
tests/test_build_adapters.py -q` -> 234 passed, 2 skipped; `ruff check scripts/ eval/` clean.

## Item 005 — state-verify writer (feature-target result mode)

Landed the eighth `state-*` verb: `cmd_state_verify` plus three private helpers
(`_require_positive_int`, `_validated_findings_file`, `_current_artifact_version`,
`_verify_result_entry`), the 03 §3.1 argparse surface, dispatch, and a `_print_state_verify`
one-liner. The 00 §6 docstring is byte-identical to the spec (verified with a diff script),
signature included.

### Gotchas for later items

- **`state-verify`'s `--json` echo is NOT the state document.** Every other verb returns the
  mutated state dict; this one returns `{feature, stage, verifyKey, statePath, entry,
  updatedAt}` per 00 §6's `Returns:`. Its printer therefore takes the RESULT, not a state
  dict — do not "fix" it to match the other `_print_state_*` signatures. Items 006/007 must
  keep the same shape (epic writes should report the `.epic-state.json` path in `statePath`).

- **Two deliberate not-yet-implemented `UsageError`s live in `cmd_state_verify`**, both
  reachable from the registered CLI: `--stage forge-0-epic` (item 006 replaces it with the
  epic branch) and `--commit-hash` (item 007 replaces it with commit-2 mode). Both are
  covered by `test_state_verify_defers_the_epic_target_and_commit_2_mode` — that test must be
  REPLACED, not deleted, when each branch lands. The mode-exclusivity checks around them
  (neither-mode / mixed-mode) are already final and must survive.

- **`--stage` choices come from the new derived `VERIFY_STAGES`** (`("forge-0-epic",
  *VERIFY_TOKEN_BY_STAGE)`) and `--status` from the new derived `VERIFY_RESULT_STATUSES`
  (`get_args(VerifyStatus)` minus `pending`). Both are derived, per item 001's no-second-copy
  rule — do not hand-list either.

- **A NUL byte cannot travel through `subprocess` argv** (`ValueError: embedded null byte`
  before the process even starts), so the NUL row of the `--findings-file` containment matrix
  is exercised IN-PROCESS against `FS.cmd_state_verify`, not through `_run`. The other control
  characters (`\x07`, `\n`) do go through argv fine. Any later containment matrix needs the
  same split.

- **`updatedAt` refresh assertions need a backdated `updatedAt`.** `_now_iso` is
  second-precision, so a test that writes state and immediately re-writes it inside the same
  second sees an unchanged timestamp and a "nothing moved" assertion passes vacuously (it
  cost one real failure here). Seed the pre-state with `"2020-01-01T00:00:00Z"` — the same
  trick the pre-existing cross-verb `updatedAt` test uses.

- **`skipped` is the only status that works against a never-written state file** (everything
  else needs the served stage's recorded `version`, per 03 §3.3's "result statuses other than
  `skipped` fail if that artifact version is absent"). That is why both `_VERB_INVOCATIONS`
  tables register `--stage forge-1-prd --status skipped` — the cross-verb guards run against
  an empty feature dir. Do not "improve" it to `passed`.

- **`passed` accepts `--findings-count 0` but rejects `--findings-file`.** 03 §3.3's forbidden
  column says only "findings count, if supplied, must be `0`", while 07 §4.2 lists "findings
  metadata on passed" among the contradictory-metadata rejections. The reconciliation
  implemented here: file always rejected on `passed`, count rejected unless it is exactly 0.

- **Each status REPLACES the entry rather than patching it** (`_verify_result_entry` builds a
  fresh dict). That is what makes the matrix's "clear …" columns exact and the scheduling keys
  DELETED rather than nulled. `findings-applied` is the one status that copies anything
  forward — `findingsFile`/`findingsCount` from the prior entry.

- `_stage_version` returns a raw `isinstance(x, int)` value, so a `True` recorded in state
  would pass it; `_current_artifact_version` funnels it through `_require_positive_int`, which
  rejects `bool` explicitly. Item 012's scheduling path should reuse
  `_current_artifact_version`, not re-read `version` itself.

### Verification

`bash scripts/validate.sh` exit 0 with `PASS: epic-manifest pytest suite` and
`PASS: adapters/ matches a fresh generation (no drift)`;
`python3 -m pytest tests -q` -> 885 passed, 2 skipped (both pre-existing);
`ruff check scripts/ eval/` clean; `python3 scripts/build-adapters.py --check` no drift.

## Item 006 — state-verify epic target (`.epic-state.json`)

Added `_load_epic_state_for_write` and branched `cmd_state_verify` on
`stage == "forge-0-epic"` BEFORE the `VERIFY_TOKEN_BY_STAGE` lookup. Two new constants in
`scripts/forge-session.py`: `EPIC_STATE_FILENAME` and `SAFE_NAME_RE` (plus a private
`_assert_safe_name`).

### Gotchas for later items

- **`forge-session.py` had NO name-safety check before this item.** `SAFE_NAME_RE` /
  `_assert_safe_name` are new here and are applied ONLY on the epic branch — the
  feature/member write path is unchanged, because widening it would change behavior for
  existing standalone/member names outside this item's scope. Item 016's "unsafe member
  name remains a `UsageError`" can reuse `_assert_safe_name` rather than adding a third
  copy of the predicate.

- **`_commit_state` is target-agnostic and is reused for the epic write.** It is not "the
  member-feature writer" — that is `_load_state_for_write`/`_resolve_feature_dir_for_write`,
  and the epic branch never calls either. Its docstring was widened by one `Args:` entry to
  say so. Item 007's commit-2 mode and item 012's scheduling should reuse
  `_load_epic_state_for_write` + `_commit_state` the same way.

- **`_load_epic_state_for_write` seeds `updatedAt: None`** so a freshly created
  `.epic-state.json` serializes in 03 §2.1's documented key order (`epic`, `updatedAt`,
  `stages`). Every caller must stamp it via `_commit_state` before writing — the null is a
  placeholder that never reaches disk. A future caller that writes through raw
  `_write_state` would persist it.

- **The revision is read inline, NOT via `epic-manifest.py::load_manifest`.**
  `forge-session.py` stays self-contained (no cross-script import; item 015's `render-status`
  subprocess is the only sanctioned crossing). The legacy rule is duplicated behaviorally:
  a manifest with no `revision` key reads as logical `1` and its bytes are NOT rewritten.
  A present `revision` goes through `_require_positive_int`, so `true`/`0` are rejected.

- **Epic freshness compares against the MANIFEST revision, never a member stage version.**
  The stale-version error message branches on the target so it names
  "`{epic}`'s manifest is at revision N" instead of "`{stage}` is at version N". The
  feature-target wording is byte-unchanged.

- **`--epic` is accepted on the epic branch when it EQUALS `--feature`** (03 §3.2 step 2
  says "None or exactly equal"), and rejected otherwise. Skills stamping the epic fence
  may therefore pass either form.

- **07 §4.3 restricts `monkeypatch` to `tempfile.mkstemp` / `os.fsync` / `os.replace`.** A
  first draft proved epic/member disjointness by patching `_load_state_for_write` to raise;
  that was replaced with an on-disk test (`test_neither_target_falls_back_to_the_other`)
  using a directory that is BOTH an epic root and a feature — the adversarial fixture that
  makes a wrong-file write observable without any mock. Prefer that shape for the remaining
  isolation items.

- **`.epic-state.json` has no JSON Schema** (03 §1 warning), so `tests/_state_schema.py`'s
  `validate_state` must NOT be pointed at it. The epic tests assert the literal minimal
  shape instead.

### Verification

`bash scripts/validate.sh` exit 0 with `PASS: epic-manifest pytest suite` and
`PASS: adapters/ matches a fresh generation (no drift)`;
`python3 -m pytest tests -q` -> 901 passed, 2 skipped (both pre-existing);
`ruff check scripts/ eval/` clean.

## Item 007 — commit-2 provenance, full-hash validation, single-writer guard

Landed commit-2 mode in `cmd_state_verify`, the shared `_assert_full_commit_hash` guard on
both writers, the REQ-REL-04 single-writer guard, and the no-`--amend` canon guard. No
schema moved — the 40-hex rule is a WRITE boundary only.

### Gotchas for later items

- **`_load_verify_target(specs_dir, feature, epic, is_epic_target)` is new** and is now the
  single resolver both `cmd_state_verify` modes go through (it wraps
  `_load_epic_state_for_write` / `_load_state_for_write` and returns
  `(state_path, state, revision|None)`). Item 012's scheduling path should call it rather
  than re-branching on `is_epic_target` — a third branch is how the two resolvers drift
  into each other's targets.

- **Validation order in `cmd_state_verify` is now: mode exclusivity → commit-2 metadata
  rejection → hash → target selection → commit-2 branch (early return) → result-mode
  metadata → load.** The commit-2 branch returns BEFORE the result-metadata block, so that
  block still only ever sees `status is not None`. Anything inserted between target
  selection and the commit-2 branch runs in both modes.

- **`_assert_full_commit_hash` fires in `cmd_state_complete` BEFORE
  `_load_state_for_write`**, so a malformed hash now out-ranks the older
  "stage is not complete" error. Two pre-existing tests passed `deadbeef` to reach that
  older message and had to be moved to a real 40-hex value. Any future test that wants the
  stage-status error must use a well-formed hash.

- **`_print_state_verify` grew a second parameter** (`commit_hash`), so `main()` dispatches
  it through a lambda like `state-complete` does. Commit-2 prints
  `recorded {verifyKey} commitHash: {hash}` — reporting the untouched status would read as
  if the result had been re-written.

- **The 07 §4.5 boundary tables are module constants in both test files** —
  `_ACCEPTED_HASHES`/`_REJECTED_HASHES` in `tests/test_state_verbs.py`,
  `ACCEPTED_HASHES`/`REJECTED_HASHES` in `tests/test_state_schema_conformance.py`. They are
  deliberately separate: the first file asserts CLI behavior, the second asserts the result
  still conforms. Extend both if the boundary moves.

- **`_epic_fixture` writes the MINIMUM manifest `state-verify` needs, which
  `epic-manifest.py render-status` rejects** (missing `charter`/`exposes`/`consumes`). The
  legacy-hash read-path test therefore overwrites the manifest with the full renderable
  shape. Any later test that runs `render-status` over an `_epic_fixture` epic needs the
  same upgrade.

- **The `--amend` guard is a NEGATION guard, not an absence guard.** Eleven canon files
  legitimately mention `--amend` — every one of them to forbid it — so
  `test_every_canon_mention_of_amend_forbids_it` requires each such line to also contain
  `never` or `without`, and `test_no_script_reaches_for_amend_at_all` bans the string
  outright under `scripts/`. A new prohibition worded differently ("do not use `--amend`")
  will fail the guard; add the wording to the accepted set rather than dropping the check.

- **`_MUTEX_TOKENS` includes `sleep`, `retry`, `O_CREAT` and `threading.`**, and is applied
  to seven functions on the write path (`_write_state`, `_commit_state`, both
  `_load_*_for_write`, `_load_verify_target`, `cmd_state_verify`, `cmd_state_complete`).
  A later item that adds a legitimate `time.sleep` anywhere in that set will trip it —
  that is the intent (REQ-REL-04 must be amended first), so route any waiting through a
  function outside the list rather than weakening the token set.

- **`_function_source(source, name)` slices one top-level `def` block** by scanning to the
  next unindented line. It asserts the name was found, and a negative control proves the
  slice is non-empty and stops before the next definition — a slicer returning `""` would
  satisfy every `not in` assertion vacuously.

### Verification

`bash scripts/validate.sh` exit 0 with `PASS: epic-manifest pytest suite` and
`PASS: adapters/ matches a fresh generation (no drift)`;
`python3 -m pytest tests -q` -> 950 passed, 2 skipped (both pre-existing);
`ruff check scripts/ eval/` clean.

## Item 008 — auto-pending classification in the session read-side paths

Ordered an `auto-verify-pending` branch ahead of the generic unresolved handling in both
`verify_state` and `_verify_state_for`, added `_scheduled_stage_version`,
`_warn_auto_verify_debt_metadata`, `AUTO_PENDING_DIAGNOSTIC`, and `auto_pending_message`,
and made `build_rows` emit the named 03 §5.3 sentence. All four signatures unchanged;
`_VERIFY_RESOLVED` untouched.

### Gotchas for later items

- **`pending_verify` and `build_rows` needed NO logic change** to report the debt: both
  already test `label not in ("fresh", "none", "skipped")`, so a new non-resolved label
  falls through correctly. The only `build_rows` edit was hoisting `verify_command` into a
  local so the diagnostic and the row share one string. Items 011/012 should check the same
  tuple before adding a branch — it is the de-facto "outstanding" predicate.

- **Two DIFFERENT diagnostics, on purpose.** `_warn_auto_verify_debt_metadata` (classifier
  level, deduped via `_AUTO_VERIFY_DEBT_WARNED`, mirrors `_warn_unknown_verify_status`)
  fires only for unusable `scheduledStageVersion` and can NOT name the feature — the
  classifiers take only `state`. The named 03 §5.3 sentence is emitted by `build_rows`,
  the one read-side emitter that knows the feature name. Item 009's epic parity and item
  030's navigator prose should reuse the WORDING, not import the function
  (`epic-manifest.py` stays self-contained).

- **The §5.3 sentence goes to STDERR, not stdout.** 03 §5.3: "Warnings stay on stderr
  unless they are an existing structured `warnings` field", and JSON output carries the
  three named keys (`verifyState`, `verifyStage`, `verifyCommand`) and no prose. That is
  what makes `rank-features --json | ...` still parse. `doctor` and `reconcile-branch` and
  `discover-feature` all call `build_rows`, so they inherit the diagnostic for free —
  which is the parity REQ-DEBT-05 asks for. Any later emitter should follow the same
  split rather than adding a prose key to `FeatureRow`.

- **`_scheduled_stage_version` rejects `bool` before `int`** (same trap as item 002's
  manifest revision: `True` is an `int` and would compare equal to version 1). A missing
  or malformed value keeps the row `auto-pending` — degrading to `never` is the exact
  conflation REQ-DEBT-02 forbids.

- **The revision clause is only appended when BOTH numbers are usable ints and differ.**
  A completed stage with no recorded `version` therefore gets the bare sentence, not a
  half-filled "advanced" claim.

- **`_print_rank_table` now says `(automatic verification owed: …)`** for an `auto-pending`
  row instead of `(verify available: …)`. Existing non-auto rows keep the old wording
  verbatim; `tests/test_rank_features.py` pins both branches.

- **Signature-stability tests must strip quotes.** `scripts/forge-session.py` has
  `from __future__ import annotations`, so `inspect.signature()` renders every annotation
  as a quoted string (`(state: 'dict') -> 'tuple[str | None, str]'`) and the return
  annotation shows `Path`, not `pathlib.Path`. `tests/test_auto_verify.py::sig` normalizes
  by removing `'`.

### Verification

`bash scripts/validate.sh` exit 0 with `PASS: epic-manifest pytest suite` and
`PASS: adapters/ matches a fresh generation (no drift)`;
`python3 -m pytest tests -q` -> 976 passed, 2 skipped (both pre-existing);
`ruff check scripts/ eval/` clean.

## Item 009 — epic-manifest verify parity + epic-root freshness

Added `_auto_verify_debt_warnings` (member obligations), `epic_verify_state` +
`_read_epic_state_safely` + `_epic_verify_warnings` (epic-root freshness), the shared
`_positive_int`/`_auto_pending_message` helpers, and split `_next_command`'s
production-complete terminus. `scripts/epic-manifest.py` stays self-contained — no import
of `forge-session.py`.

### Gotchas for later items

- **Three of the five parity bullets were already satisfied by item 001's constant
  change** and needed only tests: `_verify_status_warnings` stops warning because
  `auto-verify-pending` is in `KNOWN_VERIFY_STATUSES`; `is_complete_for_orchestration`
  already excludes it via `_VERIFY_ORCH_COMPLETE`; `derive_status`'s `started` test is
  `status not in (None, "pending")`, and `"auto-verify-pending" != "pending"`, so it
  already classified in-progress. Each now has a named test plus a negative control
  (`test_009_a_genuinely_unknown_status_is_still_flagged`) so a later refactor cannot
  quietly turn the guard into a no-op.

- **`_next_command`'s `nxt is None` default flipped from `forge-fix` to `forge-verify`.**
  Only `findings-reported` still routes to `forge-fix` (03 §5.2: "reserving forge-fix for
  findings-reported"). Reachable statuses there are the non-orchestration-complete ones —
  `findings-reported`, `auto-verify-pending`, `pending`, `skipped`, unknown — because
  `passed`/`findings-applied`/absent make the member complete and therefore not
  actionable. Item 015 consumes this `nextCommand` verbatim.

- **`RenderStatus` gained NO new key.** 04 §2.2 documents the shape as total and item 015
  routes on it, so epic freshness is exposed as the standalone `epic_verify_state(epic_dir,
  revision)` plus an entry in the existing `warnings` list. If item 015 or a later item
  wants the label in the payload, adding `epicVerifyState` is additive — but 04 §2.2 has to
  move with it.

- **Only `auto-pending` warns.** `never` is the ordinary state of every epic nobody has
  verified (every existing fixture), so warning on it would fire on the whole suite;
  `stale`/`failing` are already reachable through the epic's own verify run. Owed-and-
  dropped debt is the case that is otherwise invisible, which is REQ-DEBT-02's whole point.

- **Warning order is driven by `_VERIFY_STAGE_BY_TOKEN`, not the state file's key order.**
  A member serialized with `forge-verify-impl` before `forge-verify-prd` still renders
  prd-then-impl. `test_009_the_member_obligation_warning_is_deterministic` writes them in
  the wrong order on purpose.

- **`_auto_pending_message` and `AUTO_PENDING_DIAGNOSTIC` are hand-mirrored** from
  forge-session.py's `auto_pending_message`/`AUTO_PENDING_DIAGNOSTIC` (no shared import
  module). `tests/test_stage_constants_parity.py` guards only `KNOWN_VERIFY_STATUSES`, so
  a divergence here is caught by the epic tests' exact-sentence assertions and by
  `tests/test_auto_verify.py` on the session side — edit both copies together.

- **`_positive_int` rejects `bool` before `int`** (the recurring trap: `True` is an `int`
  and would compare equal to revision 1). Applied to both `scheduledStageVersion` and
  `verifiedStageVersion` and to the manifest `revision` read in `render_status`.

- **`_make_single_member_epic` grew `revision: int | None = None`.** The default keeps the
  LEGACY (no-key) manifest shape its pre-existing callers were written against;
  `load_manifest` synthesizes 1 for them. Item 009's freshness tests pass an explicit
  revision because the compared number is the point.

- **Epic verification never touches member state.**
  `test_009_epic_verification_never_reads_a_member_pipeline_state` plants a perfectly-formed
  passing `forge-verify-epic` entry inside `m1/.pipeline-state.json` and asserts the epic
  still classifies `never` — the adversarial-fixture shape item 006 established, rather
  than a mock.

### Verification

`bash scripts/validate.sh` exit 0, "All checks passed!";
`python3 -m pytest tests -q` -> 1006 passed, 2 skipped (both pre-existing);
`ruff check scripts/ eval/` clean; adapters/ regenerated (all six copies of
epic-manifest.py).

## Item 010 — nine-stage stage-exit surface, typed CLI inputs, owner semantics

Widened the router to all nine `EXIT_STAGES`, added the five new flags, the 02 §3.1
validation order, `resolve_served_stage`, direct/nested terminal ownership, and the
`verifyStage` / `warnings` directives.

### Gotchas for later items

- **`_STAGE_EXIT_CLI_STAGES` is GONE** (item 001 flagged this as item 010's job).
  `stage-exit --stage` now reads `choices=EXIT_STAGES` directly. The interim subset
  test in `tests/test_stage_constants_parity.py` was REPLACED — not deleted — by
  `test_the_cli_stage_choices_are_the_whole_exit_domain`, which also asserts the old
  name is absent so it cannot come back.

- **argparse errors now start with `Error:` CLI-WIDE.** 02 §2.2 demands BOTH typed
  `choices` on the enum flags AND `Error: <actionable message>` on every invalid
  input; stock argparse leads with `usage:`. `parse_args()` runs OUTSIDE `main()`'s
  `UsageError` handler, so the reconciliation is a `_ErrorPrefixParser`
  (`ArgumentParser.error` → `self.exit(2, "Error: …\nTry '<prog> --help' for
  usage.")`). `add_subparsers` defaults `parser_class` to `type(self)`, so setting it
  on the TOP-LEVEL parser was the whole change — **every** subcommand inherits it.
  Existing `"invalid choice" in stderr` assertions still pass (the argparse message
  is preserved verbatim after the prefix). If a later item wants a bespoke argparse
  message, override `error()` on that subparser, do not re-add `usage:`.

- **`route_stage` is the new routing pivot.** A branch exit routes from the stage it
  SERVED (`forge-verify` has no artifact, no verify token, and no successor of its
  own); a production exit routes from itself, so stages 0–4 are unchanged. It drives
  `_verify_state_for`, `auto_verify_for`, `_EXIT_NEXT_STAGE`, the `next_stage(state)`
  walk, and the debt warnings. Items 013–016 should branch on `outcome` INSIDE this
  derivation rather than adding a second successor computation.

- **`_EXIT_NEXT_STAGE` gained `forge-5-loop -> forge-6-docs`** and deliberately still
  has NO `forge-6-docs` entry — the pipeline ends there, so a docs (or docs-served)
  exit yields `nextStage: None` and the block falls back to
  `/feature-forge:forge`. That is the "completion action, never a nonexistent stage 7"
  rule; item 015 makes it context-aware, it does not need to add a key.

- **This item did NOT add `primaryCommand` / `deferredCommand`, and did NOT change
  `_next_steps_block`.** Item 011 owns both (it owns the verify-first ordering that
  makes them meaningful). Nested payloads today preserve routing directives and
  return `nextSteps: None` / `sentinel: None`, which is the full §3.3 contract.

- **Strict resolution for the new stages is still DEFERRED.** 02 §3.1 says loop, docs,
  branch, and explicit member-routing paths use strict resolution; none of item 010's
  15 acceptance criteria covers it, and the owning paths are items 013/015/016. All
  nine stages currently share the tolerant `_resolve_feature_dir` read. The
  §3.2 negatives "ambiguous same-named feature" and "explicit wrong epic" are
  therefore NOT yet asserted in `tests/test_stage_exit.py` — add them with the strict
  path, not before.

- **`--next-feature` is now safe-name validated**, so the literal placeholder
  `{first-actionable-feature}` can no longer be PASSED as a value. Omitting the flag
  still produces that placeholder in `nextCommand` (unchanged). 02 §9 / item 022 say
  the epic skill must pass a concrete member or nothing — never a placeholder — so
  the canon edit in item 022 is what closes this loop. `skills/forge-0-epic/SKILL.md`
  Step C8 currently stamps `--next-feature "{first-actionable-feature}"` as a
  template the model substitutes; if a model ever passed it through verbatim it now
  exits 2 instead of silently echoing it.

- **`warnings` entries 2 and 3 are mutually exclusive by construction** — a
  revision mismatch is only detectable once `scheduledStageVersion` is usable, and
  entry 2 fires exactly when it is not. `_debt_metadata_warnings` keeps the fixed
  order anyway so item 016 can insert entry 1 ahead of it without re-deriving.
  Entry 2 uses the new `AUTO_VERIFY_DEBT_METADATA_DIAGNOSTIC` constant (the
  directive-facing twin of `_warn_auto_verify_debt_metadata`'s stderr line, plus the
  subject and the host-translated retry command, per REQ-OBS-02); entry 3 reuses
  `auto_pending_message(...)` with both revisions.

- **`verifyStage` is `pending_verify(state)` verbatim** (00 §4: "the value
  `pending_verify()` returns"), NOT `_verify_state_for`'s stage. The two can disagree:
  `pending_verify` classifies the most-recently-COMPLETED stage while stage-exit runs
  inside the stage that just closed. The spec is explicit that this key mirrors
  `FeatureRow.verifyStage` so navigator rows and stage-exit JSON report the same
  thing — do not "fix" it to follow `route_stage`.

- **The nine new directive keys are additive**, so stages 0–4 keep every prior key
  and value. `test_no_epic_requests_is_byte_identical_and_omits_directive` still
  passes unchanged, which is the REQ-COMPAT-01 signal.

- **zsh does not word-split unquoted `$var`.** A `for a in "--stage X --outcome Y"`
  loop that works in bash passes the whole string as ONE argv entry here and every
  case reports "the following arguments are required: --stage". Use a shell function
  with `"$@"`, or an array.

### Verification

`bash scripts/validate.sh` exit 0 with `PASS: epic-manifest pytest suite`;
`python3 -m pytest tests -q` -> 1160 passed, 2 skipped (both pre-existing);
`ruff check scripts/ eval/` clean; `python3 scripts/build-adapters.py` run and the
regenerated `adapters/` tree left in the working tree for the loop runner to commit.

## Item 011 — verify-first primary routing + capability-aware gates

Extended `_next_steps_block` to the 00 §5 five-parameter signature, added the
`primaryCommand`/`deferredCommand` directive pair, and replaced the `host == "claude"`
gate branch with `verify_capability`.

### Gotchas for later items

- **`_next_steps_block` no longer decides which command is fenced.** 02 §5.2 rule 3 says
  it fences EXACTLY `primary_command`, so the reconcile-vs-successor promotion moved up
  into `stage_exit`. The renderer only re-derives whether the reconcile *is* the primary
  (`_host_command(reconcile["command"], host) == fenced_command`) to pick between the
  "reconcile **before** the next stage" step-2 prose and the ordinary next-stage line.
  Items 013-016 set `primary_canonical` themselves; do not add a second promotion rule
  inside the renderer.

- **`deferred_command is not None` is the renderer's ONLY signal that the primary is a
  verification/recovery action**, and it drives the fresh-session wording ("run the
  verification below" vs "run the next stage below"). The signature is fixed at five
  parameters by 00 §5, so there is no explicit flag. A later item that wants verify-first
  wording without a deferred successor has to widen the spec first, not sneak a sixth
  parameter in.

- **The caller-supplied deferred line is suppressed when the blocking reconcile already
  demoted the SAME command.** Both sources feed the unfenced deferred chain; without the
  dedupe, `/feature-forge:forge-3-specs widget` renders twice on the
  outstanding-verification + blocking-reconcile path. Order is fixed (02 §5.2): the new
  "After verification passes, reconcile the epic first — …" line, then
  `epicReconcile["deferred"]`'s "After reconciling, continue the pipeline with: …", then
  the caller's "After verification passes, continue with: …".

- **`resolved` now includes the `none` label** (a tokenless stage — only `forge-6-docs`).
  Before item 010 the router never saw stage 6, so a global `autoVerify: true` would have
  made docs claim `runInStageVerify` for a verification that has no token to record it.
  07 §3.4's last matrix row is the pin. Stages 0-4 are unaffected (all have tokens), so
  this is not a REQ-COMPAT-01 change.

- **The gate is `resolved or run_in_stage` → `none`, else capability.** `run_in_stage`
  (not `effective_auto_verify`) is the correct guard: they differ only when verification
  is already resolved, which the first arm covers, but writing `effective_auto_verify`
  invites a later reader to think auto-verify suppresses the gate even when nothing is
  owed. `tests/test_stage_exit.py::test_no_source_path_selects_the_gate_from_the_host_name`
  slices `stage_exit`'s body from the first `verify_gate =` to `next_stage_id` and asserts
  the substring `host` does not appear — keep the gate block free of host mentions,
  including in comments inside that slice.

- **Test fixtures had to seed a fresh verify entry to keep testing what they tested.**
  `_FRESH_TECH_VERIFY` and `_state_with_requests(..., verified=True)` exist because
  next-stage selection and reconcile precedence are only observable once verification is
  resolved — otherwise verify-first ordering masks them. Every changed stages 0-4
  expectation carries an `INTENTIONAL CHANGE (item 011, …)` comment naming verify-primary
  ordering or capability-aware gate selection, per 07 §3.8.

- **`--verify-capability` defaults to `manual` on the CLI**, so every pre-existing test
  that expected `verifyGate == "standard"` from the default `--host claude` now has to
  pass `--verify-capability interactive` explicitly. That is the whole point of the
  change; a test that silently still passes is a test that stopped asserting the gate.

- `outcome_text` is landed and rendered (immediately after `**Next steps**`, above the
  numbered guidance) but no caller supplies it yet — items 013-015 do.

### Verification

`bash scripts/validate.sh` exit 0, "All checks passed!", with
`PASS: epic-manifest pytest suite` and `PASS: adapters/ matches a fresh generation (no drift)`;
`python3 -m pytest tests -q` -> 1248 passed, 2 skipped (both pre-existing);
`ruff check scripts/ eval/` clean; `python3 scripts/build-adapters.py` run and the
regenerated `adapters/` tree left in the working tree for the loop runner to commit.

## Item 012 — auto-verify debt at the stage-exit scheduling boundary

Landed `_schedule_auto_verify_debt` (the 03 §4.1 boundary), the
`autoVerifyDebtRecorded` directive, epic-scoped verification reads via
`_epic_verify_context`, sorted `invalidAutoVerifyKeys` + the exact 00 §4 warning
template, and the 07 §4.1 test block.

### Gotchas for later items

- **A BRANCH exit must never schedule.** Found by reproduction, not by the suite:
  before the guard, `stage-exit --stage forge-verify --served-stage forge-2-tech
  --outcome findings` computed `run_in_stage` from the served stage's label
  (`failing` → unresolved) and OVERWROTE the `findings-reported` entry
  forge-verify had just written with a fresh `auto-verify-pending` marker —
  losing the report and the reason for the diversion. `run_in_stage` now carries
  `and stage not in _BRANCH_STAGES`. Item 013 owns branch rejoin routing and must
  not undo it; a verify/fix exit is already inside the diversion.

- **Every directive except `autoVerifyDebtRecorded` is a PRE-mutation snapshot.**
  `verifyState`, `warnings`, and `cleanTree` describe the state the routing
  decision was made from, so a first exit reports `never` while the debt it just
  recorded reads `auto-pending` on the next one. That is deliberate: 02 §10's
  determinism rule is conditioned on identical state, and item 011's recorded
  stages 0-4 expectations (`d["verifyState"] == label` for never/stale/failing
  with autoVerify on) stay valid. Do not "fix" it to report post-write.

- **Epic exits now read `.epic-state.json`, not member state.** `route_stage ==
  "forge-0-epic"` (either `--stage forge-0-epic` or a branch exit whose
  `--verify-mode epic` resolves there) classifies from
  `{specsDir}/{epic}/.epic-state.json` against the manifest `revision`, via the
  new tolerant `_epic_verify_context`. This REPLACED
  `test_epic_stage_verify_state_reads_forge_verify_epic`, which seeded
  `forge-verify-epic` in the member `.pipeline-state.json` — an entry that has had
  no home there since item 006 (REQ-SEC-01). Without the change the epic path
  would classify from a file nothing writes, making
  `runInStageVerify: true` + `autoVerifyDebtRecorded: false` reachable and letting
  a fresh epic `passed` be scheduled over.

- **`_verify_state_for` was split**, not rewritten: `_classify_verify_entry(entry,
  verify_key, current)` is the revision-agnostic half both the feature and epic
  callers share, so the two can never drift. `_debt_metadata_warnings` likewise
  now takes `(entry, verify_key, stage, subject, verify_command, current)` instead
  of re-deriving them from a member state document.

- **The scheduler tolerates an unknown revision where the CLI refuses it.**
  `state-verify --status auto-verify-pending` fails without a recorded artifact
  version (03 §3.3); the stage-exit scheduler writes `scheduledStageVersion: null`
  instead. Refusing would turn a routine stage closing into an exit 2 (several
  pre-existing tests exit with `autoVerify: true` and no state file at all), and
  forgetting the debt because its revision is unknown is precisely the REQ-DEBT-02
  conflation — item 008 already classifies a null schedule as `auto-pending` plus a
  warning. The idempotence check compares `None == None`, so a null schedule is
  still byte-idempotent.

- **A genuine write failure DOES fail closed** — `UsageError` → exit 2, empty
  stdout, no dispatch directive. The portable injection is `chmod 0o555` on the
  feature directory: `_write_state` creates its sibling temp file there, so
  `tempfile.mkstemp` fails before anything is replaced. An epic with no
  `epic-manifest.json` fails the same way through `_load_epic_state_for_write`.

- **`invalid_auto_verify_keys` is now sorted** (02 §10) and `stage_exit` prints
  one `INVALID_AUTO_VERIFY_KEY_WARNING` line per key to STDERR — advisory, never
  fatal, and off stdout so `--json` stays parseable. The `{valid}` list is derived
  from `VERIFY_TOKEN_BY_STAGE` so the sentence cannot drift from the domain.

- **The `stage-exit` write dirties the tree it just measured**, which is exactly
  why `cleanTree`/`autoFixEligible` are snapshotted first. The resulting
  `.pipeline-state.json` modification is a SANCTIONED control-plane mutation;
  `test_the_clean_tree_snapshot_predates_the_pending_write` asserts both halves.

### Verification

`bash scripts/validate.sh` exit 0 with `PASS: epic-manifest pytest suite` and
`PASS: adapters/ matches a fresh generation (no drift)`;
`python3 -m pytest tests -q` -> 1281 passed, 2 skipped (both pre-existing);
`ruff check scripts/ eval/` clean; `python3 scripts/build-adapters.py` run and the
regenerated `adapters/` tree left in the working tree for the loop runner to commit.

## Item 013 — direct verify/fix rejoin routing tables

Landed the 02 §6 outcome tables (`_BRANCH_ROUTE_KIND`, `_BRANCH_OUTCOME_TEXT`,
`_NO_FINDINGS_RESOLVED_TEXT`) and `_branch_route`, wired them into `stage_exit` ahead of
item 011's verify-first ordering, and covered 07 §3.3 in `tests/test_stage_exit.py`.

### Gotchas for later items

- **A branch exit's primary command does NOT come from verify-first ordering.** The 02 §6
  outcome table is consulted FIRST and wholly supplies `primaryCommand`. Without that
  ordering a `forge-verify --outcome findings` exit fell through to item 011's
  "verification is unresolved → fence the verify command" branch and emitted
  `/feature-forge:forge-verify FEATURE` with **no `--served-stage`** — dropping the very
  thread issue #176 is about. Items 014/015 own the loop/docs tables; they should extend
  the same `if stage in _BRANCH_STAGES: ... elif not resolved: ...` chain rather than add a
  second override after it.

- **`verifyGate` is now `none` for every branch exit.** A branch exit is already inside the
  diversion and its outcome table names the one action, so a `standard`/`manual-print` gate
  would ask "verify now?" beside a fenced FIX command — two contradictory asks. The
  `verify` rows of the table ARE the verification prompt. Note the structural guard
  `test_no_source_path_selects_the_gate_from_the_host_name` slices from the first
  `verify_gate =` to `next_stage_id` and bans the substring `host` in that slice: the
  branch condition had to go on the `if` line (before the first assignment), and any
  comment about hosts must stay above it.

- **`_next_steps_block`'s verify-first wording now follows the FENCED command**, because on
  a branch exit the fenced action may be a fix rather than a verification. It sniffs
  `"forge-fix " in fenced_command` (post-`_host_command`, so it survives Pi's `/skill:`
  rewrite) and says "run the fix below" instead of "run the verification below". Production
  exits are byte-identical, which is what
  `test_fresh_session_guidance_follows_the_verification_action` pins. The signature stayed
  at 00 §5's five parameters — a sixth would have broken
  `test_next_steps_block_matches_the_00_section_5_signature`.

- **The `skipped`/`reverified` preconditions are the CALLER's, not the router's.** 02 §6
  says `skipped` is "valid only after explicit skip persistence" and `reverified` "allowed
  only after passed state is recorded". A first draft enforced both as `UsageError`; that
  made two *valid* members of `EXIT_OUTCOMES[stage]` exit 2 on a bare project and broke
  item 010's landed `test_every_own_outcome_is_accepted`. Items 018/019 own the obligation
  (the branch skills write through `state-verify` before invoking the exit, and a fix that
  merely skips re-verification reports `deferred`, not `reverified`). `_branch_route`'s
  docstring records the division so it is not "fixed" back.

- **`no-findings` is the ONE state-dependent outcome** (`verify-if-owed`): it re-verifies
  while the served stage's verification is unresolved and rejoins only when it is settled.
  Consequence for parametrized tests: it cannot be listed among the always-non-advancing
  outcomes, and with `--served-stage forge-6-docs` (tokenless → label `none` → resolved) it
  advances to the completion action.

- **`next_arg` is now keyed off `route_stage`, not `stage`.** Previously a branch exit that
  served `forge-0-epic` produced `/feature-forge:forge-1-prd <epic>` — a member fabricated
  from the epic's name. It now emits the same `{first-actionable-feature}` placeholder the
  epic's own exit does. Identical for every production exit, where `route_stage is stage`.

- **Live successor = `next_command`, which is already state-aware.** The existing
  `next_stage(state)` override means a member past tech/specs rejoins at backlog, not at
  `served + 1`. `next_command is None` happens only at the end of the pipeline (served
  `forge-6-docs`), and `_branch_route` maps that to `/feature-forge:forge FEATURE` — the
  completion action, never a nonexistent stage 7.

- **Complete-path tests drive the REAL `state-verify` writer** (`_state_verify` /
  `_report_findings` helpers) rather than hand-writing entries, so
  findings → applied → passed and findings → applied → findings exercise the actual
  freshness clearing. `--findings-file` needs the file to exist under the feature dir;
  `_served_project` creates `findings.md`.

### Verification

`bash scripts/validate.sh` exit 0 with `PASS: epic-manifest pytest suite` and
`PASS: adapters/ matches a fresh generation (no drift)`;
`python3 -m pytest tests -q` -> 1377 passed, 2 skipped (both pre-existing);
`ruff check scripts/ eval/` clean; `python3 scripts/build-adapters.py --check` reports no
drift, with the regenerated `adapters/` tree left in the working tree for the loop runner
to commit.

Re-verified in a second iteration by driving the real CLI directly, not only the suite:
all four §6.1 verify rows and all seven §6.2 fix rows emit the exact primary command;
`no-findings` flips from the verify command to `/feature-forge:forge-3-specs` once the
served stage's verification is recorded `passed`; a branch exit serving `forge-6-docs`
emits `/feature-forge:forge <feature>` with `nextStage: null`; a fresh production exit
taken after a `findings-applied` write makes the verify command primary rather than the
successor; and the two nested payloads contain ZERO sentinels while the final direct call
contains exactly one, as its last line.

## Item 015 — docs routing from live epic status via `render-status`

Added `_render_status` (the bounded sibling subprocess), `_render_status_failure_detail`,
`_DOCS_OUTCOME_TEXT`, and `_docs_route` to `scripts/forge-session.py`, wired a
`elif stage == "forge-6-docs"` arm into `stage_exit`'s primary-routing chain, and covered
07 §3.6 in `tests/test_stage_exit.py`.

### Gotchas for later items

- **`actionable == []` is EQUIVALENT to "every member complete"** under the current
  `epic-manifest.py` derivation, so 02 §8's "no actionable member because remaining
  work is blocked" bullet is not constructible through the real helper: `validate`
  rejects cycles, so any DAG with an incomplete member has an incomplete member whose
  deps are all complete, and that member is actionable. Both cases route to the SAME
  epic command, so the acceptance criterion holds either way; the two wordings are
  selected on `rollup["complete"] < rollup["total"]`, which is the observable that
  would distinguish them if a future derivation ever admits an unactionable incomplete
  member. Item 021's canon must not promise the operator a distinction the data cannot
  currently make.

- **`render-status --json` reports an INVALID GRAPH on stdout, not stderr** (exit 1
  with `{"valid": false, "findings": [...]}` and a silent stderr). Quoting stderr alone
  produced `render-status exited 1 ({)`. `_render_status_failure_detail` prefers the
  first stderr line and falls back to the first finding's `message`, so the operator is
  told *which* dangling ref/cycle broke the routing (REQ-OBS-02).

- **A `blocked` docs outcome deliberately does NOT call `render-status`.** Its route is
  fixed at the epic dashboard whatever the live graph says, and a broken epic graph is
  precisely the state in which the recovery route must stay reachable rather than
  converting into a second exit-2. Item 021's skill can therefore always close a blocked
  docs stage.

- **The epic is taken from `--epic` OR the member state's `epic` back-pointer**, name-checked
  through `SAFE_NAME_RE` before it reaches the helper's argv (untrusted on-disk data,
  REQ-SEC-01). An unusable value degrades to the STANDALONE route rather than crashing.
  Consequence: a flat feature whose state carries a stale `epic` back-pointer now exits 2
  at docs. That is the intended fail-closed behavior — the alternative is guessing.

- **The secondary new-feature/new-epic mentions are host-translated inside `_docs_route`**,
  because `outcome_text` is passed through `_next_steps_block` verbatim and the renderer
  only `_host_command`s the *primary*. Without it a Pi block would carry a live
  `/feature-forge:` command that Pi cannot run. Any later item adding a command mention to
  an `outcome_text` must translate it at construction time.

- **`_stub_bundle` is the honest way to test the sibling contract.** It copies
  `forge-session.py` into a fresh `scripts/` dir next to a stub `epic-manifest.py`, so the
  REAL resolution path runs and only the helper's body is replaced. That covers missing
  sibling / malformed JSON / missing field / malformed rollup / non-object payload without
  mocking `subprocess.run`. Only the timeout and spawn-failure rows use `monkeypatch`, which
  07 §3.6 permits once the real success and nonzero cases exist.

- **`test_docs_resolves_the_helper_beside_itself_and_never_a_bare_python3` slices the
  DOCSTRING off before asserting `"python3" not in ...`** — the docstring legitimately
  explains why a bare `python3` is wrong, and a prose mention must not decide a behavioral
  guard. Same trick will be needed by any later source-level guard on this function.

- **`test_docs_never_reimplements_the_epic_dependency_derivation`** bans `unmet_deps`,
  `parallelEligible`, and `is_complete_for_orchestration` from `scripts/forge-session.py`
  entirely (tech-spec §3.5). A later item that wants one of those answers must consume
  `render-status`, not re-derive it.

- **Pre-existing wording note (not changed here):** a standalone docs `complete` block still
  renders `2. Then start a fresh session and run the next stage below`, because
  `deferred_command is None` and 00 §5 fixes `_next_steps_block` at five parameters. The
  fenced command and the outcome text are both correct; only that stock line reads oddly at
  the end of the pipeline. Item 021 may want to raise it.

### Verification

`bash scripts/validate.sh` exit 0, "All checks passed!", with
`PASS: epic-manifest pytest suite` and `PASS: adapters/ matches a fresh generation (no drift)`;
`python3 -m pytest tests -q` -> 1405 passed, 2 skipped (both pre-existing);
`ruff check scripts/ eval/` clean; `python3 scripts/build-adapters.py` run and the
regenerated `adapters/` tree left in the working tree for the loop runner to commit.
