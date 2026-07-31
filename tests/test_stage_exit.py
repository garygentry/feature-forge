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


def _epic_project(
    tmp_path: Path,
    revision: int | None = 1,
    epic_entry: dict | None = None,
    config: dict | None = None,
    epic: str = "my-epic",
) -> Path:
    """A project whose ``specs/<epic>/`` carries a manifest and ``.epic-state.json``.

    Epic verification state is epic-scoped: the entry lives in
    ``.epic-state.json`` and its artifact revision is the manifest's ``revision``
    (03 §2.1/§2.2). Pass ``revision=None`` for a legacy manifest with no revision
    key, which reads as logical 1.
    """
    root = _project(tmp_path, config=config or {}, feature=epic)
    epic_dir = root / "specs" / epic
    manifest: dict = {"epic": epic, "features": []}
    if revision is not None:
        manifest["revision"] = revision
    (epic_dir / "epic-manifest.json").write_text(json.dumps(manifest))
    if epic_entry is not None:
        (epic_dir / ".epic-state.json").write_text(json.dumps(
            {"epic": epic, "stages": {"forge-verify-epic": epic_entry}}
        ))
    return root


def _state_with_verify(stage: str, verify_key: str, verify_entry: dict) -> dict:
    return {
        "pipelineStatus": "active",
        "stages": {
            stage: {"status": "complete", "version": 2},
            verify_key: verify_entry,
        },
    }


#: A `forge-2-tech` verify entry that classifies `fresh` against
#: ``_state_with_verify``'s version 2. Tests whose subject is *production*
#: routing (next-stage selection, epic reconcile precedence, host command
#: rendering) seed this so verification is resolved: since item 011, an
#: unresolved verification makes the VERIFY command primary and demotes the
#: production successor to unfenced prose (02 §4 verify-primary ordering), which
#: would otherwise mask the behavior those tests exist to pin.
_FRESH_TECH_VERIFY = {"status": "passed", "verifiedStageVersion": 2}


# --------------------------------------------------------------------------- #
# autoVerify effectiveness × gate selection
# --------------------------------------------------------------------------- #


def test_auto_verify_off_outstanding_verify_gates_standard(tmp_path: Path) -> None:
    # INTENTIONAL CHANGE (item 011, capability-aware gate selection): the gate no
    # longer follows `--host claude`; it follows `--verify-capability`. The flag is
    # supplied explicitly here because the CLI default is `manual`.
    root = _project(tmp_path, config={}, state=None)
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech",
              "--verify-capability", "interactive")["directives"]
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
    # INTENTIONAL CHANGE (item 011, capability-aware gate selection): `standard`
    # now requires `--verify-capability interactive`, not `--host claude`.
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech",
              "--verify-capability", "interactive")["directives"]
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


@pytest.mark.parametrize("host", ["claude", "pi", "generic"])
def test_a_manual_capability_gates_manual_print_on_every_host(
    tmp_path: Path, host: str
) -> None:
    """INTENTIONAL CHANGE (item 011, capability-aware gate selection).

    This replaces the old `test_generic_host_gate_degrades_to_manual_print`,
    which asserted the *host name* degraded the gate. The `host == "claude"`
    branch is gone: `manual` yields `manual-print` on Claude too (REQ-EXIT-07).
    """
    root = _project(tmp_path, config={})
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech",
              "--host", host, "--verify-capability", "manual")["directives"]
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
    # INTENTIONAL CHANGE (item 011, capability-aware gate selection): the `standard`
    # rows now require an explicit `--verify-capability interactive`; before item 011
    # the default `--host claude` alone produced them.
    state = _state_with_verify("forge-2-tech", "forge-verify-tech", entry)
    root = _project(tmp_path, config={}, state=state)
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech",
              "--verify-capability", "interactive")["directives"]
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


def test_epic_stage_verify_state_reads_the_epic_state_file(tmp_path: Path) -> None:
    """INTENTIONAL CHANGE (item 012, epic-scoped verification source).

    This replaces the old `test_epic_stage_verify_state_reads_forge_verify_epic`,
    which seeded `forge-verify-epic` inside the *member* `.pipeline-state.json`
    and asserted stage-exit read it there. Since item 006 that entry's only home
    is `{specsDir}/{epic}/.epic-state.json`, compared against the epic manifest's
    `revision` — never a member state and never a member stage version (03 §2.1/
    §4.1, REQ-SEC-01). The routing assertions (`fresh` → gate `none`) are
    unchanged; only the file the label is read from moved.
    """
    root = _epic_project(tmp_path, revision=2, epic_entry={
        "status": "passed", "verifiedStageVersion": 2,
    })
    d = _exit(root, "--feature", "my-epic", "--stage", "forge-0-epic")["directives"]
    assert d["verifyState"] == "fresh"
    assert d["verifyGate"] == "none"


def test_epic_stage_ignores_a_member_state_forge_verify_epic_entry(tmp_path: Path):
    """A `forge-verify-epic` entry planted in member state is NOT the epic's."""
    root = _epic_project(tmp_path, revision=2, epic_entry=None)
    (root / "specs" / "my-epic" / ".pipeline-state.json").write_text(json.dumps(
        _state_with_verify("forge-0-epic", "forge-verify-epic",
                           {"status": "passed", "verifiedStageVersion": 2})
    ))
    d = _exit(root, "--feature", "my-epic", "--stage", "forge-0-epic")["directives"]
    assert d["verifyState"] == "never"


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
    copy button on mobile/remote hosts) sitting *before* the sentinel.

    INTENTIONAL CHANGE (item 011, verify-primary ordering): the fixture now seeds
    a fresh verify entry. The production successor is the fenced primary command
    only once verification is RESOLVED; while it is outstanding the verify command
    holds the fence instead (REQ-EXIT-06).
    """
    state = _state_with_verify("forge-2-tech", "forge-verify-tech", _FRESH_TECH_VERIFY)
    root = _project(tmp_path, config={}, state=state)
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
    block AND the structured directives the skill reads).

    INTENTIONAL CHANGE (item 011, verify-primary ordering): seeded fresh so the
    production successor legitimately holds the fence; host translation of the
    verify-primary form is pinned separately in the §3.4 matrix below.
    """
    state = _state_with_verify("forge-2-tech", "forge-verify-tech", _FRESH_TECH_VERIFY)
    root = _project(tmp_path, config={}, state=state)
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


def _state_with_requests(
    requests: list[dict], epic: str | None = "my-epic", verified: bool = True
) -> dict:
    """Epic-backflow fixture.

    ``verified`` seeds a fresh `forge-verify-tech` entry by default. INTENTIONAL
    CHANGE (item 011, verify-primary ordering): reconcile *precedence* — which
    command is fenced and which is demoted — is only observable once verification
    is resolved, because an outstanding verification outranks the reconcile
    (02 §5.2). Pass ``verified=False`` to exercise the coexistence case.
    """
    stages: dict = {"forge-2-tech": {"status": "complete", "version": 2}}
    if verified:
        stages["forge-verify-tech"] = dict(_FRESH_TECH_VERIFY)
    state = {
        "pipelineStatus": "active",
        "stages": stages,
        "epicChangeRequests": requests,
    }
    if epic is not None:
        state["epic"] = epic
    return state


def test_no_epic_requests_is_byte_identical_and_omits_directive(tmp_path: Path) -> None:
    """The common path: no requests → no epicReconcile key, NEXT-STEPS unchanged.

    INTENTIONAL CHANGE (item 011, verify-primary ordering): both sides now carry
    the same fresh verify entry, so the comparison isolates the epicChangeRequests
    field rather than accidentally comparing a verify-primary block against a
    production-primary one.
    """
    no_requests = _state_with_requests([], epic=None)
    del no_requests["epicChangeRequests"]
    plain = _project(tmp_path / "a", config={}, state=no_requests)
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


# --------------------------------------------------------------------------- #
# 07 §3.4 — verify-first priority, capability gates, hosts, and rendering
#
# This whole section is NEW for item 011. It pins the two intentional stages 0–4
# behavior changes REQ-COMPAT-01 carves out: verify-primary ordering (the verify
# command is the sole fenced action while verification is unresolved) and
# capability-aware gate selection (`--verify-capability`, never `--host`, picks
# the gate).
# --------------------------------------------------------------------------- #


_OUTSTANDING_ENTRIES = {
    "never": None,
    "stale": {"status": "passed", "verifiedStageVersion": 1},
    "failing": {"status": "findings-reported"},
    "auto-pending": {"status": "auto-verify-pending", "scheduledStageVersion": 2},
}
_RESOLVED_ENTRIES = {
    "fresh": {"status": "passed", "verifiedStageVersion": 2},
    "skipped": {"status": "skipped"},
}


def _tech_project(tmp_path: Path, entry: dict | None, config: dict | None = None) -> Path:
    """A `forge-2-tech` project whose verify entry is exactly ``entry``."""
    state = {"pipelineStatus": "active", "stages": {
        "forge-2-tech": {"status": "complete", "version": 2},
    }}
    if entry is not None:
        state["stages"]["forge-verify-tech"] = entry
    return _project(tmp_path, config=config or {}, state=state)


