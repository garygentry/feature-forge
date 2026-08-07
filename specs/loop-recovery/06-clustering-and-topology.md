# 06 — Clustering & Topology

> The two pure, deterministic graph functions this feature adds to
> `scripts/forge-session.py` — `cluster_blocked(items)` (systemic-cause clustering,
> REQ-CLU-01) and `compute_topology(items)` (dependency-topology metrics + advisory
> warnings, REQ-TOPO-01..03) — the `backlog-topology` verb that exposes them, and the
> **three consumers** that read that verb's output (forge-4-backlog authoring report,
> forge-verify CHECK-B28, forge-5-loop Step 2a depth line). Both functions are the
> **scripted substrate** the recovery procedure (`05`) and the starvation report (`03`)
> build on; neither reads `backlog.json` off disk — they are pure functions over the
> runner's item array (single data source, decision V-007).
>
> Shared types, constants, and the verb's output JSON live in `00-core-definitions.md`
> and are referenced here, not restated. This document owns the **algorithms** and the
> **placement**.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-CLU-01 | Deterministic scripted clustering substrate (token-set Jaccard union-find) | §2 (`cluster_blocked`), §2.4 (OQ-4 alternatives) |
| REQ-TOPO-01 | forge-4-backlog reports root count, max chain depth, per-root fan-out | §3 (`compute_topology`), §5.1 (consumer a) |
| REQ-TOPO-02 | forge-verify advisory topology check (warns, never blocks) | §5.2 (CHECK-B28) |
| REQ-TOPO-03 | forge-5-loop Step 2a surfaces max chain depth beside iteration count | §5.3 (consumer c) |
| REQ-ATTR-01 | `selectable` = pending items whose deps are all done, from authoritative counts | §3.3 (`selectable`), §4 (verb) |
| REQ-PERF-01 | Topology linear, clustering bounded | §6 (performance) |

---

## 1. Scope & Dependencies

**In scope:** the full Python for `cluster_blocked` and `compute_topology`, the shared
dependency-index and closure helpers they reuse, the `cmd_backlog_topology` verb
(signature + argparse registration + dispatch), and the exact placement and rendered
output of the three consumers.

**Out of scope (owned elsewhere):**
- The decision record, `resolved` outcome, routing/text tables, and the starvation
  *rendering* template → `02`, `03`.
- The recovery procedure that *invokes* `--cluster` for consolidated prompts, and tree
  reconciliation → `05`.
- The topology/clustering **tests** — line/diamond/parallel fixtures, the observed-incident
  fixture, the Jaccard-boundary cases, and the vendored one-cause-three-phrasings fixture
  (V-015), plus the `test_lifecycle_artifact_check.py` literal edit — → `07`.

**Depends on:**
- `00-core-definitions.md` — §6.1 (`TOPOLOGY_FANOUT_WARN_RATIO`, `TOPOLOGY_DEPTH_WARN_RATIO`),
  §6.2 (`CLUSTER_JACCARD_THRESHOLD`), §8 (the `backlog-topology` output shape), §8.3 (the
  cluster entry shape), §7 (the `UsageError`/exit-2 error model), §10 (`_emit`).
- `01-architecture-layout.md` — §2 (flat-function placement next to `rank-features`/
  `reconcile-branch`; argparse + dispatch tail), §1.2 (the forge-verify count-literal edits),
  §4 steps 6–7 (CLU before TOPO).

**Consumed by:**
- `03` — the starvation report reads `selectable` + `starvation.blockingRoots` from this
  verb; the Step 2a depth line reads `maxChainDepth`.
- `05` — the recovery procedure runs `backlog-topology --cluster` for consolidated
  blast-radius prompts (`00` §8.3), and reads `roots`/`maxChainDepth` for framing.
- `07` — the test suite that pins these algorithms.

All code lands in `scripts/forge-session.py` (canon; regenerates `adapters/**` via
`build-adapters.py`). Python **stdlib only** — `re`, `math`, `json`, `sys`, `pathlib.Path`.
`re`/`json`/`sys`/`Path` are already imported (`forge-session.py:160-167`); **`import math`
must be added** to the module import block (stdlib, already named in tech-spec §9's
dependency list).

## 2. Systemic-cause clustering — `cluster_blocked` (REQ-CLU-01, D7)

