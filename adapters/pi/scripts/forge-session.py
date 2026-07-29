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
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, TypedDict


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
# CLI dispatch
# --------------------------------------------------------------------------- #


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

        raise UsageError(f"unknown command: {args.cmd}")
    except UsageError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