@pytest.mark.parametrize("label", sorted(_RESOLVED_ENTRIES))
@pytest.mark.parametrize("capability", ["interactive", "manual"])
@pytest.mark.parametrize("auto", [True, False])
def test_resolved_verification_routes_to_the_production_successor(
    tmp_path: Path, label: str, capability: str, auto: bool
) -> None:
    """07 §3.4 row 1: `fresh`/`skipped` → production successor, gate `none`."""
    root = _tech_project(tmp_path, _RESOLVED_ENTRIES[label], config={"autoVerify": auto})
    payload = _exit(root, "--feature", "widget", "--stage", "forge-2-tech",
                    "--verify-capability", capability)
    d = payload["directives"]
    assert d["verifyState"] == label
    assert d["verifyGate"] == "none"
    assert d["runInStageVerify"] is False
    assert d["primaryCommand"] == "/feature-forge:forge-3-specs widget"
    assert d["deferredCommand"] is None
    assert "```\n/feature-forge:forge-3-specs widget\n```" in payload["nextSteps"]


@pytest.mark.parametrize("label", sorted(_OUTSTANDING_ENTRIES))
@pytest.mark.parametrize("capability", ["interactive", "manual"])
def test_auto_verify_owed_keeps_the_gate_none_and_defers_production(
    tmp_path: Path, label: str, capability: str
) -> None:
    """07 §3.4 row 2: auto-verify effective and owed → nested chain, gate `none`."""
    root = _tech_project(tmp_path, _OUTSTANDING_ENTRIES[label],
                         config={"autoVerify": True})
    payload = _exit(root, "--feature", "widget", "--stage", "forge-2-tech",
                    "--verify-capability", capability)
    d = payload["directives"]
    assert d["verifyState"] == label
    assert d["runInStageVerify"] is True
    assert d["verifyGate"] == "none", "the in-stage run covers it; no gate is rendered"
    assert d["primaryCommand"] == "/feature-forge:forge-verify widget"
    assert d["deferredCommand"] == "/feature-forge:forge-3-specs widget"


@pytest.mark.parametrize("label", sorted(_OUTSTANDING_ENTRIES))
def test_outstanding_plus_interactive_gates_standard(tmp_path: Path, label: str) -> None:
    """07 §3.4 row 3: outstanding + `interactive` → `standard`, verify primary."""
    root = _tech_project(tmp_path, _OUTSTANDING_ENTRIES[label])
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech",
              "--verify-capability", "interactive")["directives"]
    assert d["verifyGate"] == "standard"
    assert d["primaryCommand"] == "/feature-forge:forge-verify widget"


@pytest.mark.parametrize("label", sorted(_OUTSTANDING_ENTRIES))
def test_outstanding_plus_manual_gates_manual_print(tmp_path: Path, label: str) -> None:
    """07 §3.4 row 4: outstanding + `manual` → `manual-print`, verify fenced."""
    root = _tech_project(tmp_path, _OUTSTANDING_ENTRIES[label])
    payload = _exit(root, "--feature", "widget", "--stage", "forge-2-tech",
                    "--verify-capability", "manual")
    d = payload["directives"]
    assert d["verifyGate"] == "manual-print"
    assert d["primaryCommand"] == "/feature-forge:forge-verify widget"
    assert "```\n/feature-forge:forge-verify widget\n```" in payload["nextSteps"]


def test_a_tokenless_stage_promotes_no_verify_command(tmp_path: Path) -> None:
    """07 §3.4 row 5: `verifyState: "none"` → production, gate `none`, no promotion."""
    root = _project(tmp_path, config={"autoVerify": True}, state=None)
    payload = _exit(root, "--feature", "widget", "--stage", "forge-6-docs",
                    "--outcome", "complete", "--verify-capability", "interactive")
    d = payload["directives"]
    assert d["verifyState"] == "none"
    assert d["verifyGate"] == "none"
    assert d["runInStageVerify"] is False
    assert d["primaryCommand"] != d["verifyCommand"]
    assert "forge-verify" not in payload["nextSteps"]


# --- capability, not host, selects the gate -------------------------------- #


def test_a_capable_pi_session_gets_standard(tmp_path: Path) -> None:
    """REQ-EXIT-07: capable Pi is `standard`, exactly like capable Claude."""
    root = _tech_project(tmp_path, None)
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech",
              "--host", "pi", "--verify-capability", "interactive")["directives"]
    assert d["verifyGate"] == "standard"


def test_an_incapable_claude_session_gets_manual_print(tmp_path: Path) -> None:
    """REQ-EXIT-07: the `host == "claude"` gate branch is gone."""
    root = _tech_project(tmp_path, None)
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech",
              "--host", "claude", "--verify-capability", "manual")["directives"]
    assert d["verifyGate"] == "manual-print"


@pytest.mark.parametrize("host", ["claude", "pi", "generic"])
@pytest.mark.parametrize("capability", ["interactive", "manual"])
def test_the_gate_is_a_pure_function_of_state_and_capability(
    tmp_path: Path, host: str, capability: str
) -> None:
    """The same (verifyState, capability) pair yields the same gate on every host."""
    root = _tech_project(tmp_path, None)
    d = _exit(root, "--feature", "widget", "--stage", "forge-2-tech",
              "--host", host, "--verify-capability", capability)["directives"]
    assert d["verifyGate"] == ("standard" if capability == "interactive" else
                               "manual-print")


def test_no_source_path_selects_the_gate_from_the_host_name() -> None:
    """A structural guard: the retired `host == "claude"` gate branch stays retired."""
    source = (REPO_ROOT / "scripts" / "forge-session.py").read_text(encoding="utf-8")
    start = source.index("def stage_exit(")
    end = source.index("def _print_stage_exit(", start)
    body = source[start:end]
    gate_region = body[body.index("verify_gate ="):]
    assert 'host == "claude"' not in body, "the host-name gate branch is forbidden"
    assert "host" not in gate_region.split("next_stage_id")[0], (
        "gate selection must not read `host` at all"
    )


# --- host rendering is translation only ------------------------------------ #


def test_claude_renders_clear_and_the_canonical_prefix(tmp_path: Path) -> None:
    root = _tech_project(tmp_path, None)
    block = _exit(root, "--feature", "widget", "--stage", "forge-2-tech",
                  "--host", "claude")["nextSteps"]
    assert "`/clear`" in block
    assert "/new" not in block
    assert "```\n/feature-forge:forge-verify widget\n```" in block
    assert "/skill:" not in block


def test_pi_renders_new_and_the_skill_prefix_on_the_verify_primary(tmp_path: Path):
    root = _tech_project(tmp_path, None)
    payload = _exit(root, "--feature", "widget", "--stage", "forge-2-tech",
                    "--host", "pi")
    block = payload["nextSteps"]
    assert "`/new`" in block
    assert "/clear" not in block
    assert "```\n/skill:forge-verify widget\n```" in block
    assert "/feature-forge:" not in block
    assert payload["directives"]["primaryCommand"] == "/skill:forge-verify widget"
    assert payload["directives"]["deferredCommand"] == "/skill:forge-3-specs widget"


def test_generic_stays_host_neutral_on_the_verify_primary(tmp_path: Path) -> None:
    root = _tech_project(tmp_path, None)
    block = _exit(root, "--feature", "widget", "--stage", "forge-2-tech",
                  "--host", "generic")["nextSteps"]
    assert "/clear" not in block
    assert "/new" not in block
    assert "/skill:" not in block
    assert "fresh session" in block
    assert "```\n/feature-forge:forge-verify widget\n```" in block


# --- REQ-EXIT-06: the deferred command is never fenced --------------------- #


def _fenced_commands(block: str) -> list[str]:
    """Every command line inside a ``` fence, in order."""
    out, inside = [], False
    for line in block.splitlines():
        if line.strip() == "```":
            inside = not inside
            continue
        if inside:
            out.append(line)
    return out


@pytest.mark.parametrize("label", sorted(_OUTSTANDING_ENTRIES))
@pytest.mark.parametrize("capability", ["interactive", "manual"])
@pytest.mark.parametrize("host", ["claude", "pi", "generic"])
def test_the_verify_command_is_the_only_fenced_command(
    tmp_path: Path, label: str, capability: str, host: str
) -> None:
    root = _tech_project(tmp_path, _OUTSTANDING_ENTRIES[label])
    payload = _exit(root, "--feature", "widget", "--stage", "forge-2-tech",
                    "--host", host, "--verify-capability", capability)
    d, block = payload["directives"], payload["nextSteps"]
    assert _fenced_commands(block) == [d["primaryCommand"]]
    assert d["primaryCommand"] == d["verifyCommand"]
    assert d["deferredCommand"] not in _fenced_commands(block)
    # The successor is present, but only as unfenced conditional prose.
    assert f"After verification passes, continue with: `{d['deferredCommand']}`" in block


def test_next_command_never_overrides_the_primary_command(tmp_path: Path) -> None:
    """`nextCommand` stays compatibility/routing metadata (00 §4)."""
    root = _tech_project(tmp_path, None)
    payload = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")
    d = payload["directives"]
    assert d["nextCommand"] == "/feature-forge:forge-3-specs widget"
    assert d["primaryCommand"] == "/feature-forge:forge-verify widget"
    assert _fenced_commands(payload["nextSteps"]) == [d["primaryCommand"]]


def test_fresh_session_guidance_follows_the_verification_action(tmp_path: Path) -> None:
    """REQ-EXIT-06: never 'clear, then run the production successor'."""
    root = _tech_project(tmp_path, None)
    block = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["nextSteps"]
    lines = block.splitlines()
    clear_idx = next(i for i, ln in enumerate(lines) if ln.startswith("1. "))
    follow = lines[clear_idx + 1]
    assert follow.startswith("2. ")
    assert "run the verification below" in follow
    assert "run the next stage below" not in block


def test_a_resolved_exit_keeps_the_original_next_stage_wording(tmp_path: Path) -> None:
    """The pre-item-011 wording is retained verbatim once verification is resolved."""
    root = _tech_project(tmp_path, _RESOLVED_ENTRIES["fresh"])
    block = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")["nextSteps"]
    assert (
        "2. Then start a fresh session and run the next stage below — or "
        "re-run `/feature-forge:forge` to let the navigator resume from disk."
    ) in block


