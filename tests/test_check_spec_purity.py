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


# ── Rule 6: a shell fence using $R must bind it in-fence (finding V-002) ───
# Rule 5 pins a prelude that EXISTS; it is structurally blind to a MISSING one.
# `$R` does not survive across fences — each is its own process — so an unbound
# `$R` expands to empty and the command silently runs against `/`. That is how the
# specs-hygiene CLAUDE.md copy was dead from 2026-06-19 with every rule green.
# Driven directly against check_prelude_presence over a tmp tree.


def test_shell_fence_using_root_without_a_prelude_is_caught(tmp_path: Path):
    m = _load_checker_module()

    def _tree(name: str, body: str) -> Path:
        root = tmp_path / name
        (root / "references").mkdir(parents=True)
        (root / "references" / "hygiene.md").write_text(body)
        return root

    fence = '[ -f "x" ] || cp "$R/references/templates/t.md" "x"'

    # (a) a shell fence that binds $R in-fence passes.
    ok = _tree("ok", f"```bash\n{m.BOOTSTRAP_PRELUDE}\n{fence}\n```\n")
    assert m.check_prelude_presence(ok) == []

    # (b) the same fence WITHOUT the prelude trips — the V-002 shape exactly.
    bad = _tree("bad", f"```bash\n{fence}\n```\n")
    violations = m.check_prelude_presence(bad)
    assert violations, "an unbound $R in a shell fence must trip rule 6"
    assert violations[0].rule is m.Rule.PRELUDE_PRESENCE

    # (c) a PRECEDING fence's assignment does not carry over — that is the bug.
    split = _tree(
        "split",
        f"```bash\n{m.BOOTSTRAP_PRELUDE}\nmkdir -p x\n```\n\nProse.\n\n```bash\n{fence}\n```\n",
    )
    assert m.check_prelude_presence(split), "$R must not be treated as crossing fences"

    # (d) a non-shell fence may name $R narratively (forge-bootstrap's step list).
    prose = _tree("prose", "```\n1. Portable-root prelude → locate $R\n```\n")
    assert m.check_prelude_presence(prose) == []

    # (e) the braced form `${R}` is the same bug and must not be an escape hatch.
    braced = _tree("braced", '```bash\ncp "${R}/references/templates/t.md" "x"\n```\n')
    assert m.check_prelude_presence(braced), "${R} must not evade rule 6"

    # (f) `$ROOT` is a different variable — word boundary keeps it out.
    other = _tree("other", '```bash\ncp "$ROOT/t.md" "x"\n```\n')
    assert m.check_prelude_presence(other) == []

    # (g) an info string with attributes must still be recognised as an OPENER. If it
    # is not, its closing ``` is read as an opener, fence parity inverts, and every
    # later fence in the file silently stops being checked.
    attributed = _tree(
        "attributed",
        f'```bash title="setup"\nmkdir -p x\n```\n\nProse.\n\n```bash\n{fence}\n```\n',
    )
    assert m.check_prelude_presence(attributed), "fence parity must survive info strings"


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


# ── Rule 7: the shipped-artifact self-containment ratchet (finding V-009) ──
# Default-deny over scripts/, references/, skills/, eval/, with existing debt
# grandfathered by exact path. The property that matters is the RATCHET one: a
# file that is clean today cannot regress, and a new file starts locked. That is
# what the blanket rule (unlandable) and a flat allowlist (no enforcement) each
# fail to give. Driven directly against check_no_spec_citations over a tmp tree.


def _citation_tree(tmp_path: Path, name: str, rel: str, body: str) -> Path:
    root = tmp_path / name
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(body, encoding="utf-8")
    return root


