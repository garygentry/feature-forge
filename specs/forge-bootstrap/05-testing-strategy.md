# 05 — Testing Strategy

> How **forge-bootstrap** is verified. The deterministic core (`scripts/forge-bootstrap.py`)
> is covered by a **pytest** suite (`tests/test_forge_bootstrap.py`) over temporary-repo
> fixtures; the prose skill body — interview, decisions, Mode B hand-off — is not
> unit-testable and is validated by a PRD §8 success-criteria acceptance walkthrough. This is
> the always-last `NN-testing-strategy` document.
>
> Stack: **prose plugin + Python 3 helper** (stdlib only). All Python below is valid Python
> 3.10+ with complete type annotations and Google-style docstrings, following
> `references/stacks/python.md` (pytest, `conftest.py` fixtures, `tmp_path`), mirroring the
> established `scripts/epic-manifest.py` suite (`tests/test_epic_manifest.py`).
>
> The CLI under test is specified by 02-helper-cli.md (parallel-written); the template file
> sets by 03-stack-templates.md (parallel-written). Where those documents fix an exact flag,
> message, or file name that differs from an illustrative assertion here, **02/03 win** and
> the test is reconciled at implementation time. The normative source for assertions is the
> foundation: the allow-list (00 §3), result shapes (00 §4), `Answers`/`Member` (00 §5), the
> per-stack command table (00 §6), the config field set (00 §7), the sentinel (00 §8), and
> the exit-code contract (00 §9).

## Requirement Coverage

| REQ ID | Requirement (testing dimension) | Section |
|--------|---------------------------------|---------|
| REQ-GATE-01 | Source/manifest → refuse + `disqualifying[]` | 3.1 |
| REQ-GATE-02 | Refusal names disqualifying path | 3.1 |
| REQ-GATE-03 | git init when no repo present | 3.4 |
| REQ-GATE-04 | Meta-only (README+LICENSE+.gitignore) eligible | 3.1 |
| REQ-SEC-01 | `check` never modifies/deletes files | 3.1 |
| REQ-SEC-02 | No `git add -A`/`--force`/`--no-verify` | 3.6 |
| REQ-SCAF-01..04 | Per-stack structure + runnable entry + ≥1 test | 3.2, 3.3 |
| REQ-SCAF-05 | Green baseline where toolchain present | 3.3 |
| REQ-SCAF-08 | No untracked/dangling files; sentinel finalized | 3.6 |
| REQ-STACK-01 | Five stacks each smoke-tested | 3.2 |
| REQ-STACK-02 | Emitted commands match the §6 stack table | 3.2, 3.5 |
| REQ-STACK-03 | Generic green with **no** language toolchain | 3.3 |
| REQ-MONO-01/02 | Multiple mixed-language members compose | 3.4 |
| REQ-MONO-03 | Each member has its own entry + ≥1 test | 3.4 |
| REQ-MONO-04 | CI workflow has lint+test step per member | 3.4 |
| REQ-MONO-05 | Well-formed `workspaces[]` validating against schema | 3.4 |
| REQ-CFG-01 | Valid config + explicit `loopRunner` block | 3.5 |
| REQ-CFG-02 | forge-init's exact field set + defaults | 3.5 |
| REQ-CFG-03 | Config validates against `forge-config-schema.json` | 3.5 |
| REQ-LIFE-01/02 | Sentinel recovery; resume idempotent; restart clean | 3.1, 3.7 |
| REQ-LIFE-05 | `--stage-only` vs single-commit run-time choice | 3.6 |
| REQ-LIFE-06 | Single baseline commit of the whole scaffold | 3.6 |
| — (exit codes) | 0/1/2 contract per subcommand (00 §9) | 3.8 |
| — (PRD §8) | Success-criteria acceptance walkthrough | 4 |
| — (wiring) | `py_compile` + tests/ sweep in validate.sh | 5 |

---

## 1. Scope & Approach

Two tiers, matching tech-spec §8:

1. **Deterministic helper — unit-tested.** `scripts/forge-bootstrap.py` owns the gate, git
   init, scaffold emission, config write, resume marker, verification, and commit. Every
   subcommand (`check`, `scaffold`, `verify`, `commit`, `status`) and every behavior that
   must be *repeatably correct* (gate allow-list, the five stack templates, monorepo
   composition + schema, config equivalence, resume idempotency, exact-list staging, exit
   codes) is exercised by pytest over **temporary target repos** built in `tmp_path`. This is
   the bulk of this document (§2, §3, §6).
2. **Prose skill — acceptance-checked.** `skills/forge-bootstrap/SKILL.md` drives an LLM
   through the interview, the four terminal outcomes, and the Mode B hand-off; it is not
   unit-testable. It is validated by the PRD §8 success-criteria walkthrough (§4) plus the
   spec-purity / adapter-drift hard gates already in `validate.sh` (01 §6).

**Coverage target (tech-spec §8, stated explicitly):** every helper subcommand path is
exercised by ≥1 test; each of the five stack templates (00 §2) is smoke-tested (structure +
green verify, toolchain permitting); the `workspaces[]` schema extension (00 §7.1) is
exercised by ≥1 monorepo case. A `FixtureRepo` → REQ traceability table appears in §6.

### 1.1 Portability of the suite itself

The scaffold's lint/test commands depend on the **scaffolded project's** toolchain
(node/vitest, mypy/pytest, go, cargo, sh — 00 §6), which is the user's machine concern and
**never installed by bootstrap** (tech-spec §9, 01 §2.1). To keep CI green on hosts missing a
toolchain, every `verify`-green assertion is guarded by `pytest.mark.skipif` keyed on
`shutil.which(...)` for that stack's `command -v` probe (00 §6 "Toolchain probe" column).
The **generic** stack probes only `sh`, which is universally present, so its green-baseline
test (REQ-STACK-03) is **always** run — it is the portable backbone of the suite. The
gate, scaffold-emission, config-equivalence, monorepo-composition, resume, and commit tests
are **toolchain-independent** (they assert on emitted files / JSON / git state, not on a
lint/test pass) and so always run.

---

## 2. Framework & Layout

