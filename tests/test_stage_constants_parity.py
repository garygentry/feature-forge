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

Guard 4 is the one exception to the no-import rule, and deliberately so: it asserts
`VERIFY_MODE_TO_STAGE` against `get_args(VerifyMode)` / `get_args(ProductionStage)`,
and `get_args` needs the runtime alias objects, not their source text. It loads
`forge-session.py` through `importlib.util.spec_from_file_location` — the convention
the rest of the suite already uses for the hyphenated scripts.
"""

from __future__ import annotations

import ast
import importlib.util
import json
import re
from pathlib import Path
from typing import get_args

from _forge_paths import REFERENCES, REPO_ROOT, SCRIPTS, read

SESSION = SCRIPTS / "forge-session.py"
MANIFEST = SCRIPTS / "epic-manifest.py"
STATE_SCHEMA = REFERENCES / "pipeline-state-schema.json"

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

#: The six statuses of `00-core-definitions.md` §2's `VerifyStatus`. SOURCE OF TRUTH:
#: references/pipeline-state-schema.json (definitions.verifyEntry.properties.status.enum),
#: which this module reads directly rather than maintaining an unconnected third
#: vocabulary — the literal below only pins WHICH six, so a silent shrink in both the
#: schema and the scripts still fails here.
EXPECTED_VERIFY_STATUSES = frozenset(
    {
        "pending",
        "auto-verify-pending",
        "passed",
        "findings-reported",
        "findings-applied",
        "skipped",
    }
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


def _schema_verify_statuses() -> frozenset[str]:
    """The verifyEntry status enum — the declared source of truth for both copies."""
    schema = json.loads(read(STATE_SCHEMA))
    enum = schema["definitions"]["verifyEntry"]["properties"]["status"]["enum"]
    assert len(enum) == len(set(enum)), f"duplicate value in the verifyEntry enum: {enum}"
    return frozenset(enum)


def _load_session_module():
    """Import `forge-session.py` by path (its name is hyphenated, so unimportable).

    Only Guard 4 needs this: `get_args` operates on the live `Literal` alias, which
    no amount of regex extraction can produce.
    """
    spec = importlib.util.spec_from_file_location("forge_session_parity", SESSION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_both_copies_match_the_schema_enum():
    """The schema is the declared source of truth; neither copy may outrun it.

    Comparing the scripts to each other only proves they drifted together. This is
    the assertion that catches a status added to one script but never to
    `references/pipeline-state-schema.json` — where `auto-verify-pending` has to
    exist before any writer may persist it (REQ-DEBT-02/05).
    """
    schema = _schema_verify_statuses()
    assert schema == EXPECTED_VERIFY_STATUSES, (
        "references/pipeline-state-schema.json's verifyEntry status enum is no longer "
        f"the six statuses of 00 §2: {sorted(schema)}"
    )
    assert _verify_statuses(SESSION) == schema
    assert _verify_statuses(MANIFEST) == schema


def test_the_two_copies_are_byte_identical():
    """`KNOWN_VERIFY_STATUSES` is a mirrored copy, so the SOURCE TEXT must match.

    Set equality tolerates a reordered or reformatted copy; the byte comparison is
    what keeps the two blocks diffable and makes a one-sided edit obvious.
    """
    blocks = {}
    for path in (SESSION, MANIFEST):
        pattern = _assignment_re("KNOWN_VERIFY_STATUSES", "{", "}")
        matches = pattern.findall(read(path))
        assert len(matches) == 1, f"{path.name}: KNOWN_VERIFY_STATUSES assigned != 1x"
        blocks[path.name] = matches[0]
    session, manifest = blocks[SESSION.name], blocks[MANIFEST.name]
    assert session == manifest, (
        "the two KNOWN_VERIFY_STATUSES literals diverged textually:\n"
        f"--- {SESSION.name}\n{session}\n--- {MANIFEST.name}\n{manifest}"
    )


# --------------------------------------------------------------------------------------
# Guard 3 — auto-verify-pending is known but NOT resolved
# --------------------------------------------------------------------------------------


def test_auto_verify_pending_is_known_but_not_resolved():
    """Owed-but-unrun debt is recognized vocabulary, never a resolved verification.

    Folding it into `_VERIFY_RESOLVED` would make a dropped `runInStageVerify`
    directive read as success — exactly the conflation REQ-DEBT-02 forbids.
    """
    resolved = _parse_literal(SESSION, "_VERIFY_RESOLVED", "{", "}")
    assert isinstance(resolved, set)
    assert "auto-verify-pending" in _verify_statuses(SESSION)
    assert "auto-verify-pending" not in resolved
    assert resolved < set(EXPECTED_VERIFY_STATUSES), "resolved must stay a strict subset"


# --------------------------------------------------------------------------------------
# Guard 4 — the verify-mode routing map (the one domain still written twice)
# --------------------------------------------------------------------------------------


def test_verify_mode_to_stage_covers_exactly_the_verify_modes():
    """Its keys are `VerifyMode`; its values are production stages.

    Neither side is a subset of the other, so `00 §2` keeps this map hand-written —
    and requires both halves asserted here instead.
    """
    session = _load_session_module()
    assert set(session.VERIFY_MODE_TO_STAGE) == set(get_args(session.VerifyMode))
    assert set(session.VERIFY_MODE_TO_STAGE.values()) <= set(get_args(session.ProductionStage))


def test_the_exit_domains_are_derived_not_hand_listed():
    """`EXIT_STAGES`/`EXIT_OUTCOMES` come from `get_args`, not a second copy."""
    session = _load_session_module()
    assert session.EXIT_STAGES == get_args(session.ExitStage)
    assert len(session.EXIT_STAGES) == 9, session.EXIT_STAGES
    assert session.EXIT_OUTCOMES == {
        "forge-5-loop": frozenset(get_args(session.LoopOutcome)),
        "forge-6-docs": frozenset(get_args(session.DocsOutcome)),
        "forge-verify": frozenset(get_args(session.VerifyOutcome)),
        "forge-fix": frozenset(get_args(session.FixOutcome)),
    }
    # The derivation must be textual too: a hand-written tuple that happens to agree
    # today is the drift this guard exists to prevent.
    source = read(SESSION)
    assert "EXIT_STAGES: Final[tuple[str, ...]] = get_args(ExitStage)" in source
    for alias in ("LoopOutcome", "DocsOutcome", "VerifyOutcome", "FixOutcome"):
        assert f"frozenset(get_args({alias}))" in source, f"{alias} not derived"


def test_each_shared_constant_is_assigned_exactly_once():
    """A second module-scope assignment silently shadows the first.

    Ruff's F811 covers redefined imports, functions, and classes — not plain
    module-scope names — so a stray duplicate `NEXT_STEPS_SENTINEL` further down the
    file would win at runtime while every reader assumed the constants block did.
    """
    source = read(SESSION)
    for name in (
        "EXIT_STAGES",
        "EXIT_OUTCOMES",
        "VERIFY_MODE_TO_STAGE",
        "NEXT_STEPS_SENTINEL",
        "FULL_GIT_HASH_RE",
        "PRODUCTION_STAGES",
        "KNOWN_VERIFY_STATUSES",
        "EXIT_HOSTS",
    ):
        found = re.findall(rf"^{re.escape(name)}\s*(?::[^=\n]+)?=", source, re.MULTILINE)
        assert len(found) == 1, f"{name} assigned {len(found)}x at module scope"


def test_the_cli_stage_choices_are_the_whole_exit_domain():
    """`stage-exit --stage` now serves every EXIT_STAGES id, from the derived tuple.

    Replaces the interim subset guard: the router served only the five authoring
    stages while loop, docs, verify, and fix still stamped bespoke terminal blocks.
    The registration must read the shared constant, not a hand-listed copy — a copy
    is the second list `00-core-definitions.md` §2 exists to eliminate.
    """
    source = read(SESSION)
    assert "choices=EXIT_STAGES" in source, "stage-exit --stage must use EXIT_STAGES"
    assert "_STAGE_EXIT_CLI_STAGES" not in source, "the interim subset must be gone"


def test_the_branch_and_production_routing_domains_are_derived():
    """`_BRANCH_STAGES` and `_EXIT_PRODUCTION_STAGES` partition `EXIT_STAGES`."""
    session = _load_session_module()
    assert set(session._EXIT_PRODUCTION_STAGES) == set(get_args(session.ProductionStage))
    assert set(session._BRANCH_STAGES) == {"forge-verify", "forge-fix"}
    assert (
        set(session._BRANCH_STAGES) | set(session._EXIT_PRODUCTION_STAGES)
        == set(session.EXIT_STAGES)
    )
    assert not set(session._BRANCH_STAGES) & set(session._EXIT_PRODUCTION_STAGES)


def test_the_verify_mode_inverse_is_a_faithful_inverse():
    """`_STAGE_TO_VERIFY_MODE` is derived, so it cannot drift from the forward map."""
    session = _load_session_module()
    assert session._STAGE_TO_VERIFY_MODE == {
        stage: mode for mode, stage in session.VERIFY_MODE_TO_STAGE.items()
    }
    # Injective forward map ⇒ the inverse loses nothing.
    assert len(session._STAGE_TO_VERIFY_MODE) == len(session.VERIFY_MODE_TO_STAGE)


def test_the_verify_status_alias_matches_the_status_constant():
    """`VerifyStatus` and `KNOWN_VERIFY_STATUSES` describe the same six values."""
    session = _load_session_module()
    assert set(get_args(session.VerifyStatus)) == set(session.KNOWN_VERIFY_STATUSES)
    assert set(get_args(session.VerifyStatus)) == _schema_verify_statuses()


# --------------------------------------------------------------------------------------
# Guard 5 — the guard itself
# --------------------------------------------------------------------------------------


def test_this_guard_is_not_skippable():
    """No skip gate may be introduced here — an unskippable guard is the whole point."""
    source = read(Path(__file__).resolve())
    for banned in ("skipif", "importorskip", "pytest.skip"):
        # Only the prose above may mention them; no call may be made.
        assert f"{banned}(" not in source, f"{banned} gate introduced in the drift guard"
