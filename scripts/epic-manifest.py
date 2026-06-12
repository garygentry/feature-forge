#!/usr/bin/env python3
"""Read, validate, and atomically mutate an epic manifest.

The deterministic core for Epic Orchestration: name->directory resolution,
acyclicity and schema validation, global name-uniqueness, path containment,
live per-feature status derivation, and atomic manifest mutation.

Usage:
    python3 epic-manifest.py resolve <name> [--specs-dir DIR]
    python3 epic-manifest.py validate <epic> [--specs-dir DIR] [--json]
    python3 epic-manifest.py check-name <name> [--specs-dir DIR]
    python3 epic-manifest.py render-status <epic> [--specs-dir DIR] [--json]
    python3 epic-manifest.py add-feature <epic> <name> --charter TEXT \
        [--depends-on A,B] [--specs-dir DIR]
    python3 epic-manifest.py remove-feature <epic> <name> [--specs-dir DIR]
    python3 epic-manifest.py reorder <epic> --order A,B,C [--specs-dir DIR]
    python3 epic-manifest.py set-dep <epic> <name> --depends-on A,B [--specs-dir DIR]
    python3 epic-manifest.py set-status <epic> --status STATE [--specs-dir DIR]

Exit codes:
    0 = ok / valid / unique / resolved
    1 = findings / validation failure / duplicate / ambiguous / not-found
    2 = usage error or I/O error (missing file, unreadable, unsafe path)
"""

import argparse
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Literal, TypedDict


# --------------------------------------------------------------------------- #
# Constants (00-core-definitions.md §6)
# --------------------------------------------------------------------------- #

#: A safe feature/epic name: one kebab-case token (00 §6).
SAFE_NAME_RE: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
#: A directory is "feature-shaped" iff it directly contains this file.
PIPELINE_STATE_FILENAME: Final = ".pipeline-state.json"
#: Canonical filenames sited at the epic subtree root.
MANIFEST_FILENAME: Final = "epic-manifest.json"
NARRATIVE_FILENAME: Final = "EPIC.md"


# --------------------------------------------------------------------------- #
# Type Definitions (00-core-definitions.md §4, §5; 02 §8.4)
# --------------------------------------------------------------------------- #

FindingCode = Literal[
    "corrupt-json",     # manifest is not parseable JSON (REQ-ROBUST-02)
    "schema",           # manifest violates epic-manifest-schema.json
    "duplicate-name",   # a feature/epic name occurs more than once in the tree (REQ-DIR-04)
    "dangling-ref",     # dependsOn / consumes.from references an unknown feature (REQ-ROBUST-02)
    "cycle",            # the dependsOn graph contains a cycle (REQ-EPIC-05)
    "unsafe-name",      # a name contains a path separator, "..", or is absolute (REQ-SEC-02)
    "path-escape",      # a resolved path would leave {specsDir} (REQ-SEC-02)
    "not-found",        # a name resolves to zero feature-shaped directories
    "ambiguous",        # a name resolves to more than one feature-shaped directory (REQ-DIR-04)
    "cached-status",    # a Feature object illegally carries a status field (REQ-STATE-02)
]


class Finding(TypedDict):
    """A single, actionable validation or resolution failure.

    Attributes:
        code: Machine-readable category (see FindingCode).
        message: Human-readable, actionable description. Includes offending
            identifiers and, where relevant, the conflicting paths.
        feature: The feature name the finding pertains to, or None for
            manifest- or epic-level findings.
    """

    code: FindingCode
    message: str
    feature: str | None


DerivedStatus = Literal[
    "not-started",   # no .pipeline-state.json, or all stages pending
    "in-progress",   # at least one stage started, loop not complete-for-orchestration
    "complete",      # complete-for-orchestration per 00 §7
]


class FeatureStatus(TypedDict):
    """Live per-feature status derived from its own pipeline state (00 §5).

    Attributes:
        name: Feature name.
        stage: The feature's current pipeline stage (its currentStage), or
            "forge-0-epic" if the member directory exists but no stage has run.
        status: Coarse derived status (see DerivedStatus). Reuses existing
            navigator status semantics for display.
        blocked: True if any entry in unmetDeps is non-empty.
        unmetDeps: Names of this feature's direct dependencies that are not yet
            complete-for-orchestration (00 §7). Empty when actionable or complete.
    """

    name: str
    stage: str
    status: DerivedStatus
    blocked: bool
    unmetDeps: list[str]


