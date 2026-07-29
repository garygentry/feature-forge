"""R4 state-verb guards — the shared write machinery and the per-verb CLI contracts.

Covers the pieces every ``state-*`` verb reuses (item 007): the
``STATE_VERB_STAGES`` domain constant, the ``_now_iso`` stamp, the atomic
``_write_state``, the corrupt-file-refusing ``_load_state_for_write``,
``_commit_state``'s ``updatedAt`` refresh, and the ``_stage_entry`` bootstrap —
plus the end-to-end CLI contracts of ``state-enter``/``-artifact``/``-branch``/
``-note`` (item 008). ``state-complete`` (009) and ``state-decision``/``-ecr``
(010) extend this module further.

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


def _run(*argv: str) -> subprocess.CompletedProcess[str]:
    """Invoke `forge-session.py` out-of-process, matching conftest's run_cli style."""
    return subprocess.run(
        [sys.executable, str(FORGE_SESSION), *argv], capture_output=True, text=True
    )


def _state_of(tmp_path: Path, name: str = "demo") -> dict:
    """Read back the state file a verb just wrote, asserting it is schema-valid."""
    state = json.loads(
        (tmp_path / "specs" / name / FS.PIPELINE_STATE_FILENAME).read_text(encoding="utf-8")
    )
    assert validate_state(state) == [], validate_state(state)
    return state


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


# --------------------------------------------------------------------------- #
# Registration (item 008's four verbs)
# --------------------------------------------------------------------------- #

#: Every state verb registered so far — items 008 (enter/artifact/branch/note)
#: and 009 (complete). Item 010 (state-decision/-ecr) extends this tuple.
REGISTERED_STATE_VERBS = (
    "state-enter",
    "state-artifact",
    "state-complete",
    "state-branch",
    "state-note",
)


def test_every_verb_appears_in_the_module_docstring_usage_lines():
    usage = FS.__doc__ or ""
    for verb in REGISTERED_STATE_VERBS:
        assert f"forge-session.py {verb} " in usage, f"{verb} missing from the usage lines"


def test_every_verb_is_registered_as_a_subparser_and_dispatched():
    source = read(FORGE_SESSION)
    for verb in REGISTERED_STATE_VERBS:
        assert re.search(rf'sub\.add_parser\(\s*"{verb}"', source), f"{verb} has no subparser"
        assert f'if args.cmd == "{verb}":' in source, f"{verb} has no dispatch branch"
        assert _run(verb, "--help").returncode == 0, f"{verb} is not a registered subcommand"


def test_the_script_has_no_exit_1_branch():
    """The contract is 0/2 only — a `return 1` anywhere would break it."""
    source = read(FORGE_SESSION)
    assert not re.search(r"^\s+return 1$", source, re.M)
    assert not re.search(r"sys\.exit\(1\)", source)


# --------------------------------------------------------------------------- #
# state-enter
# --------------------------------------------------------------------------- #


def test_state_enter_stamps_the_stage_and_current_stage(tmp_path):
    _feature_dir(tmp_path)
    result = _run(
        "state-enter", "--feature", "demo", "--stage", "forge-1-prd",
        "--specs-dir", str(tmp_path / "specs"), "--json",
    )
    assert result.returncode == 0, result.stderr

    state = _state_of(tmp_path)
    entry = state["stages"]["forge-1-prd"]
    assert entry["status"] == "in-progress"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", entry["startedAt"])
    assert state["currentStage"] == "forge-1-prd"
    assert json.loads(result.stdout) == state


