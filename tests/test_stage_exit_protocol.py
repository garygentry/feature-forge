"""Drift guard for the Stage Exit Protocol, and the explicit nine-skill coverage guard.

The canonical block lives once in ``references/stage-exit-protocol.md`` but is
**stamped verbatim** into every covered skill's closing. The single-source guarantee is
enforced here: this test extracts the canonical block, renders each stamp site's slots,
and asserts the rendered block is present **verbatim** in the canon skill. An edit to the
reference that is not mirrored into a stamp site (or vice-versa) fails loudly.

On top of that, this module owns the **canonical exit coverage guard**: an explicit,
immutable allow-list (`CANONICAL_EXIT_SITES`) naming exactly the nine pipeline-advancing
skills and the exact canon files that own each one's terminus. It is an allow-list, **not**
a prefix scan — a new advisory skill named ``forge-something`` does not silently become
covered, and a new pipeline-advancing skill cannot land without an intentional edit to both
the shared ``ExitStage`` domain and this table.

The nine names are **not** written down here. They are extracted from
``scripts/forge-session.py`` by the repository's drift-guard convention (regex-locate the
assignment, ``ast.literal_eval`` it — see ``tests/test_stage_constants_parity.py``), so the
equality assertion compares the table against the real shared domain rather than against a
second hand-maintained copy of itself.

Since the Scripted Stage Exit landed, every covered stage stamps only the short
``scripted-stage-exit-stamp`` (the conditional logic moved into
``forge-session.py stage-exit``; see tests/test_stage_exit.py for the directive matrix).
The loop was the last holdout: its step-6 epic handoff and its all-done result report used
to stamp the bespoke ``standard-exit-block`` / ``warm-exit-block``, and now stamp the
scripted block once, at its Step 7 close. Both bespoke blocks are deleted from the
reference, so the rows below assert their *absence* rather than their rendering.

Runs against ``skills/`` (canon), not ``adapters/`` — the adapter copies legitimately
differ (``/clear`` and ``--host claude`` are host-term-degraded on non-Claude targets;
that degradation is covered in tests/test_build_adapters.py). Canon is never rewritten
from here. No third-party deps, so it runs under a bare ``python3 -m pytest tests``.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import Final, NamedTuple

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
REFERENCE = REPO_ROOT / "references" / "stage-exit-protocol.md"
SESSION = REPO_ROOT / "scripts" / "forge-session.py"


# ---------------------------------------------------------------------------
# Shared domains, extracted from canon rather than re-listed here.
# ---------------------------------------------------------------------------


def _literal_domain_from(source: str, name: str) -> tuple[str, ...]:
    """Return the string members of a module-scope ``NAME = Literal[...]`` alias.

    Never imports the script: ``forge-session.py`` is hyphenated (so unimportable by
    name) and does work at module scope. This is the same regex + ``ast.literal_eval``
    convention ``tests/test_stage_constants_parity.py`` uses.

    Args:
        source: Full ``scripts/forge-session.py`` text (a copy, in negative controls).
        name: The type-alias name to locate.

    Returns:
        The alias's string members, in declaration order.

    Raises:
        AssertionError: The alias is missing, assigned more than once, or is not a
            tuple of strings.
    """
    pattern = re.compile(
        rf"^{re.escape(name)}(?:\s*:[^=\n]+)?\s*=\s*Literal\[([^\]]*)\]",
        re.MULTILINE,
    )
    matches = pattern.findall(source)
    assert matches, f"scripts/forge-session.py: no module-scope `{name} = Literal[...]` found"
    assert len(matches) == 1, f"scripts/forge-session.py: {name} assigned {len(matches)}x"
    value = ast.literal_eval(f"({matches[0]})")
    if isinstance(value, str):  # a one-member Literal parses as a bare str
        value = (value,)
    assert isinstance(value, tuple) and all(isinstance(item, str) for item in value), (
        f"scripts/forge-session.py: {name} is not a tuple of string literals"
    )
    return value


def _session_source() -> str:
    return SESSION.read_text(encoding="utf-8")


def _exit_stages() -> tuple[str, ...]:
    """The nine shared ``EXIT_STAGES`` ids, in order, read from canon."""
    return _literal_domain_from(_session_source(), "ExitStage")


def _production_stages() -> tuple[str, ...]:
    """The six production stages, read from canon (used to derive the branch stages)."""
    return _literal_domain_from(_session_source(), "ProductionStage")


def _exit_outcomes() -> dict[str, tuple[str, ...]]:
    """``EXIT_OUTCOMES`` as stage -> its outcome domain, derived from canon.

    ``EXIT_OUTCOMES`` maps each outcome-carrying stage to ``frozenset(get_args(Alias))``,
    so the table's own source names the alias; the domain then comes from that alias.
    Nothing about which stages carry an outcome is written down here.
    """
    source = _session_source()
    body = re.search(
        r"^EXIT_OUTCOMES(?:\s*:[^=\n]+)?\s*=\s*\{(.*?)^\}", source, re.MULTILINE | re.DOTALL
    )
    assert body, "scripts/forge-session.py: no module-scope `EXIT_OUTCOMES = {...}` found"
    rows = re.findall(r'"([a-z0-9-]+)":\s*frozenset\(get_args\((\w+)\)\)', body.group(1))
    assert rows, "scripts/forge-session.py: EXIT_OUTCOMES rows are no longer alias-derived"
    return {stage: _literal_domain_from(source, alias) for stage, alias in rows}


def _next_steps_sentinel() -> str:
    """The exact ``NEXT_STEPS_SENTINEL`` value, read from canon."""
    source = _session_source()
    match = re.search(
        r'^NEXT_STEPS_SENTINEL(?:\s*:[^=\n]+)?\s*=\s*("(?:[^"\\]|\\.)*")\s*$',
        source,
        re.MULTILINE,
    )
    assert match, "scripts/forge-session.py: no module-scope `NEXT_STEPS_SENTINEL = \"…\"`"
    return ast.literal_eval(match.group(1))


EXIT_STAGES: Final[tuple[str, ...]] = _exit_stages()
NEXT_STEPS_SENTINEL: Final[str] = _next_steps_sentinel()


# ---------------------------------------------------------------------------
# The explicit coverage table (06-compliance-and-coverage.md §2.1).
# ---------------------------------------------------------------------------


class CanonicalExitSite(NamedTuple):
    """One required skill and the exact canon files that own its direct terminus."""

    # Skill id, matching its directory name under `skills/`. Must be one of the
    # nine covered skills; a skill in INTENTIONALLY_EXCLUDED_SKILLS must not appear.
    skill: str
    # Repo-relative canon files that together own this skill's terminal exit —
    # SKILL.md plus any reference file carrying part of the stamp. Non-empty, and
    # paths are canon-only: never an `adapters/` path, which is generated output.
    # A tuple, not a list, so the coverage table stays immutable at import time.
    contract_paths: tuple[str, ...]


CANONICAL_EXIT_SITES: Final[tuple[CanonicalExitSite, ...]] = (
    CanonicalExitSite("forge-0-epic", ("skills/forge-0-epic/SKILL.md",)),
    CanonicalExitSite("forge-1-prd", ("skills/forge-1-prd/SKILL.md",)),
    CanonicalExitSite("forge-2-tech", ("skills/forge-2-tech/SKILL.md",)),
    CanonicalExitSite("forge-3-specs", ("skills/forge-3-specs/SKILL.md",)),
    CanonicalExitSite("forge-4-backlog", ("skills/forge-4-backlog/SKILL.md",)),
    CanonicalExitSite(
        "forge-5-loop",
        (
            "skills/forge-5-loop/SKILL.md",
            "skills/forge-5-loop/references/result-reporting.md",
        ),
    ),
    CanonicalExitSite("forge-6-docs", ("skills/forge-6-docs/SKILL.md",)),
    CanonicalExitSite("forge-verify", ("skills/forge-verify/SKILL.md",)),
    CanonicalExitSite("forge-fix", ("skills/forge-fix/SKILL.md",)),
)

INTENTIONALLY_EXCLUDED_SKILLS: Final[frozenset[str]] = frozenset(
    {
        "forge",
        "forge-bootstrap",
        "forge-guide",
        "forge-init",
    }
)

#: The per-stage `{stage-exit-args}` build-time slot each site stamps, POSITIONALLY
#: zipped onto `CANONICAL_EXIT_SITES` so it cannot become a second hand-maintained list
#: of skill names (`zip(strict=True)` fails loudly if the two lengths ever diverge).
#: Ownership is a runtime placeholder on the branch skills, not a per-site constant —
#: one stamp serves both the direct and the nested invocation, and the payload's
#: `terminalOwnedBy` decides whether anything is printed.
_STAGE_EXIT_ARGS: Final[dict[str, str]] = dict(
    zip(
        (site.skill for site in CANONICAL_EXIT_SITES),
        (
            '--feature "{epic}" --stage forge-0-epic '
            '--next-feature "{first-actionable-feature}"',
            '--feature "{feature}" --stage forge-1-prd',
            '--feature "{feature}" --stage forge-2-tech',
            '--feature "{feature}" --stage forge-3-specs',
            '--feature "{feature}" --stage forge-4-backlog',
            '--feature "{feature}" --stage forge-5-loop --outcome "{LoopOutcome}"',
            '--feature "{feature}" --stage forge-6-docs --outcome "{DocsOutcome}"',
            '--feature "{feature}" --stage forge-verify --owner "{owner}" '
            '--outcome "{VerifyOutcome}" --verify-mode "{mode}"',
            '--feature "{feature}" --stage forge-fix --owner "{owner}" '
            '--outcome "{FixOutcome}" --served-stage "{servedStage}"',
        ),
        strict=True,
    )
)

_SITE_IDS: Final[list[str]] = [site.skill for site in CANONICAL_EXIT_SITES]

#: Branch (diversion) exits, derived: an EXIT_STAGE that is neither a production stage
#: nor the epic decomposition stage. Never hand-listed — the branch skills are exactly
#: the ones that carry `--owner`.
_BRANCH_SITES: Final[tuple[CanonicalExitSite, ...]] = tuple(
    site
    for site in CANONICAL_EXIT_SITES
    if site.skill not in _production_stages() and site.skill != "forge-0-epic"
)


# ---------------------------------------------------------------------------
# Stable contract markers, taken from references/stage-exit-protocol.md.
# ---------------------------------------------------------------------------

#: The complete scripted invocation prefix. Counting THIS (not a loose "stage-exit")
#: is what makes a duplicate advancing contract fail.
_SCRIPTED_INVOCATION = 'python3 "$R/scripts/forge-session.py" stage-exit'
#: The one terminal-print instruction. Exactly one per covered direct surface.
_TERMINAL_PRINT_MARKER = "print the NEXT-STEPS block verbatim as your absolute last output"
#: The no-content-after-sentinel rule that instruction must name.
_NO_TRAILING_CONTENT_MARKER = "nothing after its sentinel line"
#: The nested contract: an `outer`-owned payload prints nothing at all.
_NESTED_NO_BLOCK_MARKER = "print no terminal block at all"
#: The literal ownership tokens a branch skill reads at entry (never inferred from
#: how the invocation was phrased — see the reference's "Branch ownership" section).
_OWNER_TOKENS = ("owner: direct", "owner: nested")

# Marker phrases unique to the two deleted bespoke blocks. Their reappearance anywhere in
# canon means an alternative advancing contract came back.
_RETIRED_BLOCK_MARKERS = [
    "walk the user through the Stage Exit Protocol",
    "this is the one boundary where clearing before the next stage is optional",
]


def _extract_block(name: str) -> str:
    """Return the text between ``<!-- BEGIN: {name} -->`` and ``<!-- END: {name} -->``."""
    text = REFERENCE.read_text(encoding="utf-8")
    m = re.search(rf"<!-- BEGIN: {name} -->\n(.*?)\n<!-- END: {name} -->", text, re.S)
    assert m, f"marker pair for {name!r} not found in {REFERENCE}"
    return m.group(1)


def _render(block: str, **slots: str) -> str:
    """Substitute build-time template slots (mirrors the stamping logic).

    ``{feature}`` / ``{epic}`` / ``{specsDir}`` and similar are left untouched —
    they are runtime placeholders the skill resolves, not build-time slots.
    """
    out = block
    for key, value in slots.items():
        out = out.replace("{" + key + "}", value)
    return out


def _read_contract_surface(site: CanonicalExitSite) -> str:
    """Read the explicitly owned canon files for one covered skill.

    Args:
        site: Covered skill and its exact repository-relative canon paths.

    Returns:
        UTF-8 file contents joined in the listed order with one newline separator.

    Raises:
        AssertionError: A path is missing, escapes `skills/`, or is listed twice.
        OSError: A listed canon file cannot be read.
    """
    assert site.contract_paths, f"{site.skill}: no contract path listed"
    assert len(set(site.contract_paths)) == len(site.contract_paths), (
        f"{site.skill}: duplicate contract path in {list(site.contract_paths)}"
    )
    parts: list[str] = []
    for relpath in site.contract_paths:
        assert not Path(relpath).is_absolute(), f"{site.skill}: {relpath} is absolute"
        resolved = (REPO_ROOT / relpath).resolve()
        assert resolved.is_relative_to((REPO_ROOT / "skills").resolve()), (
            f"{site.skill}: {relpath} escapes skills/ — canon only, never adapters/"
        )
        assert resolved.is_file(), f"{site.skill}: missing canon file {relpath}"
        parts.append(resolved.read_text(encoding="utf-8"))
    return "\n".join(parts)


def _site(skill: str) -> CanonicalExitSite:
    """Return the canonical exit site for ``skill``.

    Args:
        skill: The skill id, as it appears in ``CANONICAL_EXIT_SITES``.

    Returns:
        The matching site entry.

    Raises:
        AssertionError: ``skill`` is not a covered exit site.
    """
    for site in CANONICAL_EXIT_SITES:
        if site.skill == skill:
            return site
    raise AssertionError(f"{skill!r} is not a covered exit site")


def _assert_exit_contract(site: CanonicalExitSite, surface: str) -> None:
    """Assert the 06 §2.3 closure contract against one covered skill's surface.

    Takes the surface as a STRING so negative guards can mutate a copy; repository
    files are never written from here.
    """
    where = f"{site.skill} ({', '.join(site.contract_paths)})"
    args = _STAGE_EXIT_ARGS[site.skill]

    # 1. The canonical stamp, rendered for this stage, verbatim — and exactly one
    #    scripted invocation, so a second advancing contract fails.
    block = _render(_extract_block("scripted-stage-exit-stamp"), **{"stage-exit-args": args})
    assert block in surface, (
        f"{where} is out of sync with references/stage-exit-protocol.md "
        f"(scripted-stage-exit stamp). Re-stamp the block or update the reference."
    )
    invocations = surface.count(_SCRIPTED_INVOCATION)
    assert invocations == 1, (
        f"{where}: expected exactly 1 scripted stage-exit invocation "
        f"({_SCRIPTED_INVOCATION!r}), observed {invocations}"
    )
    assert f" --stage {site.skill} " in surface, (
        f"{where}: the scripted invocation does not carry `--stage {site.skill}`"
    )

    # 2. Branch ownership: both literal tokens, the pass-through flag, and the nested
    #    return of terminal ownership to the outer caller.
    if site in _BRANCH_SITES:
        for token in _OWNER_TOKENS:
            assert token in surface, (
                f"{where}: the branch closure never names the literal {token!r} token; "
                "ownership must be read from the dispatching prompt, never inferred"
            )
        assert "--owner" in surface, f"{where}: the branch invocation omits --owner"
    else:
        assert "--owner" not in surface, (
            f"{where}: a production-stage exit takes no --owner (branch stages only)"
        )
    assert _NESTED_NO_BLOCK_MARKER in surface, (
        f"{where}: nothing states that a nested/outer-owned payload prints no terminal "
        f"block ({_NESTED_NO_BLOCK_MARKER!r})"
    )

    # 3/5. Exactly one terminal-print instruction, naming the no-trailing-content rule.
    prints = surface.count(_TERMINAL_PRINT_MARKER)
    assert prints == 1, (
        f"{where}: expected exactly 1 terminal-print instruction "
        f"({_TERMINAL_PRINT_MARKER!r}), observed {prints}"
    )
    assert _NO_TRAILING_CONTENT_MARKER in surface, (
        f"{where}: the terminal-print instruction does not name the "
        f"no-content-after-sentinel rule ({_NO_TRAILING_CONTENT_MARKER!r})"
    )
    # The sentinel is emitted by the script, never typed into canon. A nested branch
    # surface carrying one is the REQ-EXIT-04 ownership leak this guard exists to catch.
    assert NEXT_STEPS_SENTINEL not in surface, (
        f"{where}: canon carries the literal sentinel {NEXT_STEPS_SENTINEL!r} — the "
        "script owns the terminal block; a hand-typed sentinel is an ownership leak"
    )

    # 4. No retired bespoke standard/warm block as an alternative advancing contract.
    for marker in _RETIRED_BLOCK_MARKERS:
        assert marker not in surface, (
            f"{where} carries retired bespoke-block prose ({marker!r}) — close the "
            "stage with the scripted stamp instead"
        )

    # Outcome flags: an outcome-carrying stage passes --outcome and documents every
    # member of its own domain; a stage with no outcome domain passes none.
    outcomes = _exit_outcomes().get(site.skill)
    if outcomes:
        assert "--outcome" in surface, f"{where}: the invocation omits --outcome"
        for outcome in outcomes:
            assert f"`{outcome}`" in surface, (
                f"{where}: outcome {outcome!r} has no documented selection rule"
            )
    else:
        assert "--outcome" not in surface, (
            f"{where}: this stage carries no outcome domain but the surface names --outcome"
        )


# ---------------------------------------------------------------------------
# Coverage-table shape (06 §2.1).
# ---------------------------------------------------------------------------


def test_the_covered_table_equals_the_shared_exit_stage_domain():
    """CANONICAL_EXIT_SITES names exactly EXIT_STAGES, in the same order.

    Replaces the inferred authoring-stage set: coverage is now an explicit allow-list
    checked against the shared domain, so adding a pipeline-advancing stage to
    `ExitStage` without adding its row here fails immediately.
    """
    assert tuple(site.skill for site in CANONICAL_EXIT_SITES) == EXIT_STAGES, (
        "CANONICAL_EXIT_SITES has drifted from ExitStage/EXIT_STAGES in "
        "scripts/forge-session.py — add or remove the matching row, in order"
    )
    assert len(EXIT_STAGES) == 9, f"expected nine covered exits, found {len(EXIT_STAGES)}"


def test_exit_stages_is_the_runtime_tuple_derived_from_the_extracted_alias():
    """The extracted alias really is what `EXIT_STAGES` holds at runtime.

    Without this, the equality above would only pin the *alias*, and a hand-written
    `EXIT_STAGES` could diverge from it while the table still looked correct.
    """
    assert re.search(
        r"^EXIT_STAGES(?:\s*:[^=\n]+)?\s*=\s*get_args\(ExitStage\)\s*$",
        _session_source(),
        re.MULTILINE,
    ), "EXIT_STAGES is no longer `get_args(ExitStage)` — re-point this guard's extraction"


def test_the_extraction_is_not_vacuous():
    """A negative control: the domain really is read from the script's text.

    If the extractor silently returned the table's own names, editing `ExitStage`
    would not be detectable — the equality assertion would compare the table with
    itself. Feeding a mutated copy proves it reads canon.
    """
    mutated = _session_source().replace('    "forge-fix",\n]', "]", 1)
    assert mutated != _session_source(), "the ExitStage alias no longer ends with forge-fix"
    extracted = _literal_domain_from(mutated, "ExitStage")
    assert "forge-fix" not in extracted
    assert tuple(site.skill for site in CANONICAL_EXIT_SITES) != extracted, (
        "dropping a stage from ExitStage must break the coverage equality assertion"
    )


def test_the_covered_table_has_unique_names_and_unique_existing_paths():
    """Nine unique skills, no duplicate path, every path an existing file under skills/."""
    names = [site.skill for site in CANONICAL_EXIT_SITES]
    assert len(set(names)) == len(names), f"duplicate skill in the coverage table: {names}"
    seen: dict[str, str] = {}
    skills_root = (REPO_ROOT / "skills").resolve()
    for site in CANONICAL_EXIT_SITES:
        assert site.contract_paths, f"{site.skill}: no contract path listed"
        for relpath in site.contract_paths:
            assert relpath not in seen, (
                f"{relpath} is listed by both {seen[relpath]!r} and {site.skill!r}"
            )
            seen[relpath] = site.skill
            assert not relpath.startswith("adapters/"), (
                f"{site.skill}: {relpath} is generated output, never the source of truth"
            )
            resolved = (REPO_ROOT / relpath).resolve()
            assert resolved.is_relative_to(skills_root), f"{relpath} escapes skills/"
            assert resolved.is_file(), f"{site.skill}: missing canon file {relpath}"
        assert (REPO_ROOT / "skills" / site.skill / "SKILL.md").is_file(), (
            f"{site.skill}: no skills/{site.skill}/SKILL.md"
        )


def test_every_intentional_exclusion_is_real_and_uncovered():
    """Each excluded id exists under skills/ and is absent from the covered table.

    Requiring the file to exist keeps the exclusion set from rotting into phantoms —
    a renamed or deleted advisory skill must be reflected here, not left behind as a
    stale name that silently documents nothing.
    """
    covered = {site.skill for site in CANONICAL_EXIT_SITES}
    for skill in sorted(INTENTIONALLY_EXCLUDED_SKILLS):
        assert skill not in covered, (
            f"{skill!r} is both covered and intentionally excluded — pick one"
        )
        assert (REPO_ROOT / "skills" / skill / "SKILL.md").is_file(), (
            f"INTENTIONALLY_EXCLUDED_SKILLS names {skill!r}, but skills/{skill}/SKILL.md "
            "does not exist — the exclusion has rotted into a phantom entry"
        )


def test_coverage_is_an_allow_list_not_a_forge_name_prefix_scan():
    """No skill is covered merely because its directory name starts with `forge-`.

    A prefix scan over `skills/` would sweep in the navigator, bootstrap, setup, and
    advisory skills. The excluded ids prove the difference is real and non-empty.
    """
    covered = {site.skill for site in CANONICAL_EXIT_SITES}
    prefixed = {
        path.name
        for path in (REPO_ROOT / "skills").iterdir()
        if path.is_dir() and path.name.startswith("forge-")
    }
    over_covered = prefixed - covered
    assert over_covered, (
        "every forge-* skill is covered, so this guard can no longer distinguish an "
        "allow-list from a prefix scan — add the missing advisory skill to "
        "INTENTIONALLY_EXCLUDED_SKILLS or re-think the check"
    )
    assert over_covered & INTENTIONALLY_EXCLUDED_SKILLS, (
        f"prefix-scan-only skills {sorted(over_covered)} are not documented as "
        "intentionally excluded"
    )


# ---------------------------------------------------------------------------
# Per-site contract assertions (06 §2.3).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("site", CANONICAL_EXIT_SITES, ids=_SITE_IDS)
def test_each_covered_skill_satisfies_the_scripted_exit_contract(site):
    """Every covered skill's own canon files carry the full 06 §2.3 closure contract."""
    _assert_exit_contract(site, _read_contract_surface(site))


