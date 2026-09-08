# Progress & Learnings

## Codebase Patterns
<!-- Patterns discovered during development will be logged here -->

## Session Log
<!-- Each iteration appends its learnings here -->

### Item 001 — package + shim + topology pilot

- **ruff bans star imports.** `scripts/ruff.toml` selects `E,F,W`, so
  `from forge_session.topology import *` trips F403 (and every use trips F405).
  The shim re-exports via EXPLICIT imports + a module-level `__all__` listing every
  re-exported name (ruff treats `__all__` entries as "used", killing F401). The
  package imports sit after the `sys.path.insert` bootstrap, so each carries
  `# noqa: E402`.
- **Two hard constraints forced code to STAY in the shim / stay resilient:**
  1. `load_json_with_duplicates` / `warn_duplicate_keys` are **mirrored, not
     extracted** — `tests/test_json_loader_parity.py` + `test_effective_config.py`
     scan `scripts/forge-session.py` SOURCE and require the pair byte-identical to
     `scripts/forge-bootstrap.py`. Do NOT move them into `_common`. (Topology
     doesn't use them anyway.) Only `UsageError` + the TypedDicts + `VerifyStatus`
     went to `_common`.
  2. **Bare-copy test helpers** copy ONLY `forge-session.py` (no package) and run
     it: `test_stage_exit.py::_stub_bundle`, `test_doctor.py::test_doctor_survives_
     unresolvable_root_and_bare_dir`. Their copies can't `import forge_session`
     (package isn't beside them, and the subprocess env has no PYTHONPATH). Fix:
     the shim wraps the package imports in `try/except ModuleNotFoundError` and, in
     the fallback, defines just the two primitives the non-topology paths touch at
     import/run time — `UsageError` (raised/caught by write+exit verbs) and
     `VerifyStatus` (read by `get_args` at module load). The topology verb needs the
     package; no bare-copy test invokes it.
- **forge-root.sh CORE_ASSETS is mirrored by `tests/test_forge_root.py`
  (`_CORE_ASSETS`).** Adding a literal entry to the array breaks 20 tests (its
  `_make_fake_install` doesn't create the file). Instead the completeness gate
  checks the package (`scripts/forge_session/__init__.py`) ONLY when the shipped
  `forge-session.py` actually references `forge_session` (i.e. is the shim) — the
  test stubs write a sentinel-text forge-session.py, so the guard never fires for
  them, while real bundles/degraded installs are covered.
- **Bundling:** `build-adapters.py` grew `RUNTIME_HELPER_DIRS = ("forge_session",)`;
  a copy loop after the RUNTIME_HELPERS loop copies every `*.py` (skip
  `__pycache__`) byte-identically with the same `_assert_byte_identical`. The pi
  host-term pass leaves the package untouched (no `/feature-forge:` in it), so pi
  copies stay byte-identical to canon too. **Always regenerate adapters LAST** —
  if you edit `scripts/forge-session.py` after a regen, `adapters/*/` go stale and
  the drift guard (`build-adapters.py --check`, validate.sh 6b) fails.
- **Pre-existing failure in this env:** `tests/test_doctor_checks.py::test_env_stamp_
  interactive_never_carries_a_rung` fails identically at pristine HEAD when run
  inside the rauf/`claude` sandbox (the sibling test's docstring documents the
  `claude -p` ancestry issue). Not caused by the split.

- **BLOCKER (acceptance-criteria contradiction, surfaced this iteration):**
  `tests/test_build_adapters.py::test_no_new_file_appears_under_an_adapter_scripts_dir`
  (all 6 agents) FAILS because of the split, and the failure is unavoidable under the
  current acceptance criteria. Line 1260 asserts *no directory may appear under*
  `adapters/<agent>/scripts/`. But criteria 4 & 5 REQUIRE copying the whole
  `forge_session/` package dir into every bundle, and the shim's
  `sys.path.insert(parent)` + `import forge_session` mechanism forces that package to
  live as a sibling dir of the bundled `forge-session.py` — i.e. exactly at
  `adapters/<agent>/scripts/forge_session/`. There is NO bundle layout that ships a
  runnable package yet leaves zero dirs under the adapter scripts dir. So the design
  (ship the dir) and this frozen structural test (forbid any dir) are mutually
  exclusive, and criterion 8 ("validate.sh passes with zero test-file edits", echoed
  by item 008's "entire suite passes unmodified — no test file edited in any item")
  forbids relaxing the test. RESOLUTION NEEDED (human/design decision): either
  (a) amend criterion 8 to permit a minimal, behavior-preserving edit to
  `test_no_new_file_appears_under_an_adapter_scripts_dir` so it allows the required
  `forge_session/` package dir (and ideally add a positive assertion that the dir
  ships byte-identically), or (b) change the bundling strategy. Emitting RAUF_BLOCKED
  per the backlog's own convention ("a required test edit means STOP and emit
  RAUF_BLOCKED"). Note: `build-adapters.py --check` PASSES (exit 0) and
  `forge-session.py doctor --json` exits 0 — only this one guard test blocks.

### Item 002 — extract decisions.py

- **The decision-* verbs pull in a config-resolution chain, not just state
  writers.** `_resolve_decisions_path` → `resolve_loop_runner` →
  `_loop_runner_defaults` + `_load_config` → the mirrored
  `load_json_with_duplicates`/`warn_duplicate_keys`. Since decisions.py may import
  ONLY from `_common`, every link had to become importable from `_common`.
- **Chosen strategy: ADD the shared primitives to `_common`, KEEP the shim's inline
  copies.** `_common` gained `_now_iso`, `_write_state`, `_commit_state`,
  `_load_config`, `_loop_runner_defaults`, `resolve_loop_runner`, and its OWN copy of
  the duplicate-aware loader pair. The shim was NOT edited to delete or re-import any
  of these — only the 12 decision functions were excised. Rationale: (1) the shim's
  ~41 inline call-sites keep working unchanged; (2) the **bare-copy fallback** stays a
  2-symbol stub — the stage-exit `_stub_bundle` / doctor bare-dir tests run the shim
  with NO sibling package and assert "no Traceback", and those paths DO reach
  resolve_loop_runner/_load_config/_now_iso/_commit_state, so deleting them from the
  shim body would have forced ~150 lines of fallback redefinition (high risk). The
  duplication is transient — items 006/008 drain the shim's inline copies into
  `_common`, at which point they'll already be there.
- **The mirrored-loader constraint does NOT forbid a copy in `_common`.**
  `tests/test_json_loader_parity.py` asserts `def load_json_with_duplicates(` appears
  EXACTLY ONCE **per scanned file** (only forge-session.py + forge-bootstrap.py are
  scanned) and that those two are byte-equal. A third copy inside the package's
  `_common` is invisible to it. Architecturally sound too: the mirror exists because
  the *flat* scripts share no import module; `_common` IS the package's shared import
  module, so it reads config through its own copy instead of reaching back into the
  shim (which would be circular). Kept the copy behaviour-identical (a pure move,
  never a re-derivation) so ZERO behaviour change holds — a plain-json reader would
  have silently dropped the decision-path duplicate-key warning.
- **`socket` became an orphan import** in the shim once `_default_actor` moved — the
  only user. ruff `F401` would have failed the lint step; removed it.
- **Re-export via EXPLICIT imports, never `from forge_session.decisions import *`.**
  Star would (a) trip ruff F403 and (b) pull decisions.py's OWN `_common` re-imports
  (`_now_iso`, etc.) into the shim, shadowing the shim's inline defs. Explicit imports
  of just the 12 functions + 2 constants avoid both. decisions.py does not declare
  `__all__` (not needed — nothing star-imports it).
- **Pre-existing failure unchanged:** `test_doctor_checks.py::test_env_stamp_
  interactive_never_carries_a_rung` still fails identically with these edits STASHED
  (proven via `git stash`), same `claude -p` sandbox ancestry cause item 001 logged.
  Full run: 3086 passed, 2 skipped, that 1 environmental fail. doctor --json exits 0;
  build-adapters --check exits 0 after regen.
