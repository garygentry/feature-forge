"""Tests for the auto-verify navigator support in ``forge-session.py``.

Covers the pure helpers (``auto_verify_for``, ``invalid_auto_verify_keys``,
``verify_state``) and the ``rank-features --json`` integration that surfaces the
effective ``autoVerify``/``autoFix`` per feature and the freshness ledger.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER = REPO_ROOT / "scripts" / "forge-session.py"
FORGE_INIT = REPO_ROOT / "scripts" / "forge-init.sh"


def _load_module():
    spec = importlib.util.spec_from_file_location("forge_session", HELPER)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


fs = _load_module()


def _write_state(specs_dir: Path, name: str, state: dict) -> None:
    feature = specs_dir / name
    feature.mkdir(parents=True, exist_ok=True)
    (feature / ".pipeline-state.json").write_text(json.dumps(state))


def _rank_proc(
    specs_dir: Path, config_path: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run ``rank-features --json`` and hand back the whole process result.

    ``_rank`` throws stderr away; the 03 §5.3 obligation sentence is emitted
    there (JSON stdout carries the three stable keys and no prose), so the
    diagnostic assertions need the raw result.
    """
    argv = [sys.executable, str(HELPER), "rank-features",
            "--specs-dir", str(specs_dir), "--json"]
    if config_path is not None:
        argv += ["--config", str(config_path)]
    return subprocess.run(argv, capture_output=True, text=True, cwd=str(specs_dir.parent))


def _rank(specs_dir: Path, config_path: Path | None = None) -> dict:
    """Run ``rank-features`` against a tmp specs tree, isolated from this repo.

    ``--config`` defaults to the RELATIVE ``./forge.config.json``, resolved against the
    child's cwd. Without ``cwd=``, the child inherits pytest's — the repo root — so a
    ``config_path=None`` call silently reads *this project's* real config instead of the
    intended "no config" state, and the assertions then depend on whatever the developer
    happens to have set locally (it was `autoVerify: true` that surfaced this). Anchor the
    child in the tmp tree so the default resolves to a nonexistent file and `_load_config`
    downgrades to ``{}``. ``tests/test_stage_exit.py::_exit`` already does this.
    """
    result = _rank_proc(specs_dir, config_path)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


# --------------------------------------------------------------------------- #
# forge-init.sh template
# --------------------------------------------------------------------------- #


