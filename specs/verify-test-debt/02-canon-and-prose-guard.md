# 02 — Canon and the Prose Guard

> The R-10 workstream: state the capability-determination rule **once** in canon, close the
> one surface that carries neither the rule nor a pointer to it, and collapse
> `tests/test_capability_determination_prose.py` from a 6-clause × 6-surface exact-markdown
> grid into four presence assertions.
>
> Builds on `00-core-definitions.md` §3 (the clause set), §4 (the surface roster), and §5
> (the meta-guard declaration format). Nothing defined there is redefined here.
>
> Locate every symbol by **name**, never by line number (C-07).

## Requirement Coverage

| REQ ID | Requirement | Section |
|---|---|---|
| REQ-GUARD-01 | The rule exists as a single canonical section stating every clause; `shared-conventions.md` stays a summary | §2 |
| REQ-GUARD-02 | Every surface restates the paragraph **or** carries a pointer; none silently carries neither | §4.6, §5 |
| REQ-GUARD-03 | The `forge-0-epic` gap is closed **in canon**, not in a test-side exclusion constant | §3, §6.3 |
| REQ-GUARD-04 | The guard file contains at most 5 tests, covering exactly the enumerated protection set | §4.1, §4.9, §6 |
| REQ-GUARD-05 | The guard declares its protection set and its explicit non-goals in the file | §4.2 |
| REQ-GUARD-06 | Exact-markdown fidelity is a **declared non-goal** the guard must not assert | §5.3, §6.2, §9 |
| REQ-GUARD-07 | The AST self-inspection layer is deleted | §6.2 |

Supporting decisions traced but not owned here: REQ-CANON-01 (adapter regeneration, §8),
REQ-CANON-03 (narration states intent only, §4.3 and §7.3).

---

## 1. Purpose and Scope

This document owns exactly two canon files and one test file:

| File | Change | Requirement | Owner per `01-architecture-layout.md` §3.1 |
|---|---|---|---|
| `references/stage-exit-protocol.md` | Confirm § "Host and capability determination" states all six clauses; **complete it where it does not** | REQ-GUARD-01 | this document |
| `skills/forge-0-epic/SKILL.md` | Add one pointer sentence in Step C8 | REQ-GUARD-03 | this document |
| `tests/test_capability_determination_prose.py` | Full rewrite, 43 collected items → 4 | REQ-GUARD-04..07 | this document |

`references/shared-conventions.md` is **not edited** (`01-architecture-layout.md` §2 marks it
UNCHANGED). Why it is not edited is a decision, stated in §2.4.

**Out of this document:** `tests/test_stage_exit_protocol.py` is owned by
`03-machinery-trim.md`. This document only *imports* from it, under the hard constraint in
`01-architecture-layout.md` §5.3.

---

## 2. Canon: the single canonical statement (REQ-GUARD-01)

### 2.1 The decision, restated from the foundation

The single canonical statement is `references/stage-exit-protocol.md` §
"Host and capability determination" (`00-core-definitions.md` §3.1, resolving OQ-02). This
is a **confirm-and-complete** job, not an authoring job: the section exists, both existing
pointer surfaces already name it *by section title*, and every restating surface already
cites it as the "full rule".

The required clause set is `00-core-definitions.md` §3.2 — six clauses keyed `a`, `b`,
`c1a`, `c1b`, `c2`, `c3`. It is not restated here.

### 2.2 What the section states today — the confirm half, verified against the file

Read from `references/stage-exit-protocol.md`, section body running from the `##
Host and capability determination` heading to the next `##` heading (which includes its
`### Clean-room unavailable, or a non-answer` subsection):

| Clause | Stated in the section today? | Evidence in the file |
|---|---|---|
| **a** | **Yes** | `**(b) tests PERMISSION, not tool presence.**` and `"**may I dispatch \`forge-verifier\` right now**"` |
| **b** | **Yes** | `**A consent requirement is \`interactive\`, not \`manual\`.**` and `Pass \`manual\` only when there is **no** question mechanism **and** **no** permitted dispatch` |
| **c1a** | **No** | The section names the gate only as the thing that *supplies consent* ("The Standard Verify Gate's own prompt supplies the missing user request"). The routing obligation is stated in `### \`runInStageVerify: true\` — in-stage auto-verify {stageNoun}`, a **different section** under `## Directive contract`. |
| **c1b** | **No** | "dispatch on the affirmative choice" appears in `### \`runInStageVerify: true\``, not in this section. |
| **c2** | **No** | The section contains no no-skip statement at all. The obligation lives in `references/shared-conventions.md` § "Verify Capability" ("never grounds to skip verification"). |
| **c3** | **Partly, and not on this axis** | `**Never reuse an earlier payload that promotes production advancement.**` is in the recovery subsection and is about a *disproved capability claim*, not about a *dispatch bar*. It does not state the c3 obligation. |

Additionally, the `host`-is-not-a-proxy rule (`00-core-definitions.md` §3.2, final
paragraph) **is** present: `**Do not use \`host == claude\` as a capability proxy.**`

> **Inconsistency recorded.** `00-core-definitions.md` §3.1 states that the section
> "already states every clause below". Against the file as it stands that is true of `a`
> and `b` only. `tech-spec.md` §3.1 is the more precise claim — it enumerates "clause (a),
> clause (b), the permission fact, the consent fact, the `host`-is-not-a-proxy rule, and …
> the recovery path", and it does **not** claim `c1a`, `c1b`, `c2`, or `c3`. REQ-GUARD-01's
> words are "stating every required clause", so the completion in §2.3 is required work,
> not optional polish. This is the "complete" half of confirm-and-complete.

### 2.3 What must be added — the completion

**One paragraph** is added to § "Host and capability determination", carrying `c1a`, `c1b`,
`c2`, and `c3`. It gathers into the canonical section obligations that today are scattered
across `### \`runInStageVerify: true\`` and `references/shared-conventions.md`; neither of
those existing statements is removed, because neither is a *capability-determination*
statement — one is a directive-consumption instruction and the other is a summary.

