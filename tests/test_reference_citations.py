"""Catch-all citation guards for the skill bodies (spec 06 §5, REQ-MAINT-01).

Two directions, both needed, neither sufficient alone:

1. **Forward** — every literal ``references/...md`` citation in every ``skills/*/SKILL.md``
   names a file that actually exists, skill-local or shared. A citation is not decoration:
   ``scripts/build-adapters.py`` fans shared references out **by citation**, so a dangling
   path ships a bundle whose instructions point at nothing on all six hosts.
2. **Reverse** — every reference file in canon is cited by at least one skill body, is
   covered by the ``stacks/`` whole-tree fan-out rule, or is on an explicitly justified
   allowlist. Drop a shared reference's citation and it silently stops being fanned out
   while the forward guard stays perfectly green: the file is still at the bundle ROOT,
   but the bare ``references/X`` path the body actually reads no longer resolves from a
   skill dir on the non-plugin npm-installer Claude layout (``~/.claude/skills/feature-forge/``,
   no ``${CLAUDE_PLUGIN_ROOT}``) — the #122 degradation ``_fan_out_shared_references``
   exists to prevent. This guard is **derived**, not a pinned file list (issue #246): a
   tuple of names from one past feature cannot see the reference someone adds tomorrow,
   which is the only case that ever bites.

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

#: Reference files that legitimately carry NO prose citation, each with the reason it is
#: reachable anyway (issue #246). This is the deliberate-decision escape hatch for the
#: derived reverse guard below — the same shape `validate-traceability.py` uses for its
#: allowlisted foreign references. Adding a file here is a claim that must be true; an
#: entry naming a file that no longer exists is caught by its own test.
#:
#: Keyed by the path a citation would use (`references/<key>`), which for a skill-own file
#: is its path under that skill's own `references/`.
UNCITED_ALLOWLIST: dict[str, str] = {
    "templates/specs-hygiene/AGENTS.md": (
        "copied through an explicit \"$R/references/...\" path in shared-conventions.md's "
        "bash block, never a bare prose read, so it resolves from the bundle root on "
        "every install layout"
    ),
    "templates/specs-hygiene/CLAUDE.md": (
        "same explicit \"$R/references/...\" copy as its AGENTS.md sibling, gated on the "
        "host being Claude"
    ),
    "vendor-construct-inventory.md": (
        "a REQ-VND-03 audit artifact — a record of the spec-purity sweep, read by humans "
        "reviewing that sweep and by no skill at runtime"
    ),
    "templates/hygiene/AGENTS.md": (
        "read by scripts/forge-bootstrap.py from TEMPLATE_ROOT when it composes the "
        "scaffolded repo's hygiene files, not by any skill body"
    ),
    "templates/hygiene/CLAUDE.md": (
        "read by scripts/forge-bootstrap.py alongside its AGENTS.md sibling"
    ),
    "templates/hygiene/README.md": (
        "read by scripts/forge-bootstrap.py when it composes the scaffolded repo's README"
    ),
}

#: Non-vacuity floors for the reverse guard's enumeration, NOT pinned totals (15 shared +
#: 21 skill-own markdown references when this was written). A glob that matched nothing
#: would satisfy "every enumerated file is covered" trivially.
#:
#: The floors are PER SOURCE on purpose. A single combined floor is satisfiable by either
#: glob alone, so the shared glob — the only one whose files depend on citation fan-out,
#: i.e. the entire subject of this guard — could break silently while the skill-own count
#: carried the assertion.
MIN_EXPECTED_SHARED_REFERENCES = 10
MIN_EXPECTED_SKILL_OWN_REFERENCES = 10

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


def _reference_files() -> list[tuple[str | None, str]]:
    """Every markdown reference file in canon, as `(owner, relpath)`, in a stable order.

    `owner` is None for a SHARED reference (bundle-root `references/`) and the skill's
    directory name for one of its OWN `references/`. The distinction is not cosmetic:
    only a shared file depends on citation-driven fan-out to be reachable, so the two
    carry different consequences in the failure message below.
    """
    files: list[tuple[str | None, str]] = [
        (None, str(p.relative_to(REFERENCES).as_posix()))
        for p in sorted(REFERENCES.rglob("*.md"))
    ]
    for own in sorted(SKILLS.glob("*/references")):
        files.extend(
            (own.parent.name, str(p.relative_to(own).as_posix()))
            for p in sorted(own.rglob("*.md"))
        )
    return files


def _citations_by_skill() -> dict[str, set[str]]:
    """Every `references/...md` path each skill body cites, templated forms included.

    Kept per skill rather than pooled because the builder's fan-out is per skill: WHICH
    skill cites a shared reference decides whether that reference reaches a skill dir
    (see `_is_covered`). Templated forms (`stacks/{stack}.md`,
    `verification-checklists/{mode}.md`) are retained because `_stacks_is_fanned` reads
    them; `_is_covered` never matches a concrete file against one directly.
    """
    return {
        name: {m.group(1) for m in CITE_RE.finditer(body)}
        for name, body in _skill_bodies()
    }


def _all_cited() -> set[str]:
    """The union of every skill's citations."""
    return {rel for cited in _citations_by_skill().values() for rel in cited}


