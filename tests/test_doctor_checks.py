"""Tests for doctor's structured ``checks[]`` (issue #244, P0).

The legacy doctor payload is pinned by ``tests/test_doctor.py``; this file covers
the additive check layer: record shape and key order, the crash-isolating
driver, warn-only demotion (INV-1), remedy clustering, the ``--schema`` flag,
and the shared helpers (template rendering, semver parsing, the stdlib schema
validator's parity with ``tests/_state_schema.py``).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from _doctor_fixtures import (
    bin_dir,
    check,
    doctor_report,
    fake_runner,
    make_project,
    pipeline_state,
    probe_log,
    run_doctor,
    scrubbed_env,
    warn_ids,
    write_feature,
)
from _state_schema import _check as reference_schema_check

REPO_ROOT = Path(__file__).resolve().parent.parent
HELPER = REPO_ROOT / "scripts" / "forge-session.py"
CONFIG_SCHEMA = REPO_ROOT / "references" / "forge-config-schema.json"

LEGACY_DOCTOR_KEYS = (
    "pluginRoot", "currentBranch", "specsDir", "specsDirExists", "configPath",
    "configExists", "counts", "features", "invalidAutoVerifyKeys",
    "duplicateConfigKeys", "rootSandbox",
)
CHECK_KEYS = ("id", "status", "severity", "detail", "evidence", "remedy")
PRODUCTION = [
    "forge-1-prd", "forge-2-tech", "forge-3-specs", "forge-4-backlog", "forge-5-loop",
    "forge-6-docs",
]


def _load_helper_module():
    """Import forge-session.py as a module (hyphenated filename → importlib)."""
    spec = importlib.util.spec_from_file_location("forge_session_checks", HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def fs():
    return _load_helper_module()


def _doctor(cwd: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HELPER), "doctor", "--json", *extra],
        capture_output=True, text=True, cwd=str(cwd),
    )


# --------------------------------------------------------------------------- #
# Payload shape
# --------------------------------------------------------------------------- #


def test_report_keeps_legacy_keys_first_then_appends_checks(tmp_path: Path) -> None:
    """The eleven legacy keys are untouched and ordered first; new keys follow."""
    result = _doctor(tmp_path)
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    keys = tuple(report)
    assert keys[: len(LEGACY_DOCTOR_KEYS)] == LEGACY_DOCTOR_KEYS
    assert keys[len(LEGACY_DOCTOR_KEYS):] == ("checks", "checksSummary", "remedyClusters")
    assert tuple(report["checksSummary"]) == ("ok", "warn", "fail", "na")
    assert report["checksSummary"]["fail"] == 0
    for record in report["checks"]:
        assert tuple(record) == CHECK_KEYS


def test_registry_ids_are_unique_kebab_case_with_enumerated_severity(fs) -> None:
    ids = [spec.id for spec in fs.DOCTOR_CHECKS]
    assert len(ids) == len(set(ids))
    assert fs.DOCTOR_CHECK_IDS == tuple(ids)
    for spec in fs.DOCTOR_CHECKS:
        assert fs._CHECK_ID_RE.match(spec.id), spec.id
        assert spec.severity in fs.CHECK_SEVERITIES
    with pytest.raises(ValueError):
        fs._make_spec("Not_Kebab", "advisory", lambda ctx: fs._result("ok", ""))
    with pytest.raises(ValueError):
        fs._make_spec("fine-id", "critical", lambda ctx: fs._result("ok", ""))


def test_check_record_validates_enums_and_remedy_shape(fs) -> None:
    record = fs._check_record(
        "x-y", "warn", "advisory", "d", {"k": 1}, fs._remedy("do it", "cmd", "local-write"),
    )
    assert tuple(record) == CHECK_KEYS
    assert tuple(record["remedy"]) == ("description", "command", "safety")
    with pytest.raises(ValueError):
        fs._check_record("x", "meh", "advisory", "d")
    with pytest.raises(ValueError):
        fs._check_record("x", "ok", "severe", "d")
    with pytest.raises(ValueError):
        fs._check_record("x", "warn", "advisory", "d", None, {"description": "no tier"})
    with pytest.raises(ValueError):
        fs._remedy("d", None, "sudo")
    with pytest.raises(ValueError):
        fs._check_record("x", "ok", "advisory", "d", ["not", "a", "dict"])


# --------------------------------------------------------------------------- #
# Driver: crash isolation, warn-only demotion, whole-driver fallback
# --------------------------------------------------------------------------- #


def _ctx(fs, tmp_path: Path):
    return fs._build_check_context(
        tmp_path / "specs", tmp_path / "forge.config.json", CONFIG_SCHEMA,
        config={}, current_branch=None, default_branch=None, rows=[], features=[],
        plugin_root={"resolved": False, "error": "n/a"},
    )


def test_driver_isolates_a_crashing_check(fs, tmp_path: Path) -> None:
    """One raising check becomes ``na`` naming the exception; its neighbours run."""
    def boom(ctx):
        raise RuntimeError("boom")

    specs = [
        fs._make_spec("good-one", "advisory", lambda ctx: fs._result("ok", "fine")),
        fs._make_spec("bad-one", "blocking", boom),
        fs._make_spec("good-two", "advisory", lambda ctx: fs._result("warn", "hmm")),
    ]
    records = fs._run_checks(_ctx(fs, tmp_path), specs)
    assert [r["status"] for r in records] == ["ok", "na", "warn"]
    assert records[1]["id"] == "bad-one"
    assert records[1]["severity"] == "blocking"
    assert records[1]["detail"] == "check crashed: RuntimeError: boom"
    assert records[1]["remedy"] is None


def test_driver_turns_malformed_results_into_na(fs, tmp_path: Path) -> None:
    """A non-dict result, a bad status, an unserialisable evidence → ``na``."""
    specs = [
        fs._make_spec("returns-list", "advisory", lambda ctx: ["nope"]),
        fs._make_spec("bad-status", "advisory", lambda ctx: fs._result("meh", "x")),
        fs._make_spec(
            "bad-evidence", "advisory", lambda ctx: fs._result("ok", "x", {"p": Path("/")}),
        ),
        fs._make_spec(
            "bad-remedy", "advisory",
            lambda ctx: fs._result("warn", "x", None, {"description": "d", "command": None}),
        ),
    ]
    records = fs._run_checks(_ctx(fs, tmp_path), specs)
    assert [r["status"] for r in records] == ["na"] * 4
    assert all(r["detail"].startswith("check crashed: ") for r in records)
    json.dumps(records)


def test_driver_demotes_fail_to_warn_until_promoted(fs, tmp_path: Path) -> None:
    """INV-1 structurally: no un-promoted check can emit ``fail``."""
    assert fs.FAIL_PROMOTED_CHECK_IDS == frozenset()
    specs = [fs._make_spec("wants-to-fail", "blocking", lambda ctx: fs._result("fail", "x"))]
    (record,) = fs._run_checks(_ctx(fs, tmp_path), specs)
    assert record["status"] == "warn"
    assert record["evidence"] == {"demotedFromFail": True}


def test_driver_crash_degrades_every_check_to_na(fs, monkeypatch, tmp_path: Path) -> None:
    """If the context itself cannot be built, every requested check is ``na``."""
    def explode(*args, **kwargs):
        raise OSError("disk on fire")

    monkeypatch.setattr(fs, "_build_check_context", explode)
    report = fs.doctor_report(tmp_path / "specs", tmp_path / "forge.config.json")
    assert tuple(report)[-3:] == ("checks", "checksSummary", "remedyClusters")
    assert len(report["checks"]) == len(fs.DOCTOR_CHECKS)
    for record in report["checks"]:
        assert record["status"] == "na"
        assert record["detail"] == "check driver crashed: OSError: disk on fire"
    assert report["checksSummary"]["na"] == len(fs.DOCTOR_CHECKS)
    assert report["remedyClusters"] == []


def test_only_filters_the_registry_in_registry_order(fs, monkeypatch, tmp_path: Path) -> None:
    specs = (
        fs._make_spec("a-one", "advisory", lambda ctx: fs._result("ok", "")),
        fs._make_spec("b-two", "advisory", lambda ctx: fs._result("ok", "")),
        fs._make_spec("c-three", "advisory", lambda ctx: fs._result("ok", "")),
    )
    monkeypatch.setattr(fs, "DOCTOR_CHECKS", specs)
    report = fs.doctor_report(
        tmp_path / "specs", tmp_path / "forge.config.json", only=frozenset({"c-three", "a-one"}),
    )
    assert [r["id"] for r in report["checks"]] == ["a-one", "c-three"]


def test_checks_summary_counts_every_status(fs) -> None:
    records = [
        fs._check_record("a", "ok", "advisory", ""),
        fs._check_record("b", "warn", "advisory", ""),
        fs._check_record("c", "na", "advisory", ""),
        fs._check_record("d", "warn", "advisory", ""),
    ]
    assert fs._checks_summary(records) == {"ok": 1, "warn": 2, "fail": 0, "na": 1}
    assert fs._checks_summary([]) == {"ok": 0, "warn": 0, "fail": 0, "na": 0}


# --------------------------------------------------------------------------- #
# Remedy clustering
# --------------------------------------------------------------------------- #


def test_cluster_checks_merges_identical_commands_and_skips_report_only(fs) -> None:
    records = [
        fs._check_record("a", "warn", "advisory", "", None, fs._remedy("A", "rauf update .", "local-write")),
        fs._check_record("b", "ok", "advisory", ""),
        fs._check_record("c", "warn", "advisory", "", None, fs._remedy("C", None, "local-write")),
        fs._check_record("d", "warn", "blocking", "", None, fs._remedy("D", "gh auth login", "network")),
        fs._check_record("e", "warn", "advisory", "", None, fs._remedy("E", "rauf update .", "global-install")),
    ]
    clusters = fs.cluster_checks(records)
    assert [tuple(c) for c in clusters] == [("command", "safety", "checkIds", "description")] * 2
    assert clusters[0] == {
        "command": "rauf update .",
        "safety": "global-install",  # the most conservative member tier wins
        "checkIds": ["a", "e"],
        "description": "A",
    }
    assert clusters[1]["checkIds"] == ["d"]
    assert fs.cluster_checks([]) == []
    # Deterministic: the same input twice yields byte-identical clusters.
    assert json.dumps(fs.cluster_checks(records)) == json.dumps(clusters)


# --------------------------------------------------------------------------- #
# --schema and the schema validator
# --------------------------------------------------------------------------- #


def test_schema_flag_with_unreadable_schema_still_exits_zero(tmp_path: Path) -> None:
    """``_loop_runner_defaults`` raises UsageError (exit 2) elsewhere; doctor absorbs it."""
    result = _doctor(tmp_path, "--schema", str(tmp_path / "missing-schema.json"))
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert report["checksSummary"]["fail"] == 0
    assert "Traceback" not in result.stderr


def test_schema_flag_with_corrupt_schema_still_exits_zero(tmp_path: Path) -> None:
    bad = tmp_path / "schema.json"
    bad.write_text("{not json")
    result = _doctor(tmp_path, "--schema", str(bad))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["checksSummary"]["fail"] == 0


@pytest.mark.parametrize("config", [
    {},
    {"stack": "python", "autoVerify": True},
    {"stack": 3, "autoVerifyStages": {"forge-1-prd": True}},
    {"docsStage": "bogus", "loopIterationMultiplier": "2"},
    {"loopRunner": {"bin": 7, "unknown": True}},
    {"loopRunner": "rauf"},
    {"contextWindowTokens": True},
])
def test_schema_violations_match_the_test_suite_validator(fs, config: dict) -> None:
    """The in-script validator is a port of ``tests/_state_schema.py::_check``.

    The port is a strict superset (it also validates ``additionalProperties``
    given as a schema, and ``minimum``/``maximum``); on the subset both engines
    support, their findings are identical.
    """
    schema = json.loads(CONFIG_SCHEMA.read_text(encoding="utf-8"))
    assert fs._schema_violations(config, schema, schema, "$") == reference_schema_check(
        config, schema, schema, "$",
    )


def test_schema_violations_is_a_superset_of_the_reference(fs) -> None:
    schema = json.loads(CONFIG_SCHEMA.read_text(encoding="utf-8"))
    config = {"autoVerifyStages": {"forge-1-prd": "yes"}, "loopIterationMultiplier": 0}
    ours = fs._schema_violations(config, schema, schema, "$")
    theirs = reference_schema_check(config, schema, schema, "$")
    assert set(theirs) <= set(ours)
    assert "$.autoVerifyStages.forge-1-prd: expected boolean, got str" in ours


def test_schema_violations_handles_ref_numbers_and_additional_properties(fs) -> None:
    schema = {
        "definitions": {"n": {"type": "integer", "minimum": 1, "maximum": 3}},
        "type": "object",
        "properties": {"a": {"$ref": "#/definitions/n"}, "b": {"$ref": "#/definitions/zz"}},
        "additionalProperties": {"type": "string"},
    }
    assert fs._schema_violations({"a": 2, "x": "s"}, schema, schema, "$") == []
    out = fs._schema_violations({"a": 0, "b": 1, "x": 5}, schema, schema, "$")
    assert out == [
        "$.a: 0 below minimum 1",
        "$.b: unresolvable $ref '#/definitions/zz'",
        "$.x: expected string, got int",
    ]
    assert fs._schema_violations({"a": 9}, schema, schema, "$") == ["$.a: 9 above maximum 3"]
    assert fs._schema_violations({"a": True}, schema, schema, "$") == [
        "$.a: expected integer, got bool",
    ]


# --------------------------------------------------------------------------- #
# Helpers: template rendering and version parsing
# --------------------------------------------------------------------------- #


def test_render_runner_command_quotes_tokens_and_rejects_unrendered(fs) -> None:
    lr = {"bin": "rauf-stable"}
    assert fs._render_runner_command("{bin} version --json", lr) == ["rauf-stable", "version", "--json"]
    argv = fs._render_runner_command(
        "{bin} backlog validate . --backlog {backlogDir} --specs-dir {specsDir} --json",
        lr, backlogDir="specs/my feature", specsDir="./specs",
    )
    assert argv == [
        "rauf-stable", "backlog", "validate", ".", "--backlog", "specs/my feature",
        "--specs-dir", "./specs", "--json",
    ]
    # An injection attempt in a token stays a single argv element.
    argv = fs._render_runner_command("{bin} x {dir}", lr, dir="a; rm -rf /")
    assert argv == ["rauf-stable", "x", "a; rm -rf /"]
    assert fs._render_runner_command("{bin} run {missing}", lr) is None
    assert fs._render_runner_command("", lr) is None
    assert fs._render_runner_command("{bin} 'unterminated", lr) is None


def test_semver_and_installed_by_parsers(fs) -> None:
    assert fs._parse_semver("0.14.0") == (0, 14, 0)
    assert fs._parse_semver("v1.2.3 ") == (1, 2, 3)
    assert fs._parse_semver("1.2.3-beta.1") is None
    assert fs._parse_semver("1.2") is None
    assert fs._parse_semver(None) is None
    assert fs._parse_semver(14) is None
    assert fs._fmt_semver((0, 14, 0)) == "0.14.0"
    assert fs._parse_installed_by("rauf-manager@0.13.0") == ("rauf-manager", (0, 13, 0))
    assert fs._parse_installed_by("rauf-manager@v0.13.0") == ("rauf-manager", (0, 13, 0))
    assert fs._parse_installed_by("rauf-manager") is None
    assert fs._parse_installed_by("rauf-manager@0.13.0-rc.1") is None
    assert fs._parse_installed_by(None) is None
    assert fs._first_backticked("Run `rauf install .` then `x`") == "rauf install ."
    assert fs._first_backticked("no command here") is None
    assert fs._first_backticked(None) is None


def test_run_probe_never_raises_and_caps_nothing_on_its_own(fs, monkeypatch) -> None:
    missing = fs._run_probe(["/nonexistent/binary-for-doctor-test"])
    assert missing["ok"] is False and missing["returncode"] is None
    assert missing["error"] and missing["timedOut"] is False
    ok = fs._run_probe([sys.executable, "-c", "print('hi')"])
    assert ok["ok"] is True and ok["stdout"] == "hi\n"
    secret = fs._run_probe([sys.executable, "-c", "print('token')"], discard_stdout=True)
    assert secret["ok"] is True and secret["stdout"] == ""
    monkeypatch.setattr(fs, "_PROBE_TIMEOUT_S", 1)
    slow = fs._run_probe([sys.executable, "-c", "import time; time.sleep(5)"])
    assert slow["timedOut"] is True and slow["ok"] is False
    assert fs._head("x" * 1000).endswith("…") and len(fs._head("x" * 1000)) == 401
    assert fs._head(None) == ""


# --------------------------------------------------------------------------- #
# Promoted legacy fields: plugin-root, config-schema, backlog-present,
# branch-state, sandbox-root
# --------------------------------------------------------------------------- #

def test_plugin_root_ok_from_the_repo_checkout(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    report = doctor_report(project, scrubbed_env(tmp_path))
    record = check(report, "plugin-root")
    assert record["status"] == "ok"
    assert record["severity"] == "blocking"
    assert record["evidence"]["root"] == str(REPO_ROOT)
    assert "version" in record["detail"]
    assert record["remedy"] is None


def test_plugin_root_warns_with_global_install_remedy_when_unresolvable(tmp_path: Path) -> None:
    """A lone helper copy (no sentinel above it) cannot resolve — warn, never crash."""
    lone = tmp_path / "lone" / "scripts"
    lone.mkdir(parents=True)
    for name in ("forge-session.py", "forge-root.sh"):
        (lone / name).write_bytes((REPO_ROOT / "scripts" / name).read_bytes())
    project = make_project(tmp_path)
    result = run_doctor(project, scrubbed_env(tmp_path), helper=lone / "forge-session.py")
    assert result.returncode == 0, result.stderr
    record = check(json.loads(result.stdout), "plugin-root")
    assert record["status"] == "warn"
    assert record["evidence"]["resolved"] is False
    assert record["remedy"]["safety"] == "global-install"
    assert record["remedy"]["command"] is None


def test_config_schema_na_without_config(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    record = check(doctor_report(project, scrubbed_env(tmp_path)), "config-schema")
    assert record["status"] == "na"


def test_config_schema_ok_reports_unknown_keys_only_as_evidence(tmp_path: Path) -> None:
    project = make_project(tmp_path, config={"stack": "python", "gateCommand": "x"})
    record = check(doctor_report(project, scrubbed_env(tmp_path)), "config-schema")
    assert record["status"] == "ok"
    assert record["evidence"]["unknownKeys"] == ["gateCommand"]
    assert record["evidence"]["violations"] == []
    assert "gateCommand" in record["detail"]


def test_config_schema_warns_on_violations_duplicates_and_bad_auto_verify_keys(
    tmp_path: Path,
) -> None:
    project = make_project(tmp_path)
    (project / "forge.config.json").write_text(
        '{"stack": 3, "stack": "python", "docsStage": "nope", '
        '"autoVerifyStages": {"forge-1-prod": true}}'
    )
    record = check(doctor_report(project, scrubbed_env(tmp_path)), "config-schema")
    assert record["status"] == "warn"
    ev = record["evidence"]
    assert ev["duplicateKeys"] == ["stack"]
    assert ev["invalidAutoVerifyKeys"] == ["forge-1-prod"]
    assert any("docsStage" in v for v in ev["violations"])
    assert record["remedy"]["safety"] == "local-write"
    assert record["remedy"]["command"] is None


def test_config_schema_warns_on_unparseable_config(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    (project / "forge.config.json").write_text("{nope")
    record = check(doctor_report(project, scrubbed_env(tmp_path)), "config-schema")
    assert record["status"] == "warn"
    assert record["evidence"]["parseError"].startswith("JSONDecodeError")
    (project / "forge.config.json").write_text("[1, 2]")
    record = check(doctor_report(project, scrubbed_env(tmp_path)), "config-schema")
    assert record["status"] == "warn"
    assert "expected object" in record["detail"]


def test_config_schema_warns_when_the_bundled_schema_is_unreadable(tmp_path: Path) -> None:
    project = make_project(tmp_path, config={"stack": "python"})
    report = doctor_report(project, scrubbed_env(tmp_path), "--schema", str(tmp_path / "nope"))
    record = check(report, "config-schema")
    assert record["status"] == "warn"
    assert record["evidence"]["schemaError"]
    assert record["remedy"]["safety"] == "global-install"


def test_backlog_present_na_before_forge_4_and_warns_on_missing(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    write_feature(project, "early", pipeline_state(["forge-1-prd", "forge-2-tech"]))
    record = check(doctor_report(project, scrubbed_env(tmp_path)), "backlog-present")
    assert record["status"] == "na"

    write_feature(project, "has-it", pipeline_state(PRODUCTION[:4]), backlog=True)
    write_feature(project, "lost-it", pipeline_state(PRODUCTION[:4]), epic="big")
    record = check(doctor_report(project, scrubbed_env(tmp_path)), "backlog-present")
    assert record["status"] == "warn"
    assert record["severity"] == "blocking"
    assert "lost-it [big]" in record["detail"]
    assert "forge-4-backlog" in record["detail"]
    rows = {row["name"]: row for row in record["evidence"]["features"]}
    assert set(rows) == {"has-it", "lost-it"}  # 'early' is not eligible
    assert rows["lost-it"]["exists"] is False and rows["has-it"]["exists"] is True
    assert record["remedy"] is None  # the fix is a slash command, not a shell command
    assert record["evidence"]["skipped"] == 1


def test_backlog_present_ok_includes_complete_features(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    write_feature(project, "done", pipeline_state(PRODUCTION), backlog=True)
    record = check(doctor_report(project, scrubbed_env(tmp_path)), "backlog-present")
    assert record["status"] == "ok"
    assert record["detail"] == "1 backlog(s) present"


def test_branch_state_na_outside_git_or_without_pending_features(tmp_path: Path) -> None:
    project = make_project(tmp_path, git_branch=None)
    write_feature(project, "f", pipeline_state(["forge-1-prd"], branch="forge/f"))
    record = check(doctor_report(project, scrubbed_env(tmp_path)), "branch-state")
    assert record["status"] == "na" and "not a git repository" in record["detail"]

    project = make_project(tmp_path)
    write_feature(project, "f", pipeline_state(PRODUCTION, branch="forge/f"))
    record = check(doctor_report(project, scrubbed_env(tmp_path)), "branch-state")
    assert record["status"] == "na"
    assert record["evidence"]["skippedComplete"] == 1


def test_branch_state_warn_drift_on_default_branch_suggests_git_switch(tmp_path: Path) -> None:
    project = make_project(tmp_path, git_branch="main")
    write_feature(project, "pending", pipeline_state(["forge-1-prd"], branch="forge/pending"))
    write_feature(project, "finished", pipeline_state(PRODUCTION, branch="forge/finished"))
    write_feature(project, "matching", pipeline_state(["forge-1-prd"], branch="main"))
    record = check(doctor_report(project, scrubbed_env(tmp_path)), "branch-state")
    assert record["status"] == "warn"
    assert record["severity"] == "advisory"
    assert "pending (warn-drift" in record["detail"]
    assert "finished" not in record["detail"]  # complete features are skipped
    assert record["remedy"] == {
        "description": (
            "Switch to the feature's recorded branch before running forge-2-tech "
            "(create it with `git switch -c` if it no longer exists)"
        ),
        "command": "git switch forge/pending",
        "safety": "local-write",
    }
    rows = {row["name"]: row for row in record["evidence"]["features"]}
    assert rows["matching"]["reconcile"] is None and rows["matching"]["remedy"] is None
    assert record["evidence"]["skippedComplete"] == 1


def test_branch_state_adopt_current_on_topic_branch_suggests_state_branch(
    tmp_path: Path,
) -> None:
    project = make_project(tmp_path, git_branch="feature/other")
    write_feature(
        project, "member", pipeline_state(["forge-1-prd"], branch="forge/member"), epic="ep",
    )
    record = check(doctor_report(project, scrubbed_env(tmp_path)), "branch-state")
    assert record["status"] == "warn"
    assert "member [ep] (adopt-current" in record["detail"]
    cmd = record["remedy"]["command"]
    assert cmd.startswith("python3 ")
    assert cmd.endswith(
        " state-branch --feature member --branch feature/other --specs-dir specs --epic ep"
    )
    assert record["remedy"]["safety"] == "local-write"


def test_branch_state_two_drifts_yield_a_per_feature_remedy(tmp_path: Path) -> None:
    project = make_project(tmp_path, git_branch="main")
    write_feature(project, "one", pipeline_state(["forge-1-prd"], branch="forge/one"))
    write_feature(project, "two", pipeline_state(["forge-1-prd"], branch="forge/two"))
    report = doctor_report(project, scrubbed_env(tmp_path))
    record = check(report, "branch-state")
    assert record["status"] == "warn"
    assert record["remedy"]["command"] is None
    assert record["remedy"]["description"].startswith("per-feature")
    assert record["remedy"]["safety"] == "local-write"
    commands = sorted(row["remedy"]["command"] for row in record["evidence"]["features"])
    assert commands == ["git switch forge/one", "git switch forge/two"]
    # A command-less top-level remedy is report-only: no cluster is formed for it.
    assert all("branch-state" not in c["checkIds"] for c in report["remedyClusters"])


def test_sandbox_root_mirrors_the_legacy_root_sandbox_block(fs, monkeypatch) -> None:
    monkeypatch.setattr(fs.os, "geteuid", lambda: 0)
    monkeypatch.delenv("IS_SANDBOX", raising=False)
    record = fs._check_sandbox_root(None)
    assert record["status"] == "warn"
    assert record["remedy"]["command"] == "export IS_SANDBOX=1"
    assert record["remedy"]["safety"] == "read-only"
    assert record["evidence"]["loopWillSetSandbox"] is True
    monkeypatch.setenv("IS_SANDBOX", "1")
    assert fs._check_sandbox_root(None)["status"] == "ok"
    monkeypatch.setattr(fs.os, "geteuid", lambda: 1000)
    assert fs._check_sandbox_root(None)["detail"] == "not running as root"
    monkeypatch.delattr(fs.os, "geteuid")
    assert fs._check_sandbox_root(None)["status"] == "na"


def test_no_check_ever_emits_fail_and_warn_set_is_reported(tmp_path: Path) -> None:
    project = make_project(tmp_path, git_branch="main")
    write_feature(project, "drift", pipeline_state(PRODUCTION[:4], branch="forge/drift"))
    report = doctor_report(project, scrubbed_env(tmp_path))
    assert report["checksSummary"]["fail"] == 0
    assert {"branch-state", "backlog-present"} <= warn_ids(report)


# --------------------------------------------------------------------------- #
# runner-* checks (fake runner on a scrubbed PATH)
# --------------------------------------------------------------------------- #

RUNNER_CHECKS = (
    "runner-binary", "runner-version", "runner-wired", "runner-legacy-layout",
    "runner-artifacts-stale", "runner-profile-drift",
)
RAUF_JSON = {
    "installedBy": "rauf-manager@0.14.0",
    "profile": {"commands": {"test": "pytest -q"}, "verify": "pytest -q && ruff check ."},
}
CONFIG = {"stack": "python", "typeCheckCommand": "ruff check .", "testCommand": "pytest -q"}


def _loop_project(tmp_path: Path, **kwargs) -> Path:
    """A project with one feature about to run forge-5-loop (runner relevant)."""
    project = make_project(tmp_path, **kwargs)
    write_feature(
        project, "looper", pipeline_state(PRODUCTION[:4], branch="main"), backlog=True,
    )
    return project


def test_runner_checks_all_ok_with_a_healthy_fake_runner(tmp_path: Path) -> None:
    env = scrubbed_env(tmp_path)
    fake_runner(env)
    project = _loop_project(tmp_path, config=CONFIG, rauf_json=RAUF_JSON)
    report = doctor_report(project, env)
    for check_id in RUNNER_CHECKS:
        assert check(report, check_id)["status"] == "ok", check(report, check_id)
    assert check(report, "runner-binary")["evidence"]["customized"] is False
    assert check(report, "runner-version")["evidence"]["reported"] == "0.14.0"
    assert check(report, "runner-profile-drift")["evidence"]["matches"] == ["commands.test"]
    # The version probe runs exactly once per doctor run, and nothing else ran.
    assert probe_log(env) == [f"{bin_dir(env)}/rauf version --json"]


def test_runner_checks_na_when_loop_runner_config_is_unavailable(tmp_path: Path) -> None:
    env = scrubbed_env(tmp_path)
    fake_runner(env)
    project = _loop_project(tmp_path, config=CONFIG, rauf_json=RAUF_JSON)
    report = doctor_report(project, env, "--schema", str(tmp_path / "missing.json"))
    for check_id in RUNNER_CHECKS:
        record = check(report, check_id)
        assert record["status"] == "na", record
        assert "loopRunner config unavailable" in record["detail"]
    assert probe_log(env) == []


def test_runner_binary_default_missing_uses_install_hint(tmp_path: Path) -> None:
    env = scrubbed_env(tmp_path)  # no fake runner at all
    project = _loop_project(tmp_path, config=CONFIG, rauf_json=RAUF_JSON)
    report = doctor_report(project, env)
    record = check(report, "runner-binary")
    assert record["status"] == "warn" and record["severity"] == "blocking"
    assert record["evidence"]["path"] is None
    assert record["remedy"]["safety"] == "global-install"
    assert record["remedy"]["command"] == "npx @garygentry/feature-forge install"
    assert "feature-forge" in record["remedy"]["description"]
    # Downstream runner checks degrade to na, never crash, never spawn.
    assert check(report, "runner-version")["status"] == "na"
    assert check(report, "runner-artifacts-stale")["status"] == "na"
    assert check(report, "runner-wired")["status"] == "ok"  # .rauf.json is still present
    assert probe_log(env) == []


def test_runner_binary_custom_missing_but_default_present_is_a_config_fix(
    tmp_path: Path,
) -> None:
    env = scrubbed_env(tmp_path)
    fake_runner(env)  # the default 'rauf'
    config = {**CONFIG, "loopRunner": {"bin": "rauf-nightly"}}
    project = _loop_project(tmp_path, config=config, rauf_json=RAUF_JSON)
    record = check(doctor_report(project, env), "runner-binary")
    assert record["status"] == "warn"
    assert record["evidence"]["customized"] is True
    assert record["evidence"]["defaultOnPath"] == f"{bin_dir(env)}/rauf"
    assert record["remedy"]["safety"] == "local-write"
    assert record["remedy"]["command"] is None
    assert "loopRunner.bin" in record["remedy"]["description"]


def test_runner_binary_custom_missing_and_default_missing(tmp_path: Path) -> None:
    env = scrubbed_env(tmp_path)
    config = {**CONFIG, "loopRunner": {"bin": "rauf-nightly"}}
    project = _loop_project(tmp_path, config=config, rauf_json=RAUF_JSON)
    record = check(doctor_report(project, env), "runner-binary")
    assert record["status"] == "warn"
    assert record["remedy"]["safety"] == "global-install"
    assert record["remedy"]["command"] is None
    assert "rauf-nightly" in record["remedy"]["description"]


def test_runner_binary_custom_present_is_ok(tmp_path: Path) -> None:
    env = scrubbed_env(tmp_path)
    fake_runner(env, name="rauf-stable")
    config = {**CONFIG, "loopRunner": {"bin": "rauf-stable"}}
    project = _loop_project(tmp_path, config=config, rauf_json=RAUF_JSON)
    report = doctor_report(project, env)
    assert check(report, "runner-binary")["status"] == "ok"
    assert check(report, "runner-version")["status"] == "ok"
    assert probe_log(env) == [f"{bin_dir(env)}/rauf-stable version --json"]


@pytest.mark.parametrize("version, expect", [
    ("0.13.9", "below minRunnerVersion"),
    ("0.15.0-beta.1", "could not parse a semver"),
    (14, "could not parse a semver"),
])
def test_runner_version_warns_with_install_remedy(tmp_path: Path, version, expect) -> None:
    env = scrubbed_env(tmp_path)
    fake_runner(env, version=version)
    project = _loop_project(tmp_path, config=CONFIG, rauf_json=RAUF_JSON)
    record = check(doctor_report(project, env), "runner-version")
    assert record["status"] == "warn", record
    assert expect in record["detail"]
    assert record["evidence"]["required"] == "0.14.0"
    assert record["remedy"]["safety"] == "global-install"


def test_runner_version_probe_failure_is_a_warn_with_evidence(tmp_path: Path) -> None:
    env = scrubbed_env(tmp_path)
    fake_runner(env, version_exit=3)
    project = _loop_project(tmp_path, config=CONFIG, rauf_json=RAUF_JSON)
    report = doctor_report(project, env)
    record = check(report, "runner-version")
    assert record["status"] == "warn"
    assert record["evidence"]["exitCode"] == 3
    assert "exit 3" in record["detail"]
    assert record["evidence"]["command"] == "rauf version --json"
    # With no live version, staleness cannot be judged.
    assert check(report, "runner-artifacts-stale")["status"] == "na"


def test_runner_version_honours_a_custom_min_and_command(tmp_path: Path) -> None:
    env = scrubbed_env(tmp_path)
    fake_runner(env, version="0.14.0")
    config = {**CONFIG, "loopRunner": {"minRunnerVersion": "0.15.0"}}
    project = _loop_project(tmp_path, config=config, rauf_json=RAUF_JSON)
    record = check(doctor_report(project, env), "runner-version")
    assert record["status"] == "warn" and "0.15.0" in record["detail"]
    config = {**CONFIG, "loopRunner": {"minRunnerVersion": "latest"}}
    project = _loop_project(tmp_path, config=config, rauf_json=RAUF_JSON)
    record = check(doctor_report(project, env), "runner-version")
    assert record["status"] == "warn" and "not a plain semver" in record["detail"]
    assert record["remedy"]["safety"] == "local-write"
    config = {**CONFIG, "loopRunner": {"versionCommand": "{bin} {unknownToken}"}}
    project = _loop_project(tmp_path, config=config, rauf_json=RAUF_JSON)
    record = check(doctor_report(project, env), "runner-version")
    assert record["status"] == "na" and "cannot be rendered" in record["detail"]


def test_runner_version_timeout_degrades_to_warn(fs, monkeypatch, tmp_path: Path) -> None:
    """A hung runner is cut off at the probe timeout — a warn, never a hang (INV-3)."""
    env = scrubbed_env(tmp_path)
    fake_runner(env, hang_seconds=5)
    project = _loop_project(tmp_path, config=CONFIG, rauf_json=RAUF_JSON)
    monkeypatch.setenv("PATH", env["PATH"])
    monkeypatch.setenv("HOME", env["HOME"])
    monkeypatch.chdir(project)
    monkeypatch.setattr(fs, "_PROBE_TIMEOUT_S", 1)
    report = fs.doctor_report(
        Path("specs"), Path("forge.config.json"), only=frozenset({"runner-version"}),
    )
    (record,) = report["checks"]
    assert record["status"] == "warn"
    assert record["evidence"]["timedOut"] is True
    assert "timed out after 1s" in record["detail"]


def test_runner_wired_na_before_forge_4_then_warns(tmp_path: Path) -> None:
    env = scrubbed_env(tmp_path)
    fake_runner(env)
    project = make_project(tmp_path, config=CONFIG)  # no .rauf.json
    write_feature(project, "early", pipeline_state(["forge-1-prd", "forge-2-tech"]))
    record = check(doctor_report(project, env), "runner-wired")
    assert record["status"] == "na"
    assert record["evidence"]["runnerRelevant"] is False

    write_feature(project, "ready", pipeline_state(PRODUCTION[:3]))  # next: forge-4-backlog
    report = doctor_report(project, env)
    record = check(report, "runner-wired")
    assert record["status"] == "warn" and record["severity"] == "blocking"
    assert record["remedy"] == {
        "description": record["remedy"]["description"],
        "command": "rauf install .",
        "safety": "local-write",
    }
    assert "rauf install ." in record["remedy"]["description"]
    assert check(report, "runner-artifacts-stale")["status"] == "na"
    assert check(report, "runner-profile-drift")["status"] == "na"
    # doctor advises `rauf install .`; it never runs it (one version probe per run).
    assert probe_log(env) == [f"{bin_dir(env)}/rauf version --json"] * 2


def test_runner_legacy_layout_warns_on_ralph_artifacts_and_na_for_other_runners(
    tmp_path: Path,
) -> None:
    env = scrubbed_env(tmp_path)
    fake_runner(env)
    project = _loop_project(tmp_path, config=CONFIG, rauf_json=RAUF_JSON)
    (project / ".ralph.json").write_text("{}")
    (project / ".ralph").mkdir()
    record = check(doctor_report(project, env), "runner-legacy-layout")
    assert record["status"] == "warn"
    assert record["evidence"] == {
        "runnerName": "rauf", "ralphJson": True, "ralphDir": True,
        "runnerOnPath": f"{bin_dir(env)}/rauf",
    }
    assert record["remedy"]["command"] == "rauf migrate ."
    assert record["remedy"]["safety"] == "local-write"
    config = {**CONFIG, "loopRunner": {"name": "other"}}
    project = _loop_project(tmp_path, config=config, rauf_json=RAUF_JSON)
    record = check(doctor_report(project, env), "runner-legacy-layout")
    assert record["status"] == "na"
    assert "migrate" not in " ".join(probe_log(env))


@pytest.mark.parametrize("installed_by, status, command, safety", [
    ("rauf-manager@0.14.0", "ok", None, None),
    ("rauf-manager@0.13.0", "warn", "rauf update .", "local-write"),
    ("rauf-manager@0.15.0", "warn", "npx @garygentry/feature-forge install", "global-install"),
    ("rauf-manager", "warn", "rauf update .", "local-write"),
    (None, "warn", "rauf update .", "local-write"),
])
def test_runner_artifacts_stale_compares_installed_by_with_live(
    tmp_path: Path, installed_by, status, command, safety,
) -> None:
    env = scrubbed_env(tmp_path)
    fake_runner(env, version="0.14.0")
    rauf_json = {**RAUF_JSON, "installedBy": installed_by}
    if installed_by is None:
        del rauf_json["installedBy"]
    project = _loop_project(tmp_path, config=CONFIG, rauf_json=rauf_json)
    record = check(doctor_report(project, env), "runner-artifacts-stale")
    assert record["status"] == status, record
    assert record["severity"] == "advisory"
    assert record["evidence"]["liveVersion"] == "0.14.0"
    if status == "ok":
        assert record["remedy"] is None
    else:
        assert record["remedy"]["command"] == command
        assert record["remedy"]["safety"] == safety
    assert "update" not in " ".join(probe_log(env))


def test_runner_artifacts_stale_na_when_precondition_unreadable_is_a_warn(tmp_path: Path) -> None:
    env = scrubbed_env(tmp_path)
    fake_runner(env)
    project = _loop_project(tmp_path, config=CONFIG)
    (project / ".rauf.json").write_text("{corrupt")
    report = doctor_report(project, env)
    record = check(report, "runner-artifacts-stale")
    assert record["status"] == "warn" and "no parseable installedBy" in record["detail"]
    assert check(report, "runner-profile-drift")["status"] == "na"


def test_runner_profile_drift_states(tmp_path: Path) -> None:
    env = scrubbed_env(tmp_path)
    fake_runner(env)
    # Matches verify only (whitespace-normalised).
    rauf_json = {"installedBy": "rauf-manager@0.14.0",
                 "profile": {"commands": {"test": "pnpm test"}, "verify": "pytest   -q"}}
    project = _loop_project(tmp_path, config=CONFIG, rauf_json=rauf_json)
    record = check(doctor_report(project, env), "runner-profile-drift")
    assert record["status"] == "ok" and record["evidence"]["matches"] == ["verify"]
    # Matches neither → warn, advisory, no remedy.
    rauf_json["profile"]["verify"] = "pnpm gate"
    project = _loop_project(tmp_path, config=CONFIG, rauf_json=rauf_json)
    record = check(doctor_report(project, env), "runner-profile-drift")
    assert record["status"] == "warn" and record["remedy"] is None
    assert "divergence may be deliberate" in record["detail"]
    # No testCommand → na; no profile → na; profile without commands → na.
    project = _loop_project(tmp_path, config={"stack": "python"}, rauf_json=rauf_json)
    assert check(doctor_report(project, env), "runner-profile-drift")["status"] == "na"
    project = _loop_project(tmp_path, config=CONFIG, rauf_json={"installedBy": "x@0.14.0"})
    assert check(doctor_report(project, env), "runner-profile-drift")["status"] == "na"
    project = _loop_project(tmp_path, config=CONFIG,
                            rauf_json={"installedBy": "x@0.14.0", "profile": {}})
    record = check(doctor_report(project, env), "runner-profile-drift")
    assert record["status"] == "na" and "no test or verify" in record["detail"]
