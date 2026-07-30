"""Catch-all citation guards for the skill bodies (spec 06 §5, REQ-MAINT-01).

Two directions, both needed, neither sufficient alone:

1. **Forward** — every literal ``references/...md`` citation in every ``skills/*/SKILL.md``
   names a file that actually exists, skill-local or shared. A citation is not decoration:
   ``scripts/build-adapters.py`` fans shared references out **by citation**, so a dangling
   path ships a bundle whose instructions point at nothing on all six hosts.
2. **Reverse** — every reference file this feature created or moved is still cited by at
   least one skill body. Drop the citation and the file silently stops shipping while the
   forward guard stays perfectly green.

Regex provenance (finding V-030). The pattern below was validated against the
**pre-feature baseline commit** ``9a29e846ed510c3b245876a9bf4cc73b8cb60951``, where it
resolves **118 citations with zero misses**, and again against the post-R1..R6 tree
(measured 2026-07-29), where it resolves **140 with zero misses**. The count moves
whenever canon adds or drops a citation — which is why nothing here pins a total.

The two refinements over a naive ``references/([A-Za-z0-9_][A-Za-z0-9_./{}*-]*)`` are both
load-bearing; the naive form produces **3 false positives on the baseline** and would ship
red on day one:

- the ``(?<![./\\w-])`` lookbehind skips *project-level* paths — ``.agents/references/…``
  and ``.claude/references/…`` in ``forge-2-tech`` — which deliberately do not exist in the
  bundle (2 of the 3);
- the lazy ``…*?\\.md`` stop keeps a sentence-final period out of the filename
  (``…read references/runner-contract.md.`` in ``forge-5-loop``) (the 3rd).

Both are pinned below by fixture strings rather than by live line numbers, which drift.
"""

from __future__ import annotations

import re

from _forge_paths import REFERENCES, SKILLS, read

# See the module docstring for the provenance of every character in this pattern.
CITE_RE = re.compile(r"(?<![./\w-])references/([A-Za-z0-9_][A-Za-z0-9_./{}*-]*?\.md)\b")

#: Every new/moved reference file this feature introduced. Each must be cited by at least
#: one skill body or citation fan-out stops shipping it (spec 06 §5). Six mode files from
#: R1's split, its orchestrator-only template, R6's gated extract, and R3's gated read.
NEW_FILES: tuple[str, ...] = (
    "verification-checklists/prd.md",
    "verification-checklists/tech.md",
    "verification-checklists/specs.md",
    "verification-checklists/backlog.md",
    "verification-checklists/impl.md",
    "verification-checklists/epic.md",
    "findings-template.md",
    "agent-selection.md",
    "process-overview.md",
)

#: Non-vacuity floor, NOT a pinned total. A regex that matched nothing would satisfy every
#: "zero unresolved" assertion below trivially, so the forward guard needs a lower bound —
#: but the exact count is a moving target (118 at the pre-feature baseline, 140 now), so
#: asserting equality would go red on the next legitimate citation change.
MIN_EXPECTED_CITATIONS = 100

# Verbatim from `skills/forge-2-tech/SKILL.md` at the baseline commit: three candidate
# stack-decisions paths, two of them project-level and intentionally absent from the
# bundle. Kept as a fixture so the assertion survives the line moving.
PROJECT_LEVEL_FIXTURE = (
    "Look for a project stack-decisions file, first existing path wins: "
    "`.feature-forge/stack-decisions.md` (preferred), then "
    "`.agents/references/stack-decisions.md`, then "
    "`.claude/references/stack-decisions.md` (legacy alias)."
)

# Verbatim from `skills/forge-5-loop/SKILL.md` at the baseline commit: a citation that ends
# a sentence, so the filename is immediately followed by a period.
SENTENCE_FINAL_FIXTURE = (
    "provider default) and the full optional-flags catalog, read "
    "references/runner-contract.md."
)


def _skill_bodies() -> list[tuple[str, str]]:
    """(skill name, body text) for all 13 skills, in a stable order."""
    return [(p.parent.name, read(p)) for p in sorted(SKILLS.glob("*/SKILL.md"))]


def _citations(body: str) -> list[str]:
    """Literal (non-templated) `references/...md` paths cited by one body."""
    return [
        m.group(1)
        for m in CITE_RE.finditer(body)
        if not any(ch in m.group(1) for ch in "{}*")
    ]


def _resolves(skill_dir_name: str, rel: str) -> bool:
    local = SKILLS / skill_dir_name / "references" / rel
    shared = REFERENCES / rel
    return local.is_file() or shared.is_file()


# --------------------------------------------------------------------------------------
# Guard 1 — forward resolution
# --------------------------------------------------------------------------------------


def test_every_citation_in_every_skill_body_resolves():
    """Zero unresolved citations across all 13 bodies. No total is asserted."""
    unresolved = [
        f"{name}: references/{rel}"
        for name, body in _skill_bodies()
        for rel in _citations(body)
        if not _resolves(name, rel)
    ]
    assert not unresolved, "skill bodies cite reference files that do not exist:\n  " + (
        "\n  ".join(unresolved)
    )


def test_the_forward_guard_is_not_vacuous():
    """A regex that matched nothing would pass the guard above without asserting anything."""
    total = sum(len(_citations(body)) for _, body in _skill_bodies())
    assert total >= MIN_EXPECTED_CITATIONS, (
        f"only {total} literal references/*.md citations found across the skill bodies "
        f"(floor {MIN_EXPECTED_CITATIONS}) — the pattern has almost certainly stopped "
        "matching rather than canon having shrunk this far"
    )


def test_project_level_reference_paths_are_not_flagged():
    """`.agents/references/…` and `.claude/references/…` are project paths, not bundle paths.

    They intentionally do not exist in any bundle, so a pattern that captured them would
    report two permanent misses (2 of the naive pattern's 3 false positives).
    """
    assert CITE_RE.findall(PROJECT_LEVEL_FIXTURE) == [], (
        "the lookbehind stopped skipping project-level .agents/ and .claude/ paths"
    )


def test_a_sentence_final_period_is_not_swallowed_into_the_filename():
    """`…read references/runner-contract.md.` cites `runner-contract.md`, not `…md.`.

    The trailing period is punctuation; capturing it yields a path that can never resolve
    (the naive pattern's 3rd false positive).
    """
    assert CITE_RE.findall(SENTENCE_FINAL_FIXTURE) == ["runner-contract.md"]


# --------------------------------------------------------------------------------------
# Guard 2 — reverse coverage
# --------------------------------------------------------------------------------------


def test_every_new_or_moved_reference_file_is_still_cited():
    """Lose the citation and the file stops shipping, silently — the forward guard cannot see it."""
    bodies = "\n".join(body for _, body in _skill_bodies())
    uncited = [rel for rel in NEW_FILES if f"references/{rel}" not in bodies]
    assert not uncited, (
        "no skill body cites these reference files, so citation fan-out will not ship "
        "them:\n  " + "\n  ".join(uncited)
    )


def test_every_new_or_moved_reference_file_exists():
    """The reverse guard asserts a citation; this asserts the citation has a target."""
    missing = [
        rel
        for rel in NEW_FILES
        if not (
            (SKILLS / "forge-verify" / "references" / rel).is_file()
            or (SKILLS / "forge-5-loop" / "references" / rel).is_file()
            or (REFERENCES / rel).is_file()
        )
    ]
    assert not missing, "new/moved reference files missing from canon: " + ", ".join(
        missing
    )
