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


def test_validate_optional_mutates_shared_accepted(run_cli, fixture_copy) -> None:
    """The optional `mutatesShared` hint (#144) is schema-legal and validates clean.

    An epic member may declare project-root-relative shared paths it writes/migrates so
    forge-verify CHECK-E10 can detect cross-member test coupling precisely. It is optional
    (mirrors epic-manifest-schema.json definitions.feature.properties.mutatesShared) and
    must not be flagged as an unknown key.
    """
    specs = fixture_copy("valid-epic")
    manifest = specs / "auth-overhaul" / "epic-manifest.json"
    data = json.loads(manifest.read_text())
    data["features"][0]["mutatesShared"] = ["data/vendors/partner-program.json"]
    manifest.write_text(json.dumps(data))

    result = run_cli("validate", "auth-overhaul", "--specs-dir", str(specs), "--json")
    assert result.returncode == 0
    assert result.json() == {"valid": True, "findings": []}


def test_validate_mutates_shared_wrong_type_is_schema(run_cli, fixture_copy) -> None:
    """A `mutatesShared` that is not an array of strings fails with a 'schema' finding."""
    specs = fixture_copy("valid-epic")
    manifest = specs / "auth-overhaul" / "epic-manifest.json"
    data = json.loads(manifest.read_text())
    data["features"][0]["mutatesShared"] = "data/vendors/partner-program.json"  # str, not list
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


# ---------------------------------------------------------------------------
# Item 020 — nextCommand is DERIVED from stages[].status, never from currentStage
# ---------------------------------------------------------------------------


def _make_single_member_epic(
    specs: Path,
    *,
    current_stage: str,
    stages: dict,
    prd: bool = True,
    revision: int | None = None,
) -> str:
    """Build a one-member epic whose member carries the given state; return the epic.

    ``revision`` defaults to None, which writes the LEGACY manifest shape (no
    ``revision`` key) that ``load_manifest`` presents as logical 1 — the pre-item-002
    callers of this helper depend on that. Item 009's epic-freshness tests pass an
    explicit revision because the number they compare against is the point.
    """
    epic = "nextcmd-epic"
    member_dir = specs / epic / "m1"
    member_dir.mkdir(parents=True, exist_ok=True)
    if prd:
        (member_dir / "PRD.md").write_text("# PRD\n")
    (member_dir / ".pipeline-state.json").write_text(json.dumps({
        "feature": "m1",
        "epic": epic,
        "createdAt": "2026-07-29T00:00:00Z",
        "updatedAt": "2026-07-29T00:00:00Z",
        "pipelineStatus": "active",
        "currentStage": current_stage,
        "stages": stages,
    }))
    (specs / epic / "epic-manifest.json").write_text(json.dumps({
        "schemaVersion": 1,
        **({"revision": revision} if revision is not None else {}),
        "epic": epic,
        "description": "x",
        "status": "active",
        "narrativeDoc": "EPIC.md",
        "createdAt": "2026-07-29T00:00:00Z",
        "updatedAt": "2026-07-29T00:00:00Z",
        "features": [
            {"name": "m1", "charter": "c", "dependsOn": [], "exposes": [], "consumes": []}
        ],
    }))
    (specs / epic / "EPIC.md").write_text("# nextcmd-epic\n")
    return epic


def _complete(version: int = 1) -> dict:
    return {
        "status": "complete",
        "version": version,
        "completedAt": "2026-07-29T00:00:00Z",
    }


def test_next_command_advances_past_a_completed_stage(run_cli, tmp_path) -> None:
    """A member whose PRD is complete is pointed at forge-2-tech, not back at forge-1-prd.

    Item 020 regression. R4 left `state-enter` as the only writer of `currentStage`,
    so between "forge-1-prd completes" and "forge-2-tech is entered" the field still
    reads `forge-1-prd` — the window in which a user actually consults the rollup to
    find out what to do next. Reading the field here recommended re-running the stage
    they had just finished, and nothing would advance it, because advancing it
    requires running the stage the rollup declined to recommend.
    """
    specs = tmp_path / "specs"
    epic = _make_single_member_epic(
        specs, current_stage="forge-1-prd", stages={"forge-1-prd": _complete()}
    )
    out = run_cli("render-status", epic, "--specs-dir", str(specs), "--json").json()
    assert out["nextCommand"] == "/feature-forge:forge-2-tech m1"


def test_next_command_never_reoffers_a_skipped_docs_stage(run_cli, tmp_path) -> None:
    """#197: `skipped` on forge-6-docs counts as done for next-stage derivation.

    A member with stages 1–5 complete, docs deliberately skipped, and an unapplied
    impl findings report is still actionable — but the recommendation must be the
    outstanding fix, never a re-run of the stage the operator explicitly skipped.
    """
    specs = tmp_path / "specs"
    stages = {
        stage: _complete()
        for stage in ("forge-1-prd", "forge-2-tech", "forge-3-specs",
                      "forge-4-backlog", "forge-5-loop")
    }
    stages["forge-6-docs"] = {"status": "skipped", "skippedAt": "2026-07-29T00:00:00Z"}
    stages["forge-verify-impl"] = {
        "status": "findings-reported",
        "findingsFile": "verify/impl.md",
        "findingsCount": 2,
    }
    epic = _make_single_member_epic(
        specs, current_stage="forge-6-docs", stages=stages
    )
    out = run_cli("render-status", epic, "--specs-dir", str(specs), "--json").json()
    assert out["nextCommand"] == "/feature-forge:forge-fix m1"
    assert "forge-6-docs" not in (out["nextCommand"] or "")


