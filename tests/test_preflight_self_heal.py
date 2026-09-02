"""Guard: the Preflight & Self-Heal procedure and its wiring into forge-5-loop 1c/1d.

PROTECTS:
  1. `references/preflight-and-self-heal.md` exists, carries all seven step headings, and
     shares the recovery procedure's failure-rule vocabulary (one failure rule, one home
     for the "decision-record" mechanism — never re-implemented here).
  2. forge-5-loop's condensed 1c/1d cites the reference and every `--check` id the gate
     runs, keeps the load-bearing anchors (`HARD GATE FAILURE`, `installHint`,
     `setupHint`, the two heading strings, the "(1c/1d)" cross-reference, the 1c Gotcha),
     and never regrows past its pre-P1 size (INV-7).
  3. `## Remedy Safety Ladder` (`references/shared-conventions.md`) states all four tiers
     with the never-execute wording the `global-install`/`network` rows depend on.
  4. The reference's stated clustering rule matches `cluster_checks`'s actual contract
     (`scripts/forge-session.py`) — a prose/code split is only safe while the two agree.
  5. This guard cannot be skipped or disabled.

NON-GOALS:
  - Exact-markdown fidelity beyond the tokens above.
  - Runtime behavior of the gate (no harness here to execute a skill against a fixture;
    that is the live headless smoke in `plans/federated-bubbling-micali.md`).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Final

import pytest

from _forge_paths import REFERENCES, SKILLS, read

PREFLIGHT: Final[Path] = REFERENCES / "preflight-and-self-heal.md"
SHARED_CONVENTIONS: Final[Path] = REFERENCES / "shared-conventions.md"
FORGE_5_LOOP: Final[Path] = SKILLS / "forge-5-loop" / "SKILL.md"
RECOVERY_PROCEDURE: Final[Path] = SKILLS / "forge-5-loop" / "references" / "recovery-procedure.md"
HELPER: Final[Path] = REFERENCES.parent / "scripts" / "forge-session.py"

#: The seven ordered step headings the procedure promises (§2 of the reference).
STEP_HEADINGS: Final[tuple[str, ...]] = (
    "### Step 1 — Enumerate",
    "### Step 2 — Cluster",
    "### Step 3 — Consolidated prompts",
    "### Step 4 — Record",
    "### Step 5 — Apply",
    "### Step 6 — Prove",
    "### Step 7 — Return",
)

#: Failure-rule vocabulary the reference must share with recovery-procedure.md §1 — the
#: same failure semantics, restated for a remedy instead of a runner-answer/unblock apply.
FAILURE_RULE_TOKENS: Final[tuple[str, ...]] = ("verbatim", "STOPS", "never reported as")

#: The four `--check` ids the condensed 1c/1d gate must still name explicitly (never a
#: glob — an advisory check must never block a launch it has no bearing on).
GATE_CHECK_IDS: Final[tuple[str, ...]] = (
    "runner-binary", "runner-version", "runner-wired", "runner-legacy-layout",
)

#: Anchors the condensation must not disturb — other prose (the Gotchas list, the
#: 1b-epic ordering note) points at these by literal string, not by line number.
REQUIRED_ANCHORS: Final[tuple[str, ...]] = (
    "### 1c. Runner Version Gate",
    "### 1d. Runner Setup Check (precondition file)",
    "(1c/1d)",
    "The version gate (1c) uses the `--json` form",
)

#: Procedural detail P1 moves out of the skill body — the numeric compare is now the
#: check's job (`_check_runner_version`), not something the skill narrates.
DROPPED_FROM_BODY: Final[tuple[str, ...]] = ("Semver-compare", "string-compare")


def _load_helper_module():
    """Import forge-session.py as a module (hyphenated filename → importlib)."""
    spec = importlib.util.spec_from_file_location("forge_session_preflight", HELPER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def fs():
    return _load_helper_module()


def _body_lines(text: str) -> list[str]:
    """Body lines after frontmatter, matching check-spec-purity.py's own split."""
    parts = text.split("---\n", 2)
    body = parts[2] if len(parts) >= 3 else text
    lines = body.replace("\r\n", "\n").split("\n")
    if lines and lines[-1] == "":
        lines = lines[:-1]
    return lines


def _slice_1c_to_1e(lines: list[str]) -> list[str]:
    start = next(i for i, line in enumerate(lines) if line.startswith("### 1c."))
    end = next(i for i, line in enumerate(lines) if line.startswith("### 1e."))
    return lines[start:end]


def test_reference_has_all_seven_step_headings() -> None:
    text = read(PREFLIGHT)
    missing = [h for h in STEP_HEADINGS if h not in text]
    assert not missing, (
        f"{PREFLIGHT.name} is missing step headings {missing} — the seven-step shape "
        "(recovery-procedure.md's proven precedent) is no longer intact"
    )


def test_reference_shares_failure_rule_tokens_with_recovery_procedure() -> None:
    preflight_text = read(PREFLIGHT)
    recovery_text = read(RECOVERY_PROCEDURE)
    for token in FAILURE_RULE_TOKENS:
        assert token in preflight_text, (
            f"{PREFLIGHT.name} § 1 dropped failure-rule token {token!r} — it must read "
            "the same as recovery-procedure.md's failure rule, narrowed to remedies"
        )
        assert token in recovery_text, (
            f"recovery-procedure.md no longer carries {token!r} — the shared vocabulary "
            "this guard pins has drifted at the source, not the copy"
        )


