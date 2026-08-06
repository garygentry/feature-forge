"""Jaccard clustering guards — ``cluster_blocked`` and its normalization helpers.

Pins the deterministic systemic-cause clustering substrate in
``scripts/forge-session.py``: reason normalization (noise-token dropping, token
SET comparison), the Jaccard measure and its >= 0.5 boundary, union-find
transitivity, output determinism across shuffled input, the cluster entry shape
(clusterId / gated blast radius), and the vendored one-cause-three-phrasings
incident fixture (V-015) that makes ``CLUSTER_JACCARD_THRESHOLD`` falsifiable
against the real failure that motivated it.

``scripts/forge-session.py`` is hyphen-named, so it is loaded by path via
importlib rather than imported. Stdlib only.
"""

from __future__ import annotations

import importlib.util
from itertools import permutations

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
    reason: str | None = None,
    depends_on: list[str] | None = None,
) -> dict:
    """A minimal runner-shaped backlog item."""
    return {
        "id": item_id,
        "status": status,
        "blockedReason": reason,
        "dependsOn": depends_on or [],
    }


# --------------------------------------------------------------------------- #
# The V-015 vendored incident fixture.
#
# The three blockedReason strings below are copied VERBATIM from the actual
# verify-test-debt run that motivated this feature (items 001, 002, 004 — one
# shared systemic cause phrased three ways). They are vendored into this file,
# NOT read from any .rauf archive (archives are prunable). Item 001's leading
# space is part of the observed string and is preserved.
#
# Measured pairwise Jaccard under _normalize_reason (recorded so a future
# threshold change that would re-split the incident is caught):
#   001-002: 0.5469
#   001-004: 0.5278  <- the binding pair: only ~0.028 over the 0.5 threshold
#   002-004: 0.6406
# Any CLUSTER_JACCARD_THRESHOLD above ~0.5278 splits this incident back into
# multiple prompts; the one-cluster assertion below is the calibration pin.
# --------------------------------------------------------------------------- #

_INCIDENT_REASON_001 = (
    ' validate.sh is red at HEAD on 3 pre-existing traceability orphans '
    '(REQ-DEBT-04/REQ-REL-01/REQ-STATE-01, foreign ids quoted from antecedent-feature '
    'test docstrings, recorded as accepted in TRACEABILITY.md but unallowlistable in '
    "validate-traceability.py). Item 001's own ACs 1-6 all pass. Decide: add an "
    'allowlist to validate-traceability.py, declare the ids in PRD.md, or relax the '
    '"All checks passed!" AC across the backlog.'
)
_INCIDENT_REASON_002 = (
    "Item 002's own work is complete and green — only its final AC, `validate.sh` "
    'reporting "All checks passed!", fails, on the same pre-existing traceability '
    'orphans (REQ-DEBT-04/REQ-REL-01/REQ-STATE-01) that blocked item 001. Decide: '
    'add an allowlist to validate-traceability.py, declare the ids in PRD.md, or '
    'relax the "All checks passed!" AC across the backlog.'
)
_INCIDENT_REASON_004 = (
    "Item 004's own ACs 1-6 all pass (constant + two-sided test landed, "
    'mutation-verified, no fixture touched, ruff clean at the 19 ceiling, 1843 '
    'passed). Only AC 7 — `validate.sh` reporting "All checks passed!" — fails, on '
    'the same pre-existing traceability orphans (REQ-DEBT-04/REQ-REL-01/REQ-STATE-01) '
    'that blocked items 001 and 002. Decide: add an allowlist to '
    'validate-traceability.py, declare the ids in PRD.md, or relax the "All checks '
    'passed!" AC across the backlog.'
)


# --------------------------------------------------------------------------- #
# Constant & normalization
# --------------------------------------------------------------------------- #


def test_cluster_jaccard_threshold_is_half():
    """The module-level constant is exactly 0.5 — the value the V-015 pin calibrates."""
    assert FS.CLUSTER_JACCARD_THRESHOLD == 0.5


def test_normalization_drops_pure_number_and_id_shaped_tokens():
    """``42``, ``req12``, ``t7`` are noise; meaningful words survive, lowercased."""
    tokens = FS._normalize_reason("Missing 42 API key for req12 and t7")
    assert tokens == {"missing", "api", "key", "for", "and"}