**Insertion point.** Immediately **after** the paragraph beginning
`**A consent requirement is \`interactive\`, not \`manual\`.**` and immediately **before**
the paragraph beginning `**Do not use \`host == claude\` as a capability proxy.**`. That
places it with the two clauses it extends (`b` → the consent case) and before the change of
subject to `--host`.

**The paragraph, verbatim:**

```markdown
**A dispatch bar routes an auto-verify directive through the gate; it never resolves it.**
When `runInStageVerify: true` arrives and you may not dispatch unsolicited, that directive
is **presented through the Standard Verify Gate** in its consent form — see "Consent
variant on a `none` gate" below — and the clean-room `forge-verifier` is **dispatched on
the affirmative choice**, never merely printed for the user to run later. Such a bar is
**never grounds to skip verification**, and it is never resolved by **advancing to the
production successor** while verification is unresolved.
```

**Constraint checks for this edit, each verified against the real gate:**

| Check | Result |
|---|---|
| `check-spec-purity.py::check_body_size` | Applies to `skills/*/SKILL.md` only (`_skill_md_files(root)` yields `skills/*/SKILL.md`). `references/**` has **no** size cap, so C-05 does not constrain this edit. |
| `check_no_residual_var` | Bans `${CLAUDE_PLUGIN_ROOT}` on canonical surfaces. The paragraph contains none. |
| Self-containment ratchet (`01-architecture-layout.md` §6.2) | The paragraph cites no document under `specs/`. |
| `test_stage_exit_protocol.py::test_the_reference_carries_the_sentinel_exactly_once` | The paragraph does not contain the NEXT-STEPS sentinel. |
| `test_stage_exit_protocol.py` stamp extraction (`_extract_block`) | The insertion is outside every `<!-- BEGIN/END -->` marker pair. |
| `test_stage_exit.py::test_every_protocol_stage_noun_slot_has_a_directive_to_fill_it` | The paragraph introduces no `{stageNoun}` slot and removes none. |

**Derived-content rule (REQ-TRIAL-06).** §4.4's `CLAUSE_PROBES` tuples are **derived from
this paragraph's wording**. If the wording is changed, `CLAUSE_PROBES` is recomputed **in
the same edit**. They are the only two places this feature states the same thing twice, and
they are pinned to each other here so a later round resolves against a position.

### 2.4 Why `shared-conventions.md` § "Verify Capability" stays a summary (REQ-GUARD-01)

It stays a summary, is **not edited**, and is **not asserted against by the guard**.

- It self-identifies as a partial excerpt — its own text reads "The full determination
  rule, the Standard Verify Gate, and the recovery path live in
  `references/stage-exit-protocol.md`; the two facts that are most often gotten wrong".
  Promoting it would make canon self-contradictory.
- It omits the Standard Verify Gate and the recovery path, so promotion would require
  duplicating prose that already lives in `stage-exit-protocol.md` — adding a surface while
  R-10 is collapsing surfaces.
- **The guard asserting clauses against two files is what "two sources of truth" looks like
  in code.** The deleted `test_the_shared_capability_rule_is_documented` (§6.1) asserted the
  full clause set against `shared-conventions.md`; keeping it would leave two files that
  must both be edited whenever the rule changes — precisely the maintenance cost
  REQ-GUARD-01 exists to remove.

**Declared boundary.** After this rewrite, nothing in `tests/` asserts that
`shared-conventions.md` § "Verify Capability" remains a summary. That property is verified
once, by human review, against the checklist item in `00-core-definitions.md` §12. It is
not a guard protection and its absence is not a finding — see §9.

### 2.5 Rejected alternatives (from `tech-spec.md` §3.1)

| Alternative | Why rejected |
|---|---|
| Make `references/shared-conventions.md` § "Verify Capability" canonical | It self-identifies as a partial excerpt and omits the Standard Verify Gate and the recovery path. Promoting it would require duplicating prose that already lives in `stage-exit-protocol.md`. This was the tentative v1 position while OQ-02 was open; v2 resolved OQ-02 the other way. |
| Author a **third**, distinct canonical section | Adds a surface while R-10 is collapsing surfaces. The existing section is already treated as canonical by every pointer and every restatement in the tree; a new section would have to win that status back. |

---

## 3. The `forge-0-epic` pointer (REQ-GUARD-03)

### 3.1 The gap

`skills/forge-0-epic/SKILL.md` is the only stage-closing skill that passes
`--verify-capability "{verify-capability}"` with **no guidance anywhere in the file** —
neither a capability lead-in nor the canonical section title. Verified: the six restating
surfaces (`forge-1-prd`, `forge-2-tech`, `forge-3-specs`, `forge-4-backlog`, `forge-verify`,
`forge-fix`) carry a lead-in; the two pointer surfaces (`forge-5-loop`, `forge-6-docs`)
carry the title; `forge-0-epic` carries neither. This matches `00-core-definitions.md` §4.1
row 1 and closes review finding D7.

The gap is closed **in canon**. `SURFACES_WITHOUT_PROSE` is not edited to accommodate it —
it is deleted (§6.3, `00-core-definitions.md` §4.2).

### 3.2 The sentence to add

Shape-matched **verbatim** to the two existing pointer surfaces. The sibling sentence, quoted
from `skills/forge-6-docs/SKILL.md` (the same sentence appears in
`skills/forge-5-loop/SKILL.md`):

> Add `--epic "{epic}"` when this feature is an epic member — required, per the Pipeline
> State Protocol in `references/shared-conventions.md`. **Determine `{verify-capability}`
> per the \*\*Host and capability determination\*\* section of
> `references/stage-exit-protocol.md`: `interactive` needs both a question mechanism and
> *permission* to dispatch the clean-room `forge-verifier`, and a session that merely needs
> consent first is still `interactive`.**

Only the bolded second sentence is portable: the `--epic` half does not apply to
`forge-0-epic`, where the epic *is* the subject rather than a back-pointer. The sentence to
add is therefore that second sentence, byte-for-byte:

```markdown
Determine `{verify-capability}` per the **Host and capability determination** section of `references/stage-exit-protocol.md`: `interactive` needs both a question mechanism and *permission* to dispatch the clean-room `forge-verifier`, and a session that merely needs consent first is still `interactive`.
```

It is added as its **own paragraph** (one content line plus one blank separator line), not
appended to an existing one, so `_capability_evidence` (§4.4) resolves it as a block on its
own.

### 3.3 The insertion point

`skills/forge-0-epic/SKILL.md`, `### Step C8 — Review, Pipeline State & Commit`,
**immediately before** the line beginning:

```markdown
**Close this stage with the Scripted Stage Exit** (contract: `references/stage-exit-protocol.md`; do not improvise a "Next steps" list). Run:
```

That line is preceded in Step C8 by the numbered item beginning
`3. **Closing message — the Stage Exit Protocol.**`, so the new paragraph lands between
item 3 and the `**Close this stage …**` line. This is the insertion point fixed by
`01-architecture-layout.md` §4.1.

**Positional note, recorded rather than papered over.** `tech-spec.md` §3.1 describes this
as "the same structural position every sibling uses". Verified against the files, that is
true of the **six restating** siblings — `forge-1-prd`'s capability paragraph sits
immediately before its `**Close this stage …**` line — but **not** of the two **pointer**
siblings, which place their sentence *after* the fenced call and the DIRECTIVES paragraph.
The edit therefore matches the restating siblings **positionally** and the pointer siblings
**textually**. This is not a defect in either: **the guard does not assert position**
(per-surface formatting equality is a declared non-goal, REQ-GUARD-06), and
`01-architecture-layout.md` §4.1 is the position of record.

**Body-size check (C-05), measured against the real rule.** `check_body_size` counts the
body after the closing frontmatter fence. `skills/forge-0-epic/SKILL.md` is at 295/300 body
lines and 2749/5000 body words (`01-architecture-layout.md` §3.1). The addition is **2 body
lines** (sentence + blank) and roughly 45 words → 297/300 and ~2794/5000. Both stay under
the cap, so `check-spec-purity.py` continues to report 0 violations (REQ-CANON-02).

### 3.4 Why a pointer and not a paragraph

Two reasons, in this order:

1. **Shape matching.** `forge-5-loop` and `forge-6-docs` already resolve this exact need
   with a pointer, and REQ-GUARD-02 accepts a pointer as a first-class satisfying form
   (`00-core-definitions.md` §3.3). Adding a *seventh* restatement would make the surface
   set less uniform, not more.
2. **R-10's collapse goal.** The workstream exists to reduce the number of places the rule
   is stated. Closing a gap by adding a restatement moves the count in the wrong direction:
   the rule would then live in seven surfaces plus canon instead of six plus canon.

