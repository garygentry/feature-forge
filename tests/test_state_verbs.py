"""R4 state-verb guards — the shared write machinery (backlog item 007).

Covers the pieces every ``state-*`` verb reuses: the ``STATE_VERB_STAGES`` domain
constant, the ``_now_iso`` stamp, the atomic ``_write_state``, the corrupt-file-refusing
``_load_state_for_write``, ``_commit_state``'s ``updatedAt`` refresh, and the
``_stage_entry`` bootstrap. Per-verb CLI coverage (``state-enter``/``-artifact``/
``-complete``/``-note``/``-decision``/``-ecr``/``-branch``) arrives with items 008–010,
which extend this module.

``scripts/forge-session.py`` is hyphen-named, so it is loaded by path via importlib
rather than imported — the same trick the script's own flat, dependency-free design
forces on any in-process caller. Stdlib only (`jsonschema` is absent in CI); schema
conformance goes through ``tests/_state_schema.py``.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

from _forge_paths import SCRIPTS, read
from _state_schema import validate_state

FORGE_SESSION = SCRIPTS / "forge-session.py"


def _load_forge_session():
    """Load `scripts/forge-session.py` as a module (its name is not importable)."""
    spec = importlib.util.spec_from_file_location("forge_session_under_test", FORGE_SESSION)
    assert spec and spec.loader, f"cannot load {FORGE_SESSION}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FS = _load_forge_session()


def _feature_dir(tmp_path: Path, name: str = "demo") -> Path:
    """Create an EMPTY feature dir (no state file) under a temp specs tree."""
    feature_dir = tmp_path / "specs" / name
    feature_dir.mkdir(parents=True)
    return feature_dir


# --------------------------------------------------------------------------- #
# Module-level constants & imports
# --------------------------------------------------------------------------- #


def test_production_stages_is_defined_exactly_once():
    """A second module-level PRODUCTION_STAGES would win at import and reorder it.

    next_stage(), verify_state() and stage_exit() all walk that order-sensitive
    tuple, so a redefinition beginning with forge-0-epic is a runtime behavior
    change (REQ-BEHAV-01), not a cosmetic one.
    """
    source = read(FORGE_SESSION)
    assert len(re.findall(r"^PRODUCTION_STAGES: Final", source, re.M)) == 1


def test_state_verb_stages_extends_production_stages_without_redefining_it():
    assert FS.PRODUCTION_STAGES == (
        "forge-1-prd",
        "forge-2-tech",
        "forge-3-specs",
        "forge-4-backlog",
        "forge-5-loop",
        "forge-6-docs",
    )
    assert len(FS.STATE_VERB_STAGES) == 7
    assert FS.STATE_VERB_STAGES[0] == "forge-0-epic"
    assert FS.STATE_VERB_STAGES[1:] == FS.PRODUCTION_STAGES


def test_next_stage_still_returns_prd_for_a_fresh_standalone_feature():
    """The regression the PRODUCTION_STAGES collision would have caused."""
    assert FS.next_stage({}) == "forge-1-prd"
    assert FS.next_stage({"stages": {}}) == "forge-1-prd"


def test_tempfile_is_imported_and_jsonschema_is_not():
    source = read(FORGE_SESSION)
    assert re.search(r"^import tempfile$", source, re.M)
    assert "jsonschema" not in source


# --------------------------------------------------------------------------- #
# _now_iso
# --------------------------------------------------------------------------- #


def test_now_iso_is_z_suffixed_second_precision_utc():
    stamp = FS._now_iso()
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", stamp), stamp
    # The codebase's parse path normalizes the trailing Z; prove it round-trips.
    assert FS._parse_ts(stamp) is not None


# --------------------------------------------------------------------------- #
# _write_state
# --------------------------------------------------------------------------- #


def test_write_state_uses_mkstemp_fsync_and_replace(tmp_path, monkeypatch):
    calls: list[str] = []
    real_mkstemp, real_fsync, real_replace = FS.tempfile.mkstemp, FS.os.fsync, FS.os.replace

    def spy(name, fn):
        def wrapper(*args, **kwargs):
            calls.append(name)
            return fn(*args, **kwargs)

        return wrapper

    monkeypatch.setattr(FS.tempfile, "mkstemp", spy("mkstemp", real_mkstemp))
    monkeypatch.setattr(FS.os, "fsync", spy("fsync", real_fsync))
    monkeypatch.setattr(FS.os, "replace", spy("replace", real_replace))

    target = _feature_dir(tmp_path) / FS.PIPELINE_STATE_FILENAME
    FS._write_state(target, {"feature": "demo"})

    assert calls == ["mkstemp", "fsync", "replace"]
    assert json.loads(target.read_text(encoding="utf-8")) == {"feature": "demo"}
    assert target.read_text(encoding="utf-8").endswith("\n")


def test_write_state_leaves_no_temp_debris(tmp_path):
    feature_dir = _feature_dir(tmp_path)
    FS._write_state(feature_dir / FS.PIPELINE_STATE_FILENAME, {"feature": "demo"})
    assert [p.name for p in feature_dir.iterdir()] == [FS.PIPELINE_STATE_FILENAME]


def test_write_state_wraps_oserror_in_usage_error_and_cleans_up(tmp_path, monkeypatch):
    feature_dir = _feature_dir(tmp_path)
    target = feature_dir / FS.PIPELINE_STATE_FILENAME
    target.write_text('{"feature": "demo"}\n', encoding="utf-8")
    before = target.read_bytes()

    def boom(*_args, **_kwargs):
        raise OSError("Read-only file system")

    monkeypatch.setattr(FS.os, "replace", boom)

    try:
        FS._write_state(target, {"feature": "clobbered"})
    except FS.UsageError as exc:
        assert str(exc) == f"atomic write to {target} failed: Read-only file system"
    else:  # pragma: no cover - the assertion below reports the miss
        raise AssertionError("_write_state did not raise UsageError on OSError")

    assert target.read_bytes() == before, "a failed write must not touch the target"
    assert [p.name for p in feature_dir.iterdir()] == [
        FS.PIPELINE_STATE_FILENAME
    ], "the temp file must be unlinked on failure"


# --------------------------------------------------------------------------- #
# _load_state_for_write
# --------------------------------------------------------------------------- #


def test_load_state_for_write_rejects_an_unknown_feature_dir(tmp_path):
    (tmp_path / "specs").mkdir()
    try:
        FS._load_state_for_write(tmp_path / "specs", "nope", None)
    except FS.UsageError as exc:
        assert "no feature directory at" in str(exc)
        assert "--feature" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("an unknown --feature must be a usage error, not a create")


def test_usage_error_surfaces_as_error_line_and_exit_2():
    """The single top-level handler every state verb inherits (0/2 only, no exit 1).

    Driven through an existing UsageError path (`effective-config` with an
    unreadable schema) because item 007 adds machinery, not verbs — per-verb CLI
    exit codes are asserted by items 008-010, which extend this module.
    """
    result = subprocess.run(
        [sys.executable, str(FORGE_SESSION), "effective-config", "--schema", "/nonexistent/x.json"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2, result.stderr
    assert result.stderr.startswith("Error:"), result.stderr


def test_load_state_for_write_refuses_a_corrupt_state_file_byte_intact(tmp_path):
    feature_dir = _feature_dir(tmp_path)
    state_path = feature_dir / FS.PIPELINE_STATE_FILENAME
    state_path.write_bytes(b"{ not json")

    try:
        FS._load_state_for_write(tmp_path / "specs", "demo", None)
    except FS.UsageError as exc:
        assert "refusing to overwrite it" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("a corrupt state file must not be silently downgraded to {}")

    assert state_path.read_bytes() == b"{ not json"


def test_load_state_for_write_refuses_a_non_object_state_file(tmp_path):
    feature_dir = _feature_dir(tmp_path)
    state_path = feature_dir / FS.PIPELINE_STATE_FILENAME
    state_path.write_bytes(b"[1, 2, 3]")

    try:
        FS._load_state_for_write(tmp_path / "specs", "demo", None)
    except FS.UsageError as exc:
        assert "not a JSON object" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("a non-object state file must not be overwritten")

    assert state_path.read_bytes() == b"[1, 2, 3]"


def test_read_state_downgrades_where_the_write_path_refuses(tmp_path):
    """The deliberate asymmetry (V-016): the navigator's read-only sweep may
    treat a corrupt file as not-started; a writer may not."""
    state_path = _feature_dir(tmp_path) / FS.PIPELINE_STATE_FILENAME
    state_path.write_bytes(b"{ not json")
    assert FS._read_state(state_path) == {}


def test_seeded_state_satisfies_the_schema_top_level_required_list(tmp_path):
    _feature_dir(tmp_path)
    state_path, state = FS._load_state_for_write(tmp_path / "specs", "demo", None)

    assert state["feature"] == "demo"
    assert state["pipelineStatus"] == "active"
    assert state["stages"] == {}
    assert state["currentStage"] == FS.PRODUCTION_STAGES[0]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", state["createdAt"])

    written = FS._commit_state(state_path, state)
    assert validate_state(written) == [], validate_state(written)
    assert json.loads(state_path.read_text(encoding="utf-8")) == written


def test_load_state_for_write_preserves_existing_fields(tmp_path):
    state_path = _feature_dir(tmp_path) / FS.PIPELINE_STATE_FILENAME
    existing = {
        "feature": "demo",
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-02T00:00:00Z",
        "currentStage": "forge-3-specs",
        "pipelineStatus": "paused",
        "stages": {"forge-1-prd": {"status": "complete"}},
    }
    state_path.write_text(json.dumps(existing), encoding="utf-8")

    _, state = FS._load_state_for_write(tmp_path / "specs", "demo", None)
    for key, value in existing.items():
        assert state[key] == value, f"setdefault clobbered {key}"


def test_load_state_for_write_resolves_a_nested_epic_member(tmp_path):
    member = tmp_path / "specs" / "big-epic" / "demo"
    member.mkdir(parents=True)
    state_path, state = FS._load_state_for_write(tmp_path / "specs", "demo", "big-epic")
    assert state_path == member / FS.PIPELINE_STATE_FILENAME
    assert state["feature"] == "demo"


# --------------------------------------------------------------------------- #
# _commit_state / _stage_entry
# --------------------------------------------------------------------------- #


def test_commit_state_refreshes_updated_at_and_writes_atomically(tmp_path):
    state_path = _feature_dir(tmp_path) / FS.PIPELINE_STATE_FILENAME
    _, state = FS._load_state_for_write(tmp_path / "specs", "demo", None)
    state["updatedAt"] = "2020-01-01T00:00:00Z"

    returned = FS._commit_state(state_path, state)

    assert returned is state
    assert returned["updatedAt"] != "2020-01-01T00:00:00Z"
    assert json.loads(state_path.read_text(encoding="utf-8"))["updatedAt"] == state["updatedAt"]


def test_stage_entry_bootstraps_a_pending_status(tmp_path):
    state: dict = {}
    entry = FS._stage_entry(state, "forge-3-specs")
    assert entry == {"status": "pending"}
    assert state["stages"]["forge-3-specs"] is entry

    # The seed is what keeps an artifacts-only write schema-valid: stageEntry
    # declares required: ["status"].
    entry.setdefault("artifacts", []).append("00-core-definitions.md")
    state.update(
        {
            "feature": "demo",
            "createdAt": "2026-01-01T00:00:00Z",
            "updatedAt": "2026-01-01T00:00:00Z",
            "currentStage": "forge-3-specs",
            "pipelineStatus": "active",
        }
    )
    assert validate_state(state) == [], validate_state(state)


def test_stage_entry_returns_an_existing_entry_unchanged():
    state = {"stages": {"forge-1-prd": {"status": "complete", "version": 2}}}
    entry = FS._stage_entry(state, "forge-1-prd")
    assert entry == {"status": "complete", "version": 2}


def test_stage_entry_accepts_every_state_verb_stage():
    state: dict = {}
    for stage in FS.STATE_VERB_STAGES:
        assert FS._stage_entry(state, stage)["status"] == "pending"
    assert set(state["stages"]) == set(FS.STATE_VERB_STAGES)
