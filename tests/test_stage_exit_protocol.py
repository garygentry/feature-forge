"""Drift guard for the Stage Exit Protocol.

The canonical blocks live once in ``references/stage-exit-protocol.md`` but are
**stamped verbatim** into stage-skill closings. The single-source guarantee is enforced
here: this test extracts each canonical block, renders each stamp site's slots, and
asserts the rendered block is present **verbatim** in the canon skill. An edit to the
reference that is not mirrored into a stamp site (or vice-versa) fails loudly.

Since the Scripted Stage Exit landed, the five authoring stages stamp only the short
``scripted-stage-exit-stamp`` (the conditional logic moved into
``forge-session.py stage-exit``; see tests/test_stage_exit.py for the directive
matrix). The loop keeps the ``standard-exit-block`` (step-6 epic-member handoff) and
the ``warm-exit-block`` (all-done closing) — those rows are unchanged.

Runs against ``skills/`` (canon), not ``adapters/`` — the adapter copies legitimately
differ (``/clear`` and ``--host claude`` are host-term-degraded on non-Claude targets;
that degradation is covered in tests/test_build_adapters.py). No third-party deps, so
it runs under a bare ``python3 -m pytest tests``.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
REFERENCE = REPO_ROOT / "references" / "stage-exit-protocol.md"


def _extract_block(name: str) -> str:
    """Return the text between ``<!-- BEGIN: {name} -->`` and ``<!-- END: {name} -->``."""
    text = REFERENCE.read_text(encoding="utf-8")
    m = re.search(rf"<!-- BEGIN: {name} -->\n(.*?)\n<!-- END: {name} -->", text, re.S)
    assert m, f"marker pair for {name!r} not found in {REFERENCE}"
    return m.group(1)


def _render(block: str, **slots: str) -> str:
    """Substitute build-time template slots (mirrors the stamping logic).

    ``{feature}`` / ``{epic}`` / ``{specsDir}`` and similar are left untouched —
    they are runtime placeholders the skill resolves, not build-time slots.
    """
    out = block
    for key, value in slots.items():
        out = out.replace("{" + key + "}", value)
    return out


# The five authoring stages stamp the scripted exit; the one build-time slot is the
# per-stage stage-exit argument list.
_SCRIPTED_SITES = [
    ("skills/forge-0-epic/SKILL.md",
     '--feature "{epic}" --stage forge-0-epic --next-feature "{first-actionable-feature}"'),
    ("skills/forge-1-prd/SKILL.md", '--feature "{feature}" --stage forge-1-prd'),
    ("skills/forge-2-tech/SKILL.md", '--feature "{feature}" --stage forge-2-tech'),
    ("skills/forge-3-specs/SKILL.md", '--feature "{feature}" --stage forge-3-specs'),
    ("skills/forge-4-backlog/SKILL.md", '--feature "{feature}" --stage forge-4-backlog'),
]

# The loop's step-6 epic-member handoff still stamps the standard block (unchanged row).
_STANDARD_SITES = [
    ("skills/forge-5-loop/SKILL.md", dict(
        stage="feature {feature}'s loop",
        verify="/feature-forge:forge-verify {feature} impl",
        nxt="/feature-forge:forge-1-prd {chosen}")),
]

# The warm-acceptable variant is stamped at the loop → forge-6-docs boundary, which the
# loop renders via its all-done result template (unchanged row).
_WARM_SITE = ("skills/forge-5-loop/references/result-reporting.md", dict(
    nxt="/feature-forge:forge-6-docs {feature}"))


@pytest.mark.parametrize("relpath,args", _SCRIPTED_SITES, ids=[s[0] for s in _SCRIPTED_SITES])
def test_scripted_stamp_stamped_verbatim(relpath, args):
    """Each authoring stage contains the rendered scripted-stage-exit stamp verbatim."""
    block = _render(_extract_block("scripted-stage-exit-stamp"), **{"stage-exit-args": args})
    body = (REPO_ROOT / relpath).read_text(encoding="utf-8")
    assert block in body, (
        f"{relpath} is out of sync with references/stage-exit-protocol.md "
        f"(scripted-stage-exit stamp). Re-stamp the block or update the reference."
    )


@pytest.mark.parametrize("relpath,slots", _STANDARD_SITES, ids=[s[0] for s in _STANDARD_SITES])
def test_standard_block_stamped_verbatim(relpath, slots):
    """The loop's handoff stamp contains the rendered canonical standard block verbatim."""
    block = _render(_extract_block("standard-exit-block"),
                    stage=slots["stage"],
                    **{"verify-command": slots["verify"], "next-command": slots["nxt"]})
    body = (REPO_ROOT / relpath).read_text(encoding="utf-8")
    assert block in body, (
        f"{relpath} is out of sync with references/stage-exit-protocol.md "
        f"(standard block). Re-stamp the block or update the reference."
    )


