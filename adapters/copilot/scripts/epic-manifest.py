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
        [--depends-on A,B] [--specs-dir DIR] [--json]
    python3 epic-manifest.py remove-feature <epic> <name> [--specs-dir DIR] [--json]
    python3 epic-manifest.py reorder <epic> --order A,B,C [--specs-dir DIR] [--json]
    python3 epic-manifest.py set-dep <epic> <name> --depends-on A,B [--specs-dir DIR] [--json]
    python3 epic-manifest.py set-status <epic> --status STATE [--specs-dir DIR] [--json]

Exit codes:
    0 = ok / valid / unique / resolved
    1 = findings / validation failure / duplicate / ambiguous / not-found
    2 = usage error or I/O error (missing file, unreadable, unsafe path)
"""

import argparse
import json
import os
import re
import shutil
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
        openEpicChangeRequests: Count of this member's ``epicChangeRequests``
            entries with ``status == "open"`` — epic-level change requests raised
            by a member stage that forge-0-epic edit mode has not yet reconciled.
            0 for standalone features or members with no pending requests.
        blockingEpicChangeRequests: The subset of ``openEpicChangeRequests`` with
            ``blocksCurrent == true`` (pause-now, reconcile-before-specs). Always
            ``<= openEpicChangeRequests``.
    """

    name: str
    stage: str
    status: DerivedStatus
    blocked: bool
    unmetDeps: list[str]
    openEpicChangeRequests: int
    blockingEpicChangeRequests: int


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
            ``resolved path escapes specs dir: …``). Containment violations
            surface only as exit-2 usage errors per the error model in
            tech-spec §6 (there is no dedicated Finding code for them).
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
        # fsync the parent dir so the rename itself is durable on crash, not just
        # the file bytes (best-effort — some filesystems reject O_RDONLY dir fsync).
        try:
            dir_fd = os.open(parent, os.O_RDONLY)
            try:
                os.fsync(dir_fd)
            finally:
                os.close(dir_fd)
        except OSError:
            pass
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
                    # Degenerate self-loop (node == nxt): the while loop body never
                    # runs, yielding ["x", "x"] — the documented self-dependency case.
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
        findings.append(_schema(f"narrativeDoc must be {NARRATIVE_FILENAME!r}, got {manifest['narrativeDoc']!r}"))  # noqa: E501
    for key in ("epic", "description", "createdAt", "updatedAt"):
        if key in manifest and not isinstance(manifest[key], str):
            findings.append(_schema(f"{key} must be a string"))
    for key in ("createdAt", "updatedAt"):
        if isinstance(manifest.get(key), str):
            try:
                # Py3.10's fromisoformat rejects a trailing 'Z'; normalize it first.
                datetime.fromisoformat(manifest[key].replace("Z", "+00:00"))
            except ValueError:
                findings.append(_schema(f"{key} must be an ISO-8601 date-time, got {manifest[key]!r}"))  # noqa: E501
    if "status" in manifest and manifest["status"] not in _EPIC_STATUSES:
        findings.append(_schema(f"status must be one of {list(_EPIC_STATUSES)}, got {manifest['status']!r}"))  # noqa: E501
    for key in manifest:
        if key not in _TOP_REQUIRED:
            findings.append(_schema(f"unknown key {key!r}"))

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
        for key in feat:
            # 'status' is rejected separately above via the dedicated 'cached-status' code.
            if key not in _FEATURE_REQUIRED and key != "status":
                findings.append(_schema(f"feature {label!r} has unknown key {key!r}", fname))
        for key in ("name", "charter"):
            if key in feat and not isinstance(feat[key], str):
                findings.append(_schema(f"feature {label!r} {key} must be a string", fname))
        if "dependsOn" in feat:
            if not isinstance(feat["dependsOn"], list) or not all(isinstance(d, str) for d in feat["dependsOn"]):  # noqa: E501
                findings.append(_schema(f"feature {label!r} dependsOn must be an array of strings", fname))  # noqa: E501
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
                    findings.append(_schema(f"feature {label!r} {key}[{j}] must be an object", fname))  # noqa: E501
                    continue
                for rk in required:
                    if rk not in entry:
                        findings.append(_schema(f"feature {label!r} {key}[{j}] missing required key {rk!r}", fname))  # noqa: E501
                for ek in entry:
                    if ek not in required:
                        findings.append(_schema(f"feature {label!r} {key}[{j}] has unknown key {ek!r}", fname))  # noqa: E501
                if kind_check and "kind" in entry and entry["kind"] not in _CONTRACT_KINDS:
                    findings.append(_schema(f"feature {label!r} {key}[{j}] kind must be one of {list(_CONTRACT_KINDS)}", fname))  # noqa: E501
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
            "message": " → ".join(cycle),
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

    A feature is complete-for-orchestration iff::

        stages['forge-5-loop'].status == 'complete'
        AND ('forge-verify-impl' absent
             OR stages['forge-verify-impl'].status in {'passed', 'findings-applied'})

    A feature whose forge-verify-impl is 'findings-reported' (unfixed) is NOT
    complete and does NOT unblock dependents (REQ-ORCH-01). This is the single
    implementation of the predicate, reused by the dependency gate and handoff
    (04-pipeline-integration.md).

    Args:
        state: A parsed .pipeline-state.json dict (or {} if the member has none).

    Returns:
        True iff the feature is complete for orchestration purposes.
    """
    stages = state.get("stages", {})
    if not isinstance(stages, dict):
        return False
    loop = stages.get("forge-5-loop", {})
    if not isinstance(loop, dict) or loop.get("status") != "complete":
        return False
    impl = stages.get("forge-verify-impl")
    if impl is None:
        return True
    if not isinstance(impl, dict):
        return False
    return impl.get("status") in {"passed", "findings-applied"}


def _read_state_safely(state_path: Path) -> dict:
    """Read and parse a member's .pipeline-state.json, tolerating corruption.

    A missing, unreadable, unparseable, or torn (partially-written) member state
    downgrades to ``{}`` rather than crashing the dashboard (02 §8.2). Member
    state writes are made by forge-1..5 skills outside the helper's atomicity
    scope, so a torn read is expected and simply renders that one feature as
    ``not-started``.
    """
    if not state_path.is_file():
        return {}
    try:
        parsed = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def derive_status(feature_dir: Path) -> FeatureStatus:
    """Derive a feature's live status from its own pipeline state (00 §5, 02 §8).

    Reads ``{feature_dir}/.pipeline-state.json`` and maps it to a FeatureStatus:
    missing/unparseable/all-pending -> ``not-started``; complete-for-
    orchestration -> ``complete``; otherwise ``in-progress``. The ``stage`` field
    is the state's ``currentStage``, defaulting to ``forge-0-epic`` when the
    member dir exists but no stage ran. ``blocked``/``unmetDeps`` are placeholders
    (``False``/``[]``); ``render_status`` overwrites them once it knows the graph.

    Args:
        feature_dir: The member feature's directory.

    Returns:
        A FeatureStatus (00 §5) with name, stage, coarse status, and placeholder
        blocked/unmetDeps.
    """
    name = feature_dir.name
    state = _read_state_safely(feature_dir / PIPELINE_STATE_FILENAME)
    stage = state.get("currentStage") or "forge-0-epic"

    if not state:
        derived: DerivedStatus = "not-started"
    elif is_complete_for_orchestration(state):
        derived = "complete"
    else:
        stages = state.get("stages", {})
        started = isinstance(stages, dict) and any(
            isinstance(entry, dict) and entry.get("status") not in (None, "pending")
            for entry in stages.values()
        )
        derived = "in-progress" if started else "not-started"

    # Epic-backflow surfacing (Phase 2): count open epicChangeRequests from the
    # same state dict. A missing/torn state, a non-list value, or non-dict items
    # count as 0 — a malformed request must never crash the dashboard, mirroring
    # the torn-state -> not-started tolerance above.
    requests = state.get("epicChangeRequests", [])
    open_reqs = [
        r for r in requests
        if isinstance(r, dict) and r.get("status") == "open"
    ] if isinstance(requests, list) else []
    open_count = len(open_reqs)
    blocking_count = sum(1 for r in open_reqs if r.get("blocksCurrent") is True)

    return {
        "name": name,
        "stage": stage,
        "status": derived,
        "blocked": False,
        "unmetDeps": [],
        "openEpicChangeRequests": open_count,
        "blockingEpicChangeRequests": blocking_count,
    }


def _transitive_deps(name: str, adjacency: dict[str, list[str]]) -> set[str]:
    """Return all features reachable from ``name`` via dependsOn edges (00 §8)."""
    seen: set[str] = set()
    stack = list(adjacency.get(name, []))
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(adjacency.get(cur, []))
    return seen


def _next_command(feature_dir: Path, status_row: FeatureStatus) -> str:
    """Recommend the next forge command for an actionable feature (02 §8.3).

    ``/feature-forge:forge-1-prd <name>`` when the feature's PRD is absent (or it
    has not progressed past epic creation), else the command for its next un-run
    stage (its ``currentStage``).
    """
    name = status_row["name"]
    stage = status_row["stage"]
    prd_present = (feature_dir / "PRD.md").is_file()
    if not prd_present or stage in ("forge-0-epic", "forge-1-prd"):
        return f"/feature-forge:forge-1-prd {name}"
    return f"/feature-forge:{stage} {name}"


def render_status(epic_dir: Path, specs_dir: Path) -> RenderStatus:
    """Build the full live dashboard payload for an epic (00 §5, §8; 02 §8.3).

    Validates first (refusing to render over an invalid graph), then derives each
    member's live status from its own state file, computes blocked/unmetDeps,
    actionable, parallelEligible, the rollup, and the recommended next command.

    Args:
        epic_dir: The epic subtree directory.
        specs_dir: The configured specs directory.

    Returns:
        The RenderStatus dict (02 §8.4).

    Raises:
        UsageError: Missing/unreadable manifest (exit 2).
        FindingsError: The manifest fails validation (exit 1).
    """
    # (1) validate first — no dashboard over an invalid graph.
    findings = validate(epic_dir, specs_dir)
    if findings:
        raise FindingsError(findings)

    manifest = load_manifest(epic_dir)
    features = manifest.get("features", [])

    # (2) derive each feature's status and (3) build the completion map.
    rows: list[FeatureStatus] = []
    feature_dir_by_name: dict[str, Path] = {}
    complete: dict[str, bool] = {}
    for feat in features:
        name = feat["name"]
        member_dir = contained_path(epic_dir, name)
        feature_dir_by_name[name] = member_dir
        rows.append(derive_status(member_dir))
        complete[name] = is_complete_for_orchestration(
            _read_state_safely(member_dir / PIPELINE_STATE_FILENAME)
        )

    # (4) per-feature unmetDeps + blocked. A feature that is itself complete is
    #     never "blocked" — unmet deps only matter for work not yet finished.
    for row in rows:
        if complete[row["name"]]:
            row["unmetDeps"] = []
            row["blocked"] = False
            continue
        deps = unmet_deps(row["name"], features, complete)
        row["unmetDeps"] = deps
        row["blocked"] = bool(deps)

    # (5) actionable = unmetDeps empty AND not complete.
    actionable = [
        row["name"]
        for row in rows
        if not row["unmetDeps"] and not complete[row["name"]]
    ]

    # (6) parallelEligible = actionable features with no transitive dependsOn
    #     relationship to any other actionable feature.
    adjacency = {f["name"]: list(f.get("dependsOn", [])) for f in features}
    actionable_set = set(actionable)
    parallel_eligible: list[str] = []
    for name in actionable:
        related = _transitive_deps(name, adjacency)
        others = actionable_set - {name}
        # Eligible iff it neither depends on nor is depended on by another actionable.
        depends_on_other = bool(related & others)
        depended_on = any(name in _transitive_deps(o, adjacency) for o in others)
        if not depends_on_other and not depended_on:
            parallel_eligible.append(name)

    # (7) rollup.
    rollup: Rollup = {
        "complete": sum(1 for v in complete.values() if v),
        "total": len(features),
    }

    # (8) nextCommand for the first actionable feature, else None.
    next_command: str | None = None
    if actionable:
        first = actionable[0]
        first_row = next(r for r in rows if r["name"] == first)
        next_command = _next_command(feature_dir_by_name[first], first_row)

    return {
        "epic": manifest.get("epic", epic_dir.name),
        "status": manifest.get("status", "active"),
        "features": rows,
        "actionable": actionable,
        "parallelEligible": parallel_eligible,
        "rollup": rollup,
        "nextCommand": next_command,
    }


# --------------------------------------------------------------------------- #
# Mutators (02 §7) — implemented in item 008
# --------------------------------------------------------------------------- #


def _bump_and_write(
    epic_dir: Path, specs_dir: Path, manifest: dict
) -> list[Finding]:
    """Re-validate, bump updatedAt, and atomically persist a manifest (02 §7).

    The shared tail of every mutator (REQ-ROBUST-03, REQ-OBS-01, REQ-EPIC-05).
    Re-runs ``_validate_dict`` on the EDITED manifest; if any blocking finding is
    present (cycle, dangling-ref, duplicate-name, schema, ...), the on-disk file
    is left byte-identical and the findings are returned so the caller exits 1.
    Otherwise ``updatedAt`` is set to now (UTC, ISO-8601) and the manifest is
    written via ``atomic_write``.

    Args:
        epic_dir: The epic subtree directory.
        specs_dir: The configured specs directory (for the uniqueness re-check).
        manifest: The already-edited in-memory manifest dict.

    Returns:
        An empty list on success (write performed); the blocking findings on
        refusal (no write performed).

    Raises:
        UsageError: If the atomic write itself fails (exit 2).
    """
    findings = _validate_dict(manifest, epic_dir, specs_dir)
    if findings:
        return findings
    manifest["updatedAt"] = datetime.now(timezone.utc).isoformat()
    atomic_write(epic_dir / MANIFEST_FILENAME, manifest)
    return []


def add_feature(
    epic_dir: Path,
    specs_dir: Path,
    name: str,
    charter: str,
    deps: list[str],
) -> list[Finding]:
    """Append a new member feature to the manifest (02 §7.1).

    Appends a ``Feature`` with the given name/charter/dependsOn and EMPTY
    exposes/consumes. Re-validation surfaces a duplicate name (within the
    manifest or across the tree), an unknown dependency (``dangling-ref``), or a
    cycle, refusing the write in every such case.

    Args:
        epic_dir: The epic subtree directory.
        specs_dir: The configured specs directory.
        name: The new member feature name (already safe-checked by the dispatch).
        charter: The feature charter text.
        deps: The new feature's dependsOn list (already comma-split).

    Returns:
        Empty list on success; blocking findings (duplicate-name / dangling-ref /
        cycle / schema) on refusal — manifest left unchanged.

    Raises:
        UsageError: Unsafe name, corrupt/missing manifest, or write failure.
    """
    for dep in deps:
        assert_safe_name(dep)
    manifest = load_manifest(epic_dir)
    features = manifest.setdefault("features", [])
    features.append({
        "name": name,
        "charter": charter,
        "dependsOn": deps,
        "exposes": [],
        "consumes": [],
    })
    return _bump_and_write(epic_dir, specs_dir, manifest)


def remove_feature(epic_dir: Path, specs_dir: Path, name: str) -> list[Finding]:
    """Remove a member feature from the manifest (02 §7.2).

    Drops the named feature from ``features[]``. After removal, re-validation
    surfaces any now-dangling ``dependsOn`` / ``consumes.from`` that pointed at
    the removed feature; the write is refused in that case so the references can
    be fixed first. A name that is not a member yields a ``not-found`` finding.

    Args:
        epic_dir: The epic subtree directory.
        specs_dir: The configured specs directory.
        name: The member feature to remove.

    Returns:
        Empty list on success; ``not-found`` if the name is not a member, or the
        now-dangling ``dangling-ref`` findings on refusal.

    Raises:
        UsageError: Unsafe name, corrupt/missing manifest, or write failure.
    """
    manifest = load_manifest(epic_dir)
    features = manifest.get("features", [])
    if not any(isinstance(f, dict) and f.get("name") == name for f in features):
        return [{"code": "not-found",
                 "message": f"feature {name!r} is not a member of epic {epic_dir.name!r}",
                 "feature": name}]
    manifest["features"] = [
        f for f in features if not (isinstance(f, dict) and f.get("name") == name)
    ]
    return _bump_and_write(epic_dir, specs_dir, manifest)


def reorder(epic_dir: Path, specs_dir: Path, order: list[str]) -> list[Finding]:
    """Reorder the manifest features[] to a given permutation (02 §7.3).

    ``order`` must be an exact permutation of the current member names (purely a
    display sequence, not a dependency ordering — 00 §2.1). If it is not, a
    ``schema`` finding is returned and the manifest is left unchanged.

    Args:
        epic_dir: The epic subtree directory.
        specs_dir: The configured specs directory.
        order: The desired member-name ordering (already comma-split).

    Returns:
        Empty list on success; a ``schema`` finding when ``order`` is not an exact
        permutation of the current members.

    Raises:
        UsageError: Corrupt/missing manifest or write failure.
    """
    manifest = load_manifest(epic_dir)
    features = manifest.get("features", [])
    by_name = {f["name"]: f for f in features if isinstance(f, dict) and isinstance(f.get("name"), str)}  # noqa: E501
    current = sorted(by_name)
    if sorted(order) != current:
        return [{"code": "schema",
                 "message": f"--order {order} is not an exact permutation of members {sorted(by_name)}",  # noqa: E501
                 "feature": None}]
    manifest["features"] = [by_name[n] for n in order]
    return _bump_and_write(epic_dir, specs_dir, manifest)


def set_dep(
    epic_dir: Path, specs_dir: Path, name: str, deps: list[str]
) -> list[Finding]:
    """Replace a member feature's dependsOn list (02 §7.4, §7.6).

    Re-validation enforces every new dependency exists (``dangling-ref``) and the
    resulting graph is acyclic (``cycle``). An empty ``deps`` clears the
    dependencies.

    Args:
        epic_dir: The epic subtree directory.
        specs_dir: The configured specs directory.
        name: The member feature to edit.
        deps: The new dependsOn list (already comma-split; empty clears deps).

    Returns:
        Empty list on success; blocking findings (dangling-ref / cycle /
        not-found) on refusal — manifest left unchanged.

    Raises:
        UsageError: Unsafe name, corrupt/missing manifest, or write failure.
    """
    for dep in deps:
        assert_safe_name(dep)
    manifest = load_manifest(epic_dir)
    by_name = {
        f["name"]: f
        for f in manifest.get("features", [])
        if isinstance(f, dict) and isinstance(f.get("name"), str)
    }
    if name not in by_name:
        return [{"code": "not-found",
                 "message": f"feature {name!r} is not a member of epic {epic_dir.name!r}",
                 "feature": name}]
    by_name[name]["dependsOn"] = deps
    return _bump_and_write(epic_dir, specs_dir, manifest)


def set_status(epic_dir: Path, specs_dir: Path, status: str) -> list[Finding]:
    """Set the epic-level lifecycle status (02 §7.5).

    Sets the epic-level ``status`` (the value is constrained to the allowed
    lifecycle states by ``argparse`` ``choices`` before reaching here). Never
    touches per-feature status (there is none — REQ-STATE-02).

    Args:
        epic_dir: The epic subtree directory.
        specs_dir: The configured specs directory.
        status: The new epic lifecycle status (already choice-validated).

    Returns:
        Empty list on success; blocking findings if the manifest somehow fails
        re-validation.

    Raises:
        UsageError: Corrupt/missing manifest or write failure.
    """
    manifest = load_manifest(epic_dir)
    manifest["status"] = status
    return _bump_and_write(epic_dir, specs_dir, manifest)


def _load_state_strict(state_path: Path) -> dict:
    """Read a .pipeline-state.json, raising UsageError on a missing/corrupt file.

    Unlike ``_read_state_safely`` (which downgrades a torn read to ``{}`` for the
    read-only dashboard), an adopt mutation must NOT silently discard the
    standalone's stage history — a corrupt source is a hard stop (exit 2) so the
    human fixes it before the irreversible move.
    """
    try:
        parsed = json.loads(state_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise UsageError(f"cannot read {state_path}: {exc}")
    except json.JSONDecodeError as exc:
        raise UsageError(f"{state_path} is not valid JSON: {exc}")
    if not isinstance(parsed, dict):
        raise UsageError(f"{state_path} is not a JSON object")
    return parsed


def _merge_member_state(stub: dict, standalone: dict, epic_name: str) -> dict:
    """Merge a detached standalone's state onto an epic member stub (Issue #126).

    The **stub** is the base — it carries the correct ``epic`` and ``branch``
    back-pointers that the epic minted. The **standalone** holds the real work, so
    its stage history / artifacts / currentStage overlay the stub. The ``epic``
    back-pointer is forced to the target epic; the stub's ``branch`` is preserved
    (only falling back to the standalone's when the stub has none).
    """
    merged = dict(stub)
    for key in ("currentStage", "artifacts", "notes",
                "deferredDecisions", "epicChangeRequests"):
        if key in standalone:
            merged[key] = standalone[key]
    stages = dict(stub.get("stages") or {})
    stages.update(standalone.get("stages") or {})
    merged["stages"] = stages
    merged["epic"] = epic_name
    if not (isinstance(stub.get("branch"), str) and stub["branch"]) and \
            isinstance(standalone.get("branch"), str) and standalone["branch"]:
        merged["branch"] = standalone["branch"]
    return merged


def adopt_feature(
    epic_dir: Path,
    specs_dir: Path,
    feature: str,
    charter: str | None,
    deps: list[str],
) -> dict:
    """Reconcile a detached standalone feature into an epic member (Issue #126).

    The scripted recovery for a **split-brain epic** (#125): a feature that should
    be an epic member was forged as a flat standalone at ``{specsDir}/{feature}/``.
    This relocates it into the member slot ``{epicDir}/{feature}/``, merging state
    so the stub's ``epic``/``branch`` back-pointers survive, removes the flat dir
    (no residual), and adds the feature to the manifest if absent.

    Operates on the CURRENT tree/branch — both the flat standalone and the epic
    manifest must already be present (the human brings a cross-branch standalone
    onto the epic's home branch first, per ``docs/recovery-detached-epic-member.md``;
    EPIC.md prose is regenerated separately via forge-0-epic). Deliberately ordered
    **relocate-then-manifest**: after the flat dir is gone the feature name maps to
    exactly one dir, so ``add_feature``'s global-uniqueness re-validation stays
    clean. Re-entrant — a half-finished run (files moved, manifest not yet updated)
    completes on re-run.

    Args:
        epic_dir: The target epic subtree directory (must hold epic-manifest.json).
        specs_dir: The configured specs directory.
        feature: The detached standalone feature name to adopt.
        charter: Charter for the manifest entry when the feature is not yet a
            member; a default is used when omitted.
        deps: dependsOn for the new manifest entry (ignored if already a member).

    Returns:
        A summary dict (``adopted``/``relocated``/``manifestUpdated``/…) on success.

    Raises:
        UsageError: Unsafe name, missing manifest, nothing to adopt, or an I/O
            failure (exit 2).
        FindingsError: A blocking manifest finding from ``add_feature`` (e.g. an
            unknown dependency) after relocation — exit 1; re-run after fixing.
    """
    assert_safe_name(feature)
    for dep in deps:
        assert_safe_name(dep)

    # The epic manifest must exist on this tree (exit 2 if not — nothing to adopt into).
    load_manifest(epic_dir)

    flat_dir = contained_path(specs_dir, feature)
    member_dir = contained_path(epic_dir, feature)
    if flat_dir == member_dir:
        raise UsageError(f"feature {feature!r} resolves to the epic dir itself")

    flat_state = flat_dir / PIPELINE_STATE_FILENAME
    member_state = member_dir / PIPELINE_STATE_FILENAME
    flat_exists = flat_state.is_file()
    member_exists = member_state.is_file()

    if not flat_exists and not member_exists:
        raise UsageError(
            f"nothing to adopt: neither a standalone {flat_dir} nor a member "
            f"{member_dir} has a {PIPELINE_STATE_FILENAME}"
        )

    relocated = False
    if flat_exists:
        standalone = _load_state_strict(flat_state)
        if member_exists:
            merged = _merge_member_state(
                _read_state_safely(member_state), standalone, epic_dir.name
            )
        else:
            merged = dict(standalone)
            merged["epic"] = epic_dir.name
        # Move every artifact except the state file (merged separately) into the
        # member slot; the standalone (real work) wins on any name collision.
        member_dir.mkdir(parents=True, exist_ok=True)
        for child in sorted(flat_dir.iterdir()):
            if child.name == PIPELINE_STATE_FILENAME:
                continue
            dest = member_dir / child.name
            if dest.is_dir():
                shutil.rmtree(dest)
            elif dest.exists():
                dest.unlink()
            shutil.move(str(child), str(dest))
        atomic_write(member_state, merged)
        shutil.rmtree(flat_dir)
        relocated = True
    else:
        # Already nested (a prior run moved the files) — only ensure the back-pointer.
        stub = _read_state_safely(member_state)
        if stub.get("epic") != epic_dir.name:
            stub["epic"] = epic_dir.name
            atomic_write(member_state, stub)

    # Ensure the feature is a manifest member (idempotent — the flat dir is gone now,
    # so add_feature's tree-uniqueness re-check sees exactly one dir for the name).
    manifest = load_manifest(epic_dir)
    already_member = any(
        isinstance(f, dict) and f.get("name") == feature
        for f in manifest.get("features", [])
    )
    manifest_updated = False
    if not already_member:
        findings = add_feature(
            epic_dir, specs_dir, feature,
            charter or f"Adopted into the {epic_dir.name} epic from a detached standalone.",
            deps,
        )
        if findings:
            raise FindingsError(findings)
        manifest_updated = True

    return {
        "adopted": True,
        "epic": epic_dir.name,
        "feature": feature,
        "memberDir": str(member_dir),
        "relocated": relocated,
        "manifestUpdated": manifest_updated,
        "wasAlreadyMember": already_member,
        "nextSteps": [
            f"Regenerate EPIC.md prose via /feature-forge:forge-0-epic {epic_dir.name}",
            f"Confirm the dashboard via /feature-forge:forge {epic_dir.name}",
            f"Verify the member via /feature-forge:forge-verify {feature}",
            "Commit the surgery (stage the epic subtree and the removed flat dir).",
        ],
    }


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
        print(json.dumps({"valid": not findings, "findings": findings}, indent=2, ensure_ascii=False))  # noqa: E501
    else:
        for finding in findings:
            print(f"{finding['code']}: {finding['message']}", file=sys.stderr)


def _print_status_table(status: RenderStatus) -> None:
    """Print a readable epic dashboard plus the recommended next command (02 §8)."""
    rollup = status["rollup"]
    print(f"Epic: {status['epic']}  [{status['status']}]")
    print(f"Progress: {rollup['complete']}/{rollup['total']} complete")
    if not status["features"]:
        print("  (no features — add features to begin)")
    for row in status["features"]:
        line = f"  - {row['name']}: {row['status']} (stage {row['stage']})"
        if row["blocked"]:
            line += f" — blocked on {', '.join(row['unmetDeps'])}"
        if row["openEpicChangeRequests"]:
            marker = "⚠️ BLOCKING" if row["blockingEpicChangeRequests"] else "⚠️"
            line += f" — {marker} {row['openEpicChangeRequests']} pending epic change(s)"
        print(line)
    if status["actionable"]:
        print(f"Actionable: {', '.join(status['actionable'])}")
    if status["parallelEligible"]:
        print(f"Parallel-eligible: {', '.join(status['parallelEligible'])}")
    if status["nextCommand"]:
        print(f"Next: {status['nextCommand']}")


def _dispatch(args: argparse.Namespace, specs_dir: Path) -> int:
    """Route a parsed command to its handler, translating return/raise into exit codes.

    Read-only commands (resolve / check-name / validate / render-status) print to
    stdout and return 0; mutators return findings the caller raises as a
    ``FindingsError`` (exit 1). Unknown commands raise ``UsageError`` (exit 2).
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
        else:
            _print_status_table(status)
        return 0

    if cmd == "adopt-feature":
        epic_dir = contained_path(specs_dir, args.epic)
        summary = adopt_feature(
            epic_dir, specs_dir, args.name, args.charter,
            _split_list(args.depends_on),
        )
        if args.json_output:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
        else:
            print(f"Adopted {summary['feature']!r} into epic {summary['epic']!r}.")
            print(f"  member dir:      {summary['memberDir']}")
            print(f"  relocated files: {summary['relocated']}")
            print(f"  manifest added:  {summary['manifestUpdated']}"
                  f"{' (already a member)' if summary['wasAlreadyMember'] else ''}")
            print("Next steps:")
            for step in summary["nextSteps"]:
                print(f"  - {step}")
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

    def add_json(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--json", action="store_true", dest="json_output", help="Output as JSON"
        )

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
    add_json(p_add)

    # adopt-feature --------------------------------------------------------- #
    p_adopt = sub.add_parser(
        "adopt-feature",
        help="Reconcile a detached standalone feature into an epic member (#126)",
    )
    p_adopt.add_argument("epic")
    p_adopt.add_argument("name")
    p_adopt.add_argument(
        "--charter", default=None,
        help="Charter for the manifest entry when the feature is not yet a member",
    )
    p_adopt.add_argument("--depends-on", dest="depends_on", default="", help="Comma list")
    add_specs_dir(p_adopt)
    add_json(p_adopt)

    # remove-feature -------------------------------------------------------- #
    p_remove = sub.add_parser("remove-feature", help="Remove a member feature")
    p_remove.add_argument("epic")
    p_remove.add_argument("name")
    add_specs_dir(p_remove)
    add_json(p_remove)

    # reorder --------------------------------------------------------------- #
    p_reorder = sub.add_parser("reorder", help="Reorder member features")
    p_reorder.add_argument("epic")
    p_reorder.add_argument("--order", required=True, help="Comma-separated permutation")
    add_specs_dir(p_reorder)
    add_json(p_reorder)

    # set-dep --------------------------------------------------------------- #
    p_setdep = sub.add_parser("set-dep", help="Replace a feature's dependsOn")
    p_setdep.add_argument("epic")
    p_setdep.add_argument("name")
    p_setdep.add_argument("--depends-on", dest="depends_on", default="", help="Comma list")
    add_specs_dir(p_setdep)
    add_json(p_setdep)

    # set-status ------------------------------------------------------------ #
    p_setstatus = sub.add_parser("set-status", help="Set the epic lifecycle status")
    p_setstatus.add_argument("epic")
    p_setstatus.add_argument(
        "--status",
        required=True,
        choices=["active", "paused", "abandoned", "complete"],
    )
    add_specs_dir(p_setstatus)
    add_json(p_setstatus)

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