A pure flat function, following the `rank-features`/`reconcile-branch` precedent
(`forge-session.py:1901`, no class). It is the **required substrate** REQ-CLU-01 mandates:
the agent MAY merge candidate clusters by judgment, but the deterministic floor is what is
testable (§2.4). It clusters `status == "blocked"` items (needs-human **and** plain blocked
— rauf derives `needsHuman` as `status=="blocked" && needsHuman==true`, so both live under
`blocked`) by the similarity of their `blockedReason` text, where rauf lands the
`RAUF_NEEDS_HUMAN:<reason>` question.

### 2.1 Shared dependency index + transitive-dependents closure

`cluster_blocked` and `compute_topology` (§3) share two helpers so the "gated subtree"
notion is defined once. Both are cycle-safe (rauf validation has already rejected cycles;
a visited/on-path set still guards, per `00` §6.1).

```python
def _id_key(item_id: object) -> tuple[int, object]:
    """Deterministic sort key for backlog ids.

    All-digit ids sort numerically ("2" before "10"); everything else sorts
    lexically, after the numeric block. Used everywhere an ordering must not
    depend on dict/hash iteration (``00`` §Prime-Facts determinism).

    Args:
        item_id: A backlog item id (usually ``str``; coerced defensively).

    Returns:
        A ``(bucket, value)`` tuple that is a total order across mixed id shapes.
    """
    s = str(item_id)
    return (0, int(s)) if s.isdigit() else (1, s)


def _build_dep_index(
    items: list[dict],
) -> tuple[dict[str, dict], dict[str, list[str]], dict[str, list[str]]]:
    """Build the in-backlog dependency adjacency from ``dependsOn`` edges.

    Edges pointing at ids **not present** in this backlog are dropped (an item whose
    only ``dependsOn`` targets are external is therefore a root — see §3.1).

    Args:
        items: The runner's item array (each a dict with at least ``id``; optional
            ``dependsOn``, ``status``, ``blockedReason``).

    Returns:
        ``(by_id, deps, dependents)`` where ``by_id`` maps id → item, ``deps`` maps
        id → the ids it depends on (in-backlog only), and ``dependents`` maps id →
        the ids that directly depend on it.
    """
    by_id = {str(it["id"]): it for it in items}
    deps: dict[str, list[str]] = {
        i: [str(d) for d in (by_id[i].get("dependsOn") or []) if str(d) in by_id]
        for i in by_id
    }
    dependents: dict[str, list[str]] = {i: [] for i in by_id}
    for i, ds in deps.items():
        for d in ds:
            dependents[d].append(i)
    return by_id, deps, dependents


def _transitive_dependents(
    dependents: dict[str, list[str]],
) -> dict[str, set[str]]:
    """Memoized transitive-dependents (gated-subtree) closure for every node.

    ``dependents[x]`` lists items that directly depend on ``x``; the returned map
    gives, for each item, the set of items that **transitively** depend on it — the
    gated subtree that item's completion would unblock ("gates", ``00`` §8).

    Cycle-safe: a node re-encountered on the current DFS path contributes nothing and
    is not memoized (rauf rejects cycles upstream, so this only hardens against
    malformed input; it never fires on validated backlogs).

    Args:
        dependents: The reverse adjacency from :func:`_build_dep_index`.

    Returns:
        A map id → set of transitively-dependent ids. O(V + E) overall (each edge is
        walked once thanks to memoization).
    """
    memo: dict[str, set[str]] = {}

    def visit(node: str, on_path: set[str]) -> set[str]:
        if node in memo:
            return memo[node]
        if node in on_path:  # cycle guard — unreachable on validated backlogs
            return set()
        on_path.add(node)
        acc: set[str] = set()
        for child in dependents[node]:
            acc.add(child)
            acc |= visit(child, on_path)
        on_path.discard(node)
        memo[node] = acc
        return acc

    for n in dependents:
        visit(n, set())
    return memo
```

### 2.2 Normalization & the Jaccard measure

Per tech-spec §3.6 / `00` §6.2: lowercase, split on non-alphanumeric, drop **pure-number**
and **item-id-shaped** tokens (`^\d+$`, `^[a-z]*\d+$`), and use the token **set** (not bag,
so repetition does not bias the measure).

