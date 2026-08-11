"""Pytest suite for the corrected-claim sweep helper (``scripts/fix-sweep.py``).

Covers the two subcommands' behavior end-to-end over scratch git repositories in
``tmp_path``: needle extraction from the fix delta, the normalization and floor
contracts, corpus boundaries, the skip-vs-failure classification, plan-coverage
cardinality, output formats, determinism, and the cost model's shape.

The final section holds the prose guards over ``skills/forge-fix/SKILL.md``, the
verification checklists, and ``skills/forge-verify/SKILL.md`` — the literals that make
this feature's integration load-bearing.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "scripts" / "fix-sweep.py"
FORGE_FIX_SKILL = REPO_ROOT / "skills" / "forge-fix" / "SKILL.md"
VERIFY_SKILL = REPO_ROOT / "skills" / "forge-verify" / "SKILL.md"
CHECKLISTS = REPO_ROOT / "skills" / "forge-verify" / "references" / "verification-checklists"

#: The motivating false claim (PRD Success Criteria). Normalizes well above the floor.
CLAIM = "Object storage lifecycle policies are universal among the tracked hyperscalers."

#: The correction written over CLAIM by the simulated fix pass. Shares no normalized
#: substring with CLAIM, so reflow suppression never fires on these fixtures.
CORRECTED = "Only two of the four tracked providers offer that behavior."

#: The same claim re-wrapped across three lines — the whitespace-reflowed variant the
#: normalized-blob model must still match.
REFLOWED_FILE = (
    "# Summary\n"
    "\n"
    "Object storage lifecycle\n"
    "policies are universal\n"
    "among the tracked hyperscalers.\n"
)

#: The fixed human hit-line format that forge-fix prose reads (02 §2.3).
HIT_LINE_RE = re.compile(
    r'^  (?P<file>\S+):(?P<line>\d+): survivor of "(?P<needle>.*)" '
    r"\(removed at (?P<source_file>\S+):(?P<source_line>\d+)\)$"
)


# --------------------------------------------------------------------------- #
# Module loading and scratch-repo helpers (05 §1)
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="module")
def fix_sweep() -> ModuleType:
    """Load ``scripts/fix-sweep.py`` as a module for in-process unit tests.

    The filename contains a hyphen, so it is loaded via importlib rather than a
    normal import (05 §1).
    """
    spec = importlib.util.spec_from_file_location("fix_sweep", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command in ``repo`` and return the completed process."""
    return subprocess.run(
        ["git", *args], cwd=str(repo), capture_output=True, text=True
    )


def _set_git_identity(repo: Path) -> None:
    """Configure a local git identity so ``git commit`` succeeds in the test repo."""
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")


def _init_repo(repo: Path) -> Path:
    """Create ``repo`` as a fresh git repository with a local identity."""
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q")
    _set_git_identity(repo)
    return repo


def _write(repo: Path, relpath: str, content: str) -> Path:
    """Write ``content`` to ``relpath`` under ``repo``, creating parent directories."""
    target = repo / relpath
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return target


def _commit_all(repo: Path, message: str = "baseline") -> None:
    """Stage and commit the whole working tree — the sweepable baseline (00 §3)."""
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", message)


def _prd_text(sentence: str, *, appendix: str | None = None) -> str:
    """Render the canonical scratch PRD with ``sentence`` on line 5.

    A fixed layout keeps every fixture's needle provenance predictable:
    ``specs/x/PRD.md:5``. An ``appendix`` sentence, when given, lands on line 13.
    """
    lines = [
        "# PRD x",
        "",
        "## Context",
        "",
        sentence,
        "",
        "## Notes",
        "",
        "Nothing else here.",
    ]
    if appendix is not None:
        lines += ["", "## Appendix", "", appendix]
    return "\n".join(lines) + "\n"


def _fix_repo(
    repo: Path,
    files: dict[str, str],
    *,
    claim: str = CLAIM,
    corrected: str = CORRECTED,
    appendix: str | None = None,
    fixed_appendix: str | None = None,
) -> Path:
    """Build a scratch repo whose working tree carries one corrective edit.

    The committed baseline is ``specs/x/PRD.md`` carrying ``claim`` on line 5 plus
    ``files``; the working-tree "fix" rewrites line 5 to ``corrected`` and commits
    nothing, which is exactly the pre-commit state forge-fix Step 4 sweeps (00 §3).
    """
    _init_repo(repo)
    _write(repo, "specs/x/PRD.md", _prd_text(claim, appendix=appendix))
    for relpath, content in files.items():
        _write(repo, relpath, content)
    _commit_all(repo)
    _write(
        repo,
        "specs/x/PRD.md",
        _prd_text(corrected, appendix=fixed_appendix if fixed_appendix else appendix),
    )
    return repo


def _run_cli(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """Invoke ``fix-sweep.py`` as a subprocess — the surface skills actually call."""
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def _sweep_json(repo: Path, *args: str) -> tuple[int, dict]:
    """Run ``sweep --json`` in ``repo`` and return (exit code, parsed payload)."""
    proc = _run_cli(repo, "sweep", "--json", *args)
    return proc.returncode, json.loads(proc.stdout)


def _needle(module: ModuleType, file: str, line: int, text: str) -> dict:
    """Build one raw Needle the way ``extract_needles`` would (00 §4.1)."""
    return {
        "file": file,
        "line": line,
        "normalized": module.normalize(text),
        "original": text,
    }


@pytest.fixture()
def scratch_repo(tmp_path: Path) -> Path:
    """A git repo with an initial commit — the minimal sweepable baseline.

    Layout after setup: one committed artifact file. Tests then edit the working
    tree (creating the fix delta vs HEAD, per 00 §3) and run the sweep pre-commit,
    exactly as forge-fix Step 4 does.
    """
    repo = _init_repo(tmp_path / "repo")
    _write(repo, "specs/x/PRD.md", _prd_text(CLAIM))
    _commit_all(repo)
    return repo


# --------------------------------------------------------------------------- #
# §2.1 Module foundation — constants and the one exception type (00 §4.3/§5.2/§10)
# --------------------------------------------------------------------------- #


def test_script_exists_and_is_executable() -> None:
    """The sweep ships as an executable standalone script (02 §1)."""
    assert SCRIPT.is_file()
    assert SCRIPT.stat().st_mode & 0o111
    assert SCRIPT.read_text(encoding="utf-8").startswith("#!/usr/bin/env python3")


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("MIN_NEEDLE_CHARS", 24),
        ("VERIFICATION_SEGMENT", ".verification"),
        ("DRIFT_GATED_PREFIX", "adapters/"),
        ("DRIFT_GATE_SENTINEL", "scripts/build-adapters.py"),
        ("VERIFICATION_EXCLUDE_LABEL", ".verification/"),
        ("GIT_UNAVAILABLE", -1),
    ],
)
def test_shared_vocabulary_constants_carry_canonical_values(
    fix_sweep: ModuleType, name: str, expected: object
) -> None:
    """The constants carried from the shared vocabulary keep their canonical values."""
    assert getattr(fix_sweep, name) == expected


