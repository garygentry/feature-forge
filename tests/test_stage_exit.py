"""Directive matrix for ``forge-session.py stage-exit`` (the Scripted Stage Exit).

Everything the old prose exit blocks asked the model to compute now comes out of
this subcommand deterministically; this suite pins the whole decision table:
effective auto-verify (off / global / per-stage / invalid keys) × verify freshness
(fresh / stale / never / failing / skipped) × tree state (clean / dirty / no git)
× host wording (claude / generic) × next-stage selection × the sentinel-is-the-
last-line invariant.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER = REPO_ROOT / "scripts" / "forge-session.py"
SENTINEL = "─ forge: end of stage ─"


def _load_session():
    """Import the hyphenated script by path (it is not importable by name)."""
    spec = importlib.util.spec_from_file_location("forge_session_stage_exit", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


# --------------------------------------------------------------------------- #
# 07 §3.1 — nine-stage acceptance, outcome validation, terminal ownership
# --------------------------------------------------------------------------- #

#: The nine ids the CLI must accept, and nothing else. Deliberately spelled out
#: here rather than imported: this file is the CLI's black-box contract, so a
#: typo in the script's own domain must fail here instead of being echoed back.
#: (`tests/test_stage_constants_parity.py` is the structural guard that keeps this
#: literal and `EXIT_STAGES` in agreement.)
EXIT_STAGES = (
    "forge-0-epic",
    "forge-1-prd",
    "forge-2-tech",
    "forge-3-specs",
    "forge-4-backlog",
    "forge-5-loop",
    "forge-6-docs",
    "forge-verify",
    "forge-fix",
)
STATE_DRIVEN_STAGES = EXIT_STAGES[:5]
BRANCH_STAGES = ("forge-verify", "forge-fix")
EXIT_OUTCOMES = {
    "forge-5-loop": ("complete", "partial", "blocked", "needs-human", "deferred"),
    "forge-6-docs": ("complete", "blocked"),
    "forge-verify": ("passed", "findings", "skipped", "failed"),
    "forge-fix": (
        "no-findings", "decisions", "failed", "applied", "reverified",
        "reverify-findings", "deferred",
    ),
}
VERIFY_MODE_TO_STAGE = {
    "epic": "forge-0-epic",
    "prd": "forge-1-prd",
    "tech": "forge-2-tech",
    "specs": "forge-3-specs",
    "backlog": "forge-4-backlog",
    "impl": "forge-5-loop",
}
PRODUCTION_STAGES = EXIT_STAGES[:7]


def _run(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    """Run stage-exit without asserting success — the negative-path counterpart."""
    return subprocess.run(
        [sys.executable, str(HELPER), "stage-exit", "--json", *args],
        capture_output=True, text=True, cwd=str(cwd),
    )


def _rejected(cwd: Path, *args: str) -> str:
    """Assert the full fail-closed contract and return stderr.

    Exit 2, stderr leading with `Error:`, no success JSON on stdout, and no
    sentinel anywhere — a rejected request must not leak a terminal block that a
    model could copy (02 §10, REQ-REL-02).
    """
    proc = _run(cwd, *args)
    assert proc.returncode == 2, (proc.returncode, proc.stdout, proc.stderr)
    assert proc.stderr.startswith("Error:"), proc.stderr
    assert proc.stdout == "", proc.stdout
    assert SENTINEL not in proc.stdout + proc.stderr
    assert "Traceback" not in proc.stderr, proc.stderr
    return proc.stderr


def _minimal_args(stage: str) -> list[str]:
    """The smallest legal flag set for `stage`, as the CLI defines legality."""
    args = ["--stage", stage]
    if stage in EXIT_OUTCOMES:
        args += ["--outcome", EXIT_OUTCOMES[stage][0]]
    if stage in BRANCH_STAGES:
        args += ["--owner", "direct", "--served-stage", "forge-2-tech"]
    return args


@pytest.mark.parametrize("stage", EXIT_STAGES, ids=EXIT_STAGES)
def test_every_exit_stage_is_accepted(tmp_path: Path, stage: str) -> None:
    """All nine EXIT_STAGES ids close through the one router (REQ-EXIT-01/02)."""
    root = _project(tmp_path, config={})
    payload = _exit(root, "--feature", "widget", *_minimal_args(stage))
    assert payload["directives"]["stage"] == stage
    assert set(payload) == {"directives", "nextSteps", "sentinel"}


@pytest.mark.parametrize("stage", ["forge-7-ship", "forge-verify-impl", "FORGE-1-PRD", ""])
def test_an_unknown_stage_is_rejected(tmp_path: Path, stage: str) -> None:
    root = _project(tmp_path, config={})
    proc = _run(root, "--feature", "widget", "--stage", stage)
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert SENTINEL not in proc.stdout + proc.stderr


@pytest.mark.parametrize("stage", STATE_DRIVEN_STAGES, ids=STATE_DRIVEN_STAGES)
def test_state_driven_stages_reject_an_outcome(tmp_path: Path, stage: str) -> None:
    """Stages 0-4 have a single, state-driven outcome — supplying one is an error."""
    root = _project(tmp_path, config={})
    err = _rejected(root, "--feature", "widget", "--stage", stage, "--outcome", "complete")
    assert "--outcome is not accepted" in err
    assert stage in err


@pytest.mark.parametrize("stage", sorted(EXIT_OUTCOMES), ids=sorted(EXIT_OUTCOMES))
def test_outcome_bearing_stages_require_their_own_outcome(tmp_path: Path, stage: str):
    root = _project(tmp_path, config={})
    owner = ["--owner", "direct", "--served-stage", "forge-2-tech"] \
        if stage in BRANCH_STAGES else []

    err = _rejected(root, "--feature", "widget", "--stage", stage, *owner)
    assert f"{stage} requires --outcome" in err
    for value in EXIT_OUTCOMES[stage]:
        assert value in err, "the error must enumerate the accepted domain"

    # Every value from every OTHER outcome-bearing stage, unless it happens to be
    # shared (`complete`, `deferred`, `failed` legitimately appear in more than one).
    foreign = {
        value
        for other, values in EXIT_OUTCOMES.items()
        if other != stage
        for value in values
    } - set(EXIT_OUTCOMES[stage])
    for value in sorted(foreign) + ["bogus-outcome"]:
        err = _rejected(
            root, "--feature", "widget", "--stage", stage, "--outcome", value, *owner
        )
        assert f"--outcome {value!r} is not valid for {stage}" in err


@pytest.mark.parametrize("stage", sorted(EXIT_OUTCOMES), ids=sorted(EXIT_OUTCOMES))
def test_every_own_outcome_is_accepted(tmp_path: Path, stage: str) -> None:
    root = _project(tmp_path, config={})
    owner = ["--owner", "direct", "--served-stage", "forge-2-tech"] \
        if stage in BRANCH_STAGES else []
    for value in EXIT_OUTCOMES[stage]:
        d = _exit(root, "--feature", "widget", "--stage", stage,
                  "--outcome", value, *owner)["directives"]
        assert d["outcome"] == value


@pytest.mark.parametrize("stage", PRODUCTION_STAGES, ids=PRODUCTION_STAGES)
def test_production_stages_reject_owner(tmp_path: Path, stage: str) -> None:
    """Stages 0-6 are always direct owners, so the flag has nothing to say."""
    root = _project(tmp_path, config={})
    extra = ["--outcome", EXIT_OUTCOMES[stage][0]] if stage in EXIT_OUTCOMES else []
    err = _rejected(root, "--feature", "widget", "--stage", stage,
                    "--owner", "direct", *extra)
    assert "--owner is not accepted" in err


@pytest.mark.parametrize("stage", BRANCH_STAGES, ids=BRANCH_STAGES)
def test_branch_stages_require_owner(tmp_path: Path, stage: str) -> None:
    root = _project(tmp_path, config={})
    err = _rejected(root, "--feature", "widget", "--stage", stage,
                    "--outcome", EXIT_OUTCOMES[stage][0],
                    "--served-stage", "forge-2-tech")
    assert f"{stage} requires --owner" in err
    assert "direct" in err and "nested" in err


@pytest.mark.parametrize("stage", BRANCH_STAGES, ids=BRANCH_STAGES)
def test_an_unknown_owner_is_rejected(tmp_path: Path, stage: str) -> None:
    root = _project(tmp_path, config={})
    proc = _run(root, "--feature", "widget", "--stage", stage,
                "--outcome", EXIT_OUTCOMES[stage][0],
                "--served-stage", "forge-2-tech", "--owner", "outer")
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert SENTINEL not in proc.stdout + proc.stderr


@pytest.mark.parametrize("stage", BRANCH_STAGES, ids=BRANCH_STAGES)
def test_a_direct_branch_payload_owns_exactly_one_sentinel(tmp_path: Path, stage: str):
    root = _project(tmp_path, config={})
    payload = _exit(root, "--feature", "widget", "--stage", stage,
                    "--outcome", EXIT_OUTCOMES[stage][0],
                    "--served-stage", "forge-2-tech", "--owner", "direct")
    assert payload["directives"]["terminalOwnedBy"] == "self"
    assert payload["directives"]["owner"] == "direct"
    assert payload["sentinel"] == SENTINEL
    assert payload["nextSteps"].count(SENTINEL) == 1
    assert payload["nextSteps"].splitlines()[-1] == SENTINEL


@pytest.mark.parametrize("stage", BRANCH_STAGES, ids=BRANCH_STAGES)
def test_a_nested_branch_payload_prints_nothing_terminal(tmp_path: Path, stage: str):
    """An outer authoring stage owns the block, so there is no block to leak."""
    root = _project(tmp_path, config={})
    payload = _exit(root, "--feature", "widget", "--stage", stage,
                    "--outcome", EXIT_OUTCOMES[stage][0],
                    "--served-stage", "forge-2-tech", "--owner", "nested")
    assert payload["directives"]["terminalOwnedBy"] == "outer"
    assert payload["directives"]["owner"] == "nested"
    assert payload["nextSteps"] is None
    assert payload["sentinel"] is None
    # Routing/outcome directives survive; only the human block is withheld.
    assert payload["directives"]["servedStage"] == "forge-2-tech"
    assert payload["directives"]["outcome"] == EXIT_OUTCOMES[stage][0]
    assert payload["directives"]["nextStage"] == "forge-3-specs"


@pytest.mark.parametrize("stage", BRANCH_STAGES, ids=BRANCH_STAGES)
def test_nested_human_output_emits_no_sentinel(tmp_path: Path, stage: str) -> None:
    """`_print_stage_exit` must tolerate `nextSteps is None` without a terminal section."""
    root = _project(tmp_path, config={})
    proc = subprocess.run(
        [sys.executable, str(HELPER), "stage-exit", "--feature", "widget",
         "--stage", stage, "--outcome", EXIT_OUTCOMES[stage][0],
         "--served-stage", "forge-2-tech", "--owner", "nested"],
        capture_output=True, text=True, cwd=str(root),
    )
    assert proc.returncode == 0, proc.stderr
    assert SENTINEL not in proc.stdout
    assert "NEXT-STEPS" not in proc.stdout
    assert proc.stdout.splitlines()[0] == "DIRECTIVES:"
    json.loads(proc.stdout.split("\n", 1)[1])  # the rest is the directives object


def test_an_unknown_verify_capability_is_rejected_not_downgraded(tmp_path: Path) -> None:
    """Silently degrading an unknown capability to `manual` would hide a caller bug."""
    root = _project(tmp_path, config={})
    proc = _run(root, "--feature", "widget", "--stage", "forge-2-tech",
                "--verify-capability", "semi-interactive")
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert "semi-interactive" in proc.stderr
    assert SENTINEL not in proc.stdout + proc.stderr


@pytest.mark.parametrize("capability", ["interactive", "manual"])
def test_the_capability_is_reported_verbatim(tmp_path: Path, capability: str) -> None:
    root = _project(tmp_path, config={})
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech",
              "--verify-capability", capability)["directives"]
    assert d["verifyCapability"] == capability


def test_the_capability_defaults_to_manual(tmp_path: Path) -> None:
    root = _project(tmp_path, config={})
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["verifyCapability"] == "manual"


@pytest.mark.parametrize("name", ["../evil", "/abs", "a/b", "..", "Widget", ""])
def test_an_unsafe_identity_is_rejected_before_any_read(tmp_path: Path, name: str) -> None:
    root = _project(tmp_path, config={})
    _rejected(root, "--feature", name, "--stage", "forge-2-tech")


def test_unsafe_epic_and_next_feature_are_rejected_too(tmp_path: Path) -> None:
    root = _project(tmp_path, config={})
    _rejected(root, "--feature", "widget", "--stage", "forge-2-tech", "--epic", "../evil")
    _rejected(root, "--feature", "my-epic", "--stage", "forge-0-epic",
              "--next-feature", "../evil")


def test_branch_only_flags_are_rejected_on_a_production_exit(tmp_path: Path) -> None:
    root = _project(tmp_path, config={})
    for flag, value in (("--served-stage", "forge-2-tech"), ("--verify-mode", "tech")):
        err = _rejected(root, "--feature", "widget", "--stage", "forge-1-prd", flag, value)
        assert "branch-only" in err


def test_next_feature_is_rejected_outside_the_epic_stage(tmp_path: Path) -> None:
    root = _project(tmp_path, config={})
    err = _rejected(root, "--feature", "widget", "--stage", "forge-2-tech",
                    "--next-feature", "other")
    assert "--next-feature is accepted only for forge-0-epic" in err


@pytest.mark.parametrize("stage", EXIT_STAGES, ids=EXIT_STAGES)
def test_repeated_identical_requests_are_byte_identical(tmp_path: Path, stage: str):
    """Determinism (REQ-REL-01): no timestamps, no set iteration, no prose."""
    root = _project(tmp_path, config={})
    args = ["--feature", "widget", *_minimal_args(stage)]
    first = subprocess.run(
        [sys.executable, str(HELPER), "stage-exit", "--json", *args],
        capture_output=True, text=True, cwd=str(root),
    )
    second = subprocess.run(
        [sys.executable, str(HELPER), "stage-exit", "--json", *args],
        capture_output=True, text=True, cwd=str(root),
    )
    assert first.returncode == 0, first.stderr
    assert first.stdout == second.stdout
    human = [
        subprocess.run(
            [sys.executable, str(HELPER), "stage-exit", *args],
            capture_output=True, text=True, cwd=str(root),
        ).stdout
        for _ in range(2)
    ]
    assert human[0] == human[1]


# --------------------------------------------------------------------------- #
# 07 §3.2 — served-stage and verify-mode resolution
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("owner", ["direct", "nested"])
@pytest.mark.parametrize("stage", BRANCH_STAGES, ids=BRANCH_STAGES)
@pytest.mark.parametrize("served", PRODUCTION_STAGES, ids=PRODUCTION_STAGES)
def test_an_explicit_served_stage_resolves(
    tmp_path: Path, stage: str, owner: str, served: str
) -> None:
    """Explicit `--served-stage` accepts any ProductionStage, forge-6-docs included."""
    root = _project(tmp_path, config={})
    d = _exit(root, "--feature", "widget", "--stage", stage,
              "--outcome", EXIT_OUTCOMES[stage][0], "--owner", owner,
              "--served-stage", served)["directives"]
    assert d["servedStage"] == served


@pytest.mark.parametrize("mode,served", sorted(VERIFY_MODE_TO_STAGE.items()))
@pytest.mark.parametrize("stage", BRANCH_STAGES, ids=BRANCH_STAGES)
def test_a_mode_only_input_maps_through_the_unique_mapping(
    tmp_path: Path, stage: str, mode: str, served: str
) -> None:
    root = _project(tmp_path, config={})
    d = _exit(root, "--feature", "widget", "--stage", stage,
              "--outcome", EXIT_OUTCOMES[stage][0], "--owner", "direct",
              "--verify-mode", mode)["directives"]
    assert d["servedStage"] == served
    assert d["verifyMode"] == mode


@pytest.mark.parametrize("mode,served", sorted(VERIFY_MODE_TO_STAGE.items()))
def test_matching_explicit_stage_and_mode_agree(
    tmp_path: Path, mode: str, served: str
) -> None:
    root = _project(tmp_path, config={})
    d = _exit(root, "--feature", "widget", "--stage", "forge-verify",
              "--outcome", "passed", "--owner", "direct",
              "--served-stage", served, "--verify-mode", mode)["directives"]
    assert d["servedStage"] == served


#: Every adjacent-mode conflict — each mode's own stage paired with the NEXT mode —
#: plus the forge-6-docs case no mode can express, and one wrap-around pair.
_MODE_ORDER = tuple(VERIFY_MODE_TO_STAGE)
_NEIGHBOUR_CONFLICTS = [
    (VERIFY_MODE_TO_STAGE[_MODE_ORDER[i]], _MODE_ORDER[i + 1])
    for i in range(len(_MODE_ORDER) - 1)
] + [("forge-6-docs", "impl"), ("forge-0-epic", "prd")]


@pytest.mark.parametrize("served,mode", _NEIGHBOUR_CONFLICTS)
def test_a_conflicting_stage_and_mode_fails_closed(
    tmp_path: Path, served: str, mode: str
) -> None:
    """Picking one silently is exactly the guess REQ-ROUTE-03 forbids."""
    root = _project(tmp_path, config={})
    err = _rejected(root, "--feature", "widget", "--stage", "forge-verify",
                    "--outcome", "passed", "--owner", "direct",
                    "--served-stage", served, "--verify-mode", mode)
    assert "--served-stage" in err and "--verify-mode" in err
    assert served in err and mode in err
    assert VERIFY_MODE_TO_STAGE[mode] in err


@pytest.mark.parametrize("owner", ["direct", "nested"])
@pytest.mark.parametrize("stage", BRANCH_STAGES, ids=BRANCH_STAGES)
def test_neither_input_names_both_recovery_flags(
    tmp_path: Path, stage: str, owner: str
) -> None:
    root = _project(tmp_path, config={})
    err = _rejected(root, "--feature", "widget", "--stage", stage,
                    "--outcome", EXIT_OUTCOMES[stage][0], "--owner", owner)
    assert "--served-stage" in err and "--verify-mode" in err
    assert "the production stage this verification served" in err


@pytest.mark.parametrize(
    "flag,value",
    [("--served-stage", "forge-verify"), ("--served-stage", "forge-9-ship"),
     ("--verify-mode", "docs"), ("--verify-mode", "implementation")],
)
def test_an_invalid_served_stage_or_mode_is_rejected(
    tmp_path: Path, flag: str, value: str
) -> None:
    root = _project(tmp_path, config={})
    proc = _run(root, "--feature", "widget", "--stage", "forge-verify",
                "--outcome", "passed", "--owner", "direct", flag, value)
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert SENTINEL not in proc.stdout + proc.stderr


def test_resolve_served_stage_is_importable_and_pure() -> None:
    """`02` §3.2 declares this callable; tests import it rather than a wrapper."""
    session = _load_session()
    assert session.resolve_served_stage("forge-3-specs", None) == "forge-3-specs"
    assert session.resolve_served_stage(None, "backlog") == "forge-4-backlog"
    assert session.resolve_served_stage("forge-1-prd", "prd") == "forge-1-prd"
    # Explicit stage takes precedence over nothing else to disagree with.
    assert session.resolve_served_stage("forge-6-docs", None) == "forge-6-docs"
    for bad in ((None, None), ("forge-2-tech", "prd"), ("forge-verify", None),
                (None, "docs")):
        with pytest.raises(session.UsageError):
            session.resolve_served_stage(*bad)


# --------------------------------------------------------------------------- #
# directive shape: verifyStage vs servedStage, warnings, stageNoun
# --------------------------------------------------------------------------- #


def test_verify_stage_is_distinct_from_served_stage(tmp_path: Path) -> None:
    """A production exit resolves no served stage but may still owe verification."""
    state = _state_with_verify(
        "forge-2-tech", "forge-verify-tech", {"status": "pending"},
    )
    root = _project(tmp_path, config={}, state=state)
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["servedStage"] is None, "a production exit serves only itself"
    assert d["verifyStage"] == "forge-2-tech", "the debt is owed on the closing stage"


def test_verify_stage_is_none_when_nothing_is_outstanding(tmp_path: Path) -> None:
    state = _state_with_verify(
        "forge-2-tech", "forge-verify-tech",
        {"status": "passed", "verifiedStageVersion": 2},
    )
    root = _project(tmp_path, config={}, state=state)
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["verifyStage"] is None


@pytest.mark.parametrize("stage", EXIT_STAGES, ids=EXIT_STAGES)
def test_warnings_is_always_a_present_list(tmp_path: Path, stage: str) -> None:
    """`[]` means checked-and-clean; absent would mean "not evaluated" (00 §4)."""
    root = _project(tmp_path, config={})
    d = _exit(root, "--feature", "widget", *_minimal_args(stage))["directives"]
    assert d["warnings"] == []
    assert isinstance(d["warnings"], list)


def test_malformed_debt_metadata_becomes_warnings_entry_two(tmp_path: Path) -> None:
    """00 §4 entry 2: legacy/malformed `scheduledStageVersion` (03 §5.1)."""
    state = _state_with_verify(
        "forge-2-tech", "forge-verify-tech", {"status": "auto-verify-pending"},
    )
    root = _project(tmp_path, config={}, state=state)
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert len(d["warnings"]) == 1
    entry = d["warnings"][0]
    assert entry.startswith("widget: forge-verify-tech is auto-verify-pending")
    assert "scheduledStageVersion is missing or malformed" in entry
    # REQ-OBS-02: a warning names the affected subject AND the recovery action.
    assert "/feature-forge:forge-verify widget" in entry


def test_a_revision_mismatch_becomes_warnings_entry_three(tmp_path: Path) -> None:
    """00 §4 entry 3: the scheduled-vs-current revision note (03 §5.3)."""
    state = _state_with_verify(
        "forge-2-tech", "forge-verify-tech",
        {"status": "auto-verify-pending", "scheduledStageVersion": 1},
    )
    root = _project(tmp_path, config={}, state=state)
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["warnings"] == [
        "widget: automatic verification is still pending for forge-2-tech; "
        "run /feature-forge:forge-verify widget to resolve it. The artifact has "
        "advanced since it was scheduled (scheduled at revision 1, now at "
        "revision 2)."
    ]


def test_a_current_revision_schedule_warns_about_nothing(tmp_path: Path) -> None:
    state = _state_with_verify(
        "forge-2-tech", "forge-verify-tech",
        {"status": "auto-verify-pending", "scheduledStageVersion": 2},
    )
    root = _project(tmp_path, config={}, state=state)
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["verifyState"] == "auto-pending", "the debt is still owed"
    assert d["warnings"] == [], "an on-revision schedule is not an advisory"


def test_a_branch_exit_warns_from_the_stage_it_served(tmp_path: Path) -> None:
    """The debt belongs to the served artifact — forge-verify has none of its own."""
    state = _state_with_verify(
        "forge-2-tech", "forge-verify-tech",
        {"status": "auto-verify-pending", "scheduledStageVersion": 1},
    )
    root = _project(tmp_path, config={}, state=state)
    d = _exit(root, "--feature", "widget", "--stage", "forge-verify",
              "--outcome", "failed", "--owner", "direct",
              "--verify-mode", "tech")["directives"]
    assert d["verifyState"] == "auto-pending"
    assert len(d["warnings"]) == 1
    assert "forge-2-tech" in d["warnings"][0]


@pytest.mark.parametrize("stage", EXIT_STAGES, ids=EXIT_STAGES)
def test_stage_noun_is_retained_and_total(tmp_path: Path, stage: str) -> None:
    """Pre-existing key, kept verbatim: mapped where mapped, stage id otherwise."""
    root = _project(tmp_path, config={})
    d = _exit(root, "--feature", "widget", *_minimal_args(stage))["directives"]
    assert isinstance(d["stageNoun"], str) and d["stageNoun"]
    expected = {
        "forge-0-epic": "the epic decomposition",
        "forge-1-prd": "the PRD",
        "forge-2-tech": "the tech spec",
        "forge-3-specs": "the implementation specs",
        "forge-4-backlog": "the backlog",
    }.get(stage, stage)
    assert d["stageNoun"] == expected


def test_every_protocol_stage_noun_slot_has_a_directive_to_fill_it() -> None:
    """The `{stageNoun}` slots in canon are filled from this directive, not prose.

    The key is pre-existing and retained verbatim; this pins the other half of the
    contract — that canon still has slots and the router still emits a non-empty
    value for every stage that can reach them.
    """
    protocol = (REPO_ROOT / "references" / "stage-exit-protocol.md").read_text(
        encoding="utf-8"
    )
    assert protocol.count("{stageNoun}") >= 1, "canon lost its stageNoun slots"
    session = _load_session()
    for stage in EXIT_STAGES:
        filled = session.STAGE_NOUN.get(stage, stage)
        assert filled and "{" not in filled, stage