```python
_ID_SHAPED_TOKEN = re.compile(r"^(?:\d+|[a-z]*\d+)$")


def _normalize_reason(text: str | None) -> set[str]:
    """Normalize a ``blockedReason`` into its comparison token set.

    Lowercases, splits on any run of non-alphanumeric characters, and drops noise
    tokens — pure numbers and item-id-shaped tokens (``42``, ``req12``, ``t7``) —
    which carry no cause signal and would spuriously separate or merge reasons.

    Args:
        text: The item's ``blockedReason`` (may be ``None``/empty).

    Returns:
        The set of meaningful lowercased tokens (possibly empty).
    """
    tokens = re.split(r"[^a-z0-9]+", (text or "").lower())
    return {t for t in tokens if t and not _ID_SHAPED_TOKEN.match(t)}


def _jaccard(a: set[str], b: set[str]) -> float:
    """Jaccard similarity |A∩B| / |A∪B| of two token sets.

    Symmetric and order-insensitive (§2.4). Two empty sets score ``0.0`` — an item
    with no meaningful reason tokens never clusters with anything.

    Args:
        a: First token set.
        b: Second token set.

    Returns:
        A similarity in ``[0.0, 1.0]``.
    """
    union = a | b
    return len(a & b) / len(union) if union else 0.0
```

### 2.3 Union-find clustering

Deterministic: blocked items are processed in `_id_key` order; union always roots the
component at the **lowest** member id; components are emitted sorted by lowest member id.
No step depends on dict/hash iteration order.

```python
def cluster_blocked(items: list[dict]) -> list[dict]:
    """Cluster blocked items by ``blockedReason`` similarity (REQ-CLU-01, D7).

    Union-find over every pair of ``status == "blocked"`` items whose normalized
    token-set Jaccard (§2.2) is ``>= CLUSTER_JACCARD_THRESHOLD`` (``00`` §6.2). Each
    emitted component carries its member ids, the members' raw reasons, the shared
    token core, and the **union** of the members' gated subtrees for blast-radius
    framing (``00`` §8.3). Components of size 1 are emitted too — the recovery
    procedure (`05`) consolidates only components of ≥2, prompting singletons per item.

    The result is the deterministic *substrate*: the agent may merge components it
    judges to share a cause (under-clustering is the deliberately chosen failure
    direction — §2.4). It never reads disk; ``items`` is the runner's array.

    Args:
        items: The runner's ``listCommand`` item array.

    Returns:
        A list of cluster dicts (``00`` §8.3 shape), sorted by lowest member id:
        ``{clusterId, memberIds, memberReasons, sharedTokens, gatedIds, gatedCount}``.
    """
    by_id, _deps, dependents = _build_dep_index(items)
    gated = _transitive_dependents(dependents)
    blocked = sorted(
        (i for i, it in by_id.items() if it.get("status") == "blocked"),
        key=_id_key,
    )
    tokens = {i: _normalize_reason(by_id[i].get("blockedReason")) for i in blocked}

    parent = {i: i for i in blocked}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]  # path halving
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra == rb:
            return
        lo, hi = sorted((ra, rb), key=_id_key)  # lowest id is the component root
        parent[hi] = lo

    for idx, a in enumerate(blocked):
        for b in blocked[idx + 1:]:
            if _jaccard(tokens[a], tokens[b]) >= CLUSTER_JACCARD_THRESHOLD:
                union(a, b)

    groups: dict[str, list[str]] = {}
    for i in blocked:
        groups.setdefault(find(i), []).append(i)

    clusters: list[dict] = []
    for root in sorted(groups, key=_id_key):
        members = sorted(groups[root], key=_id_key)
        shared = set.intersection(*(tokens[m] for m in members)) if members else set()
        union_gated: set[str] = set()
        for m in members:
            union_gated |= gated[m]
        union_gated -= set(members)  # a member gating a sibling is not its own blast radius
        clusters.append(
            {
                "clusterId": "c" + members[0],  # 00 §8.3: "c" + lowest member id
                "memberIds": members,
                "memberReasons": [by_id[m].get("blockedReason") or "" for m in members],
                "sharedTokens": sorted(shared),
                "gatedIds": sorted(union_gated, key=_id_key),
                "gatedCount": len(union_gated),
            }
        )
    return clusters
```

**`clusterId` contract.** `"c" + members[0]` is deterministic and stable across runs for
the same component, so `05`'s `decision-record --cluster CID` can tie one consolidated
answer's per-item entries together (REQ-CLU-04; `00` §8.3).

### 2.4 Alternatives considered (OQ-4)

Token-set Jaccard ≥ 0.5 with union-find was chosen against three alternatives:

