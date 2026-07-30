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
        '"${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge',
        '"$HOME"/.claude/skills/feature-forge "${CLAUDE_PLUGIN_ROOT:-}"',
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