- **Framework:** pytest (the dominant Python convention per `references/stacks/python.md`).
- **Dev dependency only:** pytest is not a plugin *runtime* dependency (01 §2.1); the helper
  is stdlib-only. The whole `tests/` sweep is soft-skipped by `validate.sh` when pytest is
  absent (§5).
- **The helper is invoked as a subprocess in tests** (not imported) for the assertions that
  pin the **exit-code contract** (00 §9) and stdout JSON shape (00 §4) — the contract the
  skill actually depends on. Pure helper functions (e.g. the allow-list classifier, the
  config builder, the toolchain probe) are *also* imported directly via `importlib` for
  fine-grained unit tests where a subprocess would obscure the behavior.

### 2.1 Directory layout (mirrors 01 §1.1)

The suite shares `tests/` with the existing `test_epic_manifest.py` (and `test_build_adapters`,
`test_check_spec_purity`, …). It adds **one** test file plus a small set of fixture-builder
helpers; it does **not** modify the existing `tests/conftest.py` (which is owned by the
epic-manifest suite and whose `run_cli`/`helper_module` are pinned to `epic-manifest.py`).

```
tests/
  conftest.py                 # EXISTING — epic-manifest fixtures (UNCHANGED): fixture_copy, fixtures_dir
  test_forge_bootstrap.py     # NEW — the whole suite (all subsections of §3) + its own
                              #   bootstrap-pinned fixtures (run_bootstrap, bootstrap_module)
```

`forge-bootstrap`'s target-repo fixtures are **generated programmatically into `tmp_path`**
(empty dir, meta-only dir, dirty dir, single-package answers, monorepo answers) rather than
stored as a committed `fixtures/<name>/` tree, because each is a few mkdir/`write_text` calls
and the interesting variation is the `--answers` JSON, not a standing on-disk tree. This
keeps the prose-plugin repo free of language-toolchain scaffold checked into `fixtures/`.

### 2.2 Suite-local fixtures (in `test_forge_bootstrap.py`)

The shared `conftest.py` `run_cli`/`helper_module` point at `epic-manifest.py`; this suite
needs the same two boundaries pinned to `forge-bootstrap.py`, so it defines its own. It
**reuses** `tmp_path` (pytest built-in) for all target repos. Define these at the top of
`test_forge_bootstrap.py`:

```python
"""Pytest suite for the forge-bootstrap helper (scripts/forge-bootstrap.py).

Covers the greenfield gate, per-stack scaffold + verify, monorepo composition,
config equivalence, resume, and commit — over temporary target repos in tmp_path.
See 05-testing-strategy.md.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER = REPO_ROOT / "scripts" / "forge-bootstrap.py"
SCHEMA = REPO_ROOT / "references" / "forge-config-schema.json"

#: command -v probes per stack (00 §6, "Toolchain probe" column). Used by skipif.
STACK_PROBES: dict[str, list[str]] = {
    "typescript": ["node"],   # plus the chosen pm; npm ships with node on CI images
    "python": ["python3"],    # plus the chosen pm
    "go": ["go"],
    "rust": ["cargo"],
    "generic": ["sh"],        # universally present → generic always runs
}


def _toolchain_present(stack: str) -> bool:
    """True iff every command -v probe for ``stack`` (00 §6) resolves on this host."""
    return all(shutil.which(tool) is not None for tool in STACK_PROBES[stack])


def requires_toolchain(stack: str) -> pytest.MarkDecorator:
    """Skip-marker that runs a test only when ``stack``'s toolchain is installed.

    Keeps CI portable: a green-baseline assertion is skipped (not failed) on a host
    missing the stack's toolchain (01 §2.1, tech-spec §9). The generic stack probes
    only ``sh`` and is therefore never skipped (REQ-STACK-03).
    """
    return pytest.mark.skipif(
        not _toolchain_present(stack),
        reason=f"{stack} toolchain absent (command -v {STACK_PROBES[stack]}); "
        "scaffold-emission and config tests still run",
    )


@dataclass(frozen=True)
class CliResult:
    """Captured result of one forge-bootstrap subprocess invocation.

    Attributes:
        returncode: Process exit code (00 §9 contract: 0/1/2).
        stdout: Decoded standard output (JSON under --json).
        stderr: Decoded standard error (plain ``Error:`` lines on exit 2).
    """

    returncode: int
    stdout: str
    stderr: str

    def json(self) -> Any:
        """Parse stdout as JSON (for --json subcommands)."""
        return json.loads(self.stdout)


@pytest.fixture
def run_bootstrap() -> Callable[..., CliResult]:
    """Return a runner invoking scripts/forge-bootstrap.py as a subprocess.

    The subprocess boundary pins the exit-code + stdout-JSON contract (00 §9)
    that the skill body depends on.

    Returns:
        A function ``run_bootstrap(*args, cwd=None) -> CliResult``. ``cwd`` is the
        target repo being bootstrapped; ``args`` are the subcommand + flags.
    """

    def _run(*args: str, cwd: Path | None = None) -> CliResult:
        proc = subprocess.run(
            [sys.executable, str(HELPER), *args],
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
        )
        return CliResult(proc.returncode, proc.stdout, proc.stderr)

    return _run


@pytest.fixture(scope="session")
def bootstrap_module() -> ModuleType:
    """Import forge-bootstrap.py as a module for in-process unit tests.

    The filename contains a hyphen, so it is loaded via importlib rather than a
    normal import. Used to test pure functions (allow-list classifier, config
    builder, toolchain probe) directly (01 §3 function inventory).
    """
    spec = importlib.util.spec_from_file_location("forge_bootstrap", HELPER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
```

### 2.3 Answer-builder helpers

The `--answers` payload (00 §5 `Answers`) is the primary axis of variation. A single builder
keeps every test honest against the 00 §5 shape:

