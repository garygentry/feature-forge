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

from __future__ import annotations

import argparse
import bisect
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Final, TypedDict


# ─────────────────────────────────────────────────────────────────────────────
# Module-level constants.
#
# The first four are the sweep's shared vocabulary, carried here rather than
# imported: a standalone, import-free single-file script has no shared module to
# import from (the same reason epic-manifest.py and forge-session.py keep
# byte-identical copies of KNOWN_VERIFY_STATUSES).
# ─────────────────────────────────────────────────────────────────────────────

#: Minimum normalized length for a removed line to become a needle (REQ-SWEEP-02).
#: Also the --min-chars default.
MIN_NEEDLE_CHARS: Final[int] = 24

#: Path segment excluding findings documents from the corpus — unconditional.
#: Findings documents quote corrected claims by design: they are audit records,
#: not survivors.
VERIFICATION_SEGMENT: Final[str] = ".verification"

#: Drift-gated regenerated tree, excluded ONLY when the gate is detectably
#: present at DRIFT_GATE_SENTINEL.
DRIFT_GATED_PREFIX: Final[str] = "adapters/"

#: Repo-relative sentinel whose presence proves the drift gate exists, and so
#: gates the DRIFT_GATED_PREFIX exclusion.
DRIFT_GATE_SENTINEL: Final[str] = "scripts/build-adapters.py"

#: Label reported in SweepReport["excludes"] for the VERIFICATION_SEGMENT rule.
#: The rule matches a path SEGMENT; the label is the human-facing prefix form.
VERIFICATION_EXCLUDE_LABEL: Final[str] = ".verification/"

#: Wall-clock bound on every git subprocess. The sweep runs inside a fix pass; a
#: hung git must fail the pass loudly (exit 2), never hang it.
GIT_TIMEOUT_SECONDS: Final[int] = 30

#: run_git() return code when git could not be executed at all (binary missing,
#: OSError) or exceeded GIT_TIMEOUT_SECONDS. Callers classify it — a probe treats
#: it as the skip path, a corpus call raises UsageError.
GIT_UNAVAILABLE: Final[int] = -1

#: Non-alphanumeric run -> single space. Sole regex of normalize(); the `+`
#: quantifier is what collapses runs, so no second pass is needed.
_NON_ALNUM: Final = re.compile(r"[^a-z0-9]+")

#: Unified-diff hunk header. Group 1 is the a-side start line — the only field the
#: needle line numbering needs. `,count` is omitted by git when it is 1.
HUNK_RE: Final = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")

#: Findings-document `## ` heading; the negative lookahead keeps `###`/`####`
#: out. This block is the authoritative form of the findings-document anchors.
H2_RE: Final = re.compile(r"^##(?!#)\s*(.*?)\s*$")

#: Findings-document `### ` heading — the sub-section scope for step counting.
H3_RE: Final = re.compile(r"^###(?!#)\s*(.*?)\s*$")

#: Finding heading `### V-NNN: {title}`; group 1 is the finding id.
FINDING_RE: Final = re.compile(r"^### (V-\d{3}):")

#: Execution-step heading `#### Step {N}: {title}`.
STEP_RE: Final = re.compile(r"^#### Step \d+:")

#: The `- **Addresses:** …` coverage field of one execution step.
ADDRESSES_RE: Final = re.compile(r"^\s*-\s*\*\*Addresses:\*\*")

#: Any finding id, used as a findall over an Addresses field.
FINDING_ID_RE: Final = re.compile(r"V-\d{3}")

#: The `## Summary` claimed total; group 1 is the claimed count.
TOTAL_FINDINGS_RE: Final = re.compile(r"Total findings:\s*(\d+)")

#: Fenced-code delimiter. Lines inside a fence are skipped by the findings parser
#: so the template's fenced `### V-001:` examples cannot fabricate findings.
FENCE_RE: Final = re.compile(r"^\s*(?:```|~~~)")


# ─────────────────────────────────────────────────────────────────────────────
# Types and errors — the JSON-boundary shapes and the one exception type.
# ─────────────────────────────────────────────────────────────────────────────