@pytest.mark.parametrize("site", CANONICAL_EXIT_SITES, ids=_SITE_IDS)
def test_scripted_stamp_stamped_verbatim(site):
    """Each covered skill contains the rendered scripted-stage-exit stamp verbatim."""
    block = _render(
        _extract_block("scripted-stage-exit-stamp"),
        **{"stage-exit-args": _STAGE_EXIT_ARGS[site.skill]},
    )
    assert block in _read_contract_surface(site), (
        f"{site.skill} is out of sync with references/stage-exit-protocol.md "
        f"(scripted-stage-exit stamp). Re-stamp the block or update the reference."
    )


def test_the_stage_exit_argument_table_is_paired_with_the_covered_skills():
    """`_STAGE_EXIT_ARGS` is positional argument data, correctly paired to the table.

    The zip cannot drop or add a skill (`strict=True`), but it could mis-pair them, so
    each argument list must name its own stage.
    """
    assert tuple(_STAGE_EXIT_ARGS) == tuple(site.skill for site in CANONICAL_EXIT_SITES)
    for skill, args in _STAGE_EXIT_ARGS.items():
        assert f"--stage {skill}" in args, f"{skill}: stamp args name a different stage ({args!r})"


def test_the_branch_sites_are_derived_not_listed():
    """Exactly the two diversion skills carry `--owner`, derived from the shared domains."""
    assert {site.skill for site in _BRANCH_SITES} == {
        skill for skill, args in _STAGE_EXIT_ARGS.items() if "--owner" in args
    }


