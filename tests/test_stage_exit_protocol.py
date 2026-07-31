"""Drift guard for the Stage Exit Protocol.

The canonical blocks live once in ``references/stage-exit-protocol.md`` but are
**stamped verbatim** into stage-skill closings. The single-source guarantee is enforced
here: this test extracts each canonical block, renders each stamp site's slots, and
asserts the rendered block is present **verbatim** in the canon skill. An edit to the
reference that is not mirrored into a stamp site (or vice-versa) fails loudly.

Since the Scripted Stage Exit landed, every covered stage stamps only the short
``scripted-stage-exit-stamp`` (the conditional logic moved into
``forge-session.py stage-exit``; see tests/test_stage_exit.py for the directive
matrix). The loop was the last holdout: its step-6 epic handoff and its all-done result
report used to stamp the bespoke ``standard-exit-block`` / ``warm-exit-block``, and now
stamp the scripted block once, at its Step 7 close. Both bespoke blocks are deleted from
the reference, so the rows below assert their *absence* rather than their rendering.

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


# Every converted stage stamps the scripted exit; the one build-time slot is the
# per-stage stage-exit argument list.
_SCRIPTED_SITES = [
    ("skills/forge-0-epic/SKILL.md",
     '--feature "{epic}" --stage forge-0-epic --next-feature "{first-actionable-feature}"'),
    ("skills/forge-1-prd/SKILL.md", '--feature "{feature}" --stage forge-1-prd'),
    ("skills/forge-2-tech/SKILL.md", '--feature "{feature}" --stage forge-2-tech'),
    ("skills/forge-3-specs/SKILL.md", '--feature "{feature}" --stage forge-3-specs'),
    ("skills/forge-4-backlog/SKILL.md", '--feature "{feature}" --stage forge-4-backlog'),
    ("skills/forge-5-loop/SKILL.md",
     '--feature "{feature}" --stage forge-5-loop --outcome "{LoopOutcome}"'),
    ("skills/forge-6-docs/SKILL.md",
     '--feature "{feature}" --stage forge-6-docs --outcome "{DocsOutcome}"'),
]

# The two canon surfaces that carried the loop's retired bespoke blocks. They are the
# joined contract surface for forge-5-loop: SKILL.md stamps the scripted exit and
# result-reporting.md supplies the LoopOutcome it is invoked with.
_LOOP_SURFACE = [
    "skills/forge-5-loop/SKILL.md",
    "skills/forge-5-loop/references/result-reporting.md",
]

# Marker phrases unique to the two deleted blocks. Their reappearance anywhere in canon
# means a bespoke advancing contract came back.
_RETIRED_BLOCK_MARKERS = [
    "walk the user through the Stage Exit Protocol",
    "this is the one boundary where clearing before the next stage is optional",
]


@pytest.mark.parametrize("relpath,args", _SCRIPTED_SITES, ids=[s[0] for s in _SCRIPTED_SITES])
def test_scripted_stamp_stamped_verbatim(relpath, args):
    """Each authoring stage contains the rendered scripted-stage-exit stamp verbatim."""
    block = _render(_extract_block("scripted-stage-exit-stamp"), **{"stage-exit-args": args})
    body = (REPO_ROOT / relpath).read_text(encoding="utf-8")
    assert block in body, (
        f"{relpath} is out of sync with references/stage-exit-protocol.md "
        f"(scripted-stage-exit stamp). Re-stamp the block or update the reference."
    )


def test_the_retired_bespoke_blocks_are_gone_from_the_reference():
    """The standard and warm blocks no longer exist as stampable markered blocks.

    Replaces the two "…stamped verbatim" rows: with the loop converted, both bespoke
    blocks were deleted from the reference, so a surviving marker pair would mean an
    alternative advancing contract is stampable again.
    """
    text = REFERENCE.read_text(encoding="utf-8")
    for name in ("standard-exit-block", "warm-exit-block"):
        assert f"<!-- BEGIN: {name} -->" not in text, (
            f"the retired {name!r} marker pair is back in {REFERENCE.name} — the "
            "scripted stamp is the only advancing contract for all nine covered exits"
        )


def test_no_canon_surface_carries_a_retired_bespoke_block():
    """No skill re-introduces a hand-written standard or warm terminal block."""
    surfaces = sorted((REPO_ROOT / "skills").rglob("*.md")) + [REFERENCE]
    for path in surfaces:
        body = path.read_text(encoding="utf-8")
        for marker in _RETIRED_BLOCK_MARKERS:
            assert marker not in body, (
                f"{path.relative_to(REPO_ROOT)} carries retired bespoke-block prose "
                f"({marker!r}) — close the stage with the scripted stamp instead"
            )


@pytest.mark.parametrize("relpath", _LOOP_SURFACE)
def test_the_loop_surface_has_no_hand_written_next_command(relpath):
    """The loop routes only through the script — no fenced/bulleted next command."""
    body = (REPO_ROOT / relpath).read_text(encoding="utf-8")
    for command in ("/feature-forge:forge-6-docs {feature}", "/feature-forge:forge-1-prd {chosen}"):
        assert command not in body, (
            f"{relpath} still names {command!r} as a hand-written next step — the "
            "stage-exit router owns loop routing for every LoopOutcome"
        )


def test_the_loop_surface_covers_every_loop_outcome():
    """All five LoopOutcome values have a documented selection rule.

    Replaces the assertion that the loop stamps bespoke blocks: the loop's contract
    surface is now the outcome ladder plus the single scripted invocation.
    """
    surface = "\n".join(
        (REPO_ROOT / relpath).read_text(encoding="utf-8") for relpath in _LOOP_SURFACE
    )
    for outcome in ("complete", "partial", "blocked", "needs-human", "deferred"):
        assert f"`{outcome}`" in surface, (
            f"LoopOutcome {outcome!r} has no selection rule on the forge-5-loop surface"
        )
    assert surface.count("--stage forge-5-loop --outcome") == 1, (
        "the loop must emit exactly one stage-exit invocation per run"
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


def test_the_docs_surface_covers_both_docs_outcomes():
    """forge-6-docs closes through the script, with `complete` and `blocked` both documented.

    Replaces the assertion that forge-6-docs is terminal: it is now the ninth covered
    exit, so the positive obligations are a single scripted invocation plus a documented
    selection rule for each `DocsOutcome`.
    """
    body = (REPO_ROOT / "skills/forge-6-docs/SKILL.md").read_text(encoding="utf-8")
    for outcome in ("complete", "blocked"):
        assert f"`{outcome}`" in body, (
            f"DocsOutcome {outcome!r} has no selection rule on the forge-6-docs surface"
        )
    assert body.count("--stage forge-6-docs --outcome") == 1, (
        "forge-6-docs must emit exactly one stage-exit invocation per run"
    )


def test_the_docs_surface_routes_epic_members_from_live_status():
    """The docs terminus must not route from Step 1's pre-mutation render-status snapshot."""
    body = (REPO_ROOT / "skills/forge-6-docs/SKILL.md").read_text(encoding="utf-8")
    assert "Do **not** reuse Step 1's `render-status` snapshot" in body, (
        "forge-6-docs may only route an epic member from live status read at exit time"
    )


def test_every_authoring_stage_is_covered():
    """Guard against a new authoring stage silently missing an exit block.

    If someone adds a forge-N authoring stage skill, they must either stamp a block
    or explicitly add it to the terminal allow-list below — this fails until they do.

    The allow-list is empty since forge-6-docs was converted: every production stage
    now closes through the scripted exit.
    """
    stamped = {relpath for relpath, _ in _SCRIPTED_SITES}
    terminal: set[str] = set()
    authoring = {
        f"skills/{name}/SKILL.md"
        for name in (
            "forge-0-epic", "forge-1-prd", "forge-2-tech", "forge-3-specs",
            "forge-4-backlog", "forge-5-loop", "forge-6-docs",
        )
    }
    uncovered = authoring - stamped - terminal
    assert not uncovered, f"authoring stages missing an exit block: {sorted(uncovered)}"
