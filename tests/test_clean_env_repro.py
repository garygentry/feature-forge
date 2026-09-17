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

3. ``test_marketplace_channel_resolves_cited_shared_references_skill_local`` — the
   distributed Claude channel (``marketplace.json`` ``plugins[0].source``) must let every
   skill resolve the shared ``references/X`` it cites SKILL-LOCAL, since a bare prose read
   resolves relative to ``skills/<name>/``, not the plugin root (#122/#305). ``source: "."``
   ships CANON (shared refs only at the repo-root ``references/``), so it fails today; #314's
   root fix (point ``source`` at ``./adapters/claude``, or fan shared refs into canon) flips
   it to pass and its marker comes off then.

``strict=True`` means an unexpected pass fails the suite: whichever PR fixes a
case MUST also remove its xfail marker, keeping the anchors honest.
"""

from __future__ import annotations

import importlib.util
import json
import re
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
RESOLVER = REPO_ROOT / "scripts" / "forge-root.sh"
SESSION_HELPER = REPO_ROOT / "scripts" / "forge-session.py"
PURITY_CHECKER = REPO_ROOT / "scripts" / "check-spec-purity.py"

# Core assets a complete install must carry beyond the sentinel — mirrors CORE_ASSETS in
# forge-root.sh (#152). Fabricated bundles must include them or the completeness gate treats
# them as degraded and the prelude refuses to resolve.
_CORE_ASSETS = (
    "scripts/forge-session.py",
    "references/pipeline-state-schema.json",
    "references/stage-exit-protocol.md",
)


def _write_core_assets(root: Path) -> None:
    """Write placeholder core assets so ``root`` passes forge-root.sh's completeness gate."""
    for rel in _CORE_ASSETS:
        asset = root / rel
        asset.parent.mkdir(parents=True, exist_ok=True)
        asset.write_text("# core-asset sentinel\n")


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
    _write_core_assets(root)
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
    _write_core_assets(dirpath)
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


# whole-dir-fanned shared reference roots (mirror _WHOLE_DIR_FANNED_REFERENCE_ROOTS in
# build-adapters.py): a citation anywhere inside fans the ENTIRE tree, so the tree — not the
# individual file — is what must resolve skill-local.
_WHOLE_DIR_FANNED_ROOTS = frozenset({"stacks", "verifier-patterns"})

#: Mirror of _REFERENCE_CITATION_RE in build-adapters.py — a bare ``references/X`` citation.
_REFERENCE_CITATION_RE = re.compile(r"references/([A-Za-z0-9_][A-Za-z0-9_./{}*-]*)")


def _skill_body(text: str) -> str:
    """The SKILL.md body after the YAML frontmatter. ``_fan_out_shared_references`` scans
    ``skill.body`` only, so the mirror must too — a citation in frontmatter is never fanned."""
    match = re.match(r"^---\n.*?\n---\n", text, re.S)
    return text[match.end():] if match else text


@pytest.mark.xfail(
    strict=True,
    reason=(
        "#314: marketplace.json plugins[0].source='.' distributes CANON, whose skills carry no "
        "skill-local copy of the shared references they cite; a bare prose `Read references/X` "
        "then dead-references skill-local. Flips to pass when the root fix points source at "
        "./adapters/claude (which fans the shared refs skill-local) or fans them into canon."
    ),
)
def test_marketplace_channel_resolves_cited_shared_references_skill_local() -> None:
    """Every shared reference a skill cites must resolve SKILL-LOCAL on the *distributed* Claude
    channel — the plugin dir Claude installs from ``marketplace.json`` ``plugins[0].source``.

    A bare prose ``Read references/X`` resolves relative to ``skills/<name>/``, not the plugin
    root (#122/#305), so a shared ref that lives only at the plugin-root ``references/`` (as in
    canon) is unreadable from a skill. The built ``adapters/claude`` bundle fans every cited
    shared ref skill-local; ``source: "."`` ships canon and does not — hence the failure this
    anchor pins until the root fix lands.
    """
    marketplace = json.loads((REPO_ROOT / ".claude-plugin" / "marketplace.json").read_text())
    # Select the feature-forge plugin by name, not by index — the manifest could grow or reorder.
    source = next(p for p in marketplace["plugins"] if p["name"] == "feature-forge")["source"]
    plugin_dir = (REPO_ROOT / source).resolve()
    refs_root = plugin_dir / "references"

    missing: set[str] = set()
    for skill_md in sorted((plugin_dir / "skills").glob("*/SKILL.md")):
        skill_dir = skill_md.parent
        for cited in sorted(set(_REFERENCE_CITATION_RE.findall(_skill_body(skill_md.read_text())))):
            head = cited.split("/", 1)[0]
            if head in _WHOLE_DIR_FANNED_ROOTS:
                # A whole-dir root must exist skill-local as a directory when the plugin root
                # carries it (a bundle-root shared tree the skill cites). Keyed on the root, so
                # two citations into the same tree report it once.
                if (refs_root / head).is_dir() and not (skill_dir / "references" / head).is_dir():
                    missing.add(f"{skill_dir.name}: references/{head}/")
                continue
            if cited.endswith(".py") or "{" in cited or "*" in cited:
                continue  # executable-spec / templated / glob citations are not shipped refs
            if not (refs_root / cited).is_file():
                continue  # not a bundle-root shared ref (skill-own or a project-level path)
            if not (skill_dir / "references" / cited).is_file():
                missing.add(f"{skill_dir.name}: references/{cited}")

    assert not missing, (
        "shared references not resolvable skill-local on the distributed channel "
        f"(source={source!r}):\n  " + "\n  ".join(sorted(missing))
    )