def test_the_reference_carries_the_sentinel_exactly_once():
    """The canonical contract names the exact sentinel value once, in the sentinel rule."""
    text = REFERENCE.read_text(encoding="utf-8")
    assert text.count(NEXT_STEPS_SENTINEL) == 1, (
        f"{REFERENCE.name} must name {NEXT_STEPS_SENTINEL!r} exactly once "
        f"(observed {text.count(NEXT_STEPS_SENTINEL)})"
    )


# ---------------------------------------------------------------------------
# Negative guards — all operate on COPIED strings; no repository file is mutated.
# ---------------------------------------------------------------------------


#: The single surface every mutation control mutates. A branch site, because the
#: ownership-token control only applies to a branch closure; one site for all classes,
#: so a failure always names the same surface.
_MUTATION_SITE: Final[CanonicalExitSite] = _site("forge-verify")


def _surface_is_unmutated(site: CanonicalExitSite, before: str) -> None:
    assert _read_contract_surface(site) == before, (
        f"{site.skill}: a negative guard mutated repository canon — copy the string instead"
    )


def test_removing_the_scripted_invocation_fails_the_guard():
    """Deleting a covered skill's scripted exit call is caught."""
    site = _MUTATION_SITE
    surface = _read_contract_surface(site)
    broken = surface.replace(_SCRIPTED_INVOCATION, "echo 'closed the stage'", 1)
    assert broken != surface
    with pytest.raises(AssertionError):
        _assert_exit_contract(site, broken)
    _surface_is_unmutated(site, surface)


