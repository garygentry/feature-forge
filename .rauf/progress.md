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

### Item 003 — extract discover / reconcile / check-epic-base

- **The bare-copy fallback set GREW with this move — `_default_branch` must join it.**
  The discover cluster moved cleanly into `discover.py` (imports `_git_output`,
  `_parse_ts`, `build_rows`, `_load_config`, and the FILENAME constants from
  `_common`), but `_default_branch` is used by TWO callers: the moved
  `reconcile_branch` AND the still-inline **`doctor_report`** (line ~1464,
  `default_branch = _default_branch()`). Deleting it from the shim body broke the
  three bare-copy DOCTOR tests — `test_doctor_survives_unresolvable_root_and_bare_dir`,
  `test_plugin_root_warns_with_global_install_remedy_when_unresolvable`,
  `test_root_version_skew_na_when_root_is_unresolved` — which copy ONLY
  forge-session.py (no sibling package) and run `doctor`, hitting the
  `except ModuleNotFoundError` branch where the moved `_default_branch` is undefined
  → `NameError` → doctor exits 1 (tests assert 0). Fix: add a byte-equal
  `_default_branch` to the fallback block (alongside `UsageError`/`VerifyStatus`),
  exactly the item-001 pattern ("define the primitives the non-topology bare paths
  touch"). It calls the shim's inline `_git_output` (kept at ~1345), resolved at call
  time. `_default_branch` stays in `discover.py` for the package-present path; item
  004 will re-source doctor's copy from `_common` when doctor.py is extracted.
- **Lesson for the remaining items:** before deleting a moved symbol from the shim,
  grep the shim body for callers OUTSIDE main()'s verb dispatch — anything reachable
  from `doctor_report` (the one bare-copy-invoked verb) must survive in the
  `ModuleNotFoundError` fallback, not just the package.
- **Pre-existing env failure unchanged:** `test_env_stamp_interactive_never_carries_a_rung`
  fails at pristine HEAD in this `claude -p` sandbox (confirmed via `git stash`);
  not caused by the split. doctor --json exits 0; ruff clean; build-adapters --check
  exits 0 after regen.

### Item 004 — extract doctor.py — BLOCKED (criterion-internal contradiction)

Item 004 as written is **unsatisfiable**: criterion 1 ("the listed doctor
functions/classes live in doctor.py and are **gone from the shim body**") is in
direct, provable conflict with criteria 6 & 8 ("these specific tests pass
**unmodified** / zero test-file edits"). TWO independent frozen tests require the
doctor cluster to stay physically in `scripts/forge-session.py`:

1. **Bare-copy subprocess doctor tests (3).** `test_doctor.py::test_doctor_survives_
   unresolvable_root_and_bare_dir`, `test_doctor_checks.py::test_plugin_root_warns_
   with_global_install_remedy_when_unresolvable`, and `test_doctor_checks.py::test_
   root_version_skew_na_when_root_is_unresolved` copy ONLY `forge-session.py`
   (+`forge-root.sh`) into a tmp dir and run `doctor --json` in a scrubbed env with
   NO package beside it and NO PYTHONPATH → the shim's `except ModuleNotFoundError`
   fallback runs. Empirically confirmed (stripped `doctor_report` from a lone copy):
   `NameError: name 'doctor_report' is not defined` at the `doctor` dispatch → the
   verb crashes. A lone shim cannot run `doctor` once the cluster is moved out; the
   only fixes are (a) keep the cluster inline (violates crit 1) or (b) duplicate all
   ~1,900 lines in the fallback (still "in the shim body" → violates crit 1, and the
   shim never shrinks → defeats #279's stated mechanism + item 008's "pure shim").

2. **Host-neutrality bundle test.** `test_adapter_host_neutrality.py::test_the_
   interaction_record_is_reachable_from_every_bundle` greps each bundle's
   `scripts/forge-session.py` **source text** for the literal `_make_spec("interaction-mode"`.
   That literal lives ONLY in the shim's `DOCTOR_CHECKS` registry (line ~3188), which
   calls the to-be-moved `_make_spec` + `_check_interaction_mode`. Criterion 6 restates
   this as a MUST-PASS. Moving those out removes the literal from the shim source →
   test fails. Keeping a shim-side `DOCTOR_CHECKS` that references package re-exports
   fails at MODULE LOAD in the bare copy (names undefined in the fallback) → breaks
   EVERY bare-copy test. So the registry + its `_make_spec`/`_check_*` must stay in the
   shim source too — again contradicting crit 1.

Both are the SAME class as item 001's blocker (a frozen structural/contract test vs.
the required split), which was resolved by a **human design decision** pre-authorizing
ONE scoped, behavior-preserving test edit (item 001 crit 8). Item 004's criteria grant
NO such carve-out and explicitly forbid test edits, so per the backlog convention
("a required test edit means STOP and emit RAUF_BLOCKED") I made ZERO repo edits and
blocked.

**Recommended resolution (design decision needed), mirroring item 001:** pre-authorize
minimal, behavior-preserving edits to exactly the conflicting tests —
- the 3 bare-copy subprocess doctor tests: ALSO copy the `forge_session/` package dir
  beside the lone `forge-session.py` (post-split a lone shim is not a complete program;
  real degraded installs still ship the package via item-001's bundling gates +
  forge-root.sh completeness gate), and
- `test_the_interaction_record_is_reachable_from_every_bundle`: assert the interaction
  check is reachable in the bundle's `scripts/forge_session/doctor.py` (where it now
  lives) rather than in the shim source.
Then doctor moves cleanly to `doctor.py`, the shim shrinks, and item 008's pure-shim
goal stays reachable. Until that decision lands, item 004 cannot be completed as
specified. (`_git_output` sharing with discover.py — item 003's note — is a non-issue
here since no code was moved.)

### Item 004 — extract doctor.py — DONE (under the standing LOOP EXECUTION POLICY)

The 2026-09-07 policy pre-authorized the scoped, behavior-preserving monolith-assumption
test edits the earlier BLOCK flagged, so the extraction landed as a pure move. The
1,979-line doctor cluster (lines 1375–3353 of the old shim) is now
`scripts/forge_session/doctor.py` (2,119 lines with header/`__all__`). Key gotchas:

- **`__file__` anchors MUST be recomputed for the deeper module.** doctor.py ships at
  `<scripts>/forge_session/doctor.py`, one level below the shim, so the four legacy
  `Path(__file__)` anchors would silently point one dir too shallow. Fixed with three
  module constants: `_SCRIPTS_DIR = Path(__file__).resolve().parent.parent`,
  `_SHIM_PATH = _SCRIPTS_DIR / "forge-session.py"`, `_BUNDLE_ROOT = _SCRIPTS_DIR.parent`.
  These reproduce the shim's old targets EXACTLY (verified: doctor.py.parent.parent.parent
  == old forge-session.py.parent.parent). The `_check_branch_state` remedy command
  `["python3", script, "state-branch", ...]` MUST resolve `script` to the SHIM
  (`_SHIM_PATH`), never doctor.py — it's operator-facing frozen `--json` output.
  `_default_schema_path` moved to `_common` with a THREE-parent walk (vs the shim's two)
  for the same depth reason.
- **The monkeypatch-target break is the big one.** `test_doctor_checks.py` does
  `monkeypatch.setattr(fs, "_build_check_context"/"DOCTOR_CHECKS"/"_PROBE_TIMEOUT_S"/
  "_bundle_agent"/"_process_ancestry", …)` then calls `fs.doctor_report(...)`. After the
  move a patched function only takes effect in ITS OWN module, so patching the shim `fs`
  is inert — the code runs in `forge_session.doctor`. Fix with ONE fixture edit: the `fs`
  fixture now returns `forge_session.doctor` (load the shim first for the sys.path
  bootstrap, then `import forge_session.doctor`). This fixed ~10 tests at a stroke. The
  ONE cross-cluster reference, `fs.EXIT_HOSTS` (a stage-exit constant, not in the doctor
  module), is re-sourced from `_load_helper_module().EXIT_HOSTS` in that single test.
  Enumerate every `fs.<attr>` before repointing (`grep -oE "fs\.[A-Za-z_]\w*"`): all but
  `EXIT_HOSTS` already lived in the doctor module (incl. `fs.os`, `fs._git_output`).
- **`main()`'s argparse needs `DOCTOR_CHECK_IDS` in the bare-copy fallback.** `--check`'s
  `choices=DOCTOR_CHECK_IDS` is built for EVERY verb, so a package-less copy running a
  non-doctor verb (the stage-exit `_stub_bundle` test) still needs it bound. Added the
  frozen 16-ID tuple as a byte-equal literal in the `except ModuleNotFoundError` block
  (same philosophy as the fallback's `VerifyStatus`). doctor_report/_print_doctor are
  NOT needed there — no package-less test runs the doctor verb (the 3 bare-copy doctor
  tests now `shutil.copytree` the package beside the shim).
- **Bare-copy doctor tests must copy the package.** `test_doctor.py::test_doctor_survives_
  unresolvable_root_and_bare_dir` + `test_doctor_checks.py`'s two lone-helper tests copied
  only `forge-session.py` (+`forge-root.sh`); post-split a lone shim can't run doctor, so
  each now also `copytree`s `scripts/forge_session/`. Still "lone" (no sentinel above
  `scripts/`) so plugin-root stays unresolvable — the tests' actual intent.
- **Host-neutrality grep retargeted.** `test_adapter_host_neutrality.py::test_the_
  interaction_record_is_reachable_from_every_bundle` grepped the bundled shim source for
  `_make_spec("interaction-mode"`; that literal now lives in the bundled
  `forge_session/doctor.py`, so the assertion reads that file. Check present in all 6
  bundles after regen.
- **Primitives added to `_common` (shim keeps its inline copies — item-002 mirror
  pattern):** `_default_branch` (MOVED from discover.py; discover now imports it from
  `_common`), `_counts`, `_config_duplicate_keys`, `invalid_auto_verify_keys`,
  `_default_schema_path`. `RECOVERY_MIN_RUNNER_VERSION` is doctor-only, so it moved
  wholesale INTO doctor.py (deleted from the shim), not mirrored.
- **Orphan shim imports:** moving doctor dropped the only users of `shlex`, `shutil`,
  `PurePosixPath` in the shim — ruff F401 caught them; removed.
- **Pre-existing env failure UNCHANGED:** `test_env_stamp_interactive_never_carries_a_rung`
  still fails in this `claude -p` sandbox — PROVEN environmental by reconstructing the
  pristine HEAD monolith (`git show HEAD:scripts/forge-session.py`) and running the same
  `doctor --json --check interaction-mode`: it also reports `warn`/`unknown`. Full run:
  3086 passed, 2 skipped, that 1 environmental fail. doctor --json exits 0; ruff clean;
  build-adapters --check exits 0 after regen.
- **NOTE for item 008:** doctor.py is 2,119 lines — OVER the 2,000-line ceiling item 008
  asserts. The body alone is 1,979; header + `__all__` push it over. Item 008 (or a
  follow-up) must either trim/compact doctor.py or split it. Item 004 sets no ceiling, so
  this was left as-specified (single doctor.py).

### Item 005 — extract outcomes.py — DONE (pure move, ZERO test edits)

- **Cleanest extraction so far — no monolith-assumption test edits needed.** Unlike item
  004, the outcome verbs' oracles (`tests/test_select_outcome.py`, `tests/test_verify_state.py`,
  46 parity tests) path-load the shim and read the re-exported symbols off it; they do NOT
  bare-copy the shim, grep its source for a moving literal, or monkeypatch `fs.<attr>`. So the
  re-export block resolves them unmodified — `git status` shows ZERO test files touched. Enum
  parity intact. The select-outcome/verify-state CLI contract is frozen and untouched.
- **`outcomes.py` (574 lines)** holds `select_outcome`, `verify_state_for_stage`,
  `_verify_outcome`, `_fix_outcome`, `_verify_reports`, `_read_report_text`, `_section_body`,
  `_parse_report_facts`, `_classify_verify_entry`, `_verify_state_for`, and the NamedTuples
  `_VerifyReport`/`_ReportFacts` (kept in outcomes.py, not `_common` — state.py/exit.py don't
  need them yet). Imports only from `_common` (+ stdlib re/pathlib/typing).
- **Bare-copy fallback GREW by two, same pattern as items 001/003.** `_classify_verify_entry`
  + `_verify_state_for` are reached on EVERY stage-exit routing read, so the `_stub_bundle`
  bare-copy stage-exit tests (package-less shim) need them bound in the `except
  ModuleNotFoundError` block as byte-equal fallbacks. Their transitive deps
  (`_scheduled_stage_version`, `_warn_auto_verify_debt_metadata`, `_VERIFY_RESOLVED`,
  `_EXIT_VERIFY_TOKEN`, `_verify_entry`, `_stage_version`) still live inline in the shim body,
  so the fallback resolves.
- **GOTCHA — spurious adapter-drift false-positive from `__pycache__`.** `build-adapters.py
  --check` does a raw `diff -r` of the regenerated tree vs `adapters/`, and it flags the
  gitignored `adapters/<agent>/scripts/forge_session/__pycache__` that pytest writes when a
  test imports a bundled package copy. validate.sh's drift check (line 177) runs BEFORE pytest
  (line 211), so a run from a CLEAN tree passes — but the leftover `__pycache__` makes the
  NEXT run's early drift check FAIL ("adapters/ is out of date"). Fix: `find . -name __pycache__
  -type d -prune -exec rm -rf {} +` before re-running. The bundled *content* was in sync the
  whole time (check exits 0 once caches are cleared). Relevant to items 006/007/008 — always
  clean caches between validate.sh runs.
- **Pre-existing env failure UNCHANGED:** clean full run = `1 failed, 3086 passed, 2 skipped`,
  the one fail being `test_env_stamp_interactive_never_carries_a_rung` (sandbox ancestry
  reports warn/unknown). PROVEN independent of this item — the diff contains ZERO
  interaction/ancestry code (that's doctor.py, item 004); grep of the diff for
  interaction|ancestry|rung is empty. Same environmental fail items 001-004 logged. doctor
  --json exits 0; ruff clean; adapter --check exits 0 on a clean tree.

### Item 006 — extract state.py (write-side verbs) — DONE (under LOOP EXECUTION POLICY)

The write-cluster (old shim lines 3939–5450, contiguous) is now
`scripts/forge_session/state.py` (1479 lines) — all `cmd_state_*` verbs, the
fail-closed resolvers (`_load_state_for_write`/`_load_epic_state_for_write`/
`_resolve_feature_dir_for_write`/`_load_verify_target`), the verify-entry builder,
`_cascade_staleness`/`_CASCADE_TARGETS`, and the `_print_state_*` printers. Shim
dropped from 6208 → 4782 lines.

- **The three atomic-write primitives were NOT copied into state.py — they were
  DRAINED to `_common` (item-002 foresaw this).** `_now_iso`/`_write_state`/
  `_commit_state` already lived in `_common` (mirrored for decisions.py). Item 006
  DELETED the shim's inline copies and has state.py + the inline exit code import
  them FROM `_common` (state.py imports `_now_iso`/`_commit_state`; the shim re-exports
  all three via the `from forge_session._common import (...)` block for
  `_schedule_auto_verify_debt` + path-loaded tests). Net: ONE copy in `_common`, not
  three. `import tempfile` became a shim orphan (only `_write_state` used it) — removed.
- **Constants MIRRORED into `_common` (shim keeps inline copies — item-002 pattern):**
  `EPIC_STATE_FILENAME`, `SAFE_NAME_RE`, `FULL_GIT_HASH_RE`, `VERIFY_STAGES`,
  `_SKIP_PROTECTED_PRIOR`, `VERIFY_RESULT_STATUSES` (+ `import re`, `get_args` in
  `_common`). `_CASCADE_TARGETS` is cluster-only → moved INTO state.py, not `_common`.
  Free-name analysis (ast, Load names minus local binds minus cluster defs) is the
  reliable way to enumerate what a moved cluster needs from `_common`.
- **Bare-copy fallback grew by ONE: `_assert_safe_name`.** It is called at the TOP of
  `stage_exit` (validates --feature/--epic/--next-feature) on EVERY exit, so the
  package-less `_stub_bundle` stage-exit tests reach it. Item-002 warned bare-copy
  "reaches _now_iso/_commit_state" — EMPIRICALLY FALSE for the surviving package-less
  test: `_stub_rejected` only runs forge-6-docs → docs-routing-failure → exit 2
  BEFORE `_schedule_auto_verify_debt` (the sole inline writer). Confirmed: 612
  stage-exit tests pass with only `_assert_safe_name` added to the fallback. So the
  fallback stays minimal — don't preemptively add write helpers a bare path never hits.
- **Monolith-assumption TEST EDITS (all behaviour-preserving, CLI contract frozen):**
  Moving the writers out of the shim broke tests coupled to them living there:
  1. `tests/test_state_verbs.py` — writer-atomicity spies monkeypatched `FS.tempfile`
     (AttributeError: shim no longer imports tempfile) and greps of the shim source
     for `def _write_state(` etc. Fix: added `_WRITER_MODULE = forge_session._common`
     and `_WRITER_SOURCE = shim + _common.py + state.py` (text concat — line-based
     `_function_source` slices it; do NOT ast.parse a concat, the mid-file
     `from __future__` is a SyntaxError). Spies now patch `_WRITER_MODULE.tempfile/os`;
     source guards read `_WRITER_SOURCE`; `test_tempfile_is_imported...` reads imports
     from `_common.py`. `FS.os` alone would have kept working (os is a shared singleton)
     — only `tempfile` was missing.
  2. `tests/test_state_verb_call_sites.py::test_the_documented_error_messages_still_exist`
     — greps shim for exit-2 prefixes ("no feature directory at"/"refusing to overwrite
     it" → state.py; "atomic write to" → _common.py). Fix: scan shim + state.py +
     _common.py. Verified the literals still exist (relocated, not lost) before editing.
- **Pre-existing env failure UNCHANGED and PROVEN via git worktree:** ran
  `test_env_stamp_interactive_never_carries_a_rung` in a `git worktree add --detach HEAD`
  pristine tree — it fails identically (`('warn','unknown')`), so it's the documented
  `claude -p` sandbox ancestry artifact, not this item. Diff greps clean for
  interaction|ancestry|rung. Full run: 3086 passed, 2 skipped, that 1 env fail. doctor
  --json exits 0; ruff clean; adapter --check exits 0 on a clean tree (state.py bundled
  byte-identical into all 6 adapters). NOTE (item 005 gotcha still bites): pytest writes
  __pycache__ into adapters/ bundles; `find . -name __pycache__ -prune -exec rm -rf {} +`
  before any re-run or the next early drift check false-fails.

### Item 007 — extract exit.py + routes.py (stage-exit + routing engine) — DONE (under LOOP EXECUTION POLICY)

The largest cluster split cleanly into TWO modules under the 2,000-line ceiling:
`forge_session/routes.py` (1,162 lines — the branch/docs/loop terminus builders) and
`forge_session/exit.py` (1,081 lines — `stage_exit` + resolvers + printer). Shim dropped
4,782 → 2,747 lines (2,115 lines moved). Dependency graph is one-directional and
acyclic: **exit.py → routes.py, outcomes.py, state.py, _common**; **routes.py → state.py,
_common**; neither imports the shim.

- **`exit.py` calls 11 route functions; routes calls ZERO exit functions** (AST-verified
  before splitting). That asymmetry is what makes the two-file split safe — put the leaf
  routing helpers in routes.py, the orchestrator in exit.py, and exit.py imports routes,
  never the reverse. `_schedule_auto_verify_debt` (routes) writes state, so routes.py
  imports `_load_verify_target`/`_verify_result_entry` from **state.py**; `stage_exit`
  (exit) imports `_assert_safe_name` from state.py. Importing state.py from exit/routes is
  NOT circular (state.py imports only `_common`).

- **The exit-DOMAIN constants CANNOT leave the shim — they must be MIRRORED to `_common`.**
  `tests/test_stage_constants_parity.py::test_each_shared_constant_is_assigned_exactly_once`
  reads `scripts/forge-session.py` SOURCE and asserts `EXIT_STAGES, EXIT_OUTCOMES,
  VERIFY_MODE_TO_STAGE, NEXT_STEPS_SENTINEL, EXIT_HOSTS` (+ `PRODUCTION_STAGES,
  FULL_GIT_HASH_RE, KNOWN_VERIFY_STATUSES`) are assigned EXACTLY ONCE in the shim; other
  parity tests path-load `session.ExitStage/ProductionStage/EXIT_OUTCOMES/...`; `main()`'s
  argparse (`choices=EXIT_STAGES/EXIT_HOSTS`, `--verify-mode` choices) stays in the shim
  until item 008. So these stay INLINE in the shim AND get byte-equal MIRROR copies in
  `_common` (a copy in a DIFFERENT file is invisible to the exactly-once source-grep). The
  extracted modules import the mirror from `_common`; item 008 drains the shim copy. Added
  to `_common`: the 9 Literal aliases (ProductionStage/ExitStage/VerifyMode/ExitOwner/
  VerifyCapability/Loop|Docs|Verify|FixOutcome), EXIT_STAGES, EXIT_OUTCOMES,
  VERIFY_MODE_TO_STAGE, NEXT_STEPS_SENTINEL, EXIT_HOSTS, STAGE_NOUN, the 3 warning
  templates, and `pending_verify`. (`_EXIT_VERIFY_TOKEN`, `_resolve_feature_dir` were
  already there from items 004/006.)

- **Route-local TABLES that are only path-loaded (never source-grepped) CAN move + be
  re-exported.** `_BRANCH_ROUTE_KIND`, `_BRANCH_OUTCOME_TEXT`, `_LOOP_*` (7), `_DOCS_OUTCOME_TEXT`,
  `_EPIC_TERMINAL_TEXT`, `_RENDER_STATUS_*`, `_RECONCILE_FIRST_TEXT`, `_NO_FINDINGS_RESOLVED_TEXT`,
  and the derived `_EXIT_PRODUCTION_STAGES`/`_BRANCH_STAGES`/`_STAGE_TO_VERIFY_MODE`/`_EXIT_NEXT_STAGE`
  moved INTO the module that uses them (exit.py or routes.py per the AST usage split) and are
  re-exported from the shim, so `session._BRANCH_ROUTE_KIND` etc. still resolve. The
  discriminator is **source-grep vs path-load**: grep the whole `tests/` tree for each name in
  a `read_text()` context — if a parity/`assigned-exactly-once` test greps the shim SOURCE,
  the constant is pinned to the shim; if tests only read `session.X`, it can move.

- **`__file__` anchor moved one level DEEPER (same class as item 004's doctor.py).**
  `_render_status`'s docs router shells out to the sibling `epic-manifest.py`; in the shim
  that was `Path(__file__).resolve().parent / "epic-manifest.py"`. In `routes.py` (at
  `<scripts>/forge_session/routes.py`) that anchor is one dir too shallow, so it now reads a
  module constant `_SCRIPTS_DIR = Path(__file__).resolve().parent.parent`. The frozen
  behaviour (sibling beside the bundle's `forge-session.py`) is preserved; the `_stub_bundle`
  test that copies the package proves it resolves to `bundle/scripts/epic-manifest.py`.

- **Monolith-assumption TEST EDITS (behaviour-preserving; CLI contract frozen; all in
  `tests/test_stage_exit.py`):**
  1. `_stub_bundle` — the bare-copy fixture copied only `forge-session.py`; post-split a lone
     shim can't run stage-exit, so it now also `shutil.copytree`s the `forge_session/` package
     beside it (added `import shutil`). Its INTENT (sibling `.py` resolution) is unchanged.
  2. `test_no_source_path_selects_the_gate_from_the_host_name` — grepped the shim source for
     `def stage_exit(`…`def _print_stage_exit(`; retargeted to `EXIT_MOD` (exit.py) where both
     now live (order preserved by emitting moved symbols in original source order).
  3. `test_docs_resolves_the_helper_beside_itself...` + `test_docs_never_reimplements...` —
     grepped `def _render_status(specs_dir`…`\n_DOCS_OUTCOME_TEXT`; retargeted to `ROUTES_MOD`;
     the first's literal assertion updated `Path(__file__)...parent / "epic-manifest.py"` →
     `_SCRIPTS_DIR / "epic-manifest.py"` (the anchor change above).
  4. `test_loop_never_reimplements...` — grepped `def _loop_route(`…`\ndef _debt_metadata_warnings`;
     retargeted to `ROUTES_MOD`. Added `EXIT_MOD`/`ROUTES_MOD` path constants next to `HELPER`.
  Added a re-exported `_render_status_failure_detail` etc. to the shim's `__all__` (ruff F401
  requires every re-export import to be in `__all__`). `test_stage_exit_protocol.py` needed NO
  edit — it greps ExitStage/ProductionStage/EXIT_OUTCOMES/NEXT_STEPS_SENTINEL, all KEPT inline.

- **Method: SCRIPT the move, don't hand-transcribe 2,100 lines.** AST gives exact
  (start,end) spans (extend upward over `#:` comment blocks); emit each module's symbols in
  original source order (preserves the adjacencies the slice-based source-grep tests rely on:
  `_render_status`→`_DOCS_OUTCOME_TEXT`, `_loop_route`→`_debt_metadata_warnings`,
  `stage_exit`→`_print_stage_exit`); delete the same spans bottom-up from the shim. Free-name
  analysis (Load names minus local binds minus builtins) drives the exact per-module import
  list — but it flags comprehension targets (`mode`), `except … as exc`, nested `def fail`,
  and the `__file__` builtin as false "OTHER"; ignore those.

- **The shim's bare-copy `ModuleNotFoundError` fallback was left UNTOUCHED.** Its
  `_assert_safe_name`/`_classify_verify_entry`/`_verify_state_for` defs (item 006/005 added
  them for the inline stage-exit path) are now dead (a package-less shim can't run stage-exit
  and the bare-copy tests copy the package), but they're harmless — bodies never execute — and
  removing them risks the item-006 source-grep tests. Item 008 can prune them.

- **Pre-existing env failure UNCHANGED and re-proven:** `test_env_stamp_interactive_never_
  carries_a_rung` fails identically on a `git worktree add --detach HEAD` pristine tree
  (`'warn' != 'ok'`); the diff greps clean for interaction|ancestry|rung (that's doctor.py,
  item 004, untouched). Full run: `1 failed, 3086 passed, 2 skipped`. doctor --json exits 0;
  ruff clean; adapter --check exits 0 on a clean tree (exit.py/routes.py bundled byte-identical
  into all 6 adapters). Item-005 `__pycache__` gotcha still bites: clean it before any
  validate.sh re-run or the early drift check false-fails.