def test_git_timeout_constant_is_a_positive_bound(fix_sweep: ModuleType) -> None:
    """Every git subprocess is wall-clock bounded so a hung git fails, never hangs."""
    assert isinstance(fix_sweep.GIT_TIMEOUT_SECONDS, int)
    assert fix_sweep.GIT_TIMEOUT_SECONDS > 0


def test_usage_error_is_the_single_exception_type(fix_sweep: ModuleType) -> None:
    """``UsageError`` is defined and is the exit-2 carrier (00 §10)."""
    assert issubclass(fix_sweep.UsageError, Exception)


def test_usage_error_maps_to_exit_two(scratch_repo: Path) -> None:
    """A rejected flag surfaces as exit 2 with an ``Error:`` line and empty stdout."""
    proc = _run_cli(scratch_repo, "sweep", "--min-chars", "0")
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr.startswith("Error:")


# --------------------------------------------------------------------------- #
# §2.2 F-5 regression fixture — the headline test (PRD Success Criteria)
# --------------------------------------------------------------------------- #


def _build_f5_repo(repo: Path, *, self_copy: bool = False) -> Path:
    """Reproduce the F-5 incident: one claim corrected in one artifact, copies left.

    Committed baseline carries the claim in a sibling spec, a whitespace-reflowed
    variant, an un-gated generated file, an audit record under ``.verification/``,
    and a drift-gated ``adapters/`` copy whose gate sentinel is present.
    """
    files = {
        "specs/other/PRD.md": f"# PRD other\n\n{CLAIM}\n",
        "docs/summary.md": REFLOWED_FILE,
        "src/generated/foo.ts": f'// {CLAIM}\nexport const NOTE = "x";\n',
        "specs/x/.verification/VERIFY-impl-2026-01-01.md": (
            f"# Verification — impl\n\nCorrected claim, quoted as evidence: {CLAIM}\n"
        ),
        "adapters/claude/skills/x.md": f"# x\n\n{CLAIM}\n",
        "scripts/build-adapters.py": '#!/usr/bin/env python3\nprint("gate sentinel")\n',
    }
    return _fix_repo(
        repo,
        files,
        appendix=CLAIM if self_copy else None,
    )


def test_f5_reports_every_surviving_copy_outside_the_excluded_trees(
    tmp_path: Path,
) -> None:
    """A claim corrected in one artifact is reported wherever else it survives."""
    repo = _build_f5_repo(tmp_path / "repo")
    code, payload = _sweep_json(repo)

    assert code == 1
    assert payload["skipped"] is False
    assert payload["baseline"] == "HEAD"
    assert [(hit["file"], hit["line"]) for hit in payload["hits"]] == [
        ("docs/summary.md", 3),
        ("specs/other/PRD.md", 3),
        ("src/generated/foo.ts", 1),
    ]
    for hit in payload["hits"]:
        assert hit["needle"] == CLAIM
        assert hit["sourceFile"] == "specs/x/PRD.md"
        assert hit["sourceLine"] == 5


def test_f5_leaves_the_audit_record_and_the_gated_tree_silent(tmp_path: Path) -> None:
    """Findings documents and a gated regenerated tree are out of corpus (00 §5.2)."""
    repo = _build_f5_repo(tmp_path / "repo")
    _code, payload = _sweep_json(repo)

    hit_files = {hit["file"] for hit in payload["hits"]}
    assert not any(path.startswith("adapters/") for path in hit_files)
    assert not any(".verification/" in path for path in hit_files)
    assert payload["excludes"] == [".verification/", "adapters/"]


def test_f5_hits_are_sorted_by_file_then_line(tmp_path: Path) -> None:
    """Hit ordering is total, so two runs and two readers agree (02 §4.6)."""
    repo = _build_f5_repo(tmp_path / "repo")
    _code, payload = _sweep_json(repo)
    keys = [(hit["file"], hit["line"]) for hit in payload["hits"]]
    assert keys == sorted(keys)


def test_f5_needle_provenance_and_filter_counters(tmp_path: Path) -> None:
    """One needle is extracted from the corrective edit, dropped by neither filter."""
    repo = _build_f5_repo(tmp_path / "repo")
    _code, payload = _sweep_json(repo)

    assert [(n["file"], n["line"], n["original"]) for n in payload["needles"]] == [
        ("specs/x/PRD.md", 5, CLAIM)
    ]
    assert payload["droppedNeedles"] == {"belowFloor": 0, "reflowSuppressed": 0}
    assert payload["filesScanned"] == 5


def test_f5_self_file_survivor_is_reported(tmp_path: Path) -> None:
    """A duplicate left below the corrected site is the self-contradiction hit."""
    repo = _build_f5_repo(tmp_path / "repo", self_copy=True)
    code, payload = _sweep_json(repo)

    assert code == 1
    self_hits = [hit for hit in payload["hits"] if hit["file"] == "specs/x/PRD.md"]
    assert [hit["line"] for hit in self_hits] == [13]
    assert self_hits[0]["sourceFile"] == "specs/x/PRD.md"
    assert self_hits[0]["sourceLine"] == 5


def test_a_clean_fix_reports_no_survivors(tmp_path: Path) -> None:
    """Correcting the only occurrence closes the sweep clean at exit 0."""
    repo = _fix_repo(tmp_path / "repo", {"docs/other.md": "# Other\n\nUnrelated.\n"})
    code, payload = _sweep_json(repo)

    assert code == 0
    assert payload["hits"] == []
    assert payload["skipped"] is False


# --------------------------------------------------------------------------- #
# §2.3 Normalization and threshold units (REQ-SWEEP-02)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "variant",
    [
        "Universal among the tracked hyperscalers.",
        "universal, among   the\ntracked  hyperscalers",
        "  UNIVERSAL — among the (tracked) hyperscalers!  ",
        "**universal** among the `tracked` hyperscalers",
    ],
)
def test_normalize_collapses_case_punctuation_and_wrapping(
    fix_sweep: ModuleType, variant: str
) -> None:
    """Case, punctuation, and line-wrapping variants normalize identically (00 §2)."""
    assert fix_sweep.normalize(variant) == "universal among the tracked hyperscalers"


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("", ""),
        ("---", ""),
        ("   ", ""),
        ("a1 B2", "a1 b2"),
        ("one\t\ttwo\n\nthree", "one two three"),
    ],
)
def test_normalize_reference_semantics(
    fix_sweep: ModuleType, text: str, expected: str
) -> None:
    """Non-alphanumerics map to single spaces, runs collapse, the result strips."""
    assert fix_sweep.normalize(text) == expected


def test_distinct_sentences_do_not_collide(fix_sweep: ModuleType) -> None:
    """Normalization erases formatting, never meaning."""
    assert fix_sweep.normalize("Lifecycle policies are universal.") != fix_sweep.normalize(
        "Lifecycle policies are uneven."
    )


#: Two sentences differing only in normalized length: 23 chars and 24 chars.
BELOW_FLOOR_TEXT = "abcdefghij klmnopqrst u"
AT_FLOOR_TEXT = "abcdefghij klmnopqrst uv"


