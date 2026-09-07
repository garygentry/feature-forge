"""Tests for ``forge-session.py select-outcome`` (issue #276, #265 P3.1).

`select-outcome` moves exit-outcome selection for forge-verify/forge-fix out of
model judgment and into a deterministic verb, the same "never eyeball the graph"
move `rank-features` makes for `verifyGate`. Two guards live here:

- **Parity (scope 2).** The verb's outcome vocabulary is `VerifyOutcome` /
  `FixOutcome` (via `EXIT_OUTCOMES`). Nothing else pins those aliases to the prose
  a skill actually reads — the **Outcome.** tables in `skills/forge-verify/SKILL.md`
  and `skills/forge-fix/SKILL.md`. `test_*_outcome_table_matches_the_enum` asserts
  the table and the enum enumerate exactly the same values, in both directions, so
  neither can gain or drop an outcome without the other.

- **Fixtures (scope 3).** Every enum value is reached from an on-disk fixture (plus
  the runtime signal flags for the three outcomes disk cannot record), including the
  two cases the issue calls out as easy to mis-eyeball: a sweep whose survivors are
  all `FALSE-POSITIVE` (still `applied`, never `failed`), and a re-verify that reopens
  findings on a scoped subset (`reverify-findings`). `test_every_*_outcome_is_reachable`
  asserts the union of reached outcomes IS the full enum — a new outcome added without
  a fixture fails here.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import get_args

REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER = REPO_ROOT / "scripts" / "forge-session.py"
SKILLS = REPO_ROOT / "skills"


def _load_session_module():
    """Import `forge-session.py` by path (its name is hyphenated, so unimportable)."""
    spec = importlib.util.spec_from_file_location("forge_session_select", HELPER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SESSION = _load_session_module()


# --------------------------------------------------------------------------------------
# Parity (scope 2) — the enum and the skill-body Outcome table agree
# --------------------------------------------------------------------------------------


def _outcome_table_values(skill: str) -> set[str]:
    """The `--outcome` column of a skill body's **Outcome.** table.

    Anchors on the ``| This run's result | `--outcome` | ...`` header, then reads the
    second content column of each data row until the table ends. Strips markdown
    emphasis/backticks so `` `no-findings` `` and a bare ``passed`` both normalize.
    """
    text = (SKILLS / f"forge-{skill}" / "SKILL.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    values: set[str] = set()
    in_table = False
    for line in lines:
        stripped = line.strip()
        is_row = stripped.startswith("|")
        if not in_table:
            if is_row and "this run's result" in stripped.lower() and "--outcome" in stripped:
                in_table = True
            continue
        if not is_row:
            break  # blank line / prose ends the table
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if len(cells) < 2:
            continue
        outcome_cell = cells[1]
        if set(outcome_cell) <= {"-", ":", " "}:  # the header/---|--- separator row
            continue
        token = outcome_cell.strip("`*").strip()
        if token and token != "--outcome":
            values.add(token)
    assert values, f"no Outcome table parsed from forge-{skill}/SKILL.md"
    return values


def test_verify_outcome_table_matches_the_enum():
    """forge-verify's Outcome table enumerates exactly `VerifyOutcome` — both ways."""
    assert _outcome_table_values("verify") == set(get_args(SESSION.VerifyOutcome))


def test_fix_outcome_table_matches_the_enum():
    """forge-fix's Outcome table enumerates exactly `FixOutcome` — both ways."""
    assert _outcome_table_values("fix") == set(get_args(SESSION.FixOutcome))


def test_the_verb_serves_exactly_the_two_branch_skills():
    """The enums the verb chooses from are the branch-skill EXIT_OUTCOMES entries."""
    assert SESSION.EXIT_OUTCOMES["forge-verify"] == frozenset(get_args(SESSION.VerifyOutcome))
    assert SESSION.EXIT_OUTCOMES["forge-fix"] == frozenset(get_args(SESSION.FixOutcome))


def test_the_synopsis_documents_select_outcome():
    """The module docstring (argparse `description`, i.e. `--help`) names the verb."""
    doc = SESSION.__doc__ or ""
    assert "select-outcome --feature F --served-stage S" in doc
    for flag in ("--op-failure", "--user-deferred", "--decisions-open"):
        assert flag in doc, f"{flag} missing from the select-outcome synopsis"


