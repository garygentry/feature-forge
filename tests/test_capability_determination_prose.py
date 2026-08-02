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
    resolved by advancing to the production successor. This is FOUR independent
    obligations, and they are pinned as four independently-required sub-clauses,
    because a surface can state any of them while dropping the others: (c1a) the gate
    obligation — the directive is presented through the gate; (c1b) the dispatch
    obligation — the gate's affirmative choice DISPATCHES the verifier, rather than
    printing a command for the user to run later; (c2) the no-skip obligation — it is
    never silently skipped; (c3) the no-advance obligation — it is never resolved by
    advancing past unresolved verification. Merging any two of them into one any-of
    list is not enough, measured twice: inverting "never grounds to skip verification"
    into "IS grounds to skip verification entirely" left the merged c2/c3 matching on
    the untouched no-advance phrasing in the same sentence (four surfaces), and while
    c1a and c1b shared a list, rewriting the *dispatch clause* — `forge-verify`'s
    "dispatched on the affirmative choice" into "printed for the user" — left the
    merged clause matching on all six: "presented through the gate" was untouched on
    `forge-verify`, `forge-fix` kept "presented through the Step 6 gate", and the four
    authoring stages carried no dispatch phrasing at all — each surface satisfied the
    merged list on its own gate fragment.

    Note what is deliberately NOT pinned: relabelling only the gate's *option*
    (`*Verify now*` → `*Print the verify command for the user to run later*`) still
    passes, and must. The obligation now lives in its own clause of the sentence, so
    relabelling the option makes the prose self-contradictory — "choose *Print the
    command*" one clause before "the verifier is dispatched on the affirmative choice,
    never merely printed" — without unsaying the obligation. Pinning the label would
    re-admit a gate-SHAPE token, the `"choice 2 omitted"` mistake this module removed
    once already, and it could not be a `CLAUSES` fragment in any case: `forge-verify`
    and `forge-fix` render no option label at all (`*Verify now*` occurs 0 times in
    each), so any label fragment would be an authoring-stage-only token that breaks the
    six-surface uniformity of the clause set. The label is left to the clause that
    glosses it, one line away.

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

import ast
from collections.abc import Iterator
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

