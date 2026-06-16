"""Tests for scripts/check-spec-purity.py (REQ-VER-01/02, REQ-OBS-01, REQ-FM-04).

Drives the checker as a subprocess over clean + impure fixture trees (one fixture
per rule, plus the word-limit / both-limbs body-size cases, both-direction prelude
cases, and the six frontmatter-reader-robustness corners from 00-core-definitions
§4). Mirrors tests/conftest.py conventions (fixture_copy + a subprocess runner).
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

CHECKER = Path(__file__).resolve().parent.parent / "scripts" / "check-spec-purity.py"


def run_checker(root: Path) -> subprocess.CompletedProcess[str]:
    """Run check-spec-purity.py against a fixture tree.

    Args:
        root: A copied skill-tree fixture (clean or impure).

    Returns:
        The completed process (returncode + captured stdout/stderr).
    """
    return subprocess.run(
        [sys.executable, str(CHECKER), "--root", str(root)],
        capture_output=True,
        text=True,
    )


# ── 2.1 Clean canon → exit 0 (REQ-VER-02) ──────────────────────────────────


def test_clean_canon_passes(fixture_copy):
    root = fixture_copy("clean-skills")
    result = run_checker(root)
    assert result.returncode == 0, result.stdout
    assert "0 violation" in result.stdout.lower()


# ── 2.2 One impure fixture per rule → non-zero + reported file/reason ───────


@pytest.mark.parametrize(
    "fixture, token",
    [
        ("bad-disallowed-key", "disallowed frontmatter key 'argument-hint'"),
        ("bad-missing-desc", "missing required frontmatter key 'description'"),
        ("bad-name-mismatch", "!= directory"),
        ("bad-residual-var", "residual ${CLAUDE_PLUGIN_ROOT}"),
        ("bad-oversized-body", "exceeds 300"),
        ("bad-prelude-drift", "byte-identical"),
    ],
)
def test_impure_fixture_fails(fixture_copy, fixture, token):
    root = fixture_copy(fixture)
    result = run_checker(root)
    assert result.returncode != 0
    assert token in result.stdout


# ── Rule 4 — word limit (the other AND-limb) ───────────────────────────────


def test_oversized_words_fails(fixture_copy):
    root = fixture_copy("bad-oversized-words")
    result = run_checker(root)
    assert result.returncode != 0
    assert "words exceeds 5000" in result.stdout


# ── Rule 4 — both limbs at once → two BODY_SIZE violations (body-size=2) ────


def test_oversized_both_emits_two_violations(fixture_copy):
    root = fixture_copy("bad-oversized-both")
    result = run_checker(root)
    assert result.returncode != 0
    assert "lines exceeds 300" in result.stdout
    assert "words exceeds 5000" in result.stdout
    assert "body-size=2" in result.stdout


# ── Rule 5 — both directions: clean passes (above), drift fails (above) ────
# The clean-skills fixture (byte-identical prelude) exercises the passing
# direction in test_clean_canon_passes; bad-prelude-drift covers the failing
# direction in the parametrized impure test. Guards against a no-op comparison.


# ── 2.3 Reader-robustness fixtures (REQ-FM-04) ─────────────────────────────


@pytest.mark.parametrize(
    "fixture, expect_clean",
    [
        ("reader-colon-value", True),
        ("reader-folded-scalar", True),
        ("reader-nested-metadata", True),
        ("reader-blank-lines", True),
        ("reader-crlf", True),
        ("reader-malformed", False),
    ],
)
def test_reader_robustness(fixture_copy, fixture, expect_clean):
    root = fixture_copy(fixture)
    result = run_checker(root)
    if expect_clean:
        assert result.returncode == 0, result.stdout
    else:
        assert result.returncode != 0
        assert "malformed frontmatter block" in result.stdout
