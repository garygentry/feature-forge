"""Regression anchors for the clean-environment failures (docs/clean-env-repro.md).

Regression tests pinning the smoking guns diagnosed after the remote-environment
pipeline test. Each starts life as an ``xfail(strict=True)`` encoding the
*desired* behavior; the PR that fixes a case removes its marker:

1. ``test_prelude_resolves_marketplace_cache_install`` — the canonical
   bootstrap prelude must resolve a real Claude marketplace install at
   ``~/.claude/plugins/cache/<marketplace>/feature-forge/<version>/``.
   FIXED (marker removed) by the root-resolution chunk: cache glob in the
   prelude + newest-plugin.json-first cache probe in forge-root.sh.
2. ``test_discover_feature_finds_state_on_other_branch`` — pipeline state that
   lives only on a topic branch must be discoverable from the default branch
   via ``forge-session.py discover-feature``. FIXED (marker removed) by the
   discover-feature chunk; full coverage in ``test_discover_feature.py``.

The prelude is imported from ``scripts/check-spec-purity.py`` (the byte-pinned
canon), so the fix to the constant is automatically what these tests exercise —
no copy of the prelude to drift.

``strict=True`` means an unexpected pass fails the suite: whichever PR fixes a
case MUST also remove its xfail marker, keeping the anchors honest.
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESOLVER = REPO_ROOT / "scripts" / "forge-root.sh"
SESSION_HELPER = REPO_ROOT / "scripts" / "forge-session.py"
PURITY_CHECKER = REPO_ROOT / "scripts" / "check-spec-purity.py"


def _bootstrap_prelude() -> str:
    """Import the canonical BOOTSTRAP_PRELUDE from check-spec-purity.py."""
    spec = importlib.util.spec_from_file_location("check_spec_purity", PURITY_CHECKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec: 3.10 dataclasses resolve annotations through
    # sys.modules[cls.__module__], which is None for an unregistered module.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.BOOTSTRAP_PRELUDE


def _make_cache_install(home: Path, version: str = "9.9.9") -> Path:
    """Fabricate a marketplace-cache install under a redirected ``$HOME``.

    Mirrors the layout Claude Code actually writes for a marketplace plugin:
    ``~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`` (three levels
    below ``plugins/`` — the layout the original candidate globs miss).
    """
    root = home / ".claude" / "plugins" / "cache" / "test-mp" / "feature-forge" / version
    (root / "scripts").mkdir(parents=True)
    (root / ".claude-plugin").mkdir()
    (root / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "feature-forge", "version": version}) + "\n"
    )
    resolver_copy = root / "scripts" / "forge-root.sh"
    shutil.copy(RESOLVER, resolver_copy)
    resolver_copy.chmod(resolver_copy.stat().st_mode | stat.S_IXUSR)
    return root


def _make_install_at(dirpath: Path) -> Path:
    """Fabricate a minimal valid bundle (a runnable forge-root.sh + manifest) at ``dirpath``."""
    (dirpath / "scripts").mkdir(parents=True)
    (dirpath / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (dirpath / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "feature-forge", "version": "9.9.9"}) + "\n"
    )
    resolver_copy = dirpath / "scripts" / "forge-root.sh"
    shutil.copy(RESOLVER, resolver_copy)
    resolver_copy.chmod(resolver_copy.stat().st_mode | stat.S_IXUSR)
    return dirpath


def _run_prelude(home: Path, workdir: Path, *, hint: str) -> subprocess.CompletedProcess[str]:
    """Run the byte-pinned bootstrap prelude with ``$HOME``/``CLAUDE_PLUGIN_ROOT`` controlled."""
    script = _bootstrap_prelude() + '\nprintf \'%s\\n\' "$R"'
    return subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        cwd=str(workdir),
        env={**os.environ, "HOME": str(home), "CLAUDE_PLUGIN_ROOT": hint, "FEATURE_FORGE_ROOT": ""},
    )


def test_prelude_first_hint_resolves_via_claude_plugin_root(tmp_path: Path) -> None:
    """The `${CLAUDE_PLUGIN_ROOT:-}` first-hint resolves a bundle NO glob can reach (Chunk 2b).

    The bundle lives outside ``$HOME`` (unreachable by every ``$HOME``/``./`` candidate),
    and ``$HOME`` holds no install — so the prelude can only find ``forge-root.sh`` via
    the hint. Proves the hint is honored as the first candidate on any Claude layout.
    """
    bundle = _make_install_at(tmp_path / "opt" / "feature-forge")
    home = tmp_path / "home"
    home.mkdir()  # deliberately empty — no install reachable by the globs
    workdir = tmp_path / "project"
    workdir.mkdir()

    result = _run_prelude(home, workdir, hint=str(bundle))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(bundle)


def test_prelude_stale_hint_is_skipped(tmp_path: Path) -> None:
    """A hint pointing at a dir without ``forge-root.sh`` is skipped; resolution falls through.

    ``CLAUDE_PLUGIN_ROOT`` names a stale dir (no ``scripts/forge-root.sh``); the only real
    install is the marketplace cache under ``$HOME``. The prelude must skip the dead hint
    and resolve the cache install — the additive hint never breaks existing resolution.
    """
    home = tmp_path / "home"
    install_root = _make_cache_install(home)
    stale = tmp_path / "stale"
    stale.mkdir()  # exists but carries no scripts/forge-root.sh
    workdir = tmp_path / "project"
    workdir.mkdir()

    result = _run_prelude(home, workdir, hint=str(stale))

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(install_root)


def test_prelude_resolves_marketplace_cache_install(tmp_path: Path) -> None:
    """The canonical prelude resolves a marketplace-cache install.

    Runs the byte-pinned bootstrap prelude with ``$HOME`` redirected to a tree
    whose ONLY feature-forge install sits at the real marketplace-cache path.
    The prelude must exec that install's ``forge-root.sh`` and print the
    version-dir root.
    """
    home = tmp_path / "home"
    install_root = _make_cache_install(home)
    workdir = tmp_path / "project"
    workdir.mkdir()

    script = _bootstrap_prelude() + '\nprintf \'%s\\n\' "$R"'
    result = subprocess.run(
        ["bash", "-c", script],
        capture_output=True,
        text=True,
        cwd=str(workdir),
        env={
            **os.environ,
            "HOME": str(home),
            "CLAUDE_PLUGIN_ROOT": "",
            "FEATURE_FORGE_ROOT": "",
        },
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(install_root)


def _git(repo: Path, *args: str) -> None:
    """Run a git command in ``repo``, asserting success."""
    proc = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True
    )
    assert proc.returncode == 0, proc.stderr


def test_discover_feature_finds_state_on_other_branch(tmp_path: Path) -> None:
    """State committed only on a topic branch is discoverable from default.

    With ``branchPerFeature`` workflows, ``specs/<feature>/.pipeline-state.json``
    exists only on ``forge/<feature>``. A session on the default branch must be
    able to learn that the pipeline exists (branch + recorded stage) instead of
    falling back to "start with forge-1-prd".
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("# scratch\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")

    _git(repo, "checkout", "-b", "forge/widget")
    state_dir = repo / "specs" / "widget"
    state_dir.mkdir(parents=True)
    (state_dir / ".pipeline-state.json").write_text(
        json.dumps(
            {
                "feature": "widget",
                "branch": "forge/widget",
                "currentStage": "forge-2-tech",
                "pipelineStatus": "active",
                "stages": {"forge-1-prd": {"status": "complete", "version": 1}},
            }
        )
    )
    _git(repo, "add", "specs")
    _git(repo, "commit", "-m", "forge: widget prd state")
    _git(repo, "checkout", "main")
    assert not (repo / "specs").exists()  # invisible from the default branch

    result = subprocess.run(
        [
            sys.executable,
            str(SESSION_HELPER),
            "discover-feature",
            "widget",
            "--specs-dir",
            "specs",
            "--json",
        ],
        capture_output=True,
        text=True,
        cwd=str(repo),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    candidates = payload.get("candidates", [])
    assert any(c.get("branch") == "forge/widget" for c in candidates)


def test_discover_feature_flags_epic_member_across_branches(tmp_path: Path) -> None:
    """The split-brain-epic signal (Issue #125): from a branch that lacks the epic
    manifest, ``discover-feature <member>`` surfaces the member's nested stub on the
    epic branch as ``isEpicMember: true`` — the exact signal the forge-1-prd mint
    guard keys off to refuse forging the member as a detached standalone feature.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-b", "main")
    _git(repo, "config", "user.email", "test@example.invalid")
    _git(repo, "config", "user.name", "Test")
    (repo / "README.md").write_text("# scratch\n")
    _git(repo, "add", "README.md")
    _git(repo, "commit", "-m", "init")

    # The epic branch: nested member stub + epic manifest (the manifest commit).
    _git(repo, "checkout", "-b", "forge/data-enhancement")
    member = repo / "specs" / "data-enhancement" / "program-benchmarks"
    member.mkdir(parents=True)
    (member / ".pipeline-state.json").write_text(
        json.dumps({"feature": "program-benchmarks", "epic": "data-enhancement",
                    "branch": "forge/data-enhancement", "currentStage": "forge-1-prd"})
    )
    (repo / "specs" / "data-enhancement" / "epic-manifest.json").write_text(
        json.dumps({"epic": "data-enhancement", "features": [{"name": "program-benchmarks"}]})
    )
    _git(repo, "add", "specs")
    _git(repo, "commit", "-m", "forge: data-enhancement epic + member stub")

    # A session on the default branch (cut from before the manifest) sees nothing
    # on disk — yet discovery must reveal the member membership across branches.
    _git(repo, "checkout", "main")
    assert not (repo / "specs").exists()

    result = subprocess.run(
        [sys.executable, str(SESSION_HELPER), "discover-feature",
         "program-benchmarks", "--specs-dir", "specs", "--json"],
        capture_output=True, text=True, cwd=str(repo),
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    (cand,) = payload["candidates"]
    assert cand["isEpicMember"] is True
    assert cand["epic"] == "data-enhancement"
    assert cand["stateBranch"] == "forge/data-enhancement"