| Alternative | Why rejected |
|---|---|
| **Normalized exact equality** | Trivially explainable, but any rephrasing defeats it — the agent's judgment-merge becomes the *load-bearing* step, which is exactly what the scripted substrate exists to de-risk. |
| **Shared-token-core containment / normalized-prefix grouping** | Cheaper, but order- and phrasing-sensitive in ways a symmetric set measure is not (grouping would depend on which reason is the "prefix"). |
| **Trivial all-in-one** — one consolidated prompt for *all* needs-human items | Maximal consolidation, but erases genuinely distinct causes and misframes blast radius ("gates 16/16" even when two unrelated causes each gate a third). |

Jaccard is the simplest **symmetric, order-insensitive** measure. **Under-clustering is
the deliberately chosen failure direction:** the agent holds merge authority but no
scripted split authority, so a false *split* is cheap (the agent merges) while a false
*merge* would silently misframe a consolidated prompt. Semantically distant phrasings of
one cause (e.g. "missing API key" vs "cannot authenticate") can fall below any token
threshold — that residual is exactly what the agent's merge pass is for.

**Calibration (falsifiable, not asserted):** `CLUSTER_JACCARD_THRESHOLD = 0.5` is tuned so
the vendored one-cause-three-phrasings fixture in `tests/test_decision_clustering.py`
(`07`, derived verbatim from the observed verify-test-debt `blockedReason` strings, V-015)
clusters into exactly **one** candidate; the binding pair clears 0.5 by only ~0.028, so the
fixture strings are carried byte-for-byte (`00` §6.2).

## 3. Topology computation — `compute_topology` (REQ-TOPO-01..03, REQ-ATTR-01, D6)

One pure function, **linear** via the memoized helpers of §2.1 plus a memoized
longest-path pass. It never reads disk.

### 3.1 Roots, gated subtrees, max chain depth

```python
def _max_chain_depth(by_id: dict[str, dict], deps: dict[str, list[str]]) -> int:
    """Longest ``dependsOn`` chain length (node count), memoized and cycle-safe.

    Depth of a node = ``1 + max(depth(dep) …)`` over its in-backlog dependencies;
    the result is the maximum over all nodes. A node re-seen on the current path
    contributes ``0`` (cycle guard; unreachable on validated backlogs).

    Args:
        by_id: id → item, from :func:`_build_dep_index`.
        deps: id → dependency ids, from :func:`_build_dep_index`.

    Returns:
        The longest chain length; ``0`` for an empty backlog.
    """
    memo: dict[str, int] = {}

    def depth(node: str, on_path: set[str]) -> int:
        if node in memo:
            return memo[node]
        if node in on_path:  # cycle guard
            return 0
        on_path.add(node)
        d = 1 + max((depth(x, on_path) for x in deps[node]), default=0)
        on_path.discard(node)
        memo[node] = d
        return d

    return max((depth(n, set()) for n in by_id), default=0)
```

### 3.2 The assembled metrics

```python
def compute_topology(items: list[dict]) -> dict:
    """Compute dependency-topology metrics + advisory warnings (REQ-TOPO-01..03).

    Pure function over the runner's item array (single data source, decision V-007) —
    it never reads ``backlog.json`` off disk, so every derived count cites the runner's
    authoritative array (REQ-ATTR-01, REQ-OBS-01). Linear via the memoized DFS helpers
    of §2.1/§3.1 (REQ-PERF-01).

    Args:
        items: The runner's ``listCommand`` item array. Each item may carry ``id``,
            ``dependsOn`` (list of ids), and ``status`` (``pending``/``done``/
            ``blocked``/…).

    Returns:
        The ``00`` §8 output shape (without ``clusters`` — that is appended by the
        verb under ``--cluster``): ``{itemCount, rootCount, roots, maxChainDepth,
        selectable, starvation, warnings}``.
    """
    by_id, deps, dependents = _build_dep_index(items)
    item_count = len(by_id)
    gated = _transitive_dependents(dependents)

    roots = [i for i in by_id if not deps[i]]  # no in-backlog dependsOn edges
    roots_out = sorted(
        (
            {
                "id": r,
                "gatedCount": len(gated[r]),
                "gatedIds": sorted(gated[r], key=_id_key),
            }
            for r in roots
        ),
        key=lambda row: _id_key(row["id"]),
    )

    max_depth = _max_chain_depth(by_id, deps)

    selectable = sum(
        1
        for i, it in by_id.items()
        if it.get("status") == "pending"
        and all(by_id[d].get("status") == "done" for d in deps[i])
    )
    pending = sum(1 for it in by_id.values() if it.get("status") == "pending")

    fanout_threshold = math.ceil(TOPOLOGY_FANOUT_WARN_RATIO * item_count)
    depth_threshold = math.ceil(TOPOLOGY_DEPTH_WARN_RATIO * item_count)

    warnings: list[str] = []
    if any(row["gatedCount"] >= fanout_threshold for row in roots_out):
        warnings.append("single-root-fanout")
    if max_depth >= depth_threshold:
        warnings.append("chain-depth")

    starvation = None
    if selectable == 0 and pending > 0:
        starvation = {
            "starved": True,
            "blockingRoots": [
                {"id": row["id"], "gatedCount": row["gatedCount"]}
                for row in roots_out
                if row["gatedCount"] > 0 and by_id[row["id"]].get("status") != "done"
            ],
        }

    return {
        "itemCount": item_count,
        "rootCount": len(roots),
        "roots": roots_out,
        "maxChainDepth": max_depth,
        "selectable": selectable,
        "starvation": starvation,
        "warnings": warnings,
    }
```

