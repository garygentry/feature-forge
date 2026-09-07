"""Tests for ``forge-session.py verify-state`` (issue #277, #265 P3.2).

`verify-state` collapses the three hand-rolled reads of a served stage's
`stages.forge-verify-*` entry — forge-4-backlog's binary specs check, forge-5-loop's
four-case backlog check, forge-6-docs's five-case impl backstop — into one
deterministic verb: one `VerifyStateCase`, one message table, the same "never
eyeball the graph" move `select-outcome` makes for the exit outcome. Three guards
live here:

- **Parity (scope 2).** The enum is the union of the cases the three gates spell
  out. `test_enum_covers_every_case_the_gates_spell_out` greps the enumerating gate
  sections for the raw verify statuses they key on, maps each through the same
  status→case contract the verb applies, and asserts the union (plus the `never`
  fallback every gate carries) IS the whole enum — both ways, so neither the enum nor
  the gates can grow or drop a case without the other.

- **Fixtures (scope 3).** Every enum value is reached from an on-disk fixture.
  `test_every_case_is_reachable` asserts the union of reached cases IS the full enum —
  a new case added without a fixture fails here.

- **Structure.** One message per case, `nextCommand` present for every unresolved
  case and absent for `passed`, and a fail-safe (missing/torn state → `never`).
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Final, get_args

REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER = REPO_ROOT / "scripts" / "forge-session.py"
SKILLS = REPO_ROOT / "skills"


def _load_session_module():
    """Import `forge-session.py` by path (its name is hyphenated, so unimportable)."""
    spec = importlib.util.spec_from_file_location("forge_session_verify_state", HELPER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SESSION = _load_session_module()

#: The status→case contract the verb applies, restated here as the parity anchor.
#: Every KNOWN verify status maps to exactly one `VerifyStateCase`: the five result
#: statuses to themselves, and `pending` to `never` (the absent/unresolved bucket the
#: gates collapse to "not verified"). If the verb's classification and this map ever
#: disagree, the reachability fixtures below catch it — this map only pins what the
#: gate prose is allowed to key on.
STATUS_TO_CASE: Final[dict[str, str]] = {
    "passed": "passed",
    "findings-reported": "findings-reported",
    "findings-applied": "findings-applied",
    "auto-verify-pending": "auto-verify-pending",
    "skipped": "skipped",
    "pending": "never",
}


# --------------------------------------------------------------------------------------
# Parity (scope 2) — the enum is exactly what the three gates spell out
# --------------------------------------------------------------------------------------


def _section(skill: str, heading: str) -> str:
    """Return a skill body's ``### {heading}`` section, up to the next ``###``/``##``."""
    text = (SKILLS / f"forge-{skill}" / "SKILL.md").read_text(encoding="utf-8")
    lines = text.replace("\r\n", "\n").split("\n")
    body: list[str] = []
    inside = False
    for line in lines:
        if line.startswith("### ") or line.startswith("## "):
            if inside:
                break
            inside = line.startswith("### ") and line[4:].strip() == heading
            continue
        if inside:
            body.append(line)
    assert body, f"no '### {heading}' section parsed from forge-{skill}/SKILL.md"
    return "\n".join(body)


def _verify_statuses_in(text: str) -> set[str]:
    """The backtick-quoted KNOWN verify statuses a gate section keys on.

    The backtick requirement is deliberate, not incidental. A status the gate keys on
    is written as a `code` literal; matching bare words would over-match ("verification
    passed" is prose, not the `passed` case) and let the union read full even when a
    case was quietly dropped — a false GREEN, the failure a parity guard exists to
    prevent. The cost is the opposite, benign failure: rewording a `status` literal to
    unquoted prose fails this guard even though the verb is unchanged. That RED is the
    intended prompt — re-quote the status, or, if the gate genuinely stopped covering a
    case, update `VerifyStateCase` to match. Fail-safe over convenient.
    """
    quoted = set(re.findall(r"`([a-z-]+)`", text))
    return quoted & SESSION.KNOWN_VERIFY_STATUSES


#: The two gates that enumerate cases by status (forge-4 is binary, tested below).
_ENUMERATING_GATES: Final[tuple[tuple[str, str], ...]] = (
    ("5-loop", "1b. Verification Check"),
    ("6-docs", "Impl-Verify Backstop"),
)