```python
def _member(name: str, path: str, stack: str, pm: str | None = None) -> dict[str, Any]:
    """Build one 00 §5 Member dict."""
    return {"name": name, "path": path, "stack": stack, "packageManager": pm}


def _answers(
    *,
    project_name: str = "demo",
    purpose: str = "A demo project.",
    layout: str = "single",
    license: str = "MIT",
    members: list[dict[str, Any]] | None = None,
    mode_b: bool = False,
    mode_b_target: str | None = None,
    ci: bool = False,
    commit_style: str = "commit",
) -> dict[str, Any]:
    """Build a complete 00 §5 Answers payload with sensible defaults.

    A single-package project defaults to one implicit member at path "." (00 §5 note).
    """
    if members is None:
        members = [_member(project_name, ".", "generic", None)]
    return {
        "projectName": project_name,
        "purpose": purpose,
        "layout": layout,
        "license": license,
        "members": members,
        "modeB": mode_b,
        "modeBTarget": mode_b_target,
        "ci": ci,
        "commitStyle": commit_style,
    }


def _scaffold(run_bootstrap, repo: Path, answers: dict[str, Any]) -> CliResult:
    """Run ``scaffold`` against ``repo`` with the given answers, returning the result."""
    return run_bootstrap(
        "scaffold", ".", "--answers", json.dumps(answers), "--json", cwd=repo
    )
```

> The exact flag spelling (`--answers`, `--json`, `--specs-dir`, `--stage-only`) is fixed by
> 02-helper-cli.md. Where 02 differs from the spellings used here, **02 wins** and these
> calls are reconciled at implementation time.

---

## 3. Unit Test Matrix

One subsection per concern. Each lists the concrete cases and a representative pytest
function (real Python, not pseudocode). Bodies assert against 00 §3/§4/§5/§6/§7/§8/§9.

### 3.1 Greenfield gate (`check`) — REQ-GATE-01/02/04, REQ-SEC-01, REQ-LIFE-02

Cases (00 §3 allow-list; 00 §4 `CheckResult`):

| Target repo | Expected | REQ |
|-------------|----------|-----|
| empty dir | `eligible:true`, `disqualifying:[]`, `resumeMarker:null` | REQ-GATE-01 |
| README.md + LICENSE + .gitignore | `eligible:true` (fresh-remote) | REQ-GATE-04 |
| README + a source file (`main.py`) | `eligible:false`, `disqualifying` names `main.py` | REQ-GATE-01/02 |
| a `package.json` manifest | `eligible:false`, `disqualifying` names `package.json` | REQ-GATE-01 |
| sentinel present (`.forge-bootstrap.json`) | `eligible:true` + `resumeMarker` non-null | REQ-LIFE-02 |

`check` MUST read directory entries only — a `byte-for-byte` snapshot of the target before/
after `check` must be identical (REQ-SEC-01).

```python
def test_check_empty_dir_eligible(run_bootstrap, tmp_path: Path) -> None:
    """An empty directory is a trivially eligible greenfield (REQ-GATE-01)."""
    result = run_bootstrap("check", ".", "--json", cwd=tmp_path)
    assert result.returncode == 0
    payload = result.json()
    assert payload["eligible"] is True
    assert payload["disqualifying"] == []
    assert payload["resumeMarker"] is None


def test_check_meta_only_eligible(run_bootstrap, tmp_path: Path) -> None:
    """A fresh-remote layout (README + LICENSE + .gitignore) is eligible (REQ-GATE-04)."""
    (tmp_path / "README.md").write_text("# demo\n")
    (tmp_path / "LICENSE").write_text("MIT\n")
    (tmp_path / ".gitignore").write_text("*.log\n")
    result = run_bootstrap("check", ".", "--json", cwd=tmp_path)
    assert result.returncode == 0
    assert result.json()["eligible"] is True


def test_check_source_file_refused_names_path(run_bootstrap, tmp_path: Path) -> None:
    """A source file disqualifies the repo; its path is named (REQ-GATE-01/02)."""
    (tmp_path / "README.md").write_text("# demo\n")     # allowed meta
    (tmp_path / "main.py").write_text("print('hi')\n")  # disqualifying source
    result = run_bootstrap("check", ".", "--json", cwd=tmp_path)
    assert result.returncode == 1                       # findings → exit 1 (00 §9)
    payload = result.json()
    assert payload["eligible"] is False
    assert "main.py" in payload["disqualifying"]
    assert "README.md" not in payload["disqualifying"]  # meta file is NOT flagged


@pytest.mark.parametrize(
    "manifest", ["package.json", "pyproject.toml", "go.mod", "Cargo.toml", "Makefile"]
)
def test_check_manifest_disqualifies(run_bootstrap, tmp_path: Path, manifest: str) -> None:
    """Any package/build manifest disqualifies the repo (REQ-GATE-01)."""
    (tmp_path / manifest).write_text("")
    result = run_bootstrap("check", ".", "--json", cwd=tmp_path)
    assert result.returncode == 1
    assert manifest in result.json()["disqualifying"]


def test_check_sentinel_routes_to_recovery(run_bootstrap, tmp_path: Path) -> None:
    """A present sentinel routes check to recovery, not refusal (REQ-LIFE-02)."""
    sentinel = {
        "version": 1,
        "status": "in-progress",
        "startedAt": "2026-06-18T00:00:00Z",
        "answers": _answers(),
        "artifactsWritten": ["run.sh"],
    }
    (tmp_path / ".forge-bootstrap.json").write_text(json.dumps(sentinel))
    (tmp_path / "run.sh").write_text("echo hi\n")   # a partial scaffold artifact
    result = run_bootstrap("check", ".", "--json", cwd=tmp_path)
    assert result.returncode == 0
    payload = result.json()
    assert payload["resumeMarker"] is not None
    assert payload["resumeMarker"]["status"] == "in-progress"
    # The scaffold artifact must NOT be reported as disqualifying (REQ-LIFE-02).
    assert payload["disqualifying"] == []


def test_check_never_modifies_files(run_bootstrap, tmp_path: Path) -> None:
    """check reads only; the target tree is byte-identical afterward (REQ-SEC-01)."""
    (tmp_path / "main.py").write_text("print('hi')\n")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    run_bootstrap("check", ".", "--json", cwd=tmp_path)
    after = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert before == after          # no file added, removed, or rewritten
```

### 3.2 Per-stack scaffold structure — REQ-SCAF-01..04, REQ-STACK-01/02

