"""Guards for the zero-prompt loop-config gates (#153 reviewMode, #164 agentMode).

`loopRunner.reviewMode` gates forge-5-loop's Step 2d Run-mode question;
`loopRunner.agentMode` gates the Step 2d agent question. Both are opt-in: the
`"prompt"` defaults must reproduce today's prompts byte-identically, and under
`agentMode: "auto"` the availability probe + verdict + Claude-alias guard still
run — only the interactive pick is suppressed.

Three surfaces carry the contract, and each is pinned here so a rewording that
drops a load-bearing clause fails loudly:

1. `references/forge-config-schema.json` — enum + default for both keys.
2. `skills/forge-5-loop/references/runner-contract.md` — the reviewMode gate
   lives INSIDE the existing `## Run mode (Step 2d, rauf)` section (the
   heading partition is pinned by `tests/test_runner_contract_split.py`; this
   module pins the semantics).
3. `skills/forge-5-loop/references/agent-selection.md` — the agentMode gate,
   including the still-runs-under-auto list and the never-hidden Agent line.

Stdlib only; asserts against `skills/` + `references/` canon, never `adapters/`.
"""

from __future__ import annotations

import json

from _forge_paths import REFERENCES, SKILLS, read

SCHEMA = REFERENCES / "forge-config-schema.json"
RUNNER_CONTRACT = SKILLS / "forge-5-loop" / "references" / "runner-contract.md"
AGENT_SELECTION = SKILLS / "forge-5-loop" / "references" / "agent-selection.md"
LOOP_SKILL = SKILLS / "forge-5-loop" / "SKILL.md"


def _loop_runner_props() -> dict:
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    return schema["properties"]["loopRunner"]["properties"]


# --- 1. Schema -------------------------------------------------------------------


def test_review_mode_is_a_declared_tri_state_defaulting_to_prompt() -> None:
    """#153: reviewMode is a real schema contract with today's behavior as default."""
    review = _loop_runner_props()["reviewMode"]
    assert review["type"] == "string"
    assert review["enum"] == ["prompt", "always", "never"]
    assert review["default"] == "prompt"


def test_agent_mode_is_a_declared_two_state_defaulting_to_prompt() -> None:
    """#164: agentMode mirrors reviewMode's shape with today's behavior as default."""
    agent = _loop_runner_props()["agentMode"]
    assert agent["type"] == "string"
    assert agent["enum"] == ["prompt", "auto"]
    assert agent["default"] == "prompt"


def test_agent_mode_description_defers_to_the_capability_gate() -> None:
    """agentMode adds no second gate — agentArgument absent removes the whole surface."""
    description = _loop_runner_props()["agentMode"]["description"]
    assert "agentArgument" in description
    assert "no second gate" in description


# --- 2. runner-contract.md — the reviewMode gate ---------------------------------


def test_review_mode_gate_sits_inside_the_run_mode_section() -> None:
    """The gate must be in the section every rauf run reads, not a new heading."""
    contract = read(RUNNER_CONTRACT)
    section = contract.split("## Run mode (Step 2d, rauf)", 1)[1].split("\n## ", 1)[0]
    assert "`loopRunner.reviewMode`" in section


def test_review_mode_semantics_are_pinned() -> None:
    """always → skip + unconditional --review (still shown); never → skip + bare."""
    contract = read(RUNNER_CONTRACT)
    gate = contract.split("`loopRunner.reviewMode`", 1)[1]
    for clause in (
        'is `"prompt"` — the default, byte-identical to today',
        "appends `--review` unconditionally",
        "still shows `--review`",
        "launches the bare rendered\ncommand",
    ):
        assert clause in gate, f"reviewMode gate lost the clause {clause!r}"


def test_retry_blocked_keeps_a_narrow_situational_prompt_under_always_never() -> None:
    """Owner decision (#153): blocked > 0 still asks a narrower retry-blocked-only
    question under always/never; with no blocked items the launch is prompt-free."""
    contract = read(RUNNER_CONTRACT)
    gate = contract.split("`loopRunner.reviewMode`", 1)[1]
    assert "`blocked > 0`" in gate
    assert "narrower situational question" in gate
    assert "**not** re-asked" in gate
    assert "asks nothing" in gate


# --- 3. agent-selection.md — the agentMode gate ----------------------------------


def test_agent_mode_gate_is_on_the_agent_selection_surface() -> None:
    agent_selection = read(AGENT_SELECTION)
    assert "`loopRunner.agentMode` gate" in agent_selection


def test_under_auto_the_probe_verdict_and_alias_guard_still_run() -> None:
    """Only the interactive pick is suppressed — the safety checks are not."""
    agent_selection = read(AGENT_SELECTION)
    gate = agent_selection.split("`loopRunner.agentMode` gate", 1)[1]
    for clause in (
        "suppresses **only the interactive pick**",
        'still runs under `"auto"`',
        "the single probe",
        "UNKNOWN hard-reject before any loop\nside-effect",
        "Claude-only model-alias guard",
        "safety surfaces, not the pick",
    ):
        assert clause in gate, f"agentMode gate lost the clause {clause!r}"


def test_under_auto_the_resolved_agent_line_is_never_hidden() -> None:
    agent_selection = read(AGENT_SELECTION)
    gate = agent_selection.split("`loopRunner.agentMode` gate", 1)[1]
    assert "`Agent: {id} (source: …)` line still shows" in gate
    assert "never hidden" in gate


def test_agent_mode_adds_no_second_gate_on_the_surface_too() -> None:
    """The prose repeats the schema's stance: agentArgument absent ⇒ agentMode moot."""
    agent_selection = read(AGENT_SELECTION)
    gate = agent_selection.split("`loopRunner.agentMode` gate", 1)[1]
    assert "`loopRunner.agentArgument` is absent" in gate
    assert "no second gate" in gate


# --- 4. SKILL.md wiring ----------------------------------------------------------


def test_skill_body_names_both_gates() -> None:
    """The loop body routes each gate to its reference file (mode semantics live
    there, not in the word-capped body)."""
    body = read(LOOP_SKILL)
    assert "`loopRunner.reviewMode`" in body
    assert '`loopRunner.agentMode: "auto"`' in body


def test_skill_agent_mode_mention_preserves_the_still_run_steps() -> None:
    """The (b) bullet says which sub-steps survive auto, so a reader who never opens
    agent-selection.md still cannot skip the probe or the verdict."""
    body = read(LOOP_SKILL)
    assert "(a)/(c)/(d)/(d-model) still run" in body
