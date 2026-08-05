#!/usr/bin/env python3
"""Validate requirement traceability between PRD and implementation specs.

Extracts REQ-XXX-NN identifiers from a PRD file and checks that every
requirement is referenced in at least one implementation spec document.
Also reports orphaned references (IDs found in specs but not in PRD).

A suite may legitimately mention a *foreign* requirement id — most often when a
spec quotes an antecedent feature's test docstrings verbatim, carrying that
feature's ids into this suite's text. Those are not this suite's requirements and
are not orphans. Declare them with --allow-orphan, or one id per line in
<specs-dir>/.traceability-allowlist; allowed ids are reported, never silently
dropped.

Usage:
    python validate-traceability.py <prd-path> <specs-dir> [--json]
                                    [--allow-orphan REQ-ID ...]

Exit codes:
    0 = all requirements covered; no orphans other than allowlisted ones
    1 = uncovered requirements, or orphans that are not allowlisted
    2 = file not found or read error
"""

import argparse
import json
import re
import sys
from pathlib import Path

#: The category segment may contain digits after its first letter — `REQ-R1-01`,
#: `REQ-R6-03`. The original `[A-Z]+` could not match those, so whole requirement
#: families were invisible to this checker and reported as "all covered" while never
#: having been looked at (context-efficiency: 12 of 29 requirements seen). The first
#: character stays `[A-Z]` so a lowercase or digit-led token is still not an ID.
REQ_PATTERN = re.compile(r"REQ-[A-Z][A-Z0-9]*-\d+")

#: Optional per-suite allowlist of foreign requirement ids, read from the specs dir.
#: One id per line; blank lines and `#` comments ignored. Kept beside the suite it
#: describes rather than hardcoded here, so this validator stays generic across
#: repos and suites.
ALLOWLIST_FILENAME = ".traceability-allowlist"


def extract_req_ids(text: str) -> set[str]:
    """Extract all unique REQ-XXX-NN identifiers from text."""
    return set(REQ_PATTERN.findall(text))