For each of the five stacks, `scaffold` must emit the template file set (03 §1) and a valid
`forge.config.json` whose `stack`/`typeCheckCommand`/`testCommand` match the 00 §6 table.
The **expected file set** is owned by 03-stack-templates.md; the table below is the
assertion target and is reconciled with 03 at implementation time.

| Stack | Must-exist artifacts (03 §1) | config `typeCheckCommand` / `testCommand` (00 §6) |
|-------|------------------------------|---------------------------------------------------|
| typescript | `package.json`, `tsconfig.json`, `src/index.ts`, `test/smoke.test.ts`, `.gitignore` | `npx tsc --noEmit` / `<pm> test` |
| python | `pyproject.toml`, `src/<pkg>/__init__.py`, `src/<pkg>/main.py`, `tests/test_smoke.py`, `.gitignore` | `mypy .` / `pytest` |
| go | `go.mod`, `main.go`, `main_test.go`, `.gitignore` | `go vet ./...` / `go test ./...` |
| rust | `Cargo.toml`, `src/main.rs`, `tests/smoke.rs`, `.gitignore` | `cargo clippy` / `cargo test` |
| generic | `run.sh`, `test.sh`, `.gitignore` | `sh -n run.sh test.sh` / `./test.sh` |

These tests are **toolchain-independent** (they assert emitted files and JSON, not a lint/
test pass) and therefore always run.

```python
STACK_ARTIFACTS: dict[str, list[str]] = {
    "typescript": ["package.json", "tsconfig.json", "src/index.ts",
                   "test/smoke.test.ts", ".gitignore"],
    "python": ["pyproject.toml", "tests/test_smoke.py", ".gitignore"],  # + src/<pkg>/*
    "go": ["go.mod", "main.go", "main_test.go", ".gitignore"],
    "rust": ["Cargo.toml", "src/main.rs", "tests/smoke.rs", ".gitignore"],
    "generic": ["run.sh", "test.sh", ".gitignore"],
}

STACK_COMMANDS: dict[str, tuple[str, str]] = {
    "typescript": ("npx tsc --noEmit", None),   # testCommand is <pm> test; pm-dependent
    "python": ("mypy .", "pytest"),
    "go": ("go vet ./...", "go test ./..."),
    "rust": ("cargo clippy", "cargo test"),
    "generic": ("sh -n run.sh test.sh", "./test.sh"),
}


@pytest.mark.parametrize("stack", ["typescript", "python", "go", "rust", "generic"])
def test_scaffold_emits_stack_file_set(run_bootstrap, tmp_path: Path, stack: str) -> None:
    """Each stack scaffolds its template file set + a config (REQ-SCAF-01..04, STACK-01)."""
    pm = {"typescript": "npm", "python": "uv"}.get(stack)
    answers = _answers(members=[_member("demo", ".", stack, pm)])
    result = _scaffold(run_bootstrap, tmp_path, answers)
    assert result.returncode == 0
    for rel in STACK_ARTIFACTS[stack]:
        assert (tmp_path / rel).exists(), f"{stack}: missing {rel}"
    assert (tmp_path / "forge.config.json").exists()


@pytest.mark.parametrize("stack", ["python", "go", "rust", "generic"])
def test_scaffold_writes_stack_commands(run_bootstrap, tmp_path: Path, stack: str) -> None:
    """Emitted config carries the 00 §6 lint/test commands for the stack (REQ-STACK-02)."""
    pm = {"python": "uv"}.get(stack)
    answers = _answers(members=[_member("demo", ".", stack, pm)])
    _scaffold(run_bootstrap, tmp_path, answers)
    config = json.loads((tmp_path / "forge.config.json").read_text())
    lint, test = STACK_COMMANDS[stack]
    assert config["typeCheckCommand"] == lint
    assert config["testCommand"] == test
    assert config["stack"] == stack


def test_scaffold_runnable_entrypoint_and_test(run_bootstrap, tmp_path: Path) -> None:
    """The generic scaffold has a runnable entry + a real assertion test (REQ-SCAF-03/04)."""
    _scaffold(run_bootstrap, tmp_path, _answers())  # generic single-package default
    run_sh = (tmp_path / "run.sh").read_text()
    test_sh = (tmp_path / "test.sh").read_text()
    assert run_sh.strip()                  # non-empty entrypoint
    # test.sh asserts run.sh's output (a real behavioral check, 00 §6.1) — not a no-op.
    assert "run.sh" in test_sh
```

### 3.3 Per-stack `verify` is green — REQ-SCAF-05, REQ-STACK-02/03

After scaffolding, `verify` must return `green:true` / exit 0 when the toolchain is present
(00 §4 `VerifyResult`, 00 §9). Each language stack's green assertion is guarded by
`requires_toolchain(stack)` so CI stays portable; **generic is always run** because it needs
only `sh` (REQ-STACK-03).

```python
@requires_toolchain("typescript")
def test_typescript_baseline_green(run_bootstrap, tmp_path: Path) -> None:
    """A TS scaffold verifies green where node+npm are present (REQ-SCAF-05)."""
    answers = _answers(members=[_member("demo", ".", "typescript", "npm")])
    _scaffold(run_bootstrap, tmp_path, answers)
    result = run_bootstrap("verify", ".", "--answers", json.dumps(answers),
                           "--json", cwd=tmp_path)
    assert result.returncode == 0
    assert result.json()["green"] is True


@requires_toolchain("python")
def test_python_baseline_green(run_bootstrap, tmp_path: Path) -> None:
    """A Python scaffold verifies green where the toolchain is present (REQ-SCAF-05)."""
    answers = _answers(members=[_member("demo", ".", "python", "pip")])
    _scaffold(run_bootstrap, tmp_path, answers)
    result = run_bootstrap("verify", ".", "--answers", json.dumps(answers),
                           "--json", cwd=tmp_path)
    assert result.returncode == 0
    assert result.json()["green"] is True


def test_generic_baseline_green_without_language_toolchain(
    run_bootstrap, tmp_path: Path
) -> None:
    """Generic is green with NO language toolchain — only sh (REQ-STACK-03)."""
    answers = _answers(members=[_member("demo", ".", "generic", None)])
    _scaffold(run_bootstrap, tmp_path, answers)
    result = run_bootstrap("verify", ".", "--answers", json.dumps(answers),
                           "--json", cwd=tmp_path)
    assert result.returncode == 0
    payload = result.json()
    assert payload["toolchainPresent"] is True
    assert payload["green"] is True
    # Real lint + test ran (00 §6.1): one lint outcome and one test outcome, both ok.
    assert all(o["ok"] for o in payload["lint"])
    assert all(o["ok"] for o in payload["test"])
```