### 3.3 Semantics that consumers rely on

- **`roots`** — items with no *in-backlog* `dependsOn` edge (§3.1). `gatedCount`/`gatedIds`
  are the transitively-dependent subtree (`00` §8, "gates").
- **`selectable`** (REQ-ATTR-01) — pending items **all** of whose in-backlog dependencies
  are `done`. This is the count `03`'s starvation logic keys off; the pure function computes
  it, but the *iterations-remaining* condition (REQ-ATTR-02: `iterationsUsed <
  iterationsGranted`) is layered by the report template in `03`, because the item array
  carries no iteration counters (single data source). `compute_topology` therefore reports
  `starvation.starved` on the topology condition alone (`selectable == 0 && pending > 0`);
  `03` renders starvation only when that **and** the iteration counters agree.
- **`warnings`** — a subset of `["single-root-fanout", "chain-depth"]`, both driven by the
  fixed `TOPOLOGY_*_WARN_RATIO` constants and `math.ceil(ratio · itemCount)` thresholds
  (`00` §6.1). **Advisory only** — no consumer blocks on them (§5.2). The observed incident
  (3 roots gating 81%, depth 13/16) trips **both**.
- **Threshold arithmetic.** `math.ceil(0.5 · 16) = 8`; a root gating 13 ≥ 8 → warn; depth
  13 ≥ 8 → warn. `math.ceil` is used (not integer `//`) so the ratio constants remain the
  single source of the threshold even if a future ratio is non-half.

## 4. The `backlog-topology` verb (§5.2)

A thin verb wrapping the two pure functions. `clusters` is appended **only** with
`--cluster` (`00` §8). It is a pure function over the runner item array the caller already
holds — it **never** reads `backlog.json` off disk (single data source, V-007), so every
claim any consumer derives cites the runner's authoritative counts (REQ-ATTR-01, REQ-OBS-01).

### 4.1 The command function

```python
def cmd_backlog_topology(items: list[dict], *, with_clusters: bool) -> dict:
    """Assemble the ``backlog-topology`` payload (``00`` §8 shape).

    Args:
        items: The runner's ``listCommand`` item array.
        with_clusters: When true, append the ``clusters`` section (§2.3).

    Returns:
        The topology dict; with ``clusters`` appended iff ``with_clusters``.
    """
    result = compute_topology(items)
    if with_clusters:
        result["clusters"] = cluster_blocked(items)
    return result


def _load_topology_items(args: argparse.Namespace) -> list[dict]:
    """Read and parse the runner item array for ``backlog-topology``.

    Accepts either a top-level JSON array or an object with an ``items`` array
    (rauf ``backlog list --json`` emits the array; the object form is tolerated
    for forward-compatibility). All failures raise ``UsageError`` → exit 2
    (``00`` §7), never a partial/guessed result.

    Args:
        args: Parsed namespace with ``items_stdin`` / ``items_json``.

    Returns:
        The item list.

    Raises:
        UsageError: unreadable ``--items-json``, invalid JSON, or a shape that is
            neither an array nor an object carrying an ``items`` array.
    """
    if args.items_stdin:
        raw = sys.stdin.read()
    else:
        try:
            raw = Path(args.items_json).read_text(encoding="utf-8")
        except OSError as exc:
            raise UsageError(f"cannot read --items-json {args.items_json}: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UsageError(f"invalid items JSON: {exc}") from exc
    items = data.get("items", []) if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise UsageError("items JSON must be an array or an object with an 'items' array")
    return items
```

