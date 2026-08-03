"""Tests for the auto-verify navigator support in ``forge-session.py``.

Covers the pure helpers (``auto_verify_for``, ``invalid_auto_verify_keys``,
``verify_state``) and the ``rank-features --json`` integration that surfaces the
effective ``autoVerify``/``autoFix`` per feature and the freshness ledger.
"""

from __future__ import annotations

import importlib.util
import json
import re
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


@pytest.mark.parametrize("bad", [["findings-reported"], {"passed": True}, 3, True],
                         ids=["list", "dict", "int", "bool"])
def test_verify_state_never_on_a_torn_non_string_status(bad: object) -> None:
    """A torn or hand-edited entry can carry any JSON type as `status`; an
    unhashable one must classify as `never`, not raise TypeError at the
    frozenset membership — this label gates the navigator and stage exit."""
    state = _completed_prd_state({"status": bad})
    assert fs.verify_state(state) == ("forge-1-prd", "never")


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


def test_legacy_findings_applied_carrying_a_version_still_reads_stale() -> None:
    """A `findings-applied` entry never classifies `fresh`, even carrying a match.

    THIS SHAPE IS UNREACHABLE THROUGH THE CURRENT WRITER, and asserting the writer's
    behaviour instead would make this test vacuous. `_write_verify_entry` builds
    `findings-applied` with no `verifiedStageVersion` at all and actively refuses
    `--verified-stage-version` on that status. The shape arrives only from LEGACY
    state, which REQ-DEBT-06 requires loading without migration — this repo's own
    `.pipeline-state.json` carries two such entries, written before the current
    writer landed.

    What is asserted is therefore the READ side (03 §5.1): applying fixes is not
    verifying them (§4.2 step 4), so freshness stays cleared until a later `passed`
    restores it — regardless of any key a legacy entry happens to carry. Without the
    guard the version comparison returns `fresh`, `pending_verify` returns None, and
    the verification debt for a fixed-but-never-re-verified stage disappears silently.
    """
    legacy = _completed_prd_state(
        # `version: 1` matches `forge-1-prd.version`, so the generic freshness
        # comparison below the guard would return `fresh`.
        {"status": "findings-applied", "verifiedStageVersion": 1}
    )

    assert fs.verify_state(legacy) == ("forge-1-prd", "stale")
    assert fs.pending_verify(legacy) == "forge-1-prd"
    # The stage-exit classifier must agree, or routing and the ledger disagree.
    assert fs._verify_state_for(legacy, "forge-1-prd") == "stale"


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


# --------------------------------------------------------------------------- #
# Item 012 — the 03 §4.1 stage-exit scheduling boundary
#
# Debt is persisted BEFORE `stage-exit` returns a payload with
# `runInStageVerify: true`, so a dropped directive, a crash, or a compaction
# between scheduling and dispatch still leaves the obligation on disk
# (REQ-DEBT-01/04, REQ-REL-01/03).
# --------------------------------------------------------------------------- #


def _exit_project(
    tmp_path: Path,
    config: dict | None = None,
    state: dict | None = None,
    feature: str = "widget",
    git: bool = True,
) -> Path:
    """A minimal project for `stage-exit`: config + specs/<feature>/ + git.

    ``config`` defaults to auto-verify ON, since that is the precondition every
    scheduling case needs. An explicit ``{}`` means "no config", not "default" —
    hence the ``is None`` test rather than a truthiness one.
    """
    root = tmp_path / "proj"
    (root / "specs" / feature).mkdir(parents=True)
    (root / "forge.config.json").write_text(
        json.dumps({"autoVerify": True} if config is None else config)
    )
    if state is not None:
        (root / "specs" / feature / ".pipeline-state.json").write_text(json.dumps(state))
    if git:
        subprocess.run(["git", "init", "-qb", "main"], cwd=root, check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.email", "t@t.invalid"],
                       check=True)
        subprocess.run(["git", "-C", str(root), "config", "user.name", "t"], check=True)
        subprocess.run(["git", "-C", str(root), "add", "-A"], cwd=root, check=True)
        subprocess.run(["git", "-C", str(root), "commit", "-qm", "init"], check=True)
    return root


