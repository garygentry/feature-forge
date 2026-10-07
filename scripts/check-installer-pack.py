#!/usr/bin/env python3
"""Gate the installer's npm tarball contents and leave the source tree clean (FORGE-107/202).

Runs the real pack path — ``npm run prepack`` (build + bundle-adapters.mjs) then
``npm pack --dry-run --json --ignore-scripts`` — and checks the would-be tarball:

  * ``adapters/**`` is EXACTLY the git-tracked ``adapters/**`` tree: every generated
    bundle (Copilot included) ships whole, and nothing untracked rides along
    (a stale local file, a Python cache, an editor backup).
  * The Copilot bundle carries what both install paths need: the legacy plugin
    manifest (plugin-first ``copilot plugin install``), the bundle sentinel, native
    skills, ``.agent.md`` workers, and the runtime helpers the installer requires.
  * Outside ``adapters/`` only the package surface ships: ``package.json``,
    ``README.md``, ``LICENSE``, and compiled ``dist/`` (no ``src/``, ``test/``,
    ``scripts/``, ``node_modules/``, or tsconfig).

Afterwards it removes the gitignored prepack artifacts (``installer/adapters/``,
``installer/LICENSE``) — a stale ``installer/adapters/`` would otherwise shadow the
repo's ``adapters/`` as the installer's "packaged copy" source in a dev checkout —
and asserts ``git status`` is byte-identical to before the run (clean-source check).

Usage:
    python3 check-installer-pack.py [--root DIR]

Exit codes: 0 = clean, 1 = violations (each printed), 2 = npm/git unavailable or failed.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

#: Copilot bundle paths the tarball must carry (plugin-first + direct installs).
COPILOT_REQUIRED = (
    "adapters/copilot/plugin.json",
    "adapters/copilot/.feature-forge-bundle.json",
    "adapters/copilot/scripts/forge-root.sh",
    "adapters/copilot/scripts/forge-init.sh",
    "adapters/copilot/scripts/epic-manifest.py",
    "adapters/copilot/scripts/validate-traceability.py",
    "adapters/copilot/scripts/forge-bootstrap.py",
    "adapters/copilot/scripts/forge-session.py",
)
PACKAGE_FILES = frozenset({"package.json", "README.md", "LICENSE"})
#: Basenames npm-packlist ALWAYS drops from a tarball, whatever `files` says. The
#: forge-bootstrap stack templates carry `.gitignore` files, so they are absent from the
#: published bundle (a known, pre-existing gap: #359). Listed explicitly so any OTHER
#: missing file still fails.
NPM_STRIPPED_BASENAMES = frozenset({".gitignore", ".npmignore"})
PREPACK_ARTIFACTS = ("adapters", "LICENSE")


def evaluate(packed: list[str], tracked_adapters: list[str],
             canon_skills: list[str], canon_agents: list[str]) -> list[str]:
    """Return every violation in the would-be tarball file list ``packed``."""
    errors: list[str] = []
    packed_set = set(packed)
    packed_adapters = {p for p in packed_set if p.startswith("adapters/")}
    tracked = set(tracked_adapters)
    for path in sorted(packed_adapters - tracked):
        errors.append(f"{path}: in the tarball but not a source adapters/ file (stray or ignored)")
    for path in sorted(tracked - packed_adapters):
        if path.rsplit("/", 1)[-1] in NPM_STRIPPED_BASENAMES:
            continue
        errors.append(f"{path}: source adapters/ file missing from the tarball")
    for path in COPILOT_REQUIRED:
        if path not in packed_set:
            errors.append(f"{path}: required Copilot bundle file missing from the tarball")
    for name in canon_skills:
        path = f"adapters/copilot/skills/{name}/SKILL.md"
        if path not in packed_set:
            errors.append(f"{path}: Copilot native skill missing from the tarball")
    for name in canon_agents:
        path = f"adapters/copilot/agents/{name}.agent.md"
        if path not in packed_set:
            errors.append(f"{path}: Copilot custom agent missing from the tarball")
    if "dist/cli.js" not in packed_set:
        errors.append("dist/cli.js: the installer bin is missing from the tarball")
    for path in sorted(packed_set - packed_adapters):
        if path in PACKAGE_FILES:
            continue
        if not path.startswith("dist/") or not path.endswith((".js", ".d.ts")):
            errors.append(f"{path}: outside the intended package surface")
    for name in sorted(PACKAGE_FILES - packed_set):
        errors.append(f"{name}: missing from the tarball")
    return errors


def git_lines(root: Path, *args: str) -> list[str]:
    out = subprocess.run(["git", "-C", str(root), *args], check=True,
                         capture_output=True, text=True).stdout
    return [line for line in out.splitlines() if line]


def git_status(root: Path) -> list[str]:
    return git_lines(root, "status", "--porcelain=v1", "--untracked-files=all")


def clean_prepack_artifacts(installer: Path) -> None:
    for name in PREPACK_ARTIFACTS:
        path = installer / name
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path)
        elif path.exists() or path.is_symlink():
            path.unlink()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[1]))
    root = Path(parser.parse_args(argv).root).resolve()
    installer = root / "installer"
    if shutil.which("npm") is None or shutil.which("git") is None:
        print("ERROR: npm and git are required for the pack check", file=sys.stderr)
        return 2
    try:
        before = git_status(root)
        # Tracked + untracked-but-not-ignored files present on disk: the tree the drift gate
        # polices. Anything ignored (caches, venvs) must never reach the tarball.
        tracked = [p for p in git_lines(root, "ls-files", "--cached", "--others",
                                        "--exclude-standard", "--", "adapters")
                   if (root / p).is_file()]
    except subprocess.CalledProcessError as exc:
        print(f"ERROR: git failed: {exc.stderr.strip()}", file=sys.stderr)
        return 2
    try:
        prepack = subprocess.run(["npm", "run", "prepack", "--silent"], cwd=installer,
                                 capture_output=True, text=True)
        if prepack.returncode != 0:
            print(prepack.stdout + prepack.stderr, file=sys.stderr)
            print("ERROR: installer prepack failed", file=sys.stderr)
            return 2
        pack = subprocess.run(["npm", "pack", "--dry-run", "--json", "--ignore-scripts"],
                              cwd=installer, capture_output=True, text=True)
        if pack.returncode != 0:
            print(pack.stderr, file=sys.stderr)
            print("ERROR: npm pack --dry-run failed", file=sys.stderr)
            return 2
        report = json.loads(pack.stdout)[0]
    finally:
        clean_prepack_artifacts(installer)
    packed = [entry["path"] for entry in report["files"]]
    errors = evaluate(
        packed,
        tracked,
        sorted(p.parent.name for p in (root / "skills").glob("*/SKILL.md")),
        sorted(p.stem for p in (root / "agents").glob("*.md")),
    )
    after = git_status(root)
    if after != before:
        changed = sorted(set(after) ^ set(before))
        errors.append(f"git status changed across the pack check (not clean): {changed}")
    for line in errors:
        print(f"FAIL: {line}")
    if errors:
        print(f"{len(errors)} pack violation(s) in {report['name']}@{report['version']}")
        return 1
    copilot = sum(1 for p in packed if p.startswith("adapters/copilot/"))
    stripped = sum(1 for p in tracked if p.rsplit("/", 1)[-1] in NPM_STRIPPED_BASENAMES)
    if stripped:
        print(f"INFO: {stripped} source file(s) named {sorted(NPM_STRIPPED_BASENAMES)} are "
              "dropped by npm-packlist (known gap #359, not a gate failure)")
    print(f"{report['name']}@{report['version']}: {len(packed)} files "
          f"({copilot} Copilot bundle files); adapters/ == tracked tree; source tree clean")
    return 0


if __name__ == "__main__":
    sys.exit(main())
