"""Drift guard for the R1 verification-checklist split.

``skills/forge-verify/references/verification-checklists.md`` (477 lines, every mode's
checks plus the orchestrator-only findings material) was split into six per-mode files
plus ``findings-template.md`` so a dispatched ``forge-verifier`` leaf loads exactly the
one checklist it needs. That split is only safe while three boundaries hold:

1. **No check was lost or renumbered.** Each mode file carries its full contiguous
   CHECK-ID run (REQ-R1-05).
2. **The modes stay disjoint**, and none of them leaks the orchestrator-only sections —
   the leaf must not receive parent-role material (the "Which role are you?" guard).
3. **The SKILL's expected-count table stays true.** Step 3 tells the verifier to
   go back if its executed count is "significantly below the expected total"; a table
   that drifts from the files turns that self-check into noise. The table is compared
   against the counts read **from the files**, never against a second hardcoded copy.

Runs against ``skills/`` (canon), not ``adapters/`` — the generated bundles are
``test_build_adapters.py``'s job. Stdlib only, so a bare ``python3 -m pytest tests``
runs it (`jsonschema` is absent in CI).
"""

from __future__ import annotations

import re

import pytest

from _forge_paths import SKILLS, read

FORGE_VERIFY = SKILLS / "forge-verify"
VC_DIR = FORGE_VERIFY / "references" / "verification-checklists"
FINDINGS_TEMPLATE = FORGE_VERIFY / "references" / "findings-template.md"
SKILL = FORGE_VERIFY / "SKILL.md"

# Mode -> (CHECK-ID letter, expected count). Seeded from the pre-split
# verification-checklists.md (130 unique IDs, the frozen REQ-R1-05 inventory);
# grown since as checks were added (backlog +B28 → 131 total). This is the ONLY
# place a count is written down — the SKILL's expected-count table is checked
# against the counts read back out of the files, not against this.
EXPECTED = {
    "prd": ("P", 15),
    "tech": ("T", 17),
    "specs": ("S", 38),
    "backlog": ("B", 28),
    "impl": ("I", 23),
    "epic": ("E", 10),
}

# Orchestrator-only sections that moved to findings-template.md. A mode file holding
# any of these would hand the leaf subagent parent-role material.
ORCH_HEADINGS = (
    "Findings Document Template",
    "Example Findings",
    "Epic Mode State Write Detail",
)

# The two directives lifted out of the monolith's L1-6 preamble into every mode file.
# Without them, prd/tech/specs/backlog mode lose the "no skipping" instruction and the
# stack-profile pointer when the monolith is deleted.
EXECUTE_EVERY = "Execute EVERY check — do not skip."
STACK_PROFILE_PATH = "references/stacks/{stack}.md"

MODES = sorted(EXPECTED)


def _ids(text: str, letter: str) -> list[str]:
    """Unique CHECK-IDs for one mode's letter, sorted.

    Deliberately unique-ing: impl and epic cross-reference CHECK-I21/I22 and
    CHECK-E06/E07 in surrounding prose, so raw occurrence counts run high (28 and 13).
    Those cross-references are part of the verbatim moved text and must survive.
    """
    return sorted(set(re.findall(rf"CHECK-{letter}\d\d", text)))


def _counted() -> dict[str, int]:
    """Count each mode's CHECK-IDs by reading the mode files."""
    return {mode: len(_ids(read(VC_DIR / f"{mode}.md"), letter))
            for mode, (letter, _) in EXPECTED.items()}


@pytest.mark.parametrize("mode", MODES)
def test_mode_checklist_is_complete_and_contiguous(mode):
    """Every mode file holds its full, contiguous CHECK-ID run (REQ-R1-05)."""
    letter, count = EXPECTED[mode]
    ids = _ids(read(VC_DIR / f"{mode}.md"), letter)
    assert len(ids) == count, (
        f"{mode}.md: expected {count} contiguous CHECK-{letter} IDs, found {len(ids)}"
    )
    assert ids == [f"CHECK-{letter}{n:02d}" for n in range(1, count + 1)], (
        f"{mode}.md: CHECK-{letter} IDs are not contiguous 01..{count:02d} — "
        f"something was dropped or renumbered: {ids}"
    )


