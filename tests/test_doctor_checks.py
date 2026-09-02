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
