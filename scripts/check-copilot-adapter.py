#!/usr/bin/env python3
"""Gate the COMMITTED Copilot bundle (adapters/copilot/) against its contract (FORGE-107).

`build-adapters.py --check` proves the committed tree equals a fresh generation; this
gate proves that generation is a valid Copilot bundle, so a generator change that
emits a well-formed-but-wrong tree (and its regenerated fixture) still fails:

  1. plugin.json — the exact legacy five-field manifest (no Agent Plugins 1.0
     ``$schema``), its ``skills``/``agents`` paths existing in the bundle.
  2. skills — one ``skills/<name>/SKILL.md`` per canon skill (no legacy ``<name>.md``),
     frontmatter limited to Copilot's fields, ``name`` == dir name and a valid Agent
     Skills identifier, non-empty ``description`` within the 1024-char limit.
  3. agents — one ``agents/<name>.agent.md`` per canon agent, Copilot fields only,
     builtin tool aliases only, ``agents: []`` (no nested delegation) and
     ``user-invocable: false`` (workers stay out of the picker).
  4. resource links — every ``references/<path>`` a skill or agent body cites
     exists in the bundle (skill-local first, then the bundle root).
  5. drop records — every canon frontmatter key absent from the Copilot output is
     either deliberately mapped or recorded in GENERATION-REPORT.md's copilot table.
  6. stray files — no Python caches, editor/OS junk, or legacy flat skill files
     anywhere in the bundle.

Version sync for plugin.json is check-version-sync.py's job; it is not repeated here.
Needs PyYAML (validate.sh runs it under the provisioned .venv-adapters).

Usage:
    python3 check-copilot-adapter.py [--root DIR]

Exit codes: 0 = clean, 1 = violations (each printed), 2 = bundle missing/unreadable.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import yaml

#: The tested legacy Copilot plugin manifest keys (FORGE-101). Agent Plugins 1.0 is
#: deliberately NOT claimed, so ``$schema`` (or any other key) is a violation.
MANIFEST_KEYS = ("name", "description", "version", "agents", "skills")
SKILL_KEYS = frozenset({"name", "description", "argument-hint"})
AGENT_KEYS = frozenset({"name", "description", "tools", "agents", "user-invocable"})
#: Copilot custom-agent builtin tool aliases.
TOOL_ALIASES = frozenset({"read", "edit", "search", "execute", "agent", "web", "todo"})
#: Canon keys the Copilot emitter maps into another form instead of dropping:
#: ``tools`` -> aliases; the verifier's ``skills`` -> a composed contract (FORGE-102).
MAPPED_AGENT_KEYS = frozenset({"tools", "skills"})
SKILL_NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DESCRIPTION_MAX = 1024
REFERENCE_RE = re.compile(r"(?<![\w/.$}-])references/([A-Za-z0-9_][A-Za-z0-9_./-]*)")
STRAY_NAMES = frozenset({"__pycache__", ".DS_Store", "Thumbs.db", "node_modules"})
STRAY_SUFFIXES = (".pyc", ".pyo", ".orig", ".rej", ".swp", "~")


def frontmatter(path: Path) -> tuple[dict, str]:
    """Return (parsed frontmatter mapping, body) for a ``---``-fenced markdown file."""
    text = path.read_text("utf-8")
    if not text.startswith("---\n"):
        raise ValueError("no leading '---' frontmatter fence")
    head, sep, body = text[4:].partition("\n---\n")
    if not sep:
        raise ValueError("unterminated frontmatter")
    data = yaml.safe_load(head)
    if not isinstance(data, dict):
        raise ValueError("frontmatter is not a mapping")
    return data, body


def check_manifest(bundle: Path, errors: list[str]) -> None:
    path = bundle / "plugin.json"
    try:
        manifest = json.loads(path.read_text("utf-8"))
    except (OSError, ValueError) as exc:
        errors.append(f"plugin.json: unreadable ({exc})")
        return
    if not isinstance(manifest, dict) or tuple(manifest) != MANIFEST_KEYS:
        keys = list(manifest) if isinstance(manifest, dict) else type(manifest).__name__
        errors.append(f"plugin.json: keys must be exactly {list(MANIFEST_KEYS)}, found {keys}")
        return
    if manifest["name"] != "feature-forge":
        errors.append(f"plugin.json: name must be 'feature-forge', found {manifest['name']!r}")
    for key in ("agents", "skills"):
        value = manifest[key]
        if value != f"{key}/" or not (bundle / key).is_dir():
            errors.append(f"plugin.json: {key} must be '{key}/' naming a bundle dir, "
                          f"found {value!r}")


def check_skills(bundle: Path, canon: Path, errors: list[str]) -> None:
    skills_dir = bundle / "skills"
    emitted = {p.name for p in skills_dir.iterdir() if p.is_dir()} if skills_dir.is_dir() else set()
    expected = {p.parent.name for p in (canon / "skills").glob("*/SKILL.md")}
    for name in sorted(expected - emitted):
        errors.append(f"skills/{name}: canon skill missing from the Copilot bundle")
    for name in sorted(emitted - expected):
        errors.append(f"skills/{name}: not a canon skill")
    for name in sorted(emitted):
        rel = f"skills/{name}/SKILL.md"
        native = skills_dir / name / "SKILL.md"
        if (skills_dir / name / f"{name}.md").exists():
            errors.append(f"skills/{name}/{name}.md: legacy flat skill file (native is SKILL.md)")
        if not native.is_file():
            errors.append(f"{rel}: missing")
            continue
        try:
            data, body = frontmatter(native)
        except ValueError as exc:
            errors.append(f"{rel}: {exc}")
            continue
        extra = sorted(set(data) - SKILL_KEYS)
        if extra:
            errors.append(f"{rel}: non-Copilot frontmatter keys {extra}")
        if data.get("name") != name:
            errors.append(f"{rel}: name {data.get('name')!r} must equal its dir name {name!r}")
        if not SKILL_NAME_RE.match(name) or len(name) > 64:
            errors.append(f"{rel}: {name!r} is not a valid Agent Skills name")
        desc = data.get("description")
        if not isinstance(desc, str) or not desc.strip():
            errors.append(f"{rel}: description missing or empty")
        elif len(desc) > DESCRIPTION_MAX:
            errors.append(f"{rel}: description is {len(desc)} chars (limit {DESCRIPTION_MAX})")
        check_links(rel, body, [skills_dir / name, bundle], bundle, errors)


def check_agents(bundle: Path, canon: Path, errors: list[str]) -> None:
    agents_dir = bundle / "agents"
    files = sorted(agents_dir.iterdir()) if agents_dir.is_dir() else []
    expected = {p.stem for p in (canon / "agents").glob("*.md")}
    emitted: set[str] = set()
    for path in files:
        rel = f"agents/{path.name}"
        if not path.name.endswith(".agent.md"):
            errors.append(f"{rel}: Copilot custom agents must be named <name>.agent.md")
            continue
        name = path.name[: -len(".agent.md")]
        emitted.add(name)
        try:
            data, body = frontmatter(path)
        except ValueError as exc:
            errors.append(f"{rel}: {exc}")
            continue
        extra = sorted(set(data) - AGENT_KEYS)
        if extra:
            errors.append(f"{rel}: non-Copilot frontmatter keys {extra}")
        if data.get("name") != name:
            errors.append(f"{rel}: name {data.get('name')!r} must equal the file stem {name!r}")
        if not isinstance(data.get("description"), str) or not data["description"].strip():
            errors.append(f"{rel}: description missing or empty")
        tools = data.get("tools")
        if not isinstance(tools, list) or not tools:
            errors.append(f"{rel}: tools must be a non-empty list of builtin aliases")
        else:
            bad = sorted(str(t) for t in tools if t not in TOOL_ALIASES)
            if bad:
                errors.append(f"{rel}: unknown Copilot tool aliases {bad}")
        if data.get("agents") != []:
            errors.append(f"{rel}: agents must be [] (workers never delegate further)")
        if data.get("user-invocable") is not False:
            errors.append(f"{rel}: user-invocable must be false (worker agents stay hidden)")
        # The composed verifier body cites its skill's references; resolve them there too.
        roots = [bundle] + sorted(p for p in (bundle / "skills").iterdir() if p.is_dir())
        check_links(rel, body, roots, bundle, errors)
    for name in sorted(expected - emitted):
        errors.append(f"agents/{name}.agent.md: canon agent missing from the Copilot bundle")
    for name in sorted(emitted - expected):
        errors.append(f"agents/{name}.agent.md: not a canon agent")


def check_links(rel: str, body: str, roots: list[Path], bundle: Path, errors: list[str]) -> None:
    """Every ``references/<path>`` cited in ``body`` must exist under one of ``roots``."""
    for target in sorted({m.group(1).rstrip(".") for m in REFERENCE_RE.finditer(body)}):
        if not any((root / "references" / target).exists() for root in roots):
            errors.append(f"{rel}: cites references/{target}, which is not in the bundle")


def check_drops(bundle: Path, canon: Path, errors: list[str]) -> None:
    report = canon / "adapters" / "GENERATION-REPORT.md"
    try:
        section = report.read_text("utf-8").split("## copilot\n", 1)[1].split("\n## ", 1)[0]
    except (OSError, IndexError):
        errors.append("adapters/GENERATION-REPORT.md: no '## copilot' drop table")
        return
    rows = set(re.findall(r"^\| `([^`]+)` \| `([^`]+)` \|", section, re.M))

    def require(source: str, construct: str) -> None:
        if (source, construct) not in rows:
            errors.append(f"adapters/GENERATION-REPORT.md: {source} drops {construct!r} "
                          "for Copilot with no drop record")

    for src in sorted((canon / "skills").glob("*/SKILL.md")):
        data, _ = frontmatter(src)
        rel = f"skills/{src.parent.name}/SKILL.md"
        # Spec-pure canon relocates argument-hint under metadata; Copilot emits it top-level.
        metadata = data.get("metadata")
        if isinstance(metadata, dict):
            for sub in sorted(set(metadata) - {"argument-hint"}):
                errors.append(f"canon {rel}: metadata.{sub} has no Copilot mapping or record")
        for key in sorted(set(data) - SKILL_KEYS - {"metadata"}):
            require(rel, key)
    for src in sorted((canon / "agents").glob("*.md")):
        data, _ = frontmatter(src)
        for key in sorted(set(data) - {"name", "description"} - MAPPED_AGENT_KEYS):
            require(f"agents/{src.name}", f"sub-agent key '{key}'")


def check_strays(bundle: Path, errors: list[str]) -> None:
    for path in sorted(bundle.rglob("*")):
        if path.name in STRAY_NAMES or path.name.endswith(STRAY_SUFFIXES):
            errors.append(f"{path.relative_to(bundle).as_posix()}: stray artifact in the bundle")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]),
                        help="repo root holding canon skills/, agents/ and adapters/copilot/")
    root = Path(parser.parse_args(argv).root).resolve()
    bundle = root / "adapters" / "copilot"
    if not bundle.is_dir():
        print(f"ERROR: no Copilot bundle at {bundle}", file=sys.stderr)
        return 2
    errors: list[str] = []
    check_manifest(bundle, errors)
    check_skills(bundle, root, errors)
    check_agents(bundle, root, errors)
    check_drops(bundle, root, errors)
    check_strays(bundle, errors)
    for line in errors:
        repo_relative = line.startswith(("adapters/", "canon "))
        print(f"FAIL: {line}" if repo_relative else f"FAIL: adapters/copilot/{line}")
    if errors:
        print(f"{len(errors)} Copilot bundle violation(s)")
        return 1
    print("Copilot bundle: manifest, skills, agents, resource links, drop records, strays OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