def test_split_preserves_the_full_check_inventory():
    """The six files together carry the full 131-check inventory — none lost."""
    counted = _counted()
    assert sum(counted.values()) == 131, (
        f"split inventory drifted from 131 unique CHECK-IDs: {counted}"
    )


@pytest.mark.parametrize("mode", MODES)
def test_no_cross_mode_leakage(mode):
    """No mode file carries another mode's CHECK-IDs."""
    text = read(VC_DIR / f"{mode}.md")
    for other, (letter, _) in EXPECTED.items():
        if other == mode:
            continue
        assert not re.search(rf"CHECK-{letter}\d\d", text), (
            f"{mode}.md leaks a CHECK-{letter} id belonging to {other} mode"
        )


@pytest.mark.parametrize("mode", MODES)
def test_mode_files_hold_no_orchestrator_sections(mode):
    """Leaf-facing checklists must not carry parent-role material."""
    text = read(VC_DIR / f"{mode}.md")
    for heading in ORCH_HEADINGS:
        assert heading not in text, (
            f"{mode}.md leaks orchestrator-only section '{heading}' — the leaf "
            "subagent must not receive parent-role material"
        )


def test_findings_template_holds_every_orchestrator_section():
    """All three orchestrator-only sections landed in findings-template.md."""
    text = read(FINDINGS_TEMPLATE)
    for heading in ORCH_HEADINGS:
        assert heading in text, f"findings-template.md missing '{heading}'"


@pytest.mark.parametrize("mode", MODES)
def test_mode_files_carry_the_shared_directives(mode):
    """The two directives lifted from the monolith's preamble survive per mode."""
    text = read(VC_DIR / f"{mode}.md")
    assert EXECUTE_EVERY in text, (
        f"{mode}.md lost the shared '{EXECUTE_EVERY}' directive (source L3)"
    )
    stack_line = next(
        (ln for ln in text.splitlines()
         if ln.lstrip().startswith(">") and STACK_PROFILE_PATH in ln),
        None,
    )
    assert stack_line is not None, (
        f"{mode}.md lost the stack-profile blockquote citing {STACK_PROFILE_PATH} "
        "(source L5)"
    )
    assert "**Stack-specific details:**" in stack_line, (
        f"{mode}.md's stack-profile blockquote no longer matches the source wording: "
        f"{stack_line!r}"
    )


def test_skill_expected_count_table_matches_the_files():
    """Step 3's per-mode totals equal the counts read out of the mode files.

    Compared against `_counted()`, not against EXPECTED — so the same number is never
    hardcoded in two places, and a drift in either direction (a check removed from a
    file, or a stale figure in the table) goes red.
    """
    body = read(SKILL)
    counted = _counted()
    for mode, count in counted.items():
        m = re.search(rf"\b{mode}:\s*(~?)(\d+)\s*checks\b", body)
        assert m, f"SKILL Step-3 expected-count table has no entry for {mode}"
        assert not m.group(1), (
            f"SKILL expected-count table still hedges {mode} with '~' — the split "
            "made the totals exact"
        )
        assert int(m.group(2)) == count, (
            f"SKILL expected-count table says {mode}: {m.group(2)} checks, but "
            f"{mode}.md holds {count}"
        )


@pytest.mark.parametrize(
    "citation",
    [f"references/verification-checklists/{mode}.md" for mode in sorted(EXPECTED)]
    + ["references/findings-template.md"],
)
def test_every_split_file_is_cited_literally_by_the_skill(citation):
    """Each of the seven new paths is a literal citation, so adapter fan-out ships it.

    Literal, per-path citations only: build-adapters.py's fan-out regex has no comma in
    its character class, so a `{prd,tech,...}.md` brace list captures one bogus token
    and resolves nothing.
    """
    assert citation in read(SKILL), (
        f"{citation} is not cited literally in forge-verify/SKILL.md — adapter "
        "citation fan-out will not ship it"
    )
