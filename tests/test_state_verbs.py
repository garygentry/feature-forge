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

#: The verbs item 008 adds. 009 (state-complete) and 010 (state-decision/-ecr)
#: extend this tuple as they land.
ITEM_008_VERBS = ("state-enter", "state-artifact", "state-branch", "state-note")


def test_every_verb_appears_in_the_module_docstring_usage_lines():
    usage = FS.__doc__ or ""
    for verb in ITEM_008_VERBS:
        assert f"forge-session.py {verb} " in usage, f"{verb} missing from the usage lines"


def test_every_verb_is_registered_as_a_subparser_and_dispatched():
    source = read(FORGE_SESSION)
    for verb in ITEM_008_VERBS:
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