# --- verification + blocking epic reconcile coexist ------------------------ #


def test_verification_outranks_a_blocking_reconcile(tmp_path: Path) -> None:
    """Item 011 step 5 / 02 §5.2: verify primary, reconcile FIRST deferred."""
    state = _state_with_requests(
        [_request(kind="move-boundary", blocks=True)], verified=False
    )
    root = _project(tmp_path, config={}, state=state)
    payload = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")
    d, block = payload["directives"], payload["nextSteps"]
    assert d["epicReconcile"]["required"] is True
    assert d["primaryCommand"] == "/feature-forge:forge-verify widget"
    assert _fenced_commands(block) == ["/feature-forge:forge-verify widget"]
    reconcile_line = (
        "After verification passes, reconcile the epic first — 1 blocking epic "
        "change request flagged: `/feature-forge:forge-0-epic my-epic`"
    )
    successor_line = (
        "After reconciling, continue the pipeline with: "
        "`/feature-forge:forge-3-specs widget`"
    )
    assert reconcile_line in block
    assert successor_line in block
    # The reconcile is the FIRST deferred action; the ordinary production
    # successor stays subordinate to it.
    assert block.index(reconcile_line) < block.index(successor_line)
    # …and the successor is named exactly once, never duplicated by the caller's
    # own deferred line.
    assert block.count("/feature-forge:forge-3-specs widget") == 1
    assert block.splitlines()[-1] == SENTINEL


def test_a_resolved_exit_still_fences_the_blocking_reconcile(tmp_path: Path) -> None:
    """The pre-item-011 reconcile-first precedence survives once verify resolves."""
    state = _state_with_requests([_request(kind="move-boundary", blocks=True)])
    root = _project(tmp_path, config={}, state=state)
    payload = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")
    d, block = payload["directives"], payload["nextSteps"]
    assert d["primaryCommand"] == "/feature-forge:forge-0-epic my-epic"
    assert _fenced_commands(block) == ["/feature-forge:forge-0-epic my-epic"]
    assert d["deferredCommand"] is None


def test_a_nonblocking_reminder_still_defers_to_verification(tmp_path: Path) -> None:
    state = _state_with_requests(
        [_request(kind="add-feature", blocks=False)], verified=False
    )
    root = _project(tmp_path, config={}, state=state)
    payload = _exit(root, "--feature", "widget", "--stage", "forge-2-tech")
    d, block = payload["directives"], payload["nextSteps"]
    assert d["epicReconcile"]["reminder"] is True
    assert _fenced_commands(block) == ["/feature-forge:forge-verify widget"]
    assert "You also flagged 1 epic change to reconcile when convenient" in block
    assert "After verification passes, continue with: " \
           "`/feature-forge:forge-3-specs widget`" in block


# --- the sentinel invariant survives every shape --------------------------- #


@pytest.mark.parametrize("verified", [True, False])
@pytest.mark.parametrize("host", ["claude", "pi", "generic"])
@pytest.mark.parametrize("requests", [
    [],
    [_request(blocks=True)],
    [_request(blocks=False)],
], ids=["none", "blocking", "reminder"])
def test_the_sentinel_is_always_the_final_line(
    tmp_path: Path, verified: bool, host: str, requests: list[dict]
) -> None:
    state = _state_with_requests(requests, verified=verified)
    root = _project(tmp_path, config={}, state=state)
    block = _exit(root, "--feature", "widget", "--stage", "forge-2-tech",
                  "--host", host)["nextSteps"]
    assert block.splitlines()[-1] == SENTINEL
    assert block.count(SENTINEL) == 1
    assert block.startswith("**Next steps**")


def test_next_steps_block_matches_the_00_section_5_signature() -> None:
    """The 00 §5 target signature, positionally and by default."""
    import inspect

    session = _load_session()
    sig = inspect.signature(session._next_steps_block)
    assert list(sig.parameters) == [
        "primary_command", "host", "reconcile", "deferred_command", "outcome_text",
    ]
    assert sig.parameters["reconcile"].default is None
    assert sig.parameters["deferred_command"].default is None
    assert sig.parameters["outcome_text"].default is None
    # Rule 1 and rule 6 hold for every combination of the optional arguments,
    # including the outcome_text items 013-015 will supply.
    for reconcile in (None, {"required": True, "command": "/feature-forge:forge-0-epic e",
                             "count": 1, "deferred": "/feature-forge:forge-3-specs w"}):
        for deferred in (None, "/feature-forge:forge-3-specs w"):
            for text in (None, "The loop stopped with 2 items pending."):
                block = session._next_steps_block(
                    "/feature-forge:forge-verify w", "claude", reconcile, deferred, text
                )
                assert block.startswith("**Next steps**")
                assert block.splitlines()[-1] == SENTINEL
                if text:
                    assert text in block


# --------------------------------------------------------------------------- #
# 07 §3.3 — direct verify/fix rejoin routing (02 §6, issue #176)
# --------------------------------------------------------------------------- #

#: The served stage every route test below diverts from, and the artifact version
#: its state records. Chosen mid-pipeline so both a real successor and a real
#: predecessor exist.
SERVED = "forge-1-prd"
SERVED_VERSION = 3
SUCCESSOR_COMMAND = "/feature-forge:forge-2-tech widget"

#: 02 §6.1/§6.2 as a literal table, spelled out here rather than imported: this is
#: the CLI's black-box contract, so a typo in the script's own routing table must
#: fail here instead of being echoed back. `_BRANCH_ROUTE_KIND` is compared against
#: the outcome domain structurally in
#: `test_the_branch_route_table_has_a_terminus_for_every_outcome`.
FIX_BRANCH = f"/feature-forge:forge-fix widget --served-stage {SERVED}"
VERIFY_BRANCH = f"/feature-forge:forge-verify widget --served-stage {SERVED}"
BRANCH_ROUTES = {
    ("forge-verify", "passed"): SUCCESSOR_COMMAND,
    ("forge-verify", "findings"): FIX_BRANCH,
    ("forge-verify", "skipped"): SUCCESSOR_COMMAND,
    ("forge-verify", "failed"): VERIFY_BRANCH,
    ("forge-fix", "no-findings"): VERIFY_BRANCH,   # verification still owed
    ("forge-fix", "decisions"): FIX_BRANCH,
    ("forge-fix", "failed"): FIX_BRANCH,
    ("forge-fix", "applied"): VERIFY_BRANCH,
    ("forge-fix", "reverified"): SUCCESSOR_COMMAND,
    ("forge-fix", "reverify-findings"): FIX_BRANCH,
    ("forge-fix", "deferred"): FIX_BRANCH,
}
#: The outcomes that are non-advancing regardless of state. `no-findings` is left
#: out on purpose: it is the one outcome whose terminus depends on live state
#: (02 §6.2), and it is covered by its own owed/resolved pair below.
NON_ADVANCING = [
    ("forge-verify", "findings"), ("forge-verify", "failed"),
    ("forge-fix", "decisions"), ("forge-fix", "failed"),
    ("forge-fix", "applied"), ("forge-fix", "reverify-findings"),
    ("forge-fix", "deferred"),
]


def _served_project(
    tmp_path: Path, entry: dict | None = None, completed: tuple[str, ...] = (SERVED,)
) -> Path:
    """A project whose `completed` production stages are done at `SERVED_VERSION`."""
    stages: dict = {
        stage: {"status": "complete", "version": SERVED_VERSION} for stage in completed
    }
    if entry is not None:
        stages["forge-verify-prd"] = entry
    root = _project(
        tmp_path, config={}, state={"pipelineStatus": "active", "stages": stages}
    )
    (root / "specs" / "widget" / "findings.md").write_text("# findings\n")
    return root


def _branch(cwd: Path, stage: str, outcome: str, *extra: str, owner: str = "direct"):
    """Run one branch exit against `SERVED` and return the whole payload."""
    return _exit(cwd, "--feature", "widget", "--stage", stage, "--outcome", outcome,
                 "--served-stage", SERVED, "--owner", owner, *extra)


def _state_verify(cwd: Path, *args: str) -> None:
    """Write real verification state through the real writer (03 §3)."""
    proc = subprocess.run(
        [sys.executable, str(HELPER), "state-verify", "--feature", "widget",
         "--stage", SERVED, *args],
        capture_output=True, text=True, cwd=str(cwd),
    )
    assert proc.returncode == 0, proc.stderr


def _report_findings(root: Path) -> None:
    _state_verify(root, "--status", "findings-reported", "--findings-file",
                  "findings.md", "--findings-count", "2",
                  "--verified-stage-version", str(SERVED_VERSION))


@pytest.mark.parametrize(
    "stage,outcome", sorted(BRANCH_ROUTES), ids=lambda v: v if isinstance(v, str) else v
)
def test_every_branch_outcome_produces_its_exact_02_section_6_route(
    tmp_path: Path, stage: str, outcome: str
) -> None:
    """All four verify and all seven fix outcomes route exactly as 02 §6 tabulates."""
    root = _served_project(tmp_path)
    d = _branch(root, stage, outcome)["directives"]
    assert d["primaryCommand"] == BRANCH_ROUTES[(stage, outcome)]


