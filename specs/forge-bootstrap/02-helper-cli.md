# 02 — Helper CLI (`scripts/forge-bootstrap.py`)

> The deterministic engine of **forge-bootstrap**: a single stdlib-only Python 3.10+ CLI with five subcommands (`check`, `scaffold`, `verify`, `commit`, `status`) that owns the greenfield gate, git init, template-driven scaffold emission, `forge.config.json` write, the transient resume sentinel, toolchain detection + lint/test verification, and the exact-list baseline commit. The `SKILL.md` body (04-skill-orchestration.md) runs the interview and renders human output; this helper only emits structured JSON + exit codes. It builds on **00-core-definitions.md** (all shared types, constants, the per-stack command table, the config field set, the sentinel schema, the exit-code contract) and **01-architecture-layout.md §3** (the module skeleton). It does **not** redefine those shared types; it references them by section and fleshes out the full signatures and algorithms. Its style, `argparse` dispatch, exit-code handling, and `--json` convention mirror `scripts/epic-manifest.py` exactly.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-GATE-01 | Greenfield gate: only repo-meta files allowed | 3 (`check`) |
| REQ-GATE-02 | Refusal names disqualifying path(s) | 3 (`CheckResult.disqualifying`) |
| REQ-GATE-03 | `git init` when no repo present | 3 (`hasGit`), 4 (`scaffold` step 2) |
| REQ-GATE-04 | Fresh-remote (README+LICENSE) eligible | 3 (allow-list, 00 §3) |
| REQ-GATE-05 | Never modify/delete a pre-existing file | 3, 4.1 (no-overwrite) |
| REQ-SCAF-01 | Stack-appropriate directory structure | 4 (`compose_member`) |
| REQ-SCAF-02 | Toolchain config (manifest/lint/format/test) | 4 (templates, 03) |
| REQ-SCAF-03 | Minimal runnable entrypoint | 4 (templates, 03) |
| REQ-SCAF-04 | At least one passing test | 4 (templates, 03) |
| REQ-SCAF-05 | Green baseline (lint+test pass) | 5 (`verify`) |
| REQ-SCAF-06 | Repo-hygiene + agent-instruction files | 4 (`compose_member`, write_config) |
| REQ-SCAF-07 | Optional CI workflow (lint+test) | 4.4 (`maybe_write_ci`) |
| REQ-SCAF-08 | No untracked/dangling scaffold files | 6 (`commit` exact-list) |
| REQ-SCAF-09 | No-overwrite of pre-existing allowed-meta files | 4.1 (`_write_artifact`) |
| REQ-STACK-02 | Verification commands match the stack profile | 5 (resolve from 00 §6) |
| REQ-MONO-01 | Scaffold workspace root + each member | 4 (per-member loop) |
| REQ-MONO-02 | Mixed-language members | 4 (per-member `Member.stack`) |
| REQ-MONO-03 | Each member green; aggregate green | 5 (per-member verify) |
| REQ-MONO-04 | Monorepo CI runs lint+test for all members | 4.4 (`maybe_write_ci`) |
| REQ-MONO-05 | Config represents workspace per member | 4.3 (`write_config` workspaces[]) |
| REQ-CFG-01 | Valid config: stack + `loopRunner` | 4.3 (`write_config`) |
| REQ-CFG-02 | Config ≡ forge-init field set + defaults | 4.3 (field table) |
| REQ-CFG-03 | forge-init unnecessary afterward | 4.3 |
| REQ-LIFE-01 | In-progress resume marker recorded | 4 (sentinel written first), 7 (`status`) |
| REQ-LIFE-02 | Resume detection; no greenfield misfire | 3 (`resumeMarker`), 4 (idempotent), 7 |
| REQ-LIFE-03 | Toolchain detection before lint/test | 5 (`toolchain_present`) |
| REQ-LIFE-04 | Unverified marking when toolchain missing | 5 (`green` / exit 2) |
| REQ-LIFE-05 | Commit style chosen at run time | 6 (`--stage-only`) |
| REQ-LIFE-06 | Single baseline commit of whole scaffold | 6 (`commit`) |
| REQ-SEC-01 | Never modify/delete pre-existing files | 3, 4.1 |
| REQ-SEC-02 | Stage specific paths; never `git add -A` | 6 (`commit`) |

---

## 1. Overview & Invocation

`scripts/forge-bootstrap.py` is a single self-contained module organized exactly like `scripts/epic-manifest.py` (01 §3): a module docstring with usage + the exit-code contract; module constants; small pure-ish functions; a `subprocess`/`pathlib` I/O layer; an `argparse` subcommand dispatch in `main()` guarded by `if __name__ == "__main__": sys.exit(main())`.

The skill locates the helper via the byte-identical portable-root prelude (01 §2.2, `references/portable-root.md`), then invokes it against the **project cwd** being bootstrapped — distinct from the plugin root `$R` (00 §1.1):

```bash
python3 "$R/scripts/forge-bootstrap.py" <subcommand> <target-dir> [--json] [...]
```

**Subcommands** (tech-spec §2): `check`, `scaffold`, `verify`, `commit`, `status`.

**Exit codes** (00 §9, mirrored from `epic-manifest.py`):

