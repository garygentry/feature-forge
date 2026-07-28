#!/usr/bin/env python3
"""Validate requirement traceability between PRD and implementation specs.

Extracts REQ-XXX-NN identifiers from a PRD file and checks that every
requirement is referenced in at least one implementation spec document.
Also reports orphaned references (IDs found in specs but not in PRD).

Usage:
    python validate-traceability.py <prd-path> <specs-dir> [--json]

Exit codes:
    0 = all requirements covered, no orphans
    1 = gaps or orphans found
    2 = file not found or read error
"""

import argparse
import json
import re
import sys
from pathlib import Path

REQ_PATTERN = re.compile(r"REQ-[A-Z]+-\d+")


def extract_req_ids(text: str) -> set[str]:
    """Extract all unique REQ-XXX-NN identifiers from text."""
    return set(REQ_PATTERN.findall(text))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate requirement traceability between PRD and specs"
    )
    parser.add_argument("prd_path", help="Path to PRD.md file")
    parser.add_argument("specs_dir", help="Directory containing ##-*.md spec files")
    parser.add_argument(
        "--json", action="store_true", dest="json_output", help="Output as JSON"
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

    # Analysis
    uncovered = sorted(prd_reqs - all_spec_reqs)
    orphaned = sorted(all_spec_reqs - prd_reqs)

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

        if not has_issues:
            print("All requirements covered. No orphaned references.")
        else:
            total_issues = len(uncovered) + len(orphaned)
            print(f"Found {total_issues} issue(s).")

    return 1 if has_issues else 0


if __name__ == "__main__":
    sys.exit(main())
