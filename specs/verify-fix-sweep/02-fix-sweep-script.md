# 02 — `scripts/fix-sweep.py`

> The feature's **one new code artifact**: a standalone, stdlib-only Python CLI with two
> subcommands — `sweep` (corrected-claim survivor detection over the fix delta) and
> `plan-coverage` (Fix Execution Plan cardinality assertion). This document is the
> implementation contract for that file and nothing else.
>
> Shared vocabulary lives in `00-core-definitions.md` and is **referenced, never
> redefined**: `normalize()` (§2), `Needle` (§4.1), `MIN_NEEDLE_CHARS` (§4.3),
> `VERIFICATION_SEGMENT` / `DRIFT_GATED_PREFIX` / `DRIFT_GATE_SENTINEL` (§5.2),
> `NormalizedFile` (§5.3), `SweepHit` / `DroppedNeedles` / `SweepReport` (§6.1),
> `PlanCoverageReport` (§6.2), the exit-code table (§6.3), the findings-document read
> contract (§7.1), and `UsageError` (§10). Where this document gives an implementation,
> it must be **behaviorally identical** to 00's stated contract.
>
> Locate symbols and prose anchors by **name**, never by line number.

## Requirement Coverage

| REQ ID | Requirement | Section |
|---|---|---|
| REQ-SWEEP-01 | Extract corrected text from the fix delta; search the corpus | §4.1, §4.2, §4.7 |
| REQ-SWEEP-02 | Deterministic, model-free normalized matching above a floor | §4.2, §4.3, §4.5, §4.6 |
| REQ-SWEEP-03 | Corpus = tracked + untracked, minus audit + drift-gated trees | §4.4 |
| REQ-SWEEP-07 | No git delta → visible skip, never silent | §3, §4.1, §2.3 |
| REQ-CARD-01 | Plan coverage asserted; omissions named; totals re-derived | §5.1, §5.2, §5.3 |
| REQ-CARD-04 (analog) | Graceful degradation to `applicable: false`, never a hard fail | §5.2 |
| REQ-PERF-01 | Cheap, deterministic, no network, no model calls | §7 |
| REQ-OBS-01 | Every hit names file, location, and the matched removed text | §2.3, §4.6, §4.7 |
| REQ-SEC-01 | Matched text echoed verbatim, no elision | §4.6, §2.3 |
| REQ-CONC-01 | Read-only over the corpus; no locking | §1, §3 |

Out of this document's scope by design: REQ-SWEEP-04 / REQ-SWEEP-05 / REQ-SWEEP-06 are
**agent** obligations (disposition, findings-document record, outcome routing) — the
script never writes any file. See `03-forge-fix-integration.md`. REQ-CARD-02 /
REQ-CARD-03 / REQ-CONS-01 are checklist prose — see `04-verification-checks.md`.

---

## 1. Module Layout

One file, `scripts/fix-sweep.py`, no package, no importable API (its public surface is
the CLI contract in §2). Executable bit set, shebang `#!/usr/bin/env python3`. Python
3.10+, **standard library only** (C-3). It deliberately does **not** import from
`scripts/forge-session.py` (§3).

**Read-only (REQ-CONC-01):** the script opens every corpus file with mode `"r"` and never
writes, creates, locks, or removes anything. Its only outputs are stdout, stderr, and an
exit code. No locking is designed — `references/decisions/single-writer-threat-model.md`
(#180) is the recorded position (00 §1).

### 1.1 Module docstring

Follows the standalone-script convention of `scripts/validate-traceability.py` and
`scripts/check-spec-purity.py` — a summary, a **Usage** block, and an **Exit codes**
block:

```python
#!/usr/bin/env python3
"""Sweep a fix delta for surviving occurrences of corrected text (REQ-SWEEP-01..03).

Two deterministic, model-free subcommands used by the forge-fix pass:

``sweep``          extracts the removed lines of ``git diff HEAD`` as needles and
                   reports every surviving normalized occurrence across the
                   repository's tracked and untracked files.
``plan-coverage``  asserts that a verification findings document's Fix Execution
                   Plan covers every finding it reports, naming omissions.

Usage:
    python3 fix-sweep.py sweep [--repo-root DIR] [--exclude PREFIX]...
                               [--min-chars N] [--json]
    python3 fix-sweep.py plan-coverage FINDINGS_DOC [--json]

Exit codes:
    0 = sweep found no survivors (or was skipped: no git delta);
        plan-coverage fully covered, or not applicable
    1 = sweep reported one or more survivors;
        plan-coverage found uncovered findings and/or a claimed-total mismatch
    2 = usage or environment error (bad flag, unreadable document, git failure
        inside a valid repository)
"""
```

### 1.2 Imports

```python
from __future__ import annotations

import argparse
import bisect
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Final, TypedDict
```

No other imports. `datetime` is **not** needed — dates appear only in the sweep record,
which the agent writes (00 §7.2).

### 1.3 Module-level constants

Constants defined by `00-core-definitions.md` are reproduced here (a standalone,
import-free single-file script has no shared module to import from — the same reason
`epic-manifest.py` and `forge-session.py` keep byte-identical copies of
`KNOWN_VERIFY_STATUSES`). The **values** are byte-identical to 00 §4.3/§5.2; the `#:`
doc comments in this section are the ones the shipped file carries — each cites its
00 section rather than restating 00's rationale, so the rationale has exactly one
home.

```python
#: Minimum normalized length for a removed line to become a needle (REQ-SWEEP-02).
#: 00-core-definitions.md §4.3 — also the --min-chars default.
MIN_NEEDLE_CHARS: Final[int] = 24

#: Path segment excluding findings documents from the corpus — unconditional
#: (00 §5.2).
VERIFICATION_SEGMENT: Final[str] = ".verification"

#: Drift-gated regenerated tree, excluded ONLY when the gate is detectably
#: present at DRIFT_GATE_SENTINEL (00 §5.2).
DRIFT_GATED_PREFIX: Final[str] = "adapters/"
DRIFT_GATE_SENTINEL: Final[str] = "scripts/build-adapters.py"
```

Constants **new to this document** (implementation detail, not shared vocabulary):

```python
#: Label reported in SweepReport["excludes"] for the VERIFICATION_SEGMENT rule.
#: The rule matches a path SEGMENT; the label is the human-facing prefix form.
VERIFICATION_EXCLUDE_LABEL: Final[str] = ".verification/"

#: Wall-clock bound on every git subprocess. The sweep runs inside a fix pass; a
#: hung git must fail the pass loudly (exit 2), never hang it (tech-spec §5).
GIT_TIMEOUT_SECONDS: Final[int] = 30

#: run_git() return code when git could not be executed at all (binary missing,
#: OSError) or exceeded GIT_TIMEOUT_SECONDS. Callers classify it — a probe treats
#: it as the skip path, a corpus call raises UsageError (§3).
GIT_UNAVAILABLE: Final[int] = -1

#: Non-alphanumeric run -> single space. Sole regex of the normalization contract
#: (00 §2); the `+` quantifier is what collapses runs, so no second pass is needed.
_NON_ALNUM: Final = re.compile(r"[^a-z0-9]+")

#: Unified-diff hunk header. Group 1 is the a-side start line — the only field the
#: needle line numbering needs (§4.2). `,count` is omitted by git when it is 1.
HUNK_RE: Final = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

#: Findings-document anchors (00 §7.1 declares these regexes authoritative HERE).
H2_RE: Final = re.compile(r"^##(?!#)\s*(.*?)\s*$")
H3_RE: Final = re.compile(r"^###(?!#)\s*(.*?)\s*$")
FINDING_RE: Final = re.compile(r"^### (V-\d{3}):")
STEP_RE: Final = re.compile(r"^#### Step \d+:")
ADDRESSES_RE: Final = re.compile(r"^\s*-\s*\*\*Addresses:\*\*")
FINDING_ID_RE: Final = re.compile(r"V-\d{3}")
TOTAL_FINDINGS_RE: Final = re.compile(r"Total findings:\s*(\d+)")
FENCE_RE: Final = re.compile(r"^\s*(?:```|~~~)")
```

### 1.4 Type and error declarations

The six TypedDicts (`Needle`, `NormalizedFile`, `SweepHit`, `DroppedNeedles`,
`SweepReport`, `PlanCoverageReport`) and `UsageError` are declared in this file exactly
as `00-core-definitions.md` §4.1, §5.3, §6.1, §6.2, and §10 specify — same key names,
same order, same docstrings. They are **not** restated here; copy them from 00.

`UsageError` is the **only** exception type the script defines (00 §10). Everything else
routes through exit codes.

### 1.5 Function inventory

Top-to-bottom order in the file: constants → types → `normalize` → git helper →
`sweep` pipeline (§4.1 → §4.7) → `plan-coverage` (§5) → rendering → `_build_parser` →
`main` → `sys.exit(main())`.

| Function | Section |
|---|---|
| `normalize(text)` | §1.6 |
| `run_git(args, repo_root)` | §3 |
| `resolve_repo_root(start_dir)` | §4.1 |
| `extract_needles(diff_text)` | §4.2 |
| `filter_needles(raw, added_by_file, min_chars)` | §4.3 |
| `list_corpus_paths(repo_root)` / `applicable_excludes(...)` / `is_excluded(...)` | §4.4 |
| `build_normalized_file(path, content)` / `line_for_offset(...)` | §4.5 |
| `dedupe_needles(...)` / `scan_file(...)` | §4.6 |
| `run_sweep(...)` / `render_sweep(...)` | §4.7 |
| `parse_findings_doc(text)` / `run_plan_coverage(...)` / `render_plan_coverage(...)` | §5 |
| `_build_parser()` / `main()` | §2 |

### 1.6 `normalize` (REQ-SWEEP-02)

The contract is `00-core-definitions.md` §2; the implementation is exactly its reference
semantics, with 00's docstring:

```python
def normalize(text: str) -> str:
    """Normalize text for sweep matching. See 00-core-definitions.md §2."""
    return _NON_ALNUM.sub(" ", text.lower()).strip()
