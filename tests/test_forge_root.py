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


# Core assets a COMPLETE install must carry beyond the sentinel — mirrors CORE_ASSETS in
# forge-root.sh (#152). A resolved root missing any of these is reported as degraded.
_CORE_ASSETS = (
    "scripts/forge-session.py",
    "references/pipeline-state-schema.json",
    "references/stage-exit-protocol.md",
)


def _make_fake_install(root: Path) -> Path:
    """Create a sentinel-bearing, COMPLETE fake install with forge-root.sh in place.

    Writes both SENTINEL_FILES (scripts/epic-manifest.py and
    .claude-plugin/plugin.json), the core assets the completeness gate checks
    (``_CORE_ASSETS``), and copies the real resolver to
    ``root/scripts/forge-root.sh`` — so the resolver treats it as whole (#152).

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
    for rel in _CORE_ASSETS:
        asset = root / rel
        asset.parent.mkdir(parents=True, exist_ok=True)
        asset.write_text("# core-asset sentinel\n")
    return root


def _make_partial_install(root: Path, omit: str = "references/pipeline-state-schema.json") -> Path:
    """Create a sentinel-bearing but ASSET-INCOMPLETE install (a stale/partial extraction).

    Populates a full install, then deletes one core asset so the completeness gate
    classifies it as degraded (#152).

    Args:
        root: Directory to populate.
        omit: The core-asset relative path to leave missing.

    Returns:
        The populated (partial) root.
    """
    _make_fake_install(root)
    (root / omit).unlink()
    return root


def _make_neutral_install(root: Path) -> Path:
    """A COMPLETE install carrying ONLY the neutral sentinel (no .claude-plugin/plugin.json).

    Exercises the cross-agent is_root() path while still satisfying the completeness gate.
    """
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / ".feature-forge-bundle.json").write_text('{"name":"feature-forge"}\n')
    (root / "scripts" / "forge-root.sh").write_text(RESOLVER.read_text())
    for rel in _CORE_ASSETS:
        asset = root / rel
        asset.parent.mkdir(parents=True, exist_ok=True)
        asset.write_text("# core-asset sentinel\n")
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
    root = _make_neutral_install(tmp_path / "bundle")
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
        ".pi/skills/feature-forge",
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


def test_forge_root_pi_coding_agent_dir_candidate_probe(tmp_path):
    """Step 2 resolves the isolated Pi config root used for dogfood.

    Pi sessions can set PI_CODING_AGENT_DIR instead of using ~/.pi/agent, so the resolver must
    treat ${PI_CODING_AGENT_DIR}/skills/feature-forge as a first-class install root.
    """
    pi_dir = tmp_path / "pi-agent-dogfood"
    candidate = _make_fake_install(pi_dir / "skills" / "feature-forge")
    result = _run(
        _lone_resolver(tmp_path),
        {
            "HOME": str(tmp_path / "empty-home"),
            "CLAUDE_PLUGIN_ROOT": "",
            "FEATURE_FORGE_ROOT": "",
            "PI_CODING_AGENT_DIR": str(pi_dir),
        },
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(candidate)


def test_forge_root_pi_project_ancestor_candidate_probe(tmp_path):
    """Step 2 resolves project .pi/skills when invoked from a nested project directory."""
    project = tmp_path / "project"
    candidate = _make_fake_install(project / ".pi" / "skills" / "feature-forge")
    nested = project / "src" / "pkg"
    nested.mkdir(parents=True)
    result = subprocess.run(
        ["bash", str(_lone_resolver(tmp_path))],
        capture_output=True,
        text=True,
        cwd=str(nested),
        env={**os.environ, "HOME": str(tmp_path / "empty-home"), "CLAUDE_PLUGIN_ROOT": "", "FEATURE_FORGE_ROOT": ""},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(candidate)


def test_forge_root_pi_package_cache_candidate_probe(tmp_path):
    """Step 2 resolves a Pi package clone/cache root when it contains adapters/pi."""
    home = tmp_path / "home"
    candidate = _make_fake_install(home / ".pi" / "agent" / "git" / "github.com" / "feature-forge" / "adapters" / "pi")
    result = _run(
        _lone_resolver(tmp_path),
        {"HOME": str(home), "CLAUDE_PLUGIN_ROOT": "", "FEATURE_FORGE_ROOT": ""},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(candidate)


def _make_cache_install(home: Path, version: str) -> Path:
    """Create a marketplace-cache install: plugins/cache/<mp>/feature-forge/<version>/."""
    root = home / ".claude" / "plugins" / "cache" / "test-mp" / "feature-forge" / version
    return _make_fake_install(root)


def _lone_resolver(tmp_path: Path) -> Path:
    """Copy the resolver somewhere outside any root so step 1 cannot succeed."""
    lone_dir = tmp_path / "lone" / "scripts"
    lone_dir.mkdir(parents=True, exist_ok=True)
    lone = lone_dir / "forge-root.sh"
    lone.write_text(RESOLVER.read_text())
    return lone


def test_forge_root_marketplace_cache_probe(tmp_path):
    """Step 2a resolves a real marketplace-cache install (clean-env root cause A).

    Claude Code installs marketplace plugins at
    ``~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/`` — three path
    segments below ``plugins/``, unreachable by the single-star
    ``plugins/*/feature-forge`` glob.
    """
    home = tmp_path / "home"
    install = _make_cache_install(home, "1.2.3")
    result = _run(
        _lone_resolver(tmp_path),
        {"HOME": str(home), "CLAUDE_PLUGIN_ROOT": "", "FEATURE_FORGE_ROOT": ""},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(install)


def test_forge_root_cache_install_beats_marketplace_clone(tmp_path):
    """The versioned cache install wins over the marketplace clone (version skew).

    A marketplace whose repo root is itself a plugin root gets cloned to
    ``~/.claude/plugins/marketplaces/<mp>/`` — which the single-star glob CAN
    match — but the clone may sit at a different commit than the installed
    skills. The cache install must be probed first.
    """
    home = tmp_path / "home"
    install = _make_cache_install(home, "1.2.3")
    clone = home / ".claude" / "plugins" / "marketplaces" / "feature-forge"
    _make_fake_install(clone)
    result = _run(
        _lone_resolver(tmp_path),
        {"HOME": str(home), "CLAUDE_PLUGIN_ROOT": "", "FEATURE_FORGE_ROOT": ""},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(install)


def test_forge_root_cache_version_tiebreak_newest_manifest_wins(tmp_path):
    """Coexisting version dirs resolve to the newest plugin.json by mtime.

    After an upgrade, old version dirs can linger. Lexicographic glob order
    would pick ``10.0.0`` over ``9.0.0`` wrongly (or vice versa); the probe
    must key on plugin.json mtime — the newest write is the current install.
    """
    home = tmp_path / "home"
    old_install = _make_cache_install(home, "10.0.0")
    new_install = _make_cache_install(home, "9.0.0")  # lexicographically LATER dir
    old_manifest = old_install / ".claude-plugin" / "plugin.json"
    new_manifest = new_install / ".claude-plugin" / "plugin.json"
    past = 1_600_000_000  # fixed epoch seconds, comfortably in the past
    os.utime(old_manifest, (past, past))
    os.utime(new_manifest, (past + 1000, past + 1000))
    result = _run(
        _lone_resolver(tmp_path),
        {"HOME": str(home), "CLAUDE_PLUGIN_ROOT": "", "FEATURE_FORGE_ROOT": ""},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(new_install)


def test_forge_root_sentinel_only_cache_install_resolves(tmp_path):
    """A cache install carrying only the neutral bundle sentinel still resolves.

    Step 2a keys on plugin.json for mtime ordering; the step 2 glob repeat
    covers a cache-layout bundle that only has .feature-forge-bundle.json.
    """
    home = tmp_path / "home"
    root = home / ".claude" / "plugins" / "cache" / "test-mp" / "feature-forge" / "2.0.0"
    _make_neutral_install(root)
    result = _run(
        _lone_resolver(tmp_path),
        {"HOME": str(home), "CLAUDE_PLUGIN_ROOT": "", "FEATURE_FORGE_ROOT": ""},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(root)


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


# ---------------------------------------------------------------------------
# Completeness gate — degraded / partial install detection (#152)
# ---------------------------------------------------------------------------


def test_forge_root_partial_install_reports_degraded(tmp_path):
    """A sentinel-bearing root missing a core asset fails LOUDLY, not silently degraded (#152).

    Mirrors the reported stale/partial install: the skill dir + sentinel are present but the
    shared references the skills load are absent. Instead of handing back a usable-looking
    root that then runs off-script, the resolver reports the degraded install + which asset is
    missing + how to fix it, and exits 1.
    """
    partial = _make_partial_install(
        tmp_path / "install", omit="references/pipeline-state-schema.json"
    )
    result = _run(
        partial / "scripts" / "forge-root.sh",
        {"HOME": str(tmp_path / "empty-home"), "CLAUDE_PLUGIN_ROOT": "", "FEATURE_FORGE_ROOT": ""},
    )
    assert result.returncode == 1
    assert "incomplete/degraded" in result.stderr
    assert str(partial.resolve()) in result.stderr
    assert "references/pipeline-state-schema.json" in result.stderr
    # Not the generic cannot-locate message — this is a distinct, actionable failure.
    assert "cannot locate install root" not in result.stderr
    # Nothing is printed to stdout (no root handed back).
    assert result.stdout.strip() == ""


def test_forge_root_complete_root_wins_over_partial(tmp_path):
    """A partial root earlier in the probe order does not shadow a complete root found later.

    Self-location hits a partial install (remembered, not accepted); the resolver keeps
    probing and resolves the complete root named by FEATURE_FORGE_ROOT (step 3) → exit 0.
    """
    partial = _make_partial_install(tmp_path / "partial")
    complete = _make_fake_install(tmp_path / "complete")
    result = _run(
        partial / "scripts" / "forge-root.sh",
        {
            "HOME": str(tmp_path / "empty-home"),
            "CLAUDE_PLUGIN_ROOT": "",
            "FEATURE_FORGE_ROOT": str(complete),
        },
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(complete)