def test_floor_drops_twenty_three_and_keeps_twenty_four(fix_sweep: ModuleType) -> None:
    """The needle floor is a length floor on normalized text, not on raw text."""
    assert len(fix_sweep.normalize(BELOW_FLOOR_TEXT)) == 23
    assert len(fix_sweep.normalize(AT_FLOOR_TEXT)) == 24

    raw = [
        _needle(fix_sweep, "a.md", 1, BELOW_FLOOR_TEXT),
        _needle(fix_sweep, "a.md", 2, AT_FLOOR_TEXT),
    ]
    survivors, dropped = fix_sweep.filter_needles(raw, {}, fix_sweep.MIN_NEEDLE_CHARS)

    assert [needle["original"] for needle in survivors] == [AT_FLOOR_TEXT]
    assert dropped == {"belowFloor": 1, "reflowSuppressed": 0}


#: Normalizes to 21 characters — under the shipped floor, over ``--min-chars 10``.
SHORT_CLAIM = "Ten tracked clouds do."


def test_min_chars_overrides_the_shipped_floor(tmp_path: Path) -> None:
    """``--min-chars`` is the test-only knob over the floor (00 §4.3)."""
    repo = _fix_repo(
        tmp_path / "repo",
        {"docs/short.md": f"# Short\n\n{SHORT_CLAIM}\n"},
        claim=SHORT_CLAIM,
    )

    default_code, default_payload = _sweep_json(repo)
    assert default_code == 0
    assert default_payload["hits"] == []
    assert default_payload["droppedNeedles"]["belowFloor"] == 1

    lowered_code, lowered_payload = _sweep_json(repo, "--min-chars", "10")
    assert lowered_code == 1
    assert [hit["file"] for hit in lowered_payload["hits"]] == ["docs/short.md"]


def test_the_normalized_blob_spans_line_breaks(fix_sweep: ModuleType) -> None:
    """One blob per file is what lets a match cross the file's own wrapping."""
    nf = fix_sweep.build_normalized_file("docs/summary.md", REFLOWED_FILE)

    assert nf["blob"] == fix_sweep.normalize(REFLOWED_FILE)
    assert fix_sweep.normalize(CLAIM) in nf["blob"]


def test_a_blob_offset_maps_back_to_the_original_line(fix_sweep: ModuleType) -> None:
    """Blank lines keep the offset map total without ever owning a match."""
    nf = fix_sweep.build_normalized_file("docs/summary.md", REFLOWED_FILE)
    target = fix_sweep.normalize(CLAIM)
    offset = nf["blob"].find(target)

    assert fix_sweep.line_for_offset(nf, offset) == 3
    assert fix_sweep.line_for_offset(nf, offset + len(target) - 1) == 5


# --------------------------------------------------------------------------- #
# §2.4 Needle extraction and reflow/move suppression (REQ-SWEEP-01/02)
# --------------------------------------------------------------------------- #


MULTI_HUNK_DIFF = """diff --git a/doc.md b/doc.md
index 1111111..2222222 100644
--- a/doc.md
+++ b/doc.md
@@ -10 +10 @@
-The first corrected sentence about lifecycle policies.
+The first replacement sentence.
@@ -42,2 +42,1 @@
-The second corrected sentence about retention windows.
-The third corrected sentence about archival tiers.
+A single combined replacement line.
"""


def test_hunk_header_arithmetic_yields_pre_fix_line_numbers(
    fix_sweep: ModuleType,
) -> None:
    """``--unified=0`` makes a-side line numbers computable per hunk (02 §4.2)."""
    raw, added = fix_sweep.extract_needles(MULTI_HUNK_DIFF)

    assert [(needle["file"], needle["line"]) for needle in raw] == [
        ("doc.md", 10),
        ("doc.md", 42),
        ("doc.md", 43),
    ]
    assert set(added) == {"doc.md"}
    assert len(added["doc.md"]) == 2


TRIPLE_DASH_DIFF = """diff --git a/doc.md b/doc.md
--- a/doc.md
+++ b/doc.md
@@ -5,2 +5,0 @@
---
-The removed sentence about lifecycle policies everywhere.
"""


def test_a_removed_line_of_dashes_is_content_not_a_file_header(
    fix_sweep: ModuleType,
) -> None:
    """In-hunk gating keeps a ``---`` content line from hijacking the a-side path."""
    raw, _added = fix_sweep.extract_needles(TRIPLE_DASH_DIFF)

    assert [(needle["file"], needle["line"]) for needle in raw] == [
        ("doc.md", 5),
        ("doc.md", 6),
    ]
    survivors, dropped = fix_sweep.filter_needles(raw, {}, fix_sweep.MIN_NEEDLE_CHARS)
    assert [needle["line"] for needle in survivors] == [6]
    assert dropped["belowFloor"] == 1


ADDED_ONLY_DIFF = """diff --git a/doc.md b/doc.md
--- /dev/null
+++ b/doc.md
@@ -0,0 +1,2 @@
+A brand new sentence about lifecycle policies.
+Another brand new sentence.
"""


def test_an_added_only_diff_yields_no_needles(fix_sweep: ModuleType) -> None:
    """Nothing was corrected, so nothing is swept for."""
    raw, added = fix_sweep.extract_needles(ADDED_ONLY_DIFF)
    assert raw == []
    assert added["doc.md"] == [
        "a brand new sentence about lifecycle policies",
        "another brand new sentence",
    ]


def test_reflow_suppression_drops_text_that_reappears_in_the_delta(
    fix_sweep: ModuleType,
) -> None:
    """Text merely re-wrapped was not corrected (00 §4.3 filter 2)."""
    raw = [_needle(fix_sweep, "doc.md", 4, CLAIM)]
    added = {
        "doc.md": [
            fix_sweep.normalize("Object storage lifecycle policies are universal"),
            fix_sweep.normalize("among the tracked hyperscalers."),
        ]
    }
    survivors, dropped = fix_sweep.filter_needles(raw, added, fix_sweep.MIN_NEEDLE_CHARS)

    assert survivors == []
    assert dropped == {"belowFloor": 0, "reflowSuppressed": 1}


def test_reflow_suppression_spans_files_within_one_delta(
    fix_sweep: ModuleType,
) -> None:
    """Suppression is delta-wide: text moved to another file was not corrected."""
    raw = [_needle(fix_sweep, "a.md", 4, CLAIM)]
    added = {"b.md": [fix_sweep.normalize(CLAIM)]}
    survivors, dropped = fix_sweep.filter_needles(raw, added, fix_sweep.MIN_NEEDLE_CHARS)

    assert survivors == []
    assert dropped["reflowSuppressed"] == 1


