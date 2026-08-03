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

The second half of this module (from "Duplicate-aware JSON loader" onward) covers the
recursive duplicate-key diagnostics of `05-config-and-distribution.md` §2–§4 and the
matrix in `07-testing-strategy.md` §5. Those tests are **parametrized over both mirrored
copies** — the ones in `scripts/forge-session.py` and `scripts/forge-bootstrap.py` — so a
behavioural divergence fails here as well as structurally in
`tests/test_json_loader_parity.py`. They call the real in-file functions; the object hook
is never reproduced in test code (the two deliberate fakes are the negative control, and
they exist only to prove the matrix can go red).
"""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path
from types import ModuleType

import pytest

from _forge_paths import REFERENCES, SCRIPTS
from _state_schema import validate_effective_config
from test_json_loader_parity import mirrored_loader_pair

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


# --------------------------------------------------------------------------- #
# Duplicate-aware JSON loader — pure matrix over BOTH mirrored copies
# (05-config-and-distribution.md §2, 07-testing-strategy.md §5.1)
# --------------------------------------------------------------------------- #

#: The two mirrored copies, keyed by the flat script that carries each one. There is
#: no shared module by standing repository invariant (01-architecture-layout.md §3.4),
#: so the matrix below runs twice — once against each real in-file pair.
_LOADER_SOURCES = {
    "forge-bootstrap.py": SCRIPTS / "forge-bootstrap.py",
    "forge-session.py": SCRIPTS / "forge-session.py",
}


def _load_script_module(module_name: str, path: Path) -> ModuleType:
    """Load a hyphenated script as a module.

    Both filenames contain a hyphen, so neither is importable by name; this is the
    `importlib.util.spec_from_file_location` convention the rest of the suite uses
    (07 §5.1). Registered in `sys.modules` before exec so annotations resolve.
    """
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session", params=sorted(_LOADER_SOURCES), ids=sorted(_LOADER_SOURCES))
def loader(request: pytest.FixtureRequest) -> ModuleType:
    """Parametrize every loader row over both mirrored copies.

    `tests/test_json_loader_parity.py` proves the two source blocks are byte-identical;
    this fixture proves they *behave* identically, so a divergence that somehow survived
    the text comparison still fails here.
    """
    filename: str = request.param
    stem = filename.removesuffix(".py").replace("-", "_")
    return _load_script_module(f"_dupcfg_{stem}", _LOADER_SOURCES[filename])


def _write_json(tmp_path: Path, text: str, name: str = "forge.config.json") -> Path:
    """Write raw JSON text (duplicate keys and all) and return its path."""
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _warning_line(key: str, path: Path) -> str:
    """The exact stderr line from 05-config-and-distribution.md §2.2."""
    return (
        f"Warning: duplicate JSON key {json.dumps(key, ensure_ascii=False)} "
        f"in {path}; using the last value."
    )


def _warn_lines(
    loader: ModuleType,
    path: Path,
    duplicate_keys: list[str],
    capsys: pytest.CaptureFixture,
) -> list[str]:
    """Run the real `warn_duplicate_keys` and return its stderr lines.

    Asserts the stdout half of the §4 contract on every call: a duplicate warning is
    never allowed to contaminate machine-readable output.
    """
    loader.warn_duplicate_keys(path, duplicate_keys)
    captured = capsys.readouterr()
    assert captured.out == "", "duplicate warnings must never be written to stdout"
    return captured.err.splitlines()


# --- §5.1 row: no duplicate ------------------------------------------------- #


def test_no_duplicate_parses_unchanged_and_stays_silent(loader, tmp_path, capsys):
    """Row 1: a clean config parses exactly as stdlib would and emits nothing."""
    text = '{"autoVerify": true, "loopRunner": {"bin": "rauf"}}'
    path = _write_json(tmp_path, text)

    value, duplicates = loader.load_json_with_duplicates(path)

    assert value == json.loads(text)  # identical to the pre-feature result
    assert duplicates == []
    assert _warn_lines(loader, path, duplicates, capsys) == []


# --- §5.1 row: same key twice at root --------------------------------------- #


def test_same_key_twice_at_root_keeps_the_last_value_and_warns_once(
    loader, tmp_path, capsys
):
    """Row 2: last-key-wins, one warning naming the key, on stderr only."""
    path = _write_json(tmp_path, '{"autoVerify": false, "autoVerify": true}')

    value, duplicates = loader.load_json_with_duplicates(path)

    assert value == {"autoVerify": True}
    assert duplicates == ["autoVerify"]
    assert _warn_lines(loader, path, duplicates, capsys) == [
        _warning_line("autoVerify", path)
    ]


# --- §5.1 row: same key three times ----------------------------------------- #


def test_same_key_three_times_keeps_the_last_value_and_warns_twice(
    loader, tmp_path, capsys
):
    """Row 3: one line per *repeated occurrence* — evidence is preserved, not deduped."""
    path = _write_json(
        tmp_path, '{"commitPrefix": "a", "commitPrefix": "b", "commitPrefix": "c"}'
    )

    value, duplicates = loader.load_json_with_duplicates(path)

    assert value == {"commitPrefix": "c"}
    assert duplicates == ["commitPrefix", "commitPrefix"]
    assert _warn_lines(loader, path, duplicates, capsys) == [
        _warning_line("commitPrefix", path)
    ] * 2


# --- §5.1 row: nested object ------------------------------------------------ #


def test_duplicate_inside_a_nested_object_is_detected(loader, tmp_path, capsys):
    """Row 4: detection is general JSON-object behaviour, not an `autoVerify` case."""
    path = _write_json(tmp_path, '{"loopRunner": {"bin": "a", "bin": "b"}}')

    value, duplicates = loader.load_json_with_duplicates(path)

    assert value == {"loopRunner": {"bin": "b"}}
    assert duplicates == ["bin"]
    assert _warn_lines(loader, path, duplicates, capsys) == [_warning_line("bin", path)]


# --- §5.1 row: object inside an array --------------------------------------- #


def test_duplicate_inside_an_object_in_an_array_is_detected(loader, tmp_path, capsys):
    """Row 5: `object_pairs_hook` fires for objects nested in arrays too."""
    path = _write_json(tmp_path, '{"workspaces": [{"name": "a", "name": "b"}]}')

    value, duplicates = loader.load_json_with_duplicates(path)

    assert value == {"workspaces": [{"name": "b"}]}
    assert duplicates == ["name"]
    assert _warn_lines(loader, path, duplicates, capsys) == [_warning_line("name", path)]


# --- §5.1 row: same key once in two separate objects ------------------------ #


def test_the_same_key_in_two_separate_objects_is_not_a_duplicate(
    loader, tmp_path, capsys
):
    """Row 6: membership is local to each constructed object — no false positive."""
    path = _write_json(tmp_path, '{"loopRunner": {"bin": "a"}, "other": {"bin": "b"}}')

    value, duplicates = loader.load_json_with_duplicates(path)

    assert value == {"loopRunner": {"bin": "a"}, "other": {"bin": "b"}}
    assert duplicates == []
    assert _warn_lines(loader, path, duplicates, capsys) == []


# --- §5.1 row: nested plus root duplicate, in decoder-hook order ------------ #


def test_nested_and_root_duplicates_report_in_decoder_hook_order(
    loader, tmp_path, capsys
):
    """Row 7: the stdlib completes inner objects first, so `bin` precedes `commitPrefix`.

    Source order is the reverse. The list must be neither sorted nor deduplicated
    (05 §2.1), so this pins the decoder-hook order explicitly.
    """
    path = _write_json(
        tmp_path,
        '{"commitPrefix": "a", "commitPrefix": "b", "loopRunner": {"bin": "x", "bin": "y"}}',
    )

    value, duplicates = loader.load_json_with_duplicates(path)

    assert value == {"commitPrefix": "b", "loopRunner": {"bin": "y"}}
    assert duplicates == ["bin", "commitPrefix"]
    assert _warn_lines(loader, path, duplicates, capsys) == [
        _warning_line("bin", path),
        _warning_line("commitPrefix", path),
    ]


# --- §5.1 row: arbitrary Unicode / control-character key -------------------- #

#: U+0007 BEL, built with `chr` so no raw control byte lives in this file either.
_BEL = chr(7)
#: A key mixing a control character with non-ASCII text. `json.dumps` is what makes it
#: safe to print: the BEL renders as its visible escape sequence while the readable
#: text survives.
_HOSTILE_KEY = f"{_BEL}ключ✓"


def test_unicode_and_control_character_keys_are_rendered_safely(
    loader, tmp_path, capsys
):
    """Row 8: the key is JSON-quoted for display; the raw control byte never escapes."""
    encoded = json.dumps(_HOSTILE_KEY)  # ASCII-escaped source, valid JSON either way
    path = _write_json(tmp_path, f"{{{encoded}: 1, {encoded}: 2}}")

    value, duplicates = loader.load_json_with_duplicates(path)

    assert value == {_HOSTILE_KEY: 2}
    assert duplicates == [_HOSTILE_KEY]
    lines = _warn_lines(loader, path, duplicates, capsys)
    assert lines == [_warning_line(_HOSTILE_KEY, path)]
    assert _BEL not in lines[0], "the raw control character reached the terminal"
    assert "\\u0007" in lines[0], "the control character was not rendered as an escape"
    assert "ключ" in lines[0], "non-ASCII text is shown readably, not escaped"


# --- §5.1 row: scalar and array roots --------------------------------------- #


def test_scalar_root_parses_as_the_stdlib_value_with_no_duplicates(loader, tmp_path):
    """Row 9a: a scalar root is returned untouched — the loader adds no root policy."""
    path = _write_json(tmp_path, "17")

    value, duplicates = loader.load_json_with_duplicates(path)

    assert value == 17
    assert duplicates == []


def test_array_root_still_finds_duplicates_in_its_nested_objects(loader, tmp_path):
    """Row 9b: a non-object root does not disable recursive detection."""
    path = _write_json(tmp_path, '[{"k": 1, "k": 2}, {"k": 3}]')

    value, duplicates = loader.load_json_with_duplicates(path)

    assert value == [{"k": 2}, {"k": 3}]
    assert duplicates == ["k"]


# --- §5.1 row: malformed / unreadable --------------------------------------- #


def test_malformed_input_preserves_json_decode_error(loader, tmp_path):
    """Row 10a: the built-in error is not wrapped — translation stays in the caller."""
    path = _write_json(tmp_path, "{ not json")

    with pytest.raises(json.JSONDecodeError):
        loader.load_json_with_duplicates(path)


def test_missing_input_preserves_os_error(loader, tmp_path):
    """Row 10b: a missing file raises FileNotFoundError, an OSError subclass."""
    with pytest.raises(OSError):
        loader.load_json_with_duplicates(tmp_path / "absent.json")


def test_directory_input_preserves_os_error(loader, tmp_path):
    """Row 10c: a directory in the config's place is IsADirectoryError, also an OSError.

    Kept alongside the chmod row because it is deterministic for every uid, including
    root in a container, where a mode-000 file stays readable.
    """
    directory = tmp_path / "forge.config.json"
    directory.mkdir()

    with pytest.raises(OSError):
        loader.load_json_with_duplicates(directory)


@pytest.mark.skipif(
    hasattr(os, "geteuid") and os.geteuid() == 0,
    reason="mode 000 stays readable as root; the directory row covers OSError there",
)
def test_unreadable_input_preserves_os_error(loader, tmp_path):
    """Row 10d: a mode-000 file raises PermissionError, an OSError subclass."""
    path = _write_json(tmp_path, '{"a": 1}')
    path.chmod(0o000)
    try:
        with pytest.raises(OSError):
            loader.load_json_with_duplicates(path)
    finally:
        path.chmod(0o644)


# --------------------------------------------------------------------------- #
# Negative control (07 §5.1) — prove the matrix can go red
# --------------------------------------------------------------------------- #


def _assert_duplicate_contract(load, path: Path) -> None:
    """The two properties the whole matrix rests on: last-key-wins, no deduplication.

    Extracted so the negative control can feed it a deliberately wrong substitute and
    require an AssertionError. Without that, "the tests pass" would be evidence only
    that the tests exist.
    """
    value, duplicates = load(path)
    assert value == {"k": 3}, "last-key-wins was not preserved"
    assert duplicates == ["k", "k"], "one entry per repeated occurrence was not preserved"


def _reference_hook_loader(path: Path) -> tuple[object, list[str]]:
    """Conforming reference used only to build `_deduplicating_loader`'s defect."""
    duplicate_keys: list[str] = []

    def hook(pairs):
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                duplicate_keys.append(key)
            result[key] = value
        return result

    text = path.read_text(encoding="utf-8")
    return json.loads(text, object_pairs_hook=hook), duplicate_keys