def _stage_exit(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HELPER), "stage-exit", "--json", *args],
        capture_output=True, text=True, cwd=str(root),
    )


def _exit_ok(root: Path, *args: str) -> dict:
    proc = _stage_exit(root, *args)
    assert proc.returncode == 0, proc.stderr
    return json.loads(proc.stdout)


def _tech_state(verify: dict | None = None, version: int = 2) -> dict:
    stages: dict = {"forge-2-tech": {"status": "complete", "version": version}}
    if verify is not None:
        stages["forge-verify-tech"] = verify
    return {"pipelineStatus": "active", "stages": stages}


def _read_entry(root: Path, feature: str = "widget", key: str = "forge-verify-tech") -> dict:
    state = json.loads(
        (root / "specs" / feature / ".pipeline-state.json").read_text()
    )
    return state["stages"].get(key, {})


@pytest.mark.parametrize("stage,token,version_key", [
    ("forge-1-prd", "prd", "forge-1-prd"),
    ("forge-2-tech", "tech", "forge-2-tech"),
    ("forge-3-specs", "specs", "forge-3-specs"),
    ("forge-4-backlog", "backlog", "forge-4-backlog"),
    ("forge-5-loop", "impl", "forge-5-loop"),
])
def test_stage_exit_schedules_debt_for_every_verify_capable_token(
    tmp_path: Path, stage: str, token: str, version_key: str
) -> None:
    """Every verify-capable production token records its own pending marker."""
    state = {"pipelineStatus": "active",
             "stages": {version_key: {"status": "complete", "version": 3}}}
    root = _exit_project(tmp_path, state=state)
    args = ["--feature", "widget", "--stage", stage]
    if stage == "forge-5-loop":
        args += ["--outcome", "complete"]

    d = _exit_ok(root, *args)["directives"]

    assert d["runInStageVerify"] is True
    assert d["autoVerifyDebtRecorded"] is True
    entry = _read_entry(root, key=f"forge-verify-{token}")
    assert entry["status"] == "auto-verify-pending"
    assert entry["scheduledStageVersion"] == 3
    assert entry["commitHash"] is None
    assert isinstance(entry["scheduledAt"], str) and entry["scheduledAt"].endswith("Z")


def test_debt_is_on_disk_before_the_dispatch_directive_is_returned(
    tmp_path: Path,
) -> None:
    """REQ-DEBT-01: the marker exists by the time `runInStageVerify` is emitted."""
    root = _exit_project(tmp_path, state=_tech_state())
    payload = _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")

    assert payload["directives"]["runInStageVerify"] is True
    assert payload["directives"]["autoVerifyDebtRecorded"] is True
    # The process has already exited, so anything the payload claims about the
    # write is claimed about a file that must already be readable.
    assert _read_entry(root)["status"] == "auto-verify-pending"


def test_no_debt_is_recorded_when_auto_verify_is_off(tmp_path: Path) -> None:
    root = _exit_project(tmp_path, config={}, state=_tech_state())
    d = _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["runInStageVerify"] is False
    assert d["autoVerifyDebtRecorded"] is False
    assert _read_entry(root) == {}


def test_repeated_stage_exit_at_the_same_revision_is_byte_idempotent(
    tmp_path: Path,
) -> None:
    """REQ-REL-01: no `_commit_state`, so `scheduledAt` AND `updatedAt` hold still."""
    root = _exit_project(tmp_path, state=_tech_state())
    state_file = root / "specs" / "widget" / ".pipeline-state.json"

    _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")
    first = state_file.read_bytes()
    for _ in range(2):
        _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")
        assert state_file.read_bytes() == first

    written = json.loads(first)
    assert written["stages"]["forge-verify-tech"]["scheduledStageVersion"] == 2
    # Explicit, because a refreshed `updatedAt` is the easiest way to break this.
    assert json.loads(state_file.read_bytes())["updatedAt"] == written["updatedAt"]


