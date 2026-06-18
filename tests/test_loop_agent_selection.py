"""Tests for the coding-agent selection executable spec (spec 07 §3).

Exercises ``references/loop-agent-selection.py`` — the importable capture of the
documented selection algorithm (spec 02/03/04) — plus the schema defaults landed
in ``references/forge-config-schema.json`` (spec 02). Each group below maps to a
subsection of ``07-testing-strategy.md §3``:

  * §3.1 precedence (incl. the REQ-AGENT-05 no-backlog-item invariant),
  * §3.2 probe split (unknown vs unavailable; SC-08 unknown-listing; the
    once-no-retries argv assertion, REQ-PERF-02),
  * §3.3 command render + the REQ-SEC-01 allow-list,
  * §3.4 capability gating (gate-off ⇒ no probe, byte-identical launch),
  * §3.5 schema defaults (REQ-BIN-02),
  * §3.6 probe-failure edges (empty/missing-id/non-zero/unparseable).

The pre-check is driven through the real ``tests/fixtures/mock-rauf/rauf``
fixture (spec 07 §4) — a fake runner that records its argv to
``$MOCK_RAUF_ARGV_LOG`` — so the plumbing is proven WITHOUT a live agent.

IMPORTANT — this is NOT full end-to-end coverage. Per SC-07 / spec 07 §6, a
true multi-agent install driving a live non-claude coding agent end-to-end is
**maintainer-run, not CI-automatable**; the mock runner here STANDS IN for that
live run so a future reader must not mistake this suite for the real E2E.
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MODULE_PATH = REPO_ROOT / "references" / "loop-agent-selection.py"
SCHEMA_PATH = REPO_ROOT / "references" / "forge-config-schema.json"
MOCK_RAUF = Path(__file__).resolve().parent / "fixtures" / "mock-rauf" / "rauf"

RUNNER_DEFAULT = "claude-cli"


@pytest.fixture(scope="module")
def sel() -> ModuleType:
    """Import references/loop-agent-selection.py as the module loop_agent_selection.

    The filename contains a hyphen, so it is loaded via importlib (mirroring the
    helper_module fixture in conftest.py) rather than a normal import.
    """
    spec = importlib.util.spec_from_file_location("loop_agent_selection", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec so dataclasses can resolve the module's string
    # annotations (the file uses `from __future__ import annotations`).
    sys.modules["loop_agent_selection"] = module
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# Integrated pre-check flow — models the caller (skill prose) around the
# executable spec, so §3.2/§3.4/§3.6 can assert the verdict ACTIONS (offers /
# hard-reject / probe-failure / render call) without a live UI. Probe-failure
# handling lives in the caller per spec 04 §5 — classify is never reached for it.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FlowResult:
    """What the integrated Step 2d flow decided for one launch attempt.

    Attributes:
        outcome: "default" | "available" | "unavailable" | "unknown" | "probe_failure".
        launch: The rendered launch command when forge would launch, else None.
        probed: Whether agentsProbeCommand was invoked.
        offer_proceed_anyway: Whether a proceed-anyway choice is offered.
        offer_choose_another: Whether a choose-another choice is offered.
        valid_ids: For the unknown outcome, the sorted advertised ids (else None).
        detail: For the unavailable outcome, the probe row's detail (else None).
    """

    outcome: str
    launch: str | None = None
    probed: bool = False
    offer_proceed_anyway: bool = False
    offer_choose_another: bool = False
    valid_ids: tuple[str, ...] | None = None
    detail: str | None = None


def _probe(argv_log: Path) -> tuple[int, str]:
    """Run the mock-rauf probe, returning (exit_code, stdout)."""
    env = {**os.environ, "MOCK_RAUF_ARGV_LOG": str(argv_log)}
    proc = subprocess.run(
        [sys.executable, str(MOCK_RAUF), "agents", "--json"],
        capture_output=True,
        text=True,
        env=env,
    )
    return proc.returncode, proc.stdout


def _probe_failed(exit_code: int, stdout: str) -> tuple[bool, list[dict[str, Any]] | None]:
    """Detect a probe failure per spec 04 §5 (caller-side, before classify).

    Returns (failed, agents_rows). A probe failure is any outcome that is not
    "exit 0 with parseable {agents:[...]} carrying a usable advertised set":
    non-zero exit, unparseable / wrong-shape JSON, an empty agents array, or any
    row missing the required `id` field.
    """
    if exit_code != 0:
        return True, None
    try:
        data = json.loads(stdout)
    except (ValueError, TypeError):
        return True, None
    if not isinstance(data, dict) or not isinstance(data.get("agents"), list):
        return True, None
    rows = data["agents"]
    if not rows:  # empty advertised set ⇒ probe failure, NOT an empty-valid_ids UNKNOWN
        return True, None
    if any("id" not in row for row in rows):  # missing required id ⇒ probe failure (no KeyError)
        return True, None
    return False, rows


def run_flow(
    sel: ModuleType,
    *,
    run_selection: str | None,
    default_agent: str,
    agent_argument: str | None,
    base_cmd: str,
    argv_log: Path,
    probe: tuple[int, str] | None = None,
) -> FlowResult:
    """Drive the full Step 2d resolution + pre-check + render flow.

    Mirrors the skill prose (spec 02 gate → spec 03 resolve → spec 04 pre-check →
    spec 03 render_launch). ``probe`` overrides the probe result for the §3.6
    failure-edge tests; otherwise the real mock-rauf fixture is invoked.
    """
    resolution = sel.resolve(run_selection, default_agent, RUNNER_DEFAULT)

    # Capability gate (spec 02 §2) + default path (spec 04 §1): no probe at all.
    if not agent_argument or not sel.needs_precheck(resolution.agent, RUNNER_DEFAULT):
        return FlowResult(
            outcome="default",
            launch=sel.render_launch(base_cmd, agent_argument, resolution, RUNNER_DEFAULT),
            probed=False,
        )

    exit_code, stdout = probe if probe is not None else _probe(argv_log)
    failed, rows = _probe_failed(exit_code, stdout)
    if failed:
        # spec 04 §5: surface + choose-another/abort, NEVER launch unvalidated.
        return FlowResult(
            outcome="probe_failure",
            launch=None,
            probed=True,
            offer_choose_another=True,
        )

    classification = sel.classify(resolution.agent, rows, RUNNER_DEFAULT)
    verdict = classification.verdict
    if verdict is sel.Verdict.UNKNOWN:
        # spec 04 §4.1: hard-reject before side-effects, list valid ids, NO proceed.
        return FlowResult(
            outcome="unknown",
            launch=None,
            probed=True,
            valid_ids=classification.valid_ids,
        )
    if verdict is sel.Verdict.UNAVAILABLE:
        # spec 04 §4.2: warn, offer proceed-anyway OR choose-another.
        return FlowResult(
            outcome="unavailable",
            launch=sel.render_launch(base_cmd, agent_argument, resolution, RUNNER_DEFAULT),
            probed=True,
            offer_proceed_anyway=True,
            offer_choose_another=True,
            detail=classification.detail,
        )
    return FlowResult(
        outcome="available",
        launch=sel.render_launch(base_cmd, agent_argument, resolution, RUNNER_DEFAULT),
        probed=True,
    )


def _probe_count(argv_log: Path) -> int:
    """Count recorded `agents --json` invocations in the mock-rauf argv log."""
    if not argv_log.exists():
        return 0
    count = 0
    for line in argv_log.read_text().splitlines():
        if not line.strip():
            continue
        argv = json.loads(line)
        if argv[1:3] == ["agents", "--json"]:
            count += 1
    return count


# ── 3.1 Precedence (REQ-PREC-01/02, REQ-AGENT-03/05) ────────────────────────


def test_precedence_run_beats_project(sel):
    assert sel.resolve("codex", "gemini", RUNNER_DEFAULT) == sel.Resolution(
        agent="codex", source=sel.AgentSource.RUN
    )


def test_precedence_project_when_no_run(sel):
    assert sel.resolve(None, "gemini", RUNNER_DEFAULT) == sel.Resolution(
        agent="gemini", source=sel.AgentSource.PROJECT
    )


def test_precedence_empty_and_whitespace_are_default(sel):
    expected = sel.Resolution(agent=None, source=sel.AgentSource.DEFAULT)
    assert sel.resolve(None, "", RUNNER_DEFAULT) == expected
    assert sel.resolve(None, "   ", RUNNER_DEFAULT) == expected


def test_precedence_explicit_default_pick_collapses_to_default(sel):
    resolution = sel.resolve("claude-cli", "gemini", RUNNER_DEFAULT)
    assert resolution == sel.Resolution(agent=None, source=sel.AgentSource.DEFAULT)
    # And render_launch treats it as the default path — appends nothing (§3.3).
    assert sel.render_launch("BASE", "--agent {agent}", resolution, RUNNER_DEFAULT) == "BASE"


def test_no_function_accepts_a_backlog_item_argument(sel):
    """REQ-AGENT-05: no code path lets a BacklogItem.provider flow into selection.

    Operationalized per spec 07 §3.1: no public function accepts an
    item/provider/backlog parameter, so a backlog item value can never reach
    resolve/render_launch/classify.
    """
    import inspect

    banned = ("item", "provider", "backlog")
    for name in ("resolve", "render_launch", "classify", "needs_precheck", "advertised_set"):
        params = inspect.signature(getattr(sel, name)).parameters
        for pname in params:
            assert not any(b in pname.lower() for b in banned), (
                f"{name}() exposes a backlog-item-like parameter {pname!r} (REQ-AGENT-05)"
            )


# ── 3.2 Probe split — unknown vs unavailable (REQ-AVAIL-02/04, SC-08) ───────


def test_classify_available(sel, tmp_path):
    _, stdout = _probe(tmp_path / "argv.log")
    agents = json.loads(stdout)["agents"]
    assert sel.classify("codex", agents, RUNNER_DEFAULT).verdict is sel.Verdict.AVAILABLE


def test_classify_unavailable_populates_detail(sel, tmp_path):
    _, stdout = _probe(tmp_path / "argv.log")
    agents = json.loads(stdout)["agents"]
    result = sel.classify("gemini", agents, RUNNER_DEFAULT)
    assert result.verdict is sel.Verdict.UNAVAILABLE
    assert result.detail == "gemini CLI not found on PATH"


def test_classify_unknown_lists_sorted_valid_ids(sel, tmp_path):
    _, stdout = _probe(tmp_path / "argv.log")
    agents = json.loads(stdout)["agents"]
    result = sel.classify("bogus", agents, RUNNER_DEFAULT)
    assert result.verdict is sel.Verdict.UNKNOWN
    assert result.valid_ids == tuple(sorted({"claude-cli", "codex", "gemini"}))


def test_unknown_offers_no_proceed_anyway_but_unavailable_offers_both(sel, tmp_path):
    """SC-08: unknown hard-rejects (no proceed-anyway); unavailable offers both."""
    unknown = run_flow(
        sel,
        run_selection="bogus",
        default_agent="",
        agent_argument="--agent {agent}",
        base_cmd="BASE",
        argv_log=tmp_path / "u.log",
    )
    assert unknown.outcome == "unknown"
    assert unknown.launch is None
    assert unknown.offer_proceed_anyway is False
    assert unknown.offer_choose_another is False
    assert unknown.valid_ids == tuple(sorted({"claude-cli", "codex", "gemini"}))

    unavailable = run_flow(
        sel,
        run_selection="gemini",
        default_agent="",
        agent_argument="--agent {agent}",
        base_cmd="BASE",
        argv_log=tmp_path / "g.log",
    )
    assert unavailable.outcome == "unavailable"
    assert unavailable.offer_proceed_anyway is True
    assert unavailable.offer_choose_another is True
    assert unavailable.detail == "gemini CLI not found on PATH"


def test_probe_runs_exactly_once_per_nondefault_attempt(sel, tmp_path):
    """REQ-PERF-02: one `agents --json` per non-default launch attempt, no retries."""
    log = tmp_path / "argv.log"
    run_flow(
        sel,
        run_selection="codex",
        default_agent="",
        agent_argument="--agent {agent}",
        base_cmd="BASE",
        argv_log=log,
    )
    assert _probe_count(log) == 1


# ── 3.3 Command render + allow-list (REQ-AGENT-01, REQ-SEC-01) ──────────────


def test_render_appends_validated_nondefault_id(sel):
    resolution = sel.Resolution(agent="codex", source=sel.AgentSource.RUN)
    assert (
        sel.render_launch("BASE", "--agent {agent}", resolution, RUNNER_DEFAULT)
        == "BASE --agent codex"
    )


def test_render_unchanged_for_default_and_runner_default(sel):
    none_res = sel.Resolution(agent=None, source=sel.AgentSource.DEFAULT)
    default_res = sel.Resolution(agent="claude-cli", source=sel.AgentSource.RUN)
    assert sel.render_launch("BASE", "--agent {agent}", none_res, RUNNER_DEFAULT) == "BASE"
    assert sel.render_launch("BASE", "--agent {agent}", default_res, RUNNER_DEFAULT) == "BASE"


def test_unknown_id_never_reaches_render_launch(sel, tmp_path):
    """REQ-SEC-01: the advertised set is the allow-list — bogus is rejected first."""
    result = run_flow(
        sel,
        run_selection="bogus",
        default_agent="",
        agent_argument="--agent {agent}",
        base_cmd="BASE",
        argv_log=tmp_path / "argv.log",
    )
    assert result.outcome == "unknown"
    assert result.launch is None  # render_launch was never called


# ── 3.4 Capability gating (REQ-PLUG-01/02, REQ-COMPAT-01) ───────────────────


def test_render_gate_off_never_appends(sel):
    resolution = sel.Resolution(agent="codex", source=sel.AgentSource.RUN)
    assert sel.render_launch("BASE", None, resolution, RUNNER_DEFAULT) == "BASE"


def test_gate_off_runs_no_probe_and_is_byte_identical(sel, tmp_path):
    log = tmp_path / "argv.log"
    gated_off = run_flow(
        sel,
        run_selection="codex",
        default_agent="",
        agent_argument=None,  # gate OFF — agentArgument absent
        base_cmd="BASE",
        argv_log=log,
    )
    assert gated_off.outcome == "default"
    assert gated_off.probed is False
    assert _probe_count(log) == 0
    # Byte-identical to the no-agent baseline.
    assert gated_off.launch == "BASE"


# ── 3.5 Schema defaults (REQ-BIN-02) ────────────────────────────────────────


def test_schema_loop_runner_agent_defaults():
    schema = json.loads(SCHEMA_PATH.read_text())
    props = schema["properties"]["loopRunner"]["properties"]
    assert props["minRunnerVersion"]["default"] == "0.6.0"
    assert props["agentArgument"]["default"] == "--agent {agent}"
    assert props["agentsProbeCommand"]["default"] == "{bin} agents --json"
    assert props["defaultAgent"]["default"] == ""
    for field in ("agentArgument", "agentsProbeCommand", "defaultAgent"):
        assert props[field]["type"] == "string"


def test_fixture_version_reports_floor():
    """The mock-rauf `version --json` branch reports the 0.6.0 floor (spec 07 §4).

    The fixture MUST implement this for the version-gate path; assert it here so the
    branch can't silently break (the schema test above only checks the JSON default).
    """
    proc = subprocess.run(
        [sys.executable, str(MOCK_RAUF), "version", "--json"],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0
    assert json.loads(proc.stdout) == {"version": "0.6.0"}


# ── 3.6 Probe-failure edges (REQ-AVAIL-01, spec 04 §5) ──────────────────────


@pytest.mark.parametrize(
    "probe",
    [
        (0, json.dumps({"agents": []})),  # empty advertised set
        (0, json.dumps({"agents": [{"displayName": "X", "available": True}]})),  # row missing id
        (1, json.dumps({"agents": [{"id": "codex", "available": True}]})),  # non-zero exit
        (0, "not json at all"),  # unparseable JSON
        (0, json.dumps({"wrong": "shape"})),  # missing agents array
    ],
)
def test_probe_failure_paths_choose_another_no_render(sel, tmp_path, probe):
    """Each malformed probe ⇒ probe-failure (choose-another/abort), not UNKNOWN."""
    result = run_flow(
        sel,
        run_selection="codex",
        default_agent="",
        agent_argument="--agent {agent}",
        base_cmd="BASE",
        argv_log=tmp_path / "argv.log",
        probe=probe,
    )
    assert result.outcome == "probe_failure"
    assert result.launch is None  # render_launch never called
    assert result.offer_choose_another is True
    assert result.valid_ids is None  # NOT an empty-valid_ids UNKNOWN


def test_row_missing_id_raises_no_keyerror_in_detection(sel):
    """A row lacking `id` is caught as a probe failure before advertised_set runs."""
    failed, rows = _probe_failed(0, json.dumps({"agents": [{"available": True}]}))
    assert failed is True and rows is None