#: The substitutes below are the ONLY object hooks written in test code, and they exist
#: solely to be rejected. Every other row calls the real in-file functions.
def _first_key_wins_loader(path: Path) -> tuple[object, list[str]]:
    """Substitute defect: the FIRST occurrence wins instead of the last."""
    duplicate_keys: list[str] = []

    def hook(pairs):
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                duplicate_keys.append(key)
                continue  # the defect
            result[key] = value
        return result

    text = path.read_text(encoding="utf-8")
    return json.loads(text, object_pairs_hook=hook), duplicate_keys


def _deduplicating_loader(path: Path) -> tuple[object, list[str]]:
    """Substitute defect: repeated occurrences collapse to one reported name."""
    value, duplicates = _reference_hook_loader(path)
    return value, sorted(set(duplicates))  # the defect


def test_the_real_loaders_satisfy_the_shared_duplicate_contract(loader, tmp_path):
    """Both mirrored copies pass the contract the negative controls fail."""
    path = _write_json(tmp_path, '{"k": 1, "k": 2, "k": 3}')

    _assert_duplicate_contract(loader.load_json_with_duplicates, path)


def test_negative_control_first_key_wins_fails_the_contract(tmp_path):
    """Substituting first-key-wins makes the matrix fail — so a pass means something."""
    path = _write_json(tmp_path, '{"k": 1, "k": 2, "k": 3}')

    with pytest.raises(AssertionError, match="last-key-wins"):
        _assert_duplicate_contract(_first_key_wins_loader, path)