def test_reference_never_uses_decision_record_or_forge_decisions_json() -> None:
    text = read(PREFLIGHT)
    for banned in ("decision-record", "forge-decisions.json"):
        assert banned not in text, (
            f"{PREFLIGHT.name} mentions {banned!r} — preflight remedies are environment "
            "repair, not backlog decisions; recording one through the item-keyed backlog "
            "decision record would durably attribute an environment fix to a backlog "
            "item that never asked for it (§2 step 4)"
        )


def test_forge_5_loop_cites_reference_and_check_ids() -> None:
    body = "\n".join(_body_lines(read(FORGE_5_LOOP)))
    assert "references/preflight-and-self-heal.md" in body, (
        "forge-5-loop no longer cites the preflight reference — the bundle's fan-out "
        "depends on this literal citation (test_reference_citations.py)"
    )
    missing_ids = [check_id for check_id in GATE_CHECK_IDS if check_id not in body]
    assert not missing_ids, f"forge-5-loop 1c/1d no longer names --check ids: {missing_ids}"
    for retained in ("HARD GATE FAILURE", "installHint", "setupHint"):
        assert retained in body, f"forge-5-loop 1c/1d dropped required token {retained!r}"
    for dropped in DROPPED_FROM_BODY:
        assert dropped not in body, (
            f"forge-5-loop body still narrates {dropped!r} — the numeric compare moved "
            "into the runner-version check itself (scripts/forge-session.py), the skill "
            "body should not re-describe it"
        )


def test_1c_to_1e_slice_did_not_regrow() -> None:
    lines = _slice_1c_to_1e(_body_lines(read(FORGE_5_LOOP)))
    n_lines = len(lines)
    n_words = sum(len(line.split()) for line in lines)
    assert n_lines <= 26, f"1c→1e slice grew to {n_lines} lines (was 26 pre-P1)"
    assert n_words <= 329, f"1c→1e slice grew to {n_words} words (was 329 pre-P1)"


def test_body_within_caps() -> None:
    lines = _body_lines(read(FORGE_5_LOOP))
    n_lines = len(lines)
    n_words = sum(len(line.split()) for line in lines)
    assert n_lines <= 300, f"forge-5-loop body is {n_lines} lines, over the 300 cap"
    assert n_words <= 5000, f"forge-5-loop body is {n_words} words, over the 5000 cap"


def test_anchors_intact() -> None:
    body = "\n".join(_body_lines(read(FORGE_5_LOOP)))
    missing = [anchor for anchor in REQUIRED_ANCHORS if anchor not in body]
    assert not missing, (
        f"forge-5-loop dropped anchor(s) {missing} — other prose in this body (and the "
        "Gotchas entry) points at these by literal string, not by line number"
    )


def test_ladder_section_has_four_tiers_and_required_tokens() -> None:
    text = read(SHARED_CONVENTIONS)
    assert "## Remedy Safety Ladder" in text, (
        "shared-conventions.md has no '## Remedy Safety Ladder' section — the reference "
        "and every skill that applies a remedy's safety tier points at this title"
    )
    section = text.split("## Remedy Safety Ladder", 1)[1].split("\n## ", 1)[0]
    for tier in ("read-only", "local-write", "global-install", "network"):
        assert f"`{tier}`" in section, f"Remedy Safety Ladder is missing the {tier!r} tier"
    assert section.lower().count("advise-only") >= 2, (
        "the global-install and network rows must both say 'advise-only' — that word is "
        "what a consumer greps for to know a remedy is never executed"
    )
    assert "never" in section.lower()
    assert "stricter" in section, (
        "the ladder must state the 'degrade one tier stricter when unaskable' rule"
    )


def test_cluster_checks_semantics_match_reference_description(fs) -> None:
    """The reference's Step 2 description of `cluster_checks` must hold in code.

    A prose/code split (the reference *describes* the function instead of
    re-implementing it) is only safe while the two agree — this is the cross-check.
    """

    def record(check_id: str, status: str, remedy: dict | None) -> dict:
        return {"id": check_id, "status": status, "severity": "blocking", "detail": "",
                "evidence": {}, "remedy": remedy}

    healthy = record("check-ok", "ok", None)
    no_fix = record("check-null-remedy", "warn", None)
    wired = record(
        "runner-wired", "warn",
        {"description": "wire it", "command": "rauf install .", "safety": "local-write"},
    )
    legacy = record(
        "runner-legacy-layout", "warn",
        {"description": "migrate", "command": "rauf install .", "safety": "global-install"},
    )
    advice_only = record(
        "runner-version", "warn",
        {"description": "advice only", "command": None, "safety": "network"},
    )

    clusters = fs.cluster_checks([healthy, no_fix, wired, legacy, advice_only])

    all_check_ids = {cid for cluster in clusters for cid in cluster["checkIds"]}
    # remedy: null is never clustered (report-only, no prompt to build) — neither is a
    # remedy with no command (description-only advice).
    assert "check-ok" not in all_check_ids
    assert "check-null-remedy" not in all_check_ids
    assert "runner-version" not in all_check_ids
    # identical remedy.command merges into exactly one cluster.
    assert len(clusters) == 1
    merged = clusters[0]
    assert merged["command"] == "rauf install ."
    assert set(merged["checkIds"]) == {"runner-wired", "runner-legacy-layout"}
    # the merge's safety is the most conservative member tier.
    assert merged["safety"] == "global-install"


def test_this_guard_is_not_skippable() -> None:
    """No skip gate may be introduced here — an unskippable guard is the whole point."""
    source = read(Path(__file__).resolve())
    for banned in ("skipif", "importorskip", "pytest.skip"):
        assert f"{banned}(" not in source, f"{banned} gate introduced in the drift guard"
