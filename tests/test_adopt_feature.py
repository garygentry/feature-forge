"""Tests for the scripted `adopt-feature` recovery command (Issue #126).

`epic-manifest.py adopt-feature {epic} {feature}` reconciles a detached
standalone `specs/{feature}/` into an epic member `specs/{epic}/{feature}/`
(the epic-backflow Phase-3 mutator). Acceptance from #126: one command produces
a valid nested member with **no residual flat dir**, `resolve` then returns the
single nested path, and the manifest re-validates clean.

Reuses the epic-manifest suite's `run_cli` / `fixture_copy` harness; the
split-brain shape (a member stub AND a detached standalone of the same name) is
built on top of the shared `valid-epic` fixture.
"""

from __future__ import annotations

import json
from pathlib import Path

STATE = ".pipeline-state.json"


def _write_state(feature_dir: Path, state: dict) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / STATE).write_text(json.dumps(state, indent=2), encoding="utf-8")


def _manifest_names(specs: Path, epic: str) -> list[str]:
    manifest = json.loads((specs / epic / "epic-manifest.json").read_text())
    return [f["name"] for f in manifest["features"]]


# --------------------------------------------------------------------------- #
# Happy paths
# --------------------------------------------------------------------------- #


def test_adopt_new_standalone_relocates_and_adds_member(run_cli, fixture_copy) -> None:
    """A flat standalone that is not yet a member: relocated + added to manifest."""
    specs = fixture_copy("valid-epic")
    epic = "auth-overhaul"
    flat = specs / "flat-only"          # present in the fixture, not a manifest member
    (flat / "PRD.md").write_text("# real work", encoding="utf-8")
    _write_state(flat, {"currentStage": "forge-2-tech",
                        "branch": "forge/flat-only",
                        "stages": {"forge-1-prd": {"status": "complete"}}})

    res = run_cli("adopt-feature", epic, "flat-only",
                  "--charter", "Adopted leaf.", "--specs-dir", str(specs), "--json")
    assert res.returncode == 0, res.stdout + res.stderr
    summary = res.json()
    assert summary["adopted"] is True
    assert summary["relocated"] is True
    assert summary["manifestUpdated"] is True
    assert summary["wasAlreadyMember"] is False

    member = specs / epic / "flat-only"
    assert (member / "PRD.md").is_file()          # artifact moved
    assert not flat.exists()                       # no residual flat dir
    state = json.loads((member / STATE).read_text())
    assert state["epic"] == epic                   # back-pointer injected
    assert "flat-only" in _manifest_names(specs, epic)

    # Acceptance: resolve returns the single nested path; the epic re-validates clean.
    resolved = run_cli("resolve", "flat-only", "--specs-dir", str(specs))
    assert resolved.returncode == 0
    assert resolved.stdout.strip().endswith(f"{epic}/flat-only")
    valid = run_cli("validate", epic, "--specs-dir", str(specs), "--json")
    assert valid.returncode == 0 and valid.json()["valid"] is True


def test_adopt_split_brain_merges_preserving_backpointers(run_cli, fixture_copy) -> None:
    """A member stub + a detached standalone of the same name: merge keeps the
    stub's epic/branch back-pointers and overlays the standalone's real work."""
    specs = fixture_copy("valid-epic")
    epic = "auth-overhaul"
    # config-store is already a manifest member; give its stub epic+branch pointers.
    stub = specs / epic / "config-store"
    _write_state(stub, {"epic": epic, "branch": "forge/auth-overhaul",
                        "currentStage": "forge-1-prd", "stages": {}})
    # A detached standalone holds the real, further-along work on another branch.
    detached = specs / "config-store"
    _write_state(detached, {"branch": "topic/detached", "currentStage": "forge-3-specs",
                            "stages": {"forge-1-prd": {"status": "complete"},
                                       "forge-2-tech": {"status": "complete"}}})
    (detached / "PRD.md").write_text("# real", encoding="utf-8")

    res = run_cli("adopt-feature", epic, "config-store", "--specs-dir", str(specs), "--json")
    assert res.returncode == 0, res.stdout + res.stderr
    summary = res.json()
    assert summary["relocated"] is True
    assert summary["wasAlreadyMember"] is True      # no manifest add needed
    assert summary["manifestUpdated"] is False

    assert not detached.exists()                    # no residual flat dir
    assert (stub / "PRD.md").is_file()              # real work moved in
    state = json.loads((stub / STATE).read_text())
    assert state["epic"] == epic                    # preserved
    assert state["branch"] == "forge/auth-overhaul"  # stub branch preserved, NOT detached
    assert state["currentStage"] == "forge-3-specs"  # overlaid from the real work
    assert state["stages"]["forge-2-tech"]["status"] == "complete"

    resolved = run_cli("resolve", "config-store", "--specs-dir", str(specs))
    assert resolved.returncode == 0                 # single candidate, no ambiguity