def test_a_pure_reflow_sweep_finds_nothing(tmp_path: Path) -> None:
    """Re-wrapping a paragraph is not a correction, so the sweep stays clean."""
    repo = _init_repo(tmp_path / "repo")
    _write(repo, "specs/x/PRD.md", f"# PRD x\n\n{CLAIM}\n")
    _write(repo, "specs/other/PRD.md", f"# PRD other\n\n{CLAIM}\n")
    _commit_all(repo)
    _write(
        repo,
        "specs/x/PRD.md",
        "# PRD x\n\nObject storage lifecycle policies are universal\namong the "
        "tracked hyperscalers.\n",
    )

    code, payload = _sweep_json(repo)
    assert code == 0
    assert payload["hits"] == []
    assert payload["droppedNeedles"]["reflowSuppressed"] == 1


def test_duplicate_removed_lines_keep_distinct_provenance(
    fix_sweep: ModuleType,
) -> None:
    """Duplicates stay distinct needles; one representative drives the search."""
    raw = [
        _needle(fix_sweep, "a.md", 7, CLAIM),
        _needle(fix_sweep, "b.md", 21, CLAIM),
    ]
    survivors, _dropped = fix_sweep.filter_needles(
        raw, {}, fix_sweep.MIN_NEEDLE_CHARS
    )
    assert [(n["file"], n["line"]) for n in survivors] == [("a.md", 7), ("b.md", 21)]

    representatives = fix_sweep.dedupe_needles(survivors)
    assert [(n["file"], n["line"]) for n in representatives] == [("a.md", 7)]


# --------------------------------------------------------------------------- #
# §2.5 Skip paths (REQ-SWEEP-07)
# --------------------------------------------------------------------------- #


SWEEP_REPORT_KEYS = {
    "skipped",
    "reason",
    "baseline",
    "needles",
    "droppedNeedles",
    "excludes",
    "filesScanned",
    "hits",
}


@pytest.mark.parametrize("reason", ["not-a-git-repo", "no-head"])
def test_skip_payloads_are_fully_shaped_and_exit_zero(
    tmp_path: Path, reason: str
) -> None:
    """Absence of a delta is a visible skip, never a finding (00 §6.1)."""
    workdir = tmp_path / reason
    workdir.mkdir()
    if reason == "no-head":
        _init_repo(workdir)

    code, payload = _sweep_json(workdir)

    assert code == 0
    assert payload["skipped"] is True
    assert payload["reason"] == reason
    assert payload["baseline"] is None
    assert payload["needles"] == []
    assert payload["hits"] == []
    assert payload["excludes"] == []
    assert payload["filesScanned"] == 0
    assert set(payload) == SWEEP_REPORT_KEYS


def test_a_skip_is_visible_in_human_output(tmp_path: Path) -> None:
    """The skip prints a line, so the fix pass can record the NOT-RUN notice."""
    workdir = tmp_path / "plain"
    workdir.mkdir()
    proc = _run_cli(workdir, "sweep")
    assert proc.returncode == 0
    assert "SKIPPED" in proc.stdout
    assert "not-a-git-repo" in proc.stdout


# --------------------------------------------------------------------------- #
# §2.5.1 Git-failure classification (00 §10, 02 §3)
# --------------------------------------------------------------------------- #


def test_run_git_reports_failure_as_a_code_never_an_exception(
    fix_sweep: ModuleType, tmp_path: Path
) -> None:
    """The helper never classifies: it reports, and callers decide (02 §3)."""
    code, out, _err = fix_sweep.run_git(["rev-parse", "--git-dir"], tmp_path)
    assert code != 0
    assert out.strip() == ""


