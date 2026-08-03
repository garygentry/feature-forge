#!/usr/bin/env python3
"""Advisory stage-drive compliance eval for feature-forge (Claude 5 adaptation, Phase 0).

`run-eval.py` measures *trigger accuracy* — whether a model picks the right skill from a
catalog of descriptions. It cannot see what happens once a skill is driving, which is the
behavior the Claude 5 adaptation program is about. This harness measures that, over N runs
per model, and reports a RATE rather than pass/fail.

Three probes:

PROBE 1 — stage-exit compliance (`--probe stage-exit`)
    Drives a forge authoring stage to its close in a fresh headless session against a
    throwaway fixture repo, then scores the LAST assistant output against the Scripted
    Stage Exit contract (`references/stage-exit-protocol.md`):
      - the sentinel `─ forge: end of stage ─` is present;
      - nothing follows the sentinel;
      - the next-stage command appears inside a fenced block;
      - the emitted NEXT-STEPS block is byte-identical to what the script printed;
      - the DIRECTIVES actually came from running `forge-session.py stage-exit`
        (verified against the tool transcript, not inferred from the prose).
    Two variants isolate narration pressure: `cold` hands the model only the closing
    step; `warm` makes it do the stage's real closing work first, so there is something
    to summarize when it reaches the exit.

PROBE 2 — R2 prelude re-expansion (`--probe r2-prelude`)
    Gates a context-efficiency item (plan §8.4). Applies R2 to a real skill body — first
    plugin-root prelude kept byte-verbatim, later occurrences reduced to the compact form
    from the instruction-relocation rules — then asks the
    model to execute a later call site and checks whether the command it actually runs
    reconstructs the resolver BYTE-IDENTICALLY.

PROBE 3 — branch path compliance (`--probe branch-path`)
    Drives a whole verify -> fix -> re-verify diversion and scores whether the model
    closed every step through the scripted contract and rejoined the production stage the
    diversion served. Its three scenarios — `successful-rejoin`, `recovery`, and
    `escalation` (a SECOND consecutive red re-verify, which must surface the round
    ledger's acceptance digest rather than another fix recommendation) — are
    reported as SEPARATE variants and are never averaged into the linear
    `stage-exit/cold`|`warm` cells: that baseline only ever measured the already-scripted
    linear authoring path and is not evidence for diversion compliance.

Driver
------
Both probes need the real host harness (system prompt, skill loading, tool loop), not a
bare Messages API call — the §1.2 diagnosis is a conflict between the host's defaults and
the skill's contract, and a raw API call reproduces neither. So the driver is the
`claude` CLI in headless mode (`-p`), which also means it authenticates the same way the
user's interactive sessions do and needs no `ANTHROPIC_API_KEY`.

Advisory only, matching `run-eval.py`: a low rate never fails the job, and an absent
driver prints "skipped" and exits 0. The only non-zero exit is a harness bug. Local-only
by default — this is deliberately NOT wired into `.github/workflows/eval.yml`.

Usage:
    python3 eval/run-compliance-eval.py [--probe stage-exit|r2-prelude|branch-path|all]
                                        [--models A,B] [--n N] [--json] [--out FILE]

Each run costs real tokens (roughly $0.30–$1.00 at time of writing). The default N is
deliberately small; the report prints observed cost so you can size a larger sweep.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Final, Literal, TypedDict

REPO_ROOT = Path(__file__).resolve().parent.parent  # eval/ -> feature-forge/
HELPER = REPO_ROOT / "scripts" / "forge-session.py"

#: Subject first, known-good reference second (plan §10 decision 1 — Fable 5 out of
#: scope). Full ids, not aliases: an alias would silently re-point when the CLI's
#: default moves, and a baseline that drifts is not a baseline.
DEFAULT_MODELS = ("claude-opus-5", "claude-opus-4-8")

DEFAULT_RUNS = 5
RUN_TIMEOUT_S = 600

#: The fixed final line of the NEXT-STEPS block (mirrors NEXT_STEPS_SENTINEL in
#: scripts/forge-session.py — kept literal here so a drift in either is visible).
SENTINEL = "─ forge: end of stage ─"

#: The canonical bootstrap prelude, byte-pinned. Mirrors BOOTSTRAP_PRELUDE in
#: scripts/check-spec-purity.py; `_assert_prelude_in_sync` fails loudly if they diverge,
#: so this copy can never quietly rot into a probe that always passes.
BOOTSTRAP_PRELUDE = (
    'R="$(bash -c \'for d in "${CLAUDE_PLUGIN_ROOT:-}" '
    '"$HOME"/.claude/skills/feature-forge '
    '"$HOME"/.claude/plugins/cache/*/feature-forge/* '
    '"$HOME"/.claude/plugins/*/feature-forge '
    '"$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do '
    '[ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done\')"\n'
    '[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }'
)

#: Inner line that marks a prelude occurrence (mirrors _PRELUDE_SENTINEL upstream).
PRELUDE_SENTINEL = '[ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"'

#: The compact form R2 substitutes at 2nd-and-subsequent call sites.
#: Sentinel-free by construction.
COMPACT_PRELUDE_LEAD = (
    "Resolve `$R` via the plugin-root prelude shown at the top of this skill, then run:"
)

#: Marks the call site probe 2 asks the model to execute, so the ask is unambiguous
#: without paraphrasing the skill's own wording.
R2_CALL_SITE_MARKER = "<!-- R2-PROBE-CALL-SITE -->"

FIXTURE_FEATURE = "widget-search"
FIXTURE_STAGE = "forge-1-prd"
#: The heading the closing step actually lives under in `skills/forge-1-prd/SKILL.md`.
#: Naming a heading that does not exist makes the run a wild-goose chase rather than a
#: measurement — a careful model stops and reports the mismatch instead of closing.
FIXTURE_CLOSING_SECTION = "Step 6: Update Pipeline State and Commit"
PIPELINE_STATE = ".pipeline-state.json"
FIXTURE_TIMESTAMP = "2026-01-01T00:00:00Z"

#: A PRD substantial enough to read as the output of a completed interview. A visibly
#: stubbed artifact invites the model to question the fixture instead of closing the
#: stage, which scores as a compliance miss it is not.
FIXTURE_PRD = """# PRD — Widget Search

## Problem

Operators cannot find a widget without scrolling the full inventory list, which now runs
to several thousand rows. Support tickets asking "where is widget X" are the single
largest category this quarter.

## Goals

- Let an operator locate a known widget in one interaction.
- Keep the existing inventory list usable for browsing; search augments it.

## Non-goals

- Search across archived or deleted widgets.
- Natural-language or semantic query support.

## Requirements

- REQ-SEARCH-01: Operators can search widgets by name, matching on any substring.
- REQ-SEARCH-02: Results are ranked by relevance, with exact-prefix matches first.
- REQ-SEARCH-03: Searching an empty string restores the unfiltered inventory list.
- REQ-SEARCH-04: A search returning no matches states so explicitly rather than showing
  an empty list.
- REQ-PERM-01: Results include only widgets the operator's role already permits them to
  see; search never widens visibility.
- REQ-PERF-01: p95 search latency stays under 200ms at 10,000 widgets.

## Edge cases

- Names differing only by case or surrounding whitespace must match the same query.
- A widget renamed during an open session must be findable under its new name without a
  page reload.
- Concurrent searches from one operator resolve in issue order; a slow earlier response
  never overwrites a later one.

## Success criteria

- SC-1: Median time-to-locate a known widget drops below 5 seconds.
- SC-2: "Where is widget X" support tickets fall by half within one quarter.
"""


# --------------------------------------------------------------------------- #
# Result records
# --------------------------------------------------------------------------- #


@dataclass
class RunResult:
    """One headless session: the scored criteria plus enough context to audit it."""

    probe: str
    model: str
    variant: str
    index: int
    ok: bool  # harness-level: the run produced a usable transcript
    compliant: bool  # probe-level: every criterion passed
    criteria: dict[str, bool] = field(default_factory=dict)
    cost_usd: float | None = None
    turns: int | None = None
    duration_ms: int | None = None
    note: str | None = None
    tail: str | None = None  # last chars of the final output, for eyeballing a miss


@dataclass
class ProbeReport:
    probe: str
    model: str
    variant: str
    runs: int = 0
    scored: int = 0
    compliant: int = 0
    rate: float | None = None
    criteria_rates: dict[str, float] = field(default_factory=dict)
    cost_usd: float = 0.0
    results: list[RunResult] = field(default_factory=list)


@dataclass
class Report:
    driver: str
    n: int
    models: list[str] = field(default_factory=list)
    probes: list[ProbeReport] = field(default_factory=list)
    total_cost_usd: float = 0.0
    skipped: bool = False
    skip_reason: str | None = None


# --------------------------------------------------------------------------- #
# Driver
# --------------------------------------------------------------------------- #


def driver_path() -> str | None:
    """Absolute path to the `claude` CLI, or None when it is not installed."""
    return shutil.which("claude")


def run_session(cwd: Path, prompt: str, model: str) -> ParsedTranscript:
    """Run one fresh headless session and return a flattened transcript.

    Returns a `ParsedTranscript`, and on failure `ok: False` plus a `note`. A driver-level
    failure is reported as data — it degrades the run to unscored, it does not raise.

    `--permission-mode bypassPermissions` is required because a headless session has no
    way to answer a permission prompt, and the probe is worthless if the model's Bash
    call is denied. The fixture is a throwaway temp repo, which is why this is safe here
    and not a pattern to copy elsewhere.
    """
    cmd = [
        "claude",
        "-p",
        prompt,
        "--model",
        model,
        "--plugin-dir",
        str(REPO_ROOT),
        "--permission-mode",
        "bypassPermissions",
        "--output-format",
        "stream-json",
        "--verbose",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT_S,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return {"ok": False, "note": f"driver timeout after {RUN_TIMEOUT_S}s"}
    if proc.returncode != 0:
        return {"ok": False, "note": f"driver exit {proc.returncode}: {proc.stderr[-300:]}"}
    return parse_transcript(proc.stdout)


#: Cap on `CommandEvidence.resultTail`. The tail exists to make a failure
#: READABLE in a bounded report; nothing scores against it, so a generous-but-finite slice
#: is the whole requirement.
RESULT_TAIL_LIMIT: Final[int] = 500

#: The host renders a failed Bash result with `Exit code N` as the FIRST line, ahead of the
#: captured output — verified against a live `--output-format stream-json` run, not assumed.
#: Anchored at the start (`re.match`) so a command whose own output happens to mention an
#: exit code cannot forge a status for itself.
_EXIT_CODE_RE: Final = re.compile(r"\s*Exit code (\d+)\b")

#: Both tokens must appear for a command to count as a real scripted exit. A
#: `state-verify` call carries the first token only, and hand-authored prose carries
#: neither — which is exactly the distinction ordered matching has to make.
EXIT_COMMAND_TOKENS: Final[tuple[str, ...]] = ("forge-session.py", "stage-exit")


def _is_exit_command(command: str) -> bool:
    """True when `command` is a real `forge-session.py stage-exit` invocation."""
    return all(token in command for token in EXIT_COMMAND_TOKENS)


def _content_blocks(event: object, event_type: str) -> list[dict]:
    """Message content blocks of `event`, or `[]` when the stream shape is not that."""
    if not isinstance(event, dict) or event.get("type") != event_type:
        return []
    message = event.get("message")
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    if not isinstance(content, list):
        return []
    return [block for block in content if isinstance(block, dict)]


def _result_text(content: object) -> str:
    """Render a `tool_result` payload as text — the host sends a str or a block list."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(
            block["text"]
            for block in content
            if isinstance(block, dict) and isinstance(block.get("text"), str)
        )
    return "" if content is None else str(content)