def test_adopt_is_idempotent_on_rerun(run_cli, fixture_copy) -> None:
    """Re-running after a completed adopt is a clean no-op success."""
    specs = fixture_copy("valid-epic")
    epic = "auth-overhaul"
    _write_state(specs / "flat-only", {"currentStage": "forge-1-prd", "stages": {}})
    first = run_cli("adopt-feature", epic, "flat-only",
                    "--charter", "Adopted.", "--specs-dir", str(specs), "--json")
    assert first.returncode == 0
    second = run_cli("adopt-feature", epic, "flat-only",
                     "--charter", "Adopted.", "--specs-dir", str(specs), "--json")
    assert second.returncode == 0, second.stdout + second.stderr
    s = second.json()
    assert s["relocated"] is False           # nothing left to move
    assert s["wasAlreadyMember"] is True      # already in the manifest
    assert "flat-only" in _manifest_names(specs, epic)


def test_adopt_text_output_summarizes(run_cli, fixture_copy) -> None:
    """Non-JSON output prints a human summary + next steps."""
    specs = fixture_copy("valid-epic")
    _write_state(specs / "flat-only", {"currentStage": "forge-1-prd", "stages": {}})
    res = run_cli("adopt-feature", "auth-overhaul", "flat-only",
                  "--charter", "Adopted.", "--specs-dir", str(specs))
    assert res.returncode == 0
    assert "Adopted 'flat-only'" in res.stdout
    assert "Next steps:" in res.stdout


# --------------------------------------------------------------------------- #
# Failure modes (exit-code contract)
# --------------------------------------------------------------------------- #


def test_adopt_missing_epic_manifest_exit_2(run_cli, fixture_copy) -> None:
    specs = fixture_copy("valid-epic")
    _write_state(specs / "flat-only", {"currentStage": "forge-1-prd", "stages": {}})
    res = run_cli("adopt-feature", "no-such-epic", "flat-only", "--specs-dir", str(specs))
    assert res.returncode == 2
    assert res.stderr.startswith("Error:")


def test_adopt_nothing_to_adopt_exit_2(run_cli, fixture_copy) -> None:
    """Neither a flat standalone nor a member stub exists for the name."""
    specs = fixture_copy("valid-epic")
    res = run_cli("adopt-feature", "auth-overhaul", "ghost", "--specs-dir", str(specs))
    assert res.returncode == 2
    assert "nothing to adopt" in res.stderr.lower()


def test_adopt_unsafe_name_exit_2(run_cli, fixture_copy) -> None:
    specs = fixture_copy("valid-epic")
    res = run_cli("adopt-feature", "auth-overhaul", "../escape", "--specs-dir", str(specs))
    assert res.returncode == 2
    assert "Traceback" not in res.stderr


def test_adopt_dangling_dependency_exit_1_after_relocation(run_cli, fixture_copy) -> None:
    """A bad --depends-on refuses the manifest add (exit 1), but the relocation
    already happened and re-running without the bad dep completes it (re-entrant)."""
    specs = fixture_copy("valid-epic")
    epic = "auth-overhaul"
    _write_state(specs / "flat-only", {"currentStage": "forge-1-prd", "stages": {}})

    bad = run_cli("adopt-feature", epic, "flat-only", "--charter", "x",
                  "--depends-on", "does-not-exist", "--specs-dir", str(specs), "--json")
    assert bad.returncode == 1
    assert any(f["code"] == "dangling-ref" for f in bad.json()["findings"])
    # Relocation is done despite the manifest refusal — the flat dir is gone.
    assert not (specs / "flat-only").exists()
    assert (specs / epic / "flat-only" / STATE).is_file()
    assert "flat-only" not in _manifest_names(specs, epic)

    # Re-run without the bad dep: files already nested, only the manifest add remains.
    good = run_cli("adopt-feature", epic, "flat-only", "--charter", "x",
                   "--specs-dir", str(specs), "--json")
    assert good.returncode == 0
    assert good.json()["relocated"] is False
    assert "flat-only" in _manifest_names(specs, epic)
