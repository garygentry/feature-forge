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
    """An unsafe name inside a manifest yields unsafe-name/path-escape findings (exit 1)."""
    result = run_cli(
        "validate", "path-escape", "--specs-dir", str(fixtures_dir / "path-escape"),
        "--json",
    )
    assert result.returncode == 1
    codes = {f["code"] for f in result.json()["findings"]}
    # The path-escape fixture carries an unsafe feature name ('../escape');
    # at least one of the containment finding codes must be raised.
    assert codes & {"unsafe-name", "path-escape"}


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
