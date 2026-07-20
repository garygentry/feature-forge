"""Guards for the dev-runtime smoke guidance + heavy-bootstrap heuristic (#149, follow-up to #121).

Batch C is guidance + heuristic lint only — no runtime-health/CPU monitor. These content guards
lock the prose so a future edit can't silently drop the checks or turn an advisory heuristic into
a hard fail:

- CHECK-I21 prose recommends exercising the **dev runtime** and re-verifying a fix in the mode the
  bug manifested (module-graph-identity / watch-loop failure modes a prod smoke hides);
- a new **CHECK-I23** flags a heavy init wired into a universal bootstrap entry and stays advisory /
  not-applicable, keying off the stack profile's bootstrap-wiring list;
- every stack profile carries a **Runtime Entrypoints & Bootstrap-Wiring Sites** section that
  CHECK-I22 and CHECK-I23 both reference;
- the `forge-verify` impl mode total reflects the new check.

Stdlib-only so it runs under bare `pytest tests` / CI's gate.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKLISTS = REPO_ROOT / "skills" / "forge-verify" / "references" / "verification-checklists.md"
VERIFY_SKILL = REPO_ROOT / "skills" / "forge-verify" / "SKILL.md"
STACKS_DIR = REPO_ROOT / "references" / "stacks"
STACK_PROFILES = ["typescript", "python", "go", "rust", "_generic"]


def _runnability() -> str:
    text = CHECKLISTS.read_text(encoding="utf-8")
    return text.split("### Runnability", 1)[1].split("## Epic Mode Checklist", 1)[0]


def test_i21_prose_recommends_dev_runtime_and_fix_mode_reverify() -> None:
    lowered = _runnability().lower()
    assert "dev runtime" in lowered
    # the two failure modes a static typecheck + prod smoke both hide
    assert "module-graph-identity" in lowered
    assert "watch-loop" in lowered
    # a fix must be re-verified in the runtime mode the bug manifested
    assert "same runtime mode where the original bug" in lowered


def test_i23_present_and_advisory() -> None:
    runnability = _runnability()
    assert "**CHECK-I23**" in runnability
    i23 = runnability.split("**CHECK-I23**", 1)[1]
    lowered = i23.lower()
    assert "never" in lowered and "hard fail" in lowered
    assert "not-applicable" in lowered
    assert "lazy" in lowered
    # it identifies bootstrap entries via the stack profile section
    assert "Runtime Entrypoints & Bootstrap-Wiring Sites" in i23


def test_every_stack_profile_has_bootstrap_wiring_section() -> None:
    for name in STACK_PROFILES:
        text = (STACKS_DIR / f"{name}.md").read_text(encoding="utf-8")
        assert "Runtime Entrypoints & Bootstrap-Wiring Sites" in text, name
        lowered = text.lower()
        # both the CHECK-I22 (runtime entrypoint) and CHECK-I23 (universal bootstrap) roles
        assert "runtime entrypoints" in lowered, name
        assert "universal bootstrap" in lowered, name


def test_verify_skill_impl_total_bumped() -> None:
    text = VERIFY_SKILL.read_text(encoding="utf-8")
    assert "impl: ~23 checks" in text
    assert "impl ~23" in text
