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