def test_a_newer_revision_creates_exactly_one_new_schedule(tmp_path: Path) -> None:
    root = _exit_project(tmp_path, state=_tech_state())
    state_file = root / "specs" / "widget" / ".pipeline-state.json"

    _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")
    scheduled_at_v2 = _read_entry(root)["scheduledAt"]

    # The artifact advances; the older pending marker is superseded, once.
    state = json.loads(state_file.read_text())
    state["stages"]["forge-2-tech"]["version"] = 3
    state_file.write_text(json.dumps(state))

    _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")
    entry = _read_entry(root)
    assert entry["status"] == "auto-verify-pending"
    assert entry["scheduledStageVersion"] == 3
    after_first = state_file.read_bytes()

    # A second exit at revision 3 is once again a no-op.
    _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")
    assert state_file.read_bytes() == after_first
    assert entry["scheduledAt"] >= scheduled_at_v2


def test_a_pending_marker_for_an_older_revision_is_superseded(tmp_path: Path) -> None:
    """A stale schedule is replaced, and the exit warns before replacing it."""
    root = _exit_project(tmp_path, state=_tech_state(
        {"status": "auto-verify-pending", "scheduledAt": "2020-01-01T00:00:00Z",
         "scheduledStageVersion": 1, "commitHash": None}
    ))
    d = _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]

    # The pre-mutation snapshot still reports the advance (00 §4 warnings entry 3).
    assert any("artifact has advanced" in w for w in d["warnings"])
    entry = _read_entry(root)
    assert entry["scheduledStageVersion"] == 2
    assert entry["scheduledAt"] != "2020-01-01T00:00:00Z"


@pytest.mark.parametrize("entry,label", [
    ({"status": "passed", "verifiedStageVersion": 2}, "fresh"),
    ({"status": "skipped"}, "skipped"),
], ids=["fresh-terminal", "explicit-skip"])
def test_a_resolved_entry_prevents_rescheduling(
    tmp_path: Path, entry: dict, label: str
) -> None:
    """A terminal entry fresh for the current revision, and an explicit skip,
    are both resolved: nothing is owed, so nothing is written over them."""
    root = _exit_project(tmp_path, state=_tech_state(entry))
    state_file = root / "specs" / "widget" / ".pipeline-state.json"
    before = state_file.read_bytes()

    d = _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]

    assert d["verifyState"] == label
    assert d["runInStageVerify"] is False
    assert d["autoVerifyDebtRecorded"] is False
    assert state_file.read_bytes() == before


def test_a_stale_terminal_entry_does_reschedule(tmp_path: Path) -> None:
    """Negative control: only a FRESH terminal entry suppresses scheduling."""
    root = _exit_project(tmp_path, state=_tech_state(
        {"status": "passed", "verifiedStageVersion": 1}   # artifact is at 2
    ))
    d = _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["verifyState"] == "stale"
    assert d["autoVerifyDebtRecorded"] is True
    assert _read_entry(root)["status"] == "auto-verify-pending"


def test_an_injected_write_failure_exits_2_with_no_dispatch_directive(
    tmp_path: Path,
) -> None:
    """REQ-DEBT-04: a crash before the write cannot falsely claim the debt landed."""
    root = _exit_project(tmp_path, state=_tech_state())
    state_file = root / "specs" / "widget" / ".pipeline-state.json"
    before = state_file.read_bytes()
    # `_write_state` creates its sibling temp file in the feature directory; an
    # unwritable directory fails `tempfile.mkstemp` before anything is replaced.
    (root / "specs" / "widget").chmod(0o555)
    try:
        proc = _stage_exit(root, "--feature", "widget", "--stage", "forge-2-tech")
    finally:
        (root / "specs" / "widget").chmod(0o755)

    assert proc.returncode == 2
    assert proc.stderr.startswith("Error:")
    assert proc.stdout == ""
    assert "runInStageVerify" not in proc.stdout
    assert state_file.read_bytes() == before


