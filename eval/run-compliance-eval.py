#!/usr/bin/env python3
"""Advisory stage-drive compliance eval for feature-forge (Claude 5 adaptation, Phase 0).

`run-eval.py` measures *trigger accuracy* — whether a model picks the right skill from a
catalog of descriptions. It cannot see what happens once a skill is driving, which is the
behavior the Claude 5 adaptation program is about. This harness measures that, over N runs
per model, and reports a RATE rather than pass/fail.

Two probes:

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
    from `specs/context-efficiency/05-instruction-relocations.md` §1.5 — then asks the
    model to execute a later call site and checks whether the command it actually runs
    reconstructs the resolver BYTE-IDENTICALLY.

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
    python3 eval/run-compliance-eval.py [--probe stage-exit|r2-prelude|all]
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

#: The compact form R2 substitutes at 2nd-and-subsequent call sites
#: (`05-instruction-relocations.md` §1.5). Sentinel-free by construction.
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


def run_session(cwd: Path, prompt: str, model: str) -> dict:
    """Run one fresh headless session and return a flattened transcript.

    Returns a dict with `ok`, `final_text`, `bash_commands`, `cost_usd`, `turns`,
    `duration_ms`, and on failure a `note`. A driver-level failure is reported as data —
    it degrades the run to unscored, it does not raise.

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


def parse_transcript(stdout: str) -> dict:
    """Flatten a `--output-format stream-json` stream into the fields the scorers need."""
    events = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue  # a non-JSON warning line on the stream is not a harness failure

    bash_commands: list[str] = []
    for event in events:
        if event.get("type") != "assistant":
            continue
        for block in event.get("message", {}).get("content", []):
            if block.get("type") == "tool_use" and block.get("name") == "Bash":
                command = block.get("input", {}).get("command")
                if isinstance(command, str):
                    bash_commands.append(command)

    result = next((e for e in reversed(events) if e.get("type") == "result"), None)
    if result is None:
        return {
            "ok": False,
            "note": "no result event on the stream",
            "bash_commands": bash_commands,
        }
    if result.get("is_error") or not isinstance(result.get("result"), str):
        return {
            "ok": False,
            "note": f"result event reported an error: {str(result.get('result'))[:200]}",
            "bash_commands": bash_commands,
        }
    return {
        "ok": True,
        "final_text": result["result"],
        "bash_commands": bash_commands,
        "cost_usd": result.get("total_cost_usd"),
        "turns": result.get("num_turns"),
        "duration_ms": result.get("duration_ms"),
    }


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
# Probe 2 — R2 prelude re-expansion
# --------------------------------------------------------------------------- #


#: A fenced block, capturing its indentation and body. R2 operates on whole blocks —
#: the compact form replaces the fence, not just the prelude lines inside it (§1.5).
_FENCE_RE = re.compile(r"^([ \t]*)```[^\n]*\n(.*?)^[ \t]*```[ \t]*$", re.DOTALL | re.MULTILINE)


def apply_r2(body: str) -> tuple[str, int]:
    """Apply R2 to a skill body: keep prelude #1 verbatim, compact #2-and-subsequent.

    Returns the transformed body and the number of call sites compacted. This is the
    transformation R2 ships (`05-instruction-relocations.md` §1.5) applied to the real
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
        "--probe", choices=("stage-exit", "r2-prelude", "all"), default="all"
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
