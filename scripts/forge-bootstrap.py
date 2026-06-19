#!/usr/bin/env python3
"""Scaffold a brand-new empty repository to a pipeline-ready, green baseline.

The deterministic core of forge-bootstrap: the greenfield gate + recovery
detection, git init, template-driven scaffold emission, forge.config.json write,
the transient .forge-bootstrap.json resume sentinel, toolchain detection +
lint/test verification, and the exact-list baseline commit. The interview and all
human-facing output live in skills/forge-bootstrap/SKILL.md; this helper only
emits structured JSON + exit codes.

Usage:
    python3 forge-bootstrap.py check    <target-dir> [--specs-dir DIR] [--json]
    python3 forge-bootstrap.py scaffold <target-dir> --answers JSON [--json]
    python3 forge-bootstrap.py verify   <target-dir> --answers JSON [--json]
    python3 forge-bootstrap.py commit   <target-dir> --answers JSON \
        [--stage-only] [--json]
    python3 forge-bootstrap.py status   <target-dir> [--json]

Exit codes:
    0 = success: eligible / green / committed-or-staged
    1 = findings: gate refusal (eligible:false) or verify not-green
    2 = usage or IO error -- including verify toolchain-missing
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Literal, TypedDict


# --------------------------------------------------------------------------- #
# Constants (00-core-definitions.md §2, §3, §6)
# --------------------------------------------------------------------------- #

#: The five built-in stack profiles, parity with references/stacks/*.md (REQ-STACK-01).
Stack = Literal["typescript", "python", "go", "rust", "generic"]

#: Stacks that have a meaningful package-manager choice (drives REQ-INPUT-04).
#: A stack absent from this map skips the package-manager question entirely.
PACKAGE_MANAGERS: Final[dict[str, list[str]]] = {
    "typescript": ["npm", "pnpm", "yarn"],
    "python": ["uv", "poetry", "pip"],
    # go, rust, generic: no package-manager question (tech-spec §3.9 row 4).
}

#: Exact directory entries always permitted at the target repo root (00 §3).
ALLOWED_META_DIRS: Final[frozenset[str]] = frozenset({".git"})

#: The transient resume sentinel (§8) is allow-listed so a re-run over a partial
#: scaffold is routed to recovery, not refused (REQ-LIFE-02, tech-spec §3.4).
SENTINEL_FILENAME: Final = ".forge-bootstrap.json"

#: Case-insensitive filename patterns for allowed repo-meta files (REQ-GATE-01/04, OQ-02).
#: A fresh remote's auto-generated README + LICENSE must pass (REQ-GATE-04).
ALLOWED_META_FILE_RE: Final = re.compile(
    r"""^(
        README(\.md|\.txt|\.rst)?     # README, README.md, README.txt, README.rst
      | LICENSE(\.md|\.txt)?          # LICENSE, LICENSE.md, LICENSE.txt
      | \.gitignore
      | \.gitattributes
    )$""",
    re.IGNORECASE | re.VERBOSE,
)

#: Resolved verification + toolchain-probe commands per stack (00 §6). "{pm}" is
#: substituted with the member's packageManager; "{member}" with its path.
#: STACK_COMMANDS[stack] -> (typeCheckCommand-template, testCommand-template,
#: tuple-of-toolchain-probe-binaries). The single source of truth shared by
#: write_config (§4.3) and verify (§5), so config and the run agree exactly.
STACK_COMMANDS: Final[dict[str, tuple[str, str, tuple[str, ...]]]] = {
    "typescript": ("npx tsc --noEmit", "{pm} test", ("node", "{pm}")),
    "python": ("mypy .", "pytest", ("python3", "{pm}")),
    "go": ("go vet ./...", "go test ./...", ("go",)),
    "rust": ("cargo clippy", "cargo test", ("cargo",)),
    "generic": ("sh -n run.sh test.sh", "./test.sh", ("sh",)),
}


# --------------------------------------------------------------------------- #
# Type Definitions (00-core-definitions.md §4, §5, §8)
# --------------------------------------------------------------------------- #


class Member(TypedDict):
    """One package to scaffold. A single-package project has exactly one implicit member.

    Attributes:
        name: Package name. For a single package this equals the project name; for a
            monorepo member it is the user-supplied member name (REQ-MONO-01).
        path: Repo-relative directory for this member ("." for a single package;
            e.g. "packages/api" for a monorepo member). Becomes workspaces[].path.
        stack: The member's stack profile (REQ-MONO-02 allows mixed-language members).
        packageManager: The chosen package manager when the stack has a choice
            (PACKAGE_MANAGERS), else None (go/rust/generic).
    """

    name: str
    path: str
    stack: Stack
    packageManager: str | None


class Answers(TypedDict):
    """The resolved interview payload (skill → helper), mirrored into the sentinel.

    Attributes:
        projectName: Project name (REQ-INPUT-01; default inferred from the target dir).
        purpose: One-line project purpose, seeds README + config metadata (REQ-INPUT-02).
        layout: "single" or "monorepo" (REQ-INPUT-06; default "single").
        license: SPDX-ish identifier (e.g. "MIT", "Apache-2.0") or "none" (REQ-INPUT-05).
        members: One Member for a single package, ≥1 for a monorepo (REQ-MONO-01).
        modeB: True iff the user opted into pipeline hand-off (REQ-MODEB-01; default False).
        modeBTarget: "feature" or "epic" when modeB is True, else None (REQ-INPUT-07).
        ci: True iff a CI workflow should be emitted (REQ-SCAF-07, REQ-MONO-04).
        commitStyle: "commit" (single baseline commit) or "stage-only" (REQ-LIFE-05).
        author: Copyright holder for the generated LICENSE ({{AUTHOR}} token, §6.2);
            seeded from git user.name when available, else the project name (REQ-SCAF-06).
        host: The running agent host ("claude", "codex", or "other"/None). Drives the
            host-conditional agent-instruction file: AGENTS.md is always emitted; CLAUDE.md
            is additionally emitted when host == "claude" (REQ-SCAF-06).
    """

    projectName: str
    purpose: str
    layout: Literal["single", "monorepo"]
    license: str
    members: list[Member]
    modeB: bool
    modeBTarget: Literal["feature", "epic"] | None
    ci: bool
    commitStyle: Literal["commit", "stage-only"]
    author: str
    host: Literal["claude", "codex", "other"] | None


class Sentinel(TypedDict):
    """The transient `.forge-bootstrap.json` resume marker (target repo root).

    Attributes:
        version: Schema guard (const 1).
        status: "in-progress" while scaffolding; "complete" only in the instant
            between a successful verify/commit decision and sentinel removal.
        startedAt: ISO-8601 timestamp set once when the sentinel is first written.
        answers: The full interview Answers, mirrored so a resume reconstructs
            prior answers with no re-interview (REQ-LIFE-02, OQ-03).
        artifactsWritten: Repo-relative paths the helper has written so far. `scaffold`
            is idempotent over this list (skips files already recorded), enabling resume.
    """

    version: Literal[1]
    status: Literal["in-progress", "complete"]
    startedAt: str
    answers: Answers
    artifactsWritten: list[str]


class CheckResult(TypedDict):
    """Output of `check` — greenfield gate + recovery detection (REQ-GATE-01/02, REQ-LIFE-02).

    Attributes:
        eligible: True iff the target is a permitted greenfield OR a resume of
            this tool's own partial scaffold. False ⇒ greenfield refusal.
        disqualifying: Repo-relative paths that fail the allow-list. Empty when
            eligible. Drives the REQ-GATE-02 refusal message.
        hasGit: True iff the target already contains a `.git/` repository (REQ-GATE-03
            decides whether `scaffold` runs `git init`).
        resumeMarker: The parsed sentinel when one is present, else None. When
            non-None the skill routes to resume / restart / cancel (REQ-LIFE-02) rather
            than treating `eligible` as a fresh-start signal.
    """

    eligible: bool
    disqualifying: list[str]
    hasGit: bool
    resumeMarker: "Sentinel | None"


class CommandOutcome(TypedDict):
    """Result of one resolved lint or test command (REQ-SCAF-05, REQ-STACK-02).

    Attributes:
        command: The exact command string that was run (from the §6 table).
        ok: True iff the command exited 0.
        member: The member's repo-relative path the command ran for ("." for a
            single package; e.g. "packages/api" for a monorepo member).
    """

    command: str
    ok: bool
    member: str


class VerifyResult(TypedDict):
    """Output of `verify` — toolchain detection + lint/test (REQ-SCAF-05, REQ-LIFE-03/04).

    Attributes:
        toolchainPresent: True iff every required tool for the resolved stack(s) was
            found via `command -v`. False ⇒ missing-toolchain outcome (exit 2).
        lint: One CommandOutcome per resolved lint command (per member for a monorepo).
        test: One CommandOutcome per resolved test command (per member for a monorepo).
        green: True iff toolchainPresent AND every lint/test outcome is ok. The single
            predicate Mode B gates on (REQ-MODEB-04).
    """

    toolchainPresent: bool
    lint: list[CommandOutcome]
    test: list[CommandOutcome]
    green: bool


class CommitResult(TypedDict):
    """Output of `commit` — staged-or-committed baseline (REQ-LIFE-05/06, REQ-SCAF-08).

    Attributes:
        committed: True iff a baseline commit was made; False when `--stage-only` left
            the scaffold staged with no commit (REQ-LIFE-05).
        commitHash: The new commit's hash when committed, else None.
        staged: The exact list of repo-relative paths staged (the tracked artifact set;
            never via `git add -A` — REQ-SEC-02).
        sentinelRemoved: True once the sentinel was deleted before staging so it never
            enters history (REQ-SCAF-08, OQ-T3).
    """

    committed: bool
    commitHash: str | None
    staged: list[str]
    sentinelRemoved: bool


# --------------------------------------------------------------------------- #
# Internal Exceptions (02 §2)
# --------------------------------------------------------------------------- #


class UsageError(Exception):
    """A usage or I/O failure that must exit 2.

    Raised for malformed CLI arguments, unreadable/unwritable paths, a malformed
    --answers payload, git/subprocess invocation failures, and the distinct
    verify toolchain-missing outcome (00 §9). Maps to exit code 2.

    Attributes:
        message: Human-readable description printed to stderr.
    """

    def __init__(self, message: str) -> None:
        self.message = message
        super().__init__(message)


class FindingsError(Exception):
    """A non-fatal outcome that must exit 1.

    Raised for an actionable, non-error finding: a greenfield refusal
    (CheckResult.eligible == False) or a not-green verify result. Maps to exit
    code 1. Carries the structured result so the dispatch layer can emit it as
    JSON on stdout.

    Attributes:
        result: The CheckResult / VerifyResult to surface verbatim.
    """

    def __init__(self, result: dict) -> None:
        self.result = result
        super().__init__("findings")


# --------------------------------------------------------------------------- #
# Safety & I/O Layer (02 §8.1)
# --------------------------------------------------------------------------- #


def _json_text(obj: object) -> str:
    """Serialize ``obj`` to canonical JSON text with a trailing newline."""
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def _atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically via a same-dir temp file + os.replace.

    Mirrors epic-manifest.py's atomic_write, generalized to text: writes to a
    temporary file in the destination's directory, flushes + fsyncs it, then
    ``os.replace`` swaps it into place so an interrupted write never leaves a torn
    file.

    Args:
        path: The destination path (parent must already exist).
        text: The full file content to write.

    Raises:
        UsageError: If the temp file cannot be created/written or the replace
            fails (exit 2). On failure the temp file is removed.
    """
    parent = path.parent
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=parent)
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except OSError as exc:
        tmp_path.unlink(missing_ok=True)
        raise UsageError(f"atomic write to {path} failed: {exc}")


