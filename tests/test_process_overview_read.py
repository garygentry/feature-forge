"""Drift guard for the R3 conditional ``process-overview.md`` read.

The navigator used to open ``references/process-overview.md`` as an unconditional
setup step, so every invocation — including a routine dashboard render, which is by
far the most common one — paid for a 143-line architecture document it never used.
R3 moves the read site behind an explicit "is the user asking how the pipeline
works?" branch (REQ-R3-01, ``05-instruction-relocations.md`` §2).

Two boundaries have to hold together, and either one alone is a silent regression:

1. **The literal citation survives.** ``build-adapters.py``'s
   ``_fan_out_shared_references()`` discovers shared reference files by grepping the
   skill body for literal ``references/...`` paths. Move the read site but drop the
   citation string and the file simply stops shipping to the non-Claude adapters —
   a failure that never surfaces on this host.
2. **The read stays gated.** A citation reintroduced as a bare imperative
   ("read `references/process-overview.md`") restores the unconditional load while
   keeping guard 1 green, so presence alone is not coverage.

Runs against ``skills/`` (canon), never ``adapters/``. Stdlib only, so a bare
``python3 -m pytest tests`` runs it (`jsonschema` is absent in CI).
"""

from __future__ import annotations

from _forge_paths import REFERENCES, SKILLS, read

CITATION = "references/process-overview.md"
NAVIGATOR = SKILLS / "forge" / "SKILL.md"

# The pre-R3 unconditional setup line, verbatim. Kept as a literal so a revert —
# or a re-introduction under a new heading — is caught by text, not by position.
UNCONDITIONAL_LINE = "For pipeline architecture details, read `references/process-overview.md`."

# The read must be reached through a condition, not asserted as a step. One of these
# gating cues has to appear in the citing sentence itself.
GATING_CUES = ("only if", "only when", "if the user is asking", "when the user asks")

# ...and the condition has to be *this* condition: an architecture / how-it-works
# question, not some unrelated branch that happens to be phrased conditionally.
TOPIC_CUES = ("how the pipeline works", "architecture", "stage ordering", "how it works")


def _citing_sentences() -> list[str]:
    """Every sentence in the navigator body that names process-overview.md.

    Sentence-scoped rather than window-scoped: a fixed character window around the
    citation would pass on an unrelated conditional in a neighbouring paragraph.
    """
    body = read(NAVIGATOR)
    # Markdown bold markers end a clause but not a sentence; split on hard stops only.
    sentences = [s.replace("\n", " ") for s in body.replace(". ", ".\n@@\n").split("\n@@\n")]
    return [s for s in sentences if CITATION in s]


def test_process_overview_is_still_cited_so_it_still_ships():
    body = read(NAVIGATOR)
    assert CITATION in body, (
        f"{NAVIGATOR.name} no longer cites {CITATION} — citation fan-out will stop "
        "shipping the file to the non-Claude adapter bundles (REQ-PORT-01)"
    )


def test_the_unconditional_setup_read_is_gone():
    body = read(NAVIGATOR)
    assert UNCONDITIONAL_LINE not in body, (
        "the pre-R3 unconditional setup read is back in the navigator body — every "
        "dashboard render pays for process-overview.md again (REQ-R3-01)"
    )


def test_every_citation_sits_inside_a_how_it_works_conditional():
    citing = _citing_sentences()
    assert citing, f"no sentence in {NAVIGATOR.name} cites {CITATION}"
    for sentence in citing:
        lowered = sentence.lower()
        assert any(cue in lowered for cue in GATING_CUES), (
            f"{CITATION} is cited as a bare imperative, not under a condition: "
            f"{sentence.strip()!r}"
        )
        assert any(cue in lowered for cue in TOPIC_CUES), (
            f"{CITATION}'s condition does not name the architecture / how-it-works "
            f"trigger R3 gates on: {sentence.strip()!r}"
        )


def test_process_overview_itself_is_unchanged():
    """R3 relocates the read site only — the file's content is out of scope."""
    assert len(read(REFERENCES / "process-overview.md").splitlines()) == 143
