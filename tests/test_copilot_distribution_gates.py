"""Negative tests for the FORGE-107 Copilot distribution gates.

``scripts/check-copilot-adapter.py`` validates the committed Copilot bundle;
``scripts/check-installer-pack.py`` validates the npm tarball file list. Each gate
must pass on the real tree and FAIL on a representative bad input per check.
"""

from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
ADAPTER_GATE = REPO_ROOT / "scripts" / "check-copilot-adapter.py"
PACK_GATE = REPO_ROOT / "scripts" / "check-installer-pack.py"
MARKETPLACE = ".github/plugin/marketplace.json"


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- #
# check-copilot-adapter.py
# --------------------------------------------------------------------------- #


@pytest.fixture
def repo_copy(tmp_path: Path) -> Path:
    """A minimal repo root: canon skills/agents + the committed Copilot bundle + report."""
    root = tmp_path / "repo"
    for rel in ("skills", "agents", "adapters/copilot"):
        shutil.copytree(REPO_ROOT / rel, root / rel)
    shutil.copy2(REPO_ROOT / "adapters" / "GENERATION-REPORT.md",
                 root / "adapters" / "GENERATION-REPORT.md")
    (root / ".github" / "plugin").mkdir(parents=True)
    shutil.copy2(REPO_ROOT / MARKETPLACE, root / MARKETPLACE)
    return root


def _run_adapter_gate(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(ADAPTER_GATE), "--root", str(root)],
                          capture_output=True, text=True)


def test_adapter_gate_passes_on_committed_bundle(repo_copy: Path) -> None:
    result = _run_adapter_gate(repo_copy)
    assert result.returncode == 0, result.stdout + result.stderr


def _edit(path: Path, old: str, new: str) -> None:
    text = path.read_text("utf-8")
    assert old in text, f"fixture drift: {old!r} not in {path}"
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _skill(root: Path, name: str = "forge-1-prd") -> Path:
    return root / "adapters" / "copilot" / "skills" / name / "SKILL.md"


def _agent(root: Path, name: str = "forge-researcher") -> Path:
    return root / "adapters" / "copilot" / "agents" / f"{name}.agent.md"


def _break_schema_key(root: Path) -> None:
    manifest = root / "adapters" / "copilot" / "plugin.json"
    data = json.loads(manifest.read_text("utf-8"))
    manifest.write_text(json.dumps({"$schema": "x", **data}), encoding="utf-8")


def _break_skill_paths(root: Path) -> None:
    manifest = root / "adapters" / "copilot" / "plugin.json"
    data = json.loads(manifest.read_text("utf-8"))
    data["skills"] = "commands/"
    manifest.write_text(json.dumps(data), encoding="utf-8")


def _drop_skill(root: Path) -> None:
    shutil.rmtree(_skill(root, "forge-fix").parent)


def _legacy_flat_skill(root: Path) -> None:
    skill = _skill(root)
    skill.rename(skill.with_name("forge-1-prd.md"))


def _skill_name_mismatch(root: Path) -> None:
    _edit(_skill(root), "name: forge-1-prd", "name: forge-prd")


def _skill_claude_key(root: Path) -> None:
    _edit(_skill(root), "name: forge-1-prd\n", "name: forge-1-prd\nallowed-tools: [Read]\n")


def _skill_long_description(root: Path) -> None:
    _edit(_skill(root), "description: '", "description: '" + "x" * 1100)


def _agent_unknown_tool(root: Path) -> None:
    _edit(_agent(root), "- read\n", "- read\n- Bash\n")


def _agent_nested_delegation(root: Path) -> None:
    _edit(_agent(root), "agents: []", "agents: ['*']")


def _agent_user_invocable(root: Path) -> None:
    _edit(_agent(root), "user-invocable: false", "user-invocable: true")


def _agent_bad_filename(root: Path) -> None:
    agent = _agent(root)
    agent.rename(agent.with_name("forge-researcher.md"))


def _agent_claude_key(root: Path) -> None:
    _edit(_agent(root), "agents: []\n", "agents: []\nmodel: sonnet\n")


def _broken_reference(root: Path) -> None:
    skill = _skill(root)
    skill.write_text(skill.read_text("utf-8") + "\nSee `references/no-such-file.md`.\n",
                     encoding="utf-8")