def test_every_gate_status_is_a_case_the_verb_handles():
    """Every raw verify status the enumerating gates key on maps to a `VerifyStateCase`."""
    cases = set(get_args(SESSION.VerifyStateCase))
    for skill, heading in _ENUMERATING_GATES:
        for status in _verify_statuses_in(_section(skill, heading)):
            assert status in STATUS_TO_CASE, (
                f"forge-{skill} § {heading} keys on `{status}`, which the verb's "
                "status→case contract does not map"
            )
            assert STATUS_TO_CASE[status] in cases, (
                f"forge-{skill} § {heading} keys on `{status}` → "
                f"{STATUS_TO_CASE[status]!r}, absent from VerifyStateCase"
            )


def test_enum_covers_every_case_the_gates_spell_out():
    """The enum IS the union of the gate cases — both directions.

    Reached = every gate status mapped through the contract, plus `never` (the
    absent/not-verified fallback every gate carries, asserted separately below).
    """
    reached = {"never"}
    for skill, heading in _ENUMERATING_GATES:
        reached |= {STATUS_TO_CASE[s] for s in _verify_statuses_in(_section(skill, heading))}
    assert reached == set(get_args(SESSION.VerifyStateCase)), (
        "VerifyStateCase and the gate prose have diverged: "
        f"only the gates -> {reached - set(get_args(SESSION.VerifyStateCase))}, "
        f"only the enum -> {set(get_args(SESSION.VerifyStateCase)) - reached}"
    )


def test_all_three_gates_carry_a_not_verified_fallback():
    """`never` is legitimate because all three gates have an absent/not-verified branch.

    Includes forge-4-backlog, whose gate is a binary verified/not read that names no
    intermediate status — so its `never` branch is what puts it among the three.
    """
    backlog = (SKILLS / "forge-4-backlog" / "SKILL.md").read_text(encoding="utf-8")
    assert "haven't been verified" in backlog, (
        "forge-4-backlog's binary verification check is gone; the enum docstring's "
        "'three gates' claim is now stale"
    )
    assert "absent" in _section("5-loop", "1b. Verification Check").lower()
    assert "absent" in _section("6-docs", "Impl-Verify Backstop").lower()


def test_the_synopsis_documents_verify_state():
    """The module docstring (argparse `description`, i.e. `--help`) names the verb."""
    doc = SESSION.__doc__ or ""
    assert "verify-state --feature F --for-stage S" in doc


def test_one_message_per_case():
    """The message table enumerates exactly the enum — one canonical sentence each."""
    assert set(SESSION.VERIFY_STATE_MESSAGES) == set(get_args(SESSION.VerifyStateCase))


# --------------------------------------------------------------------------------------
# Fixture harness
# --------------------------------------------------------------------------------------


def _feature(tmp_path: Path, *, entry: dict | None, stage_version: int = 1) -> Path:
    """Build a specs dir with one feature carrying (or not) a forge-verify-backlog entry."""
    specs = tmp_path / "specs"
    feat = specs / "feat"
    feat.mkdir(parents=True, exist_ok=True)
    stages: dict = {"forge-4-backlog": {"status": "complete", "version": stage_version}}
    if entry is not None:
        stages["forge-verify-backlog"] = entry
    (feat / ".pipeline-state.json").write_text(
        json.dumps({"pipelineStatus": "active", "stages": stages})
    )
    return specs


def _run(specs: Path, *flags: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HELPER), "verify-state", "--feature", "feat",
         "--for-stage", "forge-4-backlog", "--specs-dir", str(specs), "--json", *flags],
        capture_output=True, text=True,
    )


def _payload(specs: Path, *flags: str) -> dict:
    result = _run(specs, *flags)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


# --------------------------------------------------------------------------------------
# Fixtures (scope 3) — every VerifyStateCase
# --------------------------------------------------------------------------------------


def test_case_passed(tmp_path: Path):
    p = _payload(_feature(tmp_path, entry={"status": "passed"}))
    assert p["case"] == "passed"
    assert p["verified"] is True and p["stale"] is False
    assert p["nextCommand"] is None  # resolved-clean: no action


def test_case_findings_reported(tmp_path: Path):
    p = _payload(_feature(tmp_path, entry={"status": "findings-reported"}))
    assert p["case"] == "findings-reported"
    assert p["verified"] is False and p["stale"] is False
    assert p["nextCommand"] == "/feature-forge:forge-verify feat backlog"


def test_case_findings_applied_is_stale(tmp_path: Path):
    """Applying fixes is not verifying them — findings-applied is `stale`, re-verify owed."""
    p = _payload(_feature(tmp_path, entry={"status": "findings-applied"}))
    assert p["case"] == "findings-applied"
    assert p["verified"] is False and p["stale"] is True
    assert p["nextCommand"]