def read_allowlist_file(specs_dir: Path) -> set[str]:
    """Read <specs-dir>/.traceability-allowlist, if present.

    A missing file is not an error — most suites have no foreign ids at all.

    Args:
        specs_dir: The suite's specs directory, searched for the allowlist file.

    Returns:
        The declared foreign requirement ids; an empty set when the file is
        absent or unreadable.
    """
    allowlist_path = specs_dir / ALLOWLIST_FILENAME
    if not allowlist_path.exists():
        return set()
    try:
        text = allowlist_path.read_text()
    except OSError as e:
        print(f"Warning: Could not read {allowlist_path}: {e}", file=sys.stderr)
        return set()
    ids: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if line:
            ids.add(line)
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate requirement traceability between PRD and specs"
    )
    parser.add_argument("prd_path", help="Path to PRD.md file")
    parser.add_argument("specs_dir", help="Directory containing ##-*.md spec files")
    parser.add_argument(
        "--json", action="store_true", dest="json_output", help="Output as JSON"
    )
    parser.add_argument(
        "--allow-orphan",
        action="append",
        default=[],
        dest="allow_orphan",
        metavar="REQ-ID",
        help=(
            "Requirement id that may appear in the specs without being defined in "
            f"this suite's PRD (repeatable). Merged with {ALLOWLIST_FILENAME}."
        ),
    )
    args = parser.parse_args()

    prd_path = Path(args.prd_path)
    specs_dir = Path(args.specs_dir)

    # Read PRD
    if not prd_path.exists():
        print(f"Error: PRD file not found: {prd_path}", file=sys.stderr)
        return 2

    try:
        prd_text = prd_path.read_text()
    except OSError as e:
        print(f"Error reading PRD: {e}", file=sys.stderr)
        return 2

    prd_reqs = extract_req_ids(prd_text)

    if not prd_reqs:
        print(f"Warning: No REQ-XXX-NN identifiers found in {prd_path}", file=sys.stderr)

    # Read spec files (##-*.md pattern)
    if not specs_dir.exists():
        print(f"Error: Specs directory not found: {specs_dir}", file=sys.stderr)
        return 2

    spec_files = sorted(specs_dir.glob("[0-9][0-9]-*.md"))
    if not spec_files:
        print(f"Warning: No spec files matching ##-*.md found in {specs_dir}", file=sys.stderr)

    # Track which specs cover which requirements
    spec_reqs: dict[str, set[str]] = {}
    all_spec_reqs: set[str] = set()

    for spec_file in spec_files:
        try:
            text = spec_file.read_text()
            reqs = extract_req_ids(text)
            spec_reqs[spec_file.name] = reqs
            all_spec_reqs |= reqs
        except OSError as e:
            print(f"Warning: Could not read {spec_file}: {e}", file=sys.stderr)

    # Also check TRACEABILITY.md if it exists
    traceability_file = specs_dir / "TRACEABILITY.md"
    if traceability_file.exists():
        try:
            text = traceability_file.read_text()
            trace_reqs = extract_req_ids(text)
            spec_reqs["TRACEABILITY.md"] = trace_reqs
            all_spec_reqs |= trace_reqs
        except OSError:
            pass

    # Analysis. Allowed foreign ids are subtracted from the orphan set but reported
    # below, so an allowlist entry is always visible rather than an invisible pass.
    allowlist = read_allowlist_file(specs_dir) | set(args.allow_orphan)
    uncovered = sorted(prd_reqs - all_spec_reqs)
    raw_orphaned = all_spec_reqs - prd_reqs
    allowed_orphans = sorted(raw_orphaned & allowlist)
    orphaned = sorted(raw_orphaned - allowlist)
    # An allowlist entry that no longer matches anything is stale — surface it so the
    # list cannot quietly outlive the quotation that justified it.
    unused_allowlist = sorted(allowlist - raw_orphaned)

    # Per-requirement coverage map
    coverage: dict[str, list[str]] = {}
    for req_id in sorted(prd_reqs):
        covering_specs = [
            name for name, reqs in spec_reqs.items() if req_id in reqs
        ]
        coverage[req_id] = covering_specs

    has_issues = bool(uncovered or orphaned)

    if args.json_output:
        result = {
            "prd_file": str(prd_path),
            "specs_dir": str(specs_dir),
            "total_requirements": len(prd_reqs),
            "total_spec_files": len(spec_files),
            "uncovered_requirements": uncovered,
            "orphaned_references": orphaned,
            "allowed_orphans": allowed_orphans,
            "unused_allowlist_entries": unused_allowlist,
            "coverage": coverage,
            "valid": not has_issues,
        }
        print(json.dumps(result, indent=2))
    else:
        print(f"PRD: {prd_path} ({len(prd_reqs)} requirements)")
        print(f"Specs: {specs_dir} ({len(spec_files)} spec files)")
        print()

        if uncovered:
            print(f"UNCOVERED REQUIREMENTS ({len(uncovered)}):")
            for req_id in uncovered:
                print(f"  - {req_id}: not found in any spec file")
            print()

        if orphaned:
            print(f"ORPHANED REFERENCES ({len(orphaned)}):")
            for req_id in orphaned:
                sources = [
                    name for name, reqs in spec_reqs.items() if req_id in reqs
                ]
                print(f"  - {req_id}: found in {', '.join(sources)} but not in PRD")
            print()

        if allowed_orphans:
            print(f"ALLOWED FOREIGN REFERENCES ({len(allowed_orphans)}):")
            for req_id in allowed_orphans:
                sources = [
                    name for name, reqs in spec_reqs.items() if req_id in reqs
                ]
                print(f"  - {req_id}: found in {', '.join(sources)}; allowlisted")
            print()

        if unused_allowlist:
            print(f"STALE ALLOWLIST ENTRIES ({len(unused_allowlist)}):")
            for req_id in unused_allowlist:
                print(
                    f"  - {req_id}: allowlisted but no longer referenced — remove it "
                    f"from <specs-dir>/{ALLOWLIST_FILENAME} "
                    f"(advisory; does not fail this check)"
                )
            print()

        if not has_issues:
            print("All requirements covered. No unallowlisted orphaned references.")
        else:
            total_issues = len(uncovered) + len(orphaned)
            print(f"Found {total_issues} issue(s).")

    return 1 if has_issues else 0


if __name__ == "__main__":
    sys.exit(main())
