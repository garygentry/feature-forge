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
    """Run the greenfield gate + recovery detection over a target repo (00 §3, §4).

    Reads only — lists the target's immediate entries and parses any sentinel; it
    never creates, modifies, or deletes a file (REQ-SEC-01). An entry is permitted
    iff it is ``.git``, the configured specs dir, the SENTINEL_FILENAME, or a
    regular file matching ALLOWED_META_FILE_RE (00 §3). Any other entry — a source
    file, a package manifest, a build/tooling config — is disqualifying
    (REQ-GATE-01) and its repo-relative path is recorded (REQ-GATE-02). A fresh
    remote's auto-generated README + LICENSE pass (REQ-GATE-04). When the sentinel
    is present the target is treated as eligible regardless of disqualifying
    entries, so a re-run over bootstrap's own partial scaffold routes to recovery
    rather than refusal (REQ-LIFE-02).

    Args:
        target: The project root being bootstrapped (the cwd, not the plugin root).
        specs_dir: The configured specs directory; its basename is the one extra
            entry permitted at the target root.

    Returns:
        A CheckResult (00 §4) with eligible / disqualifying / hasGit / resumeMarker.

    Raises:
        UsageError: If ``target`` exists but is not a directory, or its entries
            cannot be listed (exit 2).
    """
    if target.exists() and not target.is_dir():
        raise UsageError(f"target is not a directory: {target}")
    marker = read_sentinel(target)
    has_git = (target / ".git").is_dir()
    allowed_dir_names = {*ALLOWED_META_DIRS, specs_dir.name}
    disqualifying: list[str] = []
    try:
        entries = sorted(target.iterdir()) if target.is_dir() else []
    except OSError as exc:
        raise UsageError(f"cannot list target {target}: {exc}")
    for entry in entries:
        name = entry.name
        if name in allowed_dir_names and entry.is_dir():
            continue
        if name == SENTINEL_FILENAME:
            continue
        if entry.is_file() and ALLOWED_META_FILE_RE.match(name):
            continue
        disqualifying.append(name)
    eligible = (not disqualifying) or marker is not None
    return {
        "eligible": eligible,
        "disqualifying": disqualifying,
        "hasGit": has_git,
        "resumeMarker": marker,
    }


#: Repo-relative location of the bundled scaffold templates (00 §1.1). The helper
#: lives at scripts/forge-bootstrap.py, so the repo root is two levels up.
TEMPLATE_ROOT: Final = (
    Path(__file__).resolve().parent.parent
    / "skills" / "forge-bootstrap" / "references" / "templates"
)


def _sanitize_pkg(name: str) -> str:
    """Map a member name to a language-safe package identifier ({{PKG}} token).

    Lowercases, replaces any run of non-alphanumeric characters with a single
    underscore, and strips leading/trailing underscores. Kept identical across
    stacks for determinism (03 §1).
    """
    pkg = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()
    return pkg or "pkg"


def _write_artifact(
    target: Path, rel_path: str, content: str, sentinel: Sentinel
) -> None:
    """Write one scaffold artifact, idempotently and never overwriting (02 §4.1).

    Skips the write when ``rel_path`` is already recorded in artifactsWritten[]
    (resume idempotency, REQ-LIFE-02) OR when the destination already exists and was
    not written by this run — a pre-existing allowed-meta file kept verbatim
    (REQ-SCAF-09, REQ-GATE-05, REQ-SEC-01). A kept file is NOT recorded. Otherwise
    it creates parent dirs, writes atomically, appends the path, and persists the
    sentinel so an interrupt leaves a consistent resume list.
    """
    if rel_path in sentinel["artifactsWritten"]:
        return
    dest = target / rel_path
    if dest.exists():
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(dest, content)
    sentinel["artifactsWritten"].append(rel_path)
    write_sentinel(target, sentinel)


def compose_member(
    member: Member, answers: Answers, target: Path, sentinel: Sentinel
) -> None:
    """Compose one member's scaffold from its stack template dir (02 §4.2, 00 §6.2)."""
    template_root = TEMPLATE_ROOT / member["stack"]
    if not template_root.is_dir():
        raise UsageError(
            f"template dir not found for stack {member['stack']!r}: {template_root}"
        )
    pkg = _sanitize_pkg(member["name"])
    tokens = {
        "{{PROJECT_NAME}}": answers["projectName"],
        "{{PKG}}": pkg,
        "{{PM}}": member["packageManager"] or "",
        "{{PURPOSE}}": answers["purpose"],
    }
    member_base = "" if member["path"] == "." else member["path"]
    for src in sorted(p for p in template_root.rglob("*") if p.is_file()):
        rel = src.relative_to(template_root).as_posix()
        for tok, val in tokens.items():
            rel = rel.replace(tok, val)
        rel_path = rel if not member_base else f"{member_base}/{rel}"
        text = src.read_text(encoding="utf-8")
        for tok, val in tokens.items():
            text = text.replace(tok, val)
        _write_artifact(target, rel_path, text, sentinel)


