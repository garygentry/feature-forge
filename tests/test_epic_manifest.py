"""Unit tests for the epic-manifest helper (scripts/epic-manifest.py).

This file is co-authored by two backlog items:

* **010a (this part)** — structural, validation, resolution, and exit-code
  tests (05 §3.1–3.6, 3.10, 3.11, 3.13). Function names are prefixed
  ``test_struct_*`` / ``test_resolve_*`` / ``test_validate_*`` / ``test_exit_*``
  / ``test_find_cycle_*`` to stay disjoint from 010b's additions.
* **010b** — status-derivation, render-status, atomic-write, and performance
  tests. It appends functions (e.g. ``test_status_*`` / ``test_render_*`` /
  ``test_atomic_*`` / ``test_perf_*``) to this same file.

Assertions target the contracts in 00-core-definitions.md §4 (Finding codes),
§7 (completion), §9 (exit codes). Where 02-manifest-helper-cli.md fixes an exact
flag or message that differs from an illustrative assertion in 05 §3, **02
wins**: e.g. ``resolve`` and ``check-name`` have **no** ``--json`` flag (their
findings print to stderr as ``code: message``), and cycle messages use the
``→`` arrow. Tests therefore assert on finding *codes* and message *shape*, not
brittle exact strings.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# §3.1 Valid manifest round-trip (REQ-EPIC-02/03)
# ---------------------------------------------------------------------------


def test_struct_valid_manifest_round_trip(run_cli, fixture_copy) -> None:
    """A well-formed epic validates clean, survives a mutation, re-validates clean."""
    specs = fixture_copy("valid-epic")
    epic = "auth-overhaul"

    first = run_cli("validate", epic, "--specs-dir", str(specs), "--json")
    assert first.returncode == 0
    assert first.json() == {"valid": True, "findings": []}

    # Mutate: add a new leaf feature with no deps (atomic write + re-validate).
    # --charter is a required option (02 §7.1).
    added = run_cli(
        "add-feature", epic, "metrics",
        "--charter", "Metrics collection leaf feature.",
        "--specs-dir", str(specs),
    )
    assert added.returncode == 0

    again = run_cli("validate", epic, "--specs-dir", str(specs), "--json")
    assert again.returncode == 0
    assert again.json()["valid"] is True


# ---------------------------------------------------------------------------
# §3.2 Schema conformance / cached-status (REQ-EPIC-02, REQ-STATE-02)
# ---------------------------------------------------------------------------


def test_validate_per_feature_status_field_rejected(run_cli, fixture_copy) -> None:
    """A Feature illegally carrying a status field fails validation (REQ-STATE-02)."""
    specs = fixture_copy("valid-epic")
    manifest = specs / "auth-overhaul" / "epic-manifest.json"
    data = json.loads(manifest.read_text())
    data["features"][0]["status"] = "complete"   # illegal cached status
    manifest.write_text(json.dumps(data))

    result = run_cli("validate", "auth-overhaul", "--specs-dir", str(specs), "--json")
    assert result.returncode == 1
    codes = {f["code"] for f in result.json()["findings"]}
    assert "cached-status" in codes


def test_validate_missing_required_field_is_schema(run_cli, fixture_copy) -> None:
    """A manifest missing a required top-level field fails with a 'schema' finding."""
    specs = fixture_copy("valid-epic")
    manifest = specs / "auth-overhaul" / "epic-manifest.json"
    data = json.loads(manifest.read_text())
    del data["narrativeDoc"]   # required top-level key (00 §2.1)
    manifest.write_text(json.dumps(data))

    result = run_cli("validate", "auth-overhaul", "--specs-dir", str(specs), "--json")
    assert result.returncode == 1
    codes = {f["code"] for f in result.json()["findings"]}
    assert "schema" in codes


def test_validate_unknown_key_is_schema(run_cli, fixture_copy) -> None:
    """An unknown key (e.g. a typo'd field) fails with a 'schema' finding (REQ-ROBUST-02).

    Guards against the silent-drop failure mode where a hand-edited manifest with a
    mistyped key like 'dependson' would otherwise validate clean. Mirrors the schema's
    additionalProperties:false contract.
    """
    specs = fixture_copy("valid-epic")
    manifest = specs / "auth-overhaul" / "epic-manifest.json"
    data = json.loads(manifest.read_text())
    data["features"][0]["dependson"] = []   # typo'd 'dependsOn' -> unknown key
    manifest.write_text(json.dumps(data))

    result = run_cli("validate", "auth-overhaul", "--specs-dir", str(specs), "--json")
    assert result.returncode == 1
    codes = {f["code"] for f in result.json()["findings"]}
    assert "schema" in codes


# ---------------------------------------------------------------------------
# §3.3 Cyclic graph rejection (REQ-EPIC-05)
# ---------------------------------------------------------------------------


def test_validate_cyclic_graph_rejected(run_cli, fixtures_dir) -> None:
    """A dependsOn cycle yields a 'cycle' finding and exit 1 (REQ-EPIC-05)."""
    result = run_cli(
        "validate", "cyclic-epic", "--specs-dir", str(fixtures_dir / "cyclic-epic"),
        "--json",
    )
    assert result.returncode == 1
    findings = result.json()["findings"]
    assert any(f["code"] == "cycle" for f in findings)
    # Message shape is normative (00 §4.2): the cycle path is arrow-joined.
    assert any("→" in f["message"] for f in findings)


def test_find_cycle_detects_and_clears(helper_module) -> None:
    """find_cycle returns a node path for a cyclic graph, None for a DAG."""
    cyclic = [
        {"name": "a", "dependsOn": ["b"]},
        {"name": "b", "dependsOn": ["a"]},
    ]
    acyclic = [
        {"name": "a", "dependsOn": []},
        {"name": "b", "dependsOn": ["a"]},
    ]
    assert helper_module.find_cycle(cyclic) is not None
    assert helper_module.find_cycle(acyclic) is None


def test_find_cycle_self_dependency(helper_module) -> None:
    """A feature depending on itself is a degenerate cycle (00 §2.6 inv. 5)."""
    self_dep = [{"name": "x", "dependsOn": ["x"]}]
    assert helper_module.find_cycle(self_dep) == ["x", "x"]


def test_find_cycle_ignores_dangling_edges(helper_module) -> None:
    """find_cycle only follows edges to known names; a dangling dep is not a cycle."""
    dangling = [{"name": "a", "dependsOn": ["ghost"]}]
    assert helper_module.find_cycle(dangling) is None


# ---------------------------------------------------------------------------
# §3.4 Duplicate-name detection — flat vs nested (REQ-DIR-04)
# ---------------------------------------------------------------------------


def test_check_name_rejects_existing(run_cli, fixture_copy) -> None:
    """check-name rejects a name already present in the tree (REQ-DIR-04).

    check-name has no --json (02 wins); the duplicate-name finding prints to
    stderr as ``duplicate-name: ...``.
    """
    specs = fixture_copy("dup-name")
    result = run_cli("check-name", "token-service", "--specs-dir", str(specs))
    assert result.returncode == 1
    assert "duplicate-name" in result.stderr


def test_check_name_accepts_free_name(run_cli, fixture_copy) -> None:
    """check-name of an unused name exits 0 (no new collision)."""
    specs = fixture_copy("valid-epic")
    result = run_cli("check-name", "brand-new-name", "--specs-dir", str(specs))
    assert result.returncode == 0


def test_resolve_ambiguous_name(run_cli, tmp_path) -> None:
    """A name matching two NESTED feature dirs (no flat) resolves as ambiguous.

    The dup-name fixture has a flat token-service, which short-circuits resolve
    to the flat path (flat match wins, 02 §5). To exercise the 'ambiguous'
    code we build two nested matches with no flat dir of the same name.
    """
    specs = tmp_path / "specs"
    for epic in ("epic-a", "epic-b"):
        member = specs / epic / "token-service"
        member.mkdir(parents=True)
        (member / ".pipeline-state.json").write_text("{}")

    result = run_cli("resolve", "token-service", "--specs-dir", str(specs))
    assert result.returncode == 1
    # resolve has no --json; the ambiguous finding prints to stderr.
    assert "ambiguous" in result.stderr


# ---------------------------------------------------------------------------
# §3.5 Corrupt-JSON handling (REQ-ROBUST-02)
# ---------------------------------------------------------------------------


def test_validate_corrupt_manifest_no_crash(run_cli, fixtures_dir) -> None:
    """A non-parseable manifest yields 'corrupt-json' and exit 1, not a crash."""
    result = run_cli(
        "validate", "corrupt", "--specs-dir", str(fixtures_dir / "corrupt"), "--json",
    )
    assert result.returncode == 1
    assert "Traceback" not in result.stderr
    codes = {f["code"] for f in result.json()["findings"]}
    assert "corrupt-json" in codes


# ---------------------------------------------------------------------------
# §3.6 Path-escape / unsafe-name rejection (REQ-SEC-02)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["../escape", "a/b", "/abs/path", ".."])
def test_resolve_unsafe_name_exit_2(run_cli, fixture_copy, bad: str) -> None:
    """An unsafe name argument is rejected before FS access with exit 2 (REQ-SEC-02)."""
    specs = fixture_copy("valid-epic")
    result = run_cli("resolve", bad, "--specs-dir", str(specs))
    assert result.returncode == 2


def test_validate_path_escape_in_manifest_is_finding(run_cli, fixtures_dir) -> None:
    """The bad name yields unsafe-name; the escaping consumes.from yields dangling-ref."""
    result = run_cli(
        "validate", "path-escape", "--specs-dir", str(fixtures_dir / "path-escape"),
        "--json",
    )
    assert result.returncode == 1
    codes = {f["code"] for f in result.json()["findings"]}
    # The fixture carries two distinct defects; pin each independently.
    assert "unsafe-name" in codes      # the '../escape' feature name
    assert "dangling-ref" in codes     # the '../x' consumes.from references no sibling


# ---------------------------------------------------------------------------
# §3.10 Dangling-dependsOn detection (REQ-ROBUST-02)
# ---------------------------------------------------------------------------


def test_validate_dangling_depends_on(run_cli, fixture_copy) -> None:
    """A dependsOn referencing an unknown feature yields a 'dangling-ref' finding."""
    specs = fixture_copy("valid-epic")
    manifest = specs / "auth-overhaul" / "epic-manifest.json"
    data = json.loads(manifest.read_text())
    # token-service.dependsOn = ["config-store"] -> typo to an unknown member.
    ts = next(f for f in data["features"] if f["name"] == "token-service")
    ts["dependsOn"] = ["config-stor"]
    manifest.write_text(json.dumps(data))

    result = run_cli("validate", "auth-overhaul", "--specs-dir", str(specs), "--json")
    assert result.returncode == 1
    codes = {f["code"] for f in result.json()["findings"]}
    assert "dangling-ref" in codes


# ---------------------------------------------------------------------------
# §3.11 Resolution — flat / nested / not-found (REQ-DIR-03)
# ---------------------------------------------------------------------------


def test_resolve_flat(run_cli, fixture_copy) -> None:
    """A flat standalone feature resolves to its flat path, exit 0 (REQ-DIR-03)."""
    specs = fixture_copy("dup-name")   # contains an unambiguous flat-only feature
    result = run_cli("resolve", "flat-only", "--specs-dir", str(specs))
    assert result.returncode == 0
    assert result.stdout.strip().endswith("/flat-only")


def test_resolve_nested(run_cli, fixture_copy) -> None:
    """A nested epic member resolves to its nested path, exit 0 (REQ-DIR-03)."""
    specs = fixture_copy("valid-epic")
    result = run_cli("resolve", "token-service", "--specs-dir", str(specs))
    assert result.returncode == 0
    assert result.stdout.strip().endswith("/auth-overhaul/token-service")


def test_resolve_not_found(run_cli, fixture_copy) -> None:
    """An unknown name yields a 'not-found' finding and exit 1 (REQ-DIR-03).

    resolve has no --json; the not-found finding prints to stderr.
    """
    specs = fixture_copy("valid-epic")
    result = run_cli("resolve", "nonexistent", "--specs-dir", str(specs))
    assert result.returncode == 1
    assert "not-found" in result.stderr


# ---------------------------------------------------------------------------
# §3.13 Exit-code contract — 0 / 1 / 2 per (subcommand, outcome) (00 §9)
# ---------------------------------------------------------------------------
#
# Split per fixture because each row needs the matching --specs-dir. This pins
# the resolve / validate / check-name rows of the contract; the mutator rows
# (add-feature/remove-feature/reorder/set-dep/set-status) are item 010b.


def _exit_cases(fixtures_dir: Path) -> list[tuple[list[str], int]]:
    valid = str(fixtures_dir / "valid-epic")
    cyclic = str(fixtures_dir / "cyclic-epic")
    dup = str(fixtures_dir / "dup-name")
    return [
        # validate: valid -> 0 ; findings -> 1 ; missing manifest / IO -> 2
        (["validate", "auth-overhaul", "--specs-dir", valid, "--json"], 0),
        (["validate", "cyclic-epic", "--specs-dir", cyclic, "--json"], 1),
        (["validate", "no-such-epic", "--specs-dir", valid, "--json"], 2),
        # check-name: unique -> 0 ; duplicate -> 1
        (["check-name", "brand-new-name", "--specs-dir", valid], 0),
        (["check-name", "token-service", "--specs-dir", dup], 1),
        # resolve: resolved -> 0 ; unsafe arg -> 2 ; not-found -> 1
        (["resolve", "token-service", "--specs-dir", valid], 0),
        (["resolve", "../escape", "--specs-dir", valid], 2),
        (["resolve", "nonexistent", "--specs-dir", valid], 1),
    ]


@pytest.mark.parametrize(
    "idx",
    range(8),
    ids=[
        "validate-valid-0",
        "validate-findings-1",
        "validate-missing-2",
        "check-name-unique-0",
        "check-name-dup-1",
        "resolve-ok-0",
        "resolve-unsafe-2",
        "resolve-not-found-1",
    ],
)
def test_exit_code_contract(run_cli, fixtures_dir, idx: int) -> None:
    """Each (subcommand, outcome) follows the 0/1/2 exit-code contract (00 §9)."""
    argv, expected = _exit_cases(fixtures_dir)[idx]
    result = run_cli(*argv)
    assert result.returncode == expected


# ===========================================================================
# Item 010b — status-derivation / render-status / atomic-write / performance
# ===========================================================================
#
# Appended to the same file as 010a. Function names are disjoint, prefixed
# ``test_status_*`` / ``test_render_*`` / ``test_atomic_*`` / ``test_perf_*``
# / ``test_mutator_*``. 010b owns the mutator exit-code rows (§3.13) and the
# §3.7–3.9 / §3.12 coverage; together with 010a every subcommand and every
# FindingCode in 00 §4 is exercised.


# ---------------------------------------------------------------------------
# §3.7 Status derivation — every 00 §7 completion branch (REQ-STATE-02, REQ-ORCH-01)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "member, expect_complete",
    [
        ("a", False),   # loop incomplete
        ("b", True),    # loop complete, no impl-verify
        ("c", False),   # loop complete, impl findings-reported (unfixed)
        ("d", True),    # loop complete, impl findings-applied
        ("e", True),    # loop complete, impl passed
    ],
    ids=["a-loop-incomplete", "b-no-implverify", "c-findings-reported",
         "d-findings-applied", "e-passed"],
)
def test_status_derive_branches(
    helper_module, fixtures_dir, member: str, expect_complete: bool
) -> None:
    """Each 00 §7 completion branch derives the correct complete-for-orchestration value."""
    feature_dir = fixtures_dir / "status-derivation" / "lifecycle" / member
    feature_status = helper_module.derive_status(feature_dir)
    # The coarse `status` is "complete" exactly when complete-for-orchestration.
    assert (feature_status["status"] == "complete") is expect_complete


def _write_member_state(feature_dir: Path, state: dict) -> None:
    """Create a member dir with a `.pipeline-state.json` for derive_status tests."""
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / ".pipeline-state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )


def test_status_derive_epic_change_request_counts(helper_module, tmp_path) -> None:
    """derive_status counts open epicChangeRequests + the blocking subset (Phase 2)."""
    d = tmp_path / "feat"
    _write_member_state(d, {
        "currentStage": "forge-1-prd",
        "epicChangeRequests": [
            {"status": "open", "blocksCurrent": True},
            {"status": "open", "blocksCurrent": False},
            {"status": "applied", "blocksCurrent": True},   # not open -> ignored
            {"status": "dismissed", "blocksCurrent": False},  # not open -> ignored
        ],
    })
    row = helper_module.derive_status(d)
    assert row["openEpicChangeRequests"] == 2
    assert row["blockingEpicChangeRequests"] == 1


def test_status_derive_no_epic_change_requests_is_zero(helper_module, tmp_path) -> None:
    """A member with no epicChangeRequests reports both counts as 0."""
    d = tmp_path / "feat"
    _write_member_state(d, {"currentStage": "forge-1-prd"})
    row = helper_module.derive_status(d)
    assert row["openEpicChangeRequests"] == 0
    assert row["blockingEpicChangeRequests"] == 0


def test_status_derive_malformed_epic_change_requests_tolerated(
    helper_module, tmp_path
) -> None:
    """A non-list value or non-dict items count as 0 without raising (tolerance)."""
    d_nonlist = tmp_path / "nonlist"
    _write_member_state(d_nonlist, {
        "currentStage": "forge-1-prd", "epicChangeRequests": "oops",
    })
    row = helper_module.derive_status(d_nonlist)
    assert row["openEpicChangeRequests"] == 0
    assert row["blockingEpicChangeRequests"] == 0

    d_junk = tmp_path / "junk"
    _write_member_state(d_junk, {
        "currentStage": "forge-1-prd",
        "epicChangeRequests": ["not-a-dict", {"status": "open", "blocksCurrent": True}],
    })
    row = helper_module.derive_status(d_junk)
    assert row["openEpicChangeRequests"] == 1
    assert row["blockingEpicChangeRequests"] == 1


def test_status_is_complete_for_orchestration_all_branches(helper_module) -> None:
    """The completion predicate (00 §7) is exact across all five inputs."""
    f = helper_module.is_complete_for_orchestration
    # loop incomplete -> not complete
    assert f({"stages": {"forge-5-loop": {"status": "in_progress"}}}) is False
    # loop complete, no impl-verify -> complete
    assert f({"stages": {"forge-5-loop": {"status": "complete"}}}) is True
    # loop complete + impl findings-reported -> NOT complete
    assert f({"stages": {
        "forge-5-loop": {"status": "complete"},
        "forge-verify-impl": {"status": "findings-reported"},
    }}) is False
    # loop complete + impl findings-applied -> complete
    assert f({"stages": {
        "forge-5-loop": {"status": "complete"},
        "forge-verify-impl": {"status": "findings-applied"},
    }}) is True
    # loop complete + impl passed -> complete
    assert f({"stages": {
        "forge-5-loop": {"status": "complete"},
        "forge-verify-impl": {"status": "passed"},
    }}) is True


def test_status_reflects_edited_pipeline_state(run_cli, fixture_copy) -> None:
    """Editing a member's pipeline-state changes render-status with no refresh step (REQ-STATE-02)."""
    specs = fixture_copy("status-derivation")
    epic = "lifecycle"
    before = run_cli("render-status", epic, "--specs-dir", str(specs), "--json").json()

    state = specs / epic / "a" / ".pipeline-state.json"
    data = json.loads(state.read_text())
    data["stages"]["forge-5-loop"] = {"status": "complete"}
    state.write_text(json.dumps(data))

    after = run_cli("render-status", epic, "--specs-dir", str(specs), "--json").json()
    assert before != after   # live re-derivation, no cache
    a_after = next(f for f in after["features"] if f["name"] == "a")
    assert a_after["status"] == "complete"


def test_status_corrupt_member_state_downgrades_not_started(run_cli, fixture_copy) -> None:
    """A corrupt member .pipeline-state.json downgrades that one feature, no crash."""
    specs = fixture_copy("status-derivation")
    epic = "lifecycle"
    (specs / epic / "e" / ".pipeline-state.json").write_text('{"stages": {oops')

    result = run_cli("render-status", epic, "--specs-dir", str(specs), "--json")
    assert result.returncode == 0
    assert "Traceback" not in result.stderr
    e_row = next(f for f in result.json()["features"] if f["name"] == "e")
    assert e_row["status"] == "not-started"


# ---------------------------------------------------------------------------
# §3.9 render-status correctness — derived sets (REQ-ORCH-03)
# ---------------------------------------------------------------------------


def _complete_names(out: dict) -> set[str]:
    return {f["name"] for f in out["features"] if f["status"] == "complete"}


def test_render_status_derived_sets(run_cli, fixture_copy) -> None:
    """actionable/parallelEligible/rollup are computed over the graph + §7 status."""
    specs = fixture_copy("status-derivation")
    out = run_cli("render-status", "lifecycle", "--specs-dir", str(specs), "--json").json()

    # actionable features are never themselves complete (00 §8).
    assert set(out["actionable"]).isdisjoint(_complete_names(out))
    # Pin exact derived membership for the documented graph: a (in-progress, no
    # deps) and c (in-progress, dep d complete) are actionable; b/d/e are
    # complete and f is blocked on incomplete a.
    assert set(out["actionable"]) == {"a", "c"}
    # parallel-eligible is a subset of actionable (00 §8) and, for this graph
    # where the two actionable features are independent, equals it.
    assert set(out["parallelEligible"]) <= set(out["actionable"])
    assert set(out["parallelEligible"]) == {"a", "c"}
    # rollup counts.
    assert out["rollup"]["total"] == len(out["features"])
    assert out["rollup"]["complete"] == len(_complete_names(out))
    # nextCommand points at a forge stage when work remains.
    if out["actionable"]:
        assert out["nextCommand"].startswith("/feature-forge:")


def test_render_status_flags_unknown_verify_status(run_cli, fixture_copy) -> None:
    """A bogus forge-verify-* status is surfaced as a warning, not silently swallowed (#148).

    Mirrors the reported epic corruption: member ``d`` genuinely finished but its
    ``forge-verify-impl.status`` is typo'd to ``findings-resolved`` (an eye-slip for the
    adjacent ``findingsResolved`` count). It must (a) still count as incomplete, but
    (b) produce a visible warning naming member + stage + value — otherwise its
    dependent ``c`` gains a phantom unmetDep with no diagnostic.
    """
    specs = fixture_copy("status-derivation")
    epic = "lifecycle"
    state = specs / epic / "d" / ".pipeline-state.json"
    data = json.loads(state.read_text())
    data["stages"]["forge-verify-impl"]["status"] = "findings-resolved"
    state.write_text(json.dumps(data))

    result = run_cli("render-status", epic, "--specs-dir", str(specs), "--json")
    assert result.returncode == 0
    out = result.json()

    # (a) the bogus status is surfaced in warnings[], naming member + stage + value.
    assert any(
        "d" in w and "forge-verify-impl" in w and "findings-resolved" in w
        for w in out["warnings"]
    ), out["warnings"]
    # (b) unchanged rollup behavior — unknown counts as incomplete — but now VISIBLE.
    assert "d" not in _complete_names(out)
    d_row = next(f for f in out["features"] if f["name"] == "d")
    assert d_row["status"] != "complete"
    # …and the dependent reflects the (now-explained) incompleteness.
    c_row = next(f for f in out["features"] if f["name"] == "c")
    assert "d" in c_row["unmetDeps"]

    # The text dashboard renders the warning too (not just --json).
    text = run_cli("render-status", epic, "--specs-dir", str(specs)).stdout
    assert "Warnings:" in text
    assert "findings-resolved" in text


def test_verify_status_warnings_tolerates_malformed_values(helper_module) -> None:
    """The warning collector flags non-string / malformed statuses without raising (#148)."""
    w = helper_module._verify_status_warnings
    # Known statuses are silent.
    assert w("m", {"stages": {"forge-verify-impl": {"status": "passed"}}}) == []
    # A missing status (never run) is silent.
    assert w("m", {"stages": {"forge-verify-impl": {"status": None}}}) == []
    # A bogus string is flagged.
    assert len(w("m", {"stages": {"forge-verify-impl": {"status": "nope"}}})) == 1
    # A non-string (list) is flagged, not raised — no unhashable membership crash.
    assert len(w("m", {"stages": {"forge-verify-impl": {"status": ["x"]}}})) == 1
    # A non-dict stages block is tolerated.
    assert w("m", {"stages": "oops"}) == []


def test_render_status_blocked_lists_unmet_deps(run_cli, fixture_copy) -> None:
    """An incomplete feature with an incomplete dependency is blocked with its unmet deps listed."""
    specs = fixture_copy("status-derivation")
    out = run_cli("render-status", "lifecycle", "--specs-dir", str(specs), "--json").json()
    blocked = [f for f in out["features"] if f["blocked"]]
    assert all(f["unmetDeps"] for f in blocked)
    # Pin the documented graph: incomplete 'f' depends on the incomplete 'a'.
    f_row = next(f for f in out["features"] if f["name"] == "f")
    assert f_row["blocked"] and "a" in f_row["unmetDeps"]
    # A *complete* feature is never blocked, even when a dependency is still
    # incomplete: 'b' is complete and depends on the incomplete 'a'.
    b_row = next(f for f in out["features"] if f["name"] == "b")
    assert b_row["status"] == "complete"
    assert not b_row["blocked"] and b_row["unmetDeps"] == []


def test_render_status_surfaces_epic_change_request_counts(run_cli, fixture_copy) -> None:
    """render-status propagates per-member open/blocking epicChangeRequest counts (Phase 2)."""
    specs = fixture_copy("status-derivation")
    out = run_cli("render-status", "lifecycle", "--specs-dir", str(specs), "--json").json()

    # Every row carries both keys (additive-shape guard: no row omits them).
    for row in out["features"]:
        assert "openEpicChangeRequests" in row
        assert "blockingEpicChangeRequests" in row
        assert row["blockingEpicChangeRequests"] <= row["openEpicChangeRequests"]

    # Member 'a' carries two open requests (one blocking) + one applied (ignored).
    a_row = next(f for f in out["features"] if f["name"] == "a")
    assert a_row["openEpicChangeRequests"] == 2
    assert a_row["blockingEpicChangeRequests"] == 1

    # A member with no requests reports 0/0.
    c_row = next(f for f in out["features"] if f["name"] == "c")
    assert c_row["openEpicChangeRequests"] == 0
    assert c_row["blockingEpicChangeRequests"] == 0


def test_render_status_text_table_shows_pending_epic_changes(
    run_cli, fixture_copy
) -> None:
    """The human text table appends a ⚠️ pending-epic-change suffix (Phase 2)."""
    specs = fixture_copy("status-derivation")
    text = run_cli("render-status", "lifecycle", "--specs-dir", str(specs)).stdout

    # Member 'a' (2 open, 1 blocking) shows the blocking marker + count on its row.
    a_line = next(ln for ln in text.splitlines() if ln.strip().startswith("- a:"))
    assert "pending epic change(s)" in a_line
    assert "BLOCKING" in a_line
    assert "2 pending epic change(s)" in a_line

    # Member 'c' (no requests) shows no suffix.
    c_line = next(ln for ln in text.splitlines() if ln.strip().startswith("- c:"))
    assert "pending epic change(s)" not in c_line


# ---------------------------------------------------------------------------
# §3.8 Atomic-write behavior (REQ-ROBUST-03)
# ---------------------------------------------------------------------------


def test_atomic_write_replaces_cleanly(helper_module, tmp_path) -> None:
    """atomic_write produces valid JSON and leaves no temp file behind (REQ-ROBUST-03)."""
    target = tmp_path / "epic-manifest.json"
    target.write_text('{"schemaVersion": 1, "old": true}')

    helper_module.atomic_write(target, {"schemaVersion": 1, "new": True})

    assert json.loads(target.read_text()) == {"schemaVersion": 1, "new": True}
    leftovers = [p for p in tmp_path.iterdir() if p != target]
    assert leftovers == []


def test_atomic_write_interrupt_leaves_original_intact(
    helper_module, tmp_path, monkeypatch
) -> None:
    """An interrupted write (os.replace raises) never corrupts the original (REQ-ROBUST-03)."""
    import os

    target = tmp_path / "epic-manifest.json"
    original = '{"schemaVersion": 1, "old": true}'
    target.write_text(original)
    original_bytes = target.read_bytes()

    def boom(src, dst):
        raise KeyboardInterrupt

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(KeyboardInterrupt):
        helper_module.atomic_write(target, {"schemaVersion": 1, "new": True})

    # The original manifest is byte-identical afterward.
    assert target.read_bytes() == original_bytes


# ---------------------------------------------------------------------------
# §3.13 Mutator exit-code rows — clean->0, cycle/dangling->1 (byte-identical),
#        unsafe/bad-value->2 (00 §9). Exercises every mutator subcommand plus
#        render-status.
# ---------------------------------------------------------------------------


def _manifest_path(specs: Path) -> Path:
    return specs / "auth-overhaul" / "epic-manifest.json"


def test_mutator_add_feature_clean_exit_0(run_cli, fixture_copy) -> None:
    """add-feature on a clean new leaf exits 0 and the manifest still validates."""
    specs = fixture_copy("valid-epic")
    added = run_cli(
        "add-feature", "auth-overhaul", "metrics",
        "--charter", "Metrics leaf.", "--specs-dir", str(specs),
    )
    assert added.returncode == 0
    again = run_cli("validate", "auth-overhaul", "--specs-dir", str(specs), "--json")
    assert again.returncode == 0 and again.json()["valid"] is True


def test_mutator_set_dep_cycle_refused_byte_identical(run_cli, fixture_copy) -> None:
    """set-dep introducing a cycle exits 1 and leaves the file byte-identical (no write)."""
    specs = fixture_copy("valid-epic")
    manifest = _manifest_path(specs)
    before = manifest.read_bytes()

    # config-store <- token-service <- api-gateway already; make config-store
    # depend on api-gateway to close the loop.
    result = run_cli(
        "set-dep", "auth-overhaul", "config-store",
        "--depends-on", "api-gateway", "--specs-dir", str(specs),
    )
    assert result.returncode == 1
    assert manifest.read_bytes() == before   # refusal leaves it untouched


def test_mutator_remove_feature_dangling_refused_byte_identical(run_cli, fixture_copy) -> None:
    """remove-feature that would orphan a dependsOn refuses (exit 1), file byte-identical."""
    specs = fixture_copy("valid-epic")
    manifest = _manifest_path(specs)
    before = manifest.read_bytes()

    # token-service depends on config-store; removing config-store would dangle.
    result = run_cli(
        "remove-feature", "auth-overhaul", "config-store", "--specs-dir", str(specs),
    )
    assert result.returncode == 1
    codes_in_stderr = "dangling-ref" in result.stderr
    assert codes_in_stderr
    assert manifest.read_bytes() == before


def test_mutator_remove_feature_clean_exit_0(run_cli, fixture_copy) -> None:
    """remove-feature of an independent leaf exits 0 and re-validates clean."""
    specs = fixture_copy("valid-epic")
    result = run_cli(
        "remove-feature", "auth-overhaul", "audit-log", "--specs-dir", str(specs),
    )
    assert result.returncode == 0
    again = run_cli("validate", "auth-overhaul", "--specs-dir", str(specs), "--json")
    assert again.returncode == 0 and again.json()["valid"] is True


def test_mutator_reorder_bad_permutation_exit_1(run_cli, fixture_copy) -> None:
    """reorder with an order that is not an exact permutation of members exits 1."""
    specs = fixture_copy("valid-epic")
    manifest = _manifest_path(specs)
    before = manifest.read_bytes()
    result = run_cli(
        "reorder", "auth-overhaul",
        "--order", "config-store,token-service", "--specs-dir", str(specs),
    )
    assert result.returncode == 1
    assert manifest.read_bytes() == before


def test_mutator_reorder_clean_exit_0(run_cli, fixture_copy) -> None:
    """reorder with an exact permutation exits 0 and re-validates clean."""
    specs = fixture_copy("valid-epic")
    result = run_cli(
        "reorder", "auth-overhaul",
        "--order", "audit-log,config-store,token-service,api-gateway",
        "--specs-dir", str(specs),
    )
    assert result.returncode == 0
    again = run_cli("validate", "auth-overhaul", "--specs-dir", str(specs), "--json")
    assert again.returncode == 0 and again.json()["valid"] is True


def test_mutator_set_status_bad_value_exit_2(run_cli, fixture_copy) -> None:
    """set-status with an invalid value exits 2 via argparse choices."""
    specs = fixture_copy("valid-epic")
    result = run_cli(
        "set-status", "auth-overhaul", "--status", "frozen", "--specs-dir", str(specs),
    )
    assert result.returncode == 2


def test_mutator_set_status_valid_exit_0(run_cli, fixture_copy) -> None:
    """set-status with a valid value exits 0 and updates the epic status."""
    specs = fixture_copy("valid-epic")
    result = run_cli(
        "set-status", "auth-overhaul", "--status", "paused", "--specs-dir", str(specs),
    )
    assert result.returncode == 0
    out = run_cli("render-status", "auth-overhaul", "--specs-dir", str(specs), "--json").json()
    assert out["status"] == "paused"


def test_mutator_unsafe_name_exit_2(run_cli, fixture_copy) -> None:
    """A mutator given an unsafe epic-name arg exits 2 before any write (REQ-SEC-02)."""
    specs = fixture_copy("valid-epic")
    result = run_cli(
        "set-dep", "../escape", "config-store",
        "--depends-on", "token-service", "--specs-dir", str(specs),
    )
    assert result.returncode == 2


# ---------------------------------------------------------------------------
# §3.12 Performance sanity — 20 features validate + render (REQ-ROBUST-01)
# ---------------------------------------------------------------------------


def _make_20_feature_epic(specs: Path) -> str:
    """Build a 20-feature acyclic epic on disk; return the epic name."""
    epic = "big-epic"
    epic_dir = specs / epic
    features = []
    for i in range(20):
        name = f"feat-{i:02d}"
        (epic_dir / name).mkdir(parents=True, exist_ok=True)
        (epic_dir / name / ".pipeline-state.json").write_text(
            json.dumps({"epic": epic, "currentStage": "forge-1-prd", "stages": {}})
        )
        features.append({
            "name": name,
            "charter": "x",
            "dependsOn": [f"feat-{i - 1:02d}"] if i else [],
            "exposes": [],
            "consumes": [],
        })
    (epic_dir / "epic-manifest.json").write_text(json.dumps({
        "schemaVersion": 1,
        "epic": epic,
        "description": "x",
        "status": "active",
        "narrativeDoc": "EPIC.md",
        "createdAt": "2026-06-12T00:00:00Z",
        "updatedAt": "2026-06-12T00:00:00Z",
        "features": features,
    }))
    (epic_dir / "EPIC.md").write_text("# big-epic\n")
    return epic


def test_perf_20_feature_validate_render(run_cli, helper_module, tmp_path) -> None:
    """validate + render-status on a 20-feature epic is fast (REQ-ROBUST-01).

    The subprocess bound uses the spec's <1.5s fallback to absorb interpreter-
    startup jitter; the in-process render_status() call (the helper's actual
    O(V+E) work, no subprocess) is additionally asserted under 0.1s.
    """
    import time

    specs = tmp_path / "specs"
    epic = _make_20_feature_epic(specs)

    start = time.perf_counter()
    v = run_cli("validate", epic, "--specs-dir", str(specs), "--json")
    r = run_cli("render-status", epic, "--specs-dir", str(specs), "--json")
    elapsed = time.perf_counter() - start

    assert v.returncode == 0 and r.returncode == 0
    assert elapsed < 1.5

    # In-process: the helper's own work is negligible.
    in_start = time.perf_counter()
    helper_module.render_status(specs / epic, specs)
    assert (time.perf_counter() - in_start) < 0.1