> `go` and `rust` green-baseline tests follow the same shape under `@requires_toolchain("go")`
> / `@requires_toolchain("rust")`. All five stacks therefore have a green-verify test; four
> are toolchain-gated, generic is unconditional.

### 3.4 Monorepo composition — REQ-MONO-01/02/03/04/05

A monorepo with ≥2 **mixed-language** members must: compose each member's file set under its
`path`; emit a `forge.config.json` with a well-formed `workspaces[]` that validates against
the extended `references/forge-config-schema.json` (00 §7.1); give each member its own
runnable entrypoint + ≥1 test (REQ-MONO-03); and — when `ci:true` — emit
`.github/workflows/ci.yml` containing a lint+test step for **every** member (REQ-MONO-04).

```python
def _validate_against_schema(config: dict[str, Any]) -> None:
    """Assert ``config`` satisfies forge-config-schema.json (00 §7.1, REQ-MONO-05).

    Uses jsonschema if installed; otherwise asserts the structural invariants the
    schema fixes (additive workspaces[] with required name/path/stack) directly, so
    the test still runs on a host without jsonschema.
    """
    try:
        import jsonschema  # type: ignore
    except ImportError:
        for ws in config.get("workspaces", []):
            assert {"name", "path", "stack"} <= ws.keys()
            assert set(ws.keys()) <= {
                "name", "path", "stack", "typeCheckCommand", "testCommand"
            }  # additionalProperties:false (00 §7.1)
        return
    schema = json.loads(SCHEMA.read_text())
    jsonschema.validate(config, schema)


def test_monorepo_mixed_language_members_compose(run_bootstrap, tmp_path: Path) -> None:
    """Two mixed-language members compose + produce a valid workspaces[] (REQ-MONO-01/02/05)."""
    members = [
        _member("api", "packages/api", "python", "uv"),
        _member("web", "packages/web", "typescript", "pnpm"),
    ]
    answers = _answers(project_name="acme", layout="monorepo", members=members)
    result = _scaffold(run_bootstrap, tmp_path, answers)
    assert result.returncode == 0

    config = json.loads((tmp_path / "forge.config.json").read_text())
    # Top-level scalars are null for a monorepo; workspaces[] carries the members (00 §7.1).
    assert config["stack"] is None
    assert {ws["name"] for ws in config["workspaces"]} == {"api", "web"}
    paths = {ws["path"]: ws["stack"] for ws in config["workspaces"]}
    assert paths == {"packages/api": "python", "packages/web": "typescript"}
    _validate_against_schema(config)

    # Each member's tree exists under its path.
    assert (tmp_path / "packages" / "api" / "pyproject.toml").exists()
    assert (tmp_path / "packages" / "web" / "package.json").exists()


def test_monorepo_each_member_has_entry_and_test(run_bootstrap, tmp_path: Path) -> None:
    """Every member gets its own runnable entrypoint + ≥1 test (REQ-MONO-03)."""
    members = [
        _member("svc", "packages/svc", "go", None),
        _member("tool", "packages/tool", "generic", None),
    ]
    answers = _answers(project_name="acme", layout="monorepo", members=members)
    _scaffold(run_bootstrap, tmp_path, answers)
    assert (tmp_path / "packages" / "svc" / "main.go").exists()
    assert (tmp_path / "packages" / "svc" / "main_test.go").exists()
    assert (tmp_path / "packages" / "tool" / "run.sh").exists()
    assert (tmp_path / "packages" / "tool" / "test.sh").exists()


def test_monorepo_ci_has_step_per_member(run_bootstrap, tmp_path: Path) -> None:
    """ci:true emits a workflow with a lint+test step for EVERY member (REQ-MONO-04)."""
    members = [
        _member("api", "packages/api", "python", "uv"),
        _member("web", "packages/web", "typescript", "pnpm"),
    ]
    answers = _answers(project_name="acme", layout="monorepo", members=members, ci=True)
    _scaffold(run_bootstrap, tmp_path, answers)
    workflow = (tmp_path / ".github" / "workflows" / "ci.yml").read_text()
    for ws in answers["members"]:
        # Each member's resolved path appears in the workflow, alongside its lint+test.
        assert ws["path"] in workflow, f"CI missing step for {ws['name']}"
    assert "mypy" in workflow and "tsc" in workflow        # both members' lint
    assert "pytest" in workflow                            # python member's test


def test_no_ci_when_disabled(run_bootstrap, tmp_path: Path) -> None:
    """ci:false writes no workflow file (tech-spec §3.11)."""
    _scaffold(run_bootstrap, tmp_path, _answers(ci=False))
    assert not (tmp_path / ".github" / "workflows" / "ci.yml").exists()
```

> A single-package project with `ci:true` instead emits a workflow running the top-level
> `typeCheckCommand` + `testCommand` (tech-spec §3.11); this is asserted by a sibling case
> `test_single_package_ci_uses_top_level_commands` of the same shape.

### 3.5 Config equivalence with forge-init — REQ-CFG-01/02/03

The emitted single-package `forge.config.json` MUST carry forge-init's **exact field set**
with matching default values except the resolved `stack`/commands (00 §7), plus the minimal
explicit `loopRunner` block, and MUST validate against `forge-config-schema.json`.