def test_next_command_is_independent_of_the_recorded_current_stage(
    run_cli, tmp_path
) -> None:
    """The same stages[] produces the same recommendation under either convention.

    Pre-R4 canon wrote `currentStage` = the NEXT stage on completion; the schema
    defines it as the most recently STARTED stage. Both values must yield the same
    nextCommand, which is only true if the field is not consulted at all.
    """
    stages = {"forge-1-prd": _complete(), "forge-2-tech": _complete()}
    results = []
    for i, recorded in enumerate(("forge-2-tech", "forge-3-specs")):
        specs = tmp_path / f"specs-{i}"
        epic = _make_single_member_epic(specs, current_stage=recorded, stages=stages)
        results.append(
            run_cli("render-status", epic, "--specs-dir", str(specs), "--json")
            .json()["nextCommand"]
        )
    assert results == ["/feature-forge:forge-3-specs m1"] * 2


def test_next_command_resumes_an_in_progress_stage(run_cli, tmp_path) -> None:
    """An entered-but-unfinished stage is still the next thing to run (resume it)."""
    specs = tmp_path / "specs"
    epic = _make_single_member_epic(
        specs,
        current_stage="forge-2-tech",
        stages={"forge-1-prd": _complete(), "forge-2-tech": {"status": "in-progress"}},
    )
    out = run_cli("render-status", epic, "--specs-dir", str(specs), "--json").json()
    assert out["nextCommand"] == "/feature-forge:forge-2-tech m1"


def test_next_command_treats_a_stale_stage_as_un_run(run_cli, tmp_path) -> None:
    """A stage marked `stale` by the cascade is not complete, so it is next."""
    specs = tmp_path / "specs"
    epic = _make_single_member_epic(
        specs,
        current_stage="forge-3-specs",
        stages={
            "forge-1-prd": _complete(version=2),
            "forge-2-tech": {"status": "stale", "version": 1},
        },
    )
    out = run_cli("render-status", epic, "--specs-dir", str(specs), "--json").json()
    assert out["nextCommand"] == "/feature-forge:forge-2-tech m1"


def test_next_command_still_routes_a_missing_prd_to_forge_1_prd(
    run_cli, tmp_path
) -> None:
    """The PRD-absent guard is unchanged: no PRD.md means start at forge-1-prd."""
    specs = tmp_path / "specs"
    epic = _make_single_member_epic(
        specs,
        current_stage="forge-2-tech",
        stages={"forge-1-prd": _complete()},
        prd=False,
    )
    out = run_cli("render-status", epic, "--specs-dir", str(specs), "--json").json()
    assert out["nextCommand"] == "/feature-forge:forge-1-prd m1"


def test_next_command_recommends_forge_fix_when_only_findings_remain(
    run_cli, tmp_path
) -> None:
    """All six stages complete but findings unapplied -> actionable, and forge-fix.

    `findings-reported` keeps the member out of complete-for-orchestration, so it is
    still actionable while having no un-run production stage. The old code emitted
    `/feature-forge:{currentStage}` here, which pre-R4 was the literal
    `/feature-forge:complete` — not a command.
    """
    specs = tmp_path / "specs"
    stages = {s: _complete() for s in (
        "forge-1-prd", "forge-2-tech", "forge-3-specs",
        "forge-4-backlog", "forge-5-loop", "forge-6-docs",
    )}
    stages["forge-verify-impl"] = {"status": "findings-reported"}
    epic = _make_single_member_epic(specs, current_stage="forge-6-docs", stages=stages)
    out = run_cli("render-status", epic, "--specs-dir", str(specs), "--json").json()
    assert "m1" in out["actionable"]
    assert out["nextCommand"] == "/feature-forge:forge-fix m1"


def test_a_finished_member_reports_complete_without_a_next_command(
    run_cli, tmp_path
) -> None:
    """Item 020 AC: the epic rollup's finished-member display is acceptable as-is.

    `currentStage` now reads `forge-6-docs` rather than the unreachable `complete`,
    but the member's coarse status comes from `is_complete_for_orchestration`, so the
    rollup still says `complete` and offers no next command.
    """
    specs = tmp_path / "specs"
    stages = {s: _complete() for s in (
        "forge-1-prd", "forge-2-tech", "forge-3-specs",
        "forge-4-backlog", "forge-5-loop", "forge-6-docs",
    )}
    stages["forge-verify-impl"] = {"status": "passed"}
    epic = _make_single_member_epic(specs, current_stage="forge-6-docs", stages=stages)
    out = run_cli("render-status", epic, "--specs-dir", str(specs), "--json").json()

    row = next(f for f in out["features"] if f["name"] == "m1")
    assert row["status"] == "complete"
    assert row["stage"] == "forge-6-docs"
    assert out["rollup"]["complete"] == out["rollup"]["total"] == 1
    assert out["actionable"] == []
    assert out["nextCommand"] is None


# ---------------------------------------------------------------------------
# Item 002 — canonical epic manifest revision (03 §2.2; 07 §4.4 rows 1-6)
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent

