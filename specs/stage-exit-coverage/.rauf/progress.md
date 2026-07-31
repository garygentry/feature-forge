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
