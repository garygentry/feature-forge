"""Drift guard for the Stage Exit Protocol (REMEDIATION Chunk 2, item 2.5).

The canonical exit block lives once in ``references/stage-exit-protocol.md`` but is
**stamped verbatim** into every stage-skill closing — a runtime ``references/`` include
would not survive the adapter build, which flattens skills into ``adapters/<agent>/``.
So the single-source guarantee is enforced here instead: this test extracts the two
canonical blocks (standard + warm), renders each stamp site's slots, and asserts the
rendered block is present **verbatim** in the canon skill. An edit to the reference that
is not mirrored into a stamp site (or vice-versa) fails loudly.

Runs against ``skills/`` (canon), not ``adapters/`` — the adapter copies legitimately
differ (``/clear`` is host-term-degraded on non-Claude targets; that degradation is
covered in tests/test_build_adapters.py). No third-party deps, so it runs under a bare
``python3 -m pytest tests``.
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


def _render(block: str, *, stage: str | None = None, verify: str | None = None,
            nxt: str | None = None) -> str:
    """Substitute the three template slots (mirrors the stamping logic).

    ``{feature}`` / ``{epic}`` and similar are left untouched — they are runtime
    placeholders the skill resolves, not build-time slots.
    """
    out = block
    if stage is not None:
        out = out.replace("{stage}", stage)
    if verify is not None:
        out = out.replace("{verify-command}", verify)
    if nxt is not None:
        out = out.replace("{next-command}", nxt)
    return out


# (relative path, block name, slot kwargs). One row per stamp site in 2.2.
_STANDARD_SITES = [
    ("skills/forge-0-epic/SKILL.md", dict(
        stage="the epic decomposition",
        verify="/feature-forge:forge-verify {epic}",
        nxt="/feature-forge:forge-1-prd {first-actionable-feature}")),
    ("skills/forge-1-prd/SKILL.md", dict(
        stage="the PRD",
        verify="/feature-forge:forge-verify {feature}",
        nxt="/feature-forge:forge-2-tech {feature}")),
    ("skills/forge-2-tech/SKILL.md", dict(
        stage="the tech spec",
        verify="/feature-forge:forge-verify {feature}",
        nxt="/feature-forge:forge-3-specs {feature}")),
    ("skills/forge-3-specs/SKILL.md", dict(
        stage="the implementation specs",
        verify="/feature-forge:forge-verify {feature}",
        nxt="/feature-forge:forge-4-backlog {feature}")),
    ("skills/forge-4-backlog/SKILL.md", dict(
        stage="the backlog",
        verify="/feature-forge:forge-verify {feature}",
        nxt="/feature-forge:forge-5-loop {feature}")),
    # forge-5-loop step-6 epic-member handoff (finishing A → starting B's PRD).
    ("skills/forge-5-loop/SKILL.md", dict(
        stage="feature {feature}'s loop",
        verify="/feature-forge:forge-verify {feature} impl",
        nxt="/feature-forge:forge-1-prd {chosen}")),
]

# The warm-acceptable variant is stamped at the loop → forge-6-docs boundary, which the
# loop renders via its all-done result template.
_WARM_SITE = ("skills/forge-5-loop/references/result-reporting.md", dict(
    nxt="/feature-forge:forge-6-docs {feature}"))


@pytest.mark.parametrize("relpath,slots", _STANDARD_SITES, ids=[s[0] for s in _STANDARD_SITES])
def test_standard_block_stamped_verbatim(relpath, slots):
    """Each standard stamp site contains the rendered canonical standard block verbatim."""
    block = _render(_extract_block("standard-exit-block"), **slots)
    body = (REPO_ROOT / relpath).read_text(encoding="utf-8")
    assert block in body, (
        f"{relpath} is out of sync with references/stage-exit-protocol.md "
        f"(standard block). Re-stamp the block or update the reference."
    )


def test_warm_block_stamped_verbatim():
    """The loop's all-done result template contains the rendered warm variant verbatim."""
    relpath, slots = _WARM_SITE
    block = _render(_extract_block("warm-exit-block"), **slots)
    body = (REPO_ROOT / relpath).read_text(encoding="utf-8")
    assert block in body, (
        f"{relpath} is out of sync with references/stage-exit-protocol.md (warm block)."
    )


def test_forge_6_docs_is_terminal():
    """forge-6-docs stamps NO exit block — it is the warm variant's target, not a site."""
    body = (REPO_ROOT / "skills/forge-6-docs/SKILL.md").read_text(encoding="utf-8")
    header = "walk the user through the Stage Exit Protocol"
    assert header not in body, "forge-6-docs must stay terminal (no Stage Exit Protocol block)"


def test_every_authoring_stage_is_covered():
    """Guard against a new authoring stage silently missing the exit block.

    If someone adds a forge-N authoring stage skill, they must either stamp the block
    or explicitly add it to the terminal allow-list below — this fails until they do.
    """
    stamped = {relpath for relpath, _ in _STANDARD_SITES}
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