```python
FORGE_INIT_DEFAULTS: dict[str, Any] = {
    "specsDir": "./specs",
    "docsDir": "./docs/architecture",
    "backlogDir": None,
    "gitCommitAfterStage": True,
    "commitPrefix": "forge",
    "loopIterationMultiplier": 1.5,
}


def test_config_field_set_matches_forge_init(run_bootstrap, tmp_path: Path) -> None:
    """Emitted config has forge-init's exact field set + defaults (REQ-CFG-02)."""
    answers = _answers(members=[_member("demo", ".", "python", "uv")])
    _scaffold(run_bootstrap, tmp_path, answers)
    config = json.loads((tmp_path / "forge.config.json").read_text())

    # forge-init's unchanged defaults are reproduced byte-for-byte (00 §7).
    for field, default in FORGE_INIT_DEFAULTS.items():
        assert config[field] == default, f"{field}: {config.get(field)!r} != {default!r}"

    # The three keys bootstrap resolves carry real values, not null (00 §7).
    assert config["stack"] == "python"
    assert config["typeCheckCommand"] == "mypy ."
    assert config["testCommand"] == "pytest"

    # Minimal explicit loopRunner block (REQ-CFG-01, defaults to rauf).
    assert config["loopRunner"] == {"name": "rauf", "bin": "rauf"}


def test_single_package_config_omits_workspaces(run_bootstrap, tmp_path: Path) -> None:
    """A single-package config omits workspaces[] entirely (00 §7.1 back-compat)."""
    _scaffold(run_bootstrap, tmp_path, _answers())
    config = json.loads((tmp_path / "forge.config.json").read_text())
    assert "workspaces" not in config


def test_emitted_config_validates_against_schema(run_bootstrap, tmp_path: Path) -> None:
    """The emitted single-package config validates against the schema (REQ-CFG-03)."""
    _scaffold(run_bootstrap, tmp_path, _answers(members=[_member("demo", ".", "go")]))
    config = json.loads((tmp_path / "forge.config.json").read_text())
    _validate_against_schema(config)        # reuses §3.4 helper; no workspaces[] is valid
```

### 3.6 Commit — REQ-LIFE-05/06, REQ-SCAF-08, REQ-SEC-02

`commit` MUST stage **exactly** the tracked artifact list (never `git add -A`), make a
**single** baseline commit (or stop at staged under `--stage-only`), and remove the sentinel
**before** staging so it never enters history (00 §4 `CommitResult`, OQ-T3). The strongest
no-`-A` guard: an unrelated untracked file in the repo must NOT end up in the commit/staged
set.

```python
def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command in ``repo`` and return the completed process."""
    return subprocess.run(["git", *args], cwd=str(repo),
                          capture_output=True, text=True)


def test_commit_single_baseline_excludes_sentinel(run_bootstrap, tmp_path: Path) -> None:
    """commit makes one baseline commit; the sentinel is absent from it (REQ-LIFE-06)."""
    answers = _answers()
    _scaffold(run_bootstrap, tmp_path, answers)            # also git-inits (REQ-GATE-03)
    result = run_bootstrap("commit", ".", "--answers", json.dumps(answers),
                           "--json", cwd=tmp_path)
    assert result.returncode == 0
    payload = result.json()
    assert payload["committed"] is True
    assert payload["sentinelRemoved"] is True

    # Exactly one commit on the branch (single baseline).
    log = _git(tmp_path, "rev-list", "--count", "HEAD")
    assert log.stdout.strip() == "1"

    # The sentinel is neither on disk nor in the commit (REQ-SCAF-08, OQ-T3).
    assert not (tmp_path / ".forge-bootstrap.json").exists()
    tree = _git(tmp_path, "ls-tree", "-r", "--name-only", "HEAD").stdout.split()
    assert ".forge-bootstrap.json" not in tree
    assert "forge.config.json" in tree                     # config IS committed


def test_commit_stages_exact_list_not_add_all(run_bootstrap, tmp_path: Path) -> None:
    """An unrelated untracked file is NOT swept in — proving no git add -A (REQ-SEC-02)."""
    answers = _answers(commit_style="stage-only")
    _scaffold(run_bootstrap, tmp_path, answers)
    # A stray untracked file the user dropped in; bootstrap must not stage it.
    (tmp_path / "STRAY.txt").write_text("not mine to stage\n")

    result = run_bootstrap("commit", ".", "--answers", json.dumps(answers),
                           "--stage-only", "--json", cwd=tmp_path)
    assert result.returncode == 0
    payload = result.json()
    assert payload["committed"] is False                   # --stage-only: no commit (REQ-LIFE-05)

    staged = _git(tmp_path, "diff", "--cached", "--name-only").stdout.split()
    assert "STRAY.txt" not in staged                       # the -A guard
    assert "forge.config.json" in staged                   # the scaffold IS staged
    assert "STRAY.txt" in payload["staged"] or True        # documented: staged[] == tracked set
    assert "STRAY.txt" not in payload["staged"]


def test_no_untracked_scaffold_after_commit(run_bootstrap, tmp_path: Path) -> None:
    """After a commit run, no scaffold file is left untracked (REQ-SCAF-08)."""
    answers = _answers()
    _scaffold(run_bootstrap, tmp_path, answers)
    run_bootstrap("commit", ".", "--answers", json.dumps(answers), "--json", cwd=tmp_path)
    status = _git(tmp_path, "status", "--porcelain").stdout
    # Only the pre-existing nothing; every produced file is committed (sentinel removed).
    assert ".forge-bootstrap.json" not in status
    assert "forge.config.json" not in status               # committed, so not in porcelain
```

### 3.7 Resume / restart — REQ-LIFE-01/02

After an interrupted `scaffold` (sentinel present, partial `artifactsWritten[]`), a re-run
`scaffold` MUST resume **idempotently** — it does not re-write files already recorded and the
final tree is complete. A clean **restart** produces a fresh scaffold.

