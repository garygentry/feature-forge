"""Green/red guards on the always-loaded surface (spec 06 §7.3, REQ-PERF-02, REQ-MAINT-01).

Two things are paid on *every* session regardless of what the user asks for, so both are
pass/fail guards rather than review calls:

- **The 13 SKILL.md frontmatter descriptions**, which the harness loads up front to decide
  which skill (if any) to invoke. REQ-PERF-02 is a **non-increase** requirement, so the
  constant below is an exact ceiling, not a budget with headroom.
- **The SessionStart hook**, which runs on every session start. It must stay silent on the
  common path — and the silence has to be *proven*, not assumed.

The body caps are here for the same reason: ``skills/*/SKILL.md`` bodies are the largest
instruction surface a stage loads, and ``check-spec-purity.py`` Rule 4 (the CI-only gate)
is the only thing that measures them today. ``python3 -m pytest tests`` does not run that
script, so a body could sail past 300 lines in the inner loop and only go red on the PR.

Two earlier drafts of this guard were no-ops, and both traps are deliberately closed here:

- **V-007** pointed the hook test at ``hooks/session-start.py``, which does not exist,
  behind an existence check on that path — so the assertion never ran and the test was a
  permanent pass asserting nothing. ``hooks/hooks.json`` actually wires SessionStart to
  ``scripts/session-check.sh``, which is what runs below.
  ``test_the_hook_guards_cannot_degrade_to_a_skip`` greps this module's own source so no
  existence check or skip gate can be reintroduced around them.
- **V-008** set the frontmatter budget to 9000 against a measured 4688 — roughly 2x
  headroom, so it could not detect the growth REQ-PERF-02 forbids.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from _forge_paths import SCRIPTS, SKILLS, read

#: ``check-spec-purity.py`` Rule 4 limits (L89/L90). Duplicated rather than imported: that
#: script has a hyphenated module name, and a guard that broke on an import error would be
#: indistinguishable from one that passed.
MAX_BODY_LINES = 300
MAX_BODY_WORDS = 5000

#: Sum over all 13 ``skills/*/SKILL.md`` of the **raw** text following ``description: `` on
#: the frontmatter line, INCLUDING its surrounding double quotes. Measured 2026-07-28 at
#: 0.13.0 (``specs/context-efficiency/.reference/REMEASURE-0.13.0.md`` §Non-regression
#: baselines) and re-confirmed on the post-R1..R6 tree.
#:
#: The quote-INCLUSIVE measurement is deliberate. The quote-stripped sum is 4662; adopting
#: it would hand 26 chars of growth that no assertion could ever see, which defeats a
#: non-increase requirement. REQ-PERF-02 admits no headroom, so this is an exact ceiling:
#: a description that must legitimately change updates this constant in the SAME PR, with
#: the new measurement recorded, so the bump is reviewable.
FRONTMATTER_CHAR_BUDGET = 4688

#: 13 skills ship today. Pinned so that *deleting* a skill cannot silently create budget
#: headroom while the sum-based assertion stays green.
EXPECTED_SKILL_COUNT = 13

#: ``hooks/hooks.json`` wires SessionStart to
#: ``bash ${CLAUDE_PLUGIN_ROOT}/scripts/session-check.sh``. There is no
#: ``hooks/session-start.py`` — see the V-007 note in the module docstring.
HOOK = SCRIPTS / "session-check.sh"

SKILL_FILES = sorted(SKILLS.glob("*/SKILL.md"))
SKILL_IDS = [p.parent.name for p in SKILL_FILES]

_DESCRIPTION_RE = re.compile(r"^description:\s*(.+)$", re.M)


def _body_lines(text: str) -> list[str]:
    """Body = everything after the closing `---` (check-spec-purity Rule 4, spec 06 §1).

    Asserts the frontmatter block exists rather than tolerating its absence: a file with no
    frontmatter would otherwise be measured whole, inflating the count for a reason that
    has nothing to do with the cap.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    assert lines and lines[0].strip() == "---", "no frontmatter block"
    close = next(i for i, line in enumerate(lines[1:], 1) if line.strip() == "---")
    body = lines[close + 1 :]
    if body and body[-1] == "":
        body = body[:-1]
    return body