> **Headroom is a constraint check, not the rationale.** §3.3's +5-line measurement
> establishes only that the edit *fits*. Even with unlimited headroom the decision would be
> the same, on the two grounds above. `tech-spec.md` §3.1 states this explicitly ("The
> pointer-not-paragraph decision does **not** rest on headroom"), and it is repeated here
> because the inverted reading — "a pointer because there was no room" — invites a later
> round to "upgrade" it to a paragraph once room appears, which would be a regression
> against reason 2.

---

## 4. The guard file rewrite (REQ-GUARD-04, REQ-GUARD-05, REQ-GUARD-06, REQ-GUARD-07)

### 4.1 Target shape

`tests/test_capability_determination_prose.py` becomes **4 test functions / 4 collected
items**, down from 13 functions / 43 items (`tech-spec.md` §3.3). That is **one under**
REQ-GUARD-04's cap of 5.

| # | Test | Protection | REQ |
|---|---|---|---|
| 1 | `test_the_canonical_rule_states_every_clause` | The canonical section states every required clause | REQ-GUARD-01 |
| 2 | `test_every_surface_has_a_paragraph_or_pointer` | Every canonical exit surface carries a paragraph or a pointer | REQ-GUARD-02, REQ-GUARD-03 |
| 3 | `test_the_guard_is_not_vacuous` | The roster cannot shrink to a vacuous size | REQ-GUARD-04 |
| 4 | `test_this_guard_is_not_skippable` | The guard cannot be skipped or disabled | REQ-GUARD-05 |

No test in the file is parametrized. Parametrizing test 2 over the 9-site roster would
produce 9 collected items for one protection and re-introduce the per-surface grid this
workstream removes; the roster is walked **inside** one test and reported as one list.

### 4.2 The `PROTECTS` / `NON-GOALS` module docstring (REQ-GUARD-05)

The file opens with the declaration format fixed by `00-core-definitions.md` §5.1,
reproduced here verbatim as the text to ship:

```python
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
```

**The declared set and the shipped test set must be identical** (`00-core-definitions.md`
§5.1). Concretely, the four numbered `PROTECTS` entries map one-to-one onto the four test
functions in §4.1, in that order:

| `PROTECTS` entry | Shipped test |
|---|---|
| 1 | `test_the_canonical_rule_states_every_clause` |
| 2 | `test_every_surface_has_a_paragraph_or_pointer` |
| 3 | `test_the_guard_is_not_vacuous` |
| 4 | `test_this_guard_is_not_skippable` |

A fifth test with no `PROTECTS` entry is an undeclared protection — precisely the shape that
invites next round's finding. A fifth `PROTECTS` entry with no test is a false claim of
coverage. Either is a defect against REQ-GUARD-05.

A module-level `PROTECTS` / `NON_GOALS` tuple pair is **rejected** (`00-core-definitions.md`
§5.1): it invites a meta-test asserting the declaration exists, which is the
meta-guard-on-a-meta-guard layering this feature removes. The docstring is deliberately
plain and greppable rather than machine-readable, because this file is the template other
guards will copy.

**REQ-CANON-03 applies to the docstring.** It states intent. It contains no count, no
"measured", no defect history, and no round numbers. The current file's docstring — which
narrates measurements across four verify rounds — is deleted with it (§6.4).

### 4.3 Imports and module constants

```python
"""<the module docstring from §4.2>"""

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
```

**Notes on the constants, each traced:**

- `CLAUSE_PROBES` keys are the six keys of `00-core-definitions.md` §3.2 (`a`, `b`, `c1a`,
  `c1b`, `c2`, `c3`). The **keys and meanings survive**; the per-surface exact-fragment
  tuples that encoded bold markers do not (§6.3).
- Probes are written in **normalised form** — lower-case, no backticks, no emphasis — so a
  probe cannot express a formatting requirement even by accident (REQ-GUARD-06).
- `MIN_ROSTER_SIZE = 9` replaces `MIN_CAPABILITY_SURFACES = 6`
  (`00-core-definitions.md` §4.3): the roster is now all nine sites with no exclusions, so 6
  would no longer be a meaningful floor.
- `CanonicalExitSite` is imported for the `_site_evidence` annotation. Under
  `from __future__ import annotations` this is a real reference, not a lint casualty.
  `01-architecture-layout.md` §5.3 requires it to keep its `skill` and `contract_paths`
  fields through `03-machinery-trim.md`'s trim.

### 4.4 Helpers

```python
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
```

**Why site-level, not file-level.** `CANONICAL_EXIT_SITES` has 9 entries but 10 contract
paths — `forge-5-loop` owns both `skills/forge-5-loop/SKILL.md` and
`skills/forge-5-loop/references/result-reporting.md`, and only the first carries the
pointer. The roster unit fixed by `00-core-definitions.md` §4.1 is the **site**, so a site
passes when **any** of its contract paths carries the evidence. A per-file rule would fail
`forge-5-loop` against `result-reporting.md`, which is a result-ladder reference with no
capability role.

**Known limitation of `_markdown_section`, recorded.** It is not fence-aware: a
`## `-prefixed line inside a fenced block would be read as a heading. Verified against
`references/stage-exit-protocol.md` as it stands — every fence in that file is balanced and
no `## ` line occurs inside one — so the extraction is correct today. Fence-aware heading
detection is **mandatory** only for the structural region scan in `03-machinery-trim.md`
(`00-core-definitions.md` §6.3), where bash comments inside fences do collide with the naive
rule. It is deliberately not added here: this helper reads one section of one file, and the
extra machinery would be untested weight.

### 4.5 Protection 1 — `test_the_canonical_rule_states_every_clause` (REQ-GUARD-01)

```python
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
```

**Error handling.**

| Failure | Behavior |
|---|---|
| `references/stage-exit-protocol.md` missing | `read` raises `AssertionError` naming the absolute path (`tests/_forge_paths.py`). |
| The `##` heading is gone or renamed | `_markdown_section` returns `""`; the first assertion fires and names the expected heading. It cannot fall through to a vacuous clause loop over an empty string, because an empty string matches no probe — but the dedicated message is what makes the *cause* legible (REQ-OBS-01). |
| A clause is dropped or inverted | The loop fires on that clause, naming the clause key, its obligation in prose, and every accepted phrasing. |
| File unreadable / bad encoding | `Path.read_text(encoding="utf-8")` raises `UnicodeDecodeError` or `OSError`, which pytest reports as an error rather than a failure. Not caught: a canon file that cannot be decoded is not a condition this guard should paper over. |

**Against the file today, this test FAILS on `c1a`, `c1b`, `c2` and `c3`** and passes once
§2.3's paragraph lands. That is intentional and is the visible link between the canon work
and the guard work: the completion is not optional, and skipping it turns this test red.

### 4.6 Protection 2 — `test_every_surface_has_a_paragraph_or_pointer` (REQ-GUARD-02, REQ-GUARD-03)

```python
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
```

**Error handling.**

| Failure | Behavior |
|---|---|
| A surface carries neither form | The assertion fires listing **every** offending skill id — not just the first — so one run resolves the whole set. |
| A declared contract path is missing from disk | `read` raises `AssertionError` naming the path, via `_site_evidence`'s documented `Raises:`. |
| `CANONICAL_EXIT_SITES` fails to import | Collection error, not a silent pass. This is the breakage `01-architecture-layout.md` §5.3 calls the most likely in the feature; `07-testing-strategy.md` §4 makes the import an explicit gate. |
| A site has an empty `contract_paths` tuple | `_site_evidence` returns `None` and the site is reported as silent — an unreachable site cannot pass by having nothing to check. |

**Diagnostic scope (REQ-OBS-01).** The message names the skill ids and the title string a
pointer must contain, which is enough to act on without reading the test source. It
deliberately does **not** report which form each passing surface used: that is a declared
non-goal (§4.2, `NON-GOALS` bullet 2).

**Example — what a real regression looks like.** Deleting the §3.2 pointer sentence from
`skills/forge-0-epic/SKILL.md` produces:

```
AssertionError: these canonical exit surfaces neither state the capability rule nor
name 'Host and capability determination', so the stage closes on an undetermined
--verify-capability: ['forge-0-epic']
```

### 4.7 Protection 3 — `test_the_guard_is_not_vacuous` (REQ-GUARD-04)

```python
def test_the_guard_is_not_vacuous() -> None:
    """A shrunken roster would pass the surface check without examining anything."""
    assert len(CANONICAL_EXIT_SITES) >= MIN_ROSTER_SIZE, (
        f"the canonical exit table carries {len(CANONICAL_EXIT_SITES)} sites, below "
        f"the floor of {MIN_ROSTER_SIZE} — the surface check above has stopped "
        "covering the pipeline rather than the prose having been removed from canon"
    )
```

The floor is 9 because the roster is now **all** canonical exit sites with **no
exclusions** (`00-core-definitions.md` §4.1, §4.3). Under the old design the roster was a
*filtered* subset, and the floor guarded against the filter silently ceasing to match; under
this design there is no filter, so the floor guards against the imported table itself
shrinking — which is exactly the failure `03-machinery-trim.md`'s 67 → 7 collapse could
cause if it touched the table (`01-architecture-layout.md` §5.3 forbids it, and this is the
independent check).

**Error handling.** The only failure mode is a short roster; the message reports the
observed length against the floor. An import failure is a collection error (§4.6).

### 4.8 Protection 4 — `test_this_guard_is_not_skippable` (REQ-GUARD-05)

Retained **verbatim** from the current file — no behavior change, only its position in the
declared set:

```python
def test_this_guard_is_not_skippable() -> None:
    """No skip gate may be introduced here — an unskippable guard is the whole point."""
    source = read(Path(__file__).resolve())
    for banned in ("skipif", "importorskip", "pytest.skip"):
        # Only prose may mention them; no call may be made.
        assert f"{banned}(" not in source, f"{banned} gate introduced in the drift guard"
```

**Why reading its own source is legitimate here, when the AST self-inspection layer is
being deleted (REQ-GUARD-07).** This test asserts **absence** of a token. An absence
assertion cannot be satisfied by its own source line, because the needle is assembled at
runtime (`f"{banned}("`) and never appears literally in the file. The deleted
`test_the_controls_cover_every_determining_surface` asserted **presence and structure** of
its own module's bindings, which is what required an `ast` layer, and what four consecutive
rounds of hardening failed to close. Absence-only self-inspection is the boundary; §6.2
records it.

**Error handling.** A `skipif(`, `importorskip(` or `pytest.skip(` call anywhere in the file
fires the assertion naming the token. There is no other failure mode; `read` raises if the
file is somehow unreadable.

### 4.9 Why 4 and not 5 (REQ-GUARD-04)

**REQ-GUARD-04's "at most 5" is a ceiling, not a quota.** Shipping a fifth test to reach the
cap would add an undeclared or a make-work protection, and this file is the template other
guards copy.

The self-check is a **fourth declared protection**, not a fifth thing beyond the three
REQ-GUARD-04 enumerates: it protects the guard's *existence* rather than the rule, and the
cap of 5 accommodates it. Declaring it is what keeps the shipped test set and the `PROTECTS`
block identical (§4.2).

| Candidate | Disposition | Reason |
|---|---|---|
| `test_the_roster_is_derived_not_listed` | **Dropped** | The hand-listing risk it guarded *was* `SURFACES_WITHOUT_PROSE`, which §6.3 deletes; with no exclusion constant there is no second hand-kept copy to drift from. It is also the test most entangled with the `ast` layer REQ-GUARD-07 removes — its non-vacuous form required exactly the module-scope binding traversal being deleted. Keeping it would mean keeping `_module_scope_writes` and the two helpers under it, contradicting REQ-GUARD-07. |
| `test_this_guard_is_not_skippable` | **Kept** | Every sibling guard in this repo carries it, and its absence would let a `skipif` silently disable the whole file — a guard that can be turned off is not a guard. It costs one collected item and one absence assertion, with no self-inspection machinery. |

### 4.10 Assembly order

The shipped file, top to bottom: module docstring (§4.2) → imports and constants (§4.3) →
helpers `_normalised`, `_markdown_section`, `_capability_evidence`, `_site_evidence` (§4.4)
→ the four tests in `PROTECTS` order (§4.5 – §4.8). No section-banner comment blocks: with
four tests and one protection each, the banner would be longer than what it separates.

---

## 5. How "paragraph or pointer" is detected (REQ-GUARD-02)

### 5.1 The two satisfying forms

Per `00-core-definitions.md` §3.3, a surface satisfies REQ-GUARD-02 by carrying **either**:

| Form | Detected by | Implementation |
|---|---|---|
| **paragraph** | The surface announces that it determines capability itself — a **capability lead-in** in one of its blocks | `CAPABILITY_LEAD_INS` matched against `_normalised(block)` |
| **pointer** | The block names the canonical section **by section title** — the literal string `Host and capability determination` | `_normalised(CANONICAL_SECTION_TITLE) in normalised` |

**A pointer is recognised by section title, never by a URL or a path.** Matching on
`references/stage-exit-protocol.md` would let a pointer survive a section rename or a
section deletion — the path would still resolve while the rule it names had moved. Matching
on the title fails in exactly that case, which is when a maintainer needs to know
(`00-core-definitions.md` §3.3, `tech-spec.md` §3.2). Protection 1 independently pins that a
section with that title exists and states the rule, so the two assertions close the loop:
the title a pointer names is the title the canonical section carries.

### 5.2 Where clause content is checked, and where it is not

This is the actual collapse, and it is worth stating as a table because it is the difference
between the old file and the new one:

| Check | Old file | New file |
|---|---|---|
| Clause content | 6 clauses × 6 surfaces, per-surface exact fragments, plus a 7th target (`shared-conventions.md`) | 6 clauses × **1** canonical section (§4.5) |
| Per-surface | Full clause set, with per-surface accepted-phrasing lists | **Presence only** — a lead-in or the title (§4.6) |
| Negative controls | 6 parametrized mutation tests × 6 surfaces = 36 items | none |

**Per-surface assertions never read clause content.** That is what makes REQ-GUARD-06
enforceable rather than aspirational: there is no per-surface fragment list to reword a
clause against, so a canon rewording of any surface cannot turn the guard red. The rule's
content has one home and one assertion.

### 5.3 What REQ-GUARD-06 bans, and what protection 1 does instead

REQ-GUARD-06 is load-bearing and is the specific mechanism that produced the churn
(`00-core-definitions.md` §5.2). The line is:

| Banned — never assert | Why | Where it lived |
|---|---|---|
| Per-surface clause-fragment matching | A 6 × 6 grid means any canon rewording on any surface reds the suite | `CLAUSES` × `_capability_surfaces()` |
| Bold-marker presence | Emphasis carries no obligation | fragments like `` "**no** question mechanism **and** **no** permitted dispatch" `` |
| Per-surface formatting equality | Surfaces legitimately differ in wording, position and emphasis | the accepted-phrasing lists per clause |

| Permitted — what protection 1 does | Why it is not the banned thing |
|---|---|
| One meaning-bearing probe set, matched against **one** section | There is no grid: N surfaces × M clauses becomes 1 × M. A surface rewording cannot red it. |
| Matched against `_normalised()` text | Emphasis and backticks are **removed before matching**, so bold-marker presence is unassertable by construction — a probe containing `**` could never match anything. |
| Any-of within a clause | The clause's *meaning* is the contract; its sentence may be rewritten as long as it still says the thing. |

> **Reintroducing clause-fragment or bold-marker matching is a regression, not a
> hardening**, and must be treated as one by any later round
> (`00-core-definitions.md` §5.2). Concretely: adding a second target file to §4.5's loop,
> adding `**` to a probe, or parametrizing §4.6 over surfaces with clause content all
> rebuild the problem.

### 5.4 Declared boundaries of the detection (recorded, not hidden)

Recorded here so a later round resolves them against a position rather than re-deriving
them (C-04):

1. **Presence, not correctness, per surface.** A surface carrying a capability lead-in
   passes protection 2 even if its paragraph has rotted. That is deliberate: correctness of
   the rule is protection 1's job, against canon. The alternative is the 6 × 6 grid.
2. **A title mention anywhere in a block counts as a pointer.** A file that mentioned
   `Host and capability determination` in an unrelated block would pass. Accepted: the
   alternative is pinning the pointer's *sentence*, which is per-surface formatting equality
   (REQ-GUARD-06).
3. **Clause `b`'s two halves are matched any-of, not both.** A section stating the positive
   rule but not the reserve rule satisfies clause `b`. `00-core-definitions.md` §3.2 models
   it as one clause; requiring the conjunction is the shape the deleted negative controls
   existed to police, and it is not in the protection set.
4. **Position within a surface is never asserted** (§3.3).
5. **`shared-conventions.md` is not asserted against at all** (§2.4).

---

## 6. The complete deletion list

Everything below is removed from `tests/test_capability_determination_prose.py`. The file is
a rewrite, not a patch; this list exists so a reviewer can confirm nothing survived by
accident.

### 6.1 Test functions deleted — 11 functions / 41 collected items

| Function | Items | Deleted because |
|---|---|---|
| `test_every_capability_determining_surface_states_all_the_clauses` | 1 | Superseded by §4.5 — clause content is asserted once, against canon (REQ-GUARD-01) |
| `test_the_shared_capability_rule_is_documented` | 1 | Asserted the full clause set against `references/shared-conventions.md`, i.e. a **second source of truth** (REQ-GUARD-01, §2.4) |
| `test_the_delegating_surfaces_still_point_somewhere_real` | 1 | Absorbed into §4.6 — the pointer form is now a first-class satisfying form for **every** surface, not a special case for two (REQ-GUARD-02) |
| `test_the_roster_is_derived_not_listed` | 1 | §4.9 — the hand-listing risk it guarded was `SURFACES_WITHOUT_PROSE`, deleted in §6.3 |
| `test_rewriting_clause_a_to_tool_presence_wording_fails_the_guard` | 6 | Negative control over exact fragments — REQ-GUARD-06 |
| `test_downgrading_the_consent_case_to_manual_fails_the_guard` | 6 | Negative control over exact fragments — REQ-GUARD-06 |
| `test_deleting_the_auto_path_through_the_gate_fails_the_guard` | 6 | Negative control over exact fragments — REQ-GUARD-06 |
| `test_downgrading_the_affirmative_choice_to_a_printed_command_fails_the_guard` | 6 | Negative control over exact fragments — REQ-GUARD-06 |
| `test_deleting_the_no_skip_obligation_fails_the_guard` | 6 | Negative control over exact fragments — REQ-GUARD-06 |
| `test_deleting_the_no_advance_obligation_fails_the_guard` | 6 | Negative control over exact fragments — REQ-GUARD-06 |
| `test_the_controls_cover_every_determining_surface` | 1 | The AST self-inspection test — REQ-GUARD-07 |
| **total deleted** | **41** | |

Arithmetic: 43 collected items − 41 deleted = 2 retained (`test_the_guard_is_not_vacuous`,
reimplemented under its own name, and `test_this_guard_is_not_skippable`, verbatim) + 2 new
= **4**, matching `tech-spec.md` §8.2's `test_capability_determination_prose.py` row (43 →
4, −39 net).

