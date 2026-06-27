"""Tests for scripts/forge-root.sh — the portable skill/plugin-root resolver.

Drives ``bash forge-root.sh`` as a subprocess and asserts the four resolution
cases of 03-portable-root-resolver.md §2 / 06-testing-strategy.md §3:

    (a) self-location success (step 1)
    (b) total failure (step 4)
    (c) env fallback (step 3)
    (d) candidate-root probe (step 2)

Cases (b), (c), and (d) MUST run with a redirected ``HOME`` and an empty
``CLAUDE_PLUGIN_ROOT`` so the maintainer's live ``~/.claude/skills/feature-forge``
dev symlink (this repo self-hosts) cannot leak into the step-2 probe and
false-pass.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
RESOLVER = REPO_ROOT / "scripts" / "forge-root.sh"

FAILURE_MESSAGE = (
    "feature-forge: cannot locate install root. "
    "Set FEATURE_FORGE_ROOT to the bundle dir, or run from an installed skill dir."
)


def _make_fake_install(root: Path) -> Path:
    """Create a sentinel-bearing fake install with forge-root.sh in place.

    Writes both SENTINEL_FILES (scripts/epic-manifest.py and
    .claude-plugin/plugin.json) and copies the real resolver to
    ``root/scripts/forge-root.sh``.

    Args:
        root: Directory to populate as a valid plugin root.

    Returns:
        The populated root.
    """
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / ".claude-plugin").mkdir(parents=True, exist_ok=True)
    (root / "scripts" / "epic-manifest.py").write_text("# sentinel\n")
    (root / ".claude-plugin" / "plugin.json").write_text("{}\n")
    (root / "scripts" / "forge-root.sh").write_text(RESOLVER.read_text())
    return root


def _run(script: Path, env_overrides: dict[str, str]) -> subprocess.CompletedProcess[str]:
    """Run ``bash <script>`` with the given environment overrides."""
    return subprocess.run(
        ["bash", str(script)],
        capture_output=True,
        text=True,
        env={**os.environ, **env_overrides},
    )


def test_forge_root_self_location(tmp_path):
    """(a) Invoked from inside a tree with the sentinel pair → step 1 wins."""
    root = _make_fake_install(tmp_path / "install")
    result = _run(root / "scripts" / "forge-root.sh", {"CLAUDE_PLUGIN_ROOT": ""})
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(root.resolve())


def test_forge_root_fails_actionably(tmp_path):
    """(b) No discoverable root and CLAUDE_PLUGIN_ROOT unset → step 4."""
    lone_dir = tmp_path / "lone" / "scripts"
    lone_dir.mkdir(parents=True)
    lone = lone_dir / "forge-root.sh"
    lone.write_text(RESOLVER.read_text())
    result = _run(
        lone,
        {"HOME": str(tmp_path / "empty-home"), "CLAUDE_PLUGIN_ROOT": ""},
    )
    assert result.returncode == 1
    assert result.stderr.strip() == FAILURE_MESSAGE


def test_forge_root_env_fallback(tmp_path):
    """(c) Self/candidate probes fail but CLAUDE_PLUGIN_ROOT names a valid root → step 3."""
    # A valid root, but the resolver is invoked from a lone copy so step 1 fails.
    valid_root = _make_fake_install(tmp_path / "valid")
    lone_dir = tmp_path / "lone" / "scripts"
    lone_dir.mkdir(parents=True)
    lone = lone_dir / "forge-root.sh"
    lone.write_text(RESOLVER.read_text())
    result = _run(
        lone,
        {
            "HOME": str(tmp_path / "empty-home"),
            "CLAUDE_PLUGIN_ROOT": str(valid_root),
        },
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(valid_root)


def test_forge_root_candidate_probe(tmp_path):
    """(d) Self-location fails, but a HOME-redirected candidate root exists → step 2."""
    home = tmp_path / "home"
    candidate = home / ".claude" / "skills" / "feature-forge"
    _make_fake_install(candidate)
    # Invoke from a lone copy outside any root so step 1 cannot succeed.
    lone_dir = tmp_path / "lone" / "scripts"
    lone_dir.mkdir(parents=True)
    lone = lone_dir / "forge-root.sh"
    lone.write_text(RESOLVER.read_text())
    result = _run(
        lone,
        {"HOME": str(home), "CLAUDE_PLUGIN_ROOT": ""},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(candidate)


def test_forge_root_neutral_sentinel_self_location(tmp_path):
    """A bundle carrying ONLY the neutral .feature-forge-bundle.json self-locates (no plugin.json).

    This is the cross-agent path: non-Claude bundles have no .claude-plugin/plugin.json, so
    is_root() must accept the neutral sentinel alone (step 1).
    """
    root = tmp_path / "bundle"
    (root / "scripts").mkdir(parents=True)
    (root / ".feature-forge-bundle.json").write_text('{"name":"feature-forge"}\n')
    (root / "scripts" / "forge-root.sh").write_text(RESOLVER.read_text())
    result = _run(
        root / "scripts" / "forge-root.sh",
        {"HOME": str(tmp_path / "empty-home"), "CLAUDE_PLUGIN_ROOT": "", "FEATURE_FORGE_ROOT": ""},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(root.resolve())


import pytest


@pytest.mark.parametrize(
    "rel",
    [
        ".claude/skills/feature-forge",
        ".agents/skills/feature-forge",
        ".github/feature-forge",
        ".cursor/rules/feature-forge",
        ".gemini/extensions/feature-forge",
    ],
)
def test_forge_root_project_scope_candidate_probe(tmp_path, rel):
    """Step 2 resolves a PROJECT-scope ($PWD) install for every supported agent layout (A6).

    Guards the per-agent first-use path: a helper invoked from a project root must locate a
    project-scoped bundle wherever that agent loads it (codex .agents/skills, copilot
    .github/feature-forge, cursor .cursor/rules, gemini .gemini/extensions, claude .claude/skills).
    """
    project = tmp_path / "project"
    candidate = project / rel
    _make_fake_install(candidate)
    # A lone resolver copy outside any root so step 1 (self-location) cannot succeed.
    lone_dir = tmp_path / "lone" / "scripts"
    lone_dir.mkdir(parents=True)
    lone = lone_dir / "forge-root.sh"
    lone.write_text(RESOLVER.read_text())
    result = subprocess.run(
        ["bash", str(lone)],
        capture_output=True,
        text=True,
        cwd=str(project),  # sets $PWD for the project-scope probe
        env={**os.environ, "HOME": str(tmp_path / "empty-home"), "CLAUDE_PLUGIN_ROOT": "", "FEATURE_FORGE_ROOT": ""},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(candidate)


def test_forge_root_neutral_env_fallback(tmp_path):
    """FEATURE_FORGE_ROOT names a valid root when self/candidate probes fail → step 3 (neutral)."""
    valid_root = _make_fake_install(tmp_path / "valid")
    lone_dir = tmp_path / "lone" / "scripts"
    lone_dir.mkdir(parents=True)
    lone = lone_dir / "forge-root.sh"
    lone.write_text(RESOLVER.read_text())
    result = _run(
        lone,
        {
            "HOME": str(tmp_path / "empty-home"),
            "CLAUDE_PLUGIN_ROOT": "",
            "FEATURE_FORGE_ROOT": str(valid_root),
        },
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(valid_root)