@pytest.mark.parametrize(
    "stage,outcome", sorted(BRANCH_ROUTES), ids=lambda v: v if isinstance(v, str) else v
)
def test_every_direct_branch_exit_exposes_the_02_section_6_directives(
    tmp_path: Path, stage: str, outcome: str
) -> None:
    """§6's five keys plus `verifyStage`, so a tool can tell rejoin/recovery/defer apart."""
    root = _served_project(tmp_path)
    d = _branch(root, stage, outcome)["directives"]
    for key in ("servedStage", "verifyStage", "outcome", "nextStage", "primaryCommand",
                "terminalOwnedBy"):
        assert key in d, key
    assert d["servedStage"] == SERVED
    assert d["outcome"] == outcome
    assert d["terminalOwnedBy"] == "self"
    # `nextStage` stays the next PRODUCTION stage in pipeline order (00 §4) — routing
    # introspection, never a promotion over `primaryCommand`.
    assert d["nextStage"] == "forge-2-tech"


@pytest.mark.parametrize("served", PRODUCTION_STAGES, ids=PRODUCTION_STAGES)
@pytest.mark.parametrize("stage,outcome", NON_ADVANCING,
                         ids=[f"{s}-{o}" for s, o in NON_ADVANCING])
def test_every_branch_command_carries_the_resolved_served_stage_forward(
    tmp_path: Path, served: str, stage: str, outcome: str
) -> None:
    """The whole point of #176: a diversion never loses the stage it served."""
    root = _served_project(tmp_path)
    d = _exit(root, "--feature", "widget", "--stage", stage, "--outcome", outcome,
              "--served-stage", served, "--owner", "direct")["directives"]
    assert d["primaryCommand"].endswith(f" --served-stage {served}")
    assert d["servedStage"] == served


@pytest.mark.parametrize("served", PRODUCTION_STAGES, ids=PRODUCTION_STAGES)
def test_fix_applied_always_routes_to_verify_and_never_to_production(
    tmp_path: Path, served: str
) -> None:
    """`applied` is not `reverified`: re-verification is mandatory (02 §6.2)."""
    root = _served_project(tmp_path)
    d = _exit(root, "--feature", "widget", "--stage", "forge-fix", "--outcome",
              "applied", "--served-stage", served, "--owner", "direct")["directives"]
    assert d["primaryCommand"] == f"/feature-forge:forge-verify widget --served-stage {served}"
    for production in PRODUCTION_STAGES:
        assert f"/feature-forge:{production} " not in d["primaryCommand"]


@pytest.mark.parametrize(
    "stage,outcome",
    [("forge-fix", o) for o in ("decisions", "failed", "deferred", "reverify-findings")],
    ids=["decisions", "failed", "deferred", "reverify-findings"],
)
def test_unresolved_fix_outcomes_never_advance_to_a_production_stage(
    tmp_path: Path, stage: str, outcome: str
) -> None:
    """REQ-ROUTE-06: unresolved work stops the thread; it does not hand it downstream."""
    payload = _branch(_served_project(tmp_path), stage, outcome)
    d, block = payload["directives"], payload["nextSteps"]
    assert d["primaryCommand"] == FIX_BRANCH
    assert _fenced_commands(block) == [FIX_BRANCH]
    # The successor may appear only as unfenced, conditional prose.
    assert SUCCESSOR_COMMAND not in _fenced_commands(block)
    assert d["deferredCommand"] == SUCCESSOR_COMMAND


def test_deferred_states_that_findings_remain_unresolved(tmp_path: Path) -> None:
    """02 §6.2 requires `deferred` to say so explicitly, not merely stop."""
    block = _branch(_served_project(tmp_path), "forge-fix", "deferred")["nextSteps"]
    assert "explicitly deferred" in block
    assert "UNRESOLVED" in block


def test_verify_failed_carries_actionable_intervention_text(tmp_path: Path) -> None:
    """02 §6.1: `failed` names the intervention and never advances."""
    payload = _branch(_served_project(tmp_path), "forge-verify", "failed")
    assert payload["directives"]["primaryCommand"] == VERIFY_BRANCH
    assert "could not run to a result" in payload["nextSteps"]
    assert _fenced_commands(payload["nextSteps"]) == [VERIFY_BRANCH]


def test_no_findings_re_verifies_while_verification_is_still_owed(tmp_path: Path):
    """02 §6.2: absence of applicable findings is never assumed to equal a pass."""
    root = _served_project(tmp_path)   # no verify entry at all → owed
    payload = _branch(root, "forge-fix", "no-findings")
    assert payload["directives"]["primaryCommand"] == VERIFY_BRANCH
    assert "is not a pass" in payload["nextSteps"]


def test_no_findings_rejoins_once_verification_is_already_resolved(tmp_path: Path):
    root = _served_project(
        tmp_path, {"status": "passed", "verifiedStageVersion": SERVED_VERSION}
    )
    d = _branch(root, "forge-fix", "no-findings")["directives"]
    assert d["primaryCommand"] == SUCCESSOR_COMMAND


# --- live successor derivation --------------------------------------------- #


def test_live_successor_uses_the_current_production_position(tmp_path: Path) -> None:
    """Not `served + 1`: a member already past tech/specs rejoins at backlog."""
    root = _served_project(
        tmp_path, completed=(SERVED, "forge-2-tech", "forge-3-specs")
    )
    d = _branch(root, "forge-verify", "passed")["directives"]
    assert d["nextStage"] == "forge-4-backlog"
    assert d["primaryCommand"] == "/feature-forge:forge-4-backlog widget"


def test_a_completed_stage_6_routes_to_completion_not_a_nonexistent_stage_7(
    tmp_path: Path,
) -> None:
    root = _served_project(tmp_path)
    d = _exit(root, "--feature", "widget", "--stage", "forge-verify", "--outcome",
              "passed", "--served-stage", "forge-6-docs", "--owner",
              "direct")["directives"]
    assert d["nextStage"] is None
    assert d["primaryCommand"] == "/feature-forge:forge widget"
    assert "forge-7" not in json.dumps(d)


@pytest.mark.parametrize("host,expected", [
    ("claude", "/feature-forge:forge-fix widget --served-stage forge-1-prd"),
    ("pi", "/skill:forge-fix widget --served-stage forge-1-prd"),
    ("generic", "/feature-forge:forge-fix widget --served-stage forge-1-prd"),
])
def test_branch_commands_are_translated_at_render_time(
    tmp_path: Path, host: str, expected: str
) -> None:
    """02 §6: the tables are canonical, pre-`_host_command` forms."""
    payload = _branch(_served_project(tmp_path), "forge-verify", "findings",
                      "--host", host)
    assert payload["directives"]["primaryCommand"] == expected
    assert _fenced_commands(payload["nextSteps"]) == [expected]


# --- complete paths -------------------------------------------------------- #


def test_the_findings_applied_passed_path_rejoins_production(tmp_path: Path) -> None:
    """07 §3.3: findings → applied → passed, driven by the real state writer."""
    root = _served_project(tmp_path)

    _report_findings(root)
    assert _branch(root, "forge-verify", "findings")["directives"][
        "primaryCommand"] == FIX_BRANCH

    _state_verify(root, "--status", "findings-applied")
    assert _branch(root, "forge-fix", "applied")["directives"][
        "primaryCommand"] == VERIFY_BRANCH

    _state_verify(root, "--status", "passed",
                  "--verified-stage-version", str(SERVED_VERSION))
    d = _branch(root, "forge-verify", "passed")["directives"]
    assert d["primaryCommand"] == SUCCESSOR_COMMAND
    assert d["verifyState"] == "fresh"


def test_the_findings_applied_findings_path_stays_in_recovery(tmp_path: Path) -> None:
    """07 §3.3: findings → applied → findings never reaches a production stage."""
    root = _served_project(tmp_path)

    _report_findings(root)
    assert _branch(root, "forge-verify", "findings")["directives"][
        "primaryCommand"] == FIX_BRANCH

    _state_verify(root, "--status", "findings-applied")
    assert _branch(root, "forge-fix", "applied")["directives"][
        "primaryCommand"] == VERIFY_BRANCH

    _report_findings(root)   # the re-verification found more
    for stage, outcome, expected in (
        ("forge-verify", "findings", FIX_BRANCH),
        ("forge-fix", "reverify-findings", FIX_BRANCH),
    ):
        payload = _branch(root, stage, outcome)
        assert payload["directives"]["primaryCommand"] == expected
        assert _fenced_commands(payload["nextSteps"]) == [expected]


def test_a_fresh_exit_after_findings_applied_does_not_promote_the_successor(
    tmp_path: Path,
) -> None:
    """`findings-applied` CLEARS freshness, so the production successor stays demoted."""
    root = _served_project(tmp_path)
    _report_findings(root)
    _state_verify(root, "--status", "findings-applied")

    # A FRESH production stage-exit, taken before re-verification runs.
    payload = _exit(root, "--feature", "widget", "--stage", SERVED)
    d, block = payload["directives"], payload["nextSteps"]
    assert d["verifyState"] == "stale"
    assert d["primaryCommand"] == "/feature-forge:forge-verify widget"
    assert d["deferredCommand"] == SUCCESSOR_COMMAND
    assert _fenced_commands(block) == ["/feature-forge:forge-verify widget"]
    assert SUCCESSOR_COMMAND not in _fenced_commands(block)