def test_negative_control_deduplication_fails_the_contract(tmp_path):
    """Substituting duplicate deduplication makes the matrix fail for the same reason."""
    path = _write_json(tmp_path, '{"k": 1, "k": 2, "k": 3}')

    with pytest.raises(AssertionError, match="repeated occurrence"):
        _assert_duplicate_contract(_deduplicating_loader, path)


# --------------------------------------------------------------------------- #
# Common-path source assertions (07 §5.4, REQ-PERF-01/02)
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("script", sorted(_LOADER_SOURCES), ids=sorted(_LOADER_SOURCES))
def test_the_mirrored_loader_does_one_local_read_and_nothing_else(script):
    """Diagnostics add no subprocess, Git call, network request, or tree traversal."""
    source = mirrored_loader_pair(_LOADER_SOURCES[script])

    for banned in ("subprocess", "urllib", "socket", "requests", "rglob", "glob(", "iterdir"):
        assert banned not in source, f"{script}: mirrored loader reaches for {banned!r}"
    assert source.count("read_text(") == 1, f"{script}: more than one file read"


def test_load_config_does_not_add_a_second_config_read(tmp_path, monkeypatch):
    """Duplicate detection replaces the existing read; it never adds one (REQ-PERF-02)."""
    session = _load_script_module("_dupcfg_readcount", SCRIPTS / "forge-session.py")
    path = _write_json(tmp_path, '{"autoVerify": false, "autoVerify": true}')

    calls: list[Path] = []
    real = session.load_json_with_duplicates

    def counting(target: Path):
        calls.append(target)
        return real(target)

    monkeypatch.setattr(session, "load_json_with_duplicates", counting)

    assert session._load_config(path) == {"autoVerify": True}
    assert calls == [path]


