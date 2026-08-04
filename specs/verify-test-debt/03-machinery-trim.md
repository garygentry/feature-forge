# 03 — Machinery Trim

> The **test deletion and restructure** workstream (`00-core-definitions.md` §2). Three
> test files change; no production file, no canon file, and no adapter is touched by this
> document. Nothing here changes shipped behavior.
>
> This document implements the structural region model defined in
> `00-core-definitions.md` §6 — it does not redefine it. Where a bound, a variant table, or
> a declared boundary is stated there, this document cites it and specifies the code.
>
> Locate every symbol by **name**, never by line number (C-07). Line numbers below are
> as-of-authoring reading aids only.

## Requirement Coverage

| REQ ID | Requirement | Section |
|---|---|---|
| REQ-TRIM-01 | ~1 mutation control per mutation class (67 → 7) | §2 |
| REQ-TRIM-02 | Every positive stamp-verbatim test preserved | §3 |
| REQ-TRIM-03 | Guard 1 becomes a structural block scan; the window is removed | §4 |
| REQ-TRIM-04 | Window-tuning tests deleted with the machinery they constrain | §5.1, §5.2, §6 |
| REQ-TRIM-05 | The `inspect.getsource` meta-test deleted | §5.2, §5.3 |
| REQ-TRIM-06 | `test_the_epic_mandate_itself_is_still_documented` preserved | §7 |
| REQ-TRIM-07 | Source-text assertions duplicating a runtime check removed | §8 |

Governing cross-requirements this document must not violate (covered elsewhere, enforced
here): **REQ-CANON-03** (`00` §10.1) — every comment and docstring specified below states
intent only, with no count and no empirical claim; the counts live in this document's
prose. **`00` §4.2 / §10.4** — no exemption constant may be introduced, and
`CANONICAL_EXIT_SITES` keeps its name, module scope, and 9-entry tuple.

## 1. Scope and Ownership

Three files, all owned solely by this document (`01-architecture-layout.md` §3.3):

| File | Change | Requirements |
|---|---|---|
| `tests/test_stage_exit_protocol.py` | TRIM — 67 mutation items → 7 | REQ-TRIM-01, REQ-TRIM-02 |
| `tests/test_state_verb_call_sites.py` | RESTRUCTURE — window → structural scan | REQ-TRIM-03..06 |
| `tests/test_stage_constants_parity.py` | TRIM — two source-text assertions | REQ-TRIM-07 |

No other file may appear in this workstream's diff. In particular
`references/shared-conventions.md` is **read, never written**: §4's scan runs against it and
§6's mutation control mutates an **in-memory copy** of it.

Stdlib + `pytest` only (`00` §1). `tests/` may not import a third-party package —
`jsonschema` is absent in CI, so `python3 -m pytest tests` must run everything here.

## 2. Mutation-Control Trim (REQ-TRIM-01)

### 2.1 The classes, and the collected items each collapses to

All **7** mutation classes are kept. Each keeps **one collected item**, mutating a single
fixed representative exit site rather than all nine (tech spec §3.4):

| Mutation class | Test function | Items now | After |
|---|---|---|---|
| remove the scripted invocation | `test_removing_the_scripted_invocation_fails_the_guard` | 9 | **1** |
| duplicate terminal print instruction | `test_a_duplicate_terminal_print_instruction_fails_the_guard` | 9 | **1** |
| duplicate scripted invocation | `test_a_duplicate_scripted_invocation_fails_the_guard` | 9 | **1** |
| restore a retired bespoke block | `test_restoring_a_bespoke_terminal_block_fails_the_guard` | 18 | **1** |
| hand-typed sentinel | `test_a_hand_typed_sentinel_fails_the_guard` | 9 | **1** |
| drop a branch ownership token | `test_dropping_a_branch_ownership_token_fails_the_guard` | 4 | **1** |
| drop the nested no-terminal-block rule | `test_dropping_the_nested_no_terminal_block_rule_fails_the_guard` | 9 | **1** |
| **total** | | **67** | **7** |

The two 2-dimensional classes account for their second dimension as follows: the
retired-block class is `9 sites × 2 markers`; the ownership-token class is
`2 branch sites × 2 tokens`.

**Rationale (tech spec §3.4).** The per-site contract is identical *by construction* — one
`_assert_exit_contract` body is applied to every site — and
`test_each_covered_skill_satisfies_the_scripted_exit_contract` already proves that across
all 9 sites, at full parametrization (§3). Running each *mutation* against all 9 re-proves
site-uniformity seven more times rather than testing seven different things. What a
mutation control actually protects is that `_assert_exit_contract` **still fails** when its
subject is removed; that property is a property of the assertion, not of the site.

**Why a FIXED representative and not a rotating one.** A rotating or randomised site makes
a failure depend on which site was drawn, so the same regression reports differently on
different runs. A fixed site means the same class always fails on the same surface, and the
failure is explainable from the test name alone.

### 2.2 The fixed representative

```python
#: The single surface every mutation control mutates. A branch site, because the
#: ownership-token control only applies to a branch closure; one site for all classes,
#: so a failure always names the same surface.
_MUTATION_SITE: Final[CanonicalExitSite] = _site("forge-verify")
```

`forge-verify` is chosen because:

1. The ownership-token class (`_OWNER_TOKENS`) applies **only** to `_BRANCH_SITES`, whose
   members are `forge-verify` and `forge-fix` (derived, never listed — see
   `test_the_branch_sites_are_derived_not_listed`). Using one representative for all seven
   classes therefore requires a branch site.
2. Between the two branch sites, `forge-verify` carries exactly one occurrence of
   `_NESTED_NO_BLOCK_MARKER` and one of `_TERMINAL_PRINT_MARKER`, so each mutation is
   single-valued. (`forge-fix` carries the nested marker twice; the control would still
   detect it, but the mutation would no longer be minimal.)

**`_site` must move.** `_site(skill)` is currently defined below the negative-guard
section, in the *Loop and docs migration equivalence* block. It is a pure lookup over
`CANONICAL_EXIT_SITES` and must be **relocated up**, next to `_read_contract_surface`, so
`_MUTATION_SITE` can be bound at module scope. Its body is unchanged:

```python
def _site(skill: str) -> CanonicalExitSite:
    for site in CANONICAL_EXIT_SITES:
        if site.skill == skill:
            return site
    raise AssertionError(f"{skill!r} is not a covered exit site")
```

