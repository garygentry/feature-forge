"""Regression guard: the forge-verifier must never self-dispatch.

The `forge-verifier` agent pre-loads the `forge-verify` skill (its frontmatter
`skills:` list). That skill is written mostly from the *parent orchestrator's*
point of view ("dispatch the forge-verifier subagent via the Agent tool",
"Synthesize (parent session)"). Without an explicit role guard, a dispatched
verifier reads that as an instruction to itself, tries to delegate further — it
has no Agent tool, so it can't — and returns a non-answer ("verification is
running…") with no findings block and no artifact on disk.

These are static content invariants (the failure itself is behavioural and not
unit-testable), locking the disambiguation so it can't silently regress. They
assert on the canonical surfaces and the byte-identical Claude adapter copies.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CANON_SKILL = REPO_ROOT / "skills" / "forge-verify" / "SKILL.md"
CANON_AGENT = REPO_ROOT / "agents" / "forge-verifier.md"
CLAUDE_SKILL = REPO_ROOT / "adapters" / "claude" / "skills" / "forge-verify" / "SKILL.md"
CLAUDE_AGENT = REPO_ROOT / "adapters" / "claude" / "agents" / "forge-verifier.md"


def _frontmatter_tools(agent_md: Path) -> str:
    """Return the raw `tools:` line value from an agent's YAML frontmatter."""
    text = agent_md.read_text("utf-8")
    match = re.search(r"^tools:\s*(.+)$", text, re.MULTILINE)
    assert match, f"{agent_md} has no `tools:` frontmatter line"
    return match.group(1)


# --------------------------------------------------------------------------- #
# The structural invariant: the verifier cannot dispatch even if it wanted to.
# --------------------------------------------------------------------------- #


def test_verifier_agent_has_no_dispatch_tool():
    """The verifier's tool allowlist must exclude Agent/Task — it is a leaf.

    A read-only leaf agent physically cannot spawn another agent; keeping Agent
    off the allowlist is the hard backstop behind the prose guard.
    """
    tools = _frontmatter_tools(CANON_AGENT)
    for forbidden in ("Agent", "Task"):
        assert not re.search(rf"\b{forbidden}\b", tools), (
            f"forge-verifier tools must not include {forbidden!r}: {tools!r}"
        )


# --------------------------------------------------------------------------- #
# The prose guards on the agent and the skill.
# --------------------------------------------------------------------------- #


def test_agent_prompt_forbids_self_dispatch():
    """The agent system prompt tells the verifier it IS the verifier, never dispatches."""
    body = CANON_AGENT.read_text("utf-8")
    assert "you never dispatch" in body.lower(), "agent prompt lost the no-dispatch guard"
    # It must explicitly neutralise the skill's parent-facing delegation section.
    assert "for the parent" in body.lower() or "parent, not for you" in body.lower(), (
        "agent prompt must flag the skill's Subagent Delegation as parent-only"
    )


def test_skill_has_role_disambiguation_guard():
    """The skill must tell a dispatched verifier to SKIP the delegation section."""
    body = CANON_SKILL.read_text("utf-8")
    # A role-selection preamble exists.
    assert "Which role are you?" in body, "forge-verify skill lost its role guard heading"
    assert "You ARE the `forge-verifier` subagent" in body, (
        "skill guard must address the dispatched-verifier role explicitly"
    )
    # It routes the verifier past the parent-only sections.
    assert re.search(r"SKIP", body), "skill guard must tell the verifier to SKIP delegation"


def test_delegation_header_scoped_to_parent():
    """The dispatch section header must be unmistakably parent-only."""
    body = CANON_SKILL.read_text("utf-8")
    assert "## Subagent Delegation (parent orchestrator only)" in body, (
        "the Subagent Delegation header must be scoped to the parent orchestrator"
    )
    assert "## Subagent Delegation\n" not in body, (
        "the bare, unscoped 'Subagent Delegation' header must not remain"
    )


def test_guard_propagates_to_claude_adapter():
    """The Claude adapter (byte-identical to canon) carries the same guards.

    If the adapter tree is stale this fails, mirroring `build-adapters.py --check`
    for exactly the surfaces this fix touches.
    """
    if CLAUDE_SKILL.exists():
        skill = CLAUDE_SKILL.read_text("utf-8")
        assert "## Subagent Delegation (parent orchestrator only)" in skill
        assert "You ARE the `forge-verifier` subagent" in skill
    if CLAUDE_AGENT.exists():
        assert "you never dispatch" in CLAUDE_AGENT.read_text("utf-8").lower()
