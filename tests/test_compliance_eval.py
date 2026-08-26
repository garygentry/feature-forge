"""Offline tests for the stage-drive compliance eval (`eval/run-compliance-eval.py`).

The harness itself needs a live model, but everything that decides whether a run counts
as compliant is pure: the fixture builder, the R2 transform, the transcript parser, and
the two scorers. Those are what this suite pins — a scorer that silently passes a
non-compliant output would make the whole Phase 0 baseline meaningless.

No API key, no `claude` CLI, no network.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EVAL_SCRIPT = REPO_ROOT / "eval" / "run-compliance-eval.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("_forge_compliance_eval", EVAL_SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec: @dataclass resolves annotations via sys.modules[__module__].
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


ce = _load_module()


# --------------------------------------------------------------------------- #
# Prelude sync — the guard that keeps probe 2 honest
# --------------------------------------------------------------------------- #


def test_prelude_matches_the_byte_pinned_source() -> None:
    ce._assert_prelude_in_sync()


def test_sentinel_matches_the_helper() -> None:
    source = (REPO_ROOT / "scripts" / "forge-session.py").read_text(encoding="utf-8")
    assert f'NEXT_STEPS_SENTINEL: Final = "{ce.SENTINEL}"' in source


# --------------------------------------------------------------------------- #
# Fixture + ground truth
# --------------------------------------------------------------------------- #


@pytest.fixture()
def stage_fixture(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    ce.build_stage_exit_fixture(root)
    return root


def _build(tmp_path: Path, variant: str) -> Path:
    root = tmp_path / variant
    root.mkdir()
    ce.build_stage_exit_fixture(root, variant)
    return root


@pytest.mark.parametrize("variant", ["cold", "warm"])
def test_fixture_drives_the_no_gate_path(tmp_path: Path, variant: str) -> None:
    """Both variants must isolate the last-output invariant, not the verify gate."""
    directives = ce.expected_stage_exit(_build(tmp_path, variant))["directives"]
    assert directives["verifyGate"] == "none"
    assert directives["runInStageVerify"] is False
    assert directives["verifyState"] in ("fresh", "skipped")
    assert directives["cleanTree"] is True
    assert directives["nextCommand"] == f"/feature-forge:forge-2-tech {ce.FIXTURE_FEATURE}"


def test_warm_fixture_presents_an_unfinished_stage(tmp_path: Path) -> None:
    """`warm` asks the model to do the closing work, so the stage must be in-progress.

    A `complete` stage makes the ask self-contradictory, and the Stage-Completion
    Re-check (`references/shared-conventions.md`, rule 2) correctly refuses to re-fire a
    finished exit. The first two baseline sweeps scored that refusal as a compliance
    failure; it was the fixture that was wrong.
    """
    root = _build(tmp_path, "warm")
    state = json.loads((root / "specs" / ce.FIXTURE_FEATURE / ".pipeline-state.json").read_text())
    assert state["stages"][ce.FIXTURE_STAGE]["status"] == "in-progress"
    assert "completedAt" not in state["stages"][ce.FIXTURE_STAGE]
    assert state["currentStage"] == ce.FIXTURE_STAGE


def test_cold_fixture_presents_a_finished_stage(tmp_path: Path) -> None:
    root = _build(tmp_path, "cold")
    state = json.loads((root / "specs" / ce.FIXTURE_FEATURE / ".pipeline-state.json").read_text())
    assert state["stages"][ce.FIXTURE_STAGE]["status"] == "complete"


def test_expected_block_ends_with_the_sentinel(stage_fixture: Path) -> None:
    payload = ce.expected_stage_exit(stage_fixture)
    assert payload["nextSteps"].rstrip().endswith(ce.SENTINEL)


@pytest.mark.parametrize("variant", ["cold", "warm"])
def test_fixture_state_is_schema_valid(tmp_path: Path, variant: str) -> None:
    """A defective fixture measures tolerance for a broken artifact, not exit compliance.

    The first baseline sweep learned this the hard way: a state file missing the schema's
    required top-level keys made a careful model stop and ask for a repair instead of
    closing the stage, which scored as a compliance failure it was not.
    """
    root = _build(tmp_path, variant)
    schema = json.loads((REPO_ROOT / "references" / "pipeline-state-schema.json").read_text())
    state = json.loads((root / "specs" / ce.FIXTURE_FEATURE / ".pipeline-state.json").read_text())
    for key in schema["required"]:
        assert key in state, f"fixture state is missing required key {key!r}"
    stage_entry = state["stages"][ce.FIXTURE_STAGE]
    for key in schema["definitions"]["stageEntry"]["required"]:
        assert key in stage_entry
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(state, schema)


def test_prompt_names_a_section_that_exists() -> None:
    """Both variants must point at a real heading; a wrong one sends the model hunting."""
    skill = (REPO_ROOT / "skills" / ce.FIXTURE_STAGE / "SKILL.md").read_text(encoding="utf-8")
    assert f"## {ce.FIXTURE_CLOSING_SECTION}" in skill
    for variant in ("cold", "warm"):
        assert ce.FIXTURE_CLOSING_SECTION in ce.stage_exit_prompt(variant)


# --------------------------------------------------------------------------- #
# Probe 1 scorer
# --------------------------------------------------------------------------- #


def _transcript(final_text: str, commands: list[str] | None = None) -> dict:
    return {
        "ok": True,
        "final_text": final_text,
        "bash_commands": commands
        if commands is not None
        else ['python3 "$R/scripts/forge-session.py" stage-exit --feature widget-search'],
    }


def test_compliant_output_scores_all_criteria(stage_fixture: Path) -> None:
    expected = ce.expected_stage_exit(stage_fixture)
    text = "Verification is fresh on record.\n\n" + expected["nextSteps"]
    criteria = ce.score_stage_exit(_transcript(text), expected)
    assert all(criteria.values()), criteria


def test_trailing_text_after_the_sentinel_fails(stage_fixture: Path) -> None:
    """The exact Opus 5 symptom §1.2 predicts: a summary lands after the sentinel."""
    expected = ce.expected_stage_exit(stage_fixture)
    text = expected["nextSteps"] + "\n\nLet me know if you'd like me to continue!"
    criteria = ce.score_stage_exit(_transcript(text), expected)
    assert criteria["sentinel_present"] is True
    assert criteria["nothing_after_sentinel"] is False


def test_summarised_block_fails_verbatim_and_fence(stage_fixture: Path) -> None:
    """A rewritten block keeps the sentinel but loses the copyable command."""
    expected = ce.expected_stage_exit(stage_fixture)
    text = (
        "**Next steps**\n"
        "- Clear the session, then run /feature-forge:forge-2-tech widget-search\n"
        f"{ce.SENTINEL}"
    )
    criteria = ce.score_stage_exit(_transcript(text), expected)
    assert criteria["nothing_after_sentinel"] is True
    assert criteria["next_command_fenced"] is False
    assert criteria["block_verbatim"] is False


def test_missing_sentinel_fails(stage_fixture: Path) -> None:
    expected = ce.expected_stage_exit(stage_fixture)
    criteria = ce.score_stage_exit(_transcript("All done — PRD complete."), expected)
    assert criteria["sentinel_present"] is False
    assert criteria["nothing_after_sentinel"] is False


def test_hand_authored_block_fails_the_script_check(stage_fixture: Path) -> None:
    """A perfect block that never ran the script is still a contract miss."""
    expected = ce.expected_stage_exit(stage_fixture)
    criteria = ce.score_stage_exit(_transcript(expected["nextSteps"], commands=[]), expected)
    assert criteria["block_verbatim"] is True
    assert criteria["ran_stage_exit"] is False


def test_unrelated_bash_does_not_count_as_running_stage_exit(stage_fixture: Path) -> None:
    expected = ce.expected_stage_exit(stage_fixture)
    criteria = ce.score_stage_exit(
        _transcript(expected["nextSteps"], commands=["git status --porcelain"]), expected
    )
    assert criteria["ran_stage_exit"] is False


def test_fence_detection_requires_a_real_fence() -> None:
    command = "/feature-forge:forge-2-tech widget-search"
    assert ce._in_fenced_block(f"text\n```\n{command}\n```\n", command) is True
    assert ce._in_fenced_block(f"run `{command}` next", command) is False


# --------------------------------------------------------------------------- #
# R2 transform + probe 2 scorer
# --------------------------------------------------------------------------- #


@pytest.fixture()
def transformed() -> tuple[str, int]:
    source = (REPO_ROOT / "skills" / "forge" / "SKILL.md").read_text(encoding="utf-8")
    return ce.apply_r2(source)


def test_r2_keeps_exactly_one_verbatim_prelude(transformed: tuple[str, int]) -> None:
    body, compacted = transformed
    assert body.count(ce.BOOTSTRAP_PRELUDE) == 1
    assert compacted >= 1


def test_r2_compact_form_is_sentinel_free(transformed: tuple[str, int]) -> None:
    """§1.4: a compact site must never look like a drifted prelude in isolation."""
    body, _ = transformed
    head, _, tail = body.partition(ce.BOOTSTRAP_PRELUDE)
    assert ce.PRELUDE_SENTINEL not in head
    assert ce.PRELUDE_SENTINEL not in tail


def test_r2_marks_one_call_site(transformed: tuple[str, int]) -> None:
    body, _ = transformed
    assert body.count(ce.R2_CALL_SITE_MARKER) == 1
    marked = body.split(ce.R2_CALL_SITE_MARKER, 1)[1]
    assert marked.lstrip().startswith(ce.COMPACT_PRELUDE_LEAD)


def test_r2_marks_a_runnable_call_site(transformed: tuple[str, int]) -> None:
    """The marked command must have no unresolved `{placeholder}`.

    A command that cannot succeed turns the run into a discussion of why it failed
    instead of a measurement of the resolver the model reconstructed.
    """
    body, _ = transformed
    command = body.split(ce.R2_CALL_SITE_MARKER, 1)[1].splitlines()[2]
    assert 'python3 "$R/scripts/' in command
    assert "{" not in command, command


def test_r2_preserves_each_call_sites_command(transformed: tuple[str, int]) -> None:
    """The compact form replaces the resolver, never the command it was resolving for."""
    body, compacted = transformed
    assert body.count(ce.COMPACT_PRELUDE_LEAD) == compacted
    for chunk in body.split(ce.COMPACT_PRELUDE_LEAD)[1:]:
        assert 'python3 "$R/scripts/' in chunk.splitlines()[1]


def test_r2_refuses_a_body_with_one_prelude() -> None:
    with pytest.raises(RuntimeError):
        ce.apply_r2(f"intro\n```bash\n{ce.BOOTSTRAP_PRELUDE}\npython3 x.py\n```\n")


def test_prelude_fixture_resolves_the_plugin_root(tmp_path: Path) -> None:
    """A byte-identical resolver must actually succeed inside the fixture."""
    root = tmp_path / "proj"
    root.mkdir()
    ce.build_prelude_fixture(root)
    proc = subprocess.run(
        ["bash", "-c", f'{ce.BOOTSTRAP_PRELUDE}\necho "$R"'],
        cwd=str(root),
        capture_output=True,
        text=True,
        env={"HOME": str(tmp_path / "nohome"), "PATH": "/usr/bin:/bin"},
    )
    assert proc.returncode == 0, proc.stderr
    assert Path(proc.stdout.strip()).resolve() == REPO_ROOT


def test_prelude_scorer_accepts_a_byte_identical_command() -> None:
    command = f'{ce.BOOTSTRAP_PRELUDE}\npython3 "$R/scripts/forge-session.py" doctor --json'
    criteria = ce.score_prelude({"bash_commands": [command]})
    assert all(criteria.values()), criteria


def test_prelude_scorer_flags_a_drifted_but_working_resolver() -> None:
    """Reordered search paths still resolve here, but are not byte-identical."""
    drifted = ce.BOOTSTRAP_PRELUDE.replace(
        '"${FEATURE_FORGE_ROOT:-}" "${CLAUDE_PLUGIN_ROOT:-}"',
        '"${CLAUDE_PLUGIN_ROOT:-}" "${FEATURE_FORGE_ROOT:-}"',
    )
    criteria = ce.score_prelude({"bash_commands": [drifted]})
    assert criteria["byte_identical"] is False
    assert criteria["functionally_equivalent"] is True


def test_prelude_scorer_flags_a_truncated_resolver() -> None:
    truncated = (
        'R="$(bash -c \'for d in "${CLAUDE_PLUGIN_ROOT:-}" '
        '"$HOME"/.claude/plugins/*/feature-forge; do '
        '[ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done\')"'
    )
    criteria = ce.score_prelude({"bash_commands": [truncated]})
    assert criteria["attempted_resolver"] is True
    assert criteria["byte_identical"] is False
    assert criteria["functionally_equivalent"] is False


def test_prelude_scorer_reports_no_attempt() -> None:
    criteria = ce.score_prelude({"bash_commands": ["ls -la"]})
    assert criteria["attempted_resolver"] is False
    assert criteria["byte_identical"] is False


def test_prelude_scorer_ignores_reconnaissance_before_the_real_call() -> None:
    """Scoring the first `forge-root.sh` mention penalises looking before leaping.

    Observed on Opus 5 in the first baseline sweep: it inspects the candidate paths and
    dry-runs the search loop, then executes a byte-identical resolver. Scoring the probe
    commands reported 20% byte-identical for a model that was in fact 100%.
    """
    recon = [
        "ls -la ./.agents/skills/feature-forge/scripts/",
        (
            'bash -c \'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.agents/skills/feature-forge; '
            'do [ -x "$d/scripts/forge-root.sh" ] && echo "CANDIDATE: $d"; done\''
        ),
    ]
    executed = f'{ce.BOOTSTRAP_PRELUDE}\npython3 "$R/scripts/forge-session.py" context-usage --json'
    criteria = ce.score_prelude({"bash_commands": [*recon, executed]})
    assert criteria["attempted_resolver"] is True
    assert criteria["byte_identical"] is True
    assert criteria["functionally_equivalent"] is True


#: The four prelude criteria, spelled out here rather than imported. Comparing the module
#: constant against itself would be vacuous; this is the second, independent copy that
#: makes a silently added or dropped criterion fail.
SPEC_PRELUDE_CRITERIA = (
    "attempted_resolver",
    "byte_identical",
    "resolver_line_identical",
    "functionally_equivalent",
)


def test_the_prelude_scorer_returns_exactly_the_four_specified_criteria() -> None:
    """REQ-COV-03: pin probe 2's criterion key set the way probe 3's is pinned.

    Every key ANDs into the run's compliance flag, so dropping one silently
    widens what counts as compliant. Both sides are asserted: the scorer's live
    output and the module constant, each against this file's own copy.
    """
    command = f'{ce.BOOTSTRAP_PRELUDE}\npython3 "$R/scripts/forge-session.py" doctor --json'
    criteria = ce.score_prelude({"bash_commands": [command]})

    assert tuple(criteria) == SPEC_PRELUDE_CRITERIA
    assert ce.PRELUDE_CRITERIA == SPEC_PRELUDE_CRITERIA


def test_executing_command_falls_back_to_a_bare_resolver() -> None:
    bare = f'{ce.BOOTSTRAP_PRELUDE}\necho "$R"'
    assert ce.executing_command(["ls", bare]) == bare
    assert ce.executing_command(["ls -la"]) == ""


# --------------------------------------------------------------------------- #
# Transcript parsing + advisory exit
# --------------------------------------------------------------------------- #


def test_parse_transcript_extracts_bash_and_final_text() -> None:
    stream = "\n".join(
        json.dumps(event)
        for event in (
            {"type": "system", "subtype": "init"},
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "working"},
                        {"type": "tool_use", "name": "Bash", "input": {"command": "echo hi"}},
                    ]
                },
            },
            {"type": "result", "is_error": False, "result": "done", "total_cost_usd": 0.4,
             "num_turns": 3, "duration_ms": 1200},
        )
    )
    parsed = ce.parse_transcript(stream)
    assert parsed["ok"] is True
    assert parsed["final_text"] == "done"
    assert parsed["bash_commands"] == ["echo hi"]
    assert parsed["cost_usd"] == 0.4


def test_parse_transcript_tolerates_noise_and_missing_result() -> None:
    parsed = ce.parse_transcript('Warning: not json\n{"type": "system"}\n')
    assert parsed["ok"] is False
    assert "no result event" in parsed["note"]


def test_parse_transcript_reports_an_error_result() -> None:
    stream = json.dumps({"type": "result", "is_error": True, "result": "boom"})
    parsed = ce.parse_transcript(stream)
    assert parsed["ok"] is False


def test_exits_zero_and_says_skipped_without_a_driver(monkeypatch, capsys) -> None:
    """Advisory, exactly like run-eval.py: no driver is not a failure."""
    monkeypatch.setattr(ce, "driver_path", lambda: None)
    assert ce.main(["--json"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["skipped"] is True
    assert report["skip_reason"]


def test_cli_help_runs_standalone() -> None:
    proc = subprocess.run(
        [sys.executable, str(EVAL_SCRIPT), "--help"], capture_output=True, text=True
    )
    assert proc.returncode == 0
    assert "--probe" in proc.stdout


# --------------------------------------------------------------------------- #
# Command evidence — requests paired with real results (06 §4.1)
# --------------------------------------------------------------------------- #
#
# Every stream below mirrors the shape a live `claude --output-format stream-json` run
# actually emits: `tool_use` blocks on an `assistant` event carrying an `id`, and
# `tool_result` blocks on a `user` event carrying `tool_use_id` / `is_error` / `content`,
# with a failed Bash result rendering `Exit code N` as its first line.


def _text(value: str) -> dict:
    return {"type": "text", "text": value}


def _bash(command: str, tool_id: str | None = None) -> dict:
    block: dict = {"type": "tool_use", "name": "Bash", "input": {"command": command}}
    if tool_id is not None:
        block["id"] = tool_id
    return block


def _assistant(*blocks: dict) -> dict:
    return {"type": "assistant", "message": {"content": list(blocks)}}


def _tool_result(tool_id: str, content: object = "", is_error: bool = False) -> dict:
    return {
        "type": "user",
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": tool_id,
                    "content": content,
                    "is_error": is_error,
                }
            ]
        },
    }


def _final(text: str = "done", **extra: object) -> dict:
    return {"type": "result", "is_error": False, "result": text, **extra}


def _stream(*events: object) -> str:
    return "\n".join(json.dumps(event) for event in events)


def _ok(command: str, tool_id: str, output: str = "") -> list[dict]:
    """One request plus its successful result — the ordinary two-event pair."""
    return [_assistant(_bash(command, tool_id)), _tool_result(tool_id, output)]


EXIT_1 = 'python3 "$R/scripts/forge-session.py" stage-exit --stage forge-verify --owner nested'
EXIT_2 = 'python3 "$R/scripts/forge-session.py" stage-exit --stage forge-fix --owner direct'


def test_bash_commands_stay_unchanged_for_the_linear_and_r2_scorers() -> None:
    """The additive fields must not disturb what the existing scorers already read."""
    stream = _stream(
        _assistant(_text("working"), _bash("git status", "t1")),
        _tool_result("t1", "clean"),
        _assistant(_bash(EXIT_1, "t2")),
        _tool_result("t2", "ok"),
        _final("done"),
    )
    parsed = ce.parse_transcript(stream)
    assert parsed["bash_commands"] == ["git status", EXIT_1]
    assert parsed["final_text"] == "done"
    # The linear scorer reads bash_commands only; it must keep working untouched.
    assert ce.score_stage_exit(parsed, {"directives": {}, "nextSteps": ""})["ran_stage_exit"]


def test_requests_and_results_are_joined_by_id_not_by_position() -> None:
    """Results arrive REVERSED; a positional join would swap the two verdicts."""
    stream = _stream(
        _assistant(_bash("first", "a"), _bash("second", "b")),
        _tool_result("b", "Exit code 4\nboom", is_error=True),
        _tool_result("a", "fine"),
        _final(),
    )
    evidence = ce.parse_transcript(stream)["command_evidence"]
    assert [e["command"] for e in evidence] == ["first", "second"]
    assert [e["requestIndex"] for e in evidence] == [0, 1]
    assert evidence[0]["exitCode"] == 0 and evidence[0]["isError"] is False
    assert evidence[1]["exitCode"] == 4 and evidence[1]["isError"] is True


def test_request_order_survives_a_delayed_result() -> None:
    """A result that lands after two further requests still pairs with its own request."""
    stream = _stream(
        _assistant(_bash("slow", "a")),
        _assistant(_bash("quick", "b")),
        _tool_result("b", "done"),
        _assistant(_bash("later", "c")),
        _tool_result("c", "done"),
        _tool_result("a", "eventually"),
        _final(),
    )
    evidence = ce.parse_transcript(stream)["command_evidence"]
    assert [e["command"] for e in evidence] == ["slow", "quick", "later"]
    assert evidence[0]["resultTail"] == "eventually"
    assert all(e["resultSeen"] and e["exitCode"] == 0 for e in evidence)


def test_an_unpaired_request_never_scores_as_executed() -> None:
    stream = _stream(_assistant(_bash("never finished", "a")), _final())
    (entry,) = ce.parse_transcript(stream)["command_evidence"]
    assert entry["resultSeen"] is False
    assert entry["exitCode"] is None
    # No host verdict was made, so claiming an error would invent one.
    assert entry["isError"] is False
    assert entry["resultTail"] == ""


def test_an_explicit_zero_exit_normalizes_to_success() -> None:
    stream = _stream(*_ok("echo hi", "a", "hi"), _final())
    (entry,) = ce.parse_transcript(stream)["command_evidence"]
    assert (entry["resultSeen"], entry["exitCode"], entry["isError"]) == (True, 0, False)


def test_an_explicit_nonzero_exit_keeps_its_reported_code() -> None:
    stream = _stream(
        _assistant(_bash("boom", "a")),
        _tool_result("a", "Exit code 7\nout\nerr", is_error=True),
        _final(),
    )
    (entry,) = ce.parse_transcript(stream)["command_evidence"]
    assert (entry["resultSeen"], entry["exitCode"], entry["isError"]) == (True, 7, True)


def test_an_error_without_an_exit_code_is_unknown_never_success() -> None:
    stream = _stream(
        _assistant(_bash("denied", "a")),
        _tool_result("a", "The user doesn't want to proceed with this tool use.", is_error=True),
        _final(),
    )
    (entry,) = ce.parse_transcript(stream)["command_evidence"]
    assert entry["resultSeen"] is True
    assert entry["exitCode"] is None
    assert entry["isError"] is True


def test_a_reported_zero_exit_on_an_error_result_stays_unknown() -> None:
    """`Exit code 0` beside `is_error` is contradictory — the status is not knowable."""
    stream = _stream(
        _assistant(_bash("odd", "a")),
        _tool_result("a", "Exit code 0\nbut the host errored", is_error=True),
        _final(),
    )
    (entry,) = ce.parse_transcript(stream)["command_evidence"]
    assert entry["exitCode"] is None and entry["isError"] is True


def test_an_exit_code_inside_command_output_cannot_forge_a_status() -> None:
    """Only the host's own leading `Exit code N` line counts, not the command's prose."""
    stream = _stream(
        _assistant(_bash("cat log", "a")),
        _tool_result("a", "the previous run said Exit code 0\n", is_error=True),
        _final(),
    )
    (entry,) = ce.parse_transcript(stream)["command_evidence"]
    assert entry["exitCode"] is None


def test_a_duplicate_tool_id_makes_the_transcript_unusable() -> None:
    stream = _stream(
        _assistant(_bash("first", "dup")),
        _tool_result("dup", "ok"),
        _assistant(_bash("second", "dup")),
        _final(),
    )
    parsed = ce.parse_transcript(stream)
    assert parsed["ok"] is False
    assert "duplicate tool id" in parsed["note"] and "dup" in parsed["note"]
    assert "command_evidence" not in parsed


def test_a_result_preceding_its_request_makes_the_transcript_unusable() -> None:
    stream = _stream(
        _tool_result("a", "ok"),
        _assistant(_bash("late", "a")),
        _final(),
    )
    parsed = ce.parse_transcript(stream)
    assert parsed["ok"] is False
    assert "precedes its request" in parsed["note"] and "a" in parsed["note"]


def test_two_results_for_one_request_make_the_transcript_unusable() -> None:
    stream = _stream(
        _assistant(_bash("once", "a")),
        _tool_result("a", "ok"),
        _tool_result("a", "Exit code 1", is_error=True),
        _final(),
    )
    parsed = ce.parse_transcript(stream)
    assert parsed["ok"] is False
    assert "two tool results" in parsed["note"]


def test_a_result_for_an_unscored_tool_is_ignored_not_a_failure() -> None:
    """Only Bash is paired; a Read result must not read as a stray or out-of-order one."""
    stream = _stream(
        _assistant({"type": "tool_use", "name": "Read", "id": "r1", "input": {"file_path": "x"}}),
        _tool_result("r1", "file body"),
        *_ok("echo hi", "b1", "hi"),
        _final(),
    )
    parsed = ce.parse_transcript(stream)
    assert parsed["ok"] is True
    assert [e["command"] for e in parsed["command_evidence"]] == ["echo hi"]


def test_a_bash_request_without_an_id_can_never_pair() -> None:
    """It stays a request: countable in bash_commands, never evidence of execution."""
    stream = _stream(_assistant(_bash("no id here")), _final())
    parsed = ce.parse_transcript(stream)
    assert parsed["bash_commands"] == ["no id here"]
    (entry,) = parsed["command_evidence"]
    assert entry["toolUseId"] == ""
    assert entry["resultSeen"] is False and entry["exitCode"] is None


def test_malformed_stream_noise_never_breaks_the_pairing() -> None:
    stream = "\n".join(
        [
            "Warning: not json",
            json.dumps({"type": "assistant", "message": {"content": "not a list"}}),
            json.dumps({"type": "assistant", "message": None}),
            json.dumps({"type": "assistant", "message": {"content": ["not a dict", None]}}),
            json.dumps(_assistant(_bash("real", "a"))),
            json.dumps({"type": "user", "message": {"content": [{"type": "tool_result"}]}}),
            json.dumps(_tool_result("a", "ok")),
            "",
            json.dumps(_final()),
        ]
    )
    parsed = ce.parse_transcript(stream)
    assert parsed["ok"] is True
    assert [e["command"] for e in parsed["command_evidence"]] == ["real"]
    assert parsed["command_evidence"][0]["exitCode"] == 0


def test_a_missing_final_result_still_reports_the_requests_it_saw() -> None:
    parsed = ce.parse_transcript(_stream(*_ok("echo hi", "a")))
    assert parsed["ok"] is False
    assert "no result event" in parsed["note"]
    assert parsed["bash_commands"] == ["echo hi"]


def test_result_tail_is_capped_at_five_hundred_characters() -> None:
    stream = _stream(*_ok("noisy", "a", "x" * 900 + "TAIL"), _final())
    (entry,) = ce.parse_transcript(stream)["command_evidence"]
    assert len(entry["resultTail"]) == ce.RESULT_TAIL_LIMIT == 500
    assert entry["resultTail"].endswith("TAIL")


def test_a_block_list_result_payload_is_flattened() -> None:
    stream = _stream(
        _assistant(_bash("structured", "a")),
        _tool_result("a", [{"type": "text", "text": "one"}, {"type": "image"}, "junk"]),
        _final(),
    )
    (entry,) = ce.parse_transcript(stream)["command_evidence"]
    assert entry["resultTail"] == "one" and entry["exitCode"] == 0


def test_assistant_texts_carry_every_block_in_event_order() -> None:
    """Sentinel counting spans the full path, not merely the final answer."""
    stream = _stream(
        _assistant(_text("one"), _bash("echo hi", "a")),
        _tool_result("a", "hi"),
        _assistant(_text("two"), _text("three")),
        _final("four"),
    )
    assert ce.parse_transcript(stream)["assistant_texts"] == ["one", "two", "three", "four"]


def test_the_final_result_is_appended_only_when_it_is_not_already_present() -> None:
    """The host repeats the last message on the result event; counting it twice would
    double every sentinel and turn one compliant block into a duplicate."""
    stream = _stream(_assistant(_text("the only answer")), _final("the only answer"))
    assert ce.parse_transcript(stream)["assistant_texts"] == ["the only answer"]


# --------------------------------------------------------------------------- #
# Ordered command-result evidence (06 §4.2)
# --------------------------------------------------------------------------- #


def _expect(*token_groups: list[str]) -> list[dict]:
    return [{"stage": "terminal-exit", "contains": tokens} for tokens in token_groups]


def _two_exit_stream(*, second_result: dict | None = None, recon: bool = True) -> str:
    events: list[object] = [*_ok(EXIT_1, "e1", "NEXT STEPS")]
    if recon:
        events += _ok("git status --porcelain", "r1", "")
        events += _ok("cat specs/widget/PRD.md", "r2", "# PRD")
    events.append(_assistant(_bash(EXIT_2, "e2")))
    events.append(second_result if second_result is not None else _tool_result("e2", "NEXT STEPS"))
    events.append(_final())
    return _stream(*events)


TWO_EXITS = _expect(["--stage forge-verify", "--owner nested"], ["--stage forge-fix"])


def test_ordered_evidence_matches_in_fixture_order_and_ignores_reconnaissance() -> None:
    ok, matches = ce.ordered_command_evidence(ce.parse_transcript(_two_exit_stream()), TWO_EXITS)
    assert ok is True
    assert [m["command"] for m in matches] == [EXIT_1, EXIT_2]


def test_ordered_evidence_requires_all_tokens_of_one_entry_in_one_command() -> None:
    """AND, not OR: two tokens satisfied by two different commands is not a match."""
    parsed = ce.parse_transcript(_two_exit_stream())
    ok, _ = ce.ordered_command_evidence(parsed, _expect(["--stage forge-verify", "--owner direct"]))
    assert ok is False


def test_ordered_evidence_treats_contains_values_as_literal_tokens() -> None:
    parsed = ce.parse_transcript(_two_exit_stream())
    ok, _ = ce.ordered_command_evidence(parsed, _expect(["--stage forge-.*"]))
    assert ok is False


def test_ordered_evidence_rejects_a_missing_result() -> None:
    stream = _stream(
        *_ok(EXIT_1, "e1"),
        _assistant(_bash(EXIT_2, "e2")),  # requested, never observed to complete
        _final(),
    )
    ok, matches = ce.ordered_command_evidence(ce.parse_transcript(stream), TWO_EXITS)
    assert ok is False
    # The successful prefix survives for diagnostics.
    assert [m["command"] for m in matches] == [EXIT_1]


def test_ordered_evidence_rejects_a_nonzero_result() -> None:
    stream = _two_exit_stream(second_result=_tool_result("e2", "Exit code 2\nboom", is_error=True))
    ok, matches = ce.ordered_command_evidence(ce.parse_transcript(stream), TWO_EXITS)
    assert ok is False and len(matches) == 1


def test_ordered_evidence_rejects_an_error_result_without_an_exit_code() -> None:
    stream = _two_exit_stream(second_result=_tool_result("e2", "permission denied", is_error=True))
    ok, _ = ce.ordered_command_evidence(ce.parse_transcript(stream), TWO_EXITS)
    assert ok is False


def test_ordered_evidence_rejects_a_reordered_exit() -> None:
    stream = _stream(*_ok(EXIT_2, "e2"), *_ok(EXIT_1, "e1"), _final())
    ok, matches = ce.ordered_command_evidence(ce.parse_transcript(stream), TWO_EXITS)
    assert ok is False and matches == []


def test_ordered_evidence_rejects_a_duplicate_exit_between_expectations() -> None:
    stream = _stream(*_ok(EXIT_1, "e1"), *_ok(EXIT_1, "e1b"), *_ok(EXIT_2, "e2"), _final())
    ok, _ = ce.ordered_command_evidence(ce.parse_transcript(stream), TWO_EXITS)
    assert ok is False


def test_ordered_evidence_rejects_a_duplicate_exit_after_the_last_expectation() -> None:
    """A trailing extra exit is the same defect seen from the other side."""
    stream = _stream(*_ok(EXIT_1, "e1"), *_ok(EXIT_2, "e2"), *_ok(EXIT_2, "e2b"), _final())
    ok, matches = ce.ordered_command_evidence(ce.parse_transcript(stream), TWO_EXITS)
    assert ok is False and len(matches) == 2


def test_ordered_evidence_ignores_a_repeated_reconnaissance_command() -> None:
    """Only a REAL exit may not be skipped; recon repeats freely between exits."""
    events = [
        *_ok(EXIT_1, "e1"),
        *_ok("git status", "r1"),
        *_ok("git status", "r2"),
        *_ok('python3 "$R/scripts/forge-session.py" state-verify --status passed', "s1"),
        *_ok(EXIT_2, "e2"),
        _final(),
    ]
    ok, _ = ce.ordered_command_evidence(ce.parse_transcript(_stream(*events)), TWO_EXITS)
    assert ok is True


def test_a_command_counts_as_an_exit_only_with_the_invocation_shape() -> None:
    assert ce._is_exit_command(EXIT_1) is True
    assert ce._is_exit_command('python3 "$R/scripts/forge-session.py" state-verify') is False
    assert ce._is_exit_command("stage-exit was run for forge-verify") is False
    # F4: reconnaissance and mere co-mention are not exits — a --help probe
    # produces no payload, and the two tokens appearing apart is not an invocation.
    assert ce._is_exit_command(
        'python3 "$R/scripts/forge-session.py" stage-exit --help'
    ) is False
    assert ce._is_exit_command(
        "grep stage-exit notes.md; cat scripts/forge-session.py"
    ) is False


def test_ordered_evidence_rejects_a_prose_only_claim_with_no_bash_evidence() -> None:
    stream = _stream(
        _assistant(_text(f"I ran `{EXIT_1}` and then `{EXIT_2}`.")),
        _final("Both exits were invoked."),
    )
    ok, matches = ce.ordered_command_evidence(ce.parse_transcript(stream), TWO_EXITS)
    assert ok is False and matches == []


def test_ordered_evidence_never_matches_against_the_result_tail() -> None:
    """The tail is for READING a failure; a token echoed there is not a command."""
    stream = _stream(
        _assistant(_bash("cat transcript.log", "a")),
        _tool_result("a", f"the docs say to run: {EXIT_1}"),
        _final(),
    )
    parsed = ce.parse_transcript(stream)
    assert EXIT_1 in parsed["command_evidence"][0]["resultTail"]
    ok, _ = ce.ordered_command_evidence(parsed, _expect(["--stage forge-verify"]))
    assert ok is False


def test_ordered_evidence_rejects_an_unparsed_transcript() -> None:
    ok, matches = ce.ordered_command_evidence(ce.parse_transcript("Warning: nothing"), TWO_EXITS)
    assert ok is False and matches == []


def test_ordered_evidence_rejects_an_empty_token_list() -> None:
    """An empty list matches every command and would pass a scenario nobody drove."""
    ok, _ = ce.ordered_command_evidence(ce.parse_transcript(_two_exit_stream()), _expect([]))
    assert ok is False


def test_ordered_evidence_accepts_the_shipped_fixture_token_shape(branch_fixture: dict) -> None:
    """A synthetic transcript built from the real fixture's own tokens scores clean —
    proving the matcher and the shipped `expectedCommands` agree on shape."""
    for scenario in branch_fixture["scenarios"]:
        events: list[object] = []
        for index, expected in enumerate(scenario["expectedCommands"]):
            command = 'python3 "$R/scripts/forge-session.py" ' + " ".join(expected["contains"])
            events += _ok(command, f"t{index}", "ran")
        ok, matches = ce.ordered_command_evidence(
            ce.parse_transcript(_stream(*events, _final())), scenario["expectedCommands"]
        )
        assert ok is True, scenario["name"]
        assert len(matches) == len(scenario["expectedCommands"])


def test_ordered_evidence_matches_the_quoted_form_the_skill_fences(
    branch_fixture: dict,
) -> None:
    """Skill fences quote templated values (`--owner "{owner}"`), so a live run's
    quoted argv must satisfy the fixture's unquoted argv-level tokens — scoring
    the quoted form non-compliant marks a run that followed the skill verbatim
    as a miss."""
    for scenario in branch_fixture["scenarios"]:
        events: list[object] = []
        for index, expected in enumerate(scenario["expectedCommands"]):
            quoted = " ".join(
                f'{flag} "{value}"' if token.startswith("--") else token
                for token in expected["contains"]
                for flag, _, value in [token.partition(" ")]
            )
            command = 'python3 "$R/scripts/forge-session.py" stage-exit ' + quoted
            events += _ok(command, f"q{index}", "ran")
        ok, matches = ce.ordered_command_evidence(
            ce.parse_transcript(_stream(*events, _final())), scenario["expectedCommands"]
        )
        assert ok is True, scenario["name"]
        assert len(matches) == len(scenario["expectedCommands"])


# --------------------------------------------------------------------------- #
# Probe 3 — branch fixture, loader, and ground truth
# --------------------------------------------------------------------------- #


@pytest.fixture()
def branch_fixture() -> dict:
    return ce.load_branch_fixture(ce.BRANCH_FIXTURE_PATH)


def _scenario(fixture: dict, name: str) -> dict:
    return next(s for s in fixture["scenarios"] if s["name"] == name)


def _branch_repo(tmp_path: Path, fixture: dict, name: str = "proj") -> Path:
    root = tmp_path / name
    root.mkdir()
    ce.build_branch_fixture(root, fixture)
    return root


def _write_fixture(tmp_path: Path, data: object) -> Path:
    path = tmp_path / "verify-fix-reverify.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _fixture_dict() -> dict:
    """A mutable deep copy of the shipped fixture, for negative-case edits."""
    return json.loads(ce.BRANCH_FIXTURE_PATH.read_text(encoding="utf-8"))


def test_branch_fixture_lives_at_the_exact_nested_path() -> None:
    assert ce.BRANCH_FIXTURE_PATH.is_file()
    assert ce.BRANCH_FIXTURE_PATH.relative_to(REPO_ROOT) == Path(
        "eval/fixtures/compliance/verify-fix-reverify.json"
    )


def test_trigger_eval_never_discovers_the_compliance_fixture() -> None:
    """The `compliance/` nesting is load-bearing, not cosmetic (06 §3.1).

    `eval/run-eval.py::load_fixtures()` globs non-recursively, so a compliance fixture at
    `eval/fixtures/` level would be parsed as a trigger fixture and corrupt that baseline.
    """
    spec = importlib.util.spec_from_file_location(
        "_forge_trigger_eval", REPO_ROOT / "eval" / "run-eval.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    fixtures = module.load_fixtures()
    assert [f["skill"] for f in fixtures] == ["forge-1-prd", "forge-5-loop"]
    for fixture in fixtures:
        assert "scenarios" not in fixture
        assert "schemaVersion" not in fixture


def test_existing_trigger_fixtures_keep_their_schema() -> None:
    for name in ("forge-1-prd.json", "forge-5-loop.json"):
        data = json.loads((REPO_ROOT / "eval" / "fixtures" / name).read_text(encoding="utf-8"))
        assert set(data) == {"skill", "shouldTrigger", "shouldNotTrigger"}


def test_branch_fixture_loads_with_three_ordered_scenarios(branch_fixture: dict) -> None:
    assert branch_fixture["schemaVersion"] == 2
    assert [s["name"] for s in branch_fixture["scenarios"]] == [
        "successful-rejoin",
        "recovery",
        "escalation",
    ]
    assert branch_fixture["servedStage"] == "forge-1-prd"
    assert branch_fixture["verifyMode"] == "prd"
    assert [s["priorRedReverifies"] for s in branch_fixture["scenarios"]] == [0, 0, 1]


def test_served_stage_and_verify_mode_agree_under_the_real_mapping(branch_fixture: dict) -> None:
    session = ce._load_session_module()
    mode, served = branch_fixture["verifyMode"], branch_fixture["servedStage"]
    assert session.VERIFY_MODE_TO_STAGE[mode] == served


def test_the_shipped_fixture_orders_nested_calls_before_one_direct_terminal(
    branch_fixture: dict,
) -> None:
    """AC 6: intermediate calls are nested; only the final call is terminal owner."""
    for scenario in branch_fixture["scenarios"]:
        commands = scenario["expectedCommands"]
        # A first diversion drives four exits; an escalation cycle starts at the fix
        # (the prior verify close is history on disk), so it drives three.
        assert len(commands) == (3 if scenario["priorRedReverifies"] else 4)
        for entry in commands[:-1]:
            assert "--owner nested" in entry["contains"]
            assert entry["stage"] != "terminal-exit"
        assert commands[-1]["stage"] == "terminal-exit"
        assert "--owner direct" in commands[-1]["contains"]
        for entry in commands:
            assert "forge-session.py" in entry["contains"]
            assert "stage-exit" in entry["contains"]


def test_the_shipped_fixture_carries_the_served_stage_on_every_branch_command(
    branch_fixture: dict,
) -> None:
    served = branch_fixture["servedStage"]
    for scenario in branch_fixture["scenarios"]:
        for entry in scenario["expectedCommands"]:
            carried = [
                t
                for t in entry["contains"]
                if t.startswith(("--served-stage", "--verify-mode"))
            ]
            assert carried, f"{scenario['name']}/{entry['stage']} drops the served stage"
            for token in carried:
                if token.startswith("--served-stage"):
                    assert token == f"--served-stage {served}"


def test_no_next_steps_prose_is_hard_coded_in_the_fixture() -> None:
    raw = ce.BRANCH_FIXTURE_PATH.read_text(encoding="utf-8")
    assert "nextSteps" not in raw
    assert ce.SENTINEL not in raw
    assert "Next steps" not in raw


# --- loader rejections -------------------------------------------------------


def test_loader_rejects_an_unknown_schema_version(tmp_path: Path) -> None:
    data = _fixture_dict()
    data["schemaVersion"] = 1
    with pytest.raises(RuntimeError, match="schemaVersion"):
        ce.load_branch_fixture(_write_fixture(tmp_path, data))


def test_loader_rejects_a_boolean_schema_version(tmp_path: Path) -> None:
    """`bool` is an `int` subclass, so a bool would otherwise validate as an int."""
    data = _fixture_dict()
    data["schemaVersion"] = True
    with pytest.raises(RuntimeError, match="schemaVersion"):
        ce.load_branch_fixture(_write_fixture(tmp_path, data))


def test_loader_rejects_a_missing_scenario(tmp_path: Path) -> None:
    data = _fixture_dict()
    data["scenarios"] = data["scenarios"][:1]
    with pytest.raises(RuntimeError, match="in that order"):
        ce.load_branch_fixture(_write_fixture(tmp_path, data))


def test_loader_rejects_a_duplicate_scenario(tmp_path: Path) -> None:
    data = _fixture_dict()
    data["scenarios"] = [data["scenarios"][0], data["scenarios"][0]]
    with pytest.raises(RuntimeError, match="unique"):
        ce.load_branch_fixture(_write_fixture(tmp_path, data))


def test_loader_rejects_the_wrong_scenario_order(tmp_path: Path) -> None:
    data = _fixture_dict()
    data["scenarios"] = list(reversed(data["scenarios"]))
    with pytest.raises(RuntimeError, match="in that order"):
        ce.load_branch_fixture(_write_fixture(tmp_path, data))


@pytest.mark.parametrize("feature", ["../escape", "Widget Search", "", "widget_search"])
def test_loader_rejects_an_unsafe_feature(tmp_path: Path, feature: str) -> None:
    data = _fixture_dict()
    data["feature"] = feature
    with pytest.raises(RuntimeError):
        ce.load_branch_fixture(_write_fixture(tmp_path, data))


def test_loader_rejects_an_empty_command_token_list(tmp_path: Path) -> None:
    """An empty token list matches every command, so it would pass silently."""
    data = _fixture_dict()
    data["scenarios"][0]["expectedCommands"][0]["contains"] = []
    with pytest.raises(RuntimeError, match="non-empty list"):
        ce.load_branch_fixture(_write_fixture(tmp_path, data))


def test_loader_rejects_a_duplicate_evidence_stage(tmp_path: Path) -> None:
    data = _fixture_dict()
    commands = data["scenarios"][0]["expectedCommands"]
    commands[1]["stage"] = commands[0]["stage"]
    with pytest.raises(RuntimeError, match="repeats an evidence stage"):
        ce.load_branch_fixture(_write_fixture(tmp_path, data))


def test_loader_rejects_an_unknown_top_level_key(tmp_path: Path) -> None:
    data = _fixture_dict()
    data["notes"] = "helpful"
    with pytest.raises(RuntimeError, match="unknown top-level key"):
        ce.load_branch_fixture(_write_fixture(tmp_path, data))


def test_loader_rejects_an_unknown_scenario_key(tmp_path: Path) -> None:
    data = _fixture_dict()
    data["scenarios"][0]["expectedNextSteps"] = "..."
    with pytest.raises(RuntimeError, match="unknown key"):
        ce.load_branch_fixture(_write_fixture(tmp_path, data))


def test_loader_rejects_an_unknown_command_key(tmp_path: Path) -> None:
    data = _fixture_dict()
    data["scenarios"][0]["expectedCommands"][0]["optional"] = True
    with pytest.raises(RuntimeError, match="unknown key"):
        ce.load_branch_fixture(_write_fixture(tmp_path, data))


def test_loader_rejects_a_missing_top_level_key(tmp_path: Path) -> None:
    data = _fixture_dict()
    del data["verifyMode"]
    with pytest.raises(RuntimeError, match="missing top-level key"):
        ce.load_branch_fixture(_write_fixture(tmp_path, data))


def test_loader_rejects_a_mode_that_disagrees_with_the_served_stage(tmp_path: Path) -> None:
    data = _fixture_dict()
    data["verifyMode"] = "tech"
    with pytest.raises(RuntimeError, match="maps to"):
        ce.load_branch_fixture(_write_fixture(tmp_path, data))


def test_loader_rejects_a_command_that_could_be_satisfied_by_prose(tmp_path: Path) -> None:
    data = _fixture_dict()
    data["scenarios"][0]["expectedCommands"][0]["contains"] = ["verification reported findings"]
    with pytest.raises(RuntimeError, match="marker"):
        ce.load_branch_fixture(_write_fixture(tmp_path, data))


def test_loader_rejects_an_intermediate_command_claiming_direct_ownership(tmp_path: Path) -> None:
    data = _fixture_dict()
    tokens = data["scenarios"][0]["expectedCommands"][0]["contains"]
    tokens[tokens.index("--owner nested")] = "--owner direct"
    with pytest.raises(RuntimeError, match="--owner nested"):
        ce.load_branch_fixture(_write_fixture(tmp_path, data))


def test_loader_rejects_a_terminal_command_that_is_not_last(tmp_path: Path) -> None:
    data = _fixture_dict()
    data["scenarios"][0]["expectedCommands"][0]["stage"] = "terminal-exit"
    with pytest.raises(RuntimeError, match="terminal-exit"):
        ce.load_branch_fixture(_write_fixture(tmp_path, data))


def test_loader_rejects_a_foreign_served_stage_token(tmp_path: Path) -> None:
    data = _fixture_dict()
    tokens = data["scenarios"][0]["expectedCommands"][1]["contains"]
    tokens[tokens.index("--served-stage forge-1-prd")] = "--served-stage forge-3-specs"
    with pytest.raises(RuntimeError, match="served stage other than"):
        ce.load_branch_fixture(_write_fixture(tmp_path, data))


def test_loader_rejects_a_primary_command_naming_another_feature(tmp_path: Path) -> None:
    data = _fixture_dict()
    data["scenarios"][0]["expectedPrimaryCommand"] = "/feature-forge:forge-2-tech other-feature"
    with pytest.raises(RuntimeError, match="does not name"):
        ce.load_branch_fixture(_write_fixture(tmp_path, data))


def test_loader_preserves_os_error(tmp_path: Path) -> None:
    with pytest.raises(OSError):
        ce.load_branch_fixture(tmp_path / "absent.json")


def test_loader_preserves_json_decode_error(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        ce.load_branch_fixture(path)


def test_loader_uses_runtime_error_only_for_fixture_invariants(tmp_path: Path) -> None:
    """RuntimeError is reserved for invariants — it must not swallow OSError/JSONDecodeError."""
    with pytest.raises(OSError) as os_exc:
        ce.load_branch_fixture(tmp_path / "absent.json")
    assert not isinstance(os_exc.value, RuntimeError)
    path = tmp_path / "broken.json"
    path.write_text("[", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError) as json_exc:
        ce.load_branch_fixture(path)
    assert not isinstance(json_exc.value, RuntimeError)


# --- fixture construction and ground truth -----------------------------------


def test_branch_repo_state_is_schema_valid(tmp_path: Path, branch_fixture: dict) -> None:
    root = _branch_repo(tmp_path, branch_fixture)
    schema = json.loads((REPO_ROOT / "references" / "pipeline-state-schema.json").read_text())
    state = json.loads(
        (root / "specs" / branch_fixture["feature"] / ".pipeline-state.json").read_text()
    )
    for key in schema["required"]:
        assert key in state
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(state, schema)


def test_branch_repo_is_parked_before_the_diversion(tmp_path: Path, branch_fixture: dict) -> None:
    """The verify entry must be ABSENT: every transition is one the run performs."""
    root = _branch_repo(tmp_path, branch_fixture)
    feature_dir = root / "specs" / branch_fixture["feature"]
    state = json.loads((feature_dir / ".pipeline-state.json").read_text())
    assert state["stages"]["forge-1-prd"]["status"] == "complete"
    assert state["stages"]["forge-1-prd"]["version"] == 1
    assert "forge-verify-prd" not in state["stages"]
    assert (feature_dir / "PRD.md").is_file()
    assert (feature_dir / ce.BRANCH_FINDINGS_FILE).is_file()


def test_branch_repo_is_a_clean_committed_git_repo(tmp_path: Path, branch_fixture: dict) -> None:
    root = _branch_repo(tmp_path, branch_fixture)
    proc = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True
    )
    assert proc.returncode == 0
    assert proc.stdout.strip() == ""


def test_build_branch_fixture_rejects_an_unsafe_feature(
    tmp_path: Path, branch_fixture: dict
) -> None:
    hostile = {**branch_fixture, "feature": "../escape"}
    root = tmp_path / "proj"
    root.mkdir()
    with pytest.raises(RuntimeError, match="safe name"):
        ce.build_branch_fixture(root, hostile)


@pytest.mark.parametrize("name", ["successful-rejoin", "recovery"])
def test_expected_branch_exit_matches_the_fixture_primary_command(
    tmp_path: Path, branch_fixture: dict, name: str
) -> None:
    """Ground truth comes from the real CLI; the fixture only asserts which route wins."""
    scenario = _scenario(branch_fixture, name)
    root = _branch_repo(tmp_path, branch_fixture, name)
    payload = ce.expected_branch_exit(root, branch_fixture, scenario)
    directives = payload["directives"]
    assert directives["primaryCommand"] == scenario["expectedPrimaryCommand"]
    assert directives["servedStage"] == branch_fixture["servedStage"]
    assert directives["terminalOwnedBy"] == "self"
    assert payload["nextSteps"].rstrip().endswith(ce.SENTINEL)
    assert payload["nextSteps"].count(ce.SENTINEL) == 1


def test_successful_rejoin_advances_and_recovery_does_not(
    tmp_path: Path, branch_fixture: dict
) -> None:
    rejoin = ce.expected_branch_exit(
        _branch_repo(tmp_path, branch_fixture, "a"),
        branch_fixture,
        _scenario(branch_fixture, "successful-rejoin"),
    )["directives"]
    recovery = ce.expected_branch_exit(
        _branch_repo(tmp_path, branch_fixture, "b"),
        branch_fixture,
        _scenario(branch_fixture, "recovery"),
    )["directives"]
    assert rejoin["primaryCommand"] == "/feature-forge:forge-2-tech widget-search"
    assert recovery["primaryCommand"].startswith("/feature-forge:forge-fix ")
    assert "--served-stage forge-1-prd" in recovery["primaryCommand"]
    assert "forge-2-tech" not in recovery["primaryCommand"]


def test_expected_branch_exit_runs_the_real_state_transition(
    tmp_path: Path, branch_fixture: dict
) -> None:
    """`findings-applied` clears freshness, so the recorded status must be the real one."""
    root = _branch_repo(tmp_path, branch_fixture)
    ce.expected_branch_exit(root, branch_fixture, _scenario(branch_fixture, "recovery"))
    entry = json.loads(
        (root / "specs" / branch_fixture["feature"] / ".pipeline-state.json").read_text()
    )["stages"]["forge-verify-prd"]
    assert entry["status"] == "findings-reported"
    assert entry["findingsFile"] == ce.BRANCH_FINDINGS_FILE


def test_no_state_leaks_between_scenarios(tmp_path: Path, branch_fixture: dict) -> None:
    """Each scenario gets a fresh throwaway repo; one run must not colour another."""
    first = _branch_repo(tmp_path, branch_fixture, "first")
    ce.expected_branch_exit(first, branch_fixture, _scenario(branch_fixture, "recovery"))
    second = _branch_repo(tmp_path, branch_fixture, "second")
    state = json.loads(
        (second / "specs" / branch_fixture["feature"] / ".pipeline-state.json").read_text()
    )
    assert "forge-verify-prd" not in state["stages"]
    assert second != first


def test_terminal_exit_args_come_from_the_fixture(branch_fixture: dict) -> None:
    args = ce.terminal_exit_args(_scenario(branch_fixture, "successful-rejoin"))
    assert args == [
        "--stage", "forge-fix",
        "--owner", "direct",
        "--outcome", "reverified",
        "--served-stage", "forge-1-prd",
    ]


def test_branch_prompt_carries_the_ownership_tokens_and_real_paths(branch_fixture: dict) -> None:
    """Ownership is never inferred from phrasing — the prompt is the carrier (04 §3.1)."""
    for scenario in branch_fixture["scenarios"]:
        prompt = ce.branch_prompt(branch_fixture, scenario)
        assert prompt.count("owner: nested") == len(scenario["expectedCommands"]) - 1
        assert prompt.count("owner: direct") == 1
        assert branch_fixture["feature"] in prompt
        assert str(REPO_ROOT / "skills" / "forge-verify" / "SKILL.md") in prompt
        assert str(REPO_ROOT / "skills" / "forge-fix" / "SKILL.md") in prompt
        assert str(REPO_ROOT / "references" / "stage-exit-protocol.md") in prompt
        assert ce.BRANCH_FINDINGS_FILE in prompt


def test_branch_prompt_distinguishes_the_two_reverify_outcomes(branch_fixture: dict) -> None:
    rejoin = ce.branch_prompt(branch_fixture, _scenario(branch_fixture, "successful-rejoin"))
    recovery = ce.branch_prompt(branch_fixture, _scenario(branch_fixture, "recovery"))
    assert "PASSES" in rejoin and "FURTHER findings" not in rejoin
    assert "FURTHER findings" in recovery and "PASSES" not in recovery


def test_branch_prompt_never_dictates_the_expected_output(branch_fixture: dict) -> None:
    """A prompt that quotes the answer measures transcription, not compliance."""
    for scenario in branch_fixture["scenarios"]:
        prompt = ce.branch_prompt(branch_fixture, scenario)
        assert ce.SENTINEL not in prompt
        assert scenario["expectedPrimaryCommand"] not in prompt
        assert "stage-exit --stage" not in prompt


# --------------------------------------------------------------------------- #
# Branch scorer — the nine criteria and the negative matrix (06 §5.2, 07 §7.2)
# --------------------------------------------------------------------------- #
#
# Every transcript below is a pure dictionary stream: no live model, no network, and no
# API key. The one subprocess is the real `forge-session.py` CLI deriving ground truth,
# which is exactly what keeps the expectation the script's own output rather than prose.

#: The nine branch criteria (06 §5.2's eight plus the remediation round-ledger
#: criterion), spelled out here rather than imported. Comparing the module constant
#: against itself would be vacuous; this is the second, independent copy that makes
#: a silently added or dropped criterion fail.
SPEC_BRANCH_CRITERIA = (
    "ordered_command_results",
    "all_commands_succeeded",
    "exactly_one_sentinel",
    "nested_steps_emitted_no_sentinel",
    "nothing_after_sentinel",
    "next_command_fenced",
    "block_verbatim",
    "correct_rejoin_or_recovery",
    "escalation_digest_presented",
)


@pytest.fixture(scope="module")
def branch_truth(tmp_path_factory) -> dict[str, dict]:
    """Real `StageExitPayload` ground truth per scenario, derived once for the module.

    Each scenario gets its own throwaway repository: `expected_branch_exit` walks the
    repo through the scenario's real verification transitions, so sharing one would let
    the first scenario colour the second.
    """
    fixture = ce.load_branch_fixture(ce.BRANCH_FIXTURE_PATH)
    base = tmp_path_factory.mktemp("branch-truth")
    truth: dict[str, dict] = {}
    for scenario in fixture["scenarios"]:
        root = base / scenario["name"]
        root.mkdir()
        ce.build_branch_fixture(root, fixture, scenario)
        truth[scenario["name"]] = ce.expected_branch_exit(root, fixture, scenario)
    return truth


def _branch_command(expected: dict) -> str:
    """A plausible real invocation carrying every literal token the fixture requires."""
    flags = " ".join(token for token in expected["contains"] if token.startswith("--"))
    return (
        'python3 "$R/scripts/forge-session.py" stage-exit '
        f'--feature widget-search {flags} --specs-dir specs --host claude'
    )


def _branch_commands(scenario: dict) -> list[str]:
    return [_branch_command(entry) for entry in scenario["expectedCommands"]]


def _branch_stream(
    commands: list[str],
    final_text: str,
    *,
    pre_texts: tuple[str, ...] = (),
    drop_last_result: bool = False,
    fail_last_result: bool = False,
) -> str:
    events: list[object] = []
    for index, command in enumerate(commands):
        events.append(_assistant(_text(f"closing step {index + 1}"), _bash(command, f"b{index}")))
        last = index == len(commands) - 1
        if last and drop_last_result:
            continue  # requested, never observed to complete
        if last and fail_last_result:
            events.append(_tool_result(f"b{index}", "Exit code 2\nrefused", is_error=True))
            continue
        events.append(_tool_result(f"b{index}", "ran"))
    for text in pre_texts:
        events.append(_assistant(_text(text)))
    events.append(_assistant(_text(final_text)))
    events.append(_final(final_text))
    return _stream(*events)


def _score_run(
    branch_fixture: dict,
    branch_truth: dict[str, dict],
    name: str,
    final_text: str | None = None,
    *,
    commands: list[str] | None = None,
    **stream_kwargs: object,
) -> dict[str, bool]:
    """Score one synthetic run of `name`, defaulting to a fully compliant one."""
    scenario = _scenario(branch_fixture, name)
    truth = branch_truth[name]
    if scenario["priorRedReverifies"] and "pre_texts" not in stream_kwargs:
        # A compliant escalation run presents the acceptance digest as text before
        # the terminal block; the marker is what the scorer's criterion reads.
        stream_kwargs["pre_texts"] = (
            f"Second consecutive red re-verify — {ce.ESCALATION_MARKER} and advance, "
            f"run another fix pass, or stop here.",
        )
    stream = _branch_stream(
        _branch_commands(scenario) if commands is None else commands,
        truth["nextSteps"] if final_text is None else final_text,
        **stream_kwargs,  # type: ignore[arg-type]
    )
    return ce.score_branch_path(ce.parse_transcript(stream), truth, scenario)


def _assert_true(criteria: dict[str, bool], *keys: str) -> None:
    """Assert the named UNRELATED criteria survived, so one defect cannot mask another."""
    for key in keys:
        assert criteria[key] is True, f"{key} should have stayed true"


# --- the criteria set and the two positives ----------------------------------


def test_the_scorer_returns_exactly_the_nine_specified_criteria(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    criteria = _score_run(branch_fixture, branch_truth, "successful-rejoin")
    assert tuple(criteria) == SPEC_BRANCH_CRITERIA
    assert ce.BRANCH_CRITERIA == SPEC_BRANCH_CRITERIA


@pytest.mark.parametrize("name", ["successful-rejoin", "recovery", "escalation"])
def test_a_compliant_branch_run_satisfies_every_criterion(
    branch_fixture: dict, branch_truth: dict[str, dict], name: str
) -> None:
    criteria = _score_run(branch_fixture, branch_truth, name)
    assert all(criteria.values()), [key for key, value in criteria.items() if not value]


@pytest.mark.parametrize("name", ["successful-rejoin", "recovery", "escalation"])
def test_compliance_requires_all_nine(
    branch_fixture: dict, branch_truth: dict[str, dict], name: str
) -> None:
    """`_to_result` treats the scorer's dict as an AND, which is what makes each key bind."""
    criteria = _score_run(branch_fixture, branch_truth, name)
    assert all(criteria.values())
    for key in criteria:
        assert not all({**criteria, key: False}.values()), key