def _resolve_commands(member: Member) -> tuple[str, str]:
    """Resolve a member's (typeCheckCommand, testCommand) from STACK_COMMANDS (00 §6)."""
    lint_t, test_t, _ = STACK_COMMANDS[member["stack"]]
    pm = member["packageManager"] or ""
    return lint_t.replace("{pm}", pm), test_t.replace("{pm}", pm)


def write_config(answers: Answers, target: Path, sentinel: Sentinel) -> None:
    """Write forge.config.json equivalent to forge-init's output (02 §4.3, 00 §7)."""
    config: dict = {
        "specsDir": "./specs",
        "docsDir": "./docs/architecture",
        "backlogDir": None,
        "gitCommitAfterStage": True,
        "commitPrefix": "forge",
        "stack": None,
        "typeCheckCommand": None,
        "testCommand": None,
        "loopIterationMultiplier": 1.5,
        "loopRunner": {"name": "rauf", "bin": "rauf"},
    }
    if answers["layout"] == "single":
        member = answers["members"][0]
        lint, test = _resolve_commands(member)
        config["stack"] = member["stack"]
        config["typeCheckCommand"] = lint
        config["testCommand"] = test
    else:
        workspaces: list[dict] = []
        for member in answers["members"]:
            lint, test = _resolve_commands(member)
            workspaces.append({
                "name": member["name"],
                "path": member["path"],
                "stack": member["stack"],
                "typeCheckCommand": lint,
                "testCommand": test,
            })
        config["workspaces"] = workspaces
    _write_artifact(target, "forge.config.json", _json_text(config), sentinel)


def _compose_readme(answers: Answers) -> str:
    """Compose README.md from the hygiene template with token substitution (02 §4.5)."""
    text = (TEMPLATE_ROOT / "hygiene" / "README.md").read_text(encoding="utf-8")
    license_label = answers["license"] if answers["license"] != "none" else "no license"
    for tok, val in (
        ("{{PROJECT_NAME}}", answers["projectName"]),
        ("{{PURPOSE}}", answers["purpose"]),
        ("{{LICENSE}}", license_label),
    ):
        text = text.replace(tok, val)
    return text


def _compose_license(answers: Answers) -> str:
    """Compose the LICENSE text from templates/licenses/<id>/LICENSE (02 §4.5)."""
    src = TEMPLATE_ROOT / "licenses" / answers["license"] / "LICENSE"
    if not src.is_file():
        raise UsageError(f"no license template for {answers['license']!r}: {src}")
    text = src.read_text(encoding="utf-8")
    year = str(datetime.now(timezone.utc).year)
    for tok, val in (
        ("{{YEAR}}", year),
        ("{{AUTHOR}}", answers["author"]),
        ("{{PROJECT_NAME}}", answers["projectName"]),
    ):
        text = text.replace(tok, val)
    return text


def _compose_agent_file(answers: Answers, filename: str) -> str:
    """Compose AGENTS.md / CLAUDE.md from the hygiene template (02 §4.5)."""
    text = (TEMPLATE_ROOT / "hygiene" / filename).read_text(encoding="utf-8")
    for tok, val in (
        ("{{PROJECT_NAME}}", answers["projectName"]),
        ("{{PURPOSE}}", answers["purpose"]),
    ):
        text = text.replace(tok, val)
    return text


def write_hygiene(answers: Answers, target: Path, sentinel: Sentinel) -> None:
    """Emit README, LICENSE, and the host agent-instruction file(s) (02 §4.5)."""
    _write_artifact(target, "README.md", _compose_readme(answers), sentinel)
    if answers["license"] != "none":
        _write_artifact(target, "LICENSE", _compose_license(answers), sentinel)
    _write_artifact(
        target, "AGENTS.md", _compose_agent_file(answers, "AGENTS.md"), sentinel
    )
    if answers["host"] == "claude":
        _write_artifact(
            target, "CLAUDE.md", _compose_agent_file(answers, "CLAUDE.md"), sentinel
        )