def test_a_nested_chain_emits_no_sentinel_and_the_final_direct_call_emits_one(
    tmp_path: Path,
) -> None:
    """REQ-EXIT-04: the outermost authoring stage is the sole terminal owner."""
    root = _served_project(tmp_path)

    def human(*args: str) -> str:
        proc = subprocess.run(
            [sys.executable, str(HELPER), "stage-exit", "--feature", "widget", *args],
            capture_output=True, text=True, cwd=str(root),
        )
        assert proc.returncode == 0, proc.stderr
        return proc.stdout

    _report_findings(root)
    steps = [
        ("forge-verify", "findings"),
        ("forge-fix", "applied"),
        ("forge-verify", "passed"),
    ]
    for i, (stage, outcome) in enumerate(steps):
        out = human("--stage", stage, "--outcome", outcome,
                    "--served-stage", SERVED, "--owner", "nested")
        assert SENTINEL not in out, f"nested step {i} ({stage}/{outcome}) leaked a block"
        assert "NEXT-STEPS" not in out
        payload = _branch(root, stage, outcome, owner="nested")
        assert payload["nextSteps"] is None and payload["sentinel"] is None
        # Routing directives survive the whole way down.
        assert payload["directives"]["servedStage"] == SERVED
        assert payload["directives"]["terminalOwnedBy"] == "outer"
        if i == 0:
            _state_verify(root, "--status", "findings-applied")
        elif i == 1:
            _state_verify(root, "--status", "passed",
                          "--verified-stage-version", str(SERVED_VERSION))

    # The outer authoring stage now owns exactly one terminal block.
    outer = human("--stage", SERVED)
    assert outer.count(SENTINEL) == 1
    assert outer.rstrip().splitlines()[-1] == SENTINEL


def test_the_branch_route_table_has_a_terminus_for_every_outcome() -> None:
    """REQ-ROUTE-05/06: no fall-through — every outcome is routed explicitly."""
    session = _load_session()
    table = session._BRANCH_ROUTE_KIND
    assert set(table) == set(BRANCH_STAGES)
    for stage in BRANCH_STAGES:
        assert set(table[stage]) == set(EXIT_OUTCOMES[stage]), stage
        assert set(session._BRANCH_OUTCOME_TEXT[stage]) == set(EXIT_OUTCOMES[stage])
    # The literal table above is the black-box contract; this proves it covers the
    # same domain the script routes, so neither can grow an outcome the other lacks.
    assert set(BRANCH_ROUTES) == {
        (stage, outcome) for stage in BRANCH_STAGES for outcome in EXIT_OUTCOMES[stage]
    }


# --------------------------------------------------------------------------- #
# 07 §3.6 — documentation live-state routing (02 §8)
# --------------------------------------------------------------------------- #

DOCS_EPIC = "my-epic"
#: The epic dashboard command every non-member docs route lands on, and the recovery
#: command every docs routing failure must name.
DASHBOARD = f"/feature-forge:forge-0-epic {DOCS_EPIC}"


def _member(name: str, depends_on: tuple[str, ...] = ()) -> dict:
    return {
        "name": name,
        "charter": f"Charter for {name}, long enough to satisfy the manifest schema.",
        "dependsOn": list(depends_on),
        "exposes": [],
        "consumes": [],
    }


def _member_state(complete: bool) -> dict | None:
    """Real member state: every production stage complete, verification passed."""
    if not complete:
        return None
    return {
        "pipelineStatus": "active",
        "epic": DOCS_EPIC,
        "stages": {
            **{
                stage: {"status": "complete", "version": 1}
                for stage in PRODUCTION_STAGES[1:]
            },
            "forge-verify-impl": {"status": "passed", "verifiedStageVersion": 1},
        },
    }


def _docs_epic_project(
    tmp_path: Path, members: list[dict], complete: tuple[str, ...] = ()
) -> Path:
    """A REAL epic: schema-valid manifest plus real member state on disk.

    07 §3.6 forbids mocking `render-status` for the routing cases — the live helper
    must actually run over this tree, so the manifest carries every required key and
    each complete member gets the state that makes `is_complete_for_orchestration`
    true (a completed `forge-5-loop` plus a passing `forge-verify-impl`).
    """
    root = tmp_path / "proj"
    epic_dir = root / "specs" / DOCS_EPIC
    epic_dir.mkdir(parents=True)
    (root / "forge.config.json").write_text("{}")
    (epic_dir / "EPIC.md").write_text("# epic\n")
    (epic_dir / "epic-manifest.json").write_text(json.dumps({
        "schemaVersion": 1,
        "revision": 1,
        "epic": DOCS_EPIC,
        "description": "A real epic used to exercise live documentation routing.",
        "status": "active",
        "narrativeDoc": "EPIC.md",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
        "features": members,
    }))
    for entry in members:
        name = entry["name"]
        member_dir = epic_dir / name
        member_dir.mkdir()
        state = _member_state(name in complete)
        if state is not None:
            (member_dir / ".pipeline-state.json").write_text(json.dumps(state))
            (member_dir / "PRD.md").write_text("# prd\n")
    subprocess.run(["git", "init", "-qb", "main"], cwd=root, check=True)
    return root


def _docs(cwd: Path, feature: str, outcome: str = "complete", *extra: str) -> dict:
    return _exit(cwd, "--feature", feature, "--stage", "forge-6-docs",
                 "--outcome", outcome, *extra)


def test_docs_requires_its_own_outcome_and_rejects_any_other(tmp_path: Path) -> None:
    """02 §8: `forge-6-docs` always uses stage-exit and takes `complete` or `blocked`."""
    root = _project(tmp_path, config={})
    err = _rejected(root, "--feature", "widget", "--stage", "forge-6-docs")
    assert "forge-6-docs requires --outcome" in err
    for value in ("partial", "passed", "applied", "needs-human", "", "COMPLETE"):
        err = _rejected(root, "--feature", "widget", "--stage", "forge-6-docs",
                        "--outcome", value)
        assert f"--outcome {value!r} is not valid for forge-6-docs" in err


def test_docs_epic_member_routes_to_the_live_next_member_command(tmp_path: Path) -> None:
    """An actionable next member routes to that member's LIVE render-status command."""
    root = _docs_epic_project(
        tmp_path, [_member("alpha"), _member("beta", ("alpha",))], complete=("alpha",)
    )
    # Ground truth from the real helper, not a hand-written expectation.
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "epic-manifest.py"),
         "render-status", DOCS_EPIC, "--specs-dir", str(root / "specs"), "--json"],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr
    live = json.loads(proc.stdout)
    assert live["actionable"] == ["beta"] and live["nextCommand"]

    payload = _docs(root, "alpha", "complete", "--epic", DOCS_EPIC)
    d = payload["directives"]
    assert d["primaryCommand"] == live["nextCommand"] == "/feature-forge:forge-1-prd beta"
    assert d["deferredCommand"] is None
    assert f"```\n{live['nextCommand']}\n```" in payload["nextSteps"]
    assert payload["nextSteps"].rstrip().splitlines()[-1] == SENTINEL


def test_docs_routes_from_live_state_not_a_stale_snapshot(tmp_path: Path) -> None:
    """The status read happens at EXIT time: advancing a member changes the route."""
    root = _docs_epic_project(
        tmp_path, [_member("alpha"), _member("beta", ("alpha",))], complete=("alpha",)
    )
    assert _docs(root, "alpha", "complete", "--epic", DOCS_EPIC)[
        "directives"]["primaryCommand"] == "/feature-forge:forge-1-prd beta"
    # Beta really progresses on disk; the very next exit must follow it.
    beta = root / "specs" / DOCS_EPIC / "beta"
    (beta / ".pipeline-state.json").write_text(json.dumps({
        "pipelineStatus": "active", "epic": DOCS_EPIC,
        "stages": {"forge-1-prd": {"status": "complete", "version": 1}},
    }))
    (beta / "PRD.md").write_text("# prd\n")
    assert _docs(root, "alpha", "complete", "--epic", DOCS_EPIC)[
        "directives"]["primaryCommand"] == "/feature-forge:forge-2-tech beta"


def test_docs_with_every_member_complete_routes_to_the_epic_dashboard(tmp_path: Path):
    """All members complete → the dashboard completion view, same epic command."""
    root = _docs_epic_project(
        tmp_path,
        [_member("alpha"), _member("beta", ("alpha",))],
        complete=("alpha", "beta"),
    )
    payload = _docs(root, "beta", "complete", "--epic", DOCS_EPIC)
    d = payload["directives"]
    assert d["primaryCommand"] == DASHBOARD
    assert f"```\n{DASHBOARD}\n```" in payload["nextSteps"]
    assert "every member of epic my-epic is now complete (2/2)" in payload["nextSteps"]


def test_docs_with_no_actionable_member_routes_to_the_same_epic_command(tmp_path: Path):
    """No actionable member and all-complete share one route (02 §8)."""
    root = _docs_epic_project(tmp_path, [_member("alpha")], complete=("alpha",))
    proc = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "epic-manifest.py"),
         "render-status", DOCS_EPIC, "--specs-dir", str(root / "specs"), "--json"],
        capture_output=True, text=True,
    )
    live = json.loads(proc.stdout)
    assert live["actionable"] == [] and live["nextCommand"] is None
    d = _docs(root, "alpha", "complete", "--epic", DOCS_EPIC)["directives"]
    assert d["primaryCommand"] == DASHBOARD


def test_docs_blocked_in_an_epic_recovers_and_never_claims_completion(tmp_path: Path):
    """A blocked docs outcome routes to dashboard recovery, never to completion."""
    root = _docs_epic_project(
        tmp_path, [_member("alpha"), _member("beta", ("alpha",))], complete=("alpha",)
    )
    payload = _docs(root, "alpha", "blocked", "--epic", DOCS_EPIC)
    d = payload["directives"]
    assert d["outcome"] == "blocked"
    assert d["primaryCommand"] == DASHBOARD
    block = payload["nextSteps"]
    assert "could not be completed" in block
    # It must not advance to the actionable member, and must not claim completion.
    assert "/feature-forge:forge-1-prd beta" not in block
    assert "is now complete" not in block and "with it the pipeline" not in block