class Needle(TypedDict):
    """One removed line surviving extraction filters, in normalized form.

    Keys:
        file: Repo-relative path the line was removed from (diff's a-side path).
        line: 1-based line number in the PRE-fix file (from the @@ hunk header's
            a-side start, plus offset within the hunk's removed run).
        normalized: normalize(original) — the matching key.
        original: The removed line's raw text, verbatim (REQ-OBS-01/REQ-SEC-01:
            echoed without elision; it is already in git history).
    """

    file: str
    line: int
    normalized: str
    original: str


class NormalizedFile(TypedDict):
    """A corpus file prepared for substring matching.

    Keys:
        path: Repo-relative POSIX path.
        blob: normalize() applied to the full file content — one string, so a
            match spanning the file's original line breaks still lands (the F-5
            whitespace-reflow success criterion).
        line_starts: For each character offset in `blob`, enough structure to map
            a match offset back to the 1-based line number in the ORIGINAL file.
            Concretely: a sorted list of (blob_offset, original_line) pairs; the
            match's line is the last pair whose blob_offset <= match offset
            (bisect).
    """

    path: str
    blob: str
    line_starts: list[tuple[int, int]]


class SweepHit(TypedDict):
    """One surviving occurrence of corrected text (REQ-OBS-01).

    Keys:
        file: Repo-relative path of the surviving occurrence.
        line: 1-based line in the CURRENT working-tree file where the match
            begins (mapped through NormalizedFile.line_starts).
        needle: The matched needle's ORIGINAL removed text, verbatim
            (REQ-SEC-01: no elision — it is already in git history).
        excerpt: The original text of the matched region in the corpus file
            (the line(s) overlapping the match span), verbatim.
        sourceFile: Needle provenance — file the text was removed from.
        sourceLine: Needle provenance — pre-fix line number of the removal.
    """

    file: str
    line: int
    needle: str
    excerpt: str
    sourceFile: str
    sourceLine: int


class DroppedNeedles(TypedDict):
    """Filter counters for the evidence archive.

    Keys:
        belowFloor: Count of raw needles dropped because normalize(original) was
            shorter than MIN_NEEDLE_CHARS (filter 1). A needle counted
            here is never tested for reflow.
        reflowSuppressed: Count of raw needles dropped because their normalized
            text appears in the delta's normalized added text (filter 2).

    Invariant: belowFloor + reflowSuppressed + len(needles) equals the raw
    removed-line count extracted from the delta.
    """

    belowFloor: int
    reflowSuppressed: int


class SweepReport(TypedDict):
    """Top-level `sweep --json` payload.

    Keys:
        skipped: True iff no delta was available (REQ-SWEEP-07).
        reason: None when not skipped; "not-a-git-repo" | "no-head" when skipped.
        baseline: Always "HEAD" when the sweep ran; None when skipped.
        needles: Surviving needles after both extraction filters.
        droppedNeedles: Filter counters.
        excludes: The exclusion prefixes/segments actually applied this run —
            [".verification/"] always; plus "adapters/" when gated;
            plus any --exclude values, in the order applied.
        filesScanned: Count of corpus files read and matched (decode-skipped
            files are not counted).
        hits: All survivors, ordered by (file, line) for determinism.
    """

    skipped: bool
    reason: str | None
    baseline: str | None
    needles: list[Needle]
    droppedNeedles: DroppedNeedles
    excludes: list[str]
    filesScanned: int
    hits: list[SweepHit]


class PlanCoverageReport(TypedDict):
    """Top-level `plan-coverage --json` payload (REQ-CARD-01, REQ-CARD-04).

    Keys:
        applicable: False when the document has no `## Findings` section or no
            `## Fix Execution Plan` section — exit 0, nothing asserted
            (REQ-CARD-04 analog at the fix-pass level).
        findings: Every V-NNN id found as a `### V-NNN:` heading under
            `## Findings`, in document order.
        steps: Count of `#### Step {N}:` entries under `### Execution Steps`.
        covered: Findings ids appearing in >=1 step's `**Addresses:**` field.
        uncovered: Findings ids appearing in NO step's Addresses field —
            omissions BY NAME, never a count delta.
        claimedTotal: The N parsed from `## Summary`'s `Total findings: {N}`
            line; None when no such line exists.
        actualTotal: len(findings) — re-derived, never trusted from prose.
        totalMismatch: True iff claimedTotal is not None and differs from
            actualTotal. False whenever claimedTotal is None.
    """

    applicable: bool
    findings: list[str]
    steps: int
    covered: list[str]
    uncovered: list[str]
    claimedTotal: int | None
    actualTotal: int
    totalMismatch: bool