# --- negative 1: missing tool result -----------------------------------------


@pytest.mark.parametrize("name", ["successful-rejoin", "recovery"])
def test_negative_1_a_missing_tool_result_fails_ordered_command_results(
    branch_fixture: dict, branch_truth: dict[str, dict], name: str
) -> None:
    criteria = _score_run(branch_fixture, branch_truth, name, drop_last_result=True)
    assert criteria["ordered_command_results"] is False
    _assert_true(
        criteria,
        "all_commands_succeeded",  # the successful prefix is intact
        "exactly_one_sentinel",
        "nothing_after_sentinel",
        "next_command_fenced",
        "block_verbatim",
        "correct_rejoin_or_recovery",
    )


# --- negative 2: non-zero / error result -------------------------------------


def test_negative_2_a_failed_tool_result_fails_ordered_command_results(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    criteria = _score_run(branch_fixture, branch_truth, "successful-rejoin", fail_last_result=True)
    assert criteria["ordered_command_results"] is False
    _assert_true(criteria, "exactly_one_sentinel", "block_verbatim", "correct_rejoin_or_recovery")


# --- negative 3: reordered fix and re-verify ---------------------------------


def test_negative_3_reordering_the_fix_and_reverify_fails_ordered_command_results(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    scenario = _scenario(branch_fixture, "successful-rejoin")
    commands = _branch_commands(scenario)
    commands[1], commands[2] = commands[2], commands[1]
    criteria = _score_run(branch_fixture, branch_truth, "successful-rejoin", commands=commands)
    assert criteria["ordered_command_results"] is False
    _assert_true(criteria, "exactly_one_sentinel", "block_verbatim", "next_command_fenced")


# --- negative 4: duplicate stage-exit request --------------------------------


def test_negative_4_a_duplicate_stage_exit_fails_ordered_command_results(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    scenario = _scenario(branch_fixture, "successful-rejoin")
    commands = _branch_commands(scenario)
    criteria = _score_run(
        branch_fixture, branch_truth, "successful-rejoin", commands=[*commands, commands[-1]]
    )
    assert criteria["ordered_command_results"] is False
    _assert_true(criteria, "exactly_one_sentinel", "nothing_after_sentinel", "block_verbatim")


# --- negative 5: duplicate terminal sentinel ---------------------------------


def test_negative_5_a_duplicate_terminal_sentinel_fails_the_count_and_the_tail(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    block = branch_truth["successful-rejoin"]["nextSteps"]
    criteria = _score_run(branch_fixture, branch_truth, "successful-rejoin", block + "\n" + block)
    assert criteria["exactly_one_sentinel"] is False
    assert criteria["nothing_after_sentinel"] is False
    _assert_true(
        criteria,
        "ordered_command_results",
        "nested_steps_emitted_no_sentinel",  # the leak check is about EARLIER texts
        "block_verbatim",
        "next_command_fenced",
    )


def test_nothing_after_sentinel_fails_an_earlier_duplicate_despite_a_correct_tail(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    """A suffix check alone would pass this: the final line IS the sentinel (06 §5.2)."""
    block = branch_truth["recovery"]["nextSteps"]
    final_text = block + "\n" + block
    assert final_text.rstrip().endswith(ce.SENTINEL)
    criteria = _score_run(branch_fixture, branch_truth, "recovery", final_text)
    assert criteria["nothing_after_sentinel"] is False


# --- negative 6: sentinel emitted during a nested call -----------------------


@pytest.mark.parametrize("name", ["successful-rejoin", "recovery"])
def test_negative_6_a_nested_step_printing_a_sentinel_fails_the_ownership_check(
    branch_fixture: dict, branch_truth: dict[str, dict], name: str
) -> None:
    """REQ-EXIT-04: a nested verify/fix that prints its own terminal block leaks ownership."""
    leak = f"Verification closed.\n\n```\n/feature-forge:forge-fix widget-search\n```\n{ce.SENTINEL}"
    criteria = _score_run(branch_fixture, branch_truth, name, pre_texts=(leak,))
    assert criteria["nested_steps_emitted_no_sentinel"] is False
    assert criteria["exactly_one_sentinel"] is False  # two across all assistant texts
    _assert_true(
        criteria,
        "ordered_command_results",
        "nothing_after_sentinel",  # the FINAL block is still clean
        "block_verbatim",
    )


def test_the_terminal_block_itself_is_never_counted_as_a_nested_leak(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    """Negative control: the compliant run's own sentinel must not trip the leak check."""
    criteria = _score_run(branch_fixture, branch_truth, "successful-rejoin")
    assert criteria["nested_steps_emitted_no_sentinel"] is True


# --- negative 7: correct sentinel followed by prose --------------------------


@pytest.mark.parametrize("name", ["successful-rejoin", "recovery"])
def test_negative_7_trailing_prose_after_the_sentinel_fails_nothing_after_sentinel(
    branch_fixture: dict, branch_truth: dict[str, dict], name: str
) -> None:
    block = branch_truth[name]["nextSteps"]
    criteria = _score_run(
        branch_fixture, branch_truth, name, block + "\n\nLet me know if you want anything else."
    )
    assert criteria["nothing_after_sentinel"] is False
    _assert_true(
        criteria,
        "ordered_command_results",
        "exactly_one_sentinel",
        "nested_steps_emitted_no_sentinel",
        "next_command_fenced",
        "block_verbatim",
        "correct_rejoin_or_recovery",
    )


# --- negative 8: prose-only claim with no Bash evidence ----------------------


def test_negative_8_a_prose_only_claim_fails_ordered_command_results(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    """A perfect-looking block proves nothing when no command was ever run."""
    claim = "I closed the verification, the fix, and the re-verification through the script."
    criteria = _score_run(
        branch_fixture, branch_truth, "successful-rejoin", commands=[], pre_texts=(claim,)
    )
    assert criteria["ordered_command_results"] is False
    _assert_true(
        criteria,
        "exactly_one_sentinel",
        "nothing_after_sentinel",
        "next_command_fenced",
        "block_verbatim",
        "correct_rejoin_or_recovery",
    )


# --- negative 9: verbatim-looking block without the real terminal command ----


def test_negative_9_a_verbatim_block_without_the_terminal_command_fails_evidence(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    scenario = _scenario(branch_fixture, "recovery")
    criteria = _score_run(
        branch_fixture, branch_truth, "recovery", commands=_branch_commands(scenario)[:-1]
    )
    assert criteria["ordered_command_results"] is False
    _assert_true(
        criteria,
        "block_verbatim",  # the block really is byte-identical — and still not earned
        "next_command_fenced",
        "exactly_one_sentinel",
        "correct_rejoin_or_recovery",
    )


# --- negative 10: wrong feature or served stage ------------------------------


@pytest.mark.parametrize(
    ("wrong", "why"),
    [
        ("/feature-forge:forge-fix other-feature --served-stage forge-1-prd", "wrong feature"),
        ("/feature-forge:forge-fix widget-search --served-stage forge-3-specs", "wrong served"),
    ],
)
def test_negative_10_a_wrong_feature_or_served_stage_fails_the_route(
    branch_fixture: dict, branch_truth: dict[str, dict], wrong: str, why: str
) -> None:
    truth = branch_truth["recovery"]
    primary = truth["directives"]["primaryCommand"]
    criteria = _score_run(
        branch_fixture, branch_truth, "recovery", truth["nextSteps"].replace(primary, wrong)
    )
    assert criteria["correct_rejoin_or_recovery"] is False, why
    # The block carries the sentinel but is no longer the script's own bytes.
    assert criteria["block_verbatim"] is False
    _assert_true(
        criteria,
        "ordered_command_results",
        "all_commands_succeeded",
        "exactly_one_sentinel",
        "nothing_after_sentinel",
        "nested_steps_emitted_no_sentinel",
    )


@pytest.mark.parametrize(
    ("doctored", "why"),
    [
        ("/feature-forge:forge-fix widget-search", "no served stage carried forward"),
        ("/feature-forge:forge-fix --served-stage forge-1-prd", "no feature named"),
        ("/feature-forge:forge-2-tech widget-search", "recovery route equals the successor"),
    ],
)
def test_a_recovery_route_that_loses_its_context_is_not_correct(
    branch_fixture: dict, branch_truth: dict[str, dict], doctored: str, why: str
) -> None:
    """The recovery command must keep the same feature and served stage (06 §5.2).

    Driven through a doctored expectation because a transcript cannot express it: the
    guard is on the ROUTE the payload names, which a live run never gets to choose.
    """
    truth = branch_truth["recovery"]
    payload = {
        **truth,
        "directives": {**truth["directives"], "primaryCommand": doctored},
        "nextSteps": truth["nextSteps"].replace(truth["directives"]["primaryCommand"], doctored),
    }
    criteria = ce.score_branch_path(
        ce.parse_transcript(
            _branch_stream(
                _branch_commands(_scenario(branch_fixture, "recovery")), payload["nextSteps"]
            )
        ),
        payload,
        _scenario(branch_fixture, "recovery"),
    )
    assert criteria["correct_rejoin_or_recovery"] is False, why


def test_a_rejoin_route_that_is_not_the_production_successor_is_not_correct(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    """The resolved diversion must hand back to the successor, not to another diversion."""
    truth = branch_truth["successful-rejoin"]
    doctored = "/feature-forge:forge-fix widget-search --served-stage forge-1-prd"
    payload = {
        **truth,
        "directives": {**truth["directives"], "primaryCommand": doctored},
        "nextSteps": truth["nextSteps"].replace(truth["directives"]["primaryCommand"], doctored),
    }
    criteria = ce.score_branch_path(
        ce.parse_transcript(
            _branch_stream(
                _branch_commands(_scenario(branch_fixture, "successful-rejoin")),
                payload["nextSteps"],
            )
        ),
        payload,
        _scenario(branch_fixture, "successful-rejoin"),
    )
    assert criteria["correct_rejoin_or_recovery"] is False


def test_all_commands_succeeded_rejects_a_matched_command_that_did_not_succeed(
    branch_fixture: dict, branch_truth: dict[str, dict], monkeypatch
) -> None:
    """The matcher refuses to match a failed result today; this pins the second guard.

    Driven through a stubbed matcher on purpose — it is the only way to reach the
    criterion, and it is exactly the future relaxation the guard exists to survive.
    """
    failed: dict = {
        "requestIndex": 0,
        "toolUseId": "b0",
        "command": "stage-exit",
        "resultSeen": True,
        "exitCode": 2,
        "isError": True,
        "resultTail": "boom",
    }
    monkeypatch.setattr(ce, "ordered_command_evidence", lambda *_: (True, [failed]))
    criteria = _score_run(branch_fixture, branch_truth, "recovery")
    assert criteria["ordered_command_results"] is True
    assert criteria["all_commands_succeeded"] is False


def test_a_paraphrased_block_fails_block_verbatim_while_keeping_the_sentinel(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    """Byte-for-byte, not sentinel-shaped: a summary that ends correctly is still a summary."""
    truth = branch_truth["successful-rejoin"]
    primary = truth["directives"]["primaryCommand"]
    paraphrase = f"**Next steps**\nThe diversion is resolved.\n\n```\n{primary}\n```\n{ce.SENTINEL}"
    criteria = _score_run(branch_fixture, branch_truth, "successful-rejoin", paraphrase)
    assert criteria["block_verbatim"] is False
    _assert_true(
        criteria,
        "exactly_one_sentinel",
        "nothing_after_sentinel",
        "next_command_fenced",
        "correct_rejoin_or_recovery",
        "ordered_command_results",
    )


# --- negative 11: recovery incorrectly advancing to production ---------------


def test_negative_11_recovery_that_fences_the_production_successor_fails_the_route(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    """The deferred successor may be MENTIONED; fencing it offers an advance (REQ-EXIT-06)."""
    truth = branch_truth["recovery"]
    successor = truth["directives"]["nextCommand"]
    advance = f"```\n{successor}\n```\n{ce.SENTINEL}"
    criteria = _score_run(
        branch_fixture, branch_truth, "recovery", truth["nextSteps"].replace(ce.SENTINEL, advance)
    )
    assert criteria["correct_rejoin_or_recovery"] is False
    _assert_true(
        criteria,
        "ordered_command_results",
        "next_command_fenced",  # the real recovery command is STILL fenced
        "exactly_one_sentinel",
        "nothing_after_sentinel",
    )


def test_the_recovery_block_mentions_the_successor_without_fencing_it(
    branch_truth: dict[str, dict]
) -> None:
    """Negative control for the rule above: the real block would otherwise trip it."""
    truth = branch_truth["recovery"]
    successor = truth["directives"]["nextCommand"]
    assert successor in truth["nextSteps"]
    assert ce._in_fenced_block(truth["nextSteps"], successor) is False


# --- negative 12: successful commands but the wrong fenced primary command ---


def test_negative_12_a_substituted_fenced_command_fails_next_command_fenced(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    truth = branch_truth["successful-rejoin"]
    primary = truth["directives"]["primaryCommand"]
    criteria = _score_run(
        branch_fixture,
        branch_truth,
        "successful-rejoin",
        truth["nextSteps"].replace(primary, "/feature-forge:forge widget-search"),
    )
    assert criteria["next_command_fenced"] is False
    assert criteria["block_verbatim"] is False
    _assert_true(
        criteria,
        "ordered_command_results",
        "all_commands_succeeded",
        "exactly_one_sentinel",
        "nothing_after_sentinel",
        "nested_steps_emitted_no_sentinel",
    )


def test_an_unfenced_primary_command_fails_only_the_fencing_criterion(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    """Fencing is the tap-to-copy surface — naming the command in prose is not enough."""
    truth = branch_truth["successful-rejoin"]
    primary = truth["directives"]["primaryCommand"]
    criteria = _score_run(
        branch_fixture,
        branch_truth,
        "successful-rejoin",
        truth["nextSteps"].replace(f"```\n{primary}\n```", f"Next, run `{primary}` when ready."),
    )
    assert criteria["next_command_fenced"] is False
    # Routing is right, presentation is not — the two criteria are genuinely independent.
    _assert_true(criteria, "correct_rejoin_or_recovery", "ordered_command_results")


# --- required-payload validation (06 §5.1) -----------------------------------


@pytest.mark.parametrize("missing", ["directives", "nextSteps", "sentinel"])
def test_a_missing_payload_key_raises_runtime_error_not_key_error(
    branch_fixture: dict, branch_truth: dict[str, dict], missing: str
) -> None:
    payload = {k: v for k, v in branch_truth["recovery"].items() if k != missing}
    with pytest.raises(RuntimeError, match=missing):
        ce.score_branch_path(
            ce.parse_transcript(_stream(_final("x"))), payload, _scenario(branch_fixture, "recovery")
        )


def test_a_missing_primary_command_raises_runtime_error_not_key_error(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    truth = branch_truth["recovery"]
    directives = {k: v for k, v in truth["directives"].items() if k != "primaryCommand"}
    with pytest.raises(RuntimeError, match="primaryCommand"):
        ce.score_branch_path(
            ce.parse_transcript(_stream(_final("x"))),
            {**truth, "directives": directives},
            _scenario(branch_fixture, "recovery"),
        )


@pytest.mark.parametrize("payload", [None, [], "nextSteps"])
def test_a_non_payload_expectation_raises_runtime_error(
    branch_fixture: dict, payload: object
) -> None:
    with pytest.raises(RuntimeError, match="StageExitPayload"):
        ce.score_branch_path(
            ce.parse_transcript(_stream(_final("x"))),
            payload,  # type: ignore[arg-type]
            _scenario(branch_fixture, "recovery"),
        )


@pytest.mark.parametrize("key", ["nextSteps", "sentinel"])
def test_an_empty_required_string_raises_runtime_error(
    branch_fixture: dict, branch_truth: dict[str, dict], key: str
) -> None:
    with pytest.raises(RuntimeError, match="non-empty"):
        ce.score_branch_path(
            ce.parse_transcript(_stream(_final("x"))),
            {**branch_truth["recovery"], key: ""},
            _scenario(branch_fixture, "recovery"),
        )


def test_a_nested_payload_is_rejected_rather_than_scored(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    """A nested exit has `nextSteps`/`sentinel` None — never valid terminal ground truth."""
    nested = {**branch_truth["recovery"], "nextSteps": None, "sentinel": None}
    with pytest.raises(RuntimeError, match="non-empty"):
        ce.score_branch_path(
            ce.parse_transcript(_stream(_final("x"))),
            nested,
            _scenario(branch_fixture, "recovery"),
        )


def test_a_drifted_sentinel_is_a_harness_defect_not_a_model_miss(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    with pytest.raises(RuntimeError, match="drifted"):
        ce.score_branch_path(
            ce.parse_transcript(_stream(_final("x"))),
            {**branch_truth["recovery"], "sentinel": "- forge: end -"},
            _scenario(branch_fixture, "recovery"),
        )


# --- probe registration and advisory behavior (07 §7.3) ----------------------


def test_branch_path_is_a_distinct_probe_choice_included_in_all(monkeypatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(ce, "driver_path", lambda: "/usr/bin/claude")
    monkeypatch.setattr(ce, "_assert_prelude_in_sync", lambda: None)
    for name in (
        "run_stage_exit_probe",
        "run_prelude_probe",
        "run_branch_probe",
        "run_loop_outcome_probe",
    ):
        monkeypatch.setattr(
            ce, name, (lambda label: lambda *a, **k: (calls.append(label), [])[1])(name)
        )
    assert ce.main(["--probe", "all", "--n", "1"]) == 0
    assert calls == [
        "run_stage_exit_probe",
        "run_prelude_probe",
        "run_branch_probe",
        "run_loop_outcome_probe",
    ]
    calls.clear()
    assert ce.main(["--probe", "branch-path", "--n", "1"]) == 0
    assert calls == ["run_branch_probe"]
    calls.clear()
    assert ce.main(["--probe", "loop-outcome", "--n", "1"]) == 0
    assert calls == ["run_loop_outcome_probe"]


def test_branch_path_is_rejected_by_neither_argparse_nor_the_help() -> None:
    proc = subprocess.run(
        [sys.executable, str(EVAL_SCRIPT), "--help"], capture_output=True, text=True
    )
    assert proc.returncode == 0
    assert "branch-path" in proc.stdout


def test_branch_probe_reports_the_three_scenarios_as_separate_variants() -> None:
    """Never averaged into stage-exit/cold or /warm — they are their own cells."""
    reports = ce.run_branch_probe(["model-x"], 0)  # n=0 drives no session
    assert [(r.probe, r.variant) for r in reports] == [
        ("branch-path", "successful-rejoin"),
        ("branch-path", "recovery"),
        ("branch-path", "escalation"),
    ]
    assert all(report.runs == 0 and report.rate is None for report in reports)


def test_the_offline_branch_path_never_reaches_a_live_driver(
    branch_fixture: dict, branch_truth: dict[str, dict], monkeypatch
) -> None:
    """CI hard-tests the fixture, parser, matcher, and scorer with no model in the loop."""

    def boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("the offline suite must not start a live session")

    monkeypatch.setattr(ce, "run_session", boom)
    monkeypatch.setattr(ce, "driver_path", boom)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    for name in ("successful-rejoin", "recovery", "escalation"):
        assert all(_score_run(branch_fixture, branch_truth, name).values())
    assert len(ce.run_branch_probe(["model-x"], 0)) == 3


def test_a_missing_driver_still_skips_at_exit_zero_for_the_branch_probe(
    monkeypatch, capsys
) -> None:
    monkeypatch.setattr(ce, "driver_path", lambda: None)
    assert ce.main(["--probe", "branch-path"]) == 0
    assert "skipped" in capsys.readouterr().out


def test_a_model_miss_is_a_scored_non_compliant_result_not_a_process_failure(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    scenario = _scenario(branch_fixture, "successful-rejoin")
    truth = branch_truth["successful-rejoin"]
    stream = _branch_stream(_branch_commands(scenario), "I finished the diversion.")
    result = ce._to_result(
        "branch-path", "model-x", scenario["name"], 0, ce.parse_transcript(stream),
        lambda t: ce.score_branch_path(t, truth, scenario),
    )
    assert result.ok is True and result.compliant is False
    assert result.criteria["block_verbatim"] is False


def test_an_unusable_transcript_is_unscored_rather_than_non_compliant(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    scenario = _scenario(branch_fixture, "recovery")
    result = ce._to_result(
        "branch-path", "model-x", scenario["name"], 0, ce.parse_transcript("Warning: nothing"),
        lambda t: ce.score_branch_path(t, branch_truth["recovery"], scenario),
    )
    assert result.ok is False and result.criteria == {}


# --- escalation scenario (the round ledger) ----------------------------------


def test_escalation_build_seeds_the_round_ledger(
    tmp_path: Path, branch_fixture: dict
) -> None:
    """A nonzero priorRedReverifies seeds the round-2 report AND its real state entry."""
    scenario = _scenario(branch_fixture, "escalation")
    root = tmp_path / "esc"
    root.mkdir()
    ce.build_branch_fixture(root, branch_fixture, scenario)
    feature_dir = root / "specs" / branch_fixture["feature"]
    assert (feature_dir / ce.BRANCH_ROUND2_FINDINGS_FILE).is_file()
    entry = json.loads((feature_dir / ".pipeline-state.json").read_text())[
        "stages"]["forge-verify-prd"]
    assert entry["status"] == "findings-reported"
    assert entry["findingsFile"] == ce.BRANCH_ROUND2_FINDINGS_FILE
    proc = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True
    )
    assert proc.returncode == 0 and proc.stdout.strip() == ""


def test_a_zero_prior_scenario_build_stays_parked(
    tmp_path: Path, branch_fixture: dict
) -> None:
    scenario = _scenario(branch_fixture, "recovery")
    root = tmp_path / "rec"
    root.mkdir()
    ce.build_branch_fixture(root, branch_fixture, scenario)
    state = json.loads(
        (root / "specs" / branch_fixture["feature"] / ".pipeline-state.json").read_text()
    )
    assert "forge-verify-prd" not in state["stages"]
    assert not (
        root / "specs" / branch_fixture["feature"] / ce.BRANCH_ROUND2_FINDINGS_FILE
    ).is_file()


def test_expected_branch_exit_for_escalation_routes_to_fix(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    scenario = _scenario(branch_fixture, "escalation")
    directives = branch_truth["escalation"]["directives"]
    assert directives["primaryCommand"] == scenario["expectedPrimaryCommand"]
    assert directives["primaryCommand"].startswith("/feature-forge:forge-fix ")
    assert "--served-stage forge-1-prd" in directives["primaryCommand"]


def test_escalation_prompt_supplies_the_ledger_not_the_conclusion(
    branch_fixture: dict,
) -> None:
    """The prompt states the facts (both reports, the red result); the escalation
    behavior itself must come from the skills, or the probe measures prompt-following."""
    prompt = ce.branch_prompt(branch_fixture, _scenario(branch_fixture, "escalation"))
    assert ce.BRANCH_ROUND2_FINDINGS_FILE in prompt
    assert ce.BRANCH_FINDINGS_FILE in prompt
    assert ce.ESCALATION_MARKER not in prompt
    assert "escalat" not in prompt.lower()


def test_escalation_criterion_reads_the_digest_marker(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    """Present digest -> true; absent digest -> the one failing criterion."""
    compliant = _score_run(branch_fixture, branch_truth, "escalation")
    assert compliant["escalation_digest_presented"] is True

    silent = _score_run(branch_fixture, branch_truth, "escalation", pre_texts=())
    assert silent["escalation_digest_presented"] is False
    _assert_true(
        silent,
        "ordered_command_results",
        "exactly_one_sentinel",
        "block_verbatim",
        "correct_rejoin_or_recovery",
    )


def test_the_digest_criterion_is_vacuous_only_without_prior_rounds(
    branch_fixture: dict, branch_truth: dict[str, dict]
) -> None:
    """Zero-prior scenarios auto-pass the criterion so the set stays uniform."""
    for name in ("successful-rejoin", "recovery"):
        criteria = _score_run(branch_fixture, branch_truth, name)
        assert criteria["escalation_digest_presented"] is True


def test_loader_rejects_a_bool_or_negative_prior_count(tmp_path: Path) -> None:
    for bad in (True, -1):
        data = _fixture_dict()
        data["scenarios"][2]["priorRedReverifies"] = bad
        with pytest.raises(RuntimeError, match="priorRedReverifies"):
            ce.load_branch_fixture(_write_fixture(tmp_path, data))


def test_loader_rejects_an_escalation_whose_reverify_passes(tmp_path: Path) -> None:
    data = _fixture_dict()
    data["scenarios"][2]["reverifyOutcome"] = "passed"
    with pytest.raises(RuntimeError, match="must\nreport findings|must report findings"):
        ce.load_branch_fixture(_write_fixture(tmp_path, data))


# --- loop-outcome probe (REQ-EVAL-01) -----------------------------------------


def _loop_fixture_dict() -> dict:
    return json.loads(ce.LOOP_OUTCOME_FIXTURE_PATH.read_text(encoding="utf-8"))


def _write_loop_fixture(tmp_path: Path, data: dict) -> Path:
    path = tmp_path / "loop-fixture.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


@pytest.fixture()
def loop_fixture() -> dict:
    return ce.load_loop_outcome_fixture(ce.LOOP_OUTCOME_FIXTURE_PATH)


@pytest.fixture()
def loop_truth(tmp_path: Path, loop_fixture: dict) -> dict:
    """Real ground truth from the real close, against a real fixture repository."""
    root = tmp_path / "loop-truth"
    root.mkdir()
    ce.build_loop_outcome_fixture(root, loop_fixture)
    return ce.expected_loop_exit(root, loop_fixture, loop_fixture["scenarios"][0])


def test_the_shipped_loop_fixture_declares_the_resolved_route(loop_fixture: dict) -> None:
    assert loop_fixture["schemaVersion"] == 1
    scenario = loop_fixture["scenarios"][0]
    assert scenario["outcome"] == "resolved"
    assert scenario["expectedPrimaryCommand"] == (
        f"/feature-forge:forge-5-loop {loop_fixture['feature']}"
    )


def test_loop_loader_hard_fails_on_a_foreign_schema_version(tmp_path: Path) -> None:
    """The shared guard idiom: bool is not an int here, and no other version reads."""
    for bad in (2, "1", True):
        data = _loop_fixture_dict()
        data["schemaVersion"] = bad
        with pytest.raises(RuntimeError, match="schemaVersion"):
            ce.load_loop_outcome_fixture(_write_loop_fixture(tmp_path, data))


def test_loop_loader_rejects_branch_shaped_keys(tmp_path: Path) -> None:
    """NOT a mirror of verify-fix-reverify.json: branch keys are unknown keys here."""
    data = _loop_fixture_dict()
    data["servedStage"] = "forge-1-prd"
    with pytest.raises(RuntimeError, match="servedStage"):
        ce.load_loop_outcome_fixture(_write_loop_fixture(tmp_path, data))
    data = _loop_fixture_dict()
    data["scenarios"][0]["expectedCommands"] = []
    with pytest.raises(RuntimeError, match="expectedCommands"):
        ce.load_loop_outcome_fixture(_write_loop_fixture(tmp_path, data))


def test_loop_loader_rejects_a_complete_or_foreign_outcome(tmp_path: Path) -> None:
    """`complete` routes a handoff, not the relaunch; a non-loop outcome is foreign."""
    for bad, match in (
        ("complete", "post-run facts"),
        ("passed", "not a forge-5-loop outcome"),
    ):
        data = _loop_fixture_dict()
        data["scenarios"][0]["outcome"] = bad
        with pytest.raises(RuntimeError, match=match):
            ce.load_loop_outcome_fixture(_write_loop_fixture(tmp_path, data))


def test_loop_truth_fences_the_relaunch_and_ends_with_the_sentinel(
    loop_fixture: dict, loop_truth: dict
) -> None:
    scenario = loop_fixture["scenarios"][0]
    assert loop_truth["directives"]["primaryCommand"] == scenario["expectedPrimaryCommand"]
    assert loop_truth["nextSteps"].rstrip().endswith(ce.SENTINEL)
    assert f"```\n{scenario['expectedPrimaryCommand']}\n```" in loop_truth["nextSteps"]


def test_loop_fixture_repo_holds_the_recovery_facts(
    tmp_path: Path, loop_fixture: dict
) -> None:
    """The prompt's stated facts are on disk: an applied decision and a clean tree."""
    root = tmp_path / "loop-run"
    root.mkdir()
    ce.build_loop_outcome_fixture(root, loop_fixture)
    record = json.loads(
        (root / "specs" / loop_fixture["feature"] / ".rauf" / "forge-decisions.json").read_text()
    )
    entry = record["decisions"][-1]
    assert entry["itemId"] == ce.LOOP_FIXTURE_DECISION_ITEM
    assert entry["appliedAt"] is not None
    proc = subprocess.run(
        ["git", "-C", str(root), "status", "--porcelain"], capture_output=True, text=True
    )
    assert proc.returncode == 0 and proc.stdout.strip() == ""


def test_a_compliant_loop_close_scores_all_criteria(
    loop_fixture: dict, loop_truth: dict
) -> None:
    scenario = loop_fixture["scenarios"][0]
    text = "The recovery held and the counts are authoritative.\n\n" + loop_truth["nextSteps"]
    transcript = {"ok": True, "final_text": text, "assistant_texts": [text]}
    criteria = ce.score_loop_outcome(transcript, loop_truth, scenario)
    assert tuple(criteria) == ce.LOOP_OUTCOME_CRITERIA
    assert all(criteria.values()), criteria


def test_trailing_text_after_the_loop_sentinel_fails(
    loop_fixture: dict, loop_truth: dict
) -> None:
    scenario = loop_fixture["scenarios"][0]
    text = loop_truth["nextSteps"] + "\n\nLet me know if you'd like me to continue!"
    transcript = {"ok": True, "final_text": text, "assistant_texts": [text]}
    criteria = ce.score_loop_outcome(transcript, loop_truth, scenario)
    assert criteria["exactly_one_sentinel"] is True
    assert criteria["nothing_after_sentinel"] is False


def test_a_duplicated_loop_block_fails_the_single_sentinel_criterion(
    loop_fixture: dict, loop_truth: dict
) -> None:
    scenario = loop_fixture["scenarios"][0]
    transcript = {
        "ok": True,
        "final_text": loop_truth["nextSteps"],
        "assistant_texts": [loop_truth["nextSteps"], loop_truth["nextSteps"]],
    }
    criteria = ce.score_loop_outcome(transcript, loop_truth, scenario)
    assert criteria["exactly_one_sentinel"] is False


def test_a_drifted_loop_primary_is_a_harness_defect_not_a_model_miss(
    loop_fixture: dict, loop_truth: dict
) -> None:
    scenario = dict(loop_fixture["scenarios"][0])
    scenario["expectedPrimaryCommand"] = f"/feature-forge:forge {loop_fixture['feature']}"
    transcript = {"ok": True, "final_text": "x", "assistant_texts": ["x"]}
    with pytest.raises(RuntimeError, match="drifted"):
        ce.score_loop_outcome(transcript, loop_truth, scenario)


def test_loop_prompt_supplies_the_facts_not_the_conclusion(loop_fixture: dict) -> None:
    """The ladder must supply the outcome word; the prompt states only what is true."""
    prompt = ce.loop_outcome_prompt(loop_fixture, loop_fixture["scenarios"][0])
    assert "resolved" not in prompt.lower()
    assert "Step 7" in prompt


def test_loop_probe_reports_its_scenario_as_its_own_variant() -> None:
    reports = ce.run_loop_outcome_probe(["model-x"], 0)  # n=0 drives no session
    assert [(r.probe, r.variant) for r in reports] == [("loop-outcome", "resolved-resume")]
    assert all(report.runs == 0 and report.rate is None for report in reports)
