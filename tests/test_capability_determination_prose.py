"""Drift guard for the capability-determination contract (spec 07 §6.2, REQ-EXIT-07).

`--verify-capability` is the one contract in this feature that is **prose-only and
degrades silently**. Every other exit invariant has a script behind it: pass a bad
`--outcome` and `stage-exit` exits 2; drop the stamp and `test_stage_exit_protocol.py`
fails. Capability has no such backstop. The agent reads the prose, decides
`interactive` or `manual`, and passes the result — so a surface whose prose has rotted
produces a model that self-reports `manual`, prints a copy-paste command instead of
dispatching the clean-room verifier, and looks entirely well-behaved while doing it.
Nothing downstream can tell that apart from a genuinely incapable session.

The contract has already been misread once, which is why §6.2 singles it out. Three
clauses must survive in every capability-determining surface:

(a) **Capability is a permission test, not a tool-presence test.** "May I dispatch
    `forge-verifier` right now", never "is a dispatch tool in my tool surface."
(b) **Consent-gated dispatch is `interactive`.** A session that may dispatch only once
    the user asks still has a question mechanism to ask with, so the gate's affirmative
    choice supplies the request. `manual` is reserved for *no question mechanism* **and**
    *no permitted dispatch*.
(c) **An auto-verify directive under a no-unsolicited-dispatch bar goes through the
    gate** and is dispatched on the affirmative — never silently skipped, and never
    resolved by advancing to the production successor.

The roster is **derived, not listed**: it comes from
`test_stage_exit_protocol.CANONICAL_EXIT_SITES` filtered to the surfaces that actually
determine capability (detected by their "Pass … only when" lead-in). A second
hand-maintained copy of the skill list is exactly the drift these guards exist to catch.

Surfaces that *delegate* the decision — `forge-5-loop` and `forge-6-docs` point at
`references/stage-exit-protocol.md` §"Host and capability determination" rather than
restating the rule — are deliberately out of the roster; they are covered by the shared
rule this module also pins. `forge-0-epic` passes `--verify-capability` while carrying
neither the prose nor a pointer to it; that is noted in `SURFACES_WITHOUT_PROSE` rather
than silently swept in, because asserting the clauses there would fail on canon as it
stands and asserting nothing would hide it.

Asserts against `skills/` and `references/` (canon), never `adapters/`. Stdlib only, so
a bare `python3 -m pytest tests` runs it. No skip gate may be introduced — see
`test_this_guard_is_not_skippable` at the bottom.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import pytest
from _forge_paths import REFERENCES, REPO_ROOT, read
from test_stage_exit_protocol import CANONICAL_EXIT_SITES

CONVENTIONS = REFERENCES / "shared-conventions.md"
PROTOCOL = REFERENCES / "stage-exit-protocol.md"

#: How a surface announces that it determines capability itself. Both forms introduce
#: the same paragraph; `forge-verify` inlines the flag name, the rest do not.
CAPABILITY_LEAD_INS: Final[tuple[str, ...]] = (
    "Pass `interactive` only when",
    "Pass `--verify-capability interactive` only when",
)

#: The three clauses, each satisfied by ANY of its accepted phrasings. Fragments are
#: short and load-bearing so the guard survives rewording around them but not deletion
#: of the requirement. Multiple phrasings per clause are not slack: the surfaces really
#: do say the same thing differently — `forge-verify` writes "Reserve `manual` for no
#: question mechanism and no permitted dispatch" where the authoring stages write
#: "`interactive`, not `manual`" — and forcing one wording would be a rewrite of canon
#: disguised as a test.
CLAUSES: Final[dict[str, tuple[str, tuple[str, ...]]]] = {
    "a": (
        "capability is a permission test, not a tool-presence test",
        ("dispatch, not a listed tool",),
    ),
    "b": (
        "consent-gated dispatch is `interactive`; `manual` needs neither mechanism",
        ("`interactive`, not `manual`", "Reserve `manual`"),
    ),
    "c": (
        "an auto-verify directive under a dispatch bar goes through the gate",
        (
            "choice 2 omitted",
            "dispatched on the affirmative",
            "Standard Verify Gate first when you may not dispatch unsolicited",
            "never grounds to fence the production successor",
        ),
    ),
}

#: Non-vacuity floor. Six surfaces determine capability today (the four authoring
#: stages plus `forge-verify` and `forge-fix`). A filter that stopped matching would
#: leave an empty roster and pass every assertion below without checking anything.
MIN_CAPABILITY_SURFACES: Final[int] = 6

#: Covered by the shared rule instead of restating it. `forge-5-loop` and `forge-6-docs`
#: carry a "Determine `{verify-capability}` per …" pointer; `forge-0-epic` carries
#: neither pointer nor prose, which is a real hole in canon rather than a design choice —
#: recorded here so it stays visible instead of being quietly excluded.
SURFACES_WITHOUT_PROSE: Final[frozenset[str]] = frozenset(
    {
        "skills/forge-0-epic/SKILL.md",
        "skills/forge-5-loop/SKILL.md",
        "skills/forge-6-docs/SKILL.md",
    }
)


def _assert_capability_prose(surface: str, where: str) -> None:
    """Raise `AssertionError` unless `surface` states all three clauses.

    Takes the surface's **text**, not a path, so the negative controls can call it on
    mutated copies without ever writing to the repository.
    """
    for clause, (description, fragments) in CLAUSES.items():
        assert any(fragment in surface for fragment in fragments), (
            f"{where}: capability clause ({clause}) is gone — {description}. "
            f"None of these phrasings survive: {list(fragments)}"
        )


def _capability_surfaces() -> list[tuple[str, str]]:
    """(relpath, text) for every canon exit surface that determines capability itself."""
    found = []
    for site in CANONICAL_EXIT_SITES:
        for relpath in site.contract_paths:
            text = read(REPO_ROOT / relpath)
            if any(lead in text for lead in CAPABILITY_LEAD_INS):
                found.append((relpath, text))
    return found


# --------------------------------------------------------------------------------------
# Guard 1 — every determining surface states all three clauses
# --------------------------------------------------------------------------------------


def test_every_capability_determining_surface_states_all_three_clauses():
    """The clause set survives in each skill that decides `--verify-capability` itself."""
    surfaces = _capability_surfaces()
    for relpath, text in surfaces:
        _assert_capability_prose(text, relpath)


def test_the_shared_capability_rule_is_documented():
    """The rule the delegating skills point at still states the clauses.

    `forge-5-loop` and `forge-6-docs` do not restate the contract; they defer to
    `references/`. If the shared statement rots, those two are left deferring to
    nothing and Guard 1 would not notice — it only walks the surfaces that restate.
    """
    _assert_capability_prose(read(CONVENTIONS), "references/shared-conventions.md")
    assert "Host and capability determination" in read(PROTOCOL), (
        "references/stage-exit-protocol.md lost the section the delegating skills "
        "name by title — their pointer now resolves to nothing"
    )


def test_the_delegating_surfaces_still_point_somewhere_real():
    """A surface with no capability prose of its own must name where the rule lives."""
    orphaned = []
    for relpath in sorted(SURFACES_WITHOUT_PROSE - {"skills/forge-0-epic/SKILL.md"}):
        text = read(REPO_ROOT / relpath)
        if "Host and capability determination" not in text:
            orphaned.append(relpath)
    assert not orphaned, (
        "these surfaces neither state the capability rule nor point at it:\n  "
        + "\n  ".join(orphaned)
    )


def test_the_roster_is_derived_not_listed():
    """The surface list comes from the shared exit table, not a second hand-kept copy."""
    covered = {relpath for relpath, _ in _capability_surfaces()}
    known = {relpath for site in CANONICAL_EXIT_SITES for relpath in site.contract_paths}
    assert covered <= known, (
        f"capability surfaces outside the canonical exit table: {sorted(covered - known)}"
    )
    assert not covered & SURFACES_WITHOUT_PROSE, (
        "a surface recorded as having no capability prose now matches the lead-in "
        f"filter — update SURFACES_WITHOUT_PROSE: {sorted(covered & SURFACES_WITHOUT_PROSE)}"
    )


def test_the_guard_is_not_vacuous():
    """An empty or shrunken roster would pass Guard 1 without asserting anything."""
    total = len(_capability_surfaces())
    assert total >= MIN_CAPABILITY_SURFACES, (
        f"only {total} capability-determining surfaces found (floor "
        f"{MIN_CAPABILITY_SURFACES}) — the lead-in filter has almost certainly stopped "
        "matching rather than the prose having been removed from canon"
    )


# --------------------------------------------------------------------------------------
# Guard 2 — the three negative controls spec 07 §6.2 mandates
#
# Each operates on a COPIED string. None writes to the repository.
# --------------------------------------------------------------------------------------


def _representative_surface() -> str:
    """The text of one real determining surface, used as the mutation base."""
    surfaces = _capability_surfaces()
    assert surfaces, "no capability-determining surface to mutate"
    for relpath, text in surfaces:
        if relpath == "skills/forge-1-prd/SKILL.md":
            return text
    return surfaces[0][1]


def test_rewriting_clause_b_to_tool_presence_wording_fails_the_guard():
    """Negative control 1: capability restated as "do I have the tool" must be caught."""
    base = _representative_surface()
    _assert_capability_prose(base, "control-base")  # the base really is compliant

    mutated = base.replace(
        "dispatch, not a listed tool",
        "dispatch, which requires the tool to be listed in my tool surface",
    )
    assert mutated != base, "clause (a)'s wording moved — this control now mutates nothing"
    with pytest.raises(AssertionError, match=r"clause \(a\)"):
        _assert_capability_prose(mutated, "control-1")


def test_downgrading_the_consent_case_to_manual_fails_the_guard():
    """Negative control 2: calling a consent-gated session `manual` must be caught."""
    base = _representative_surface()
    mutated = base.replace("`interactive`, not `manual`", "`manual`, not `interactive`")
    mutated = mutated.replace("Reserve `manual`", "Prefer `manual`")
    assert mutated != base, "clause (b)'s wording moved — this control now mutates nothing"
    with pytest.raises(AssertionError, match=r"clause \(b\)"):
        _assert_capability_prose(mutated, "control-2")


def test_deleting_the_auto_path_through_the_gate_fails_the_guard():
    """Negative control 3: dropping the "auto directive still goes through the gate"
    sentence must be caught."""
    base = _representative_surface()
    mutated = base
    for fragment in CLAUSES["c"][1]:
        mutated = mutated.replace(fragment, "")
    assert mutated != base, "clause (c)'s wording moved — this control now mutates nothing"
    with pytest.raises(AssertionError, match=r"clause \(c\)"):
        _assert_capability_prose(mutated, "control-3")


# --------------------------------------------------------------------------------------
# Guard 3 — the guard itself
# --------------------------------------------------------------------------------------


def test_this_guard_is_not_skippable():
    """No skip gate may be introduced here — an unskippable guard is the whole point."""
    source = read(Path(__file__).resolve())
    for banned in ("skipif", "importorskip", "pytest.skip"):
        # Only the prose above may mention them; no call may be made.
        assert f"{banned}(" not in source, f"{banned} gate introduced in the drift guard"