class UsageError(Exception):
    """A caller/environment error that maps to exit 2.

    Raised for: an unreadable findings document, a git invocation that fails
    inside a valid repository (timeout, non-zero exit on diff/ls-files), a
    repository with no working tree (a bare repo: `rev-parse --git-dir`
    succeeds while `rev-parse --show-toplevel` fails), or invalid flag
    combinations. The message is printed as `Error: {msg}` on stderr; stdout
    stays empty (the exit-2 convention).
    """


# ─────────────────────────────────────────────────────────────────────────────
# Normalization — one contract, applied to needles and corpus alike.
# ─────────────────────────────────────────────────────────────────────────────


def normalize(text: str) -> str:
    """Normalize text for sweep matching.

    Lowercases, maps every non-alphanumeric character to a space, collapses
    whitespace runs to a single space, and strips. Two texts that differ only
    in case, punctuation, or line-wrapping normalize identically — the
    reflowed-prose recall target of REQ-SWEEP-02.

    Args:
        text: Raw text (a diff line or file content).

    Returns:
        The normalized form; possibly the empty string.
    """
    return _NON_ALNUM.sub(" ", text.lower()).strip()


# ─────────────────────────────────────────────────────────────────────────────
# Bounded git helper — deliberately not shared with forge-session.py.
# ─────────────────────────────────────────────────────────────────────────────


def run_git(args: list[str], repo_root: Path) -> tuple[int, str, str]:
    """Run one bounded, read-only git command with cwd set to `repo_root`.

    The helper NEVER classifies: it reports what happened and lets the caller
    decide whether the outcome is the skip path or a UsageError. A git
    binary that cannot be executed at all, or one that exceeds
    GIT_TIMEOUT_SECONDS, yields GIT_UNAVAILABLE rather than raising — the probe
    calls in resolve_repo_root() must treat a missing git as "not a repo"
    (REQ-SWEEP-07), while list_corpus_paths() must treat it as exit 2.

    Args:
        args: git arguments after the program name, e.g. ["rev-parse", "HEAD"].
        repo_root: Directory used as the subprocess cwd. Every git invocation in
            this script runs from the repository top level so that paths in
            output are repo-relative.

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


def _first_line(text: str) -> str:
    """Return the first non-empty-stripped line of `text`, or "".

    Args:
        text: Captured stderr from a git invocation.

    Returns:
        The first line, stripped; the empty string when there is none.
    """
    stripped = text.strip()
    return stripped.splitlines()[0] if stripped else ""


# ─────────────────────────────────────────────────────────────────────────────
# sweep pipeline.
# ─────────────────────────────────────────────────────────────────────────────


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
        admits.

    Raises:
        UsageError: The repository exists but has no working tree (a bare repo:
            --git-dir succeeds while --show-toplevel fails), or --show-toplevel
            fails for any other reason. Not a skip — an operational failure
            (exit 2), and forge-fix never runs in a bare repo.
    """
    rc, _out, _err = run_git(["rev-parse", "--git-dir"], start_dir)
    if rc != 0:
        return None, "not-a-git-repo"

    rc, out, _err = run_git(["rev-parse", "--show-toplevel"], start_dir)
    if rc != 0 or not out.strip():
        raise UsageError(
            f"repository has no working tree (bare repo): {start_dir}"
        )
    repo_root = Path(out.strip())

    rc, _out, _err = run_git(["rev-parse", "HEAD"], repo_root)
    if rc != 0:
        return None, "no-head"
    return repo_root, None


def _diff_path(raw: str) -> str | None:
    """Decode one `---`/`+++` diff header path.

    A path git C-quoted (embedded quote, backslash, or control character) is
    unquoted best-effort by stripping the surrounding double quotes; a
    mis-decoded path affects only provenance reporting, never matching.

    Args:
        raw: The header text after the `--- ` / `+++ ` prefix.

    Returns:
        The repo-relative path with its `a/` or `b/` prefix stripped, or None
        for `/dev/null`.
    """
    value = raw.strip()
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        value = value[1:-1]
    if value == "/dev/null":
        return None
    if value.startswith("a/") or value.startswith("b/"):
        value = value[2:]
    return value