def _compose_ci_workflow(answers: Answers) -> str:
    """Compose the CI workflow, injecting per-member lint+test steps (03 §9).

    Reads templates/ci/github-actions.yml and replaces the ``# <<MEMBER_STEPS>>``
    marker with one lint step + one test step per member. For a single package
    (one implicit member at '.') the steps carry no ``working-directory``; for a
    monorepo every member is pinned to its ``path`` so CI exercises EVERY member
    (REQ-MONO-04).
    """
    src = TEMPLATE_ROOT / "ci" / "github-actions.yml"
    if not src.is_file():
        raise UsageError(f"CI workflow template not found: {src}")
    template = src.read_text(encoding="utf-8")
    marker = "# <<MEMBER_STEPS>>"
    if marker not in template:
        raise UsageError(f"CI template missing {marker!r} marker: {src}")
    indent = template[: template.index(marker)].rsplit("\n", 1)[-1]
    single = answers["layout"] == "single"
    lines: list[str] = []
    for member in answers["members"]:
        lint, test = _resolve_commands(member)
        wd = None if single else member["path"]
        label = member["name"]
        for kind, cmd in (("lint", lint), ("test", test)):
            name = kind if single else f"{label} — {kind}"
            lines.append(f"{indent}- name: {name}")
            if wd is not None:
                lines.append(f"{indent}  working-directory: {wd}")
            lines.append(f"{indent}  run: {cmd}")
    block = "\n".join(lines)
    return template.replace(f"{indent}{marker}", block)


def maybe_write_ci(answers: Answers, target: Path, sentinel: Sentinel) -> None:
    """Emit a CI workflow when answers.ci is true (02 §4.4).

    No-op when answers.ci is false (REQ-SCAF-07). When enabled, composes
    .github/workflows/ci.yml from templates/ci/github-actions.yml with one
    lint+test step per member (03 §9, REQ-MONO-04) and records it for staging.
    """
    if not answers["ci"]:
        return
    content = _compose_ci_workflow(answers)
    _write_artifact(target, ".github/workflows/ci.yml", content, sentinel)


def scaffold(target: Path, answers: Answers) -> list[str]:
    """Emit the pipeline-ready baseline for every member, idempotently (02 §4).

    Ordering is load-bearing: the sentinel is written FIRST (REQ-LIFE-01) so a crash
    leaves a recoverable partial scaffold; ``git init`` runs only when no ``.git/``
    exists (REQ-GATE-03); then each member is composed (REQ-MONO-01/02), the
    repo-hygiene files are emitted (REQ-SCAF-06/09), ``forge.config.json`` is written
    (REQ-CFG-01/02/03), and a CI workflow is emitted when requested. Every written
    path is recorded in the sentinel's artifactsWritten[]; a recorded path or a
    pre-existing allowed-meta file is skipped, making the run idempotent.
    """
    sentinel = read_sentinel(target)
    if sentinel is None:
        sentinel = {
            "version": 1,
            "status": "in-progress",
            "startedAt": datetime.now(timezone.utc).isoformat(),
            "answers": answers,
            "artifactsWritten": [],
        }
        write_sentinel(target, sentinel)
    if not (target / ".git").is_dir():
        run(["git", "init"], cwd=target)
    for member in answers["members"]:
        compose_member(member, answers, target, sentinel)
    write_hygiene(answers, target, sentinel)
    write_config(answers, target, sentinel)
    maybe_write_ci(answers, target, sentinel)
    return sentinel["artifactsWritten"]


def toolchain_present(required: list[str]) -> bool:
    """Return True iff every required tool is on PATH (REQ-LIFE-03).

    Probes each binary with ``command -v`` via the run wrapper (a shell builtin,
    invoked through ``sh -c``). A single missing tool yields False, driving the
    distinct missing-toolchain outcome (exit 2, 00 §9): the skill then offers
    scaffold-anyway-unverified vs abort and marks the baseline unverified
    (REQ-LIFE-04). Bootstrap NEVER installs a toolchain (tech-spec §9).

    Args:
        required: Distinct probe binaries for the resolved stack(s) (00 §6),
            already {pm}-substituted.

    Returns:
        True iff ``command -v`` succeeds for every entry.
    """
    for tool in required:
        try:
            proc = run(["sh", "-c", f"command -v {tool}"], cwd=Path.cwd(), check=False)
        except UsageError:
            # The probe itself could not be launched (e.g. an empty PATH leaves no
            # `sh`): treat that as the tool being absent, the missing-toolchain
            # outcome, never an internal error (REQ-LIFE-03/04).
            return False
        if proc.returncode != 0:
            return False
    return True


