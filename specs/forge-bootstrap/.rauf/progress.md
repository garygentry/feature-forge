# forge-bootstrap — Progress Log

## Item 002 — foundation + fixtures
- `scripts/forge-bootstrap.py` mirrors `epic-manifest.py` (flat functions, IO layer,
  UsageError/FindingsError → exit 2/1, `_atomic_write_text` + `_json_text` helpers).
- Subcommand bodies (check/scaffold/verify/commit/status) are `NotImplementedError`
  stubs; later items fill them. `main()` dispatch + `--json`/`--answers`/`--stage-only`
  parse correctly. `_parse_answers` runs before the stub, so malformed `--answers`
  exits 2 deterministically (tested without reaching a stub).
- Tests load the hyphenated module via `importlib` (`bootstrap_module` session fixture);
  `run_bootstrap` subprocess fixture merges `env` over `os.environ` (PATH='' hook for the
  later item-008 toolchain-missing test).
- Verify: `python3 -m py_compile scripts/forge-bootstrap.py` + `python3 -m pytest
  tests/test_forge_bootstrap.py -q` (12 passed).

## Item 003 — `check` subcommand (greenfield gate + recovery)
- Implemented `check()` verbatim from 02 §3: read-only walk of top-level entries,
  allow `.git` + specsDir basename + SENTINEL_FILENAME + ALLOWED_META_FILE_RE files;
  `eligible = (not disqualifying) or resumeMarker is not None` so an own sentinel
  never misfires the gate (REQ-LIFE-02).
- Updated `test_subcommand_bodies_are_stubs` to drop `check` (now implemented;
  scaffold/verify/commit/status remain stubs).
- Added 7 check tests (empty/fresh-remote eligible, source+manifest refused,
  own-sentinel resume, read-only, hasGit). 19 passed.
- NOTE: full `validate.sh` reports a PRE-EXISTING adapter-drift FAIL (`adapters/`
  out of date) — confirmed present on the bare 002 tree via `git stash`. That is
  item 014's job (regenerate + commit adapters/), not item 003.