def read_sentinel(target: Path) -> "Sentinel | None":
    """Read and parse the transient resume sentinel, or None when absent (00 §8).

    Args:
        target: The project root being inspected.

    Returns:
        The parsed Sentinel when present, else None.

    Raises:
        UsageError: If the file exists but is unreadable or not valid JSON (exit 2).
    """
    path = target / SENTINEL_FILENAME
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"corrupt sentinel {path}: {exc}")


def write_sentinel(target: Path, sentinel: Sentinel) -> None:
    """Atomically write the resume sentinel to the target root (00 §8).

    Uses a same-dir temp file + os.replace so an interrupted write never leaves a
    torn marker (mirroring epic-manifest.py's atomic_write).

    Args:
        target: The project root.
        sentinel: The sentinel dict to persist.

    Raises:
        UsageError: If the write fails (exit 2).
    """
    _atomic_write_text(target / SENTINEL_FILENAME, _json_text(sentinel))


def run(
    cmd: list[str], cwd: Path, check: bool = True
) -> subprocess.CompletedProcess:
    """Run a subprocess (git / toolchain probe / lint / test) and capture output.

    A thin wrapper that captures stdout/stderr as text. With ``check=True`` a
    non-zero exit raises UsageError (exit 2) — used for git operations that must
    succeed. With ``check=False`` the CompletedProcess is returned for the caller
    to inspect ``returncode`` — used for ``command -v`` probes and lint/test, whose
    non-zero exits are data (toolchain-missing / not-green), not IO errors.

    Args:
        cmd: The argv list (never shell-joined except the explicit ``sh -c`` forms).
        cwd: The working directory (the target root or a member dir).
        check: Raise on non-zero when True; return the process when False.

    Returns:
        The CompletedProcess.

    Raises:
        UsageError: ``check`` is True and the command exited non-zero, or the
            command could not be launched (exit 2).
    """
    try:
        proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    except OSError as exc:
        raise UsageError(f"failed to run {cmd[0]!r}: {exc}")
    if check and proc.returncode != 0:
        raise UsageError(f"command {' '.join(cmd)!r} failed: {proc.stderr.strip()}")
    return proc