def test_run_git_reports_an_unrunnable_git_as_git_unavailable(
    fix_sweep: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A git that cannot be executed at all is its own return code, not a crash."""
    monkeypatch.setenv("PATH", "")
    code, out, _err = fix_sweep.run_git(["rev-parse", "--git-dir"], tmp_path)
    assert code == fix_sweep.GIT_UNAVAILABLE
    assert out == ""


def test_sweep_without_git_still_produces_the_skip_shape(
    fix_sweep: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing git binary is the skip path, so a fix pass is never blocked by it."""
    monkeypatch.setenv("PATH", "")
    report = fix_sweep.run_sweep(tmp_path, [], fix_sweep.MIN_NEEDLE_CHARS)

    assert report["skipped"] is True
    assert report["reason"] == "not-a-git-repo"
    assert report["hits"] == []


def test_a_bare_repository_is_an_error_not_a_skip(tmp_path: Path) -> None:
    """A repository with no working tree cannot be swept — exit 2 (00 §10)."""
    bare = tmp_path / "bare.git"
    bare.mkdir()
    _git(bare, "init", "--bare", "-q")

    proc = _run_cli(bare, "sweep", "--json")
    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr.startswith("Error: repository has no working tree (bare repo):")


def test_a_git_failure_inside_a_valid_repository_is_exit_two(
    fix_sweep: ModuleType,
    scratch_repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A failing corpus enumeration is an operational failure, never a clean sweep."""
    original = fix_sweep.run_git

    def failing(args: list[str], repo_root: Path) -> tuple[int, str, str]:
        if args and args[0] == "ls-files":
            return 128, "", "fatal: simulated ls-files failure\n"
        return original(args, repo_root)

    monkeypatch.setattr(fix_sweep, "run_git", failing)
    monkeypatch.setattr(
        sys, "argv", ["fix-sweep.py", "sweep", "--repo-root", str(scratch_repo)]
    )

    assert fix_sweep.main() == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("Error: git ls-files failed (128):")


def test_list_corpus_paths_raises_usage_error_on_git_failure(
    fix_sweep: ModuleType, tmp_path: Path
) -> None:
    """Corpus enumeration outside a repository is exit-2 territory, not a skip."""
    with pytest.raises(fix_sweep.UsageError):
        fix_sweep.list_corpus_paths(tmp_path)


# --------------------------------------------------------------------------- #
# §2.6 Corpus boundaries (REQ-SWEEP-03)
# --------------------------------------------------------------------------- #


def test_untracked_files_are_swept_and_ignored_files_are_not(tmp_path: Path) -> None:
    """The corpus is tracked plus untracked-not-ignored (00 §5.1)."""
    repo = _fix_repo(tmp_path / "repo", {".gitignore": "build/\n"})
    _write(repo, "notes/new.md", f"# Notes\n\n{CLAIM}\n")
    _write(repo, "build/out.md", f"# Built\n\n{CLAIM}\n")

    code, payload = _sweep_json(repo)

    assert code == 1
    assert [hit["file"] for hit in payload["hits"]] == ["notes/new.md"]


def test_an_ungated_adapters_tree_is_swept(tmp_path: Path) -> None:
    """Without a detectable drift gate, ``adapters/`` is an ordinary directory."""
    repo = _fix_repo(tmp_path / "repo", {"adapters/claude/skills/x.md": f"# x\n\n{CLAIM}\n"})

    code, payload = _sweep_json(repo)

    assert code == 1
    assert [hit["file"] for hit in payload["hits"]] == ["adapters/claude/skills/x.md"]
    assert payload["excludes"] == [".verification/"]


def test_a_gated_adapters_tree_is_excluded(tmp_path: Path) -> None:
    """The gate sentinel's presence is what excludes the regenerated tree."""
    repo = _fix_repo(
        tmp_path / "repo",
        {
            "adapters/claude/skills/x.md": f"# x\n\n{CLAIM}\n",
            "scripts/build-adapters.py": 'print("gate sentinel")\n',
        },
    )

    code, payload = _sweep_json(repo)

    assert code == 0
    assert payload["hits"] == []
    assert payload["excludes"] == [".verification/", "adapters/"]


def test_excludes_payload_lists_gate_and_user_prefixes_in_application_order(
    tmp_path: Path,
) -> None:
    """The payload names every exclusion actually applied, in order (00 §6.1)."""
    repo = _fix_repo(
        tmp_path / "repo",
        {
            "docs/summary.md": f"# Summary\n\n{CLAIM}\n",
            "scripts/build-adapters.py": 'print("gate sentinel")\n',
        },
    )

    code, payload = _sweep_json(repo, "--exclude", "docs/")

    assert code == 0
    assert payload["excludes"] == [".verification/", "adapters/", "docs/"]
    assert payload["hits"] == []


def test_a_user_exclude_prefix_is_repo_relative(tmp_path: Path) -> None:
    """``--exclude`` matches the repo-relative POSIX path as a plain prefix."""
    repo = _fix_repo(
        tmp_path / "repo",
        {
            "docs/summary.md": f"# Summary\n\n{CLAIM}\n",
            "notes/summary.md": f"# Notes\n\n{CLAIM}\n",
        },
    )

    code, payload = _sweep_json(repo, "--exclude", "docs/")

    assert code == 1
    assert [hit["file"] for hit in payload["hits"]] == ["notes/summary.md"]


def test_an_empty_exclude_prefix_is_rejected(scratch_repo: Path) -> None:
    """An empty prefix would silently empty the corpus and report a false clean."""
    proc = _run_cli(scratch_repo, "sweep", "--exclude", "")

    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr.startswith("Error:")


def test_a_verification_segment_at_any_depth_is_excluded(
    fix_sweep: ModuleType,
) -> None:
    """Findings documents are audit records, matched by path segment (00 §5.2)."""
    excludes = [fix_sweep.VERIFICATION_EXCLUDE_LABEL]
    assert fix_sweep.is_excluded("specs/x/.verification/VERIFY-impl.md", excludes, [])
    assert not fix_sweep.is_excluded("specs/x/verification/notes.md", excludes, [])


def test_a_binary_file_is_skipped_and_not_counted(tmp_path: Path) -> None:
    """Undecodable files are skipped silently, never fatal (00 §5.2)."""
    repo = _fix_repo(tmp_path / "repo", {"docs/summary.md": f"# Summary\n\n{CLAIM}\n"})
    (repo / "assets").mkdir()
    (repo / "assets" / "blob.bin").write_bytes(b"\xff\xfe\x00\x01binary")

    code, payload = _sweep_json(repo)

    assert code == 1
    assert payload["filesScanned"] == 2
    assert [hit["file"] for hit in payload["hits"]] == ["docs/summary.md"]


# --------------------------------------------------------------------------- #
# §2.7 plan-coverage (REQ-CARD-01, REQ-CARD-04)
# --------------------------------------------------------------------------- #


def _findings_doc(
    finding_count: int,
    covered_count: int,
    *,
    claimed_total: int | None = None,
    include_plan: bool = True,
    include_findings: bool = True,
    fenced_extra: bool = False,
) -> str:
    """Render a findings document with the template's anchors (00 §7.1)."""
    parts: list[str] = ["# Verification Findings", ""]
    if claimed_total is not None:
        parts += ["## Summary", "", f"- Total findings: {claimed_total}", ""]
    if include_findings:
        parts += ["## Findings", ""]
        for index in range(1, finding_count + 1):
            parts += [f"### V-{index:03d}: Finding {index}", "", "Body text.", ""]
        if fenced_extra:
            parts += [
                "```markdown",
                "### V-900: A template example, not a finding",
                "- **Addresses:** V-901",
                "```",
                "",
            ]
    if include_plan:
        parts += ["## Fix Execution Plan", "", "### Execution Steps", ""]
        for index in range(1, covered_count + 1):
            parts += [
                f"#### Step {index}: Fix finding {index}",
                "",
                f"- **Addresses:** V-{index:03d}",
                "",
            ]
    return "\n".join(parts) + "\n"


def _plan_json(tmp_path: Path, name: str, text: str) -> tuple[int, dict]:
    """Write ``text`` to ``name`` and run ``plan-coverage --json`` over it."""
    doc = tmp_path / name
    doc.write_text(text, encoding="utf-8")
    proc = _run_cli(tmp_path, "plan-coverage", str(doc), "--json")
    return proc.returncode, json.loads(proc.stdout)


def test_plan_coverage_names_the_omitted_finding(tmp_path: Path) -> None:
    """A dropped work item is named, never reported as a count delta (REQ-CARD-01)."""
    code, payload = _plan_json(
        tmp_path, "findings.md", _findings_doc(16, 15, claimed_total=16)
    )

    assert code == 1
    assert payload["applicable"] is True
    assert payload["uncovered"] == ["V-016"]
    assert payload["actualTotal"] == 16
    assert payload["steps"] == 15
    assert payload["totalMismatch"] is False


def test_plan_coverage_reports_a_claimed_total_mismatch(tmp_path: Path) -> None:
    """The findings count is re-derived, never trusted from the Summary prose."""
    code, payload = _plan_json(
        tmp_path, "findings.md", _findings_doc(15, 15, claimed_total=16)
    )

    assert code == 1
    assert payload["claimedTotal"] == 16
    assert payload["actualTotal"] == 15
    assert payload["totalMismatch"] is True
    assert payload["uncovered"] == []


def test_plan_coverage_mismatch_is_human_readable(tmp_path: Path) -> None:
    """The human report states the disagreement as ``claimed N, actual M``."""
    doc = tmp_path / "findings.md"
    doc.write_text(_findings_doc(15, 15, claimed_total=16), encoding="utf-8")
    proc = _run_cli(tmp_path, "plan-coverage", str(doc))

    assert proc.returncode == 1
    assert "claimed 16, actual 15" in proc.stdout


def test_plan_coverage_passes_when_every_finding_is_addressed(tmp_path: Path) -> None:
    """Full coverage with consistent totals closes clean at exit 0."""
    code, payload = _plan_json(
        tmp_path, "findings.md", _findings_doc(3, 3, claimed_total=3)
    )

    assert code == 0
    assert payload["uncovered"] == []
    assert payload["covered"] == ["V-001", "V-002", "V-003"]
    assert payload["totalMismatch"] is False


@pytest.mark.parametrize(
    ("include_findings", "include_plan"),
    [(True, False), (False, True), (False, False)],
)
def test_plan_coverage_degrades_to_not_applicable(
    tmp_path: Path, include_findings: bool, include_plan: bool
) -> None:
    """Missing trigger structure degrades to not-applicable, never a hard fail."""
    code, payload = _plan_json(
        tmp_path,
        "findings.md",
        _findings_doc(
            3, 3, include_findings=include_findings, include_plan=include_plan
        ),
    )

    assert code == 0
    assert payload["applicable"] is False
    assert payload["findings"] == []
    assert payload["uncovered"] == []


def test_plan_coverage_without_a_summary_total_asserts_no_mismatch(
    tmp_path: Path,
) -> None:
    """An absent claimed total is not a disagreement (00 §6.2)."""
    code, payload = _plan_json(tmp_path, "findings.md", _findings_doc(3, 3))

    assert code == 0
    assert payload["claimedTotal"] is None
    assert payload["totalMismatch"] is False


def test_fenced_finding_headings_are_not_counted(tmp_path: Path) -> None:
    """The template ships fenced examples; counting them would fabricate findings."""
    code, payload = _plan_json(
        tmp_path,
        "findings.md",
        _findings_doc(3, 3, claimed_total=3, fenced_extra=True),
    )

    assert code == 0
    assert payload["findings"] == ["V-001", "V-002", "V-003"]
    assert "V-900" not in payload["findings"]


def test_plan_coverage_on_an_unreadable_document_is_exit_two(tmp_path: Path) -> None:
    """An unreadable path is an error; a readable odd document is not-applicable."""
    proc = _run_cli(tmp_path, "plan-coverage", str(tmp_path / "absent.md"), "--json")

    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr.startswith("Error: cannot read findings document:")


# --------------------------------------------------------------------------- #
# §2.8 CLI, payloads, and output formats (REQ-OBS-01, REQ-SEC-01)
# --------------------------------------------------------------------------- #


def test_json_mode_emits_exactly_one_object(tmp_path: Path) -> None:
    """``--json`` stdout is one parseable object and no human lines (02 §2.3)."""
    repo = _build_f5_repo(tmp_path / "repo")
    proc = _run_cli(repo, "sweep", "--json")

    payload = json.loads(proc.stdout)
    assert isinstance(payload, dict)
    assert set(payload) == SWEEP_REPORT_KEYS
    assert proc.stdout.lstrip().startswith("{")
    assert proc.stdout.rstrip().endswith("}")


def test_human_hit_lines_use_the_fixed_format(tmp_path: Path) -> None:
    """forge-fix prose reads this line shape, so it is pinned here (02 §2.3)."""
    repo = _build_f5_repo(tmp_path / "repo")
    proc = _run_cli(repo, "sweep")

    assert proc.returncode == 1
    lines = proc.stdout.splitlines()
    assert lines[0].startswith("sweep: FAIL — 3 survivor(s)")
    matches = [HIT_LINE_RE.match(line) for line in lines[1:]]
    assert all(matches)
    assert [match.group("file") for match in matches] == [
        "docs/summary.md",
        "specs/other/PRD.md",
        "src/generated/foo.ts",
    ]
    assert {match.group("source_file") for match in matches} == {"specs/x/PRD.md"}
    assert {match.group("source_line") for match in matches} == {"5"}


def test_a_clean_sweep_reports_its_counters(tmp_path: Path) -> None:
    """The PASS line carries the needle and filter counters for the record."""
    repo = _fix_repo(tmp_path / "repo", {"docs/other.md": "# Other\n\nUnrelated.\n"})
    proc = _run_cli(repo, "sweep")

    assert proc.returncode == 0
    assert proc.stdout.startswith("sweep: PASS — 0 survivor(s)")


#: A claim carrying quotes and markup — echoed unelided (REQ-SEC-01).
MARKUP_CLAIM = 'The "universal" <b>lifecycle</b> flag is set for every tracked account.'


def test_matched_text_is_echoed_verbatim(tmp_path: Path) -> None:
    """Removed text is already in git history, so it is reported without elision."""
    repo = _fix_repo(
        tmp_path / "repo",
        {"docs/summary.md": f"# Summary\n\n{MARKUP_CLAIM}\n"},
        claim=MARKUP_CLAIM,
    )

    code, payload = _sweep_json(repo)

    assert code == 1
    hit = payload["hits"][0]
    assert hit["needle"] == MARKUP_CLAIM
    assert hit["excerpt"] == MARKUP_CLAIM
    assert payload["needles"][0]["original"] == MARKUP_CLAIM


def test_an_unknown_flag_is_rejected_by_the_parser(scratch_repo: Path) -> None:
    """Unknown flags land on the exit-2 row (02 §2.1)."""
    proc = _run_cli(scratch_repo, "sweep", "--nope")

    assert proc.returncode == 2
    assert proc.stdout == ""
    assert proc.stderr != ""


def test_a_missing_subcommand_is_rejected(scratch_repo: Path) -> None:
    """The subcommand is required — there is no default mode."""
    proc = _run_cli(scratch_repo)

    assert proc.returncode == 2
    assert proc.stdout == ""


# --------------------------------------------------------------------------- #
# §2.9 Determinism and read-only behavior (REQ-CONC-01)
# --------------------------------------------------------------------------- #


def test_two_runs_over_one_tree_are_byte_identical(tmp_path: Path) -> None:
    """Ordering is total and nothing is cached, so output is reproducible (02 §7)."""
    repo = _build_f5_repo(tmp_path / "repo")
    first = _run_cli(repo, "sweep", "--json")
    second = _run_cli(repo, "sweep", "--json")

    assert first.returncode == second.returncode == 1
    assert first.stdout == second.stdout


def test_the_sweep_never_writes_to_the_corpus(tmp_path: Path) -> None:
    """The script's only outputs are stdout, stderr, and an exit code (02 §1)."""
    repo = _build_f5_repo(tmp_path / "repo")
    before = {
        path: (path.stat().st_mtime_ns, path.read_bytes())
        for path in sorted(repo.rglob("*"))
        if path.is_file() and ".git/" not in path.as_posix()
    }

    proc = _run_cli(repo, "sweep", "--json")
    assert proc.returncode == 1

    after = {
        path: (path.stat().st_mtime_ns, path.read_bytes())
        for path in sorted(repo.rglob("*"))
        if path.is_file() and ".git/" not in path.as_posix()
    }
    assert after == before


# --------------------------------------------------------------------------- #
# §2.10 Cost-model shape (REQ-PERF-01 — no wall-clock assertion)
# --------------------------------------------------------------------------- #


def test_git_invocations_do_not_grow_with_corpus_size(
    fix_sweep: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The git roster is fixed at the probes plus diff plus ls-files (02 §7)."""
    repo = _build_f5_repo(tmp_path / "repo")
    original = fix_sweep.run_git
    calls: list[list[str]] = []

    def counting(args: list[str], repo_root: Path) -> tuple[int, str, str]:
        calls.append(list(args))
        return original(args, repo_root)

    monkeypatch.setattr(fix_sweep, "run_git", counting)
    report = fix_sweep.run_sweep(repo, [], fix_sweep.MIN_NEEDLE_CHARS)

    assert report["filesScanned"] > 1
    assert len(calls) <= 5
    assert sum(1 for args in calls if args and args[0] == "ls-files") == 1


def test_each_corpus_file_is_read_exactly_once(
    fix_sweep: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One read plus one normalize pass over the corpus, with no re-reads (02 §7)."""
    repo = _build_f5_repo(tmp_path / "repo")
    original_read_text = Path.read_text
    reads: list[str] = []

    def counting_read_text(self: Path, *args: object, **kwargs: object) -> str:
        reads.append(self.as_posix())
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read_text)
    report = fix_sweep.run_sweep(repo, [], fix_sweep.MIN_NEEDLE_CHARS)

    assert len(reads) == report["filesScanned"]
    assert len(set(reads)) == len(reads)


# --------------------------------------------------------------------------- #
# §2.11 Prose guards over the canon edits (pattern: test_lifecycle_artifact_check.py)
#
# Meta-guard contract: the protection set is the enumerated literals below and
# nothing else. Exact-markdown fidelity of the surrounding prose, wording beyond
# these literals, and resistance to every conceivable rewording are declared
# non-goals (05 §2.11).
# --------------------------------------------------------------------------- #

STAGE_EXIT_PROTOCOL = REPO_ROOT / "references" / "stage-exit-protocol.md"
BUILD_ADAPTERS = REPO_ROOT / "scripts" / "build-adapters.py"

#: The seven `--outcome` values Step 7's table maps every path onto. This feature adds
#: none and removes none (C-6), so the set is asserted exactly rather than by membership.
FIX_OUTCOMES = frozenset(
    {
        "no-findings",
        "decisions",
        "failed",
        "applied",
        "reverified",
        "reverify-findings",
        "deferred",
    }
)

#: The Step 1–7 headings verbatim — no renumbering and no retitling (C-1).
STEP_HEADINGS = (
    "## Step 1: Locate Findings and Establish the Served Stage",
    "## Step 2: Parse Fix Execution Plan",
    "## Step 3: Handle User Decisions",
    "## Step 4: Execute Fix Steps",
    "## Step 5: Record the Fixes Through `state-verify` and Commit",
    "## Step 6: Re-verify Gate",
    "## Step 7: Close the Stage",
)

#: `## Step 6: Re-verify Gate` through the next `## ` heading, captured from
#: `skills/forge-fix/SKILL.md` as it stood before this feature's Step 2/4/5 insertions.
#: The re-verify gate is out of scope for the change (C-1), and heading survival alone
#: would not detect a body edit inside the section.
STEP_6_PINNED = """\
## Step 6: Re-verify Gate

Fixes are applied and recorded as `findings-applied`. That status makes **no** claim of freshness: the writer clears `verifiedStageVersion`, so the served stage's verification stays **outstanding** in the navigator's ledger, and only a re-verify that passes resolves it. Because a re-verify is the one thing that confirms the fixes actually resolved the findings, on a **direct** invocation **prompt** for it rather than leaving it as a passive suggestion — this is the same **Standard Verify Gate** the stage skills stamp (`references/stage-exit-protocol.md`).

**A nested owner presents no gate.** Return your structured result (served stage, outcome `applied`, findings file, steps applied) to the outer caller — it performs the mandatory re-verify itself — and print no terminal block of your own. This follows from the `owner:` token read at entry; it is never decided by how the invocation was phrased.

On a **direct** invocation, present the gate with `AskUserQuestion` using these three options — but only when your verify capability is `interactive` (Step 7):
- **Re-verify {feature} now** *(recommended)* — dispatch the clean-room `forge-verifier` subagent from this session in require-clean mode to confirm every finding is resolved. The dispatch is **scoped** per "Re-verify scope and convergence" in `references/stage-exit-protocol.md`: it confirms the prior report's findings against their acceptance evidence and examines this fix's delta — never a fresh full-checklist sweep — a finding with a recorded decision is never re-filed, and only an unresolved prior finding or a new blocking defect the fix introduced may block. The digest returns here so any remaining issue keeps its context. One-time — it does **not** change config. A clean-or-advisory-only result closes as `reverified`; unresolved prior findings or new blocking defects close as `reverify-findings` for the same served stage. **Escalation:** if that would be the second consecutive `reverify-findings` for this served stage (count the round-discriminated reports in `.verification/`), follow "Escalation (the round ledger)" in `references/stage-exit-protocol.md` before closing — present the digest and offer explicit acceptance of the residual findings; do not recommend another fix pass.
- **Re-verify now + enable auto-verify going forward** — re-verify now **and** patch `"autoVerify": true` into `forge.config.json` in place (preserve formatting and every other key) so future stages verify automatically, no prompt. This complements the `forge-init` opt-in. **Do not auto-commit this config change** — treat it like `notes`: a user-facing edit the user commits on their own cadence, never folded into a stage's artifact commit. Its outcome mapping is identical to the option above.
- **Skip for now** — an explicit deferral of the re-verify. It closes as **`deferred`**, never `reverified`: the fixes are recorded but nothing has confirmed them, and the served stage's verification stays outstanding until a re-verify passes, so the pipeline does not advance on this pass. Run `/feature-forge:forge {feature}` when you want pipeline status.

**Manual capability is not a skip, and not a deferral.** When your capability is `manual` (Step 7 — no question mechanism **and** no permitted dispatch), do not run clean-room and do not fabricate a choice nobody made: close with `applied`, and the script prints `/feature-forge:forge-verify {feature} --served-stage {servedStage}` as the primary action for the user to run. Offer the auto-verify enable as plain text only if a config write is possible.

**A re-verify that cannot run is an operational failure.** If the user chose to re-verify and the dispatch is refused, returns the `CLEAN_ROOM_UNAVAILABLE` sentinel, or returns no answer, the fixes remain recorded but nothing was confirmed: close with `failed`. Never report `reverified` on an unrun verify, and never treat an unavailable tool as an explicit user skip.
"""


def _section(text: str, heading: str, level: str = "\n## ") -> str:
    """Return `heading` through (excluding) the next heading at `level`.

    Heading-terminated rather than sliced to end-of-file, so a section appended
    later cannot satisfy an assertion aimed at this one.
    """
    start = text.index(heading)
    rest = text[start + len(heading) :]
    end = rest.find(level)
    return heading + (rest if end == -1 else rest[:end])


def _bash_fences(text: str) -> list[str]:
    """Return the bodies of every ```bash fence in `text`."""
    return re.findall(r"^```bash\n(.*?)^```", text, flags=re.MULTILINE | re.DOTALL)


def _dimension_bullet(text: str, mode: str) -> str:
    """Return the `  - **{mode}** (…)` dimension-group bullet from the verify skill."""
    start = text.index(f"  - **{mode}** (")
    rest = text[start:]
    end = rest.find("\n  - **")
    return rest if end == -1 else rest[:end]


def test_step_2_invokes_plan_coverage_from_a_bash_fence() -> None:
    """The cardinality assertion is a runnable fenced invocation (03 §3.2)."""
    fences = _bash_fences(FORGE_FIX_SKILL.read_text(encoding="utf-8"))
    matching = [
        fence
        for fence in fences
        if re.search(r'\$R/scripts/fix-sweep\.py"?\s+plan-coverage\b', fence)
    ]
    assert len(matching) == 1
    assert "--json" in matching[0]


def test_step_4_invokes_the_sweep_from_a_bash_fence() -> None:
    """The closing sub-step's sweep is a runnable fenced invocation (03 §4.6)."""
    fences = _bash_fences(FORGE_FIX_SKILL.read_text(encoding="utf-8"))
    matching = [
        fence for fence in fences if re.search(r'\$R/scripts/fix-sweep\.py"?\s+sweep\b', fence)
    ]
    assert len(matching) == 1
    assert "scripts/fix-sweep.py" in matching[0]
    assert "--json" in matching[0]


def test_not_run_notice_wording_is_exact() -> None:
    """The skip notice keeps its em dash and its `{reason}` placeholder (REQ-SWEEP-07)."""
    text = FORGE_FIX_SKILL.read_text(encoding="utf-8")
    assert "- Sweep: NOT RUN \u2014 no git delta ({reason})" in text


def test_all_three_disposition_tokens_are_present() -> None:
    """Every hit gets exactly one of the three dispositions (REQ-SWEEP-04)."""
    text = FORGE_FIX_SKILL.read_text(encoding="utf-8")
    for token in ("FIXED", "JUSTIFIED:", "FALSE-POSITIVE:"):
        assert token in text


def test_failed_fixed_rule_is_stated() -> None:
    """A re-appearing `FIXED` hit must be re-dispositioned, never left as fixed (03 §4.6)."""
    text = FORGE_FIX_SKILL.read_text(encoding="utf-8")
    assert "never leave it recorded as" in text


def test_staging_is_enumerated_and_bulk_staging_is_prohibited() -> None:
    """Disposition edits are staged one path at a time (REQ-SWEEP-05, 03 §5.2)."""
    text = FORGE_FIX_SKILL.read_text(encoding="utf-8")
    assert "git add <path>" in text
    for bulk in ("git add -A", "git add ."):
        occurrences = list(re.finditer(re.escape(bulk), text))
        assert occurrences
        for match in occurrences:
            preceding = text[max(0, match.start() - 40) : match.start()]
            assert "never" in preceding


def test_operator_escape_hatches_stay_out_of_the_skill() -> None:
    """`--exclude` and `--min-chars` are operator knobs, not agent prose (03 §4.6)."""
    text = FORGE_FIX_SKILL.read_text(encoding="utf-8")
    assert "--exclude" not in text
    assert "--min-chars" not in text


def test_outcome_table_holds_exactly_the_seven_existing_values() -> None:
    """Step 7's outcome vocabulary is unchanged by this feature (C-6)."""
    step7 = _section(FORGE_FIX_SKILL.read_text(encoding="utf-8"), "## Step 7: Close the Stage")
    rows = [
        line
        for line in step7.splitlines()
        if line.startswith("|") and not line.startswith("|---") and "`--outcome`" not in line
    ]
    values = [row.split("|")[2].strip().strip("`") for row in rows]
    assert len(values) == len(FIX_OUTCOMES)
    assert set(values) == FIX_OUTCOMES


def test_step_headings_survive_unrenumbered() -> None:
    """Steps 1–7 keep their numbers and titles — the insertions renumber nothing (C-1)."""
    text = FORGE_FIX_SKILL.read_text(encoding="utf-8")
    for heading in STEP_HEADINGS:
        assert f"\n{heading}\n" in text


def test_step_6_reverify_gate_is_byte_identical_to_the_pinned_text() -> None:
    """The re-verify gate is out of scope for this feature, body included (C-1)."""
    section = _section(FORGE_FIX_SKILL.read_text(encoding="utf-8"), "## Step 6: Re-verify Gate")
    assert section == STEP_6_PINNED


def test_stage_exit_protocol_still_cites_forge_fix_step_6() -> None:
    """The shared protocol's Step 6 citation is untouched by this feature (C-1)."""
    text = STAGE_EXIT_PROTOCOL.read_text(encoding="utf-8")
    assert "`skills/forge-fix/SKILL.md` Step 6" in text


def test_check_b29_present_with_its_degradation_and_severity() -> None:
    """Backlog work-order cardinality degrades to not-applicable and names omissions (04 §3.1)."""
    text = (CHECKLISTS / "backlog.md").read_text(encoding="utf-8")
    section = _section(text, "### Work-Order Cardinality", level="\n### ")
    assert "**CHECK-B29**" in section
    assert "(#170)" in section
    assert "not-applicable" in section
    assert "never a hard fail" in section
    assert "`gap`" in section
    assert "by name" in section
    assert "Report, do not repair" in section


def test_check_i24_present_with_its_degradation_and_severity() -> None:
    """Impl work-order cardinality degrades to not-applicable and names omissions (04 §3.2)."""
    text = (CHECKLISTS / "impl.md").read_text(encoding="utf-8")
    section = _section(text, "### Work-Order Cardinality", level="\n### ")
    assert "**CHECK-I24**" in section
    assert "(#170)" in section
    assert "not-applicable" in section
    assert "never a hard fail" in section
    assert "`gap`" in section
    assert "by name" in section
    assert "Report, do not repair" in section


def test_check_i25_present_with_its_severity_ladder() -> None:
    """Intra-artifact consistency is advisory until decision-bearing (04 §3.3)."""
    text = (CHECKLISTS / "impl.md").read_text(encoding="utf-8")
    section = _section(text, "### Internal Consistency", level="\n### ")
    assert "**CHECK-I25**" in section
    assert "(#170)" in section
    assert "not-applicable" in section
    assert "`inconsistency`" in section
    assert "`error`" in section
    assert "decision-bearing" in section
    assert "Report, do not repair" in section


def test_check_s39_present_with_its_severity_ladder() -> None:
    """Intra-document consistency is advisory until decision-bearing (04 §3.4)."""
    text = (CHECKLISTS / "specs.md").read_text(encoding="utf-8")
    section = _section(text, "### Internal Consistency", level="\n### ")
    assert "**CHECK-S39**" in section
    assert "(#170)" in section
    assert "not-applicable" in section
    assert "`inconsistency`" in section
    assert "`error`" in section
    assert "decision-bearing" in section
    assert "Report, do not repair" in section


@pytest.mark.parametrize(
    ("mode", "tag"),
    [
        ("backlog", "(owns CHECK-B29)"),
        ("impl", "(owns CHECK-I24/I25)"),
        ("specs", "(owns CHECK-S39)"),
    ],
)
def test_new_checks_are_reachable_from_their_dimension_group(mode: str, tag: str) -> None:
    """Each new check is tagged onto the dimension group that dispatches it (04 §4.3)."""
    bullet = _dimension_bullet(VERIFY_SKILL.read_text(encoding="utf-8"), mode)
    assert tag in bullet


def test_runtime_helpers_distributes_the_sweep_script() -> None:
    """Every adapter bundle ships `fix-sweep.py`, so the fenced invocations resolve (01 §5.1)."""
    text = BUILD_ADAPTERS.read_text(encoding="utf-8")
    tuple_body = _section(text, "RUNTIME_HELPERS", level="\n)")
    assert '"fix-sweep.py"' in tuple_body