### 4.2 argparse registration (in `main()`, beside the `state-*` registrations, `~:5746`)

```python
    p_topo = sub.add_parser(
        "backlog-topology",
        help="Dependency-topology metrics + advisory warnings over a runner item array",
    )
    topo_src = p_topo.add_mutually_exclusive_group(required=True)
    topo_src.add_argument(
        "--items-json", help="Path to the loopRunner listCommand JSON output"
    )
    topo_src.add_argument(
        "--items-stdin", action="store_true",
        help="Read the listCommand JSON from stdin",
    )
    p_topo.add_argument(
        "--cluster", action="store_true", dest="with_clusters",
        help="Append blocked-item clusters (§2.3) for consolidated prompts",
    )
    p_topo.add_argument("--json", action="store_true", dest="json_output")
```

The mutually-exclusive `required=True` group makes "neither source given" and "both given"
argparse errors (exit 2 with the `Error:` prefix via `_ErrorPrefixParser`, `00` §7) — no
hand-rolled validation needed.

### 4.3 Dispatch block (in the `main()` try-body, beside the `state-*` dispatches, `~:5970`)

```python
        if args.cmd == "backlog-topology":
            items = _load_topology_items(args)
            payload = cmd_backlog_topology(items, with_clusters=args.with_clusters)
            _emit(payload, args.json_output, _print_topology)
            return 0
```

`_emit` (`00` §10, `forge-session.py:5514`) dispatches `--json` vs a human printer.
`_print_topology(payload)` is a small human-readable printer mirroring the existing
`_print_*` helpers — root count, max chain depth, per-root fan-out, and any warnings — for
parity with the other verbs; machine consumers always pass `--json`.

## 5. The three consumers

All five call sites feed the verb the `loopRunner.listCommand` JSON they **already have**
(`rauf backlog list . --backlog {dir} --json`) via `--items-stdin`; none passes a
`backlog.json` path (V-007).

### 5.1 Consumer a — forge-4-backlog authoring report (REQ-TOPO-01)

**Placement:** a new topology-report step in the Step 5/6 slot of
`skills/forge-4-backlog/SKILL.md` (~100 lines of body headroom, `01` §5). It runs **after
Step 5 validation succeeds** (the runner is installed and invoked there, so `listCommand`
is available) and **before / within** the Step 6 user review that already prints
"dependency-chain depth, estimated loop iterations" (`SKILL.md:135-137`). It **always
reports** the metrics; it renders the warning block **only when `warnings` is non-empty**.

**What the step runs:**

```
rauf backlog list . --backlog {resolvedBacklogDir} --json \
  | python3 {CLAUDE_PLUGIN_ROOT}/scripts/forge-session.py backlog-topology --items-stdin --json
```

**What it always prints** (from the payload; cites the runner counts, REQ-OBS-01):

```
Topology: {itemCount} items, {rootCount} roots, max chain depth {maxChainDepth}.
Per-root fan-out (gated subtree size): {id}→{gatedCount}, … (largest first).
```

**Warning block, rendered only when a trigger fires** (`warnings` non-empty):

```
⚠️ Fragile topology (advisory — does not block authoring):
  - single-root-fanout: root {id} gates {gatedCount}/{itemCount} items (≥50%).
  - chain-depth: max chain depth {maxChainDepth} is ≥50% of {itemCount} items.
A single defect in a high-fan-out root or a long chain can strand most of the backlog
(the loop-recovery incident: 3 roots gating 81%, 13-deep chain). Consider splitting the
gating root's subtree or flattening the chain — this is a heads-up, not a gate.
```

This is guidance only; forge-4-backlog does not fail on it (mirrors forge-verify's advisory
posture, §5.2). Whether it should also *suggest concrete restructurings* is OTQ-3
(current position: report + warn only).

### 5.2 Consumer b — forge-verify CHECK-B28 (REQ-TOPO-02)

**Placement:** a new check in
`skills/forge-verify/references/verification-checklists/backlog.md`, modeled on the
advisory-heuristic template of **CHECK-B26/B27** (severity `improvement`, `not-applicable`
when no trigger fires; `backlog.md:45-96`). It lands under a new **`### Dependency
Topology`** subsection (adjacent to the existing `### Dependency Ordering` block,
`backlog.md:29-34`) and is assigned, for the parallel dimensioned dispatch, to the
**dependency/ordering sanity** group — **group 2** of the backlog dimension groups
(`SKILL.md:43-45`: "backlog … (2) dependency/ordering sanity"). CHECK-B28 must **not**
land in the forge-verify body (`01` §5) — it is a checklist entry only.

