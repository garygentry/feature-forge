"""Guard: `bash scripts/validate.sh` cannot silently take its pytest-less branch.

`scripts/validate.sh` runs the suite only when `python3 -c "import pytest"` succeeds. If
it does not, the gate prints `SKIP: pytest not installed …` and continues **green**. That
degradation is deliberate and stays non-fatal, but it used to be invisible in the one
place it mattered: roughly a third of every backlog item's acceptance criteria were
phrased as *"validate.sh shows PASS …; if it shows SKIP, `python3 -m pytest tests -q` was
run explicitly and passed."* The second clause leaves no trace on disk, so a reviewer
could not tell "the suite ran green" from "the suite was skipped and the fallback quietly
was not run" — and in a CI image without pytest, those criteria are vacuously satisfiable.

The acceptance-criteria template has since been narrowed to the artifact-level assertion
alone (`output shows "PASS: epic-manifest pytest suite"`). This module is the other half:
it pins that the PASS branch is actually reachable here, and that the SKIP branch stays
distinguishable and counted rather than blending into a green run.

Stdlib only, so it runs under a bare `python3 -m pytest tests`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from _forge_paths import REPO_ROOT, read

VALIDATE = REPO_ROOT / "scripts" / "validate.sh"

#: The line the tightened acceptance criteria assert on.
PASS_LINE = "PASS: epic-manifest pytest suite"

#: The degraded line, and the counter that keeps it visible in the gate's summary.
SKIP_PREFIX = "SKIP: pytest not installed"
WARNING_COUNTER = "WARNINGS=$((WARNINGS + 1))"


def test_pytest_is_importable_so_the_gate_takes_its_pass_branch():
    """The environment running this suite can also satisfy `validate.sh`'s import probe.

    `validate.sh` gates on `python3 -c "import pytest"`; `find_spec` is the same
    resolution. If this ever fails, the gate has been running its non-fatal SKIP branch
    and every acceptance criterion that reads "output shows PASS" was never actually
    demonstrated.
    """
    assert importlib.util.find_spec("pytest") is not None, (
        "pytest is not importable, so `bash scripts/validate.sh` takes its non-fatal "
        f"{SKIP_PREFIX!r} branch and never prints {PASS_LINE!r} — the gate is green "
        "without having run the suite"
    )


def test_the_gate_still_has_both_branches_and_keeps_the_skip_visible():
    """The PASS line exists, and the SKIP branch is counted rather than silent.

    Asserted against the script's text because the point is what a *reader of the gate's
    output* can conclude. A SKIP that did not bump `WARNINGS` would be indistinguishable
    from a clean run in the summary line, which is exactly the ambiguity the acceptance
    criteria were rewritten to remove.
    """
    body = read(VALIDATE)
    assert PASS_LINE in body, (
        f"scripts/validate.sh no longer prints {PASS_LINE!r} — the acceptance criteria "
        "that assert on it can no longer be satisfied by any run"
    )
    assert SKIP_PREFIX in body, (
        "the pytest-less branch is gone; if that was intentional, this guard and the "
        "acceptance-criteria wording both need updating"
    )

    skip_index = body.index(SKIP_PREFIX)
    tail = body[skip_index : skip_index + 400]
    assert WARNING_COUNTER in tail, (
        "the SKIP branch no longer increments WARNINGS, so a skipped suite now reads as "
        "a clean gate run in the summary"
    )


def test_this_guard_is_not_skippable():
    """No skip gate may be introduced here — an unskippable guard is the whole point."""
    source = read(Path(__file__).resolve())
    for banned in ("skipif", "importorskip", "pytest.skip"):
        # Only the prose above may mention them; no call may be made.
        assert f"{banned}(" not in source, f"{banned} gate introduced in the drift guard"