def _stacks_is_fanned(cited: set[str]) -> bool:
    """Whether ANY citation triggers the whole-`stacks/`-tree fan-out.

    `_fan_out_shared_references` (scripts/build-adapters.py) special-cases a citation whose
    first path segment is `stacks`: the stack is unknown at build time, so ONE such
    citation — literal, `{stack}`-templated, or globbed — copies the entire `stacks/` tree
    into that skill's own `references/`. Every `stacks/*.md` file is therefore reachable
    without a citation naming it, and this guard models that rule rather than allowlisting
    the individual profiles, which would go stale the moment a stack is added.
    """
    return any(rel.split("/", 1)[0] == "stacks" for rel in cited)


def _is_covered(
    owner: str | None,
    rel: str,
    by_skill: dict[str, set[str]],
    stacks_fanned: bool,
) -> bool:
    """Whether a reference file is reachable by the path a skill body would use.

    `owner` is None for a SHARED reference and the skill name for a skill-own one, and
    it changes what "cited" has to mean. `_fan_out_shared_references` REFUSES to fan a
    shared ref into a skill that already has a same-named file in its own `references/`
    (scripts/build-adapters.py — the never-shadow rule), so a shared file is reachable
    only through a skill whose citation is not already answered by its own copy. Pooling
    every body's citations would let one skill's citation of its OWN `foo.md` vouch for
    a shared `foo.md` that the builder fans to nobody. No such name collides today; the
    guard models the rule anyway, because the day one does is exactly the day a pooled
    check would go quietly green.
    """
    if stacks_fanned and rel.split("/", 1)[0] == "stacks":
        return True
    if rel in UNCITED_ALLOWLIST:
        return True
    if owner is not None:
        # A skill's own references/ is copied wholesale, so any citation resolves it.
        return any(rel in cited for cited in by_skill.values())
    return any(
        rel in cited and not (SKILLS / name / "references" / rel).is_file()
        for name, cited in by_skill.items()
    )


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


def test_every_reference_file_is_cited_or_deliberately_allowlisted():
    """Every reference file in canon, derived — not a pinned list (issue #246).

    A SHARED reference nobody cites still ships at the bundle root, but
    `_fan_out_shared_references` copies only CITED shared refs into a skill's own
    `references/`, so the bare `references/X` path the body reads stops resolving on the
    non-plugin npm-installer Claude layout. A SKILL-OWN reference always ships (the
    whole dir is copied), so an uncited one is dead prose rather than a broken read —
    still worth a deliberate decision, never a silent one.

    The fix is one of three things, in preference order: cite it from the skill that
    reads it; delete it; or add it to `UNCITED_ALLOWLIST` with the reason it is reachable
    without a citation.
    """
    by_skill = _citations_by_skill()
    stacks_fanned = _stacks_is_fanned(_all_cited())
    uncovered = [
        f"references/{rel}"
        + (" (shared — loses its skill-local fan-out)" if owner is None
           else f" (own to {owner} — shipped but read by nothing)")
        for owner, rel in _reference_files()
        if not _is_covered(owner, rel, by_skill, stacks_fanned)
    ]
    assert not uncovered, (
        "these reference files are neither cited by any skill body nor allowlisted:\n  "
        + "\n  ".join(uncovered)
    )


