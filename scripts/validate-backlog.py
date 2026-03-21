#!/usr/bin/env python3
"""
Validate a ralph backlog.json file for schema compliance and logical consistency.

Usage: python validate-backlog.py <path-to-backlog.json> [--specs-dir <path>]

Exit codes:
  0 = valid
  1 = errors found
  2 = file not found or invalid JSON
"""

import json
import sys
import os
from pathlib import Path


def validate_backlog(backlog_path: str, specs_dir: str | None = None) -> list[dict]:
    """Validate backlog.json and return a list of findings."""
    findings = []

    # Load and parse
    try:
        with open(backlog_path, "r") as f:
            data = json.load(f)
    except FileNotFoundError:
        return [{"severity": "error", "message": f"File not found: {backlog_path}"}]
    except json.JSONDecodeError as e:
        return [{"severity": "error", "message": f"Invalid JSON: {e}"}]

    # Top-level structure
    if not isinstance(data, dict):
        return [{"severity": "error", "message": "Root must be an object"}]

    for field in ["project", "description", "items"]:
        if field not in data:
            findings.append({"severity": "error", "message": f"Missing required top-level field: {field}"})

    if "items" not in data or not isinstance(data.get("items"), list):
        findings.append({"severity": "error", "message": "'items' must be an array"})
        return findings

    items = data["items"]
    if len(items) == 0:
        findings.append({"severity": "error", "message": "Backlog has zero items"})
        return findings

    # Required fields per item
    required_fields = [
        "id", "type", "priority", "title", "description",
        "acceptanceCriteria", "status", "dependsOn", "specReferences"
    ]
    valid_statuses = ["pending", "in-progress", "complete", "blocked", "skipped"]
    valid_types = ["feature", "bugfix", "chore", "refactor", "test", "docs"]

    ids_seen = set()

    for i, item in enumerate(items):
        item_id = item.get("id", f"<index {i}>")
        prefix = f"Item {item_id}"

        # Required fields
        for field in required_fields:
            if field not in item:
                findings.append({
                    "severity": "error",
                    "message": f"{prefix}: missing required field '{field}'"
                })

        # Unique IDs
        if "id" in item:
            if item["id"] in ids_seen:
                findings.append({
                    "severity": "error",
                    "message": f"{prefix}: duplicate ID '{item['id']}'"
                })
            ids_seen.add(item["id"])

        # Type validation
        if "type" in item and item["type"] not in valid_types:
            findings.append({
                "severity": "warning",
                "message": f"{prefix}: type '{item['type']}' not in standard set {valid_types}"
            })

        # Status validation
        if "status" in item and item["status"] not in valid_statuses:
            findings.append({
                "severity": "warning",
                "message": f"{prefix}: status '{item['status']}' not in standard set {valid_statuses}"
            })

        # Acceptance criteria
        ac = item.get("acceptanceCriteria", [])
        if isinstance(ac, list) and len(ac) == 0:
            findings.append({
                "severity": "warning",
                "message": f"{prefix}: empty acceptanceCriteria"
            })

        # Dependency validation
        deps = item.get("dependsOn", [])
        if isinstance(deps, list):
            for dep in deps:
                if dep not in ids_seen and dep not in {it.get("id") for it in items}:
                    findings.append({
                        "severity": "error",
                        "message": f"{prefix}: dependsOn references non-existent item '{dep}'"
                    })

        # Spec reference validation
        if specs_dir:
            refs = item.get("specReferences", [])
            if isinstance(refs, list):
                for ref in refs:
                    # Resolve spec references relative to CWD (project root)
                    ref_path = Path.cwd() / ref
                    if not ref_path.exists():
                        findings.append({
                            "severity": "warning",
                            "message": f"{prefix}: specReference '{ref}' not found"
                        })

        # Description quality
        desc = item.get("description", "")
        if isinstance(desc, str) and len(desc) < 50:
            findings.append({
                "severity": "warning",
                "message": f"{prefix}: description is very short ({len(desc)} chars) — may lack detail for a fresh agent"
            })

    # Circular dependency check
    dep_graph = {}
    for item in items:
        item_id = item.get("id")
        if item_id:
            dep_graph[item_id] = item.get("dependsOn", [])

    def has_cycle(node, visited, rec_stack):
        visited.add(node)
        rec_stack.add(node)
        for dep in dep_graph.get(node, []):
            if dep not in visited:
                if has_cycle(dep, visited, rec_stack):
                    return True
            elif dep in rec_stack:
                return True
        rec_stack.discard(node)
        return False

    visited = set()
    for node in dep_graph:
        if node not in visited:
            if has_cycle(node, visited, set()):
                findings.append({
                    "severity": "error",
                    "message": "Circular dependency detected in dependsOn graph"
                })
                break

    return findings


def main():
    if len(sys.argv) < 2:
        print("Usage: validate-backlog.py <backlog.json> [--specs-dir <path>] [--json]")
        sys.exit(2)

    backlog_path = sys.argv[1]
    specs_dir = None
    json_output = "--json" in sys.argv

    if "--specs-dir" in sys.argv:
        idx = sys.argv.index("--specs-dir")
        if idx + 1 < len(sys.argv):
            specs_dir = sys.argv[idx + 1]

    findings = validate_backlog(backlog_path, specs_dir)

    if json_output:
        print(json.dumps({"findings": findings, "valid": not any(f["severity"] == "error" for f in findings)}, indent=2))
        sys.exit(1 if any(f["severity"] == "error" for f in findings) else 0)

    if not findings:
        print("✅ Backlog is valid. No issues found.")
        sys.exit(0)

    errors = [f for f in findings if f["severity"] == "error"]
    warnings = [f for f in findings if f["severity"] == "warning"]

    print(f"Found {len(errors)} error(s) and {len(warnings)} warning(s):\n")

    for f in errors:
        print(f"  ❌ ERROR: {f['message']}")
    for f in warnings:
        print(f"  ⚠️  WARN:  {f['message']}")

    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