#: Every mutator subcommand, as (argv-tail, "what it changes") pairs. Each must
#: increment `revision` exactly once per successful mutation (03 §2.2). The
#: adopt-feature row is the epic edit-mode mutation path present in source.
_INCREMENTING_MUTATIONS: list[tuple[str, list[str]]] = [
    ("add-feature", ["add-feature", "auth-overhaul", "metrics",
                     "--charter", "Metrics collection leaf."]),
    ("remove-feature", ["remove-feature", "auth-overhaul", "audit-log"]),
    ("reorder", ["reorder", "auth-overhaul",
                 "--order", "audit-log,config-store,token-service,api-gateway"]),
    ("set-dep", ["set-dep", "auth-overhaul", "audit-log",
                 "--depends-on", "config-store"]),
    ("set-status", ["set-status", "auth-overhaul", "--status", "paused"]),
    ("adopt-feature", ["adopt-feature", "auth-overhaul", "flat-only",
                       "--charter", "Adopted leaf."]),
]


def _revision(specs: Path) -> object:
    """Read the on-disk revision of the valid-epic fixture's manifest."""
    return json.loads(_manifest_path(specs).read_text()).get("revision")


def _make_flat_standalone(specs: Path) -> None:
    """Give the fixture's `flat-only` dir a state file so adopt-feature can run."""
    flat = specs / "flat-only"
    flat.mkdir(parents=True, exist_ok=True)
    (flat / ".pipeline-state.json").write_text(
        json.dumps({"currentStage": "forge-1-prd", "stages": {}}), encoding="utf-8"
    )


# --- Row 1: a newly created manifest starts at revision 1 ------------------- #


def test_revision_creation_writes_revision_1(run_cli, tmp_path) -> None:
    """A freshly composed manifest carries revision 1 and validates clean (03 §2.2)."""
    specs = tmp_path / "specs"
    epic_dir = specs / "brand-new"
    epic_dir.mkdir(parents=True)
    (epic_dir / "EPIC.md").write_text("# brand-new\n")
    (epic_dir / "epic-manifest.json").write_text(json.dumps({
        "schemaVersion": 1,
        "revision": 1,
        "epic": "brand-new",
        "description": "x",
        "status": "active",
        "narrativeDoc": "EPIC.md",
        "createdAt": "2026-07-30T00:00:00Z",
        "updatedAt": "2026-07-30T00:00:00Z",
        "features": [],
    }))

    result = run_cli("validate", "brand-new", "--specs-dir", str(specs), "--json")
    assert result.returncode == 0
    assert result.json() == {"valid": True, "findings": []}


def test_revision_creation_canon_instructs_revision_1() -> None:
    """forge-0-epic's compose step tells the skill to write `revision`: `1`.

    Creation is skill-authored (there is no `create` subcommand), so the canon
    instruction IS the creation-time contract the script can only validate after
    the fact.
    """
    body = (REPO_ROOT / "skills" / "forge-0-epic" / "SKILL.md").read_text(encoding="utf-8")
    assert "- `revision`: `1`" in body


# --- Row 2: committed current-format fixtures carry revision 1 -------------- #


def test_revision_committed_fixtures_carry_revision_1(fixtures_dir) -> None:
    """Both epic fixtures are kept in the CURRENT format, not the legacy one."""
    for rel in ("valid-epic/auth-overhaul", "status-derivation/lifecycle"):
        manifest = json.loads((fixtures_dir / rel / "epic-manifest.json").read_text())
        assert manifest["revision"] == 1, rel


def test_revision_must_be_an_integer_at_least_one(run_cli, fixture_copy) -> None:
    """A boolean or a below-1 revision is a schema finding (exit 1), never accepted.

    `bool` is an `int` subclass, so an unguarded check would let `True` through as
    revision 1 and then arithmetic-increment it to 2.
    """
    specs = fixture_copy("valid-epic")
    manifest = _manifest_path(specs)
    pristine = json.loads(manifest.read_text())
    for bad in (True, False, 0, -1, "1", 1.5, None):
        manifest.write_text(json.dumps({**pristine, "revision": bad}))

        result = run_cli("validate", "auth-overhaul", "--specs-dir", str(specs), "--json")
        assert result.returncode == 1, f"{bad!r} was accepted"
        messages = " ".join(f["message"] for f in result.json()["findings"])
        assert "revision" in messages


# --- Rows 3-4: legacy load-as-1, then first mutation writes 2 --------------- #


def test_revision_legacy_manifest_loads_as_1_without_rewriting_bytes(
    helper_module, fixture_copy
) -> None:
    """A copied fixture with `revision` removed loads logically as 1, bytes untouched.

    REQ-DEBT-06: legacy manifests must keep loading, validating, and rendering with
    no eager migration write.
    """
    specs = fixture_copy("valid-epic")
    manifest = _manifest_path(specs)
    data = json.loads(manifest.read_text())
    del data["revision"]
    manifest.write_text(json.dumps(data, indent=2) + "\n")
    legacy_bytes = manifest.read_bytes()

    loaded = helper_module.load_manifest(specs / "auth-overhaul")
    assert loaded["revision"] == 1
    assert manifest.read_bytes() == legacy_bytes


def test_revision_legacy_manifest_still_validates_and_renders(
    run_cli, fixture_copy
) -> None:
    """The legacy shape passes validate and render-status unchanged (REQ-COMPAT-02)."""
    specs = fixture_copy("valid-epic")
    manifest = _manifest_path(specs)
    data = json.loads(manifest.read_text())
    del data["revision"]
    manifest.write_text(json.dumps(data, indent=2) + "\n")
    legacy_bytes = manifest.read_bytes()

    assert run_cli("validate", "auth-overhaul", "--specs-dir", str(specs),
                   "--json").returncode == 0
    assert run_cli("render-status", "auth-overhaul", "--specs-dir", str(specs),
                   "--json").returncode == 0
    assert manifest.read_bytes() == legacy_bytes  # read paths never migrate