class Rollup(TypedDict):
    """Aggregate completion counts for the epic dashboard (00 §8)."""

    complete: int  #: Number of member features complete-for-orchestration (00 §7).
    total: int     #: Total member features in the manifest (0 for an empty epic).


class RenderStatus(TypedDict):
    """The full live dashboard payload returned by render_status (00 §5, §8).

    Attributes:
        epic: The epic name (manifest `epic`).
        status: The epic lifecycle status (00 §2.1).
        features: Per-member status rows, one per manifest feature (may be empty).
        actionable: Names of features whose dependsOn are all complete and that
            are not themselves complete (00 §8).
        parallelEligible: Subset of `actionable` with no mutual (transitive)
            dependency — surfaced for future parallel execution (00 §8).
        rollup: Aggregate {complete, total} counts.
        nextCommand: Recommended next command for the first actionable feature, or
            None when nothing is actionable (all complete, empty epic, or paused).
    """

    epic: str
    status: Literal["active", "paused", "abandoned", "complete"]
    features: list[FeatureStatus]
    actionable: list[str]
    parallelEligible: list[str]
    rollup: Rollup
    nextCommand: str | None


# --------------------------------------------------------------------------- #
# Internal Exceptions (02 §2)
# --------------------------------------------------------------------------- #


class UsageError(Exception):
    """A usage or I/O failure that must exit 2.

    Raised for missing files, unreadable paths, malformed CLI arguments, and
    unsafe-name / path-escape conditions detected before filesystem access
    (REQ-SEC-02). Maps to exit code 2.

    Attributes:
        message: Human-readable description printed to stderr.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class FindingsError(Exception):
    """A non-fatal validation outcome that must exit 1.

    Raised when an operation produces one or more Findings (00 §4) that block a
    gating operation: a cycle, a dangling ref, an ambiguous/not-found name, etc.
    Maps to exit code 1. Carries the structured findings so the dispatch layer
    can emit them as JSON or human lines.

    Attributes:
        findings: The list of Findings to surface.
    """

    def __init__(self, findings: list["Finding"]) -> None:
        self.findings = findings
        super().__init__(f"{len(findings)} finding(s)")


# --------------------------------------------------------------------------- #
# Safety & I/O Layer (02 §3)
# --------------------------------------------------------------------------- #


def assert_safe_name(name: str) -> None:
    """Validate a bare feature/epic name before any filesystem access.

    A name is safe iff it is a single kebab-case token with no path separator,
    no ``..`` segment, and is not absolute (REQ-SEC-02). This runs first in
    every subcommand so that an unsafe name never reaches a glob or open().

    Args:
        name: The bare name supplied on the command line.

    Raises:
        UsageError: If the name is empty, absolute, contains '/' or '\\',
            equals '..', or fails SAFE_NAME_RE. The message embeds the
            offending name (e.g. ``unsafe name '../escape'``) so the caller can
            surface it verbatim. Corresponds to the 'unsafe-name' Finding code
            (00 §4) but is raised as a usage error because it is detected before
            any manifest is read.
    """
    if (
        not name
        or name == ".."
        or "/" in name
        or "\\" in name
        or os.path.isabs(name)
        or not SAFE_NAME_RE.match(name)
    ):
        raise UsageError(f"unsafe name {name!r}")


def contained_path(base: Path, *parts: str) -> Path:
    """Join parts onto base and assert the result stays within base.

    Canonicalizes (symlink-resolves) both base and the joined path and verifies
    the result is contained within the real base (REQ-SEC-02). Used before
    reading or writing any manifest, narrative, or pipeline-state file so no
    epic operation can read or write outside the specs subtree.

    Args:
        base: The containing directory (typically {specsDir} or an epic dir),
            already known to exist.
        *parts: Path segments to append (each already passed through
            assert_safe_name when it originates from user input).

    Returns:
        The resolved, contained absolute path.

    Raises:
        UsageError: If the resolved path escapes ``base`` (message:
            ``resolved path escapes specs dir: …``). Corresponds to the
            'path-escape' Finding code (00 §4); raised as a usage error
            (exit 2) per the error model in tech-spec §6.
    """
    base_real = base.resolve()
    target = (base_real / Path(*parts)).resolve()
    try:
        target.relative_to(base_real)
    except ValueError:
        raise UsageError(f"resolved path escapes specs dir: {base_real / Path(*parts)}")
    return target


def load_manifest(epic_dir: Path) -> dict:
    """Load and JSON-parse an epic's manifest.

    Args:
        epic_dir: The epic subtree directory (must already be contained within
            {specsDir} via contained_path).

    Returns:
        The parsed manifest as a plain dict. Structural validation (schema,
        cycles, dangling refs) is performed separately by ``validate`` — this
        function only guarantees the file exists and parses.

    Raises:
        UsageError: If the manifest file is missing or unreadable (exit 2).
        FindingsError: If the file exists but is not parseable JSON — emits a
            single 'corrupt-json' Finding (00 §4) with the JSON error position,
            so a hand-corrupted manifest fails with an actionable message rather
            than a traceback (REQ-ROBUST-02). Exit 1.
    """
    path = epic_dir / MANIFEST_FILENAME
    if not path.is_file():
        raise UsageError(f"manifest not found: {path}")
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise UsageError(f"cannot read manifest {path}: {exc}")
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise FindingsError([
            {
                "code": "corrupt-json",
                "message": f"manifest {path} is not valid JSON: {exc}",
                "feature": None,
            }
        ])


def atomic_write(path: Path, data: dict) -> None:
    """Write a manifest dict to disk atomically.

    Writes to a temporary file **in the same directory** as the target, flushes
    and fsyncs it, then ``os.replace`` swaps it into place. ``os.replace`` is
    atomic on POSIX within a single filesystem, so an interrupted write never
    leaves a partial or corrupt manifest (REQ-ROBUST-03). Concurrent multi-
    session mutation is out of scope (single-writer assumed, PRD REQ-ROBUST-03).

    Args:
        path: The destination manifest path (e.g. {epic}/epic-manifest.json).
        data: The fully-formed, already-validated manifest dict to serialize.

    Raises:
        UsageError: If the temp file cannot be created/written or the replace
            fails (exit 2). On failure the temp file is removed so no debris is
            left behind.
    """
    parent = path.parent
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=parent
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except OSError as exc:
        tmp_path.unlink(missing_ok=True)
        raise UsageError(f"atomic write to {path} failed: {exc}")


# --------------------------------------------------------------------------- #
# Graph Algorithms (02 §4) — implemented in item 004
# --------------------------------------------------------------------------- #


def find_cycle(features: list[dict]) -> list[str] | None:
    """Return a cycle in the dependsOn graph, or None if acyclic (02 §4).

    Iterative DFS over the directed graph whose edges are ``feature -> dep``.
    On the first back-edge into a GRAY node, reconstructs and returns the cycle
    path including the repeated start node (e.g. ``["a", "b", "a"]``). A
    self-dependency is a degenerate self-loop returning ``["x", "x"]``. Only
    edges to names present in ``features`` are traversed (dangling refs are
    reported separately by validate). O(V+E).
    """
    adjacency: dict[str, list[str]] = {f["name"]: list(f.get("dependsOn", [])) for f in features}
    WHITE, GRAY, BLACK = 0, 1, 2
    color: dict[str, int] = {name: WHITE for name in adjacency}
    parent: dict[str, str | None] = {name: None for name in adjacency}

    for root in adjacency:
        if color[root] != WHITE:
            continue
        # Iterative DFS; stack holds (node, index-of-next-neighbor-to-visit).
        stack: list[tuple[str, int]] = [(root, 0)]
        color[root] = GRAY
        while stack:
            node, idx = stack[-1]
            neighbors = [n for n in adjacency[node] if n in adjacency]
            if idx < len(neighbors):
                stack[-1] = (node, idx + 1)
                nxt = neighbors[idx]
                if color[nxt] == WHITE:
                    color[nxt] = GRAY
                    parent[nxt] = node
                    stack.append((nxt, 0))
                elif color[nxt] == GRAY:
                    # Back-edge: reconstruct nxt -> … -> node -> nxt.
                    path = [nxt]
                    cursor: str | None = node
                    while cursor is not None and cursor != nxt:
                        path.append(cursor)
                        cursor = parent[cursor]
                    path.append(nxt)
                    path.reverse()
                    return path
            else:
                color[node] = BLACK
                stack.pop()
    return None


def unmet_deps(
    name: str, features: list[dict], complete: dict[str, bool]
) -> list[str]:
    """Return a feature's direct dependencies that are not complete (02 §4).

    Names of this feature's direct ``dependsOn`` entries whose value in
    ``complete`` is False, preserving manifest order. Empty when the feature is
    actionable or itself complete.
    """
    by_name = {f["name"]: f for f in features}
    feature = by_name.get(name, {})
    return [dep for dep in feature.get("dependsOn", []) if not complete.get(dep, False)]


# --------------------------------------------------------------------------- #
# Resolution & Uniqueness (02 §5) — implemented in item 005
# --------------------------------------------------------------------------- #


def feature_dirs(specs_dir: Path) -> dict[str, list[Path]]:
    """Map every feature name in the specs tree to the dirs that bear it (02 §5).

    Scans both layouts to a fixed depth, treating a directory as a feature iff
    it directly contains a ``.pipeline-state.json`` (00 §6, REQ-DIR-03):
      * flat:   {specsDir}/{name}/.pipeline-state.json
      * nested: {specsDir}/{epic}/{name}/.pipeline-state.json

    The returned map is keyed by bare feature name; a name with more than one
    entry is a uniqueness violation (REQ-DIR-04) surfaced as 'ambiguous' or
    'duplicate-name' by the caller. Epic directories themselves (which hold
    ``epic-manifest.json`` but no ``.pipeline-state.json``) are skipped, so an
    epic name never collides with a feature name (01 §4.3).

    Args:
        specs_dir: The configured specs directory (already verified to exist).

    Returns:
        Dict of feature name -> sorted list of absolute feature-dir paths. A
        single-entry list means the name is unique. Descends exactly one level
        below each top dir — never deeper.
    """
    result: dict[str, list[Path]] = {}
    specs_real = specs_dir.resolve()
    for top in sorted(p for p in specs_real.iterdir() if p.is_dir()):
        if (top / PIPELINE_STATE_FILENAME).is_file():
            result.setdefault(top.name, []).append(top)  # flat feature
        # Descend one level for nested features (skip epic root, which has no state file).
        for child in sorted(p for p in top.iterdir() if p.is_dir()):
            if (child / PIPELINE_STATE_FILENAME).is_file():
                result.setdefault(child.name, []).append(child)
    return result


def resolve(name: str, specs_dir: Path) -> Path:
    """Resolve a bare feature/epic name to its absolute directory (02 §5).

    Implements the 5-step algorithm (tech-spec §3.4):
      1. reject unsafe names (assert_safe_name) — exit 2 before any FS access;
      2. flat match: {specsDir}/{name}/.pipeline-state.json wins outright;
      3. exactly one nested match resolves cleanly;
      4. more than one match anywhere -> 'ambiguous' (REQ-DIR-04);
      5. zero matches -> 'not-found'.

    Standalone features resolve to their flat path exactly as today, with no
    epic logic engaged (REQ-COMPAT-01/02).

    Args:
        name: Bare feature/epic name from the command line.
        specs_dir: The configured specs directory.

    Returns:
        The resolved, path-contained absolute feature directory.

    Raises:
        UsageError: Unsafe name or missing specs dir (exit 2).
        FindingsError: 'ambiguous' (lists every matching path) or 'not-found'
            (exit 1). 00 §4.2 gives the canonical message shapes.
    """
    assert_safe_name(name)
    if not specs_dir.is_dir():
        raise UsageError(f"specs dir not found: {specs_dir}")

    flat = specs_dir / name
    if (flat / PIPELINE_STATE_FILENAME).is_file():
        return contained_path(specs_dir, name)  # step 2: flat match wins

    matches = feature_dirs(specs_dir).get(name, [])
    if len(matches) == 1:  # step 3
        return contained_path(matches[0].parent, matches[0].name)
    if len(matches) > 1:  # step 4
        joined = " and ".join(str(p) for p in matches)
        raise FindingsError([
            {"code": "ambiguous",
             "message": f"ambiguous name {name!r}: matches {joined}",
             "feature": name}
        ])
    raise FindingsError([  # step 5
        {"code": "not-found",
         "message": f"no feature named {name!r} found under {specs_dir}",
         "feature": name}
    ])


def check_name(name: str, specs_dir: Path) -> list[Finding]:
    """Return a duplicate-name finding if the name is already taken (02 §6.3).

    Used by forge-0-epic before creating a new member feature so no NEW global
    name collision can be introduced (REQ-DIR-04, tech-spec §3.4). Any single
    existing occurrence is enough to reject — unlike ``resolve``, which tolerates
    a uniquely-matching name and only errors on genuine multi-match.

    Args:
        name: The candidate new feature/epic name.
        specs_dir: The configured specs directory.

    Returns:
        A single-element list with a 'duplicate-name' Finding when the name
        already maps to one or more feature-shaped dirs (or to an existing epic
        dir); an empty list when the name is free.

    Raises:
        UsageError: Unsafe name or missing specs dir (exit 2).
    """
    assert_safe_name(name)
    if not specs_dir.is_dir():
        raise UsageError(f"specs dir not found: {specs_dir}")
    existing = feature_dirs(specs_dir).get(name, [])
    # An epic dir (manifest, no state file) with this name also collides.
    epic_dir = specs_dir / name
    if (epic_dir / MANIFEST_FILENAME).is_file():
        existing = [*existing, epic_dir]
    if existing:
        joined = ", ".join(str(p) for p in existing)
        return [{"code": "duplicate-name",
                 "message": f"duplicate feature name {name!r} (also at {joined})",
                 "feature": name}]
    return []


# --------------------------------------------------------------------------- #
# Validation (02 §6.2, §10) — implemented in item 006
# --------------------------------------------------------------------------- #


#: Top-level required keys (00 §2.1, mirrors epic-manifest-schema.json).
_TOP_REQUIRED: Final = (
    "schemaVersion", "epic", "description", "status",
    "narrativeDoc", "createdAt", "updatedAt", "features",
)
#: Required keys on each Feature object (00 §2.2).
_FEATURE_REQUIRED: Final = ("name", "charter", "dependsOn", "exposes", "consumes")
#: Required keys on each Contract (exposes[]) object (00 §2.3).
_CONTRACT_REQUIRED: Final = ("name", "kind", "summary")
#: Required keys on each ConsumedContract (consumes[]) object (00 §2.4).
_CONSUMED_REQUIRED: Final = ("from", "name", "summary")
#: Allowed epic lifecycle states (00 §2.1).
_EPIC_STATUSES: Final = ("active", "paused", "abandoned", "complete")
#: Allowed Contract kinds (00 §2.3).
_CONTRACT_KINDS: Final = ("function", "type", "endpoint", "module", "event")


def _schema(message: str, feature: str | None = None) -> Finding:
    """Construct a 'schema' Finding (00 §4)."""
    return {"code": "schema", "message": message, "feature": feature}


def _schema_findings(manifest: dict) -> list[Finding]:
    """Hand-rolled stdlib schema checker over the manifest (02 §6.2, 00 §2.6).

    Asserts required keys/types/enums/consts from 00 §2 and explicitly rejects
    any ``features[].status`` key (REQ-STATE-02 -> 'cached-status'). No
    third-party ``jsonschema`` (01 §2.1). Returns 'schema' findings plus, for a
    per-feature status key, a 'cached-status' finding.
    """
    findings: list[Finding] = []
    if not isinstance(manifest, dict):
        return [_schema(f"manifest must be a JSON object, got {type(manifest).__name__}")]

    for key in _TOP_REQUIRED:
        if key not in manifest:
            findings.append(_schema(f"missing required key {key!r}"))

    if "schemaVersion" in manifest and manifest["schemaVersion"] != 1:
        findings.append(_schema(f"schemaVersion must be 1, got {manifest['schemaVersion']!r}"))
    if "narrativeDoc" in manifest and manifest["narrativeDoc"] != NARRATIVE_FILENAME:
        findings.append(_schema(f"narrativeDoc must be {NARRATIVE_FILENAME!r}, got {manifest['narrativeDoc']!r}"))
    for key in ("epic", "description", "createdAt", "updatedAt"):
        if key in manifest and not isinstance(manifest[key], str):
            findings.append(_schema(f"{key} must be a string"))
    if "status" in manifest and manifest["status"] not in _EPIC_STATUSES:
        findings.append(_schema(f"status must be one of {list(_EPIC_STATUSES)}, got {manifest['status']!r}"))

    features = manifest.get("features")
    if "features" in manifest and not isinstance(features, list):
        findings.append(_schema("features must be an array"))
        return findings
    if not isinstance(features, list):
        return findings

    for idx, feat in enumerate(features):
        if not isinstance(feat, dict):
            findings.append(_schema(f"features[{idx}] must be an object"))
            continue
        fname = feat.get("name") if isinstance(feat.get("name"), str) else None
        label = fname or f"features[{idx}]"
        if "status" in feat:
            findings.append({
                "code": "cached-status",
                "message": f"feature {label!r} carries a forbidden 'status' key (REQ-STATE-02)",
                "feature": fname,
            })
        for key in _FEATURE_REQUIRED:
            if key not in feat:
                findings.append(_schema(f"feature {label!r} missing required key {key!r}", fname))
        for key in ("name", "charter"):
            if key in feat and not isinstance(feat[key], str):
                findings.append(_schema(f"feature {label!r} {key} must be a string", fname))
        if "dependsOn" in feat:
            if not isinstance(feat["dependsOn"], list) or not all(isinstance(d, str) for d in feat["dependsOn"]):
                findings.append(_schema(f"feature {label!r} dependsOn must be an array of strings", fname))
        for key, required, kind_check in (
            ("exposes", _CONTRACT_REQUIRED, True),
            ("consumes", _CONSUMED_REQUIRED, False),
        ):
            if key not in feat:
                continue
            entries = feat[key]
            if not isinstance(entries, list):
                findings.append(_schema(f"feature {label!r} {key} must be an array", fname))
                continue
            for j, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    findings.append(_schema(f"feature {label!r} {key}[{j}] must be an object", fname))
                    continue
                for rk in required:
                    if rk not in entry:
                        findings.append(_schema(f"feature {label!r} {key}[{j}] missing required key {rk!r}", fname))
                if kind_check and "kind" in entry and entry["kind"] not in _CONTRACT_KINDS:
                    findings.append(_schema(f"feature {label!r} {key}[{j}] kind must be one of {list(_CONTRACT_KINDS)}", fname))
    return findings


def _validate_dict(
    manifest: dict, epic_dir: Path, specs_dir: Path
) -> list[Finding]:
    """Validate an already-parsed manifest dict, returning findings (02 §6.2).

    Runs the invariant checks of 00 §2.6 in order, short-circuiting only where a
    later check cannot run. Reused by the item-008 mutators on the EDITED dict
    before writing. Does not parse JSON (that is ``validate``'s job) — operates
    purely in memory.
    """
    findings: list[Finding] = []

    # (2) schema conformance (incl. cached-status guard).
    findings.extend(_schema_findings(manifest))

    features = manifest.get("features")
    if not isinstance(features, list) or not all(
        isinstance(f, dict) and isinstance(f.get("name"), str) for f in features
    ):
        # Cannot run name/graph checks without well-formed feature names.
        return findings

    names = [f["name"] for f in features]

    # (3) epic + every feature name safe.
    epic_name = manifest.get("epic")
    candidates = ([epic_name] if isinstance(epic_name, str) else []) + names
    for candidate in candidates:
        if not SAFE_NAME_RE.match(candidate):
            findings.append({
                "code": "unsafe-name",
                "message": f"unsafe name {candidate!r}",
                "feature": candidate if candidate in names else None,
            })

    # (3b) names unique within the manifest.
    seen: set[str] = set()
    for n in names:
        if n in seen:
            findings.append({
                "code": "duplicate-name",
                "message": f"duplicate feature name {n!r} within the manifest",
                "feature": n,
            })
        seen.add(n)

    # (4) global name uniqueness across the specs tree.
    if specs_dir.is_dir():
        tree = feature_dirs(specs_dir)
        for n in names:
            dirs = tree.get(n, [])
            if len(dirs) > 1:
                joined = ", ".join(str(p) for p in dirs)
                findings.append({
                    "code": "duplicate-name",
                    "message": f"duplicate feature name {n!r} (maps to {joined})",
                    "feature": n,
                })

    # (5) every dependsOn / consumes.from references a known feature.
    known = set(names)
    for feat in features:
        fname = feat["name"]
        for dep in feat.get("dependsOn", []) or []:
            if isinstance(dep, str) and dep not in known:
                findings.append({
                    "code": "dangling-ref",
                    "message": f"feature {fname!r} dependsOn unknown feature {dep!r}",
                    "feature": fname,
                })
        for entry in feat.get("consumes", []) or []:
            if isinstance(entry, dict):
                src = entry.get("from")
                if isinstance(src, str) and src not in known:
                    findings.append({
                        "code": "dangling-ref",
                        "message": f"feature {fname!r} consumes from unknown feature {src!r}",
                        "feature": fname,
                    })

    # (6) dependsOn graph acyclic (self-dependency surfaces as a cycle).
    cycle = find_cycle(features)
    if cycle is not None:
        findings.append({
            "code": "cycle",
            "message": "cycle: " + " → ".join(cycle),
            "feature": cycle[0],
        })

    return findings


def validate(epic_dir: Path, specs_dir: Path) -> list[Finding]:
    """Validate a single epic manifest, returning all findings (02 §6.2).

    Parses the manifest (folding any corrupt-json finding from load_manifest
    into the returned list) then delegates to ``_validate_dict``. Raises
    UsageError (exit 2) for a missing/unreadable manifest.
    """
    try:
        manifest = load_manifest(epic_dir)
    except FindingsError as exc:
        return list(exc.findings)
    return _validate_dict(manifest, epic_dir, specs_dir)


# --------------------------------------------------------------------------- #
# Live Status Derivation (02 §8) — implemented in item 007
# --------------------------------------------------------------------------- #


def is_complete_for_orchestration(state: dict) -> bool:
    """Apply the completion-for-orchestration predicate (00 §7, 02 §8.1).

    Stub — implemented in backlog item 007.
    """
    raise NotImplementedError


def derive_status(feature_dir: Path) -> FeatureStatus:
    """Derive a feature's live status from its own pipeline state (02 §8).

    Stub — implemented in backlog item 007.
    """
    raise NotImplementedError


def render_status(epic_dir: Path, specs_dir: Path) -> RenderStatus:
    """Build the full live dashboard payload for an epic (02 §8.3).

    Stub — implemented in backlog item 007.
    """
    raise NotImplementedError


# --------------------------------------------------------------------------- #
# Mutators (02 §7) — implemented in item 008
# --------------------------------------------------------------------------- #


def _bump_and_write(
    epic_dir: Path, specs_dir: Path, manifest: dict
) -> list[Finding]:
    """Re-validate, bump updatedAt, and atomically persist a manifest (02 §7).

    Stub — implemented in backlog item 008.
    """
    raise NotImplementedError


def add_feature(
    epic_dir: Path,
    specs_dir: Path,
    name: str,
    charter: str,
    deps: list[str],
) -> list[Finding]:
    """Append a new member feature to the manifest (02 §7.1).

    Stub — implemented in backlog item 008.
    """
    raise NotImplementedError


def remove_feature(epic_dir: Path, specs_dir: Path, name: str) -> list[Finding]:
    """Remove a member feature from the manifest (02 §7.2).

    Stub — implemented in backlog item 008.
    """
    raise NotImplementedError


def reorder(epic_dir: Path, specs_dir: Path, order: list[str]) -> list[Finding]:
    """Reorder the manifest features[] to a given permutation (02 §7.3).

    Stub — implemented in backlog item 008.
    """
    raise NotImplementedError


def set_dep(
    epic_dir: Path, specs_dir: Path, name: str, deps: list[str]
) -> list[Finding]:
    """Replace a member feature's dependsOn list (02 §7.4).

    Stub — implemented in backlog item 008.
    """
    raise NotImplementedError


def set_status(epic_dir: Path, specs_dir: Path, status: str) -> list[Finding]:
    """Set the epic-level lifecycle status (02 §7.5).

    Stub — implemented in backlog item 008.
    """
    raise NotImplementedError


# --------------------------------------------------------------------------- #
# CLI Dispatch (02 §9)
# --------------------------------------------------------------------------- #


def _split_list(value: str | None) -> list[str]:
    """Split a comma-separated CLI argument into a stripped list.

    An empty or absent value yields an empty list (e.g. ``--depends-on ""``
    clears dependencies). Each token is stripped; empty tokens are dropped.
    """
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _emit_findings(findings: list[Finding], as_json: bool) -> None:
    """Print findings as JSON or as one actionable line per finding.

    JSON ({"valid": false, "findings": [...]}) goes to stdout; human-readable
    lines go to stderr (mirroring validate-traceability.py's two output modes).
    """
    if as_json:
        print(json.dumps({"valid": not findings, "findings": findings}, indent=2, ensure_ascii=False))
    else:
        for finding in findings:
            print(f"{finding['code']}: {finding['message']}", file=sys.stderr)


def _dispatch(args: argparse.Namespace, specs_dir: Path) -> int:
    """Route a parsed command to its handler and emit results.

    Subcommand handlers are stubs at this stage (backlog items 004-008 fill
    them in); this dispatch wiring is in place so each command parses cleanly.
    """
    cmd: str = args.cmd

    if cmd == "resolve":
        path = resolve(args.name, specs_dir)
        print(str(path))
        return 0

    if cmd == "check-name":
        findings = check_name(args.name, specs_dir)
        if findings:
            raise FindingsError(findings)
        return 0

    if cmd == "validate":
        epic_dir = contained_path(specs_dir, args.epic)
        findings = validate(epic_dir, specs_dir)
        if findings:
            raise FindingsError(findings)
        if args.json_output:
            print(json.dumps({"valid": True, "findings": []}, indent=2))
        return 0

    if cmd == "render-status":
        epic_dir = contained_path(specs_dir, args.epic)
        status = render_status(epic_dir, specs_dir)
        if args.json_output:
            print(json.dumps(status, indent=2))
        return 0

    # Mutators ---------------------------------------------------------------
    if cmd in {"add-feature", "remove-feature", "reorder", "set-dep", "set-status"}:
        epic_dir = contained_path(specs_dir, args.epic)
        if cmd == "add-feature":
            findings = add_feature(
                epic_dir, specs_dir, args.name, args.charter,
                _split_list(args.depends_on),
            )
        elif cmd == "remove-feature":
            findings = remove_feature(epic_dir, specs_dir, args.name)
        elif cmd == "reorder":
            findings = reorder(epic_dir, specs_dir, _split_list(args.order))
        elif cmd == "set-dep":
            findings = set_dep(
                epic_dir, specs_dir, args.name, _split_list(args.depends_on)
            )
        else:  # set-status
            findings = set_status(epic_dir, specs_dir, args.status)
        if findings:
            raise FindingsError(findings)
        return 0

    raise UsageError(f"unknown command: {cmd}")


def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser with one subparser per subcommand (02 §9)."""
    parser = argparse.ArgumentParser(prog="epic-manifest.py", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_specs_dir(p: argparse.ArgumentParser) -> None:
        p.add_argument("--specs-dir", default="./specs", help="Specs directory")

    # resolve --------------------------------------------------------------- #
    p_resolve = sub.add_parser("resolve", help="Resolve a name to its directory")
    p_resolve.add_argument("name")
    add_specs_dir(p_resolve)

    # validate -------------------------------------------------------------- #
    p_validate = sub.add_parser("validate", help="Validate an epic manifest")
    p_validate.add_argument("epic")
    add_specs_dir(p_validate)
    p_validate.add_argument(
        "--json", action="store_true", dest="json_output", help="Output as JSON"
    )

    # check-name ------------------------------------------------------------ #
    p_check = sub.add_parser("check-name", help="Check global name uniqueness")
    p_check.add_argument("name")
    add_specs_dir(p_check)

    # render-status --------------------------------------------------------- #
    p_render = sub.add_parser("render-status", help="Render the live epic dashboard")
    p_render.add_argument("epic")
    add_specs_dir(p_render)
    p_render.add_argument(
        "--json", action="store_true", dest="json_output", help="Output as JSON"
    )

    # add-feature ----------------------------------------------------------- #
    p_add = sub.add_parser("add-feature", help="Add a member feature")
    p_add.add_argument("epic")
    p_add.add_argument("name")
    p_add.add_argument("--charter", required=True, help="One-paragraph charter")
    p_add.add_argument("--depends-on", dest="depends_on", default="", help="Comma list")
    add_specs_dir(p_add)

    # remove-feature -------------------------------------------------------- #
    p_remove = sub.add_parser("remove-feature", help="Remove a member feature")
    p_remove.add_argument("epic")
    p_remove.add_argument("name")
    add_specs_dir(p_remove)

    # reorder --------------------------------------------------------------- #
    p_reorder = sub.add_parser("reorder", help="Reorder member features")
    p_reorder.add_argument("epic")
    p_reorder.add_argument("--order", required=True, help="Comma-separated permutation")
    add_specs_dir(p_reorder)

    # set-dep --------------------------------------------------------------- #
    p_setdep = sub.add_parser("set-dep", help="Replace a feature's dependsOn")
    p_setdep.add_argument("epic")
    p_setdep.add_argument("name")
    p_setdep.add_argument("--depends-on", dest="depends_on", default="", help="Comma list")
    add_specs_dir(p_setdep)

    # set-status ------------------------------------------------------------ #
    p_setstatus = sub.add_parser("set-status", help="Set the epic lifecycle status")
    p_setstatus.add_argument("epic")
    p_setstatus.add_argument(
        "--status",
        required=True,
        choices=["active", "paused", "abandoned", "complete"],
    )
    add_specs_dir(p_setstatus)

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    specs_dir = Path(args.specs_dir)
    try:
        return _dispatch(args, specs_dir)
    except UsageError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return 2
    except FindingsError as exc:
        _emit_findings(exc.findings, getattr(args, "json_output", False))
        return 1
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
