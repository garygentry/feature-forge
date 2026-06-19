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