def test_forge_init_template_carries_auto_verify_keys(tmp_path: Path) -> None:
    """A freshly ``forge-init``'d config carries the auto-verify keys explicitly.

    The template must ship ``autoVerify``/``autoVerifyStages``/``autoFix`` with
    off-by-default values so the setup-time opt-in (skills/forge-init) has a key
    to flip, and so ``rank-features`` reads a real value, not an implicit default.
    """
    result = subprocess.run(
        ["bash", str(FORGE_INIT)], cwd=tmp_path, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    config = json.loads((tmp_path / "forge.config.json").read_text())
    assert config["autoVerify"] is False
    assert config["autoVerifyStages"] == {}
    assert config["autoFix"] is False


# --------------------------------------------------------------------------- #
# auto_verify_for precedence
# --------------------------------------------------------------------------- #


def test_auto_verify_for_defaults_off() -> None:
    assert fs.auto_verify_for({}, "forge-1-prd") is False


def test_auto_verify_for_global_true() -> None:
    assert fs.auto_verify_for({"autoVerify": True}, "forge-2-tech") is True


def test_auto_verify_for_stage_override_wins() -> None:
    config = {"autoVerify": True, "autoVerifyStages": {"forge-1-prd": False}}
    assert fs.auto_verify_for(config, "forge-1-prd") is False
    assert fs.auto_verify_for(config, "forge-2-tech") is True


def test_auto_verify_for_stage_override_on_when_global_off() -> None:
    config = {"autoVerify": False, "autoVerifyStages": {"forge-5-loop": True}}
    assert fs.auto_verify_for(config, "forge-5-loop") is True
    assert fs.auto_verify_for(config, "forge-1-prd") is False


def test_auto_verify_for_string_false_fails_closed() -> None:
    """A truthy-but-not-True value (e.g. the string "false") must NOT enable.

    Regression for the Codex finding: ``bool("false")`` is True in Python, so
    strict identity parsing is required to fail closed on a hand-edited config.
    """
    assert fs.auto_verify_for({"autoVerify": "false"}, "forge-1-prd") is False
    assert fs.auto_verify_for({"autoVerify": "no"}, "forge-1-prd") is False
    assert fs.auto_verify_for({"autoVerify": 1}, "forge-1-prd") is False


def test_auto_verify_for_string_override_fails_closed() -> None:
    config = {"autoVerify": True, "autoVerifyStages": {"forge-1-prd": "false"}}
    assert fs.auto_verify_for(config, "forge-1-prd") is False
    # A literal true override still enables.
    assert fs.auto_verify_for({"autoVerifyStages": {"forge-1-prd": True}}, "forge-1-prd") is True


# --------------------------------------------------------------------------- #
# invalid_auto_verify_keys
# --------------------------------------------------------------------------- #


def test_invalid_keys_empty_when_all_known() -> None:
    config = {"autoVerifyStages": {"forge-1-prd": True, "forge-5-loop": False}}
    assert fs.invalid_auto_verify_keys(config) == []


def test_invalid_keys_flags_typos_and_docs() -> None:
    config = {"autoVerifyStages": {"forge-1-prod": True, "forge-6-docs": True}}
    assert set(fs.invalid_auto_verify_keys(config)) == {"forge-1-prod", "forge-6-docs"}


# --------------------------------------------------------------------------- #
# verify_state freshness ledger
# --------------------------------------------------------------------------- #


def _completed_prd_state(verify: dict | None) -> dict:
    stages = {"forge-1-prd": {"status": "complete", "version": 1}}
    if verify is not None:
        stages["forge-verify-prd"] = verify
    return {"pipelineStatus": "active", "stages": stages}


def test_verify_state_never_when_not_run() -> None:
    state = _completed_prd_state(None)
    assert fs.verify_state(state) == ("forge-1-prd", "never")


def test_verify_state_fresh_when_version_matches() -> None:
    state = _completed_prd_state({"status": "passed", "verifiedStageVersion": 1})
    assert fs.verify_state(state) == ("forge-1-prd", "fresh")


def test_verify_state_stale_when_version_moved() -> None:
    state = _completed_prd_state({"status": "passed", "verifiedStageVersion": 1})
    state["stages"]["forge-1-prd"]["version"] = 2  # artifact revised
    assert fs.verify_state(state) == ("forge-1-prd", "stale")


def test_verify_state_stale_when_legacy_no_version_field() -> None:
    state = _completed_prd_state({"status": "findings-applied"})  # no verifiedStageVersion
    assert fs.verify_state(state) == ("forge-1-prd", "stale")


def test_verify_state_failing_on_reported_findings() -> None:
    state = _completed_prd_state({"status": "findings-reported"})
    assert fs.verify_state(state) == ("forge-1-prd", "failing")


def test_verify_state_none_when_nothing_complete() -> None:
    state = {"pipelineStatus": "active", "stages": {}}
    assert fs.verify_state(state) == (None, "none")


def test_verify_state_skipped_is_resolved_not_pending() -> None:
    """An explicit skip (no verifiedStageVersion) stays skipped, never stale.

    Regression for the Codex finding: skip writers record only
    ``status: "skipped"``; the freshness check must not reclassify it as stale
    and re-surface a gate the user explicitly declined.
    """
    state = _completed_prd_state({"status": "skipped"})
    assert fs.verify_state(state) == ("forge-1-prd", "skipped")
    assert fs.pending_verify(state) is None


def test_verify_state_skipped_does_not_go_stale_on_revision() -> None:
    state = _completed_prd_state({"status": "skipped"})
    state["stages"]["forge-1-prd"]["version"] = 5  # artifact revised after the skip
    assert fs.verify_state(state) == ("forge-1-prd", "skipped")
    assert fs.pending_verify(state) is None


def test_pending_verify_false_only_when_fresh() -> None:
    fresh = _completed_prd_state({"status": "passed", "verifiedStageVersion": 1})
    assert fs.pending_verify(fresh) is None
    stale = _completed_prd_state({"status": "passed", "verifiedStageVersion": 1})
    stale["stages"]["forge-1-prd"]["version"] = 2
    assert fs.pending_verify(stale) == "forge-1-prd"


# --------------------------------------------------------------------------- #
# rank-features integration
# --------------------------------------------------------------------------- #


def test_rank_features_no_config_keys(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    _write_state(specs, "a", _completed_prd_state({"status": "passed", "verifiedStageVersion": 1}))
    row = _rank(specs)["active"][0]
    assert row["autoVerify"] is False
    assert row["autoFix"] is False
    assert row["verifyState"] == "fresh"
    assert row["verifyPending"] is False


def test_rank_features_auto_verify_true(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    _write_state(specs, "a", _completed_prd_state({"status": "findings-reported"}))
    config = tmp_path / "forge.config.json"
    config.write_text(json.dumps({"autoVerify": True}))
    row = _rank(specs, config)["active"][0]
    assert row["autoVerify"] is True
    assert row["verifyState"] == "failing"
    assert row["verifyPending"] is True


def test_rank_features_stage_override(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    _write_state(specs, "a", _completed_prd_state(None))  # prd never verified
    config = tmp_path / "forge.config.json"
    config.write_text(json.dumps({
        "autoVerify": True,
        "autoVerifyStages": {"forge-1-prd": False},
        "autoFix": True,
    }))
    row = _rank(specs, config)["active"][0]
    assert row["verifyStage"] == "forge-1-prd"
    assert row["autoVerify"] is False  # overridden off for this stage
    assert row["autoFix"] is False  # autoFix only honored when auto-verify on


def test_rank_features_auto_fix_honored_when_verify_on(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    _write_state(specs, "a", _completed_prd_state(None))
    config = tmp_path / "forge.config.json"
    config.write_text(json.dumps({"autoVerify": True, "autoFix": True}))
    row = _rank(specs, config)["active"][0]
    assert row["autoVerify"] is True
    assert row["autoFix"] is True


def test_rank_features_skip_not_pending_even_with_auto_verify(tmp_path: Path) -> None:
    """autoVerify must not re-run a gate the user explicitly skipped."""
    specs = tmp_path / "specs"
    _write_state(specs, "a", _completed_prd_state({"status": "skipped"}))
    config = tmp_path / "forge.config.json"
    config.write_text(json.dumps({"autoVerify": True}))
    row = _rank(specs, config)["active"][0]
    assert row["verifyState"] == "skipped"
    assert row["verifyPending"] is False


def test_rank_features_string_false_auto_fix_fails_closed(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    _write_state(specs, "a", _completed_prd_state(None))
    config = tmp_path / "forge.config.json"
    config.write_text(json.dumps({"autoVerify": True, "autoFix": "false"}))
    row = _rank(specs, config)["active"][0]
    assert row["autoVerify"] is True
    assert row["autoFix"] is False  # string "false" must not enable mutation


def test_rank_features_invalid_keys_surfaced(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    _write_state(specs, "a", _completed_prd_state(None))
    config = tmp_path / "forge.config.json"
    config.write_text(json.dumps({"autoVerifyStages": {"forge-1-prod": True}}))
    payload = _rank(specs, config)
    assert payload["invalidAutoVerifyKeys"] == ["forge-1-prod"]


# ── verifyGate: single resolved gate classification (5b) ────────────────────


def test_rank_features_verify_gate_none_when_fresh(tmp_path: Path) -> None:
    """A fresh verify → gate `none` (nothing outstanding)."""
    specs = tmp_path / "specs"
    _write_state(specs, "a", _completed_prd_state({"status": "passed", "verifiedStageVersion": 1}))
    row = _rank(specs)["active"][0]
    assert row["verifyPending"] is False
    assert row["verifyGate"] == "none"


def test_rank_features_verify_gate_standard_when_pending_no_autoverify(tmp_path: Path) -> None:
    """Verify outstanding + auto-verify off → gate `standard` (the §3 gate)."""
    specs = tmp_path / "specs"
    _write_state(specs, "a", _completed_prd_state(None))  # prd never verified
    row = _rank(specs)["active"][0]
    assert row["verifyPending"] is True
    assert row["autoVerify"] is False
    assert row["verifyGate"] == "standard"


def test_rank_features_verify_gate_auto_when_pending_and_autoverify(tmp_path: Path) -> None:
    """Verify outstanding + auto-verify on → gate `auto` (§2b catch-up runs it)."""
    specs = tmp_path / "specs"
    _write_state(specs, "a", _completed_prd_state(None))
    config = tmp_path / "forge.config.json"
    config.write_text(json.dumps({"autoVerify": True}))
    row = _rank(specs, config)["active"][0]
    assert row["verifyPending"] is True
    assert row["autoVerify"] is True
    assert row["verifyGate"] == "auto"


# --------------------------------------------------------------------------- #
# auto-verify-pending: owed-but-unrun automatic verification (03 §5.1/§5.3)
#
# REQ-DEBT-02 — "auto-verify was owed but has not run" must stay distinguishable
# from "verification was never scheduled", from manual pending work, and from an
# explicit skip. A dropped runInStageVerify directive is exactly what these
# assertions keep visible (#163).
# --------------------------------------------------------------------------- #


def _auto_pending_state(scheduled: object = 1, version: int = 1) -> dict:
    """A completed PRD carrying auto-verify debt at ``scheduled``.

    ``scheduled`` is passed through verbatim so the malformed/legacy rows can
    supply a bool, a string, 0, or the sentinel ``None`` (field omitted).
    """
    entry: dict = {
        "status": "auto-verify-pending",
        "scheduledAt": "2026-07-30T00:00:00Z",
        "commitHash": None,
    }
    if scheduled is not None:
        entry["scheduledStageVersion"] = scheduled
    state = _completed_prd_state(entry)
    state["stages"]["forge-1-prd"]["version"] = version
    return state


def test_auto_verify_pending_classifies_as_auto_pending_not_never() -> None:
    """The matching-revision case: every classifier agrees on ``auto-pending``."""
    state = _auto_pending_state()
    assert fs.verify_state(state) == ("forge-1-prd", "auto-pending")
    assert fs._verify_state_for(state, "forge-1-prd") == "auto-pending"
    assert fs.pending_verify(state) == "forge-1-prd"


def test_auto_pending_is_never_reported_as_never_or_resolved() -> None:
    """None of the four read-side paths may report ``never`` or a resolved label."""
    state = _auto_pending_state()
    resolved_labels = {"fresh", "skipped", "none"}
    assert fs.verify_state(state)[1] not in resolved_labels | {"never"}
    assert fs._verify_state_for(state, "forge-1-prd") not in resolved_labels | {"never"}
    # pending_verify returning the stage IS the "not resolved" signal.
    assert fs.pending_verify(state) is not None


def test_auto_verify_pending_is_not_a_member_of_verify_resolved() -> None:
    """_VERIFY_RESOLVED is unchanged: pending debt is not resolved (03 §5.1)."""
    assert fs._VERIFY_RESOLVED == frozenset({"passed", "findings-applied", "skipped"})
    assert "auto-verify-pending" not in fs._VERIFY_RESOLVED
    assert "auto-pending" not in fs._VERIFY_RESOLVED


def test_auto_pending_survives_an_older_scheduled_revision() -> None:
    """A later artifact edit does not erase owed work — it stays ``auto-pending``."""
    state = _auto_pending_state(scheduled=1, version=3)
    assert fs.verify_state(state) == ("forge-1-prd", "auto-pending")
    assert fs._verify_state_for(state, "forge-1-prd") == "auto-pending"


def test_auto_pending_message_states_the_artifact_advanced() -> None:
    """The revision-mismatch message appends BOTH revision numbers (03 §5.3)."""
    message = fs.auto_pending_message(
        "widget", "forge-1-prd", "/feature-forge:forge-verify widget", 1, 3
    )
    assert message.startswith(
        "widget: automatic verification is still pending for forge-1-prd; "
        "run /feature-forge:forge-verify widget to resolve it."
    )
    assert "artifact has advanced" in message
    assert "revision 1" in message and "revision 3" in message


def test_auto_pending_message_is_the_bare_sentence_when_revisions_match() -> None:
    """No revision clause when the schedule is current — one sentence, no dump."""
    message = fs.auto_pending_message(
        "widget", "forge-1-prd", "/feature-forge:forge-verify widget", 2, 2
    )
    assert message == (
        "widget: automatic verification is still pending for forge-1-prd; "
        "run /feature-forge:forge-verify widget to resolve it."
    )
    assert "advanced" not in message


@pytest.mark.parametrize(
    "scheduled",
    [None, 0, -1, True, "1", 1.0],
    ids=["absent", "zero", "negative", "bool", "string", "float"],
)
def test_malformed_schedule_stays_auto_pending_and_warns(
    scheduled: object, capsys: pytest.CaptureFixture[str]
) -> None:
    """Unusable scheduling metadata warns — it never degrades to ``never``."""
    fs._AUTO_VERIFY_DEBT_WARNED.clear()
    state = _auto_pending_state(scheduled=scheduled)

    assert fs.verify_state(state) == ("forge-1-prd", "auto-pending")

    warning = capsys.readouterr().err
    assert "forge-verify-prd" in warning
    assert "auto-verify-pending" in warning
    assert "scheduledStageVersion is missing or malformed" in warning
    # Actionable: it says what to run and that the debt is still owed.
    assert "stays outstanding" in warning
    assert "forge-verify" in warning


def test_malformed_schedule_warns_from_the_stage_exit_classifier_too(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """_verify_state_for applies identical labels AND the identical warning."""
    fs._AUTO_VERIFY_DEBT_WARNED.clear()
    state = _auto_pending_state(scheduled=None)

    assert fs._verify_state_for(state, "forge-1-prd") == "auto-pending"

    assert "scheduledStageVersion is missing or malformed" in capsys.readouterr().err


def test_matching_schedule_does_not_warn(capsys: pytest.CaptureFixture[str]) -> None:
    """A current, usable schedule is the quiet path — no metadata warning."""
    fs._AUTO_VERIFY_DEBT_WARNED.clear()
    fs.verify_state(_auto_pending_state(scheduled=2, version=2))
    assert "malformed" not in capsys.readouterr().err


def test_auto_pending_is_distinct_from_manual_pending_and_skip() -> None:
    """The three neighbouring states classify to three different labels."""
    assert fs.verify_state(_auto_pending_state())[1] == "auto-pending"
    # Generic/manual `pending` is not a resolved status and is not auto debt.
    assert fs.verify_state(_completed_prd_state({"status": "pending"}))[1] == "never"
    assert fs.verify_state(_completed_prd_state({"status": "skipped"}))[1] == "skipped"


def test_read_side_signatures_are_unchanged() -> None:
    """The four functions keep their exact 03 §5.1 signatures.

    ``from __future__ import annotations`` makes every annotation a string, so
    the quotes are normalized away before comparing.
    """
    import inspect

    def sig(func: object) -> str:
        return str(inspect.signature(func)).replace("'", "")

    assert sig(fs.verify_state) == "(state: dict) -> tuple[str | None, str]"
    assert sig(fs.pending_verify) == "(state: dict) -> str | None"
    assert sig(fs._verify_state_for) == "(state: dict, stage: str) -> str"
    assert sig(fs.build_rows) == (
        "(specs_dir: Path, config: dict | None = None) -> list[FeatureRow]"
    )


# ── build_rows / rank-features / doctor surfacing ───────────────────────────


def _write_auto_pending(specs: Path, name: str, scheduled: object = 1, version: int = 1) -> None:
    _write_state(specs, name, _auto_pending_state(scheduled=scheduled, version=version))


def test_rank_features_row_reports_auto_pending(tmp_path: Path) -> None:
    """build_rows: verifyPending true, auto-pending label, non-null command."""
    specs = tmp_path / "specs"
    _write_auto_pending(specs, "a")
    row = _rank(specs)["active"][0]
    assert row["verifyState"] == "auto-pending"
    assert row["verifyPending"] is True
    assert row["verifyStage"] == "forge-1-prd"
    assert row["verifyCommand"] == "/feature-forge:forge-verify a"
    # Never verification-complete: the gate stays open.
    assert row["verifyGate"] != "none"


def test_rank_features_auto_pending_is_not_complete_even_with_autoverify(
    tmp_path: Path,
) -> None:
    """Auto-verify configured on does not discharge the recorded debt."""
    specs = tmp_path / "specs"
    _write_auto_pending(specs, "a")
    config = tmp_path / "forge.config.json"
    config.write_text(json.dumps({"autoVerify": True}))
    row = _rank(specs, config)["active"][0]
    assert row["verifyState"] == "auto-pending"
    assert row["verifyPending"] is True
    assert row["verifyGate"] == "auto"


def test_rank_features_emits_the_exact_diagnostic_sentence(tmp_path: Path) -> None:
    """rank-features prints the 03 §5.3 sentence and never dumps the state file."""
    specs = tmp_path / "specs"
    _write_auto_pending(specs, "widget")

    result = _rank_proc(specs)

    assert result.returncode == 0, result.stderr
    assert (
        "widget: automatic verification is still pending for forge-1-prd; "
        "run /feature-forge:forge-verify widget to resolve it." in result.stderr
    )
    # No state dump: the scheduling timestamp and the raw status never appear.
    assert "2026-07-30T00:00:00Z" not in result.stderr
    assert "auto-verify-pending" not in result.stderr
    # stdout stays independently parseable and prose-free.
    json.loads(result.stdout)
    assert "still pending" not in result.stdout


def test_rank_features_diagnostic_appends_both_revisions_when_advanced(
    tmp_path: Path,
) -> None:
    specs = tmp_path / "specs"
    _write_auto_pending(specs, "widget", scheduled=1, version=4)

    result = _rank_proc(specs)

    assert "widget: automatic verification is still pending for forge-1-prd" in result.stderr
    assert "artifact has advanced" in result.stderr
    assert "scheduled at revision 1" in result.stderr
    assert "now at revision 4" in result.stderr


def test_rank_features_quiet_when_nothing_is_owed(tmp_path: Path) -> None:
    specs = tmp_path / "specs"
    _write_state(specs, "a", _completed_prd_state({"status": "passed", "verifiedStageVersion": 1}))
    assert "still pending" not in _rank_proc(specs).stderr


def test_doctor_reports_auto_pending_and_the_diagnostic(tmp_path: Path) -> None:
    """doctor shares build_rows, so it reports the same label and sentence."""
    specs = tmp_path / "specs"
    _write_auto_pending(specs, "widget")
    (tmp_path / "forge.config.json").write_text("{}")

    result = subprocess.run(
        [sys.executable, str(HELPER), "doctor", "--json"],
        capture_output=True, text=True, cwd=str(tmp_path),
    )

    assert result.returncode == 0, result.stderr
    (feat,) = json.loads(result.stdout)["features"]
    assert feat["verifyState"] == "auto-pending"
    assert (
        "widget: automatic verification is still pending for forge-1-prd; "
        "run /feature-forge:forge-verify widget to resolve it." in result.stderr
    )
    assert "scheduledStageVersion" not in result.stderr