def extract_needles(diff_text: str) -> tuple[list[Needle], dict[str, list[str]]]:
    """Parse a unified diff into raw needles and per-file added lines.

    `--unified=0` means every diff body line is a change: hunk headers delimit
    the changed runs exactly, so a-side line numbers are computable without
    context-line bookkeeping.

    Parse contract:
      * `diff --git …` resets file state and clears the in-hunk flag.
      * `--- a/{path}` sets the a-side path; `+++ b/{path}` sets the b-side path.
        A leading `a/`/`b/` prefix is stripped; `/dev/null` maps to None.
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

    Args:
        diff_text: stdout of `git diff HEAD --unified=0 --no-color`.

    Returns:
        (raw_needles, added_by_file) where raw_needles are Needle dicts in
        document order with `normalized` already computed, and added_by_file maps
        each b-side path to its normalized non-empty added lines in order — the
        input to reflow suppression.
    """
    raw_needles: list[Needle] = []
    added_by_file: dict[str, list[str]] = {}
    a_path: str | None = None
    b_path: str | None = None
    a_line = 0
    in_hunk = False

    for line in diff_text.splitlines():
        if line.startswith("diff --git "):
            a_path = None
            b_path = None
            in_hunk = False
            continue
        if not in_hunk:
            if line.startswith("--- "):
                a_path = _diff_path(line[4:])
                continue
            if line.startswith("+++ "):
                b_path = _diff_path(line[4:])
                continue
        hunk = HUNK_RE.match(line)
        if hunk:
            a_line = int(hunk.group(1))
            in_hunk = True
            continue
        if not in_hunk:
            continue
        if line.startswith("-"):
            content = line[1:]
            raw_needles.append(
                Needle(
                    file=a_path or "",
                    line=a_line,
                    normalized=normalize(content),
                    original=content,
                )
            )
            a_line += 1
        elif line.startswith("+"):
            piece = normalize(line[1:])
            if piece:
                added_by_file.setdefault(b_path or "", []).append(piece)
    return raw_needles, added_by_file


def filter_needles(
    raw: list[Needle],
    added_by_file: dict[str, list[str]],
    min_chars: int,
) -> tuple[list[Needle], DroppedNeedles]:
    """Apply the two extraction filters, in order, with counters.

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
    joined with a single space, in the order files appeared in the diff —
    concatenated per file, then joined delta-wide. Joining rather than
    testing lines individually is deliberate — a corrected sentence re-wrapped
    across new line breaks must still suppress.

    Args:
        raw: Needles in extraction order.
        added_by_file: Normalized added lines per b-side path.
        min_chars: The --min-chars value; MIN_NEEDLE_CHARS by default.

    Returns:
        (surviving needles in extraction order, the DroppedNeedles counters).
    """
    added_text = " ".join(" ".join(lines) for lines in added_by_file.values())
    survivors: list[Needle] = []
    below_floor = 0
    reflow_suppressed = 0

    for needle in raw:
        if len(needle["normalized"]) < min_chars:
            below_floor += 1
            continue
        if needle["normalized"] in added_text:
            reflow_suppressed += 1
            continue
        survivors.append(needle)

    counters = DroppedNeedles(
        belowFloor=below_floor, reflowSuppressed=reflow_suppressed
    )
    return survivors, counters


def list_corpus_paths(repo_root: Path) -> list[str]:
    """Enumerate candidate corpus paths: tracked plus untracked-not-ignored.

    Runs `git ls-files -z --cached --others --exclude-standard` — NUL-terminated
    so paths containing spaces, quotes, or newlines survive intact and no quoting
    mode can mangle them. During an unresolved merge, `--cached` lists
    a conflicted path once per stage; entries are de-duplicated preserving first
    appearance, then sorted lexicographically so the scan order — and therefore
    every tie-break in the output — is deterministic.

    Args:
        repo_root: Repository top level; also the subprocess cwd.

    Returns:
        Sorted, unique, repo-relative POSIX paths.

    Raises:
        UsageError: ls-files exited non-zero or could not be run.
    """
    rc, out, err = run_git(
        ["ls-files", "-z", "--cached", "--others", "--exclude-standard"], repo_root
    )
    if rc != 0:
        raise UsageError(f"git ls-files failed ({rc}): {_first_line(err)}")
    seen: dict[str, None] = {}
    for entry in out.split("\0"):
        if entry:
            seen.setdefault(entry, None)
    return sorted(seen)


