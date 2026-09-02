"""Guard: the Interaction Capability Ladder is stated once in canon (#244 P2, #252).

PROTECTS (the enumerated contract — the whole of it):
  1. The canonical section (`references/shared-conventions.md` § Interaction Capability
     Ladder) states every required clause.
  2. Every canon file that actually poses an `AskUserQuestion` prompt points at the
     canonical section **by title** — a bare citation of the file it lives in does not
     count (11+ bodies already cite `shared-conventions.md` for unrelated reasons).
  3. The roster cannot shrink to a vacuous size.
  4. The rung-1 mandate in the User Input Protocol is softened to a pointer, never to a
     weaker MUST.
  5. No skill body reintroduces its own local three-rung enumeration — the ladder has one
     canonical home.
  6. The Codex overlay's rung-3 wording is rung-aware, not the pre-#252 blanket mandate.
  7. This guard cannot be skipped or disabled.

NON-GOALS (never a finding against this guard):
  - Exact-markdown fidelity beyond the clause/pointer tokens below.
  - The wording of any surface's own rung-3 default beyond citing the ladder's title.
  - Runtime behavior of the ladder (no harness here to execute a skill against a
    fixture; that is the live headless smoke in `plans/federated-bubbling-micali.md`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from _forge_paths import REFERENCES, REPO_ROOT, SKILLS, read

#: The one canonical statement of interaction capability.
PROTOCOL: Final[Path] = REFERENCES / "shared-conventions.md"

#: The canonical section's title. A pointer surface names the rule by this string rather
#: than by a path, so moving or renaming the file cannot leave a stale pointer silently
#: passing, and a bare `shared-conventions.md` citation (used for unrelated reasons by
#: many bodies) cannot masquerade as coverage.
CANONICAL_SECTION_TITLE: Final[str] = "Interaction Capability Ladder"

#: Emphasis markers carry no obligation, so they are removed before matching — the same
#: normalisation `test_capability_determination_prose.py` uses.
_EMPHASIS: Final[tuple[str, ...]] = ("**", "*", "`", "_")

#: Each clause of the ladder, with the obligation it carries and the phrasings that
#: express it. Matched against the canonical section only, never against a surface.
CLAUSE_PROBES: Final[dict[str, tuple[str, tuple[str, ...]]]] = {
    "rung1": (
        "rung 1 is a structured question tool present, use it",
        ("rung 1 structured question tool present",),
    ),
    "rung2": (
        "rung 2 is no structured tool but the host can still prompt and be answered",
        ("rung 2 no structured tool, but the host",),
    ),
    "rung3": (
        "rung 3 is genuinely non-interactive",
        ("rung 3 genuinely non-interactive",),
    ),
    "host-independent": (
        "the ladder reads correctly independent of the host name",
        ("independent of the host name",),
    ),
    "host-static": (
        "--host is static per adapter bundle",
        ("is static per adapter bundle",),
    ),
    "rung-dynamic": (
        "rung is dynamic, self-assessed once per turn",
        ("rung is dynamic",),
    ),
    "conservative-default": (
        "the rung-3 declared default is always the no-write / no-proceed option",
        ("no-write / no-proceed",),
    ),
    "never-advances": (
        "the declared default never advances a pipeline stage",
        ("never advances a pipeline stage",),
    ),
    "must-state": (
        "the rung-3 outcome must be stated in the output",
        ("must be stated in the output",),
    ),
    "no-default": (
        "an undefaultable interview question aborts with a stated reason",
        ("no-default: abort",),
    ),
    "pi-stripped": (
        "Pi strips AskUserQuestion from the tool list in non-interactive mode",
        ("stripped from the tool list",),
    ),
    "pi-error-literal": (
        "the Pi non-interactive error is the rung-3 backstop, never a decline",
        ("error: ui not available (running in non-interactive mode)",),
    ),
    "codex-exec": (
        "codex exec is the Codex rung-3 detection surface",
        ("codex exec",),
    ),
}

#: Non-vacuity floor. A roster smaller than this would let the surface check pass
#: without examining the pipeline it exists to cover — #252 measured 20 non-exempt
#: files at landing time.
MIN_ROSTER_SIZE: Final[int] = 15

#: Files that mention `AskUserQuestion` only as example/template prose, never as a real
#: prompting site — a pointer requirement here would be noise, not coverage.
META_EXEMPT: Final[frozenset[str]] = frozenset({
    "skills/forge-verify/references/findings-template.md",
})

#: Canon roots the roster is computed from (never `adapters/` — generated, host-degraded).
_ROSTER_ROOTS: Final[tuple[Path, ...]] = (SKILLS, REFERENCES)


def _normalised(text: str) -> str:
    """Return text with emphasis dropped, whitespace collapsed and case folded."""
    for marker in _EMPHASIS:
        text = text.replace(marker, "")
    return " ".join(text.split()).lower()


def _markdown_section(text: str, heading: str) -> str:
    """Return the body of the ``## {heading}`` section, up to the next ``## `` heading."""
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


def _computed_roster() -> list[Path]:
    """Every canon `.md` file that poses an `AskUserQuestion` prompt, minus META_EXEMPT.

    Computed, not hardcoded (unlike `test_capability_determination_prose.py`'s imported
    `CANONICAL_EXIT_SITES`) — a new prompting site is caught by construction rather than
    requiring a roster edit to be remembered alongside it.
    """
    found: list[Path] = []
    for root in _ROSTER_ROOTS:
        for path in sorted(root.rglob("*.md")):
            if "AskUserQuestion" not in read(path):
                continue
            rel = path.relative_to(REPO_ROOT).as_posix()
            if rel in META_EXEMPT:
                continue
            found.append(path)
    return found


