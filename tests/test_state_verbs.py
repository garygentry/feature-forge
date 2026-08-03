"""R4 state-verb guards — the shared write machinery and the per-verb CLI contracts.

Covers the pieces every ``state-*`` verb reuses (item 007): the
``STATE_VERB_STAGES`` domain constant, the ``_now_iso`` stamp, the atomic
``_write_state``, the corrupt-file-refusing ``_load_state_for_write``,
``_commit_state``'s ``updatedAt`` refresh, and the ``_stage_entry`` bootstrap —
plus the end-to-end CLI contracts of ``state-enter``/``-artifact``/``-branch``/
``-note`` (item 008), ``state-complete`` (009) and the two array-appending verbs
``state-decision``/``state-ecr`` (010) — all seven verbs.

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

from _forge_paths import REFERENCES, REPO_ROOT, SCRIPTS, SKILLS, read
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


#: A well-formed full Git object hash — the only shape a NEW `--commit-hash` write
#: accepts (03 §6.1, REQ-STATE-01).
_FULL_HASH = "9a29e846ed510c3b245876a9bf4cc73b8cb60951"

#: The three casings that must all be accepted, each recorded VERBATIM: the regex
#: accepts either case and nothing normalizes it, so a caller's case survives.
_ACCEPTED_HASHES = (
    ("lower", "9a29e846ed510c3b245876a9bf4cc73b8cb60951"),
    ("upper", "9A29E846ED510C3B245876A9BF4CC73B8CB60951"),
    ("mixed", "9a29E846eD510c3B245876A9bf4CC73b8cB60951"),
)

#: Every shape that must be refused BEFORE any mutation (07 §4.5). Lengths 0, 7,
#: 39 and 41 bracket the boundary; 7 is the legacy-looking abbreviation, which is
#: rejected on a WRITE rather than expanded through Git — while the same value
#: already sitting in a loaded state file keeps reading (REQ-STATE-02).
_REJECTED_HASHES = (
    ("empty", ""),
    ("legacy-7", "a1b2c3d"),
    ("39-hex", "0" * 39),
    ("41-hex", "0" * 41),
    ("non-hex", "z" * 40),
    ("hex-plus-space", "0" * 39 + " "),
    ("leading-space", " " + "0" * 39),
    ("trailing-newline", "0" * 40 + "\n"),
    ("internal-space", "0" * 20 + " " + "0" * 19),
    ("all-whitespace", " " * 40),
)


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
# Fail-closed write resolution (the flat-vs-nested collision)
# --------------------------------------------------------------------------- #

#: A minimal schema-valid state, used to give two same-named dirs a state file.
_SEED_STATE = {
    "feature": "api",
    "createdAt": "2020-01-01T00:00:00Z",
    "updatedAt": "2020-01-01T00:00:00Z",
    "currentStage": "forge-1-prd",
    "pipelineStatus": "active",
    "stages": {},
}


def _collision_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Seed a standalone `specs/api` AND an epic member `specs/checkout/api`.

    Both carry a state file, so a bare `--feature api` matches two candidates.
    Returns `(specs_dir, flat_state_path, nested_state_path)`.
    """
    specs = tmp_path / "specs"
    flat = specs / "api"
    nested = specs / "checkout" / "api"
    for directory in (flat, nested):
        directory.mkdir(parents=True)
        (directory / FS.PIPELINE_STATE_FILENAME).write_text(
            json.dumps(_SEED_STATE), encoding="utf-8"
        )
    return specs, flat / FS.PIPELINE_STATE_FILENAME, nested / FS.PIPELINE_STATE_FILENAME


#: The two verbs the regression pins: the entry stamp and the completion write.
_COLLISION_VERBS = {
    "state-enter": ("--stage", "forge-2-tech"),
    "state-complete": ("--stage", "forge-2-tech", "--version", "1"),
}


def test_a_flat_vs_nested_collision_exits_2_and_mutates_neither_file(tmp_path):
    """A bare `--feature` matching two state-carrying dirs must refuse to guess.

    The reader's `_resolve_feature_dir` returns the FLAT dir whenever it holds a
    state file, so before the fix `state-enter --feature api` silently mutated a
    standalone `specs/api` while the epic member `specs/checkout/api` it was
    meant for went untouched — cross-feature corruption at exit 0.
    """
    for verb, extra in _COLLISION_VERBS.items():
        specs, flat_state, nested_state = _collision_fixture(tmp_path / verb)
        before = (flat_state.read_bytes(), nested_state.read_bytes())

        result = _run(verb, "--feature", "api", *extra, "--specs-dir", str(specs))

        assert result.returncode == 2, f"{verb}: expected exit 2, got {result.returncode}"
        assert result.stderr.startswith("Error:"), f"{verb}: {result.stderr!r}"
        assert "ambiguous feature 'api'" in result.stderr, f"{verb}: {result.stderr!r}"
        assert "--epic" in result.stderr, f"{verb}: {result.stderr!r}"
        assert str(flat_state.parent) in result.stderr, f"{verb}: {result.stderr!r}"
        assert str(nested_state.parent) in result.stderr, f"{verb}: {result.stderr!r}"
        assert (flat_state.read_bytes(), nested_state.read_bytes()) == before, (
            f"{verb} mutated a state file while refusing"
        )


def test_epic_disambiguates_the_collision_and_leaves_the_standalone_intact(tmp_path):
    """With `--epic`, the member is written and the same-named standalone is not."""
    for verb, extra in _COLLISION_VERBS.items():
        specs, flat_state, nested_state = _collision_fixture(tmp_path / verb)
        flat_before = flat_state.read_bytes()

        result = _run(
            verb, "--feature", "api", *extra, "--epic", "checkout", "--specs-dir", str(specs)
        )

        assert result.returncode == 0, f"{verb}: {result.stderr}"
        assert flat_state.read_bytes() == flat_before, f"{verb} touched the standalone feature"
        written = json.loads(nested_state.read_text(encoding="utf-8"))
        assert validate_state(written) == [], f"{verb}: {validate_state(written)}"
        assert written["updatedAt"] != "2020-01-01T00:00:00Z", f"{verb} did not write the member"
        assert "forge-2-tech" in written["stages"], verb


def test_an_unambiguous_lone_flat_or_lone_nested_feature_still_resolves(tmp_path):
    """The fix must not cost the bare-name convenience where there is no collision."""
    lone_flat = tmp_path / "flat" / "specs" / "api"
    lone_flat.mkdir(parents=True)
    (lone_flat / FS.PIPELINE_STATE_FILENAME).write_text(json.dumps(_SEED_STATE), "utf-8")
    assert (
        FS._resolve_feature_dir_for_write(tmp_path / "flat" / "specs", "api", None) == lone_flat
    )

    lone_nested = tmp_path / "nested" / "specs" / "checkout" / "api"
    lone_nested.mkdir(parents=True)
    (lone_nested / FS.PIPELINE_STATE_FILENAME).write_text(json.dumps(_SEED_STATE), "utf-8")
    assert (
        FS._resolve_feature_dir_for_write(tmp_path / "nested" / "specs", "api", None)
        == lone_nested
    )

    # First write: no state file anywhere yet -> the flat path, so state-branch
    # (which fires before the entry stamp) still bootstraps a standalone feature.
    fresh = tmp_path / "fresh" / "specs"
    (fresh / "api").mkdir(parents=True)
    assert FS._resolve_feature_dir_for_write(fresh, "api", None) == fresh / "api"


def test_two_epics_with_a_same_named_member_are_ambiguous_not_a_flat_fallback(tmp_path):
    """Multi-nested previously fell back to a nonexistent flat path (exit 2, wrong reason)."""
    specs = tmp_path / "specs"
    for epic in ("checkout", "billing"):
        member = specs / epic / "api"
        member.mkdir(parents=True)
        (member / FS.PIPELINE_STATE_FILENAME).write_text(json.dumps(_SEED_STATE), "utf-8")

    result = _run(
        "state-enter", "--feature", "api", "--stage", "forge-2-tech", "--specs-dir", str(specs)
    )
    assert result.returncode == 2
    assert "ambiguous feature 'api'" in result.stderr, result.stderr
    assert "no feature directory at" not in result.stderr, result.stderr


def test_the_writer_is_not_more_permissive_than_the_canonical_resolver(tmp_path):
    """`_resolve_feature_dir` stays tolerant for the READ-ONLY stage-exit path.

    Its multi-match fallback is safe for a reader and unsafe for a writer, so the
    two resolvers must stay distinct — a "simplification" that points the write
    path back at the reader reintroduces the silent cross-feature write.
    """
    specs, _, _ = _collision_fixture(tmp_path)
    assert FS._resolve_feature_dir(specs, "api", None) == specs / "api"
    try:
        FS._resolve_feature_dir_for_write(specs, "api", None)
    except FS.UsageError as exc:
        assert "ambiguous" in str(exc)
    else:  # pragma: no cover - the guard exists to make this unreachable
        raise AssertionError("the write resolver silently preferred the flat dir")


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