def test_revision_legacy_first_semantic_mutation_writes_2(run_cli, fixture_copy) -> None:
    """A legacy manifest's first real edit persists revision 2 (03 §2.2)."""
    specs = fixture_copy("valid-epic")
    manifest = _manifest_path(specs)
    data = json.loads(manifest.read_text())
    del data["revision"]
    manifest.write_text(json.dumps(data, indent=2) + "\n")

    result = run_cli("set-status", "auth-overhaul", "--status", "paused",
                     "--specs-dir", str(specs))
    assert result.returncode == 0
    assert _revision(specs) == 2


# --- Row 5: every mutator increments exactly once --------------------------- #


@pytest.mark.parametrize(
    "label,argv", _INCREMENTING_MUTATIONS, ids=[m[0] for m in _INCREMENTING_MUTATIONS]
)
def test_revision_every_mutator_increments_exactly_once(
    run_cli, fixture_copy, label: str, argv: list[str]
) -> None:
    """One successful mutation advances revision by exactly 1 — never 0, never 2."""
    specs = fixture_copy("valid-epic")
    _make_flat_standalone(specs)
    before = _revision(specs)
    assert before == 1

    result = run_cli(*argv, "--specs-dir", str(specs))
    assert result.returncode == 0, result.stdout + result.stderr
    assert _revision(specs) == before + 1, label


def test_revision_repeated_distinct_mutations_increment_monotonically(
    run_cli, fixture_copy
) -> None:
    """Three distinct edits in sequence produce 2, 3, 4 — one bump per mutation."""
    specs = fixture_copy("valid-epic")
    seen = []
    for status in ("paused", "active", "complete"):
        assert run_cli("set-status", "auth-overhaul", "--status", status,
                       "--specs-dir", str(specs)).returncode == 0
        seen.append(_revision(specs))
    assert seen == [2, 3, 4]


# --- Row 6: validation failure / I/O failure / semantic no-op change nothing - #


def test_revision_validation_failure_leaves_revision_and_bytes_unchanged(
    run_cli, fixture_copy
) -> None:
    """A refused mutation (cycle) writes nothing at all (REQ-ROBUST-03)."""
    specs = fixture_copy("valid-epic")
    manifest = _manifest_path(specs)
    before_bytes = manifest.read_bytes()

    # config-store <- token-service <- api-gateway; this closes the loop.
    result = run_cli("set-dep", "auth-overhaul", "config-store",
                     "--depends-on", "api-gateway", "--specs-dir", str(specs), "--json")
    assert result.returncode == 1
    assert {f["code"] for f in result.json()["findings"]} == {"cycle"}
    assert manifest.read_bytes() == before_bytes
    assert _revision(specs) == 1


def test_revision_io_failure_leaves_revision_and_bytes_unchanged(
    helper_module, fixture_copy, monkeypatch
) -> None:
    """A failed atomic write raises and leaves the previous revision on disk."""
    import os

    specs = fixture_copy("valid-epic")
    manifest = _manifest_path(specs)
    before_bytes = manifest.read_bytes()

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(helper_module.UsageError):
        helper_module.set_status(specs / "auth-overhaul", specs, "paused")

    assert manifest.read_bytes() == before_bytes
    assert _revision(specs) == 1
    leftovers = [p.name for p in (specs / "auth-overhaul").iterdir()
                 if p.name.startswith(".epic-manifest.json.")]
    assert leftovers == []


def test_revision_semantic_no_op_leaves_revision_and_bytes_unchanged(
    run_cli, fixture_copy
) -> None:
    """An edit that changes nothing semantic writes nothing — updatedAt included.

    The byte-equality assertion is the point: refreshing `updatedAt` on a no-op
    would make an epic's verification look stale for an edit that did not happen.
    """
    specs = fixture_copy("valid-epic")
    manifest = _manifest_path(specs)
    before_bytes = manifest.read_bytes()

    # The fixture is already `active`, already in this order, and audit-log already
    # has no dependencies — three separate no-op shapes.
    for argv in (
        ["set-status", "auth-overhaul", "--status", "active"],
        ["reorder", "auth-overhaul",
         "--order", "config-store,token-service,api-gateway,audit-log"],
        ["set-dep", "auth-overhaul", "audit-log", "--depends-on", ""],
    ):
        result = run_cli(*argv, "--specs-dir", str(specs))
        assert result.returncode == 0, result.stdout + result.stderr
        assert manifest.read_bytes() == before_bytes, argv[0]
        assert _revision(specs) == 1


# --- Item 032: a no-op mutation still re-validates (REQ-ROBUST-03) --------- #
#
# `_bump_and_write` used to run the semantic no-op comparison BEFORE
# `_validate_dict`, so a semantically idempotent mutation against a manifest that
# was already invalid on disk exited 0 in silence — while the very same mutator
# with a *different* value exited 1 with the blocking findings. A caller reading
# exit 0 as "the epic is well-formed" was misled. The order is now
# validate -> no-op check, which restores the diagnostic without writing.