### 6.2 The AST self-inspection layer (REQ-GUARD-07)

Deleted in full — the test and all three helpers:

| Symbol | Kind |
|---|---|
| `test_the_controls_cover_every_determining_surface` | test |
| `_module_scope_nodes` | helper |
| `_store_target_names` | helper |
| `_module_scope_writes` | helper |

With them go the ~70 lines of in-test commentary enumerating binding forms, decoy shapes,
and per-round defect history — narration that REQ-CANON-03 forbids and that this layer
existed to justify.

The `import ast` statement is removed (`00-core-definitions.md` §11). `ast` **remains** in
`tests/test_stage_exit_protocol.py` and `tests/test_stage_constants_parity.py`, where it is
used for `ast.literal_eval` constant extraction rather than self-inspection, and is out of
scope for this feature.

**The boundary that survives:** a test in this file may assert **absence** in its own source
(§4.8). It may not assert presence or structure of its own module's bindings — that is the
layer being deleted, and the space of ways to rebind a Python name is not enumerable by
adding node types.

### 6.3 Constants deleted

| Constant | Deleted because |
|---|---|
| `SURFACES_WITHOUT_PROSE` | **Deleted outright, not shrunk** (REQ-GUARD-03, `00-core-definitions.md` §4.2). Under paragraph-**or**-pointer two of its three entries already pass, and §3's canon edit empties the third. An empty exclusion constant is still a place to encode a future gap. **No exemption constant may be reintroduced anywhere in this feature.** |
| `MIN_CAPABILITY_SURFACES` | Replaced by `MIN_ROSTER_SIZE = 9` (`00-core-definitions.md` §4.3) — the roster is now all nine sites with no exclusions, so a floor of 6 is not meaningful |
| `CLAUSES` | The clause-fragment tuples that encode bold markers — REQ-GUARD-06. Its six **keys and meanings** survive as `CLAUSE_PROBES` (§4.3); its per-surface accepted-phrasing lists do not |
| `ALL_SURFACES` | Module-level roster materialised only to parametrize the deleted negative controls |
| `SURFACE_IDS` | Parametrize ids for the deleted negative controls |
| `CONVENTIONS` | Pointed at `references/shared-conventions.md`, which the guard no longer asserts against (§2.4) |