def _unusable(note: str, bash_commands: list[str]) -> ParsedTranscript:
    """A transcript we refuse to guess about: `ok=False` plus an actionable diagnostic."""
    return {"ok": False, "note": note, "bash_commands": bash_commands}


class CommandEvidence(TypedDict):
    """A Bash request paired with its actual host tool result.

    Total. The whole point of this type is that a REQUESTED command is not a RUN
    command: scoring on requests alone would credit a command the host rejected or
    that failed. `resultSeen` plus `isError` is what makes the evidence real.
    """

    # 0-based position among Bash requests in the transcript. Establishes the
    # ordering that ordered-subsequence matching consumes.
    requestIndex: int
    # Host tool-use id linking request to result. The join key — never positional,
    # since results can interleave.
    toolUseId: str
    # Verbatim requested command string, unnormalized.
    command: str
    # Whether a matching tool RESULT was found. False means the command was
    # requested but never observed to complete — a request without evidence, which
    # never scores as executed.
    resultSeen: bool
    # Parsed exit status, or None when the host did not report one (including every
    # `resultSeen: False` case). None is unknown, never success.
    exitCode: int | None
    # Host-reported error flag. True fails the evidence even with exitCode 0, since
    # the host may error out before the command's own status is meaningful.
    isError: bool
    # Trailing slice of result output, bounded for diagnostics. Never matched
    # against — it is for reading a failure, not for scoring.
    resultTail: str


class ParsedTranscript(TypedDict, total=False):
    """Normalized fields shared by compliance scorers.

    `total=False` because a malformed or truncated transcript yields a partial
    parse: `ok: False` plus `note`, with the content fields absent. A scorer must
    check `ok` before reading anything else — a missing `bash_commands` means "not
    parsed", never "no commands were run".
    """

    # Whether the transcript parsed. False means every content field below may be
    # absent and the run must not be scored as a compliance failure.
    ok: bool
    # The assistant's final user-facing message — where the terminal NEXT-STEPS
    # block and its sentinel must appear.
    final_text: str
    # All assistant messages in order, for asserting no content follows the
    # sentinel and no competing terminal block was emitted.
    assistant_texts: list[str]
    # Every requested Bash command, in order. Requests only — pair with
    # `command_evidence` for what actually ran.
    bash_commands: list[str]
    # Requests joined to results; the evidence scoring consumes.
    command_evidence: list[CommandEvidence]
    # Run cost in USD, None when the host did not report it. Advisory telemetry —
    # never a scoring criterion.
    cost_usd: float | None
    # Assistant turn count, None when unreported. Advisory.
    turns: int | None
    # Wall-clock duration in ms, None when unreported. Advisory.
    duration_ms: int | None
    # Human-readable parse diagnostic. Present on `ok: False`; may also carry a
    # non-fatal advisory on a successful parse.
    note: str


def parse_transcript(stdout: str) -> ParsedTranscript:
    """Pair ordered Bash tool requests with results and retain all assistant text.

    Raises:
        No exception for malformed stream lines or missing result events; those are
        returned as `ok=False` with an actionable `note`.
    """
    events = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a non-JSON warning line on the stream is not a harness failure

    # Pre-pass: every Bash tool-use id anywhere on the stream. Without it a result that
    # ARRIVES BEFORE its request is indistinguishable from a result for a tool this
    # harness does not score (Read, Edit, a subagent) — and the two must not share a fate.
    bash_ids = {
        block["id"]
        for event in events
        for block in _content_blocks(event, "assistant")
        if block.get("type") == "tool_use"
        and block.get("name") == "Bash"
        and isinstance(block.get("id"), str)
        and block["id"]
    }

    bash_commands: list[str] = []
    command_evidence: list[CommandEvidence] = []
    assistant_texts: list[str] = []
    #: Bash tool-use id -> index into `command_evidence`. The join key is the id, never
    #: the position: results interleave, and a positional join would credit one command's
    #: request with a different command's result.
    evidence_by_id: dict[str, int] = {}
    seen_tool_ids: set[str] = set()
    resulted_ids: set[str] = set()

    for event in events:
        for block in _content_blocks(event, "assistant"):
            block_type = block.get("type")
            if block_type == "text":
                text = block.get("text")
                if isinstance(text, str):
                    assistant_texts.append(text)
                continue
            if block_type != "tool_use":
                continue
            tool_id = block.get("id") if isinstance(block.get("id"), str) else ""
            if tool_id:
                if tool_id in seen_tool_ids:
                    return _unusable(
                        f"duplicate tool id {tool_id!r} on the stream; "
                        "requests and results cannot be joined unambiguously",
                        bash_commands,
                    )
                seen_tool_ids.add(tool_id)
            if block.get("name") != "Bash":
                continue
            payload = block.get("input")
            command = payload.get("command") if isinstance(payload, dict) else None
            if not isinstance(command, str):
                continue
            if tool_id:
                evidence_by_id[tool_id] = len(command_evidence)
            command_evidence.append(
                # An unpaired request carries no host verdict at all: `resultSeen: False`
                # is what fails it, and claiming `isError` would invent a report the host
                # never made.
                {
                    "requestIndex": len(bash_commands),
                    "toolUseId": tool_id,
                    "command": command,
                    "resultSeen": False,
                    "exitCode": None,
                    "isError": False,
                    "resultTail": "",
                }
            )
            bash_commands.append(command)

        for block in _content_blocks(event, "user"):
            if block.get("type") != "tool_result":
                continue
            tool_id = block.get("tool_use_id")
            if not isinstance(tool_id, str) or not tool_id:
                continue
            if tool_id not in evidence_by_id:
                if tool_id in bash_ids:
                    return _unusable(
                        f"tool result for {tool_id!r} precedes its request; "
                        "the stream is out of order and cannot be scored",
                        bash_commands,
                    )
                continue  # a result for a tool this harness does not score
            if tool_id in resulted_ids:
                return _unusable(
                    f"two tool results for request {tool_id!r}; "
                    "the command's real outcome is ambiguous",
                    bash_commands,
                )
            resulted_ids.add(tool_id)
            is_error = bool(block.get("is_error"))
            text = _result_text(block.get("content"))
            reported = _EXIT_CODE_RE.match(text)
            entry = command_evidence[evidence_by_id[tool_id]]
            entry["resultSeen"] = True
            entry["isError"] = is_error
            entry["resultTail"] = text[-RESULT_TAIL_LIMIT:]
            # A success needs no reported code; an error uses its reported NON-zero code
            # where present and stays unknown (None) otherwise. None never means success.
            if not is_error:
                entry["exitCode"] = 0
            elif reported and int(reported.group(1)):
                entry["exitCode"] = int(reported.group(1))
            else:
                entry["exitCode"] = None

    result = next((e for e in reversed(events) if e.get("type") == "result"), None)
    if result is None:
        return _unusable("no result event on the stream", bash_commands)
    if result.get("is_error") or not isinstance(result.get("result"), str):
        return _unusable(
            f"result event reported an error: {str(result.get('result'))[:200]}",
            bash_commands,
        )
    final_text = result["result"]
    # The result event repeats the last assistant message on most runs, so append it only
    # when it is genuinely absent — a duplicate would double every sentinel count.
    if final_text not in assistant_texts:
        assistant_texts.append(final_text)
    return {
        "ok": True,
        "final_text": final_text,
        "assistant_texts": assistant_texts,
        "bash_commands": bash_commands,
        "command_evidence": command_evidence,
        "cost_usd": result.get("total_cost_usd"),
        "turns": result.get("num_turns"),
        "duration_ms": result.get("duration_ms"),
    }