def _corrupt_manifest(specs: Path, kind: str) -> None:
    """Make the copied `valid-epic` fixture invalid in place, without a mutator.

    Writing the corruption directly (rather than via a refused mutation, which by
    design leaves the file untouched) is the only way to reach the state these
    tests are about: an epic that is ALREADY invalid on disk when a mutator runs.
    """
    path = _manifest_path(specs)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    by_name = {f["name"]: f for f in manifest["features"]}
    if kind == "dangling-ref":
        by_name["audit-log"]["dependsOn"] = ["ghost"]
    else:  # cycle: config-store <- token-service <- api-gateway <- config-store
        by_name["config-store"]["dependsOn"] = ["api-gateway"]
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def _no_op_argv(mutator: str, kind: str) -> list[str]:
    """Argv for a mutation that changes nothing semantic on the corrupted fixture."""
    if mutator == "set-status":
        return ["set-status", "auth-overhaul", "--status", "active"]  # already active
    if mutator == "reorder":
        return ["reorder", "auth-overhaul",
                "--order", "config-store,token-service,api-gateway,audit-log"]
    # set-dep: re-assert exactly the dependency the corruption installed.
    if kind == "dangling-ref":
        return ["set-dep", "auth-overhaul", "audit-log", "--depends-on", "ghost"]
    return ["set-dep", "auth-overhaul", "config-store", "--depends-on", "api-gateway"]


@pytest.mark.parametrize("mutator", ["set-status", "set-dep", "reorder"])
@pytest.mark.parametrize("kind", ["dangling-ref", "cycle"])
def test_no_op_mutation_on_an_invalid_manifest_reports_the_findings(
    run_cli, fixture_copy, mutator, kind
) -> None:
    """Every no-op mutator path re-validates and exits 1 on an invalid manifest."""
    specs = fixture_copy("valid-epic")
    _corrupt_manifest(specs, kind)
    manifest = _manifest_path(specs)
    before_bytes = manifest.read_bytes()

    result = run_cli(*_no_op_argv(mutator, kind), "--specs-dir", str(specs), "--json")

    assert result.returncode == 1, result.stdout + result.stderr
    assert {f["code"] for f in result.json()["findings"]} == {kind}
    # Refusing still writes nothing: no bytes, no updatedAt refresh, no bump.
    assert manifest.read_bytes() == before_bytes
    assert _revision(specs) == 1


@pytest.mark.parametrize("kind", ["dangling-ref", "cycle"])
def test_no_op_and_real_mutation_report_the_same_findings(
    run_cli, fixture_copy, kind
) -> None:
    """The no-op path matches the non-no-op path exactly — that is the whole bug."""
    specs = fixture_copy("valid-epic")
    _corrupt_manifest(specs, kind)
    manifest = _manifest_path(specs)
    before_bytes = manifest.read_bytes()

    no_op = run_cli("set-status", "auth-overhaul", "--status", "active",
                    "--specs-dir", str(specs), "--json")
    real = run_cli("set-status", "auth-overhaul", "--status", "paused",
                   "--specs-dir", str(specs), "--json")

    assert no_op.returncode == real.returncode == 1
    assert no_op.json()["findings"] == real.json()["findings"]
    assert manifest.read_bytes() == before_bytes


@pytest.mark.parametrize("mutator", ["set-status", "set-dep", "reorder"])
def test_no_op_mutation_on_a_valid_manifest_still_succeeds_silently(
    run_cli, fixture_copy, mutator
) -> None:
    """Negative control: validating first did not turn every no-op into a write or a refusal.

    Pins item 002's byte-equality requirement explicitly on `updatedAt` and
    `revision`, the two fields a spurious write would move.
    """
    specs = fixture_copy("valid-epic")
    manifest = _manifest_path(specs)
    before_bytes = manifest.read_bytes()
    before_updated_at = json.loads(before_bytes)["updatedAt"]

    # `set-dep audit-log --depends-on ""` is the no-op on the pristine fixture.
    argv = (["set-dep", "auth-overhaul", "audit-log", "--depends-on", ""]
            if mutator == "set-dep" else _no_op_argv(mutator, "dangling-ref"))
    result = run_cli(*argv, "--specs-dir", str(specs))

    assert result.returncode == 0, result.stdout + result.stderr
    assert manifest.read_bytes() == before_bytes
    assert json.loads(manifest.read_text())["updatedAt"] == before_updated_at
    assert _revision(specs) == 1


# ---------------------------------------------------------------------------
# Item 009 — verify-status parity + epic-root freshness (03 §5.2; 07 §4.4 rows 7-8)
# ---------------------------------------------------------------------------

#: The five production stages that carry a member verify token, plus one that does not.
_ALL_STAGES_COMPLETE = (
    "forge-1-prd", "forge-2-tech", "forge-3-specs",
    "forge-4-backlog", "forge-5-loop", "forge-6-docs",
)


def _auto_pending(version: int | None = 1) -> dict:
    """An `auto-verify-pending` verify entry as `state-verify` writes it (03 §3.3)."""
    entry: dict = {
        "status": "auto-verify-pending",
        "scheduledAt": "2026-07-30T00:00:00Z",
        "commitHash": None,
    }
    if version is not None:
        entry["scheduledStageVersion"] = version
    return entry


def _write_epic_state(specs: Path, epic: str, entry: object) -> Path:
    """Write the epic's own `.epic-state.json` carrying one `forge-verify-epic` entry."""
    path = specs / epic / ".epic-state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "epic": epic,
        "updatedAt": "2026-07-30T00:00:00Z",
        "stages": {"forge-verify-epic": entry},
    }), encoding="utf-8")
    return path


def _production_complete_epic(specs: Path, verify_impl: dict, **kwargs) -> str:
    """A one-member epic whose member finished every production stage."""
    stages = {s: _complete() for s in _ALL_STAGES_COMPLETE}
    stages["forge-verify-impl"] = verify_impl
    return _make_single_member_epic(
        specs, current_stage="forge-6-docs", stages=stages, **kwargs
    )


# --- Parity: auto-verify-pending is a KNOWN status, not an unknown one ------ #