def test_normalization_is_a_set_and_splits_on_non_alphanumeric():
    """Repetition cannot bias the measure; any non-alphanumeric run is a separator."""
    assert FS._normalize_reason("key KEY key... key/key") == {"key"}
    assert FS._normalize_reason("a-b_c.d(e)") == {"a", "b", "c", "d", "e"}


def test_normalization_of_none_and_empty_is_empty_set():
    assert FS._normalize_reason(None) == set()
    assert FS._normalize_reason("") == set()
    assert FS._normalize_reason("42 007 req12") == set()


def test_jaccard_of_two_empty_sets_is_zero():
    """Empty vs empty is 0.0 by definition here — never a division error, never 1.0."""
    assert FS._jaccard(set(), set()) == 0.0


def test_items_with_empty_reasons_never_cluster_together():
    """Two blocked items with no meaningful tokens stay singletons (0.0 < 0.5)."""
    items = [
        _item("1", status="blocked", reason=""),
        _item("2", status="blocked", reason="42 req12"),  # all tokens are noise
    ]
    clusters = FS.cluster_blocked(items)
    assert [c["memberIds"] for c in clusters] == [["1"], ["2"]]


# --------------------------------------------------------------------------- #
# Jaccard boundary & union-find
# --------------------------------------------------------------------------- #


def test_pair_at_exactly_half_clusters_and_just_below_does_not():
    """The edge condition is >= 0.5: 2/4 == 0.5 joins, 2/5 == 0.4 does not."""
    at_boundary = [
        _item("1", status="blocked", reason="alpha beta gamma"),
        _item("2", status="blocked", reason="alpha beta delta"),
    ]
    assert FS._jaccard(
        FS._normalize_reason("alpha beta gamma"), FS._normalize_reason("alpha beta delta")
    ) == 0.5
    assert [c["memberIds"] for c in FS.cluster_blocked(at_boundary)] == [["1", "2"]]

    just_below = [
        _item("1", status="blocked", reason="alpha beta gamma"),
        _item("2", status="blocked", reason="alpha beta delta epsilon"),
    ]
    assert [c["memberIds"] for c in FS.cluster_blocked(just_below)] == [["1"], ["2"]]


def test_union_find_transitivity_yields_one_cluster():
    """A~B and B~C but A!~C directly still forms one {A, B, C} component."""
    reasons = {
        "1": "alpha beta gamma",  # ~ item 2 (2/4 = 0.5)
        "2": "alpha beta delta",  # ~ item 3 (2/4 = 0.5)
        "3": "alpha delta epsilon",  # vs item 1: 1/5 = 0.2 — below threshold
    }
    assert FS._jaccard(
        FS._normalize_reason(reasons["1"]), FS._normalize_reason(reasons["3"])
    ) < 0.5
    items = [_item(i, status="blocked", reason=r) for i, r in reasons.items()]
    clusters = FS.cluster_blocked(items)
    assert [c["memberIds"] for c in clusters] == [["1", "2", "3"]]
    assert clusters[0]["clusterId"] == "c1"


def test_only_blocked_items_participate():
    """Similar reasons on non-blocked items never form or join clusters."""
    items = [
        _item("1", status="blocked", reason="alpha beta gamma"),
        _item("2", status="pending", reason="alpha beta gamma"),
        _item("3", status="done", reason="alpha beta gamma"),
    ]
    clusters = FS.cluster_blocked(items)
    assert [c["memberIds"] for c in clusters] == [["1"]]


# --------------------------------------------------------------------------- #
# Output shape, ordering & determinism
# --------------------------------------------------------------------------- #