def test_an_interrupted_dispatch_leaves_the_marker_readable_from_a_new_process(
    tmp_path: Path,
) -> None:
    """REQ-REL-03, 07 §4.1: schedule, then deliberately perform NO verify call.

    The marker must survive into a separate CLI process — the only evidence that
    survives a dropped directive, a crash, or a compaction.
    """
    root = _exit_project(tmp_path, state=_tech_state())
    _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")
    # No `state-verify` follows. A fresh process reads the persisted obligation.
    rank = subprocess.run(
        [sys.executable, str(HELPER), "rank-features",
         "--specs-dir", str(root / "specs"), "--json"],
        capture_output=True, text=True, cwd=str(root),
    )
    assert rank.returncode == 0, rank.stderr
    (row,) = json.loads(rank.stdout)["active"]
    assert row["verifyState"] == "auto-pending"
    assert row["verifyPending"] is True
    assert row["verifyStage"] == "forge-2-tech"
    assert row["verifyCommand"] == "/feature-forge:forge-verify widget"
    assert (
        "widget: automatic verification is still pending for forge-2-tech; "
        "run /feature-forge:forge-verify widget to resolve it." in rank.stderr
    )
    # And a second stage-exit process sees it too, without rescheduling.
    d = _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["verifyState"] == "auto-pending"
    assert d["autoVerifyDebtRecorded"] is True


def test_an_advertised_but_unavailable_dispatch_never_promotes_the_deferred_command(
    tmp_path: Path,
) -> None:
    """07 §3.4 (b) and (c): a dispatch that was advertised and then failed to happen.

    The scenario: a payload announces `runInStageVerify: true`, the clean-room verifier
    then returns `CLEAN_ROOM_UNAVAILABLE` or a non-answer, and the agent re-enters the
    exit. Verification did **not** run, so the recovery payload must still lead with the
    verify command — and the *previous* payload's `deferredCommand` (the production
    successor) must never be promoted into its place. Promoting it is the
    dropped-pipeline-thread failure this feature exists to prevent: the stage would
    advance on the strength of a verification that silently never happened.

    The sibling test above covers (a), that the debt survives into a new process. This
    covers the two halves it leaves unproven, under the specified `manual` capability.

    One deviation from the finding that proposed this test: it expected
    `verifyGate == "manual-print"`. The contract emits `"none"` here, and that is
    correct — `manual-print` is for the *gate* path, while `runInStageVerify: true`
    keeps the gate at `none` and routes consent through the Standard Verify Gate
    instead. Asserting `manual-print` would have pinned a bug into the suite, so the
    real invariant is asserted and the gate value is pinned as `none`.
    """
    root = _exit_project(tmp_path, state=_tech_state())
    first = _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert first["runInStageVerify"] is True, "precondition: the dispatch was advertised"
    assert first["deferredCommand"] == "/feature-forge:forge-3-specs widget"

    # The dispatch failed: no `state-verify` call follows, so the debt stays unresolved.
    payload = _exit_ok(
        root, "--feature", "widget", "--stage", "forge-2-tech",
        "--verify-capability", "manual",
    )
    second = payload["directives"]

    # (b) the recovery payload still leads with verification.
    assert second["primaryCommand"] == "/feature-forge:forge-verify widget"
    assert second["verifyState"] == "auto-pending"
    assert second["verifyGate"] == "none"  # see the docstring — not `manual-print`

    # (c) the earlier payload's deferred production command is never promoted.
    assert second["primaryCommand"] != first["deferredCommand"]
    assert second["deferredCommand"] == first["deferredCommand"], (
        "the production successor should stay deferred, not change identity"
    )

    # The fenced command the user is told to run is the verify command, not the
    # successor. The successor may still appear in prose ("after verification passes,
    # continue with …"); what must never happen is it being the thing in the fence.
    fenced = re.findall(r"```\n(.*?)\n```", payload["nextSteps"], re.DOTALL)
    assert fenced, f"no fenced command in nextSteps: {payload['nextSteps']!r}"
    assert any("/feature-forge:forge-verify widget" in block for block in fenced)
    assert not any(first["deferredCommand"] in block for block in fenced), (
        "the deferred production command was promoted into the actionable fence while "
        "verification is still outstanding"
    )