# --------------------------------------------------------------------------------------
# Guard 3 — SKILL.md body caps (check-spec-purity Rule 4, which pytest does not run)
# --------------------------------------------------------------------------------------


def test_the_expected_skills_are_present():
    assert len(SKILL_FILES) == EXPECTED_SKILL_COUNT, (
        f"expected {EXPECTED_SKILL_COUNT} skills, found {len(SKILL_IDS)}: {SKILL_IDS}"
    )


@pytest.mark.parametrize("skill", SKILL_FILES, ids=SKILL_IDS)
def test_skill_body_is_within_the_line_cap(skill):
    body = _body_lines(read(skill))
    assert len(body) <= MAX_BODY_LINES, (
        f"{skill.parent.name}: body is {len(body)} lines (cap {MAX_BODY_LINES})"
    )


@pytest.mark.parametrize("skill", SKILL_FILES, ids=SKILL_IDS)
def test_skill_body_is_within_the_word_cap(skill):
    # Word counting mirrors check-spec-purity exactly: per-line `.split()`, summed.
    body = _body_lines(read(skill))
    words = sum(len(line.split()) for line in body)
    assert words <= MAX_BODY_WORDS, (
        f"{skill.parent.name}: body is {words} words (cap {MAX_BODY_WORDS})"
    )


# --------------------------------------------------------------------------------------
# Guard 4 — the always-loaded surface: frontmatter budget + the SessionStart hook
# --------------------------------------------------------------------------------------


def test_frontmatter_description_budget_not_increased():
    total = 0
    counted = 0
    for skill in SKILL_FILES:
        m = _DESCRIPTION_RE.search(read(skill))
        if m:
            counted += 1
            total += len(m.group(1))  # raw, quotes included — see FRONTMATTER_CHAR_BUDGET
    assert counted == EXPECTED_SKILL_COUNT, (
        f"only {counted} of {EXPECTED_SKILL_COUNT} skills declare a description"
    )
    assert total <= FRONTMATTER_CHAR_BUDGET, (
        f"always-loaded frontmatter grew to {total} chars "
        f"(ceiling {FRONTMATTER_CHAR_BUDGET}); REQ-PERF-02 forbids an increase"
    )


def test_session_hook_is_silent_on_the_common_path(tmp_path):
    """A configured project sees nothing at session start — exit 0, empty stdout."""
    (tmp_path / "forge.config.json").write_text("{}", encoding="utf-8")
    r = subprocess.run(
        ["bash", str(HOOK)], cwd=tmp_path, capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr
    assert r.stdout == "", f"hook emitted output on the common path: {r.stdout!r}"


def test_session_hook_still_warns_when_config_is_missing(tmp_path):
    """Control: proves the silence above is real, not a hook that failed to run at all."""
    feature = tmp_path / "specs" / "demo"
    feature.mkdir(parents=True)
    (feature / ".pipeline-state.json").write_text("{}", encoding="utf-8")
    r = subprocess.run(
        ["bash", str(HOOK)], cwd=tmp_path, capture_output=True, text=True
    )
    assert r.returncode == 0, r.stderr
    assert "forge-init" in r.stdout, (
        f"hook did not point at forge-init when config was absent: {r.stdout!r}"
    )


def test_the_hook_guards_cannot_degrade_to_a_skip():
    """No existence check or skip gate may guard the two hook tests (finding V-007).

    An existence check on HOOK — or a skip marker — turns REQ-PERF-02 back into the review
    call it explicitly forbids, while still reading as coverage. The banned constructs are
    named only as data below, never spelled out in prose, so this guard cannot flag itself.
    """
    source = read(Path(__file__).resolve())
    # The call form is assembled at runtime so this list does not match itself.
    for banned in ("is_file", "exists", "skipif", "importorskip", "pytest.skip"):
        assert f"{banned}(" not in source, (
            f"{banned}() introduced in the always-loaded-surface guard — the hook tests "
            "must never be able to pass without executing the hook"
        )