def test_the_reverse_guard_enumerates_both_sources():
    """A glob that matched nothing would pass the guard above without asserting anything.

    Floored per source: the shared glob is the one whose files depend on fan-out, so a
    combined floor the skill-own count alone could satisfy would not guard it.
    """
    files = _reference_files()
    shared = sum(1 for owner, _ in files if owner is None)
    own = len(files) - shared
    assert shared >= MIN_EXPECTED_SHARED_REFERENCES, (
        f"only {shared} SHARED markdown references enumerated (floor "
        f"{MIN_EXPECTED_SHARED_REFERENCES}) — the references/ glob has almost certainly "
        "stopped matching rather than canon having shrunk this far"
    )
    assert own >= MIN_EXPECTED_SKILL_OWN_REFERENCES, (
        f"only {own} SKILL-OWN markdown references enumerated (floor "
        f"{MIN_EXPECTED_SKILL_OWN_REFERENCES}) — the skills/*/references/ glob has "
        "almost certainly stopped matching"
    )


def test_the_reverse_guard_would_catch_a_brand_new_uncited_reference():
    """The issue #246 repro (`touch references/never-cited.md`), as a pure assertion.

    Creating the file would be the literal reproduction; asserting on the predicate keeps
    the guard honest without a canon write. If this ever passes, the coverage rule has
    become vacuous and every assertion above it is decoration.
    """
    by_skill = _citations_by_skill()
    stacks_fanned = _stacks_is_fanned(_all_cited())
    assert not _is_covered(None, "never-cited.md", by_skill, stacks_fanned)


def test_a_shared_reference_is_not_vouched_for_by_a_skills_own_same_named_file():
    """The never-shadow rule, modelled: a citation the builder answers LOCALLY is not
    coverage for a shared file of the same name (`_is_covered`'s owner branch).

    `forge-1-prd` cites `references/prd-template.md` and owns that exact file, so the
    builder resolves it from the skill dir and fans nothing. A shared file of the same
    name would therefore reach no skill dir — and must not be reported as covered.
    """
    own = SKILLS / "forge-1-prd" / "references" / "prd-template.md"
    assert own.is_file(), "fixture drifted: forge-1-prd no longer owns prd-template.md"
    by_skill = _citations_by_skill()
    assert any("prd-template.md" in cited for cited in by_skill.values()), (
        "fixture drifted: no skill body cites references/prd-template.md any more"
    )
    assert not _is_covered(None, "prd-template.md", by_skill, stacks_fanned=False)
    # The same path as a SKILL-OWN file is covered — it ships with its own dir.
    assert _is_covered("forge-1-prd", "prd-template.md", by_skill, stacks_fanned=False)


def test_every_allowlist_entry_names_a_file_that_exists():
    """A stale allowlist entry is a silent hole: it excuses a path nothing enumerates."""
    stale = [
        rel
        for rel in UNCITED_ALLOWLIST
        if not any(rel == candidate for _, candidate in _reference_files())
    ]
    assert not stale, (
        "UNCITED_ALLOWLIST names reference files that no longer exist — delete the "
        "entries:\n  " + "\n  ".join(stale)
    )


def test_every_allowlist_entry_states_a_reason():
    """The allowlist is a record of decisions; an empty reason records nothing."""
    unexplained = [rel for rel, why in UNCITED_ALLOWLIST.items() if len(why.strip()) < 20]
    assert not unexplained, (
        "UNCITED_ALLOWLIST entries must say WHY the file is reachable without a "
        "citation:\n  " + "\n  ".join(unexplained)
    )