# --------------------------------------------------------------------------------------
# Fixture harness
# --------------------------------------------------------------------------------------

_CLEAN_REPORT = """# Verification Report: feat (tech)
## Summary
- Blocking (errors + gaps): 0
## Findings

_No findings._
"""

_ADVISORY_REPORT = """# Verification Report: feat (tech)
## Summary
- Blocking (errors + gaps): 0
## Findings
### V-001: minor
- **Severity:** improvement
"""

_BLOCKING_REPORT = """# Verification Report: feat (tech)
## Summary
- Blocking (errors + gaps): 2
## Findings
### V-001: a
- **Severity:** gap
### V-002: b
- **Severity:** error
### V-003: c
- **Severity:** improvement
"""

_FIX_PROGRESS_FALSE_POSITIVE = """
## Fix Progress
- Step 1: [APPLIED] 2026-09-07 — applied the plan
- Sweep: 2026-09-07 — 2 needle(s), 2 survivor(s), 2 disposition(s)
  - a.py:1 — "old" → FALSE-POSITIVE: unrelated match
  - b.py:2 — "old" → FALSE-POSITIVE: deliberate quote
"""

_FIX_PROGRESS_FIXED = """
## Fix Progress
- Step 1: [APPLIED] 2026-09-07 — applied the plan
- Sweep: 2026-09-07 — 1 needle(s), 1 survivor(s), 1 disposition(s)
  - a.py:1 — "old" → FIXED 2026-09-07
"""


def _feature(tmp_path: Path, *, entry: dict | None, reports: dict[str, str]) -> Path:
    """Build a specs dir with one feature: its verify entry + `.verification/` reports."""
    specs = tmp_path / "specs"
    feat = specs / "feat"
    (feat / ".verification").mkdir(parents=True, exist_ok=True)
    stages: dict = {"forge-2-tech": {"status": "complete", "version": 1}}
    if entry is not None:
        stages["forge-verify-tech"] = entry
    (feat / ".pipeline-state.json").write_text(
        json.dumps({"pipelineStatus": "active", "stages": stages})
    )
    for name, body in reports.items():
        (feat / ".verification" / name).write_text(body)
    return specs


def _run(specs: Path, skill: str, *flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HELPER), "select-outcome", "--feature", "feat",
         "--served-stage", "forge-2-tech", "--skill", skill,
         "--specs-dir", str(specs), "--json", *flags],
        capture_output=True, text=True,
    )


def _outcome(specs: Path, skill: str, *flags: str) -> str:
    result = _run(specs, skill, *flags)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["outcome"]


# --------------------------------------------------------------------------------------
# Fixtures (scope 3) — forge-verify: every VerifyOutcome
# --------------------------------------------------------------------------------------


def test_verify_passed_clean(tmp_path: Path):
    specs = _feature(
        tmp_path,
        entry={"status": "passed", "findingsCount": 0},
        reports={"VERIFY-tech-2026-09-07.md": _CLEAN_REPORT},
    )
    assert _outcome(specs, "verify") == "passed"


def test_verify_passed_advisory_only(tmp_path: Path):
    """An advisory-only report (no error/gap) is recorded `passed`, so → passed."""
    specs = _feature(
        tmp_path,
        entry={"status": "passed", "findingsCount": 1},
        reports={"VERIFY-tech-2026-09-07.md": _ADVISORY_REPORT},
    )
    assert _outcome(specs, "verify") == "passed"


def test_verify_findings(tmp_path: Path):
    specs = _feature(
        tmp_path,
        entry={"status": "findings-reported", "findingsCount": 2},
        reports={"VERIFY-tech-2026-09-07.md": _BLOCKING_REPORT},
    )
    assert _outcome(specs, "verify") == "findings"


def test_verify_skipped(tmp_path: Path):
    specs = _feature(tmp_path, entry={"status": "skipped"}, reports={})
    assert _outcome(specs, "verify") == "skipped"


def test_verify_failed_signal(tmp_path: Path):
    """`failed` is an operational failure — a runtime fact disk cannot record."""
    specs = _feature(tmp_path, entry={"status": "pending"}, reports={})
    assert _outcome(specs, "verify", "--op-failure") == "failed"