# --------------------------------------------------------------------------- #
# CLI matrix (05 §4 / §8.1, 07 §5.2) — real subprocesses, streams kept apart
# --------------------------------------------------------------------------- #

#: Duplicates at the root AND inside both nested objects the config schema owns.
#: `loopRunner` and `autoVerifyStages` are here on purpose: REQ-CONFIG-04 is the claim
#: that detection is general JSON-object behaviour, not an `autoVerify` special case.
_DUPLICATE_CONFIG = textwrap.dedent(
    """\
    {
      "specsDir": "./specs",
      "autoVerify": false,
      "autoVerify": true,
      "loopRunner": {"bin": "first", "bin": "last"},
      "autoVerifyStages": {"forge-1-prd": false, "forge-1-prd": true}
    }
    """
)

#: Decoder-hook order for `_DUPLICATE_CONFIG`: the stdlib finishes each nested object
#: before the root, so the two nested keys precede the root key even though the root
#: duplicate appears first in the source text.
_DUPLICATE_CONFIG_KEYS = ["bin", "forge-1-prd", "autoVerify"]


def _session_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    """Run the real forge-session CLI in ``cwd`` with the two streams captured apart."""
    return subprocess.run(
        [sys.executable, FS, *args], cwd=str(cwd), capture_output=True, text=True
    )