def test_state_enter_prints_a_one_line_summary_without_json(tmp_path):
    _feature_dir(tmp_path)
    result = _run(
        "state-enter", "--feature", "demo", "--stage", "forge-2-tech",
        "--specs-dir", str(tmp_path / "specs"),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "entered forge-2-tech (in-progress) for demo"


def test_state_enter_rejects_a_stage_outside_the_domain(tmp_path):
    _feature_dir(tmp_path)
    result = _run(
        "state-enter", "--feature", "demo", "--stage", "forge-9-nope",
        "--specs-dir", str(tmp_path / "specs"),
    )
    assert result.returncode != 0
    assert "invalid choice" in result.stderr


# --------------------------------------------------------------------------- #
# state-artifact
# --------------------------------------------------------------------------- #


def test_state_artifact_is_repeatable_and_deduplicates(tmp_path):
    _feature_dir(tmp_path)
    specs = str(tmp_path / "specs")
    base = ["state-artifact", "--feature", "demo", "--stage", "forge-3-specs", "--specs-dir", specs]

    assert _run(*base, "--path", "00-core.md", "--path", "01-layout.md").returncode == 0
    assert _state_of(tmp_path)["stages"]["forge-3-specs"]["artifacts"] == [
        "00-core.md",
        "01-layout.md",
    ]

    # A re-record of one tracked path plus one new path appends only the new one.
    assert _run(*base, "--path", "00-core.md", "--path", "03-state-verbs.md").returncode == 0
    assert _state_of(tmp_path)["stages"]["forge-3-specs"]["artifacts"] == [
        "00-core.md",
        "01-layout.md",
        "03-state-verbs.md",
    ]

    # An all-duplicates run is a no-op on the array but still exits 0.
    assert _run(*base, "--path", "00-core.md").returncode == 0
    assert len(_state_of(tmp_path)["stages"]["forge-3-specs"]["artifacts"]) == 3


def test_state_artifact_on_a_never_entered_stage_carries_a_status(tmp_path):
    """The `{"status": "pending"}` seed — `stageEntry` declares required: ["status"].

    Without it this write would persist a bare {"artifacts": [...]} at exit 0.
    """
    _feature_dir(tmp_path)
    result = _run(
        "state-artifact", "--feature", "demo", "--stage", "forge-3-specs",
        "--path", "00-core.md", "--specs-dir", str(tmp_path / "specs"),
    )
    assert result.returncode == 0, result.stderr

    entry = _state_of(tmp_path)["stages"]["forge-3-specs"]
    assert entry["status"] == "pending"
    assert entry["artifacts"] == ["00-core.md"]


def test_state_artifact_prints_a_one_line_summary_without_json(tmp_path):
    _feature_dir(tmp_path)
    result = _run(
        "state-artifact", "--feature", "demo", "--stage", "forge-3-specs",
        "--path", "00-core.md", "--path", "01-layout.md",
        "--specs-dir", str(tmp_path / "specs"),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == (
        "tracked forge-3-specs artifact(s): 00-core.md, 01-layout.md (2 total)"
    )


# --------------------------------------------------------------------------- #
# state-complete
# --------------------------------------------------------------------------- #


def _seed(tmp_path: Path, stages: dict, name: str = "demo") -> Path:
    """Create a feature dir pre-populated with a schema-valid state file."""
    feature_dir = _feature_dir(tmp_path, name)
    state = {
        "feature": name,
        "createdAt": "2026-01-01T00:00:00Z",
        "updatedAt": "2026-01-01T00:00:00Z",
        "currentStage": "forge-1-prd",
        "pipelineStatus": "active",
        "stages": stages,
    }
    assert validate_state(state) == [], validate_state(state)
    (feature_dir / FS.PIPELINE_STATE_FILENAME).write_text(json.dumps(state), encoding="utf-8")
    return feature_dir


def test_state_complete_records_the_full_completion_write(tmp_path):
    _feature_dir(tmp_path)
    result = _run(
        "state-complete", "--feature", "demo", "--stage", "forge-3-specs", "--version", "2",
        "--based-on", "forge-1-prd=3", "--based-on", "forge-2-tech=1",
        "--artifact", "00-core.md", "--artifact", "03-state-verbs.md",
        "--specs-dir", str(tmp_path / "specs"), "--json",
    )
    assert result.returncode == 0, result.stderr

    state = _state_of(tmp_path)  # asserts schema conformance
    entry = state["stages"]["forge-3-specs"]
    assert entry["status"] == "complete"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", entry["completedAt"])
    assert entry["version"] == 2
    assert entry["basedOnVersions"] == {"forge-1-prd": 3, "forge-2-tech": 1}
    assert entry["artifacts"] == ["00-core.md", "03-state-verbs.md"]
    assert entry["commitHash"] is None, "Commit 1 records a null hash"


def test_state_complete_with_no_based_on_records_an_empty_map(tmp_path):
    """forge-1-prd has no upstream — basedOnVersions is {} , not absent."""
    _feature_dir(tmp_path)
    result = _run(
        "state-complete", "--feature", "demo", "--stage", "forge-1-prd", "--version", "1",
        "--artifact", "PRD.md", "--specs-dir", str(tmp_path / "specs"),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "completed forge-1-prd v1 (commitHash: null)"
    assert _state_of(tmp_path)["stages"]["forge-1-prd"]["basedOnVersions"] == {}


def test_commit_hash_follow_up_touches_only_commit_hash(tmp_path):
    """Commit 2 of the Git Commit Protocol: record the hash, disturb nothing else."""
    _seed(
        tmp_path,
        {
            "forge-1-prd": {
                "status": "complete",
                "completedAt": "2026-01-01T00:00:00Z",
                "version": 2,
                "basedOnVersions": {},
                "artifacts": ["PRD.md"],
                "commitHash": None,
            }
        },
    )
    before = _state_of(tmp_path)["stages"]["forge-1-prd"]

    result = _run(
        "state-complete", "--feature", "demo", "--stage", "forge-1-prd", "--version", "2",
        "--commit-hash", "9a29e846ed510c3b245876a9bf4cc73b8cb60951",
        "--specs-dir", str(tmp_path / "specs"),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == (
        "recorded forge-1-prd commitHash: 9a29e846ed510c3b245876a9bf4cc73b8cb60951"
    )

    after = _state_of(tmp_path)["stages"]["forge-1-prd"]
    assert after["commitHash"] == "9a29e846ed510c3b245876a9bf4cc73b8cb60951"
    assert {k: v for k, v in after.items() if k != "commitHash"} == {
        k: v for k, v in before.items() if k != "commitHash"
    }, "the Commit-2 follow-up must leave status/version/artifacts intact"


def test_commit_hash_against_an_incomplete_stage_exits_2(tmp_path):
    """A typo'd --stage would otherwise write a lone {"commitHash": …} at exit 0,
    violating stageEntry's required: ["status"]."""
    _seed(tmp_path, {"forge-1-prd": {"status": "complete", "version": 1}})
    state_path = tmp_path / "specs" / "demo" / FS.PIPELINE_STATE_FILENAME
    before = state_path.read_bytes()

    result = _run(
        "state-complete", "--feature", "demo", "--stage", "forge-2-tech", "--version", "1",
        "--commit-hash", "deadbeef", "--specs-dir", str(tmp_path / "specs"),
    )
    assert result.returncode == 2, result.stdout
    assert result.stderr.strip() == (
        "Error: --commit-hash requires forge-2-tech to be complete (status: 'pending'); "
        "run state-complete without --commit-hash first"
    )
    assert state_path.read_bytes() == before, "the rejected follow-up must not write"


def test_commit_hash_against_a_partial_stage_names_its_actual_status(tmp_path):
    _seed(tmp_path, {"forge-5-loop": {"status": "in-progress"}})
    result = _run(
        "state-complete", "--feature", "demo", "--stage", "forge-5-loop", "--version", "1",
        "--commit-hash", "deadbeef", "--specs-dir", str(tmp_path / "specs"),
    )
    assert result.returncode == 2, result.stdout
    assert "status: 'in-progress'" in result.stderr


def test_partial_completion_keeps_every_completion_field(tmp_path):
    """A bare --status in-progress is forge-5-loop's PARTIAL COMPLETION (spec 03
    §11.2 row 14) — a real completion-with-artifacts that simply is not finished.

    Only `status` may differ from the complete branch: completedAt, version,
    basedOnVersions and artifacts are all still written (item 013 passes
    --based-on forge-4-backlog=N on exactly this call), commitHash is still reset,
    and the staleness cascade still fires.
    """
    _seed(
        tmp_path,
        {
            "forge-5-loop": {"status": "in-progress", "commitHash": "stale-hash"},
            "forge-6-docs": {
                "status": "complete",
                "version": 1,
                "basedOnVersions": {"forge-5-loop": 1},
            },
        },
    )
    result = _run(
        "state-complete", "--feature", "demo", "--stage", "forge-5-loop", "--version", "2",
        "--based-on", "forge-4-backlog=3", "--artifact", "src/thing.py",
        "--status", "in-progress", "--specs-dir", str(tmp_path / "specs"), "--json",
    )
    assert result.returncode == 0, result.stderr

    state = _state_of(tmp_path)
    entry = state["stages"]["forge-5-loop"]
    assert entry["status"] == "in-progress"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", entry["completedAt"])
    assert entry["version"] == 2
    assert entry["basedOnVersions"] == {"forge-4-backlog": 3}, "--based-on was discarded"
    assert entry["artifacts"] == ["src/thing.py"]
    assert entry["commitHash"] is None, "the partial branch still resets commitHash"
    assert state["stages"]["forge-6-docs"]["status"] == "stale", "the cascade must fire"
    assert json.loads(result.stdout)["_cascadedStale"] == ["forge-6-docs"]


def test_partial_completion_differs_from_complete_only_in_status(tmp_path):
    """The strongest form of the AC: run both branches over identical inputs and
    diff the resulting stage entries."""
    common = [
        "--stage", "forge-5-loop", "--version", "2",
        "--based-on", "forge-4-backlog=3", "--artifact", "src/thing.py",
    ]
    for name, extra in (("done", []), ("partial", ["--status", "in-progress"])):
        _feature_dir(tmp_path / name)
        assert _run(
            "state-complete", "--feature", "demo", *common, *extra,
            "--specs-dir", str(tmp_path / name / "specs"),
        ).returncode == 0

    done = _state_of(tmp_path / "done")["stages"]["forge-5-loop"]
    partial = _state_of(tmp_path / "partial")["stages"]["forge-5-loop"]
    assert done["status"] == "complete"
    assert partial["status"] == "in-progress"
    assert {k: v for k, v in done.items() if k not in ("status", "completedAt")} == {
        k: v for k, v in partial.items() if k not in ("status", "completedAt")
    }


def test_resumable_records_only_the_status(tmp_path):
    """The failed-Commit-1 revert (shared-conventions L245).

    Asserted field-by-field rather than by schema validation: stageEntry declares
    `status` and `completedAt` as independent optional properties, so a state that
    wrongly carried a completion stamp would still validate cleanly.
    """
    seeded = {
        "status": "complete",
        "version": 4,
        "basedOnVersions": {"forge-1-prd": 2},
        "artifacts": ["00-core.md"],
        "commitHash": "abc1234",
        "startedAt": "2026-01-01T00:00:00Z",
    }
    _seed(
        tmp_path,
        {
            "forge-3-specs": dict(seeded),
            "forge-4-backlog": {
                "status": "complete",
                "version": 1,
                "basedOnVersions": {"forge-3-specs": 4},
            },
        },
    )

    result = _run(
        "state-complete", "--feature", "demo", "--stage", "forge-3-specs", "--version", "9",
        "--based-on", "forge-1-prd=7", "--artifact", "ignored.md", "--resumable",
        "--specs-dir", str(tmp_path / "specs"), "--json",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["_cascadedStale"] == [], "no cascade off a failed commit"

    state = _state_of(tmp_path)
    entry = state["stages"]["forge-3-specs"]
    assert entry["status"] == "in-progress"
    assert entry.get("completedAt") is None, "a stage that never completed gets no stamp"
    assert entry["version"] == 4, "--version must not be written on the revert"
    assert entry["basedOnVersions"] == {"forge-1-prd": 2}, "--based-on must not be written"
    assert entry["artifacts"] == ["00-core.md"], "--artifact must not be written"
    assert entry["commitHash"] == "abc1234", "a recoverable hash must survive the revert"
    assert {k: v for k, v in entry.items() if k != "status"} == {
        k: v for k, v in seeded.items() if k != "status"
    }
    assert state["stages"]["forge-4-backlog"]["status"] == "complete", "no cascade"
    assert state["updatedAt"] != "2026-01-01T00:00:00Z", "the updatedAt refresh still happens"


def test_resumable_prints_a_revert_summary_without_json(tmp_path):
    _seed(tmp_path, {"forge-3-specs": {"status": "complete", "version": 1}})
    result = _run(
        "state-complete", "--feature", "demo", "--stage", "forge-3-specs", "--version", "1",
        "--resumable", "--specs-dir", str(tmp_path / "specs"),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "left forge-3-specs in-progress (resumable — no completion recorded)"


def test_resumable_with_an_explicit_status_complete_exits_2(tmp_path):
    """Reject the contradiction rather than silently forcing in-progress."""
    _seed(tmp_path, {"forge-3-specs": {"status": "complete", "version": 1}})
    state_path = tmp_path / "specs" / "demo" / FS.PIPELINE_STATE_FILENAME
    before = state_path.read_bytes()

    result = _run(
        "state-complete", "--feature", "demo", "--stage", "forge-3-specs", "--version", "1",
        "--resumable", "--status", "complete", "--specs-dir", str(tmp_path / "specs"),
    )
    assert result.returncode == 2, result.stdout
    assert result.stderr.strip() == (
        "Error: --resumable implies --status in-progress; do not pass --status complete"
    )
    assert state_path.read_bytes() == before


def test_resumable_with_an_explicit_status_in_progress_is_accepted(tmp_path):
    """The flag *implies* in-progress, so restating it is redundant, not a conflict."""
    _seed(tmp_path, {"forge-3-specs": {"status": "complete", "version": 1}})
    result = _run(
        "state-complete", "--feature", "demo", "--stage", "forge-3-specs", "--version", "1",
        "--resumable", "--status", "in-progress", "--specs-dir", str(tmp_path / "specs"),
    )
    assert result.returncode == 0, result.stderr
    assert _state_of(tmp_path)["stages"]["forge-3-specs"]["status"] == "in-progress"


def test_preserve_commit_hash_leaves_an_existing_hash(tmp_path):
    """The Git Commit Protocol's "nothing to commit" branch (L248)."""
    _seed(
        tmp_path,
        {"forge-1-prd": {"status": "complete", "version": 1, "commitHash": "abc1234"}},
    )
    result = _run(
        "state-complete", "--feature", "demo", "--stage", "forge-1-prd", "--version", "2",
        "--artifact", "PRD.md", "--preserve-commit-hash",
        "--specs-dir", str(tmp_path / "specs"),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "completed forge-1-prd v2 (commitHash: abc1234)"

    entry = _state_of(tmp_path)["stages"]["forge-1-prd"]
    assert entry["commitHash"] == "abc1234", "the reset must be skipped"
    assert entry["version"] == 2, "every other completion field is still written"


def test_without_preserve_commit_hash_an_existing_hash_is_reset(tmp_path):
    """The control for the test above — the default really does clear the hash."""
    _seed(
        tmp_path,
        {"forge-1-prd": {"status": "complete", "version": 1, "commitHash": "abc1234"}},
    )
    assert _run(
        "state-complete", "--feature", "demo", "--stage", "forge-1-prd", "--version", "2",
        "--specs-dir", str(tmp_path / "specs"),
    ).returncode == 0
    assert _state_of(tmp_path)["stages"]["forge-1-prd"]["commitHash"] is None


def test_a_malformed_based_on_token_exits_2_naming_the_token(tmp_path):
    for token, expected in (
        ("forge-1-prd", "Error: --based-on expects STAGE=N, got: 'forge-1-prd'"),
        ("forge-1-prd=two", "Error: --based-on version must be an integer: 'forge-1-prd=two'"),
        ("forge-1-prd=1.5", "Error: --based-on version must be an integer: 'forge-1-prd=1.5'"),
    ):
        _feature_dir(tmp_path / token, "demo")
        result = _run(
            "state-complete", "--feature", "demo", "--stage", "forge-2-tech", "--version", "1",
            "--based-on", token, "--specs-dir", str(tmp_path / token / "specs"),
        )
        assert result.returncode == 2, f"{token}: {result.stdout}"
        assert result.stderr.strip() == expected, token
        assert not (
            tmp_path / token / "specs" / "demo" / FS.PIPELINE_STATE_FILENAME
        ).exists(), f"{token}: a parse failure must not write state"


# --------------------------------------------------------------------------- #
# state-complete — the staleness cascade
# --------------------------------------------------------------------------- #


#: A downstream fixture exercising every cascade decision at once, against a
#: forge-1-prd completing at version 2.
_CASCADE_FIXTURE = {
    "forge-1-prd": {"status": "complete", "version": 1, "artifacts": ["PRD.md"]},
    # complete + built on the OLD version -> goes stale.
    "forge-3-specs": {
        "status": "complete", "version": 1, "basedOnVersions": {"forge-1-prd": 1},
    },
    # complete but already on the NEW version -> untouched ("older" is strict).
    "forge-4-backlog": {
        "status": "complete", "version": 1, "basedOnVersions": {"forge-1-prd": 2},
    },
    # built on the old version but NOT complete -> no artifact to stale.
    "forge-5-loop": {
        "status": "in-progress", "basedOnVersions": {"forge-1-prd": 1},
    },
    # complete but never referenced this upstream -> untouched.
    "forge-6-docs": {
        "status": "complete", "version": 1, "basedOnVersions": {"forge-5-loop": 1},
    },
}


def test_the_cascade_stales_only_downstream_stages_built_on_an_older_version(tmp_path):
    _seed(tmp_path, {k: dict(v) for k, v in _CASCADE_FIXTURE.items()})
    result = _run(
        "state-complete", "--feature", "demo", "--stage", "forge-1-prd", "--version", "2",
        "--artifact", "PRD.md", "--specs-dir", str(tmp_path / "specs"), "--json",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["_cascadedStale"] == ["forge-3-specs"]

    stages = _state_of(tmp_path)["stages"]
    assert stages["forge-3-specs"]["status"] == "stale"
    assert stages["forge-4-backlog"]["status"] == "complete", "an equal version is not older"
    assert stages["forge-5-loop"]["status"] == "in-progress", "only complete artifacts go stale"
    assert stages["forge-6-docs"]["status"] == "complete", "an unreferenced upstream is a no-op"


def test_the_cascade_prints_the_stale_stages_in_the_human_summary(tmp_path):
    _seed(tmp_path, {k: dict(v) for k, v in _CASCADE_FIXTURE.items()})
    result = _run(
        "state-complete", "--feature", "demo", "--stage", "forge-1-prd", "--version", "2",
        "--artifact", "PRD.md", "--specs-dir", str(tmp_path / "specs"),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == (
        "completed forge-1-prd v2 (commitHash: null); marked stale: forge-3-specs"
    )


def test_the_cascade_is_a_no_op_when_nothing_downstream_is_outdated(tmp_path):
    """The no-op case: a first completion with no downstream stages at all, and a
    re-completion at the SAME version with current downstream stages."""
    _feature_dir(tmp_path, "fresh")
    result = _run(
        "state-complete", "--feature", "fresh", "--stage", "forge-1-prd", "--version", "1",
        "--artifact", "PRD.md", "--specs-dir", str(tmp_path / "specs"), "--json",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["_cascadedStale"] == []
    assert "marked stale" not in result.stdout

    _seed(
        tmp_path,
        {
            "forge-1-prd": {"status": "complete", "version": 2},
            "forge-3-specs": {
                "status": "complete", "version": 1, "basedOnVersions": {"forge-1-prd": 2},
            },
        },
        name="current",
    )
    result = _run(
        "state-complete", "--feature", "current", "--stage", "forge-1-prd", "--version", "2",
        "--artifact", "PRD.md", "--specs-dir", str(tmp_path / "specs"), "--json",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["_cascadedStale"] == []
    assert _state_of(tmp_path, "current")["stages"]["forge-3-specs"]["status"] == "complete"


def test_the_cascade_never_stales_the_stage_that_just_completed(tmp_path):
    """forge-3-specs is itself a cascade target; completing it must not self-stale."""
    _seed(
        tmp_path,
        {
            "forge-3-specs": {
                "status": "complete", "version": 1, "basedOnVersions": {"forge-3-specs": 1},
            }
        },
    )
    result = _run(
        "state-complete", "--feature", "demo", "--stage", "forge-3-specs", "--version", "2",
        "--specs-dir", str(tmp_path / "specs"), "--json",
    )
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["_cascadedStale"] == []
    assert _state_of(tmp_path)["stages"]["forge-3-specs"]["status"] == "complete"


def test_cascade_targets_is_its_own_map_not_a_production_stages_slice(tmp_path):
    """Keying off PRODUCTION_STAGES ordering would put forge-2-tech in scope."""
    assert FS._CASCADE_TARGETS == (
        "forge-3-specs", "forge-4-backlog", "forge-5-loop", "forge-6-docs"
    )
    state = {
        "stages": {
            "forge-2-tech": {
                "status": "complete", "basedOnVersions": {"forge-1-prd": 1},
            }
        }
    }
    assert FS._cascade_staleness(state, "forge-1-prd", 2) == []
    assert state["stages"]["forge-2-tech"]["status"] == "complete"


def test_cascaded_stale_is_echo_only_and_never_persisted(tmp_path):
    _seed(tmp_path, {k: dict(v) for k, v in _CASCADE_FIXTURE.items()})
    result = _run(
        "state-complete", "--feature", "demo", "--stage", "forge-1-prd", "--version", "2",
        "--specs-dir", str(tmp_path / "specs"), "--json",
    )
    assert result.returncode == 0, result.stderr
    assert "_cascadedStale" in json.loads(result.stdout)

    on_disk = json.loads(
        (tmp_path / "specs" / "demo" / FS.PIPELINE_STATE_FILENAME).read_text(encoding="utf-8")
    )
    assert "_cascadedStale" not in on_disk


# --------------------------------------------------------------------------- #
# state-branch
# --------------------------------------------------------------------------- #


def test_state_branch_as_the_first_verb_satisfies_the_top_level_required_list(tmp_path):
    """Finding V-012: Branch Setup fires BEFORE Feature Directory Resolution and
    the Entry Stamp, so state-branch can genuinely be the first write."""
    _feature_dir(tmp_path)
    assert not (tmp_path / "specs" / "demo" / FS.PIPELINE_STATE_FILENAME).exists()

    result = _run(
        "state-branch", "--feature", "demo", "--branch", "forge/demo",
        "--specs-dir", str(tmp_path / "specs"), "--json",
    )
    assert result.returncode == 0, result.stderr

    state = _state_of(tmp_path)  # asserts schema validity, required list included
    assert state["branch"] == "forge/demo"
    required = ["feature", "createdAt", "updatedAt", "currentStage", "stages", "pipelineStatus"]
    assert [key for key in required if key not in state] == []


def test_state_branch_overwrites_an_existing_branch(tmp_path):
    """Branch Reconciliation's `adopt-current` re-records the resolved branch."""
    _feature_dir(tmp_path)
    specs = str(tmp_path / "specs")
    assert _run("state-branch", "--feature", "demo", "--branch", "old", "--specs-dir", specs).returncode == 0
    result = _run("state-branch", "--feature", "demo", "--branch", "new", "--specs-dir", specs)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "recorded branch for demo: new"
    assert _state_of(tmp_path)["branch"] == "new"


# --------------------------------------------------------------------------- #
# state-note
# --------------------------------------------------------------------------- #


def test_state_note_sets_the_top_level_notes_field(tmp_path):
    _feature_dir(tmp_path)
    note = "Rebaselined tokens at impl time."
    result = _run(
        "state-note", "--feature", "demo", "--note", note,
        "--specs-dir", str(tmp_path / "specs"), "--json",
    )
    assert result.returncode == 0, result.stderr
    assert _state_of(tmp_path)["notes"] == note
    assert json.loads(result.stdout)["notes"] == note


def test_state_note_overwrites_rather_than_appends(tmp_path):
    _feature_dir(tmp_path)
    specs = str(tmp_path / "specs")
    assert _run("state-note", "--feature", "demo", "--note", "first", "--specs-dir", specs).returncode == 0
    result = _run("state-note", "--feature", "demo", "--note", "second", "--specs-dir", specs)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "note set for demo (6 chars)"
    assert _state_of(tmp_path)["notes"] == "second"


# --------------------------------------------------------------------------- #
# Cross-verb invariants
# --------------------------------------------------------------------------- #


#: One minimal invocation per verb, for the invariants every verb must satisfy.
_VERB_INVOCATIONS = {
    "state-enter": ("--stage", "forge-1-prd"),
    "state-artifact": ("--stage", "forge-3-specs", "--path", "00-core.md"),
    "state-complete": ("--stage", "forge-1-prd", "--version", "1"),
    "state-branch": ("--branch", "forge/demo"),
    "state-note": ("--note", "a note"),
}


def test_every_verb_refreshes_updated_at_on_a_successful_write(tmp_path):
    for verb, extra in _VERB_INVOCATIONS.items():
        feature_dir = _feature_dir(tmp_path / verb)
        state_path = feature_dir / FS.PIPELINE_STATE_FILENAME
        state_path.write_text(
            json.dumps(
                {
                    "feature": "demo",
                    "createdAt": "2020-01-01T00:00:00Z",
                    "updatedAt": "2020-01-01T00:00:00Z",
                    "currentStage": "forge-1-prd",
                    "pipelineStatus": "active",
                    "stages": {},
                }
            ),
            encoding="utf-8",
        )
        result = _run(
            verb, "--feature", "demo", *extra, "--specs-dir", str(tmp_path / verb / "specs")
        )
        assert result.returncode == 0, f"{verb}: {result.stderr}"
        state = _state_of(tmp_path / verb)
        assert state["updatedAt"] != "2020-01-01T00:00:00Z", f"{verb} did not refresh updatedAt"
        assert state["createdAt"] == "2020-01-01T00:00:00Z", f"{verb} clobbered createdAt"


def test_every_verb_exits_2_on_an_unknown_feature(tmp_path):
    (tmp_path / "specs").mkdir()
    for verb, extra in _VERB_INVOCATIONS.items():
        result = _run(verb, "--feature", "nope", *extra, "--specs-dir", str(tmp_path / "specs"))
        assert result.returncode == 2, f"{verb}: expected exit 2, got {result.returncode}"
        assert result.stderr.startswith("Error:"), f"{verb}: {result.stderr!r}"
        assert "no feature directory at" in result.stderr, verb


def test_every_verb_refuses_a_corrupt_state_file_byte_intact(tmp_path):
    for verb, extra in _VERB_INVOCATIONS.items():
        state_path = _feature_dir(tmp_path / verb) / FS.PIPELINE_STATE_FILENAME
        state_path.write_bytes(b"{ not json")
        result = _run(
            verb, "--feature", "demo", *extra, "--specs-dir", str(tmp_path / verb / "specs")
        )
        assert result.returncode == 2, f"{verb}: {result.stdout}{result.stderr}"
        assert "refusing to overwrite it" in result.stderr, verb
        assert state_path.read_bytes() == b"{ not json", f"{verb} touched a corrupt file"


def test_every_verb_writes_schema_valid_state_for_a_nested_epic_member(tmp_path):
    for verb, extra in _VERB_INVOCATIONS.items():
        member = tmp_path / verb / "specs" / "big-epic" / "demo"
        member.mkdir(parents=True)
        result = _run(
            verb, "--feature", "demo", *extra, "--epic", "big-epic",
            "--specs-dir", str(tmp_path / verb / "specs"),
        )
        assert result.returncode == 0, f"{verb}: {result.stderr}"
        state = json.loads((member / FS.PIPELINE_STATE_FILENAME).read_text(encoding="utf-8"))
        assert validate_state(state) == [], f"{verb}: {validate_state(state)}"
