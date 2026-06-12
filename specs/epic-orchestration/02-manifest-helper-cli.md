# 02 — Manifest Helper CLI (`scripts/epic-manifest.py`)

> The deterministic read/validate/write engine for the epic manifest. A single
> stdlib-only Python 3.10+ CLI, invoked by every stage skill via `Bash`, that owns
> acyclicity checking (REQ-EPIC-05), corrupt-manifest validation (REQ-ROBUST-02),
> atomic writes (REQ-ROBUST-03), global name uniqueness (REQ-DIR-04), path containment
> (REQ-SEC-02), name→directory resolution (REQ-DIR-03), and live status derivation
> (REQ-STATE-02). Skills never eyeball a dependency graph for cycles — they shell out to
> this helper and surface its findings verbatim.
>
> This document builds on **00-core-definitions.md** (shared types, finding taxonomy,
> safety constants, completion rule, derived sets, exit codes, manifest schema) and
> **01-architecture-layout.md §3** (module skeleton). It does **not** redefine those
> shared types; it references them by section and fleshes out the full function
> signatures and algorithms. Its style, `argparse` pattern, exit-code handling, and
> `--json` convention mirror `scripts/validate-traceability.py` exactly.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-EPIC-05 | Dependency graph validated acyclic at creation and after every modification | 4 (`find_cycle`), 6.2 (`validate`), 7 (mutators re-validate) |
| REQ-DIR-03 | Resolve a bare feature name regardless of nesting (flat + nested) | 5, 6.1 (`resolve`) |
| REQ-DIR-04 | Globally unique feature names; duplicate creation rejected | 5 (`feature_dirs`), 6.1, 6.3 (`check-name`), 7.1 (`add-feature`) |
| REQ-STATE-01 | Manifest canonical; conflict resolution | 8 (`derive_status` reads state), 6.2 |
| REQ-STATE-02 | No cached per-feature status; derived live at read time | 8 (`derive_status`, `render-status`), 6.2 (rejects `status` field) |
| REQ-ORCH-01 | Completion-for-orchestration rule | 8.1 (`is_complete_for_orchestration`) |
| REQ-ORCH-03 | Actionable / parallel-eligible derived sets | 8.3 (`render_status`), 6.4 |
| REQ-ORCH-05 | Epic lifecycle `status` field maintained | 7.6 (`set-status`) |
| REQ-ROBUST-01 | Reconstruct from disk; correct + <1s at 20 features | 4 (O(V+E)), 8.4, 11 (Verification) |
| REQ-ROBUST-02 | Corrupt/hand-edited manifest → actionable findings | 3.2 (`load_manifest`), 6.2 (`validate`) |
| REQ-ROBUST-03 | Atomic writes (temp file + `os.replace`) | 3.3 (`atomic_write`), 7 (all mutators) |
| REQ-SEC-02 | Name/path containment within `{specsDir}` | 3.1 (`assert_safe_name`, `contained_path`), 5, 6 |
| REQ-OBS-01 | `updatedAt` bumped on every mutation | 7 (all mutators), 7.7 (`_bump_and_write`) |
| REQ-COMPAT-01/02 | Standalone features resolve exactly as today; no migration | 5 (flat-match precedence), 6.1 |

---

## 1. Overview & Invocation

`scripts/epic-manifest.py` is a single self-contained module organized exactly like
`scripts/validate-traceability.py`: a module docstring with usage + exit codes, module
constants, small pure functions, then an `argparse` dispatch in `main()` guarded by
`if __name__ == "__main__": sys.exit(main())`.

