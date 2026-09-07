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
   which is the only case that ever bites. This supersedes the ``NEW_FILES`` guard
   specified in ``specs/context-efficiency/06-testing-strategy.md §5``: the protection
   that spec describes is preserved and strengthened — a brace-list citation of the six
   ``verification-checklists/`` paths passed the old substring match and now leaves all
   six uncovered — but the pinned tuple itself is gone.

Where the reverse guard's ``CITE_RE`` differs from the builder's own
``_REFERENCE_CITATION_RE``, it differs in the SAFE direction: the lookbehind makes it
strictly narrower, so it can demand a citation the builder would have honoured (a
false alarm, recoverable through ``UNCITED_ALLOWLIST`` — which is what the two
``templates/specs-hygiene`` entries are) but never excuse one the builder would not.

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
#: Keyed by `(owner, relpath)` — owner None for a SHARED reference, else the skill that
#: owns it. The owner is part of the key on purpose: a shared file and a skill-own file
#: can carry the same relpath, and an entry that excused both would silently cover a
#: future shared file it was never written about.
UNCITED_ALLOWLIST: dict[tuple[str | None, str], str] = {
    (None, "templates/specs-hygiene/AGENTS.md"): (
        "copied through an explicit \"$R/references/...\" path in shared-conventions.md's "
        "bash block, never a bare prose read, so it resolves from the bundle root on "
        "every install layout"
    ),
    (None, "templates/specs-hygiene/CLAUDE.md"): (
        "same explicit \"$R/references/...\" copy as its AGENTS.md sibling, gated on the "
        "host being Claude"
    ),
    (None, "templates/root-hygiene/AGENTS.md"): (
        "copied through an explicit \"$R/references/...\" path in shared-conventions.md's "
        "Root Hygiene bash block (forge-init's tooling-feedback step), never a bare prose "
        "read, so it resolves from the bundle root on every install layout"
    ),
    (None, "templates/root-hygiene/CLAUDE.md"): (
        "same explicit \"$R/references/...\" copy as its AGENTS.md sibling, gated on the "
        "host being Claude"
    ),
    (None, "vendor-construct-inventory.md"): (
        "a REQ-VND-03 audit artifact — a record of the spec-purity sweep, read by humans "
        "reviewing that sweep and by no skill at runtime"
    ),
    ("forge-bootstrap", "templates/hygiene/AGENTS.md"): (
        "read by scripts/forge-bootstrap.py from TEMPLATE_ROOT when it composes the "
        "scaffolded repo's hygiene files, not by any skill body"
    ),
    ("forge-bootstrap", "templates/hygiene/CLAUDE.md"): (
        "read by scripts/forge-bootstrap.py alongside its AGENTS.md sibling"
    ),
    ("forge-bootstrap", "templates/hygiene/README.md"): (
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


def _strip_frontmatter(text: str) -> str:
    """The skill BODY — what `build-adapters.py` scans — with YAML frontmatter removed.

    The builder fans out by scanning `skill.body`, which its `split_frontmatter` has
    already stripped. Scanning the whole file here instead would count a citation in a
    `description:` as coverage for a shared reference the builder then fans to nobody:
    green guard, unreachable file.

    Mirror the builder's `split_frontmatter` fence rule, which is LINE-based: the block
    runs from the first line whose `.strip() == "---"` to the next such line. The old form
    used a substring scan (`text.find("\\n---")`), which stops at any *value* line that
    merely starts with `---` rather than at a real fence line. Input is already
    newline-normalized — `read()` opens in text mode (universal newlines) — so this
    operates on `\\n`.

    This does NOT re-police malformed frontmatter: on a file with no opening fence (or an
    unterminated one) it returns the whole text as body and moves on. The builder itself
    *raises* on those, and a BOM makes `lines[0].strip() != "---"` here just as it makes
    the builder reject the file — so a malformed SKILL.md fails the build's own frontmatter
    guard long before citation coverage matters. Faithfully matching the builder means
    matching its fence rule for well-formed files, not reimplementing its error handling.
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return text  # no opening fence → whole file is body (build guard polices this)
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return "\n".join(lines[i + 1:])
    return text  # unterminated frontmatter → whole file is body (build guard polices this)


def _skill_bodies() -> list[tuple[str, str]]:
    """(skill name, body text) for all 13 skills, in a stable order."""
    return [
        (p.parent.name, _strip_frontmatter(read(p)))
        for p in sorted(SKILLS.glob("*/SKILL.md"))
    ]


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
    (see `_is_covered`). Templated forms are retained rather than filtered, for two
    different reasons: the `stacks/{stack}.md` form is what `_whole_dir_fanned_roots`
    reads to detect the whole-`stacks/`-tree fan, while `verification-checklists/{mode}.md`
    is harmless noise — `_is_covered` never matches a concrete file against a templated
    form, and the concrete checklist files are covered as forge-verify's own references
    besides.
    """
    return {
        name: {m.group(1) for m in CITE_RE.finditer(body)}
        for name, body in _skill_bodies()
    }


def _all_cited() -> set[str]:
    """The union of every skill's citations."""
    return {rel for cited in _citations_by_skill().values() for rel in cited}


#: Shared reference subtrees the builder fans WHOLE on any citation inside them, so every
#: file in the tree is reachable without a citation naming it individually. Kept
#: byte-aligned with `_WHOLE_DIR_FANNED_REFERENCE_ROOTS` in scripts/build-adapters.py.
WHOLE_DIR_FANNED_ROOTS: frozenset[str] = frozenset({"stacks", "verifier-patterns"})


def _whole_dir_fanned_roots(cited: set[str]) -> frozenset[str]:
    """Which whole-dir-fanned roots ANY citation triggers.

    `_fan_out_shared_references` (scripts/build-adapters.py) special-cases a citation whose
    first path segment is a WHOLE_DIR_FANNED_ROOTS member: ONE such citation — literal,
    `{stack}`-templated, or globbed — copies that ENTIRE tree into the skill's own
    `references/`. `stacks/` because the stack is unknown at build time; `verifier-patterns/`
    because the forge-verifier agent opens the index and follows its intra-dir links. Every
    file under such a root is therefore reachable without a citation naming it, and this
    guard models that rule rather than allowlisting the individual files, which would go
    stale the moment one is added (a new stack profile, a new verifier pattern).
    """
    return frozenset(
        root
        for root in WHOLE_DIR_FANNED_ROOTS
        if any(rel.split("/", 1)[0] == root for rel in cited)
    )


def _is_covered(
    owner: str | None,
    rel: str,
    by_skill: dict[str, set[str]],
    fanned_roots: frozenset[str],
    *,
    ignore_allowlist: bool = False,
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

    `ignore_allowlist=True` re-asks the question with the UNCITED_ALLOWLIST branch removed
    — "would this be covered even WITHOUT its allowlist entry?" — which is how
    `test_no_allowlist_entry_excuses_a_file_that_is_now_cited` decides an entry is stale.
    Without it that check is tautological: every allowlisted key returns True here, so the
    entry always looks covered.
    """
    if rel.split("/", 1)[0] in fanned_roots:
        return True
    if not ignore_allowlist and (owner, rel) in UNCITED_ALLOWLIST:
        return True
    if owner is not None:
        # A skill's own references/ ships wholesale, but only its OWNING skill (its body,
        # or the agent it preloads) reads it. Another skill citing the same relpath resolves
        # to *that* skill's own or the shared copy, never this one — so only the owner's
        # citation vouches. Pooling every body would let an unrelated skill's citation mark
        # this skill-own file "read" when nothing in its own skill reads it (the dead-prose
        # case the reverse guard exists to catch).
        return rel in by_skill.get(owner, set())
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
    fanned_roots = _whole_dir_fanned_roots(_all_cited())
    uncovered = [
        f"references/{rel}"
        + (" (shared — loses its skill-local fan-out)" if owner is None
           else f" (own to {owner} — shipped but read by nothing)")
        for owner, rel in _reference_files()
        if not _is_covered(owner, rel, by_skill, fanned_roots)
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
    fanned_roots = _whole_dir_fanned_roots(_all_cited())
    assert not _is_covered(None, "never-cited.md", by_skill, fanned_roots)


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
    assert not _is_covered(None, "prd-template.md", by_skill, fanned_roots=frozenset())
    # The same path as a SKILL-OWN file is covered — it ships with its own dir.
    assert _is_covered("forge-1-prd", "prd-template.md", by_skill, fanned_roots=frozenset())


def _describe(key: tuple[str | None, str]) -> str:
    owner, rel = key
    return f"references/{rel}" + ("" if owner is None else f" (own to {owner})")


def test_every_allowlist_entry_names_a_file_that_exists():
    """A stale allowlist entry is a silent hole: it excuses a path nothing enumerates."""
    enumerated = set(_reference_files())
    stale = [_describe(key) for key in UNCITED_ALLOWLIST if key not in enumerated]
    assert not stale, (
        "UNCITED_ALLOWLIST names reference files that no longer exist at that owner — "
        "delete the entries:\n  " + "\n  ".join(stale)
    )


def test_no_allowlist_entry_excuses_a_file_that_is_now_cited():
    """An entry that stopped being needed is an excuse left lying around.

    Existence alone does not keep the allowlist honest: once a file gains a real
    citation, its entry silently becomes a standing exemption for a future
    de-citation of the same path — the exact hole this guard closes.
    """
    by_skill = _citations_by_skill()
    fanned_roots = _whole_dir_fanned_roots(_all_cited())
    unnecessary = [
        _describe((owner, rel))
        for owner, rel in UNCITED_ALLOWLIST
        # Re-ask coverage with the allowlist itself taken OUT of the answer: an entry is
        # unnecessary only if the file is reachable by a real citation or a fan-out rule.
        if _is_covered(owner, rel, by_skill, fanned_roots, ignore_allowlist=True)
    ]
    assert not unnecessary, (
        "these UNCITED_ALLOWLIST entries are no longer needed — the files are cited "
        "or covered by a whole-dir fan-out rule; delete the entries:\n  "
        + "\n  ".join(unnecessary)
    )


def test_every_allowlist_entry_states_a_reason():
    """The allowlist is a record of decisions; an empty reason records nothing."""
    unexplained = [
        _describe(key) for key, why in UNCITED_ALLOWLIST.items() if len(why.strip()) < 20
    ]
    assert not unexplained, (
        "UNCITED_ALLOWLIST entries must say WHY the file is reachable without a "
        "citation:\n  " + "\n  ".join(unexplained)
    )


# --------------------------------------------------------------------------------------
# Guard 3 — reference→reference sibling edges (issue #282)
# --------------------------------------------------------------------------------------
#
# The two guards above are anchored on SKILL bodies: the builder's fan-out scans skill
# bodies, so it never follows a citation that lives INSIDE a reference. A reference that
# cites another reference by a BARE sibling name (`recovery-procedure.md`, no path) reads
# as "the file beside me" — but the cited sibling may live in a different dir and not
# travel with the fanned copy, so an agent opening it beside the fanned reference finds
# nothing. This guard walks the reference→reference edges the skill-body guards cannot see.
#
# A citation written as a FULL bundle path (`skills/forge-5-loop/references/x.md`) is NOT
# a sibling read — it resolves from the bundle root, where every skill's tree ships — so
# the detector below (a lookbehind barring `/`) deliberately ignores it.

#: Reference basenames that are also the names of files a skill SCAFFOLDS into a target
#: repo (root-hygiene / docs output), so a bare mention names that output file, never a
#: reference to open beside the citing one. Their template forms are always cited by full
#: `references/templates/.../` path, which the detector ignores anyway.
_SCAFFOLD_OUTPUT_BASENAMES: frozenset[str] = frozenset({"AGENTS.md", "CLAUDE.md", "README.md"})

#: Bare reference→reference sibling citations deliberately allowed, each with the reason it
#: is safe. Keyed by (citing reference's repo-relative path, cited basename). Same
#: discipline as UNCITED_ALLOWLIST: a claim that must stay true, enforced below.
SIBLING_CITATION_ALLOWLIST: dict[tuple[str, str], str] = {
    ("references/stage-exit-protocol.md", "findings-template.md"): (
        "a provenance mention that names the OWNER in prose (\"forge-verify's "
        "`findings-template.md`\") to contrast two mechanisms — not a beside-me read; and "
        "stage-exit-protocol.md is a prose-change-gated surface, so rewording a "
        "non-behavioral provenance line is not worth a compliance-eval round"
    ),
}


def _all_reference_paths() -> list[Path]:
    """Every markdown reference in canon: shared (`references/`) and skill-own."""
    return sorted(REFERENCES.rglob("*.md")) + sorted(SKILLS.glob("*/references/**/*.md"))


def _reference_basenames() -> set[str]:
    return {p.name for p in _all_reference_paths()}


def _bare_sibling_citations(path: Path, basenames: set[str]) -> list[str]:
    """Reference basenames the given file cites as a BARE sibling — not path-prefixed, not
    its own name, not a scaffold-output name.

    Anchored on `name in basenames` (a file that really exists as a reference somewhere) BY
    DESIGN, and this is the guard's deliberate scope boundary. The bare backticked `<x>.md`
    form is shared by ~50 NON-citations across canon: pipeline artifacts an agent writes at
    runtime (`PRD.md`, `EPIC.md`, `tech-spec.md`, `progress.md`, `TRACEABILITY.md`),
    spec-document examples, and generated docs (`api-reference.md`). So the guard covers the
    actual #282 gap — a real reference cited as a bare sibling that lives elsewhere and does
    not travel with the fanned copy — and it deliberately CANNOT flag a citation of a file
    that exists NOWHERE (a typo, or a since-deleted target): that shape is indistinguishable
    from those legitimate artifact/spec/output mentions, so catching it would need a
    different, non-form-based signal, not a wider net here (which would false-positive on
    all ~50)."""
    body = read(path)
    hits: list[str] = []
    for name in sorted(basenames):
        if name == path.name or name in _SCAFFOLD_OUTPUT_BASENAMES:
            continue
        # Bare = not preceded by `/` (a full path) or a word/hyphen char (a longer token),
        # and not followed by a word char (so `foo.md` never matches inside `foo.mdx`).
        if re.search(r"(?<![/\w-])" + re.escape(name) + r"(?![\w])", body):
            hits.append(name)
    return hits


def _rel(path: Path) -> str:
    """Repo-relative POSIX path (REFERENCES.parent is the repo root)."""
    return path.relative_to(REFERENCES.parent).as_posix()


def test_no_reference_cites_a_bare_sibling_absent_from_its_own_dir():
    """Guard 3 (issue #282): reference→reference sibling edges the skill-body guards miss.

    A bare `<name>.md` in a reference reads as a file beside it; if that sibling lives
    elsewhere it does not travel with the fanned copy. Fix by rewording self-contained,
    using a full `skills/.../references/<name>.md` bundle path (resolves from the root in
    every bundle), or — for a genuinely safe case — a SIBLING_CITATION_ALLOWLIST entry.
    """
    basenames = _reference_basenames()
    offenders = [
        f"{_rel(path)} -> {name} (absent from {_rel(path.parent)}/)"
        for path in _all_reference_paths()
        for name in _bare_sibling_citations(path, basenames)
        if not (path.parent / name).is_file()
        and (_rel(path), name) not in SIBLING_CITATION_ALLOWLIST
    ]
    assert not offenders, (
        "these references cite a bare sibling that is not beside them (issue #282) — an "
        "agent reading the fanned copy would find nothing; reword self-contained, use a "
        "full bundle path, or allowlist with a reason:\n  " + "\n  ".join(offenders)
    )


def test_guard3_detector_fires_on_a_bare_sibling_but_not_a_full_path():
    """Non-vacuity: the detector must match the shape it guards and ignore a full path."""
    name = "recovery-procedure.md"
    pat = r"(?<![/\w-])" + re.escape(name) + r"(?![\w])"
    assert re.search(pat, "see `recovery-procedure.md` for the rule"), (
        "detector stopped matching a bare sibling citation"
    )
    assert not re.search(pat, "see `skills/forge-5-loop/references/recovery-procedure.md`"), (
        "detector wrongly matches a full bundle path (not a sibling read)"
    )


def test_guard3_scans_a_nonempty_reference_set():
    """A glob that matched nothing would satisfy Guard 3 trivially."""
    assert len(_all_reference_paths()) >= 10
    assert len(_reference_basenames()) >= 10


def test_sibling_allowlist_entries_are_still_needed_and_explained():
    """Each SIBLING_CITATION_ALLOWLIST entry must name a citation that is really present
    and really absent from its dir (else it is a stale standing exemption), and give a
    reason — the same honesty discipline as UNCITED_ALLOWLIST."""
    basenames = _reference_basenames()
    for (rel, name), why in SIBLING_CITATION_ALLOWLIST.items():
        assert len(why.strip()) >= 20, f"{rel} -> {name}: allowlist entry needs a reason"
        path = REFERENCES.parent / rel
        assert path.is_file(), f"{rel}: allowlisted citing file does not exist"
        assert name in _bare_sibling_citations(path, basenames), (
            f"{rel} -> {name}: no longer a bare sibling citation — delete the stale entry"
        )
        assert not (path.parent / name).is_file(), (
            f"{rel} -> {name}: the sibling is now beside it — the entry is unnecessary"
        )


# --------------------------------------------------------------------------------------
# Robustness fixes surfaced by the #296 review (issue #297)
# --------------------------------------------------------------------------------------


def test_ignore_allowlist_makes_is_covered_consult_real_coverage():
    """`_is_covered(..., ignore_allowlist=True)` must re-ask coverage without the allowlist.

    Non-vacuity for the fix to test_no_allowlist_entry_excuses_a_file_that_is_now_cited:
    without the flag every allowlisted key returns True here, so that necessity check is
    tautological. Asserted PER ENTRY (a for-loop is empty-safe — an emptied allowlist has
    nothing to prove — where an `any(...)` would fail spuriously on the empty set): each
    entry is covered WITH the allowlist and NOT covered without it, i.e. genuinely
    allowlist-dependent (an entry covered without it would be flagged by the sibling test).
    """
    by_skill = _citations_by_skill()
    fanned = _whole_dir_fanned_roots(_all_cited())
    for (o, r) in UNCITED_ALLOWLIST:
        assert _is_covered(o, r, by_skill, fanned), (
            f"{o, r}: an allowlisted entry should be covered via the allowlist branch"
        )
        assert not _is_covered(o, r, by_skill, fanned, ignore_allowlist=True), (
            f"{o, r}: covered even without its allowlist entry — the flag proves the "
            "necessity check is not tautological, and this entry is then unnecessary"
        )


def test_skill_own_coverage_requires_the_owning_skills_own_citation():
    """A skill-own reference is covered only by its OWNING skill's citation, never by an
    unrelated skill that happens to cite the same relpath (the cross-skill pooling the
    reverse guard's shared branch already forbids; the owner branch now matches it)."""
    by_skill = {"skill-a": set(), "skill-b": {"foo.md"}}
    assert not _is_covered("skill-a", "foo.md", by_skill, frozenset()), (
        "skill-a owns foo.md but never cites it; skill-b's citation must not vouch for it"
    )
    assert _is_covered("skill-b", "foo.md", by_skill, frozenset()), (
        "the owning skill's own citation is coverage"
    )


def test_strip_frontmatter_uses_the_builders_line_fence_rule():
    """`_strip_frontmatter` matches the builder's LINE-based `.strip() == '---'` fence rule
    (not a `find("\\n---")` substring scan), and returns the whole text as body when there
    is no well-formed frontmatter (the build's own guard polices malformed files)."""
    marker = "references/x.md"
    # A value line that merely starts with `---` is NOT a closing fence.
    tricky = "---\nname: n\ntag: ---x\n---\nBODY " + marker
    assert _strip_frontmatter(tricky).strip() == "BODY " + marker, "closed on a non-fence value line"
    # `.strip()` on the fence lines tolerates CRLF fences (input is normalized upstream anyway).
    crlf = "---\r\nname: n\r\n---\r\nBODY " + marker
    assert _strip_frontmatter(crlf).strip() == "BODY " + marker, "line-based rule mishandled CRLF fences"
    # No opening fence → whole text is body (not re-policed here).
    assert _strip_frontmatter("no frontmatter " + marker) == "no frontmatter " + marker
    # Unterminated frontmatter → whole text is body (build guard raises on it).
    assert _strip_frontmatter("---\nname: n\nno close " + marker) == "---\nname: n\nno close " + marker