### 6.4 Helpers, imports and narration

| Symbol | Disposition |
|---|---|
| `_capability_paragraph` | Deleted — replaced by `_capability_evidence`, which resolves a pointer as well as a paragraph |
| `_assert_capability_prose` | Deleted — per-surface clause assertion (REQ-GUARD-06) |
| `_assert_clauses_in` | Deleted — folded into §4.5's single-target loop |
| `_capability_surfaces` | Deleted — the lead-in **filter** is gone; the roster is the whole table |
| `_markdown_section` | **Retained**, behavior unchanged, docstring rewritten to state intent only (REQ-CANON-03) |
| `import ast` | Removed (§6.2, `00-core-definitions.md` §11) |
| `from collections.abc import Iterator` | Removed — its only use was annotating the deleted AST helpers |
| `import pytest` | **Removed** — with no `parametrize` and no `pytest.raises` in the four-test shape, nothing in the file uses it. Leaving it is an unused-import lint error and counts against REQ-QUAL-02's ≤19 budget (`07-testing-strategy.md`) |
| The 70-line module docstring | Replaced wholesale by §4.2's declaration. Its measurement narration ("measured twice", "left the guard green on five of the six surfaces", round numbers) is exactly what REQ-CANON-03 forbids |

**Retained imports:** `from __future__ import annotations`, `from pathlib import Path`,
`from typing import Final`, `from _forge_paths import REFERENCES, REPO_ROOT, read`,
`from test_stage_exit_protocol import CANONICAL_EXIT_SITES` (now also `CanonicalExitSite`).
All three `_forge_paths` names remain in use: `REFERENCES` builds `PROTOCOL`, `REPO_ROOT`
resolves contract paths, `read` performs every file read.

