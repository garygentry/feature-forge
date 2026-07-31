"""Tests for ``forge-session.py rank-features`` recency sorting.

Regression coverage for issue #64: a specs tree mixing pipeline states that
have an ``updatedAt`` timestamp with ones that omit it must not crash with
``TypeError: can't compare offset-naive and offset-aware datetimes``.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER = REPO_ROOT / "scripts" / "forge-session.py"


def _write_state(specs_dir: Path, name: str, state: dict) -> None:
    feature = specs_dir / name
    feature.mkdir(parents=True, exist_ok=True)
    (feature / ".pipeline-state.json").write_text(json.dumps(state))


def _rank(specs_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HELPER), "rank-features",
         "--specs-dir", str(specs_dir), "--json"],
        capture_output=True,
        text=True,
    )


def test_mixed_updatedat_does_not_crash(tmp_path: Path) -> None:
    """A tree mixing aware-timestamp and missing-timestamp states sorts cleanly.

    The aware-timestamp feature must rank ahead of the timestamp-less one,
    which sorts last (issue #64).
    """
    specs = tmp_path / "specs"
    _write_state(specs, "a", {"updatedAt": "2026-06-26T00:00:00Z",
                              "pipelineStatus": "active"})
    _write_state(specs, "b", {"pipelineStatus": "active"})  # no updatedAt

    result = _rank(specs)

    assert result.returncode == 0, result.stderr
    active = json.loads(result.stdout)["active"]
    assert [row["name"] for row in active] == ["a", "b"]


def _auto_pending_state(scheduled: int = 1, version: int = 1) -> dict:
    """A completed PRD whose automatic verification was scheduled and never ran."""
    return {
        "pipelineStatus": "active",
        "updatedAt": "2026-07-30T00:00:00Z",
        "stages": {
            "forge-1-prd": {"status": "complete", "version": version},
            "forge-verify-prd": {
                "status": "auto-verify-pending",
                "scheduledAt": "2026-07-30T00:00:00Z",
                "scheduledStageVersion": scheduled,
                # Commit 1 of the two-commit protocol records no hash yet.
                "commitHash": None,
            },
        },
    }


def test_rank_table_calls_owed_auto_verification_an_obligation(tmp_path: Path) -> None:
    """The human table must not offer owed debt as an optional extra.

    ``(verify available: …)`` reads as a suggestion; recorded auto-verify debt is
    owed work (REQ-DEBT-02). The full 03 §5.3 sentence rides on stderr.
    """
    specs = tmp_path / "specs"
    _write_state(specs, "widget", _auto_pending_state())

    result = subprocess.run(
        [sys.executable, str(HELPER), "rank-features", "--specs-dir", str(specs)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert result.returncode == 0, result.stderr
    assert "(automatic verification owed: /feature-forge:forge-verify widget)" in result.stdout
    assert "verify available" not in result.stdout
    assert (
        "widget: automatic verification is still pending for forge-1-prd; "
        "run /feature-forge:forge-verify widget to resolve it." in result.stderr
    )


def test_rank_table_still_offers_an_ordinary_pending_verify(tmp_path: Path) -> None:
    """A never-verified stage keeps the pre-existing wording — no relabelling."""
    specs = tmp_path / "specs"
    _write_state(specs, "widget", {
        "pipelineStatus": "active",
        "stages": {"forge-1-prd": {"status": "complete", "version": 1}},
    })

    result = subprocess.run(
        [sys.executable, str(HELPER), "rank-features", "--specs-dir", str(specs)],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert result.returncode == 0, result.stderr
    assert "(verify available: /feature-forge:forge-verify widget)" in result.stdout
    assert "still pending" not in result.stderr


def test_naive_timestamp_is_normalized(tmp_path: Path) -> None:
    """A timestamp with no ``Z``/offset is coerced to UTC, not left naive."""
    specs = tmp_path / "specs"
    _write_state(specs, "newer", {"updatedAt": "2026-06-27T00:00:00Z",
                                  "pipelineStatus": "active"})
    _write_state(specs, "older", {"updatedAt": "2026-06-25T00:00:00",  # naive
                                  "pipelineStatus": "active"})

    result = _rank(specs)

    assert result.returncode == 0, result.stderr
    active = json.loads(result.stdout)["active"]
    assert [row["name"] for row in active] == ["newer", "older"]
