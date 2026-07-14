"""Tests for ``forge-session.py discover-feature`` — cross-branch state discovery.

Root cause B of the clean-environment failures (docs/clean-env-repro.md): with
``branchPerFeature``, pipeline state lives only on the topic branch, so a
session on the default branch used to conclude the pipeline never existed.
``discover-feature`` closes that hole deterministically and read-only: it scans
local heads + remote-tracking refs, and — when nothing is found locally — asks
``git ls-remote`` about branches a single-branch clone never fetched.
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


def _commit_state(
    repo: Path,
    feature: str,
    state: dict,
    epic: str | None = None,
    specs: str = "specs",
) -> None:
    feature_dir = repo / specs / epic / feature if epic else repo / specs / feature
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / ".pipeline-state.json").write_text(json.dumps(state))
    _git(repo, "add", specs)
    _git(repo, "commit", "-m", f"forge: {feature} state")


def _discover(repo: Path, name: str, *extra: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(HELPER), "discover-feature", name, "--json", *extra],
        capture_output=True,
        text=True,
        cwd=str(repo),
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_discovers_flat_feature_on_topic_branch(tmp_path: Path) -> None:
    """State committed only on forge/<feature> is found from the default branch."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "checkout", "-b", "forge/widget")
    _commit_state(repo, "widget", {
        "feature": "widget",
        "branch": "forge/widget",
        "currentStage": "forge-2-tech",
        "pipelineStatus": "active",
    })
    _git(repo, "checkout", "main")

    payload = _discover(repo, "widget")

    assert payload["gitRepo"] is True
    assert payload["currentBranch"] == "main"
    (cand,) = payload["candidates"]
    assert cand["branch"] == "forge/widget"
    assert cand["path"] == "specs/widget/.pipeline-state.json"
    assert cand["stateBranchMatches"] is True
    assert cand["currentStage"] == "forge-2-tech"
    assert cand["remoteTracking"] is False
    assert cand["switchCommand"] == "git switch forge/widget"
    assert payload["remoteCandidates"] == []


def test_discovers_nested_epic_member(tmp_path: Path) -> None:
    """A nested {specsDir}/{epic}/{feature}/ layout is matched (never deeper)."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "checkout", "-b", "forge/big-epic")
    _commit_state(repo, "member", {"branch": "forge/big-epic"}, epic="big-epic")
    # A decoy at depth 3 must NOT match (feature-shaped-dir bound).
    deep = repo / "specs" / "a" / "b" / "member"
    deep.mkdir(parents=True)
    (deep / ".pipeline-state.json").write_text("{}")
    _git(repo, "add", "specs")
    _git(repo, "commit", "-m", "decoy")
    _git(repo, "checkout", "main")

    payload = _discover(repo, "member")

    (cand,) = payload["candidates"]
    assert cand["path"] == "specs/big-epic/member/.pipeline-state.json"


def test_nested_member_is_flagged_as_epic_member(tmp_path: Path) -> None:
    """A nested member surfaces isEpicMember=true and the epic name (Issue #125)."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "checkout", "-b", "forge/data-enhancement")
    _commit_state(repo, "program-benchmarks",
                  {"branch": "forge/data-enhancement", "epic": "data-enhancement",
                   "currentStage": "forge-1-prd"},
                  epic="data-enhancement")
    _git(repo, "checkout", "main")

    payload = _discover(repo, "program-benchmarks")

    (cand,) = payload["candidates"]
    assert cand["isEpicMember"] is True
    assert cand["epic"] == "data-enhancement"
    assert cand["stateBranch"] == "forge/data-enhancement"


def test_nested_member_without_epic_field_uses_dir_name(tmp_path: Path) -> None:
    """Nested-ness alone flags an epic member even when the state omits `epic`."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "checkout", "-b", "forge/big-epic")
    _commit_state(repo, "member", {"branch": "forge/big-epic"}, epic="big-epic")
    _git(repo, "checkout", "main")

    payload = _discover(repo, "member")

    (cand,) = payload["candidates"]
    assert cand["isEpicMember"] is True
    assert cand["epic"] == "big-epic"  # falls back to the nested dir name


def test_epic_member_discoverable_when_specs_dir_absent(tmp_path: Path) -> None:
    """The clean-branch (exit-2) split-brain trigger: even when the current branch
    has no ``specs/`` tree at all — so ``resolve`` returns ``specs dir not found``
    (exit 2) rather than ``not-found`` (exit 1) — cross-branch discovery still sees
    the epic member on the epic branch. This is what lets the forge-1-prd mint guard
    fire on a default branch that predates the epic (Issue #125 dogfood finding).
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "checkout", "-b", "forge/data-enhancement")
    _commit_state(repo, "program-benchmarks",
                  {"branch": "forge/data-enhancement", "epic": "data-enhancement"},
                  epic="data-enhancement")
    _git(repo, "checkout", "main")
    assert not (repo / "specs").exists()  # no specs tree on this branch at all

    payload = _discover(repo, "program-benchmarks")

    (cand,) = payload["candidates"]
    assert cand["isEpicMember"] is True
    assert cand["epic"] == "data-enhancement"
    assert cand["branch"] == "forge/data-enhancement"


def test_flat_standalone_is_not_an_epic_member(tmp_path: Path) -> None:
    """A flat standalone feature on another branch is isEpicMember=false."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "checkout", "-b", "forge/widget")
    _commit_state(repo, "widget", {"branch": "forge/widget",
                                   "currentStage": "forge-2-tech"})
    _git(repo, "checkout", "main")

    payload = _discover(repo, "widget")

    (cand,) = payload["candidates"]
    assert cand["isEpicMember"] is False
    assert cand["epic"] is None


def test_single_branch_clone_emits_needs_fetch(tmp_path: Path) -> None:
    """A single-branch clone learns the topic branch exists on origin.

    The emitted fetch/switch commands must actually work: running them makes
    the state discoverable as a normal candidate.
    """
    origin = tmp_path / "origin"
    _init_repo(origin)
    _git(origin, "checkout", "-b", "forge/widget")
    _commit_state(origin, "widget", {"branch": "forge/widget",
                                     "currentStage": "forge-3-specs"})
    _git(origin, "checkout", "main")

    clone = tmp_path / "clone"
    subprocess.run(
        ["git", "clone", "--single-branch", "--branch", "main",
         str(origin), str(clone)],
        capture_output=True, text=True, check=True,
    )

    payload = _discover(clone, "widget")

    assert payload["candidates"] == []
    (remote,) = payload["remoteCandidates"]
    assert remote["branch"] == "forge/widget"
    assert remote["needsFetch"] is True

    # The emitted commands are the real recovery path — prove they work.
    fetch = remote["fetchCommand"].split()
    assert fetch[:2] == ["git", "fetch"]
    subprocess.run(fetch, cwd=str(clone), capture_output=True, check=True)
    after = _discover(clone, "widget")
    (cand,) = after["candidates"]
    assert cand["branch"] == "forge/widget"
    assert cand["remoteTracking"] is True
    assert cand["currentStage"] == "forge-3-specs"


def test_non_git_directory_degrades_to_data(tmp_path: Path) -> None:
    """Outside a git repo: exit 0, gitRepo false, no candidates — never a crash."""
    workdir = tmp_path / "plain"
    workdir.mkdir()

    payload = _discover(workdir, "widget")

    assert payload["gitRepo"] is False
    assert payload["candidates"] == []
    assert payload["remoteCandidates"] == []


def test_ranking_prefers_state_branch_match_then_recency(tmp_path: Path) -> None:
    """The branch the state itself records outranks a stray copy of the state.

    A rebase/merge can leave the same feature's state reachable from several
    branches; the one whose name matches the state's own ``branch`` field is
    the real home.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "checkout", "-b", "forge/widget")
    _commit_state(repo, "widget", {"branch": "forge/widget",
                                   "currentStage": "forge-2-tech"})
    # A LATER copy on a differently-named branch (state still says forge/widget).
    _git(repo, "checkout", "-b", "scratch/experiment")
    _commit_state(repo, "widget", {"branch": "forge/widget",
                                   "currentStage": "forge-3-specs"})
    _git(repo, "checkout", "main")

    payload = _discover(repo, "widget")

    branches = [c["branch"] for c in payload["candidates"]]
    assert branches[0] == "forge/widget"  # match beats the newer stray copy
    assert set(branches) == {"forge/widget", "scratch/experiment"}