def test_every_verify_outcome_is_reachable(tmp_path: Path):
    """The union of the verify fixtures IS the whole VerifyOutcome enum."""
    reached = set()
    specs = _feature(tmp_path, entry={"status": "passed"},
                     reports={"VERIFY-tech-2026-09-07.md": _CLEAN_REPORT})
    reached.add(_outcome(specs, "verify"))
    specs = _feature(tmp_path, entry={"status": "findings-reported"},
                     reports={"VERIFY-tech-2026-09-07.md": _BLOCKING_REPORT})
    reached.add(_outcome(specs, "verify"))
    specs = _feature(tmp_path, entry={"status": "skipped"}, reports={})
    reached.add(_outcome(specs, "verify"))
    reached.add(_outcome(specs, "verify", "--op-failure"))
    assert reached == set(get_args(SESSION.VerifyOutcome))


# --------------------------------------------------------------------------------------
# Fixtures (scope 3) — forge-fix: every FixOutcome
# --------------------------------------------------------------------------------------


def test_fix_no_findings_empty(tmp_path: Path):
    specs = _feature(tmp_path, entry={"status": "passed"}, reports={})
    assert _outcome(specs, "fix") == "no-findings"


def test_fix_applied(tmp_path: Path):
    specs = _feature(
        tmp_path,
        entry={"status": "findings-applied", "findingsCount": 2},
        reports={"VERIFY-tech-2026-09-07.md": _BLOCKING_REPORT + _FIX_PROGRESS_FIXED},
    )
    assert _outcome(specs, "fix") == "applied"


def test_fix_applied_when_sweep_is_all_false_positive(tmp_path: Path):
    """The issue's ambiguous case: findings text present but every survivor is a
    FALSE-POSITIVE. Disposition is not a failure — the entry is findings-applied, so
    the outcome is `applied`, never `failed`."""
    specs = _feature(
        tmp_path,
        entry={"status": "findings-applied", "findingsCount": 2},
        reports={"VERIFY-tech-2026-09-07.md": _BLOCKING_REPORT + _FIX_PROGRESS_FALSE_POSITIVE},
    )
    assert _outcome(specs, "fix") == "applied"


def test_fix_reverified(tmp_path: Path):
    """Fixes applied, then a re-verify recorded `passed` → reverified."""
    specs = _feature(
        tmp_path,
        entry={"status": "passed", "findingsCount": 0},
        reports={
            "VERIFY-tech-2026-09-07.md": _BLOCKING_REPORT + _FIX_PROGRESS_FIXED,
            "VERIFY-tech-2026-09-07-round2.md": _CLEAN_REPORT,
        },
    )
    assert _outcome(specs, "fix") == "reverified"


def test_fix_reverify_findings_on_scoped_subset(tmp_path: Path):
    """The issue's other ambiguous case: a re-verify reopens blocking findings on a
    scoped subset. A round-2 findings report post-dates the fix's Fix Progress and the
    entry is back to findings-reported → reverify-findings."""
    specs = _feature(
        tmp_path,
        entry={"status": "findings-reported", "findingsCount": 1},
        reports={
            "VERIFY-tech-2026-09-07.md": _BLOCKING_REPORT + _FIX_PROGRESS_FIXED,
            "VERIFY-tech-2026-09-07-round2.md": _BLOCKING_REPORT,
        },
    )
    assert _outcome(specs, "fix") == "reverify-findings"


def test_fix_deferred_signal(tmp_path: Path):
    specs = _feature(
        tmp_path,
        entry={"status": "findings-applied"},
        reports={"VERIFY-tech-2026-09-07.md": _BLOCKING_REPORT + _FIX_PROGRESS_FIXED},
    )
    assert _outcome(specs, "fix", "--user-deferred") == "deferred"


def test_fix_decisions_signal(tmp_path: Path):
    specs = _feature(
        tmp_path,
        entry={"status": "findings-reported"},
        reports={"VERIFY-tech-2026-09-07.md": _BLOCKING_REPORT},
    )
    assert _outcome(specs, "fix", "--decisions-open") == "decisions"


def test_fix_failed_signal(tmp_path: Path):
    specs = _feature(
        tmp_path,
        entry={"status": "findings-reported"},
        reports={"VERIFY-tech-2026-09-07.md": _BLOCKING_REPORT},
    )
    assert _outcome(specs, "fix", "--op-failure") == "failed"