def applicable_excludes(repo_root: Path, user_excludes: list[str]) -> list[str]:
    """Compute the exclusion labels actually in force this run.

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
    excludes = [VERIFICATION_EXCLUDE_LABEL]
    if (repo_root / DRIFT_GATE_SENTINEL).is_file():
        excludes.append(DRIFT_GATED_PREFIX)
    excludes.extend(user_excludes)
    return excludes


def is_excluded(path: str, excludes: list[str], user_excludes: list[str]) -> bool:
    """Decide whether one repo-relative path is out of corpus.

    Rules, in evaluation order:
      1. VERIFICATION_SEGMENT appears as a path SEGMENT — at any depth,
         unconditionally. Segment matching, not prefix matching: findings
         documents live at `{featureDir}/.verification/…`, never at the root.
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
    if VERIFICATION_SEGMENT in PurePosixPath(path).parts:
        return True
    if DRIFT_GATED_PREFIX in excludes and path.startswith(DRIFT_GATED_PREFIX):
        return True
    return any(path.startswith(prefix) for prefix in user_excludes)


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
        content: The file's working-tree text (read post-fix,
            so just-corrected sites read as corrected, not as survivors).

    Returns:
        The NormalizedFile. The ORIGINAL lines are deliberately not stored on
        it — the TypedDict's three keys are fixed — so the caller keeps
        `content.splitlines()` alongside it for excerpt rendering.
    """
    pieces: list[str] = []
    line_starts: list[tuple[int, int]] = []
    offset = 0

    for line_number, raw_line in enumerate(content.splitlines(), start=1):
        piece = normalize(raw_line)
        if not piece:
            line_starts.append((offset, line_number))
            continue
        if pieces:
            pieces.append(" ")
            offset += 1
        line_starts.append((offset, line_number))
        pieces.append(piece)
        offset += len(piece)

    return NormalizedFile(path=path, blob="".join(pieces), line_starts=line_starts)


def line_for_offset(nf: NormalizedFile, offset: int) -> int:
    """Map a blob offset back to a 1-based line number in the original file.

    Uses `bisect.bisect_right` over the offsets of `nf["line_starts"]`, taking
    the entry at index-1: the LAST pair whose blob_offset <= offset. When a
    zero-width (blank-line) entry ties with the following real entry,
    bisect_right selects the later — the line whose text actually begins there.

    Args:
        nf: A NormalizedFile from build_normalized_file().
        offset: A blob offset, expected to be a match start or end.

    Returns:
        The 1-based original line number; 1 for an empty map (empty file, which
        cannot produce a match anyway).
    """
    starts = nf["line_starts"]
    if not starts:
        return 1
    offsets = [entry[0] for entry in starts]
    index = bisect.bisect_right(offsets, offset)
    if index == 0:
        return starts[0][1]
    return starts[index - 1][1]


def dedupe_needles(needles: list[Needle]) -> list[Needle]:
    """Pick one representative per distinct normalized text, first extracted wins.

    Duplicate needles stay distinct in the payload, but a corpus hit
    reports the FIRST extracted needle matching it. Deduplicating here makes
    that deterministic and removes redundant str.find() calls.

    Args:
        needles: Surviving needles in extraction order.

    Returns:
        Representatives in extraction order.
    """
    seen: set[str] = set()
    representatives: list[Needle] = []
    for needle in needles:
        if needle["normalized"] in seen:
            continue
        seen.add(needle["normalized"])
        representatives.append(needle)
    return representatives


def scan_file(
    nf: NormalizedFile,
    original_lines: list[str],
    representatives: list[Needle],
) -> list[SweepHit]:
    """Search one prepared corpus file for every representative needle.

    One hit per (file, needle), at the FIRST match offset: disposition
    is recorded per file + needle, so reporting every occurrence in a file would
    generate hits the disposition vocabulary cannot address separately.

    The file a needle was removed from is scanned like any other — self-file
    hits count: a surviving duplicate two sections below the
    corrected site is the F-5 self-contradiction and must be reported. The
    corrected site itself does not match because content is read post-fix.

    Args:
        nf: The prepared file from build_normalized_file().
        original_lines: `content.splitlines()` for the same file.
        representatives: Output of dedupe_needles().

    Returns:
        Hits for this file, in representative order; the caller sorts globally.
    """
    hits: list[SweepHit] = []
    blob = nf["blob"]
    for needle in representatives:
        target = needle["normalized"]
        if not target:
            continue
        offset = blob.find(target)
        if offset < 0:
            continue
        line = line_for_offset(nf, offset)
        end = line_for_offset(nf, offset + len(target) - 1)
        excerpt = "\n".join(original_lines[line - 1 : end])
        hits.append(
            SweepHit(
                file=nf["path"],
                line=line,
                needle=needle["original"],
                excerpt=excerpt,
                sourceFile=needle["file"],
                sourceLine=needle["line"],
            )
        )
    return hits


def run_sweep(
    start_dir: Path,
    user_excludes: list[str],
    min_chars: int,
) -> SweepReport:
    """Execute the whole sweep and return the payload.

    Steps: resolve_repo_root() -> skip payload or continue; run the diff;
    extract_needles(); filter_needles(); applicable_excludes();
    list_corpus_paths(); for each non-excluded readable path
    build_normalized_file() + scan_file(); sort hits; assemble.

    Args:
        start_dir: The --repo-root value.
        user_excludes: --exclude values, in order.
        min_chars: --min-chars value.

    Returns:
        A fully populated SweepReport. Never partially populated: the skip
        shape fills every key.

    Raises:
        UsageError: Any git failure inside a valid repository, or a bare repo
            — exit 2, and the fix pass closes on its failure outcome.
    """
    repo_root, reason = resolve_repo_root(start_dir)
    if repo_root is None:
        return SweepReport(
            skipped=True,
            reason=reason,
            baseline=None,
            needles=[],
            droppedNeedles=DroppedNeedles(belowFloor=0, reflowSuppressed=0),
            excludes=[],
            filesScanned=0,
            hits=[],
        )

    rc, diff_text, err = run_git(
        ["-c", "core.quotePath=false", "diff", "HEAD", "--unified=0", "--no-color"],
        repo_root,
    )
    if rc != 0:
        raise UsageError(f"git diff failed ({rc}): {_first_line(err)}")

    raw_needles, added_by_file = extract_needles(diff_text)
    needles, dropped = filter_needles(raw_needles, added_by_file, min_chars)
    excludes = applicable_excludes(repo_root, user_excludes)
    representatives = dedupe_needles(needles)
    rep_order = {
        (needle["file"], needle["line"]): index
        for index, needle in enumerate(representatives)
    }

    files_scanned = 0
    hits: list[SweepHit] = []
    for path in list_corpus_paths(repo_root):
        if is_excluded(path, excludes, user_excludes):
            continue
        try:
            content = (repo_root / path).read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        files_scanned += 1
        nf = build_normalized_file(path, content)
        hits.extend(scan_file(nf, content.splitlines(), representatives))

    hits.sort(
        key=lambda hit: (
            hit["file"],
            hit["line"],
            rep_order.get((hit["sourceFile"], hit["sourceLine"]), 0),
        )
    )

    return SweepReport(
        skipped=False,
        reason=None,
        baseline="HEAD",
        needles=needles,
        droppedNeedles=dropped,
        excludes=excludes,
        filesScanned=files_scanned,
        hits=hits,
    )


# ─────────────────────────────────────────────────────────────────────────────
# plan-coverage.
# ─────────────────────────────────────────────────────────────────────────────


def parse_findings_doc(text: str) -> PlanCoverageReport:
    """Parse a findings document into the coverage payload.

    State carried per line: `h2` (the current `## ` heading text, reset by every
    `## ` line), `h3` (the current `### ` heading text, reset by every `## ` and
    every `### ` line), and `in_fence` (toggled by a line matching FENCE_RE).
    Lines inside a fence are skipped entirely — the findings template ships
    fenced markdown examples containing `### V-001:` and `**Addresses:**`
    literals, and counting those would fabricate findings or coverage.

    Scoped recognitions (each ONLY under its stated scope):
      * `### V-NNN:` while h2 == "Findings" -> append the id to `findings` in
        document order (duplicates ignored: first wins).
      * `#### Step N:` while h2 == "Fix Execution Plan" and
        h3 == "Execution Steps" -> increment `steps`.
      * `- **Addresses:** …` in the same scope -> every FINDING_ID_RE match on
        that line joins the covered set. Scope is the SECTION, not an enclosing
        step heading: a mis-numbered `#### Step` heading must not silently drop
        the coverage it declares.
      * `Total findings: N` while h2 == "Summary" -> the first such match sets
        `claimedTotal`; later ones are ignored.

    Args:
        text: The full document text.

    Returns:
        A fully populated PlanCoverageReport.
    """
    h2: str | None = None
    h3: str | None = None
    in_fence = False
    has_findings = False
    has_plan = False
    findings: list[str] = []
    covered_ids: set[str] = set()
    steps = 0
    claimed_total: int | None = None

    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue

        heading2 = H2_RE.match(line)
        if heading2:
            h2 = heading2.group(1)
            h3 = None
            if h2 == "Findings":
                has_findings = True
            elif h2 == "Fix Execution Plan":
                has_plan = True
            continue

        heading3 = H3_RE.match(line)
        if heading3:
            h3 = heading3.group(1)
            finding = FINDING_RE.match(line)
            if finding and h2 == "Findings":
                finding_id = finding.group(1)
                if finding_id not in findings:
                    findings.append(finding_id)
            continue

        in_steps = h2 == "Fix Execution Plan" and h3 == "Execution Steps"
        if in_steps and STEP_RE.match(line):
            steps += 1
            continue
        if in_steps and ADDRESSES_RE.match(line):
            covered_ids.update(FINDING_ID_RE.findall(line))
            continue
        if h2 == "Summary" and claimed_total is None:
            total = TOTAL_FINDINGS_RE.search(line)
            if total:
                claimed_total = int(total.group(1))

    if not (has_findings and has_plan):
        return PlanCoverageReport(
            applicable=False,
            findings=[],
            steps=0,
            covered=[],
            uncovered=[],
            claimedTotal=None,
            actualTotal=0,
            totalMismatch=False,
        )

    covered = [fid for fid in findings if fid in covered_ids]
    uncovered = [fid for fid in findings if fid not in covered_ids]
    actual_total = len(findings)
    return PlanCoverageReport(
        applicable=True,
        findings=findings,
        steps=steps,
        covered=covered,
        uncovered=uncovered,
        claimedTotal=claimed_total,
        actualTotal=actual_total,
        totalMismatch=claimed_total is not None and claimed_total != actual_total,
    )


def run_plan_coverage(doc_path: Path) -> PlanCoverageReport:
    """Read and parse a findings document.

    Args:
        doc_path: The FINDINGS_DOC argument.

    Returns:
        The PlanCoverageReport from parse_findings_doc().

    Raises:
        UsageError: The path does not exist, is a directory, is unreadable, or
            is not valid UTF-8 — exit 2. An unreadable path is an error,
            while a readable-but-unrecognizable document is `applicable: false`.
    """
    try:
        text = doc_path.read_text(encoding="utf-8")
    except OSError as exc:
        detail = exc.strerror or str(exc)
        raise UsageError(
            f"cannot read findings document: {doc_path} ({detail})"
        ) from exc
    except UnicodeDecodeError as exc:
        raise UsageError(
            f"cannot read findings document: {doc_path} (not valid UTF-8)"
        ) from exc
    return parse_findings_doc(text)


# ─────────────────────────────────────────────────────────────────────────────
# Rendering.
# ─────────────────────────────────────────────────────────────────────────────


def render_sweep(report: SweepReport, json_output: bool) -> None:
    """Render a SweepReport to stdout.

    With `--json`, stdout carries exactly one JSON object and no human lines.
    Otherwise the report is rendered in the check-spec-purity.py reporting
    style: a verdict line, then one indented row per hit. A skip always
    produces a visible line, so it is never silent on any surface
    (REQ-SWEEP-07).

    Args:
        report: The payload from run_sweep().
        json_output: True when --json was passed.
    """
    if json_output:
        print(json.dumps(report, indent=2))
        return

    if report["skipped"]:
        print(f"sweep: SKIPPED — no git delta ({report['reason']})")
        return

    needle_count = len(report["needles"])
    files = report["filesScanned"]
    hits = report["hits"]
    if not hits:
        dropped = report["droppedNeedles"]
        print(
            f"sweep: PASS — 0 survivor(s) in {files} file(s) "
            f"({needle_count} needle(s), {dropped['belowFloor']} below floor, "
            f"{dropped['reflowSuppressed']} reflowed)."
        )
        return

    print(
        f"sweep: FAIL — {len(hits)} survivor(s) in {files} file(s) "
        f"({needle_count} needle(s)):"
    )
    for hit in hits:
        text = hit["needle"].strip()
        print(
            f"  {hit['file']}:{hit['line']}: survivor of \"{text}\" "
            f"(removed at {hit['sourceFile']}:{hit['sourceLine']})"
        )


def render_plan_coverage(report: PlanCoverageReport, json_output: bool) -> None:
    """Render a PlanCoverageReport to stdout.

    Both FAIL lines are printed when a document is both uncovered and
    mismatched.

    Args:
        report: The payload from run_plan_coverage().
        json_output: True when --json was passed.
    """
    if json_output:
        print(json.dumps(report, indent=2))
        return

    if not report["applicable"]:
        print(
            "plan-coverage: NOT APPLICABLE — no `## Findings` and/or "
            "`## Fix Execution Plan` section."
        )
        return

    uncovered = report["uncovered"]
    if not uncovered and not report["totalMismatch"]:
        print(
            f"plan-coverage: PASS — {len(report['findings'])} finding(s), "
            f"{report['steps']} step(s), all covered."
        )
        return

    if uncovered:
        print(f"plan-coverage: FAIL — {len(uncovered)} uncovered finding(s):")
        for finding_id in uncovered:
            print(
                f"  {finding_id}: named in no execution step's "
                f"**Addresses:** field"
            )
    if report["totalMismatch"]:
        print(
            f"plan-coverage: FAIL — claimed {report['claimedTotal']}, actual "
            f"{report['actualTotal']} (`## Summary` total disagrees with "
            f"`### V-NNN:` count)"
        )


# ─────────────────────────────────────────────────────────────────────────────
# CLI.
# ─────────────────────────────────────────────────────────────────────────────


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
        "--repo-root",
        default=".",
        help="Directory inside the repository to sweep (default: cwd). The "
        "repository top level is resolved from it.",
    )
    p_sweep.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PREFIX",
        help="Additional repo-relative path prefix to exclude (repeatable).",
    )
    p_sweep.add_argument(
        "--min-chars",
        type=int,
        default=MIN_NEEDLE_CHARS,
        metavar="N",
        help=f"Minimum normalized needle length (default: {MIN_NEEDLE_CHARS}).",
    )
    p_sweep.add_argument(
        "--json", action="store_true", dest="json_output", help="Output as JSON"
    )

    p_plan = sub.add_parser(
        "plan-coverage", help="Assert Fix Execution Plan coverage of the findings"
    )
    p_plan.add_argument(
        "findings_doc",
        metavar="FINDINGS_DOC",
        help="Path to a verification findings document",
    )
    p_plan.add_argument(
        "--json", action="store_true", dest="json_output", help="Output as JSON"
    )
    return parser


def main() -> int:
    """Parse arguments, dispatch, and map exceptions to exit codes.

    Returns:
        0, 1, or 2 per the exit-code table in the module docstring.
    """
    args = _build_parser().parse_args()
    try:
        if args.cmd == "sweep":
            if args.min_chars < 1:
                raise UsageError("--min-chars must be >= 1")
            for prefix in args.exclude:
                if not prefix.strip():
                    raise UsageError("--exclude requires a non-empty path prefix")
            report = run_sweep(
                start_dir=Path(args.repo_root),
                user_excludes=list(args.exclude),
                min_chars=args.min_chars,
            )
            render_sweep(report, args.json_output)
            return 1 if report["hits"] else 0
        if args.cmd == "plan-coverage":
            plan = run_plan_coverage(Path(args.findings_doc))
            render_plan_coverage(plan, args.json_output)
            return 1 if (plan["uncovered"] or plan["totalMismatch"]) else 0
        raise UsageError(f"unknown command: {args.cmd}")
    except UsageError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