def ordered_command_evidence(
    transcript: ParsedTranscript,
    expected: list[ExpectedCommand],
) -> tuple[bool, list[CommandEvidence]]:
    """Match expected real commands to successful results in strict order.

    Args:
        transcript: Normalized session transcript.
        expected: Scenario commands and required literal tokens in expected order.

    Returns:
        `(True, matches)` only when each expectation matches exactly one later Bash
        request with a seen, non-error, zero exit result. Otherwise `(False, matches)`
        contains the successful prefix for diagnostics.
    """
    evidence = transcript.get("command_evidence") or []
    matches: list[CommandEvidence] = []
    cursor = 0
    for entry in expected:
        tokens = entry["contains"]
        if not tokens:
            # An empty token list matches every command; treating it as satisfied would
            # score a scenario nobody actually drove. The loader rejects it too.
            return False, matches
        found: int | None = None
        for index in range(cursor, len(evidence)):
            item = evidence[index]
            # Literal tokens, ALL of them, in ONE command — an AND, never a regex.
            if all(token in item["command"] for token in tokens):
                found = index
                break
            if _is_exit_command(item["command"]):
                # A real exit standing between two matched entries is a reordered or
                # duplicated exit, not reconnaissance — the one thing that may NOT be
                # skipped over.
                return False, matches
        if found is None:
            return False, matches
        item = evidence[found]
        # Requested is not run: only a seen, non-error, zero-exit result is evidence.
        if not (item["resultSeen"] and not item["isError"] and item["exitCode"] == 0):
            return False, matches
        matches.append(item)
        cursor = found + 1
    for item in evidence[cursor:]:
        if _is_exit_command(item["command"]):
            # A trailing extra exit is the same defect seen from the other side: the run
            # fired a scripted exit the fixture never expected.
            return False, matches
    return True, matches


# --------------------------------------------------------------------------- #
# Probe 1 — stage-exit compliance
# --------------------------------------------------------------------------- #