@pytest.mark.parametrize(
    "citation",
    [
        "see 03-verification-state.md for the matrix",  # full spec filename
        "per 03 §5.1 the entry is cleared",  # bare numeric shorthand
        "per `02` §3.1 step 5, owners are direct",  # BACKTICKED — the N-3 spelling
        "the tech-spec §3.4 rules govern this",  # tech-spec coordinate
    ],
)
def test_each_citation_form_trips_the_ratchet(tmp_path: Path, citation: str):
    """All four leaked citation forms trip, including the backticked one.

    The backticked case is the regression that matters: the round-1 cleanup
    measured itself with the same space-requiring pattern that produced it, so
    six ``\\`02\\` §3.1``-style coordinates re-entered an already-cleaned file
    invisibly. A pattern that cannot see that spelling is not a gate.
    """
    m = _load_checker_module()
    root = _citation_tree(tmp_path, "bad", "scripts/helper.py", f"# {citation}\n")
    violations = m.check_no_spec_citations(root)
    assert violations, f"citation form must trip rule 7: {citation}"
    assert violations[0].rule is m.Rule.SELF_CONTAINMENT
    assert violations[0].path == "scripts/helper.py"


def test_new_file_starts_locked_but_grandfathered_file_is_exempt(tmp_path: Path):
    m = _load_checker_module()
    citation = "# see 04-pipeline-integration.md\n"

    # (a) A file NOT on the grandfather list is locked from birth.
    new = _citation_tree(tmp_path, "new", "scripts/brand-new.py", citation)
    assert m.check_no_spec_citations(new), "a new shipped file must start locked"

    # (b) A grandfathered path carries its documented debt without failing.
    old = _citation_tree(
        tmp_path, "old", m.CITATION_GRANDFATHERED[0], citation
    )
    assert m.check_no_spec_citations(old) == []


def test_bare_section_reference_is_not_a_citation(tmp_path: Path):
    """An intra-file ``§`` points at something that ships — it must not trip.

    Rule 7 targets pointers into the specs tree, which is archived once the
    feature ships. A bare section mark with no document coordinate is not one,
    and flagging it would make the rule unlandable for the wrong reason.
    """
    m = _load_checker_module()
    root = _citation_tree(tmp_path, "ok", "scripts/helper.py", "# see §7 above\n")
    assert m.check_no_spec_citations(root) == []


def test_the_ratchet_would_have_caught_the_n3_leak():
    """The six coordinates that re-entered forge-session.py go red under rule 7.

    Verified against the real file at the commit that carried them, so the claim
    is measured rather than asserted. The current worktree copy is clean, and
    ``scripts/forge-session.py`` is deliberately NOT grandfathered — that pairing
    is the whole point of the ratchet.
    """
    m = _load_checker_module()
    assert "scripts/forge-session.py" not in m.CITATION_GRANDFATHERED
    leaked = subprocess.run(
        ["git", "show", "99e63e6:scripts/forge-session.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if leaked.returncode != 0:
        pytest.skip("pre-fix revision unavailable (shallow clone)")
    assert len(m._SPEC_CITATION_RE.findall(leaked.stdout)) == 6


def test_grandfather_list_is_sorted_deduped_and_shrinking_only():
    """The allowlist is debt, so it must stay auditable — and every entry must exist.

    A stale entry silently un-locks nothing, but it hides that the file was
    cleaned or renamed; catching it here is what makes "delete the line" the
    natural maintenance action and keeps the list shrinking.
    """
    m = _load_checker_module()
    entries = list(m.CITATION_GRANDFATHERED)
    assert entries == sorted(entries), "keep the grandfather list sorted"
    assert len(entries) == len(set(entries)), "duplicate grandfather entries"
    for rel in entries:
        path = REPO_ROOT / rel
        assert path.is_file(), f"grandfathered path no longer exists: {rel}"
        text = path.read_text(encoding="utf-8", errors="replace")
        assert m._SPEC_CITATION_RE.search(text), (
            f"{rel} is now clean — delete its CITATION_GRANDFATHERED entry"
        )


def test_repo_itself_is_clean_under_rule_7():
    m = _load_checker_module()
    assert m.check_no_spec_citations(REPO_ROOT) == []


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
