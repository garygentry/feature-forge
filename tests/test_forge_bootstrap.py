"""Pytest suite for the forge-bootstrap helper (scripts/forge-bootstrap.py).

Covers the greenfield gate, per-stack scaffold + verify, monorepo composition,
config equivalence, resume, and commit — over temporary target repos in tmp_path.
See 05-testing-strategy.md.

This file currently exercises the foundation (item 002): the shared fixtures,
the constants/types, and the argparse dispatch. Subcommand-behavior tests are
added by later items (003/006/008/009/010/011) as the stubs are filled.
"""

from __future__ import annotations

import importlib.util
import json
import os
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
        A function ``run_bootstrap(*args, cwd=None, env=None) -> CliResult``. ``cwd``
        is the target repo being bootstrapped; ``args`` are the subcommand + flags;
        ``env``, when given, is merged over ``os.environ`` for the child process
        (lets a test control ``PATH`` to force a deterministic toolchain miss — see
        ``test_verify_toolchain_missing_is_exit_2``).
    """

    def _run(
        *args: str, cwd: Path | None = None, env: dict[str, str] | None = None
    ) -> CliResult:
        child_env = {**os.environ, **env} if env is not None else None
        proc = subprocess.run(
            [sys.executable, str(HELPER), *args],
            capture_output=True,
            text=True,
            cwd=str(cwd) if cwd else None,
            env=child_env,
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


# --------------------------------------------------------------------------- #
# Answer-builder helpers (05 §2.3)
# --------------------------------------------------------------------------- #


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
    author: str = "Demo Author",
    host: str | None = None,
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
        "author": author,
        "host": host,
    }


def _scaffold(run_bootstrap, repo: Path, answers: dict[str, Any]) -> CliResult:
    """Run ``scaffold`` against ``repo`` with the given answers, returning the result."""
    return run_bootstrap(
        "scaffold", ".", "--answers", json.dumps(answers), "--json", cwd=repo
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command in ``repo`` and return the completed process."""
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True
    )


# --------------------------------------------------------------------------- #
# Foundation tests (item 002) — module loads, constants/types, dispatch parse
# --------------------------------------------------------------------------- #


def test_helper_file_exists() -> None:
    """The helper module exists at its load-bearing path (01 §1.1)."""
    assert HELPER.is_file()


def test_module_imports_cleanly(bootstrap_module: ModuleType) -> None:
    """The hyphenated helper loads via importlib without error (05 §2.2)."""
    assert bootstrap_module is not None


def test_constants_present(bootstrap_module: ModuleType) -> None:
    """The 00 §2/§3/§6 constants are defined with their canonical values."""
    m = bootstrap_module
    assert m.SENTINEL_FILENAME == ".forge-bootstrap.json"
    assert m.ALLOWED_META_DIRS == frozenset({".git"})
    assert set(m.PACKAGE_MANAGERS) == {"typescript", "python"}
    assert m.PACKAGE_MANAGERS["typescript"] == ["npm", "pnpm", "yarn"]
    assert m.PACKAGE_MANAGERS["python"] == ["uv", "poetry", "pip"]
    assert set(m.STACK_COMMANDS) == {"typescript", "python", "go", "rust", "generic"}
    # The allow-list regex passes meta files and rejects source/manifest files.
    assert m.ALLOWED_META_FILE_RE.match("README.md")
    assert m.ALLOWED_META_FILE_RE.match("license")  # case-insensitive
    assert m.ALLOWED_META_FILE_RE.match(".gitignore")
    assert not m.ALLOWED_META_FILE_RE.match("main.py")
    assert not m.ALLOWED_META_FILE_RE.match("package.json")


def test_stack_commands_match_table(bootstrap_module: ModuleType) -> None:
    """STACK_COMMANDS carries the resolved 00 §6 lint/test/probe entries."""
    sc = bootstrap_module.STACK_COMMANDS
    assert sc["python"] == ("mypy .", "pytest", ("python3", "{pm}"))
    assert sc["go"] == ("go vet ./...", "go test ./...", ("go",))
    assert sc["rust"] == ("cargo clippy", "cargo test", ("cargo",))
    assert sc["generic"] == ("sh -n run.sh test.sh", "./test.sh", ("sh",))
    assert sc["typescript"][0] == "npx tsc --noEmit"


