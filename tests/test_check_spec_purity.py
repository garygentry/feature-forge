"""Tests for scripts/check-spec-purity.py (REQ-VER-01/02, REQ-OBS-01, REQ-FM-04).

Drives the checker as a subprocess over clean + impure fixture trees (one fixture
per rule, plus the word-limit / both-limbs body-size cases, both-direction prelude
cases, and the six frontmatter-reader-robustness corners from 00-core-definitions
§4). Mirrors tests/conftest.py conventions (fixture_copy + a subprocess runner).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKER = REPO_ROOT / "scripts" / "check-spec-purity.py"


def _load_checker_module():
    """Import check-spec-purity.py as a module (hyphenated filename -> importlib)."""
    spec = importlib.util.spec_from_file_location("check_spec_purity", CHECKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # so dataclass annotation resolution works
    spec.loader.exec_module(module)
    return module


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


# ── Regression: rules 3 & 5 must scan references/ trees, not just SKILL.md ──
# Guards the CANONICAL_SURFACES glob fix (a bare `/**` matches directories only,
# so the recursive patterns must end `/**/*`). Before the fix these fixtures
# passed — the reference files were silently skipped.


def test_residual_var_in_references_is_caught(fixture_copy):
    root = fixture_copy("bad-residual-var-references")
    result = run_checker(root)
    assert result.returncode != 0
    assert "residual ${CLAUDE_PLUGIN_ROOT}" in result.stdout
    assert "references/leaky.md" in result.stdout


def test_prelude_drift_in_skill_references_is_caught(fixture_copy):
    root = fixture_copy("bad-prelude-drift-references")
    result = run_checker(root)
    assert result.returncode != 0
    assert "byte-identical" in result.stdout
    assert "skills/alpha/references/drift.md" in result.stdout


# ── Regression: the REQ-VND-03 audit inventory is exempt from rule 3 ────────
# vendor-construct-inventory.md documents ${CLAUDE_PLUGIN_ROOT} as prose inside a
# canonical surface; RESIDUAL_VAR_EXEMPT must keep it from tripping rule 3.


def test_inventory_residual_var_is_exempt(fixture_copy):
    root = fixture_copy("exempt-inventory-residual-var")
    result = run_checker(root)
    assert result.returncode == 0, result.stdout


# ── Rule 3 scoping: the prelude first-hint is the ONLY sanctioned use (Chunk 2b) ──
# The bootstrap prelude carries `${CLAUDE_PLUGIN_ROOT:-}`; rule 3 allows it by
# stripping the byte-pinned prelude before scanning. Every OTHER occurrence — bare
# `}` or the default `:-}` form — must still trip, so the `:-}` form is not an
# escape hatch. Driven directly against check_no_residual_var over a tmp tree.


def test_prelude_hint_allowed_but_stray_var_still_caught(tmp_path: Path):
    m = _load_checker_module()

    # (a) a file containing ONLY the sanctioned prelude passes.
    ok = tmp_path / "ok"
    (ok / "references").mkdir(parents=True)
    (ok / "references" / "clean.md").write_text(m.BOOTSTRAP_PRELUDE + "\n")
    assert m.check_no_residual_var(ok) == []

    # (b) a stray default-form `:-}` OUTSIDE the prelude trips (no escape hatch).
    bad_default = tmp_path / "bad_default"
    (bad_default / "references").mkdir(parents=True)
    (bad_default / "references" / "leak.md").write_text(
        "Prose referencing ${CLAUDE_PLUGIN_ROOT:-} outside the prelude.\n"
    )
    assert m.check_no_residual_var(bad_default), "the :-} form must not be an escape hatch"

    # (c) a stray bare `}` form still trips (unchanged behavior).
    bad_bare = tmp_path / "bad_bare"
    (bad_bare / "references").mkdir(parents=True)
    (bad_bare / "references" / "leak.md").write_text("A bare ${CLAUDE_PLUGIN_ROOT} literal.\n")
    assert m.check_no_residual_var(bad_bare)


# ── Determinism: sorted, byte-identical repeated runs (spec 05 §3.4, §7) ────


def test_output_is_deterministic_and_sorted(fixture_copy):
    root = fixture_copy("bad-multi")
    first = run_checker(root)
    second = run_checker(root)
    assert first.returncode == 1
    assert first.stdout == second.stdout  # byte-identical across runs
    violation_lines = [
        line.strip()
        for line in first.stdout.splitlines()
        if line.strip().startswith("skills/")
    ]
    # bad-multi's two violations share rule + reason and differ only by path, so
    # ordering the rendered `path: reason` lines coincides with the production sort
    # key (path, rule.value, reason); the assertion pins the path dimension.
    assert violation_lines == sorted(violation_lines)
    assert len(violation_lines) == 2  # one per skill dir (alpha before zeta)


# ── 3.11 adapters/ exemption (REQ-PUR-01, REQ-PUR-02) ──────────────────────
# The SAME impure SKILL.md (top-level argument-hint + ${CLAUDE_PLUGIN_ROOT}
# residual) is exempt under adapters/ (REQ-PUR-01) but still caught under
# skills/ (REQ-PUR-02), proving the exemption did not weaken enforcement over
# canonical surfaces. Detail: 05-purity-exemption-and-drift-guard.md §1.


def test_adapters_impurity_is_exempt(fixture_copy):
    """Impure content under adapters/ does NOT trip check-spec-purity.py (REQ-PUR-01).

    A SKILL.md placed under adapters/<agent>/skills/ carrying intentional vendor
    frontmatter (e.g. a top-level argument-hint) and a ${CLAUDE_PLUGIN_ROOT}
    residual must be ignored by the checker — adapters/** is exempt.
    """
    root = fixture_copy("adapters-impure-exempt")
    result = run_checker(root)
    assert result.returncode == 0, result.stdout


def test_same_impurity_under_skills_still_fails(fixture_copy):
    """The SAME impurity under skills/ is still caught — exemption did not weaken enforcement (REQ-PUR-02)."""
    root = fixture_copy("adapters-impure-under-skills")
    result = run_checker(root)
    assert result.returncode != 0
    assert "argument-hint" in result.stdout  # canonical surface still enforced


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


def test_loaded_keysets_match_schema():
    """check-spec-purity's loaded ALLOWED/REQUIRED == the schema's properties/required.

    Guards against the checker's key sets drifting from the single declarative
    source of truth (references/skill-frontmatter.schema.json). 00 §3 fixes the
    6 allowed / 2 required keys; this asserts the loader reproduces them exactly.
    """
    schema = json.loads(
        (REPO_ROOT / "references" / "skill-frontmatter.schema.json").read_text("utf-8")
    )
    check_spec_purity = _load_checker_module()
    required, allowed = check_spec_purity._load_frontmatter_key_sets(REPO_ROOT)
    assert allowed == frozenset(schema["properties"].keys())
    assert required == frozenset(schema["required"])
    # Belt-and-suspenders: the exact 00 §3 sets.
    assert allowed == frozenset(
        {"name", "description", "license", "compatibility", "metadata", "allowed-tools"}
    )
    assert required == frozenset({"name", "description"})