# --------------------------------------------------------------------------- #
# Subcommand stubs (filled by later backlog items 003/006/008/009/010)
# --------------------------------------------------------------------------- #


def check(target: Path, specs_dir: Path) -> CheckResult:
    """Run the greenfield gate + recovery detection over a target repo (02 §3).

    Stub — implemented in backlog item 003.
    """
    raise NotImplementedError("check is implemented in backlog item 003")


def scaffold(target: Path, answers: Answers) -> list[str]:
    """Emit the pipeline-ready baseline for every member, idempotently (02 §4).

    Stub — implemented in backlog item 006.
    """
    raise NotImplementedError("scaffold is implemented in backlog item 006")


def verify(target: Path, answers: Answers) -> VerifyResult:
    """Detect the toolchain and run resolved lint/test per member (02 §5).

    Stub — implemented in backlog item 008.
    """
    raise NotImplementedError("verify is implemented in backlog item 008")


def commit(target: Path, answers: Answers, stage_only: bool) -> CommitResult:
    """Stage the exact artifact list and commit or stop at staged (02 §6).

    Stub — implemented in backlog item 009.
    """
    raise NotImplementedError("commit is implemented in backlog item 009")


def status(target: Path) -> "Sentinel | None":
    """Return the parsed resume sentinel, or None when absent (02 §7).

    Stub — implemented in backlog item 010.
    """
    raise NotImplementedError("status is implemented in backlog item 010")