def test_009_auto_verify_pending_is_not_flagged_as_an_unknown_status(
    helper_module, run_cli, tmp_path
) -> None:
    """`_verify_status_warnings` recognizes the status, so it emits no unknown warning.

    The misleading alternative — "unknown forge-verify-impl status
    'auto-verify-pending' (treated as incomplete...)" — would tell an operator the
    state file was corrupt when it is in fact valid and simply owes work (03 §5.2).
    """
    state = {"stages": {"forge-5-loop": _complete(), "forge-verify-impl": _auto_pending()}}
    assert helper_module._verify_status_warnings("m1", state) == []

    specs = tmp_path / "specs"
    epic = _production_complete_epic(specs, _auto_pending())
    out = run_cli("render-status", epic, "--specs-dir", str(specs), "--json").json()
    assert not any("unknown" in w for w in out["warnings"])


def test_009_a_genuinely_unknown_status_is_still_flagged(helper_module) -> None:
    """Negative control: the unknown-status guard did not become a no-op."""
    state = {"stages": {"forge-verify-impl": {"status": "auto-verify-pendign"}}}
    warnings = helper_module._verify_status_warnings("m1", state)
    assert len(warnings) == 1
    assert "unknown forge-verify-impl status" in warnings[0]


# --- Parity: completion predicates treat the debt as outstanding ------------ #


def test_009_auto_verify_pending_is_not_complete_for_orchestration(
    helper_module,
) -> None:
    """A member owing automatic implementation verification does not unblock dependents."""
    owed = {"stages": {"forge-5-loop": _complete(), "forge-verify-impl": _auto_pending()}}
    assert helper_module.is_complete_for_orchestration(owed) is False

    discharged = {
        "stages": {
            "forge-5-loop": _complete(),
            "forge-verify-impl": {"status": "passed", "verifiedStageVersion": 1},
        }
    }
    assert helper_module.is_complete_for_orchestration(discharged) is True


def test_009_derive_status_reports_in_progress_for_auto_verify_pending(
    helper_module, tmp_path
) -> None:
    """The debt keeps the member in-progress — never complete, never not-started."""
    member = tmp_path / "m1"
    member.mkdir()
    (member / ".pipeline-state.json").write_text(json.dumps({
        "currentStage": "forge-5-loop",
        "stages": {"forge-5-loop": _complete(), "forge-verify-impl": _auto_pending()},
    }))
    assert helper_module.derive_status(member)["status"] == "in-progress"


# --- Parity: _next_command routes debt to verify, findings to fix ----------- #


def test_009_next_command_splits_auto_pending_from_findings_reported(
    run_cli, tmp_path
) -> None:
    """forge-verify for owed automatic debt; forge-fix reserved for a written report.

    Recommending forge-fix for `auto-verify-pending` sends the operator looking for
    a findings document that was never produced, because the scheduled verification
    never ran (03 §5.2).
    """
    cases = {
        "verify": (_auto_pending(), "/feature-forge:forge-verify m1"),
        "fix": ({"status": "findings-reported"}, "/feature-forge:forge-fix m1"),
    }
    for label, (entry, expected) in cases.items():
        specs = tmp_path / f"specs-{label}"
        epic = _production_complete_epic(specs, entry)
        out = run_cli("render-status", epic, "--specs-dir", str(specs), "--json").json()
        assert out["actionable"] == ["m1"], label
        assert out["nextCommand"] == expected, label


# --- render_status obligation warnings (JSON + human) ----------------------- #


_MEMBER_DEBT_SENTENCE = (
    "m1: automatic verification is still pending for forge-5-loop; "
    "run /feature-forge:forge-verify m1 to resolve it."
)


def test_009_render_status_emits_the_member_obligation_warning(run_cli, tmp_path) -> None:
    """The 03 §5.3 sentence appears in JSON warnings AND in the human status output."""
    specs = tmp_path / "specs"
    epic = _production_complete_epic(specs, _auto_pending())

    as_json = run_cli("render-status", epic, "--specs-dir", str(specs), "--json")
    assert as_json.returncode == 0
    assert _MEMBER_DEBT_SENTENCE in as_json.json()["warnings"]

    human = run_cli("render-status", epic, "--specs-dir", str(specs))
    assert human.returncode == 0
    assert "Warnings:" in human.stdout
    assert _MEMBER_DEBT_SENTENCE in human.stdout


def test_009_the_member_obligation_warning_is_deterministic(run_cli, tmp_path) -> None:
    """Two debts on one member render in pipeline order, identically on every run."""
    specs = tmp_path / "specs"
    stages = {s: _complete() for s in _ALL_STAGES_COMPLETE}
    # Deliberately serialized impl-before-prd so key order cannot drive the output.
    stages["forge-verify-impl"] = _auto_pending()
    stages["forge-verify-prd"] = _auto_pending()
    epic = _make_single_member_epic(specs, current_stage="forge-6-docs", stages=stages)

    first = run_cli("render-status", epic, "--specs-dir", str(specs), "--json").json()
    second = run_cli("render-status", epic, "--specs-dir", str(specs), "--json").json()
    assert first["warnings"] == second["warnings"]
    assert [w.split(" for ")[1].split(";")[0] for w in first["warnings"]] == [
        "forge-1-prd", "forge-5-loop",
    ]