def test_current_branch_hit_is_flagged(tmp_path: Path) -> None:
    """A hit on the branch we're already on is marked (no switch needed)."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _commit_state(repo, "widget", {"branch": "main"})

    payload = _discover(repo, "widget")

    (cand,) = payload["candidates"]
    assert cand["isCurrentBranch"] is True


def test_custom_specs_dir_and_dot_slash_normalization(tmp_path: Path) -> None:
    """--specs-dir ./docs/specs matches git's repo-relative path form."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "checkout", "-b", "forge/widget")
    _commit_state(repo, "widget", {"branch": "forge/widget"},
                  specs="docs/specs")
    _git(repo, "checkout", "main")

    payload = _discover(repo, "widget", "--specs-dir", "./docs/specs")

    (cand,) = payload["candidates"]
    assert cand["path"] == "docs/specs/widget/.pipeline-state.json"


# ── --all: whole-pipeline discovery for the empty-dashboard case (Chunk 5c) ──


def _discover_all(repo: Path, *extra: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(HELPER), "discover-feature", "--all", "--json", *extra],
        capture_output=True, text=True, cwd=str(repo),
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def test_discover_all_lists_features_across_branches(tmp_path: Path) -> None:
    """--all enumerates every feature whose state lives on any branch."""
    repo = tmp_path / "repo"
    _init_repo(repo)  # default branch: main, no state
    _git(repo, "checkout", "-b", "forge/alpha")
    _commit_state(repo, "alpha", {"feature": "alpha", "branch": "forge/alpha",
                                  "currentStage": "forge-2-tech", "pipelineStatus": "active"})
    _git(repo, "checkout", "main")
    _git(repo, "checkout", "-b", "forge/beta")
    _commit_state(repo, "beta", {"feature": "beta", "branch": "forge/beta",
                                 "currentStage": "forge-1-prd", "pipelineStatus": "active"})
    _git(repo, "checkout", "main")  # a fresh default-branch session sees nothing on disk

    payload = _discover_all(repo)
    features = {f["feature"] for f in payload["features"]}
    assert features == {"alpha", "beta"}
    alpha = next(f for f in payload["features"] if f["feature"] == "alpha")
    assert alpha["candidates"][0]["branch"] == "forge/alpha"


def test_discover_all_empty_when_no_state(tmp_path: Path) -> None:
    """--all on a repo with no pipeline state reports an empty feature list, exit 0."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    payload = _discover_all(repo)
    assert payload["gitRepo"] is True
    assert payload["features"] == []
