"""R5 drift guard — `forge-session.py effective-config` (spec 04, spec 06 §4.1).

The subcommand exists so no skill body has to read `forge-config-schema.json` just
to learn the `loopRunner` defaults, and so the defaults/overrides merge is
deterministic rather than a model's mental merge. These tests pin the four things
that makes true: the defaults come from the schema (not hardcoded), a user value
wins, an unknown key survives, and the failure modes land on the script's 0/2 exit
contract.

Stdlib only — no `jsonschema`, which is absent in CI. Schema conformance is checked
through the shared `_state_schema` validator, which every R4 guard also imports.
Subprocess calls use `sys.executable` so the suite tests the interpreter it runs on.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from _forge_paths import REFERENCES, SCRIPTS
from _state_schema import validate_effective_config

FS = str(SCRIPTS / "forge-session.py")
CONFIG_SCHEMA = REFERENCES / "forge-config-schema.json"


def _schema_defaults() -> dict:
    """Read the loopRunner defaults straight from the schema (the source of truth)."""
    schema = json.loads(CONFIG_SCHEMA.read_text(encoding="utf-8"))
    props = schema["properties"]["loopRunner"]["properties"]
    return {field: spec["default"] for field, spec in props.items() if "default" in spec}


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, FS, "effective-config", *args],
        capture_output=True,
        text=True,
    )


def test_missing_config_resolves_to_the_schema_defaults(tmp_path: Path) -> None:
    """No forge.config.json at all -> every schema default, exit 0."""
    result = _run("--config", str(tmp_path / "absent.json"), "--json")

    assert result.returncode == 0, result.stderr
    resolved = json.loads(result.stdout)
    defaults = _schema_defaults()
    assert len(defaults) == 22, f"schema no longer declares 22 defaults: {len(defaults)}"
    assert resolved == defaults
    assert resolved["name"] == "rauf"
    # Template defaults stay literal — effective-config resolves defaults, not
    # call-time substitution (spec 04 §3 note).
    assert "{bin}" in resolved["runCommand"]


def test_resolved_output_validates_against_the_config_schema(tmp_path: Path) -> None:
    """REQ-R4-03: the schema stays the source of truth, test-enforced without jsonschema."""
    config = tmp_path / "forge.config.json"
    config.write_text(json.dumps({"specsDir": "./specs"}), encoding="utf-8")

    result = _run("--config", str(config), "--json")

    assert result.returncode == 0, result.stderr
    resolved = json.loads(result.stdout)
    assert validate_effective_config(resolved) == [], validate_effective_config(resolved)


def test_user_override_wins_over_the_default(tmp_path: Path) -> None:
    """A user loopRunner field replaces its default; absent fields keep theirs."""
    config = tmp_path / "forge.config.json"
    config.write_text(
        json.dumps({"loopRunner": {"bin": "/usr/local/bin/ralph", "defaultAgent": "codex"}}),
        encoding="utf-8",
    )

    result = _run("--config", str(config), "--json")

    assert result.returncode == 0, result.stderr
    resolved = json.loads(result.stdout)
    assert resolved["bin"] == "/usr/local/bin/ralph"
    assert resolved["defaultAgent"] == "codex"
    assert resolved["name"] == _schema_defaults()["name"]
    assert validate_effective_config(resolved) == []


def test_unknown_user_key_is_passed_through(tmp_path: Path) -> None:
    """Parity with the hand-merge: a forward-compat/typo'd key is carried, not dropped.

    The config schema — not this subcommand — is the authority that flags an
    unknown key at author time (spec 04 §4).
    """
    config = tmp_path / "forge.config.json"
    config.write_text(
        json.dumps({"loopRunner": {"someFutureField": "keep-me"}}), encoding="utf-8"
    )

    result = _run("--config", str(config), "--json")

    assert result.returncode == 0, result.stderr
    resolved = json.loads(result.stdout)
    assert resolved["someFutureField"] == "keep-me"
    assert len(resolved) == len(_schema_defaults()) + 1


def test_malformed_config_degrades_to_pure_defaults_at_exit_0(tmp_path: Path) -> None:
    """`_load_config` already degrades a corrupt config to {} — that is not an error."""
    config = tmp_path / "forge.config.json"
    config.write_text("{ not json", encoding="utf-8")

    result = _run("--config", str(config), "--json")

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == _schema_defaults()


def test_unreadable_schema_exits_2(tmp_path: Path) -> None:
    """Without a schema there are no defaults to resolve — fail deterministically.

    Asserts the mechanism, not just the code: nothing on stdout (so a consumer
    capturing it never mistakes a partial result for a config) and a descriptive
    `Error:` line on stderr.
    """
    config = tmp_path / "forge.config.json"
    config.write_text("{}", encoding="utf-8")

    result = _run(
        "--config", str(config), "--schema", str(tmp_path / "nope.json"), "--json"
    )

    assert result.returncode == 2
    assert result.stdout == ""
    assert "Error:" in result.stderr
    assert "config schema unreadable" in result.stderr


def test_malformed_schema_exits_2(tmp_path: Path) -> None:
    """A present-but-unparseable schema is the same all-or-nothing failure."""
    schema = tmp_path / "schema.json"
    schema.write_text("{ not json", encoding="utf-8")

    result = _run("--schema", str(schema), "--json")

    assert result.returncode == 2
    assert result.stdout == ""
    assert "Error:" in result.stderr


def test_human_summary_is_emitted_without_json(tmp_path: Path) -> None:
    """The non---json path renders the readable table, still at exit 0."""
    result = _run("--config", str(tmp_path / "absent.json"))

    assert result.returncode == 0, result.stderr
    assert result.stdout.startswith("Effective loopRunner config:")
    assert "name" in result.stdout


def test_the_command_has_no_exit_1_branch() -> None:
    """The script's contract is 0/2 only (spec 04 §10); an unknown flag is a 2."""
    result = _run("--nope")

    assert result.returncode == 2


def test_the_validator_flags_a_malformed_block() -> None:
    """A guard that cannot go red is not coverage — prove the validator rejects."""
    bad = dict(_schema_defaults())
    bad["bin"] = 17  # schema declares every loopRunner field a string

    findings = validate_effective_config(bad)

    assert findings and "bin" in findings[0]