def _warned_keys(stderr: str) -> list[str]:
    """The duplicate key names named on stderr, in emission order."""
    return [
        line.split('"')[1]
        for line in stderr.splitlines()
        if line.startswith("Warning: duplicate JSON key ")
    ]


def test_effective_config_json_warns_on_stderr_and_keeps_stdout_parseable(tmp_path):
    """`--json` stdout parses with json.loads while every warning stays on stderr.

    This is the contract that lets a caller pipe stdout without filtering warning text
    (05 §4). Config bytes are captured before and after: a warning-only command never
    writes to the file it is warning about.
    """
    config = _write_json(tmp_path, _DUPLICATE_CONFIG)
    before = config.read_bytes()

    result = _session_cli(
        "effective-config", "--config", str(config), "--json", cwd=tmp_path
    )

    assert result.returncode == 0, result.stderr
    resolved = json.loads(result.stdout)  # independently parseable, unfiltered
    assert resolved["bin"] == "last", "the last nested value must be the effective one"
    assert "Warning:" not in result.stdout
    assert _warned_keys(result.stderr) == _DUPLICATE_CONFIG_KEYS
    assert config.read_bytes() == before


def test_nested_loop_runner_and_auto_verify_stages_duplicates_are_both_detected(
    tmp_path,
):
    """REQ-CONFIG-04: `loopRunner` and `autoVerifyStages` warn like any other object."""
    config = _write_json(tmp_path, _DUPLICATE_CONFIG)

    result = _session_cli(
        "effective-config", "--config", str(config), "--json", cwd=tmp_path
    )

    assert result.returncode == 0, result.stderr
    warned = _warned_keys(result.stderr)
    assert "bin" in warned, "a nested loopRunner duplicate went unreported"
    assert "forge-1-prd" in warned, "a nested autoVerifyStages duplicate went unreported"
    for key in _DUPLICATE_CONFIG_KEYS:
        assert _warning_line(key, config) in result.stderr


