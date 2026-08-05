"""Guard: the capability-determination rule is stated once in canon.

PROTECTS (the enumerated contract — the whole of it):
  1. The canonical section states every required clause.
  2. Every canonical exit surface carries a paragraph or a pointer.
  3. The roster cannot shrink to a vacuous size.
  4. This guard cannot be skipped or disabled.

NON-GOALS (never a finding against this guard):
  - Exact-markdown fidelity: clause-fragment matching, bold-marker
    presence, per-surface formatting equality.
  - Which of paragraph-or-pointer any given surface chooses.
  - The wording of any surface's restatement.
  - Whether a surface's prose is well written or complete beyond
    the clause set.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from _forge_paths import REFERENCES, REPO_ROOT, read
from test_stage_exit_protocol import CANONICAL_EXIT_SITES, CanonicalExitSite

#: The one canonical statement of the capability rule.
PROTOCOL: Final[Path] = REFERENCES / "stage-exit-protocol.md"

#: The canonical section's title. A pointer surface names the rule by this string
#: rather than by a path, so moving or renaming the file cannot leave a stale
#: pointer silently passing.
CANONICAL_SECTION_TITLE: Final[str] = "Host and capability determination"

#: How a surface announces that it determines capability itself, in normalised
#: form. Both forms introduce the same paragraph; one surface inlines the flag
#: name and the rest do not.
CAPABILITY_LEAD_INS: Final[tuple[str, ...]] = (
    "pass interactive only when",
    "pass --verify-capability interactive only when",
)

#: Emphasis markers carry no obligation, so they are removed before matching.
#: Removing them is what makes bold-marker presence unassertable by construction.
_EMPHASIS: Final[tuple[str, ...]] = ("**", "*", "`", "_")

#: Each clause of the rule, with the obligation it carries and the phrasings that
#: express it. Matched against the canonical section only, never against a
#: surface: the clause set has one home, and this is the assertion that says so.
CLAUSE_PROBES: Final[dict[str, tuple[str, tuple[str, ...]]]] = {
    "a": (
        "capability (b) is a permission test, not a tool-presence test",
        (
            "tests permission, not tool presence",
            "may i dispatch forge-verifier right now",
        ),
    ),
    "b": (
        "a consent requirement is interactive, not manual; manual needs neither a "
        "question mechanism nor permitted dispatch",
        (
            "a consent requirement is interactive, not manual",
            "no question mechanism and no permitted dispatch",
        ),
    ),
    "c1a": (
        "an auto-verify directive under a dispatch bar is routed through the gate",
        ("presented through the standard verify gate",),
    ),
    "c1b": (
        "the gate's affirmative choice dispatches the verifier rather than printing "
        "a command for the user to run later",
        ("dispatched on the affirmative choice",),
    ),
    "c2": (
        "that directive is never silently skipped",
        ("never grounds to skip verification",),
    ),
    "c3": (
        "it is never resolved by advancing past unresolved verification",
        ("advancing to the production successor",),
    ),
}

#: Non-vacuity floor. A roster smaller than the canonical exit table would let the
#: surface check pass without examining the pipeline it exists to cover.
MIN_ROSTER_SIZE: Final[int] = 9


def _normalised(text: str) -> str:
    """Return text with emphasis dropped, whitespace collapsed and case folded.

    Matching happens on this form so an assertion expresses an obligation rather
    than a formatting choice.

    Args:
        text: Raw markdown read from a canon file.

    Returns:
        A single-spaced, lower-cased rendering with emphasis markers removed.
    """
    for marker in _EMPHASIS:
        text = text.replace(marker, "")
    return " ".join(text.split()).lower()


def _markdown_section(text: str, heading: str) -> str:
    """Return the body of the ``## {heading}`` section, up to the next ``## `` heading.

    Nested ``###`` subsections belong to the section and are kept, so the rule and
    its recovery path are read as one unit.

    Args:
        text: The full text of a canon file.
        heading: The section title, without its ``## `` prefix.

    Returns:
        The section body, or ``""`` when the file carries no such heading — which
        fails the caller's assertion rather than passing vacuously.
    """
    lines = text.replace("\r\n", "\n").split("\n")
    body: list[str] = []
    inside = False
    for line in lines:
        if line.startswith("## "):
            if inside:
                break
            inside = line[3:].strip() == heading
            continue
        if inside:
            body.append(line)
    return "\n".join(body)


def _capability_evidence(text: str) -> tuple[str, str] | None:
    """Return how one canon file satisfies paragraph-or-pointer, or ``None``.

    Blocks are blank-line separated, matching how these bodies are written. The
    first block carrying either form wins; a file may carry both.

    Args:
        text: The full text of a canon contract file.

    Returns:
        ``("paragraph", block)`` when a block announces that this surface
        determines capability itself, ``("pointer", block)`` when a block names the
        canonical section by title, or ``None`` when no block does either.
    """
    for block in text.replace("\r\n", "\n").split("\n\n"):
        normalised = _normalised(block)
        if any(lead in normalised for lead in CAPABILITY_LEAD_INS):
            return "paragraph", block
        if _normalised(CANONICAL_SECTION_TITLE) in normalised:
            return "pointer", block
    return None


def _site_evidence(site: CanonicalExitSite) -> tuple[str, str] | None:
    """Return the first contract file carrying this site's capability evidence.

    A site owns one or more canon files, and the rule has to appear in one of them
    rather than in every one.

    Args:
        site: One entry of the canonical exit table.

    Returns:
        ``(relpath, kind)`` for the first file carrying a paragraph or a pointer,
        or ``None`` when no file of this site does.

    Raises:
        AssertionError: A declared contract file is missing from the repository.
            Raised by ``_forge_paths.read``, which fails loudly rather than
            skipping — a silently skipped file reads as coverage while asserting
            nothing.
    """
    for relpath in site.contract_paths:
        found = _capability_evidence(read(REPO_ROOT / relpath))
        if found is not None:
            return relpath, found[0]
    return None


def test_the_canonical_rule_states_every_clause() -> None:
    """The single canonical section carries every obligation the rule imposes.

    This is the only assertion in the suite that reads clause content, and it
    reads it in one place. Adding a second target is what two sources of truth
    look like in code.
    """
    section = _markdown_section(read(PROTOCOL), CANONICAL_SECTION_TITLE)
    assert section, (
        f"{PROTOCOL.name} has no '## {CANONICAL_SECTION_TITLE}' section — the rule "
        "has no canonical home, and every pointer to it resolves to nothing"
    )
    normalised = _normalised(section)
    for clause, (obligation, probes) in CLAUSE_PROBES.items():
        assert any(probe in normalised for probe in probes), (
            f"{PROTOCOL.name} § {CANONICAL_SECTION_TITLE}: clause ({clause}) is no "
            f"longer stated — {obligation}. None of these phrasings survive in the "
            f"section: {list(probes)}"
        )


def test_every_surface_has_a_paragraph_or_pointer() -> None:
    """No canonical exit surface silently carries neither the rule nor a pointer.

    Which of the two forms a surface chooses is not this guard's business; that a
    surface has resolved the question one way or the other is.
    """
    silent = [
        site.skill for site in CANONICAL_EXIT_SITES if _site_evidence(site) is None
    ]
    assert not silent, (
        "these canonical exit surfaces neither state the capability rule nor name "
        f"'{CANONICAL_SECTION_TITLE}', so the stage closes on an undetermined "
        f"--verify-capability: {silent}"
    )


def test_the_guard_is_not_vacuous() -> None:
    """A shrunken roster would pass the surface check without examining anything."""
    assert len(CANONICAL_EXIT_SITES) >= MIN_ROSTER_SIZE, (
        f"the canonical exit table carries {len(CANONICAL_EXIT_SITES)} sites, below "
        f"the floor of {MIN_ROSTER_SIZE} — the surface check above has stopped "
        "covering the pipeline rather than the prose having been removed from canon"
    )


def test_this_guard_is_not_skippable() -> None:
    """No skip gate may be introduced here — an unskippable guard is the whole point."""
    source = read(Path(__file__).resolve())
    for banned in ("skipif", "importorskip", "pytest.skip"):
        # Only prose may mention them; no call may be made.
        assert f"{banned}(" not in source, f"{banned} gate introduced in the drift guard"
