"""Guards for the impl-verify runnability check (#135, fixes #121).

Locks the wiring of the optional `smokeCommand` config field and the two new
Runnability checklist items (CHECK-I21 smoke + CHECK-I22 non-test-caller):

- the schema declares `smokeCommand` as `string|null`, default `null`, and keeps it
  distinct from `testCommand` and `loopRunner.runCommand`;
- `forge-init.sh` emits `smokeCommand: null` (the parity tests already assert the whole
  field set — this pins the specific default);
- the impl checklist grows a **Runnability** section with CHECK-I21 and CHECK-I22 that
  degrade gracefully (advisory / not-applicable, never a hard fail);
- `forge-verify` SKILL.md's impl mode total and dimension list are updated.

Stdlib-only so it runs under bare `pytest tests` / CI's gate.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA = REPO_ROOT / "references" / "forge-config-schema.json"
FORGE_INIT = REPO_ROOT / "scripts" / "forge-init.sh"
CHECKLISTS = REPO_ROOT / "skills" / "forge-verify" / "references" / "verification-checklists.md"
VERIFY_SKILL = REPO_ROOT / "skills" / "forge-verify" / "SKILL.md"


def _forge_init_config() -> dict:
    text = FORGE_INIT.read_text(encoding="utf-8")
    marker = "<< 'EOF'\n"
    start = text.index(marker) + len(marker)
    end = text.index("\nEOF", start)
    return json.loads(text[start:end])


def test_schema_declares_smoke_command_string_or_null_default_null() -> None:
    props = json.load(SCHEMA.open(encoding="utf-8"))["properties"]
    assert "smokeCommand" in props, "smokeCommand missing from config schema"
    smoke = props["smokeCommand"]
    assert smoke["type"] == ["string", "null"], smoke["type"]
    assert smoke["default"] is None, smoke["default"]


def test_smoke_command_is_distinct_from_test_and_run_command() -> None:
    """The description must call out that it is NOT testCommand / loopRunner.runCommand."""
    desc = json.load(SCHEMA.open(encoding="utf-8"))["properties"]["smokeCommand"]["description"]
    assert "testCommand" in desc
    assert "runCommand" in desc


def test_forge_init_emits_smoke_command_null() -> None:
    assert _forge_init_config().get("smokeCommand", "MISSING") is None


def test_checklist_has_runnability_section_with_i21_i22() -> None:
    text = CHECKLISTS.read_text(encoding="utf-8")
    assert "### Runnability" in text
    assert "**CHECK-I21**" in text
    assert "**CHECK-I22**" in text


def test_runnability_checks_degrade_gracefully() -> None:
    """CHECK-I21/I22 must be advisory (not-applicable), never a hard fail, and completion-only."""
    text = CHECKLISTS.read_text(encoding="utf-8")
    runnability = text.split("### Runnability", 1)[1].split("## Epic Mode Checklist", 1)[0]
    lowered = runnability.lower()
    assert "not-applicable" in lowered
    assert "never a hard fail" in lowered
    assert "never mid-loop" in lowered
    # I21 keys off a configured smokeCommand; I22 excludes test-only call sites.
    assert "smokeCommand" in runnability
    assert "non-test" in runnability


def test_verify_skill_impl_total_and_dimension_updated() -> None:
    text = VERIFY_SKILL.read_text(encoding="utf-8")
    assert "impl: ~23 checks" in text
    assert "impl ~23" in text
    assert "runnability" in text.lower()