| Exit | Meaning |
|------|---------|
| `0` | success: eligible / green / committed-or-staged |
| `1` | actionable findings: gate refusal (`eligible:false`), or `verify` not-green |
| `2` | usage or IO error — **including `verify` toolchain-missing** (the distinct missing-toolchain outcome) |

`--json` prints a single JSON object (the matching `CheckResult` / `VerifyResult` / `CommitResult` / `Sentinel` from 00 §4/§8) to **stdout**; all diagnostic text goes to **stderr**, so a caller can capture stdout cleanly. On exit 2 stdout is empty and a plain `Error:` line is printed to stderr (the `epic-manifest.py` convention).

### 1.1 Module preamble

The docstring carries the usage block and the 00 §9 exit-code contract; the import set covers every operation the helper performs (git/toolchain/lint-test via `subprocess`, template copy via `shutil`/`pathlib`, JSON for the sentinel/`--answers`/config, `datetime` for `startedAt`).

```python
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
    python3 forge-bootstrap.py commit   <target-dir> --answers JSON \\
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
```

The typed structures — `Stack`, `PACKAGE_MANAGERS`, `ALLOWED_META_DIRS`, `SENTINEL_FILENAME`, `ALLOWED_META_FILE_RE`, `Member`, `Answers`, `Sentinel`, `CheckResult`, `CommandOutcome`, `VerifyResult`, `CommitResult` — are defined in **00 §2/§3/§4/§5/§8** and the per-stack command table in **00 §6**. They are single-file `TypedDict`s / constants, re-stated verbatim in this module (not imported across modules — 01 §5), exactly as `epic-manifest.py` re-states the epic types. This document references them rather than redefining them.

A module-level constant holds the per-stack command table (00 §6) so `write_config` and `verify` share one source of truth:

```python
#: Resolved verification + toolchain-probe commands per stack (00 §6). "{pm}" is
#: substituted with the member's packageManager; "{member}" with its path.
#: STACK_COMMANDS[stack] -> (typeCheckCommand-template, testCommand-template,
#: tuple-of-toolchain-probe-binaries). The single source of truth shared by
#: write_config (§4.3) and verify (§5), so config and the run agree exactly.
STACK_COMMANDS: Final[dict[str, tuple[str, str, tuple[str, ...]]]] = {
    "typescript": ("npx tsc --noEmit", "{pm} test",        ("node", "{pm}")),
    "python":     ("mypy .",          "pytest",            ("python3", "{pm}")),
    "go":         ("go vet ./...",    "go test ./...",     ("go",)),
    "rust":       ("cargo clippy",    "cargo test",        ("cargo",)),
    "generic":    ("sh -n run.sh test.sh", "./test.sh",    ("sh",)),
}
```

---

## 2. Internal Exceptions

Two module-private exceptions carry exit-code intent up to `main()`, identical in shape and contract to `epic-manifest.py` §2, so every subcommand can `raise` and one handler maps them to exit codes.

```python
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
```

`main()` wraps the dispatch in `try/except`: `UsageError` → print `Error: …` to stderr, return `2`; `FindingsError` → print its `result` as JSON to stdout (under `--json`), return `1`; any uncaught `OSError` → print and return `2` (§8).

---

## 3. `check` — Greenfield Gate + Recovery Detection (REQ-GATE-01/02/03/04, REQ-LIFE-02, REQ-SEC-01)

**Purpose.** Decide whether the target is a permitted greenfield (00 §3 allow-list), OR a resume of bootstrap's own partial scaffold (sentinel present → recovery, never refusal — REQ-LIFE-02). It is **read-only**: it only lists directory entries and reads the sentinel; it never creates, modifies, or deletes anything (REQ-SEC-01).

**CLI.** `check <target-dir> [--specs-dir DIR] [--json]`. `--specs-dir` defaults to `./specs` (matching `epic-manifest.py` and forge-init) and is the one directory name (besides `.git/` and the allow-listed meta files) that is permitted at the target root. `--json` prints the `CheckResult` (00 §4).

**Algorithm.**

