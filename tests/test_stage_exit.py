"""Directive matrix for ``forge-session.py stage-exit`` (the Scripted Stage Exit).

Everything the old prose exit blocks asked the model to compute now comes out of
this subcommand deterministically; this suite pins the whole decision table:
effective auto-verify (off / global / per-stage / invalid keys) × verify freshness
(fresh / stale / never / failing / skipped) × tree state (clean / dirty / no git)
× host wording (claude / generic) × next-stage selection × the sentinel-is-the-
last-line invariant.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER = REPO_ROOT / "scripts" / "forge-session.py"
SENTINEL = "─ forge: end of stage ─"


def _project(
    tmp_path: Path,
    config: dict | None = None,
    state: dict | None = None,
    feature: str = "widget",
    git: bool = True,
    dirty: bool = False,
) -> Path:
    """Build a minimal project: config, specs/<feature>/.pipeline-state.json, git."""
    root = tmp_path / "proj"
    feature_dir = root / "specs" / feature
    feature_dir.mkdir(parents=True)
    (root / "forge.config.json").write_text(json.dumps(config or {}))
    if state is not None:
        (feature_dir / ".pipeline-state.json").write_text(json.dumps(state))
    if git:
        subprocess.run(["git", "init", "-qb", "main"], cwd=root, check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "t@t.invalid"],
                       check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "t"], check=True)
        subprocess.run(["git", "-C", str(root), "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "init"], check=True)
        if dirty:
            (root / "dirty.txt").write_text("uncommitted\n")
    return root


def _exit(cwd: Path, *args: str) -> dict:
    proc = subprocess.run(
        [sys.executable, str(HELPER), "stage-exit", "--json", *args],
        capture_output=True,
        text=True,
        cwd=str(cwd),
    )
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _state_with_verify(stage: str, verify_key: str, verify_entry: dict) -> dict:
    return {
        "pipelineStatus": "active",
        "stages": {
            stage: {"status": "complete", "version": 2},
            verify_key: verify_entry,
        },
    }


# --------------------------------------------------------------------------- #
# autoVerify effectiveness × gate selection
# --------------------------------------------------------------------------- #


def test_auto_verify_off_outstanding_verify_gates_standard(tmp_path: Path) -> None:
    root = _project(tmp_path, config={}, state=None)
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["autoVerifyEffective"] is False
    assert d["runInStageVerify"] is False
    assert d["verifyState"] == "never"
    assert d["verifyGate"] == "standard"
    assert d["verifyCommand"] == "/feature-forge:forge-verify widget"


def test_global_auto_verify_runs_in_stage_and_gates_none(tmp_path: Path) -> None:
    root = _project(tmp_path, config={"autoVerify": True})
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["autoVerifyEffective"] is True
    assert d["runInStageVerify"] is True
    assert d["verifyGate"] == "none"


def test_per_stage_override_beats_global(tmp_path: Path) -> None:
    root = _project(tmp_path, config={
        "autoVerify": True,
        "autoVerifyStages": {"forge-2-tech": False},
    })
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["autoVerifyEffective"] is False
    assert d["runInStageVerify"] is False
    assert d["verifyGate"] == "standard"


def test_non_boolean_auto_verify_fails_closed(tmp_path: Path) -> None:
    root = _project(tmp_path, config={"autoVerify": "true"})  # string, not bool
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["autoVerifyEffective"] is False


def test_invalid_auto_verify_keys_surface(tmp_path: Path) -> None:
    root = _project(tmp_path, config={"autoVerifyStages": {"forge-1-prod": True}})
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["invalidAutoVerifyKeys"] == ["forge-1-prod"]


def test_generic_host_gate_degrades_to_manual_print(tmp_path: Path) -> None:
    root = _project(tmp_path, config={})
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech",
              "--host", "generic")["directives"]
    assert d["verifyGate"] == "manual-print"


# --------------------------------------------------------------------------- #
# verify freshness × resolution collapse
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("entry,expected_state,expected_gate", [
    ({"status": "passed", "verifiedStageVersion": 2}, "fresh", "none"),
    ({"status": "passed", "verifiedStageVersion": 1}, "stale", "standard"),
    ({"status": "passed"}, "stale", "standard"),  # legacy: no freshness ledger
    ({"status": "findings-reported"}, "failing", "standard"),
    ({"status": "skipped"}, "skipped", "none"),
], ids=["fresh", "stale-version", "stale-legacy", "failing", "skipped"])
def test_verify_freshness_matrix(tmp_path: Path, entry, expected_state, expected_gate):
    state = _state_with_verify("forge-2-tech", "forge-verify-tech", entry)
    root = _project(tmp_path, config={}, state=state)
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["verifyState"] == expected_state
    assert d["verifyGate"] == expected_gate


def test_fresh_verify_suppresses_in_stage_run_even_with_auto_verify(tmp_path: Path):
    """A stage already verified at its current version is never double-verified."""
    state = _state_with_verify(
        "forge-2-tech", "forge-verify-tech",
        {"status": "passed", "verifiedStageVersion": 2},
    )
    root = _project(tmp_path, config={"autoVerify": True}, state=state)
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["runInStageVerify"] is False
    assert d["verifyGate"] == "none"


def test_skipped_verify_is_respected_not_reoffered(tmp_path: Path) -> None:
    state = _state_with_verify("forge-2-tech", "forge-verify-tech", {"status": "skipped"})
    root = _project(tmp_path, config={"autoVerify": True}, state=state)
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["runInStageVerify"] is False
    assert d["verifyGate"] == "none"


# --------------------------------------------------------------------------- #
# autoFix eligibility (config × tree state × no-git)
# --------------------------------------------------------------------------- #


def test_auto_fix_eligible_when_all_preconditions_hold(tmp_path: Path) -> None:
    root = _project(tmp_path, config={"autoVerify": True, "autoFix": True})
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["cleanTree"] is True
    assert d["autoFixEligible"] is True


def test_dirty_tree_blocks_auto_fix(tmp_path: Path) -> None:
    root = _project(tmp_path, config={"autoVerify": True, "autoFix": True}, dirty=True)
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["cleanTree"] is False
    assert d["autoFixEligible"] is False
    assert d["runInStageVerify"] is True  # verify still runs; only autoFix is blocked


def test_no_git_blocks_auto_fix_but_not_verify(tmp_path: Path) -> None:
    root = _project(tmp_path, config={"autoVerify": True, "autoFix": True}, git=False)
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["gitRepo"] is False
    assert d["cleanTree"] is None
    assert d["autoFixEligible"] is False
    assert d["runInStageVerify"] is True


def test_auto_fix_needs_auto_verify(tmp_path: Path) -> None:
    root = _project(tmp_path, config={"autoFix": True})  # autoVerify off
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["autoFixEligible"] is False


# --------------------------------------------------------------------------- #
# next stage selection
# --------------------------------------------------------------------------- #


def test_next_stage_fixed_successor_without_state(tmp_path: Path) -> None:
    root = _project(tmp_path, config={}, state=None)
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["nextStage"] == "forge-3-specs"
    assert d["nextCommand"] == "/feature-forge:forge-3-specs widget"


def test_next_stage_from_state_skips_completed_stages(tmp_path: Path) -> None:
    state = {
        "pipelineStatus": "active",
        "stages": {
            "forge-1-prd": {"status": "complete", "version": 1},
            "forge-2-tech": {"status": "complete", "version": 1},
            "forge-3-specs": {"status": "complete", "version": 1},  # done out of order
        },
    }
    root = _project(tmp_path, config={}, state=state)
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["nextStage"] == "forge-4-backlog"


def test_state_walk_behind_stage_never_wins(tmp_path: Path) -> None:
    """A state that hasn't flushed this stage's completion falls back to the successor."""
    state = {"pipelineStatus": "active", "stages": {}}
    root = _project(tmp_path, config={}, state=state)
    d = _exit(root, "--feature", "widget", "--stage", "forge-3-specs")["directives"]
    assert d["nextStage"] == "forge-4-backlog"  # never forge-1-prd


def test_epic_stage_handoff_placeholder_and_next_feature(tmp_path: Path) -> None:
    root = _project(tmp_path, config={}, feature="my-epic")
    d = _exit(root, "--feature", "my-epic", "--stage", "forge-0-epic")["directives"]
    assert d["nextCommand"] == "/feature-forge:forge-1-prd {first-actionable-feature}"
    d2 = _exit(root, "--feature", "my-epic", "--stage", "forge-0-epic",
               "--next-feature", "config-store")["directives"]
    assert d2["nextCommand"] == "/feature-forge:forge-1-prd config-store"


def test_epic_stage_verify_state_reads_forge_verify_epic(tmp_path: Path) -> None:
    state = _state_with_verify(
        "forge-0-epic", "forge-verify-epic",
        {"status": "passed", "verifiedStageVersion": 2},
    )
    root = _project(tmp_path, config={}, state=state, feature="my-epic")
    d = _exit(root, "--feature", "my-epic", "--stage", "forge-0-epic")["directives"]
    assert d["verifyState"] == "fresh"
    assert d["verifyGate"] == "none"


def test_nested_epic_member_resolves_state(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    member_dir = root / "specs" / "big-epic" / "member"
    member_dir.mkdir(parents=True)
    (root / "forge.config.json").write_text("{}")
    (member_dir / ".pipeline-state.json").write_text(json.dumps(
        _state_with_verify("forge-2-tech", "forge-verify-tech",
                           {"status": "passed", "verifiedStageVersion": 2})
    ))
    d = _exit(root, "--feature", "member", "--stage", "forge-2-tech")["directives"]
    assert d["verifyState"] == "fresh"


# --------------------------------------------------------------------------- #
# NEXT-STEPS block: host wording + sentinel invariant
# --------------------------------------------------------------------------- #


def test_claude_next_steps_wording_and_sentinel_last(tmp_path: Path) -> None:
    root = _project(tmp_path, config={})
    payload = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")
    block = payload["nextSteps"]
    assert "`/clear`" in block
    assert "/feature-forge:forge-3-specs widget" in block
    assert block.splitlines()[-1] == SENTINEL
    assert payload["sentinel"] == SENTINEL


def test_next_command_is_in_a_fenced_block_for_mobile_copy(tmp_path: Path) -> None:
    """The next-stage command is emitted inside a fenced code block (native
    copy button on mobile/remote hosts) sitting *before* the sentinel."""
    root = _project(tmp_path, config={})
    block = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["nextSteps"]
    lines = block.splitlines()
    assert "```\n/feature-forge:forge-3-specs widget\n```" in block
    # Sentinel still absolute-last; closing fence is the line just before it.
    assert lines[-1] == SENTINEL
    assert lines[-2] == "```"
    assert lines[-3] == "/feature-forge:forge-3-specs widget"


def test_generic_next_steps_has_no_clear_token(tmp_path: Path) -> None:
    root = _project(tmp_path, config={})
    block = _exit(root, "--feature", "widget", "--stage", "forge-2-tech",
                  "--host", "generic")["nextSteps"]
    assert "/clear" not in block
    assert "fresh session" in block
    assert block.splitlines()[-1] == SENTINEL


def test_pi_next_steps_uses_new_command_and_skill_prefix(tmp_path: Path) -> None:
    """`--host pi` names Pi's real commands: `/new` for a fresh session, `/skill:` slash
    commands — never Claude's `/clear` or the `/feature-forge:` prefix (in the rendered
    block AND the structured directives the skill reads)."""
    root = _project(tmp_path, config={})
    payload = _exit(root, "--feature", "widget", "--stage", "forge-2-tech", "--host", "pi")
    block = payload["nextSteps"]
    assert "`/new`" in block
    assert "/clear" not in block
    assert "```\n/skill:forge-3-specs widget\n```" in block
    assert "/feature-forge:" not in block
    assert block.splitlines()[-1] == SENTINEL
    # Structured directives are Pi-shaped too (the skill may surface these directly).
    assert payload["directives"]["nextCommand"] == "/skill:forge-3-specs widget"
    assert payload["directives"]["verifyCommand"] == "/skill:forge-verify widget"


def test_human_output_ends_with_sentinel(tmp_path: Path) -> None:
    """The default (non-JSON) form also ends at the sentinel — the skill copies it."""
    root = _project(tmp_path, config={})
    proc = subprocess.run(
        [sys.executable, str(HELPER), "stage-exit",
         "--feature", "widget", "--stage", "forge-2-tech"],
        capture_output=True, text=True, cwd=str(root),
    )
    assert proc.returncode == 0, proc.stderr
    lines = proc.stdout.rstrip("\n").splitlines()
    assert lines[-1] == SENTINEL
    assert lines[0] == "DIRECTIVES:"


# --------------------------------------------------------------------------- #
# epic backflow: stage-exit routing on epicChangeRequests[] / blocksCurrent
# --------------------------------------------------------------------------- #


def _request(kind="add-feature", blocks=False, status="open", target="net-new") -> dict:
    return {
        "kind": kind,
        "target": target,
        "rationale": "surfaced during the interview",
        "blocksCurrent": blocks,
        "raisedBy": "forge-2-tech",
        "raisedAt": "2026-07-10T00:00:00Z",
        "status": status,
    }


def _state_with_requests(requests: list[dict], epic: str | None = "my-epic") -> dict:
    state = {
        "pipelineStatus": "active",
        "stages": {"forge-2-tech": {"status": "complete", "version": 2}},
        "epicChangeRequests": requests,
    }
    if epic is not None:
        state["epic"] = epic
    return state


def test_no_epic_requests_is_byte_identical_and_omits_directive(tmp_path: Path) -> None:
    """The common path: no requests → no epicReconcile key, NEXT-STEPS unchanged."""
    plain = _project(tmp_path / "a", config={}, state=None)
    empty = _project(tmp_path / "b", config={},
                     state=_state_with_requests([]))  # field present but empty
    p = _exit(plain, "--feature", "widget", "--stage", "forge-2-tech")
    e = _exit(empty, "--feature", "widget", "--stage", "forge-2-tech")
    assert "epicReconcile" not in p["directives"]
    assert "epicReconcile" not in e["directives"]
    assert p["nextSteps"] == e["nextSteps"]  # empty array routes like no array
    assert "reconcile the epic" not in p["nextSteps"]


def test_blocking_request_interposes_reconcile_first(tmp_path: Path) -> None:
    state = _state_with_requests([_request(kind="move-boundary", blocks=True)])
    root = _project(tmp_path, config={}, state=state)
    payload = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")
    d, block = payload["directives"], payload["nextSteps"]
    assert d["epicReconcile"]["required"] is True
    assert d["epicReconcile"]["command"] == "/feature-forge:forge-0-epic my-epic"
    assert d["epicReconcile"]["count"] == 1
    # normal next stage is unchanged in the directives, only demoted in the block
    assert d["nextCommand"] == "/feature-forge:forge-3-specs widget"
    # the fenced primary command is the reconcile command
    assert "```\n/feature-forge:forge-0-epic my-epic\n```" in block
    assert "After reconciling, continue the pipeline with: " \
           "`/feature-forge:forge-3-specs widget`" in block
    assert block.splitlines()[-1] == SENTINEL


def test_nonblocking_request_keeps_routing_adds_reminder(tmp_path: Path) -> None:
    state = _state_with_requests([_request(kind="add-feature", blocks=False)])
    root = _project(tmp_path, config={}, state=state)
    payload = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")
    d, block = payload["directives"], payload["nextSteps"]
    assert d["epicReconcile"]["required"] is False
    assert d["epicReconcile"]["reminder"] is True
    assert d["epicReconcile"]["count"] == 1
    # fenced primary stays the normal next stage
    assert "```\n/feature-forge:forge-3-specs widget\n```" in block
    assert "You also flagged 1 epic change to reconcile when convenient: " \
           "`/feature-forge:forge-0-epic my-epic`" in block
    assert block.splitlines()[-1] == SENTINEL


def test_applied_and_dismissed_requests_are_ignored(tmp_path: Path) -> None:
    state = _state_with_requests([
        _request(blocks=True, status="applied"),
        _request(blocks=False, status="dismissed"),
    ])
    root = _project(tmp_path, config={}, state=state)
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert "epicReconcile" not in d  # only `open` requests route


def test_open_request_without_resolvable_epic_falls_back(tmp_path: Path) -> None:
    """A stray request but no epic name (no back-pointer, no --epic) → normal routing."""
    state = _state_with_requests([_request(blocks=True)], epic=None)
    root = _project(tmp_path, config={}, state=state)
    payload = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")
    assert "epicReconcile" not in payload["directives"]
    assert "reconcile the epic" not in payload["nextSteps"]


def test_mixed_requests_blocking_wins(tmp_path: Path) -> None:
    state = _state_with_requests([
        _request(kind="add-feature", blocks=False),
        _request(kind="move-boundary", blocks=True),
    ])
    root = _project(tmp_path, config={}, state=state)
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["epicReconcile"]["required"] is True
    assert d["epicReconcile"]["count"] == 1  # count of blocking requests