# --------------------------------------------------------------------------- #
# CLI Dispatch (02 §8.2)
# --------------------------------------------------------------------------- #


def _parse_answers(raw: str) -> Answers:
    """Parse the --answers JSON payload into an Answers dict (02 §8.2).

    Args:
        raw: The raw JSON string passed via --answers.

    Returns:
        The parsed Answers dict.

    Raises:
        UsageError: If the payload is not valid JSON or not an object (exit 2).
    """
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UsageError(f"malformed --answers JSON: {exc}")
    if not isinstance(parsed, dict):
        raise UsageError("--answers must be a JSON object")
    return parsed


def _dispatch(args: argparse.Namespace, target: Path) -> int:
    """Route a parsed command to its handler, translating outcomes into exit codes.

    Read-only / write commands print their result as JSON under --json. ``check``
    raises FindingsError on a greenfield refusal; ``verify`` raises UsageError on a
    missing toolchain (exit 2) or FindingsError when not green (exit 1).
    """
    cmd: str = args.cmd

    if cmd == "check":
        specs_dir = Path(args.specs_dir)
        result = check(target, specs_dir)
        if not result["eligible"] and result["resumeMarker"] is None:
            raise FindingsError(result)
        if args.json_output:
            print(_json_text(result), end="")
        return 0

    if cmd == "scaffold":
        answers = _parse_answers(args.answers)
        written = scaffold(target, answers)
        if args.json_output:
            print(_json_text({"artifactsWritten": written}), end="")
        return 0

    if cmd == "verify":
        answers = _parse_answers(args.answers)
        result = verify(target, answers)
        if not result["toolchainPresent"]:
            if args.json_output:
                print(_json_text(result), end="")
            raise UsageError("toolchain missing")
        if not result["green"]:
            raise FindingsError(result)
        if args.json_output:
            print(_json_text(result), end="")
        return 0

    if cmd == "commit":
        answers = _parse_answers(args.answers)
        result = commit(target, answers, args.stage_only)
        if args.json_output:
            print(_json_text(result), end="")
        return 0

    if cmd == "status":
        result = status(target)
        if args.json_output:
            print(_json_text(result), end="")
        return 0

    raise UsageError(f"unknown command: {cmd}")