1. Resolve `target = Path(target_dir)`. A non-existent or empty target is trivially eligible (00 §3).
2. Read the sentinel if present: `marker = read_sentinel(target)` (§4 I/O layer). `resumeMarker = marker` (may be `None`).
3. `hasGit = (target / ".git").is_dir()` — the REQ-GATE-03 signal that drives whether `scaffold` runs `git init`.
4. Walk the **immediate** entries of `target` (basename only; never descends into allowed dirs — 00 §3). For each entry, classify with the 00 §3 allow rules:
   - `.git` (in `ALLOWED_META_DIRS`) → allowed.
   - the directory named `specs_dir.name` (the configured `specsDir`) → allowed.
   - the `SENTINEL_FILENAME` → allowed (recovery routing).
   - a regular file matching `ALLOWED_META_FILE_RE` (case-insensitive) → allowed (covers a fresh remote's README + LICENSE — REQ-GATE-04).
   - **anything else** → append its repo-relative path to `disqualifying[]` (REQ-GATE-01/02).
5. `eligible = not disqualifying` **OR** `resumeMarker is not None`. The sentinel being allow-listed (step 4) plus this OR means a re-run over bootstrap's own partial scaffold is **never** refused as a foreign project (REQ-LIFE-02): even if a partial scaffold has written non-meta files, the live sentinel routes the skill to resume/restart/cancel.
6. Return the `CheckResult`. The skill maps a `False` `eligible` (with empty `resumeMarker`) to the greenfield-refusal terminal outcome (00 §4) and a non-null `resumeMarker` to the partial-state outcome.

**Exit codes.** `0` eligible (fresh greenfield or resume); `1` greenfield refusal (`eligible:false`, `resumeMarker:null`); `2` IO error (e.g. `target` exists as a file, unreadable dir).

**Findings.** A refusal `CheckResult` with `disqualifying[]` populated. No `Stack`/template work occurs in `check`.

```python
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
```

---

## 4. `scaffold` — Emit the Pipeline-Ready Baseline (REQ-GATE-03, REQ-SCAF-01..09, REQ-MONO-01..05, REQ-CFG-01..03, REQ-LIFE-01/02)

**Purpose.** Compose the per-stack templates for every member, write `forge.config.json`, optionally emit CI, and record every written path into the sentinel — idempotently, so an interrupted run resumes without re-writing or overwriting (REQ-LIFE-02).

**CLI.** `scaffold <target-dir> --answers JSON [--json]`. The `--answers` payload is the resolved `Answers` (00 §5), parsed and validated into the typed structure. `--json` prints `{"artifactsWritten": [...]}` (the sentinel's running list).

**Algorithm (ordering is load-bearing).**

1. **Write the sentinel FIRST**, before any scaffold file (REQ-LIFE-01, 00 §8). On a fresh run, create `.forge-bootstrap.json` with `status:"in-progress"`, `startedAt` = now (ISO-8601 UTC), `answers` = the parsed payload mirrored verbatim, and `artifactsWritten: []`. On a **resume** (a sentinel already exists), load it and keep its `startedAt` and existing `artifactsWritten` — the running list is the idempotency key.
2. **`git init` if absent** (REQ-GATE-03): if `not (target / ".git").is_dir()`, run `git init` in `target` via the `run` wrapper. (No `git init` is attempted when `.git/` already exists — the fresh-remote case.)
3. **Per-member compose** (REQ-MONO-01/02): for each `member` in `answers["members"]` (exactly one with `path == "."` for a single package — 00 §5), call `compose_member(member, answers, target, sentinel)`. Each member's stack maps 1:1 to `templates/<stack>/` (00 §2; 03 §1). Mixed-language members coexist because each is composed against its own `member["stack"]` (REQ-MONO-02). Composition copies the template files with token substitution (00 §6.2) and records each written path.
4. **Write `forge.config.json`** (REQ-CFG-01/02/03) via `write_config(answers, target, sentinel)` (§4.3), recording it in `artifactsWritten[]`.
5. **Optionally emit CI** (REQ-SCAF-07, REQ-MONO-04) via `maybe_write_ci(answers, target, sentinel)` (§4.4) when `answers["ci"]` is true.
6. Persist the sentinel after each artifact (so an interrupt mid-run leaves a consistent `artifactsWritten[]` to resume from) and return the full list.

**Exit codes.** `0` scaffold complete (or fully resumed with nothing left to write); `2` IO error (template dir missing, unwritable target, malformed `--answers`, `git init` failure).

**Findings.** None — `scaffold` either succeeds (exit 0) or fails as a usage/IO error (exit 2). The green-baseline *judgment* is `verify`'s job (§5), not `scaffold`'s.

```python
def scaffold(target: Path, answers: Answers) -> list[str]:
    """Emit the pipeline-ready baseline for every member, idempotently (00 §8).

    Ordering is load-bearing: the sentinel is written FIRST (REQ-LIFE-01) so a
    crash at any later point leaves a recoverable partial scaffold (REQ-LIFE-02);
    ``git init`` runs only when no ``.git/`` exists (REQ-GATE-03); then each member
    is composed from its template dir (REQ-MONO-01/02), ``forge.config.json`` is
    written (REQ-CFG-01/02/03), and a CI workflow is emitted when requested
    (REQ-SCAF-07, REQ-MONO-04). Every written path is appended to the sentinel's
    artifactsWritten[]; a file already recorded there is skipped, making the whole
    operation idempotent over a resume. A pre-existing allowed-meta file
    (README/LICENSE/.gitignore) is never overwritten (REQ-SCAF-09, REQ-GATE-05).

    Args:
        target: The project root being bootstrapped.
        answers: The resolved interview payload (00 §5), already parsed/validated.

    Returns:
        The full list of repo-relative paths written across this run and any prior
        resumed runs (the sentinel's artifactsWritten[]).

    Raises:
        UsageError: Template dir missing, unwritable target, ``git init`` failure,
            or a malformed/unsupported answers payload (exit 2).
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
    write_config(answers, target, sentinel)
    maybe_write_ci(answers, target, sentinel)
    return sentinel["artifactsWritten"]
```

### 4.1 `_write_artifact` — the single no-overwrite write primitive (REQ-SCAF-09, REQ-GATE-05, REQ-LIFE-02)

Every scaffold write goes through one helper that enforces idempotency and the no-overwrite guarantee, and keeps the sentinel's `artifactsWritten[]` authoritative.

```python
def _write_artifact(
    target: Path, rel_path: str, content: str, sentinel: Sentinel
) -> None:
    """Write one scaffold artifact, idempotently and never overwriting (00 §8).

    Skips the write when ``rel_path`` is already in the sentinel's
    artifactsWritten[] (resume idempotency, REQ-LIFE-02) OR when the destination
    file already exists on disk and was NOT written by this run — the latter is a
    pre-existing allowed-meta file (e.g. a fresh remote's README/LICENSE) that must
    be kept verbatim (REQ-SCAF-09, REQ-GATE-05, REQ-SEC-01). In that kept case the
    path is NOT added to artifactsWritten[] (it is not bootstrap's artifact to
    stage). Otherwise it creates parent dirs, writes atomically (temp + os.replace,
    same dir), appends ``rel_path`` to artifactsWritten[], and persists the
    sentinel so an interrupt mid-scaffold leaves a consistent resume list.

    Args:
        target: The project root.
        rel_path: The repo-relative destination path (POSIX-style).
        content: The fully token-substituted file content.
        sentinel: The live sentinel dict; mutated in place and re-persisted.

    Raises:
        UsageError: If the file cannot be written (exit 2).
    """
    if rel_path in sentinel["artifactsWritten"]:
        return
    dest = target / rel_path
    if dest.exists():
        # Pre-existing (allowed-meta) file — keep it, do not record or stage it.
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(dest, content)
    sentinel["artifactsWritten"].append(rel_path)
    write_sentinel(target, sentinel)
```

> A scaffolded `.gitignore` collision is the common REQ-SCAF-09 case: if the repo already has a `.gitignore`, the template's is skipped (kept file noted by the skill in the completion summary — REQ-OUT-01). The interview seeds the license default from a pre-existing LICENSE upstream in the skill (04); the helper only honors the no-overwrite here.

### 4.2 `compose_member` — template copy + token substitution (REQ-SCAF-01..06, REQ-MONO-01/02)

```python
def compose_member(
    member: Member, answers: Answers, target: Path, sentinel: Sentinel
) -> None:
    """Compose one member's scaffold from its stack template dir (00 §6.2, 03 §1).

    Resolves the template dir from ``__file__`` (00 §1.1):
    ``<root>/skills/forge-bootstrap/references/templates/<member.stack>/``. For each
    file in that tree, computes the destination as ``member.path`` joined with the
    template-relative path (so a single package at "." writes at the repo root and a
    monorepo member at "packages/api" writes under it — REQ-MONO-01), applies the
    00 §6.2 token substitution to the file's text, and writes via _write_artifact
    (§4.1). Tokens: {{PROJECT_NAME}} -> answers.projectName, {{PKG}} -> a sanitized
    member.name, {{PM}} -> member.packageManager (when applicable), {{PURPOSE}} ->
    answers.purpose. Filenames carrying {{PKG}} (e.g. python's src/{{PKG}}/) are
    substituted too. This produces the stack-appropriate structure (REQ-SCAF-01), the
    toolchain config + runnable entrypoint + passing test + hygiene files
    (REQ-SCAF-02..06) that the §6 commands pass green. Each member is composed against
    its own stack, so mixed-language members coexist (REQ-MONO-02).

    Args:
        member: The member to scaffold (name/path/stack/packageManager, 00 §5).
        answers: The full interview payload (for project-level tokens).
        target: The project root.
        sentinel: The live sentinel (passed through to _write_artifact).

    Raises:
        UsageError: If the member's template dir is missing or a file is
            unreadable (exit 2).
    """
    template_root = (
        Path(__file__).resolve().parent.parent
        / "skills" / "forge-bootstrap" / "references" / "templates" / member["stack"]
    )
    if not template_root.is_dir():
        raise UsageError(f"template dir not found for stack {member['stack']!r}: {template_root}")
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
```

`_sanitize_pkg` maps a member name to a language-safe package identifier (e.g. lowercasing and replacing `-`/spaces with `_` for `{{PKG}}`); the exact rule is a small pure helper finalized at implementation, kept identical across stacks for determinism (03 §1).

### 4.3 `write_config` — `forge.config.json` ≡ forge-init + `loopRunner` (REQ-CFG-01/02/03, REQ-MONO-05)

The helper writes the config **directly**, reproducing `forge-init.sh`'s exact field set + default values (00 §7), differing only where bootstrap has resolved a real value, plus a minimal explicit `loopRunner` block. After this, `forge-init` is unnecessary (REQ-CFG-03).

| Field | forge-init default | bootstrap value (single) | bootstrap value (monorepo) |
|-------|--------------------|--------------------------|----------------------------|
| `specsDir` | `./specs` | same | same |
| `docsDir` | `./docs/architecture` | same | same |
| `backlogDir` | `null` | same | same |
| `gitCommitAfterStage` | `true` | same | same |
| `commitPrefix` | `forge` | same | same |
| `loopIterationMultiplier` | `1.5` | same | same |
| `stack` | `null` | the single member's stack | `null` |
| `typeCheckCommand` | `null` | resolved per stack (00 §6) | `null` |
| `testCommand` | `null` | resolved per stack (00 §6) | `null` |
| `loopRunner` | (implicit default) | `{ "name": "rauf", "bin": "rauf" }` | same |
| `workspaces` | (absent) | **omitted** | one entry per member |

```python
def write_config(answers: Answers, target: Path, sentinel: Sentinel) -> None:
    """Write forge.config.json equivalent to forge-init's output (00 §7).

    Reproduces forge-init.sh's exact field set + defaults, overriding only the
    resolved stack/commands and adding the minimal loopRunner block (REQ-CFG-01/02).
    For a single package (layout == "single", one member at "."), the top-level
    stack/typeCheckCommand/testCommand are resolved from STACK_COMMANDS for that
    member's stack and packageManager (00 §6) and ``workspaces`` is OMITTED
    (byte-for-byte back-compatible). For a monorepo, the three top-level scalars are
    null and ``workspaces[]`` carries one {name, path, stack, typeCheckCommand,
    testCommand} entry per member, each resolved from STACK_COMMANDS (REQ-MONO-05,
    00 §7.1). Written via _write_artifact so it is recorded for staging and never
    clobbers a pre-existing config (REQ-SCAF-09). After this, forge-init is
    unnecessary (REQ-CFG-03).

    Args:
        answers: The resolved interview payload.
        target: The project root.
        sentinel: The live sentinel (for artifact recording).

    Raises:
        UsageError: If the config cannot be written (exit 2).
    """
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
        config["workspaces"] = []
        for member in answers["members"]:
            lint, test = _resolve_commands(member)
            config["workspaces"].append({
                "name": member["name"],
                "path": member["path"],
                "stack": member["stack"],
                "typeCheckCommand": lint,
                "testCommand": test,
            })
    _write_artifact(target, "forge.config.json", _json_text(config), sentinel)


def _resolve_commands(member: Member) -> tuple[str, str]:
    """Resolve a member's (typeCheckCommand, testCommand) from STACK_COMMANDS (00 §6).

    Substitutes ``{pm}`` with the member's packageManager (REQ-INPUT-04). Matches
    the references/stacks/<stack>.md verification commands so downstream
    acceptance-criteria verification runs against this baseline unchanged
    (REQ-STACK-02).
    """
    lint_t, test_t, _ = STACK_COMMANDS[member["stack"]]
    pm = member["packageManager"] or ""
    return lint_t.replace("{pm}", pm), test_t.replace("{pm}", pm)
```

### 4.4 `maybe_write_ci` — optional CI workflow (REQ-SCAF-07, REQ-MONO-04)

```python
def maybe_write_ci(answers: Answers, target: Path, sentinel: Sentinel) -> None:
    """Emit a CI workflow that runs lint + test, when answers.ci is true (00 §6, 03 §5).

    No-op when answers.ci is false (REQ-SCAF-07: CI is skippable). When enabled,
    composes ``.github/workflows/ci.yml`` from
    templates/ci/github-actions.yml: for a single package, one lint+test job using
    the resolved top-level commands; for a monorepo, one lint+test step per member
    iterating workspaces[] so CI exercises EVERY member (REQ-MONO-04). The per-member
    step generation and the workflow template are defined in 03 §5; this helper only
    gates on answers.ci and records the file for staging via _write_artifact.

    Args:
        answers: The resolved interview payload.
        target: The project root.
        sentinel: The live sentinel (for artifact recording).

    Raises:
        UsageError: If the CI template is missing or unwritable (exit 2).
    """
    if not answers["ci"]:
        return
    content = _compose_ci_workflow(answers)  # per-member steps; 03 §5
    _write_artifact(target, ".github/workflows/ci.yml", content, sentinel)
```

> The exact workflow template and per-member step expansion live in **03-stack-templates.md §5**; this helper does not duplicate them — it gates on `answers["ci"]` and delegates composition.

---

## 5. `verify` — Toolchain Detection + Lint/Test (REQ-SCAF-05, REQ-STACK-02, REQ-MONO-03, REQ-LIFE-03/04, REQ-MODEB-04)

**Purpose.** Detect whether the resolved stack(s) toolchain is installed (REQ-LIFE-03) and, when present, run the resolved lint + test command per member (00 §6). The `green` predicate is the single Mode B gate (REQ-MODEB-04): `green = toolchainPresent AND every lint/test outcome ok`.

**CLI.** `verify <target-dir> --answers JSON [--json]`. `--json` prints the `VerifyResult` (00 §4).

**Algorithm.**

1. Gather the distinct `(stack, packageManager)` pairs across `answers["members"]`, and the required toolchain probe binaries from `STACK_COMMANDS[stack][2]` (substituting `{pm}`).
2. `toolchain_present(...)`: for each required binary run `command -v <bin>` (REQ-LIFE-03); `toolchainPresent` is true iff **all** are found. If any is missing → return early with `toolchainPresent:false`, empty `lint`/`test`, `green:false`, and the caller raises the **exit-2** missing-toolchain outcome (00 §9; the skill offers scaffold-anyway-unverified vs abort, marking the baseline unverified — REQ-LIFE-04).
3. With the toolchain present, for each member run its resolved `typeCheckCommand` (lint) then `testCommand` (00 §6) with `cwd = target / member["path"]`, recording one `CommandOutcome{command, ok, member}` each (member name is `"."` for a single package). The aggregate over all members makes the workspace lint+test green (REQ-MONO-03).
4. `green = toolchainPresent and all(o["ok"] for o in lint + test)`.
5. Return the `VerifyResult`.

**Exit codes.** `0` green; `1` not-green (toolchain present but a lint/test failed); `2` toolchain-missing (the distinct outcome — 00 §9). The skill gates Mode B on `green` (REQ-MODEB-04): it never launches the next stage on exit 1 or 2 unless the user explicitly overrides.

**Findings.** A not-green `VerifyResult` (exit 1) carries the per-member `CommandOutcome[]` so the skill can name which command failed.

```python
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
        proc = run(["sh", "-c", f"command -v {tool}"], cwd=Path.cwd(), check=False)
        if proc.returncode != 0:
            return False
    return True


def verify(target: Path, answers: Answers) -> VerifyResult:
    """Detect the toolchain and run resolved lint/test per member (00 §6, §4).

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
            bucket.append({"command": cmd, "ok": proc.returncode == 0, "member": member["name"]})
    green = all(o["ok"] for o in (*lint, *test))
    return {"toolchainPresent": True, "lint": lint, "test": test, "green": green}
```

---

## 6. `commit` — Exact-List Baseline Commit (REQ-LIFE-05/06, REQ-SCAF-08, REQ-SEC-02)

**Purpose.** Stage the **exact** tracked artifact list (never `git add -A`) and either make a single baseline commit (REQ-LIFE-06) or stop at staged (`--stage-only`, REQ-LIFE-05). The sentinel is removed **before** staging so it never enters history (REQ-SCAF-08, OQ-T3).

**CLI.** `commit <target-dir> --answers JSON [--stage-only] [--json]`. `--json` prints the `CommitResult` (00 §4). The artifact list comes from the live sentinel's `artifactsWritten[]` (mirrored from the `scaffold` run); `--answers` provides the `commitStyle` cross-check.

**Algorithm (ordering is load-bearing — OQ-T3).**

1. Load the sentinel; `staged = list(sentinel["artifactsWritten"])` — the exact set bootstrap wrote (never a wildcard — REQ-SEC-02). If absent → `UsageError` (nothing to commit; resume `scaffold` first).
2. **Remove the sentinel file FIRST**, before any `git add` (REQ-SCAF-08, OQ-T3): delete `.forge-bootstrap.json` from disk so it is never staged and never enters history. Set `sentinelRemoved = True`. (The scaffolded `.gitignore` also lists it as belt-and-suspenders — 00 §8.)
3. **Stage the exact list**: `git add -- <each path in staged>` (the `--` and explicit paths guarantee no `git add -A`/`-u`/glob — REQ-SEC-02). Following the shared Git Commit Protocol, never pass `--force` or `--no-verify`.
4. **Commit or stop** (REQ-LIFE-05): if `stage_only` (or `answers["commitStyle"] == "stage-only"`), return with `committed:false`, `commitHash:null`. Otherwise make a **single** baseline commit (REQ-LIFE-06) of the whole staged scaffold (`git commit -m "<commitPrefix>: bootstrap baseline"`, identity from the project's git config per REQ-SEC-02), capture the new `commitHash`.
5. Return the `CommitResult`. On a git failure at step 3/4 the sentinel has already been removed; the helper surfaces the error (exit 2) and the run is recoverable by re-staging (the artifact list is reconstructable from disk; the skill re-runs `commit`).

**Exit codes.** `0` committed or staged; `2` git/IO failure (e.g. `git commit` rejected, no git identity).

**Findings.** None — `commit` is success-or-IO-error.

```python
def commit(target: Path, answers: Answers, stage_only: bool) -> CommitResult:
    """Stage the exact artifact list and commit or stop at staged (00 §4).

    Ordering is load-bearing (OQ-T3): the sentinel file is deleted BEFORE any
    ``git add`` so it can never be staged or enter history (REQ-SCAF-08). Staging
    uses the exact artifactsWritten[] list with ``git add -- <paths>`` — never
    ``git add -A`` (REQ-SEC-02) — and follows the shared Git Commit Protocol (never
    --force / --no-verify). When stage_only (or commitStyle == "stage-only") the
    scaffold is left staged with no commit (REQ-LIFE-05); otherwise a single
    baseline commit captures the whole scaffold plus forge.config.json (REQ-LIFE-06).

    Args:
        target: The project root being committed.
        answers: The resolved interview payload (for commitStyle + commitPrefix).
        stage_only: True to stop at staged with no commit (the --stage-only flag).

    Returns:
        A CommitResult (00 §4): committed / commitHash / staged / sentinelRemoved.

    Raises:
        UsageError: No sentinel to commit, or a git/IO failure (exit 2). On a git
            failure the sentinel is already removed; the run is re-stageable.
    """
    sentinel = read_sentinel(target)
    if sentinel is None:
        raise UsageError("no .forge-bootstrap.json sentinel to commit; run scaffold first")
    staged = list(sentinel["artifactsWritten"])

    # OQ-T3: remove the sentinel BEFORE staging so it never enters history.
    (target / SENTINEL_FILENAME).unlink(missing_ok=True)

    run(["git", "add", "--", *staged], cwd=target)

    if stage_only or answers["commitStyle"] == "stage-only":
        return {"committed": False, "commitHash": None, "staged": staged, "sentinelRemoved": True}

    message = f"{answers.get('commitPrefix', 'forge')}: bootstrap baseline"
    run(["git", "commit", "-m", message], cwd=target)
    rev = run(["git", "rev-parse", "HEAD"], cwd=target)
    return {
        "committed": True,
        "commitHash": rev.stdout.strip(),
        "staged": staged,
        "sentinelRemoved": True,
    }
```

> `answers.get("commitPrefix", "forge")` is illustrative; the prefix is the config's `commitPrefix` (default `forge`, 00 §7). The single baseline commit subsumes the whole scaffold plus `forge.config.json` because both were recorded into `artifactsWritten[]` and thus into `staged` (REQ-LIFE-06, REQ-SCAF-08: nothing is left untracked).

---

## 7. `status` — Inspect the Sentinel (REQ-LIFE-01/02)

**Purpose.** Return the parsed sentinel so the skill can drive the resume/recovery flow (answers, artifacts, status) without re-running the gate.

**CLI.** `status <target-dir> [--json]`. `--json` prints the `Sentinel` (00 §8) or `null` when none is present.

**Exit codes.** `0` always when the target is readable (sentinel present → printed; absent → `null`); `2` IO error.

**Findings.** None.

```python
def status(target: Path) -> Sentinel | None:
    """Return the parsed resume sentinel, or None when absent (00 §8).

    Reads ``{target}/.forge-bootstrap.json`` and returns it verbatim so the skill
    can present the resume/restart/cancel choice with the prior answers and the
    list of already-written artifacts already in hand (REQ-LIFE-01/02), with no
    re-interview. A missing sentinel returns None (no partial scaffold).

    Args:
        target: The project root being inspected.

    Returns:
        The Sentinel (00 §8) when present, else None.

    Raises:
        UsageError: If the sentinel exists but is unreadable or not valid JSON
            (exit 2) — a corrupt resume marker is an IO error, not a finding.
    """
    return read_sentinel(target)
```

---

## 8. Safety / I/O Layer & CLI Dispatch

### 8.1 Sentinel I/O and subprocess wrapper

```python
def read_sentinel(target: Path) -> Sentinel | None:
    """Read and parse the transient resume sentinel, or None when absent (00 §8).

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
```

`_atomic_write_text(path, text)` writes via `tempfile.mkstemp` in the destination's directory, `fsync`, then `os.replace` (the `epic-manifest.py` `atomic_write` pattern, generalized to text). `_json_text(obj)` is `json.dumps(obj, indent=2, ensure_ascii=False) + "\n"`.

### 8.2 `main()` dispatch

`main()` mirrors `epic-manifest.py` §9 exactly: an `argparse` parser with one subparser per subcommand; each takes the `target-dir` positional, and `scaffold`/`verify`/`commit` add `--answers` (required, JSON), `commit` adds `--stage-only`; `check` adds `--specs-dir` (default `./specs`); all add `--json`. The `--answers` string is parsed with `json.loads` (a malformed payload → `UsageError`, exit 2). Dispatch calls the matching function inside a `try/except` mapping `UsageError`→2, `FindingsError`→1, bare `OSError`→2; a clean return is 0. `check` raises `FindingsError(result)` when `result["eligible"]` is false and `resumeMarker` is null; `verify` raises `FindingsError(result)` when not green with the toolchain present, and `UsageError` (exit 2) when `toolchainPresent` is false.

```python
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
```

`_dispatch` resolves `--answers` (where present) to an `Answers` dict, calls the subcommand, prints its result as JSON under `--json`, and translates the gate/verify outcomes to the right exit:

- `check` → if `not result["eligible"] and result["resumeMarker"] is None`: `raise FindingsError(result)`; else print + 0.
- `scaffold` → print `{"artifactsWritten": result}`; 0.
- `verify` → if `not result["toolchainPresent"]`: `raise UsageError("toolchain missing")` (exit 2, after printing the result under `--json` so the skill still sees `toolchainPresent:false`); elif `not result["green"]`: `raise FindingsError(result)`; else print + 0.
- `commit` / `status` → print + 0 (status prints `null` when None).

---

## 9. Error Handling Summary

| Condition | Detected by | Exit | Output |
|-----------|-------------|------|--------|
| Greenfield refusal (non-meta file present, no sentinel) | `check` | 1 | `CheckResult` with `eligible:false` + `disqualifying[]` (stdout JSON) |
| Target is a file / unreadable dir | `check` | 2 | `Error: target is not a directory: …` (stderr) |
| Interrupted run / resume detected | `check` (`resumeMarker != null`) / `status` | 0 | `CheckResult.resumeMarker` / `Sentinel` (stdout) → skill routes to resume/restart/cancel |
| Corrupt sentinel | `read_sentinel` | 2 | `Error: corrupt sentinel …` (stderr) |
| Malformed `--answers` JSON | `main`/`_dispatch` | 2 | `Error: …` (stderr) |
| Template dir missing for a stack | `compose_member` | 2 | `Error: template dir not found for stack 'X': …` |
| No-overwrite of pre-existing allowed-meta file | `_write_artifact` | 0 | file kept, not recorded, not staged; skill notes it (REQ-OUT-01) |
| `git init` / `git add` / `git commit` failure | `run(check=True)` | 2 | `Error: command '…' failed: …` (stderr) |
| Missing toolchain | `verify` (`toolchainPresent:false`) | 2 | `VerifyResult` (stdout under `--json`) + `Error` (stderr); skill marks **unverified** |
| Not-green baseline (toolchain present, lint/test failed) | `verify` | 1 | `VerifyResult` with `green:false` + per-member `CommandOutcome[]` (stdout) |
| Nothing to commit (no sentinel) | `commit` | 2 | `Error: no .forge-bootstrap.json sentinel to commit; …` |

The skill surfaces every result **verbatim** and routes each non-zero outcome to its matching terminal action (00 §4; tech-spec §3.10). The four terminal outcomes — success, greenfield refusal, missing toolchain, partial-state — are each sourced from exactly one helper result here (REQ-OBS-01).

---

## Dependencies

- **00-core-definitions.md** — the canonical source this helper implements: `Stack` / `PACKAGE_MANAGERS` (§2), the greenfield allow-list `ALLOWED_META_DIRS` / `SENTINEL_FILENAME` / `ALLOWED_META_FILE_RE` (§3), the result shapes `CheckResult` / `CommandOutcome` / `VerifyResult` / `CommitResult` (§4), `Member` / `Answers` (§5), the per-stack command table (§6), the `forge.config.json` field set + `workspaces[]` (§7), the `Sentinel` schema (§8), and the exit-code contract (§9). This document does **not** redefine these; it re-states them in-module (single-file `TypedDict`s, 01 §5) and implements them.
- **01-architecture-layout.md §3** — the module skeleton this document fleshes out with full signatures; §2.2 — the portable-root invocation convention; §4 — the additive `workspaces[]` schema `write_config` conforms to.
- **03-stack-templates.md** — the per-stack template files `compose_member` copies (§1) and the CI workflow template + per-member step expansion `maybe_write_ci` delegates to (§5). This helper does **not** duplicate the templates.
- **`scripts/epic-manifest.py`** — the style / `argparse` / exit-code / `--json` / atomic-write template this module mirrors exactly.
- **`scripts/forge-init.sh`** — the config field set + defaults `write_config` reproduces for REQ-CFG-02 equivalence (mirrored, not called).
- **05-testing-strategy.md** — *downstream* consumer: the pytest suite that exercises every subcommand, each stack scaffold+verify, the monorepo + CI path, config equivalence, resume, and the commit exact-list / sentinel-removal guarantees. (Cross-reference, not a build prerequisite.)

## Verification

An engineer confirms an implementation matches this spec by checking:

- [ ] `python3 -m py_compile scripts/forge-bootstrap.py` exits 0 (valid 3.10+ syntax, 01 §6.2).
- [ ] `check` on an empty dir and on a meta-only dir (README + LICENSE + `.gitignore`) returns `eligible:true`, `disqualifying:[]` (REQ-GATE-04); on a dir with any source/manifest file returns `eligible:false` with that path in `disqualifying[]` and exits 1 (REQ-GATE-01/02); with a sentinel present returns `eligible:true` + non-null `resumeMarker` and exits 0 even over non-meta files (REQ-LIFE-02); never writes (REQ-SEC-01).
- [ ] `scaffold` writes the sentinel before any artifact, runs `git init` only when `.git/` is absent (REQ-GATE-03), composes each member's `templates/<stack>/` with tokens substituted, writes a `forge.config.json` carrying forge-init's exact field set + defaults except the resolved stack/commands plus the minimal `loopRunner` block (REQ-CFG-02), and is idempotent on re-run — already-recorded paths and pre-existing allowed-meta files are skipped, never overwritten (REQ-SCAF-09, REQ-LIFE-02).
- [ ] A monorepo `scaffold` produces a well-formed `workspaces[]` (one entry per member, resolved commands) validating against the extended schema, mixed-language members coexist (REQ-MONO-02/05), and `ci:true` emits `.github/workflows/ci.yml` with a lint+test step for **every** member (REQ-MONO-04).
- [ ] `verify` returns `green:true` exit 0 when the toolchain is present and lint+test pass (per member — REQ-MONO-03); `green:false` exit 1 when a command fails; `toolchainPresent:false` exit 2 when a probe is missing (REQ-LIFE-03/04); commands match `references/stacks/*.md` (REQ-STACK-02); generic is green with no language toolchain (REQ-STACK-03 via 03).
- [ ] `commit` removes the sentinel before staging (absent from the commit — REQ-SCAF-08, OQ-T3), stages exactly `artifactsWritten[]` via `git add -- <paths>` with no `git add -A` (REQ-SEC-02), makes a single baseline commit including `forge.config.json` (REQ-LIFE-06), and `--stage-only` leaves the scaffold staged with no commit (REQ-LIFE-05).
- [ ] `status` returns the parsed sentinel (or `null`) for the resume flow (REQ-LIFE-01/02).
- [ ] The full pytest suite (05-testing-strategy.md) passes via `bash scripts/validate.sh`.