#: All eight state verbs — R4 items 008 (enter/artifact/branch/note), 009
#: (complete) and 010 (decision/ecr), plus `state-verify`.
REGISTERED_STATE_VERBS = (
    "state-enter",
    "state-artifact",
    "state-complete",
    "state-branch",
    "state-note",
    "state-decision",
    "state-ecr",
    "state-verify",
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


def test_state_complete_accepts_every_40_hex_casing_verbatim(tmp_path):
    """REQ-STATE-01: 40 hex characters, in any case, recorded exactly as supplied."""
    for label, value in _ACCEPTED_HASHES:
        root = tmp_path / f"complete-{label}"
        _seed(root, {"forge-1-prd": {"status": "complete", "version": 1}})
        result = _run(
            "state-complete", "--feature", "demo", "--stage", "forge-1-prd",
            "--version", "1", "--commit-hash", value,
            "--specs-dir", str(root / "specs"),
        )
        assert result.returncode == 0, f"{label}: {result.stderr}"
        recorded = _state_of(root)["stages"]["forge-1-prd"]["commitHash"]
        assert recorded == value, f"{label}: case was not preserved ({recorded!r})"


def test_state_complete_rejects_a_short_or_malformed_hash_before_mutation(tmp_path):
    """Every non-40-hex shape fails, and the state file is left byte-identical.

    The check runs before `_load_state_for_write`, so the stage-not-complete guard
    below is never even consulted for a malformed value (03 §6.1).
    """
    for label, value in _REJECTED_HASHES:
        root = tmp_path / f"reject-{label}"
        _seed(root, {"forge-1-prd": {"status": "complete", "version": 1}})
        state_path = root / "specs" / "demo" / FS.PIPELINE_STATE_FILENAME
        before = state_path.read_bytes()
        result = _run(
            "state-complete", "--feature", "demo", "--stage", "forge-1-prd",
            "--version", "1", "--commit-hash", value,
            "--specs-dir", str(root / "specs"),
        )
        assert result.returncode == 2, f"{label}: exit {result.returncode}"
        assert result.stderr.startswith("Error:"), f"{label}: {result.stderr!r}"
        assert "40-character" in result.stderr, f"{label}: {result.stderr!r}"
        assert not result.stdout.strip(), f"{label} produced stdout"
        assert state_path.read_bytes() == before, f"{label} mutated state"


def test_commit_hash_against_an_incomplete_stage_exits_2(tmp_path):
    """A typo'd --stage would otherwise write a lone {"commitHash": …} at exit 0,
    violating stageEntry's required: ["status"]."""
    _seed(tmp_path, {"forge-1-prd": {"status": "complete", "version": 1}})
    state_path = tmp_path / "specs" / "demo" / FS.PIPELINE_STATE_FILENAME
    before = state_path.read_bytes()

    result = _run(
        "state-complete", "--feature", "demo", "--stage", "forge-2-tech", "--version", "1",
        "--commit-hash", _FULL_HASH, "--specs-dir", str(tmp_path / "specs"),
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
        "--commit-hash", _FULL_HASH, "--specs-dir", str(tmp_path / "specs"),
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
    # the PRD's most direct dependent: complete + built on the OLD version -> stale.
    "forge-2-tech": {
        "status": "complete", "version": 1, "basedOnVersions": {"forge-1-prd": 1},
    },
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
    assert json.loads(result.stdout)["_cascadedStale"] == ["forge-2-tech", "forge-3-specs"]

    stages = _state_of(tmp_path)["stages"]
    assert stages["forge-2-tech"]["status"] == "stale", "a PRD revision stales the tech spec"
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
        "completed forge-1-prd v2 (commitHash: null); "
        "marked stale: forge-2-tech, forge-3-specs"
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
    """Every cascade target must be self-exempt when it is the completing stage."""
    for stage in FS._CASCADE_TARGETS:
        _seed(
            tmp_path,
            {stage: {"status": "complete", "version": 1, "basedOnVersions": {stage: 1}}},
            name=stage,
        )
        result = _run(
            "state-complete", "--feature", stage, "--stage", stage, "--version", "2",
            "--specs-dir", str(tmp_path / "specs"), "--json",
        )
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["_cascadedStale"] == [], stage
        assert _state_of(tmp_path, stage)["stages"][stage]["status"] == "complete", stage


def test_cascade_targets_is_its_own_map_not_a_production_stages_slice(tmp_path):
    """The map is authored, not derived from PRODUCTION_STAGES.

    Its scope is tech..docs — the pre-R4 canon at baseline commit 9a29e846
    (skills/forge-1-prd/SKILL.md L134) named `forge-2-tech` FIRST among the
    stages a PRD revision invalidates, so a cascade that omitted it lost the
    most common revision path's most direct dependent.

    Two things a PRODUCTION_STAGES-derived scope would get wrong, both pinned
    here: the full tuple would put forge-1-prd in scope (no upstream stage is
    ever staled by a downstream completion), and a positional slice keyed off
    the completing stage would raise on forge-0-epic, which is a valid --stage
    but not a PRODUCTION_STAGES member.
    """
    assert FS._CASCADE_TARGETS == (
        "forge-2-tech", "forge-3-specs", "forge-4-backlog", "forge-5-loop", "forge-6-docs"
    )
    assert FS._CASCADE_TARGETS != FS.PRODUCTION_STAGES
    assert "forge-1-prd" not in FS._CASCADE_TARGETS

    # The regression this test now guards: a PRD bump stales the tech spec.
    state = {
        "stages": {
            "forge-2-tech": {
                "status": "complete", "basedOnVersions": {"forge-1-prd": 1},
            }
        }
    }
    assert FS._cascade_staleness(state, "forge-1-prd", 2) == ["forge-2-tech"]
    assert state["stages"]["forge-2-tech"]["status"] == "stale"

    # No upstream self-invalidation: completing a downstream stage never stales
    # forge-1-prd, even if it somehow recorded an older downstream version.
    upstream = {
        "stages": {
            "forge-1-prd": {
                "status": "complete", "basedOnVersions": {"forge-4-backlog": 1},
            }
        }
    }
    assert FS._cascade_staleness(upstream, "forge-4-backlog", 2) == []
    assert upstream["stages"]["forge-1-prd"]["status"] == "complete"

    # Not a positional slice: forge-0-epic has no index in PRODUCTION_STAGES.
    assert FS._cascade_staleness({"stages": {}}, "forge-0-epic", 2) == []


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
# state-decision
# --------------------------------------------------------------------------- #


def test_state_decision_appends_an_open_item_with_every_field(tmp_path):
    _feature_dir(tmp_path)
    result = _run(
        "state-decision", "--feature", "demo",
        "--question", "Which cache backend?",
        "--rationale", "forge-2-tech designs it",
        "--target-stage", "forge-2-tech",
        "--raised-by", "forge-1-prd",
        "--specs-dir", str(tmp_path / "specs"), "--json",
    )
    assert result.returncode == 0, result.stderr

    state = _state_of(tmp_path)
    assert len(state["deferredDecisions"]) == 1
    item = state["deferredDecisions"][0]
    assert item == {
        "question": "Which cache backend?",
        "rationale": "forge-2-tech designs it",
        "targetStage": "forge-2-tech",
        "raisedBy": "forge-1-prd",
        "raisedAt": item["raisedAt"],
        "status": "open",
    }
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", item["raisedAt"])
    assert json.loads(result.stdout) == state


def test_state_decision_omits_the_optional_keys_when_not_given(tmp_path):
    """`additionalProperties: false` — an absent optional must be ABSENT, not null."""
    _feature_dir(tmp_path)
    result = _run(
        "state-decision", "--feature", "demo", "--question", "Who owns retries?",
        "--raised-by", "forge-3-specs", "--specs-dir", str(tmp_path / "specs"),
    )
    assert result.returncode == 0, result.stderr

    item = _state_of(tmp_path)["deferredDecisions"][0]
    assert set(item) == {"question", "raisedBy", "raisedAt", "status"}


def test_state_decision_always_records_status_open(tmp_path):
    """The recorder never resolves — only the target stage flips open→addressed."""
    _feature_dir(tmp_path)
    assert _run(
        "state-decision", "--feature", "demo", "--question", "q",
        "--raised-by", "forge-4-backlog", "--specs-dir", str(tmp_path / "specs"),
    ).returncode == 0
    assert _state_of(tmp_path)["deferredDecisions"][0]["status"] == "open"


def test_repeated_state_decision_invocations_append(tmp_path):
    _feature_dir(tmp_path)
    specs = str(tmp_path / "specs")
    for question in ("first?", "second?", "third?"):
        assert _run(
            "state-decision", "--feature", "demo", "--question", question,
            "--raised-by", "forge-1-prd", "--specs-dir", specs,
        ).returncode == 0

    items = _state_of(tmp_path)["deferredDecisions"]
    assert [item["question"] for item in items] == ["first?", "second?", "third?"]


def test_state_decision_rejects_an_out_of_enum_raised_by(tmp_path):
    """forge-5-loop/forge-6-docs may be a targetStage but can never RAISE one."""
    _feature_dir(tmp_path)
    result = _run(
        "state-decision", "--feature", "demo", "--question", "q",
        "--raised-by", "forge-5-loop", "--specs-dir", str(tmp_path / "specs"),
    )
    assert result.returncode != 0
    assert "invalid choice" in result.stderr
    assert not (tmp_path / "specs" / "demo" / FS.PIPELINE_STATE_FILENAME).exists()


def test_state_decision_rejects_an_out_of_enum_target_stage(tmp_path):
    _feature_dir(tmp_path)
    result = _run(
        "state-decision", "--feature", "demo", "--question", "q",
        "--raised-by", "forge-1-prd", "--target-stage", "forge-0-epic",
        "--specs-dir", str(tmp_path / "specs"),
    )
    assert result.returncode != 0
    assert "invalid choice" in result.stderr


def test_state_decision_prints_a_one_line_summary_without_json(tmp_path):
    _feature_dir(tmp_path)
    specs = str(tmp_path / "specs")
    result = _run(
        "state-decision", "--feature", "demo", "--question", "q",
        "--target-stage", "forge-2-tech", "--raised-by", "forge-1-prd", "--specs-dir", specs,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == (
        "deferred decision recorded (raisedBy forge-1-prd → forge-2-tech)"
    )

    untargeted = _run(
        "state-decision", "--feature", "demo", "--question", "q2",
        "--raised-by", "forge-1-prd", "--specs-dir", specs,
    )
    assert untargeted.returncode == 0, untargeted.stderr
    assert untargeted.stdout.strip() == (
        "deferred decision recorded (raisedBy forge-1-prd, no target stage)"
    )


# --------------------------------------------------------------------------- #
# state-ecr
# --------------------------------------------------------------------------- #


_ECR_ARGS = (
    "--kind", "add-feature",
    "--target", "shared-conventions-split",
    "--rationale", "R7 emerged as a distinct feature",
    "--raised-by", "forge-2-tech",
)


def test_state_ecr_appends_an_open_item_with_all_seven_fields(tmp_path):
    _feature_dir(tmp_path)
    result = _run(
        "state-ecr", "--feature", "demo", *_ECR_ARGS, "--blocks-current", "false",
        "--specs-dir", str(tmp_path / "specs"), "--json",
    )
    assert result.returncode == 0, result.stderr

    state = _state_of(tmp_path)
    assert len(state["epicChangeRequests"]) == 1
    item = state["epicChangeRequests"][0]
    assert item == {
        "kind": "add-feature",
        "target": "shared-conventions-split",
        "rationale": "R7 emerged as a distinct feature",
        "blocksCurrent": False,
        "raisedBy": "forge-2-tech",
        "raisedAt": item["raisedAt"],
        "status": "open",
    }
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", item["raisedAt"])
    assert json.loads(result.stdout) == state


def test_state_ecr_parses_blocks_current_as_a_real_boolean(tmp_path):
    """`blocksCurrent` is schema-typed boolean and routes the stage exit — not "true"."""
    _feature_dir(tmp_path)
    assert _run(
        "state-ecr", "--feature", "demo", *_ECR_ARGS, "--blocks-current", "TRUE",
        "--specs-dir", str(tmp_path / "specs"),
    ).returncode == 0
    assert _state_of(tmp_path)["epicChangeRequests"][0]["blocksCurrent"] is True


def test_repeated_state_ecr_invocations_append(tmp_path):
    _feature_dir(tmp_path)
    specs = str(tmp_path / "specs")
    for target in ("alpha", "beta"):
        assert _run(
            "state-ecr", "--feature", "demo", "--kind", "redep", "--target", target,
            "--rationale", "why", "--raised-by", "forge-1-prd",
            "--blocks-current", "true", "--specs-dir", specs,
        ).returncode == 0

    items = _state_of(tmp_path)["epicChangeRequests"]
    assert [item["target"] for item in items] == ["alpha", "beta"]


def test_blocks_current_rejects_anything_but_true_or_false(tmp_path):
    _feature_dir(tmp_path)
    for bad in ("yes", "1", "", "True false", "no"):
        result = _run(
            "state-ecr", "--feature", "demo", *_ECR_ARGS, "--blocks-current", bad,
            "--specs-dir", str(tmp_path / "specs"),
        )
        assert result.returncode == 2, f"{bad!r}: expected exit 2, got {result.returncode}"
        assert result.stderr.strip() == (
            f"Error: --blocks-current expects true|false, got: {bad!r}"
        ), result.stderr
    assert not (tmp_path / "specs" / "demo" / FS.PIPELINE_STATE_FILENAME).exists()


def test_state_ecr_rejects_an_out_of_enum_kind_and_raised_by(tmp_path):
    _feature_dir(tmp_path)
    specs = str(tmp_path / "specs")
    bad_kind = _run(
        "state-ecr", "--feature", "demo", "--kind", "rename", "--target", "t",
        "--rationale", "why", "--raised-by", "forge-2-tech",
        "--blocks-current", "false", "--specs-dir", specs,
    )
    assert bad_kind.returncode != 0
    assert "invalid choice" in bad_kind.stderr

    bad_raiser = _run(
        "state-ecr", "--feature", "demo", *_ECR_ARGS[:6], "--raised-by", "forge-3-specs",
        "--blocks-current", "false", "--specs-dir", specs,
    )
    assert bad_raiser.returncode != 0
    assert "invalid choice" in bad_raiser.stderr


def test_state_ecr_prints_a_one_line_summary_without_json(tmp_path):
    _feature_dir(tmp_path)
    result = _run(
        "state-ecr", "--feature", "demo", *_ECR_ARGS, "--blocks-current", "false",
        "--specs-dir", str(tmp_path / "specs"),
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == (
        "epic change request recorded (add-feature → shared-conventions-split, "
        "blocksCurrent=false)"
    )


# --------------------------------------------------------------------------- #
# state-verify (the eighth verb)
# --------------------------------------------------------------------------- #


def _verify_fixture(
    tmp_path: Path, stage: str = "forge-1-prd", version: int = 1, name: str = "demo"
) -> Path:
    """Create a feature whose ``stage`` is complete at ``version``; return specs dir."""
    specs = _feature_dir(tmp_path, name).parent
    result = _run(
        "state-complete", "--feature", name, "--stage", stage,
        "--version", str(version), "--artifact", "PRD.md", "--specs-dir", str(specs),
    )
    assert result.returncode == 0, result.stderr
    return specs


def _verify(specs: Path, *extra: str, name: str = "demo") -> subprocess.CompletedProcess[str]:
    """Run ``state-verify`` against ``specs`` for feature ``name``."""
    return _run("state-verify", "--feature", name, *extra, "--specs-dir", str(specs))


def _entry(specs: Path, key: str = "forge-verify-prd", name: str = "demo") -> dict:
    """Read one verify entry back off disk, asserting the whole file stays valid."""
    state = json.loads((specs / name / FS.PIPELINE_STATE_FILENAME).read_text(encoding="utf-8"))
    assert validate_state(state) == [], validate_state(state)
    return state["stages"][key]


def test_state_verify_registers_exactly_the_spec_flags_and_excludes_docs():
    """03 §3.1's surface: forge-6-docs has no verification token, so no entry."""
    help_text = _run("state-verify", "--help").stdout
    for flag in (
        "--feature", "--stage", "--status", "--findings-file", "--findings-count",
        "--verified-stage-version", "--commit-hash", "--epic", "--specs-dir", "--json",
    ):
        assert flag in help_text, f"{flag} is not registered"
    assert list(FS.VERIFY_STAGES) == [
        "forge-0-epic", "forge-1-prd", "forge-2-tech",
        "forge-3-specs", "forge-4-backlog", "forge-5-loop",
    ]
    assert "forge-6-docs" not in FS.VERIFY_STAGES
    assert list(FS.VERIFY_RESULT_STATUSES) == [
        "auto-verify-pending", "passed", "findings-reported",
        "findings-applied", "skipped",
    ]


def test_state_verify_rejects_the_docs_stage(tmp_path):
    specs = _verify_fixture(tmp_path)
    result = _verify(specs, "--stage", "forge-6-docs", "--status", "skipped")
    assert result.returncode == 2
    assert "invalid choice" in result.stderr


def test_state_verify_schedules_auto_verify_debt(tmp_path):
    specs = _verify_fixture(tmp_path)
    assert _verify(specs, "--stage", "forge-1-prd",
                   "--status", "auto-verify-pending").returncode == 0
    entry = _entry(specs)
    assert entry["status"] == "auto-verify-pending"
    assert entry["scheduledStageVersion"] == 1
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", entry["scheduledAt"])
    assert entry["commitHash"] is None
    assert "verifiedAt" not in entry and "verifiedStageVersion" not in entry


def test_state_verify_passed_records_the_current_version(tmp_path):
    specs = _verify_fixture(tmp_path)
    assert _verify(specs, "--stage", "forge-1-prd", "--status", "passed",
                   "--verified-stage-version", "1").returncode == 0
    entry = _entry(specs)
    assert entry["status"] == "passed"
    assert entry["verifiedStageVersion"] == 1
    assert entry["commitHash"] is None, "Commit 1 records a null hash"
    assert "findingsFile" not in entry and "fixedAt" not in entry


def test_state_verify_passed_accepts_a_zero_findings_count(tmp_path):
    """'verified with nothing found' is legal; a non-zero count is not."""
    specs = _verify_fixture(tmp_path)
    assert _verify(specs, "--stage", "forge-1-prd", "--status", "passed",
                   "--verified-stage-version", "1",
                   "--findings-count", "0").returncode == 0
    assert _entry(specs)["status"] == "passed"

    result = _verify(specs, "--stage", "forge-1-prd", "--status", "passed",
                     "--verified-stage-version", "1", "--findings-count", "2")
    assert result.returncode == 2
    assert "findings-reported" in result.stderr


def test_state_verify_findings_reported_records_the_report(tmp_path):
    specs = _verify_fixture(tmp_path)
    assert _verify(
        specs, "--stage", "forge-1-prd", "--status", "findings-reported",
        "--findings-file", "verify/prd-findings.md", "--findings-count", "0",
        "--verified-stage-version", "1",
    ).returncode == 0
    entry = _entry(specs)
    assert entry["findingsFile"] == "verify/prd-findings.md"
    # 0 is meaningful for findings-reported and is NOT the same as an absent key.
    assert entry["findingsCount"] == 0
    assert entry["verifiedStageVersion"] == 1


def test_state_verify_terminal_writes_delete_the_scheduling_keys(tmp_path):
    """DELETE, not null — `VerifyEntry` is total=False, so absent means unscheduled."""
    for status, extra in (
        ("passed", ("--verified-stage-version", "1")),
        ("skipped", ()),
        (
            "findings-reported",
            ("--findings-file", "verify/f.md", "--findings-count", "1",
             "--verified-stage-version", "1"),
        ),
    ):
        specs = _verify_fixture(tmp_path / status)
        assert _verify(specs, "--stage", "forge-1-prd",
                       "--status", "auto-verify-pending").returncode == 0
        assert "scheduledAt" in _entry(specs)
        assert _verify(specs, "--stage", "forge-1-prd",
                       "--status", status, *extra).returncode == 0
        entry = _entry(specs)
        assert "scheduledAt" not in entry, f"{status} nulled rather than deleted"
        assert "scheduledStageVersion" not in entry, status


def test_state_verify_skipped_clears_every_result_field(tmp_path):
    specs = _verify_fixture(tmp_path)
    assert _verify(
        specs, "--stage", "forge-1-prd", "--status", "findings-reported",
        "--findings-file", "verify/f.md", "--findings-count", "3",
        "--verified-stage-version", "1",
    ).returncode == 0
    assert _verify(specs, "--stage", "forge-1-prd", "--status", "skipped").returncode == 0
    assert _entry(specs) == {"status": "skipped", "commitHash": None}


def test_state_verify_scheduling_refuses_to_clobber_a_current_revision_report(tmp_path):
    """Scheduling REPLACES the entry, so a report at the current revision would
    lose ``findingsFile``/``findingsCount`` and break the later
    ``findings-applied`` precondition (REQ-EXIT-04 through the CLI)."""
    specs = _verify_fixture(tmp_path)
    assert _verify(
        specs, "--stage", "forge-1-prd", "--status", "findings-reported",
        "--findings-file", "verify/f.md", "--findings-count", "3",
        "--verified-stage-version", "1",
    ).returncode == 0
    before = _state_bytes(specs)

    result = _verify(specs, "--stage", "forge-1-prd", "--status", "auto-verify-pending")

    assert result.returncode == 2
    assert "would replace" in result.stderr
    assert _state_bytes(specs) == before, "mutated on a rejected write"
    # The report survives, so the applied transition still works.
    assert _verify(specs, "--stage", "forge-1-prd",
                   "--status", "findings-applied").returncode == 0


def test_state_verify_scheduling_supersedes_a_stale_report(tmp_path):
    """A report against a since-revised artifact is superseded normally."""
    specs = _verify_fixture(tmp_path)
    assert _verify(
        specs, "--stage", "forge-1-prd", "--status", "findings-reported",
        "--findings-file", "verify/f.md", "--findings-count", "3",
        "--verified-stage-version", "1",
    ).returncode == 0
    assert _run(
        "state-complete", "--feature", "demo", "--stage", "forge-1-prd",
        "--version", "2", "--artifact", "PRD.md", "--specs-dir", str(specs),
    ).returncode == 0

    assert _verify(specs, "--stage", "forge-1-prd",
                   "--status", "auto-verify-pending").returncode == 0
    entry = _entry(specs)
    assert entry["status"] == "auto-verify-pending"
    assert entry["scheduledStageVersion"] == 2


def test_state_verify_findings_applied_preserves_the_report_and_clears_freshness(tmp_path):
    specs = _verify_fixture(tmp_path)
    assert _verify(
        specs, "--stage", "forge-1-prd", "--status", "findings-reported",
        "--findings-file", "verify/f.md", "--findings-count", "3",
        "--verified-stage-version", "1",
    ).returncode == 0
    assert _verify(specs, "--stage", "forge-1-prd",
                   "--status", "findings-applied").returncode == 0

    entry = _entry(specs)
    assert entry["status"] == "findings-applied"
    assert entry["findingsFile"] == "verify/f.md" and entry["findingsCount"] == 3
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", entry["fixedAt"])
    assert entry["commitHash"] is None
    # The whole point (03 §3.3): an interruption between fix and re-verify must not
    # be able to advance the pipeline, so freshness is left UNRESOLVED.
    assert "verifiedStageVersion" not in entry
    assert "verifiedAt" not in entry


def test_state_verify_findings_applied_accepts_matching_metadata_and_rejects_drift(tmp_path):
    specs = _verify_fixture(tmp_path)
    reported = (
        "--stage", "forge-1-prd", "--status", "findings-reported",
        "--findings-file", "verify/f.md", "--findings-count", "3",
        "--verified-stage-version", "1",
    )
    assert _verify(specs, *reported).returncode == 0
    assert _verify(
        specs, "--stage", "forge-1-prd", "--status", "findings-applied",
        "--findings-file", "verify/f.md", "--findings-count", "3",
    ).returncode == 0

    assert _verify(specs, *reported).returncode == 0
    for bad in (("--findings-count", "4"), ("--findings-file", "verify/other.md")):
        result = _verify(specs, "--stage", "forge-1-prd",
                         "--status", "findings-applied", *bad)
        assert result.returncode == 2, bad
        assert "does not match the recorded report" in result.stderr, bad


def test_state_verify_findings_applied_requires_a_prior_report(tmp_path):
    for prior in (None, "passed", "skipped", "auto-verify-pending"):
        specs = _verify_fixture(tmp_path / str(prior))
        if prior is not None:
            extra = ("--verified-stage-version", "1") if prior == "passed" else ()
            assert _verify(specs, "--stage", "forge-1-prd",
                           "--status", prior, *extra).returncode == 0
        before = _state_bytes(specs)
        result = _verify(specs, "--stage", "forge-1-prd", "--status", "findings-applied")
        assert result.returncode == 2, prior
        assert "requires an existing forge-verify-prd entry" in result.stderr, prior
        assert _state_bytes(specs) == before, f"{prior}: mutated on a rejected write"


def test_state_verify_findings_applied_rejects_a_verified_stage_version(tmp_path):
    specs = _verify_fixture(tmp_path)
    assert _verify(
        specs, "--stage", "forge-1-prd", "--status", "findings-reported",
        "--findings-file", "verify/f.md", "--findings-count", "1",
        "--verified-stage-version", "1",
    ).returncode == 0
    before = _state_bytes(specs)
    result = _verify(specs, "--stage", "forge-1-prd", "--status", "findings-applied",
                     "--verified-stage-version", "1")
    assert result.returncode == 2
    assert "deliberately CLEARS freshness" in result.stderr
    assert _state_bytes(specs) == before


def _state_bytes(specs: Path, name: str = "demo") -> bytes:
    """Raw bytes of a feature's state file (b"" when it does not exist yet)."""
    path = specs / name / FS.PIPELINE_STATE_FILENAME
    return path.read_bytes() if path.exists() else b""


def test_state_verify_rejects_a_stale_zero_or_negative_version(tmp_path):
    for status, extra in (
        ("passed", ()),
        ("findings-reported", ("--findings-file", "verify/f.md", "--findings-count", "1")),
    ):
        specs = _verify_fixture(tmp_path / status, version=2)
        before = _state_bytes(specs)
        for bad in ("1", "3", "0", "-1"):
            result = _verify(specs, "--stage", "forge-1-prd", "--status", status,
                             *extra, "--verified-stage-version", bad)
            assert result.returncode == 2, f"{status} {bad}"
            assert result.stderr.startswith("Error:"), f"{status} {bad}: {result.stderr!r}"
            assert _state_bytes(specs) == before, f"{status} {bad} mutated state"
        assert _verify(specs, "--stage", "forge-1-prd", "--status", status, *extra,
                       "--verified-stage-version", "2").returncode == 0


def test_state_verify_rejects_a_boolean_version_at_the_callable(tmp_path):
    """argparse's `type=int` never yields a bool; the callable still must refuse one.

    `bool` is an `int` subclass, so an unguarded check would record `True` as
    version 1 — a freshness ledger entry for a revision that never existed.
    """
    specs = _verify_fixture(tmp_path)
    before = _state_bytes(specs)
    try:
        FS.cmd_state_verify(
            "demo", "forge-1-prd", specs, None, status="passed",
            verified_stage_version=True,
        )
    except FS.UsageError as exc:
        assert "positive integer" in str(exc)
    else:
        raise AssertionError("a boolean --verified-stage-version was accepted")
    assert _state_bytes(specs) == before


def test_state_verify_requires_a_recorded_artifact_version(tmp_path):
    """Everything but `skipped` needs an artifact revision to verify against."""
    specs = _feature_dir(tmp_path).parent
    for status, extra in (
        ("auto-verify-pending", ()),
        ("passed", ("--verified-stage-version", "1")),
    ):
        result = _verify(specs, "--stage", "forge-1-prd", "--status", status, *extra)
        assert result.returncode == 2, status
        assert "no recorded version" in result.stderr, status
    assert _verify(specs, "--stage", "forge-1-prd", "--status", "skipped").returncode == 0


def test_state_verify_rejects_findings_metadata_on_pending_and_skipped(tmp_path):
    for status in ("auto-verify-pending", "skipped"):
        specs = _verify_fixture(tmp_path / status)
        before = _state_bytes(specs)
        for bad in (
            ("--findings-file", "verify/f.md"),
            ("--findings-count", "1"),
            ("--verified-stage-version", "1"),
        ):
            result = _verify(specs, "--stage", "forge-1-prd", "--status", status, *bad)
            assert result.returncode == 2, f"{status} {bad}"
            assert "does not accept" in result.stderr, f"{status} {bad}"
            assert _state_bytes(specs) == before, f"{status} {bad}"


def test_state_verify_passed_requires_a_count_with_an_advisory_file(tmp_path):
    """An advisory report is file + count together; half a record is refused."""
    specs = _verify_fixture(tmp_path)
    before = _state_bytes(specs)
    result = _verify(specs, "--stage", "forge-1-prd", "--status", "passed",
                     "--verified-stage-version", "1", "--findings-file", "verify/f.md")
    assert result.returncode == 2
    assert "requires --findings-count" in result.stderr
    assert _state_bytes(specs) == before


def test_state_verify_passed_records_an_advisory_report(tmp_path):
    """An advisory-only report (no error/gap) resolves as `passed` WITH the
    report attached, so it never routes to forge-fix and stays discoverable."""
    specs = _verify_fixture(tmp_path)
    assert _verify(
        specs, "--stage", "forge-1-prd", "--status", "passed",
        "--findings-file", "verify/advisories.md", "--findings-count", "3",
        "--verified-stage-version", "1",
    ).returncode == 0
    entry = _entry(specs)
    assert entry["status"] == "passed"
    assert entry["findingsFile"] == "verify/advisories.md"
    assert entry["findingsCount"] == 3
    assert entry["verifiedStageVersion"] == 1
    assert entry["commitHash"] is None


def test_state_verify_plain_passed_keeps_the_report_free_shape(tmp_path):
    """A bare zero count still records no report keys — the plain 'verified
    clean' entry keeps its pre-advisory shape."""
    specs = _verify_fixture(tmp_path)
    assert _verify(specs, "--stage", "forge-1-prd", "--status", "passed",
                   "--verified-stage-version", "1",
                   "--findings-count", "0").returncode == 0
    entry = _entry(specs)
    assert "findingsFile" not in entry and "findingsCount" not in entry


def test_state_verify_findings_reported_requires_its_full_metadata(tmp_path):
    specs = _verify_fixture(tmp_path)
    before = _state_bytes(specs)
    for extra in (
        ("--findings-file", "verify/f.md", "--findings-count", "1"),   # no version
        ("--findings-count", "1", "--verified-stage-version", "1"),    # no file
        ("--findings-file", "verify/f.md", "--verified-stage-version", "1"),  # no count
        ("--findings-file", "verify/f.md", "--findings-count", "-1",
         "--verified-stage-version", "1"),                             # negative count
    ):
        result = _verify(specs, "--stage", "forge-1-prd",
                         "--status", "findings-reported", *extra)
        assert result.returncode == 2, extra
        assert result.stderr.startswith("Error:"), extra
        assert _state_bytes(specs) == before, extra


#: `--findings-file` values that must be refused before any mutation (03 §7.1,
#: REQ-SEC-01). The stored value is followed verbatim by forge-fix, so it gets the
#: same containment treatment as the write target itself.
#: A NUL byte is absent here on purpose: `subprocess` cannot put one in argv at all
#: (ValueError before the process starts), so that row is exercised at the callable
#: level below, where stage-exit will also reach this writer.
_UNSAFE_FINDINGS_FILES = (
    "/etc/passwd",
    "../../escape.md",
    "verify/../../escape.md",
    "verify/bell\x07.md",
    "verify/newline\n.md",
    "",
)


def test_state_verify_rejects_an_unsafe_findings_file_before_mutation(tmp_path):
    specs = _verify_fixture(tmp_path)
    before = _state_bytes(specs)
    for bad in _UNSAFE_FINDINGS_FILES:
        result = _verify(
            specs, "--stage", "forge-1-prd", "--status", "findings-reported",
            "--findings-file", bad, "--findings-count", "1",
            "--verified-stage-version", "1",
        )
        assert result.returncode == 2, f"{bad!r} was accepted"
        assert result.stderr.startswith("Error:"), f"{bad!r}: {result.stderr!r}"
        assert "--findings-file" in result.stderr, f"{bad!r}: {result.stderr!r}"
        assert _state_bytes(specs) == before, f"{bad!r} mutated state"


def test_state_verify_rejects_a_nul_bearing_findings_file_at_the_callable(tmp_path):
    """subprocess refuses a NUL in argv, so this row can only be reached in-process."""
    specs = _verify_fixture(tmp_path)
    before = _state_bytes(specs)
    try:
        FS.cmd_state_verify(
            "demo", "forge-1-prd", specs, None, status="findings-reported",
            findings_file="verify/\x00truncated.md", findings_count=1,
            verified_stage_version=1,
        )
    except FS.UsageError as exc:
        assert "control character" in str(exc)
    else:
        raise AssertionError("a NUL-bearing --findings-file was accepted")
    assert _state_bytes(specs) == before


def test_state_verify_rejects_a_findings_file_that_escapes_through_a_symlink(tmp_path):
    specs = _verify_fixture(tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    (specs / "demo" / "elsewhere").symlink_to(outside, target_is_directory=True)
    before = _state_bytes(specs)

    result = _verify(
        specs, "--stage", "forge-1-prd", "--status", "findings-reported",
        "--findings-file", "elsewhere/f.md", "--findings-count", "1",
        "--verified-stage-version", "1",
    )
    assert result.returncode == 2, result.stdout
    assert "escapes the feature directory" in result.stderr
    assert _state_bytes(specs) == before


def test_state_verify_accepts_a_findings_file_that_does_not_exist_yet(tmp_path):
    """The verb records the path the skill asserts it wrote — it never stats it."""
    specs = _verify_fixture(tmp_path)
    assert _verify(
        specs, "--stage", "forge-1-prd", "--status", "findings-reported",
        "--findings-file", "verify/not-written-yet.md", "--findings-count", "2",
        "--verified-stage-version", "1",
    ).returncode == 0
    assert _entry(specs)["findingsFile"] == "verify/not-written-yet.md"


def test_state_verify_rejects_neither_mode_and_mixed_mode(tmp_path):
    specs = _verify_fixture(tmp_path)
    before = _state_bytes(specs)
    full_hash = "0123456789abcdef0123456789abcdef01234567"

    neither = _verify(specs, "--stage", "forge-1-prd")
    assert neither.returncode == 2
    assert neither.stderr.startswith("Error:")
    assert "exactly one mode" in neither.stderr
    assert _state_bytes(specs) == before

    mixed = _verify(specs, "--stage", "forge-1-prd", "--status", "passed",
                    "--verified-stage-version", "1", "--commit-hash", full_hash)
    assert mixed.returncode == 2
    assert mixed.stderr.startswith("Error:")
    assert "mutually exclusive" in mixed.stderr
    assert _state_bytes(specs) == before
    assert not neither.stdout.strip() and not mixed.stdout.strip()


def test_state_verify_leaves_unrelated_entries_and_unknown_fields_alone(tmp_path):
    specs = _verify_fixture(tmp_path)
    state_path = specs / "demo" / FS.PIPELINE_STATE_FILENAME
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["stages"]["forge-verify-tech"] = {"status": "passed", "verifiedStageVersion": 9}
    state["stages"]["forge-2-tech"] = {"status": "complete", "version": 9}
    state["someFutureField"] = {"kept": True}
    # Backdated so the refresh is observable even inside a one-second write window.
    state["updatedAt"] = "2020-01-01T00:00:00Z"
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    assert _verify(specs, "--stage", "forge-1-prd", "--status", "passed",
                   "--verified-stage-version", "1").returncode == 0

    after = json.loads(state_path.read_text(encoding="utf-8"))
    assert after["stages"]["forge-verify-tech"] == {
        "status": "passed", "verifiedStageVersion": 9,
    }
    assert after["stages"]["forge-2-tech"] == {"status": "complete", "version": 9}
    assert after["someFutureField"] == {"kept": True}
    assert after["stages"]["forge-1-prd"] == state["stages"]["forge-1-prd"]
    # Only the selected verify entry plus top-level updatedAt moved.
    changed = {k for k in after if after[k] != state.get(k)}
    assert changed == {"updatedAt", "stages"}


def test_state_verify_json_carries_the_entry_and_the_resolved_path(tmp_path):
    """A caller must not have to re-read state to report what landed (00 §6)."""
    specs = _verify_fixture(tmp_path)
    result = _verify(specs, "--stage", "forge-1-prd", "--status", "passed",
                     "--verified-stage-version", "1", "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)

    assert payload["statePath"] == str(specs / "demo" / FS.PIPELINE_STATE_FILENAME)
    assert payload["verifyKey"] == "forge-verify-prd"
    assert payload["feature"] == "demo" and payload["stage"] == "forge-1-prd"
    assert payload["entry"] == _entry(specs)


def test_state_verify_prints_a_one_line_summary_without_json(tmp_path):
    specs = _verify_fixture(tmp_path)
    result = _verify(specs, "--stage", "forge-1-prd", "--status", "passed",
                     "--verified-stage-version", "1")
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "recorded forge-verify-prd = passed for demo (v1)"


def test_state_verify_writes_every_stage_token(tmp_path):
    for stage, key in FS.VERIFY_TOKEN_BY_STAGE.items():
        specs = _verify_fixture(tmp_path / stage, stage=stage)
        assert _verify(specs, "--stage", stage, "--status", "passed",
                       "--verified-stage-version", "1").returncode == 0
        assert _entry(specs, f"forge-verify-{key}")["status"] == "passed"


# --------------------------------------------------------------------------- #
# state-verify — commit-2 provenance mode (03 §3.4 / §6, 07 §4.5)
# --------------------------------------------------------------------------- #


def _reported(specs: Path, *, name: str = "demo") -> None:
    """Record a `findings-reported` result — the richest entry to leave undisturbed."""
    assert _verify(
        specs, "--stage", "forge-1-prd", "--status", "findings-reported",
        "--findings-file", "verify/f.md", "--findings-count", "3",
        "--verified-stage-version", "1", name=name,
    ).returncode == 0


def test_state_verify_commit_2_changes_only_the_hash_and_updated_at(tmp_path):
    """03 §3.4: status, findings metadata, timestamps and versions all survive."""
    specs = _verify_fixture(tmp_path)
    _reported(specs)

    state_path = specs / "demo" / FS.PIPELINE_STATE_FILENAME
    state = json.loads(state_path.read_text(encoding="utf-8"))
    # Backdated so the top-level refresh is observable inside a one-second window,
    # and seeded so an unrelated entry can be proven untouched.
    state["updatedAt"] = "2020-01-01T00:00:00Z"
    state["stages"]["forge-verify-tech"] = {"status": "passed", "verifiedStageVersion": 4}
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    before = json.loads(state_path.read_text(encoding="utf-8"))
    assert before["stages"]["forge-verify-prd"]["commitHash"] is None, "Commit 1 wrote null"

    result = _verify(specs, "--stage", "forge-1-prd", "--commit-hash", _FULL_HASH)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"recorded forge-verify-prd commitHash: {_FULL_HASH}"

    after = json.loads(state_path.read_text(encoding="utf-8"))
    assert validate_state(after) == [], validate_state(after)
    assert after["stages"]["forge-verify-prd"]["commitHash"] == _FULL_HASH
    assert after["updatedAt"] != "2020-01-01T00:00:00Z", "top-level updatedAt must refresh"

    # Everything else — including the untouched sibling entry and every other
    # top-level field — must be identical.
    before["updatedAt"] = after["updatedAt"]
    before["stages"]["forge-verify-prd"]["commitHash"] = _FULL_HASH
    assert after == before, "commit-2 changed more than commitHash and updatedAt"


def test_state_verify_commit_2_accepts_every_40_hex_casing_verbatim(tmp_path):
    for label, value in _ACCEPTED_HASHES:
        specs = _verify_fixture(tmp_path / f"case-{label}")
        _reported(specs)
        assert _verify(specs, "--stage", "forge-1-prd",
                       "--commit-hash", value).returncode == 0, label
        assert _entry(specs)["commitHash"] == value, f"{label}: case was not preserved"


def test_state_verify_commit_2_rejects_a_short_or_malformed_hash_before_mutation(tmp_path):
    for label, value in _REJECTED_HASHES:
        specs = _verify_fixture(tmp_path / f"bad-{label}")
        _reported(specs)
        before = _state_bytes(specs)
        result = _verify(specs, "--stage", "forge-1-prd", "--commit-hash", value)
        assert result.returncode == 2, f"{label}: exit {result.returncode}"
        assert result.stderr.startswith("Error:"), f"{label}: {result.stderr!r}"
        assert "40-character" in result.stderr, f"{label}: {result.stderr!r}"
        assert not result.stdout.strip(), f"{label} produced stdout"
        assert _state_bytes(specs) == before, f"{label} mutated state"


def test_state_verify_commit_2_requires_an_existing_entry(tmp_path):
    """Provenance for an entry that was never written is a fail-closed error.

    Recording it anyway would persist a lone ``{"commitHash": …}`` — which
    ``verifyEntry``'s ``required: ["status"]`` rejects — at exit 0.
    """
    specs = _verify_fixture(tmp_path)
    _reported(specs)   # a DIFFERENT stage's entry must not stand in for this one
    before = _state_bytes(specs)

    result = _verify(specs, "--stage", "forge-2-tech", "--commit-hash", _FULL_HASH)
    assert result.returncode == 2
    assert "forge-verify-tech" in result.stderr
    assert "has none" in result.stderr
    assert _state_bytes(specs) == before


def test_state_verify_commit_2_rejects_result_metadata(tmp_path):
    """Mixed result/hash metadata means the caller conflated the two writes."""
    specs = _verify_fixture(tmp_path)
    _reported(specs)
    before = _state_bytes(specs)
    for extra in (
        ("--findings-file", "verify/f.md"),
        ("--findings-count", "3"),
        ("--verified-stage-version", "1"),
    ):
        result = _verify(specs, "--stage", "forge-1-prd",
                         "--commit-hash", _FULL_HASH, *extra)
        assert result.returncode == 2, extra
        assert "does not accept" in result.stderr, f"{extra}: {result.stderr!r}"
        assert _state_bytes(specs) == before, extra


def test_the_two_commit_protocol_writes_null_then_the_commit_1_hash(tmp_path):
    """REQ-STATE-04, end to end: every result status starts at null and is filled in.

    The hash lands in a SECOND targeted state write, never by amending the first.
    """
    for status, extra in (
        ("auto-verify-pending", ()),
        ("passed", ("--verified-stage-version", "1")),
        (
            "findings-reported",
            ("--findings-file", "verify/f.md", "--findings-count", "2",
             "--verified-stage-version", "1"),
        ),
        ("skipped", ()),
    ):
        specs = _verify_fixture(tmp_path / f"protocol-{status}")
        assert _verify(specs, "--stage", "forge-1-prd",
                       "--status", status, *extra).returncode == 0, status
        assert _entry(specs)["commitHash"] is None, f"{status}: Commit 1 must write null"

        assert _verify(specs, "--stage", "forge-1-prd",
                       "--commit-hash", _FULL_HASH).returncode == 0, status
        entry = _entry(specs)
        assert entry["commitHash"] == _FULL_HASH, status
        assert entry["status"] == status, f"{status}: commit-2 changed the status"


def test_state_verify_commit_2_json_echo_reports_the_written_entry(tmp_path):
    specs = _verify_fixture(tmp_path)
    _reported(specs)
    result = _verify(specs, "--stage", "forge-1-prd",
                     "--commit-hash", _FULL_HASH, "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["verifyKey"] == "forge-verify-prd"
    assert payload["entry"]["commitHash"] == _FULL_HASH
    assert payload["entry"]["status"] == "findings-reported"
    assert payload["statePath"] == str(specs / "demo" / FS.PIPELINE_STATE_FILENAME)


def test_state_verify_rejects_an_unknown_status_at_the_callable(tmp_path):
    """argparse pins the CLI; the callable is reachable from stage-exit too."""
    specs = _verify_fixture(tmp_path)
    try:
        FS.cmd_state_verify("demo", "forge-1-prd", specs, None, status="pending")
    except FS.UsageError as exc:
        assert "unknown --status" in str(exc)
    else:
        raise AssertionError("--status pending was accepted as a result")


# --------------------------------------------------------------------------- #
# state-verify — the epic target (03 §3.2 step 2 / §2.1, 07 §4.3)
# --------------------------------------------------------------------------- #


def _epic_fixture(
    tmp_path: Path,
    revision: int | None = 1,
    epic: str = "auth-overhaul",
    members: tuple[str, ...] = ("login",),
) -> Path:
    """Create an epic root with a manifest and completed members; return the specs dir.

    ``revision=None`` writes a LEGACY manifest with no ``revision`` key, which
    ``load_manifest`` presents as logical 1 (03 §2.2) — the compatibility row.
    Each member gets a real, complete ``.pipeline-state.json`` so an epic write can
    be proven not to touch one.
    """
    specs = tmp_path / "specs"
    epic_dir = specs / epic
    epic_dir.mkdir(parents=True)
    manifest = {
        "schemaVersion": "1",
        "epic": epic,
        "title": "Auth overhaul",
        "features": [{"name": m, "dependsOn": []} for m in members],
    }
    if revision is not None:
        manifest["revision"] = revision
    (epic_dir / FS.MANIFEST_FILENAME).write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    for member in members:
        (epic_dir / member).mkdir()
        result = _run(
            "state-complete", "--feature", member, "--epic", epic,
            "--stage", "forge-1-prd", "--version", "1", "--artifact", "PRD.md",
            "--specs-dir", str(specs),
        )
        assert result.returncode == 0, result.stderr
    return specs


def _epic_verify(
    specs: Path, *extra: str, epic: str = "auth-overhaul"
) -> subprocess.CompletedProcess[str]:
    """Run ``state-verify --stage forge-0-epic`` against ``specs``."""
    return _run(
        "state-verify", "--feature", epic, "--stage", "forge-0-epic",
        *extra, "--specs-dir", str(specs),
    )


def _epic_state(specs: Path, epic: str = "auth-overhaul") -> dict:
    """Read the epic's `.epic-state.json` back off disk."""
    return json.loads(
        (specs / epic / FS.EPIC_STATE_FILENAME).read_text(encoding="utf-8")
    )


def _member_bytes(specs: Path, epic: str = "auth-overhaul") -> dict[str, bytes]:
    """Snapshot every member state file under ``epic``, for byte-equality checks."""
    return {
        str(p.relative_to(specs)): p.read_bytes()
        for p in sorted((specs / epic).glob(f"*/{FS.PIPELINE_STATE_FILENAME}"))
    }


def test_epic_verify_writes_only_the_epic_state_file(tmp_path):
    """REQ-SEC-01: an epic write never creates or changes a member state file."""
    specs = _epic_fixture(tmp_path, revision=3, members=("login", "signup"))
    members_before = _member_bytes(specs)
    assert members_before, "fixture should carry member state to compare against"

    assert _epic_verify(specs, "--status", "auto-verify-pending").returncode == 0

    assert (specs / "auth-overhaul" / FS.EPIC_STATE_FILENAME).is_file()
    assert _member_bytes(specs) == members_before, "a member state file moved"
    assert not (specs / "auth-overhaul" / FS.PIPELINE_STATE_FILENAME).exists()


def test_a_new_epic_state_matches_the_minimal_documented_shape(tmp_path):
    """03 §2.1's minimal shape, exactly — no member rollup, no cached manifest data."""
    specs = _epic_fixture(tmp_path, revision=3)
    assert _epic_verify(specs, "--status", "auto-verify-pending").returncode == 0

    state = _epic_state(specs)
    assert set(state) == {"epic", "updatedAt", "stages"}
    assert state["epic"] == "auth-overhaul"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", state["updatedAt"])
    assert set(state["stages"]) == {"forge-verify-epic"}
    assert state["stages"]["forge-verify-epic"] == {
        "status": "auto-verify-pending",
        "scheduledAt": state["updatedAt"],
        "scheduledStageVersion": 3,
        "commitHash": None,
    }


def test_epic_versions_carry_the_manifest_revision_not_a_member_version(tmp_path):
    """03 §2.2: `current` for an epic is the manifest revision, full stop."""
    specs = _epic_fixture(tmp_path, revision=7)
    member_version = json.loads(
        (specs / "auth-overhaul" / "login" / FS.PIPELINE_STATE_FILENAME)
        .read_text(encoding="utf-8")
    )["stages"]["forge-1-prd"]["version"]
    assert member_version == 1, "the member sits at a DIFFERENT version by design"

    assert _epic_verify(specs, "--status", "auto-verify-pending").returncode == 0
    assert _epic_state(specs)["stages"]["forge-verify-epic"]["scheduledStageVersion"] == 7

    assert _epic_verify(specs, "--status", "passed",
                        "--verified-stage-version", "7").returncode == 0
    assert _epic_state(specs)["stages"]["forge-verify-epic"]["verifiedStageVersion"] == 7

    stale = _epic_verify(specs, "--status", "passed",
                         "--verified-stage-version", str(member_version))
    assert stale.returncode == 2
    assert "revision 7" in stale.stderr


def test_a_legacy_manifest_without_a_revision_verifies_at_revision_1(tmp_path):
    """REQ-DEBT-06/REQ-COMPAT-02: the synthesized 1 is a read, not a rewrite."""
    specs = _epic_fixture(tmp_path, revision=None)
    manifest_path = specs / "auth-overhaul" / FS.MANIFEST_FILENAME
    before = manifest_path.read_bytes()

    assert _epic_verify(specs, "--status", "passed",
                        "--verified-stage-version", "1").returncode == 0
    assert _epic_state(specs)["stages"]["forge-verify-epic"]["verifiedStageVersion"] == 1
    assert manifest_path.read_bytes() == before, "state-verify rewrote the manifest"


def test_every_result_status_works_against_the_epic_target(tmp_path):
    """pass / findings-reported / findings-applied / skipped, same as a feature."""
    specs = _epic_fixture(tmp_path, revision=2)
    key = "forge-verify-epic"

    assert _epic_verify(specs, "--status", "passed",
                        "--verified-stage-version", "2").returncode == 0
    assert _epic_state(specs)["stages"][key]["status"] == "passed"

    assert _epic_verify(
        specs, "--status", "findings-reported", "--verified-stage-version", "2",
        "--findings-file", "verify/epic-findings.md", "--findings-count", "3",
    ).returncode == 0
    reported = _epic_state(specs)["stages"][key]
    assert reported["findingsFile"] == "verify/epic-findings.md"
    assert reported["findingsCount"] == 3

    assert _epic_verify(specs, "--status", "findings-applied").returncode == 0
    applied = _epic_state(specs)["stages"][key]
    assert applied["status"] == "findings-applied"
    assert applied["findingsFile"] == "verify/epic-findings.md"
    assert "fixedAt" in applied
    assert "verifiedStageVersion" not in applied, "applied deliberately clears freshness"

    assert _epic_verify(specs, "--status", "skipped").returncode == 0
    skipped = _epic_state(specs)["stages"][key]
    assert skipped == {"status": "skipped", "commitHash": None}


def test_an_epic_write_touches_only_its_own_entry_and_updated_at(tmp_path):
    """Unrelated epic-state keys and entries survive (03 §3.2)."""
    specs = _epic_fixture(tmp_path, revision=2)
    state_path = specs / "auth-overhaul" / FS.EPIC_STATE_FILENAME
    state_path.write_text(
        json.dumps(
            {
                "epic": "auth-overhaul",
                "updatedAt": "2020-01-01T00:00:00Z",
                "unknownTopLevel": {"kept": True},
                "stages": {
                    "forge-0-epic": {"status": "complete"},
                    "forge-verify-epic": {"status": "pending"},
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    assert _epic_verify(specs, "--status", "skipped").returncode == 0
    state = _epic_state(specs)
    assert state["unknownTopLevel"] == {"kept": True}
    assert state["stages"]["forge-0-epic"] == {"status": "complete"}
    assert state["stages"]["forge-verify-epic"]["status"] == "skipped"
    assert state["updatedAt"] != "2020-01-01T00:00:00Z"


def test_the_epic_result_echo_names_the_epic_state_path(tmp_path):
    """The --json echo reports what landed, so no caller re-reads the file."""
    specs = _epic_fixture(tmp_path, revision=4)
    result = _epic_verify(specs, "--status", "auto-verify-pending", "--json")
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["verifyKey"] == "forge-verify-epic"
    assert payload["statePath"] == str(specs / "auth-overhaul" / FS.EPIC_STATE_FILENAME)
    assert payload["entry"]["scheduledStageVersion"] == 4


def test_an_epic_findings_file_is_contained_by_the_epic_dir(tmp_path):
    """The containment target is the epic root, never a member directory."""
    specs = _epic_fixture(tmp_path, revision=1)
    for bad in ("/etc/passwd", "../login/f.md", "verify/../../escape.md"):
        result = _epic_verify(
            specs, "--status", "findings-reported", "--verified-stage-version", "1",
            "--findings-file", bad, "--findings-count", "1",
        )
        assert result.returncode == 2, f"{bad!r} was accepted"
        assert "--findings-file" in result.stderr, f"{bad!r}: {result.stderr!r}"
        assert not (specs / "auth-overhaul" / FS.EPIC_STATE_FILENAME).exists()


def test_epic_metadata_validation_matches_the_feature_target(tmp_path):
    """Same forbidden-metadata matrix as a feature write (03 §3.3)."""
    specs = _epic_fixture(tmp_path, revision=1)
    rejected = (
        ("--status", "auto-verify-pending", "--verified-stage-version", "1"),
        ("--status", "skipped", "--findings-count", "1"),
        ("--status", "passed", "--verified-stage-version", "1",
         "--findings-file", "verify/f.md"),
        ("--status", "passed", "--verified-stage-version", "1",
         "--findings-count", "2"),
        ("--status", "passed",),
        ("--status", "findings-reported", "--verified-stage-version", "1",
         "--findings-count", "1"),
        ("--status", "findings-applied", "--verified-stage-version", "1"),
        ("--status", "findings-applied",),
        (),
    )
    for extra in rejected:
        result = _epic_verify(specs, *extra)
        assert result.returncode == 2, extra
        assert result.stderr.startswith("Error:"), extra
        assert not (specs / "auth-overhaul" / FS.EPIC_STATE_FILENAME).exists(), extra


def test_a_conflicting_feature_epic_pair_fails_before_mutation(tmp_path):
    specs = _epic_fixture(tmp_path, revision=1)
    members_before = _member_bytes(specs)

    result = _epic_verify(specs, "--epic", "other-epic", "--status", "skipped")
    assert result.returncode == 2
    assert "disagree" in result.stderr
    assert not (specs / "auth-overhaul" / FS.EPIC_STATE_FILENAME).exists()
    assert _member_bytes(specs) == members_before

    # The matching pair is legal — `--epic` may repeat the epic's own name.
    assert _epic_verify(specs, "--epic", "auth-overhaul",
                        "--status", "skipped").returncode == 0


def test_an_unsafe_epic_name_or_path_escape_fails_before_mutation(tmp_path):
    specs = _epic_fixture(tmp_path, revision=1)
    for bad in ("../escape", "..", "/absolute", "Bad_Name", "nested/name", ""):
        result = _run(
            "state-verify", "--feature", bad, "--stage", "forge-0-epic",
            "--status", "skipped", "--specs-dir", str(specs),
        )
        assert result.returncode == 2, f"{bad!r} was accepted"
        assert "unsafe name" in result.stderr, f"{bad!r}: {result.stderr!r}"


def test_an_epic_name_reached_through_a_symlink_out_of_specs_is_refused(tmp_path):
    specs = _epic_fixture(tmp_path, revision=1)
    outside = tmp_path / "outside"
    (outside / "epic-manifest.json").parent.mkdir()
    (outside / FS.MANIFEST_FILENAME).write_text(
        json.dumps({"schemaVersion": "1", "epic": "elsewhere", "features": []}),
        encoding="utf-8",
    )
    (specs / "elsewhere").symlink_to(outside, target_is_directory=True)

    result = _run(
        "state-verify", "--feature", "elsewhere", "--stage", "forge-0-epic",
        "--status", "skipped", "--specs-dir", str(specs),
    )
    assert result.returncode == 2, result.stdout
    assert "escapes the specs dir" in result.stderr
    assert not (outside / FS.EPIC_STATE_FILENAME).exists()


def test_a_missing_or_mismatched_manifest_fails_before_mutation(tmp_path):
    specs = _epic_fixture(tmp_path, revision=1)
    manifest_path = specs / "auth-overhaul" / FS.MANIFEST_FILENAME
    original = manifest_path.read_bytes()

    # A plain feature directory is not an epic — and must not fall back to it.
    plain = _verify_fixture(tmp_path / "flat")
    missing = _run(
        "state-verify", "--feature", "demo", "--stage", "forge-0-epic",
        "--status", "skipped", "--specs-dir", str(plain),
    )
    assert missing.returncode == 2
    assert "no epic manifest" in missing.stderr
    assert not (plain / "demo" / FS.EPIC_STATE_FILENAME).exists()
    assert _state_bytes(plain), "the member state file must be left in place"

    for mutation, needle in (
        ('{"schemaVersion": "1", "epic": "other-epic", "features": []}', "declares epic"),
        ("not json at all", "not valid JSON"),
        ("[]", "not a JSON object"),
        ('{"epic": "auth-overhaul", "revision": 0}', "positive integer"),
        ('{"epic": "auth-overhaul", "revision": true}', "positive integer"),
    ):
        manifest_path.write_text(mutation, encoding="utf-8")
        result = _epic_verify(specs, "--status", "skipped")
        assert result.returncode == 2, mutation
        assert needle in result.stderr, f"{mutation}: {result.stderr!r}"
        assert not (specs / "auth-overhaul" / FS.EPIC_STATE_FILENAME).exists()
    manifest_path.write_bytes(original)


def test_a_corrupt_or_malformed_epic_state_is_refused_byte_intact(tmp_path):
    specs = _epic_fixture(tmp_path, revision=1)
    state_path = specs / "auth-overhaul" / FS.EPIC_STATE_FILENAME
    for content, needle in (
        ("{ not json", "not valid JSON"),
        ("[]", "not a JSON object"),
        ('{"epic": "auth-overhaul", "stages": []}', "non-object 'stages'"),
        ('{"epic": "auth-overhaul", "stages": "nope"}', "non-object 'stages'"),
        ('{"epic": "some-other-epic"}', "records epic"),
    ):
        state_path.write_text(content, encoding="utf-8")
        before = state_path.read_bytes()
        result = _epic_verify(specs, "--status", "skipped")
        assert result.returncode == 2, content
        assert needle in result.stderr, f"{content}: {result.stderr!r}"
        assert state_path.read_bytes() == before, f"{content}: mutated on a refusal"


def test_a_legacy_epic_state_without_epic_or_stages_is_enriched(tmp_path):
    """REQ-DEBT-06: a sparse legacy file loads and is filled in on its next write."""
    specs = _epic_fixture(tmp_path, revision=1)
    state_path = specs / "auth-overhaul" / FS.EPIC_STATE_FILENAME
    state_path.write_text("{}", encoding="utf-8")

    assert _epic_verify(specs, "--status", "skipped").returncode == 0
    state = _epic_state(specs)
    assert state["epic"] == "auth-overhaul"
    assert state["stages"]["forge-verify-epic"]["status"] == "skipped"
    assert state["updatedAt"]


def test_neither_target_falls_back_to_the_other(tmp_path):
    """No fallback in either direction, proven on disk (03 §3.2 step 3).

    The fixture is the adversarial one: a directory that is BOTH an epic root and
    carries a ``.pipeline-state.json``. If either branch reached the other's
    resolver, one of these writes would land in the wrong file — so the two target
    files are asserted independently, byte-for-byte, across both writes.
    """
    specs = _epic_fixture(tmp_path, revision=5)
    epic_dir = specs / "auth-overhaul"
    assert _run(
        "state-complete", "--feature", "auth-overhaul", "--stage", "forge-1-prd",
        "--version", "9", "--artifact", "PRD.md", "--specs-dir", str(specs),
    ).returncode == 0
    member_state = epic_dir / FS.PIPELINE_STATE_FILENAME
    epic_state = epic_dir / FS.EPIC_STATE_FILENAME
    member_before = member_state.read_bytes()

    # Epic target: writes .epic-state.json at the MANIFEST revision, and the
    # same-named feature state beside it does not move.
    assert _epic_verify(specs, "--status", "passed",
                        "--verified-stage-version", "5").returncode == 0
    assert member_state.read_bytes() == member_before
    assert _epic_state(specs)["stages"]["forge-verify-epic"]["verifiedStageVersion"] == 5

    # Feature target on the very same name: writes .pipeline-state.json at the
    # STAGE version, and the epic state does not move.
    epic_before = epic_state.read_bytes()
    assert _verify(specs, "--stage", "forge-1-prd", "--status", "passed",
                   "--verified-stage-version", "9", name="auth-overhaul").returncode == 0
    assert epic_state.read_bytes() == epic_before
    written = json.loads(member_state.read_text(encoding="utf-8"))
    assert written["stages"]["forge-verify-prd"]["verifiedStageVersion"] == 9
    assert "forge-verify-epic" not in written["stages"]


def test_epic_commit_2_changes_only_the_hash_and_updated_at(tmp_path):
    """Commit-2 mode is valid for an epic entry and stays epic-scoped (03 §3.4)."""
    specs = _epic_fixture(tmp_path, revision=3, members=("login", "signup"))
    assert _epic_verify(specs, "--status", "findings-reported",
                        "--findings-file", "verify/epic-findings.md",
                        "--findings-count", "2",
                        "--verified-stage-version", "3").returncode == 0
    members_before = _member_bytes(specs)
    state_path = specs / "auth-overhaul" / FS.EPIC_STATE_FILENAME
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["updatedAt"] = "2020-01-01T00:00:00Z"
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    before = json.loads(state_path.read_text(encoding="utf-8"))
    assert before["stages"]["forge-verify-epic"]["commitHash"] is None

    result = _epic_verify(specs, "--commit-hash", _FULL_HASH)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"recorded forge-verify-epic commitHash: {_FULL_HASH}"

    after = _epic_state(specs)
    assert after["updatedAt"] != "2020-01-01T00:00:00Z"
    before["updatedAt"] = after["updatedAt"]
    before["stages"]["forge-verify-epic"]["commitHash"] = _FULL_HASH
    assert after == before, "epic commit-2 changed more than commitHash and updatedAt"
    assert _member_bytes(specs) == members_before, "an epic write touched a member"


def test_epic_commit_2_requires_an_existing_entry_and_creates_no_state_file(tmp_path):
    specs = _epic_fixture(tmp_path, revision=1)
    state_path = specs / "auth-overhaul" / FS.EPIC_STATE_FILENAME
    assert not state_path.exists()
    members_before = _member_bytes(specs)

    result = _epic_verify(specs, "--commit-hash", _FULL_HASH)
    assert result.returncode == 2
    assert "forge-verify-epic" in result.stderr and "has none" in result.stderr
    assert not state_path.exists(), "a rejected commit-2 lazily created the epic state"
    assert _member_bytes(specs) == members_before


def test_epic_commit_2_rejects_a_short_or_malformed_hash_before_mutation(tmp_path):
    for label, value in _REJECTED_HASHES:
        specs = _epic_fixture(tmp_path / f"epic-bad-{label}", revision=1)
        assert _epic_verify(specs, "--status", "skipped").returncode == 0
        state_path = specs / "auth-overhaul" / FS.EPIC_STATE_FILENAME
        before = state_path.read_bytes()
        result = _epic_verify(specs, "--commit-hash", value)
        assert result.returncode == 2, f"{label}: exit {result.returncode}"
        assert "40-character" in result.stderr, f"{label}: {result.stderr!r}"
        assert state_path.read_bytes() == before, f"{label} mutated the epic state"


# --------------------------------------------------------------------------- #
# Enum parity with the schema (REQ-R4-03 — the schema stays source of truth)
# --------------------------------------------------------------------------- #


def _schema_enum(*path: str) -> list[str]:
    """Pull an ``enum`` list out of references/pipeline-state-schema.json by key path."""
    node = json.loads(read(REFERENCES / "pipeline-state-schema.json"))
    for key in path:
        node = node[key]
    return node["enum"]


def test_the_verb_enum_choices_match_the_schema_exactly():
    """No stage reads the schema any more, so the choices must be pinned to it."""
    decisions = ("properties", "deferredDecisions", "items", "properties")
    ecrs = ("properties", "epicChangeRequests", "items", "properties")
    assert list(FS.DECISION_RAISED_BY) == _schema_enum(*decisions, "raisedBy")
    assert list(FS.DECISION_TARGET_STAGES) == _schema_enum(*decisions, "targetStage")
    assert list(FS.ECR_KINDS) == _schema_enum(*ecrs, "kind")
    assert list(FS.ECR_RAISED_BY) == _schema_enum(*ecrs, "raisedBy")


def test_the_registered_choices_are_the_constants_not_a_retyped_literal():
    """A drifting inline tuple would pass the parity test above while the CLI drifts."""
    source = read(FORGE_SESSION)
    for flag, constant in (
        ("--raised-by", "DECISION_RAISED_BY"),
        ("--target-stage", "DECISION_TARGET_STAGES"),
        ("--kind", "ECR_KINDS"),
        ("--raised-by", "ECR_RAISED_BY"),
    ):
        assert f"choices={constant}" in source, f"{flag} does not use {constant}"


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
    "state-decision": ("--question", "Which cache backend?", "--raised-by", "forge-1-prd"),
    "state-ecr": (
        "--kind", "add-feature", "--target", "sibling-feature",
        "--rationale", "R7 emerged as a distinct feature",
        "--raised-by", "forge-2-tech", "--blocks-current", "false",
    ),
    # `skipped` is the one result that needs no completed artifact behind it, so it
    # is the only invocation that works against a never-written state file.
    "state-verify": ("--stage", "forge-1-prd", "--status", "skipped"),
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


# --------------------------------------------------------------------------- #
# Legacy short hashes stay readable (REQ-STATE-02, 03 §6.2)
# --------------------------------------------------------------------------- #


EPIC_MANIFEST = SCRIPTS / "epic-manifest.py"


def _run_manifest(*argv: str) -> subprocess.CompletedProcess[str]:
    """Invoke `epic-manifest.py` out-of-process, the way validate.sh does."""
    return subprocess.run(
        [sys.executable, str(EPIC_MANIFEST), *argv], capture_output=True, text=True
    )


#: A 7-character abbreviation of the kind pre-feature state files carry. Rejected
#: on a NEW write; never rejected, migrated, truncated, or Git-resolved on a READ.
_LEGACY_HASH = "a1b2c3d"


def _legacy_member(tmp_path: Path) -> Path:
    """An epic member whose stage AND verify entries both carry a short hash.

    The manifest is upgraded to the full renderable shape (`_epic_fixture` writes
    the minimum `state-verify` needs, which `render-status` rejects for missing
    `charter`/`exposes`/`consumes`).
    """
    specs = _epic_fixture(tmp_path, revision=1, members=("login",))
    (specs / "auth-overhaul" / FS.MANIFEST_FILENAME).write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "revision": 1,
                "epic": "auth-overhaul",
                "description": "Legacy-hash compatibility fixture.",
                "status": "active",
                "narrativeDoc": "EPIC.md",
                "createdAt": "2026-01-01T00:00:00Z",
                "updatedAt": "2026-01-01T00:00:00Z",
                "features": [
                    {
                        "name": "login",
                        "charter": "Sign-in surface for the legacy-hash fixture.",
                        "dependsOn": [],
                        "exposes": [],
                        "consumes": [],
                    }
                ],
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    state_path = specs / "auth-overhaul" / "login" / FS.PIPELINE_STATE_FILENAME
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["stages"]["forge-1-prd"]["commitHash"] = _LEGACY_HASH
    state["stages"]["forge-verify-prd"] = {
        "status": "passed",
        "verifiedAt": "2026-01-02T00:00:00Z",
        "verifiedStageVersion": 1,
        "commitHash": "9f8e7d6",
    }
    assert validate_state(state) == [], validate_state(state)
    state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return specs


def test_a_legacy_short_hash_survives_every_read_side_path(tmp_path):
    """03 §6.2: the reader must not reject, migrate, truncate, or Git-resolve it.

    The new write-boundary validation is exactly that — a WRITE boundary. Every
    consumer that merely loads the document has to keep working, so the four named
    in the spec (`_read_state`, `_load_state_for_write`, the manifest status
    readers, the navigator) and stage exit are each exercised against the same
    file, and the bytes are re-checked at the end.
    """
    specs = _legacy_member(tmp_path)
    state_path = specs / "auth-overhaul" / "login" / FS.PIPELINE_STATE_FILENAME

    # _read_state + the navigator's ranked ledger.
    ranked = _run("rank-features", "--specs-dir", str(specs), "--json")
    assert ranked.returncode == 0, ranked.stderr
    rows = json.loads(ranked.stdout)
    assert [row["name"] for row in rows["active"]] == ["login"], rows
    # The freshness classifier read the entry rather than choking on its hash.
    assert rows["active"][0]["verifyState"] == "fresh", rows

    # Stage exit, which reads the same document to route.
    exited = _run(
        "stage-exit", "--feature", "login", "--epic", "auth-overhaul",
        "--stage", "forge-1-prd", "--specs-dir", str(specs), "--json",
    )
    assert exited.returncode == 0, exited.stderr

    # The manifest status readers.
    status = _run_manifest(
        "render-status", "auth-overhaul", "--specs-dir", str(specs), "--json"
    )
    assert status.returncode == 0, status.stderr
    assert json.loads(status.stdout)["epic"] == "auth-overhaul"

    # Nothing above may have rewritten the file.
    reread = json.loads(state_path.read_text(encoding="utf-8"))
    assert reread["stages"]["forge-1-prd"]["commitHash"] == _LEGACY_HASH
    assert reread["stages"]["forge-verify-prd"]["commitHash"] == "9f8e7d6"


def test_load_state_for_write_carries_a_legacy_short_hash_forward(tmp_path):
    """An unrelated WRITE must not migrate or drop a short hash it did not author."""
    specs = _legacy_member(tmp_path)
    assert _run(
        "state-note", "--feature", "login", "--epic", "auth-overhaul",
        "--note", "unrelated", "--specs-dir", str(specs),
    ).returncode == 0
    state = json.loads(
        (specs / "auth-overhaul" / "login" / FS.PIPELINE_STATE_FILENAME)
        .read_text(encoding="utf-8")
    )
    assert state["stages"]["forge-1-prd"]["commitHash"] == _LEGACY_HASH
    assert state["stages"]["forge-verify-prd"]["commitHash"] == "9f8e7d6"

    # And commit-2 against that same entry replaces it with a full hash — the only
    # sanctioned way a legacy value ever moves.
    assert _verify(specs, "--stage", "forge-1-prd", "--commit-hash", _FULL_HASH,
                   "--epic", "auth-overhaul", name="login").returncode == 0
    entry = json.loads(
        (specs / "auth-overhaul" / "login" / FS.PIPELINE_STATE_FILENAME)
        .read_text(encoding="utf-8")
    )["stages"]["forge-verify-prd"]
    assert entry["commitHash"] == _FULL_HASH
    assert entry["status"] == "passed" and entry["verifiedStageVersion"] == 1


# --------------------------------------------------------------------------- #
# Single-writer model preserved (REQ-REL-04, 07 §4.3)
# --------------------------------------------------------------------------- #
#
# REQ-REL-04 is a NEGATIVE requirement, so nothing but a guard enforces it:
# atomicity here protects against an INTERRUPTED write, not against concurrent
# writers, and multi-session concurrency is explicitly out of scope (issue #180).
# A future change that adds mutual exclusion has to amend REQ-REL-04 first — these
# tests are what force that conversation instead of letting the model widen
# silently under a plausible-sounding "make it safe" edit.

#: Tokens that would betray a lock, lease, optimistic-version check, retry, or
#: backoff inside the writers. `O_EXCL`/`O_CREAT` are here because a hand-rolled
#: exclusive-create lockfile is the cheapest way to smuggle one in.
_MUTEX_TOKENS = (
    "fcntl", "flock", "lockf", "LOCK_EX", "LOCK_NB", "msvcrt", "filelock",
    "portalocker", "threading.", "multiprocessing", "O_EXCL", "O_CREAT",
    ".lock", "lockfile", "lease", "backoff", "sleep", "retry", "retries",
    "compare_and_swap", "stateVersion", "expectedVersion", "if_match",
)


def _function_source(source: str, name: str) -> str:
    """Return one top-level ``def name(...)`` block, verbatim."""
    lines = source.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith(f"def {name}(")), None
    )
    assert start is not None, f"def {name}( not found in {FORGE_SESSION}"
    end = start + 1
    while end < len(lines) and (
        not lines[end].strip() or lines[end].startswith((" ", "\t", ")"))
    ):
        end += 1
    return "\n".join(lines[start:end])


#: Every function on the state write path, from the verb entrypoints down.
_WRITER_FUNCTIONS = (
    "_write_state",
    "_commit_state",
    "_load_state_for_write",
    "_load_epic_state_for_write",
    "_load_verify_target",
    "cmd_state_verify",
    "cmd_state_complete",
)


def test_the_state_writers_acquire_no_lock_lease_or_version_guard():
    source = read(FORGE_SESSION)
    for name in _WRITER_FUNCTIONS:
        body = _function_source(source, name)
        for token in _MUTEX_TOKENS:
            assert token not in body, (
                f"{name} contains {token!r}: REQ-REL-04 forbids adding a lock, "
                f"lease, optimistic-version check, retry, or backoff to the state "
                f"writers. Amend REQ-REL-04 before widening this."
            )


def test_the_single_writer_guard_can_actually_fail():
    """Negative control: a `_function_source` returning "" would pass vacuously.

    Proves the slice really carries the writer's body, stops at the next top-level
    definition, and that the token list catches a lock smuggled into it.
    """
    body = _function_source(read(FORGE_SESSION), "_write_state")
    for expected in ("def _write_state(", "tempfile.mkstemp", "os.fsync", "os.replace"):
        assert expected in body, f"{expected} missing from the sliced body"
    assert "def _resolve_feature_dir_for_write(" not in body, "the slice overran"

    widened = body.replace(
        "        os.replace(tmp_path, state_path)",
        "        fcntl.flock(fd, fcntl.LOCK_EX)\n        os.replace(tmp_path, state_path)",
    )
    assert widened != body, "the control failed to inject a lock"
    assert any(token in widened for token in _MUTEX_TOKENS), (
        "the token list would not catch a flock() added to _write_state"
    )


def _writer_spies(monkeypatch, *, replace_fails: bool = False) -> dict:
    """Install the only three spies 07 §4.3 permits; return the recorded calls.

    Deliberately NOT a general mocking layer: patching anything else would let the
    test assert against a writer that no longer exists.
    """
    record: dict = {"order": [], "temps": []}
    real_mkstemp, real_fsync, real_replace = (
        FS.tempfile.mkstemp, FS.os.fsync, FS.os.replace
    )

    def mkstemp(*args, **kwargs):
        record["order"].append("mkstemp")
        fd, name = real_mkstemp(*args, **kwargs)
        record["temps"].append(Path(name))
        return fd, name

    def fsync(*args, **kwargs):
        record["order"].append("fsync")
        return real_fsync(*args, **kwargs)

    def replace(*args, **kwargs):
        record["order"].append("replace")
        if replace_fails:
            raise OSError("Read-only file system")
        return real_replace(*args, **kwargs)

    monkeypatch.setattr(FS.tempfile, "mkstemp", mkstemp)
    monkeypatch.setattr(FS.os, "fsync", fsync)
    monkeypatch.setattr(FS.os, "replace", replace)
    return record


def test_a_verify_write_is_exactly_temp_file_fsync_replace(tmp_path, monkeypatch):
    """One sibling temp, one fsync, one replace — and no fourth sibling, ever."""
    specs = _verify_fixture(tmp_path)
    feature_dir = specs / "demo"
    before = sorted(p.name for p in feature_dir.iterdir())
    record = _writer_spies(monkeypatch)

    FS.cmd_state_verify("demo", "forge-1-prd", specs, None, status="passed",
                        verified_stage_version=1)

    assert record["order"] == ["mkstemp", "fsync", "replace"], record["order"]
    assert len(record["temps"]) == 1, "a second sibling file was created"
    assert record["temps"][0].parent == feature_dir, "the temp file was not a sibling"
    assert not record["temps"][0].exists(), "os.replace should have consumed the temp"
    assert sorted(p.name for p in feature_dir.iterdir()) == before, (
        "the write created or removed a sibling beyond its own temp file"
    )


def test_an_epic_verify_write_uses_the_same_unguarded_sequence(tmp_path, monkeypatch):
    """The epic branch reuses `_commit_state`, so it inherits the same model."""
    specs = _epic_fixture(tmp_path, revision=2)
    epic_dir = specs / "auth-overhaul"
    before = sorted(p.name for p in epic_dir.iterdir())
    record = _writer_spies(monkeypatch)

    FS.cmd_state_verify("auth-overhaul", "forge-0-epic", specs, None,
                        status="passed", verified_stage_version=2)

    assert record["order"] == ["mkstemp", "fsync", "replace"], record["order"]
    assert len(record["temps"]) == 1
    assert sorted(p.name for p in epic_dir.iterdir()) == sorted(
        [*before, FS.EPIC_STATE_FILENAME]
    ), "the epic write touched something other than .epic-state.json"


def test_a_failed_replacement_leaves_the_original_byte_identical(tmp_path, monkeypatch):
    """No retry, no backoff, no debris — the failure is surfaced, not worked around."""
    specs = _verify_fixture(tmp_path)
    feature_dir = specs / "demo"
    state_path = feature_dir / FS.PIPELINE_STATE_FILENAME
    original = state_path.read_bytes()
    before = sorted(p.name for p in feature_dir.iterdir())
    record = _writer_spies(monkeypatch, replace_fails=True)

    try:
        FS.cmd_state_verify("demo", "forge-1-prd", specs, None, status="passed",
                            verified_stage_version=1)
    except FS.UsageError as exc:
        assert "atomic write to" in str(exc)
    else:  # pragma: no cover - the assertion below reports the miss
        raise AssertionError("a failed os.replace did not raise UsageError")

    assert record["order"].count("replace") == 1, "the writer retried a failed replace"
    assert record["order"] == ["mkstemp", "fsync", "replace"], record["order"]
    assert state_path.read_bytes() == original, "a failed write touched the target"
    assert not record["temps"][0].exists(), "the temp file was left behind"
    assert sorted(p.name for p in feature_dir.iterdir()) == before, "temp debris remains"


# --------------------------------------------------------------------------- #
# No `git commit --amend` provenance route (REQ-STATE-04, 03 §6.3)
# --------------------------------------------------------------------------- #


def _canon_text_files() -> list[Path]:
    """Every canon source/prose file a provenance route could hide in."""
    roots = (SCRIPTS, SKILLS, REFERENCES, REPO_ROOT / "agents")
    suffixes = {".py", ".md", ".json", ".sh"}
    return sorted(
        path
        for root in roots
        if root.is_dir()
        for path in root.rglob("*")
        if path.is_file() and path.suffix in suffixes
    )


def test_no_script_reaches_for_amend_at_all():
    """`--amend` is not a route any executable may take (REQ-STATE-04)."""
    for path in sorted(SCRIPTS.rglob("*.py")) + sorted(SCRIPTS.rglob("*.sh")):
        assert "--amend" not in read(path), f"{path} references --amend"


def test_every_canon_mention_of_amend_forbids_it():
    """Prose may name `--amend` only to prohibit it — never as an instruction.

    The two-commit protocol exists precisely because amending rewrites HEAD, so a
    hash captured before the amend points at a commit that is not in the final
    history. A line that mentioned `--amend` without forbidding it would be a
    provenance route, however it was phrased.
    """
    files = _canon_text_files()
    assert files, "no canon files were scanned"
    seen = 0
    for path in files:
        for number, line in enumerate(read(path).splitlines(), start=1):
            if "--amend" not in line:
                continue
            seen += 1
            lowered = line.lower()
            assert "never" in lowered or "without" in lowered, (
                f"{path.relative_to(REPO_ROOT)}:{number} mentions --amend without "
                f"forbidding it:\n{line.strip()}"
            )
    assert seen, "the prohibition itself disappeared from canon"