---

## 7. Error handling summary

### 7.1 Canon edits

Neither canon edit can fail at runtime — they are text. They can fail a **gate**, and the
mapping is:

| Failure | Gate that catches it | Recovery |
|---|---|---|
| Adapters not regenerated after either edit | `build-adapters.py --check` (non-zero) inside `scripts/validate.sh` | Run `python3 scripts/build-adapters.py`, commit all six mirrors in the same commit (§8) |
| `forge-0-epic` body pushed over 300 lines | `check-spec-purity.py::check_body_size` → `VR_BODY_LINES` | Should not occur: §3.3 measures +2 lines against +5 headroom. If it does, the pointer is the wrong shape for that file and the decision in §3.4 must be revisited, not the cap worked around |
| Canon prose citing a document under `specs/` | `check-spec-purity.py` self-containment ratchet | Neither added text cites `specs/` (§2.3, §3.2) |
| Adapter modes land 0664 after a `git` operation | adapter mode test | Re-run `build-adapters.py`; content is unaffected (C-02). **Do not investigate as a content defect** |

### 7.2 Guard runtime failures

Enumerated per test in §4.5 – §4.8. The shared contract:

- **Missing canon file** → `AssertionError` from `_forge_paths.read`, naming the absolute
  path. Never a skip: a silently skipped file reads as coverage while asserting nothing.
- **Undecodable canon file** → `UnicodeDecodeError`/`OSError` propagates as a pytest error.
  Not caught — this guard has no defensible degraded mode.
- **`CANONICAL_EXIT_SITES` import failure** → collection error for the whole module. This is
  the breakage `01-architecture-layout.md` §5.3 names as the most likely in the feature.
- **Every assertion message names the artifact and the obligation** (REQ-OBS-01,
  `00-core-definitions.md` §8.3): the clause key and its obligation for protection 1, the
  offending skill ids and the required title for protection 2, the observed length and the
  floor for protection 3, the banned token for protection 4.

### 7.3 Narration constraint (REQ-CANON-03)

Every docstring and comment specified in §4 states **intent only**. No count, no "measured",
no "confirmed", no round number, no defect history appears in any of them. The counts in
this document (43 → 4, 41 deleted, 9 sites, 6 clauses) are **spec content** and must not be
copied into the file (`00-core-definitions.md` §10.1).

The one numeric literal in the shipped code is `MIN_ROSTER_SIZE = 9`, which is a *value*
required by `00-core-definitions.md` §4.3, not a narrated measurement — and its comment says
what the floor is for, not what was counted.

---

## 8. Adapter regeneration obligation (REQ-CANON-01)

Both canon edits in this document require regeneration of the six adapter mirrors in the
**same commit** (`01-architecture-layout.md` §6.1, C-01):

```bash
python3 scripts/build-adapters.py
python3 scripts/build-adapters.py --check   # must exit 0
```

Propagation for these two specific edits:

| Edit | Propagation | Host-term translation |
|---|---|---|
| `references/stage-exit-protocol.md` (§2.3) | `references/**` is copied **verbatim** into each bundle | None — the paragraph contains no host term (`/clear`, `--host claude`, `/feature-forge:`) |
| `skills/forge-0-epic/SKILL.md` (§3.2) | Through the per-skill emitters | None applies — the sentence contains no host term either, so the six mirrors receive it identically |

The six mirrors: `adapters/claude`, `adapters/codex`, `adapters/copilot`, `adapters/cursor`,
`adapters/gemini`, `adapters/pi`. **Never hand-edited.**

**Ordering.** Per `01-architecture-layout.md` §5.2, canon lands **first** (step 1), adapters
are regenerated with it, and the guard rewrite is step 3. Landing the guard before the canon
completion leaves protection 1 red on `c1a`, `c1b`, `c2` and `c3` (§4.5) and protection 2
red on `forge-0-epic` (§4.6) — a correct but noisy intermediate state that the stated order
avoids.

---

## 9. Declared non-goals of this document

Recorded so a verifier resolves them against a position rather than filing them (C-04,
`00-core-definitions.md` §10.3):