def test_case_auto_verify_pending(tmp_path: Path):
    entry = {"status": "auto-verify-pending", "scheduledStageVersion": 1}
    p = _payload(_feature(tmp_path, entry=entry))
    assert p["case"] == "auto-verify-pending"
    assert p["verified"] is False and p["stale"] is False


def test_case_skipped(tmp_path: Path):
    p = _payload(_feature(tmp_path, entry={"status": "skipped"}))
    assert p["case"] == "skipped"
    assert p["verified"] is False  # an explicit skip is resolved, but NOT verified


def test_case_never_when_absent(tmp_path: Path):
    p = _payload(_feature(tmp_path, entry=None))
    assert p["case"] == "never"
    assert p["verified"] is False and p["stale"] is False


def test_every_case_is_reachable(tmp_path: Path):
    """The union of the fixtures IS the whole VerifyStateCase enum."""
    reached = set()
    for entry in (
        {"status": "passed"},
        {"status": "findings-reported"},
        {"status": "findings-applied"},
        {"status": "auto-verify-pending", "scheduledStageVersion": 1},
        {"status": "skipped"},
        None,
    ):
        reached.add(_payload(_feature(tmp_path, entry=entry))["case"])
    assert reached == set(get_args(SESSION.VerifyStateCase))


# --------------------------------------------------------------------------------------
# Behavioural detail and fail-safe
# --------------------------------------------------------------------------------------


def test_pending_is_never_and_stays_quiet(tmp_path: Path):
    """A known `pending` (generic/manual pending, not a result) is `never`, no warning."""
    result = _run(_feature(tmp_path, entry={"status": "pending"}))
    assert result.returncode == 0
    assert json.loads(result.stdout)["case"] == "never"
    assert result.stderr == ""


def test_unknown_status_warns_and_is_never(tmp_path: Path):
    """An out-of-vocabulary status is flagged once (#148) then treated as `never`."""
    result = _run(_feature(tmp_path, entry={"status": "findings-resolved"}))
    assert result.returncode == 0
    assert json.loads(result.stdout)["case"] == "never"
    assert "unknown" in result.stderr and "findings-resolved" in result.stderr


def test_auto_pending_missing_schedule_warns_but_stays_owed(tmp_path: Path):
    """Unusable scheduling metadata warns (REQ-DEBT-02) yet never downgrades the debt."""
    result = _run(_feature(tmp_path, entry={"status": "auto-verify-pending"}))
    assert json.loads(result.stdout)["case"] == "auto-verify-pending"
    assert "scheduledStageVersion" in result.stderr


def test_auto_pending_message_names_the_version_advance(tmp_path: Path):
    """When the artifact moved since the debt was scheduled, the message says so."""
    specs = _feature(
        tmp_path,
        entry={"status": "auto-verify-pending", "scheduledStageVersion": 1},
        stage_version=3,
    )
    p = _payload(specs)
    assert "scheduled at revision 1, now at revision 3" in p["message"]


def test_missing_state_is_never_not_an_error(tmp_path: Path):
    """No feature dir at all → `never`, the same fail-safe the three gates take."""
    p = _payload(tmp_path / "does-not-exist" / "specs")
    assert p["case"] == "never"


def test_docs_and_epic_stages_are_rejected(tmp_path: Path):
    """`--for-stage` serves only the five verify-token stages (argparse `choices`)."""
    specs = _feature(tmp_path, entry={"status": "passed"})
    for stage in ("forge-6-docs", "forge-0-epic"):
        result = subprocess.run(
            [sys.executable, str(HELPER), "verify-state", "--feature", "feat",
             "--for-stage", stage, "--specs-dir", str(specs)],
            capture_output=True, text=True,
        )
        assert result.returncode == 2
        assert "invalid choice" in result.stderr.lower()


def test_epic_member_resolves_nested(tmp_path: Path):
    """`--epic` reads the nested `{specsDir}/{epic}/{feature}` layout."""
    specs = tmp_path / "specs"
    feat = specs / "big-epic" / "feat"
    feat.mkdir(parents=True)
    (feat / ".pipeline-state.json").write_text(
        json.dumps({"stages": {"forge-verify-backlog": {"status": "passed"}}})
    )
    result = subprocess.run(
        [sys.executable, str(HELPER), "verify-state", "--feature", "feat",
         "--for-stage", "forge-4-backlog", "--epic", "big-epic",
         "--specs-dir", str(specs), "--json"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["case"] == "passed"