def test_docs_standalone_complete_fences_only_the_navigator(tmp_path: Path) -> None:
    """02 §8: `/feature-forge:forge FEATURE` is THE completion action; new-feature
    guidance is secondary text and is never fenced."""
    root = _project(tmp_path, config={})
    payload = _docs(root, "widget", "complete")
    block = payload["nextSteps"]
    assert payload["directives"]["primaryCommand"] == "/feature-forge:forge widget"
    assert block.count("```") == 2, "exactly one fence"
    fenced = block.split("```")[1].strip()
    assert fenced == "/feature-forge:forge widget"
    # The new-feature/new-epic mentions exist, outside the fence.
    for secondary in ("/feature-forge:forge-1-prd <new-feature>",
                      "/feature-forge:forge-0-epic <new-epic>"):
        assert secondary in block
        assert secondary not in fenced


def test_docs_standalone_blocked_routes_to_navigator_recovery(tmp_path: Path) -> None:
    root = _project(tmp_path, config={})
    payload = _docs(root, "widget", "blocked")
    assert payload["directives"]["primaryCommand"] == "/feature-forge:forge widget"
    assert "the pipeline is NOT complete" in payload["nextSteps"]
    assert "<new-feature>" not in payload["nextSteps"]


def test_docs_routes_on_the_state_epic_back_pointer_without_an_explicit_flag(
    tmp_path: Path,
) -> None:
    """A member's own state names its epic, so `--epic` is a confirmation, not a key."""
    root = _docs_epic_project(
        tmp_path, [_member("alpha"), _member("beta", ("alpha",))], complete=("alpha",)
    )
    d = _docs(root, "alpha", "complete")["directives"]
    assert d["primaryCommand"] == "/feature-forge:forge-1-prd beta"


def test_docs_pi_translates_both_the_route_and_the_secondary_mentions(
    tmp_path: Path,
) -> None:
    """REQ-EXIT-05: nothing in a Pi block may keep the `/feature-forge:` surface."""
    epic_root = _docs_epic_project(
        tmp_path, [_member("alpha"), _member("beta", ("alpha",))], complete=("alpha",)
    )
    payload = _docs(epic_root, "alpha", "complete", "--epic", DOCS_EPIC, "--host", "pi")
    assert payload["directives"]["primaryCommand"] == "/skill:forge-1-prd beta"
    assert "/feature-forge:" not in payload["nextSteps"]

    standalone = _project(tmp_path / "flat", config={})
    block = _docs(standalone, "widget", "complete", "--host", "pi")["nextSteps"]
    assert "/skill:forge-1-prd <new-feature>" in block
    assert "/feature-forge:" not in block


def test_docs_routing_is_byte_deterministic(tmp_path: Path) -> None:
    """02 §10: identical state, identical output — including the live epic read."""
    root = _docs_epic_project(
        tmp_path, [_member("alpha"), _member("beta", ("alpha",))], complete=("alpha",)
    )
    first = _docs(root, "alpha", "complete", "--epic", DOCS_EPIC)
    second = _docs(root, "alpha", "complete", "--epic", DOCS_EPIC)
    assert first == second


# --- routing failures: exit 2, no sentinel, no guessed member --------------- #


def _docs_rejected(root: Path, feature: str = "alpha") -> str:
    err = _rejected(root, "--feature", feature, "--stage", "forge-6-docs",
                    "--outcome", "complete", "--epic", DOCS_EPIC)
    assert DOCS_EPIC in err, "the failure must name the epic"
    assert DASHBOARD in err, "the failure must name the recovery command"
    # No guessed member route may appear anywhere in the failure output.
    assert "forge-1-prd beta" not in err and "forge-6-docs beta" not in err
    return err


def test_docs_invalid_graph_is_an_actionable_routing_failure(tmp_path: Path) -> None:
    """An invalid graph exits 1 from the real helper with findings on stdout only."""
    root = _docs_epic_project(
        tmp_path, [_member("alpha"), _member("beta", ("alpha",))], complete=("alpha",)
    )
    manifest = root / "specs" / DOCS_EPIC / "epic-manifest.json"
    data = json.loads(manifest.read_text())
    data["features"][1]["dependsOn"] = ["ghost"]
    manifest.write_text(json.dumps(data))
    err = _docs_rejected(root)
    assert "render-status exited 1" in err
    assert "unknown feature 'ghost'" in err, "the first finding must be named"


def test_docs_render_status_nonzero_exit_is_a_routing_failure(tmp_path: Path) -> None:
    """A missing manifest makes the real helper exit 2; the router does not guess."""
    root = _docs_epic_project(
        tmp_path, [_member("alpha"), _member("beta", ("alpha",))], complete=("alpha",)
    )
    (root / "specs" / DOCS_EPIC / "epic-manifest.json").unlink()
    err = _docs_rejected(root)
    assert "render-status exited 2" in err


# The stub cases below still execute a REAL sibling helper through the REAL
# resolution path — only the helper's own body is replaced, so the contract under
# test (sibling resolution, `sys.executable`, exit/JSON handling) is unmocked.

def _stub_bundle(tmp_path: Path, body: str | None) -> Path:
    """Copy `forge-session.py` into a fresh `scripts/` dir beside a stub helper.

    This is how the sibling-resolution contract is exercised honestly: the copied
    script must find (or fail to find) `epic-manifest.py` next to ITSELF, not next
    to the repository it came from. Pass `body=None` to omit the sibling entirely.
    """
    bundle = tmp_path / "bundle" / "scripts"
    bundle.mkdir(parents=True)
    (bundle / "forge-session.py").write_text(HELPER.read_text())
    if body is not None:
        (bundle / "epic-manifest.py").write_text(body)
    return bundle / "forge-session.py"


def _stub_rejected(tmp_path: Path, body: str | None) -> str:
    root = _docs_epic_project(
        tmp_path, [_member("alpha"), _member("beta", ("alpha",))], complete=("alpha",)
    )
    proc = subprocess.run(
        [sys.executable, str(_stub_bundle(tmp_path, body)), "stage-exit", "--json",
         "--feature", "alpha", "--stage", "forge-6-docs", "--outcome", "complete",
         "--epic", DOCS_EPIC],
        capture_output=True, text=True, cwd=str(root),
    )
    assert proc.returncode == 2, (proc.returncode, proc.stdout, proc.stderr)
    assert proc.stdout == ""
    assert SENTINEL not in proc.stdout + proc.stderr
    assert "Traceback" not in proc.stderr, proc.stderr
    assert DOCS_EPIC in proc.stderr and DASHBOARD in proc.stderr
    assert "forge-1-prd beta" not in proc.stderr
    return proc.stderr


def test_docs_missing_sibling_epic_manifest_is_a_routing_failure(tmp_path: Path) -> None:
    err = _stub_rejected(tmp_path, None)
    assert "sibling epic-manifest.py is missing" in err
    assert str(tmp_path / "bundle" / "scripts" / "epic-manifest.py") in err


def test_docs_malformed_json_is_a_routing_failure(tmp_path: Path) -> None:
    err = _stub_rejected(tmp_path, "print('{not json')\n")
    assert "did not emit parseable JSON" in err


@pytest.mark.parametrize(
    "omit", ["epic", "features", "actionable", "rollup", "nextCommand"]
)
def test_docs_a_missing_required_field_is_a_routing_failure(
    tmp_path: Path, omit: str
) -> None:
    """`RenderStatus` is TOTAL, so an absent key is a broken contract, not 'none'."""
    body = (
        "import json\n"
        "payload = {'epic': 'my-epic', 'features': [], 'actionable': ['beta'],\n"
        "           'rollup': {'complete': 1, 'total': 2},\n"
        "           'nextCommand': '/feature-forge:forge-1-prd beta'}\n"
        f"payload.pop({omit!r})\n"
        "print(json.dumps(payload))\n"
    )
    err = _stub_rejected(tmp_path, body)
    assert f"omitted required field(s): {omit}" in err


@pytest.mark.parametrize("bad_rollup", ["null", '{"complete": 1}', '{"complete": true, "total": 2}'])
def test_docs_a_malformed_rollup_is_a_routing_failure(
    tmp_path: Path, bad_rollup: str
) -> None:
    body = (
        "print('''{\"epic\": \"my-epic\", \"features\": [], \"actionable\": [],\n"
        f"  \"rollup\": {bad_rollup}, \"nextCommand\": null}}''')\n"
    )
    assert "malformed rollup" in _stub_rejected(tmp_path, body)


def test_docs_a_non_object_payload_is_a_routing_failure(tmp_path: Path) -> None:
    assert "non-object JSON payload" in _stub_rejected(tmp_path, "print('[]')\n")


def test_docs_a_timeout_at_the_ten_second_bound_is_a_routing_failure(
    tmp_path: Path, monkeypatch
) -> None:
    """07 §3.6's narrowly injected failure — allowed only alongside the real cases
    above, and asserting the BOUND that is actually passed to `subprocess.run`."""
    session = _load_session()
    assert session._RENDER_STATUS_TIMEOUT == 10, "02 §8 fixes the bound at 10 seconds"
    seen: dict = {}

    def fake_run(cmd, **kwargs):
        seen.update(kwargs)
        seen["cmd"] = cmd
        raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])

    monkeypatch.setattr(session.subprocess, "run", fake_run)
    with pytest.raises(session.UsageError) as excinfo:
        session._render_status(tmp_path, DOCS_EPIC)
    message = str(excinfo.value)
    assert "did not finish within 10 seconds" in message
    assert DOCS_EPIC in message and DASHBOARD in message
    assert seen["timeout"] == 10 and seen["check"] is False
    # The invocation contract itself: sys.executable, never a bare python3.
    assert seen["cmd"][0] == sys.executable
    assert seen["cmd"][1].endswith("epic-manifest.py")
    assert seen["cmd"][2:4] == ["render-status", DOCS_EPIC]
    assert "--json" in seen["cmd"]


