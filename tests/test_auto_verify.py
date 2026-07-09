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


def _rank(specs_dir: Path, config_path: Path | None = None) -> dict:
    argv = [sys.executable, str(HELPER), "rank-features",
            "--specs-dir", str(specs_dir), "--json"]
    if config_path is not None:
        argv += ["--config", str(config_path)]
    result = subprocess.run(argv, capture_output=True, text=True)
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