def _build_parser() -> argparse.ArgumentParser:
    """Build the argparse parser with one subparser per subcommand (02 §8.2)."""
    parser = argparse.ArgumentParser(prog="forge-bootstrap.py", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add_json(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--json", action="store_true", dest="json_output", help="Output as JSON"
        )

    # check ----------------------------------------------------------------- #
    p_check = sub.add_parser("check", help="Greenfield gate + recovery detection")
    p_check.add_argument("target", help="Target repo directory to bootstrap")
    p_check.add_argument("--specs-dir", default="./specs", help="Specs directory")
    add_json(p_check)

    # scaffold -------------------------------------------------------------- #
    p_scaffold = sub.add_parser("scaffold", help="Emit the pipeline-ready baseline")
    p_scaffold.add_argument("target", help="Target repo directory to bootstrap")
    p_scaffold.add_argument("--answers", required=True, help="Resolved Answers JSON")
    add_json(p_scaffold)

    # verify ---------------------------------------------------------------- #
    p_verify = sub.add_parser("verify", help="Toolchain detection + lint/test")
    p_verify.add_argument("target", help="Target repo directory to verify")
    p_verify.add_argument("--answers", required=True, help="Resolved Answers JSON")
    add_json(p_verify)

    # commit ---------------------------------------------------------------- #
    p_commit = sub.add_parser("commit", help="Exact-list baseline commit")
    p_commit.add_argument("target", help="Target repo directory to commit")
    p_commit.add_argument("--answers", required=True, help="Resolved Answers JSON")
    p_commit.add_argument(
        "--stage-only", action="store_true", dest="stage_only",
        help="Stage the scaffold without committing",
    )
    add_json(p_commit)

    # status ---------------------------------------------------------------- #
    p_status = sub.add_parser("status", help="Inspect the resume sentinel")
    p_status.add_argument("target", help="Target repo directory to inspect")
    add_json(p_status)

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    target = Path(args.target)
    try:
        return _dispatch(args, target)
    except UsageError as exc:
        print(f"Error: {exc.message}", file=sys.stderr)
        return 2
    except FindingsError as exc:
        print(json.dumps(exc.result, indent=2, ensure_ascii=False))
        return 1
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