```

**Error Handling:** total function — no failure mode. Non-`str` input is a programming
error, not a runtime case.

**Verification:**
- [ ] `normalize("Universal among the tracked hyperscalers.") ==
      normalize("universal, among   the\ntracked  hyperscalers")`.
- [ ] `normalize("---")` and `normalize("")` are both `""`.

---

## 2. CLI Surface

### 2.1 argparse tree

```python
def _build_parser() -> argparse.ArgumentParser:
    """Build the parser with one subparser per subcommand (epic-manifest.py idiom).

    Returns:
        The configured parser. `--json` is stored as `json_output` on both
        subcommands so `main()` can read it uniformly.
    """
    parser = argparse.ArgumentParser(prog="fix-sweep.py", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_sweep = sub.add_parser("sweep", help="Report survivors of corrected text")
    p_sweep.add_argument(
        "--repo-root", default=".",
        help="Directory inside the repository to sweep (default: cwd). The "
             "repository top level is resolved from it.",
    )
    p_sweep.add_argument(
        "--exclude", action="append", default=[], metavar="PREFIX",
        help="Additional repo-relative path prefix to exclude (repeatable).",
    )
    p_sweep.add_argument(
        "--min-chars", type=int, default=MIN_NEEDLE_CHARS, metavar="N",
        help=f"Minimum normalized needle length (default: {MIN_NEEDLE_CHARS}).",
    )
    p_sweep.add_argument(
        "--json", action="store_true", dest="json_output", help="Output as JSON"
    )

    p_plan = sub.add_parser(
        "plan-coverage", help="Assert Fix Execution Plan coverage of the findings"
    )
    p_plan.add_argument("findings_doc", metavar="FINDINGS_DOC",
                        help="Path to a verification findings document")
    p_plan.add_argument(
        "--json", action="store_true", dest="json_output", help="Output as JSON"
    )
    return parser
```

Notes binding the surface:

- `--min-chars` is **exposed for tests, not advertised in skill prose** — forge-fix
  always invokes the default (00 §4.3, `03-forge-fix-integration.md`).
- `--exclude` is the operator escape hatch for a consumer repo's own drift-gated trees;
  the fenced skill invocation passes none (tech-spec §3.6).
- Unknown flags, a missing subcommand, and a non-integer `--min-chars` are handled by
  argparse, which exits **2** with its own message — the intended exit-2 row (00 §6.3).
- A `--min-chars` value below 1 is rejected in `main()` as `UsageError("--min-chars must
  be >= 1")` (argparse cannot express it without a custom type).
- An `--exclude` value that is empty or whitespace-only is rejected in `main()` as
  `UsageError("--exclude requires a non-empty path prefix")` — an empty prefix matches
  every path and would silently empty the corpus, reporting a false clean (00 §5.2
  rule 3).

### 2.2 `main()`

```python
def main() -> int:
    """Parse arguments, dispatch, and map exceptions to exit codes.

    Returns:
        0, 1, or 2 per the exit-code table (00-core-definitions.md §6.3).
    """
    args = _build_parser().parse_args()
    try:
        if args.cmd == "sweep":
            if args.min_chars < 1:
                raise UsageError("--min-chars must be >= 1")
            report = run_sweep(
                start_dir=Path(args.repo_root),
                user_excludes=list(args.exclude),
                min_chars=args.min_chars,
            )
            render_sweep(report, args.json_output)
            return 1 if report["hits"] else 0
        if args.cmd == "plan-coverage":
            report = run_plan_coverage(Path(args.findings_doc))
            render_plan_coverage(report, args.json_output)
            return 1 if (report["uncovered"] or report["totalMismatch"]) else 0
        raise UsageError(f"unknown command: {args.cmd}")
    except UsageError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
```

The exit code is computed from the **report**, never from a side channel — the payload
and the exit code can never disagree.

### 2.3 Output formats (REQ-OBS-01, REQ-SEC-01, REQ-SWEEP-07)

With `--json`, stdout carries **exactly one** JSON object (`json.dumps(report,
indent=2)`) and no human lines. Without it, the report is rendered as lines in the
`check-spec-purity.py` reporting style (`<verdict> — <detail>`, then indented rows).

`sweep`, no survivors:

```
sweep: PASS — 0 survivor(s) in 1633 file(s) (5 needle(s), 3 below floor, 1 reflowed).
```

`sweep`, survivors (**the hit line format is fixed** — `03-forge-fix-integration.md`
reads it and `05-testing-strategy.md` pins it):

```
sweep: FAIL — 2 survivor(s) in 1633 file(s) (5 needle(s)):
  specs/other/PRD.md:41: survivor of "universal among the tracked hyperscalers" (removed at specs/x/PRD.md:12)
  src/generated/foo.ts:88: survivor of "universal among the tracked hyperscalers" (removed at specs/x/PRD.md:12)
```

`sweep`, skipped (REQ-SWEEP-07 — the notice exists even in human mode so a skip is never
silent on any surface):

```
sweep: SKIPPED — no git delta (not-a-git-repo)
```

`plan-coverage`:

```
plan-coverage: PASS — 3 finding(s), 2 step(s), all covered.
plan-coverage: NOT APPLICABLE — no `## Findings` and/or `## Fix Execution Plan` section.
plan-coverage: FAIL — 1 uncovered finding(s):
  V-003: named in no execution step's **Addresses:** field
plan-coverage: FAIL — claimed 16, actual 15 (`## Summary` total disagrees with `### V-NNN:` count)
```

Rendering rules:

- `{needle}` in the hit line is the needle's **`original`** removed text with leading and
  trailing whitespace stripped — a single-line render of already-public text, not
  elision (REQ-SEC-01). The JSON payload carries `original`/`excerpt` byte-exact.
- Exit-2 messages are a plain `Error: …` line on **stderr** with empty stdout (00 §6.3).
- Both FAIL lines are printed when a document is both uncovered and mismatched.

**Error Handling:** rendering itself cannot fail; a `BrokenPipeError` from a truncated
consumer surfaces as the `OSError` branch of `main()` (exit 2).

**Dependencies:** `SweepReport` / `PlanCoverageReport` (00 §6.1, §6.2).

**Verification:**
- [ ] `--json` stdout parses as a single JSON object with no leading human line.
- [ ] The hit line matches `^\S+:\d+: survivor of ".*" \(removed at \S+:\d+\)$`.
- [ ] A skipped sweep prints the SKIPPED line and exits 0.

---

## 3. Bounded git helper (REQ-CONC-01, REQ-SWEEP-07)

**WARNING — deliberate non-reuse.** `forge-session.py` defines `_git_output(args:
list[str]) -> str | None` (verified at `scripts/forge-session.py`, function
`_git_output`), but it is not importable without loading that ~7k-line module, and its
"any failure → `None`" collapse cannot distinguish a missing repository (skip, exit 0)
from a git failure inside a valid one (exit 2). `fix-sweep.py` therefore carries its own
helper following the same conventions (tech-spec §6, item 8). This is the only
duplication the feature introduces.

```python
def run_git(args: list[str], repo_root: Path) -> tuple[int, str, str]:
    """Run one bounded, read-only git command with cwd set to `repo_root`.

    The helper NEVER classifies: it reports what happened and lets the caller
    decide whether the outcome is the skip path (00 §10) or a UsageError. A git
    binary that cannot be executed at all, or one that exceeds
    GIT_TIMEOUT_SECONDS, yields GIT_UNAVAILABLE rather than raising — the probe
    calls in resolve_repo_root() must treat a missing git as "not a repo"
    (REQ-SWEEP-07), while list_corpus_paths() must treat it as exit 2.

    Args:
        args: git arguments after the program name, e.g. ["rev-parse", "HEAD"].
        repo_root: Directory used as the subprocess cwd. Every git invocation in
            this script runs from the repository top level so that paths in
            output are repo-relative (§4.1).

    Returns:
        (returncode, stdout, stderr). returncode is GIT_UNAVAILABLE (-1) when
        git could not be run or timed out; stdout is "" in that case and stderr
        carries a short diagnostic.
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return GIT_UNAVAILABLE, "", str(exc)
    return proc.returncode, proc.stdout, proc.stderr
```

Classification table (the whole of 00 §10's git rows, in one place):

| Call | Non-zero / `GIT_UNAVAILABLE` outcome |
|---|---|
| `rev-parse --git-dir` | skip, `reason="not-a-git-repo"`, exit 0 |
| `rev-parse --show-toplevel` | `UsageError` — a repo with no working tree (bare) cannot be swept |
| `rev-parse HEAD` | skip, `reason="no-head"`, exit 0 |
| `diff HEAD …` | `UsageError`, exit 2 |
| `ls-files …` | `UsageError`, exit 2 |

`text=True` decodes with the locale encoding; git output for these commands is ASCII or
UTF-8, and a decode failure surfaces as a `UnicodeDecodeError` (a `ValueError`) that
propagates as an unhandled crash — acceptable, and not reachable with the `-z` /
`core.quotePath=false` invocations specified in §4.2 and §4.4.

**Verification:**
- [ ] `run_git(["rev-parse", "--git-dir"], tmp_path)` on a non-repo returns a non-zero
      code, not an exception.
- [ ] With `PATH` emptied of `git`, the same call returns `GIT_UNAVAILABLE`.

---

## 4. `sweep` pipeline

### 4.1 Repository resolution and skip detection (REQ-SWEEP-01, REQ-SWEEP-07)

```python
def resolve_repo_root(start_dir: Path) -> tuple[Path | None, str | None]:
    """Resolve the repository top level and detect the two skip conditions.

    Probes in order: `rev-parse --git-dir` (is this a repository at all?),
    `rev-parse --show-toplevel` (where is the working tree?), and
    `rev-parse HEAD` (is there a baseline to diff against?). The top level —
    not `start_dir` — becomes the cwd of every later git call, so a sweep
    launched from a subdirectory still enumerates the whole corpus rather than
    the subtree `git ls-files` would default to.

    Args:
        start_dir: The --repo-root value (default: the process cwd).

    Returns:
        (repo_root, None) when the sweep can run, or (None, reason) where reason
        is "not-a-git-repo" or "no-head" — the two values SweepReport["reason"]
        admits (00 §6.1).

    Raises:
        UsageError: The repository exists but has no working tree (a bare repo:
            --git-dir succeeds while --show-toplevel fails), or --show-toplevel
            fails for any other reason. Not a skip — an operational failure
            (exit 2), and forge-fix never runs in a bare repo.
    """
```

Sequence:

1. `run_git(["rev-parse", "--git-dir"], start_dir)` — non-zero **or**
   `GIT_UNAVAILABLE` → `(None, "not-a-git-repo")`. A missing `git` binary lands here by
   design (tech-spec §9: git's absence is the skip path, not an install requirement); so
   does a `start_dir` that does not exist, because `subprocess.run` raises `OSError` on a
   bad cwd and the helper converts it. A **timeout** on this probe also lands here — rare,
   and the resulting notice is visible, which is REQ-SWEEP-07's entire obligation.
2. `run_git(["rev-parse", "--show-toplevel"], start_dir)` — non-zero → `UsageError`.
   Success → `repo_root = Path(stdout.strip())`.
3. `run_git(["rev-parse", "HEAD"], repo_root)` — non-zero (unborn branch: `git init`
   with no commit) → `(None, "no-head")`.

A skip returns the skip payload of 00 §6.1 verbatim (`baseline: null`, empty
`needles`/`hits`, zeroed `droppedNeedles`, empty `excludes`, `filesScanned: 0`) with
**exit 0**. The script never writes the NOT-RUN notice — the forge-fix agent converts the
payload (00 §7.2, `03-forge-fix-integration.md`).

**Error Handling:** as tabulated in §3. No path here can crash on a missing directory,
missing git, or an unborn branch.

**Verification:**
- [ ] A plain `tmp_path` yields `reason="not-a-git-repo"`, exit 0, `skipped: true`.
- [ ] A fresh `git init` with no commit yields `reason="no-head"`, exit 0.
- [ ] A sweep launched with `--repo-root` pointing at a **subdirectory** of a repo
      enumerates the same corpus as one launched at the top level.

### 4.2 Needle extraction from the fix delta (REQ-SWEEP-01, REQ-SWEEP-02)

The delta is fixed by `00-core-definitions.md` §3: `git diff HEAD --unified=0
--no-color`, taken pre-commit against the literal baseline `"HEAD"`. The invocation adds
`-c core.quotePath=false` so non-ASCII paths arrive unescaped:

```python
["-c", "core.quotePath=false", "diff", "HEAD", "--unified=0", "--no-color"]
```

```python
def extract_needles(diff_text: str) -> tuple[list[Needle], dict[str, list[str]]]:
    """Parse a unified diff into raw needles and per-file added lines.

    `--unified=0` means every diff body line is a change: hunk headers delimit
    the changed runs exactly, so a-side line numbers are computable without
    context-line bookkeeping (00 §4.2).

    Parse contract:
      * `diff --git …` resets file state and clears the in-hunk flag.
      * `--- a/{path}` sets the a-side path; `+++ b/{path}` sets the b-side path.
        A leading `a/`/`b/` prefix is stripped; `/dev/null` maps to None. A path
        git C-quoted (embedded quote, backslash, or control character) is
        unquoted best-effort by stripping the surrounding double quotes; a
        mis-decoded path affects only provenance reporting, never matching.
      * `@@ -a[,b] +c[,d] @@` sets the a-side counter to `a` and raises the
        in-hunk flag.
      * ONLY while in-hunk: a line starting with `-` is a removed line whose
        content is the text after the prefix, at the current a-side counter,
        which then advances by one; a line starting with `+` is an added line,
        appended to added_by_file[b_path] (it does not move the a-side counter);
        anything else (` `, `\\`) is ignored.
        Gating on the in-hunk flag is what keeps a removed line whose content is
        literally `--` (rendered `---`) from being mistaken for a file header —
        headers only ever appear before the first `@@` of a file.
      * Removed lines whose a-side path is None (a file created by the delta)
        cannot occur; removed lines in a deleted file carry the a-side path.

    Args:
        diff_text: stdout of the diff invocation above.

    Returns:
        (raw_needles, added_by_file) where raw_needles are Needle dicts in
        document order with `normalized` already computed, and added_by_file maps
        each b-side path to its normalized non-empty added lines in order — the
        input to reflow suppression (§4.3).
    """
```

Every removed line becomes a raw `Needle` — filtering happens in §4.3, so
`droppedNeedles` can count what the filters removed.

Benign cases needing no special handling: binary files (`Binary files … differ` produces
no body lines), pure renames (no body lines), renames with edits (a-side path is the old
path; moved text is caught by reflow suppression), and submodule pointers
(`-Subproject commit …` normalizes above the floor and is simply searched for, matching
nothing).

**Error Handling:** a `GIT_UNAVAILABLE` or non-zero diff → `UsageError` (§3). A diff line
the contract does not recognize is ignored, never fatal — the parser must not raise on
unexpected input.

**Dependencies:** `Needle` (00 §4.1), `normalize()` (§1.6).

**Verification:**
- [ ] A two-hunk diff yields needles whose `line` equals the a-side line each removed
      line occupied **before** the fix.
- [ ] A removed line whose content is `--` produces a needle, not a path change.
- [ ] `added_by_file` contains an entry for every file with at least one `+` line.

### 4.3 Filters, in order (REQ-SWEEP-02)

```python
def filter_needles(
    raw: list[Needle],
    added_by_file: dict[str, list[str]],
    min_chars: int,
) -> tuple[list[Needle], DroppedNeedles]:
    """Apply the two extraction filters of 00 §4.3, in order, with counters.

    1. Length floor: `len(needle["normalized"]) < min_chars` -> dropped,
       counted in `belowFloor`. A line that normalizes to "" is dropped here.
    2. Reflow/move suppression: the needle's normalized text appearing as a
       substring of the delta's added text -> dropped, counted in
       `reflowSuppressed`. Text merely moved or re-wrapped was not corrected;
       sweeping it would flag every reflow as a survivor.

    The order matters for the counters: a below-floor needle is counted ONCE,
    in `belowFloor`, and never tested for reflow.

    The added text is built once per run: per file, its normalized added lines
    joined with a single space (in diff order); then those per-file strings
    joined with a single space, in the order files appeared in the diff (00
    §4.3, "concatenated per file then joined delta-wide"). Joining rather than
    testing lines individually is deliberate — a corrected sentence re-wrapped
    across new line breaks must still suppress. The delta-wide join can in
    principle suppress a needle that spans a file boundary in the concatenation;
    that is the recorded contract and errs toward silence on moves rather than
    noise.

    Args:
        raw: Needles in extraction order (§4.2).
        added_by_file: Normalized added lines per b-side path (§4.2).
        min_chars: The --min-chars value; MIN_NEEDLE_CHARS by default.

    Returns:
        (surviving needles in extraction order, the DroppedNeedles counters).
    """
```

Duplicate needles (identical `normalized` from different removed sites) are **kept
distinct** in the returned list — each carries its own provenance and all appear in
`SweepReport["needles"]` (00 §4.3). Deduplication happens only at match time (§4.6).

No superset suppression: if needle A's normalized text is a substring of needle B's, both
survive and both are searched. Milestone 1 errs toward recall (tech-spec §3.3).

**Error Handling:** total function.

**Dependencies:** `DroppedNeedles` (00 §6.1), `MIN_NEEDLE_CHARS` (00 §4.3).

**Verification:**
- [ ] A removed line normalizing to 23 characters is dropped; 24 survives.
- [ ] A removed line that reappears verbatim among the added lines yields no needle and
      increments `reflowSuppressed`.
- [ ] A removed sentence re-added split across two `+` lines is suppressed.
- [ ] `belowFloor + reflowSuppressed + len(needles) == len(raw)`.

### 4.4 Corpus enumeration and exclusions (REQ-SWEEP-03)

```python
def list_corpus_paths(repo_root: Path) -> list[str]:
    """Enumerate candidate corpus paths: tracked plus untracked-not-ignored.

    Runs `git ls-files -z --cached --others --exclude-standard` (tech-spec §3.4's
    command, with `-z` added here — NUL-terminated so paths containing spaces,
    quotes, or newlines survive intact and no quoting mode can mangle them; 00
    §5.1 carries the same flag). During an unresolved
    merge, `--cached` lists a conflicted path once per stage; entries are
    de-duplicated preserving first appearance, then sorted lexicographically so
    the scan order — and therefore every tie-break in the output — is
    deterministic.

    Args:
        repo_root: Repository top level (§4.1); also the subprocess cwd.

    Returns:
        Sorted, unique, repo-relative POSIX paths.

    Raises:
        UsageError: ls-files exited non-zero or could not be run (§3).
    """


def applicable_excludes(repo_root: Path, user_excludes: list[str]) -> list[str]:
    """Compute the exclusion labels actually in force this run (00 §5.2).

    Order, matching SweepReport["excludes"]:
      1. VERIFICATION_EXCLUDE_LABEL — always.
      2. DRIFT_GATED_PREFIX — ONLY when (repo_root / DRIFT_GATE_SENTINEL) is an
         existing file. REQ-SWEEP-03 defines a CLASS (trees a mechanical drift
         gate already keeps fresh); `adapters/` is only this repository's
         instance, and a consumer repo's ungated `adapters/` must be swept, not
         silently dropped.
      3. Each --exclude value, in the order given.

    Args:
        repo_root: Repository top level.
        user_excludes: Raw --exclude values.

    Returns:
        The labels, in application order, for the payload and for is_excluded().
    """


def is_excluded(path: str, excludes: list[str], user_excludes: list[str]) -> bool:
    """Decide whether one repo-relative path is out of corpus (00 §5.2).

    Rules, in evaluation order:
      1. VERIFICATION_SEGMENT appears as a path SEGMENT — `".verification" in
         PurePosixPath(path).parts` — at any depth, unconditionally. Segment
         matching, not prefix matching: findings documents live at
         `{featureDir}/.verification/…`, never at the repo root.
      2. The path starts with DRIFT_GATED_PREFIX and that label is present in
         `excludes` (i.e. the gate sentinel was found).
      3. The path starts with any of `user_excludes`, compared as a plain string
         prefix against the repo-relative POSIX path.

    Args:
        path: Repo-relative POSIX path from list_corpus_paths().
        excludes: Labels from applicable_excludes() (used for rule 2's gate).
        user_excludes: The --exclude values (rule 3).

    Returns:
        True when the path must not be read or matched.
    """
```

**No pre-exclusion of historical corpora** — prior features' `specs/`, `CHANGELOG.md`,
and `STATUS.md` are swept. The motivating F-5 survivor lived in a spec artifact, so
recall wins; hits there disposition cheaply as "historical record" (00 §8).

Reading each surviving path:

```python
content = (repo_root / path).read_text(encoding="utf-8")
```

- `UnicodeDecodeError` → skip silently (binaries), **not** counted in `filesScanned`.
- `OSError` (a directory entry such as a submodule gitlink, a dangling symlink, a file
  removed between enumeration and read, a permission error) → skip silently, not
  counted. Never fatal (00 §10, tech-spec §7).
- Everything else increments `filesScanned` — so the counter means "files actually read
  and matched", exactly as 00 §6.1 states.

**Verification:**
- [ ] `specs/f/.verification/VERIFY-specs-2026-01-01.md` is excluded; a file literally
      named `verification.md` is not.
- [ ] With `scripts/build-adapters.py` present, `adapters/x/skills/y.md` is excluded;
      with the sentinel absent, the same path is scanned.
- [ ] `--exclude vendor/` removes `vendor/lib.md` and leaves `vendored.md` in corpus.
- [ ] A binary file in the corpus does not raise and does not increment `filesScanned`.

### 4.5 `NormalizedFile` construction (REQ-SWEEP-02, REQ-PERF-01)

```python
def build_normalized_file(path: str, content: str) -> NormalizedFile:
    """Normalize a file into one blob plus a blob-offset -> line-number map.

    The blob is behaviorally `normalize(content)`: each original line is
    normalized independently and the non-empty results are joined with a single
    space. That is identical to normalizing the whole content, because the line
    break between two lines is itself a non-alphanumeric run that collapses to
    one space — and building it line-wise is what makes `line_starts` free.

    Algorithm, per original line (1-based) of `content.splitlines()`:
      * piece = normalize(raw_line).
      * If piece is empty (blank line, or punctuation only), record
        (current_offset, line_number) as a zero-width entry and continue. The
        entry keeps the map total over lines while contributing no blob text;
        because it is recorded BEFORE the following line's entry and carries a
        strictly smaller-or-equal offset, the bisect in line_for_offset() can
        never attribute a match to it (no match can begin at a separator).
      * Otherwise: if the blob is non-empty, append a single space separator and
        advance the offset by 1; then record (current_offset, line_number) —
        pointing at the piece's FIRST character — and append the piece,
        advancing the offset by len(piece).

    `line_starts` is therefore sorted by offset by construction, which is what
    line_for_offset()'s bisect requires.

    Args:
        path: Repo-relative POSIX path (stored on the result).
        content: The file's working-tree text (00 §3 — content is read post-fix,
            so just-corrected sites read as corrected, not as survivors).

    Returns:
        The NormalizedFile (00 §5.3). The ORIGINAL lines are deliberately not
        stored on it — 00 fixes the TypedDict's three keys — so the caller keeps
        `content.splitlines()` alongside it for excerpt rendering (§4.6).
    """


def line_for_offset(nf: NormalizedFile, offset: int) -> int:
    """Map a blob offset back to a 1-based line number in the original file.

    Uses `bisect.bisect_right` over the offsets of `nf["line_starts"]`, taking
    the entry at index-1: the LAST pair whose blob_offset <= offset. When a
    zero-width (blank-line) entry ties with the following real entry, bisect_right
    selects the later — the line whose text actually begins there.

    Args:
        nf: A NormalizedFile from build_normalized_file().
        offset: A blob offset, expected to be a match start or end.

    Returns:
        The 1-based original line number; 1 for an empty map (empty file, which
        cannot produce a match anyway).
    """
```

Implementation note: keep the offsets in a parallel `list[int]` built once per file so
`bisect_right` needs no key function on Python 3.10 (`bisect`'s `key=` parameter is 3.10+
but a parallel list is cheaper and clearer).

**Error Handling:** total functions — both operate on already-decoded text.

**Dependencies:** `NormalizedFile` (00 §5.3), `normalize()` (§1.6).

**Verification:**
- [ ] `build_normalized_file(p, content)["blob"] == normalize(content)` for a fixture
      containing blank lines, punctuation-only lines, CRLF line endings, and a trailing
      newline.
- [ ] A needle matching text on original line 5 maps back to 5, with a blank line at 3.
- [ ] A needle spanning a line break maps to the line where the match **begins**.

### 4.6 The matching loop (REQ-SWEEP-02, REQ-OBS-01, REQ-SEC-01)

**Resolved contract — one hit per (file, needle):** a distinct normalized needle is
reported **once per file**, at its **first** match offset. Rationale: disposition is
recorded per file + needle (00 §7.2: a re-run matches previously dispositioned hits by
`(file, needle)`), so reporting every occurrence in a file would generate hits the
disposition vocabulary cannot address separately, and a second occurrence in the same
file is normally fixed by the same edit — when it is not, the re-run's `FIXED`
re-report is what catches it (`03-forge-fix-integration.md` §4.4). A survivor in a
*different* file is always a separate hit.

```python
def dedupe_needles(needles: list[Needle]) -> list[Needle]:
    """Pick one representative per distinct normalized text, first extracted wins.

    00 §4.3: duplicate needles stay distinct in the payload, but a corpus hit
    reports the FIRST extracted needle matching it. Deduplicating here makes
    that deterministic and removes redundant str.find() calls.

    Args:
        needles: Surviving needles in extraction order (§4.3).

    Returns:
        Representatives in extraction order.
    """


def scan_file(
    nf: NormalizedFile,
    original_lines: list[str],
    representatives: list[Needle],
) -> list[SweepHit]:
    """Search one prepared corpus file for every representative needle.

    For each representative, in extraction order:
      * `offset = nf["blob"].find(needle["normalized"])`; -1 -> no hit.
      * line   = line_for_offset(nf, offset)
      * end    = line_for_offset(nf, offset + len(needle["normalized"]) - 1)
      * excerpt = "\\n".join(original_lines[line - 1 : end]) — the original text
        of every line the match span overlaps, verbatim and unelided
        (REQ-OBS-01, REQ-SEC-01: the text is already in git history).
      * The hit's `needle` is the representative's ORIGINAL removed text, and
        `sourceFile`/`sourceLine` its provenance.

    The file a needle was removed from is scanned like any other (00 §5.3,
    "self-file hits count"): a surviving duplicate two sections below the
    corrected site is the F-5 self-contradiction and must be reported. The
    corrected site itself does not match because content is read post-fix.

    Args:
        nf: The prepared file (§4.5).
        original_lines: `content.splitlines()` for the same file.
        representatives: Output of dedupe_needles().

    Returns:
        Hits for this file, in representative order; the caller sorts globally.
    """
```

**Global ordering (determinism).** `SweepReport["hits"]` is sorted by
`(file, line, representative_index)`. The third key breaks the tie when two different
needles match on the same line of the same file; `representative_index` is the needle's
position in `dedupe_needles()`'s output, which is fixed by diff order. The sort is total,
so two runs over an unchanged tree emit byte-identical output.

**No short-circuit on an empty needle set.** When the filters leave no needles, the
corpus is still enumerated and read: `filesScanned` is a reported observable
(REQ-OBS-01), and a payload claiming `filesScanned: 0` for a healthy repository would be
misleading evidence in the milestone-2 archive (tech-spec §10). The cost is one bounded
pass (§7).

**Error Handling:** per-file read failures are handled by the caller (§4.4) before
`scan_file` is reached; `scan_file` itself is total.

**Dependencies:** `SweepHit` (00 §6.1), `NormalizedFile` (00 §5.3).

**Verification:**
- [ ] A needle occurring twice in one file yields exactly one hit, at the first
      occurrence's line.
- [ ] The same needle surviving in two files yields two hits.
- [ ] Hits are sorted by `(file, line)`; two runs produce identical JSON.
- [ ] A hit's `excerpt` contains the original punctuation and casing of the matched
      region.

### 4.7 Report assembly and exit selection (REQ-SWEEP-01, REQ-OBS-01)

```python
def run_sweep(
    start_dir: Path,
    user_excludes: list[str],
    min_chars: int,
) -> SweepReport:
    """Execute the whole sweep and return the payload (00 §6.1).

    Steps: resolve_repo_root() -> skip payload or continue; run the diff;
    extract_needles(); filter_needles(); applicable_excludes();
    list_corpus_paths(); for each non-excluded readable path
    build_normalized_file() + scan_file(); sort hits; assemble.

    Field sources: `skipped`/`reason` from resolve_repo_root(); `baseline` is
    the literal "HEAD" when the sweep ran and None when skipped (00 §3);
    `needles` are ALL survivors of §4.3 (duplicates included), in extraction
    order; `droppedNeedles` from §4.3; `excludes` from applicable_excludes();
    `filesScanned` counts files actually read and matched; `hits` are sorted per
    §4.6.

    Args:
        start_dir: The --repo-root value.
        user_excludes: --exclude values, in order.
        min_chars: --min-chars value.

    Returns:
        A fully populated SweepReport. Never partially populated: the skip shape
        of 00 §6.1 fills every key.

    Raises:
        UsageError: Any git failure inside a valid repository, or a bare repo
            (§3, §4.1) — exit 2, and forge-fix closes `failed` (00 §8.2).
    """
```

Exit selection lives in `main()` (§2.2): `1 if report["hits"] else 0`. A **skipped** run
has no hits and therefore exits 0 — absence of a delta is not a finding (00 §6.3).

**Verification:**
- [ ] Survivors present → exit 1 and every hit appears in both renderings.
- [ ] Clean tree with needles → exit 0, `hits: []`, `filesScanned > 0`.
- [ ] Skip → exit 0 and every key of the 00 §6.1 skip shape is present.
- [ ] Git failure inside a valid repo → exit 2, empty stdout, one `Error: …` stderr line.

---

## 5. `plan-coverage` (REQ-CARD-01, REQ-CARD-04 analog)

### 5.1 Section-scoped parsing

The read contract is `00-core-definitions.md` §7.1; the regexes in §1.3 are its
authoritative implementation. Parsing is a single forward pass with a small state
machine — heading *level* scoping is what keeps a `### V-NNN:` heading in an unrelated
section, or an `**Addresses:**` line in a narrative paragraph, from counting.

```python
def parse_findings_doc(text: str) -> PlanCoverageReport:
    """Parse a findings document into the coverage payload (00 §6.2).

    State carried per line: `h2` (the current `## ` heading text, reset by every
    `## ` line), `h3` (the current `### ` heading text, reset by every `## ` and
    every `### ` line), and `in_fence` (toggled by a line matching FENCE_RE).
    Lines inside a fence are skipped entirely — the findings template ships
    fenced markdown examples containing `### V-001:` and `**Addresses:**`
    literals, and counting those would fabricate findings or coverage. This is a
    strengthening of 00 §7.1 that changes no regex.

    Scoped recognitions (each ONLY under its stated scope):
      * `### V-NNN:` (FINDING_RE) while h2 == "Findings" -> append the id to
        `findings` in document order (duplicates ignored: first wins).
      * `#### Step N:` (STEP_RE) while h2 == "Fix Execution Plan" and
        h3 == "Execution Steps" -> increment `steps`.
      * `- **Addresses:** …` (ADDRESSES_RE) in the same scope -> every
        FINDING_ID_RE match on that line joins the covered set. Scope is the
        SECTION, not an enclosing step heading: a mis-numbered `#### Step`
        heading must not silently drop the coverage it declares — this check
        exists to catch MISSING coverage, so it errs toward recognizing it.
      * `Total findings: N` (TOTAL_FINDINGS_RE) while h2 == "Summary" -> the
        first such match sets `claimedTotal`; later ones are ignored.

    Presence of the `## Findings` and `## Fix Execution Plan` headings is
    recorded as the pass proceeds and drives applicability (§5.2).

    Args:
        text: The full document text.

    Returns:
        A fully populated PlanCoverageReport (00 §6.2).
    """
```

An `**Addresses:**` line naming an id with no `### V-NNN:` heading (a typo, or a
reference to another round's finding) is recorded in `covered` but, having no
corresponding finding, affects neither `uncovered` nor the totals. It is not reported —
milestone 1 asserts coverage of the findings set, not the converse.

### 5.2 Applicability, uncovered set, totals (REQ-CARD-01, REQ-CARD-04)

- **`applicable`** is `False` when the document has **no** `## Findings` heading **or**
  **no** `## Fix Execution Plan` heading. Then `findings`, `covered`, and `uncovered` are
  empty, `steps` and `actualTotal` are 0, `claimedTotal` is `None`, `totalMismatch` is
  `False`, and the exit code is **0**. A document that is not a findings document, or a
  findings report written before its plan exists, degrades to not-applicable — never a
  hard fail (REQ-CARD-04's analog at the fix-pass level).
- **`covered`** = findings ids appearing in ≥1 `**Addresses:**` field, in `findings`
  order. **`uncovered`** = `findings` minus `covered`, in `findings` order — **omissions
  by name, never a count delta** (REQ-CARD-01). This is the 15-of-16 incident class: the
  dropped item is *named*.
- **`actualTotal`** = `len(findings)`, always re-derived from the `### V-NNN:` headings
  and never trusted from prose. **`claimedTotal`** is the `## Summary` value or `None`.
  **`totalMismatch`** is `True` iff `claimedTotal is not None and claimedTotal !=
  actualTotal`; a document with no Summary total has `claimedTotal: None` and
  `totalMismatch: False`.
- **Exit 1** iff `uncovered` is non-empty **or** `totalMismatch` is `True` (00 §6.3).
  Both conditions are reported when both hold.

A zero-findings document with both sections present is applicable, fully covered, and
exits 0 — the vacuous case is a pass, not a failure.

### 5.3 Entry point and rendering

```python
def run_plan_coverage(doc_path: Path) -> PlanCoverageReport:
    """Read and parse a findings document.

    Args:
        doc_path: The FINDINGS_DOC argument.

    Returns:
        The PlanCoverageReport from parse_findings_doc().

    Raises:
        UsageError: The path does not exist, is a directory, is unreadable, or
            is not valid UTF-8 — exit 2 (00 §10: unreadable path is an error,
            while a readable-but-unrecognizable document is `applicable: false`).
    """
```

Rendering per §2.3. `render_plan_coverage(report, json_output)` prints the JSON object
under `--json`, otherwise the PASS / NOT APPLICABLE / FAIL lines, with one indented
`  {id}: named in no execution step's **Addresses:** field` row per uncovered id and the
`claimed N, actual M` line when `totalMismatch`.

**Error Handling:**
- Missing / directory / permission / decode failure → `UsageError` → `Error: …` on
  stderr, exit 2.
- Present but structurally unrecognizable → `applicable: false`, exit 0 (tech-spec §7).
- The parser must not raise on any text input: an unterminated fence, a `####` heading
  outside any `##`, or CRLF endings are all tolerated.

**Dependencies:** `PlanCoverageReport` (00 §6.2), the findings-document read contract
(00 §7.1), `UsageError` (00 §10). The template itself
(`skills/forge-verify/references/findings-template.md`) is a **read-only** dependency —
this feature does not modify it (`01-architecture-layout.md` §2).

**Verification:**
- [ ] A 16-findings / 15-covered document exits 1 and names exactly the missing id.
- [ ] `## Summary` claiming 16 with 15 `### V-NNN:` headings prints `claimed 16, actual
      15` and exits 1.
- [ ] Full coverage with consistent totals exits 0 with `applicable: true`.
- [ ] A document with no `## Fix Execution Plan` exits 0 with `applicable: false`.
- [ ] `### V-001:` inside a fenced block does not become a finding.
- [ ] A nonexistent path exits 2 with an `Error: …` stderr line and empty stdout.

---

## 6. Error Handling (consolidated, tech-spec §7)

| Condition | Behavior | Exit |
|---|---|---|
| Not a git repository, or `git` missing from PATH | Skip payload, `reason="not-a-git-repo"` | 0 |
| Valid repo, unborn branch (no HEAD) | Skip payload, `reason="no-head"` | 0 |
| Bare repo (no working tree) | `UsageError` — `Error: repository has no working tree (bare repo): {repo_root}` | 2 |
| `git diff` / `git ls-files` non-zero or timed out | `UsageError` — `Error: git {subcommand} failed ({rc}): {first line of git stderr}` | 2 |
| Corpus file fails UTF-8 decode (binary) | Skipped silently; not counted in `filesScanned` | — |
| Corpus file unreadable / vanished / is a directory entry | Skipped silently; not counted | — |
| `--min-chars` below 1 | `UsageError` | 2 |
| `--exclude` empty or whitespace-only | `UsageError` — `Error: --exclude requires a non-empty path prefix` | 2 |
| Unknown flag / missing subcommand | argparse's own message | 2 |
| `plan-coverage` path missing, unreadable, or not UTF-8 | `UsageError` — `Error: cannot read findings document: {path} ({reason})` | 2 |
| `plan-coverage` document with no recognizable sections | `applicable: false` | 0 |
| Survivors found | Report rendered | 1 |
| Uncovered findings and/or claimed-total mismatch | Report rendered | 1 |
| Unexpected exception (implementation bug) | Traceback on stderr, empty stdout — callers distinguish from "survivors found" by the **absent JSON payload** | 1 (Python default) |

Two invariants over the whole table: **never silent** — a skip always produces a visible
line (human mode) or `skipped: true` (JSON), which the agent converts into the Fix
Progress NOT-RUN notice (REQ-SWEEP-07, `03-forge-fix-integration.md`); and **never
partial** — every exit-0/1 path emits a complete payload, so a caller can always read the
outcome from the payload rather than inferring it from the exit code.

An exit 2 from either subcommand routes forge-fix to the existing `failed` outcome row
(00 §8.2) — an operational failure, not a skip. No new outcome values exist (C-6).

---

## 7. Performance (REQ-PERF-01)

The cost model's **shape** is the contract; wall-clock is not asserted anywhere in CI
(tech-spec §3.8 — timing assertions on shared runners are flaky by construction).
`05-testing-strategy.md` pins the shape; §10 of the tech spec records that wall-clock is
*observed* at milestone acceptance on the first real fix pass.

The pinned shape:

1. **Bounded git work** — exactly four to five `git` invocations per run (`rev-parse`
   ×3, `diff`, `ls-files`), each capped at `GIT_TIMEOUT_SECONDS`. No git call is made
   per corpus file.
2. **One read + normalize pass over the corpus** — each surviving path is read whole
   once, normalized once into a blob + offset map, matched, and released. No file is read
   twice; nothing is cached across runs; no directory is walked outside `ls-files`'s
   output.
3. **Needle count bounded by the delta** — the search set is the removed lines of one fix
   delta after two filters, not by the corpus. Total matching work is
   O(corpus bytes × distinct surviving needles) `str.find` calls (C-implemented), single
   process.
4. **No network, no model calls, no subprocess per file, no concurrency** — deterministic
   and model-free (C-2), so two runs over an unchanged tree produce byte-identical
   output.

Whole-file reads (rather than streaming) are deliberate: forge corpora are small text
files, and the blob + offset map is precisely what makes reflow matching and line
reporting cheap (00 §5.3).

**Verification:**
- [ ] A run over a corpus of N files performs N reads (assertable by counting
      `Path.read_text` calls or by an `strace`-free monkeypatch counter).
- [ ] The number of `subprocess.run` calls does not grow with corpus size.

---

## 8. Example Usage

Inside a repository, mid fix pass, with the tree dirty:

```console
$ python3 scripts/fix-sweep.py sweep
sweep: FAIL — 2 survivor(s) in 1633 file(s) (5 needle(s)):
  specs/other/PRD.md:41: survivor of "universal among the tracked hyperscalers" (removed at specs/x/PRD.md:12)
  src/generated/foo.ts:88: survivor of "universal among the tracked hyperscalers" (removed at specs/x/PRD.md:12)
$ echo $?
1
```

Machine-readable form, as forge-fix invokes it (`03-forge-fix-integration.md`):

```console
$ python3 "$R/scripts/fix-sweep.py" sweep --json
{
  "skipped": false,
  "reason": null,
  "baseline": "HEAD",
  "needles": [ { "file": "specs/x/PRD.md", "line": 12, "normalized": "…", "original": "…" } ],
  "droppedNeedles": { "belowFloor": 3, "reflowSuppressed": 1 },
  "excludes": [".verification/", "adapters/"],
  "filesScanned": 1633,
  "hits": [ … ]
}
```

Pre-flight, before any fix executes:

```console
$ python3 scripts/fix-sweep.py plan-coverage specs/f/.verification/VERIFY-specs-2026-08-11.md
plan-coverage: FAIL — 1 uncovered finding(s):
  V-016: named in no execution step's **Addresses:** field
$ echo $?
1
```

Outside a repository:

```console
$ python3 scripts/fix-sweep.py sweep --repo-root /tmp/empty
sweep: SKIPPED — no git delta (not-a-git-repo)
$ echo $?
0
```

---

## 9. Dependencies

**Spec documents that must be implemented first:** `00-core-definitions.md` only — its
`normalize()` contract, `Needle` / `NormalizedFile` / `SweepHit` / `DroppedNeedles` /
`SweepReport` / `PlanCoverageReport` TypedDicts, `MIN_NEEDLE_CHARS`,
`VERIFICATION_SEGMENT` / `DRIFT_GATED_PREFIX` / `DRIFT_GATE_SENTINEL`, the exit-code
table, the findings-document read contract, and `UsageError` are all reproduced (not
re-derived) in this file. Nothing else in the suite blocks this document:
`01-architecture-layout.md` §3 places `scripts/fix-sweep.py` first in the dependency
graph with no upstream.

**Documents that depend on this one:**
- `03-forge-fix-integration.md` — consumes the CLI: `plan-coverage` at forge-fix Step 2,
  `sweep` at the close of Step 4, the hit-line and skip formats of §2.3, and the exit-code
  routing of §6.
- `05-testing-strategy.md` — tests every function specified here in
  `tests/test_fix_sweep.py`, and owns the `RUNTIME_HELPERS` length pin that ships this
  script into non-Claude adapter bundles (`01-architecture-layout.md` §5.1).
- `04-verification-checks.md` — independent of this document (checklist prose only).

**Runtime dependencies:** Python 3 standard library only (C-3); `git` on PATH, whose
absence is the skip path rather than an install requirement.

**Explicit non-dependencies:** `scripts/forge-session.py` (not imported — §3),
`forge.config.json`, `references/pipeline-state-schema.json`, and
`skills/forge-verify/references/findings-template.md` (read-only parse contract, never
modified) — all four are out of bounds per `01-architecture-layout.md` §2.

---

## 10. Verification

Structural:

- [ ] `scripts/fix-sweep.py` exists, is executable, has the `#!/usr/bin/env python3`
      shebang, and its module docstring carries **Usage** and **Exit codes** blocks
      (§1.1) — matching `validate-traceability.py` / `check-spec-purity.py`.
- [ ] Imports are stdlib only; `grep -n "^from\|^import"` shows nothing outside §1.2's
      list, and no import of `forge_session` / `forge-session.py`.
- [ ] Every module-level constant is annotated `Final` and carries a `#:` doc comment
      (§1.3).
- [ ] Every public function carries a Google-style docstring with `Args:` / `Returns:`
      and, where it can raise, `Raises:`.
- [ ] The six TypedDicts and `UsageError` match `00-core-definitions.md` key-for-key.
- [ ] `ruff check scripts/` is clean (CI-only gate — run it locally).

Behavioral — exit-code matrix (the authoritative acceptance grid):

| Scenario | Command | Exit | Payload assertion |
|---|---|---|---|
| Non-repo directory | `sweep --repo-root {tmp}` | 0 | `skipped:true`, `reason:"not-a-git-repo"` |
| `git init`, no commit | `sweep` | 0 | `skipped:true`, `reason:"no-head"` |
| Repo, delta, no survivors | `sweep` | 0 | `hits:[]`, `filesScanned>0`, `baseline:"HEAD"` |
| Repo, delta, survivors | `sweep` | 1 | one hit per surviving (file, needle) |
| `git ls-files` forced to fail | `sweep` | 2 | empty stdout, `Error: git ls-files failed ({rc}): {first stderr line}` |
| Bare repo (`git init --bare`) | `sweep` | 2 | empty stdout, `Error: repository has no working tree (bare repo): {repo_root}` |
| `--min-chars 0` | `sweep` | 2 | `Error: --min-chars must be >= 1` |
| `--exclude ""` | `sweep` | 2 | `Error: --exclude requires a non-empty path prefix` |
| Full coverage, totals agree | `plan-coverage` | 0 | `applicable:true`, `uncovered:[]` |
| One finding uncovered | `plan-coverage` | 1 | `uncovered:["V-016"]`, id printed by name |
| Summary total disagrees | `plan-coverage` | 1 | `claimedTotal!=actualTotal`, `claimed N, actual M` printed |
| No `## Fix Execution Plan` | `plan-coverage` | 0 | `applicable:false` |
| Missing document path | `plan-coverage` | 2 | `Error: cannot read findings document: {path} ({reason})` |

Behavioral — matching semantics:

- [ ] F-5 shape: a claim removed from one artifact, surviving verbatim in a sibling, as a
      whitespace-reflowed variant in a second file, and in an un-gated generated file →
      three hits with correct file and line; **zero** hits from the `.verification/` copy;
      **zero** hits from the gated `adapters/` copy.
- [ ] Needle floor: 23 normalized chars dropped (`belowFloor` +1), 24 kept.
- [ ] Reflow suppression: a removed line re-added elsewhere in the delta yields no needle
      (`reflowSuppressed` +1).
- [ ] Untracked, non-ignored file carrying the claim → hit; a `.gitignore`d copy → no hit.
- [ ] Ungated repo (no `scripts/build-adapters.py`): `adapters/` is swept and
      `excludes == [".verification/"]`.

Determinism:

- [ ] Two consecutive `sweep --json` runs over an unchanged tree produce byte-identical
      stdout.
- [ ] `hits` is sorted by `(file, line)`; the tie-break by needle order is stable across
      runs.
- [ ] Corpus scan order is the sorted, de-duplicated `ls-files` output — independent of
      filesystem ordering.
- [ ] `belowFloor + reflowSuppressed + len(needles)` equals the raw removed-line count of
      the delta.