Skills invoke it through the established plugin-root convention
(01-architecture-layout.md §2.2):

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" <subcommand> [args] --specs-dir "<specsDir>"
```

**Subcommands** (tech-spec §2.3): `resolve`, `validate`, `check-name`, `render-status`,
`add-feature`, `remove-feature`, `reorder`, `set-dep`, `set-status`.

**Exit codes** (00-core-definitions.md §9, mirrored from `validate-traceability.py`):

| Exit | Meaning |
|------|---------|
| `0` | ok / valid / unique / resolved |
| `1` | findings / validation failure / duplicate / ambiguous / not-found |
| `2` | usage error or I/O error (missing file, unreadable, unsafe path before FS access) |

`--json` (where supported) prints a single JSON object to stdout, mirroring
`validate-traceability.py`'s `--json` flag. Human-readable mode prints actionable lines.
All error/diagnostic text goes to `stderr`; the resolved value or JSON payload goes to
`stdout`, so a caller can capture `stdout` cleanly (e.g. `DIR="$(python3 … resolve …)"`).

### 1.1 Module preamble

```python
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
    python3 epic-manifest.py add-feature <epic> <name> --charter TEXT \\
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
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Literal, TypedDict
```

The `Finding`, `FindingCode`, `FeatureStatus`, and `DerivedStatus` types are defined in
**00-core-definitions.md §4 and §5**; the module re-states them verbatim (they are
single-file `TypedDict`s, not imported across modules — 01-architecture-layout.md §5).
The safety constants `SAFE_NAME_RE`, `PIPELINE_STATE_FILENAME`, `MANIFEST_FILENAME`,
`NARRATIVE_FILENAME` are defined in **00-core-definitions.md §6** and likewise re-stated.

---

## 2. Internal Exceptions

Two module-private exceptions carry the exit-code intent up to `main()`, so subcommand
functions can `raise` and a single handler maps them to exit codes. This keeps each
subcommand readable and centralizes the I/O-vs-finding distinction (tech-spec §6).

```python
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
```

`main()` wraps the dispatch in `try/except`: `UsageError` → print to stderr, return `2`;
`FindingsError` → emit findings (JSON or lines), return `1`; any uncaught `OSError` →
print and return `2`. This mirrors `validate-traceability.py`'s practice of returning `2`
for read errors and `1` for findings.

---

## 3. Safety & I/O Layer

### 3.1 Name & path safety (REQ-SEC-02)

Every name/path is checked **before** any filesystem access, using the constants from
00-core-definitions.md §6.

```python
#: A safe feature/epic name: one kebab-case token (00 §6).
SAFE_NAME_RE: Final = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
PIPELINE_STATE_FILENAME: Final = ".pipeline-state.json"
MANIFEST_FILENAME: Final = "epic-manifest.json"
NARRATIVE_FILENAME: Final = "EPIC.md"


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
```

### 3.2 Manifest load (REQ-ROBUST-02)

```python
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
```

### 3.3 Atomic write (REQ-ROBUST-03)

```python
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
```

---

## 4. Graph Algorithms (REQ-EPIC-05, REQ-ROBUST-01)

Acyclicity uses an iterative DFS with a recursion-stack (gray/black) coloring, returning
the **cycle path** for the `cycle` Finding's message. Complexity is `O(V+E)`; at the
REQ-ROBUST-01 ceiling of 20 features the runtime is sub-millisecond — comfortably inside
the <1s interactive target.

```python
def find_cycle(features: list[dict]) -> list[str] | None:
    """Return a cycle in the dependsOn graph, or None if acyclic.

    Performs an iterative depth-first search over the directed graph whose edges
    are ``feature -> dep`` for each dep in ``dependsOn``. On the first back-edge
    into a node on the current DFS stack, reconstructs and returns the cycle as
    an ordered list of names ending where it began (e.g.
    ``["a", "b", "a"]``), which the caller formats as ``cycle: a -> b -> a``.

    Only edges to names that exist in ``features`` are traversed; dangling refs
    are reported separately by ``validate`` so a cycle finding is never masked
    by (or confused with) a typo'd dependency.

    A self-dependency (a feature whose ``dependsOn`` lists its own ``name``) is a
    degenerate self-loop: the root is colored GRAY on push, the self-edge is seen
    as a back-edge into a GRAY node, and the reconstructed path is ``["X", "X"]``
    (formatted ``cycle: X -> X``). It is reported as an ordinary ``cycle`` finding
    (00 §2.6 invariant 5), not a separate code.

    Args:
        features: The manifest's ``features`` array (each a dict with ``name``
            and ``dependsOn``).

    Returns:
        The cycle path including the repeated start node, or None when the graph
        is acyclic. O(V+E) — trivially <1s for <=20 nodes (REQ-ROBUST-01).
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
    """Return the direct dependencies of a feature that are not yet complete.

    Args:
        name: The feature whose dependencies are checked.
        features: The manifest ``features`` array.
        complete: Map of feature name -> complete-for-orchestration (00 §7),
            as produced by render_status (§8).

    Returns:
        The names of this feature's direct ``dependsOn`` entries whose value in
        ``complete`` is False, preserving manifest order. Empty when the feature
        is actionable or itself complete (REQ-ORCH-03/04).
    """
    by_name = {f["name"]: f for f in features}
    feature = by_name.get(name, {})
    return [dep for dep in feature.get("dependsOn", []) if not complete.get(dep, False)]
```

---

## 5. Resolution & Uniqueness (REQ-DIR-03/04, REQ-SEC-02, REQ-COMPAT-01/02)

Resolution implements the tech-spec §3.4 five-step algorithm, bounded to **feature-shaped
directories** — directories that *directly* contain `.pipeline-state.json` (00 §6).
Non-feature subtrees (`.verification/`, `tests/`, fixture dirs) are never matched.

```python
def feature_dirs(specs_dir: Path) -> dict[str, list[Path]]:
    """Map every feature name in the specs tree to the dirs that bear it.

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
        single-entry list means the name is unique. O(number of dirs); bounded
        to two levels, well under the <1s target for <=20 features.
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
    """Resolve a bare feature/epic name to its absolute directory.

    Implements the 5-step algorithm (tech-spec §3.4):
      1. reject unsafe names (assert_safe_name) — exit 2 before any FS access;
      2. flat match: {specsDir}/{name}/.pipeline-state.json wins outright;
      3. exactly one nested match resolves cleanly;
      4. more than one match anywhere -> 'ambiguous' (REQ-DIR-04);
      5. zero matches -> 'not-found'.

    Standalone features resolve to their flat path exactly as today, with no
    epic logic engaged (REQ-COMPAT-01/02). Pre-existing-collision nuance: this
    function reports ambiguity ONLY on a genuine multi-match; a name matching
    exactly one dir always resolves, so a latent duplicate elsewhere in the tree
    never breaks an unrelated, uniquely-named command (tech-spec §3.4). Newly
    *introducing* a collision is blocked separately by ``check-name`` (§6.3).

    Args:
        name: Bare feature/epic name from the command line.
        specs_dir: The configured specs directory.

    Returns:
        The resolved, path-contained absolute feature directory.

    Raises:
        UsageError: Unsafe name (exit 2).
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
    if len(matches) == 1:
        return contained_path(matches[0].parent, matches[0].name)  # step 3
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
```

---

## 6. Read-Only Subcommands

### 6.1 `resolve` (REQ-DIR-03/04, REQ-SEC-02)

**Purpose.** Resolve a bare feature/epic name → absolute directory, handling flat +
nested, enforcing uniqueness and path containment. Called by every stage skill before any
file I/O (tech-spec §5.1).

**CLI.** `resolve <name> [--specs-dir DIR]`. No `--json`: on success it prints the single
absolute directory to **stdout** (so `DIR="$(… resolve x)"` works); on failure it prints
the finding to stderr and exits 1/2.

**Algorithm.** Delegates to `resolve()` (§5). Success: `print(str(dir))`, return 0.

**Exit codes.** 0 resolved; 1 `ambiguous`/`not-found`; 2 `unsafe-name`/missing specs dir.

**Findings emitted.** `ambiguous`, `not-found` (exit 1); `unsafe-name`, `path-escape`
surfaced as exit-2 usage errors.

### 6.2 `validate` (REQ-EPIC-05, REQ-ROBUST-02, REQ-STATE-02, REQ-SEC-02, REQ-DIR-04)

**Purpose.** Full structural validation of one epic's manifest: JSON parse → schema
conformance → name safety/uniqueness → dangling-ref detection → acyclicity → no cached
per-feature `status`. Backs `forge-verify` epic-mode checks E01/E02/E03/E08 (tech-spec
§5.5).

**CLI.** `validate <epic> [--specs-dir DIR] [--json]`. `--json` prints
`{ "valid": bool, "findings": [...] }` (the `findings[]` array is `Finding` objects per
00 §4); human mode prints one line per finding then a summary, in the same spirit as
`validate-traceability.py`.

```python
def validate(epic_dir: Path, specs_dir: Path) -> list[Finding]:
    """Validate a single epic manifest, returning all findings (00 §2.6).

    Runs the invariant checks in order, short-circuiting only where a later
    check cannot run (e.g. a corrupt-json manifest can't be schema-checked):
      1. parse (load_manifest -> corrupt-json on failure);
      2. schema conformance against references/epic-manifest-schema.json
         (-> 'schema' findings), including the explicit rule that NO feature
         carries a 'status' key (-> 'cached-status', REQ-STATE-02);
      3. epic + every feature name safe (SAFE_NAME_RE) (-> 'unsafe-name');
      4. global name uniqueness across the specs tree via feature_dirs
         (-> 'duplicate-name', REQ-DIR-04);
      5. every dependsOn and consumes.from references a known feature
         (-> 'dangling-ref', REQ-ROBUST-02);
      6. dependsOn graph acyclic via find_cycle (-> 'cycle', REQ-EPIC-05). This
         includes self-dependencies: a feature listing its own name in dependsOn
         is a degenerate self-loop that find_cycle returns as ["X", "X"]
         (-> 'cycle', message `cycle: X → X`; 00 §2.6 invariant 5).

    Args:
        epic_dir: The epic subtree directory.
        specs_dir: The configured specs directory (for the uniqueness scan).

    Returns:
        A list of Findings (00 §4). Empty list means the manifest is valid.

    Raises:
        UsageError: Manifest missing/unreadable, or schema file unavailable
            (exit 2). A corrupt-json manifest is returned as a Finding (via the
            FindingsError from load_manifest), not raised here.
    """
    ...
```

The driver catches `FindingsError` from `load_manifest` and folds its `corrupt-json`
finding into the returned list, so `validate` always yields a complete `findings[]` for
the JSON contract. Schema validation is performed with a small hand-rolled checker over
`references/epic-manifest-schema.json` (stdlib only — no `jsonschema` dependency,
matching the no-third-party rule of 01-architecture-layout.md §2.1): it asserts required
keys/types/enums from 00 §2 and explicitly rejects any `features[].status` key.

**Exit codes.** 0 valid (empty findings); 1 any finding; 2 missing/unreadable manifest or
schema file.

**Findings emitted.** `corrupt-json`, `schema`, `cached-status`, `unsafe-name`,
`duplicate-name`, `dangling-ref`, `cycle`.

**Example (`--json`, a cyclic manifest):**

```json
{
  "valid": false,
  "findings": [
    { "code": "cycle",
      "message": "cycle: token-service → api-gateway → token-service",
      "feature": "token-service" }
  ]
}
```

### 6.3 `check-name` (REQ-DIR-04)

**Purpose.** Reject a name that already exists **anywhere** in the specs tree (flat or
nested) before `forge-0-epic` creates a new member. This is the hard gate that prevents a
**new** collision from being introduced (tech-spec §3.4), distinct from `resolve`'s
softer "only error on genuine multi-match" behavior for pre-existing trees.

**CLI.** `check-name <name> [--specs-dir DIR]`. No `--json`. Exit 0 = unique; exit 1 =
duplicate (prints a `duplicate-name` finding line listing the existing path(s)).

```python
def check_name(name: str, specs_dir: Path) -> list[Finding]:
    """Return a duplicate-name finding if the name is already taken, else [].

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
```

**Exit codes.** 0 unique; 1 duplicate; 2 unsafe name/missing specs dir.
**Findings emitted.** `duplicate-name`.

### 6.4 `render-status` (REQ-STATE-02, REQ-ORCH-01/03, REQ-VIS-01)

**Purpose.** Produce the live epic dashboard payload: per-feature derived status, blocked
vs actionable sets, parallel-eligible set, rollup, and recommended next command. Backs the
navigator dashboard (tech-spec §5.4), the loop dependency gate, and the handoff. Full
algorithm in §8.

**CLI.** `render-status <epic> [--specs-dir DIR] [--json]`. `--json` prints the §8.4
object. Human mode prints a readable table plus the next command.

**Exit codes.** 0 on success (even when features are blocked — blocked-ness is data, not a
failure); 1 only if the manifest is invalid (it runs `validate` first and refuses to
render an unvalidated graph); 2 missing/unreadable manifest.

**Findings emitted.** Re-emits any `validate` findings (so a corrupt manifest can't yield
a misleading dashboard).

---

## 7. Mutator Subcommands (REQ-ROBUST-03, REQ-OBS-01, REQ-EPIC-05)

Every mutator follows the same envelope (the heart of REQ-ROBUST-03 + REQ-OBS-01):

1. `assert_safe_name` on every name argument (REQ-SEC-02).
2. `load_manifest` (corrupt → exit 1 before any change).
3. Apply the in-memory edit to the parsed dict.
4. **Re-validate the edited manifest** via `validate`-equivalent invariant checks
   (acyclicity + dangling-ref + uniqueness + schema). **Refuse the write** (return the
   findings, exit 1, leave the file untouched) if the edit would introduce a cycle or a
   dangling ref (tech-spec §3.1, §3.7).
5. Bump `updatedAt` to the current ISO-8601 UTC timestamp (REQ-OBS-01).
6. `atomic_write` (temp file + `os.replace`, REQ-ROBUST-03).

This envelope is factored into one helper so each mutator is a thin edit + call:

```python
def _bump_and_write(epic_dir: Path, specs_dir: Path, manifest: dict) -> list[Finding]:
    """Re-validate an edited manifest, bump updatedAt, and atomically persist.

    The shared tail of every mutator (REQ-ROBUST-03, REQ-OBS-01, REQ-EPIC-05).
    Re-runs the structural invariant checks on the EDITED manifest; if any
    blocking finding is present (cycle, dangling-ref, duplicate-name, schema),
    the on-disk file is left untouched and the findings are returned so the
    caller exits 1. Otherwise ``updatedAt`` is set to now (UTC, ISO-8601) and the
    manifest is written via atomic_write.

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
```

(`_validate_dict` is the in-memory core shared with §6.2 `validate`, operating on an
already-parsed dict so re-validation skips the parse step.)

### 7.1 `add-feature` (REQ-DIR-04, REQ-EPIC-05, REQ-ROBUST-03)

**CLI.** `add-feature <epic> <name> --charter TEXT [--depends-on A,B] [--specs-dir DIR]`.
Appends a new `Feature` (`name`, `charter`, `dependsOn`, empty `exposes`/`consumes`) to
`features[]`. The caller (`forge-0-epic`) is expected to have already run `check-name`;
`add-feature` additionally re-validates uniqueness within the manifest and that every
`--depends-on` entry already exists (else `dangling-ref`), and that the addition keeps the
graph acyclic. **Exit codes:** 0 written; 1 duplicate-in-manifest / dangling-ref / cycle
(no write); 2 unsafe name / corrupt manifest / I/O. **Findings:** `duplicate-name`,
`dangling-ref`, `cycle`, `unsafe-name`.

### 7.2 `remove-feature` (REQ-ROBUST-03)

**CLI.** `remove-feature <epic> <name> [--specs-dir DIR]`. Removes the named feature from
`features[]`. After removal, re-validation will surface any **now-dangling** `dependsOn`
or `consumes.from` that pointed at the removed feature; the mutator refuses the write and
returns those `dangling-ref` findings so the caller can fix the references first (the
edit-mode skill warns the user, tech-spec §3.7). Member-subdirectory disposition is the
skill's concern (open question, tech-spec §9), not the helper's. **Exit:** 0 / 1
(dangling-ref, or `not-found` if the name isn't a member) / 2. **Findings:** `dangling-ref`,
`not-found`, `unsafe-name`.

### 7.3 `reorder` (REQ-EPIC-06 support, REQ-ROBUST-03)

**CLI.** `reorder <epic> --order A,B,C [--specs-dir DIR]`. Reorders `features[]` to the
given permutation of existing names. The order is purely the user-declared display
sequence — **not** a dependency ordering (00 §2.1) — so no graph re-derivation is needed,
but re-validation still runs. Refuses if `--order` is not an exact permutation of current
member names (a `schema`/`not-found` finding). **Exit:** 0 / 1 / 2.

### 7.4 `set-dep` (REQ-EPIC-05/06, REQ-ROBUST-03)

**CLI.** `set-dep <epic> <name> --depends-on A,B [--specs-dir DIR]`. Replaces the named
feature's `dependsOn` array. Re-validation enforces every new dep exists (`dangling-ref`)
and the resulting graph is acyclic (`cycle`) — the core REQ-EPIC-05 guard "validated
acyclic after every modification." A `--depends-on ""` clears the deps. **Exit:** 0 / 1
(dangling-ref/cycle, no write) / 2. **Findings:** `dangling-ref`, `cycle`, `not-found`,
`unsafe-name`.

### 7.5 `set-status` (REQ-ORCH-05, REQ-ROBUST-03)

**CLI.** `set-status <epic> --status STATE [--specs-dir DIR]` where `STATE ∈ {active,
paused, abandoned, complete}` (00 §2). Sets the **epic-level** `status` (lifecycle verbs
from the navigator, tech-spec §5.4). Rejects any other value with an `argparse` `choices`
error (exit 2). This never touches per-feature status (there is none — REQ-STATE-02).
**Exit:** 0 / 1 (if the resulting manifest somehow fails re-validation) / 2 (bad value /
corrupt manifest). **Findings:** none specific beyond re-validation.

### 7.6 Mutator example (`set-dep`)

```python
def set_dep(epic_dir: Path, specs_dir: Path, name: str, deps: list[str]) -> list[Finding]:
    """Replace a member feature's dependsOn list, atomically and validated.

    Args:
        epic_dir: The epic subtree directory.
        specs_dir: The configured specs directory.
        name: The member feature to edit.
        deps: The new dependsOn list (already split from the comma CLI arg;
            empty list clears dependencies).

    Returns:
        Empty list on success; blocking findings (dangling-ref / cycle /
        not-found) on refusal — in which case the manifest is left unchanged.

    Raises:
        UsageError: Unsafe name, corrupt/missing manifest, or write failure.
    """
    for dep in deps:
        assert_safe_name(dep)
    manifest = load_manifest(epic_dir)
    by_name = {f["name"]: f for f in manifest["features"]}
    if name not in by_name:
        return [{"code": "not-found",
                 "message": f"feature {name!r} is not a member of epic {epic_dir.name!r}",
                 "feature": name}]
    by_name[name]["dependsOn"] = deps
    return _bump_and_write(epic_dir, specs_dir, manifest)
```

---

## 8. Live Status Derivation (REQ-STATE-02, REQ-ORCH-01/03)

`render-status` opens each member's own `.pipeline-state.json` on **every** read and
derives status live — there is nothing cached to refresh (tech-spec §3.3), satisfying the
PRD acceptance test (edit a state file, re-render, see the change).

### 8.1 Completion predicate (REQ-ORCH-01, 00 §7)

```python
def is_complete_for_orchestration(state: dict) -> bool:
    """Apply the single completion-for-orchestration predicate (00 §7).

    A feature is complete-for-orchestration iff:
        stages['forge-5-loop'].status == 'complete'
        AND ('forge-verify-impl' absent
             OR stages['forge-verify-impl'].status in {'passed', 'findings-applied'})

    A feature whose forge-verify-impl is 'findings-reported' (unfixed) is NOT
    complete and does NOT unblock dependents (REQ-ORCH-01). Implemented ONCE here
    and reused by the dependency gate and handoff (04-pipeline-integration.md).

    Args:
        state: A parsed .pipeline-state.json dict (or {} if the member has none).

    Returns:
        True iff the feature is complete for orchestration purposes.
    """
    stages = state.get("stages", {})
    loop = stages.get("forge-5-loop", {})
    if loop.get("status") != "complete":
        return False
    impl = stages.get("forge-verify-impl")
    if impl is None:
        return True
    return impl.get("status") in {"passed", "findings-applied"}


def derive_status(feature_dir: Path) -> FeatureStatus:
    """Derive a feature's live status from its own pipeline state (00 §5).

    Reads ``{feature_dir}/.pipeline-state.json`` and maps it to a FeatureStatus.
    A missing/unparseable state file yields ``not-started`` (the member dir may
    have been created empty at epic creation). ``blocked``/``unmetDeps`` are
    filled in by render_status, which alone knows the dependency graph; this
    function sets them to ``False``/``[]`` and lets the caller overwrite them.

    Args:
        feature_dir: The member feature's directory.

    Returns:
        A FeatureStatus (00 §5) with name, stage, coarse status, and placeholder
        blocked/unmetDeps.
    """
    ...
```

`derive_status` maps to `DerivedStatus` (00 §5): no/empty state → `not-started`; complete-
for-orchestration → `complete`; otherwise `in-progress`. The `stage` field is the state's
`currentStage`, defaulting to `forge-0-epic` when the member dir exists but no stage ran
(00 §5).

### 8.2 Reading member state safely

Each member's state path is built with `contained_path(epic_dir, feature_name,
PIPELINE_STATE_FILENAME)` (REQ-SEC-02), then parsed with a try/except that downgrades a
corrupt or missing member state to `not-started` rather than crashing the whole dashboard
(per-feature corruption must not blind the navigator to the rest of the epic). This same
downgrade also tolerates a **torn read** of a member state file written concurrently by
another stage skill: member `.pipeline-state.json` writes are made by forge-1..5 skills the
helper does not control and are **outside** the helper's atomicity scope (REQ-ROBUST-03
covers only the helper's own manifest writes). A partially-written member state simply
parses as corrupt → `not-started` for that one render, with no effect on the rest of the
dashboard and no crash. On the manifest-vs-back-pointer conflict (REQ-STATE-01) the
manifest wins: members listed in the manifest are always rendered; a back-pointer mismatch
is left for `forge-verify` CHECK-E07.

### 8.3 Derived sets (REQ-ORCH-03, 00 §8)

```python
def render_status(epic_dir: Path, specs_dir: Path) -> RenderStatus:
    """Build the full live dashboard payload for an epic (00 §5, §8; §8.4 here).

    Steps:
      1. validate(epic_dir, specs_dir); if findings, raise FindingsError (a
         dashboard over an invalid graph would be misleading).
      2. For each feature, derive_status from its member state file.
      3. Build complete = {name: is_complete_for_orchestration(state)}.
      4. For each feature set unmetDeps = unmet_deps(name, features, complete)
         and blocked = bool(unmetDeps).
      5. actionable = features whose unmetDeps is empty AND not complete (00 §8).
      6. parallelEligible = actionable features that do not (transitively)
         depend on one another (00 §8) — computed from the transitive closure of
         dependsOn restricted to the actionable set.
      7. rollup = {complete: count(complete), total: len(features)}.
      8. nextCommand = recommended command for the first actionable feature
         (e.g. '/feature-forge:forge-1-prd <name>' when its PRD is absent, else
         the next un-run stage), or None when nothing is actionable.

    Empty epic (features == []): a valid manifest may have zero members (e.g. all
    removed via remove-feature). render_status then returns features=[],
    actionable=[], parallelEligible=[], rollup={complete: 0, total: 0},
    nextCommand=None. Consumers MUST treat total == 0 as the distinct "empty epic
    — add features" state, NOT as completion: the completion/docs-offer gate is
    `rollup.total > 0 AND rollup.complete == rollup.total` (04 §7.2, §10), so a
    `0 == 0` rollup never spuriously reports an empty epic as complete.

    Args:
        epic_dir: The epic subtree directory.
        specs_dir: The configured specs directory.

    Returns:
        The render-status dict (§8.4). O(V+E) for the graph work plus one file
        read per member — well within <1s at 20 features (REQ-ROBUST-01).

    Raises:
        UsageError: Missing/unreadable manifest (exit 2).
        FindingsError: The manifest fails validation (exit 1).
    """
    ...
```

`parallelEligible` is computed by taking the transitive closure of `dependsOn` over the
actionable subset and keeping only features with no actionable ancestor/descendant among
the other actionable features. This is `O(V·(V+E))` worst case — trivial at ≤20 nodes.

### 8.4 `render-status` JSON output (tech-spec §4.4, 00 §5, §8)

Full output contract (reproduced here so this CLI doc is self-contained, per 00 §8). The
object is typed — `render_status` returns a `RenderStatus`, not a bare `dict`:

```python
class Rollup(TypedDict):
    """Aggregate completion counts for the epic dashboard (00 §8)."""

    complete: int  #: Number of member features complete-for-orchestration (00 §7).
    total: int     #: Total member features in the manifest (0 for an empty epic).


class RenderStatus(TypedDict):
    """The full live dashboard payload returned by `render_status` (00 §5, §8).

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
```

Example payload:

```json
{
  "epic": "auth-overhaul",
  "status": "active",
  "features": [
    { "name": "config-store",  "stage": "forge-5-loop", "status": "complete",
      "blocked": false, "unmetDeps": [] },
    { "name": "token-service", "stage": "forge-1-prd",   "status": "in-progress",
      "blocked": false, "unmetDeps": [] },
    { "name": "api-gateway",   "stage": "forge-0-epic",  "status": "not-started",
      "blocked": true,  "unmetDeps": ["token-service"] }
  ],
  "actionable": ["token-service"],
  "parallelEligible": ["token-service"],
  "rollup": { "complete": 1, "total": 4 },
  "nextCommand": "/feature-forge:forge-1-prd token-service"
}
```

Per-feature `stage`/`status` reuse the existing navigator status indicators (REQ-VIS-01).
`nextCommand` is `null` when no feature is actionable (e.g. all complete, or epic paused).

---

## 9. CLI Dispatch (`main`)

`main()` mirrors `validate-traceability.py`: build an `argparse.ArgumentParser` with a
`subparsers` group (one per subcommand), each declaring its positional name(s),
`--specs-dir` (default `./specs`, matching tech-spec §2.4), and `--json` where applicable.
Mutators add `--charter`, `--depends-on`, `--order`, `--status` (with `choices=` for
`--status`). Comma-separated list args (`--depends-on`, `--order`) are split on `,` and
stripped. Dispatch resolves `--specs-dir` to a `Path`, then calls the matching function
inside a `try/except` that maps `UsageError`→2, `FindingsError`→1, bare `OSError`→2; a
clean return is 0.

```python
def _emit_findings(findings: list[Finding], as_json: bool) -> None:
    """Print findings as JSON ({"valid": false, "findings": [...]}) or as one
    actionable line per finding (mirroring validate-traceability.py's two
    output modes). JSON goes to stdout; human lines go to stderr."""
    ...


def main() -> int:
    parser = argparse.ArgumentParser(prog="epic-manifest.py", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)
    # ... one add_parser(...) per subcommand, each with --specs-dir default "./specs"
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
```

---

## 10. Error Handling Summary (tech-spec §6)

| Condition | Detected by | Exit | Output |
|-----------|-------------|------|--------|
| Unsafe name (separator / `..` / absolute) | `assert_safe_name` (pre-FS) | 2 | `Error: unsafe name '../z'` (stderr) |
| Resolved path escapes `{specsDir}` | `contained_path` | 2 | `Error: resolved path escapes specs dir: …` |
| Missing / unreadable manifest or specs dir | `load_manifest` / `resolve` | 2 | `Error: manifest not found: …` |
| Corrupt (non-JSON) manifest | `load_manifest` | 1 | `corrupt-json` finding |
| Schema violation / cached per-feature `status` | `validate` | 1 | `schema` / `cached-status` findings |
| Duplicate name across tree | `feature_dirs` + `validate`/`check-name` | 1 | `duplicate-name` finding |
| Dangling `dependsOn`/`consumes.from` | `validate` / mutator re-validate | 1 | `dangling-ref` finding |
| Cycle in `dependsOn` | `find_cycle` | 1 | `cycle` finding (with path) |
| Ambiguous / not-found resolution | `resolve` | 1 | `ambiguous` / `not-found` finding |
| Mutation would break invariants | `_bump_and_write` | 1 | blocking findings; **no write** |
| Atomic write fails | `atomic_write` | 2 | `Error: atomic write … failed: …`; temp removed |

Skills surface findings **verbatim** and stop on exit ≥ 1 for gating operations
(00 §4, §9).

---

## Dependencies

- **00-core-definitions.md** — the canonical source for: the manifest schema and its
  invariants (§2, §2.6), the pipeline-state `epic` back-pointer and conflict rule (§3),
  the `Finding`/`FindingCode` taxonomy (§4), `FeatureStatus`/`DerivedStatus` (§5), name &
  path safety constants (§6), the completion-for-orchestration rule (§7), the derived sets
  `actionable`/`parallelEligible` (§8), and the exit-code contract (§9). This document
  does **not** redefine these; it implements them.
- **01-architecture-layout.md §3** — the module skeleton this document fleshes out with
  full signatures; §2.2 — the `${CLAUDE_PLUGIN_ROOT}` invocation convention; §4.3 — how
  epic dirs vs feature dirs are distinguished (consumed by `feature_dirs`).
- **`scripts/validate-traceability.py`** — the style/`argparse`/exit-code/`--json`
  template this module mirrors exactly.
- **`references/epic-manifest-schema.json`** (authored per 00 §2) — read by `validate`.
- **04-pipeline-integration.md** — *downstream* consumer: the loop dependency gate and
  handoff call `render-status` and reuse the §8.1 completion predicate. (Listed for
  cross-reference; not a build prerequisite of this helper.)
- **05-testing-strategy.md** — the pytest suite that exercises every subcommand and every
  §8.1 completion branch (see Verification below).

## Verification

An engineer confirms an implementation matches this spec by checking:

- [ ] `python3 -m py_compile scripts/epic-manifest.py` exits 0 (valid 3.10+ syntax,
      01 §6).
- [ ] `resolve` returns the **flat** path for a standalone feature unchanged
      (REQ-COMPAT-01/02), the nested path for a uniquely-nested feature (REQ-DIR-03), exit
      1 `ambiguous` for a genuine multi-match, and exit 1 `not-found` for an unknown name.
- [ ] `resolve ../escape` and a manifest naming `../x` both exit 2 / produce
      `unsafe-name` (REQ-SEC-02); a contrived symlink escaping `{specsDir}` yields
      `path-escape`.
- [ ] `validate` on the `cyclic-epic` fixture emits a `cycle` finding whose message lists
      the cycle path and exits 1 (REQ-EPIC-05); on `dup-name` a `duplicate-name`
      (REQ-DIR-04); on `corrupt` a `corrupt-json` (REQ-ROBUST-02); on a manifest carrying
      a per-feature `status` a `cached-status` (REQ-STATE-02); on `valid-epic` exits 0 with
      empty findings.
- [ ] `check-name` exits 1 for any already-existing name (flat, nested, or epic dir) and
      0 for a free name (REQ-DIR-04).
- [ ] `render-status` over the `status-derivation` fixtures reflects each §8.1 branch
      (loop incomplete; loop complete + no impl-verify; loop complete + impl
      `findings-reported`; loop complete + `findings-applied`) and computes
      `actionable`/`parallelEligible`/`rollup`/`nextCommand` per §8.4 (REQ-ORCH-01/03);
      editing a member's `.pipeline-state.json` and re-rendering reflects the change with
      no refresh step (REQ-STATE-02 acceptance test).
- [ ] Every mutator refuses to write (exit 1, file byte-identical afterward) when its edit
      would introduce a cycle or dangling ref, and on success bumps `updatedAt` and leaves
      a valid manifest (REQ-EPIC-05, REQ-OBS-01); interrupting a write (killing between
      temp-write and replace) never leaves a partial manifest (REQ-ROBUST-03).
- [ ] A synthetic 20-feature epic validates + renders in well under 1 second
      (REQ-ROBUST-01).
- [ ] The full pytest suite (05-testing-strategy.md) passes via `bash scripts/validate.sh`.
