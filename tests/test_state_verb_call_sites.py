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

import re
from pathlib import Path

from _forge_paths import REFERENCES, REPO_ROOT, SCRIPTS, SKILLS, read

CONVENTIONS = REFERENCES / "shared-conventions.md"
SESSION = SCRIPTS / "forge-session.py"

#: A `state-*` verb invocation in a bash fence, e.g. `forge-session.py" state-complete \`.
CALL_RE = re.compile(r'forge-session\.py"?\s+(state-[a-z]+)')

#: Non-vacuity floor, NOT a pinned total. A regex that stopped matching would satisfy the
#: "every call site carries --epic" assertion trivially. 21 sites today (2026-07-29);
#: the floor is the count, since a call site being REMOVED is itself worth a look.
MIN_CALL_SITES = 21

#: How far above a call site the `--epic` instruction may live. Every site today carries
#: it within 10 lines (it sits in the prose sentence introducing the fence, or inline in
#: the call itself); 20 is headroom for a reworded lead-in, not a licence to rely on a
#: neighbouring fence's instruction.
LOOKBEHIND = 20
LOOKAHEAD = 8

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
        f"{LOOKBEHIND} lines above — epic members will write the wrong feature's "
        "state:\n  " + "\n  ".join(missing)
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
# Guard 3 — the guard itself
# --------------------------------------------------------------------------------------


def test_this_guard_is_not_skippable():
    """No skip gate may be introduced here — an unskippable guard is the whole point."""
    source = read(Path(__file__).resolve())
    for banned in ("skipif", "importorskip", "pytest.skip"):
        # Only the prose above may mention them; no call may be made.
        assert f"{banned}(" not in source, f"{banned} gate introduced in the drift guard"