def test_a_duplicate_terminal_print_instruction_fails_the_guard():
    """A second terminal-print instruction is a duplicate advancing contract."""
    site = _MUTATION_SITE
    surface = _read_contract_surface(site)
    doubled = f"{surface}\n\nThen {_TERMINAL_PRINT_MARKER} — {_NO_TRAILING_CONTENT_MARKER}.\n"
    with pytest.raises(AssertionError, match="terminal-print instruction"):
        _assert_exit_contract(site, doubled)
    _surface_is_unmutated(site, surface)


def test_a_duplicate_scripted_invocation_fails_the_guard():
    """Two scripted exits per surface is likewise a duplicate advancing contract."""
    site = _MUTATION_SITE
    surface = _read_contract_surface(site)
    doubled = f"{surface}\n\n```bash\n{_SCRIPTED_INVOCATION} --stage {site.skill}\n```\n"
    with pytest.raises(AssertionError, match="scripted stage-exit invocation"):
        _assert_exit_contract(site, doubled)
    _surface_is_unmutated(site, surface)


def test_restoring_a_bespoke_terminal_block_fails_the_guard():
    """A restored standard/warm block is an alternative advancing contract."""
    site = _MUTATION_SITE
    surface = _read_contract_surface(site)
    for marker in _RETIRED_BLOCK_MARKERS:
        restored = f"{surface}\n\nOtherwise, {marker}.\n"
        with pytest.raises(AssertionError, match="retired bespoke-block prose"):
            _assert_exit_contract(site, restored)
    _surface_is_unmutated(site, surface)


