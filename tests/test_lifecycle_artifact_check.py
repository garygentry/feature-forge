"""Guards for the contradictory-lifecycle backlog heuristic (#150).

Batch C is guidance + heuristic lint only — forge tracks no artifact-lifecycle model. These
content guards lock the prose so a future edit can't silently drop the check or turn the advisory
heuristic into a hard fail:

- a new **CHECK-B27** flags a test item forcing a lifecycle transition another item forbids,
  keyword/artifact-name based and advisory / not-applicable;
- `forge-4-backlog` carries matching authoring guidance citing CHECK-B27;
- the `forge-verify` backlog mode total reflects the new check.

Stdlib-only so it runs under bare `pytest tests` / CI's gate.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKLISTS = REPO_ROOT / "skills" / "forge-verify" / "references" / "verification-checklists.md"
VERIFY_SKILL = REPO_ROOT / "skills" / "forge-verify" / "SKILL.md"
FORGE4 = REPO_ROOT / "skills" / "forge-4-backlog" / "SKILL.md"


def test_b27_present_and_advisory() -> None:
    text = CHECKLISTS.read_text(encoding="utf-8")
    assert "### Artifact Lifecycle Consistency" in text
    assert "**CHECK-B27**" in text
    backlog = text.split("### Artifact Lifecycle Consistency", 1)[1].split(
        "## Implementation Mode Checklist", 1
    )[0]
    lowered = backlog.lower()
    assert "not-applicable" in lowered
    assert "never" in lowered and "hard fail" in lowered
    # the fabrication risk and the two escape hatches (dependsOn a publisher, or fixture path)
    assert "fabricate" in lowered
    assert "dependson" in lowered
    assert "fixture" in lowered


def test_forge4_cites_b27_lifecycle_guidance() -> None:
    text = FORGE4.read_text(encoding="utf-8")
    assert "#150" in text
    assert "CHECK-B27" in text


def test_verify_skill_backlog_total_bumped() -> None:
    text = VERIFY_SKILL.read_text(encoding="utf-8")
    assert "backlog: ~27 checks" in text
    assert "backlog ~27" in text