def test_a_second_load_config_consumer_warns_identically(tmp_path):
    """`rank-features` shares the one read path, so it warns without its own hook.

    Proves the adoption point is `_load_config` itself (05 §3.1) rather than a
    per-command opt-in that the next consumer could forget.
    """
    (tmp_path / "specs").mkdir()
    config = _write_json(tmp_path, _DUPLICATE_CONFIG)
    before = config.read_bytes()

    result = _session_cli(
        "rank-features",
        "--specs-dir", str(tmp_path / "specs"),
        "--config", str(config),
        "--json",
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    json.loads(result.stdout)
    assert _warned_keys(result.stderr) == _DUPLICATE_CONFIG_KEYS
    assert "Warning:" not in result.stdout
    assert config.read_bytes() == before


def test_a_config_without_duplicates_adds_no_output(tmp_path):
    """The no-duplicate path is byte-for-byte what it was before the feature."""
    config = _write_json(
        tmp_path, '{"specsDir": "./specs", "loopRunner": {"bin": "rauf"}}'
    )
    before = config.read_bytes()

    result = _session_cli(
        "effective-config", "--config", str(config), "--json", cwd=tmp_path
    )

    assert result.returncode == 0, result.stderr
    assert "Warning:" not in result.stderr
    assert json.loads(result.stdout)["bin"] == "rauf"
    assert config.read_bytes() == before


def test_duplicate_warnings_never_dump_the_config(tmp_path):
    """A warning names the key and the path — it never reserializes the whole file."""
    config = _write_json(tmp_path, _DUPLICATE_CONFIG)

    result = _session_cli(
        "effective-config", "--config", str(config), "--json", cwd=tmp_path
    )

    assert "specsDir" not in result.stderr, "the warning leaked unrelated config content"
    assert result.stderr.count("Warning: duplicate JSON key") == len(
        _DUPLICATE_CONFIG_KEYS
    )


# --- §5.3: the deliberate stderr-unwritable split (session half) ------------- #

#: Runs a real CLI whose FIRST stderr write raises OSError.
#:
#: The first write is the duplicate warning, so this reproduces "the advisory could not
#: be written" without also breaking the interpreter: an fd 2 that is unwritable for the
#: whole process makes CPython exit 120 while flushing at shutdown, which would mask the
#: exit code under test instead of measuring it. Later writes succeed, so an error path
#: that reports after the failed advisory (forge-bootstrap's, in
#: tests/test_forge_bootstrap.py) is still observable.
_FAIL_FIRST_STDERR_DRIVER = textwrap.dedent(
    """\
    import runpy
    import sys


    class _FailFirstWrite:
        def __init__(self, real):
            self._real = real
            self._failed = False

        def write(self, text):
            if not self._failed:
                self._failed = True
                raise OSError(5, "unwritable stderr")
            return self._real.write(text)

        def flush(self):
            return self._real.flush()

        def isatty(self):
            return False


    sys.stderr = _FailFirstWrite(sys.stderr)
    script = sys.argv[1]
    sys.argv = sys.argv[1:]
    runpy.run_path(script, run_name="__main__")
    """
)


def run_with_failing_stderr(
    script: str, *args: str, cwd: Path
) -> subprocess.CompletedProcess:
    """Run ``script`` as a real CLI whose first stderr write raises OSError.

    Shared with tests/test_forge_bootstrap.py, which pins the other half of the
    deliberate 05 §3.3 asymmetry.
    """
    return subprocess.run(
        [sys.executable, "-c", _FAIL_FIRST_STDERR_DRIVER, script, *args],
        cwd=str(cwd),
        capture_output=True,
        text=True,
    )


def test_unwritable_stderr_drops_the_warning_and_leaves_the_session_exit_unchanged(
    tmp_path,
):
    """05 §3.1/§3.3: `_load_config` swallows the OSError so the read path stays total.

    Losing an advisory is strictly better than losing the command — which is what
    `rank-features --json | head` would otherwise cost. The bootstrap half of this
    asymmetry (still exit 2) is pinned in tests/test_forge_bootstrap.py.
    """
    config = _write_json(
        tmp_path, '{"specsDir": "./specs", "autoVerify": false, "autoVerify": true}'
    )

    result = run_with_failing_stderr(
        FS, "effective-config", "--config", str(config), "--json", cwd=tmp_path
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["name"] == "rauf"
    assert "Warning:" not in result.stderr, "the dropped warning reappeared"
    assert "Traceback" not in result.stderr


def test_unwritable_stderr_in_process_still_returns_the_parsed_dict(
    tmp_path, monkeypatch
):
    """The same guarantee at the function boundary, with every stderr write raising."""
    session = _load_script_module("_dupcfg_stderr", SCRIPTS / "forge-session.py")
    config = _write_json(tmp_path, '{"autoVerify": false, "autoVerify": true}')

    class _AlwaysFails:
        """A stderr that is unwritable for the whole call, not just the first write."""

        def write(self, text: str) -> int:
            raise OSError(5, "unwritable stderr")

        def flush(self) -> None:
            raise OSError(5, "unwritable stderr")

    monkeypatch.setattr(sys, "stderr", _AlwaysFails())

    assert session._load_config(config) == {"autoVerify": True}
