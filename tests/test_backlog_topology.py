"""Topology guards — ``compute_topology`` and the ``backlog-topology`` verb.

Pins the dependency-topology metrics in ``scripts/forge-session.py``: graph
fixtures (line, diamond, parallel roots, trivial, cycle), the observed-incident
fixture (16 items, 3 roots gating 81%, a 13-deep chain) that both advisory
warn tokens and the starvation shape are calibrated against, status-aware
``selectable`` counting, determinism across shuffled input, a linear-perf guard
on a synthetic ~1000-item chain, and the verb's CLI contract (``--cluster``
gating, source-flag exclusivity, exit-2 error model, no ``backlog.json`` read).

``scripts/forge-session.py`` is hyphen-named, so it is loaded by path via
importlib rather than imported. Stdlib only.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
import json
import math
import random
import subprocess
import sys
import textwrap
import time

from _forge_paths import SCRIPTS

FORGE_SESSION = SCRIPTS / "forge-session.py"


def _load_forge_session():
    """Load `scripts/forge-session.py` as a module (its name is not importable)."""
    spec = importlib.util.spec_from_file_location("forge_session_under_test", FORGE_SESSION)
    assert spec and spec.loader, f"cannot load {FORGE_SESSION}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FS = _load_forge_session()


def _item(
    item_id: str,
    *,
    status: str = "pending",
    depends_on: list[str] | None = None,
    reason: str | None = None,
) -> dict:
    """A minimal runner-shaped backlog item."""
    return {
        "id": item_id,
        "status": status,
        "blockedReason": reason,
        "dependsOn": depends_on or [],
    }


def _run(*argv: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    """Run the forge-session CLI out of process."""
    return subprocess.run(
        [sys.executable, str(FORGE_SESSION), *argv],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=60,
    )


# --------------------------------------------------------------------------- #
# Module constants
# --------------------------------------------------------------------------- #


class TestTopologyConstants:
    def test_warn_ratios_are_half(self):
        assert FS.TOPOLOGY_FANOUT_WARN_RATIO == 0.5
        assert FS.TOPOLOGY_DEPTH_WARN_RATIO == 0.5

    def test_recovery_min_runner_version(self):
        assert FS.RECOVERY_MIN_RUNNER_VERSION == "0.14.0"

    def test_loop_runner_min_version_floor_unchanged(self):
        """RECOVERY_MIN_RUNNER_VERSION is a capability threshold, NOT the install
        floor — loopRunner.minRunnerVersion in the config schema stays 0.6.0."""
        schema = json.loads(
            (FORGE_SESSION.parent.parent / "references" / "forge-config-schema.json")
            .read_text(encoding="utf-8")
        )
        min_version = schema["properties"]["loopRunner"]["properties"]["minRunnerVersion"]
        assert min_version["default"] == "0.6.0"


# --------------------------------------------------------------------------- #
# Graph fixtures
# --------------------------------------------------------------------------- #


class TestLineGraph:
    """a -> b -> c -> d (each item depends on the previous)."""

    ITEMS = [
        _item("1"),
        _item("2", depends_on=["1"]),
        _item("3", depends_on=["2"]),
        _item("4", depends_on=["3"]),
    ]

    def test_metrics(self):
        topo = FS.compute_topology(self.ITEMS)
        assert topo["itemCount"] == 4
        assert topo["rootCount"] == 1
        assert topo["roots"] == [{"id": "1", "gatedCount": 3, "gatedIds": ["2", "3", "4"]}]
        assert topo["maxChainDepth"] == 4

    def test_warnings_fire_on_deep_gating_line(self):
        # threshold = ceil(0.5 * 4) = 2; root gates 3 >= 2, depth 4 >= 2
        topo = FS.compute_topology(self.ITEMS)
        assert topo["warnings"] == ["single-root-fanout", "chain-depth"]

    def test_only_the_root_is_selectable(self):
        topo = FS.compute_topology(self.ITEMS)
        assert topo["selectable"] == 1
        assert topo["starvation"] is None


class TestDiamondGraph:
    """a at the top; b and c depend on a; d depends on b and c."""

    ITEMS = [
        _item("a"),
        _item("b", depends_on=["a"]),
        _item("c", depends_on=["a"]),
        _item("d", depends_on=["b", "c"]),
    ]

    def test_metrics(self):
        topo = FS.compute_topology(self.ITEMS)
        assert topo["itemCount"] == 4
        assert topo["rootCount"] == 1
        assert topo["roots"] == [{"id": "a", "gatedCount": 3, "gatedIds": ["b", "c", "d"]}]
        assert topo["maxChainDepth"] == 3

    def test_selectable_after_partial_completion(self):
        items = [
            _item("a", status="done"),
            _item("b", depends_on=["a"]),
            _item("c", depends_on=["a"]),
            _item("d", depends_on=["b", "c"]),
        ]
        # b and c have their only dep done; d still waits on both.
        assert FS.compute_topology(items)["selectable"] == 2


class TestParallelRoots:
    """Three independent roots — no edges at all."""

    ITEMS = [_item("1"), _item("2"), _item("3")]

    def test_metrics_and_no_warnings(self):
        topo = FS.compute_topology(self.ITEMS)
        assert topo["itemCount"] == 3
        assert topo["rootCount"] == 3
        assert [r["id"] for r in topo["roots"]] == ["1", "2", "3"]
        assert all(r["gatedCount"] == 0 and r["gatedIds"] == [] for r in topo["roots"])
        assert topo["maxChainDepth"] == 1
        assert topo["warnings"] == []
        assert topo["selectable"] == 3


class TestTrivialGraph:
    def test_single_node_no_warnings(self):
        topo = FS.compute_topology([_item("1")])
        assert topo["itemCount"] == 1
        assert topo["rootCount"] == 1
        assert topo["maxChainDepth"] == 1
        assert topo["warnings"] == []
        assert topo["selectable"] == 1
        assert topo["starvation"] is None

    def test_empty_backlog(self):
        topo = FS.compute_topology([])
        assert topo["itemCount"] == 0
        assert topo["rootCount"] == 0
        assert topo["roots"] == []
        assert topo["maxChainDepth"] == 0
        assert topo["warnings"] == []
        assert topo["selectable"] == 0
        assert topo["starvation"] is None


class TestCycleGraph:
    """rauf rejects cycles upstream; the visited-set guard must still terminate."""

    ITEMS = [
        _item("1", depends_on=["2"]),
        _item("2", depends_on=["1"]),
        _item("3", depends_on=["1"]),
    ]

    def test_terminates_and_keeps_the_shape(self):
        topo = FS.compute_topology(self.ITEMS)
        assert topo["itemCount"] == 3
        assert set(topo) == {
            "itemCount", "rootCount", "roots", "maxChainDepth",
            "selectable", "starvation", "warnings",
        }
        # No node is dep-free, so there are no roots and nothing is selectable.
        assert topo["rootCount"] == 0
        assert topo["selectable"] == 0
        assert topo["starvation"] == {"starved": True, "blockingRoots": []}

    def test_external_deps_are_dropped(self):
        # An item whose only dependsOn targets are outside the backlog is a root.
        items = [_item("1", depends_on=["999"]), _item("2", depends_on=["1"])]
        topo = FS.compute_topology(items)
        assert topo["rootCount"] == 1
        assert topo["roots"][0]["id"] == "1"
        assert topo["maxChainDepth"] == 2


# --------------------------------------------------------------------------- #
# The observed-incident fixture (SC-1 substrate).
#
# Reproduces the real stranded-backlog topology: 16 items, 3 roots whose gated
# subtrees union to 13/16 = 81%, and a 13-deep dependsOn chain. All three roots
# are blocked, so nothing is selectable and the whole tree is starved.
# --------------------------------------------------------------------------- #


def _incident_items() -> list[dict]:
    items = [_item("001", status="blocked", reason="shared systemic cause")]
    # The 13-deep chain: 001 <- 002 <- ... <- 013.
    for n in range(2, 14):
        items.append(_item(f"{n:03d}", depends_on=[f"{n - 1:03d}"]))
    # Two more blocked roots, jointly gating 016.
    items.append(_item("014", status="blocked", reason="shared systemic cause"))
    items.append(_item("015", status="blocked", reason="shared systemic cause"))
    items.append(_item("016", depends_on=["014", "015"]))
    return items


class TestObservedIncident:
    def test_both_warnings_fire_in_order(self):
        topo = FS.compute_topology(_incident_items())
        assert topo["warnings"] == ["single-root-fanout", "chain-depth"]

    def test_metrics(self):
        topo = FS.compute_topology(_incident_items())
        assert topo["itemCount"] == 16
        assert topo["rootCount"] == 3
        assert topo["maxChainDepth"] == 13
        # 3 roots gating 81%: the union of the gated subtrees is 13/16 items.
        gated_union = set()
        for root in topo["roots"]:
            gated_union.update(root["gatedIds"])
        assert len(gated_union) == 13
        assert len(gated_union) / topo["itemCount"] > 0.8

    def test_threshold_arithmetic_uses_ceil(self):
        topo = FS.compute_topology(_incident_items())
        threshold = math.ceil(0.5 * topo["itemCount"])
        assert threshold == 8
        assert max(r["gatedCount"] for r in topo["roots"]) >= threshold
        assert topo["maxChainDepth"] >= threshold

    def test_starvation_names_the_three_blocking_roots(self):
        topo = FS.compute_topology(_incident_items())
        assert topo["selectable"] == 0
        starvation = topo["starvation"]
        assert starvation["starved"] is True
        assert [r["id"] for r in starvation["blockingRoots"]] == ["001", "014", "015"]
        by_id = {r["id"]: r for r in starvation["blockingRoots"]}
        assert by_id["001"]["gatedCount"] == 12
        assert by_id["014"]["gatedCount"] == 1
        assert by_id["015"]["gatedCount"] == 1


# --------------------------------------------------------------------------- #
# selectable correctness (status-aware)
# --------------------------------------------------------------------------- #


class TestSelectable:
    def test_counts_exactly_pending_with_all_deps_done(self):
        items = [
            _item("1", status="done"),
            _item("2", status="blocked", reason="stuck"),
            _item("3", depends_on=["1"]),           # pending, dep done -> selectable
            _item("4", depends_on=["2"]),           # pending, dep blocked -> not
            _item("5", depends_on=["1", "2"]),      # one dep not done -> not
            _item("6", status="done", depends_on=["1"]),  # done -> never counted
            _item("7"),                              # pending root -> selectable
        ]
        assert FS.compute_topology(items)["selectable"] == 2

    def test_no_starvation_while_pending_is_zero(self):
        items = [_item("1", status="done"), _item("2", status="blocked", reason="x")]
        topo = FS.compute_topology(items)
        assert topo["selectable"] == 0
        assert topo["starvation"] is None

    def test_starvation_excludes_done_and_zero_gate_roots(self):
        items = [
            _item("1", status="done"),
            _item("2", status="blocked", reason="x"),  # root, gates 3
            _item("3", depends_on=["2"]),
            _item("4", status="blocked", reason="y"),  # root, gates nothing
        ]
        topo = FS.compute_topology(items)
        assert topo["starvation"]["starved"] is True
        assert [r["id"] for r in topo["starvation"]["blockingRoots"]] == ["2"]


# --------------------------------------------------------------------------- #
# Determinism
# --------------------------------------------------------------------------- #


class TestDeterminism:
    def test_stable_across_shuffled_input(self):
        items = _incident_items()
        baseline = FS.compute_topology(items)
        rng = random.Random(42)
        for _ in range(10):
            shuffled = list(items)
            rng.shuffle(shuffled)
            assert FS.compute_topology(shuffled) == baseline

    def test_roots_sorted_numerically_not_lexically(self):
        items = [
            _item("10", depends_on=[]),
            _item("2", depends_on=[]),
            _item("1", depends_on=["2", "10"]),
        ]
        topo = FS.compute_topology(items)
        assert [r["id"] for r in topo["roots"]] == ["2", "10"]


# --------------------------------------------------------------------------- #
# Linear-perf guard (a regression tripwire, not a benchmark)
# --------------------------------------------------------------------------- #


class TestLinearPerf:
    def test_thousand_item_chain_is_fast(self):
        n = 1000
        items = [_item("1")]
        items += [_item(str(i), depends_on=[str(i - 1)]) for i in range(2, n + 1)]
        old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(max(old_limit, 10 * n))  # the memoized DFS recurses per chain link
        try:
            start = time.perf_counter()
            topo = FS.compute_topology(items)
            elapsed = time.perf_counter() - start
        finally:
            sys.setrecursionlimit(old_limit)
        assert topo["maxChainDepth"] == n
        assert topo["roots"][0]["gatedCount"] == n - 1
        # Memoized DFS finishes in well under a second; an accidental
        # exponential/cubic regression blows far past this generous bound.
        assert elapsed < 10.0, f"compute_topology took {elapsed:.2f}s on a {n}-item chain"


# --------------------------------------------------------------------------- #
# The backlog-topology verb (CLI contract)
# --------------------------------------------------------------------------- #


class TestBacklogTopologyVerb:
    def test_stdin_json_and_cluster_gating(self):
        payload = json.dumps(_incident_items())
        without = _run("backlog-topology", "--items-stdin", "--json", stdin=payload)
        assert without.returncode == 0, without.stderr
        topo = json.loads(without.stdout)
        assert "clusters" not in topo
        assert topo["warnings"] == ["single-root-fanout", "chain-depth"]

        with_clusters = _run(
            "backlog-topology", "--items-stdin", "--cluster", "--json", stdin=payload
        )
        assert with_clusters.returncode == 0, with_clusters.stderr
        clustered = json.loads(with_clusters.stdout)
        # The three blocked roots share one verbatim reason -> one cluster.
        assert [c["memberIds"] for c in clustered["clusters"]] == [["001", "014", "015"]]
        del clustered["clusters"]
        assert clustered == topo

    def test_items_json_file_and_object_form(self, tmp_path):
        # Object-with-items form is tolerated for forward-compatibility.
        path = tmp_path / "items.json"
        path.write_text(json.dumps({"items": _incident_items()}), encoding="utf-8")
        result = _run("backlog-topology", "--items-json", str(path), "--json")
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["itemCount"] == 16

    def test_human_output_without_json(self):
        result = _run("backlog-topology", "--items-stdin", stdin=json.dumps(_incident_items()))
        assert result.returncode == 0, result.stderr
        assert "16 items, 3 roots" in result.stdout
        assert "single-root-fanout" in result.stdout

    def test_neither_source_is_exit_2(self):
        result = _run("backlog-topology", "--json")
        assert result.returncode == 2
        assert result.stdout == ""
        assert result.stderr.startswith("Error:")

    def test_both_sources_is_exit_2(self, tmp_path):
        path = tmp_path / "items.json"
        path.write_text("[]", encoding="utf-8")
        result = _run(
            "backlog-topology", "--items-json", str(path), "--items-stdin", stdin="[]"
        )
        assert result.returncode == 2
        assert result.stdout == ""
        assert result.stderr.startswith("Error:")

    def test_unreadable_items_json_is_exit_2(self, tmp_path):
        result = _run("backlog-topology", "--items-json", str(tmp_path / "missing.json"))
        assert result.returncode == 2
        assert result.stdout == ""
        assert result.stderr.startswith("Error:")

    def test_invalid_json_is_exit_2(self):
        result = _run("backlog-topology", "--items-stdin", stdin="not json {")
        assert result.returncode == 2
        assert result.stdout == ""
        assert result.stderr.startswith("Error:")

    def test_non_array_shape_is_exit_2(self):
        for bad in ('"a string"', "42", '{"items": 7}'):
            result = _run("backlog-topology", "--items-stdin", stdin=bad)
            assert result.returncode == 2, bad
            assert result.stdout == ""
            assert result.stderr.startswith("Error:")

    def test_topology_path_never_reads_backlog_json(self):
        """Single data source: the verb consumes only --items-json/--items-stdin.

        Docstrings legitimately SAY "never reads backlog.json", so the scan runs
        over the docstring-free ast.unparse of the code, not the raw source.
        """
        for fn in (
            FS.compute_topology,
            FS._max_chain_depth,
            FS.cmd_backlog_topology,
            FS._load_topology_items,
        ):
            tree = ast.parse(textwrap.dedent(inspect.getsource(fn)))
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    if ast.get_docstring(node) is not None:
                        node.body = node.body[1:] or [ast.Pass()]
            code = ast.unparse(tree)
            assert "backlog.json" not in code, fn.__name__