#: The clauses, each satisfied by ANY of its accepted phrasings. Fragments are
#: short and load-bearing so the guard survives rewording around them but not deletion
#: of the requirement. Multiple phrasings per clause are not slack: the surfaces really
#: do say the same thing differently — `forge-verify` writes "Reserve `manual` for no
#: question mechanism and no permitted dispatch" where the authoring stages write
#: "`interactive`, not `manual`" — and forcing one wording would be a rewrite of canon
#: disguised as a test.
#: Every fragment must carry the clause's MEANING, so that rewriting the sentence into
#: the misreading the clause exists to prevent breaks the match. Two fragments failed
#: that bar and were removed:
#:
#:   * `"Reserve \`manual\`"` (clause b) — a bare token with no semantic content.
#:     `forge-verify` matched clause (b) on it alone, so rewriting its sentence to
#:     "Reserve `manual` for any session that may not dispatch a subagent unsolicited"
#:     — precisely the misreading §6.2 exists to prevent — left the guard green.
#:     The accepted phrasing now requires the *conjunction*.
#:   * `"Standard Verify Gate first when you may not dispatch unsolicited"` (clause c)
#:     — that sentence lives in the DIRECTIVES-consumption paragraph, which is
#:     verbatim boilerplate in all nine exit skills including the three that carry no
#:     capability prose at all. Every surface matched it for free, and `forge-fix`
#:     matched clause (c) on nothing else; deleting the real clause-(c) sentence from
#:     two surfaces left the guard green both times.
#:   * `"choice 2 omitted"` (clause c) — a gate-SHAPE token, not a clause. It says how
#:     many options the gate offers, which is true of a production stage and meaningless
#:     on a branch stage, and it carries neither the gate obligation nor the no-skip
#:     one. It admitted the misreading twice over: inverting "is never grounds to skip
#:     verification" to "IS grounds to skip verification entirely" left the guard green
#:     on five surfaces, and — because the token is production-stage-only — accepting it
#:     as clause-(c) evidence is what let `forge-fix`, a BRANCH stage, be "repaired" by
#:     pasting production-stage prose describing a directive path it can never emit
#:     (round-3 V-001). Clause (c) is now four required sub-clauses so no obligation can go
#:     unsaid.
CLAUSES: Final[dict[str, tuple[str, tuple[str, ...]]]] = {
    "a": (
        "capability is a permission test, not a tool-presence test",
        ("dispatch, not a listed tool",),
    ),
    "b": (
        "consent-gated dispatch is `interactive`; `manual` needs neither mechanism",
        (
            "`interactive`, not `manual`",
            "**no** question mechanism **and** **no** permitted dispatch",
        ),
    ),
    "c1a": (
        "an auto-verify directive under a dispatch bar is routed through the gate",
        (
            "presented through the gate",
            # `forge-fix` names *which* gate, because it has two numbered steps a
            # directive could plausibly route through. Same obligation, one word wider.
            "presented through the Step 6 gate",
            # The four authoring stages state the gate obligation mechanically rather than
            # narratively: they name the block the directive is routed through. Deleting
            # it leaves no statement that the directive is gated at all.
            "reuse the Standard Verify Gate block for consent",
        ),
    ),
    "c1b": (
        "and the gate's affirmative choice DISPATCHES the verifier rather than "
        "printing a command for the user to run later",
        ("dispatched on the affirmative",),
    ),
    "c2": (
        "that directive is never silently skipped",
        (
            "never grounds to skip verification",
            "never skipped",
        ),
    ),
    "c3": (
        "and is never resolved by advancing past unresolved verification",
        (
            "never grounds to fence the production successor",
            "never resolved by advancing to the production successor",
            "never resolved by closing with an outcome that advances the pipeline",
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


def _capability_paragraph(text: str) -> str:
    """The single paragraph in which this surface determines capability.

    Clause matching is scoped to this paragraph rather than the whole file, because
    a whole-file match let boilerplate elsewhere satisfy the clauses for free — the
    DIRECTIVES-consumption paragraph is verbatim in all nine exit skills, so any
    fragment appearing there is matched by every surface regardless of what its
    capability prose actually says. A clause must be stated where the decision is
    made, or the guard is asserting the existence of boilerplate.

    Paragraphs are blank-line separated, matching how these skill bodies are written.
    Returns `""` when no paragraph carries a lead-in, which fails every clause rather
    than passing vacuously.
    """
    for block in text.replace("\r\n", "\n").split("\n\n"):
        if any(lead in block for lead in CAPABILITY_LEAD_INS):
            return block
    return ""


def _markdown_section(text: str, heading: str) -> str:
    """The body of the `## {heading}` section, up to the next same-or-higher heading.

    The shared rule in `references/shared-conventions.md` states the clauses across a
    bulleted section rather than in one paragraph, so it is scoped by section instead.
    The point of scoping is identical: keep unrelated boilerplate from satisfying a
    clause on the strength of appearing somewhere in the same file.
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


def _assert_capability_prose(surface: str, where: str) -> None:
    """Raise `AssertionError` unless `surface` states every clause.

    Takes the surface's **text**, not a path, so the negative controls can call it on
    mutated copies without ever writing to the repository. Matching is scoped to the
    capability paragraph — see `_capability_paragraph`.
    """
    paragraph = _capability_paragraph(surface)
    assert paragraph, (
        f"{where}: no capability-determining paragraph found — the lead-in is gone, "
        "so the clauses below cannot be located, let alone satisfied"
    )
    _assert_clauses_in(paragraph, where, "capability paragraph")


def _assert_clauses_in(scope: str, where: str, scope_name: str) -> None:
    """Assert every clause — (c) counted as its four required sub-clauses — is in `scope`."""
    for clause, (description, fragments) in CLAUSES.items():
        assert any(fragment in scope for fragment in fragments), (
            f"{where}: capability clause ({clause}) is gone — {description}. "
            f"None of these phrasings survive in the {scope_name}: {list(fragments)}"
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
# Guard 1 — every determining surface states every clause
# --------------------------------------------------------------------------------------


def test_every_capability_determining_surface_states_all_the_clauses():
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
    section = _markdown_section(read(CONVENTIONS), "Verify Capability")
    assert section, "references/shared-conventions.md lost its Verify Capability section"
    _assert_clauses_in(
        section, "references/shared-conventions.md", "Verify Capability section"
    )
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
# Guard 2 — the negative controls spec 07 §6.2 mandates (control 3 split per sub-clause)
#
# Each operates on a COPIED string. None writes to the repository.
# --------------------------------------------------------------------------------------


#: The controls run over EVERY determining surface, not one representative. A single
#: representative hid a real hole: `forge-1-prd` satisfies clause (b) through
#: "`interactive`, not `manual`", so the control never exercised the *other* accepted
#: phrasing, and `forge-verify` — the only surface that uses it — was degradable
#: undetected. A per-surface parametrization makes each roster entry its own control.
ALL_SURFACES: Final[list[tuple[str, str]]] = _capability_surfaces()
SURFACE_IDS: Final[list[str]] = [relpath for relpath, _ in ALL_SURFACES]


@pytest.mark.parametrize("relpath,base", ALL_SURFACES, ids=SURFACE_IDS)
def test_rewriting_clause_a_to_tool_presence_wording_fails_the_guard(
    relpath: str, base: str
):
    """Negative control 1: capability restated as "do I have the tool" must be caught."""
    _assert_capability_prose(base, f"{relpath} (control-base)")  # the base is compliant

    mutated = base.replace(
        "dispatch, not a listed tool",
        "dispatch, which requires the tool to be listed in my tool surface",
    )
    assert mutated != base, (
        f"{relpath}: clause (a)'s wording moved — this control now mutates nothing"
    )
    with pytest.raises(AssertionError, match=r"clause \(a\)"):
        _assert_capability_prose(mutated, f"{relpath} (control-1)")


@pytest.mark.parametrize("relpath,base", ALL_SURFACES, ids=SURFACE_IDS)
def test_downgrading_the_consent_case_to_manual_fails_the_guard(relpath: str, base: str):
    """Negative control 2: calling a consent-gated session `manual` must be caught.

    The `Reserve \\`manual\\`` mutation is the one N-5 measured: rewriting it to
    "for any session that may not dispatch a subagent unsolicited" is exactly the
    misreading the clause exists to prevent, and it used to leave the guard green.
    """
    mutated = base.replace("`interactive`, not `manual`", "`manual`, not `interactive`")
    mutated = mutated.replace(
        "Reserve `manual` for **no** question mechanism **and** **no** permitted dispatch",
        "Reserve `manual` for any session that may not dispatch a subagent unsolicited",
    )
    assert mutated != base, (
        f"{relpath}: clause (b)'s wording moved — this control now mutates nothing"
    )
    with pytest.raises(AssertionError, match=r"clause \(b\)"):
        _assert_capability_prose(mutated, f"{relpath} (control-2)")


@pytest.mark.parametrize("relpath,base", ALL_SURFACES, ids=SURFACE_IDS)
def test_deleting_the_auto_path_through_the_gate_fails_the_guard(relpath: str, base: str):
    """Negative control 3a-i: dropping the "auto directive goes through the gate" obligation.

    With the shared DIRECTIVES boilerplate no longer an accepted phrasing, this
    control now deletes only sentences that live in the capability paragraph — a
    degradation a real edit would produce, which was not true before. It is split
    from 3a-ii, 3b and 3c because (c)'s four obligations are independently droppable:
    while they shared one fragment list, a surface that stated any one of them
    satisfied all of them.
    """
    mutated = base
    for fragment in CLAUSES["c1a"][1]:
        mutated = mutated.replace(fragment, "")
    assert mutated != base, (
        f"{relpath}: clause (c1a)'s wording moved — this control now mutates nothing"
    )
    with pytest.raises(AssertionError, match=r"clause \(c1a\)"):
        _assert_capability_prose(mutated, f"{relpath} (control-3a-i)")


@pytest.mark.parametrize("relpath,base", ALL_SURFACES, ids=SURFACE_IDS)
def test_downgrading_the_affirmative_choice_to_a_printed_command_fails_the_guard(
    relpath: str, base: str
):
    """Negative control 3a-ii: dropping the "the affirmative choice dispatches" obligation.

    Pinned apart from 3a-i because routing the directive through the gate and then
    *printing* the verify command on the affirmative choice — the `manual-print` path
    the capability rule exists to keep separate — satisfies the gate obligation while
    abandoning the dispatch one. While c1a and c1b shared one any-of list this
    misreading was undetected on all six surfaces: rewriting `forge-verify`'s
    "dispatched on the affirmative choice" to "printed for the user" left the
    untouched "presented through the gate" matching on `forge-verify`, `forge-fix`
    matching on its own "presented through the Step 6 gate", and the four authoring
    stages matching on their gate-block fragment — they carried no dispatch phrasing
    at all, so the mutation was a no-op there.
    """
    mutated = base
    for fragment in CLAUSES["c1b"][1]:
        mutated = mutated.replace(fragment, "")
    assert mutated != base, (
        f"{relpath}: clause (c1b)'s wording moved — this control now mutates nothing"
    )
    with pytest.raises(AssertionError, match=r"clause \(c1b\)"):
        _assert_capability_prose(mutated, f"{relpath} (control-3a-ii)")


@pytest.mark.parametrize("relpath,base", ALL_SURFACES, ids=SURFACE_IDS)
def test_deleting_the_no_skip_obligation_fails_the_guard(relpath: str, base: str):
    """Negative control 3b: dropping the "never skipped" obligation.

    This is the obligation that had NO pin of its own while `"choice 2 omitted"` was
    accepted as clause-(c) evidence: inverting "is never grounds to skip
    verification" into "IS grounds to skip verification entirely" — the exact
    misreading §6.2 exists to prevent — left the guard green on five of the six
    surfaces, and still did after (c) was merely split in two, because the
    no-advance phrasing in the same sentence went on matching.
    """
    mutated = base
    for fragment in CLAUSES["c2"][1]:
        mutated = mutated.replace(fragment, "")
    assert mutated != base, (
        f"{relpath}: clause (c2)'s wording moved — this control now mutates nothing"
    )
    with pytest.raises(AssertionError, match=r"clause \(c2\)"):
        _assert_capability_prose(mutated, f"{relpath} (control-3b)")


@pytest.mark.parametrize("relpath,base", ALL_SURFACES, ids=SURFACE_IDS)
def test_deleting_the_no_advance_obligation_fails_the_guard(relpath: str, base: str):
    """Negative control 3c: dropping the "never resolved by advancing past" obligation.

    Pinned separately from 3b for the mirror-image reason: a surface that keeps its
    no-skip sentence while dropping the promise not to advance past unresolved
    verification has given up the obligation that actually fences the successor.
    """
    mutated = base
    for fragment in CLAUSES["c3"][1]:
        mutated = mutated.replace(fragment, "")
    assert mutated != base, (
        f"{relpath}: clause (c3)'s wording moved — this control now mutates nothing"
    )
    with pytest.raises(AssertionError, match=r"clause \(c3\)"):
        _assert_capability_prose(mutated, f"{relpath} (control-3c)")


def _module_scope_nodes(tree: ast.Module) -> Iterator[ast.AST]:
    """Every statement executing in MODULE scope, at any control-flow nesting depth.

    `tree.body` alone sees depth 0 only, so `if True:` one level down hid a genuine
    module-global re-binding. `ast.walk` alone would also descend into function and
    class bodies, where a plain local of the same name rebinds nothing at module scope
    and would be a false positive. Descending through control flow but stopping at
    function and class bodies covers every module-level BINDING STATEMENT. It is
    deliberately NOT exhaustive: an assignment inside a function that declares
    `global ALL_SURFACES` also replaces the global and is out of this traversal's reach.
    See the comment in `test_the_controls_cover_every_determining_surface` for the full
    list of binding forms left out of scope, and why.
    """
    stack: list[ast.AST] = list(tree.body)
    while stack:
        node = stack.pop()
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue  # a new scope — its bindings are not this module's globals
        stack.extend(ast.iter_child_nodes(node))


def _store_target_names(target: ast.AST) -> Iterator[str]:
    """The module-global name a store target reaches, through every wrapper.

    `ALL_SURFACES[:] = [...]` stores into a `Subscript` and re-binds nothing at all,
    yet the roster every `parametrize` reads is replaced just the same — so the name
    is recovered from inside subscripts, attributes, starred targets and tuple
    unpackings rather than only from a bare `Name`.
    """
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, (ast.Subscript, ast.Attribute, ast.Starred)):
        yield from _store_target_names(target.value)
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            yield from _store_target_names(element)


def _module_scope_writes(tree: ast.Module, name: str) -> list[ast.AST]:
    """Module-scope statements binding or mutating `name` as an `Assign`, `AnnAssign`
    or `AugAssign` — including stores reached through a subscript, attribute, star or
    tuple target. Not every binding form: see the comment in
    `test_the_controls_cover_every_determining_surface` for what is out of scope."""
    writes: list[ast.AST] = []
    for node in _module_scope_nodes(tree):
        if isinstance(node, ast.Assign):
            targets: list[ast.AST] = list(node.targets)
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
            targets = [node.target]
        else:
            continue
        if any(
            reached == name for target in targets for reached in _store_target_names(target)
        ):
            writes.append(node)
    return writes


def test_the_controls_cover_every_determining_surface():
    """The control parametrization is the roster, not a sample of it."""
    assert len(ALL_SURFACES) >= MIN_CAPABILITY_SURFACES, (
        f"only {len(ALL_SURFACES)} surfaces parametrize the negative controls "
        f"(floor {MIN_CAPABILITY_SURFACES})"
    )
    # NOT `SURFACE_IDS == [relpath for relpath, _ in _capability_surfaces()]`: both
    # sides are the same pure function of the same files, so within one process that
    # is `f() == f()` and cannot fail — it advertised drift detection it did not
    # provide. The property actually at risk is someone replacing the derived roster
    # with a literal list at module level, so assert the derivation itself.
    #
    # Asserted STRUCTURALLY, via `ast`, and not as a substring search: a search for
    # the assignment's own text would be satisfied by this assertion's source line,
    # since the needle would then occur twice in the file it reads — once at the
    # assignment and once here. That is the vacuity round-3 V-002 named, and the substring
    # form of this very assertion shipped with it (round-4 V-001). A test that reads
    # its own file may only assert ABSENCE (see `test_this_guard_is_not_skippable`),
    # or must assert over parsed structure rather than raw text, as here.
    #
    # Every module-level binding of the name is counted, not just the annotated one,
    # because a single-node check is satisfied by a DECOY: keeping the derived
    # `AnnAssign` and re-binding `ALL_SURFACES = [<hand-kept tuples>]` below it left
    # this guard green while `SURFACE_IDS` and every `parametrize` took the shadowed
    # value. The callee is pinned as a `FunctionDef` and asserted un-rebound for the
    # mirror reason: `func.id` is compared textually, so aliasing the derivation name
    # (`_capability_surfaces = _hand_kept_surfaces`) was equally invisible.
    #
    # Written over binding FORMS and SCOPES rather than over one node, deliberately.
    # Four consecutive rounds closed exactly the shape each was shown, and the next
    # round found the next shape immediately: a plain `Assign` decoy, then an aliasing
    # `Assign`, then an ANNOTATED alias (`_capability_surfaces: Final = …`) that the
    # `Assign`-only alias check could not see even though the roster check twelve lines
    # up already counted both forms, then a binding one level below `tree.body`, an
    # in-place `ALL_SURFACES[:] = …` that re-binds nothing, and a second `def` shadowing
    # the first. None of those is a new IDEA — each is the same idea spelled with a
    # different node — so the check now enumerates the binding forms (`Assign`,
    # `AnnAssign`, `AugAssign`, and stores reached through a subscript, attribute,
    # star or tuple) across every module-scope nesting level, and pins the definition
    # count, instead of naming instances one round at a time.
    #
    # DELIBERATELY OUT OF SCOPE, a recorded decision (round-7 Decision 1(c)), NOT an
    # oversight: `NamedExpr` (walrus `(ALL_SURFACES := …)`), a `For`/`AsyncFor` loop
    # target, `with … as`, a comprehension target, `import … as`, `except … as`, a
    # `match`-capture (`case ALL_SURFACES`), and an assignment inside a called function
    # that declares `global ALL_SURFACES` all replace the roster and are NOT caught here.
    # Each of THOSE was probed and confirmed to leave the suite green with the roster
    # displaced. (`del ALL_SURFACES` is a separate case, not one of them: it UNBINDS
    # rather than replaces, and cannot be a green-and-displaced decoy — placed before the
    # `SURFACE_IDS`/`parametrize` reads it raises `NameError` at collection, placed after
    # them the roster is already captured.) They are left open for the same reason
    # `SURFACES_WITHOUT_PROSE` records rather than closes its hole: the space of ways to
    # rebind a Python name is not enumerable by adding node types (five consecutive
    # rounds each closed the shape it was shown and the next round found the next one),
    # every one of these paths requires a hand-planted decoy, and none is live drift.
    # The ONE property that actually matters — replacing the derivation
    # `_capability_surfaces()` at the single annotated binding with a literal list — IS
    # caught, but NOT "regardless of binding form": the count assertion reds any
    # ADDITIONAL counted binding (`Assign`/`AnnAssign`/`AugAssign`), and the
    # derivation-`Call` assertion reds a literal VALUE at that one annotated binding. A
    # literal installed through one of the out-of-scope forms above is NOT caught — it
    # leaves the real derivation as `bindings[0]` — and that is the recorded, accepted
    # residue, not a claim of coverage.
    tree = ast.parse(read(Path(__file__).resolve()))
    bindings = _module_scope_writes(tree, "ALL_SURFACES")
    assert len(bindings) == 1, (
        f"ALL_SURFACES is bound or mutated {len(bindings)} times at module level — a "
        "later re-binding would shadow the derived roster while leaving this check green"
    )
    assert isinstance(bindings[0], ast.AnnAssign), (
        "ALL_SURFACES is no longer a module-level ANNOTATED assignment — the annotation "
        "is what makes the single binding legible as the roster's one definition"
    )
    assert (
        isinstance(bindings[0].value, ast.Call)
        and getattr(bindings[0].value.func, "id", None) == "_capability_surfaces"
    ), (
        "ALL_SURFACES is no longer derived from the canonical exit table — the "
        "controls now run over a hand-kept list, which is the drift they exist to catch"
    )
    definitions = [
        node
        for node in _module_scope_nodes(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and node.name == "_capability_surfaces"
    ]
    assert len(definitions) == 1, (
        f"_capability_surfaces is defined {len(definitions)} times at module level — a "
        "later redefinition shadows the derivation while leaving this check green"
    )
    assert not _module_scope_writes(tree, "_capability_surfaces"), (
        "_capability_surfaces is re-bound at module level — the derivation name is aliased"
    )


# --------------------------------------------------------------------------------------
# Guard 3 — the guard itself
# --------------------------------------------------------------------------------------


def test_this_guard_is_not_skippable():
    """No skip gate may be introduced here — an unskippable guard is the whole point."""
    source = read(Path(__file__).resolve())
    for banned in ("skipif", "importorskip", "pytest.skip"):
        # Only the prose above may mention them; no call may be made.
        assert f"{banned}(" not in source, f"{banned} gate introduced in the drift guard"