def test_a_hand_typed_sentinel_fails_the_guard():
    """A nested/branch surface that types the sentinel leaks terminal ownership."""
    site = _MUTATION_SITE
    surface = _read_contract_surface(site)
    leaked = f"{surface}\n\nAs a nested owner, end with:\n\n{NEXT_STEPS_SENTINEL}\n"
    with pytest.raises(AssertionError, match="literal sentinel"):
        _assert_exit_contract(site, leaked)
    _surface_is_unmutated(site, surface)


def test_dropping_a_branch_ownership_token_fails_the_guard():
    """A branch skill that stops naming an ownership token is caught."""
    site = _MUTATION_SITE
    assert site in _BRANCH_SITES, (
        f"{site.skill} is no longer a branch site, so it cannot exercise the ownership "
        "tokens — re-point the representative at a site that carries --owner"
    )
    surface = _read_contract_surface(site)
    for token in _OWNER_TOKENS:
        stripped = surface.replace(token, "the dispatcher's intent")
        assert stripped != surface
        with pytest.raises(AssertionError, match="never inferred"):
            _assert_exit_contract(site, stripped)
    _surface_is_unmutated(site, surface)


def test_dropping_the_nested_no_terminal_block_rule_fails_the_guard():
    """Losing the nested "prints nothing" rule is caught on a covered surface.

    The rule is carried by the canonical stamp, so on a covered surface the verbatim
    stamp check is what trips first — the stricter of the two. The dedicated
    `_NESTED_NO_BLOCK_MARKER` assertion still covers a surface that reworded the rule
    outside the stamp, which is why both messages are accepted here.
    """
    site = _MUTATION_SITE
    surface = _read_contract_surface(site)
    stripped = surface.replace(_NESTED_NO_BLOCK_MARKER, "hand off to the caller")
    assert stripped != surface
    with pytest.raises(
        AssertionError, match="scripted-stage-exit stamp|nested/outer-owned payload"
    ):
        _assert_exit_contract(site, stripped)
    _surface_is_unmutated(site, surface)