**The CHECK-B28 text** (to add to `backlog.md`):

```markdown
### Dependency Topology
- [ ] **CHECK-B28**: **Fragile dependency topology — a single root gates a large fraction
  of the backlog, or the chain is deep** (#194). *Advisory heuristic — severity
  `improvement`, **never** `error`/`gap`, and it **never blocks**. **not-applicable** when
  no trigger fires or the graph is trivial (0–1 items, or no dependsOn edges at all).*
  A backlog where one root item gates most of the tree, or whose critical chain is deep
  relative to its size, has a single point of near-total failure: one defect in that root
  (or anywhere on the long chain) strands the dependent subtree — the loop-recovery
  incident was 3 roots gating 81% of 16 items down a 13-deep chain, and it passed both
  authoring and verification without comment. Verify by computing, never by eyeballing:
  1. **Compute the topology.** Feed the runner's item array to the scripted metric —
     `rauf backlog list . --backlog {resolvedBacklogDir} --json | python3
     {scriptsDir}/forge-session.py backlog-topology --items-stdin --json`. Read
     `itemCount`, `rootCount`, `roots[].gatedCount`, `maxChainDepth`, and `warnings`.
     If `itemCount <= 1` or there are no `dependsOn` edges, this check is **not-applicable**.
  2. **Read the warnings, do not re-derive them.** The metric applies the fixed thresholds
     (`single-root-fanout` when any root gates ≥50% of items; `chain-depth` when
     `maxChainDepth` ≥50% of item count). If `warnings` is empty, record **pass** (topology
     computed, no fragile shape). Do not invent a different threshold — the constants are
     canonical (`forge-session.py`).
  3. **Report each fired warning as one `improvement` finding.** For `single-root-fanout`,
     name the root and its `gatedCount`/`itemCount` ("root 1 gates 13/16 items") and
     suggest splitting that root's subtree or introducing an intermediate. For
     `chain-depth`, name `maxChainDepth`/`itemCount` and suggest flattening. **Report, do
     not repair** — this is a heads-up to the author, never a blocking gate. Cite the
     metric output the claim was derived from (REQ-OBS-01).
```

**Count-literal edits (both, in-line, zero line growth — `01` §1.2, `01` §5):**
- `skills/forge-verify/SKILL.md:33` — the dimension-group total `"backlog 27"` → `"backlog
  28"` (in "specs 38, backlog 27, impl 23").
- `skills/forge-verify/SKILL.md:171` — the expected-total sentence `"backlog: 27 checks"` →
  `"backlog: 28 checks"`.

Both are single-token replacements; neither adds or removes a body line, so the
`forge-verify` body stays at 298/300 (`01` §5).

**Test contract (edit owned by `07`, stated here):**
`tests/test_lifecycle_artifact_check.py:49-52` (`test_verify_skill_backlog_total_bumped`)
asserts both literals verbatim — `"backlog: 27 checks"` and `"backlog 27"` — and must be
updated to `28` in the **same change** that edits `SKILL.md`, or it red-gates. No
split-brain `27`/`28` across `SKILL.md` and the test is permitted (`01` §Verification).

### 5.3 Consumer c — forge-5-loop Step 2a depth line (REQ-TOPO-03, REQ-COMPAT-02)

**Placement:** `skills/forge-5-loop/SKILL.md` Step 2a — the "Analyze Backlog" block
(`SKILL.md:120-124`) already runs `listCommand` and computes the iteration count
(`ceil((pending + in_progress) * loopIterationMultiplier)`). Add **one** line surfacing
`maxChainDepth` from `backlog-topology` beside that count. This renders on **every** run
and is the **only** new happy-path output (REQ-COMPAT-02); it adds no prompt and no operator
decision.

**The exact line** (added to the Step 2a "Iterations:" report line at `SKILL.md:161`, and
described in the Step 2a prose at `:124`):

```
  - Max chain depth: {maxChainDepth} — depth bounds achievable progress regardless of iteration budget
```

Sourced from `backlog-topology --items-stdin --json` over the same `listCommand` JSON Step
2a already fetched (`00` §9 citation table — Step 2a depth line cites `maxChainDepth`). No
new command invocation beyond piping the array it already has into the verb. This is the
in-line edit budgeted in `01` §5 (net ~0–1 lines; forge-5-loop stays within cap).

## 6. Performance (REQ-PERF-01)

