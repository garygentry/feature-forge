"""Drift guard: the two flat scripts' duplicated stage/status constants stay equal.

`scripts/forge-session.py` owns stage order (`PRODUCTION_STAGES`, "the ONE place stage
order lives") and the forge-verify status vocabulary (`KNOWN_VERIFY_STATUSES`).
`scripts/epic-manifest.py` keeps a copy of each — flat, self-contained scripts have no
shared import module, since every one of them is copied verbatim into the six per-agent
adapter bundles. Both copies say "mirrors …" in a comment; neither was enforced.

Why that matters (item 020, finding V-004):

- `epic-manifest.py::_next_production_stage` DERIVES "what runs next" by walking its
  `_PRODUCTION_STAGES`. Insert a stage in `forge-session.py` only and the epic router
  silently skips it — regressing exactly the `_next_command` defect item 020 fixed.
- A `KNOWN_VERIFY_STATUSES` divergence poisons the epic rollup and dependency gates
  (#148), which is why both files already carry a "byte-identical copy" note.

`tests/test_agent_targets_parity.py` documents the precedent: `AGENT_TARGETS` drifted
once already and silently dropped `adapters/pi/` coverage. Same shape, same remedy.

Follows that module's constraints: the literals are regex-extracted and
`ast.literal_eval`'d rather than imported (both filenames are hyphenated, and both
scripts do work at module scope), and nothing here may grow a skip gate.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from _forge_paths import REPO_ROOT, SCRIPTS, read

SESSION = SCRIPTS / "forge-session.py"
MANIFEST = SCRIPTS / "epic-manifest.py"

#: The six production stages in pipeline order. Order is SEMANTIC — `next_stage`,
#: `verify_state`, `stage_exit` and `_next_production_stage` all walk it — so this is
#: an ordered comparison, never a set comparison.
EXPECTED_STAGES = (
    "forge-1-prd",
    "forge-2-tech",
    "forge-3-specs",
    "forge-4-backlog",
    "forge-5-loop",
    "forge-6-docs",
)

#: SOURCE OF TRUTH: references/pipeline-state-schema.json
#: (definitions.verifyEntry.properties.status.enum).
EXPECTED_VERIFY_STATUSES = frozenset(
    {"pending", "passed", "findings-reported", "findings-applied", "skipped"}
)


def _assignment_re(name: str, opener: str, closer: str) -> re.Pattern[str]:
    """Match a module-scope ``NAME[: annotation] = <opener>…<closer>`` literal.

    The annotation is optional: `forge-session.py` writes
    ``PRODUCTION_STAGES: Final[tuple[str, ...]] = (…)`` while `epic-manifest.py` writes
    ``_PRODUCTION_STAGES: Final = (…)``.
    """
    return re.compile(
        rf"^{re.escape(name)}(?:\s*:[^=\n]+)?\s*=\s*"
        rf"(?:frozenset\(\s*)?({re.escape(opener)}[^{re.escape(closer)}]*{re.escape(closer)})",
        re.MULTILINE,
    )


def _parse_literal(path: Path, name: str, opener: str, closer: str) -> object:
    """Return the module-scope literal assigned to ``name`` in ``path``.

    Never imports the file: both script names are hyphenated (so unimportable by
    `import`) and both execute module-scope work.
    """
    pattern = _assignment_re(name, opener, closer)
    matches = pattern.findall(read(path))
    rel = path.relative_to(REPO_ROOT).as_posix()
    assert matches, f"{rel}: no module-scope `{name} = ...` assignment found"
    assert len(matches) == 1, f"{rel}: {name} assigned {len(matches)}x — which wins?"
    return ast.literal_eval(matches[0])


def _stages(path: Path, name: str) -> tuple[str, ...]:
    value = _parse_literal(path, name, "(", ")")
    assert isinstance(value, tuple), f"{path.name}: {name} is not a tuple literal"
    return value


def _verify_statuses(path: Path) -> frozenset[str]:
    value = _parse_literal(path, "KNOWN_VERIFY_STATUSES", "{", "}")
    assert isinstance(value, set), f"{path.name}: KNOWN_VERIFY_STATUSES is not a set literal"
    return frozenset(value)


# --------------------------------------------------------------------------------------
# Guard 1 — ordered production stages
# --------------------------------------------------------------------------------------


def test_forge_session_declares_the_six_production_stages():
    """The owning script's PRODUCTION_STAGES is the six-tuple, in pipeline order."""
    assert _stages(SESSION, "PRODUCTION_STAGES") == EXPECTED_STAGES


def test_epic_manifest_declares_the_six_production_stages():
    """The mirror copy is the same six-tuple — a short/reordered copy misroutes."""
    assert _stages(MANIFEST, "_PRODUCTION_STAGES") == EXPECTED_STAGES


def test_the_two_stage_tuples_are_equal():
    """Order-sensitive equality: a new stage cannot land in only one of the two."""
    assert _stages(MANIFEST, "_PRODUCTION_STAGES") == _stages(SESSION, "PRODUCTION_STAGES")


# --------------------------------------------------------------------------------------
# Guard 2 — forge-verify status vocabulary
# --------------------------------------------------------------------------------------


def test_the_two_verify_status_sets_are_equal():
    """Both copies of KNOWN_VERIFY_STATUSES agree with each other and with the schema."""
    session = _verify_statuses(SESSION)
    manifest = _verify_statuses(MANIFEST)
    assert session == EXPECTED_VERIFY_STATUSES
    assert manifest == EXPECTED_VERIFY_STATUSES
    assert session == manifest


# --------------------------------------------------------------------------------------
# Guard 3 — the guard itself
# --------------------------------------------------------------------------------------


def test_this_guard_is_not_skippable():
    """No skip gate may be introduced here — an unskippable guard is the whole point."""
    source = read(Path(__file__).resolve())
    for banned in ("skipif", "importorskip", "pytest.skip"):
        # Only the prose above may mention them; no call may be made.
        assert f"{banned}(" not in source, f"{banned} gate introduced in the drift guard"