def test_docs_a_spawn_failure_is_a_routing_failure(tmp_path: Path, monkeypatch) -> None:
    session = _load_session()

    def fake_run(cmd, **kwargs):
        raise OSError("Exec format error")

    monkeypatch.setattr(session.subprocess, "run", fake_run)
    with pytest.raises(session.UsageError) as excinfo:
        session._render_status(tmp_path, DOCS_EPIC)
    message = str(excinfo.value)
    assert "could not be started" in message and "Exec format error" in message
    assert DOCS_EPIC in message and DASHBOARD in message


def test_docs_resolves_the_helper_beside_itself_and_never_a_bare_python3() -> None:
    """The invocation contract 02 §8 makes normative, asserted on the source."""
    source = HELPER.read_text()
    body = source[source.index("def _render_status(specs_dir"):]
    body = body[: body.index("\n_DOCS_OUTCOME_TEXT")]
    # Executable lines only: the docstring legitimately explains why a bare `python3`
    # is wrong, and a prose mention must not satisfy (or fail) a behavioral guard.
    code = body[body.index('"""', body.index('"""') + 3) + 3:]
    assert 'Path(__file__).resolve().parent / "epic-manifest.py"' in code
    assert "sys.executable" in code
    assert "python3" not in code, "a bare python3 may be absent or a different runtime"
    assert "<bundle-root>" not in code
    assert "_RENDER_STATUS_TIMEOUT" in code


def test_docs_never_reimplements_the_epic_dependency_derivation() -> None:
    """tech-spec §3.5: the router consumes render-status; it does not re-derive."""
    source = HELPER.read_text()
    for forbidden in ("unmet_deps", "parallelEligible", "is_complete_for_orchestration"):
        assert forbidden not in source, forbidden


# --------------------------------------------------------------------------- #
# 07 §3.5 — loop outcome routing (02 §7)
# --------------------------------------------------------------------------- #

LOOP_OUTCOMES = EXIT_OUTCOMES["forge-5-loop"]
NON_COMPLETE_LOOP_OUTCOMES = tuple(o for o in LOOP_OUTCOMES if o != "complete")
#: The exact primary command each non-complete outcome must fence (02 §7).
LOOP_RESUME = "/feature-forge:forge-5-loop widget"
LOOP_RECOVERY = "/feature-forge:forge widget"
#: The one production successor no non-complete outcome may name, anywhere.
LOOP_DOCS = "/feature-forge:forge-6-docs widget"

#: A loop-complete feature whose implementation verification is already settled, so
#: verify-first ordering has nothing to put in front of the handoff. Tests whose
#: subject is the HANDOFF seed this; tests whose subject is verify-first ordering
#: deliberately do not.
_LOOP_VERIFIED = _state_with_verify(
    "forge-5-loop", "forge-verify-impl", {"status": "passed", "verifiedStageVersion": 2}
)


def _loop(cwd: Path, outcome: str, feature: str = "widget", *extra: str) -> dict:
    return _exit(cwd, "--feature", feature, "--stage", "forge-5-loop",
                 "--outcome", outcome, *extra)


def test_loop_requires_its_own_outcome_and_rejects_any_other(tmp_path: Path) -> None:
    """A missing or foreign outcome exits 2 BEFORE any output (REQ-EXIT-03)."""
    root = _project(tmp_path, config={})
    err = _rejected(root, "--feature", "widget", "--stage", "forge-5-loop")
    assert "forge-5-loop requires --outcome" in err
    for value in sorted(LOOP_OUTCOMES):
        assert value in err, "the error must enumerate the accepted domain"
    for value in ("passed", "applied", "no-findings", "reverified", "", "COMPLETE",
                  "done", "success"):
        err = _rejected(root, "--feature", "widget", "--stage", "forge-5-loop",
                        "--outcome", value)
        assert f"--outcome {value!r} is not valid for forge-5-loop" in err


@pytest.mark.parametrize("outcome", LOOP_OUTCOMES, ids=LOOP_OUTCOMES)
def test_loop_accepts_exactly_the_five_loop_outcomes(tmp_path: Path, outcome: str):
    root = _project(tmp_path, config={})
    d = _loop(root, outcome)["directives"]
    assert d["outcome"] == outcome
    assert d["stage"] == "forge-5-loop"


@pytest.mark.parametrize("outcome", ["partial", "deferred"])
def test_loop_partial_and_deferred_fence_the_loop_resume(tmp_path: Path, outcome: str):
    """02 §7: state remains resumable, so the loop itself is the primary action."""
    root = _project(tmp_path, config={})
    payload = _loop(root, outcome)
    assert payload["directives"]["primaryCommand"] == LOOP_RESUME
    assert f"```\n{LOOP_RESUME}\n```" in payload["nextSteps"]
    assert payload["nextSteps"].count("```") == 2, "exactly one fenced command"


@pytest.mark.parametrize("outcome", ["blocked", "needs-human"])
def test_loop_blocked_and_needs_human_fence_the_navigator(tmp_path: Path, outcome: str):
    """02 §7: the navigator is the deterministic diagnostic/recovery action."""
    root = _project(tmp_path, config={})
    payload = _loop(root, outcome)
    assert payload["directives"]["primaryCommand"] == LOOP_RECOVERY
    assert f"```\n{LOOP_RECOVERY}\n```" in payload["nextSteps"]
    assert payload["nextSteps"].count("```") == 2


@pytest.mark.parametrize("outcome", NON_COMPLETE_LOOP_OUTCOMES,
                         ids=NON_COMPLETE_LOOP_OUTCOMES)
@pytest.mark.parametrize("config", [{}, {"autoVerify": True, "autoFix": True}],
                         ids=["auto-verify-off", "auto-verify-on"])
def test_no_non_complete_loop_outcome_claims_downstream_readiness(
    tmp_path: Path, outcome: str, config: dict
) -> None:
    """REQ-PROD-02: no directive and no rendered line may imply docs is ready.

    Every downstream signal is checked, not just the fenced command: `forge-6-docs`
    must not appear ANYWHERE in the payload, and the in-stage verify chain — which
    would assert the implementation is finished enough to audit — stays off even
    when `autoVerify` is on.
    """
    root = _project(tmp_path, config=config)
    payload = _loop(root, outcome, "widget", "--verify-capability", "interactive")
    d = payload["directives"]
    assert "forge-6-docs" not in json.dumps(payload)
    assert LOOP_DOCS not in payload["nextSteps"]
    assert d["nextStage"] is None
    assert d["nextCommand"] is None
    assert d["deferredCommand"] is None
    assert d["runInStageVerify"] is False
    assert d["autoVerifyDebtRecorded"] is False
    assert d["autoFixEligible"] is False
    assert d["verifyGate"] == "none"
    assert d["primaryCommand"] in (LOOP_RESUME, LOOP_RECOVERY)


@pytest.mark.parametrize("outcome", NON_COMPLETE_LOOP_OUTCOMES,
                         ids=NON_COMPLETE_LOOP_OUTCOMES)
def test_a_non_complete_loop_schedules_no_auto_verify_debt(
    tmp_path: Path, outcome: str
) -> None:
    """A loop still in flight has no finished implementation to owe a verify for."""
    root = _project(tmp_path, config={"autoVerify": True})
    state_path = root / "specs" / "widget" / ".pipeline-state.json"
    assert not state_path.exists()
    _loop(root, outcome)
    assert not state_path.exists(), "no auto-verify-pending marker may be written"


def test_a_complete_loop_still_schedules_auto_verify_debt(tmp_path: Path) -> None:
    """The negative control for the suppression above — `complete` still owes it."""
    root = _project(tmp_path, config={"autoVerify": True})
    d = _loop(root, "complete")["directives"]
    assert d["runInStageVerify"] is True
    assert d["autoVerifyDebtRecorded"] is True
    written = json.loads((root / "specs" / "widget" / ".pipeline-state.json").read_text())
    assert written["stages"]["forge-verify-impl"]["status"] == "auto-verify-pending"


def test_loop_complete_is_verify_first_and_docs_is_not_primary(tmp_path: Path) -> None:
    """REQ-EXIT-06: docs never leads while implementation verification is unresolved."""
    root = _project(tmp_path, config={})
    payload = _loop(root, "complete", "widget", "--verify-capability", "interactive")
    d = payload["directives"]
    assert d["primaryCommand"] == "/feature-forge:forge-verify widget"
    assert d["deferredCommand"] == LOOP_DOCS
    block = payload["nextSteps"]
    assert f"```\n/feature-forge:forge-verify widget\n```" in block
    assert f"```\n{LOOP_DOCS}\n```" not in block, "the successor is never fenced"
    assert block.count("```") == 2
    assert f"continue with: `{LOOP_DOCS}`" in block


@pytest.mark.parametrize(
    "entry",
    [{"status": "passed", "verifiedStageVersion": 2}, {"status": "skipped"}],
    ids=["passed", "explicitly-skipped"],
)
def test_loop_complete_advances_to_docs_once_verification_settles(
    tmp_path: Path, entry: dict
) -> None:
    """02 §7: docs becomes primary only after a pass or an explicit skip."""
    root = _project(
        tmp_path, config={},
        state=_state_with_verify("forge-5-loop", "forge-verify-impl", entry),
    )
    payload = _loop(root, "complete")
    assert payload["directives"]["primaryCommand"] == LOOP_DOCS
    assert payload["directives"]["deferredCommand"] is None
    assert f"```\n{LOOP_DOCS}\n```" in payload["nextSteps"]


