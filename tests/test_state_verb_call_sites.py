"""Drift guards for R4's two call-site invariants (spec 03 §14, §3.6; finding V-005).

R4 converted seven hand-edited pipeline-state writes into `scripts/forge-session.py`
subprocess calls. That created a runtime failure surface governed by two prose
invariants in `references/shared-conventions.md` — and, alone among R1/R3/R4/R6's
boundaries, neither had a drift guard:

1. **`--epic` on every call.** § Pipeline State Protocol mandates appending
   ``--epic "{epic}"`` to **every** `state-*` call "in this file and in every skill
   body" when the feature is an epic member. Lose that instruction and the verb
   resolves the bare name itself and exits 2 on ambiguity — a hard break that surfaces
   **only** in epic mode, the least-exercised path, so it would ship undetected.
2. **The exit-2 failure protocol.** § Pipeline State Protocol requires an agent to
   surface the verb's `Error:` line verbatim, stop, and never hand-author the JSON as a
   workaround. Lose that text and an agent routes around a failed verb by writing state
   by hand — re-introducing exactly the drift REQ-R4-02 exists to remove.

Both invariants hold across canon today; these guards keep them holding.

Stdlib only, asserting against canon (`skills/`, `references/`, `scripts/`) and never
against generated `adapters/`. No skip gate may be introduced — see
`test_always_loaded_surface.py::test_the_hook_guards_cannot_degrade_to_a_skip`.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final, NamedTuple

from _forge_paths import REFERENCES, REPO_ROOT, SCRIPTS, SKILLS, read

CONVENTIONS = REFERENCES / "shared-conventions.md"
SESSION = SCRIPTS / "forge-session.py"

#: A `state-*` verb invocation in a bash fence, e.g. `forge-session.py" state-complete \`.
CALL_RE = re.compile(r'forge-session\.py"?\s+(state-[a-z]+)')

#: Non-vacuity floor, NOT a pinned total. A regex that stopped matching would satisfy the
#: "every call site carries --epic" assertion trivially. 34 sites today (2026-07-31, after
#: the `state-verify` fences landed in forge-verify, forge-fix, forge-6-docs, and
#: shared-conventions.md, then the two `--status skipped` fences in forge-4-backlog Step 6
#: and forge-5-loop Step 5b); the floor is the count, since a call site being REMOVED is
#: itself worth a look.
MIN_CALL_SITES = 34

#: A fenced block delimiter. Anchored at line start (allowing leading indentation) so a
#: triple backtick appearing mid-sentence in prose cannot open or close a block.
FENCE_RE: Final[re.Pattern[str]] = re.compile(r"^\s*```")

#: A markdown ATX heading. Meaningful only OUTSIDE a fence: a bash comment has the same
#: shape and is not a document boundary.
HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^#{1,6} ")

#: The member flag whose mandate every call site's region must carry.
EPIC_FLAG: Final[str] = "--epic"

#: `--status skipped` on a `state-verify` call, matched against a flattened invocation.
SKIP_STATUS_RE = re.compile(r"--status\s+skipped\b")

#: Canon surfaces whose prose records a `forge-verify-*` result of `skipped`, each of
#: which must therefore ship the fence that writes it. Seeded from V-002's two regressed
#: sites plus forge-6-docs, which already had one and is the shape the other two copied.
#:
#: This is an allow-list, not a scan. A prose scan for "persist … `skipped`" also matches
#: the shared `--verify-capability` paragraph in forge-1-prd, forge-2-tech, and
#: forge-3-specs, which describe the in-stage Standard Verify Gate's skip and carry no
#: fence of their own. Whether those three need one is a live question V-002 did not
#: settle; folding them in here would assert an answer this guard has no basis to give.
SKIP_RECORDING_SURFACES = (
    "skills/forge-4-backlog/SKILL.md",
    "skills/forge-5-loop/SKILL.md",
    "skills/forge-6-docs/SKILL.md",
)

#: The normative sentence the per-call-site mandates restate. Guard 1 checks the
#: restatements; without this, deleting the RULE ITSELF flags zero call sites — the
#: invariant would be gone while its echoes kept the guard green.
EPIC_MANDATE_CLAUSES = (
    "**Epic members MUST pass `--epic`.**",
    "in this file and in every skill body",
)

#: The three clauses of the exit-2 failure protocol. Fragments, not whole sentences, so
#: the guard survives rewording around them but not deletion of the requirement.
FAILURE_PROTOCOL_CLAUSES = (
    "surface the plain `Error:` line from stderr verbatim",
    "do **not** proceed to the next step",
    "do **not** hand-author the JSON as a workaround",
)

#: The operator-facing message prefixes the failure protocol documents. Asserted against
#: the script so the documented exit-2 surface and the emitting code cannot drift apart.
ERROR_MESSAGE_PREFIXES = (
    "no feature directory at",
    "refusing to overwrite it",
    "atomic write to",
)


def _canon_files() -> list[Path]:
    """Every canon file that may contain a `state-*` call site, in a stable order."""
    return sorted(SKILLS.glob("*/SKILL.md")) + [CONVENTIONS]


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


# --------------------------------------------------------------------------------------
# Guard 1 — every call site carries the --epic instruction
# --------------------------------------------------------------------------------------


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


def test_the_epic_mandate_itself_is_still_documented():
    """The normative rule survives, not just its per-call-site echoes.

    Guard 1 walks call sites, so deleting the mandate at its source flags nothing —
    every call site is still covered by its own nearby restatement. This pins the rule.
    """
    body = read(CONVENTIONS)
    absent = [clause for clause in EPIC_MANDATE_CLAUSES if clause not in body]
    assert not absent, (
        "references/shared-conventions.md lost the normative `--epic` mandate — the "
        "per-call-site restatements now have no rule behind them:\n  " + "\n  ".join(absent)
    )


def test_the_epic_guard_is_not_vacuous():
    """A regex that matched nothing would pass the guard above without asserting anything."""
    total = len(_call_sites())
    assert total >= MIN_CALL_SITES, (
        f"only {total} `state-*` call sites found across the skill bodies and "
        f"shared-conventions.md (floor {MIN_CALL_SITES}) — the pattern has almost "
        "certainly stopped matching rather than the call sites having been removed"
    )


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


# --------------------------------------------------------------------------------------
# Guard 2 — the exit-2 failure protocol is still documented, and still matches the script
# --------------------------------------------------------------------------------------


def test_the_verb_failure_protocol_is_still_documented():
    """All three §14 clauses survive in shared-conventions.md."""
    body = read(CONVENTIONS)
    absent = [clause for clause in FAILURE_PROTOCOL_CLAUSES if clause not in body]
    assert not absent, (
        "the `state-*` exit-2 failure protocol lost clauses from "
        "references/shared-conventions.md — an agent may now hand-author state around a "
        "failed verb:\n  " + "\n  ".join(absent)
    )


def test_the_documented_error_messages_still_exist_in_the_script():
    """The operator-facing exit-2 prefixes the protocol describes are still emitted."""
    source = read(SESSION)
    absent = [prefix for prefix in ERROR_MESSAGE_PREFIXES if prefix not in source]
    assert not absent, (
        "scripts/forge-session.py no longer emits documented exit-2 messages — the "
        "failure protocol now describes errors that cannot occur:\n  "
        + "\n  ".join(absent)
    )


# --------------------------------------------------------------------------------------
# Guard 3 — a recorded verify skip is persisted through `state-verify`, never by hand
# --------------------------------------------------------------------------------------


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


def test_every_skip_recording_surface_persists_the_skip_through_state_verify():
    """Each surface that records a `forge-verify-*` skip ships the fence that writes it.

    A skill whose prose says "record the skip" without a scripted call leaves the agent
    to hand-author `stages.forge-verify-*` — the precise drift `state-verify` exists to
    remove, and the way both of V-002's sites regressed.
    """
    missing = []
    for relpath in SKIP_RECORDING_SURFACES:
        path = REPO_ROOT / relpath
        assert path.is_file(), f"{relpath} is listed as a skip-recording surface but is absent"
        if not any(SKIP_STATUS_RE.search(call) for call in _state_verify_call_text(path)):
            missing.append(relpath)
    assert not missing, (
        "these surfaces record a verification skip but ship no "
        "`state-verify --status skipped` invocation, so the skip will be hand-authored:"
        "\n  " + "\n  ".join(missing)
    )


def test_the_skip_guard_is_not_vacuous():
    """A negative control: deleting a fence's `--status skipped` must break Guard 3.

    Without this, a `SKIP_STATUS_RE` that stopped matching — or a
    `_state_verify_call_text` that stopped returning the fenced block the flag lives in
    — would satisfy the guard above by finding nothing to complain about, which is
    indistinguishable from every surface being compliant.
    """
    assert SKIP_RECORDING_SURFACES, "the skip-recording roster is empty"
    probe = REPO_ROOT / SKIP_RECORDING_SURFACES[0]
    calls = _state_verify_call_text(probe)
    assert calls, f"no `state-verify` call parsed out of {SKIP_RECORDING_SURFACES[0]}"
    matched = [call for call in calls if SKIP_STATUS_RE.search(call)]
    assert matched, f"{SKIP_RECORDING_SURFACES[0]} lost its `--status skipped` fence"

    mutated = [SKIP_STATUS_RE.sub("--status passed", call) for call in matched]
    assert not any(SKIP_STATUS_RE.search(call) for call in mutated), (
        "flipping `--status skipped` to `--status passed` left the guard's pattern "
        "matching — Guard 3 cannot detect a fence being repurposed"
    )


# --------------------------------------------------------------------------------------
# Guard 4 — the guard itself
# --------------------------------------------------------------------------------------


def test_this_guard_is_not_skippable():
    """No skip gate may be introduced here — an unskippable guard is the whole point."""
    source = read(Path(__file__).resolve())
    for banned in ("skipif", "importorskip", "pytest.skip"):
        # Only the prose above may mention them; no call may be made.
        assert f"{banned}(" not in source, f"{banned} gate introduced in the drift guard"
