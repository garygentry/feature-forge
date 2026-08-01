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

Both hold today (21 call sites, 0 misses). These guards keep them holding.

Stdlib only, asserting against canon (`skills/`, `references/`, `scripts/`) and never
against generated `adapters/`. No skip gate may be introduced — see
`test_always_loaded_surface.py::test_the_hook_guards_cannot_degrade_to_a_skip`.
"""

from __future__ import annotations

import inspect
import re
from pathlib import Path

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

#: How far around a call site the `--epic` instruction may live. Both bounds are
#: MEASURED against canon, not chosen: the widest real site carries its mandate **10**
#: lines above (in the prose sentence introducing the fence), and the widest site that
#: carries it BELOW carries it **1** line down (inline on the call's own continuation
#: line). 12 is 10 plus 2 lines of margin for a reworded lead-in; 3 is 1 rounded up to
#: `CALL_SPAN`, so the window reaches to the end of the longest fenced call and no
#: further. Neither is deliberately wider: at 20 the lookbehind reached past a block's
#: own mandate into the PRECEDING block's, so deleting the `state-artifact` mandate at
#: `shared-conventions.md:318` left the guard green on the strength of the unrelated
#: `state-enter` mandate 17 lines up. Widening either re-opens that hole — LOOKAHEAD
#: was 8 (7 lines of unmeasured reach below every site) until V-005 measured it.
LOOKBEHIND = 12
LOOKAHEAD = 3

#: How many lines a single fenced `state-*` call may span. The verb sits on the first
#: line and its flags on `\`-continued lines below; 3 covers the longest call in canon
#: (verb + two flag lines) without reaching into a neighbouring invocation.
#:
#: LOAD-BEARING FOR GUARD 1'S WINDOW, not only for call flattening: `LOOKAHEAD` is
#: pinned relative to it (`LOOKAHEAD <= CALL_SPAN`), so widening this to fit a longer
#: fenced call would silently widen how far below a call site Guard 1 will accept an
#: `--epic` mandate. That is why it carries an absolute bound of its own in
#: `test_the_window_is_no_wider_than_the_measured_maximum` — raising it means
#: re-measuring canon, exactly as raising `LOOKBEHIND` does.
CALL_SPAN = 3

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


def _call_sites() -> list[tuple[Path, int, str, list[str]]]:
    """(path, 1-indexed line, verb, window) for every `state-*` call site in canon."""
    sites = []
    for path in _canon_files():
        lines = read(path).splitlines()
        for index, line in enumerate(lines):
            match = CALL_RE.search(line)
            if match:
                window = lines[max(0, index - LOOKBEHIND) : index + LOOKAHEAD]
                sites.append((path, index + 1, match.group(1), window))
    return sites


# --------------------------------------------------------------------------------------
# Guard 1 — every call site carries the --epic instruction
# --------------------------------------------------------------------------------------


def test_every_state_verb_call_site_carries_the_epic_instruction():
    """Zero call sites without a nearby `--epic` mandate (spec 03 §3.6)."""
    missing = [
        f"{path.relative_to(REPO_ROOT).as_posix()}:{line} ({verb})"
        for path, line, verb, window in _call_sites()
        if not any("--epic" in text for text in window)
    ]
    assert not missing, (
        "`state-*` call sites with no `--epic` instruction within "
        f"{LOOKBEHIND} lines above or {LOOKAHEAD} lines below — epic members will "
        "write the wrong feature's state:\n  " + "\n  ".join(missing)
    )


def test_the_window_is_no_wider_than_the_measured_maximum():
    """The lookaround bounds are pinned, because widening them silently guts Guard 1.

    The window is the guard's entire discriminating power: at 20 lines of lookbehind
    it reached past a block's own `--epic` mandate into the PRECEDING block's, so
    deleting the `state-artifact` mandate left Guard 1 green on the strength of an
    unrelated `state-enter` mandate 17 lines up. Nothing else fails when these
    numbers grow — the guard just quietly stops discriminating — so the bound is
    asserted here rather than left to review.

    Both bounds are measured, and the docstring states both measurements rather than
    supplying one and implying the other: 10 lines above and 1 line below at the
    widest real sites. 12/3 adds margin for a reworded lead-in and for the longest
    fenced call (`CALL_SPAN`) respectively. Raising either constant means re-measuring
    canon and re-confirming the buried-mandate hole stays closed, not editing this
    assertion.

    THREE assertions, not two, because the lookahead bound is expressed relative to
    `CALL_SPAN`. The coupling is deliberate — the window should reach to the end of
    the call and no further — but `CALL_SPAN` has an independent job (flattening, at
    the `" ".join` below), so a maintainer who adds a fenced call with three flag
    lines has a legitimate, self-contained reason to raise it, and would silently
    raise the permitted `LOOKAHEAD` with it. Pinning `CALL_SPAN` absolutely keeps
    both halves of the window at the same strength as `LOOKBEHIND`'s.
    """
    assert LOOKBEHIND <= 12, (
        f"LOOKBEHIND widened to {LOOKBEHIND}: the window now reaches past a block's "
        "own `--epic` mandate into its neighbour's, which is how a deleted mandate "
        "once passed Guard 1"
    )
    assert CALL_SPAN <= 3, (
        f"CALL_SPAN widened to {CALL_SPAN}: it is the LOOKAHEAD bound as well as the "
        "flattening span, so widening it widens Guard 1's window past the call's own "
        "fence — re-measure canon first, then raise this bound deliberately"
    )
    assert LOOKAHEAD <= CALL_SPAN, (
        f"LOOKAHEAD widened to {LOOKAHEAD} (> CALL_SPAN={CALL_SPAN}): the window now "
        "reaches past this call's own fence into the NEXT block's mandate — same "
        "buried-mandate failure mode as LOOKBEHIND, in the other direction"
    )


def test_the_failure_message_describes_the_whole_window():
    """Guard 1's message must name both limbs, or it misdirects the reader.

    It described only the lookbehind while the window searched in both directions,
    so a maintainer chasing a failure would look 12 lines up, find nothing relevant,
    and never think to look below the call.
    """
    guard_src = inspect.getsource(test_every_state_verb_call_site_carries_the_epic_instruction)
    assert "lines above or " in guard_src and "lines below" in guard_src, (
        "Guard 1's failure message no longer describes both limbs of the window"
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
    """Each `state-verify` invocation in `path`, as one flattened string per call.

    A fenced call spans a `\\`-continued line pair, so the flag being looked for sits on
    a different line from the verb. Joining the verb's line with the lines that follow it
    lets a single `--status skipped` search see the whole invocation.
    """
    lines = read(path).splitlines()
    calls = []
    for index, line in enumerate(lines):
        match = CALL_RE.search(line)
        if match and match.group(1) == "state-verify":
            calls.append(" ".join(lines[index : index + CALL_SPAN]))
    return calls


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

    Without this, a `SKIP_STATUS_RE` that stopped matching — or a `_state_verify_call_text`
    span too short to reach the flag — would satisfy the guard above by finding nothing to
    complain about, which is indistinguishable from every surface being compliant.
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