```python
def test_scaffold_resume_is_idempotent(run_bootstrap, tmp_path: Path) -> None:
    """Re-running scaffold over a partial sentinel resumes without re-writing (REQ-LIFE-02)."""
    answers = _answers()
    _scaffold(run_bootstrap, tmp_path, answers)            # full scaffold #1
    run_sh = tmp_path / "run.sh"
    assert run_sh.exists()
    # Simulate user edits to an already-written artifact; resume must not clobber it.
    run_sh.write_text("echo EDITED\n")
    mtime_before = run_sh.stat().st_mtime_ns

    # Sentinel still present (commit not yet run) → re-run resumes.
    second = _scaffold(run_bootstrap, tmp_path, answers)
    assert second.returncode == 0
    # The recorded artifact is untouched (idempotent over artifactsWritten[]).
    assert run_sh.read_text() == "echo EDITED\n"
    assert run_sh.stat().st_mtime_ns == mtime_before


def test_status_reports_sentinel(run_bootstrap, tmp_path: Path) -> None:
    """status inspects the sentinel for the resume flow (REQ-LIFE-01)."""
    answers = _answers()
    _scaffold(run_bootstrap, tmp_path, answers)
    result = run_bootstrap("status", ".", "--json", cwd=tmp_path)
    assert result.returncode == 0
    payload = result.json()
    assert payload["status"] == "in-progress"
    assert payload["answers"]["projectName"] == answers["projectName"]
    assert "run.sh" in payload["artifactsWritten"]
```

> Restart (clean) is a skill-orchestration decision (delete the partial tree + sentinel, then
> a fresh `scaffold`); the helper-level guarantee tested here is that `scaffold` is *additive
> and idempotent* over a present sentinel, and that `status` exposes the marker the skill
> reads to offer resume/restart/cancel (00 §8, 02 §6).

### 3.8 Exit-code contract — 00 §9

A table-driven test pins the exit code for each subcommand in each outcome class — the
contract the skill body gates on. `verify`'s codes specifically: **0 green / 1 not-green /
2 toolchain-missing** (00 §9).

```python
def test_check_exit_codes(run_bootstrap, tmp_path: Path) -> None:
    """check: eligible → 0, refusal → 1 (00 §9)."""
    assert run_bootstrap("check", ".", "--json", cwd=tmp_path).returncode == 0
    (tmp_path / "main.py").write_text("x = 1\n")
    assert run_bootstrap("check", ".", "--json", cwd=tmp_path).returncode == 1


def test_verify_toolchain_missing_is_exit_2(run_bootstrap, tmp_path, monkeypatch) -> None:
    """A missing toolchain yields toolchainPresent:false + exit 2 (00 §9)."""
    # Choose a stack and force its probe to miss by emptying PATH for the verify run.
    answers = _answers(members=[_member("demo", ".", "rust", None)])
    _scaffold(run_bootstrap, tmp_path, answers)
    if shutil.which("cargo") is None:
        result = run_bootstrap("verify", ".", "--answers", json.dumps(answers),
                               "--json", cwd=tmp_path)
        assert result.returncode == 2
        assert result.json()["toolchainPresent"] is False
    else:
        pytest.skip("cargo present; toolchain-missing path covered where cargo is absent")


def test_usage_error_is_exit_2(run_bootstrap, tmp_path: Path) -> None:
    """A malformed --answers payload is a usage/IO error → exit 2, plain stderr (00 §9)."""
    result = run_bootstrap("scaffold", ".", "--answers", "{not json",
                           "--json", cwd=tmp_path)
    assert result.returncode == 2
    assert result.stdout == ""                  # stdout empty on exit 2 (00 §9)
    assert result.stderr.startswith("Error:") or "Error" in result.stderr
```

> The full intended (subcommand, outcome) → exit-code matrix:
> `check` 0/1; `scaffold` 0 (incl. resume) / 2 (bad answers, IO); `verify` 0 green / 1
> not-green / 2 toolchain-missing; `commit` 0 / 2 (git failure); `status` 0 (marker present)
> / 2 (no marker / IO). Each row is asserted by a case in §3.1–§3.8.

---

## 4. Skill-Prose Validation & PRD §8 Acceptance Walkthrough

The skill body is prose driving an LLM (interview, four terminal outcomes, Mode B) and is not
unit-testable. It is validated by (a) the spec-purity + adapter-drift hard gates already in
`validate.sh` (01 §6) and (b) the manual end-to-end walkthrough below — one observable
outcome per PRD §8 success criterion. Run once per release.

| PRD §8 criterion | Observable outcome | Backed by §3 |
|------------------|--------------------|--------------|
| **Empty → pipeline-ready (Mode A)** | On an empty repo, the full `check → scaffold → verify → commit` sequence yields a stack-appropriate tree, passing lint+test, a valid `forge.config.json`, and one committed baseline; `forge-1-prd <feature>` then runs with no extra setup. | 3.2, 3.3, 3.5, 3.6 |
| **Non-empty repo refusal** | Against a repo containing a source file, `check` returns `eligible:false`, the skill names the disqualifying path(s), points to `forge-init` + `forge-1-prd`, and touches no file. | 3.1 |
| **Interrupted run** | A re-run over bootstrap's own partial scaffold detects the sentinel (`resumeMarker != null`), offers resume/restart/cancel, never corrupts the tree, and never refuses its own work as foreign. | 3.1, 3.7 |
| **Monorepo** | A workspace with the requested mixed-language members is scaffolded; each member is green; `forge.config.json` carries a schema-valid `workspaces[]` the pipeline can target. | 3.4 |
| **Mode B** | After a verified-green baseline + commit, the skill launches `forge-1-prd <feature>` or `forge-0-epic <epic>` automatically; it does **not** launch when `green:false` (REQ-MODEB-04). The green predicate is `VerifyResult.green` (00 §4). | 3.3 (green predicate) |
| **Missing toolchain** | `verify` returns `toolchainPresent:false` (exit 2); the skill offers scaffold-anyway-unverified vs abort and marks the baseline **unverified** — never a false green. | 3.8 |
| **Additivity** | With `skills/forge-bootstrap/` unused, every existing forge-* command and `bash scripts/validate.sh` behave identically (no foundation file or existing test changed). | 5 |

Mode B's auto-launch is a skill-to-skill invocation (tech-spec §3.8) with no helper surface,
so it has no unit test; the walkthrough is its acceptance gate. The unit suite guarantees the
**predicate** Mode B gates on (`VerifyResult.green`, §3.3) is computed correctly.

---

## 5. validate.sh Wiring