Binding through `_site` (rather than `next(...)` over a generator) means a representative
that stopped being a covered site fails at import with a named, readable `AssertionError`
instead of a bare `StopIteration`.

### 2.3 The seven surviving controls — complete replacement text

Every `@pytest.mark.parametrize` decorator on a mutation control is removed, together with
its `site` / `marker` / `token` parameter. The helper `_surface_is_unmutated` is unchanged
and still called by each control, so the "no repository file is mutated" property holds.

Function **names are unchanged** — the trim removes parametrization, not identity, so the
suite's failure vocabulary and the record of what each class protects survive the edit.

```python
@pytest.mark.parametrize("site", CANONICAL_EXIT_SITES, ids=_SITE_IDS)   # DELETED
def test_removing_the_scripted_invocation_fails_the_guard():
    """Deleting a covered skill's scripted exit call is caught."""
    site = _MUTATION_SITE
    surface = _read_contract_surface(site)
    broken = surface.replace(_SCRIPTED_INVOCATION, "echo 'closed the stage'", 1)
    assert broken != surface
    with pytest.raises(AssertionError):
        _assert_exit_contract(site, broken)
    _surface_is_unmutated(site, surface)
```

> The `# DELETED` line above marks the decorator to remove; it is not part of the shipped
> file. Every control below follows the same shape and the same deletion.

```python
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
```

**Why the two multi-valued classes keep an in-test loop.** `_RETIRED_BLOCK_MARKERS` and
`_OWNER_TOKENS` are module constants whose **membership** is part of the contract —
`_assert_exit_contract` iterates both. A loop inside the control keeps every member
exercised while still collecting as **one item**, so REQ-TRIM-01's budget is met without
narrowing what the class covers. Parametrizing over the members instead would spend a
second collected item to buy the same coverage.

**The ordering facts these controls depend on** (properties of `_assert_exit_contract`, not
of any site, and the reason each `match=` is what it is):

| Control | Which assertion trips | Why |
|---|---|---|
| remove the scripted invocation | the verbatim-stamp assertion | the invocation is inside the stamp, so the stamp check precedes the count check — the control therefore uses a bare `pytest.raises` with no `match=` |
| duplicate scripted invocation | the invocation-count assertion | the appended fence leaves the stamp intact |
| duplicate terminal print | the print-count assertion | the appended sentence leaves the stamp intact |
| retired bespoke block | the retired-marker loop | appended prose, stamp intact |
| hand-typed sentinel | the sentinel-absence assertion | appended text, stamp intact |
| ownership token | the branch-token loop | the tokens live in the branch skill's own prose, **not** in the canonical stamp |
| nested no-terminal-block rule | stamp **or** the dedicated marker assertion | the marker is inside the stamp, so both messages are admissible |

### 2.4 Constants and helpers the trim must NOT remove

| Symbol | Still used by |
|---|---|
| `CANONICAL_EXIT_SITES` | the two preserved parametrized tests, the coverage-table tests, `_site`, **and `tests/test_capability_determination_prose.py`** (`00` §10.4) |
| `CanonicalExitSite` | the tuple's element type; imported transitively |
| `_SITE_IDS` | `ids=` on both preserved parametrized tests (§3) |
| `_BRANCH_SITES` | `_assert_exit_contract`'s ownership branch, `test_the_branch_sites_are_derived_not_listed`, and §2.3's representative assertion |
| `_OWNER_TOKENS` | `_assert_exit_contract`, §2.3's ownership control |
| `_RETIRED_BLOCK_MARKERS` | `_assert_exit_contract`, `test_no_canon_surface_carries_a_retired_bespoke_block`, §2.3's bespoke-block control |
| `_surface_is_unmutated` | all seven controls |
| `import pytest` | `pytest.raises` in all seven controls, `parametrize` in §3 |

`_SITE_IDS` and `_BRANCH_SITES` are **trimmed in use, not deleted** — exactly the hard
constraint in `01-architecture-layout.md` §5.3.

## 3. The Preserve List — a Hard Floor (REQ-TRIM-02)

These tests are **out of scope for trimming**. They keep their **full parametrization over
all 9 sites** and are not touched by any edit in this document:

| Test | Items | Why it is not a mutation control |
|---|---|---|
| `test_each_covered_skill_satisfies_the_scripted_exit_contract` | **9** | the positive per-site contract assertion — the thing §2.1's rationale *relies on* |
| `test_scripted_stamp_stamped_verbatim` | **9** | a golden-file assertion on the rendered stamp |

Also **not trimmed**, per tech spec §3.4 — positive assertions, not mutation controls:

- `test_the_loop_surface_covers_every_loop_outcome`
- `test_the_docs_surface_covers_both_docs_outcomes`

**This list is the guard on the trim itself.** The risk REQ-TRIM-01 carries is
**over-deletion**: a trim pass that treats "collapse the parametrized negatives" as
"collapse the parametrized tests" would delete the golden-file coverage that makes the
collapse safe in the first place. If `test_each_covered_skill_satisfies_the_scripted_exit_contract`
stops running on all 9 sites, §2.1's rationale no longer holds and the mutation trim must
be reverted, not patched.

Everything else in `test_stage_exit_protocol.py` — the coverage-table tests, the extraction
tests, the retirement scans, `test_the_docs_surface_routes_epic_members_from_live_status`,
and `test_the_loop_surface_has_no_hand_written_next_command` — is unchanged.

## 4. The Structural Block Scan (REQ-TRIM-03)

Implements the region model in `00-core-definitions.md` §6. Everything below lands in
`tests/test_state_verb_call_sites.py`.

The unit of assertion becomes the fenced `state-*` call **together with the prose attached
to it**, delimited by markdown structure. The proximity window is removed (§5).

### 4.1 Constants

`CALL_RE`, `MIN_CALL_SITES`, `SKIP_STATUS_RE`, `SKIP_RECORDING_SURFACES`,
`EPIC_MANDATE_CLAUSES`, `FAILURE_PROTOCOL_CLAUSES`, and `ERROR_MESSAGE_PREFIXES` are
**unchanged**, values and doc-comments alike. Three constants are added:

```python
#: A fenced block delimiter. Anchored at line start (allowing leading indentation) so a
#: triple backtick appearing mid-sentence in prose cannot open or close a block.
FENCE_RE: Final[re.Pattern[str]] = re.compile(r"^\s*```")

#: A markdown ATX heading. Meaningful only OUTSIDE a fence: a bash comment has the same
#: shape and is not a document boundary.
HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^#{1,6} ")

#: The member flag whose mandate every call site's region must carry.
EPIC_FLAG: Final[str] = "--epic"
```

`EPIC_FLAG` is the **searched token**, not an exemption list. **No exemption constant is
introduced by this document, and none may be** (`00` §4.2): a per-site allow-list here
would recreate the `SURFACES_WITHOUT_PROSE` failure mode that `02-canon-and-prose-guard.md`
removes. The one call that must never carry the flag — the epic-scoped `state-verify` under
`--stage forge-0-epic` in `references/shared-conventions.md` — passes **naturally**, because
its own governing prose reads "``--epic`` must be absent or exactly equal to it" and that
sentence sits inside its region.

New module constants carry `Final` annotations, per `00` §1 and the stack profile's
complete-annotation rule. The file's pre-existing bare constants (`CALL_RE`,
`MIN_CALL_SITES`, …) are **left as they are** — re-annotating them is out of scope and
would enlarge the diff for no behavioral gain.

### 4.2 Fence-aware heading index — mandatory

`00-core-definitions.md` §6.3 makes this non-optional. A naive `^#{1,6} ` scan reads the
bash comments inside `references/shared-conventions.md` § Git Commit Protocol
(`# Commit 1 — before \`git commit\``, `# Commit 2 — after Commit 1 lands, so its hash
exists`) as headings. Under the fence-**block** bound of §4.4 those two lines sit *inside*
the block holding both `state-complete` calls, so they satisfy neither `index < first` nor
`index > last` and cannot move either bound — both calls keep identical bounds under either
heading mode, and canon is green either way. The fence-aware index is required because the
bound degrades to the call's own line for any `state-*` call found **outside** a fence
(§4.5's `(index, index)` fallback), and there an in-fence `#` line does truncate the region
below its mandate.

```python
def _fence_flags(lines: list[str]) -> list[bool]:
    """Mark every line that lies inside a fenced block, delimiters included.

    A `#` line inside a fence is a comment in the fenced language, never a document
    heading, so heading detection must consult this index first.

    Args:
        lines: The document's lines, in order, without trailing newlines.

    Returns:
        One flag per line, `True` when that line belongs to a fenced block — counting
        the opening and closing delimiter lines themselves as part of their block.
    """
    flags: list[bool] = []
    inside = False
    for line in lines:
        if FENCE_RE.match(line):
            flags.append(True)  # the delimiter belongs to its own block
            inside = not inside
            continue
        flags.append(inside)
    return flags


def _heading_lines(lines: list[str], flags: list[bool]) -> list[int]:
    """Return the 0-indexed heading lines, ignoring `#` lines inside a fence.

    Args:
        lines: The document's lines, in order.
        flags: `_fence_flags(lines)` for the same document.

    Returns:
        Ascending 0-indexed positions of the document's ATX headings.
    """
    return [
        index
        for index, line in enumerate(lines)
        if not flags[index] and HEADING_RE.match(line)
    ]
```

### 4.3 Fenced blocks that hold a call

The bound is the fence **BLOCK**, not the call line (`00` §6.2). This function is what
makes that true:

```python
def _call_blocks(lines: list[str]) -> list[tuple[int, int]]:
    """Return the bounds of every fenced block containing a `state-*` call.

    Blocks are delimited by toggling on fence delimiters rather than by scanning the
    fence-flag index, so two adjacent blocks with no blank line between them stay
    separate. A block with no `state-*` call is not a region bound and is omitted.

    Args:
        lines: The document's lines, in order.

    Returns:
        Ascending, non-overlapping `(first, last)` 0-indexed inclusive bounds — the
        opening and closing delimiter lines — one per call-bearing block. A fence left
        unterminated at end of file contributes no block.
    """
    blocks: list[tuple[int, int]] = []
    start: int | None = None
    holds_call = False
    for index, line in enumerate(lines):
        if FENCE_RE.match(line):
            if start is None:
                start, holds_call = index, False
            else:
                if holds_call:
                    blocks.append((start, index))
                start, holds_call = None, False
            continue
        if start is not None and CALL_RE.search(line):
            holds_call = True
    return blocks
```

### 4.4 Region bounds

```python
def _region_bounds(
    block: tuple[int, int],
    headings: list[int],
    blocks: list[tuple[int, int]],
    total: int,
) -> tuple[int, int]:
    """Return the half-open line span attached to one call-bearing fenced block.

    The lower bound is the later of the nearest enclosing heading and the end of the
    previous call-bearing fenced block; the upper bound is the earlier of the next
    heading and the start of the next call-bearing fenced block. Bounding below on the
    block rather than on the previous call line is what lets two calls inside one fence
    share the mandate that precedes both.

    Args:
        block: `(first, last)` 0-indexed bounds of the block holding the call — or the
            call's own line twice, when the call is not fenced.
        headings: `_heading_lines(...)` for the same document.
        blocks: `_call_blocks(...)` for the same document.
        total: The document's line count.

    Returns:
        A `(lower, upper)` half-open 0-indexed span, suitable for slicing `lines`.
    """
    first, last = block
    lower = max(
        max((index + 1 for index in headings if index < first), default=0),
        max((end + 1 for _, end in blocks if end < first), default=0),
    )
    upper = min(
        min((index for index in headings if index > last), default=total),
        min((start for start, _ in blocks if start > last), default=total),
    )
    return lower, upper
```

The call's own block is **inside** its region (`00` §6.1's diagram), which is how the two
fenced calls that literally carry the flag satisfy the guard through their own text.

### 4.5 Call-site enumeration

```python
class CallSite(NamedTuple):
    """One `state-*` invocation and the document structure attached to it."""

    # Canon file the call was read from — carried for the failure message only.
    path: Path
    # 1-indexed line of the verb, as a reader would cite it.
    line: int
    # The verb itself, e.g. `state-artifact`.
    verb: str
    # 0-indexed inclusive bounds of the fenced block holding the call. A call found
    # outside any fence bounds itself, so the region rules still apply to it.
    block: tuple[int, int]
    # 0-indexed half-open span of the attached region.
    bounds: tuple[int, int]
    # The fenced block's own text — the unit Guard 3 searches.
    block_text: str
    # The whole attached region's text — the unit Guard 1 searches.
    region: str


def _sites_in(path: Path, text: str) -> list[CallSite]:
    """Return every `state-*` call site in `text`, with its attached region.

    Takes the document text as an argument rather than reading `path`, so a control can
    scan a mutated copy without any repository file being written.

    Args:
        path: The canon file `text` was read from; used only to label failures.
        text: The document's full contents.

    Returns:
        Call sites in document order, one per matching verb line.
    """
    lines = text.splitlines()
    flags = _fence_flags(lines)
    headings = _heading_lines(lines, flags)
    blocks = _call_blocks(lines)
    sites: list[CallSite] = []
    for index, line in enumerate(lines):
        match = CALL_RE.search(line)
        if not match:
            continue
        block = next(
            ((first, last) for first, last in blocks if first <= index <= last),
            (index, index),
        )
        bounds = _region_bounds(block, headings, blocks, len(lines))
        sites.append(
            CallSite(
                path=path,
                line=index + 1,
                verb=match.group(1),
                block=block,
                bounds=bounds,
                block_text="\n".join(lines[block[0] : block[1] + 1]),
                region="\n".join(lines[bounds[0] : bounds[1]]),
            )
        )
    return sites


def _call_sites() -> list[CallSite]:
    """Every `state-*` call site across canon, in a stable file order."""
    return [site for path in _canon_files() for site in _sites_in(path, read(path))]
```

`_canon_files()` is unchanged. `_call_sites()` keeps its name and remains a `list`, so
`test_the_epic_guard_is_not_vacuous`'s `len(_call_sites())` is untouched (§7).

### 4.6 Guard 1, rewritten

```python
def test_every_state_verb_call_site_carries_the_epic_instruction():
    """Zero call sites whose attached region omits the `--epic` mandate."""
    missing = [
        f"{site.path.relative_to(REPO_ROOT).as_posix()}:{site.line} ({site.verb})"
        for site in _call_sites()
        if EPIC_FLAG not in site.region
    ]
    assert not missing, (
        "`state-*` call sites whose section carries no `--epic` instruction — the "
        "region searched runs from the enclosing heading (or the previous fenced call "
        "block) to the next heading (or the next fenced call block). Epic members will "
        "write the wrong feature's state:\n  " + "\n  ".join(missing)
    )
```

**The failure message names the region's bounds in structural terms**, so a maintainer
chasing a failure knows exactly which span to inspect — the same diagnostic obligation the
deleted meta-test (§5.2) was reaching for, now discharged by construction rather than by a
test that reads another test's source.

### 4.7 Worked example — the two cases that decide the design

Against `references/shared-conventions.md`:

**§ Stage-Entry Guard** holds two call-bearing fences under one heading: the `state-enter`
fence and, further down, the `state-artifact` fence. Between them sit three prose
paragraphs, the last of which carries the `state-artifact` call's own `--epic` mandate
("Add ``--epic "{epic}"`` when this feature is an epic member — required, per the Pipeline
State Protocol.").

| Call | lower bound | upper bound | mandate found at |
|---|---|---|---|
| `state-enter` | the line after `## Stage-Entry Guard` | the `state-artifact` fence's opening delimiter | the paragraph introducing the `state-enter` fence |
| `state-artifact` | the line after the `state-enter` fence's closing delimiter | the next heading (`## Stage-Completion Re-check`) | the paragraph introducing the `state-artifact` fence |

The fence-block bound is what separates these two. Under a **heading-only** bound they merge
into one region, and deleting the `state-artifact` mandate leaves the guard green on the
strength of the unrelated `state-enter` mandate — the exact regression the current
`LOOKBEHIND` doc-comment records at lookbehind 20. §6's mutation control pins this case.

**§ Git Commit Protocol** holds **one** fence containing **two** `state-complete` calls
(commit 1 and commit 2). Both calls resolve to the same block, therefore to the same region,
which starts after the heading and contains the paragraph mandating "Add ``--epic
"{epic}"`` to each". Both pass.

### 4.8 The two false-failure modes this section exists to prevent

Both are stated because the wrong variant **looks correct** and fails in a way that reads
as a canon defect rather than a guard defect:

| Wrong variant | Symptom |
|---|---|
| bounding on the previous **call line** instead of the previous fence **block** | the Git Commit Protocol's second `state-complete` gets a region starting *below* the shared mandate → **1 false failure** on a correct canon file |
| a naive `^#{1,6} ` heading scan that does not toggle on fences | no false failure under the fence-block bound — the two bash comments sit inside the block and cannot move a bound; the region truncates for any **unfenced** call site, which is why the index is fence-aware |

Per `00` §6.2, the call-line variant discriminates more finely per site and is nonetheless
**rejected**: a guard that is red on correct canon is not a stronger guard.

**Recorded limitation.** An **unterminated** fence in a canon file makes every later
heading invisible to `_heading_lines` and contributes no block to `_call_blocks`, which
widens the affected regions rather than crashing. This is a fail-open direction on a
condition that any markdown renderer also mis-renders, and it is recorded here rather than
guarded, so a later round resolves it against a position (C-04).

## 5. Consequent Deletions (REQ-TRIM-04, REQ-TRIM-05)

### 5.1 Constants deleted

| Symbol | Requirement | Note |
|---|---|---|
| `LOOKBEHIND` | REQ-TRIM-04 | with its measured-bounds doc-comment |
| `LOOKAHEAD` | REQ-TRIM-04 | with its measured-bounds doc-comment |
| `CALL_SPAN` | REQ-TRIM-04 | with its doc-comment, including the "LOAD-BEARING FOR GUARD 1'S WINDOW" paragraph |

`_call_sites()`'s window slicing —
`window = lines[max(0, index - LOOKBEHIND) : index + LOOKAHEAD]` — is deleted with them and
replaced by §4.5.

**Why these are deletable and the structural bounds are not** (`00` §6.5): the replacement's
bounds are *document structure*, which moves with the text; the deleted bounds are *tuned
integers*, which must be re-tuned whenever prose is reflowed. There is nothing left to tune,
which is what makes REQ-TRIM-04's tuning tests meaningless rather than merely redundant.
This is a **tunability** claim only — detection strength is a separate axis and is weaker
(§9).

### 5.2 Tests deleted

| Test | Requirement | Why |
|---|---|---|
| `test_the_window_is_no_wider_than_the_measured_maximum` | REQ-TRIM-04 | its three assertions bound `LOOKBEHIND`, `CALL_SPAN`, and `LOOKAHEAD ≤ CALL_SPAN` — three constants that no longer exist. Replaced, not merely removed: §6. |
| `test_the_failure_message_describes_the_whole_window` | REQ-TRIM-05 | it asserts *another test's failure-message wording* by reading its source with `inspect.getsource`. Its subject — a window with two limbs — no longer exists, and the meta-layer is the shape this feature removes. |

### 5.3 Import removed

`import inspect` is deleted from `tests/test_state_verb_call_sites.py` — its only use was
the REQ-TRIM-05 meta-test (`00` §11). `inspect` remains available to the rest of the suite
and is untouched elsewhere.

The final import block for this file:

```python
from __future__ import annotations

import re
from pathlib import Path
from typing import Final, NamedTuple

from _forge_paths import REFERENCES, REPO_ROOT, SCRIPTS, SKILLS, read
```

**No `import pytest`.** This file has never imported it and must not start: it contains no
parametrized test and no `raises` usage, and `test_this_guard_is_not_skippable` scans this
file's own source for gate calls (see §7).

### 5.4 Guard 3 keeps its protection without the flattening window

`SKIP_STATUS_RE` is unchanged. `_state_verify_call_text` no longer joins `CALL_SPAN` lines;
it returns each `state-verify` call's **own fenced block**, computed by the same structural
machinery as §4:

```python
def _state_verify_call_text(path: Path) -> list[str]:
    """Each `state-verify` invocation in `path`, as the text of its own fenced block.

    The fenced block is the unit this guard's subject is stated in: a surface that
    records a verification skip must ship the fence that writes it, so the invocation's
    block — not the prose around it — is what is searched.

    Args:
        path: A canon file to scan.

    Returns:
        One string per `state-verify` call site, being that call's fenced block. Two
        calls sharing one block yield that block twice, matching the per-call unit the
        caller iterates.
    """
    return [
        site.block_text
        for site in _sites_in(path, read(path))
        if site.verb == "state-verify"
    ]
```

**Deviation from tech spec §3.5, recorded deliberately.** §3.5's consequent-deletion bullet
says the flattening is "replaced by the same structural region". This document binds Guard 3
to the region model's **inner** bound (the call's own fence block) rather than its outer
bound (the whole region), because Guard 3's subject is *a shipped fence*: searching the
whole region would let a prose sentence reading "record it with `--status skipped`" satisfy
a guard that exists to require the fence. Both bounds come from the same structural
computation and neither carries a tuned integer, so REQ-TRIM-04's intent is fully met;
the inner bound is the one that does not silently weaken Guard 3. Recorded here so a
verifier resolves it against a position rather than filing it (C-04).

`test_every_skip_recording_surface_persists_the_skip_through_state_verify` and
`test_the_skip_guard_is_not_vacuous` are **otherwise unchanged**, and both keep working:
the flag `SKIP_STATUS_RE` looks for sits on the call's own continuation line, inside the
block.

**One narration correction is required, and only one.**
`test_the_skip_guard_is_not_vacuous`'s docstring names a mechanism that no longer exists
("a `_state_verify_call_text` span too short to reach the flag"). Leaving it would document
a removed window. Replace that clause with the block-based statement of the same intent —
no counts, no measurements (REQ-CANON-03):

```python
def test_the_skip_guard_is_not_vacuous():
    """A negative control: deleting a fence's `--status skipped` must break Guard 3.

    Without this, a `SKIP_STATUS_RE` that stopped matching — or a
    `_state_verify_call_text` that stopped returning the fenced block the flag lives in
    — would satisfy the guard above by finding nothing to complain about, which is
    indistinguishable from every surface being compliant.
    """
```

The test **body is unchanged**.

### 5.5 The module docstring

The file's module docstring currently describes the two invariants and then records a
parenthetical tally of call sites, which contradicts `MIN_CALL_SITES` and is a count in
narration. The restructure replaces that sentence with an intent-only statement
(REQ-CANON-03):

```
Both invariants hold across canon today; these guards keep them holding.
```

Nothing else in the docstring changes. In particular the two numbered invariant paragraphs
and the "no skip gate may be introduced" paragraph survive verbatim — they state the
guards' purpose, not their mechanism.

## 6. The Replacement Mutation Control (REQ-TRIM-04)

**One test is ADDED, so REQ-TRIM-04 is a replacement rather than a net deletion.**

Deleting `test_the_window_is_no_wider_than_the_measured_maximum` removes the **only bound on
the guard's discriminating width**. `test_the_epic_guard_is_not_vacuous` cannot substitute:
a site-count floor detects a regex that stopped matching, not a region that silently grew
until every site is covered by a neighbour's mandate. Nothing else fails when the guard
stops discriminating — which is precisely how the original hole shipped.

Its structural equivalent is a **mutation control**: delete one known site's own `--epic`
mandate from an in-memory copy of `references/shared-conventions.md` and assert Guard 1's
predicate reports that site. The site is the **`state-artifact` call under § Stage-Entry
Guard**, because that is the case the recorded regression names (§4.7, `00` §6.4).

```python
#: The verb whose own `--epic` mandate the region control deletes. Its mandate sits in
#: the prose between two fenced calls under one heading, so a region that stops
#: separating those two fences stops reporting it.
_REGION_PROBE_VERB: Final[str] = "state-artifact"


def _region_probe_site(text: str) -> CallSite:
    """Return the probe call site in a copy of shared-conventions.md.

    Args:
        text: The document's contents — canon, or a mutated copy of it.

    Returns:
        The single `state-artifact` call site the region control targets.

    Raises:
        AssertionError: The document does not carry exactly one such call site, so the
            control can no longer name which one it probed.
    """
    found = [
        site for site in _sites_in(CONVENTIONS, text) if site.verb == _REGION_PROBE_VERB
    ]
    assert len(found) == 1, (
        f"expected exactly one `{_REGION_PROBE_VERB}` call site in "
        f"{CONVENTIONS.name}, found {len(found)} — re-point the region control at a "
        "site whose own mandate can be identified"
    )
    return found[0]


def _without_the_probe_mandate(text: str) -> str:
    """Return a copy of `text` with the probe site's own `--epic` mandate removed.

    The mandate is located structurally — the lines of the probe's lead-in that lie
    outside its own fenced block — so the control does not depend on the exact wording
    of the sentence carrying it, and no repository file is written.

    Args:
        text: The document's contents.

    Returns:
        The same document with the flag struck from the probe's attached prose.

    Raises:
        AssertionError: The probe's lead-in carries no mandate to remove, so the control
            would assert nothing.
    """
    lines = text.splitlines()
    site = _region_probe_site(text)
    first, last = site.block
    flags = _fence_flags(lines)
    headings = _heading_lines(lines, flags)
    blocks = _call_blocks(lines)
    # The probe's own lead-in, fixed by document structure. Deliberately NOT
    # site.bounds: a span taken from the function under test widens with it, so the
    # control would delete a neighbour's mandate too and never go green.
    lower = max(
        max((index + 1 for index in headings if index < first), default=0),
        max((end + 1 for _, end in blocks if end < first), default=0),
    )
    upper = min(
        min((index for index in headings if index > last), default=len(lines)),
        min((start for start, _ in blocks if start > last), default=len(lines)),
    )
    mutated = list(lines)
    removed = 0
    for index in range(lower, upper):
        if first <= index <= last or EPIC_FLAG not in mutated[index]:
            continue
        mutated[index] = mutated[index].replace(EPIC_FLAG, "the member flag")
        removed += 1
    assert removed, (
        f"{CONVENTIONS.name}: the {_REGION_PROBE_VERB} lead-in carries no `{EPIC_FLAG}` "
        "mandate to delete — the control has nothing to mutate"
    )
    return "\n".join(mutated)


def test_deleting_a_call_sites_own_epic_mandate_is_reported():
    """Guard 1 must report a site whose own mandate is gone, not lean on a neighbour's.

    This is the bound on the guard's discriminating width. A region that widened until
    every site is covered by an adjacent call's mandate would still pass Guard 1 and the
    non-vacuity floor, and nothing else would fail.
    """
    original = read(CONVENTIONS)
    probe_line = _region_probe_site(original).line

    before = {
        site.line for site in _sites_in(CONVENTIONS, original) if EPIC_FLAG not in site.region
    }
    assert not before, (
        f"{CONVENTIONS.name} already has call sites with no `{EPIC_FLAG}` mandate in "
        f"region {sorted(before)} — fix canon before reading this control"
    )

    after = {
        site.line
        for site in _sites_in(CONVENTIONS, _without_the_probe_mandate(original))
        if EPIC_FLAG not in site.region
    }
    assert probe_line in after, (
        f"deleting the {_REGION_PROBE_VERB} call's own `{EPIC_FLAG}` mandate left Guard "
        f"1 green at {CONVENTIONS.name}:{probe_line} — the region now reaches into a "
        "neighbouring call's mandate, which is the hole this control exists to close"
    )

    assert read(CONVENTIONS) == original, (
        f"the region control mutated {CONVENTIONS.name} — mutate the copy, never canon"
    )
```

Four properties make this a real control rather than a restatement:

1. **The `before` assertion establishes the baseline.** Without it, a guard that reported
   *every* site would satisfy the `after` assertion trivially.
2. **The mutation is structural, not textual.** It strikes the flag from whichever lead-in
   lines carry it outside the probe's own fence, so rewording the mandate sentence in canon
   does not silently turn the control into a no-op.
3. **Canon is re-read and compared afterwards**, matching the `_surface_is_unmutated`
   idiom in `test_stage_exit_protocol.py`: a control that mutated the repository would be a
   defect of its own.
4. **The strike span is computed from document structure directly, never from
   `_region_bounds`.** A control whose mutation is sized by the function under test cannot
   detect that function widening: widening the region would widen the strike span in
   lockstep, so the neighbouring call's mandate would be deleted too and the probe would
   still be reported. Sizing the span independently is what makes the degradation in §13
   observable.

This is **one test inside REQ-TRIM-04's budget** (2 deleted, 1 added) and is the only thing
that fails if the region silently widens again.

## 7. Preserved Unchanged (REQ-TRIM-06)

| Symbol | Status | Why |
|---|---|---|
| `test_the_epic_mandate_itself_is_still_documented` | **verbatim** | it pins the normative rule in `references/shared-conventions.md` — the clauses in `EPIC_MANDATE_CLAUSES` — rather than a mechanism. Guard 1 walks call sites, so deleting the mandate *at its source* flags nothing; this is the only test that catches it. |
| `EPIC_MANDATE_CLAUSES` | **verbatim** | its subject |
| `MIN_CALL_SITES` | **verbatim**, value and doc-comment | the non-vacuity floor is independent of how regions are computed. Its comment references no removed machinery, so it is not rewritten — an unnecessary narration edit is exactly the churn this feature exists to stop. |
| `test_the_epic_guard_is_not_vacuous` | **verbatim** | `len(_call_sites())` still returns the site count |
| `test_the_verb_failure_protocol_is_still_documented` | **verbatim** | Guard 2, untouched by this workstream |
| `test_the_documented_error_messages_still_exist_in_the_script` | **verbatim** | Guard 2, untouched |
| `test_every_skip_recording_surface_persists_the_skip_through_state_verify` | **verbatim** | Guard 3; its helper is rebound (§5.4), its own body is not |
| `test_this_guard_is_not_skippable` | **verbatim** | Guard 4 |

**A constraint every symbol added by §4 and §6 must satisfy:**
`test_this_guard_is_not_skippable` reads this file's own source and asserts that
`"skipif("`, `"importorskip("`, and `"pytest.skip("` do not appear. No code specified in
this document uses any of them, and none may be introduced — including in a docstring where
the token would be followed by an open parenthesis.

## 8. Source-Text Assertion Removal (REQ-TRIM-07)

In `tests/test_stage_constants_parity.py`, remove **exactly** the source-text assertions in
`test_the_exit_domains_are_derived_not_hand_listed` that duplicate a runtime check **in the
same test** (tech spec §3.6) — together with the comment that narrates only them:

```python
    # DELETE from here …
    # The derivation must be textual too: a hand-written tuple that happens to agree
    # today is the drift this guard exists to prevent.
    source = read(SESSION)
    assert "EXIT_STAGES: Final[tuple[str, ...]] = get_args(ExitStage)" in source
    for alias in ("LoopOutcome", "DocsOutcome", "VerifyOutcome", "FixOutcome"):
        assert f"frozenset(get_args({alias}))" in source, f"{alias} not derived"
    # … to here.
```

The resulting test in full:

```python
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
```

**Why each removal is duplication and not coverage:**

| Removed assertion | The runtime check that already proves it |
|---|---|
| `"EXIT_STAGES: Final[tuple[str, ...]] = get_args(ExitStage)" in source` | `session.EXIT_STAGES == get_args(session.ExitStage)` — two lines above, on the loaded module |
| the per-alias `f"frozenset(get_args({alias}))" in source` loop | the `session.EXIT_OUTCOMES == {...}` dict comparison — each value is compared against `frozenset(get_args(alias))` at runtime |

The first is additionally corroborated cross-file by
`tests/test_stage_exit_protocol.py::test_exit_stages_is_the_runtime_tuple_derived_from_the_extracted_alias`,
which regex-matches the same assignment against the script's text. That is corroboration,
not the basis: REQ-TRIM-07's basis is the same-test runtime check.

**RETAINED — `test_the_cli_stage_choices_are_the_whole_exit_domain`.** Its
`assert "choices=EXIT_STAGES" in source` and `assert "_STAGE_EXIT_CLI_STAGES" not in source`
both stay, unchanged, along with the whole test and its docstring. REQ-TRIM-07 scopes to
assertions that duplicate an **existing runtime check**; this one has no counterpart —
**no runtime check in this file establishes that the `--stage` argument's `choices` reads
the shared constant**, so removing it would delete coverage rather than duplication. It is
cited in PRD §3.2's requirement text but is out of scope for it. Converting it to a runtime
`argparse`-choices inspection is recorded as out of scope in tech spec §10.2 item 4 and must
not be attempted here.

**No import churn.** `read` and `SESSION` remain used by other tests in the same file
(`test_each_shared_constant_is_assigned_exactly_once`,
`test_the_cli_stage_choices_are_the_whole_exit_domain`, and others), so no import becomes
unused and `ruff check tests/` sees no new error from this edit. `ast` also remains — it is
used for `ast.literal_eval` constant extraction, not self-inspection, and is out of scope
(`00` §11).

## 9. Declared Boundaries (C-04)

Recorded so a later round resolves them against a position rather than re-deriving them.

**Detection strength is reduced, and this is not parity.** With the fence-block bound, some
sites remain detectable only through a neighbouring call's mandate in the same region. That
is a **real reduction** from the window's per-site discrimination, accepted in exchange for
removing every tuned integer (`00` §6.4).

**The residual is deliberately not enumerated.** "Remove each site's own mandate and ask
whether the guard still reports it" has no single mechanical meaning where a region carries
more than one mandate — which is precisely the case the measurement would be about. The one
realization this document ships, §6's `_without_the_probe_mandate`, strikes every in-region
mandate outside the call's own block; applied per-site across canon it yields a materially
different census than a rule striking only the call's own lead-in prose. Rather than pin a
figure no later round could reproduce, this document states the ordering qualitatively (`00`
§6.2) and keeps only the reproducible facts: **34/34 green on canon**, and **1 false failure**
for the rejected call-line variant. `00` §9's "re-measure, never re-estimate" rule binds
figures that have a procedure; this residual deliberately has none.

**Do not read §5.1's tunability argument as a detection-parity claim.** `00` §6.5 states the
distinction: the adopted bounds have nothing to tune; they do not discriminate as finely.
Both facts are true and neither implies the other.

**The mutation control pins the `state-artifact` case specifically** (§6), which is the
documented regression and the case the adopted variant recovers over the heading-only
variant. It does **not** pin the remaining residual sites, and no test in this document
claims to.

**Not a goal of this workstream:** re-deriving the residual, adding per-site exemptions
(forbidden — `00` §4.2), or hardening the region model against evasion shapes not
enumerated here. `00` §5.3's meta-guard norm applies: the guard's contract is the declared
set.

## 10. Error Handling

Every operation in this document is a test-time assertion; no runtime exception type is
introduced and nothing raises `UsageError` (`00` §8 governs production paths only, none of
which this document touches).

| Operation | Failure mode | Handling |
|---|---|---|
| reading a canon file | file missing | `_forge_paths.read` asserts `path.is_file()` and fails with the path — a missing canon file is a drift failure in its own right, never a skipped test |
| `_site(skill)` at import | the representative is no longer a covered site | `AssertionError` naming the skill, raised at collection |
| `_region_probe_site` | zero or multiple probe call sites | `AssertionError` naming the count and the file, telling the reader to re-point the control |
| `_without_the_probe_mandate` | the probe's region carries no mandate | `AssertionError` — refuses to run a control that would assert nothing |
| `_call_blocks` on an unterminated fence | the block is dropped | fail-open: regions widen; recorded in §4.8, not guarded |
| Guard 1 | one or more sites uncovered | one message listing every offending `path:line (verb)`, plus the region's structural bounds |
| the seven mutation controls | the guard no longer detects the mutation | `pytest.raises` fails with the class's own name; `_surface_is_unmutated` separately fails if canon was written |

**Diagnostic obligation.** Every assertion specified here names *which* file, *which* line,
and *what* is missing. This is the same standard `00` §8.3 sets for `06-brittleness-batch.md`
and it applies to the replacements in §4.6 and §6 as well: reading the failure output alone
must be enough to locate the defect.

## 11. Net Effect

| File | Before | After | Delta |
|---|---|---|---|
| `test_stage_exit_protocol.py` — mutation controls | 67 items | **7** | −60 |
| `test_stage_exit_protocol.py` — stamp-verbatim | 18 items | **18** | 0 (REQ-TRIM-02) |
| `test_stage_exit_protocol.py` — everything else | 17 items | **17** | 0 |
| `test_state_verb_call_sites.py` | 10 tests | **9** | −2 (§5.2), +1 (§6) |
| `test_stage_constants_parity.py` | unchanged count | unchanged | 0 — assertions removed, no test removed |

> **Derived figures (REQ-TRIAL-06).** These are computed from §2.1, §3, §5.2, §6 and §8. If
> any of those rosters changes, recompute this table **in the same edit**.
> `07-testing-strategy.md` §5.2 and §5.4 derive from this table in turn.

## 12. Dependencies

**Spec documents that must be read first:**

- `00-core-definitions.md` — §4.2 (no exemption constant), §6 (the structural region model
  this document implements), §8.3 (diagnostic obligation), §10.1 (REQ-CANON-03), §10.4 (the
  `CANONICAL_EXIT_SITES` export constraint), §11 (the removed `inspect` import).
- `01-architecture-layout.md` — §3.3 (file ownership), §5.2 step 4 (this workstream runs
  after the canon edit, the production validations, and the prose-guard rewrite), §5.3 (the
  export constraint as a sequencing hazard).

**Documents that depend on this one:**

- `02-canon-and-prose-guard.md` — imports `CANONICAL_EXIT_SITES` from the file §2 trims.
  **Sequencing:** `02`'s guard rewrite lands before this trim (`01` §5.2 steps 3 then 4),
  and the import must be re-checked after **both**.
- `07-testing-strategy.md` — asserts against §4's region model and consumes §11's counts.

**Implementation order within this document:** §4 before §6 (the control calls `_sites_in`),
§4 before §5.4 (the helper rebinding uses the same machinery), §2 independent of both. §8 is
independent of everything else here.

**External packages:** none added, none removed. Stdlib (`re`, `pathlib`, `typing`) plus
`pytest` in `test_stage_exit_protocol.py` only.

**Nothing in this document depends on `04-production-validations.md`.** The trim is
independent of both shipped-behavior changes.

## 13. Verification

Run `python3 -m pytest tests -q` after each block; the ordered gate list is
`01-architecture-layout.md` §7.

**REQ-TRIM-01**

- [ ] `tests/test_stage_exit_protocol.py` collects **7** mutation-control items — one per
      class in §2.1's table, with all seven classes still present.
- [ ] `python3 -m pytest tests/test_stage_exit_protocol.py --collect-only -q` shows no
      mutation control parametrized over `CANONICAL_EXIT_SITES`, `_BRANCH_SITES`,
      `_RETIRED_BLOCK_MARKERS`, or `_OWNER_TOKENS`.
- [ ] Every control mutates `_MUTATION_SITE`, and `_MUTATION_SITE` is bound through `_site`
      at module scope.
- [ ] Each control still fails when its `pytest.raises` is inverted — i.e. the class is
      genuinely detected, not vacuously passing.

**REQ-TRIM-02**

- [ ] `test_each_covered_skill_satisfies_the_scripted_exit_contract` collects **9** items.
- [ ] `test_scripted_stamp_stamped_verbatim` collects **9** items.
- [ ] `test_the_loop_surface_covers_every_loop_outcome` and
      `test_the_docs_surface_covers_both_docs_outcomes` are unchanged in the diff.

**REQ-TRIM-03**

- [ ] Guard 1 passes against current canon with **zero** reported sites.
- [ ] `len(_call_sites())` is at or above `MIN_CALL_SITES`.
- [ ] No exemption constant, allow-list, or per-site skip exists anywhere in
      `tests/test_state_verb_call_sites.py`; the epic-scoped `state-verify` under
      `--stage forge-0-epic` passes through its own region's prose.
- [ ] `_heading_lines(lines, _fence_flags(lines))` returns no index that `_fence_flags`
      marks `True`, asserted directly against `references/shared-conventions.md`.
- [ ] The two `state-complete` calls in § Git Commit Protocol resolve to **identical**
      `bounds`, confirming the bound is the fence block and not the call line.

**REQ-TRIM-04, REQ-TRIM-05**

- [ ] `LOOKBEHIND`, `LOOKAHEAD`, and `CALL_SPAN` do not appear anywhere in `tests/`.
- [ ] `test_the_window_is_no_wider_than_the_measured_maximum` and
      `test_the_failure_message_describes_the_whole_window` no longer exist.
- [ ] `import inspect` is absent from `tests/test_state_verb_call_sites.py`.
- [ ] `test_deleting_a_call_sites_own_epic_mandate_is_reported` exists and **passes**.
- [ ] That control **fails** when `_region_bounds`'s lower bound is degraded to the
      enclosing heading alone — the heading-only variant is what it is bounding against.
- [ ] `references/shared-conventions.md` is byte-identical before and after the run
      (`git status --porcelain references/` prints nothing).
- [ ] `tests/test_state_verb_call_sites.py` contains **9** test functions.

**REQ-TRIM-06**

- [ ] `test_the_epic_mandate_itself_is_still_documented` and `EPIC_MANDATE_CLAUSES` are
      byte-identical in the diff.
- [ ] `MIN_CALL_SITES` and `test_the_epic_guard_is_not_vacuous` are byte-identical in the
      diff.
- [ ] Guard 2's two tests and Guard 4 are absent from the diff.

**REQ-TRIM-07**

- [ ] `"EXIT_STAGES: Final[tuple[str, ...]] = get_args(ExitStage)"` no longer appears as an
      assertion in `tests/test_stage_constants_parity.py`.
- [ ] No `f"frozenset(get_args({alias}))"` loop remains in that file.
- [ ] `assert "choices=EXIT_STAGES" in source` **still exists** in
      `test_the_cli_stage_choices_are_the_whole_exit_domain`.
- [ ] `ruff check tests/` reports no new unused-import error from that file.

**Cross-cutting**

- [ ] `from test_stage_exit_protocol import CANONICAL_EXIT_SITES` still resolves and yields
      **9** entries after this workstream and `02`'s (`00` §10.4, `01` §5.3).
- [ ] `CANONICAL_EXIT_SITES`, `CanonicalExitSite`, `_SITE_IDS`, and `_BRANCH_SITES` all
      still exist with their current names and module scope.
- [ ] No comment or docstring added by this workstream carries a count, a date, a
      "measured", or any other empirical claim (REQ-CANON-03).
- [ ] `skipif(`, `importorskip(`, and `pytest.skip(` appear nowhere in
      `tests/test_state_verb_call_sites.py`.
- [ ] `adapters/`, `references/`, `skills/`, `scripts/`, and `eval/` are absent from this
      workstream's diff.
- [ ] `bash scripts/validate.sh` reports "All checks passed!".
