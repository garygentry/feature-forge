#!/usr/bin/env python3
"""Session-aware navigation helpers for the feature-forge pipeline navigator.

Read-only subcommands that drive the usability features of the `/forge`
root navigator:

    python3 forge-session.py rank-features [--specs-dir DIR] [--json]
    python3 forge-session.py context-usage [--config FILE] [--window N] \
        [--threshold F] [--json]
    python3 forge-session.py doctor [--specs-dir DIR] [--config FILE] [--json]
    python3 forge-session.py discover-feature [NAME | --all] [--specs-dir DIR] [--json]
    python3 forge-session.py reconcile-branch --feature F [--specs-dir DIR] \
        [--config FILE] [--epic E] [--json]
    python3 forge-session.py check-epic-base --feature F [--specs-dir DIR] \
        [--config FILE] [--epic E] [--json]
    python3 forge-session.py stage-exit --feature F --stage S [--specs-dir DIR] \
        [--config FILE] [--epic E] [--next-feature N] [--host claude|generic] [--json]
    python3 forge-session.py effective-config [--config FILE] [--schema PATH] [--json]

Plus the `state-*` write verbs, which author `.pipeline-state.json` so no stage
has to hand-write the JSON (and therefore no stage has to read the state schema):

    python3 forge-session.py state-enter --feature F --stage S [--specs-dir DIR] \
        [--epic E] [--json]
    python3 forge-session.py state-artifact --feature F --stage S --path P \
        [--path P ...] [--specs-dir DIR] [--epic E] [--json]
    python3 forge-session.py state-complete --feature F --stage S --version N \
        [--based-on STAGE=N ...] [--artifact P ...] [--commit-hash H] \
        [--status complete|in-progress] [--resumable] [--preserve-commit-hash] \
        [--specs-dir DIR] [--epic E] [--json]
    python3 forge-session.py state-branch --feature F --branch B [--specs-dir DIR] \
        [--epic E] [--json]
    python3 forge-session.py state-note --feature F --note TEXT [--specs-dir DIR] \
        [--epic E] [--json]
    python3 forge-session.py state-decision --feature F --question Q --raised-by S \
        [--rationale R] [--target-stage S] [--specs-dir DIR] [--epic E] [--json]
    python3 forge-session.py state-ecr --feature F --kind K --target T --rationale R \
        --raised-by S --blocks-current true|false [--specs-dir DIR] [--epic E] [--json]

`rank-features` scans the specs tree for feature-shaped directories (those that
directly contain a `.pipeline-state.json`, in both the flat
`{specsDir}/{feature}/` and nested `{specsDir}/{epic}/{feature}/` layouts) and
reports the **active** ones ordered by `updatedAt` descending, so the navigator
can offer the most-recently-touched feature as the recency default. Each row
carries the next actionable stage + its slash command, derived from the single
ordered stage map below.

`context-usage` reads the live Claude Code session transcript (the most-recently
modified `*.jsonl` under `~/.claude/projects/<cwd-slug>/`), sums the last
assistant message's token usage, and compares it to the context window so the
navigator can recommend a clean session before the next stage. It is best-effort
and degrades gracefully: when no transcript or usage is found (a non-Claude host,
or a fresh session) it reports `{"available": false}` and still exits 0, so the
caller simply omits the context advice.

`doctor` captures pipeline ground truth in one shot for debugging a confused
session or a broken install: the plugin root the sibling `forge-root.sh`
actually resolves (plus its version and commit), the current git branch vs.
each feature's recorded state branch, the recency-ranked feature summary, and
whether each feature's composed backlog path exists on disk. Every probe is
best-effort — a failure is reported as data, never as a crash — and the
command always exits 0 so it can run in any half-broken environment.

`discover-feature` looks for a feature's `.pipeline-state.json` across ALL
git branches (local heads and remote-tracking refs), so a session on the
default branch can learn that a pipeline exists on a topic branch instead of
concluding it was never started. When nothing is found locally it also asks
`git ls-remote --heads origin` about branches a single-branch clone never
fetched, and emits the exact `git fetch`/`git switch` commands a caller could
run. It is strictly read-only — it never checks anything out itself — and
like `doctor` it always exits 0 and degrades to data. Each candidate also
carries `epic`/`isEpicMember`, so a caller minting a new standalone feature can
refuse when the name is a known epic member discoverable on another branch
(the split-brain-epic guard, Issue #125).

`check-epic-base` is the defense-in-depth companion: given a feature that
resolves to a nested epic member on the current branch, it confirms the epic's
`epic-manifest.json` is actually present on HEAD. When it is absent, the member
was reached from a branch that predates or lacks the manifest commit (a detached
base) and the command emits `warn-detached-base` with the member's recorded home
branch. Read-only; always exits 0.

`stage-exit` computes everything an authoring stage's closing used to derive
in prose (the Scripted Stage Exit, `references/stage-exit-protocol.md`):
the DIRECTIVES (whether the in-stage auto-verify runs, which verify gate to
present, autoFix eligibility, the verify and next-stage commands) plus the
exact sentinel-terminated NEXT-STEPS block the skill must print verbatim as
its absolute last output. Deterministic and read-only; always exits 0.

`effective-config` resolves the `loopRunner` block deterministically so no
caller has to read `references/forge-config-schema.json` just to learn the
defaults: it extracts each field's schema `default` at runtime and merges the
project's `loopRunner` overrides on top. A missing or corrupt
`forge.config.json` resolves to pure defaults (exit 0); only an unreadable
schema is fatal (exit 2), because then there are no defaults to resolve.

The `state-*` verbs are the script's only writers. Each follows the same
resolve -> load -> mutate -> refresh `updatedAt` -> atomic write path, so every
successful write leaves a schema-conformant state file: `state-enter` stamps a
stage in-progress and moves `currentStage`, `state-artifact` appends artifact
paths to a stage (de-duplicating), `state-branch` records the branch resolved by
Branch Setup / Branch Reconciliation, and `state-note` persists the free-text
note a user volunteers at a stage exit. They never create a feature directory —
an unknown `--feature` is a usage error (exit 2) — and they never overwrite a
state file they could not parse.

`state-complete` is the largest of them: it records the completion (status,
`completedAt`, `version`, `basedOnVersions`, `artifacts`), resets `commitHash` to
null for Commit 1 of the two-commit Git Commit Protocol, and runs the
deterministic downstream staleness cascade that each stage used to describe in
prose. `--commit-hash` is the Commit-2 follow-up, setting only that field (and
refusing a stage that is not yet complete). The protocol's two recovery branches
stay executable without hand-authored JSON: `--resumable` is the failed-Commit-1
revert (status-only, no cascade), and `--preserve-commit-hash` is the "nothing to
commit" branch. A bare `--status in-progress` is something else again —
forge-5-loop's partial completion, which keeps every completion field.

`state-decision` and `state-ecr` are the two array-appending verbs. The first
appends a `deferredDecisions[]` item — a same-feature decision deliberately
postponed to a later stage; the second appends an `epicChangeRequests[]` item —
a member stage's report that the epic decomposition itself must change, whose
`blocksCurrent` boolean drives the stage exit's pause-now vs. finish-then-edit
routing (so it is required and parsed strictly: only `true`/`false`). Both always
record `status: "open"` — resolving an item is the target stage's job, never the
recorder's — and both emit exactly the schema keys, because those two array item
shapes set `additionalProperties: false`.

3.10 baseline, Google-style docstrings, full type annotations, stdlib only —
matching the conventions of `scripts/epic-manifest.py`.

Exit codes:
    0 = ok (including an empty feature list or unavailable context usage)
    2 = usage error or unreadable I/O
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Final, TypedDict


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

#: A directory is "feature-shaped" iff it directly contains this file.
PIPELINE_STATE_FILENAME: Final = ".pipeline-state.json"
#: Epic roots hold this (and no .pipeline-state.json) — never a feature.
MANIFEST_FILENAME: Final = "epic-manifest.json"

#: The ordered production stages. This is the ONE place stage order lives.
PRODUCTION_STAGES: Final[tuple[str, ...]] = (
    "forge-1-prd",
    "forge-2-tech",
    "forge-3-specs",
    "forge-4-backlog",
    "forge-5-loop",
    "forge-6-docs",
)

#: The --stage domain for the state-write verbs: the six PRODUCTION_STAGES above
#: (order-sensitive — next_stage/verify_state/stage_exit all walk that tuple, so it
#: is NEVER redefined) plus forge-0-epic, which also carries a stageEntry but is
#: excluded from the next-stage walk.
STATE_VERB_STAGES: Final[tuple[str, ...]] = ("forge-0-epic", *PRODUCTION_STAGES)

#: The `--raised-by` / `--target-stage` domains for `state-decision`, and the
#: `--kind` / `--raised-by` domains for `state-ecr`. SOURCE OF TRUTH:
#: references/pipeline-state-schema.json (the `deferredDecisions` and
#: `epicChangeRequests` array item enums). Mirrored here so an out-of-enum value is
#: rejected at parse time; a drift guard asserts they still match the schema.
DECISION_RAISED_BY: Final[tuple[str, ...]] = (
    "forge-1-prd",
    "forge-2-tech",
    "forge-3-specs",
    "forge-4-backlog",
)
DECISION_TARGET_STAGES: Final[tuple[str, ...]] = (
    "forge-1-prd",
    "forge-2-tech",
    "forge-3-specs",
    "forge-4-backlog",
    "forge-5-loop",
    "forge-6-docs",
)
ECR_KINDS: Final[tuple[str, ...]] = ("add-feature", "redep", "move-boundary", "split")
ECR_RAISED_BY: Final[tuple[str, ...]] = ("forge-1-prd", "forge-2-tech")

#: Production stage -> the verify token its findings file uses, and the
#: `forge-verify-<token>` key its state lives under. forge-6-docs has no verify.
VERIFY_TOKEN_BY_STAGE: Final[dict[str, str]] = {
    "forge-1-prd": "prd",
    "forge-2-tech": "tech",
    "forge-3-specs": "specs",
    "forge-4-backlog": "backlog",
    "forge-5-loop": "impl",
}

#: A production stage status that counts as "done" for next-stage selection.
_DONE_STATUS: Final = "complete"
#: The authoritative forge-verify status vocabulary. SOURCE OF TRUTH:
#: references/pipeline-state-schema.json (definitions.verifyEntry.properties.status.enum).
#: A status outside this set is unrecognized and must not be silently interpreted (#148).
#: NOTE: epic-manifest.py keeps a byte-identical copy — flat, self-contained scripts have
#: no shared import module (each is copied verbatim into per-agent adapter bundles).
KNOWN_VERIFY_STATUSES: Final = frozenset(
    {"pending", "passed", "findings-reported", "findings-applied", "skipped"}
)
#: Verify statuses that count as "resolved" (no outstanding verify needed). A STRICT
#: subset of KNOWN_VERIFY_STATUSES — not collapsible into it (different meaning).
_VERIFY_RESOLVED: Final = frozenset({"passed", "findings-applied", "skipped"})
#: Per-process dedupe for the unknown-verify-status diagnostic (#148) so a single
#: bogus status is flagged once, not once per verify_state() call in a command.
_UNKNOWN_VERIFY_WARNED: set[str] = set()

#: Default context window when the model can't be inferred and config is silent.
_DEFAULT_WINDOW: Final = 200_000
#: Window for 1M-context models (model id carries a `[1m]` / `-1m` marker).
_WIDE_WINDOW: Final = 1_000_000
#: Default fraction of the window past which a clean session is recommended.
_DEFAULT_THRESHOLD: Final = 0.7


# --------------------------------------------------------------------------- #
# Types
# --------------------------------------------------------------------------- #


class FeatureRow(TypedDict):
    """One active feature, ranked by recency, with its next actionable step."""

    name: str
    epic: str | None
    currentStage: str
    branch: str | None
    updatedAt: str | None
    complete: bool
    nextStage: str | None
    nextCommand: str | None
    verifyPending: bool
    verifyCommand: str | None
    verifyStage: str | None
    verifyState: str
    autoVerify: bool
    autoFix: bool
    verifyGate: str


class UsageError(Exception):
    """A usage or I/O failure that must exit 2."""


# --------------------------------------------------------------------------- #
# Feature scanning & ranking
# --------------------------------------------------------------------------- #


def _read_state(state_path: Path) -> dict:
    """Read a `.pipeline-state.json`, tolerating missing/corrupt files.

    A missing, unreadable, or unparseable state downgrades to ``{}`` rather than
    crashing the scan — the navigator simply treats that feature as not-started.
    """
    try:
        parsed = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _scan_features(specs_dir: Path) -> list[tuple[str, str | None, dict]]:
    """Find every feature-shaped dir under the specs tree (flat + nested).

    Descends exactly one level below each top-level dir (never deeper), matching
    ``epic-manifest.py``'s feature-shaped-dir bound.

    Args:
        specs_dir: The configured specs directory.

    Returns:
        A list of ``(feature_name, epic_name_or_None, state_dict)`` tuples. The
        epic name is the parent dir name for a nested member, ``None`` for a flat
        feature.
    """
    if not specs_dir.is_dir():
        return []
    out: list[tuple[str, str | None, dict]] = []
    for top in sorted(p for p in specs_dir.iterdir() if p.is_dir()):
        flat_state = top / PIPELINE_STATE_FILENAME
        if flat_state.is_file():
            out.append((top.name, None, _read_state(flat_state)))
        # Descend one level for nested epic members (skip the epic root itself).
        for child in sorted(p for p in top.iterdir() if p.is_dir()):
            nested_state = child / PIPELINE_STATE_FILENAME
            if nested_state.is_file():
                out.append((child.name, top.name, _read_state(nested_state)))
    return out


def _stage_status(state: dict, stage: str) -> str | None:
    """Return the recorded status of a stage, or None if absent."""
    stages = state.get("stages")
    if not isinstance(stages, dict):
        return None
    entry = stages.get(stage)
    if not isinstance(entry, dict):
        return None
    status = entry.get("status")
    return status if isinstance(status, str) else None


def next_stage(state: dict) -> str | None:
    """Return the first production stage that is not yet complete (the next step).

    Walks ``PRODUCTION_STAGES`` in order and returns the first whose recorded
    status is not ``complete`` (a missing/pending/in-progress/stale stage all
    count as "not done"). Returns ``None`` when every production stage is
    complete (nothing left to run).

    This is the derived "what runs next" value — the single source of truth for
    the next stage. It is intentionally distinct from the stored
    ``currentStage`` field ("where the pipeline IS"; see the schema): the next
    stage is computed from ``stages[].status`` here, never read from
    ``currentStage``.
    """
    for stage in PRODUCTION_STAGES:
        if _stage_status(state, stage) != _DONE_STATUS:
            return stage
    return None


def _stage_version(state: dict, stage: str) -> int | None:
    """Return the recorded ``version`` of a stage entry, or None if absent."""
    stages = state.get("stages")
    if not isinstance(stages, dict):
        return None
    entry = stages.get(stage)
    if not isinstance(entry, dict):
        return None
    version = entry.get("version")
    return version if isinstance(version, int) else None


def _verify_entry(state: dict, verify_key: str) -> dict:
    """Return the ``forge-verify-*`` entry dict, or ``{}`` if absent."""
    stages = state.get("stages")
    if not isinstance(stages, dict):
        return {}
    entry = stages.get(verify_key)
    return entry if isinstance(entry, dict) else {}


def _warn_unknown_verify_status(stage_name: str, status: object) -> None:
    """Emit a one-time stderr diagnostic for an out-of-vocabulary verify status (#148).

    The freshness classifier maps an unrecognized status to "never verified" — correct,
    but silent, so a typo poisons the downstream gate (e.g. forge-5-loop's dependency
    check) with no clue. Flagging it here makes the bad value visible where it is read.
    """
    key = f"{stage_name}={status!r}"
    if key in _UNKNOWN_VERIFY_WARNED:
        return
    _UNKNOWN_VERIFY_WARNED.add(key)
    known = ", ".join(sorted(KNOWN_VERIFY_STATUSES))
    print(
        f"feature-forge: unknown {stage_name} status {status!r} "
        f"(treated as unverified; expected one of {known})",
        file=sys.stderr,
    )


def verify_state(state: dict) -> tuple[str | None, str]:
    """Classify verify freshness for the most-recently-completed stage.

    Returns ``(stage, state_label)`` where ``state_label`` is one of:

    - ``fresh``   — verify is resolved AND its ``verifiedStageVersion`` matches the
      stage's current ``version`` (so no re-verify is needed).
    - ``stale``   — verify was resolved once, but the stage version has since moved
      (artifact revised) OR the entry predates the freshness ledger (no
      ``verifiedStageVersion``). A revised artifact must be re-verified.
    - ``failing`` — verify ran and reported findings that are not yet applied
      (``findings-reported``).
    - ``never``   — the stage completed but verify has not run at all.
    - ``skipped`` — the user explicitly chose to proceed without verifying. A
      resolved, non-pending state: it is deliberately NOT re-offered or
      auto-verified, and (unlike a genuine verification result) it does not go
      stale on an artifact revision — skip writers record no version to compare
      against, and re-surfacing would override an explicit human decision.
    - ``none``    — no completed verify-capable stage (nothing to verify), stage
      is ``None``.

    Only the most-recent completed production stage is considered, matching the
    navigator's "verify before continuing" gate. Absent ``verifiedStageVersion``
    on a ``passed``/``findings-applied`` entry (legacy state) is deliberately
    treated as ``stale`` — verify rather than skip.
    """
    for stage in reversed(PRODUCTION_STAGES):
        if _stage_status(state, stage) != _DONE_STATUS:
            continue
        token = VERIFY_TOKEN_BY_STAGE.get(stage)
        if token is None:
            continue  # forge-6-docs has no verify step
        entry = _verify_entry(state, f"forge-verify-{token}")
        status = entry.get("status")
        if status == "skipped":
            # An explicit skip is resolved and non-pending — preserve the user's
            # decision. It never goes stale (no recorded version to compare), so
            # the freshness check below deliberately does not apply.
            return stage, "skipped"
        if status not in _VERIFY_RESOLVED:
            if status == "findings-reported":
                return stage, "failing"
            # An unrecognized status (outside KNOWN_VERIFY_STATUSES) is treated as
            # "never verified" — defensible, but flag it once so a typo (e.g. the
            # eye-slip 'findings-resolved') doesn't silently poison the gate that
            # reads this label (#148). ``pending``/``None`` are known/absent → quiet.
            if status is not None and status not in KNOWN_VERIFY_STATUSES:
                _warn_unknown_verify_status(f"forge-verify-{token}", status)
            return stage, "never"
        verified_version = entry.get("verifiedStageVersion")
        stage_version = _stage_version(state, stage)
        if (
            isinstance(verified_version, int)
            and stage_version is not None
            and verified_version == stage_version
        ):
            return stage, "fresh"
        return stage, "stale"
    return None, "none"


def pending_verify(state: dict) -> str | None:
    """Return the production stage whose verify is outstanding, if any.

    Outstanding means the most-recently-completed production stage's verify is not
    ``fresh`` (never run, reported findings, or gone stale after an artifact
    revision). An explicit ``skipped`` is treated as resolved (never outstanding).
    Surfaced so the navigator can offer "verify before continuing" as an
    alternative to advancing. Returns ``None`` when the latest stage is fresh,
    skipped, or there is nothing to verify.
    """
    stage, label = verify_state(state)
    return stage if label not in ("fresh", "none", "skipped") else None


def _parse_ts(value: str | None) -> datetime | None:
    """Parse an ISO-8601 timestamp (tolerating a trailing 'Z'), else None."""
    if not isinstance(value, str):
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def build_rows(specs_dir: Path, config: dict | None = None) -> list[FeatureRow]:
    """Build the recency-ranked active-feature rows (the rank-features payload).

    Active features (``pipelineStatus == "active"``, the default when absent) are
    sorted by ``updatedAt`` descending — most recently touched first — so the
    navigator's recency default is row 0.

    ``config`` is the loaded forge.config.json (or ``{}``); it drives the effective
    ``autoVerify``/``autoFix`` per stage so the navigator can branch without
    re-reading config.
    """
    config = config or {}
    # Fail closed: only a literal JSON ``true`` enables artifact-mutating autoFix.
    global_auto_fix = config.get("autoFix") is True
    rows: list[FeatureRow] = []
    for name, epic, state in _scan_features(specs_dir):
        status = state.get("pipelineStatus", "active")
        if status != "active":
            continue
        nxt = next_stage(state)
        vstage, vlabel = verify_state(state)
        verify_pending = vstage is not None and vlabel not in ("fresh", "none", "skipped")
        effective_auto_verify = auto_verify_for(config, vstage) if vstage else False
        branch = state.get("branch")
        updated = state.get("updatedAt")
        rows.append({
            "name": name,
            "epic": epic,
            # currentStage = "where the pipeline IS" (the recorded field). When a
            # legacy/absent state omits it, fall back to the DERIVED next stage
            # for display only — never conflate the two elsewhere (schema O1).
            "currentStage": state.get("currentStage") or (nxt or "complete"),
            "branch": branch if isinstance(branch, str) else None,
            "updatedAt": updated if isinstance(updated, str) else None,
            "complete": nxt is None,
            "nextStage": nxt,
            "nextCommand": f"/skill:{nxt} {name}" if nxt else None,
            "verifyPending": verify_pending,
            "verifyCommand": f"/skill:forge-verify {name}" if verify_pending else None,
            "verifyStage": vstage,
            "verifyState": vlabel,
            "autoVerify": effective_auto_verify,
            "autoFix": global_auto_fix and effective_auto_verify,
            # Single resolved verify-gate classification (5b — one exit computation,
            # mirroring stage-exit's `verifyGate`): the navigator reads this instead of
            # re-deriving from verifyPending + autoVerify in prose. `auto` = the §2b
            # catch-up runs it unattended; `standard` = the §3 gate (degrades to
            # manual-print on a non-Claude host); `none` = nothing outstanding.
            "verifyGate": (
                "none" if not verify_pending
                else "auto" if effective_auto_verify
                else "standard"
            ),
        })
    # Sort by updatedAt desc; rows without a parseable timestamp sort last.
    rows.sort(
        key=lambda r: (_parse_ts(r["updatedAt"]) or datetime.min.replace(tzinfo=timezone.utc)),
        reverse=True,
    )
    return rows


def _counts(specs_dir: Path) -> dict[str, int]:
    """Tally active/paused/abandoned pipelines across the specs tree."""
    tally = {"active": 0, "paused": 0, "abandoned": 0}
    for _name, _epic, state in _scan_features(specs_dir):
        status = state.get("pipelineStatus", "active")
        if status in tally:
            tally[status] += 1
    return tally


# --------------------------------------------------------------------------- #
# Context-window usage
# --------------------------------------------------------------------------- #


def _cwd_slug(cwd: Path) -> str:
    """Map a working directory to its Claude Code project-dir slug.

    Claude Code names the per-project transcript dir by replacing path
    separators (and dots) in the absolute cwd with hyphens, e.g.
    ``/home/u/proj`` -> ``-home-u-proj``.
    """
    return str(cwd.resolve()).replace("/", "-").replace(".", "-")


def _latest_transcript(cwd: Path) -> Path | None:
    """Return the most-recently-modified transcript JSONL for this cwd, if any."""
    project_dir = Path.home() / ".claude" / "projects" / _cwd_slug(cwd)
    if not project_dir.is_dir():
        return None
    transcripts = [p for p in project_dir.glob("*.jsonl") if p.is_file()]
    if not transcripts:
        return None
    return max(transcripts, key=lambda p: p.stat().st_mtime)


def _last_usage(transcript: Path) -> tuple[int, str | None] | None:
    """Scan a transcript from the end for the last `usage` record.

    Returns ``(token_total, model_id)`` where the total sums
    ``input_tokens + cache_creation_input_tokens + cache_read_input_tokens +
    output_tokens`` of the most recent message carrying a usage object — i.e. the
    current context occupancy. Returns ``None`` if no usable record is found.
    """
    try:
        lines = transcript.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        line = line.strip()
        if not line or '"usage"' not in line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        message = record.get("message")
        usage = message.get("usage") if isinstance(message, dict) else record.get("usage")
        if not isinstance(usage, dict):
            continue
        # A malformed transcript may carry a non-numeric usage field; skip that
        # record rather than crash the whole context-usage read (ValueError/TypeError).
        try:
            total = (
                int(usage.get("input_tokens", 0) or 0)
                + int(usage.get("cache_creation_input_tokens", 0) or 0)
                + int(usage.get("cache_read_input_tokens", 0) or 0)
                + int(usage.get("output_tokens", 0) or 0)
            )
        except (TypeError, ValueError):
            continue
        if total <= 0:
            continue
        model = message.get("model") if isinstance(message, dict) else record.get("model")
        return total, (model if isinstance(model, str) else None)
    return None


def _infer_window(model: str | None) -> int:
    """Infer the context window from a model id (1M-context markers -> wide)."""
    if model and ("[1m]" in model.lower() or "-1m" in model.lower()):
        return _WIDE_WINDOW
    return _DEFAULT_WINDOW


def _load_config(config_path: Path) -> dict:
    """Read forge.config.json into a dict, tolerating missing/corrupt files.

    A missing, unreadable, or non-object config downgrades to ``{}`` so callers
    read every key through absent-safe ``.get`` defaults.
    """
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return config if isinstance(config, dict) else {}


def _config_value(config_path: Path, key: str):
    """Read a single key from forge.config.json, or None if absent/unreadable."""
    return _load_config(config_path).get(key)


def auto_verify_for(config: dict, stage: str) -> bool:
    """Return the effective auto-verify setting for ``stage``.

    Per-stage override in ``autoVerifyStages`` wins over the global ``autoVerify``;
    both default to off, so a config with neither key means "no auto-verify".

    Parsing is strict and **fails closed**: only a literal JSON ``true`` enables
    auto-verify. A non-boolean value (e.g. the string ``"false"``, which is truthy
    in Python) is treated as off, not on. The schema already rejects non-booleans
    at author time; this guards a hand-edited config from silently enabling
    automation.
    """
    stages = config.get("autoVerifyStages")
    if isinstance(stages, dict) and stage in stages:
        return stages[stage] is True
    return config.get("autoVerify") is True


def invalid_auto_verify_keys(config: dict) -> list[str]:
    """Return ``autoVerifyStages`` keys outside the verify-capable stage ids.

    An unknown/typo key (e.g. ``forge-1-prod``) would silently never take effect,
    turning an intended off-switch into a no-op. Surfacing it lets the navigator
    warn instead of failing quietly. Mirrors the schema's ``propertyNames.enum``.
    """
    stages = config.get("autoVerifyStages")
    if not isinstance(stages, dict):
        return []
    return [key for key in stages if key not in VERIFY_TOKEN_BY_STAGE]


def context_usage(
    config_path: Path,
    window_override: int | None,
    threshold_override: float | None,
) -> dict:
    """Compute live context-window occupancy for the current session.

    Window precedence: ``--window`` > config ``contextWindowTokens`` > inferred
    from the transcript's model id > ``_DEFAULT_WINDOW``. When inferring (no
    override, no config) and the observed token total already exceeds the default
    window, the window is auto-bumped to ``_WIDE_WINDOW`` — observed tokens above
    200k prove a wider (1M-beta) window is active, so this corrects the reading
    without ever under-reporting a genuine 200k session. Threshold precedence:
    ``--threshold`` > config ``contextWarnThreshold`` > ``_DEFAULT_THRESHOLD``.

    Returns a dict with ``available: True`` and ``{tokens, windowTokens, pct,
    overThreshold, recommendation, model}`` when usage is found, or
    ``{available: False, reason}`` otherwise. Never raises for a missing
    transcript — that is the expected non-Claude / fresh-session path.
    """
    threshold = threshold_override
    if threshold is None:
        cfg_threshold = _config_value(config_path, "contextWarnThreshold")
        threshold = (
            float(cfg_threshold)
            if isinstance(cfg_threshold, (int, float))
            else _DEFAULT_THRESHOLD
        )

    transcript = _latest_transcript(Path.cwd())
    if transcript is None:
        return {"available": False, "reason": "no session transcript found"}
    found = _last_usage(transcript)
    if found is None:
        return {"available": False, "reason": "no usage record in transcript"}
    tokens, model = found

    window = window_override
    if window is None or window <= 0:
        cfg_window = _config_value(config_path, "contextWindowTokens")
        if isinstance(cfg_window, int) and cfg_window > 0:
            window = cfg_window
        else:
            # Inferring (no override, no config). Start from the model marker /
            # conservative default, then auto-bump: observed tokens above the
            # default window PROVE a wider window is active (a 200k session can
            # never exceed 200k), so widen to 1M rather than report a nonsensical
            # >100%. Never under-reports a real 200k session, which can't trip it.
            window = _infer_window(model)
            if tokens > window:
                window = _WIDE_WINDOW

    pct = round(tokens / window, 4)
    over = pct >= threshold
    if over:
        recommendation = "clean-session"
    else:
        recommendation = "continue"
    return {
        "available": True,
        "tokens": tokens,
        "windowTokens": window,
        "pct": pct,
        "threshold": threshold,
        "overThreshold": over,
        "recommendation": recommendation,
        "model": model,
    }


# --------------------------------------------------------------------------- #
# Doctor
# --------------------------------------------------------------------------- #


def _git_output(args: list[str]) -> str | None:
    """Run a read-only git command and return stripped stdout, or None.

    Any failure (git missing, not a repo, nonzero exit, timeout) degrades to
    ``None`` — doctor reports absence rather than crashing.
    """
    try:
        proc = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    return out or None


def _resolve_plugin_root() -> dict:
    """Resolve the plugin root by running the sibling ``forge-root.sh``.

    Uses the resolver that ships next to this script, so the answer reflects
    the install this helper actually belongs to — exactly what a skill's
    bootstrap prelude would find (or fail to find). On success the dict also
    carries the root's ``version`` (from ``.claude-plugin/plugin.json`` or the
    neutral ``.feature-forge-bundle.json``) and, when the root is a git
    checkout, its short ``commit`` — enough to spot version skew between the
    resolved root and the skills a session loaded.
    """
    resolver = Path(__file__).resolve().parent / "forge-root.sh"
    if not resolver.is_file():
        return {"resolved": False, "error": f"resolver not found: {resolver}"}
    try:
        proc = subprocess.run(
            ["bash", str(resolver)], capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"resolved": False, "error": str(exc)}
    if proc.returncode != 0:
        return {
            "resolved": False,
            "error": proc.stderr.strip() or f"resolver exited {proc.returncode}",
        }
    root = proc.stdout.strip()
    info: dict = {"resolved": True, "root": root}
    for rel in (".claude-plugin/plugin.json", ".feature-forge-bundle.json"):
        manifest = Path(root) / rel
        if manifest.is_file():
            version = _load_config(manifest).get("version")
            if isinstance(version, str):
                info["version"] = version
            info["manifest"] = rel
            break
    commit = _git_output(["-C", root, "rev-parse", "--short", "HEAD"])
    if commit:
        info["commit"] = commit
    return info


def _backlog_path(config: dict, name: str, epic: str | None, specs_dir: Path) -> Path:
    """Compose a feature's backlog.json path per the forge-4-backlog rule.

    ``{backlogDir}/{feature}/backlog.json`` when ``backlogDir`` is configured,
    else ``{resolvedFeatureDir}/backlog.json`` (flat or nested under the epic).
    """
    backlog_dir = config.get("backlogDir")
    if isinstance(backlog_dir, str) and backlog_dir:
        return Path(backlog_dir) / name / "backlog.json"
    feature_dir = specs_dir / epic / name if epic else specs_dir / name
    return feature_dir / "backlog.json"


def doctor_report(specs_dir: Path, config_path: Path) -> dict:
    """Assemble the ground-truth diagnostic payload (always succeeds).

    One snapshot of everything a confused session needs checked: resolved
    plugin root + version/commit, current git branch vs. each feature's
    recorded state branch, the recency-ranked feature summary, and whether
    each feature's composed backlog path exists on disk.
    """
    config = _load_config(config_path)
    # --show-current (not rev-parse HEAD) so an unborn branch (fresh repo,
    # no commits yet) still reports its name instead of failing.
    current_branch = _git_output(["branch", "--show-current"])
    default_branch = _default_branch()
    rows = build_rows(specs_dir, config)
    features = []
    for row in rows:
        backlog = _backlog_path(config, row["name"], row["epic"], specs_dir)
        state_branch = row["branch"]
        mismatch = bool(state_branch and current_branch and state_branch != current_branch)
        # Classify a mismatch: on a topic branch it is adoptable (imposed/session-branch
        # drift, Chunk 6); on the default branch it is real drift-back, only a warning.
        branch_reconcile = None
        if mismatch:
            branch_reconcile = "warn-drift" if current_branch == default_branch else "adopt-current"
        features.append({
            "name": row["name"],
            "epic": row["epic"],
            "currentStage": row["currentStage"],
            "nextStage": row["nextStage"],
            "verifyState": row["verifyState"],
            "stateBranch": state_branch,
            "branchMatchesState": (
                state_branch == current_branch
                if state_branch and current_branch
                else None
            ),
            "branchReconcile": branch_reconcile,
            "backlogPath": str(backlog),
            "backlogExists": backlog.is_file(),
        })
    return {
        "pluginRoot": _resolve_plugin_root(),
        "currentBranch": current_branch,
        "specsDir": str(specs_dir),
        "specsDirExists": specs_dir.is_dir(),
        "configPath": str(config_path),
        "configExists": config_path.is_file(),
        "counts": _counts(specs_dir),
        "features": features,
        "invalidAutoVerifyKeys": invalid_auto_verify_keys(config),
        "rootSandbox": _root_sandbox_status(),
    }


def _root_sandbox_status() -> dict:
    """Report the root/sandbox launch condition for forge-5-loop (issue #99).

    On a hosted remote (e.g. Claude.ai) the loop runs as root, where rauf's
    ``claude --dangerously-skip-permissions`` is refused unless ``IS_SANDBOX``
    is set. forge-5-loop exports ``IS_SANDBOX=${IS_SANDBOX:-1}`` at launch when
    root; this surfaces the same condition as a diagnosable check. ``geteuid``
    is absent on Windows — treat that as non-root.
    """
    geteuid = getattr(os, "geteuid", None)
    is_root = geteuid() == 0 if geteuid is not None else False
    is_sandbox_set = os.environ.get("IS_SANDBOX") not in (None, "")
    return {
        "isRoot": is_root,
        "isSandboxSet": is_sandbox_set,
        # True only when the loop would need to supply the default at launch.
        "loopWillSetSandbox": is_root and not is_sandbox_set,
    }


def _print_doctor(report: dict) -> None:
    """Print the human-readable doctor report."""
    root = report["pluginRoot"]
    if root.get("resolved"):
        detail = " ".join(
            f"{key}={root[key]}" for key in ("version", "commit") if key in root
        )
        print(f"plugin root: {root['root']}" + (f"  ({detail})" if detail else ""))
    else:
        print(f"plugin root: UNRESOLVED — {root.get('error', 'unknown')}")
    print(f"current branch: {report['currentBranch'] or '(not a git repo)'}")
    print(
        f"specs dir: {report['specsDir']}"
        + ("" if report["specsDirExists"] else "  (MISSING)")
    )
    print(
        f"config: {report['configPath']}"
        + ("" if report["configExists"] else "  (MISSING)")
    )
    counts = report["counts"]
    print(
        f"features: {counts['active']} active "
        f"(paused: {counts['paused']}, abandoned: {counts['abandoned']})"
    )
    for feat in report["features"]:
        label = feat["name"] + (f" [{feat['epic']}]" if feat["epic"] else "")
        branch = feat["stateBranch"] or "?"
        if feat["branchMatchesState"] is False:
            if feat.get("branchReconcile") == "adopt-current":
                branch += " (MISMATCH — reconcile: adopt current branch)"
            elif feat.get("branchReconcile") == "warn-drift":
                branch += " (MISMATCH — on default branch; create a topic branch)"
            else:
                branch += " (MISMATCH vs current)"
        backlog = "exists" if feat["backlogExists"] else "MISSING"
        print(
            f"  - {label}: stage={feat['currentStage']} "
            f"verify={feat['verifyState']} branch={branch} "
            f"backlog={backlog} ({feat['backlogPath']})"
        )
    invalid = report.get("invalidAutoVerifyKeys") or []
    if invalid:
        print("  ! invalid autoVerifyStages keys (ignored): " + ", ".join(invalid))
    rs = report.get("rootSandbox") or {}
    if rs.get("isRoot"):
        if rs.get("isSandboxSet"):
            print("root/sandbox: running as root; IS_SANDBOX already set — loop launch OK")
        else:
            print(
                "root/sandbox: running as root; IS_SANDBOX not set — forge-5-loop will "
                "export IS_SANDBOX=1 at launch so rauf's "
                "--dangerously-skip-permissions is not refused"
            )


# --------------------------------------------------------------------------- #
# Cross-branch feature discovery
# --------------------------------------------------------------------------- #


def _specs_rel(specs_dir: str) -> str:
    """Normalize a specs dir to the repo-relative POSIX form git ls-tree uses."""
    rel = specs_dir.replace("\\", "/")
    while rel.startswith("./"):
        rel = rel[2:]
    return rel.rstrip("/")


def _state_paths_in_ref(ref: str, specs_rel: str, name: str) -> list[str]:
    """Feature-shaped ``.pipeline-state.json`` paths for ``name`` in one ref.

    Mirrors the ``_scan_features`` flat/nested bound: exactly
    ``{specsDir}/{name}/.pipeline-state.json`` or
    ``{specsDir}/{epic}/{name}/.pipeline-state.json`` — never deeper.
    """
    listing = _git_output(["ls-tree", "-r", "--name-only", ref, "--", specs_rel])
    if not listing:
        return []
    hits: list[str] = []
    prefix = specs_rel + "/"
    for path in listing.splitlines():
        if not path.startswith(prefix) or not path.endswith("/" + PIPELINE_STATE_FILENAME):
            continue
        segments = path[len(prefix):].split("/")
        # [name, state-file] (flat) or [epic, name, state-file] (nested).
        if len(segments) == 2 and segments[0] == name:
            hits.append(path)
        elif len(segments) == 3 and segments[1] == name:
            hits.append(path)
    return hits


def _read_state_at_ref(ref: str, path: str) -> dict:
    """Parse ``git show ref:path`` as pipeline state, downgrading failures to {}."""
    raw = _git_output(["show", f"{ref}:{path}"])
    if raw is None:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _epic_membership(path: str, specs_rel: str, state: dict) -> tuple[str | None, bool]:
    """Derive ``(epic, isEpicMember)`` for a discovered candidate.

    A candidate is an epic member when its state carries an ``epic`` back-pointer
    **or** its path is nested (``{specsDir}/{epic}/{name}/.pipeline-state.json``).
    Nested-ness is structurally authoritative; the ``epic`` field is the recorded
    back-pointer. When the state lacks the field, the nested directory name is used
    so the signal is never "member of epic None".
    """
    prefix = specs_rel + "/"
    nested_epic: str | None = None
    if path.startswith(prefix):
        segments = path[len(prefix):].split("/")
        if len(segments) == 3:  # [epic, name, state-file]
            nested_epic = segments[0]
    epic = state.get("epic")
    epic = epic if isinstance(epic, str) and epic else nested_epic
    return epic, bool(nested_epic) or bool(epic)


def _list_refs(pattern: str) -> list[tuple[str, str]]:
    """Return ``(short_ref, committer_date)`` pairs under a ref namespace."""
    raw = _git_output([
        "for-each-ref",
        "--format=%(refname:short)\t%(committerdate:iso-strict)",
        pattern,
    ])
    if not raw:
        return []
    out: list[tuple[str, str]] = []
    for line in raw.splitlines():
        ref, _, date = line.partition("\t")
        if ref:
            out.append((ref, date))
    return out


def discover_feature(name: str, specs_dir: str) -> dict:
    """Find a feature's pipeline state across all branches (strictly read-only).

    Scans every local head and remote-tracking ref for a feature-shaped
    ``.pipeline-state.json``, parses each hit via ``git show``, and ranks
    candidates by (state's own ``branch`` field matches the ref) first, then
    local-before-remote-tracking, then newest commit. When no candidate exists
    locally, ``git ls-remote --heads origin`` surfaces plausibly-named
    branches a single-branch clone never fetched, as ``needsFetch`` entries
    with the exact fetch/switch commands.

    Never mutates anything: checkout is the caller's decision (and requires
    the user's explicit accept plus a clean tree — see shared-conventions).
    """
    if _git_output(["rev-parse", "--git-dir"]) is None:
        return {
            "feature": name,
            "gitRepo": False,
            "currentBranch": None,
            "candidates": [],
            "remoteCandidates": [],
        }
    current_branch = _git_output(["branch", "--show-current"])
    specs_rel = _specs_rel(specs_dir)

    refs = [(ref, date, False) for ref, date in _list_refs("refs/heads")]
    refs += [(ref, date, True) for ref, date in _list_refs("refs/remotes")]

    candidates: list[dict] = []
    matched_branches: set[str] = set()
    known_branches: set[str] = set()
    for ref, commit_date, is_remote in refs:
        branch = ref.split("/", 1)[1] if is_remote else ref
        if is_remote and (not branch or branch == "HEAD"):
            continue
        known_branches.add(branch)
        if branch in matched_branches:
            continue  # the local head already yielded this branch's state
        for path in _state_paths_in_ref(ref, specs_rel, name):
            state = _read_state_at_ref(ref, path)
            state_branch = state.get("branch")
            state_branch = state_branch if isinstance(state_branch, str) else None
            updated = state.get("updatedAt")
            epic, is_epic_member = _epic_membership(path, specs_rel, state)
            matched_branches.add(branch)
            candidates.append({
                "branch": branch,
                "ref": ref,
                "remoteTracking": is_remote,
                "path": path,
                "stateBranch": state_branch,
                "stateBranchMatches": state_branch == branch,
                "currentStage": state.get("currentStage"),
                "pipelineStatus": state.get("pipelineStatus", "active"),
                "epic": epic,
                "isEpicMember": is_epic_member,
                "updatedAt": updated if isinstance(updated, str) else None,
                "commitDate": commit_date or None,
                "isCurrentBranch": branch == current_branch,
                "switchCommand": f"git switch {branch}",
            })

    def _rank(cand: dict) -> tuple:
        ts = _parse_ts(cand["commitDate"]) or datetime.min.replace(tzinfo=timezone.utc)
        return (
            not cand["stateBranchMatches"],
            cand["remoteTracking"],
            -ts.timestamp(),
        )

    candidates.sort(key=_rank)

    # Single-branch clones: the branch holding the state may never have been
    # fetched. Only when nothing was found locally, ask the remote for heads we
    # do not know and surface the plausibly-named ones (the feature name appears
    # in the branch name — e.g. forge/<feature>). These are name-based hints
    # only; their contents were NOT inspected.
    remote_candidates: list[dict] = []
    if not candidates:
        ls_remote = _git_output(["ls-remote", "--heads", "origin"])
        for line in (ls_remote or "").splitlines():
            _, _, refname = line.partition("\t")
            if not refname.startswith("refs/heads/"):
                continue
            branch = refname[len("refs/heads/"):]
            if branch in known_branches or name not in branch:
                continue
            remote_candidates.append({
                "branch": branch,
                "needsFetch": True,
                "fetchCommand": f"git fetch origin {branch}:refs/remotes/origin/{branch}",
                "switchCommand": f"git switch {branch}",
            })

    return {
        "feature": name,
        "gitRepo": True,
        "currentBranch": current_branch,
        "specsDir": specs_rel,
        "candidates": candidates,
        "remoteCandidates": remote_candidates,
    }


def _print_discover(payload: dict) -> None:
    """Print the human-readable discovery report."""
    name = payload["feature"]
    if not payload["gitRepo"]:
        print(f"discover-feature {name}: not a git repository — nothing to scan")
        return
    candidates = payload["candidates"]
    remote = payload["remoteCandidates"]
    if not candidates and not remote:
        print(
            f"discover-feature {name}: no pipeline state found on any local or "
            "remote-tracking branch"
        )
        return
    for cand in candidates:
        marks = []
        if cand["isCurrentBranch"]:
            marks.append("current branch")
        if cand["remoteTracking"]:
            marks.append("remote-tracking")
        if not cand["stateBranchMatches"] and cand["stateBranch"]:
            marks.append(f"state records branch {cand['stateBranch']}")
        if cand.get("isEpicMember"):
            marks.append(f"member of epic {cand.get('epic') or '?'}")
        suffix = f"  ({'; '.join(marks)})" if marks else ""
        print(
            f"  {cand['branch']}: stage={cand['currentStage'] or '?'} "
            f"status={cand['pipelineStatus']} path={cand['path']}{suffix}"
        )
        if not cand["isCurrentBranch"]:
            print(f"      switch: {cand['switchCommand']}")
    for cand in remote:
        print(
            f"  {cand['branch']}: on origin only (never fetched; contents not "
            "inspected — name matches)"
        )
        print(f"      fetch:  {cand['fetchCommand']}")
        print(f"      switch: {cand['switchCommand']}")


def _all_state_paths_in_ref(ref: str, specs_rel: str) -> list[tuple[str, str]]:
    """Every feature-shaped ``.pipeline-state.json`` in one ref as ``(path, feature)``.

    The ``--all`` counterpart to ``_state_paths_in_ref``: same flat/nested bound
    (``{specsDir}/{name}/…`` or ``{specsDir}/{epic}/{name}/…``) but for every
    feature, not one named one.
    """
    listing = _git_output(["ls-tree", "-r", "--name-only", ref, "--", specs_rel])
    if not listing:
        return []
    hits: list[tuple[str, str]] = []
    prefix = specs_rel + "/"
    for path in listing.splitlines():
        if not path.startswith(prefix) or not path.endswith("/" + PIPELINE_STATE_FILENAME):
            continue
        segments = path[len(prefix):].split("/")
        if len(segments) == 2:          # [name, state-file] (flat)
            hits.append((path, segments[0]))
        elif len(segments) == 3:        # [epic, name, state-file] (nested)
            hits.append((path, segments[1]))
    return hits


def discover_all(specs_dir: str) -> dict:
    """Discover EVERY feature's pipeline state across all branches (read-only, Chunk 5c).

    The empty-dashboard counterpart to ``discover-feature <name>``: enumerates every
    feature-shaped state across local heads + remote-tracking refs and groups the
    candidates by feature, so a fresh clone / default-branch session can see the whole
    branch-scattered pipeline set instead of nothing. Never mutates anything.
    """
    if _git_output(["rev-parse", "--git-dir"]) is None:
        return {"gitRepo": False, "currentBranch": None, "features": []}
    current_branch = _git_output(["branch", "--show-current"])
    specs_rel = _specs_rel(specs_dir)
    refs = [(ref, date, False) for ref, date in _list_refs("refs/heads")]
    refs += [(ref, date, True) for ref, date in _list_refs("refs/remotes")]

    by_feature: dict[str, list[dict]] = {}
    for ref, commit_date, is_remote in refs:
        branch = ref.split("/", 1)[1] if is_remote else ref
        if is_remote and (not branch or branch == "HEAD"):
            continue
        for path, feature in _all_state_paths_in_ref(ref, specs_rel):
            seen = by_feature.setdefault(feature, [])
            if any(c["branch"] == branch for c in seen):
                continue  # a local head already yielded this branch's state
            state = _read_state_at_ref(ref, path)
            state_branch = state.get("branch")
            state_branch = state_branch if isinstance(state_branch, str) else None
            epic, is_epic_member = _epic_membership(path, specs_rel, state)
            seen.append({
                "branch": branch,
                "remoteTracking": is_remote,
                "path": path,
                "stateBranch": state_branch,
                "stateBranchMatches": state_branch == branch,
                "currentStage": state.get("currentStage"),
                "pipelineStatus": state.get("pipelineStatus", "active"),
                "epic": epic,
                "isEpicMember": is_epic_member,
                "commitDate": commit_date or None,
                "isCurrentBranch": branch == current_branch,
                "switchCommand": f"git switch {branch}",
            })

    def _rank(cand: dict) -> tuple:
        ts = _parse_ts(cand["commitDate"]) or datetime.min.replace(tzinfo=timezone.utc)
        return (not cand["stateBranchMatches"], cand["remoteTracking"], -ts.timestamp())

    features = []
    for feature in sorted(by_feature):
        cands = sorted(by_feature[feature], key=_rank)
        features.append({"feature": feature, "candidates": cands})
    return {"gitRepo": True, "currentBranch": current_branch, "features": features}


def _print_discover_all(payload: dict) -> None:
    """Human-readable ``discover-feature --all`` report."""
    if not payload["gitRepo"]:
        print("discover-feature --all: not a git repository — nothing to scan")
        return
    if not payload["features"]:
        print("discover-feature --all: no pipeline state found on any local or "
              "remote-tracking branch")
        return
    for feat in payload["features"]:
        print(f"{feat['feature']}:")
        for cand in feat["candidates"]:
            marks = []
            if cand["isCurrentBranch"]:
                marks.append("current branch")
            if cand["remoteTracking"]:
                marks.append("remote-tracking")
            if not cand["stateBranchMatches"] and cand["stateBranch"]:
                marks.append(f"state records branch {cand['stateBranch']}")
            if cand.get("isEpicMember"):
                marks.append(f"member of epic {cand.get('epic') or '?'}")
            suffix = f"  ({'; '.join(marks)})" if marks else ""
            print(f"  {cand['branch']}: stage={cand['currentStage'] or '?'} "
                  f"status={cand['pipelineStatus']}{suffix}")
            if not cand["isCurrentBranch"]:
                print(f"      switch: {cand['switchCommand']}")


# --------------------------------------------------------------------------- #
# Branch reconciliation (Chunk 6) — imposed/session-branch drift
# --------------------------------------------------------------------------- #


def _default_branch() -> str | None:
    """The repo's default branch: origin/HEAD target, else `main`/`master` if present."""
    ref = _git_output(["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"])
    if ref:
        return ref.rsplit("/", 1)[-1]
    for cand in ("main", "master"):
        if _git_output(["rev-parse", "--verify", "--quiet", f"refs/heads/{cand}"]) is not None:
            return cand
    return None


def reconcile_branch(
    name: str, specs_dir: Path, config_path: Path, epic: str | None = None
) -> dict:
    """Decide whether a feature's recorded ``branch`` should adopt the current branch.

    Read-only: it emits a decision; the caller performs any state write. A hosted
    environment (Claude.ai remote, cloud agents) imposes an arbitrary session branch
    that Branch Setup silently records; when the user moves to the intended branch the
    recorded ``branch`` goes stale and every branch-aware mechanism keys off it. This
    reconciler treats *where the state actually resolves* as the source of truth, with a
    default-branch guardrail so genuine drift-back-to-default is still surfaced, not
    silently adopted.
    """
    if _git_output(["rev-parse", "--git-dir"]) is None:
        return {"feature": name, "gitRepo": False, "reconcile": False,
                "action": "none", "reason": "not a git repository"}
    current = _git_output(["branch", "--show-current"])
    default = _default_branch()
    config = _load_config(config_path)
    row = next(
        (r for r in build_rows(specs_dir, config)
         if r["name"] == name and (epic is None or r["epic"] == epic)),
        None,
    )
    state_path = None
    if row is not None:
        parent = specs_dir / row["epic"] / name if row["epic"] else specs_dir / name
        state_path = str(parent / PIPELINE_STATE_FILENAME)
    base = {
        "feature": name,
        "gitRepo": True,
        "currentBranch": current,
        "defaultBranch": default,
        "stateBranch": row["branch"] if row else None,
        "resolvesOnCurrentBranch": row is not None,
        "statePath": state_path,
        "newBranch": None,
    }
    if current is None:
        return {**base, "reconcile": False, "action": "none",
                "reason": "no current branch (detached HEAD or unborn branch)"}
    if row is None:
        return {**base, "reconcile": False, "action": "not-resolved",
                "reason": "feature state does not resolve on the current branch — "
                          "use discover-feature to locate it"}
    state_branch = base["stateBranch"]
    if state_branch == current:
        return {**base, "reconcile": False, "action": "none",
                "reason": "recorded branch already matches the current branch"}
    if current == default:
        return {**base, "reconcile": False, "action": "warn-drift",
                "reason": f"on the default branch ({default}); recording it would commit "
                          "here — create/switch to a topic branch instead of reconciling"}
    detail = (f"recorded branch {state_branch!r} differs from the current topic branch"
              if state_branch else "no branch recorded")
    return {**base, "reconcile": True, "action": "adopt-current", "newBranch": current,
            "reason": f"{detail}; the feature state resolves here, so adopt the current branch"}


def _print_reconcile(payload: dict) -> None:
    """Human-readable reconcile-branch report."""
    if not payload["gitRepo"]:
        print(f"reconcile-branch {payload['feature']}: not a git repository")
        return
    print(f"reconcile-branch {payload['feature']}: {payload['action']} — {payload['reason']}")
    print(f"  current={payload['currentBranch']} recorded={payload['stateBranch'] or '(none)'} "
          f"default={payload['defaultBranch']}")
    if payload["reconcile"]:
        print(f"  → write state branch := {payload['newBranch']}  ({payload['statePath']})")


# --------------------------------------------------------------------------- #
# Epic-member base guard (Issue #125) — detached-base detection
# --------------------------------------------------------------------------- #


def check_epic_base(
    name: str, specs_dir: Path, config_path: Path, epic: str | None = None
) -> dict:
    """Verify the current HEAD actually contains the epic manifest for a nested member.

    Defense-in-depth for the split-brain-epic failure (Issue #125): when a feature
    resolves to a nested epic-member directory but the epic's ``epic-manifest.json``
    is absent from the current checkout, the member stub was reached from a branch
    that predates (or otherwise lacks) the manifest commit — a detached base. This
    is read-only: it emits a decision; the caller stops or warns.

    Actions:
    - ``none`` — not a git repo, a standalone feature (no epic to check), or the
      manifest is present on HEAD. Nothing to do.
    - ``not-resolved`` — the feature does not resolve on the current branch.
    - ``warn-detached-base`` — nested member resolves here but the manifest is
      missing on HEAD; ``homeBranch`` is the member stub's recorded ``branch``.
    """
    base = {
        "feature": name,
        "gitRepo": True,
        "epic": epic,
        "isEpicMember": False,
        "manifestOnHead": None,
        "homeBranch": None,
    }
    if _git_output(["rev-parse", "--git-dir"]) is None:
        return {**base, "gitRepo": False, "action": "none",
                "reason": "not a git repository"}
    config = _load_config(config_path)
    row = next(
        (r for r in build_rows(specs_dir, config)
         if r["name"] == name and (epic is None or r["epic"] == epic)),
        None,
    )
    if row is None:
        return {**base, "action": "not-resolved",
                "reason": "feature state does not resolve on the current branch — "
                          "use discover-feature to locate it"}
    member_epic = row["epic"]
    if not member_epic:
        return {**base, "action": "none",
                "reason": "standalone feature — no epic base to check"}
    base = {**base, "epic": member_epic, "isEpicMember": True,
            "homeBranch": row["branch"]}
    manifest = specs_dir / member_epic / MANIFEST_FILENAME
    if manifest.is_file():
        return {**base, "manifestOnHead": True, "action": "none",
                "reason": f"epic manifest present on the current branch "
                          f"({member_epic}/{MANIFEST_FILENAME})"}
    return {**base, "manifestOnHead": False, "action": "warn-detached-base",
            "reason": f"member of epic {member_epic!r} resolves here, but "
                      f"{member_epic}/{MANIFEST_FILENAME} is absent on the current "
                      f"branch — this base predates or lacks the epic manifest"}


def _print_check_epic_base(payload: dict) -> None:
    """Human-readable check-epic-base report."""
    if not payload["gitRepo"]:
        print(f"check-epic-base {payload['feature']}: not a git repository")
        return
    print(f"check-epic-base {payload['feature']}: {payload['action']} — {payload['reason']}")
    if payload["action"] == "warn-detached-base":
        print(f"  → switch to the epic's home branch: {payload['homeBranch'] or '(unknown)'}")


# --------------------------------------------------------------------------- #
# Scripted Stage Exit
# --------------------------------------------------------------------------- #

#: Authoring stages whose closing runs stage-exit (the loop keeps bespoke exits).
EXIT_STAGES: Final[tuple[str, ...]] = (
    "forge-0-epic",
    "forge-1-prd",
    "forge-2-tech",
    "forge-3-specs",
    "forge-4-backlog",
)

#: Stage id -> the noun phrase gate wording uses (the old {stage} stamp slot).
STAGE_NOUN: Final[dict[str, str]] = {
    "forge-0-epic": "the epic decomposition",
    "forge-1-prd": "the PRD",
    "forge-2-tech": "the tech spec",
    "forge-3-specs": "the implementation specs",
    "forge-4-backlog": "the backlog",
}

#: Verify token per exit stage. Extends the production map with the epic stage,
#: whose verify entry is recorded under ``forge-verify-epic``.
_EXIT_VERIFY_TOKEN: Final[dict[str, str]] = {
    **VERIFY_TOKEN_BY_STAGE,
    "forge-0-epic": "epic",
}

#: The stage each exit hands off to when pipeline state cannot say better.
_EXIT_NEXT_STAGE: Final[dict[str, str]] = {
    "forge-0-epic": "forge-1-prd",
    "forge-1-prd": "forge-2-tech",
    "forge-2-tech": "forge-3-specs",
    "forge-3-specs": "forge-4-backlog",
    "forge-4-backlog": "forge-5-loop",
}

#: The fixed final line of the NEXT-STEPS block. The stamp instructs the skill
#: to print the block verbatim as its absolute last output — nothing after this.
NEXT_STEPS_SENTINEL: Final = "─ forge: end of stage ─"


def _verify_state_for(state: dict, stage: str) -> str:
    """Classify THIS stage's verify freshness (stage-scoped ``verify_state``).

    Same labels as ``verify_state`` — fresh / stale / failing / never /
    skipped / none — but for the given stage rather than the most-recently
    completed one, because stage-exit runs inside the stage that just closed.
    """
    token = _EXIT_VERIFY_TOKEN.get(stage)
    if token is None:
        return "none"
    entry = _verify_entry(state, f"forge-verify-{token}")
    status = entry.get("status")
    if status == "skipped":
        return "skipped"
    if status == "findings-reported":
        return "failing"
    if status not in _VERIFY_RESOLVED:
        return "never"
    verified_version = entry.get("verifiedStageVersion")
    stage_version = _stage_version(state, stage)
    if (
        isinstance(verified_version, int)
        and stage_version is not None
        and verified_version == stage_version
    ):
        return "fresh"
    return "stale"


def _resolve_feature_dir(specs_dir: Path, feature: str, epic: str | None) -> Path:
    """Best-effort feature dir (flat, else unique nested, else flat literal).

    stage-exit tolerates an unresolvable dir — the state read downgrades to
    ``{}`` and every directive still computes from defaults.
    """
    if epic:
        return specs_dir / epic / feature
    flat = specs_dir / feature
    if (flat / PIPELINE_STATE_FILENAME).is_file():
        return flat
    if specs_dir.is_dir():
        nested = [
            p for p in specs_dir.glob(f"*/{feature}")
            if (p / PIPELINE_STATE_FILENAME).is_file()
        ]
        if len(nested) == 1:
            return nested[0]
    return flat


def _host_command(command: str, host: str) -> str:
    """Rewrite a `/skill:` slash command to the host's surface.

    Pi's slash-command surface is `/skill:` (matching the adapter body's
    `/skill:` -> `/skill:` translation). The scripted stage-exit output bypasses
    that body translation, so it rewrites the commands it emits here. No-op for
    claude/generic, which keep the canonical `/skill:` form.
    """
    return command.replace("/skill:", "/skill:") if host == "pi" else command


def _next_steps_block(
    next_command: str, host: str, reconcile: dict | None = None
) -> str:
    """Render the sentinel-terminated NEXT-STEPS block for the given host.

    The Claude wording uses the literal ``/clear`` slash-command; the generic
    wording is host-neutral (matching the adapter build's host-term table, so
    a non-Claude bundle invoking ``--host generic`` never instructs a fake
    slash-command).

    ``reconcile`` carries the epic-backflow routing (§Epic backflow in
    ``references/stage-exit-protocol.md``). When it marks a **blocking** request
    (``required: true``), the fenced primary command becomes the epic reconcile
    command and the normal next stage is demoted to a follow-up line. When it
    marks only **non-blocking** requests (``reminder: true``), the fenced command
    stays the normal next stage and a reminder line is appended. Either way the
    added prose is host-neutral (no literal ``/clear``) so it survives verbatim
    into a generic bundle.
    """
    if host == "claude":
        clear_line = (
            "1. `/clear` — recommended unconditionally at this stage boundary; "
            "every artifact is on disk, so the work survives the clear. "
            "I can't `/clear` for you — you have to run it yourself."
        )
        next_line = (
            "2. Then start a fresh session and run the next stage below — or "
            "re-run `/skill:forge` to let the navigator resume from disk."
        )
    elif host == "pi":
        # Pi's fresh-session command is `/new` (not `/clear`); its slash-command
        # surface is `/skill:` (the fenced command below is rewritten to match).
        clear_line = (
            "1. `/new` — recommended unconditionally at this stage boundary; every "
            "artifact is on disk, so the work survives starting a fresh session. "
            "I can't run `/new` for you — you have to run it yourself."
        )
        next_line = (
            "2. Then, in the new session, run the next stage below — or re-run "
            "`/skill:forge` to let the navigator resume from disk."
        )
    else:
        clear_line = (
            "1. Clear your session / start a fresh session — recommended "
            "unconditionally at this stage boundary; every artifact is on "
            "disk, so the work survives it."
        )
        next_line = (
            "2. Then start a fresh session and run the next stage below — or "
            "re-run the forge navigator skill to resume from disk."
        )
    blocking = bool(reconcile and reconcile.get("required"))
    # The primary actionable command goes in a fenced block so mobile/remote hosts
    # get a native copy button (inline code is not tap-to-copy). For a blocking
    # epic-change request the primary is the reconcile command; otherwise it is the
    # normal next-stage command. The fence sits before the sentinel, so the
    # sentinel remains the absolute last line.
    fenced_command = _host_command(reconcile["command"] if blocking else next_command, host)
    lines = ["**Next steps**", clear_line]
    if blocking:
        count = reconcile["count"]
        plural = "s" if count != 1 else ""
        lines.append(
            f"2. Then reconcile the epic **before** the next stage — {count} "
            f"blocking epic change request{plural} flagged, and proceeding would "
            "build this feature's artifacts on a decomposition that is about to "
            "change. Run the reconcile command below first."
        )
    else:
        lines.append(next_line)
    lines.append("")
    lines.append(f"```\n{fenced_command}\n```")
    if blocking and reconcile.get("deferred"):
        deferred_cmd = _host_command(reconcile["deferred"], host)
        lines.append(f"After reconciling, continue the pipeline with: `{deferred_cmd}`")
    elif reconcile and reconcile.get("reminder"):
        count = reconcile["count"]
        plural = "s" if count != 1 else ""
        lines.append(
            f"You also flagged {count} epic change{plural} to reconcile when "
            f"convenient: `{_host_command(reconcile['command'], host)}`"
        )
    lines.append(NEXT_STEPS_SENTINEL)
    return "\n".join(lines)


def stage_exit(
    feature: str,
    stage: str,
    specs_dir: Path,
    config_path: Path,
    epic: str | None,
    host: str,
    next_feature: str | None,
) -> dict:
    """Compute the Scripted Stage Exit payload: DIRECTIVES + NEXT-STEPS block.

    Directive semantics (the contract in ``references/stage-exit-protocol.md``):

    - ``runInStageVerify`` — the effective auto-verify (per-stage override,
      else global; strict-true) is on AND this stage's verify is not already
      resolved (fresh/skipped). The skill then dispatches the clean-room
      verify in-session (principle #2: verify before the clear).
    - ``autoFixEligible`` — ``autoFix`` is strict-true AND the in-stage verify
      runs AND the working tree is clean. Findings-level preconditions (zero
      unresolved decisions) remain the skill's runtime check.
    - ``verifyGate`` — ``none`` when verify is resolved or the in-stage run
      covers it; ``standard`` when auto-verify is off and verification is
      outstanding on a host with a question mechanism + clean-room path
      (``--host claude``); ``manual-print`` for the same state on a generic
      host (print ``verifyCommand`` instead of presenting the gate).
    - ``nextStage``/``nextCommand`` — from pipeline state when it already
      records this stage complete (first non-complete production stage), else
      the fixed successor. ``--next-feature`` names the first actionable
      feature for the epic handoff; without it the runtime placeholder
      ``{first-actionable-feature}`` passes through for the skill to resolve.
    - ``epicReconcile`` — present only when the exiting member carries
      ``open`` ``epicChangeRequests`` (epic-backflow). ``required: true`` (any
      ``blocksCurrent: true`` request) interposes a reconcile-first exit: the
      NEXT-STEPS primary command becomes ``/skill:forge-0-epic {epic}``
      and the normal next stage is deferred. Only non-blocking requests set
      ``reminder: true`` and append a non-blocking reminder line. Absent when
      there are no open requests (common path) or the epic name is unresolvable.

    Read-only, deterministic, exit 0 — errors degrade to defaults, never
    crash a stage closing.
    """
    config = _load_config(config_path)
    feature_dir = _resolve_feature_dir(specs_dir, feature, epic)
    state = _read_state(feature_dir / PIPELINE_STATE_FILENAME)

    git_repo = _git_output(["rev-parse", "--git-dir"]) is not None
    clean_tree: bool | None = None
    if git_repo:
        porcelain = _git_output(["status", "--porcelain"])
        clean_tree = porcelain is None or porcelain == ""

    verify_label = _verify_state_for(state, stage)
    resolved = verify_label in ("fresh", "skipped")
    effective_auto_verify = auto_verify_for(config, stage)
    run_in_stage = effective_auto_verify and not resolved
    auto_fix_eligible = (
        config.get("autoFix") is True and run_in_stage and clean_tree is True
    )
    if resolved or effective_auto_verify:
        verify_gate = "none"
    elif host == "claude":
        verify_gate = "standard"
    else:
        verify_gate = "manual-print"

    next_stage_id = _EXIT_NEXT_STAGE.get(stage)
    state_next = next_stage(state)
    if (
        stage in PRODUCTION_STAGES
        and state_next is not None
        and PRODUCTION_STAGES.index(state_next) > PRODUCTION_STAGES.index(stage)
    ):
        # State records this stage complete AND its walk lands beyond it —
        # trust it (it skips stages already completed out of order). A missing
        # or behind-the-stage walk (state not yet flushed, corrupt file) falls
        # back to the fixed successor, never to an earlier stage.
        next_stage_id = state_next
    next_arg = next_feature or (
        "{first-actionable-feature}" if stage == "forge-0-epic" else feature
    )
    next_command = f"/skill:{next_stage_id} {next_arg}" if next_stage_id else None

    # Epic backflow routing: an exiting member may carry epic-level change requests
    # (recorded by forge-1-prd/forge-2-tech). A `blocksCurrent: true` request means
    # the current feature's next stage would build on a soon-to-change decomposition,
    # so the exit interposes a reconcile-first step; only-`false` requests append a
    # non-blocking reminder. Read-only; the common path (no open requests) is a no-op.
    # The epic name comes from the `--epic` arg or the state's `epic` back-pointer.
    epic_reconcile: dict | None = None
    epic_name = epic or state.get("epic")
    open_requests = [
        r
        for r in state.get("epicChangeRequests", [])
        if isinstance(r, dict) and r.get("status") == "open"
    ]
    if open_requests and epic_name:
        reconcile_command = f"/skill:forge-0-epic {epic_name}"
        blocking = [r for r in open_requests if r.get("blocksCurrent") is True]
        if blocking:
            epic_reconcile = {
                "required": True,
                "command": reconcile_command,
                "count": len(blocking),
                "deferred": next_command,
            }
        else:
            epic_reconcile = {
                "required": False,
                "reminder": True,
                "command": reconcile_command,
                "count": len(open_requests),
            }

    directives = {
        "stage": stage,
        "stageNoun": STAGE_NOUN.get(stage, stage),
        "feature": feature,
        "runInStageVerify": run_in_stage,
        "verifyGate": verify_gate,
        "autoFixEligible": auto_fix_eligible,
        "verifyState": verify_label,
        "verifyCommand": _host_command(f"/skill:forge-verify {feature}", host),
        "autoVerifyEffective": effective_auto_verify,
        "nextStage": next_stage_id,
        "nextCommand": _host_command(next_command, host) if next_command else next_command,
        "invalidAutoVerifyKeys": invalid_auto_verify_keys(config),
        "gitRepo": git_repo,
        "cleanTree": clean_tree,
        "host": host,
    }
    if epic_reconcile is not None:
        directives["epicReconcile"] = epic_reconcile
    return {
        "directives": directives,
        "nextSteps": _next_steps_block(
            next_command or "/skill:forge", host, epic_reconcile
        ),
        "sentinel": NEXT_STEPS_SENTINEL,
    }


def _print_stage_exit(payload: dict) -> None:
    """Print DIRECTIVES then the NEXT-STEPS block (the skill-facing form)."""
    print("DIRECTIVES:")
    print(json.dumps(payload["directives"], indent=2, ensure_ascii=False))
    print(
        "NEXT-STEPS (print this block verbatim as your absolute last output — "
        "nothing after the sentinel):"
    )
    print(payload["nextSteps"])


# --------------------------------------------------------------------------- #
# Effective loopRunner config
# --------------------------------------------------------------------------- #


def _default_schema_path() -> Path:
    """Return the bundled forge-config-schema.json path (sibling references/ dir).

    Resolved relative to this script file so `effective-config` works from any
    cwd. Overridable via the ``--schema`` flag (chiefly for tests).

    Returns:
        The Path to ``references/forge-config-schema.json`` next to ``scripts/``.
    """
    return Path(__file__).resolve().parent.parent / "references" / "forge-config-schema.json"


def _loop_runner_defaults(schema_path: Path) -> dict[str, object]:
    """Extract every ``loopRunner`` field's schema ``default``.

    Reads ``properties.loopRunner.properties.<field>.default`` for each field.
    Stdlib-only (``json`` + dict access), mirroring
    ``tests/test_config_defaults_parity.py``. The schema is the single source of
    truth; nothing here is hardcoded.

    Only fields that actually declare a ``default`` keyword are included. Every
    ``loopRunner`` field does today; a field losing its default would be a schema
    regression the drift guard catches, not something silently patched here.

    Args:
        schema_path: Path to ``forge-config-schema.json``.

    Returns:
        A dict mapping each ``loopRunner`` field name to its declared default
        value (templates such as ``"{bin} loop run …"`` are returned literally).

    Raises:
        UsageError: If the schema is missing, unreadable, unparseable, or lacks a
            ``loopRunner.properties`` object — a deterministic failure that must
            exit 2. Never returns partial/empty defaults silently.
    """
    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise UsageError(f"config schema unreadable: {schema_path} ({exc})") from exc
    except json.JSONDecodeError as exc:
        raise UsageError(f"config schema is not valid JSON: {schema_path} ({exc})") from exc

    props = None
    if isinstance(schema, dict):
        loop_runner = schema.get("properties", {})
        if isinstance(loop_runner, dict):
            loop_runner = loop_runner.get("loopRunner", {})
        if isinstance(loop_runner, dict):
            props = loop_runner.get("properties")
    if not isinstance(props, dict) or not props:
        raise UsageError(f"config schema has no loopRunner.properties object: {schema_path}")

    return {
        field: spec["default"]
        for field, spec in props.items()
        if isinstance(spec, dict) and "default" in spec
    }


def resolve_loop_runner(config_path: Path, schema_path: Path) -> dict[str, object]:
    """Resolve the effective ``loopRunner`` config: schema defaults + user overrides.

    Reads the schema defaults, then merges the user's ``loopRunner`` block (from
    ``forge.config.json`` via the existing ``_load_config``) OVER them. A user
    field replaces the default; an absent field keeps the default. The result is
    the fully-resolved block the loop consumes — computed deterministically so no
    model ever merges it by hand.

    Args:
        config_path: Path to ``forge.config.json`` (``_load_config`` tolerates a
            missing/corrupt file, yielding pure defaults).
        schema_path: Path to ``forge-config-schema.json`` (source of the defaults).

    Returns:
        The resolved ``loopRunner`` object: every schema-defaulted field present,
        with user overrides applied.

    Raises:
        UsageError: If the schema is unreadable/unparseable (propagated from
            ``_loop_runner_defaults``) — exit 2, a deterministic failure.
    """
    resolved: dict[str, object] = dict(_loop_runner_defaults(schema_path))

    user_loop_runner = _load_config(config_path).get("loopRunner")
    if isinstance(user_loop_runner, dict):
        for key, value in user_loop_runner.items():
            # Flat override: a user value replaces the default for that field.
            # (A future nested loopRunner field would recurse here; today every
            # field is a scalar, so a shallow override is exact.) An unknown key
            # is carried through — the model would have carried it too, and the
            # config schema is the authority that flags it at author time.
            resolved[key] = value

    return resolved


def _print_effective_config(resolved: dict[str, object]) -> None:
    """Print the resolved loopRunner config as an aligned key: value table.

    Args:
        resolved: The resolved loopRunner object from ``resolve_loop_runner``.
    """
    print("Effective loopRunner config:")
    width = max((len(k) for k in resolved), default=0)
    for key in sorted(resolved):
        print(f"  {key.ljust(width)} : {resolved[key]!r}")


# --------------------------------------------------------------------------- #
# State writes (shared machinery for the state-* verbs)
# --------------------------------------------------------------------------- #


def _now_iso() -> str:
    """Return the current UTC time as a Z-suffixed, second-precision ISO-8601 string.

    Matches the `.pipeline-state.json` timestamp convention already on disk (the
    schema's ``format: date-time`` values; the read path normalizes a trailing
    ``Z``). Second precision keeps `updatedAt`/`startedAt`/`completedAt` visually
    consistent with the values other pipeline writers produce.

    Returns:
        A timestamp like ``"2026-07-29T03:30:00Z"``.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_state(state_path: Path, state: dict) -> None:
    """Atomically write a `.pipeline-state.json` (temp file + os.replace).

    Mirrors epic-manifest.py's ``atomic_write``: write to a sibling temp file in
    the same directory as the target, flush + fsync the bytes, then os.replace()
    the temp file onto the target. os.replace is atomic on POSIX within one
    filesystem, so an interrupted write never leaves a partial or corrupt state
    file. Concurrent multi-session mutation is out of scope (single writer
    assumed, matching epic-manifest.py).

    Args:
        state_path: Destination path, e.g.
            ``{specsDir}/{feature}/.pipeline-state.json``.
        state: The fully-formed state dict to serialize.

    Raises:
        UsageError: If the temp file cannot be created/written or the replace
            fails (→ exit 2). The temp file is removed first, so a failed write
            leaves no debris and the original target untouched.
    """
    try:
        fd, tmp_name = tempfile.mkstemp(
            prefix=f".{state_path.name}.", suffix=".tmp", dir=state_path.parent
        )
    except OSError as exc:
        raise UsageError(f"atomic write to {state_path} failed: {exc}") from exc
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, state_path)
    except OSError as exc:
        tmp_path.unlink(missing_ok=True)
        raise UsageError(f"atomic write to {state_path} failed: {exc}") from exc


def _resolve_feature_dir_for_write(
    specs_dir: Path, feature: str, epic: str | None
) -> Path:
    """Fail-closed feature dir for the ``state-*`` WRITERS.

    ``_resolve_feature_dir`` is the reader's best-effort resolver: it returns the
    flat ``{specsDir}/{feature}`` whenever that dir carries a state file, and
    falls back to the flat literal on a multi-match. That tolerance was written
    for ``stage-exit``, which is READ-ONLY — an unresolvable dir there just
    downgrades to ``{}``. For a writer the same tolerance means a bare
    ``--feature api`` mutates a standalone ``{specsDir}/api/`` while an epic
    member ``{specsDir}/{epic}/api/`` of the same name is silently left behind:
    cross-feature state corruption at exit 0.

    So the write path mirrors ``epic-manifest.py resolve`` — the canonical
    resolver that produced ``{resolvedFeatureDir}`` in the first place, and which
    rejects an ambiguous name with a structured ``ambiguous:`` finding. A writer
    must not be more permissive than that resolver: more than one candidate
    carrying a state file, with no explicit ``--epic``, is a hard stop.

    Args:
        specs_dir: The configured specs directory (``--specs-dir``).
        feature: The feature name (``--feature``).
        epic: The owning epic name for a nested member, else None (``--epic``).

    Returns:
        The resolved feature directory. With ``--epic`` the nested path is taken
        verbatim; otherwise the single candidate carrying a state file, or the
        flat path when none does (the first-write case).

    Raises:
        UsageError: The bare name matches more than one directory carrying a
            state file (→ exit 2, nothing written).
    """
    if epic:
        return specs_dir / epic / feature
    flat = specs_dir / feature
    candidates = [flat] if (flat / PIPELINE_STATE_FILENAME).is_file() else []
    if specs_dir.is_dir():
        candidates.extend(
            sorted(
                p
                for p in specs_dir.glob(f"*/{feature}")
                if (p / PIPELINE_STATE_FILENAME).is_file()
            )
        )
    if len(candidates) > 1:
        listed = ", ".join(str(p) for p in candidates)
        raise UsageError(
            f"ambiguous feature {feature!r}: {len(candidates)} directories carry a "
            f"state file ({listed}) — pass --epic <epic> to name the one to write. "
            f"Refusing to guess; nothing was written."
        )
    return candidates[0] if candidates else flat


def _load_state_for_write(
    specs_dir: Path, feature: str, epic: str | None
) -> tuple[Path, dict]:
    """Resolve a feature's state path and load its current state for mutation.

    Resolves through the fail-closed `_resolve_feature_dir_for_write`, NOT the
    reader's tolerant `_resolve_feature_dir`. Deliberately does NOT
    reuse `_read_state`: that reader downgrades a *corrupt* file to ``{}`` because
    the navigator's read-only sweep can safely treat it as not-started. A writer
    that inherited it would atomically replace a corrupt-but-recoverable state
    file with a near-empty one at exit 0. So: absent -> ``{}``; present but
    unparseable -> refuse, leaving the file byte-intact.

    The verbs never create a feature directory; an unknown ``--feature`` is a
    usage error, not a silent create.

    Args:
        specs_dir: The configured specs directory (``--specs-dir``).
        feature: The feature name (``--feature``).
        epic: The owning epic name for a nested member, else None (``--epic``).

    Returns:
        A ``(state_path, state)`` tuple. ``state`` is a schema-shaped shell when
        no state file exists yet (see the seeding below).

    Raises:
        UsageError: The bare ``feature`` name is ambiguous (more than one
            candidate directory carries a state file and no ``--epic`` was
            given), the feature directory does not exist, or the state file
            exists but is not a JSON object (→ exit 2).
    """
    state_dir = _resolve_feature_dir_for_write(specs_dir, feature, epic)
    if not state_dir.is_dir():
        raise UsageError(
            f"no feature directory at {state_dir} — check --feature "
            f"(and --epic for a nested epic member)"
        )
    state_path = state_dir / PIPELINE_STATE_FILENAME
    if state_path.exists():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise UsageError(
                f"{state_path} exists but is not valid JSON ({exc}); refusing to "
                f"overwrite it. Fix or move the file, then re-run."
            ) from exc
        if not isinstance(state, dict):
            raise UsageError(
                f"{state_path} is not a JSON object; refusing to overwrite it."
            )
    else:
        state = {}

    # Seed the schema-required top-level fields for EVERY verb, not just
    # state-enter. Branch Setup fires state-branch before the entry stamp
    # (references/shared-conventions.md), so without this a first-write
    # state-branch would persist {"branch": ..., "updatedAt": ...} — missing
    # every required field — at exit 0. setdefault keeps existing state as-is.
    # (`updatedAt`, the sixth required field, is stamped by _commit_state.)
    state.setdefault("feature", feature)
    state.setdefault("createdAt", _now_iso())
    state.setdefault("pipelineStatus", "active")
    state.setdefault("stages", {})
    state.setdefault("currentStage", PRODUCTION_STAGES[0])
    return state_path, state


def _commit_state(state_path: Path, state: dict) -> dict:
    """Refresh ``updatedAt`` and write ``state`` atomically; return it for echo.

    Every verb calls this exactly once, after its mutation, so ``updatedAt`` is
    always refreshed on a successful write and the write is atomic.

    Args:
        state_path: The resolved ``.pipeline-state.json`` path.
        state: The mutated state dict.

    Returns:
        The same ``state`` dict (now carrying a fresh ``updatedAt``), so the verb
        can echo it under ``--json``.

    Raises:
        UsageError: If the atomic write fails (→ exit 2).
    """
    state["updatedAt"] = _now_iso()
    _write_state(state_path, state)
    return state


def _stage_entry(state: dict, stage: str) -> dict:
    """Return (creating if absent) the mutable ``stages.{stage}`` sub-object.

    Bootstraps ``state["stages"]`` and ``state["stages"][stage]`` when missing, so
    a verb can write into a brand-new state (``{}``), and returns the stage dict
    for in-place mutation. The bootstrap seeds ``{"status": "pending"}`` rather
    than ``{}`` because ``stageEntry`` declares ``required: ["status"]`` — an entry
    created by state-artifact (which sets only ``artifacts``) would otherwise be
    schema-invalid at exit 0.

    Args:
        state: The full state dict (mutated in place).
        stage: A stage id from ``STATE_VERB_STAGES`` (e.g. ``"forge-1-prd"``).

    Returns:
        The mutable ``stages.{stage}`` dict.
    """
    stages = state.setdefault("stages", {})
    return stages.setdefault(stage, {"status": "pending"})


# --------------------------------------------------------------------------- #
# State-write verbs
# --------------------------------------------------------------------------- #


def cmd_state_enter(feature: str, stage: str, specs_dir: Path, epic: str | None) -> dict:
    """Apply the Entry Stamp: mark ``stage`` in-progress and set ``currentStage``.

    Idempotent on re-entry within the same run: re-stamping an already
    in-progress stage simply refreshes ``startedAt``/``updatedAt``. The
    interactive resume-vs-restart decision stays the skill's — the verb never
    prompts. The write is left uncommitted; the stage's existing exit commit
    stages it later.

    Args:
        feature: Feature name.
        stage: The stage being entered (a ``STATE_VERB_STAGES`` id).
        specs_dir: Specs directory.
        epic: Owning epic name, or None.

    Returns:
        The mutated state dict (for the --json echo).

    Raises:
        UsageError: Unknown feature directory, unparseable state file, or a
            failed atomic write (→ exit 2).
    """
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    entry = _stage_entry(state, stage)
    entry["status"] = "in-progress"
    entry["startedAt"] = _now_iso()
    state["currentStage"] = stage
    return _commit_state(state_path, state)


def cmd_state_artifact(
    feature: str, stage: str, paths: list[str], specs_dir: Path, epic: str | None
) -> dict:
    """Append each path in ``paths`` to ``stages.{stage}.artifacts``, de-duplicating.

    Idempotent: an already-tracked path is a no-op (no duplicate append), so a
    resumed run that re-records files it wrote earlier does not bloat the array.
    ``updatedAt`` is refreshed even on the all-duplicates branch, keeping "state
    was touched" honest. The verb does NOT stat the file — it records the path
    the skill asserts it wrote.

    Args:
        feature: Feature name.
        stage: The producing stage id.
        paths: Artifact paths relative to the feature dir (repeatable ``--path``).
        specs_dir: Specs directory.
        epic: Owning epic name, or None.

    Returns:
        The mutated state dict (for the --json echo).

    Raises:
        UsageError: Unknown feature directory, unparseable state file, or a
            failed atomic write (→ exit 2).
    """
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    entry = _stage_entry(state, stage)
    artifacts = entry.setdefault("artifacts", [])
    for path in paths:
        if path not in artifacts:
            artifacts.append(path)
    return _commit_state(state_path, state)


def _parse_based_on(pairs: list[str]) -> dict[str, int]:
    """Parse ``--based-on STAGE=N`` tokens into a ``{stageId: int}`` map.

    Args:
        pairs: Raw ``STAGE=N`` strings from repeated ``--based-on`` flags.

    Returns:
        A ``{stageId: version}`` dict (empty when no pairs were given — the
        forge-1-prd case, which records ``basedOnVersions == {}``).

    Raises:
        UsageError: If a token lacks ``=`` or its value is not an integer
            (→ exit 2).
    """
    out: dict[str, int] = {}
    for token in pairs:
        if "=" not in token:
            raise UsageError(f"--based-on expects STAGE=N, got: {token!r}")
        stage_id, _, raw = token.partition("=")
        try:
            out[stage_id] = int(raw)
        except ValueError as exc:
            raise UsageError(f"--based-on version must be an integer: {token!r}") from exc
    return out


#: Stages the staleness cascade may mark stale (downstream authored artifacts).
#: The scope is tech..docs, matching the pre-R4 canon this cascade replaces —
#: forge-1-prd L134 named `forge-2-tech` FIRST among the stages a PRD revision
#: invalidates, and the tech spec is a PRD revision's most direct dependent.
#: forge-1-prd is never marked stale by a later completion (nothing downstream
#: feeds back into it). Keyed off this map, NOT off PRODUCTION_STAGES ordering —
#: the two are not interchangeable (a positional slice from the completing stage
#: would also break on forge-0-epic, which is a valid --stage but not a
#: PRODUCTION_STAGES member).
_CASCADE_TARGETS: Final[tuple[str, ...]] = (
    "forge-2-tech",
    "forge-3-specs",
    "forge-4-backlog",
    "forge-5-loop",
    "forge-6-docs",
)


def _cascade_staleness(state: dict, completed_stage: str, new_version: int) -> list[str]:
    """Mark downstream stages ``stale`` when they were built on an OLDER version.

    Deterministic replacement for the model-prose rule in each stage's completion
    step ("if any downstream stage has basedOnVersions referencing an older
    version, set its status to stale"). For every downstream target (tech..docs),
    if its recorded ``basedOnVersions[completed_stage]`` is an integer strictly
    less than ``new_version`` AND the stage is currently ``complete``, flip it to
    ``stale``. A downstream stage that never referenced this upstream, or already
    references the new version, is untouched. A ``pending``/``in-progress``/
    already-``stale`` downstream stage is not re-flipped — only a ``complete``
    artifact can go stale.

    Args:
        state: The full state dict (mutated in place).
        completed_stage: The stage that just completed (e.g. "forge-1-prd").
        new_version: That stage's new version.

    Returns:
        The list of stage ids newly marked stale (for the --json echo / printer).
    """
    stages = state.get("stages", {})
    newly_stale: list[str] = []
    for target in _CASCADE_TARGETS:
        if target == completed_stage:
            continue
        entry = stages.get(target)
        if not isinstance(entry, dict) or entry.get("status") != "complete":
            continue
        based_on = entry.get("basedOnVersions")
        if not isinstance(based_on, dict):
            continue
        recorded = based_on.get(completed_stage)
        if isinstance(recorded, int) and not isinstance(recorded, bool) and recorded < new_version:
            entry["status"] = "stale"
            newly_stale.append(target)
    return newly_stale


def cmd_state_complete(
    feature: str,
    stage: str,
    version: int,
    based_on: dict[str, int],
    artifacts: list[str],
    commit_hash: str | None,
    specs_dir: Path,
    epic: str | None,
    status: str | None = None,
    preserve_commit_hash: bool = False,
    resumable: bool = False,
) -> dict:
    """Mark ``stage`` complete, bump version, record provenance, cascade staleness.

    Three branches, in precedence order:

    1. ``commit_hash`` given — Commit 2 of the two-commit Git Commit Protocol.
       Sets ONLY ``commitHash``, leaving status/version/artifacts intact. Guarded
       on the stage already being ``complete``, so a typo'd ``--stage`` cannot
       write a lone ``{"commitHash": …}`` entry (which would violate
       ``stageEntry``'s ``required: ["status"]``) at exit 0.
    2. ``resumable`` — the failed-Commit-1 revert (`references/shared-conventions.md`
       L245). Records ONLY ``status = "in-progress"`` plus the ``updatedAt``
       refresh: no completedAt, no version bump, no basedOnVersions/artifacts
       write, no commitHash reset, no cascade. The frozen contract is "leave state
       as in-progress so the stage can be resumed"; stamping a completion, bumping
       the version, or cascading staleness off a commit that never landed are all
       behavioral changes.
    3. Otherwise — the completion write: status, completedAt, version,
       basedOnVersions, artifacts, ``commitHash = None`` (Commit 1) unless
       ``preserve_commit_hash``, then the downstream staleness cascade.

    Branch 2 is gated on ``resumable``, NOT on ``status == "in-progress"``:
    forge-5-loop's PARTIAL completion also passes ``--status in-progress`` but is a
    real completion-with-artifacts, so it takes branch 3 and keeps its
    completedAt/version/basedOnVersions/artifacts. Only ``status`` differs between
    ``--status complete`` and a bare ``--status in-progress``. Conflating the two
    would silently discard the ``--based-on`` item 013 passes on that call.

    Args:
        feature: Feature name.
        stage: The completing stage id.
        version: The stage's new version.
        based_on: Parsed ``{upstreamStage: version}`` provenance map.
        artifacts: Final canonical artifact path list for this stage.
        commit_hash: If given, record it as the stage's commitHash (Commit 2);
            else set commitHash to None (Commit 1).
        specs_dir: Specs directory.
        epic: Owning epic name, or None.
        status: Terminal status to record — "complete" (the default when the flag
            is absent) or "in-progress" for a partial forge-5-loop run. ``None``
            means "not passed".
        preserve_commit_hash: Skip the ``commitHash = None`` reset, for the Git
            Commit Protocol's "Nothing to commit" branch (L248).
        resumable: Failed-Commit-1 revert (L245). Record only the status; implies
            ``--status in-progress``.

    Returns:
        The mutated state dict, plus a synthetic ``_cascadedStale`` key that is
        surfaced in the --json echo / printer but NEVER written to disk.

    Raises:
        UsageError: Contradictory ``--resumable --status complete``, a
            ``--commit-hash`` follow-up against a stage that is not complete, an
            unknown feature directory, an unparseable state file, or a failed
            atomic write (→ exit 2).
    """
    if resumable and status == "complete":
        raise UsageError(
            "--resumable implies --status in-progress; do not pass --status complete"
        )
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    entry = _stage_entry(state, stage)
    cascaded: list[str] = []
    if commit_hash is not None:
        # Commit-2 follow-up: record the real hash, leave everything else intact.
        actual = entry.get("status")
        if actual != _DONE_STATUS:
            raise UsageError(
                f"--commit-hash requires {stage} to be complete (status: {actual!r}); "
                "run state-complete without --commit-hash first"
            )
        entry["commitHash"] = commit_hash
    elif resumable:
        # Failed-Commit-1 revert (L245): record ONLY the status. See the note above
        # on why this is gated on --resumable rather than on the status value.
        entry["status"] = "in-progress"
    else:
        entry["status"] = status or _DONE_STATUS   # "complete" | "in-progress" (partial)
        entry["completedAt"] = _now_iso()
        entry["version"] = version
        entry["basedOnVersions"] = based_on
        entry["artifacts"] = artifacts
        if not preserve_commit_hash:
            entry["commitHash"] = None             # Commit 1 of the Commit Protocol
        cascaded = _cascade_staleness(state, stage, version)
    result = _commit_state(state_path, state)
    # Surface the cascade result for the caller without persisting it in state:
    # _commit_state already wrote the real dict, and `echo` is a copy.
    echo = dict(result)
    echo["_cascadedStale"] = cascaded
    return echo


def cmd_state_branch(feature: str, branch: str, specs_dir: Path, epic: str | None) -> dict:
    """Set the top-level ``branch`` field.

    Records the branch resolved by Branch Setup / Branch Reconciliation. The verb
    only writes the field; the interactive prompts and the visible one-line
    reconciliation note stay unchanged skill prose.

    Branch Setup fires before the Entry Stamp, so this verb can legitimately be
    the FIRST thing to touch a feature's state file — `_load_state_for_write`'s
    field seeding is what keeps that first write schema-valid.

    Args:
        feature: Feature name.
        branch: The branch name to record.
        specs_dir: Specs directory.
        epic: Owning epic name, or None.

    Returns:
        The mutated state dict (for the --json echo).

    Raises:
        UsageError: Unknown feature directory, unparseable state file, or a
            failed atomic write (→ exit 2).
    """
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    state["branch"] = branch
    return _commit_state(state_path, state)


def cmd_state_note(feature: str, note: str, specs_dir: Path, epic: str | None) -> dict:
    """Set the top-level ``notes`` field to ``note``.

    Overwrites any existing note (the field is a single free-text string, not an
    append log — matching the schema's ``notes: string``). The skill's "offer a
    note — don't force one" statement is unchanged; this verb runs only when the
    user volunteered text.

    Args:
        feature: Feature name.
        note: The note text.
        specs_dir: Specs directory.
        epic: Owning epic name, or None.

    Returns:
        The mutated state dict (for the --json echo).

    Raises:
        UsageError: Unknown feature directory, unparseable state file, or a
            failed atomic write (→ exit 2).
    """
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    state["notes"] = note
    return _commit_state(state_path, state)


def cmd_state_decision(
    feature: str,
    question: str,
    raised_by: str,
    rationale: str | None,
    target_stage: str | None,
    specs_dir: Path,
    epic: str | None,
) -> dict:
    """Append an open deferred-decision item to ``deferredDecisions[]``.

    Emits exactly the schema keys — the array item sets
    ``additionalProperties: false``, so a convenience field is a hard validation
    failure: required ``question``/``raisedBy``/``raisedAt``/``status``, plus
    ``rationale``/``targetStage`` only when provided. ``status`` is always
    ``"open"``; the recorder never resolves a decision (the target stage flips it
    to ``"addressed"``).

    Args:
        feature: Feature name.
        question: The deferred decision, phrased for the target stage.
        raised_by: The deferring stage id.
        rationale: Optional reason for deferring.
        target_stage: Optional resolving stage id.
        specs_dir: Specs directory.
        epic: Owning epic name, or None.

    Returns:
        The mutated state dict (for the --json echo).

    Raises:
        UsageError: Unknown feature directory, unparseable state file, or a
            failed atomic write (→ exit 2).
    """
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    item: dict = {
        "question": question,
        "raisedBy": raised_by,
        "raisedAt": _now_iso(),
        "status": "open",
    }
    if rationale is not None:
        item["rationale"] = rationale
    if target_stage is not None:
        item["targetStage"] = target_stage
    state.setdefault("deferredDecisions", []).append(item)
    return _commit_state(state_path, state)


def _parse_bool(raw: str, flag: str) -> bool:
    """Parse an explicit boolean CLI value; fail closed on anything else.

    Args:
        raw: The raw flag value (e.g. from ``--blocks-current``).
        flag: The flag name, for the error message.

    Returns:
        ``True`` for ``"true"``, ``False`` for ``"false"`` (case-insensitive,
        surrounding whitespace ignored).

    Raises:
        UsageError: For any other value (→ exit 2), so a typo like ``"yes"`` is
            rejected rather than silently misrouting the stage exit.
    """
    normalized = raw.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise UsageError(f"{flag} expects true|false, got: {raw!r}")


def cmd_state_ecr(
    feature: str,
    kind: str,
    target: str,
    rationale: str,
    raised_by: str,
    blocks_current: bool,
    specs_dir: Path,
    epic: str | None,
) -> dict:
    """Append an open epic-change-request item to ``epicChangeRequests[]``.

    Emits exactly the schema keys — the array item sets
    ``additionalProperties: false``, so a convenience field is a hard validation
    failure. All six payload fields are required, and ``status`` is always
    ``"open"`` (only forge-0-epic edit mode flips it). ``blocksCurrent`` drives
    stage-exit routing, so it is a strictly-parsed boolean.

    Args:
        feature: Feature name.
        kind: One of add-feature|redep|move-boundary|split.
        target: The sibling feature to add, or the affected feature/boundary.
        rationale: Why the epic must change.
        raised_by: forge-1-prd or forge-2-tech.
        blocks_current: True → pause-now; False → finish-then-edit.
        specs_dir: Specs directory.
        epic: Owning epic name, or None.

    Returns:
        The mutated state dict (for the --json echo).

    Raises:
        UsageError: Unknown feature directory, unparseable state file, or a
            failed atomic write (→ exit 2).
    """
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    item = {
        "kind": kind,
        "target": target,
        "rationale": rationale,
        "blocksCurrent": blocks_current,
        "raisedBy": raised_by,
        "raisedAt": _now_iso(),
        "status": "open",
    }
    state.setdefault("epicChangeRequests", []).append(item)
    return _commit_state(state_path, state)


def _print_state_enter(state: dict) -> None:
    """Print the one-line human summary for `state-enter`."""
    print(f"entered {state['currentStage']} (in-progress) for {state['feature']}")


def _print_state_artifact(state: dict, stage: str, paths: list[str]) -> None:
    """Print the one-line human summary for `state-artifact`."""
    total = len(state.get("stages", {}).get(stage, {}).get("artifacts", []))
    print(f"tracked {stage} artifact(s): {', '.join(paths)} ({total} total)")


def _print_state_complete(
    state: dict, stage: str, commit_hash: str | None, resumable: bool
) -> None:
    """Print the one-line human summary for `state-complete` (one per branch)."""
    if commit_hash is not None:
        print(f"recorded {stage} commitHash: {commit_hash}")
        return
    if resumable:
        print(f"left {stage} in-progress (resumable — no completion recorded)")
        return
    entry = state.get("stages", {}).get(stage, {})
    label = (
        "completed"
        if entry.get("status") == _DONE_STATUS
        else f"partially completed ({entry.get('status')})"
    )
    recorded = entry.get("commitHash")
    cascaded = state.get("_cascadedStale") or []
    suffix = f"; marked stale: {', '.join(cascaded)}" if cascaded else ""
    print(
        f"{label} {stage} v{entry.get('version')} "
        f"(commitHash: {'null' if recorded is None else recorded}){suffix}"
    )


def _print_state_branch(state: dict) -> None:
    """Print the one-line human summary for `state-branch`."""
    print(f"recorded branch for {state['feature']}: {state['branch']}")


def _print_state_note(state: dict) -> None:
    """Print the one-line human summary for `state-note`."""
    print(f"note set for {state['feature']} ({len(state['notes'])} chars)")


def _print_state_decision(state: dict) -> None:
    """Print the one-line human summary for `state-decision` (the item appended)."""
    item = state["deferredDecisions"][-1]
    target = item.get("targetStage")
    routing = f"{item['raisedBy']} → {target}" if target else f"{item['raisedBy']}, no target stage"
    print(f"deferred decision recorded (raisedBy {routing})")


def _print_state_ecr(state: dict) -> None:
    """Print the one-line human summary for `state-ecr` (the item appended)."""
    item = state["epicChangeRequests"][-1]
    blocks = "true" if item["blocksCurrent"] else "false"
    print(
        f"epic change request recorded ({item['kind']} → {item['target']}, "
        f"blocksCurrent={blocks})"
    )


# --------------------------------------------------------------------------- #
# CLI dispatch
# --------------------------------------------------------------------------- #


def _emit(payload: dict, json_output: bool, printer: Callable[[dict], None]) -> None:
    """Emit a state-verb result: the full JSON echo on --json, else the printer.

    Args:
        payload: The verb's resulting state dict.
        json_output: The ``--json`` flag.
        printer: The verb's one-line human-readable printer.
    """
    if json_output:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        printer(payload)


def _print_rank_table(rows: list[FeatureRow], counts: dict[str, int]) -> None:
    """Print a human-readable recency-ranked feature list."""
    print(
        f"Active: {counts['active']}  "
        f"(paused: {counts['paused']}, abandoned: {counts['abandoned']})"
    )
    if not rows:
        print("  (no active feature pipelines)")
        return
    for idx, row in enumerate(rows):
        marker = "→" if idx == 0 else " "
        label = row["name"] + (f" [{row['epic']}]" if row["epic"] else "")
        nxt = row["nextCommand"] or "complete"
        print(f"  {marker} {label}: {row['currentStage']} — next: {nxt}")
        if row["verifyPending"]:
            print(f"      (verify available: {row['verifyCommand']})")


def _print_context(usage: dict) -> None:
    """Print a one-line human-readable context-usage summary."""
    if not usage.get("available"):
        print(f"context usage: unavailable ({usage.get('reason', 'unknown')})")
        return
    pct = round(usage["pct"] * 100, 1)
    flag = " — over threshold, clean session recommended" if usage["overThreshold"] else ""
    print(
        f"context: {usage['tokens']:,} / {usage['windowTokens']:,} tokens "
        f"(~{pct}%){flag}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(prog="forge-session.py", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_rank = sub.add_parser("rank-features", help="Rank active features by recency")
    p_rank.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_rank.add_argument("--config", default="./forge.config.json", help="forge.config.json path")
    p_rank.add_argument("--json", action="store_true", dest="json_output")

    p_ctx = sub.add_parser("context-usage", help="Report live context-window usage")
    p_ctx.add_argument("--config", default="./forge.config.json", help="forge.config.json path")
    p_ctx.add_argument("--window", type=int, default=None, help="Override context window size")
    p_ctx.add_argument("--threshold", type=float, default=None, help="Override warn fraction (0-1)")
    p_ctx.add_argument("--json", action="store_true", dest="json_output")

    p_doc = sub.add_parser("doctor", help="Capture pipeline ground truth for debugging")
    p_doc.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_doc.add_argument("--config", default="./forge.config.json", help="forge.config.json path")
    p_doc.add_argument("--json", action="store_true", dest="json_output")

    p_disc = sub.add_parser(
        "discover-feature", help="Find a feature's pipeline state across all branches"
    )
    p_disc.add_argument("name", nargs="?", default=None,
                        help="Feature name to discover (omit with --all)")
    p_disc.add_argument("--all", action="store_true", dest="discover_all",
                        help="Discover every feature across all branches (empty-dashboard)")
    p_disc.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_disc.add_argument("--json", action="store_true", dest="json_output")

    p_recon = sub.add_parser(
        "reconcile-branch",
        help="Decide whether a feature's recorded branch should adopt the current branch",
    )
    p_recon.add_argument("--feature", required=True, help="Feature name")
    p_recon.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_recon.add_argument("--config", default="./forge.config.json", help="forge.config.json path")
    p_recon.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_recon.add_argument("--json", action="store_true", dest="json_output")

    p_base = sub.add_parser(
        "check-epic-base",
        help="Verify HEAD contains the epic manifest for a resolved nested member",
    )
    p_base.add_argument("--feature", required=True, help="Feature name")
    p_base.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_base.add_argument("--config", default="./forge.config.json", help="forge.config.json path")
    p_base.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_base.add_argument("--json", action="store_true", dest="json_output")

    p_exit = sub.add_parser(
        "stage-exit", help="Emit the Scripted Stage Exit directives + NEXT-STEPS block"
    )
    p_exit.add_argument("--feature", required=True,
                        help="Feature name (the epic name for forge-0-epic)")
    p_exit.add_argument("--stage", required=True, choices=EXIT_STAGES,
                        help="The just-completed authoring stage")
    p_exit.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_exit.add_argument("--config", default="./forge.config.json", help="forge.config.json path")
    p_exit.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_exit.add_argument("--next-feature", default=None, dest="next_feature",
                        help="First actionable feature (epic handoff next-command arg)")
    p_exit.add_argument("--host", default="claude", choices=("claude", "generic", "pi"),
                        help="Host wording for the NEXT-STEPS block")
    p_exit.add_argument("--json", action="store_true", dest="json_output")

    p_eff = sub.add_parser(
        "effective-config",
        help="Resolve the loopRunner config from schema defaults + user overrides",
    )
    p_eff.add_argument("--config", default="./forge.config.json", help="forge.config.json path")
    p_eff.add_argument(
        "--schema", default=None,
        help="forge-config-schema.json path (default: bundled references/ copy)",
    )
    p_eff.add_argument("--json", action="store_true", dest="json_output")

    p_enter = sub.add_parser(
        "state-enter", help="Stamp a stage as in-progress (Entry Stamp)"
    )
    p_enter.add_argument("--feature", required=True, help="Feature name")
    p_enter.add_argument("--stage", required=True, choices=STATE_VERB_STAGES,
                         help="The stage being entered")
    p_enter.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_enter.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_enter.add_argument("--json", action="store_true", dest="json_output")

    p_art = sub.add_parser(
        "state-artifact", help="Append artifact paths to a stage (de-duplicating)"
    )
    p_art.add_argument("--feature", required=True, help="Feature name")
    p_art.add_argument("--stage", required=True, choices=STATE_VERB_STAGES,
                       help="The stage producing the artifact")
    p_art.add_argument("--path", required=True, action="append", dest="paths",
                       metavar="PATH",
                       help="Artifact path relative to the feature dir (repeatable)")
    p_art.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_art.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_art.add_argument("--json", action="store_true", dest="json_output")

    p_comp = sub.add_parser(
        "state-complete", help="Mark a stage complete; bump version; cascade staleness"
    )
    p_comp.add_argument("--feature", required=True, help="Feature name")
    p_comp.add_argument("--stage", required=True, choices=STATE_VERB_STAGES,
                        help="The stage being completed")
    p_comp.add_argument("--version", type=int, required=True,
                        help="This stage's new version (integer)")
    p_comp.add_argument("--based-on", action="append", default=[], dest="based_on",
                        metavar="STAGE=N",
                        help="Upstream version this artifact was built on (repeatable)")
    p_comp.add_argument("--artifact", action="append", default=[], dest="artifacts",
                        metavar="PATH",
                        help="Artifact path produced by this stage (repeatable)")
    p_comp.add_argument("--commit-hash", default=None, dest="commit_hash",
                        help="Commit 2 follow-up: record the artifact commit's hash")
    p_comp.add_argument("--status", default=None,
                        choices=("complete", "in-progress"),
                        help="Terminal status to record (default: complete). "
                             "Use in-progress for a partial forge-5-loop run -- the "
                             "stage still records completedAt/version/basedOnVersions/"
                             "artifacts; only the status differs.")
    p_comp.add_argument("--resumable", action="store_true",
                        help="Failed-Commit-1 revert (L245): record ONLY status="
                             "in-progress, leaving completedAt/version/basedOnVersions/"
                             "artifacts/commitHash untouched and firing no cascade. "
                             "Implies --status in-progress.")
    p_comp.add_argument("--preserve-commit-hash", action="store_true",
                        dest="preserve_commit_hash",
                        help="Do not reset commitHash to null on completion "
                             "(the Git Commit Protocol's 'Nothing to commit' branch)")
    p_comp.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_comp.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_comp.add_argument("--json", action="store_true", dest="json_output")

    p_br = sub.add_parser("state-branch", help="Set the top-level branch field")
    p_br.add_argument("--feature", required=True, help="Feature name")
    p_br.add_argument("--branch", required=True, help="Branch name to record")
    p_br.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_br.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_br.add_argument("--json", action="store_true", dest="json_output")

    p_note = sub.add_parser("state-note", help="Set the top-level notes field")
    p_note.add_argument("--feature", required=True, help="Feature name")
    p_note.add_argument("--note", required=True, help="Note text to persist")
    p_note.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_note.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_note.add_argument("--json", action="store_true", dest="json_output")

    p_dec = sub.add_parser(
        "state-decision", help="Append a deferred decision (status: open)"
    )
    p_dec.add_argument("--feature", required=True, help="Feature name")
    p_dec.add_argument("--question", required=True,
                       help="The deferred decision, phrased for the target stage")
    p_dec.add_argument("--raised-by", required=True, dest="raised_by",
                       choices=DECISION_RAISED_BY,
                       help="The stage deferring the decision")
    p_dec.add_argument("--rationale", default=None, help="Why it is deferred (optional)")
    p_dec.add_argument("--target-stage", default=None, dest="target_stage",
                       choices=DECISION_TARGET_STAGES,
                       help="The stage that should resolve it (optional)")
    p_dec.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_dec.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_dec.add_argument("--json", action="store_true", dest="json_output")

    p_ecr = sub.add_parser(
        "state-ecr", help="Append an epic change request (status: open)"
    )
    p_ecr.add_argument("--feature", required=True, help="Feature name")
    p_ecr.add_argument("--kind", required=True, choices=ECR_KINDS,
                       help="The decomposition change kind")
    p_ecr.add_argument("--target", required=True,
                       help="The sibling feature to add, or the feature/boundary affected")
    p_ecr.add_argument("--rationale", required=True, help="Why the epic must change")
    p_ecr.add_argument("--raised-by", required=True, dest="raised_by",
                       choices=ECR_RAISED_BY,
                       help="The stage that detected the epic-level concern")
    p_ecr.add_argument("--blocks-current", required=True, dest="blocks_current",
                       metavar="true|false",
                       help="true → pause-now (reconcile before proceeding); "
                            "false → finish-then-edit")
    p_ecr.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_ecr.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_ecr.add_argument("--json", action="store_true", dest="json_output")

    args = parser.parse_args()

    try:
        if args.cmd == "rank-features":
            specs_dir = Path(args.specs_dir)
            config = _load_config(Path(args.config))
            rows = build_rows(specs_dir, config)
            counts = _counts(specs_dir)
            invalid_keys = invalid_auto_verify_keys(config)
            if args.json_output:
                payload = {"active": rows, "counts": counts}
                if invalid_keys:
                    payload["invalidAutoVerifyKeys"] = invalid_keys
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                _print_rank_table(rows, counts)
                if invalid_keys:
                    print(
                        "  ! invalid autoVerifyStages keys (ignored): "
                        + ", ".join(invalid_keys)
                    )
            return 0

        if args.cmd == "context-usage":
            usage = context_usage(Path(args.config), args.window, args.threshold)
            if args.json_output:
                print(json.dumps(usage, indent=2, ensure_ascii=False))
            else:
                _print_context(usage)
            return 0

        if args.cmd == "doctor":
            report = doctor_report(Path(args.specs_dir), Path(args.config))
            if args.json_output:
                print(json.dumps(report, indent=2, ensure_ascii=False))
            else:
                _print_doctor(report)
            return 0

        if args.cmd == "discover-feature":
            if args.discover_all:
                payload = discover_all(args.specs_dir)
                printer = _print_discover_all
            elif args.name:
                payload = discover_feature(args.name, args.specs_dir)
                printer = _print_discover
            else:
                parser.error("discover-feature requires a NAME or --all")
            if args.json_output:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                printer(payload)
            return 0

        if args.cmd == "reconcile-branch":
            payload = reconcile_branch(
                args.feature, Path(args.specs_dir), Path(args.config), args.epic
            )
            if args.json_output:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                _print_reconcile(payload)
            return 0

        if args.cmd == "check-epic-base":
            payload = check_epic_base(
                args.feature, Path(args.specs_dir), Path(args.config), args.epic
            )
            if args.json_output:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                _print_check_epic_base(payload)
            return 0

        if args.cmd == "stage-exit":
            payload = stage_exit(
                args.feature,
                args.stage,
                Path(args.specs_dir),
                Path(args.config),
                args.epic,
                args.host,
                args.next_feature,
            )
            if args.json_output:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                _print_stage_exit(payload)
            return 0

        if args.cmd == "effective-config":
            schema_path = Path(args.schema) if args.schema else _default_schema_path()
            resolved = resolve_loop_runner(Path(args.config), schema_path)
            if args.json_output:
                print(json.dumps(resolved, indent=2, ensure_ascii=False))
            else:
                _print_effective_config(resolved)
            return 0

        if args.cmd == "state-enter":
            payload = cmd_state_enter(
                args.feature, args.stage, Path(args.specs_dir), args.epic
            )
            _emit(payload, args.json_output, _print_state_enter)
            return 0

        if args.cmd == "state-artifact":
            payload = cmd_state_artifact(
                args.feature, args.stage, args.paths, Path(args.specs_dir), args.epic
            )
            _emit(
                payload,
                args.json_output,
                lambda state: _print_state_artifact(state, args.stage, args.paths),
            )
            return 0

        if args.cmd == "state-complete":
            payload = cmd_state_complete(
                args.feature,
                args.stage,
                args.version,
                _parse_based_on(args.based_on),
                args.artifacts,
                args.commit_hash,
                Path(args.specs_dir),
                args.epic,
                status=args.status,
                preserve_commit_hash=args.preserve_commit_hash,
                resumable=args.resumable,
            )
            _emit(
                payload,
                args.json_output,
                lambda state: _print_state_complete(
                    state, args.stage, args.commit_hash, args.resumable
                ),
            )
            return 0

        if args.cmd == "state-branch":
            payload = cmd_state_branch(
                args.feature, args.branch, Path(args.specs_dir), args.epic
            )
            _emit(payload, args.json_output, _print_state_branch)
            return 0

        if args.cmd == "state-note":
            payload = cmd_state_note(
                args.feature, args.note, Path(args.specs_dir), args.epic
            )
            _emit(payload, args.json_output, _print_state_note)
            return 0

        if args.cmd == "state-decision":
            payload = cmd_state_decision(
                args.feature,
                args.question,
                args.raised_by,
                args.rationale,
                args.target_stage,
                Path(args.specs_dir),
                args.epic,
            )
            _emit(payload, args.json_output, _print_state_decision)
            return 0

        if args.cmd == "state-ecr":
            payload = cmd_state_ecr(
                args.feature,
                args.kind,
                args.target,
                args.rationale,
                args.raised_by,
                _parse_bool(args.blocks_current, "--blocks-current"),
                Path(args.specs_dir),
                args.epic,
            )
            _emit(payload, args.json_output, _print_state_ecr)
            return 0

        raise UsageError(f"unknown command: {args.cmd}")
    except UsageError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