def test_the_canonical_ladder_states_every_clause() -> None:
    """The single canonical section carries every obligation the ladder imposes."""
    section = _markdown_section(read(PROTOCOL), CANONICAL_SECTION_TITLE)
    assert section, (
        f"{PROTOCOL.name} has no '## {CANONICAL_SECTION_TITLE}' section — the ladder "
        "has no canonical home, and every pointer to it resolves to nothing"
    )
    normalised = _normalised(section)
    for clause, (obligation, probes) in CLAUSE_PROBES.items():
        assert any(probe in normalised for probe in probes), (
            f"{PROTOCOL.name} § {CANONICAL_SECTION_TITLE}: clause ({clause}) is no "
            f"longer stated — {obligation}. None of these phrasings survive in the "
            f"section: {list(probes)}"
        )


def test_every_prompting_surface_points_at_the_ladder_by_title() -> None:
    """No canon file that poses a real question silently omits the ladder pointer.

    Strict title-pointer rule: a bare `shared-conventions.md` citation is NOT coverage —
    many bodies already cite that file for the User Input Protocol, Decision Support, or
    the Pipeline State Protocol, none of which says anything about rung 2/3. Only the
    literal section title counts.
    """
    roster = _computed_roster()
    silent = [
        str(p.relative_to(REPO_ROOT))
        for p in roster
        if CANONICAL_SECTION_TITLE.lower() not in _normalised(read(p))
    ]
    assert not silent, (
        "these canon files pose an AskUserQuestion prompt but never point at "
        f"'{CANONICAL_SECTION_TITLE}' by title, so a rung-3 session hitting them has no "
        f"declared default to fall back on: {silent}"
    )


def test_the_roster_is_not_vacuous() -> None:
    """A shrunken roster would pass the surface check without examining anything."""
    roster = _computed_roster()
    assert len(roster) >= MIN_ROSTER_SIZE, (
        f"the computed AskUserQuestion roster carries {len(roster)} files, below the "
        f"floor of {MIN_ROSTER_SIZE} — the surface check above has stopped covering the "
        "pipeline rather than prompting sites having genuinely shrunk"
    )


def test_user_input_protocol_keeps_rung1_must() -> None:
    """Softening the guardrail to point at the ladder never weakens the rung-1 MUST.

    P2 qualifies the mandate ("whenever it is present in your tool surface") so it reads
    correctly on a host without the tool, but a Claude session that DOES have the tool
    must still read an unambiguous MUST — the ladder only ever loosens the rung-2/3 path.
    """
    section = _markdown_section(read(PROTOCOL), "User Input Protocol")
    assert section, f"{PROTOCOL.name} has no '## User Input Protocol' section"
    assert "MUST use the `AskUserQuestion` tool" in section, (
        f"{PROTOCOL.name} § User Input Protocol dropped the rung-1 MUST — a host that "
        "HAS the structured tool must still be told to use it unconditionally"
    )
    assert CANONICAL_SECTION_TITLE in section, (
        f"{PROTOCOL.name} § User Input Protocol no longer points at "
        f"'{CANONICAL_SECTION_TITLE}' for the non-rung-1 path"
    )


def test_no_body_retains_local_rung_ladder() -> None:
    """No SKILL.md body re-enumerates its own Rung 1/2/3 — the ladder has one home.

    Scoped to bodies (not references): several references legitimately mention all three
    rung numbers in passing while citing or annotating the canonical ladder
    (`stage-exit-protocol.md`, `preflight-and-self-heal.md`) — that is citation, not
    duplication. A SKILL.md body doing the same would mean a second full local ladder,
    which is exactly what forge-init's pre-#252 prose was and #252 retires.
    """
    offenders = []
    for skill_md in sorted(SKILLS.glob("*/SKILL.md")):
        text = _normalised(read(skill_md))
        if all(f"rung {n}" in text for n in (1, 2, 3)):
            offenders.append(str(skill_md.relative_to(REPO_ROOT)))
    assert not offenders, (
        f"these SKILL.md bodies enumerate all three rungs locally: {offenders} — the "
        f"Interaction Capability Ladder has one canonical home "
        f"({PROTOCOL.relative_to(REPO_ROOT)}); a body should cite it by title instead"
    )


def test_codex_overlay_is_rung_aware() -> None:
    """`_HOST_NOTES_CODEX` states the rung-3 default, not the pre-#252 blanket mandate."""
    source = read(REPO_ROOT / "scripts" / "build-adapters.py")
    start = source.index("_HOST_NOTES_CODEX = (")
    end = source.index("_HOST_NOTES_NEUTRAL = (", start)
    overlay = _normalised(source[start:end])
    assert "codex exec" in overlay, (
        "_HOST_NOTES_CODEX no longer names `codex exec` as the rung-3 trigger — a Codex "
        "reader has no way to tell which invocation shape is non-interactive"
    )
    assert "declared" in overlay, (
        "_HOST_NOTES_CODEX no longer mentions the ladder's declared default — the "
        "overlay must tell a rung-3 Codex session to take it, not stall"
    )
    assert "never skip a required question" not in overlay, (
        "_HOST_NOTES_CODEX still carries the pre-#252 blanket 'never skip a required "
        "question or assume an answer' mandate — that is unconditionally true only at "
        "rung 2 (interactive Codex); under `codex exec` (rung 3) the ladder's declared "
        "default must be taken, not treated as skipped"
    )


def test_this_guard_is_not_skippable() -> None:
    """No skip gate may be introduced here — an unskippable guard is the whole point."""
    source = read(Path(__file__).resolve())
    for banned in ("skipif", "importorskip", "pytest.skip"):
        assert f"{banned}(" not in source, f"{banned} gate introduced in the drift guard"
