"""Order guard for forge-5-loop's `LoopOutcome` ladder (result-reporting.md, #339).

The ladder is first-match-wins, so its rung ORDER is the contract. Following rauf's
supervisor decision table, the unfinished-runner rung (a pending review, or a reported
`loopState` that is not a clean finish) must sit above the needs-human / blocked /
deferred rungs: a crashed, stopped or limit-halted runner is recovered first, and a
declined pending-review resume closes `partial --cause review-pending` even when items
are blocked. `resolved` stays on top and `complete` stays last.

Stdlib only; asserts against `skills/` canon, never `adapters/`.
"""

from __future__ import annotations

import re

from _forge_paths import SKILLS, read

RESULT_REPORTING = SKILLS / "forge-5-loop" / "references" / "result-reporting.md"
LOOP_SKILL = SKILLS / "forge-5-loop" / "SKILL.md"

EXPECTED_RUNGS = [
    "`resolved`",
    "`partial` (runner not finished)",
    "`needs-human`",
    "`blocked`",
    "`deferred`",
    "`partial`",
    "`complete`",
]


def _ladder_rungs() -> list[str]:
    """The bold rung labels of the numbered ladder, in document order."""
    text = read(RESULT_REPORTING)
    section = text.split("## Selecting the one `LoopOutcome` (Step 7)", 1)[1]
    section = section.split("\n## ", 1)[0]
    return re.findall(r"^\d+\. \*\*(.+?)\*\*", section, flags=re.MULTILINE)


def test_ladder_rungs_are_in_contract_order():
    assert _ladder_rungs() == EXPECTED_RUNGS


def test_unfinished_runner_rung_names_both_triggers_and_causes():
    text = read(RESULT_REPORTING)
    rung = text.split("2. **`partial` (runner not finished)**", 1)[1].split("\n3. ", 1)[0]
    for needle in ("reviewPending", "loopState", "--cause review-pending",
                   "--cause runner-stopped", "ITERATIONS_COMPLETE"):
        assert needle in rung, needle


def test_skill_step7_summary_matches_ladder_order():
    body = read(LOOP_SKILL)
    assert (
        "`resolved` → unfinished-runner `partial` → `needs-human` → `blocked` → "
        "`deferred` → `partial` → `complete`"
    ) in body
