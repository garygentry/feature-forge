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

## Item 006 — `scaffold` subcommand
- Implemented scaffold per 02 §4: `_write_artifact` (idempotent + no-overwrite,
  skips recorded paths and pre-existing destinations, never recording kept files),
  `compose_member` (token sub on filenames + contents, member path "." → repo root),
  `write_config` (single → top-level stack/commands, no workspaces key; monorepo →
  null scalars + workspaces[]), `write_hygiene` (README always, LICENSE skip on
  'none', AGENTS always, CLAUDE only host=='claude'), `_resolve_commands`,
  `maybe_write_ci` (no-op on ci:false; raises NotImplementedError on ci:true → item 007).
- `TEMPLATE_ROOT = Path(__file__).resolve().parent.parent/skills/.../templates` (01 §1.1).
- README hygiene template carries a {{LICENSE}} token (→ "no license" when none);
  license texts carry {{YEAR}} (UTC year) + {{AUTHOR}}; agent files {{PROJECT_NAME}}/{{PURPOSE}}.
- Updated `test_subcommand_bodies_are_stubs` to drop scaffold (now implemented).
- Added 9 scaffold tests. 28 passed. NOTE: adapter-drift FAIL in full validate.sh
  remains pre-existing (item 014's job).

## Item 008 — `verify` subcommand
- Implemented `toolchain_present` + `verify` verbatim from 02 §5: probe each
  distinct `{pm}`-substituted binary via `sh -c "command -v <tool>"`; if any miss,
  return `{toolchainPresent:false, lint:[], test:[], green:false}` → dispatch prints
  the JSON then raises UsageError → exit 2. Else run resolved lint then test per
  member with `cwd = target/member["path"]`, `member` field = the PATH ("." single).
- GOTCHA: the deterministic PATH='' test makes even `sh` unlaunchable, so
  `run()` raises OSError→UsageError inside the probe. `toolchain_present` must
  CATCH UsageError and return False (treat unlaunchable probe as missing), else the
  helper exits 2 with empty stdout and the JSON guard payload is never printed.
- GOTCHA: the generic stack's `run.sh`/`test.sh` are NOT executable as scaffolded
  (compose_member writes text, no +x; templates are 0644), so `./test.sh` fails.
  Green/member verify tests `chmod 0755` the scripts first to test verify's logic;
  the missing exec-bit on scaffolded generic scripts is a template/scaffold gap for
  item 011's green-baseline integration, not verify.
