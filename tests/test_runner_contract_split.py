"""R6 drift guard — the runner-contract.md / agent-selection.md split.

`skills/forge-5-loop/references/runner-contract.md` used to carry nine sections, three
of which are only meaningful when the Step 2d agent-selection capability gate
(`loopRunner.agentArgument`) is on. R6 moved those three into a sibling
`references/agent-selection.md` so a gate-off run never loads them.

Three properties have to hold together, and none of them is coverage on its own:

1. **Partition** — the union of the two files' headings is exactly the original nine,
   split {1,4,6,7,8,9} / {2,3,5}. A dropped section is a silently lost instruction; a
   duplicated one is drift waiting to happen.
2. **Citation placement** — every `references/agent-selection.md` citation in the loop
   SKILL body sits *below* the capability-gate heading. A citation above the gate loads
   the file on every gate-off run and defeats the split (REQ-R6-02).
3. **Presence + cap** — both files stay cited by literal path (so adapter citation
   fan-out keeps shipping them) and the loop body stays inside check-spec-purity's
   Rule 4 budget, which pytest does not otherwise enforce.

Stdlib only; asserts against `skills/` canon, never `adapters/`.
"""

from __future__ import annotations

import re

from _forge_paths import SKILLS, read

LOOP_SKILL = SKILLS / "forge-5-loop" / "SKILL.md"
RUNNER_CONTRACT = SKILLS / "forge-5-loop" / "references" / "runner-contract.md"
AGENT_SELECTION = SKILLS / "forge-5-loop" / "references" / "agent-selection.md"

# The nine sections of the pre-split runner-contract.md, verbatim (spec 05 §3.2).
ALWAYS_LOADED = [
    "## Model selection precedence (Step 2d)",
    "## Run mode (Step 2d, rauf)",
    "## Launch detail (Step 3b — background process)",
    "## Arm a Monitor on the event stream (Step 3d)",
    "## React to events as they land (Step 3e)",
    "## Inform-user output template (Step 3c)",
]
AGENT_CONDITIONAL = [
    "## Agent selection (Step 2d)",
    "### Claude-only model-alias guard (Step 2d, sub-step d-model)",
    "## Optional flags catalog (Step 2d, rauf)",
]

# The capability-gate heading. Everything below it in the body runs only when
# `loopRunner.agentArgument` is present and non-empty.
GATE_HEADING = "#### Agent selection (gated on `loopRunner.agentArgument`)"
GATE_SENTINEL = "applies **only when** the effective `loopRunner.agentArgument`"

MAX_BODY_LINES = 300  # check-spec-purity.py Rule 4
MAX_BODY_WORDS = 5000


def _headings(text: str) -> list[str]:
    """Every ATX heading below the file's `# ` title, in document order."""
    return [line.rstrip() for line in text.splitlines() if re.match(r"^#{2,6} ", line)]


def _body_lines(text: str) -> list[str]:
    """The frontmatter-stripped region check-spec-purity Rule 4 measures."""
    assert text.startswith("---\n"), f"{LOOP_SKILL} has no YAML frontmatter block"
    return text.split("---\n", 2)[2].splitlines()


# --- 1. Partition ----------------------------------------------------------------


def test_agent_selection_holds_exactly_the_three_conditional_sections():
    assert _headings(read(AGENT_SELECTION)) == AGENT_CONDITIONAL


def test_runner_contract_holds_exactly_the_six_always_loaded_sections():
    assert _headings(read(RUNNER_CONTRACT)) == ALWAYS_LOADED


def test_the_union_of_both_files_is_the_original_nine_sections():
    union = _headings(read(RUNNER_CONTRACT)) + _headings(read(AGENT_SELECTION))
    assert sorted(union) == sorted(ALWAYS_LOADED + AGENT_CONDITIONAL), (
        "the split dropped, renamed or duplicated a section — every one of the nine "
        "original runner-contract.md headings must survive in exactly one file"
    )
    assert len(set(union)) == len(union) == 9


def test_no_agent_selection_content_leaked_back_into_runner_contract():
    contract = read(RUNNER_CONTRACT)
    for marker in (
        "agentsProbeCommand",  # the availability pre-check
        "`opus`/`sonnet`/`haiku`",  # the Claude-only model-alias guard
        "--retry-blocked   Unblock",  # the optional-flags catalog body
    ):
        assert marker not in contract, (
            f"agent-conditional content ({marker!r}) is back in runner-contract.md, "
            "which every run loads"
        )


# --- 2. Citation placement -------------------------------------------------------


def test_agent_selection_is_cited_only_below_the_capability_gate():
    lines = _body_lines(read(LOOP_SKILL))
    gate_index = next(i for i, line in enumerate(lines) if line.startswith(GATE_HEADING))
    assert any(GATE_SENTINEL in line for line in lines[gate_index:]), (
        "the capability-gate sentinel moved — re-derive GATE_SENTINEL before trusting "
        "the placement assertion below"
    )

    cited_at = [
        i for i, line in enumerate(lines) if "references/agent-selection.md" in line
    ]
    assert cited_at, "references/agent-selection.md is no longer cited from the body"
    above_gate = [i + 1 for i in cited_at if i <= gate_index]
    assert not above_gate, (
        f"references/agent-selection.md is cited above the capability gate at body "
        f"line(s) {above_gate} — a gate-off run would load it, defeating REQ-R6-02"
    )


def test_the_confirmation_pointer_above_the_gate_cites_only_runner_contract():
    lines = _body_lines(read(LOOP_SKILL))
    gate_index = next(i for i, line in enumerate(lines) if line.startswith(GATE_HEADING))
    pointer = [
        line
        for line in lines[:gate_index]
        if "read references/runner-contract.md" in line
        or "read `references/runner-contract.md`" in line
    ]
    assert pointer, "the model-selection-precedence pointer above the gate is gone"
    assert not any("optional-flags catalog" in line for line in lines[:gate_index]), (
        "the optional-flags-catalog clause is back above the capability gate — the "
        "catalog moved into agent-selection.md and must be named from inside the gate"
    )


# --- 3. Presence + cap -----------------------------------------------------------


def test_both_reference_files_are_cited_by_literal_path_for_fan_out():
    body = "\n".join(_body_lines(read(LOOP_SKILL)))
    for path in ("references/runner-contract.md", "references/agent-selection.md"):
        assert path in body, (
            f"{path} is not cited by literal path in the loop body — the adapter "
            "build's citation fan-out would stop shipping it to non-Claude hosts"
        )


def test_the_loop_body_stays_within_rule_4():
    lines = _body_lines(read(LOOP_SKILL))
    words = len("\n".join(lines).split())
    assert len(lines) <= MAX_BODY_LINES, (
        f"forge-5-loop body is {len(lines)} lines (cap {MAX_BODY_LINES}) — R4, R5 and "
        "R6 share this budget"
    )
    assert words <= MAX_BODY_WORDS, f"forge-5-loop body is {words} words (cap {MAX_BODY_WORDS})"