def test_warm_block_stamped_verbatim():
    """The loop's all-done result template contains the rendered warm variant verbatim."""
    relpath, slots = _WARM_SITE
    block = _render(_extract_block("warm-exit-block"), **{"next-command": slots["nxt"]})
    body = (REPO_ROOT / relpath).read_text(encoding="utf-8")
    assert block in body, (
        f"{relpath} is out of sync with references/stage-exit-protocol.md (warm block)."
    )


def test_no_skill_retains_the_old_in_stage_block():
    """The prose in-stage auto-verify block is fully retired.

    Its semantics live in the stage-exit directive contract now; a resurrected
    prose copy would fork the logic (the exact drift this migration removes).
    """
    for skill in sorted((REPO_ROOT / "skills").glob("*/SKILL.md")):
        body = skill.read_text(encoding="utf-8")
        assert "In-stage auto-verify" not in body, (
            f"{skill.relative_to(REPO_ROOT)} still carries the retired prose "
            "in-stage auto-verify block — stage-exit directives replace it."
        )


def test_authoring_stages_do_not_stamp_standard_block():
    """forge-0..4 no longer carry the standard block (scripted exit replaces it)."""
    header = "walk the user through the Stage Exit Protocol"
    for relpath, _ in _SCRIPTED_SITES:
        body = (REPO_ROOT / relpath).read_text(encoding="utf-8")
        assert header not in body, (
            f"{relpath} still stamps the standard exit block — the scripted "
            "stage exit replaces it on authoring stages."
        )


def test_forge_6_docs_is_terminal():
    """forge-6-docs stamps NO exit block — it is the warm variant's target, not a site."""
    body = (REPO_ROOT / "skills/forge-6-docs/SKILL.md").read_text(encoding="utf-8")
    assert "walk the user through the Stage Exit Protocol" not in body
    assert "Close this stage with the Scripted Stage Exit" not in body, (
        "forge-6-docs must stay terminal (no exit block of any kind)"
    )


def test_every_authoring_stage_is_covered():
    """Guard against a new authoring stage silently missing an exit block.

    If someone adds a forge-N authoring stage skill, they must either stamp a block
    or explicitly add it to the terminal allow-list below — this fails until they do.
    """
    stamped = {relpath for relpath, _ in _SCRIPTED_SITES}
    stamped |= {relpath for relpath, _ in _STANDARD_SITES}
    stamped.add(_WARM_SITE[0])
    terminal = {"skills/forge-6-docs/SKILL.md"}
    authoring = {
        f"skills/{name}/SKILL.md"
        for name in (
            "forge-0-epic", "forge-1-prd", "forge-2-tech", "forge-3-specs",
            "forge-4-backlog", "forge-5-loop", "forge-6-docs",
        )
    }
    uncovered = authoring - stamped - terminal
    assert not uncovered, f"authoring stages missing an exit block: {sorted(uncovered)}"
