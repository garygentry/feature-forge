"""Argument parsing and command dispatch for the forge-session CLI (#279 P4.1).

``main()`` is the single entry point the hyphen-named shim ``scripts/forge-session.py``
calls. Every verb's business logic lives in a sibling package module
(``discover``/``doctor``/``outcomes``/``state``/``exit``/``routes``/``decisions``/
``topology``); this module owns only the argparse construction, the per-verb dispatch,
the ``rank-features``/``context-usage``/``effective-config`` verbs (the small read-only
reporters that never earned their own module), and the shared ``_emit`` helper.

All verb names, flags, exit codes, and JSON shapes are frozen — this module is a pure
relocation of the dispatch that used to live in the shim body.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Final, NoReturn, get_args

from forge_session._common import (
    ExitOwner,
    FeatureRow,
    PRODUCTION_STAGES,
    UsageError,
    VERIFY_MODE_TO_STAGE,
    VERIFY_RESULT_STATUSES,
    VERIFY_STAGES,
    VERIFY_TOKEN_BY_STAGE,
    VerifyCapability,
    EXIT_HOSTS,
    EXIT_STAGES,
    _counts,
    _default_schema_path,
    _load_config,
    build_rows,
    invalid_auto_verify_keys,
    resolve_loop_runner,
)
from forge_session.decisions import (
    _default_actor,
    _print_decision_apply,
    _print_decision_list,
    _print_decision_record,
    cmd_decision_apply,
    cmd_decision_list,
    cmd_decision_record,
)
from forge_session.discover import (
    _print_check_epic_base,
    _print_discover,
    _print_discover_all,
    _print_reconcile,
    check_epic_base,
    discover_all,
    discover_feature,
    reconcile_branch,
)
from forge_session.doctor import (
    DOCTOR_CHECK_IDS,
    _print_doctor,
    doctor_report,
)
from forge_session.exit import (
    _EXIT_PRODUCTION_STAGES,
    _print_stage_exit,
    stage_exit,
)
from forge_session.outcomes import (
    select_outcome,
    verify_state_for_stage,
)
from forge_session.state import (
    _parse_based_on,
    _parse_bool,
    _print_state_artifact,
    _print_state_branch,
    _print_state_complete,
    _print_state_decision,
    _print_state_ecr,
    _print_state_enter,
    _print_state_note,
    _print_state_skip,
    _print_state_verify,
    cmd_state_artifact,
    cmd_state_branch,
    cmd_state_complete,
    cmd_state_decision,
    cmd_state_ecr,
    cmd_state_enter,
    cmd_state_note,
    cmd_state_skip,
    cmd_state_verify,
)
from forge_session.topology import (
    _load_topology_items,
    _print_topology,
    cmd_backlog_topology,
)


# --------------------------------------------------------------------------- #
# CLI-only argparse-choice domains
#
# These enumerations exist ONLY to constrain a flag's `choices`; no package module
# imports them (they are referenced only in main()'s argparse), so they live here
# beside the parser that uses them rather than in the shared _common layer.
# --------------------------------------------------------------------------- #

#: The --stage domain for the state-write verbs: the six PRODUCTION_STAGES (order-
#: sensitive) plus forge-0-epic, which also carries a stageEntry but is excluded from
#: the next-stage walk.
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


# --------------------------------------------------------------------------- #
# Context-window usage (the `context-usage` verb)
# --------------------------------------------------------------------------- #

#: Default context window when the model can't be inferred and config is silent.
_DEFAULT_WINDOW: Final = 200_000
#: Window for 1M-context models (model id carries a `[1m]` / `-1m` marker).
_WIDE_WINDOW: Final = 1_000_000
#: Default fraction of the window past which a clean session is recommended.
_DEFAULT_THRESHOLD: Final = 0.7


def _config_value(config_path: Path, key: str):
    """Read a single key from forge.config.json, or None if absent/unreadable."""
    return _load_config(config_path).get(key)


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
            # Owed automatic verification is an obligation, not an offer — the
            # full diagnostic sentence went to stderr, so keep this line honest
            # rather than repeating it (REQ-DEBT-02).
            offer = (
                "automatic verification owed"
                if row["verifyState"] == "auto-pending"
                else "verify available"
            )
            print(f"      ({offer}: {row['verifyCommand']})")


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


def _print_effective_config(resolved: dict[str, object]) -> None:
    """Print the resolved loopRunner config as an aligned key: value table.

    Args:
        resolved: The resolved loopRunner object from ``resolve_loop_runner``.
    """
    print("Effective loopRunner config:")
    width = max((len(k) for k in resolved), default=0)
    for key in sorted(resolved):
        print(f"  {key.ljust(width)} : {resolved[key]!r}")


class _ErrorPrefixParser(argparse.ArgumentParser):
    """An argparse parser whose failures use this CLI's ``Error: ...`` exit-2 form.

    ``stage-exit`` carries two contracts that argparse cannot satisfy together out
    of the box: its enum flags MUST be registered with typed ``choices`` drawn from
    the shared literal domains, AND any invalid input must print
    ``Error: <actionable message>`` to stderr and return exit 2 with no payload and
    no sentinel. Stock argparse leads with ``usage:``, so the reconciliation lives
    here rather than in a hand-rolled second validation pass that would drift from
    the ``choices`` it duplicates.

    ``parse_args`` runs before ``main``'s ``UsageError`` handler, so this exits
    directly instead of raising. ``add_subparsers`` defaults ``parser_class`` to
    ``type(self)``, so every subcommand inherits the same form — matching the
    ``UsageError`` path they already share.
    """

    def error(self, message: str) -> NoReturn:  # noqa: D102 - argparse override
        self.exit(2, f"Error: {message}\nTry '{self.prog} --help' for usage.\n")


def main() -> int:
    parser = _ErrorPrefixParser(prog="forge-session.py", description=__doc__)
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
    p_doc.add_argument(
        "--schema", default=None,
        help="Override the bundled forge-config-schema.json (chiefly for tests)",
    )
    p_doc.add_argument(
        "--check", action="append", dest="checks", metavar="ID", choices=DOCTOR_CHECK_IDS,
        help="Run only this check (repeatable); legacy fields are always reported",
    )
    p_doc.add_argument(
        "--verbose", action="store_true",
        help="Also print the ok/na check lines in the human report",
    )
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
                        help="The just-completed stage (or branch skill)")
    p_exit.add_argument("--served-stage", default=None, dest="served_stage",
                        choices=_EXIT_PRODUCTION_STAGES,
                        help="Production stage a verify/fix diversion served")
    p_exit.add_argument("--verify-mode", default=None, dest="verify_mode",
                        choices=tuple(VERIFY_MODE_TO_STAGE),
                        help="Verify mode; maps to --served-stage when unique")
    # No argparse `choices`: the accepted outcome domain differs per stage, which
    # argparse cannot express. `stage_exit` validates it against EXIT_OUTCOMES.
    p_exit.add_argument("--outcome", default=None,
                        help="Stage-specific outcome (loop/docs/verify/fix only)")
    p_exit.add_argument(
        "--cause", default=None, dest="cause", choices=("dependency-starvation",),
        help="Pending-attribution cause; valid only with "
             "--stage forge-5-loop --outcome partial",
    )
    p_exit.add_argument("--owner", default=None, choices=get_args(ExitOwner),
                        help="Branch terminal ownership (forge-verify/forge-fix only)")
    p_exit.add_argument("--verify-capability", default="manual",
                        dest="verify_capability", choices=get_args(VerifyCapability),
                        help="interactive only with BOTH a question mechanism and "
                             "permitted clean-room verifier dispatch")
    p_exit.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_exit.add_argument("--config", default="./forge.config.json", help="forge.config.json path")
    p_exit.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_exit.add_argument("--next-feature", default=None, dest="next_feature",
                        help="First actionable feature (epic handoff next-command arg)")
    p_exit.add_argument("--host", default="claude", choices=EXIT_HOSTS,
                        help="Host wording for the NEXT-STEPS block")
    p_exit.add_argument("--json", action="store_true", dest="json_output")

    p_sel = sub.add_parser(
        "select-outcome",
        help="Derive the deterministic stage-exit --outcome for a verify/fix run",
    )
    p_sel.add_argument("--feature", required=True, help="Feature name")
    p_sel.add_argument("--served-stage", required=True, dest="served_stage",
                       choices=tuple(VERIFY_TOKEN_BY_STAGE),
                       help="Production stage the verify/fix run served")
    p_sel.add_argument("--skill", required=True, choices=("verify", "fix"),
                       help="Which branch skill is choosing its exit outcome")
    p_sel.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_sel.add_argument("--epic", default=None, help="Epic name for a nested member")
    # Runtime signals for the outcomes disk cannot record (see references/select-outcome.md).
    p_sel.add_argument("--op-failure", action="store_true", dest="op_failure",
                       help="a dispatch/step/validation/commit/state-write failed → failed")
    p_sel.add_argument("--user-deferred", action="store_true", dest="user_deferred",
                       help="fix only: user explicitly deferred the fix/re-verify → deferred")
    p_sel.add_argument("--decisions-open", action="store_true", dest="decisions_open",
                       help="fix only: unresolved user decisions block fixes → decisions")
    p_sel.add_argument("--json", action="store_true", dest="json_output")

    p_vst = sub.add_parser(
        "verify-state",
        help="Classify a served stage's verification into one VerifyStateCase",
    )
    p_vst.add_argument("--feature", required=True, help="Feature name")
    p_vst.add_argument("--for-stage", required=True, dest="for_stage",
                       choices=tuple(VERIFY_TOKEN_BY_STAGE),
                       help="Production stage whose forge-verify-* entry to classify")
    p_vst.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_vst.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_vst.add_argument("--json", action="store_true", dest="json_output")

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

    p_skip = sub.add_parser(
        "state-skip", help="Record forge-6-docs as deliberately skipped (#197)"
    )
    p_skip.add_argument("--feature", required=True, help="Feature name")
    p_skip.add_argument("--stage", required=True, choices=("forge-6-docs",),
                        help="The stage being skipped (only forge-6-docs is skippable)")
    p_skip.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_skip.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_skip.add_argument("--json", action="store_true", dest="json_output")

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

    p_ver = sub.add_parser(
        "state-verify", help="Write one forge-verify-* transition (result or provenance)"
    )
    p_ver.add_argument("--feature", required=True,
                       help="Feature name (the EPIC name for --stage forge-0-epic)")
    p_ver.add_argument("--stage", required=True, choices=VERIFY_STAGES,
                       help="The production stage this verify entry serves "
                            "(forge-6-docs has no verification token)")
    p_ver.add_argument("--status", default=None, choices=VERIFY_RESULT_STATUSES,
                       help="Result mode: the transition to record "
                            "(mutually exclusive with --commit-hash)")
    p_ver.add_argument("--findings-file", default=None, dest="findings_file",
                       metavar="PATH",
                       help="Findings document, relative to and contained by the "
                            "feature directory (required by findings-reported)")
    p_ver.add_argument("--findings-count", type=int, default=None,
                       dest="findings_count", metavar="N",
                       help="Number of findings in --findings-file (0 is meaningful)")
    p_ver.add_argument("--verified-stage-version", type=int, default=None,
                       dest="verified_stage_version", metavar="N",
                       help="The served stage's current version, for the freshness "
                            "ledger (rejected by findings-applied)")
    p_ver.add_argument("--commit-hash", default=None, dest="commit_hash",
                       help="Commit-2 provenance mode: the full 40-hex Commit-1 hash")
    p_ver.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_ver.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_ver.add_argument("--json", action="store_true", dest="json_output")

    p_drec = sub.add_parser(
        "decision-record", help="Append a needs-human decision entry (append-only)"
    )
    p_drec.add_argument("--backlog-dir", required=True, dest="backlog_dir",
                        help="Resolved backlog directory (e.g. specs/loop-recovery)")
    p_drec.add_argument("--item", required=True, action="append", dest="item_ids",
                        metavar="ID", help="Backlog item id (repeatable — one entry per id)")
    p_drec.add_argument("--question", required=True, help="The needs-human question text")
    _ans = p_drec.add_mutually_exclusive_group(required=True)
    _ans.add_argument("--answer", default=None, help="The operator's answer")
    _ans.add_argument("--deferred", action="store_true",
                      help="Record a deferral / cancel-early (answer: null)")
    p_drec.add_argument("--cluster", default=None, dest="cluster_id", metavar="CID",
                        help="Shared clusterId for one consolidated decision (REQ-CLU-04)")
    p_drec.add_argument("--actor", default=None,
                        help="Session/actor label for recordedBy (default forge-5-loop@<host>)")
    p_drec.add_argument("--state-dir", default=None, dest="state_dir",
                        help="State-dir name (default: effective loopRunner.stateDir)")
    p_drec.add_argument("--config", default="./forge.config.json",
                        help="forge.config.json path")
    p_drec.add_argument("--json", action="store_true", dest="json_output")

    p_dlist = sub.add_parser(
        "decision-list", help="Read the decision record (or the unapplied set)"
    )
    p_dlist.add_argument("--backlog-dir", required=True, dest="backlog_dir",
                         help="Resolved backlog directory")
    p_dlist.add_argument("--unapplied", action="store_true",
                         help="Return only the latest-unapplied-per-item set (REQ-DEC-05)")
    p_dlist.add_argument("--state-dir", default=None, dest="state_dir",
                         help="State-dir name (default: effective loopRunner.stateDir)")
    p_dlist.add_argument("--config", default="./forge.config.json",
                         help="forge.config.json path")
    p_dlist.add_argument("--json", action="store_true", dest="json_output")

    p_dapply = sub.add_parser(
        "decision-apply", help="Mark the latest decision for an item applied"
    )
    p_dapply.add_argument("--backlog-dir", required=True, dest="backlog_dir",
                          help="Resolved backlog directory")
    p_dapply.add_argument("--item", required=True, dest="item_id", metavar="ID",
                          help="Backlog item whose latest decision to stamp applied")
    p_dapply.add_argument("--actor", default=None,
                          help="Session/actor label for appliedBy (default forge-5-loop@<host>)")
    p_dapply.add_argument("--state-dir", default=None, dest="state_dir",
                          help="State-dir name (default: effective loopRunner.stateDir)")
    p_dapply.add_argument("--config", default="./forge.config.json",
                          help="forge.config.json path")
    p_dapply.add_argument("--json", action="store_true", dest="json_output")

    p_topo = sub.add_parser(
        "backlog-topology",
        help="Dependency-topology metrics + advisory warnings over a runner item array",
    )
    topo_src = p_topo.add_mutually_exclusive_group(required=True)
    topo_src.add_argument(
        "--items-json", help="Path to the loopRunner listCommand JSON output"
    )
    topo_src.add_argument(
        "--items-stdin", action="store_true",
        help="Read the listCommand JSON from stdin",
    )
    p_topo.add_argument(
        "--cluster", action="store_true", dest="with_clusters",
        help="Append blocked-item clusters for consolidated prompts",
    )
    p_topo.add_argument("--json", action="store_true", dest="json_output")

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
            # Check details carry non-ASCII (em dash, ellipsis); a terminal whose
            # encoding cannot represent them must not turn the diagnostic into a
            # traceback (INV-3). Only the doctor path reconfigures.
            reconfigure = getattr(sys.stdout, "reconfigure", None)
            if reconfigure is not None:
                try:
                    reconfigure(errors="backslashreplace")
                except (ValueError, OSError):
                    pass
            report = doctor_report(
                Path(args.specs_dir),
                Path(args.config),
                schema_path=Path(args.schema) if args.schema else None,
                only=frozenset(args.checks) if args.checks else None,
            )
            if args.json_output:
                print(json.dumps(report, indent=2, ensure_ascii=False))
            else:
                _print_doctor(report, verbose=args.verbose or bool(args.checks))
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
                args.served_stage,
                args.verify_mode,
                args.outcome,
                args.owner,
                args.verify_capability,
                args.cause,
            )
            if args.json_output:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                _print_stage_exit(payload)
            return 0

        if args.cmd == "select-outcome":
            payload = select_outcome(
                args.feature,
                args.served_stage,
                args.skill,
                Path(args.specs_dir),
                args.epic,
                op_failure=args.op_failure,
                user_deferred=args.user_deferred,
                decisions_open=args.decisions_open,
            )
            if args.json_output:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                print(f"{payload['outcome']}: {payload['reason']}")
                for line in payload["evidence"]:
                    print(f"  - {line}")
            return 0

        if args.cmd == "verify-state":
            payload = verify_state_for_stage(
                args.feature,
                args.for_stage,
                Path(args.specs_dir),
                args.epic,
            )
            if args.json_output:
                print(json.dumps(payload, indent=2, ensure_ascii=False))
            else:
                flags = []
                if payload["verified"]:
                    flags.append("verified")
                if payload["stale"]:
                    flags.append("stale")
                suffix = f" [{', '.join(flags)}]" if flags else ""
                print(f"{payload['case']}{suffix}: {payload['message']}")
                if payload["nextCommand"]:
                    print(f"  next: {payload['nextCommand']}")
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

        if args.cmd == "state-skip":
            payload = cmd_state_skip(
                args.feature, args.stage, Path(args.specs_dir), args.epic
            )
            _emit(
                payload,
                args.json_output,
                lambda state: _print_state_skip(state, args.stage),
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

        if args.cmd == "state-verify":
            payload = cmd_state_verify(
                args.feature,
                args.stage,
                Path(args.specs_dir),
                args.epic,
                status=args.status,
                findings_file=args.findings_file,
                findings_count=args.findings_count,
                verified_stage_version=args.verified_stage_version,
                commit_hash=args.commit_hash,
            )
            _emit(
                payload,
                args.json_output,
                lambda result: _print_state_verify(result, args.commit_hash),
            )
            return 0

        if args.cmd == "decision-record":
            payload = cmd_decision_record(
                Path(args.backlog_dir),
                args.item_ids,
                args.question,
                args.answer,
                args.deferred,
                args.cluster_id,
                args.actor or _default_actor(),
                args.state_dir,
                Path(args.config),
                _default_schema_path(),
            )
            _emit(payload, args.json_output, _print_decision_record)
            return 0

        if args.cmd == "decision-list":
            payload = cmd_decision_list(
                Path(args.backlog_dir), args.unapplied, args.state_dir,
                Path(args.config), _default_schema_path(),
            )
            _emit(payload, args.json_output, _print_decision_list)
            return 0

        if args.cmd == "decision-apply":
            payload = cmd_decision_apply(
                Path(args.backlog_dir), args.item_id, args.actor or _default_actor(),
                args.state_dir, Path(args.config), _default_schema_path(),
            )
            _emit(payload, args.json_output, _print_decision_apply)
            return 0

        if args.cmd == "backlog-topology":
            items = _load_topology_items(args)
            payload = cmd_backlog_topology(items, with_clusters=args.with_clusters)
            _emit(payload, args.json_output, _print_topology)
            return 0

        raise UsageError(f"unknown command: {args.cmd}")
    except UsageError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