def test_the_clean_tree_snapshot_predates_the_pending_write(tmp_path: Path) -> None:
    """The sanctioned control-plane mutation must not dirty its own precondition."""
    root = _exit_project(tmp_path, config={"autoVerify": True, "autoFix": True},
                         state=_tech_state())
    d = _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]

    assert d["cleanTree"] is True
    assert d["autoFixEligible"] is True
    # The write itself DID dirty the tree — which is exactly why the snapshot has
    # to be taken first. The state-file modification is sanctioned, not user dirt.
    porcelain = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert ".pipeline-state.json" in porcelain


def test_an_unknown_artifact_revision_still_records_the_debt(tmp_path: Path) -> None:
    """Forgetting owed debt because its revision is unknown is the REQ-DEBT-02
    conflation; a null schedule stays `auto-pending` and warns instead."""
    root = _exit_project(tmp_path, state=None)
    d = _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["autoVerifyDebtRecorded"] is True
    entry = _read_entry(root)
    assert entry["status"] == "auto-verify-pending"
    assert entry["scheduledStageVersion"] is None

    second = _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert second["verifyState"] == "auto-pending"
    assert any("scheduledStageVersion" in w for w in second["warnings"])


def test_a_tokenless_stage_never_schedules(tmp_path: Path) -> None:
    """forge-6-docs has no verification token, so there is no debt to record."""
    root = _exit_project(tmp_path, state=_tech_state())
    state_file = root / "specs" / "widget" / ".pipeline-state.json"
    before = state_file.read_bytes()
    d = _exit_ok(root, "--feature", "widget", "--stage", "forge-6-docs",
                 "--outcome", "complete")["directives"]
    assert d["verifyState"] == "none"
    assert d["runInStageVerify"] is False
    assert d["autoVerifyDebtRecorded"] is False
    assert state_file.read_bytes() == before


# --- epic-scoped scheduling (03 §4.1, REQ-SEC-01) --------------------------- #


def _epic_exit_project(
    tmp_path: Path,
    revision: int | None = 1,
    epic_entry: dict | None = None,
    member: str | None = None,
) -> Path:
    """An epic with a manifest, optionally an `.epic-state.json` and one member."""
    root = _exit_project(tmp_path, feature="my-epic")
    epic_dir = root / "specs" / "my-epic"
    manifest: dict = {"epic": "my-epic", "features": []}
    if revision is not None:
        manifest["revision"] = revision
    (epic_dir / "epic-manifest.json").write_text(json.dumps(manifest))
    if epic_entry is not None:
        (epic_dir / ".epic-state.json").write_text(json.dumps(
            {"epic": "my-epic", "stages": {"forge-verify-epic": epic_entry}}
        ))
    if member is not None:
        (epic_dir / member).mkdir()
        (epic_dir / member / ".pipeline-state.json").write_text(json.dumps(
            {"pipelineStatus": "active",
             "stages": {"forge-1-prd": {"status": "complete", "version": 7}}}
        ))
    return root


def test_epic_scheduling_writes_epic_state_and_touches_no_member(
    tmp_path: Path,
) -> None:
    root = _epic_exit_project(tmp_path, revision=4, member="alpha")
    member_state = root / "specs" / "my-epic" / "alpha" / ".pipeline-state.json"
    member_before = member_state.read_bytes()
    epic_pipeline_state = root / "specs" / "my-epic" / ".pipeline-state.json"

    d = _exit_ok(root, "--feature", "my-epic", "--stage", "forge-0-epic")["directives"]

    assert d["runInStageVerify"] is True
    assert d["autoVerifyDebtRecorded"] is True
    entry = json.loads(
        (root / "specs" / "my-epic" / ".epic-state.json").read_text()
    )["stages"]["forge-verify-epic"]
    assert entry["status"] == "auto-verify-pending"
    # The manifest revision, never a member production-stage version (7 above).
    assert entry["scheduledStageVersion"] == 4
    assert member_state.read_bytes() == member_before
    assert not epic_pipeline_state.exists()


