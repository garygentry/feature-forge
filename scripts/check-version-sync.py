#!/usr/bin/env python3
"""Assert the three feature-forge version fields agree (REQ-CI-05, REQ-OBS-01).

Within-repo version-sync gate. The three fields are the version-sync contract from
00-core-definitions.md §5; installer/package.json is EXCLUDED (independent line).
The gate prints every field and its value, flags conflicts, and exits non-zero on
any mismatch (REQ-OBS-01 — no silent failure). It MUST currently FAIL on the live
desync (plugin 0.10.0 / marketplace 0.9.0 / gemini 0.0.0) until reconciliation
lands (06-packaging-versioning-hygiene.md), then PASS (SC-03).

Stdlib only (json) — no third-party deps, matching the repo's other gate scripts.

Usage:
    python3 check-version-sync.py [--root DIR]

Exit codes:
    0 = all three fields byte-equal
    1 = mismatch (conflicting files+values printed)
    2 = a field is missing/unreadable (config error)
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

#: The three synced fields (00 §5). Each: (repo-relative file, accessor label,
#: a function extracting the version string from the parsed JSON).
FIELDS: tuple[tuple[str, str, "object"], ...] = (
    (".claude-plugin/plugin.json", "version", lambda d: d["version"]),
    (
        ".claude-plugin/marketplace.json",
        "plugins[0].version",
        lambda d: d["plugins"][0]["version"],
    ),
    ("adapters/gemini/gemini-extension.json", "version", lambda d: d["version"]),
)

#: EXCLUDED from the gate — installer/ is a separately published sub-package (00 §5).
EXCLUDED = ("installer/package.json",)


def _read_version(root: Path, rel: str, label: str, accessor) -> tuple[str | None, str | None]:
    """Return (version, error). version is None when an error string is set."""
    path = root / rel
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, f"{rel}: file not found"
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"{rel}: unreadable/invalid JSON ({exc})"
    try:
        value = accessor(data)
    except (KeyError, IndexError, TypeError):
        return None, f"{rel}: missing field '{label}'"
    if not isinstance(value, str):
        return None, f"{rel}: field '{label}' is not a string ({value!r})"
    return value, None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check-version-sync.py",
        description="Assert feature-forge's three version fields agree (REQ-CI-05).",
    )
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repo root to scan (default: parent of this script's dir).",
    )
    args = parser.parse_args(argv)
    root: Path = args.root.resolve()

    print("version-sync: checking the three synced feature-forge fields (REQ-CI-05)...")
    print(f"version-sync: excluded (independent line): {', '.join(EXCLUDED)}")

    versions: dict[str, str] = {}
    config_error = False
    for rel, label, accessor in FIELDS:
        value, error = _read_version(root, rel, label, accessor)
        if error is not None:
            print(f"  ERROR  {error}")
            config_error = True
            continue
        print(f"  {rel} ({label}) = {value}")
        versions[f"{rel} ({label})"] = value  # type: ignore[assignment]

    if config_error:
        print("version-sync: FATAL — a synced field is missing/unreadable (config error).")
        return 2

    distinct = set(versions.values())
    if len(distinct) == 1:
        only = next(iter(distinct))
        print(f"version-sync: PASS — all three fields agree at {only}.")
        return 0

    # Mismatch — print the conflict explicitly (REQ-OBS-01: conflicting files+values).
    print(f"version-sync: FAIL — fields disagree: {sorted(distinct)}")
    for label, value in versions.items():
        print(f"  CONFLICT  {label} = {value}")
    print(
        "version-sync: reconcile to a single version (00 §5: 0.10.0). marketplace.json "
        "is hand-edited; gemini-extension.json is REGENERATED via "
        "scripts/build-adapters.py (bump GEMINI_EXTENSION_VERSION). See "
        "06-packaging-versioning-hygiene.md."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