# ---------------------------------------------------------------------------
# Loop and docs migration equivalence (06 §2.4) — positive replacements.
# ---------------------------------------------------------------------------


def test_the_loop_surface_covers_every_loop_outcome():
    """All five LoopOutcome values have a documented selection rule.

    Replaces the assertion that the loop stamps bespoke blocks: the loop's contract
    surface is now the outcome ladder plus the single scripted invocation. The five
    values come from `EXIT_OUTCOMES["forge-5-loop"]`, never from a copy here.
    """
    site = _site("forge-5-loop")
    surface = _read_contract_surface(site)
    outcomes = _exit_outcomes()["forge-5-loop"]
    assert len(outcomes) == 5, f"expected five LoopOutcome values, found {sorted(outcomes)}"
    for outcome in outcomes:
        assert f"`{outcome}`" in surface, (
            f"LoopOutcome {outcome!r} has no selection rule on the forge-5-loop surface"
        )
    assert surface.count("--stage forge-5-loop --outcome") == 1, (
        "the loop must emit exactly one stage-exit invocation per run"
    )


def test_the_docs_surface_covers_both_docs_outcomes():
    """forge-6-docs closes through the script, with `complete` and `blocked` documented.

    Replaces the assertion that forge-6-docs is terminal: it is now the ninth covered
    exit, so the positive obligations are a single scripted invocation plus a documented
    selection rule for each `DocsOutcome`.
    """
    site = _site("forge-6-docs")
    surface = _read_contract_surface(site)
    outcomes = _exit_outcomes()["forge-6-docs"]
    assert set(outcomes) == {"complete", "blocked"}, (
        f"DocsOutcome is no longer complete|blocked: {sorted(outcomes)}"
    )
    for outcome in outcomes:
        assert f"`{outcome}`" in surface, (
            f"DocsOutcome {outcome!r} has no selection rule on the forge-6-docs surface"
        )
    assert surface.count("--stage forge-6-docs --outcome") == 1, (
        "forge-6-docs must emit exactly one stage-exit invocation per run"
    )