def test_epic_scheduling_is_idempotent_at_the_same_manifest_revision(
    tmp_path: Path,
) -> None:
    root = _epic_exit_project(tmp_path, revision=4)
    epic_state = root / "specs" / "my-epic" / ".epic-state.json"

    _exit_ok(root, "--feature", "my-epic", "--stage", "forge-0-epic")
    first = epic_state.read_bytes()
    _exit_ok(root, "--feature", "my-epic", "--stage", "forge-0-epic")
    assert epic_state.read_bytes() == first


def test_a_manifest_edit_supersedes_the_epic_schedule(tmp_path: Path) -> None:
    root = _epic_exit_project(tmp_path, revision=4)
    _exit_ok(root, "--feature", "my-epic", "--stage", "forge-0-epic")

    manifest = root / "specs" / "my-epic" / "epic-manifest.json"
    manifest.write_text(json.dumps({"epic": "my-epic", "features": [], "revision": 5}))
    _exit_ok(root, "--feature", "my-epic", "--stage", "forge-0-epic")

    entry = json.loads(
        (root / "specs" / "my-epic" / ".epic-state.json").read_text()
    )["stages"]["forge-verify-epic"]
    assert entry["scheduledStageVersion"] == 5


def test_a_fresh_epic_verification_prevents_epic_scheduling(tmp_path: Path) -> None:
    root = _epic_exit_project(tmp_path, revision=4, epic_entry={
        "status": "passed", "verifiedStageVersion": 4,
    })
    epic_state = root / "specs" / "my-epic" / ".epic-state.json"
    before = epic_state.read_bytes()

    d = _exit_ok(root, "--feature", "my-epic", "--stage", "forge-0-epic")["directives"]

    assert d["verifyState"] == "fresh"
    assert d["autoVerifyDebtRecorded"] is False
    assert epic_state.read_bytes() == before


def test_a_legacy_epic_manifest_schedules_at_revision_1(tmp_path: Path) -> None:
    """REQ-DEBT-06: a manifest with no `revision` reads as logical 1, unmigrated."""
    root = _epic_exit_project(tmp_path, revision=None)
    manifest = root / "specs" / "my-epic" / "epic-manifest.json"
    manifest_before = manifest.read_bytes()

    _exit_ok(root, "--feature", "my-epic", "--stage", "forge-0-epic")

    entry = json.loads(
        (root / "specs" / "my-epic" / ".epic-state.json").read_text()
    )["stages"]["forge-verify-epic"]
    assert entry["scheduledStageVersion"] == 1
    assert manifest.read_bytes() == manifest_before


def test_an_epic_without_a_manifest_fails_closed_with_no_directive(
    tmp_path: Path,
) -> None:
    """The debt cannot be recorded, so no dispatch directive is emitted."""
    root = _exit_project(tmp_path, feature="my-epic")   # no epic-manifest.json
    proc = _stage_exit(root, "--feature", "my-epic", "--stage", "forge-0-epic")
    assert proc.returncode == 2
    assert proc.stderr.startswith("Error:")
    assert proc.stdout == ""
    assert not (root / "specs" / "my-epic" / ".epic-state.json").exists()


# --- directives.autoVerifyEffective / invalidAutoVerifyKeys (00 §4) --------- #


def test_auto_verify_effective_reports_the_per_stage_value_not_the_raw_config(
    tmp_path: Path,
) -> None:
    root = _exit_project(
        tmp_path,
        config={"autoVerify": True, "autoVerifyStages": {"forge-2-tech": False}},
        state=_tech_state(),
    )
    d = _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["autoVerifyEffective"] is False, "the raw autoVerify value is True"
    assert d["autoVerifyDebtRecorded"] is False
    assert _read_entry(root) == {}


def test_an_override_can_turn_auto_verify_on_for_one_stage_only(
    tmp_path: Path,
) -> None:
    root = _exit_project(
        tmp_path,
        config={"autoVerify": False, "autoVerifyStages": {"forge-2-tech": True}},
        state=_tech_state(),
    )
    d = _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["autoVerifyEffective"] is True
    assert d["autoVerifyDebtRecorded"] is True