def test_every_fix_outcome_is_reachable(tmp_path: Path):
    """The union of the fix fixtures IS the whole FixOutcome enum."""
    reached = set()
    reached.add(_outcome(_feature(tmp_path, entry={"status": "passed"}, reports={}), "fix"))
    reached.add(_outcome(
        _feature(tmp_path, entry={"status": "findings-applied"},
                 reports={"VERIFY-tech-2026-09-07.md": _BLOCKING_REPORT + _FIX_PROGRESS_FIXED}),
        "fix"))
    reached.add(_outcome(
        _feature(tmp_path, entry={"status": "passed"},
                 reports={"VERIFY-tech-2026-09-07.md": _BLOCKING_REPORT + _FIX_PROGRESS_FIXED,
                          "VERIFY-tech-2026-09-07-round2.md": _CLEAN_REPORT}),
        "fix"))
    reached.add(_outcome(
        _feature(tmp_path, entry={"status": "findings-reported"},
                 reports={"VERIFY-tech-2026-09-07.md": _BLOCKING_REPORT + _FIX_PROGRESS_FIXED,
                          "VERIFY-tech-2026-09-07-round2.md": _BLOCKING_REPORT}),
        "fix"))
    base = _feature(tmp_path, entry={"status": "findings-applied"},
                    reports={"VERIFY-tech-2026-09-07.md": _BLOCKING_REPORT + _FIX_PROGRESS_FIXED})
    reached.add(_outcome(base, "fix", "--user-deferred"))
    reached.add(_outcome(base, "fix", "--decisions-open"))
    reached.add(_outcome(base, "fix", "--op-failure"))
    assert reached == set(get_args(SESSION.FixOutcome))


# --------------------------------------------------------------------------------------
# Fail-closed and validation
# --------------------------------------------------------------------------------------


def test_verify_fails_closed_when_no_terminal_result(tmp_path: Path):
    """A pending/absent verify entry with no --op-failure is exit-2, never a guess."""
    specs = _feature(tmp_path, entry={"status": "pending"}, reports={})
    result = _run(specs, "verify")
    assert result.returncode == 2
    assert "no terminal result" in result.stderr


def test_fix_fails_closed_on_unfixed_findings(tmp_path: Path):
    """findings-reported with no fixes applied and no signal is exit-2, never a guess."""
    specs = _feature(
        tmp_path,
        entry={"status": "findings-reported"},
        reports={"VERIFY-tech-2026-09-07.md": _BLOCKING_REPORT},
    )
    result = _run(specs, "fix")
    assert result.returncode == 2
    assert "findings-reported" in result.stderr


def test_verify_rejects_fix_only_signals(tmp_path: Path):
    specs = _feature(tmp_path, entry={"status": "passed"},
                     reports={"VERIFY-tech-2026-09-07.md": _CLEAN_REPORT})
    result = _run(specs, "verify", "--user-deferred")
    assert result.returncode == 2
    assert "forge-fix signals" in result.stderr


def test_docs_and_epic_served_stages_are_rejected(tmp_path: Path):
    """The verb serves only the five verify-token stages; forge-6-docs/forge-0-epic
    are not even in the argparse `choices`."""
    specs = _feature(tmp_path, entry={"status": "passed"}, reports={})
    for stage in ("forge-6-docs", "forge-0-epic"):
        result = subprocess.run(
            [sys.executable, str(HELPER), "select-outcome", "--feature", "feat",
             "--served-stage", stage, "--skill", "verify", "--specs-dir", str(specs)],
            capture_output=True, text=True,
        )
        assert result.returncode == 2
        assert "invalid choice" in result.stderr.lower()


def test_evidence_is_always_present(tmp_path: Path):
    """Every derivation carries its on-disk evidence for the operator to audit."""
    specs = _feature(tmp_path, entry={"status": "findings-reported", "findingsCount": 2},
                     reports={"VERIFY-tech-2026-09-07.md": _BLOCKING_REPORT})
    payload = json.loads(_run(specs, "verify").stdout)
    assert payload["reason"]
    assert any("forge-verify-tech status" in e for e in payload["evidence"])
    assert any(re.search(r"\d+ blocking", e) for e in payload["evidence"])
