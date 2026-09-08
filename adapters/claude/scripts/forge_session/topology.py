"""Dependency graph & blocked-item clustering — the ``backlog-topology`` verb.

Pure, stdlib-only flat functions over the loop runner's item array (the
``listCommand`` JSON the caller already holds) — same precedent as
rank-features/reconcile-branch, no class. Nothing here reads backlog.json off
disk: single data source, so every derived claim cites the runner's
authoritative counts. All ordering flows through ``_id_key``, never dict/hash
iteration, which is what makes the output deterministic and testable.

Extracted from the ``forge-session.py`` monolith (#279); imports the shared
``UsageError`` from :mod:`forge_session._common`, never from the shim.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Final

from forge_session._common import UsageError

#: Token-set Jaccard edge threshold for ``cluster_blocked``: two blocked items whose
#: normalized blockedReason token sets score >= this join one systemic-cause cluster
#: candidate. Calibrated against a real one-cause-three-phrasings incident — the
#: binding pair clears 0.5 by only ~0.028, and tests/test_decision_clustering.py
#: vendors those strings verbatim so a threshold change that would re-split the
#: incident is caught. Under-clustering is the deliberately chosen failure direction:
#: the agent holds merge authority, so the scripted floor must never over-merge.
CLUSTER_JACCARD_THRESHOLD: Final[float] = 0.5
#: Advisory topology warn triggers for ``compute_topology`` — a single root whose
#: gated subtree is >= ceil(ratio * itemCount) items trips "single-root-fanout";
#: a dependsOn chain of >= ceil(ratio * itemCount) nodes trips "chain-depth".
#: math.ceil keeps the ratios the single source of the thresholds even if a
#: future ratio is non-half. Advisory only: no consumer blocks on them.
TOPOLOGY_FANOUT_WARN_RATIO: Final[float] = 0.5
TOPOLOGY_DEPTH_WARN_RATIO: Final[float] = 0.5


def _id_key(item_id: object) -> tuple[int, object]:
    """Deterministic sort key for backlog ids.

    All-digit ids sort numerically ("2" before "10"); everything else sorts
    lexically, after the numeric block. Used everywhere an ordering must not
    depend on dict/hash iteration.

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

    Edges pointing at ids **not present** in this backlog are dropped (an item
    whose only ``dependsOn`` targets are external is therefore a root).

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
    gated subtree that item's completion would unblock ("gates").

    Cycle-safe: a node re-encountered on the current DFS path contributes nothing
    and is not memoized (rauf rejects cycles upstream, so this only hardens against
    malformed input; it never fires on validated backlogs).

    Args:
        dependents: The reverse adjacency from :func:`_build_dep_index`.

    Returns:
        A map id → set of transitively-dependent ids. O(V + E) overall (each edge
        is walked once thanks to memoization).
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


#: A token that is a pure number or item-id-shaped (``42``, ``req12``, ``t7``) —
#: noise carrying no cause signal, dropped by _normalize_reason.
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

    Symmetric and order-insensitive. Two empty sets score ``0.0`` — an item with
    no meaningful reason tokens never clusters with anything.

    Args:
        a: First token set.
        b: Second token set.

    Returns:
        A similarity in ``[0.0, 1.0]``.
    """
    union = a | b
    return len(a & b) / len(union) if union else 0.0


def cluster_blocked(items: list[dict]) -> list[dict]:
    """Cluster blocked items by ``blockedReason`` similarity.

    Union-find over every pair of ``status == "blocked"`` items whose normalized
    token-set Jaccard is ``>= CLUSTER_JACCARD_THRESHOLD``. Each emitted component
    carries its member ids, the members' raw reasons, the shared token core, and
    the **union** of the members' gated subtrees for blast-radius framing.
    Components of size 1 are emitted too — the recovery procedure consolidates
    only components of >= 2, prompting singletons per item.

    The result is the deterministic *substrate*: the agent may merge components it
    judges to share a cause (under-clustering is the deliberately chosen failure
    direction). It never reads disk; ``items`` is the runner's array.

    Args:
        items: The runner's ``listCommand`` item array.

    Returns:
        A list of cluster dicts, sorted by lowest member id:
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
                "clusterId": "c" + members[0],  # "c" + lowest member id: stable across runs
                "memberIds": members,
                "memberReasons": [by_id[m].get("blockedReason") or "" for m in members],
                "sharedTokens": sorted(shared),
                "gatedIds": sorted(union_gated, key=_id_key),
                "gatedCount": len(union_gated),
            }
        )
    return clusters


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


def compute_topology(items: list[dict]) -> dict:
    """Compute dependency-topology metrics + advisory warnings (REQ-TOPO-01..03).

    Pure function over the runner's item array (single data source, decision
    V-007) — it never reads ``backlog.json`` off disk, so every derived count
    cites the runner's authoritative array (REQ-ATTR-01, REQ-OBS-01). Linear via
    the memoized DFS helpers above (REQ-PERF-01).

    Args:
        items: The runner's ``listCommand`` item array. Each item may carry
            ``id``, ``dependsOn`` (list of ids), and ``status`` (``pending``/
            ``done``/``blocked``/…).

    Returns:
        The ``backlog-topology`` output shape (without ``clusters`` — that is
        appended by the verb under ``--cluster``): ``{itemCount, rootCount,
        roots, maxChainDepth, selectable, starvation, warnings}``.
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

    # A trivial graph (0-1 items, or no dependsOn edges at all) has no topology
    # to warn about — a single node's depth of 1 would otherwise trip the
    # ceil(0.5 * 1) = 1 depth threshold on every one-item backlog.
    warnings: list[str] = []
    if item_count > 1 and any(deps[i] for i in by_id):
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


def cmd_backlog_topology(items: list[dict], *, with_clusters: bool) -> dict:
    """Assemble the ``backlog-topology`` payload.

    Args:
        items: The runner's ``listCommand`` item array.
        with_clusters: When true, append the ``clusters`` section.

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
    for forward-compatibility). All failures raise ``UsageError`` → exit 2,
    never a partial/guessed result. This is the ONLY input path for the
    topology verb — it never opens ``backlog.json`` off disk (single data
    source, decision V-007).

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


def _print_topology(payload: dict) -> None:
    """Human-readable topology summary (machine consumers pass ``--json``)."""
    print(
        f"Topology: {payload['itemCount']} items, {payload['rootCount']} roots, "
        f"max chain depth {payload['maxChainDepth']}, selectable {payload['selectable']}"
    )
    for row in sorted(payload["roots"], key=lambda r: -r["gatedCount"]):
        print(f"  root {row['id']} gates {row['gatedCount']} item(s)")
    for warning in payload["warnings"]:
        print(f"  warning: {warning}")
    starvation = payload.get("starvation")
    if starvation:
        blocking = ", ".join(r["id"] for r in starvation["blockingRoots"])
        print(f"  starved: no selectable item; blocking roots: {blocking}")
    for cluster in payload.get("clusters", []):
        members = ", ".join(cluster["memberIds"])
        print(
            f"  cluster {cluster['clusterId']}: members {members} "
            f"(gates {cluster['gatedCount']} item(s))"
        )


__all__ = [
    "CLUSTER_JACCARD_THRESHOLD",
    "TOPOLOGY_FANOUT_WARN_RATIO",
    "TOPOLOGY_DEPTH_WARN_RATIO",
    "_id_key",
    "_build_dep_index",
    "_transitive_dependents",
    "_normalize_reason",
    "_jaccard",
    "cluster_blocked",
    "_max_chain_depth",
    "compute_topology",
    "cmd_backlog_topology",
    "_load_topology_items",
    "_print_topology",
]