def test_009_the_member_warning_names_both_revisions_when_the_artifact_advanced(
    run_cli, tmp_path
) -> None:
    """Debt scheduled against an older artifact version stays owed and says so."""
    specs = tmp_path / "specs"
    stages = {s: _complete() for s in _ALL_STAGES_COMPLETE}
    stages["forge-5-loop"] = _complete(version=3)
    stages["forge-verify-impl"] = _auto_pending(version=1)
    epic = _make_single_member_epic(specs, current_stage="forge-6-docs", stages=stages)

    warnings = run_cli(
        "render-status", epic, "--specs-dir", str(specs), "--json"
    ).json()["warnings"]
    assert warnings == [
        _MEMBER_DEBT_SENTENCE
        + " The artifact has advanced since it was scheduled "
        + "(scheduled at revision 1, now at revision 3)."
    ]


def test_009_a_clean_epic_still_reports_no_warnings(run_cli, tmp_path) -> None:
    """Negative control: the obligation warning does not fire on ordinary members."""
    specs = tmp_path / "specs"
    epic = _make_single_member_epic(
        specs, current_stage="forge-1-prd", stages={"forge-1-prd": _complete()}
    )
    out = run_cli("render-status", epic, "--specs-dir", str(specs), "--json").json()
    assert out["warnings"] == []


# --- Epic-root freshness against the manifest revision (03 §5.2) ------------ #


_EPIC_FRESHNESS_ROWS: list[tuple[str, object, str]] = [
    ("null-status", {"status": None}, "never"),
    ("unknown-status", {"status": "findings-resolved"}, "never"),
    ("manual-pending", {"status": "pending"}, "never"),
    ("auto-pending-matching", _auto_pending(2), "auto-pending"),
    ("auto-pending-older", _auto_pending(1), "auto-pending"),
    ("auto-pending-no-version", _auto_pending(None), "auto-pending"),
    ("auto-pending-bool-version", _auto_pending(True), "auto-pending"),
    ("passed-matching", {"status": "passed", "verifiedStageVersion": 2}, "fresh"),
    ("passed-mismatched", {"status": "passed", "verifiedStageVersion": 1}, "stale"),
    ("passed-no-version", {"status": "passed"}, "stale"),
    ("findings-reported", {"status": "findings-reported",
                           "verifiedStageVersion": 2}, "failing"),
    ("findings-applied", {"status": "findings-applied", "fixedAt": "x"}, "stale"),
    ("skipped", {"status": "skipped"}, "skipped"),
    ("not-a-dict", "passed", "never"),
    # Torn/hand-edited statuses: an unhashable value must classify, not raise
    # TypeError at the frozenset membership (the dashboard reads every epic's file).
    ("list-status", {"status": ["findings-reported"]}, "never"),
    ("dict-status", {"status": {"passed": True}}, "never"),
    ("int-status", {"status": 3}, "never"),
]


@pytest.mark.parametrize(
    "label,entry,expected", _EPIC_FRESHNESS_ROWS, ids=[r[0] for r in _EPIC_FRESHNESS_ROWS]
)
def test_009_epic_verify_state_matrix(
    helper_module, tmp_path, label: str, entry: object, expected: str
) -> None:
    """Every 03 §5.2 epic-root classification, compared against manifest revision 2."""
    epic_dir = tmp_path / "an-epic"
    _write_epic_state(tmp_path, "an-epic", entry)
    assert helper_module.epic_verify_state(epic_dir, 2) == expected, label


def test_009_epic_verify_state_is_never_without_state(helper_module, tmp_path) -> None:
    """Missing, corrupt, non-object, and malformed-`stages` epic state all read `never`."""
    epic_dir = tmp_path / "an-epic"
    epic_dir.mkdir()
    assert helper_module.epic_verify_state(epic_dir, 1) == "never"

    path = epic_dir / ".epic-state.json"
    for text in ("{not json", '"a string"', "[]", '{"stages": []}', '{"stages": {}}'):
        path.write_text(text, encoding="utf-8")
        assert helper_module.epic_verify_state(epic_dir, 1) == "never", text


def test_009_render_status_survives_a_torn_epic_state(run_cli, tmp_path) -> None:
    """The dashboard renders (exit 0, valid JSON) over an unhashable status."""
    specs = tmp_path / "specs"
    epic = _make_single_member_epic(
        specs, current_stage="forge-1-prd", stages={"forge-1-prd": _complete()}
    )
    _write_epic_state(specs, epic, {"status": ["findings-reported"]})
    result = run_cli("render-status", epic, "--specs-dir", str(specs), "--json")
    assert result.returncode == 0, result.stderr
    result.json()


def test_009_epic_verify_warning_classifies_and_reads_one_snapshot(
    helper_module, tmp_path, monkeypatch
) -> None:
    """The warning renderer reads the state file ONCE and indexes that same
    snapshot — a file rewritten between a classify-read and a metadata-read
    could otherwise KeyError while rendering the dashboard."""
    epic_dir = tmp_path / "an-epic"
    _write_epic_state(tmp_path, "an-epic", _auto_pending(1))
    calls: list[Path] = []
    real = helper_module._read_epic_state_safely

    def counting_read(path: Path) -> dict:
        calls.append(path)
        return real(path)

    monkeypatch.setattr(helper_module, "_read_epic_state_safely", counting_read)
    warnings = helper_module._epic_verify_warnings("an-epic", epic_dir, 1)
    assert len(warnings) == 1
    assert len(calls) == 1