@pytest.mark.parametrize("outcome", LOOP_OUTCOMES, ids=LOOP_OUTCOMES)
def test_loop_outcome_text_sits_inside_the_block_above_the_sentinel(
    tmp_path: Path, outcome: str
) -> None:
    """02 §7: explanatory text is rendered INSIDE NEXT-STEPS; nothing follows the
    sentinel, which stays the single final line."""
    root = _project(tmp_path, config={}, state=_LOOP_VERIFIED)
    block = _loop(root, outcome)["nextSteps"]
    lines = block.splitlines()
    assert lines[0] == "**Next steps**"
    # The outcome text is line 2 — above the numbered guidance and the fence.
    assert lines[1].startswith(("Every backlog item is done", "The loop"))
    assert "widget" in lines[1]
    assert block.count(SENTINEL) == 1
    assert lines[-1] == SENTINEL
    assert block.endswith(SENTINEL)


@pytest.mark.parametrize("outcome", NON_COMPLETE_LOOP_OUTCOMES,
                         ids=NON_COMPLETE_LOOP_OUTCOMES)
def test_a_non_complete_loop_outcome_states_nothing_downstream_is_ready(
    tmp_path: Path, outcome: str
) -> None:
    root = _project(tmp_path, config={})
    block = _loop(root, outcome)["nextSteps"]
    assert "nothing downstream is ready" in block.lower()


def test_loop_routing_is_byte_deterministic(tmp_path: Path) -> None:
    """02 §10: identical state and inputs produce identical output."""
    root = _project(tmp_path, config={}, state=_LOOP_VERIFIED)
    for outcome in LOOP_OUTCOMES:
        first = _loop(root, outcome)
        second = _loop(root, outcome)
        assert first == second, outcome


@pytest.mark.parametrize("outcome", LOOP_OUTCOMES, ids=LOOP_OUTCOMES)
def test_loop_routes_are_host_translated(tmp_path: Path, outcome: str) -> None:
    root = _project(tmp_path, config={}, state=_LOOP_VERIFIED)
    block = _loop(root, outcome, "widget", "--host", "pi")["nextSteps"]
    assert "/feature-forge:" not in block
    assert "/skill:" in block


# --- epic-member handoff, delegated to live render-status (tech-spec §3.5) --- #

def _loop_member_state() -> dict:
    """A member whose loop is complete: docs still owed, impl verify already passed.

    That combination is `is_complete_for_orchestration` (00 §7 does NOT require
    documentation), so this member is complete for the epic's purposes and therefore
    NOT actionable — which is exactly what makes the epic handoff observable.
    """
    stages: dict = {
        stage: {"status": "complete", "version": 1}
        for stage in PRODUCTION_STAGES[1:6]  # forge-1-prd .. forge-5-loop
    }
    stages["forge-verify-impl"] = {"status": "passed", "verifiedStageVersion": 1}
    return {"pipelineStatus": "active", "epic": DOCS_EPIC, "stages": stages}


def _loop_epic_project(tmp_path: Path, members: list[dict],
                       states: dict[str, dict]) -> Path:
    """A REAL epic whose member state is written verbatim, so `render-status` runs
    over the same tree the router does (07 §3.5/§3.6 forbid mocking it)."""
    root = _docs_epic_project(tmp_path, members)
    for name, state in states.items():
        member_dir = root / "specs" / DOCS_EPIC / name
        (member_dir / ".pipeline-state.json").write_text(json.dumps(state))
        (member_dir / "PRD.md").write_text("# prd\n")
    return root


def test_loop_complete_epic_member_routes_to_the_live_next_actionable_member(
    tmp_path: Path,
) -> None:
    """The epic handoff comes from `render-status`, not from a re-derivation here."""
    root = _loop_epic_project(
        tmp_path,
        [_member("beta"), _member("alpha")],
        {"alpha": _loop_member_state(), "beta": None},
    )
    live = json.loads(subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "epic-manifest.py"),
         "render-status", DOCS_EPIC, "--specs-dir", str(root / "specs"), "--json"],
        capture_output=True, text=True, check=True).stdout)
    assert live["nextCommand"] == "/feature-forge:forge-1-prd beta"

    payload = _loop(root, "complete", "alpha", "--epic", DOCS_EPIC)
    assert payload["directives"]["primaryCommand"] == live["nextCommand"]
    assert "puts the next actionable work below" in payload["nextSteps"]
    assert f"epic {DOCS_EPIC} (1/2 members complete)" in payload["nextSteps"]


def test_loop_complete_epic_member_routes_to_its_docs_once_the_epic_is_complete(
    tmp_path: Path,
) -> None:
    """Nothing actionable AND every member complete: this member's documentation is
    what remains — the same handoff this stage made before it was scripted."""
    root = _loop_epic_project(
        tmp_path, [_member("alpha")], {"alpha": _loop_member_state()},
    )
    payload = _loop(root, "complete", "alpha", "--epic", DOCS_EPIC)
    assert payload["directives"]["primaryCommand"] == "/feature-forge:forge-6-docs alpha"
    assert f"every member of epic {DOCS_EPIC} is now complete (1/1)" in payload["nextSteps"]


def test_loop_complete_in_an_empty_epic_opens_the_dashboard(tmp_path: Path) -> None:
    """An empty epic's 0/0 must not read as complete (the `total > 0` guard)."""
    root = _loop_epic_project(tmp_path, [], {})
    (root / "specs" / DOCS_EPIC / "alpha").mkdir()
    (root / "specs" / DOCS_EPIC / "alpha" / ".pipeline-state.json").write_text(
        json.dumps(_loop_member_state())
    )
    payload = _loop(root, "complete", "alpha", "--epic", DOCS_EPIC)
    assert payload["directives"]["primaryCommand"] == DASHBOARD
    assert f"no member of epic {DOCS_EPIC} is actionable right now (0/0" in \
        payload["nextSteps"]


def test_loop_complete_epic_member_stays_verify_first(tmp_path: Path) -> None:
    """The epic handoff is DEFERRED while implementation verification is unresolved."""
    state = _loop_member_state()
    del state["stages"]["forge-verify-impl"]
    root = _loop_epic_project(tmp_path, [_member("alpha")], {"alpha": state})
    d = _loop(root, "complete", "alpha", "--epic", DOCS_EPIC)["directives"]
    assert d["primaryCommand"] == "/feature-forge:forge-verify alpha"
    # Unresolved verification keeps the member actionable, so the live epic status
    # names its own next production stage — deferred, never fenced.
    assert d["deferredCommand"] == "/feature-forge:forge-6-docs alpha"


def test_loop_complete_routes_on_the_state_epic_back_pointer(tmp_path: Path) -> None:
    """`--epic` is optional: the member state's back-pointer resolves the same epic."""
    root = _loop_epic_project(
        tmp_path, [_member("alpha")], {"alpha": _loop_member_state()},
    )
    with_flag = _loop(root, "complete", "alpha", "--epic", DOCS_EPIC)
    without = _loop(root, "complete", "alpha")
    assert without == with_flag


def test_loop_complete_in_a_broken_epic_is_an_actionable_routing_failure(
    tmp_path: Path,
) -> None:
    """A guessed member command is never emitted: the invalid graph surfaces."""
    root = _loop_epic_project(
        tmp_path, [_member("alpha", depends_on=("ghost",))],
        {"alpha": _loop_member_state()},
    )
    err = _rejected(root, "--feature", "alpha", "--stage", "forge-5-loop",
                    "--outcome", "complete", "--epic", DOCS_EPIC)
    assert "render-status exited 1" in err
    assert DOCS_EPIC in err and DASHBOARD in err


@pytest.mark.parametrize("outcome", NON_COMPLETE_LOOP_OUTCOMES,
                         ids=NON_COMPLETE_LOOP_OUTCOMES)
def test_a_non_complete_loop_closes_even_when_the_epic_graph_is_broken(
    tmp_path: Path, outcome: str
) -> None:
    """A resume or recovery action must stay reachable exactly when the epic's own
    state is what is broken — so no non-complete outcome consults render-status."""
    root = _loop_epic_project(
        tmp_path, [_member("alpha", depends_on=("ghost",))],
        {"alpha": _loop_member_state()},
    )
    d = _loop(root, outcome, "alpha", "--epic", DOCS_EPIC)["directives"]
    assert d["primaryCommand"] in (
        "/feature-forge:forge-5-loop alpha", "/feature-forge:forge alpha"
    )


def test_loop_never_reimplements_the_epic_handoff_derivation() -> None:
    """tech-spec §3.5: `_loop_route` consumes `_render_status`; it derives nothing."""
    source = HELPER.read_text()
    body = source[source.index("def _loop_route("):]
    body = body[: body.index("\ndef _debt_metadata_warnings")]
    assert "_render_status(" in body
    for forbidden in ("dependsOn", "epic-manifest.json", "PIPELINE_STATE_FILENAME"):
        assert forbidden not in body, forbidden


def test_every_loop_outcome_has_a_route_and_a_sentence() -> None:
    """REQ-ROUTE-05/06: complete maps, no fall-through (06 §2.4's positive test)."""
    session = _load_session()
    assert set(session._LOOP_ROUTE_KIND) == set(LOOP_OUTCOMES)
    assert set(session._LOOP_OUTCOME_TEXT) == set(NON_COMPLETE_LOOP_OUTCOMES)
    assert set(session._LOOP_ROUTE_KIND.values()) == {"handoff", "resume", "recover"}
    # Only `complete` may reach a production stage.
    assert [o for o, k in session._LOOP_ROUTE_KIND.items() if k == "handoff"] == \
        ["complete"]