def test_the_docs_surface_routes_epic_members_from_live_status():
    """The docs terminus must not route from Step 1's pre-mutation render-status snapshot."""
    body = (REPO_ROOT / "skills/forge-6-docs/SKILL.md").read_text(encoding="utf-8")
    assert "Do **not** reuse Step 1's `render-status` snapshot" in body, (
        "forge-6-docs may only route an epic member from live status read at exit time"
    )


@pytest.mark.parametrize("relpath", list(_site("forge-5-loop").contract_paths))
def test_the_loop_surface_has_no_hand_written_next_command(relpath):
    """The loop routes only through the script — no fenced/bulleted next command."""
    body = (REPO_ROOT / relpath).read_text(encoding="utf-8")
    for command in ("/feature-forge:forge-6-docs {feature}", "/feature-forge:forge-1-prd {chosen}"):
        assert command not in body, (
            f"{relpath} still names {command!r} as a hand-written next step — the "
            "stage-exit router owns loop routing for every LoopOutcome"
        )


# ---------------------------------------------------------------------------
# Repository-wide retirements.
# ---------------------------------------------------------------------------


def test_the_retired_bespoke_blocks_are_gone_from_the_reference():
    """The standard and warm blocks no longer exist as stampable markered blocks.

    Replaces the two "…stamped verbatim" rows: with the loop converted, both bespoke
    blocks were deleted from the reference, so a surviving marker pair would mean an
    alternative advancing contract is stampable again.
    """
    text = REFERENCE.read_text(encoding="utf-8")
    for name in ("standard-exit-block", "warm-exit-block"):
        assert f"<!-- BEGIN: {name} -->" not in text, (
            f"the retired {name!r} marker pair is back in {REFERENCE.name} — the "
            "scripted stamp is the only advancing contract for all nine covered exits"
        )


def test_no_canon_surface_carries_a_retired_bespoke_block():
    """No skill re-introduces a hand-written standard or warm terminal block."""
    surfaces = sorted((REPO_ROOT / "skills").rglob("*.md")) + [REFERENCE]
    for path in surfaces:
        body = path.read_text(encoding="utf-8")
        for marker in _RETIRED_BLOCK_MARKERS:
            assert marker not in body, (
                f"{path.relative_to(REPO_ROOT)} carries retired bespoke-block prose "
                f"({marker!r}) — close the stage with the scripted stamp instead"
            )


def test_no_skill_retains_the_old_in_stage_block():
    """The prose in-stage auto-verify block is fully retired.

    Its semantics live in the stage-exit directive contract now; a resurrected
    prose copy would fork the logic (the exact drift this migration removes).
    """
    for skill in sorted((REPO_ROOT / "skills").glob("*/SKILL.md")):
        body = skill.read_text(encoding="utf-8")
        assert "In-stage auto-verify" not in body, (
            f"{skill.relative_to(REPO_ROOT)} still carries the retired prose "
            "in-stage auto-verify block — stage-exit directives replace it."
        )