def test_exceptions_defined(bootstrap_module: ModuleType) -> None:
    """UsageError (exit 2) and FindingsError (exit 1) exist as Exceptions (02 §2)."""
    m = bootstrap_module
    assert issubclass(m.UsageError, Exception)
    assert issubclass(m.FindingsError, Exception)
    assert m.UsageError("boom").message == "boom"
    assert m.FindingsError({"eligible": False}).result == {"eligible": False}


def test_io_layer_round_trips_sentinel(bootstrap_module: ModuleType, tmp_path: Path) -> None:
    """write_sentinel/read_sentinel round-trip; absent sentinel reads as None (02 §8.1)."""
    m = bootstrap_module
    assert m.read_sentinel(tmp_path) is None
    sentinel = {
        "version": 1,
        "status": "in-progress",
        "startedAt": "2026-06-19T00:00:00+00:00",
        "answers": _answers(),
        "artifactsWritten": ["run.sh"],
    }
    m.write_sentinel(tmp_path, sentinel)
    assert (tmp_path / ".forge-bootstrap.json").is_file()
    assert m.read_sentinel(tmp_path) == sentinel


def test_run_wrapper_returns_completed_process(
    bootstrap_module: ModuleType, tmp_path: Path
) -> None:
    """run() wraps subprocess; check=False returns the process for inspection (02 §8.1)."""
    proc = bootstrap_module.run(["sh", "-c", "exit 3"], cwd=tmp_path, check=False)
    assert proc.returncode == 3


def test_parser_parses_all_subcommands_and_flags(bootstrap_module: ModuleType) -> None:
    """main()'s parser accepts check/scaffold/verify/commit/status + their flags (02 §8.2)."""
    parser = bootstrap_module._build_parser()

    args = parser.parse_args(["check", ".", "--specs-dir", "specs", "--json"])
    assert args.cmd == "check" and args.json_output is True and args.specs_dir == "specs"

    args = parser.parse_args(["scaffold", ".", "--answers", "{}", "--json"])
    assert args.cmd == "scaffold" and args.answers == "{}"

    args = parser.parse_args(["verify", ".", "--answers", "{}"])
    assert args.cmd == "verify" and args.json_output is False

    args = parser.parse_args(["commit", ".", "--answers", "{}", "--stage-only"])
    assert args.cmd == "commit" and args.stage_only is True

    args = parser.parse_args(["status", "."])
    assert args.cmd == "status"


def test_subcommand_bodies_are_stubs(bootstrap_module: ModuleType, tmp_path: Path) -> None:
    """The remaining subcommand functions are NotImplementedError stubs for now.

    ``check`` is implemented (item 003); scaffold/verify/commit/status remain stubs
    until their items fill them.
    """
    m = bootstrap_module
    answers = _answers()
    for call in (
        lambda: m.scaffold(tmp_path, answers),
        lambda: m.verify(tmp_path, answers),
        lambda: m.commit(tmp_path, answers, False),
        lambda: m.status(tmp_path),
    ):
        with pytest.raises(NotImplementedError):
            call()