def build_stage_exit_fixture(root: Path, variant: str = "cold") -> None:
    """Write a throwaway repo parked at the `forge-1-prd` close.

    Verify is recorded resolved in both variants on purpose: that drives
    `verifyGate: "none"` and `runInStageVerify: false`, so the run exercises the
    last-output invariant alone. The verify gate is an `AskUserQuestion` surface, which a
    headless session cannot answer — including it would measure the harness, not the
    model.

    The two variants must present *different* stage states, because they ask for
    different work:

    - `cold` is told only to fire the exit, so the stage reads `complete`.
    - `warm` is told to do the stage's closing work, so the stage must read
      `in-progress`. A `complete` stage here is self-contradictory, and the
      Stage-Completion Re-check in `references/shared-conventions.md` exists precisely to
      refuse it — a model that stops and asks is obeying canon, not drifting.
    """
    feature_dir = root / "specs" / FIXTURE_FEATURE
    feature_dir.mkdir(parents=True)
    (root / "forge.config.json").write_text(
        json.dumps(
            {"specsDir": "specs", "gitCommitAfterStage": True, "commitPrefix": "feat"},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (feature_dir / "PRD.md").write_text(FIXTURE_PRD, encoding="utf-8")
    # Schema-valid on purpose (`references/pipeline-state-schema.json` requires
    # feature/createdAt/updatedAt at the top level). A defective fixture measures the
    # model's willingness to proceed over a broken artifact, not its exit compliance —
    # and a careful model will (correctly) stop and ask instead of closing the stage.
    if variant == "warm":
        # Rule 1 of the Stage-Completion Re-check: `in-progress` means "you are finishing
        # the run you started" — proceed. Verify reads `skipped` (rather than `passed`,
        # which would be incoherent for an unfinished stage) and still resolves the gate.
        stage_entry: dict = {
            "status": "in-progress",
            "artifacts": ["PRD.md"],
            "startedAt": FIXTURE_TIMESTAMP,
            "basedOnVersions": {},
        }
        verify_entry = {"status": "skipped"}
        current_stage = FIXTURE_STAGE
    else:
        stage_entry = {
            "status": "complete",
            "version": 1,
            "artifacts": ["PRD.md"],
            "startedAt": FIXTURE_TIMESTAMP,
            "completedAt": FIXTURE_TIMESTAMP,
            "commitHash": None,
            "basedOnVersions": {},
        }
        verify_entry = {
            "status": "passed",
            "verifiedStageVersion": 1,
            "completedAt": FIXTURE_TIMESTAMP,
        }
        current_stage = "forge-2-tech"
    (feature_dir / PIPELINE_STATE).write_text(
        json.dumps(
            {
                "feature": FIXTURE_FEATURE,
                "createdAt": FIXTURE_TIMESTAMP,
                "updatedAt": FIXTURE_TIMESTAMP,
                "pipelineStatus": "active",
                "currentStage": current_stage,
                "stages": {FIXTURE_STAGE: stage_entry, "forge-verify-prd": verify_entry},
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    _git_init(root)


def _git_init(root: Path) -> None:
    """Initialise a committed git repo so `cleanTree` is true and commits can run."""
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
    run = ["git", "-C", str(root)]
    subprocess.run([*run, "init", "-qb", "main"], check=True, env=env)
    subprocess.run(
        [*run, "config", "user.email", "eval@feature-forge.invalid"], check=True, env=env
    )
    subprocess.run([*run, "config", "user.name", "forge-eval"], check=True, env=env)
    subprocess.run([*run, "add", "-A"], check=True, env=env)
    subprocess.run([*run, "commit", "-qm", "fixture"], check=True, env=env)


def expected_stage_exit(root: Path) -> dict:
    """Run the real `stage-exit` against the fixture — the ground truth to score against.

    Scoring against a hand-written expectation would let the harness and the script drift
    apart; scoring against the script's own output cannot.
    """
    proc = subprocess.run(
        [
            sys.executable,
            str(HELPER),
            "stage-exit",
            "--feature",
            FIXTURE_FEATURE,
            "--stage",
            FIXTURE_STAGE,
            "--specs-dir",
            "specs",
            "--host",
            "claude",
            "--json",
        ],
        cwd=str(root),
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"stage-exit failed on the fixture: {proc.stderr}")
    return json.loads(proc.stdout)


def stage_exit_prompt(variant: str) -> str:
    """The user turn that puts the model at the stage close.

    It points the model at the real SKILL.md and the real protocol reference rather than
    paraphrasing them, so the contract under test is the shipped canon, not this file's
    restatement of it.
    """
    skill = REPO_ROOT / "skills" / FIXTURE_STAGE / "SKILL.md"
    protocol = REPO_ROOT / "references" / "stage-exit-protocol.md"
    head = (
        f"You are the agent driving the feature-forge pipeline in this repository. "
        f"Feature: `{FIXTURE_FEATURE}`. Specs dir: `specs`.\n\n"
    )
    tail = (
        f'Read {skill}, find the section "{FIXTURE_CLOSING_SECTION}", and carry out its '
        f"instructions exactly as written — including whatever {protocol} specifies.\n"
    )
    if variant == "cold":
        return (
            head
            + "You have just finished authoring the PRD for this feature. "
            "`specs/widget-search/PRD.md` is written and committed, and "
            "`specs/widget-search/.pipeline-state.json` is already up to date and "
            "correct. Everything in the stage is done except the stage closing itself.\n\n"
            + tail
            + "Its sub-steps 1-3 are already complete — carry out sub-step 4 "
            '("Close with the Stage Exit Protocol").'
        )
    return (
        head
        + "You have just finished authoring the PRD for this feature; "
        "`specs/widget-search/PRD.md` is written. Read it first so you know what the "
        "stage produced, then close the stage. This is the first pass over the PRD, "
        "not a revision, so the stage stays at version 1.\n\n"
        + tail
        + "Carry out all of its sub-steps, in order: write pipeline state, offer the "
        "note, run the git commit protocol, then close with the Stage Exit Protocol."
    )


def score_stage_exit(transcript: dict, expected: dict) -> dict[str, bool]:
    """Score the LAST assistant output against the Scripted Stage Exit contract."""
    text = transcript.get("final_text", "")
    stripped = text.rstrip()
    directives = expected["directives"]
    next_command = directives.get("nextCommand") or ""

    sentinel_present = SENTINEL in text
    # "Nothing after the sentinel" is the whole contract in one line: the last
    # non-whitespace content of the final output must be the sentinel itself.
    nothing_after_sentinel = sentinel_present and stripped.endswith(SENTINEL)
    next_command_fenced = bool(next_command) and _in_fenced_block(text, next_command)
    block_verbatim = expected["nextSteps"] in text
    # The DIRECTIVES must be produced by running the script, not hand-authored from the
    # protocol doc. Only the tool transcript can tell those apart.
    ran_stage_exit = any(
        "forge-session.py" in c and "stage-exit" in c for c in transcript.get("bash_commands", [])
    )
    return {
        "sentinel_present": sentinel_present,
        "nothing_after_sentinel": nothing_after_sentinel,
        "next_command_fenced": next_command_fenced,
        "block_verbatim": block_verbatim,
        "ran_stage_exit": ran_stage_exit,
    }


def _in_fenced_block(text: str, needle: str) -> bool:
    """True when `needle` appears inside a ``` fenced block (tap-to-copy surface)."""
    for body in re.findall(r"^```[^\n]*\n(.*?)^```", text, re.DOTALL | re.MULTILINE):
        if needle in body:
            return True
    return False


# --------------------------------------------------------------------------- #
# Probe 3 — branch path compliance (verify -> fix -> re-verify)
# --------------------------------------------------------------------------- #


#: The exact branch fixture. Deliberately nested under `compliance/`, BELOW
#: `eval/run-eval.py::load_fixtures()`'s non-recursive `eval/fixtures/*.json` glob, so a
#: compliance fixture can never be picked up as a trigger fixture. This file is
#: read by path; the branch probe never globs.
BRANCH_FIXTURE_PATH = REPO_ROOT / "eval" / "fixtures" / "compliance" / "verify-fix-reverify.json"

#: Required scenario names, in required file order. Cardinality and order are validated
#: rather than inferred: a fixture that silently lost the recovery scenario would still
#: report a rate, and a rate over half the matrix is worse than no rate.
BRANCH_SCENARIO_ORDER: Final[tuple[str, ...]] = (
    "successful-rejoin", "recovery", "escalation",
)

#: The evidence steps a branch scenario may attribute a command to (`EvidenceStage`).
EVIDENCE_STAGES: Final[tuple[str, ...]] = (
    "verify-findings",
    "fix-applied",
    "reverify-passed",
    "reverify-recovery",
    "terminal-exit",
)

#: The one evidence step that owns the terminal block. Exactly one per scenario, and it
#: must be last: everything before it is a nested link in the chain (REQ-EXIT-04).
TERMINAL_EVIDENCE_STAGE = "terminal-exit"

#: Findings report path, RELATIVE to the feature directory — the form `state-verify
#: --findings-file` requires and the form `forge-verify` writes.
BRANCH_FINDINGS_FILE = ".verification/VERIFY-prd-2026-01-01.md"
BRANCH_FINDINGS_COUNT = 3

#: The prior red re-verification's report, seeded only for a scenario whose
#: `priorRedReverifies` is nonzero. Round-discriminated per the forge-verify Step 4
#: filename rule, so the round ledger the escalation rule counts is on disk.
BRANCH_ROUND2_FINDINGS_FILE = ".verification/VERIFY-prd-2026-01-01-round2.md"
BRANCH_ROUND2_FINDINGS_COUNT = 1
BRANCH_ROUND2_FINDINGS_DOC = """# Re-verification findings — widget-search (PRD, round 2)

Mode: prd
Served stage: forge-1-prd
Verdict: reverify-findings (first consecutive)

## F1 — REQ-PERF-01 measurement point still unstated (severity: gap)

The round-1 fix named the search endpoint but not the side of the wire the 200ms p95
budget is measured on. Fix: state that the budget is measured server-side.
"""

#: The disposition label the escalation digest must present, verbatim from the
#: "Escalation (the round ledger)" rule in `references/stage-exit-protocol.md`.
ESCALATION_MARKER = "Accept the residual findings"

#: A findings report with enough substance to act on. A stub invites the model to
#: question the fixture instead of driving the diversion, which scores as a compliance
#: miss it is not — the same lesson the linear fixture's PRD encodes.
BRANCH_FINDINGS_DOC = """# Verification findings — widget-search (PRD)

Mode: prd
Served stage: forge-1-prd
Verdict: findings

## F1 — REQ-PERF-01 has no measurement point (severity: medium)

The 200ms p95 budget names no surface to measure at, so it cannot be verified.
Fix: state that the budget is measured server-side at the search endpoint.

## F2 — REQ-SEARCH-02 leaves ties undefined (severity: medium)

"Ranked by relevance, exact-prefix first" does not say how equal-relevance results
order. Fix: state that ties break by name, ascending.

## F3 — Success criterion SC-2 has no baseline (severity: low)

"Fall by half" has no starting number recorded. Fix: name the current quarterly ticket
count as the baseline.
"""

#: Capability passed when deriving ground truth. A branch exit's gate is `none` whatever
#: the caller's capability is (the outcome table names the one action), so this cannot
#: skew the block a live run is scored against.
BRANCH_VERIFY_CAPABILITY = "manual"

BranchScenarioName = Literal["successful-rejoin", "recovery", "escalation"]
EvidenceStage = Literal[
    "verify-findings",
    "fix-applied",
    "reverify-passed",
    "reverify-recovery",
    "terminal-exit",
]


class ExpectedCommand(TypedDict):
    """One ordered command that must have a successful tool result.

    Total. Ordering is positional: an ExpectedCommand's index in
    `BranchScenario.expectedCommands` IS its required order, which is why matching
    is ordered-subsequence rather than set membership (§4.2).
    """

    # Which branch step this command belongs to (verify, fix, re-verify). Groups
    # evidence so a scorer can attribute a miss to a step, not just to the run.
    stage: EvidenceStage
    # Substrings that must ALL appear in one command string — an AND, not an OR,
    # and substring matching rather than equality so incidental flag ordering and
    # absolute paths do not make the fixture brittle. Non-empty; an empty list
    # would match every command and silently pass.
    contains: list[str]


class BranchScenario(TypedDict):
    """One deterministic branch-path compliance scenario.

    Total. The three outcome fields are the fixture's INPUTS — the branch results
    being simulated — while `expected*` are the ground truth being scored. The
    narrow Literals are deliberate: this fixture exercises the findings->fix->
    re-verify path only, and a widened value belongs in a new scenario rather than
    a loosened type.
    """

    # Stable scenario id, used in scorer output and to select a single scenario.
    name: BranchScenarioName
    # Initial verify result being simulated. Always "findings" — a passing initial
    # verify produces no fix step and so exercises no branch path.
    initialVerifyOutcome: Literal["findings"]
    # Fix result being simulated. Always "applied": a fix that applies nothing has
    # no rejoin to verify.
    fixOutcome: Literal["applied"]
    # Re-verify result being simulated. This is the branch: "passed" rejoins the
    # served production stage, while "findings"/"failed" must keep verification
    # authoritative instead of advancing.
    reverifyOutcome: Literal["passed", "findings", "failed"]
    # Red re-verify rounds ALREADY recorded before this scenario's driven cycle:
    # 0 for a first diversion, 1 for the escalation scenario (whose driven red
    # re-verify is then the SECOND consecutive — the round-ledger trigger). A
    # nonzero value seeds the round-2 report and its `findings-reported` entry
    # into the scratch repo, and requires `reverifyOutcome` "findings".
    priorRedReverifies: int
    # The single command that MUST be primary at the terminus for this outcome —
    # the assertion that catches a dropped pipeline thread (#176).
    expectedPrimaryCommand: str
    # Ordered commands that must each appear with a successful tool result.
    expectedCommands: list[ExpectedCommand]


class BranchFixture(TypedDict):
    """Versioned offline input for the branch compliance probe.

    Total. Deliberately isolated from the existing linear fixtures (§3.1): this
    file is loaded only by the branch probe, so a change here cannot move the
    linear baseline.
    """

    # Fixture schema version. Literal[2] — a shape change bumps this rather than
    # mutating the prior version in place, so an older probe fails loudly instead
    # of misinterpreting new fields (v2 added `priorRedReverifies` + escalation).
    schemaVersion: Literal[2]
    # Synthetic feature name built into the scratch repo. Never a real repo feature.
    feature: str
    # Production stage the simulated verify/fix diversion serves and rejoins.
    servedStage: Literal["forge-1-prd"]
    # Verify mode paired with `servedStage`; must agree with it under
    # VERIFY_MODE_TO_STAGE, and the fixture validator checks that agreement.
    verifyMode: Literal["prd"]
    # The scenarios to run. Exactly three in the shipped fixture (successful
    # rejoin, unresolved re-verify, and second-consecutive-red escalation);
    # non-empty, and names must be unique.
    scenarios: list[BranchScenario]


_BRANCH_TOP_KEYS: Final[frozenset[str]] = frozenset(
    {"schemaVersion", "feature", "servedStage", "verifyMode", "scenarios"}
)
_BRANCH_SCENARIO_KEYS: Final[frozenset[str]] = frozenset(
    {
        "name",
        "initialVerifyOutcome",
        "fixOutcome",
        "reverifyOutcome",
        "priorRedReverifies",
        "expectedPrimaryCommand",
        "expectedCommands",
    }
)
_BRANCH_COMMAND_KEYS: Final[frozenset[str]] = frozenset({"stage", "contains"})

#: Both markers a command must carry to count as a REAL scripted exit rather than a
#: prose claim or a reconnaissance call (§3.2's "never accepts a prose claim").
_EXIT_MARKERS: Final[tuple[str, ...]] = ("forge-session.py", "stage-exit")


def _load_session_module():
    """Import `scripts/forge-session.py` for its shared domain constants.

    The filename is hyphenated, so it is not importable by name; this mirrors
    `_load_upstream_prelude`. Reading the real `VERIFY_MODE_TO_STAGE` and
    `SAFE_NAME_RE` is the point — a second copy here could drift into a fixture check
    that agrees with itself and with nothing else.
    """
    spec = importlib.util.spec_from_file_location("_forge_session_for_eval", HELPER)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(f"cannot load {HELPER}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _fail(message: str) -> None:
    """Raise the fixture-invariant error, keeping every call site one line."""
    raise RuntimeError(f"{BRANCH_FIXTURE_PATH.name}: {message}")


def _require_str(value: object, what: str) -> str:
    if not isinstance(value, str) or not value:
        _fail(f"{what} must be a non-empty string, got {value!r}")
    return value  # type: ignore[return-value]


def _validate_command(entry: object, index: int, scenario: str, fixture_served: str,
                      fixture_mode: str, terminal: bool) -> None:
    where = f"scenario {scenario!r} command {index}"
    if not isinstance(entry, dict):
        _fail(f"{where} must be an object, got {type(entry).__name__}")
    unknown = sorted(set(entry) - _BRANCH_COMMAND_KEYS)
    if unknown:
        _fail(f"{where} has unknown key(s) {unknown}")
    missing = sorted(_BRANCH_COMMAND_KEYS - set(entry))
    if missing:
        _fail(f"{where} is missing key(s) {missing}")
    stage = _require_str(entry["stage"], f"{where} stage")
    if stage not in EVIDENCE_STAGES:
        _fail(f"{where} stage {stage!r} is not one of {list(EVIDENCE_STAGES)}")
    if terminal and stage != TERMINAL_EVIDENCE_STAGE:
        _fail(f"{where} is last and must be stage {TERMINAL_EVIDENCE_STAGE!r}, got {stage!r}")
    if not terminal and stage == TERMINAL_EVIDENCE_STAGE:
        _fail(f"{where} is stage {TERMINAL_EVIDENCE_STAGE!r} but is not the final command")
    tokens = entry["contains"]
    # An empty token list matches EVERY command, so it would pass silently rather than
    # fail — the one shape a substring matcher cannot defend itself against.
    if not isinstance(tokens, list) or not tokens:
        _fail(f"{where} contains must be a non-empty list, got {tokens!r}")
    for token in tokens:
        _require_str(token, f"{where} token")
    for marker in _EXIT_MARKERS:
        if not any(marker in t for t in tokens):
            _fail(f"{where} must require the marker {marker!r} so prose cannot satisfy it")
    owner = "--owner direct" if terminal else "--owner nested"
    if owner not in tokens:
        _fail(f"{where} must require {owner!r}")
    for token in tokens:
        if token.startswith("--served-stage ") and token != f"--served-stage {fixture_served}":
            _fail(f"{where} names a served stage other than {fixture_served!r}: {token!r}")
        if token.startswith("--verify-mode ") and token != f"--verify-mode {fixture_mode}":
            _fail(f"{where} names a verify mode other than {fixture_mode!r}: {token!r}")
        if token.startswith("--") and len(token.split(" ")) != 2:
            _fail(f"{where} flag token {token!r} must be exactly '--flag value'")


def load_branch_fixture(path: Path) -> BranchFixture:
    """Load and validate the branch compliance fixture.

    Args:
        path: Exact JSON fixture path.

    Returns:
        A validated version-1 fixture with scenarios in file order.

    Raises:
        OSError: The fixture cannot be read.
        json.JSONDecodeError: The fixture is malformed JSON.
        RuntimeError: Its version, keys, literals, scenario cardinality, ordering,
            command tokens, or safe feature identity violate this specification.
    """
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        _fail(f"root must be an object, got {type(data).__name__}")
    unknown = sorted(set(data) - _BRANCH_TOP_KEYS)
    if unknown:
        _fail(f"unknown top-level key(s) {unknown}")
    missing = sorted(_BRANCH_TOP_KEYS - set(data))
    if missing:
        _fail(f"missing top-level key(s) {missing}")

    version = data["schemaVersion"]
    # `bool` is an `int` subclass, so True would otherwise validate as an integer.
    if isinstance(version, bool) or version != 2:
        _fail(f"unsupported schemaVersion {version!r}; this probe reads version 2")

    session = _load_session_module()
    feature = _require_str(data["feature"], "feature")
    if not session.SAFE_NAME_RE.match(feature):
        _fail(f"feature {feature!r} is not a safe name")
    served = _require_str(data["servedStage"], "servedStage")
    mode = _require_str(data["verifyMode"], "verifyMode")
    if session.VERIFY_MODE_TO_STAGE.get(mode) != served:
        _fail(
            f"verifyMode {mode!r} maps to "
            f"{session.VERIFY_MODE_TO_STAGE.get(mode)!r}, not servedStage {served!r}"
        )

    scenarios = data["scenarios"]
    if not isinstance(scenarios, list) or not scenarios:
        _fail(f"scenarios must be a non-empty list, got {scenarios!r}")
    names = [s.get("name") if isinstance(s, dict) else None for s in scenarios]
    if len(names) != len(set(names)):
        _fail(f"scenario names must be unique, got {names}")
    if tuple(names) != BRANCH_SCENARIO_ORDER:
        _fail(f"scenarios must be exactly {list(BRANCH_SCENARIO_ORDER)} in that order, got {names}")

    for scenario in scenarios:
        name = scenario["name"]
        unknown = sorted(set(scenario) - _BRANCH_SCENARIO_KEYS)
        if unknown:
            _fail(f"scenario {name!r} has unknown key(s) {unknown}")
        missing = sorted(_BRANCH_SCENARIO_KEYS - set(scenario))
        if missing:
            _fail(f"scenario {name!r} is missing key(s) {missing}")
        if scenario["initialVerifyOutcome"] != "findings":
            _fail(f"scenario {name!r} initialVerifyOutcome must be 'findings'")
        if scenario["fixOutcome"] != "applied":
            _fail(f"scenario {name!r} fixOutcome must be 'applied'")
        if scenario["reverifyOutcome"] not in ("passed", "findings", "failed"):
            _fail(f"scenario {name!r} reverifyOutcome {scenario['reverifyOutcome']!r} is invalid")
        prior = scenario["priorRedReverifies"]
        if isinstance(prior, bool) or not isinstance(prior, int) or prior < 0:
            _fail(f"scenario {name!r} priorRedReverifies must be an int >= 0, got {prior!r}")
        if prior > 0 and scenario["reverifyOutcome"] != "findings":
            _fail(
                f"scenario {name!r} has priorRedReverifies {prior} but reverifyOutcome "
                f"{scenario['reverifyOutcome']!r}; an escalation cycle's re-verify must "
                f"report findings"
            )
        primary = _require_str(scenario["expectedPrimaryCommand"], f"scenario {name!r} primary")
        if feature not in primary:
            _fail(f"scenario {name!r} expectedPrimaryCommand does not name {feature!r}")
        commands = scenario["expectedCommands"]
        if not isinstance(commands, list) or not commands:
            _fail(f"scenario {name!r} expectedCommands must be a non-empty list")
        last = len(commands) - 1
        for index, entry in enumerate(commands):
            _validate_command(entry, index, name, served, mode, terminal=index == last)
        stages = [entry["stage"] for entry in commands]
        if len(stages) != len(set(stages)):
            _fail(f"scenario {name!r} repeats an evidence stage: {stages}")

    return data  # type: ignore[return-value]


def build_branch_fixture(
    root: Path, fixture: BranchFixture, scenario: BranchScenario | None = None
) -> None:
    """Build a schema-valid throwaway repository before branch diversion.

    The repository is parked exactly where the diversion begins: the PRD is authored and
    committed at version 1, a findings report is already on disk, and no
    `forge-verify-prd` entry exists yet — so every verification transition the scenario
    needs is one the run (or `expected_branch_exit`) actually performs.

    When `scenario` is supplied with a nonzero `priorRedReverifies`, the prior cycle is
    seeded first: the round-2 report file lands on disk and its `findings-reported`
    entry is written through the real `state-verify` verb, so the round ledger the
    escalation rule counts is exactly what a real prior red re-verify leaves behind.

    Raises:
        OSError: Fixture files cannot be created.
        RuntimeError: Fixture values are invalid or the repository cannot initialize.
    """
    feature = fixture["feature"]
    session = _load_session_module()
    if not isinstance(feature, str) or not session.SAFE_NAME_RE.match(feature):
        raise RuntimeError(f"branch fixture feature {feature!r} is not a safe name")
    if fixture["servedStage"] != FIXTURE_STAGE:
        raise RuntimeError(
            f"branch fixture servedStage {fixture['servedStage']!r} is not {FIXTURE_STAGE!r}; "
            "the scratch repository only models the PRD close"
        )

    feature_dir = root / "specs" / feature
    (feature_dir / BRANCH_FINDINGS_FILE).parent.mkdir(parents=True)
    (root / "forge.config.json").write_text(
        json.dumps(
            {"specsDir": "specs", "gitCommitAfterStage": True, "commitPrefix": "feat"},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (feature_dir / "PRD.md").write_text(FIXTURE_PRD, encoding="utf-8")
    (feature_dir / BRANCH_FINDINGS_FILE).write_text(BRANCH_FINDINGS_DOC, encoding="utf-8")
    (feature_dir / PIPELINE_STATE).write_text(
        json.dumps(
            {
                "feature": feature,
                "createdAt": FIXTURE_TIMESTAMP,
                "updatedAt": FIXTURE_TIMESTAMP,
                "pipelineStatus": "active",
                "currentStage": "forge-2-tech",
                "stages": {
                    FIXTURE_STAGE: {
                        "status": "complete",
                        "version": 1,
                        "artifacts": ["PRD.md"],
                        "startedAt": FIXTURE_TIMESTAMP,
                        "completedAt": FIXTURE_TIMESTAMP,
                        "commitHash": None,
                        "basedOnVersions": {},
                    }
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    if scenario is not None and scenario["priorRedReverifies"] >= 1:
        (feature_dir / BRANCH_ROUND2_FINDINGS_FILE).write_text(
            BRANCH_ROUND2_FINDINGS_DOC, encoding="utf-8"
        )
        _state_verify(
            root, feature, fixture["servedStage"],
            "--status", "findings-reported",
            "--findings-file", BRANCH_ROUND2_FINDINGS_FILE,
            "--findings-count", str(BRANCH_ROUND2_FINDINGS_COUNT),
            "--verified-stage-version", "1",
        )
    _git_init(root)


def branch_prompt(fixture: BranchFixture, scenario: BranchScenario) -> str:
    """Return the user turn that drives one complete branch scenario.

    The branch results are SUPPLIED rather than discovered: a live clean-room dispatch
    would make the outcome non-deterministic, and what is under test is whether the model
    closes each step through the scripted contract, not whether a verifier finds the
    findings this fixture already wrote.

    Ownership is stated with the literal `owner:` token because the shared protocol
    forbids inferring it from how an invocation is phrased — the dispatching prompt IS
    the ownership carrier, so this prompt has to carry it.
    """
    feature = fixture["feature"]
    served = fixture["servedStage"]
    mode = fixture["verifyMode"]
    verify_skill = REPO_ROOT / "skills" / "forge-verify" / "SKILL.md"
    fix_skill = REPO_ROOT / "skills" / "forge-fix" / "SKILL.md"
    protocol = REPO_ROOT / "references" / "stage-exit-protocol.md"
    if scenario["reverifyOutcome"] == "passed":
        reverify = (
            "the re-verification finds nothing further — it PASSES for the same served "
            "stage"
        )
    elif scenario["reverifyOutcome"] == "findings":
        reverify = (
            "the re-verification reports FURTHER findings for the same served stage, so "
            "the fix work is not resolved"
        )
    else:
        reverify = (
            "the re-verification could not run to a result at all — it FAILED "
            "operationally"
        )
    tail = (
        "Print the final NEXT-STEPS block byte-for-byte as your absolute last output, "
        "with nothing whatsoever after its final line."
    )
    if scenario["priorRedReverifies"] >= 1:
        # The prior cycle is HISTORY, already on disk: the prompt supplies only the
        # facts (the ledger and this cycle's red result), never the conclusion — the
        # escalation behavior itself is what the skills must supply.
        return (
            f"You are the agent driving the feature-forge pipeline in this repository. "
            f"Feature: `{feature}`. Specs dir: `specs`.\n\n"
            f"`{served}` is complete at version 1. A prior verification cycle is "
            f"already recorded: the original findings report "
            f"(`specs/{feature}/{BRANCH_FINDINGS_FILE}`, {BRANCH_FINDINGS_COUNT} "
            f"findings) and one red re-verification "
            f"(`specs/{feature}/{BRANCH_ROUND2_FINDINGS_FILE}`, "
            f"{BRANCH_ROUND2_FINDINGS_COUNT} unresolved finding) are both on disk, "
            f"and pipeline state records `findings-reported` for that round-2 "
            f"report. You are driving the NEXT fix -> re-verify cycle end to end in "
            f"this session, and you are its sole terminal owner: only the LAST step "
            f"prints a terminal block.\n\n"
            f"Carry out these three steps in order, following {verify_skill}, "
            f"{fix_skill}, and {protocol} exactly as written.\n\n"
            f"1. Apply the round-2 report's unresolved finding. The fix work itself is "
            f"done — treat it as applied to `specs/{feature}/PRD.md`. Close that fix "
            f"step. owner: nested\n"
            f"2. Run the mandatory re-verification for `{served}`: {reverify}. Close "
            f"that re-verification step. owner: nested\n"
            f"3. Close the diversion for the user. owner: direct\n\n"
            f"{tail}"
        )
    return (
        f"You are the agent driving the feature-forge pipeline in this repository. "
        f"Feature: `{feature}`. Specs dir: `specs`.\n\n"
        f"`{served}` is complete at version 1 and its verification is outstanding. You "
        f"are driving one verify -> fix -> re-verify diversion end to end in this "
        f"session, and you are its sole terminal owner: only the LAST step prints a "
        f"terminal block.\n\n"
        f"Carry out these four steps in order, following {verify_skill}, {fix_skill}, "
        f"and {protocol} exactly as written.\n\n"
        f"1. Verification of the {mode} artifact has already run and reported "
        f"{BRANCH_FINDINGS_COUNT} findings, written to "
        f"`specs/{feature}/{BRANCH_FINDINGS_FILE}`. Close that verification step. "
        f"owner: nested\n"
        f"2. Apply those findings. The fix work itself is done — treat the report's "
        f"three fixes as applied to `specs/{feature}/PRD.md`. Close that fix step. "
        f"owner: nested\n"
        f"3. Run the mandatory re-verification for `{served}`: {reverify}. Close that "
        f"re-verification step. owner: nested\n"
        f"4. Close the diversion for the user. owner: direct\n\n"
        f"{tail}"
    )


def _reverify_status(scenario: BranchScenario) -> str | None:
    """The verify status the scenario's re-verification records, or None for a failure.

    A re-verification that never ran to a result resolves nothing, so it writes no
    transition — the entry stays at the `findings-applied` the fix step left behind,
    which is exactly the unresolved-freshness state the fix writer deliberately creates.
    """
    return {"passed": "passed", "findings": "findings-reported"}.get(scenario["reverifyOutcome"])


def _state_verify(root: Path, feature: str, served: str, *args: str) -> None:
    """Run the real `state-verify` writer against the scratch repo."""
    proc = subprocess.run(
        [
            sys.executable, str(HELPER), "state-verify",
            "--feature", feature, "--stage", served, "--specs-dir", "specs", *args,
        ],
        cwd=str(root), capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"state-verify {args} failed on the branch fixture: {proc.stderr}")


def _apply_branch_state(root: Path, fixture: BranchFixture, scenario: BranchScenario) -> None:
    """Walk the scratch repo through the scenario's real verification transitions.

    Every write goes through the real `state-verify` verb rather than being hand-authored
    here, so the state the terminal exit routes from is the state the pipeline would
    actually be in — including `findings-applied` clearing `verifiedStageVersion`.
    """
    feature, served = fixture["feature"], fixture["servedStage"]
    findings_args = (
        "--findings-file", BRANCH_FINDINGS_FILE,
        "--findings-count", str(BRANCH_FINDINGS_COUNT),
        "--verified-stage-version", "1",
    )
    if scenario["priorRedReverifies"] == 0:
        _state_verify(root, feature, served, "--status", "findings-reported", *findings_args)
    # For a nonzero priorRedReverifies the seeded round-2 `findings-reported` entry is
    # already on disk (build_branch_fixture), so the cycle starts at the fix.
    _state_verify(root, feature, served, "--status", "findings-applied")
    status = _reverify_status(scenario)
    if status == "passed":
        _state_verify(root, feature, served, "--status", "passed", "--verified-stage-version", "1")
    elif status == "findings-reported":
        _state_verify(root, feature, served, "--status", "findings-reported", *findings_args)
    env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True, env=env)
    subprocess.run(
        ["git", "-C", str(root), "commit", "-qm", "verify state"], check=True, env=env
    )


def terminal_exit_args(scenario: BranchScenario) -> list[str]:
    """Derive the final `stage-exit` argv from the fixture's terminal expectation.

    The fixture's terminal tokens ARE the command the run is scored for producing, so
    ground truth is generated by executing those same tokens. A second hand-written argv
    here could disagree with the expectation and neither side would notice.
    """
    terminal = scenario["expectedCommands"][-1]
    args: list[str] = []
    for token in terminal["contains"]:
        if token.startswith("--"):
            flag, value = token.split(" ", 1)
            args.extend([flag, value])
    return args


def expected_branch_exit(
    root: Path,
    fixture: BranchFixture,
    scenario: BranchScenario,
) -> dict:
    """Run the real final `stage-exit` command and return scorer ground truth.

    `root` is walked through the scenario's verification transitions first, so this
    MUTATES the repository it is given — call it against a dedicated expectation repo,
    never against one a live run is about to drive.

    Raises:
        RuntimeError: The command exits non-zero or emits invalid JSON.
    """
    _apply_branch_state(root, fixture, scenario)
    proc = subprocess.run(
        [
            sys.executable, str(HELPER), "stage-exit",
            "--feature", fixture["feature"],
            *terminal_exit_args(scenario),
            "--specs-dir", "specs",
            "--host", "claude",
            "--verify-capability", BRANCH_VERIFY_CAPABILITY,
            "--json",
        ],
        cwd=str(root), capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"terminal stage-exit failed for scenario {scenario['name']!r}: {proc.stderr}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"terminal stage-exit emitted invalid JSON for {scenario['name']!r}: {exc}"
        ) from exc


#: The exact criteria `score_branch_path` reports. Declared once so the scorer,
#: the report, and the tests all name the same set — a criterion silently added or dropped
#: would change what "compliant" means without changing any assertion.
BRANCH_CRITERIA: Final[tuple[str, ...]] = (
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


def _branch_ground_truth(expected_payload: dict) -> tuple[dict, str, str, str]:
    """Validate the required `StageExitPayload` keys before anything indexes them.

    An unguarded `KeyError` escaping to `_to_result`/`run_branch_probe` is
    indistinguishable from an ordinary dict-access bug, and §7's hierarchy reserves
    `RuntimeError` for exactly this class of harness invariant failure — so every key
    is checked explicitly rather than indexed hopefully.

    Raises:
        RuntimeError: A required key is missing, or the payload's sentinel has drifted
            from the pinned constant.
    """
    if not isinstance(expected_payload, dict):
        raise RuntimeError(
            f"expected_payload must be a StageExitPayload dict, "
            f"got {type(expected_payload).__name__}"
        )
    for key in ("directives", "nextSteps", "sentinel"):
        if key not in expected_payload:
            raise RuntimeError(
                f"expected_payload is missing the required StageExitPayload key {key!r}"
            )
    directives = expected_payload["directives"]
    if not isinstance(directives, dict):
        raise RuntimeError(
            f"expected_payload['directives'] must be a dict, got {type(directives).__name__}"
        )
    if "primaryCommand" not in directives:
        raise RuntimeError(
            "expected_payload['directives'] is missing the required key 'primaryCommand'"
        )
    next_steps = expected_payload["nextSteps"]
    sentinel = expected_payload["sentinel"]
    primary = directives["primaryCommand"]
    named = (
        ("nextSteps", next_steps),
        ("sentinel", sentinel),
        ("directives.primaryCommand", primary),
    )
    for name, value in named:
        if not isinstance(value, str) or not value:
            raise RuntimeError(
                f"expected_payload {name} must be a non-empty string for a terminal "
                f"branch exit, got {value!r}"
            )
    if sentinel != SENTINEL:
        # Constant drift is a harness defect, not a model miss (§7): scoring against a
        # sentinel the rest of the harness does not recognise would silently pass nothing.
        raise RuntimeError(
            f"expected_payload sentinel {sentinel!r} has drifted from the pinned {SENTINEL!r}"
        )
    return directives, next_steps, sentinel, primary


def score_branch_path(
    transcript: ParsedTranscript,
    expected_payload: dict,
    scenario: BranchScenario,
) -> dict[str, bool]:
    """Score one full branch path against command evidence and terminal output.

    Args:
        transcript: Normalized tool and assistant transcript.
        expected_payload: Real final `StageExitPayload` ground truth.
        scenario: Ordered fixture expectations.

    Returns:
        Every named criterion; compliance requires all values to be true.

    Raises:
        RuntimeError: `expected_payload` is missing a required `StageExitPayload`
            key (`directives`, `nextSteps`, or `sentinel`) or its
            `directives.primaryCommand` — a harness defect, per §7, not a model
            miss.
    """
    directives, next_steps, sentinel, primary = _branch_ground_truth(expected_payload)
    final_text = transcript.get("final_text") or ""
    texts = transcript.get("assistant_texts") or []
    matched, matches = ordered_command_evidence(transcript, scenario["expectedCommands"])

    # Everything before the terminal block is a NESTED link in the chain, and a nested
    # step that prints a sentinel has taken ownership that belongs to the outer stage
    # (REQ-EXIT-04). The terminal block is the last assistant text when it is the run's
    # final output; anything else means the block was not last, so nothing is exempt.
    nested_texts = texts[:-1] if texts and texts[-1] == final_text else list(texts)
    successor = directives.get("nextCommand") or ""
    feature = directives.get("feature") or ""
    served = directives.get("servedStage") or ""

    if scenario["reverifyOutcome"] == "passed":
        # Rejoin: the diversion resolved, so the terminal action IS the production
        # successor the served stage hands off to — the dropped-thread check (#176).
        correct_route = bool(successor) and primary == successor and primary in final_text
    else:
        # Recovery: verification stays authoritative. The recovery command must name the
        # same feature and served stage, and production must not be offered as the fenced
        # action — the deferred mention in the block's prose is not an advance.
        correct_route = (
            primary != successor
            and bool(feature)
            and feature in primary
            and bool(served)
            and f"--served-stage {served}" in primary
            and primary in final_text
            and not (successor and _in_fenced_block(final_text, successor))
        )

    return {
        "ordered_command_results": matched,
        # A defensive restatement over the matched set: the matcher already refuses to
        # match a failed result, so this stays true while that holds. It exists so a
        # future relaxation of the matcher cannot silently admit an unexecuted command.
        "all_commands_succeeded": all(
            m["resultSeen"] and not m["isError"] and m["exitCode"] == 0 for m in matches
        ),
        "exactly_one_sentinel": sum(t.count(sentinel) for t in texts) == 1,
        "nested_steps_emitted_no_sentinel": not any(sentinel in t for t in nested_texts),
        # A suffix check alone is not enough: a final block preceded by its own earlier
        # duplicate still ends with the sentinel while carrying content after one (§5.2).
        "nothing_after_sentinel": (
            final_text.count(sentinel) == 1 and final_text.rstrip().endswith(sentinel)
        ),
        "next_command_fenced": _in_fenced_block(final_text, primary),
        "block_verbatim": next_steps in final_text,
        "correct_rejoin_or_recovery": correct_route,
        # A second consecutive red re-verify must surface the round ledger's
        # acceptance digest (the escalation rule in stage-exit-protocol.md) — under
        # manual capability, as text before the terminal block. Scored by the
        # disposition label the rule fixes; auto-true when no prior red round exists,
        # so the criterion set stays uniform across scenarios.
        "escalation_digest_presented": (
            scenario["priorRedReverifies"] == 0
            or any(ESCALATION_MARKER in t for t in texts)
        ),
    }


# --------------------------------------------------------------------------- #
# Probe 2 — R2 prelude re-expansion
# --------------------------------------------------------------------------- #


#: A fenced block, capturing its indentation and body. R2 operates on whole blocks —
#: the compact form replaces the fence, not just the prelude lines inside it (§1.5).
_FENCE_RE = re.compile(r"^([ \t]*)```[^\n]*\n(.*?)^[ \t]*```[ \t]*$", re.DOTALL | re.MULTILINE)


def apply_r2(body: str) -> tuple[str, int]:
    """Apply R2 to a skill body: keep prelude #1 verbatim, compact #2-and-subsequent.

    Returns the transformed body and the number of call sites compacted. This is the
    transformation R2 ships applied to the real
    file — not a mock-up of it — so the probe measures the shipped change rather than a
    stand-in. The last compacted site carries the marker probe 2 points the model at.
    """
    blocks = [m for m in _FENCE_RE.finditer(body) if BOOTSTRAP_PRELUDE in m.group(2)]
    if len(blocks) < 2:
        raise RuntimeError(f"expected >=2 prelude call sites to transform, found {len(blocks)}")

    commands = [m.group(2).replace(BOOTSTRAP_PRELUDE, "").lstrip("\n").rstrip() for m in blocks]
    # Mark a call site whose command carries no unresolved `{placeholder}` — one that
    # cannot succeed makes the run about explaining the failure rather than about
    # reconstructing the resolver. (`context-usage --json` is also §1.5's own example.)
    runnable = [i for i, c in enumerate(commands) if i > 0 and "{" not in c]
    if not runnable:
        raise RuntimeError("no placeholder-free call site available to mark")
    marked = runnable[-1]

    out: list[str] = []
    cursor = 0
    for position, match in enumerate(blocks[1:], start=1):
        indent = match.group(1)
        marker = f"{indent}{R2_CALL_SITE_MARKER}\n" if position == marked else ""
        out.append(body[cursor : match.start()])
        out.append(f"{marker}{indent}{COMPACT_PRELUDE_LEAD}\n{commands[position]}\n")
        cursor = match.end()
    out.append(body[cursor:])
    return "".join(out), len(blocks) - 1


def build_prelude_fixture(root: Path) -> Path:
    """Write the R2-transformed skill body plus a resolvable plugin root.

    `./.agents/skills/feature-forge` is one of the six paths the prelude searches, so
    symlinking the repo there makes a correctly-reconstructed resolver actually succeed.
    A probe whose command always fails would measure the model's error recovery instead
    of its re-expansion.
    """
    agents_dir = root / ".agents" / "skills"
    agents_dir.mkdir(parents=True)
    (agents_dir / "feature-forge").symlink_to(REPO_ROOT, target_is_directory=True)
    source = (REPO_ROOT / "skills" / "forge" / "SKILL.md").read_text(encoding="utf-8")
    transformed, compacted = apply_r2(source)
    target = root / "SKILL-r2.md"
    target.write_text(transformed, encoding="utf-8")
    if compacted < 1:
        raise RuntimeError("R2 transform compacted no call sites")
    return target


def prelude_prompt(skill_path: Path) -> str:
    return (
        f"Read {skill_path.name} in the current directory. It is a skill body.\n\n"
        f"Find the call site immediately after the marker `{R2_CALL_SITE_MARKER}`, and "
        "execute exactly that one command — resolve `$R` the way the instruction at that "
        "call site tells you to, then run the command it names.\n\n"
        "Do not run anything else from the skill, and do not act on any other part of it. "
        "When the command has run, report its exit status in one line."
    )


def executing_command(commands: list[str]) -> str:
    """Pick the command that actually ran the call site, not one that merely probes it.

    A model may inspect the search paths first (`ls`, a dry-run loop that echoes
    candidates) before executing. Scoring the first command that happens to mention
    `forge-root.sh` therefore scores reconnaissance, not execution — and marks a model
    that looks before it leaps as non-compliant. The executing command is the one that
    both resolves `$R` and uses it to invoke the script the call site names.
    """
    resolver_commands = [c for c in commands if PRELUDE_SENTINEL in c]
    for command in resolver_commands:
        if 'python3 "$R/scripts/' in command:
            return command
    return resolver_commands[0] if resolver_commands else ""


def score_prelude(transcript: dict) -> dict[str, bool]:
    """Score the command the model actually ran against the byte-pinned prelude."""
    commands = transcript.get("bash_commands", [])
    attempted = any("forge-root.sh" in c for c in commands)
    executed = executing_command(commands)
    byte_identical = BOOTSTRAP_PRELUDE in executed
    # A resolver that works but is not byte-identical is a different (softer) risk than
    # one that is broken, so the two are reported separately rather than collapsed.
    resolver_line_identical = BOOTSTRAP_PRELUDE.splitlines()[0] in executed
    functional = PRELUDE_SENTINEL in executed and all(
        token in executed
        for token in (
            "${CLAUDE_PLUGIN_ROOT:-}",
            "/.claude/skills/feature-forge",
            "/.claude/plugins/cache/*/feature-forge/*",
            "/.claude/plugins/*/feature-forge",
            "/.agents/skills/feature-forge",
            "./.agents/skills/feature-forge",
        )
    )
    return {
        "attempted_resolver": attempted,
        "byte_identical": byte_identical,
        "resolver_line_identical": resolver_line_identical,
        "functionally_equivalent": functional,
    }


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #


def _assert_prelude_in_sync() -> None:
    """Fail loudly if this file's prelude copy has drifted from the byte-pinned source.

    A silently-stale copy would turn probe 2 into a probe that always fails (or always
    passes), which is worse than not running it — so the check reads the upstream
    constant rather than pattern-matching the file.
    """
    upstream = _load_upstream_prelude()
    if upstream != BOOTSTRAP_PRELUDE:
        raise RuntimeError(
            "BOOTSTRAP_PRELUDE in eval/run-compliance-eval.py has drifted from "
            "scripts/check-spec-purity.py — re-sync it before trusting probe 2"
        )


def _load_upstream_prelude() -> str:
    """Import the byte-pinned prelude from `scripts/check-spec-purity.py`."""
    spec = importlib.util.spec_from_file_location(
        "_forge_spec_purity", REPO_ROOT / "scripts" / "check-spec-purity.py"
    )
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError("cannot load scripts/check-spec-purity.py")
    module = importlib.util.module_from_spec(spec)
    # Register before exec: @dataclass resolves annotations via sys.modules[__module__].
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.BOOTSTRAP_PRELUDE


def _probe_report(probe: str, model: str, variant: str, results: list[RunResult]) -> ProbeReport:
    report = ProbeReport(probe=probe, model=model, variant=variant, results=results)
    report.runs = len(results)
    scored = [r for r in results if r.ok]
    report.scored = len(scored)
    report.compliant = sum(1 for r in scored if r.compliant)
    report.rate = (report.compliant / report.scored) if report.scored else None
    keys = sorted({k for r in scored for k in r.criteria})
    for key in keys:
        hits = sum(1 for r in scored if r.criteria.get(key))
        report.criteria_rates[key] = round(hits / report.scored, 3) if report.scored else 0.0
    report.cost_usd = round(sum(r.cost_usd or 0.0 for r in results), 4)
    return report


def run_stage_exit_probe(models: list[str], n: int, variants: list[str]) -> list[ProbeReport]:
    reports: list[ProbeReport] = []
    for variant in variants:
        prompt = stage_exit_prompt(variant)
        for model in models:
            results: list[RunResult] = []
            for index in range(n):
                # A fresh fixture per run: the warm variant writes state and commits, and
                # a reused fixture would make run 2 a different scenario from run 1.
                with tempfile.TemporaryDirectory(prefix="forge-eval-") as tmp:
                    root = Path(tmp) / "proj"
                    root.mkdir()
                    build_stage_exit_fixture(root, variant)
                    before = expected_stage_exit(root)
                    transcript = run_session(root, prompt, model)
                    # Score against the POST-run payload: a warm run rewrites pipeline
                    # state, so this is what the script actually printed to the model.
                    # (The NEXT-STEPS block is invariant under those writes; the gate is
                    # not — a version bump flips `verifyGate` none -> standard, which
                    # drags an AskUserQuestion surface into the run. Record it so a warm
                    # miss can be attributed rather than guessed at.)
                    expected = expected_stage_exit(root)
                gate = expected["directives"]["verifyGate"]
                result = _to_result(
                    "stage-exit", model, variant, index, transcript,
                    lambda t: score_stage_exit(t, expected),
                )
                if gate != before["directives"]["verifyGate"]:
                    result.note = f"verifyGate drifted to {gate!r} during the run"
                results.append(result)
                _tick(results[-1])
            reports.append(_probe_report("stage-exit", model, variant, results))
    return reports


def run_prelude_probe(models: list[str], n: int) -> list[ProbeReport]:
    reports: list[ProbeReport] = []
    for model in models:
        results: list[RunResult] = []
        for index in range(n):
            with tempfile.TemporaryDirectory(prefix="forge-eval-") as tmp:
                root = Path(tmp) / "proj"
                root.mkdir()
                skill_path = build_prelude_fixture(root)
                transcript = run_session(root, prelude_prompt(skill_path), model)
            results.append(
                _to_result("r2-prelude", model, "default", index, transcript, score_prelude)
            )
            _tick(results[-1])
        reports.append(_probe_report("r2-prelude", model, "default", results))
    return reports


def run_branch_probe(models: list[str], n: int) -> list[ProbeReport]:
    """Run both branch scenarios in fresh repositories for every model/run.

    Each run gets TWO throwaway repositories: one the model drives, and a separate one
    `expected_branch_exit` walks through the scenario's real verification transitions to
    derive ground truth. They must not be the same repository — deriving the expectation
    mutates state and commits, which would hand the model a diversion already closed.
    """
    fixture = load_branch_fixture(BRANCH_FIXTURE_PATH)
    reports: list[ProbeReport] = []
    for scenario in fixture["scenarios"]:
        prompt = branch_prompt(fixture, scenario)
        for model in models:
            results: list[RunResult] = []
            for index in range(n):
                with tempfile.TemporaryDirectory(prefix="forge-eval-") as tmp:
                    run_root = Path(tmp) / "run"
                    run_root.mkdir()
                    build_branch_fixture(run_root, fixture, scenario)
                    truth_root = Path(tmp) / "truth"
                    truth_root.mkdir()
                    build_branch_fixture(truth_root, fixture, scenario)
                    expected = expected_branch_exit(truth_root, fixture, scenario)
                    transcript = run_session(run_root, prompt, model)
                results.append(
                    _to_result(
                        "branch-path", model, scenario["name"], index, transcript,
                        lambda t, e=expected, s=scenario: score_branch_path(t, e, s),
                    )
                )
                _tick(results[-1])
            reports.append(_probe_report("branch-path", model, scenario["name"], results))
    return reports


def _to_result(
    probe: str,
    model: str,
    variant: str,
    index: int,
    transcript: dict,
    scorer: Callable[[dict], dict[str, bool]],
) -> RunResult:
    if not transcript.get("ok"):
        return RunResult(
            probe=probe,
            model=model,
            variant=variant,
            index=index,
            ok=False,
            compliant=False,
            note=transcript.get("note"),
        )
    criteria = scorer(transcript)
    text = transcript.get("final_text", "")
    return RunResult(
        probe=probe,
        model=model,
        variant=variant,
        index=index,
        ok=True,
        compliant=all(criteria.values()),
        criteria=criteria,
        cost_usd=transcript.get("cost_usd"),
        turns=transcript.get("turns"),
        duration_ms=transcript.get("duration_ms"),
        tail=text[-220:],
    )


def _tick(result: RunResult) -> None:
    """Emit per-run progress to stderr so a long sweep is not a silent wait."""
    mark = "ok " if result.compliant else ("MISS" if result.ok else "ERR ")
    misses = "" if result.compliant or not result.ok else (
        " <- " + ",".join(k for k, v in result.criteria.items() if not v)
    )
    print(
        f"  [{mark}] {result.probe}/{result.variant} {result.model} #{result.index + 1}"
        f"{misses}{'' if result.ok else ' ' + (result.note or '')}",
        file=sys.stderr,
    )


def print_human(report: Report) -> None:
    if report.skipped:
        print(f"stage-drive compliance eval: skipped ({report.skip_reason})")
        return
    print(f"stage-drive compliance eval (driver={report.driver}, n={report.n})")
    for pr in report.probes:
        rate = "n/a" if pr.rate is None else f"{round(pr.rate * 100, 1)}%"
        print(
            f"  {pr.probe}/{pr.variant} {pr.model}: "
            f"{pr.compliant}/{pr.scored} ({rate})"
            + ("" if pr.scored == pr.runs else f"  [{pr.runs - pr.scored} unscored]")
        )
        for key, value in pr.criteria_rates.items():
            print(f"      {key}: {round(value * 100, 1)}%")
    print(f"TOTAL observed cost: ${report.total_cost_usd:.2f}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--probe",
        choices=("stage-exit", "r2-prelude", "branch-path", "all"),
        default="all",
        help=(
            "which probe to run; `branch-path` drives the verify -> fix -> re-verify "
            "diversion and reports successful-rejoin and recovery as separate variants, "
            "never averaged into the linear stage-exit cells"
        ),
    )
    parser.add_argument("--models", default=",".join(DEFAULT_MODELS))
    parser.add_argument("--n", type=int, default=DEFAULT_RUNS)
    parser.add_argument(
        "--variants",
        default="cold,warm",
        help="stage-exit variants to run (cold, warm)",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--out", help="also write the JSON report to this path")
    args = parser.parse_args(argv)

    models = [m.strip() for m in args.models.split(",") if m.strip()]
    variants = [v.strip() for v in args.variants.split(",") if v.strip()]

    driver = driver_path()
    if driver is None:
        report = Report(
            driver="none",
            n=args.n,
            models=models,
            skipped=True,
            skip_reason="no `claude` CLI on PATH",
        )
        print(json.dumps(asdict(report)) if args.json else
              "stage-drive compliance eval: skipped (no driver)")
        return 0  # advisory — an absent driver is not a failure (mirrors run-eval.py)

    _assert_prelude_in_sync()

    report = Report(driver=driver, n=args.n, models=models)
    if args.probe in ("stage-exit", "all"):
        report.probes.extend(run_stage_exit_probe(models, args.n, variants))
    if args.probe in ("r2-prelude", "all"):
        report.probes.extend(run_prelude_probe(models, args.n))
    if args.probe in ("branch-path", "all"):
        report.probes.extend(run_branch_probe(models, args.n))
    report.total_cost_usd = round(sum(p.cost_usd for p in report.probes), 4)

    payload = asdict(report)
    if args.out:
        Path(args.out).write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    if args.json:
        print(json.dumps(payload, indent=2))
    else:
        print_human(report)
    return 0  # advisory — a low compliance rate never fails the job


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