def _missing_drop_record(root: Path) -> None:
    report = root / "adapters" / "GENERATION-REPORT.md"
    head, copilot = report.read_text("utf-8").split("## copilot\n", 1)
    row = "| `agents/forge-researcher.md` | `sub-agent key 'effort'` |"
    assert row in copilot.split("\n## ", 1)[0]
    report.write_text(f"{head}## copilot\n{copilot.replace(row, '', 1)}", encoding="utf-8")


def _stray_cache(root: Path) -> None:
    cache = root / "adapters" / "copilot" / "scripts" / "__pycache__"
    cache.mkdir(exist_ok=True)
    (cache / "x.cpython-312.pyc").write_bytes(b"\0")


def _marketplace_entry(root: Path, **changes) -> None:
    path = root / MARKETPLACE
    data = json.loads(path.read_text("utf-8"))
    data["plugins"][0].update(changes)
    path.write_text(json.dumps(data), encoding="utf-8")


def _marketplace_serves_claude(root: Path) -> None:
    _marketplace_entry(root, source="./adapters/claude")


def _marketplace_renamed(root: Path) -> None:
    _marketplace_entry(root, name="forge")


def _marketplace_missing(root: Path) -> None:
    (root / MARKETPLACE).unlink()


def _marketplace_shadowed(root: Path) -> None:
    shutil.copy2(root / MARKETPLACE, root / "marketplace.json")


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (_break_schema_key, "plugin.json: keys must be exactly"),
        (_break_skill_paths, "plugin.json: skills must be 'skills/'"),
        (_drop_skill, "skills/forge-fix: canon skill missing"),
        (_legacy_flat_skill, "legacy flat skill file"),
        (_skill_name_mismatch, "must equal its dir name"),
        (_skill_claude_key, "non-Copilot frontmatter keys ['allowed-tools']"),
        (_skill_long_description, "(limit 1024)"),
        (_agent_unknown_tool, "unknown Copilot tool aliases ['Bash']"),
        (_agent_nested_delegation, "agents must be []"),
        (_agent_user_invocable, "user-invocable must be false"),
        (_agent_bad_filename, "must be named <name>.agent.md"),
        (_agent_claude_key, "non-Copilot frontmatter keys ['model']"),
        (_broken_reference, "cites references/no-such-file.md"),
        (_missing_drop_record, "drops \"sub-agent key 'effort'\" for Copilot with no drop record"),
        (_stray_cache, "__pycache__: stray artifact"),
        (_marketplace_serves_claude, "source must be './adapters/copilot'"),
        (_marketplace_renamed, "plugin name must be 'feature-forge'"),
        (_marketplace_missing, f"{MARKETPLACE}: unreadable"),
        (_marketplace_shadowed, f"marketplace.json: shadows {MARKETPLACE}"),
    ],
    ids=lambda v: v.__name__ if callable(v) else "",
)
def test_adapter_gate_fails_on_bad_bundle(repo_copy: Path, mutate, expected: str) -> None:
    mutate(repo_copy)
    result = _run_adapter_gate(repo_copy)
    assert result.returncode == 1, result.stdout + result.stderr
    assert expected in result.stdout, result.stdout


def test_adapter_gate_reports_missing_skills_dir_cleanly(repo_copy: Path) -> None:
    shutil.rmtree(repo_copy / "adapters" / "copilot" / "skills")
    result = _run_adapter_gate(repo_copy)
    assert result.returncode == 1, result.stdout + result.stderr
    assert "Traceback" not in result.stderr
    assert "canon skill missing from the Copilot bundle" in result.stdout


def test_adapter_gate_missing_bundle_is_config_error(tmp_path: Path) -> None:
    assert _run_adapter_gate(tmp_path).returncode == 2


# --------------------------------------------------------------------------- #
# check-installer-pack.py — evaluate() over a synthetic tarball file list
# --------------------------------------------------------------------------- #

pack = _load(PACK_GATE, "check_installer_pack")

SKILLS = ["forge", "forge-1-prd"]
AGENTS = ["forge-researcher"]
SOURCE = sorted(
    list(pack.COPILOT_REQUIRED)
    + [f"adapters/copilot/skills/{s}/SKILL.md" for s in SKILLS]
    + [f"adapters/copilot/agents/{a}.agent.md" for a in AGENTS]
    + ["adapters/GENERATION-REPORT.md", "adapters/claude/skills/forge/SKILL.md"]
)
GOOD = sorted(SOURCE + ["package.json", "README.md", "LICENSE", "dist/cli.js",
                        "dist/cli.d.ts"])


def _evaluate(packed: list[str], source: list[str] = SOURCE) -> list[str]:
    return pack.evaluate(packed, source, SKILLS, AGENTS)