def verify(target: Path, answers: Answers) -> VerifyResult:
    """Detect the toolchain and run resolved lint/test per member (02 §5, 00 §6).

    First probes every required tool (toolchain_present). If any is missing,
    returns immediately with toolchainPresent=False, empty lint/test, green=False —
    the caller maps this to exit 2 (the distinct missing-toolchain outcome, 00 §9,
    REQ-LIFE-03/04). When the toolchain is present, runs each member's resolved
    typeCheckCommand then testCommand (00 §6) in that member's directory, collecting
    one CommandOutcome per command (per member for a monorepo — REQ-MONO-03). The
    ``green`` predicate — toolchainPresent AND every outcome ok — is the single gate
    Mode B checks before launching the next stage (REQ-MODEB-04). Commands resolve
    from STACK_COMMANDS so they match references/stacks/*.md exactly (REQ-STACK-02).

    Args:
        target: The project root being verified.
        answers: The resolved interview payload (members + commands).

    Returns:
        A VerifyResult (00 §4): toolchainPresent / lint[] / test[] / green.

    Raises:
        UsageError: If a member directory is missing or a command cannot be
            launched (exit 2).
    """
    required: list[str] = []
    for member in answers["members"]:
        _, _, probes = STACK_COMMANDS[member["stack"]]
        pm = member["packageManager"] or ""
        for probe in probes:
            tool = probe.replace("{pm}", pm)
            if tool and tool not in required:
                required.append(tool)
    present = toolchain_present(required)
    if not present:
        return {"toolchainPresent": False, "lint": [], "test": [], "green": False}

    lint: list[CommandOutcome] = []
    test: list[CommandOutcome] = []
    for member in answers["members"]:
        lint_cmd, test_cmd = _resolve_commands(member)
        cwd = target / member["path"]
        for bucket, cmd in ((lint, lint_cmd), (test, test_cmd)):
            proc = run(["sh", "-c", cmd], cwd=cwd, check=False)
            bucket.append(
                {"command": cmd, "ok": proc.returncode == 0, "member": member["path"]}
            )
    green = all(o["ok"] for o in (*lint, *test))
    return {"toolchainPresent": True, "lint": lint, "test": test, "green": green}


def commit(target: Path, answers: Answers, stage_only: bool) -> CommitResult:
    """Stage the exact artifact list and commit or stop at staged (02 §6, 00 §4).

    Ordering is load-bearing (OQ-T3): the sentinel file is deleted BEFORE any
    ``git add`` so it can never be staged or enter history (REQ-SCAF-08). Staging
    uses the exact artifactsWritten[] list with ``git add -- <paths>`` — never
    ``git add -A`` (REQ-SEC-02) — and follows the shared Git Commit Protocol (never
    --force / --no-verify). When stage_only (or commitStyle == "stage-only") the
    scaffold is left staged with no commit (REQ-LIFE-05); otherwise a single
    baseline commit captures the whole scaffold plus forge.config.json (REQ-LIFE-06).
    The commit prefix is read from the just-written forge.config.json's
    ``commitPrefix`` field (default "forge"), NOT from answers (00 §5/§7).

    Args:
        target: The project root being committed.
        answers: The resolved interview payload (for commitStyle; the commit
            prefix is read from forge.config.json, not from answers).
        stage_only: True to stop at staged with no commit (the --stage-only flag).

    Returns:
        A CommitResult (00 §4): committed / commitHash / staged / sentinelRemoved.

    Raises:
        UsageError: No sentinel to commit, or a git/IO failure (exit 2). On a git
            failure the sentinel is already removed; the run is re-stageable.
    """
    sentinel = read_sentinel(target)
    if sentinel is None:
        raise UsageError(
            "no .forge-bootstrap.json sentinel to commit; run scaffold first"
        )
    staged = list(sentinel["artifactsWritten"])

    # OQ-T3: remove the sentinel BEFORE staging so it never enters history.
    (target / SENTINEL_FILENAME).unlink(missing_ok=True)

    run(["git", "add", "--", *staged], cwd=target)

    if stage_only or answers["commitStyle"] == "stage-only":
        return {
            "committed": False,
            "commitHash": None,
            "staged": staged,
            "sentinelRemoved": True,
        }

    # commitPrefix is a forge.config.json field (00 §7), not an interview answer.
    # Read it back from the config bootstrap just wrote; default "forge" if absent.
    try:
        cfg = json.loads(
            (target / "forge.config.json").read_text(encoding="utf-8")
        )
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"cannot read forge.config.json: {exc}")
    prefix = cfg.get("commitPrefix") or "forge"
    message = f"{prefix}: bootstrap baseline"
    run(["git", "commit", "-m", message], cwd=target)
    rev = run(["git", "rev-parse", "HEAD"], cwd=target)
    return {
        "committed": True,
        "commitHash": rev.stdout.strip(),
        "staged": staged,
        "sentinelRemoved": True,
    }


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