def test_009_epic_verification_never_reads_a_member_pipeline_state(
    helper_module, tmp_path
) -> None:
    """A `forge-verify-epic` entry hidden in a member's state does not count (REQ-SEC-01).

    Adversarial on purpose: the member sits inside the epic dir and carries a
    perfectly-formed passing epic entry at the current revision. Reading it would
    make an unverified epic report `fresh`.
    """
    epic_dir = tmp_path / "an-epic"
    member = epic_dir / "m1"
    member.mkdir(parents=True)
    (member / ".pipeline-state.json").write_text(json.dumps({
        "stages": {"forge-verify-epic": {"status": "passed", "verifiedStageVersion": 2}}
    }), encoding="utf-8")

    assert helper_module.epic_verify_state(epic_dir, 2) == "never"


# --- 07 §4.4 row 7: a manifest edit moves epic freshness ------------------- #


def test_009_a_manifest_edit_makes_a_prior_epic_pass_stale(
    helper_module, run_cli, tmp_path
) -> None:
    """Revision 1 pass reads `fresh`; one semantic edit (revision 2) makes it `stale`.

    This is what the manifest revision is FOR: the epic's artifact changed, so the
    verification that approved the previous shape no longer speaks for it.
    """
    specs = tmp_path / "specs"
    epic = _make_single_member_epic(
        specs, current_stage="forge-1-prd",
        stages={"forge-1-prd": _complete()}, revision=1,
    )
    state_path = _write_epic_state(
        specs, epic, {"status": "passed", "verifiedStageVersion": 1}
    )
    before_bytes = state_path.read_bytes()
    epic_dir = specs / epic
    assert helper_module.epic_verify_state(epic_dir, 1) == "fresh"

    assert run_cli("set-status", epic, "--status", "paused",
                   "--specs-dir", str(specs)).returncode == 0
    revision = json.loads((epic_dir / "epic-manifest.json").read_text())["revision"]
    assert revision == 2
    assert helper_module.epic_verify_state(epic_dir, revision) == "stale"
    # The mutation touches the manifest only — epic verification state is untouched.
    assert state_path.read_bytes() == before_bytes


def test_009_a_manifest_edit_leaves_a_pending_marker_visibly_owed(
    helper_module, run_cli, tmp_path
) -> None:
    """A superseded schedule stays `auto-pending` and the dashboard names both revisions.

    Owed work is not erased by a later edit (REQ-DEBT-02) — the alternative reading,
    "the revision moved, so forget the debt", is exactly how a dropped
    `runInStageVerify` directive becomes invisible.
    """
    specs = tmp_path / "specs"
    epic = _make_single_member_epic(
        specs, current_stage="forge-1-prd",
        stages={"forge-1-prd": _complete()}, revision=1,
    )
    _write_epic_state(specs, epic, _auto_pending(1))
    epic_dir = specs / epic
    assert helper_module.epic_verify_state(epic_dir, 1) == "auto-pending"

    assert run_cli("set-status", epic, "--status", "paused",
                   "--specs-dir", str(specs)).returncode == 0
    assert helper_module.epic_verify_state(epic_dir, 2) == "auto-pending"

    out = run_cli("render-status", epic, "--specs-dir", str(specs), "--json").json()
    assert out["warnings"] == [
        f"{epic}: automatic verification is still pending for forge-0-epic; "
        f"run /feature-forge:forge-verify {epic} to resolve it."
        " The artifact has advanced since it was scheduled "
        "(scheduled at revision 1, now at revision 2)."
    ]


def test_009_the_epic_obligation_warning_reaches_human_output(run_cli, tmp_path) -> None:
    """The epic-root obligation is visible without --json too."""
    specs = tmp_path / "specs"
    epic = _make_single_member_epic(
        specs, current_stage="forge-1-prd",
        stages={"forge-1-prd": _complete()}, revision=1,
    )
    _write_epic_state(specs, epic, _auto_pending(1))

    human = run_cli("render-status", epic, "--specs-dir", str(specs))
    assert human.returncode == 0
    assert f"run /feature-forge:forge-verify {epic} to resolve it." in human.stdout


def test_009_a_resolved_epic_verification_emits_no_obligation_warning(
    run_cli, tmp_path
) -> None:
    """Negative control: only owed debt warns — `passed`, `stale`, and `never` do not."""
    specs = tmp_path / "specs"
    epic = _make_single_member_epic(
        specs, current_stage="forge-1-prd",
        stages={"forge-1-prd": _complete()}, revision=1,
    )
    for entry in (
        {"status": "passed", "verifiedStageVersion": 1},
        {"status": "passed", "verifiedStageVersion": 99},
        {"status": "skipped"},
    ):
        _write_epic_state(specs, epic, entry)
        out = run_cli("render-status", epic, "--specs-dir", str(specs), "--json").json()
        assert out["warnings"] == [], entry


# --- 07 §4.4 row 8: epic metadata is the manifest revision ----------------- #


def test_009_epic_freshness_uses_the_manifest_revision_not_a_member_stage_version(
    helper_module, tmp_path
) -> None:
    """A member stage version that happens to match must not make the epic look fresh."""
    specs = tmp_path / "specs"
    stages = {"forge-1-prd": _complete(version=7)}
    epic = _make_single_member_epic(
        specs, current_stage="forge-1-prd", stages=stages, revision=2
    )
    epic_dir = specs / epic

    # verifiedStageVersion carrying the MEMBER's stage version (7) is stale...
    _write_epic_state(specs, epic, {"status": "passed", "verifiedStageVersion": 7})
    assert helper_module.epic_verify_state(epic_dir, 2) == "stale"

    # ...and only the manifest revision (2) reads fresh.
    _write_epic_state(specs, epic, {"status": "passed", "verifiedStageVersion": 2})
    assert helper_module.epic_verify_state(epic_dir, 2) == "fresh"
