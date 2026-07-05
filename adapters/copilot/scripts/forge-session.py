#!/usr/bin/env python3
"""Session-aware navigation helpers for the feature-forge pipeline navigator.

Two read-only subcommands that drive the usability features of the `/forge`
root navigator:

    python3 forge-session.py rank-features [--specs-dir DIR] [--json]
    python3 forge-session.py context-usage [--config FILE] [--window N] \
        [--threshold F] [--json]

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

3.10 baseline, Google-style docstrings, full type annotations, stdlib only —
matching the conventions of `scripts/epic-manifest.py`.

Exit codes:
    0 = ok (including an empty feature list or unavailable context usage)
    2 = usage error or unreadable I/O
"""

from __future__ import annotations

import argparse
import json
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
#: Verify statuses that count as "resolved" (no outstanding verify needed).
_VERIFY_RESOLVED: Final = frozenset({"passed", "findings-applied", "skipped"})

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
            "currentStage": state.get("currentStage") or (nxt or "complete"),
            "branch": branch if isinstance(branch, str) else None,
            "updatedAt": updated if isinstance(updated, str) else None,
            "complete": nxt is None,
            "nextStage": nxt,
            "nextCommand": f"/feature-forge:{nxt} {name}" if nxt else None,
            "verifyPending": verify_pending,
            "verifyCommand": f"/feature-forge:forge-verify {name}" if verify_pending else None,
            "verifyStage": vstage,
            "verifyState": vlabel,
            "autoVerify": effective_auto_verify,
            "autoFix": global_auto_fix and effective_auto_verify,
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
        total = (
            int(usage.get("input_tokens", 0) or 0)
            + int(usage.get("cache_creation_input_tokens", 0) or 0)
            + int(usage.get("cache_read_input_tokens", 0) or 0)
            + int(usage.get("output_tokens", 0) or 0)
        )
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

        raise UsageError(f"unknown command: {args.cmd}")
    except UsageError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
