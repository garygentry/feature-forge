"""Tests for ``forge-session.py reconcile-branch`` — imposed/session-branch drift (Chunk 6).

A hosted environment (Claude.ai remote, cloud agents) imposes an arbitrary session
branch that Branch Setup silently records as the feature's ``branch``. When the user
moves to the intended topic branch the recorded field goes stale, and every branch-aware
mechanism (the loop guard, discover-feature) keys off it. ``reconcile-branch`` decides —
read-only — whether the recorded branch should adopt the current one, with a
default-branch guardrail so genuine drift-back-to-default is warned, not adopted.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER = REPO_ROOT / "scripts" / "forge-session.py"


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True)
    assert proc.returncode == 0, f"git {' '.join(args)}: {proc.stderr}"
    return proc.stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("# scratch\n")
    (repo / "forge.config.json").write_text("{}\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


def _write_state(repo: Path, feature: str, branch: str | None) -> None:
    d = repo / "specs" / feature
    d.mkdir(parents=True, exist_ok=True)
    state = {
        "feature": feature,
        "currentStage": "forge-2-tech",
        "pipelineStatus": "active",
        "stages": {"forge-1-prd": {"status": "complete", "version": 1}},
    }
    if branch is not None:
        state["branch"] = branch
    (d / ".pipeline-state.json").write_text(json.dumps(state))


def _reconcile(repo: Path, feature: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(HELPER), "reconcile-branch", "--feature", feature,
         "--specs-dir", "./specs", "--config", "./forge.config.json", "--json"],
        capture_output=True, text=True, cwd=str(repo),
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_adopt_current_when_moved_to_topic_branch(tmp_path: Path) -> None:
    """On a non-default topic branch where the state resolves, adopt the current branch."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "switch", "-c", "epic/real-work")
    _write_state(repo, "widget", branch="claude/imposed-slug")  # stale/imposed record

    out = _reconcile(repo, "widget")
    assert out["action"] == "adopt-current"
    assert out["reconcile"] is True
    assert out["newBranch"] == "epic/real-work"
    assert out["stateBranch"] == "claude/imposed-slug"
    assert out["statePath"].endswith("specs/widget/.pipeline-state.json")


def test_warn_drift_on_default_branch(tmp_path: Path) -> None:
    """On the default branch, a topic-branch record is drift-back — warn, do not adopt."""
    repo = tmp_path / "repo"
    _init_repo(repo)  # stays on main (default)
    _write_state(repo, "widget", branch="forge/widget")

    out = _reconcile(repo, "widget")
    assert out["action"] == "warn-drift"
    assert out["reconcile"] is False
    assert out["defaultBranch"] == "main"


def test_none_when_recorded_matches_current(tmp_path: Path) -> None:
    """Recorded branch already equals the current branch → nothing to do."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "switch", "-c", "forge/widget")
    _write_state(repo, "widget", branch="forge/widget")

    out = _reconcile(repo, "widget")
    assert out["action"] == "none"
    assert out["reconcile"] is False


def test_unrecorded_branch_adopts_current_topic(tmp_path: Path) -> None:
    """No branch recorded yet, on a topic branch where state resolves → adopt-current."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "switch", "-c", "epic/real-work")
    _write_state(repo, "widget", branch=None)

    out = _reconcile(repo, "widget")
    assert out["action"] == "adopt-current"
    assert out["newBranch"] == "epic/real-work"


def test_not_resolved_when_feature_absent(tmp_path: Path) -> None:
    """A feature whose state is not on the current branch cannot be reconciled from here."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "switch", "-c", "epic/real-work")

    out = _reconcile(repo, "ghost")
    assert out["action"] == "not-resolved"
    assert out["reconcile"] is False


def test_non_git_is_safe(tmp_path: Path) -> None:
    """Outside a git repo the reconciler is a no-op, never an error."""
    (tmp_path / "forge.config.json").write_text("{}\n")
    proc = subprocess.run(
        [sys.executable, str(HELPER), "reconcile-branch", "--feature", "widget",
         "--specs-dir", "./specs", "--json"],
        capture_output=True, text=True, cwd=str(tmp_path),
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout)
    assert out["gitRepo"] is False
    assert out["reconcile"] is False