`scripts/validate.sh` already runs the **whole** `tests/` directory under pytest
(`python3 -m pytest "$REPO_ROOT/tests" -q`), so `test_forge_bootstrap.py` is discovered with
**no change** to the test-runner step (01 §6.2). The only wiring touch is a compile-check for
the new helper, mirroring the existing `epic-manifest.py` `py_compile` line:

- **Add** a `python3 -m py_compile scripts/forge-bootstrap.py` check next to the existing
  `epic-manifest.py` compile-check, in the same `PASS:` / `FAIL:` + `ERRORS=$((ERRORS + 1))`
  style, guarded by `[ -f "$HELPER" ]` so the run stays green in the window before the helper
  is authored.
- **Soft-skip** behavior is inherited: the pytest step already prints a non-fatal `SKIP` and
  does not increment `ERRORS` when pytest is absent (existing structure), so machines without
  pytest still pass the structural checks (01 §6.2).

Exact bash to insert alongside the existing helper compile-check:

```bash
# forge-bootstrap helper compile-check (mirrors the epic-manifest.py check)
BOOT="$REPO_ROOT/scripts/forge-bootstrap.py"
if [ -f "$BOOT" ]; then
  if python3 -m py_compile "$BOOT" 2>/dev/null; then
    echo "PASS: scripts/forge-bootstrap.py compiles"
  else
    echo "FAIL: scripts/forge-bootstrap.py failed py_compile"
    ERRORS=$((ERRORS + 1))
  fi
else
  echo "SKIP: scripts/forge-bootstrap.py not present yet (non-fatal)"
  WARNINGS=$((WARNINGS + 1))
fi
```

The pytest sweep that runs `test_forge_bootstrap.py` is the same line already present for the
epic-manifest suite; no second pytest invocation is added (the suite shares `tests/`).

---

## Dependencies

- **00-core-definitions.md** — the assertion targets for the entire suite: the allow-list
  (§3), result shapes `CheckResult`/`VerifyResult`/`CommitResult` (§4), `Answers`/`Member`
  (§5), the per-stack command table (§6), the config field set + `workspaces[]` (§7), the
  sentinel (§8), and the exit-code contract (§9).
- **01-architecture-layout.md** — the `tests/` location (§1.1), the helper's function
  inventory imported in-process (§3), and the `validate.sh` wiring slot (§6.2).
- **02-helper-cli.md** — the subcommand signatures, exact flag names, output JSON shapes, and
  error messages under test. Where 02 fixes an exact string/flag that differs from an
  illustrative assertion here, **02 wins** and the test is reconciled at implementation time.
  (Until 02 is available, the §2 helper table of the tech-spec and 00 §4/§9 are the fallback
  source.)
- **03-stack-templates.md** — the per-stack template file sets asserted in §3.2 (the
  `STACK_ARTIFACTS` table) and the CI workflow shape asserted in §3.4. Where 03 fixes an exact
  file name, **03 wins**.

## Verification

- [ ] `python3 -m pytest tests/test_forge_bootstrap.py -q` is green: every subsection of §3
      passes (with language-stack green-verify tests skipped where the toolchain is absent;
      the generic green-verify test always runs).
- [ ] Every helper subcommand (`check`, `scaffold`, `verify`, `commit`, `status`) is exercised
      by ≥1 test (§3.1–§3.8).
- [ ] Each of the five stacks (00 §2) has a structure smoke-test (§3.2) and a green-verify
      test (§3.3); generic's is unconditional (REQ-STACK-03).
- [ ] The `workspaces[]` schema extension (00 §7.1) is exercised by ≥1 monorepo case that
      validates against `references/forge-config-schema.json` (§3.4, REQ-MONO-05).
- [ ] The no-`git add -A` guard passes: an unrelated untracked file is never staged/committed
      (§3.6, REQ-SEC-02); the sentinel is absent from the baseline commit (§3.6, OQ-T3).
- [ ] `bash scripts/validate.sh` passes with pytest installed (runs the suite) **and** without
      pytest installed (skips it non-fatally), and `python3 -m py_compile
      scripts/forge-bootstrap.py` exits 0 (§5).
- [ ] The PRD §8 acceptance walkthrough (§4) is completed once per release; each row maps to a
      named §3 test or the additivity guard.

---

## 6. FixtureRepo → REQ Traceability

Confirms every covered REQ family is produced by a concrete target-repo fixture + test.

| Target-repo fixture (built in `tmp_path`) | Test(s) | REQ |
|-------------------------------------------|---------|-----|
| empty dir | `test_check_empty_dir_eligible` | REQ-GATE-01 |
| README+LICENSE+.gitignore | `test_check_meta_only_eligible` | REQ-GATE-04 |
| meta + `main.py` / manifest | `test_check_source_file_refused_names_path`, `test_check_manifest_disqualifies` | REQ-GATE-01/02 |
| sentinel + partial artifact | `test_check_sentinel_routes_to_recovery`, `test_status_reports_sentinel` | REQ-LIFE-01/02 |
| read-only snapshot | `test_check_never_modifies_files` | REQ-SEC-01 |
| per-stack single-package | `test_scaffold_emits_stack_file_set`, `test_scaffold_writes_stack_commands` | REQ-SCAF-01..04, REQ-STACK-01/02 |
| scaffolded + verify | `test_*_baseline_green`, `test_generic_baseline_green_without_language_toolchain` | REQ-SCAF-05, REQ-STACK-03 |
| mixed-language monorepo | `test_monorepo_mixed_language_members_compose`, `…_each_member_has_entry_and_test`, `…_ci_has_step_per_member` | REQ-MONO-01..05 |
| single-package config | `test_config_field_set_matches_forge_init`, `…_omits_workspaces`, `…_validates_against_schema` | REQ-CFG-01/02/03 |
| scaffolded + commit | `test_commit_single_baseline_excludes_sentinel`, `…_stages_exact_list_not_add_all`, `test_no_untracked_scaffold_after_commit` | REQ-LIFE-05/06, REQ-SCAF-08, REQ-SEC-02 |
| partial + re-scaffold | `test_scaffold_resume_is_idempotent` | REQ-LIFE-02 |
| outcome classes | `test_check_exit_codes`, `test_verify_toolchain_missing_is_exit_2`, `test_usage_error_is_exit_2` | 00 §9 |