def test_malformed_answers_is_exit_2(run_bootstrap, tmp_path: Path) -> None:
    """A malformed --answers payload is a usage error → exit 2 before any stub (00 §9)."""
    result = run_bootstrap(
        "scaffold", ".", "--answers", "{not json", "--json", cwd=tmp_path
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert "Error" in result.stderr


def test_missing_subcommand_is_usage_error(run_bootstrap, tmp_path: Path) -> None:
    """Invoking with no subcommand is an argparse usage error (non-zero exit)."""
    result = run_bootstrap(cwd=tmp_path)
    assert result.returncode != 0


# --------------------------------------------------------------------------- #
# `check` subcommand tests (item 003) — greenfield gate + recovery (02 §3)
# --------------------------------------------------------------------------- #


def _sentinel(**overrides: Any) -> dict[str, Any]:
    """Build a minimal own-tool Sentinel (00 §8) for recovery tests."""
    base = {
        "version": 1,
        "status": "in-progress",
        "startedAt": "2026-06-19T00:00:00+00:00",
        "answers": _answers(),
        "artifactsWritten": ["run.sh"],
    }
    base.update(overrides)
    return base


def test_check_empty_dir_eligible(run_bootstrap, tmp_path: Path) -> None:
    """An empty target is trivially eligible, exit 0 (00 §3)."""
    result = run_bootstrap("check", ".", "--json", cwd=tmp_path)
    assert result.returncode == 0
    payload = result.json()
    assert payload["eligible"] is True
    assert payload["disqualifying"] == []
    assert payload["resumeMarker"] is None


def test_check_fresh_remote_layout_eligible(run_bootstrap, tmp_path: Path) -> None:
    """README + LICENSE + .gitignore + ./specs is eligible (REQ-GATE-04)."""
    (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")
    (tmp_path / "LICENSE").write_text("MIT\n", encoding="utf-8")
    (tmp_path / ".gitignore").write_text("node_modules\n", encoding="utf-8")
    (tmp_path / "specs").mkdir()
    result = run_bootstrap("check", ".", "--json", cwd=tmp_path)
    assert result.returncode == 0
    payload = result.json()
    assert payload["eligible"] is True
    assert payload["disqualifying"] == []


def test_check_source_file_refused(run_bootstrap, tmp_path: Path) -> None:
    """A source file disqualifies and is named in disqualifying[] (REQ-GATE-01/02)."""
    src = tmp_path / "src"
    src.mkdir()
    (src / "index.ts").write_text("export const x = 1;\n", encoding="utf-8")
    result = run_bootstrap("check", ".", "--json", cwd=tmp_path)
    assert result.returncode == 1
    payload = result.json()
    assert payload["eligible"] is False
    assert "src" in payload["disqualifying"]


def test_check_manifest_file_refused(run_bootstrap, tmp_path: Path) -> None:
    """A package manifest disqualifies and is named (REQ-GATE-01/02)."""
    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")
    result = run_bootstrap("check", ".", "--json", cwd=tmp_path)
    assert result.returncode == 1
    payload = result.json()
    assert payload["eligible"] is False
    assert "package.json" in payload["disqualifying"]


def test_check_own_sentinel_sets_resume_marker(run_bootstrap, tmp_path: Path) -> None:
    """An own sentinel yields resumeMarker != null and eligible, exit 0 (REQ-LIFE-02)."""
    # Disqualifying file present, but the live sentinel routes to recovery.
    (tmp_path / "package.json").write_text("{}\n", encoding="utf-8")
    sentinel = _sentinel()
    (tmp_path / ".forge-bootstrap.json").write_text(
        json.dumps(sentinel), encoding="utf-8"
    )
    result = run_bootstrap("check", ".", "--json", cwd=tmp_path)
    assert result.returncode == 0
    payload = result.json()
    assert payload["eligible"] is True
    assert payload["resumeMarker"] is not None
    assert payload["resumeMarker"]["artifactsWritten"] == ["run.sh"]


def test_check_is_read_only(run_bootstrap, tmp_path: Path) -> None:
    """check writes/deletes no files (read-only gate, REQ-SEC-01)."""
    (tmp_path / "README.md").write_text("# demo\n", encoding="utf-8")
    before = sorted(p.name for p in tmp_path.iterdir())
    run_bootstrap("check", ".", "--json", cwd=tmp_path)
    after = sorted(p.name for p in tmp_path.iterdir())
    assert before == after


def test_check_reports_has_git(run_bootstrap, tmp_path: Path) -> None:
    """hasGit reflects a pre-existing .git/ directory (REQ-GATE-03 signal)."""
    result = run_bootstrap("check", ".", "--json", cwd=tmp_path)
    assert result.json()["hasGit"] is False
    (tmp_path / ".git").mkdir()
    result = run_bootstrap("check", ".", "--json", cwd=tmp_path)
    assert result.json()["hasGit"] is True


def test_answers_builder_shape() -> None:
    """The _answers helper produces the full 00 §5 Answers key set."""
    answers = _answers()
    assert set(answers) == {
        "projectName", "purpose", "layout", "license", "members",
        "modeB", "modeBTarget", "ci", "commitStyle", "author", "host",
    }
    assert answers["members"][0] == {
        "name": "demo", "path": ".", "stack": "generic", "packageManager": None
    }