- **Exact-markdown fidelity** on any capability surface — clause-fragment matching,
  bold-marker presence, per-surface formatting equality (REQ-GUARD-06, §5.3). Its absence is
  **not** a guard-incompleteness finding; its **presence** is a regression.
- **Which of paragraph-or-pointer** any surface chooses (§4.2 `NON-GOALS`, §5.4).
- **The wording of any surface's restatement**, and **the position** of the pointer within a
  surface (§3.3, §5.4).
- **Guarding that `shared-conventions.md` stays a summary** (§2.4). Verified by review
  against `00-core-definitions.md` §12, not by a test.
- **Fence-aware heading detection** in `_markdown_section` (§4.4). Mandatory only for
  `03-machinery-trim.md`'s region scan.
- **Conjunction of clause `b`'s two halves** (§5.4 item 3).

---

## 10. Dependencies

**Spec documents that must be read first:**

| Document | For |
|---|---|
| `00-core-definitions.md` | §3 the clause set and the paragraph-or-pointer definition; §4 the surface roster and the deletion of `SURFACES_WITHOUT_PROSE`; §5 the meta-guard declaration format; §10.4 the cross-test-module import; §11 the removed imports |
| `01-architecture-layout.md` | §3.1 file ownership; §4.1 the canon insertion point; §5.2 implementation order; §5.3 the export constraint; §6 adapter and purity obligations |

**Spec documents this one is coupled to:**

| Document | Coupling |
|---|---|
| `03-machinery-trim.md` | Owns `tests/test_stage_exit_protocol.py`, which **exports** `CANONICAL_EXIT_SITES` and `CanonicalExitSite`. Both must keep their names, module scope and fields, and the tuple must keep **9** entries (`01-architecture-layout.md` §5.3). Also owns the fence-aware region model this document defers to (§4.4) |
| `07-testing-strategy.md` | Owns the gate list, the expected collected-item counts (43 → 4), and the explicit gate that `from test_stage_exit_protocol import CANONICAL_EXIT_SITES` still resolves after both files are edited |

**Implementation order within this document:** §2 canon completion → §3 pointer → regenerate
adapters (§8) → §4/§6 guard rewrite. The guard asserts the canon the first two steps produce.

**External packages:** none added, none removed. Stdlib plus `pytest` as the runner; after
§6.4, this file does not `import pytest` at all. `jsonschema` is absent in CI, so a bare
`python3 -m pytest tests` must run this file (`00-core-definitions.md` §1).

---

## 11. Verification

**Canon (REQ-GUARD-01, REQ-GUARD-03):**

- [ ] `references/stage-exit-protocol.md` § "Host and capability determination" states all
      six clauses of `00-core-definitions.md` §3.2 — verified by
      `test_the_canonical_rule_states_every_clause` passing.
- [ ] §2.3's paragraph sits between the `**A consent requirement is \`interactive\`, not
      \`manual\`.**` paragraph and the `**Do not use \`host == claude\` as a capability
      proxy.**` paragraph.
- [ ] `references/shared-conventions.md` is **absent from the diff** and still
      self-identifies as a summary deferring to `stage-exit-protocol.md`.
- [ ] `skills/forge-0-epic/SKILL.md` carries the §3.2 sentence as its own paragraph,
      immediately before the `**Close this stage with the Scripted Stage Exit**` line in
      Step C8.
- [ ] The sentence is byte-identical to the second sentence of `forge-6-docs`'s pointer
      paragraph.
- [ ] `python3 scripts/check-spec-purity.py` reports **0 violations**; `forge-0-epic`'s body
      is ≤300 lines and ≤5000 words.

**Guard shape (REQ-GUARD-04, REQ-GUARD-05):**

- [ ] `python3 -m pytest tests/test_capability_determination_prose.py -q` collects **exactly
      4 items** and all pass.
- [ ] The file defines exactly the four functions named in §4.1 — no more, no fewer.
- [ ] The module docstring reproduces §4.2 verbatim; its four `PROTECTS` entries map
      one-to-one onto the four shipped tests, in order.
- [ ] No `@pytest.mark.parametrize` appears in the file.

**Deletions (REQ-GUARD-06, REQ-GUARD-07):**

- [ ] `grep -c "def test_" tests/test_capability_determination_prose.py` returns **4**.
- [ ] None of the eleven functions in §6.1 appears anywhere in the file.
- [ ] `ast`, `Iterator` and `pytest` are **not imported**; `_module_scope_nodes`,
      `_store_target_names` and `_module_scope_writes` do not exist.
- [ ] `SURFACES_WITHOUT_PROSE`, `MIN_CAPABILITY_SURFACES`, `CLAUSES`, `ALL_SURFACES`,
      `SURFACE_IDS` and `CONVENTIONS` do not exist, and **no exemption constant replaces
      them** anywhere in this feature.
- [ ] No probe or fragment in the file contains `**`, and no assertion in the file compares
      formatting between two surfaces.
- [ ] `grep -n "measured\|confirmed\|round-" tests/test_capability_determination_prose.py`
      returns nothing (REQ-CANON-03).

**Integration:**

- [ ] `from test_stage_exit_protocol import CANONICAL_EXIT_SITES, CanonicalExitSite`
      resolves after both this document's and `03-machinery-trim.md`'s edits, and the tuple
      still yields **9** entries.
- [ ] `python3 scripts/build-adapters.py --check` exits **0**, with all six mirrors in the
      same commit as the two canon edits (REQ-CANON-01).
- [ ] `python3 -m pytest tests -q` stays green; `ruff check tests/` is **≤19 errors**
      (REQ-QUAL-02) — confirm the three removed imports did not leave a new unused name.

**Negative check — the regression this document exists to prevent:**

- [ ] Reword any single capability paragraph in any one skill (e.g. change `forge-1-prd`'s
      "may I dispatch `forge-verifier` right now" to an equivalent sentence). The suite
      stays **green**. If it goes red, per-surface clause matching has been reintroduced and
      REQ-GUARD-06 is violated.
