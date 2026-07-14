"""Tests for ``forge-session.py check-epic-base`` — the split-brain-epic base guard.

Defense-in-depth for Issue #125: when a feature resolves to a nested epic member
on the current branch but the epic's ``epic-manifest.json`` is missing on HEAD,
the member was reached from a branch that predates or lacks the manifest commit
(a detached base). The helper flags that as ``warn-detached-base`` and points at
the member's recorded home branch. It is strictly read-only.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER = REPO_ROOT / "scripts" / "forge-session.py"


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )
    assert proc.returncode == 0, f"git {' '.join(args)}: {proc.stderr}"
    return proc.stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("# scratch\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")


def _write_member(repo: Path, epic: str, feature: str, state: dict) -> None:
    d = repo / "specs" / epic / feature
    d.mkdir(parents=True, exist_ok=True)
    (d / ".pipeline-state.json").write_text(json.dumps(state))


def _write_manifest(repo: Path, epic: str) -> None:
    d = repo / "specs" / epic
    d.mkdir(parents=True, exist_ok=True)
    (d / "epic-manifest.json").write_text(json.dumps({"epic": epic, "features": []}))


def _check(repo: Path, feature: str, *extra: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(HELPER), "check-epic-base", "--feature", feature,
         "--json", *extra],
        capture_output=True, text=True, cwd=str(repo),
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_detached_base_warns_with_home_branch(tmp_path: Path) -> None:
    """Member resolves but the manifest is missing on HEAD → warn-detached-base."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_member(repo, "data-enhancement", "program-benchmarks",
                  {"branch": "forge/data-enhancement", "epic": "data-enhancement"})
    # No epic-manifest.json on this branch — the detached-base condition.

    payload = _check(repo, "program-benchmarks")

    assert payload["action"] == "warn-detached-base"
    assert payload["isEpicMember"] is True
    assert payload["epic"] == "data-enhancement"
    assert payload["manifestOnHead"] is False
    assert payload["homeBranch"] == "forge/data-enhancement"


def test_manifest_present_is_a_noop(tmp_path: Path) -> None:
    """Member resolves and the manifest is on HEAD → action none."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_manifest(repo, "data-enhancement")
    _write_member(repo, "data-enhancement", "program-benchmarks",
                  {"branch": "forge/data-enhancement", "epic": "data-enhancement"})

    payload = _check(repo, "program-benchmarks")

    assert payload["action"] == "none"
    assert payload["isEpicMember"] is True
    assert payload["manifestOnHead"] is True


def test_standalone_feature_is_a_noop(tmp_path: Path) -> None:
    """A flat standalone feature has no epic base to check → action none."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    d = repo / "specs" / "widget"
    d.mkdir(parents=True)
    (d / ".pipeline-state.json").write_text(json.dumps({"branch": "main"}))

    payload = _check(repo, "widget")

    assert payload["action"] == "none"
    assert payload["isEpicMember"] is False
    assert payload["epic"] is None


def test_unresolved_feature_reports_not_resolved(tmp_path: Path) -> None:
    """A feature that does not resolve on the current branch → not-resolved."""
    repo = tmp_path / "repo"
    _init_repo(repo)

    payload = _check(repo, "ghost")

    assert payload["action"] == "not-resolved"
    assert payload["isEpicMember"] is False


def test_non_git_directory_degrades(tmp_path: Path) -> None:
    """Outside a git repo: exit 0, gitRepo false, action none — never a crash."""
    workdir = tmp_path / "plain"
    workdir.mkdir()

    payload = _check(workdir, "widget")

    assert payload["gitRepo"] is False
    assert payload["action"] == "none"
