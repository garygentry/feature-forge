"""Guard: `bash scripts/validate.sh` cannot silently take its pytest-less branch.

`scripts/validate.sh` used to run the suite only when `python3 -c "import pytest"`
succeeded; otherwise it printed `SKIP: pytest not installed …` and continued **green**. That
degradation used to be invisible in the one place it mattered: roughly a third of every
backlog item's acceptance criteria were phrased as *"validate.sh shows PASS …; if it shows
SKIP, `python3 -m pytest tests -q` was run explicitly and passed."* The second clause leaves
no trace on disk, so a reviewer could not tell "the suite ran green" from "the suite was
skipped and the fallback quietly was not run" — and in a CI image without pytest, those
criteria are vacuously satisfiable.

The acceptance-criteria template has since been narrowed to the artifact-level assertion
alone (`output shows "PASS: epic-manifest pytest suite"`). Since #336 the gate no longer
depends on the ambient `python3` at all: it provisions a pinned `.venv-test` (pytest +
jsonschema + the YAML pin) and runs the suite there, and a provisioning failure is a counted
FAIL, not a skip. This module pins that the PASS branch is reachable, and that no pytest-less
branch can blend into a green run.

Stdlib only, so it runs under a bare `python3 -m pytest tests`.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

from _forge_paths import REPO_ROOT, read

VALIDATE = REPO_ROOT / "scripts" / "validate.sh"

#: The line the tightened acceptance criteria assert on.
PASS_LINE = "PASS: epic-manifest pytest suite"

#: The retired degraded line (#336) — it must not come back.
SKIP_PREFIX = "SKIP: pytest not installed"

#: The provisioning-failure line, and the counter that makes it fail the gate.
PROVISION_FAIL = "FAIL: could not provision .venv-test"
ERROR_COUNTER = "ERRORS=$((ERRORS + 1))"


def test_pytest_is_importable_so_the_gate_takes_its_pass_branch():
    """The environment running this suite can also satisfy `validate.sh`'s import probe.

    Trivially true when running at all, but kept as a canary: `find_spec` failing here
    would mean the suite was collected by something other than pytest.
    """
    assert importlib.util.find_spec("pytest") is not None, (
        f"pytest is not importable, so `bash scripts/validate.sh` cannot print {PASS_LINE!r}"
    )


def test_the_gate_has_a_pass_line_and_no_silent_pytest_less_branch():
    """The PASS line exists, the SKIP branch is gone, and a provisioning fault FAILS.

    Asserted against the script's text because the point is what a *reader of the gate's
    output* can conclude. A pytest-less run that did not bump `ERRORS` would read as a
    clean gate run, which is exactly the ambiguity the acceptance criteria were rewritten
    to remove.
    """
    body = read(VALIDATE)
    assert PASS_LINE in body, (
        f"scripts/validate.sh no longer prints {PASS_LINE!r} — the acceptance criteria "
        "that assert on it can no longer be satisfied by any run"
    )
    assert SKIP_PREFIX not in body, (
        "the non-fatal pytest-less SKIP branch is back; the suite must run in the "
        "provisioned .venv-test or fail (#336)"
    )
    assert PROVISION_FAIL in body, "validate.sh lost its .venv-test provisioning-failure branch"

    fail_index = body.index(PROVISION_FAIL)
    tail = body[fail_index : fail_index + 400]
    assert ERROR_COUNTER in tail, (
        "the provisioning-failure branch no longer increments ERRORS, so an un-run suite "
        "now reads as a clean gate run"
    )


def test_this_guard_is_not_skippable():
    """No skip gate may be introduced here — an unskippable guard is the whole point."""
    source = read(Path(__file__).resolve())
    for banned in ("skipif", "importorskip", "pytest.skip"):
        # Only the prose above may mention them; no call may be made.
        assert f"{banned}(" not in source, f"{banned} gate introduced in the drift guard"