def test_invalid_auto_verify_keys_render_the_exact_template_in_sorted_order(
    tmp_path: Path,
) -> None:
    """00 §4's template verbatim, sorted (02 §10), and never fatal."""
    root = _exit_project(tmp_path, config={
        "autoVerify": True,
        # Deliberately NOT in sorted order on disk.
        "autoVerifyStages": {"zz-nope": True, "forge-1-prod": True},
    }, state=_tech_state())

    proc = _stage_exit(root, "--feature", "widget", "--stage", "forge-2-tech")

    assert proc.returncode == 0, proc.stderr
    d = json.loads(proc.stdout)["directives"]
    assert d["invalidAutoVerifyKeys"] == ["forge-1-prod", "zz-nope"]
    rendered = [
        'Warning: autoVerifyStages key "forge-1-prod" names no verify-capable '
        "stage; it is ignored. Valid keys are forge-1-prd, forge-2-tech, "
        "forge-3-specs, forge-4-backlog, forge-5-loop.",
        'Warning: autoVerifyStages key "zz-nope" names no verify-capable '
        "stage; it is ignored. Valid keys are forge-1-prd, forge-2-tech, "
        "forge-3-specs, forge-4-backlog, forge-5-loop.",
    ]
    emitted = [line for line in proc.stderr.splitlines() if line.startswith("Warning:")]
    assert emitted == rendered
    # An ignored key is an advisory: the exit still runs, and the valid global
    # setting still applies.
    assert d["autoVerifyEffective"] is True
    assert d["autoVerifyDebtRecorded"] is True


def test_a_valid_config_emits_no_invalid_key_warning(tmp_path: Path) -> None:
    root = _exit_project(tmp_path, config={
        "autoVerify": True, "autoVerifyStages": {"forge-2-tech": True},
    }, state=_tech_state())
    proc = _stage_exit(root, "--feature", "widget", "--stage", "forge-2-tech")
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout)["directives"]["invalidAutoVerifyKeys"] == []
    assert "names no verify-capable stage" not in proc.stderr


# --- a branch exit is inside the diversion; it never schedules -------------- #


@pytest.mark.parametrize("stage,outcome", [
    ("forge-verify", "findings"),
    ("forge-fix", "applied"),
])
@pytest.mark.parametrize("owner", ["direct", "nested"])
def test_a_branch_exit_never_schedules_over_the_result_it_just_wrote(
    tmp_path: Path, stage: str, outcome: str, owner: str
) -> None:
    """A verify/fix exit is already inside the verification diversion.

    Scheduling there would both direct a re-dispatch of the branch skill and
    overwrite the `findings-reported` entry the skill had just recorded with a
    fresh `auto-verify-pending` marker — losing the report and the reason for the
    diversion (REQ-EXIT-04, REQ-DEBT-03).
    """
    report = {"status": "findings-reported", "findingsFile": "findings.md",
              "findingsCount": 3, "verifiedStageVersion": 2, "commitHash": None}
    root = _exit_project(tmp_path, state=_tech_state(report))
    state_file = root / "specs" / "widget" / ".pipeline-state.json"
    before = state_file.read_bytes()

    d = _exit_ok(root, "--feature", "widget", "--stage", stage,
                 "--served-stage", "forge-2-tech", "--outcome", outcome,
                 "--owner", owner)["directives"]

    assert d["runInStageVerify"] is False
    assert d["autoVerifyDebtRecorded"] is False
    assert state_file.read_bytes() == before
    assert _read_entry(root) == report


# --- a live findings report is never clobbered by scheduling ----------------- #


def _live_report(version: int = 2) -> dict:
    return {"status": "findings-reported", "findingsFile": "findings.md",
            "findingsCount": 3, "verifiedStageVersion": version, "commitHash": None}


