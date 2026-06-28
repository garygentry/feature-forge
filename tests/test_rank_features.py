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