def test_pack_gate_accepts_intended_tarball() -> None:
    assert _evaluate(GOOD) == []


def test_pack_gate_tolerates_only_npm_stripped_gitignore() -> None:
    gitignore = "adapters/copilot/skills/forge/references/templates/go/.gitignore"
    assert _evaluate(GOOD, SOURCE + [gitignore]) == []


@pytest.mark.parametrize(
    ("packed", "expected"),
    [
        ([p for p in GOOD if p != "adapters/copilot/plugin.json"],
         "adapters/copilot/plugin.json: source adapters/ file missing"),
        ([p for p in GOOD if p != "adapters/copilot/agents/forge-researcher.agent.md"],
         "Copilot custom agent missing"),
        (GOOD + ["adapters/copilot/scripts/__pycache__/x.pyc"], "(stray or ignored)"),
        (GOOD + ["src/cli.ts"], "src/cli.ts: outside the intended package surface"),
        (GOOD + ["test/apply.test.js"], "outside the intended package surface"),
        (GOOD + ["node_modules/typescript/package.json"], "outside the intended package"),
        ([p for p in GOOD if p != "dist/cli.js"], "dist/cli.js: the installer bin is missing"),
        ([p for p in GOOD if p != "LICENSE"], "LICENSE: missing from the tarball"),
    ],
)
def test_pack_gate_rejects_bad_tarball(packed: list[str], expected: str) -> None:
    errors = _evaluate(sorted(packed))
    assert any(expected in e for e in errors), errors


def test_pack_gate_requires_copilot_bundle_even_if_source_lacks_it() -> None:
    """A generator that stops emitting the Copilot manifest fails even though the
    tarball still mirrors the (now wrong) source tree exactly."""
    source = [p for p in SOURCE if p != "adapters/copilot/plugin.json"]
    packed = [p for p in GOOD if p != "adapters/copilot/plugin.json"]
    errors = _evaluate(packed, source)
    assert any("required Copilot bundle file missing" in e for e in errors), errors


def test_pack_gate_cleans_prepack_artifacts(tmp_path: Path) -> None:
    installer = tmp_path / "installer"
    (installer / "adapters" / "copilot").mkdir(parents=True)
    (installer / "LICENSE").write_text("x", encoding="utf-8")
    (installer / "package.json").write_text("{}", encoding="utf-8")
    pack.clean_prepack_artifacts(installer)
    assert sorted(p.name for p in installer.iterdir()) == ["package.json"]


# --------------------------------------------------------------------------- #
# check-version-sync.py — the Copilot manifest is a synced field
# --------------------------------------------------------------------------- #


def test_version_sync_fails_when_copilot_manifest_drifts(tmp_path: Path) -> None:
    sync = _load(REPO_ROOT / "scripts" / "check-version-sync.py", "check_version_sync")
    for rel, _label, _accessor in sync.FIELDS:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / rel, tmp_path / rel)
    script = REPO_ROOT / "scripts" / "check-version-sync.py"
    ok = subprocess.run([sys.executable, str(script), "--root", str(tmp_path)],
                        capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout + ok.stderr
    manifest = tmp_path / "adapters" / "copilot" / "plugin.json"
    data = json.loads(manifest.read_text("utf-8"))
    manifest.write_text(json.dumps({**data, "version": "9.9.9"}), encoding="utf-8")
    bad = subprocess.run([sys.executable, str(script), "--root", str(tmp_path)],
                         capture_output=True, text=True)
    assert bad.returncode == 1
    assert "adapters/copilot/plugin.json" in bad.stdout + bad.stderr


def test_version_sync_fails_when_copilot_marketplace_drifts(tmp_path: Path) -> None:
    sync = _load(REPO_ROOT / "scripts" / "check-version-sync.py", "check_version_sync")
    for rel, _label, _accessor in sync.FIELDS:
        (tmp_path / rel).parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / rel, tmp_path / rel)
    catalog = tmp_path / MARKETPLACE
    data = json.loads(catalog.read_text("utf-8"))
    data["plugins"][0]["version"] = "9.9.9"
    catalog.write_text(json.dumps(data), encoding="utf-8")
    script = REPO_ROOT / "scripts" / "check-version-sync.py"
    bad = subprocess.run([sys.executable, str(script), "--root", str(tmp_path)],
                         capture_output=True, text=True)
    assert bad.returncode == 1
    assert f"CONFLICT  {MARKETPLACE}" in bad.stdout
