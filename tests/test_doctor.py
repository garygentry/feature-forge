"""Tests for ``forge-session.py doctor`` — the ground-truth diagnostic.

Doctor is the one command a confused or half-broken environment runs to
capture what is actually true on disk: resolved plugin root, current vs.
recorded branch, feature summary, backlog-path existence. Its contract is
therefore "always exits 0, failures are data" — pinned here.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER = REPO_ROOT / "scripts" / "forge-session.py"


def _write_state(specs_dir: Path, name: str, state: dict, epic: str | None = None) -> None:
    feature = specs_dir / epic / name if epic else specs_dir / name
    feature.mkdir(parents=True, exist_ok=True)
    (feature / ".pipeline-state.json").write_text(json.dumps(state))


def _doctor(cwd: Path, helper: Path = HELPER, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(helper), "doctor", "--json", *extra],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )


def test_doctor_happy_path(tmp_path: Path) -> None:
    """A populated project yields a full report: root, branch, features, backlog."""
    specs = tmp_path / "specs"
    _write_state(specs, "widget", {
        "pipelineStatus": "active",
        "branch": "forge/widget",
        "updatedAt": "2026-07-01T00:00:00Z",
        "stages": {"forge-1-prd": {"status": "complete", "version": 1}},
    })
    (tmp_path / "forge.config.json").write_text("{}")
    (specs / "widget" / "backlog.json").write_text("[]")
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, capture_output=True)

    result = _doctor(tmp_path)

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    # The helper runs from the repo checkout, whose sibling forge-root.sh
    # self-locates the repo root — doctor reports the install it belongs to.
    assert report["pluginRoot"]["resolved"] is True
    assert report["pluginRoot"]["root"] == str(REPO_ROOT)
    assert report["currentBranch"] == "main"
    assert report["specsDirExists"] is True
    assert report["configExists"] is True
    (feat,) = report["features"]
    assert feat["name"] == "widget"
    assert feat["stateBranch"] == "forge/widget"
    assert feat["branchMatchesState"] is False  # on main, state says forge/widget
    assert feat["backlogExists"] is True
    assert feat["backlogPath"] == "specs/widget/backlog.json"


def test_doctor_composes_configured_backlog_dir(tmp_path: Path) -> None:
    """With ``backlogDir`` configured, the per-feature subpath rule applies."""
    specs = tmp_path / "specs"
    _write_state(specs, "widget", {"pipelineStatus": "active"})
    (tmp_path / "forge.config.json").write_text(json.dumps({"backlogDir": "bl"}))

    result = _doctor(tmp_path)

    assert result.returncode == 0, result.stderr
    (feat,) = json.loads(result.stdout)["features"]
    assert feat["backlogPath"] == "bl/widget/backlog.json"
    assert feat["backlogExists"] is False


def test_doctor_nested_epic_member_backlog_path(tmp_path: Path) -> None:
    """A nested epic member's default backlog path stays under the epic dir."""
    specs = tmp_path / "specs"
    _write_state(specs, "member", {"pipelineStatus": "active"}, epic="big-epic")
    (tmp_path / "forge.config.json").write_text("{}")

    result = _doctor(tmp_path)

    assert result.returncode == 0, result.stderr
    (feat,) = json.loads(result.stdout)["features"]
    assert feat["epic"] == "big-epic"
    assert feat["backlogPath"] == "specs/big-epic/member/backlog.json"


def test_doctor_survives_unresolvable_root_and_bare_dir(tmp_path: Path) -> None:
    """No git, no specs, no config, unresolvable root → still exit 0 with data.

    A lone copy of the helper pair (forge-session.py + forge-root.sh) outside
    any install, with ``$HOME`` redirected, cannot resolve a plugin root —
    doctor must report that as data, not crash.
    """
    scripts = tmp_path / "lone" / "scripts"
    scripts.mkdir(parents=True)
    shutil.copy(HELPER, scripts / "forge-session.py")
    shutil.copy(REPO_ROOT / "scripts" / "forge-root.sh", scripts / "forge-root.sh")
    workdir = tmp_path / "empty-project"
    workdir.mkdir()

    result = subprocess.run(
        [sys.executable, str(scripts / "forge-session.py"), "doctor", "--json"],
        capture_output=True,
        text=True,
        cwd=str(workdir),
        env={
            "HOME": str(tmp_path / "empty-home"),
            "PATH": subprocess.os.environ["PATH"],
            "CLAUDE_PLUGIN_ROOT": "",
            "FEATURE_FORGE_ROOT": "",
        },
    )

    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["pluginRoot"]["resolved"] is False
    assert "error" in report["pluginRoot"]
    assert report["currentBranch"] is None
    assert report["specsDirExists"] is False
    assert report["configExists"] is False
    assert report["features"] == []


def test_doctor_human_output_mentions_root_and_features(tmp_path: Path) -> None:
    """The human-readable form prints the root line and per-feature rows."""
    specs = tmp_path / "specs"
    _write_state(specs, "widget", {"pipelineStatus": "active"})
    (tmp_path / "forge.config.json").write_text("{}")

    result = subprocess.run(
        [sys.executable, str(HELPER), "doctor"],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert result.returncode == 0, result.stderr
    assert "plugin root:" in result.stdout
    assert "widget" in result.stdout
    assert "backlog=MISSING" in result.stdout