def test_a_production_re_exit_preserves_a_current_revision_findings_report(
    tmp_path: Path,
) -> None:
    """A findings report at the current revision is live evidence, not owed debt.

    Scheduling over it would replace the entry and delete
    ``findingsFile``/``findingsCount`` (the REQ-EXIT-04 clobber reached from a
    production re-exit), after which ``state-verify --status findings-applied``
    loses its precondition. The exit must leave the entry intact and route to
    forge-fix instead.
    """
    report = _live_report()
    root = _exit_project(tmp_path, state=_tech_state(report))
    state_file = root / "specs" / "widget" / ".pipeline-state.json"
    before = state_file.read_bytes()

    d = _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]

    assert d["runInStageVerify"] is False
    assert d["autoVerifyDebtRecorded"] is False
    assert d["verifyGate"] == "none"
    assert d["verifyState"] == "failing"
    assert d["primaryCommand"] == "/feature-forge:forge-fix widget --served-stage forge-2-tech"
    assert state_file.read_bytes() == before
    assert _read_entry(root) == report


def test_findings_applied_still_succeeds_after_a_production_re_exit(
    tmp_path: Path,
) -> None:
    root = _exit_project(tmp_path, state=_tech_state(_live_report()))
    _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")

    proc = subprocess.run(
        [sys.executable, str(HELPER), "state-verify", "--feature", "widget",
         "--stage", "forge-2-tech", "--status", "findings-applied",
         "--specs-dir", "specs"],
        capture_output=True, text=True, cwd=str(root),
    )
    assert proc.returncode == 0, proc.stderr
    entry = _read_entry(root)
    assert entry["status"] == "findings-applied"
    assert entry["findingsFile"] == "findings.md"
    assert entry["findingsCount"] == 3


def test_a_stale_findings_report_is_still_superseded_by_scheduling(
    tmp_path: Path,
) -> None:
    """A report against a since-revised artifact is superseded normally."""
    root = _exit_project(tmp_path, state=_tech_state(_live_report(version=1)))

    d = _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]

    assert d["runInStageVerify"] is True
    assert d["autoVerifyDebtRecorded"] is True
    entry = _read_entry(root)
    assert entry["status"] == "auto-verify-pending"
    assert entry["scheduledStageVersion"] == 2


def test_stage_exit_classifies_a_torn_verify_entry_without_crashing(
    tmp_path: Path,
) -> None:
    """`_classify_verify_entry` runs while closing a stage; an unhashable
    status must label `never` rather than raise (auto-verify off keeps this
    scoped to classification — corrupt-state debt writes are their own case)."""
    root = _exit_project(
        tmp_path, config={}, state=_tech_state({"status": ["findings-reported"]})
    )
    d = _exit_ok(root, "--feature", "widget", "--stage", "forge-2-tech")["directives"]
    assert d["verifyState"] == "never"
    assert d["runInStageVerify"] is False


def test_a_loop_complete_exit_with_a_live_report_routes_to_fix(
    tmp_path: Path,
) -> None:
    """The loop's `complete` handoff obeys the same live-report rule as a
    production re-exit: the fenced action is the fix, no debt is scheduled,
    and the report survives byte-identically."""
    state = {"pipelineStatus": "active", "stages": {
        "forge-5-loop": {"status": "complete", "version": 1},
        "forge-verify-impl": {"status": "findings-reported", "findingsFile": "f.md",
                              "findingsCount": 2, "verifiedStageVersion": 1,
                              "commitHash": None},
    }}
    root = _exit_project(tmp_path, state=state)
    state_file = root / "specs" / "widget" / ".pipeline-state.json"
    before = state_file.read_bytes()

    d = _exit_ok(root, "--feature", "widget", "--stage", "forge-5-loop",
                 "--outcome", "complete")["directives"]

    assert d["runInStageVerify"] is False
    assert d["autoVerifyDebtRecorded"] is False
    assert d["verifyGate"] == "none"
    assert d["primaryCommand"] == "/feature-forge:forge-fix widget --served-stage forge-5-loop"
    assert state_file.read_bytes() == before


def test_rank_features_warns_on_a_torn_non_string_status(tmp_path: Path) -> None:
    """The non-string guard degrades to `never` WITH the #148 diagnostic —
    a malformed status is at least as warn-worthy as an unknown string."""
    specs = tmp_path / "specs"
    _write_state(specs, "a", _completed_prd_state({"status": ["findings-reported"]}))
    result = _rank_proc(specs)
    assert result.returncode == 0, result.stderr
    assert "unknown forge-verify-prd status" in result.stderr