def test_cluster_entry_shape_and_gated_blast_radius():
    """clusterId is "c"+lowest member id; gated = union of subtrees minus members.

    Item 3 depends on item 2, so 3 sits inside 2's gated subtree — but as a
    cluster member it must be excluded from the cluster's own blast radius.
    """
    items = [
        _item("2", status="blocked", reason="alpha beta gamma"),
        _item("3", status="blocked", reason="alpha beta delta", depends_on=["2"]),
        _item("4", status="pending", depends_on=["2"]),
        _item("5", status="pending", depends_on=["4"]),
        _item("6", status="pending", depends_on=["3"]),
        _item("7", status="pending"),  # unrelated: gated by nobody
    ]
    clusters = FS.cluster_blocked(items)
    assert len(clusters) == 1
    (cluster,) = clusters
    assert cluster["clusterId"] == "c2"
    assert cluster["memberIds"] == ["2", "3"]
    assert cluster["memberReasons"] == ["alpha beta gamma", "alpha beta delta"]
    assert cluster["sharedTokens"] == ["alpha", "beta"]
    assert cluster["gatedIds"] == ["4", "5", "6"]
    assert cluster["gatedCount"] == 3
    assert set(cluster) == {
        "clusterId", "memberIds", "memberReasons", "sharedTokens", "gatedIds", "gatedCount",
    }


def test_numeric_ids_sort_numerically_for_root_and_ordering():
    """"2" beats "10" as the component root and in member order (numeric, not lexical)."""
    items = [
        _item("10", status="blocked", reason="alpha beta gamma"),
        _item("2", status="blocked", reason="alpha beta delta"),
    ]
    (cluster,) = FS.cluster_blocked(items)
    assert cluster["clusterId"] == "c2"
    assert cluster["memberIds"] == ["2", "10"]


def test_clusters_are_sorted_by_lowest_member_id():
    items = [
        _item("9", status="blocked", reason="omega psi chi"),
        _item("1", status="blocked", reason="alpha beta gamma"),
        _item("4", status="blocked", reason="alpha beta delta"),
    ]
    clusters = FS.cluster_blocked(items)
    assert [c["clusterId"] for c in clusters] == ["c1", "c9"]
    assert [c["memberIds"] for c in clusters] == [["1", "4"], ["9"]]


def test_output_is_deterministic_across_shuffled_input():
    """Every permutation of the item array yields byte-identical clusters."""
    base = [
        _item("1", status="blocked", reason="alpha beta gamma"),
        _item("2", status="blocked", reason="alpha beta delta"),
        _item("3", status="blocked", reason="omega psi chi"),
        _item("4", status="pending", depends_on=["1"]),
    ]
    expected = FS.cluster_blocked(base)
    for perm in permutations(base):
        assert FS.cluster_blocked(list(perm)) == expected


# --------------------------------------------------------------------------- #
# V-015: the vendored incident + the over-merge guard
# --------------------------------------------------------------------------- #


def test_v015_incident_reasons_cluster_into_exactly_one_candidate():
    """The three real one-cause phrasings form ONE cluster — the calibration pin.

    The binding pair (001 vs 004) measures Jaccard 0.5278, only ~0.028 over
    CLUSTER_JACCARD_THRESHOLD = 0.5 (all three pairs recorded at the fixture
    definition above). If a threshold change re-splits this incident, this test
    is the tripwire.
    """
    items = [
        _item("001", status="blocked", reason=_INCIDENT_REASON_001),
        _item("002", status="blocked", reason=_INCIDENT_REASON_002),
        _item("004", status="blocked", reason=_INCIDENT_REASON_004),
    ]
    clusters = FS.cluster_blocked(items)
    assert len(clusters) == 1
    assert clusters[0]["memberIds"] == ["001", "002", "004"]
    assert clusters[0]["clusterId"] == "c001"

    # The margin the fixture comment records, re-measured so the comment cannot rot.
    binding = FS._jaccard(
        FS._normalize_reason(_INCIDENT_REASON_001), FS._normalize_reason(_INCIDENT_REASON_004)
    )
    assert 0.52 < binding < 0.54
    assert binding - FS.CLUSTER_JACCARD_THRESHOLD < 0.03


def test_two_genuinely_distinct_causes_do_not_merge():
    """Over-clustering is the forbidden failure direction: distinct causes stay apart."""
    items = [
        _item("1", status="blocked", reason=_INCIDENT_REASON_001),
        _item(
            "2",
            status="blocked",
            reason="Design decision needed: should the pagination API expose cursor "
            "tokens or page numbers? The mobile client team must weigh in.",
        ),
    ]
    clusters = FS.cluster_blocked(items)
    assert [c["memberIds"] for c in clusters] == [["1"], ["2"]]
