"""Shared pytest fixtures for the epic-manifest helper suite."""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER = REPO_ROOT / "scripts" / "epic-manifest.py"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@dataclass(frozen=True)
class CliResult:
    """Captured result of one helper subprocess invocation.

    Attributes:
        returncode: Process exit code (00 §9 contract: 0/1/2).
        stdout: Decoded standard output.
        stderr: Decoded standard error.
    """

    returncode: int
    stdout: str
    stderr: str

    def json(self) -> Any:
        """Parse stdout as JSON (for --json subcommands)."""
        return json.loads(self.stdout)


@pytest.fixture
def fixtures_dir() -> Path:
    """Absolute path to the read-only fixture templates."""
    return FIXTURES


@pytest.fixture
def fixture_copy(tmp_path: Path) -> "callable[[str], Path]":
    """Return a factory that copies a named fixture tree into tmp_path.

    Returns:
        A function taking a fixture name and returning the copied specs-dir
        root inside tmp_path. Used for any test that mutates state or depends
        on absolute paths.
    """

    def _copy(name: str) -> Path:
        dst = tmp_path / name
        shutil.copytree(FIXTURES / name, dst)
        return dst

    return _copy


@pytest.fixture
def run_cli() -> "callable[..., CliResult]":
    """Return a runner that invokes the helper as a subprocess.

    The subprocess boundary is deliberate: it pins the exit-code and stdout
    JSON contract (00 §9) that skills actually depend on.

    Returns:
        A function `run_cli(*args, cwd=None) -> CliResult`.
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
def helper_module() -> ModuleType:
    """Import epic-manifest.py as a module for in-process unit tests.

    The filename contains a hyphen, so it is loaded via importlib rather than
    a normal import. Used to test pure functions (find_cycle, atomic_write,
    derive_status) directly.
    """
    spec = importlib.util.spec_from_file_location("epic_manifest", HELPER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