- **`compute_topology`** is linear: `_build_dep_index` is O(V + E); `_transitive_dependents`
  and `_max_chain_depth` are memoized DFS, each edge relaxed once → O(V + E); `roots`,
  `selectable`, and the threshold checks are O(V). No perceptible Step 2a latency at
  realistic sizes (tens of items; the observed corpus is 16). No quantified throughput
  target applies — a local single-operator CLI has no throughput dimension (PRD §4.6).
- **`cluster_blocked`** is O(k²) pairwise over the **blocked** items only (k ≪ n; every pair
  is a set-intersection over small token sets) plus the shared O(V + E) closure. On the
  observed corpus k is a handful. Well within REQ-PERF-01.
- Both are **pure and deterministic** (`00` §Prime-Facts 4): fixed, `_id_key`-sorted output,
  no dependence on dict/hash iteration — this is what makes their reports reproducible and
  their `07` tests stable.

## Dependencies

- **`00-core-definitions.md`** — §6.1/§6.2 (the four constants; note **`import math`** must
  be added to the module imports for the `math.ceil` thresholds), §8/§8.3 (the verb output
  and cluster-entry shapes this document produces), §7 (`UsageError`/exit-2), §10 (`_emit`,
  `Path`/`json`/`sys`/`re` already imported).
- **`01-architecture-layout.md`** — §2 (flat-function + argparse/dispatch placement), §1.2
  and §5 (the forge-verify count-literal edits, zero line growth), §4 steps 6–7 (implement
  CLU before TOPO).
- **Implementation order** (`01` §4): `cluster_blocked` (CLU) lands before the topology
  consumers (TOPO); both reuse the §2.1 helpers, so those helpers land with whichever is
  first.

## Verification

- [ ] `cluster_blocked` and `compute_topology` are module-level flat functions in
      `scripts/forge-session.py` (no class), stdlib-only; `import math` is present.
- [ ] **Determinism:** `cluster_blocked` and `compute_topology` return identical output
      across repeated runs and across input item orderings (shuffle the array → same
      result); all ordering flows through `_id_key`, never dict/hash order.
- [ ] **Observed-incident fixture** (`07`, 3 roots, 13-deep chain, 16 items):
      `compute_topology` returns `warnings == ["single-root-fanout", "chain-depth"]` (both
      present), `maxChainDepth == 13`, and `starvation.starved == true` naming the blocking
      roots.
- [ ] **Threshold arithmetic:** with `itemCount == 16`, a root with `gatedCount >= 8` trips
      `single-root-fanout` and `maxChainDepth >= 8` trips `chain-depth` (`math.ceil(0.5·16)`).
- [ ] **`selectable`:** counts exactly the pending items whose in-backlog `dependsOn` are all
      `done`; excludes pending items with any non-done dependency.
- [ ] **One-cause-three-phrasings fixture** (`07`, V-015, vendored verbatim from the real
      `blockedReason` strings): `cluster_blocked` returns exactly **one** cluster of the
      three items; `CLUSTER_JACCARD_THRESHOLD == 0.5`.
- [ ] **Normalization:** pure-number and item-id-shaped tokens (`42`, `req12`, `t7`) are
      dropped; comparison is over the token **set**; two empty token sets score `0.0` and
      never cluster.
- [ ] **`clusterId`** is `"c" + lowest member id`; `gatedIds`/`gatedCount` are the union of
      members' gated subtrees minus the members themselves.
- [ ] **`--cluster` gating:** `backlog-topology` omits `clusters` without `--cluster` and
      includes it with the flag; the payload otherwise matches `00` §8.
- [ ] **Single data source:** the verb reads only `--items-json`/`--items-stdin`; it never
      opens `backlog.json` (grep proves no disk read of a backlog path in the topology path).
- [ ] **Error model:** unreadable `--items-json`, invalid JSON, or a non-array/non-`items`
      shape each exit 2 with an `Error:` line (`00` §7); neither source, or both, is an
      argparse exit-2 error.
- [ ] **Consumers:** forge-4-backlog prints the metrics after Step 5 validation and the
      warning block only when `warnings` is non-empty; CHECK-B28 exists in `backlog.md` as a
      severity-`improvement`, never-blocking, `not-applicable`-on-trivial check; both
      forge-verify count literals (`SKILL.md:33` and `:171`) and the
      `test_lifecycle_artifact_check.py:49-52` assertions all read **28**; forge-5-loop Step
      2a renders the single `maxChainDepth` line on every run.
