"""Tests for eval/run-eval.py — the advisory no-key contract (REQ-EVAL-02, REQ-SEC-02).

The eval harness is advisory: with no ANTHROPIC_API_KEY it must print a clear skip
and exit 0 (never a failure, never an API call). The eval CI job runs only on
dispatch/weekly (never on PR), so without this test the no-key/exit-0 contract and
the --json EvalReport shape would have no PR-gated coverage. Both cases below are
key-absent, so they make no network call. Mirrors tests/conftest.py conventions
(subprocess runner, REPO_ROOT).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HARNESS = REPO_ROOT / "eval" / "run-eval.py"

# Must match the pinned model in run-eval.py (MODEL constant, OQ-D).
PINNED_MODEL = "claude-haiku-4-5-20251001"


def _run_no_key(*args: str) -> subprocess.CompletedProcess[str]:
    """Run run-eval.py with ANTHROPIC_API_KEY stripped from the environment."""
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    return subprocess.run(
        [sys.executable, str(HARNESS), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(REPO_ROOT),
    )


def test_no_key_human_path_skips_and_exits_zero() -> None:
    """No key, human output: exit 0 and a clear "skipped (no key)" message."""
    proc = _run_no_key()
    assert proc.returncode == 0, proc.stderr
    assert "skipped (no key)" in proc.stdout


def test_no_key_json_path_emits_skipped_report() -> None:
    """No key, --json: a valid EvalReport with skipped=True, accuracy 0.0, pinned model."""
    proc = _run_no_key("--json")
    assert proc.returncode == 0, proc.stderr
    report = json.loads(proc.stdout)
    assert report["skipped"] is True
    assert report["accuracy"] == 0.0
    assert report["model"] == PINNED_MODEL
