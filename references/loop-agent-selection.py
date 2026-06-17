"""Executable spec for forge's coding-agent selection algorithm (feature ``forge-rauf-loop-default``).

This module is the single importable capture of the documented selection
algorithm so the test suite cannot drift from the skill prose. It reproduces,
verbatim from the spec suite at ``specs/agent-agnostic/forge-rauf-loop-default/``:

  * the shared types + constants (spec 00 — Core Definitions, §2, §4),
  * ``resolve`` / ``render_launch`` (spec 03 — Selection, Resolution & Observability, §3),
  * ``classify`` / ``needs_precheck`` / ``advertised_set`` (spec 04 — Availability Pre-Check, §1–§3).

It is **test-only + documentation** (OQ-T1 RESOLVED): the skills stay prose and
this module is NOT wired into any generated adapter, so it neither triggers nor
is checked by the build-adapters drift guard. Every function is pure and total,
takes no backlog item, and accepts no item-provider/backlog argument
(REQ-AGENT-05). Python 3.10+, standard library only.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TypedDict

# ---------------------------------------------------------------------------
# 2. Constants owned / pinned by this feature (spec 00 §2)
# ---------------------------------------------------------------------------

#: rauf's own default agent id — the "default path" sentinel (00 §1.2). For rauf == "claude-cli".
#: Passed into resolve()/classify() as a parameter, never hardcoded into the algorithm, so an
#: alternate runner with a different default id is handled without edits (CON-04).
RUNNER_DEFAULT_ID: str = "claude-cli"

#: Minimum rauf version that ships the agent-selection surface (--agent flag, `rauf agents`
#: probe, preset registry). Verified present in rauf source at VERSION 0.6.0
#: (packages/core/src/version.ts == "0.6.0"). REQ-BIN-02; resolves OQ-01.
MIN_RUNNER_VERSION: str = "0.6.0"


# ---------------------------------------------------------------------------
# 4. Owned result types — resolution & classification (spec 00 §4)
# ---------------------------------------------------------------------------

#: The advertised id set parsed from the probe — { row.id for row in agents }. Doubles as
#: REQ-SEC-01's allow-list: the ONLY values ever interpolated into {agent}.
AdvertisedSet = frozenset[str]


class _AgentRow(TypedDict):
    """Required fields of one `rauf agents --json` probe row."""
    id: str            # stable registry key — the only field read for the advertised set
    displayName: str   # human-readable name (e.g. "Claude Code (CLI)")
    available: bool    # whether the agent's CLI / credentials are currently available


class AgentAvailability(_AgentRow, total=False):
    """One probe row — the Python mirror of the TS `AgentAvailability` interface in §1.1
    (what `rauf agents --json` emits per agent). The base `_AgentRow` carries the required
    fields; the optional fields below default to absent (`total=False`). Consumed by
    `classify` / `advertised_set` in `04-availability-precheck.md` — only `id` is read for
    the advertised set; `detail` is surfaced for the UNAVAILABLE warning. Split into a
    required base + optional subclass to stay Python 3.10-compatible (no `NotRequired`)."""
    binaryName: str    # executable probed on PATH, or absent for binary-less descriptors
    detail: str        # PATH location, "not found", or credential status


class AgentSource(str, Enum):
    """Which layer supplied the resolved agent — shown to the user (REQ-OBS-01)."""
    RUN = "run"          # per-run selector (Step 2d)
    PROJECT = "project"  # loopRunner.defaultAgent
    DEFAULT = "default"  # runner's own default (no forge layer set)


@dataclass(frozen=True)
class Resolution:
    """Result of forge collapsing its run+project layers into one value (§5).

    Attributes:
        agent: The resolved agent id, or None when no forge layer is set (the
            default path — append nothing; rauf applies RUNNER_DEFAULT_ID).
        source: Which layer supplied it (RUN/PROJECT/DEFAULT) — for observability.
    """
    agent: str | None
    source: AgentSource


class Verdict(str, Enum):
    """Outcome of classifying a non-default resolved agent against the probe (§4, REQ-AVAIL-*)."""
    AVAILABLE = "available"      # id ∈ advertised set AND available == true ⇒ proceed
    UNAVAILABLE = "unavailable"  # id ∈ advertised set AND available == false ⇒ warn/proceed-or-choose (REQ-AVAIL-02)
    UNKNOWN = "unknown"          # id ∉ advertised set ⇒ HARD-REJECT before launch (REQ-AVAIL-04)


@dataclass(frozen=True)
class Classification:
    """Verdict plus the context needed to act on it.

    Attributes:
        verdict: AVAILABLE | UNAVAILABLE | UNKNOWN.
        detail: For UNAVAILABLE, the probe row's `detail` (PATH/credential status). None otherwise.
        valid_ids: For UNKNOWN, sorted(advertised set) to list in the rejection error. None otherwise.

    Invariant: `detail` is set iff `verdict == UNAVAILABLE`; `valid_ids` is set iff
    `verdict == UNKNOWN`; both are None for AVAILABLE. Enforced by `classify`'s construction
    (04 §3.2), not by the dataclass itself.
    """
    verdict: Verdict
    detail: str | None = None
    valid_ids: tuple[str, ...] | None = None


# ---------------------------------------------------------------------------
# resolve — collapse forge's run + project layers (spec 03 §3.1)
# ---------------------------------------------------------------------------


def resolve(
    run_selection: str | None,
    default_agent: str,
    runner_default_id: str,
) -> Resolution:
    """Collapse forge's run + project layers into one agent value.

    Implements the run-over-project decision forge owns (REQ-PREC-02). forge
    feeds ONLY this resolved value to rauf's run layer via the rendered
    ``--agent {agent}`` argument; rauf alone applies the per-item override
    (``BacklogItem.provider``) ABOVE it (REQ-AGENT-05) and falls through to its
    own ``runner_default_id`` when forge sends nothing (REQ-AGENT-03). forge
    never reads any item-, project-, or global-level agent from rauf's surfaces
    (CON-02/CON-04) — see ``00-core-definitions.md §1.3, §5``.

    Precedence collapsed here (highest wins): run_selection > default_agent.
    A whitespace-only ``default_agent`` is treated as unset (matching rauf's
    own empty/whitespace handling in ``resolveAgentId`` — see §4).

    Args:
        run_selection: The id picked in the Step 2d selector, or None when the
            user picked "default (claude-cli)" / made no run-level choice
            (§2.2). An empty/whitespace string is treated as None.
        default_agent: ``loopRunner.defaultAgent`` from ``forge.config.json``
            (``02-config-schema-and-gating.md``). Empty/whitespace ⇒ no project
            default.
        runner_default_id: The runner's own default id sentinel
            (``RUNNER_DEFAULT_ID`` from ``00-core-definitions.md §2`` —
            ``"claude-cli"`` for rauf). Used to classify the source as DEFAULT
            when the resolved value equals it (and is therefore on the
            default path — §5).

    Returns:
        A :class:`Resolution` whose ``agent`` is the chosen id or None (the
        default path: append no argument, run no probe), and whose ``source``
        is RUN, PROJECT, or DEFAULT.
    """
    def _clean(value: str | None) -> str | None:
        stripped = value.strip() if value is not None else None
        return stripped or None

    run = _clean(run_selection)
    project = _clean(default_agent)

    if run is not None:
        # A run-level pick of the runner default id is still the DEFAULT path:
        # forge sends nothing and rauf applies its own default (§5).
        if run == runner_default_id:
            return Resolution(agent=None, source=AgentSource.DEFAULT)
        return Resolution(agent=run, source=AgentSource.RUN)

    if project is not None:
        if project == runner_default_id:
            return Resolution(agent=None, source=AgentSource.DEFAULT)
        return Resolution(agent=project, source=AgentSource.PROJECT)

    return Resolution(agent=None, source=AgentSource.DEFAULT)


# ---------------------------------------------------------------------------
# render_launch — append the agent argument (spec 03 §3.4)
# ---------------------------------------------------------------------------


def render_launch(
    base_cmd: str,
    agent_argument: str | None,
    resolved: Resolution,
    runner_default_id: str,
) -> str:
    """Append the rendered ``agentArgument`` to the launch command, or return it unchanged.

    Appends ``agent_argument`` (with ``{agent}`` substituted by ``resolved.agent``)
    exactly when an agent surface is present AND a non-default agent was resolved.
    Returns ``base_cmd`` byte-identical to the pre-feature command otherwise — the
    default path and the capability-gated-off path (REQ-COMPAT-01, REQ-PLUG-02).

    Args:
        base_cmd: The rendered run/eventStream command before any agent argument.
        agent_argument: ``loopRunner.agentArgument`` (e.g. ``"--agent {agent}"``), or
            None when the capability gate is off (``agentArgument`` absent — §`02`).
        resolved: The :class:`Resolution` from :func:`resolve`.
        runner_default_id: The runner's own default id (``"claude-cli"`` for rauf).

    Returns:
        ``base_cmd`` with ``" " + agent_argument`` appended (``{agent}`` → ``resolved.agent``)
        when ``agent_argument`` is non-empty AND ``resolved.agent`` is a non-None id that
        differs from ``runner_default_id``; otherwise ``base_cmd`` unchanged.
    """
    if not agent_argument:                       # capability gate off (REQ-PLUG-02)
        return base_cmd
    agent = resolved.agent
    if agent is None or agent == runner_default_id:  # default path (REQ-AGENT-03, REQ-COMPAT-01)
        return base_cmd
    return f"{base_cmd} {agent_argument.replace('{agent}', agent)}"


# ---------------------------------------------------------------------------
# needs_precheck — the single pre-check guard (spec 04 §1)
# ---------------------------------------------------------------------------


def needs_precheck(resolution_agent: str | None, runner_default_id: str) -> bool:
    """Whether the availability pre-check must run for this resolved agent.

    The pre-check runs only for a non-default agent on an agent-surface runner
    (the capability gate is checked separately, upstream — see §1). The default
    path (None or the runner's own default id) is skipped entirely so the common
    case incurs no extra probe (REQ-AVAIL-03, REQ-PERF-01).

    Args:
        resolution_agent: Resolution.agent from
            03-selection-resolution-observability.md — the agent id forge
            resolved from its run+project layers, or None for the default path.
        runner_default_id: The runner's own default agent id
            (RUNNER_DEFAULT_ID == "claude-cli" for rauf; 00-core-definitions.md §2).

    Returns:
        True iff resolution_agent is a non-empty, non-default id (the pre-check
        must run); False for None or the runner default (skip the probe).
    """
    return resolution_agent is not None and resolution_agent != runner_default_id


# ---------------------------------------------------------------------------
# advertised_set — build the allow-list from probe rows (spec 04 §2)
# ---------------------------------------------------------------------------


def advertised_set(agents: list[AgentAvailability]) -> AdvertisedSet:
    """Build the advertised id set (the allow-list) from parsed probe rows.

    AdvertisedSet = { row["id"] for row in agents }. This set is both the basis
    for unknown-vs-unavailable disambiguation (§3) and REQ-SEC-01's allow-list:
    the ONLY values ever interpolated into the {agent} token (§7).

    Args:
        agents: The parsed `agents` array from `{ agents: AgentAvailability[] }`.
            Each element is the dict form of an AgentAvailability row
            (00-core-definitions.md §1.1).

    Returns:
        A frozenset of every advertised agent id.
    """
    return frozenset(str(row["id"]) for row in agents)


# ---------------------------------------------------------------------------
# classify — three-way availability verdict (spec 04 §3.2)
# ---------------------------------------------------------------------------


def classify(
    resolved_agent: str,
    agents: list[AgentAvailability],
    runner_default_id: str,
) -> Classification:
    """Classify a non-default resolved agent against the probe's advertised rows.

    Disambiguates the three pre-check outcomes by MEMBERSHIP in the advertised id
    set, then (for members) by the matching row's `available` flag — never by the
    probe's exit code, because `rauf agents --json` always exits 0 (an unknown id
    is simply absent; a known-unavailable one is present with available=False).
    See "Why membership, not exit code" in §3.3.

    This function assumes `resolved_agent` is a non-default id (the default path
    never reaches the pre-check — §1, REQ-AVAIL-03); callers gate with
    `needs_precheck` (§1) before invoking it.

    Args:
        resolved_agent: The non-default agent id forge resolved (Resolution.agent,
            03-selection-resolution-observability.md §3). Non-empty, != runner_default_id.
        agents: The parsed `agents` rows from the probe
            (`{ agents: AgentAvailability[] }`, 00-core-definitions.md §1.1).
        runner_default_id: The runner's own default id (RUNNER_DEFAULT_ID, accepted
            as a parameter so an alternate runner's default needs no code edit; CON-04).
            Present for symmetry with `resolve`/`needs_precheck`; the default id never
            reaches this function in practice.

    Returns:
        A Classification:
          - Verdict.UNKNOWN     with valid_ids = sorted advertised ids, when the id
                                is not advertised (REQ-AVAIL-04).
          - Verdict.UNAVAILABLE with detail = the row's `detail`, when advertised but
                                available is False (REQ-AVAIL-02).
          - Verdict.AVAILABLE   when advertised and available is True (REQ-AVAIL-01).

    Raises:
        Never. Classification is total over the inputs; malformed probe output is a
        probe failure handled BEFORE this call (§5), not here.
    """
    advertised: dict[str, AgentAvailability] = {str(row["id"]): row for row in agents}

    match advertised.get(resolved_agent):
        case None:
            # Not advertised ⇒ unknown / typo / unsupported. REQ-AVAIL-04.
            return Classification(
                verdict=Verdict.UNKNOWN,
                valid_ids=tuple(sorted(advertised)),
            )
        case {"available": True}:
            return Classification(verdict=Verdict.AVAILABLE)
        case row:
            # Advertised but not available ⇒ known-but-unavailable. REQ-AVAIL-02.
            return Classification(
                verdict=Verdict.UNAVAILABLE,
                detail=row.get("detail"),
            )
