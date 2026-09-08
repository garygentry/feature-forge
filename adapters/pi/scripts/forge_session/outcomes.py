"""Deterministic verify/fix outcome + upstream-verification-state selection.

The ``select-outcome`` and ``verify-state`` verbs (#265 P3.1/P3.2, shipped by
#276/#277) live here, carved out of the ``forge-session.py`` monolith (#279 P4.1).
Both replace model judgment over conversational state with a derivation from the
authoritative on-disk record — the served stage's ``forge-verify-*`` entry and, for
``select-outcome``, the latest ``.verification/VERIFY-*.md`` report and its
``## Fix Progress`` sweep dispositions. Their flags, the outcome/case enums, exit
codes, and JSON shapes are FROZEN; the parity tests in ``tests/test_select_outcome.py``
and ``tests/test_verify_state.py`` pin the enums to ``references/select-outcome.md``
and ``references/verify-state.md``.

This is a pure move: shared readers and tables come from ``_common`` (never from the
shim, which would be circular); the shim re-exports every symbol below so the
path-loaded test oracle resolves it unchanged.

3.10 baseline, Google-style docstrings, stdlib only — matching the conventions of
the monolith it was carved out of.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Final, NamedTuple

from forge_session._common import (
    KNOWN_VERIFY_STATUSES,
    PIPELINE_STATE_FILENAME,
    VERIFY_STATE_MESSAGES,
    VERIFY_TOKEN_BY_STAGE,
    UsageError,
    _EXIT_VERIFY_TOKEN,
    _read_state,
    _resolve_feature_dir,
    _scheduled_stage_version,
    _stage_version,
    _VERIFY_RESOLVED,
    _verify_entry,
    _warn_auto_verify_debt_metadata,
    _warn_unknown_verify_status,
    auto_pending_message,
)


def _classify_verify_entry(entry: dict, verify_key: str, current: int | None) -> str:
    """Label one ``forge-verify-*`` entry against the artifact revision it serves.

    The revision-agnostic half of ``_verify_state_for``, factored out because an
    EPIC-scoped exit compares against the epic manifest's ``revision`` held in
    ``.epic-state.json``, not against a member production-stage ``version``
    (REQ-SEC-01). Both callers must apply identical rules, so there is
    one implementation rather than two that can drift.

    Args:
        entry: The verify entry (``{}`` when absent).
        verify_key: The ``forge-verify-*`` key, named in the metadata diagnostic.
        current: The artifact's current revision, or None when it is unknown.

    Returns:
        One of fresh / stale / failing / auto-pending / never / skipped.
    """
    status = entry.get("status")
    if status is not None and not isinstance(status, str):
        # Same guard as `verify_state`: an unhashable status from a torn or
        # hand-edited entry must classify, not raise at the frozenset
        # membership below — this label is read while closing a stage.
        return "never"
    if status == "skipped":
        return "skipped"
    if status == "findings-reported":
        return "failing"
    if status == "auto-verify-pending":
        # Ahead of the generic unresolved branch, exactly as in verify_state.
        if _scheduled_stage_version(entry) is None:
            _warn_auto_verify_debt_metadata(verify_key)
        return "auto-pending"
    if status not in _VERIFY_RESOLVED:
        return "never"
    if status == "findings-applied":
        # §4.2 step 4: applying fixes CLEARS freshness; only a later `passed` restores
        # it. The writer omits `verifiedStageVersion` on this status, but REQ-DEBT-06
        # requires loading legacy state without migration, so a pre-writer entry can
        # still carry the key — and would otherwise read `fresh` here. Mirrors the
        # identical guard in `verify_state` (§5.1).
        return "stale"
    verified_version = entry.get("verifiedStageVersion")
    if (
        isinstance(verified_version, int)
        and current is not None
        and verified_version == current
    ):
        return "fresh"
    return "stale"


def _verify_state_for(state: dict, stage: str) -> str:
    """Classify THIS stage's verify freshness (stage-scoped ``verify_state``).

    Same labels as ``verify_state`` — fresh / stale / failing / auto-pending /
    never / skipped / none — but for the given stage rather than the
    most-recently completed one, because stage-exit runs inside the stage that
    just closed. ``auto-pending`` is classified identically here so stage-exit
    routing and the navigator ledger never disagree about owed debt (REQ-DEBT-05).
    """
    token = _EXIT_VERIFY_TOKEN.get(stage)
    if token is None:
        return "none"
    return _classify_verify_entry(
        _verify_entry(state, f"forge-verify-{token}"),
        f"forge-verify-{token}",
        _stage_version(state, stage),
    )


# --------------------------------------------------------------------------- #
# select-outcome — deterministic exit-outcome selection (forge-verify/forge-fix)
# --------------------------------------------------------------------------- #
#
# forge-verify and forge-fix each close a run by choosing ONE `stage-exit
# --outcome` value. That selection used to be model judgment over conversational
# state; this verb derives it from the authoritative on-disk record instead — the
# served stage's `forge-verify-*` entry (written mechanically by `state-verify`),
# the latest `.verification/VERIFY-*.md` report, and its `## Fix Progress` sweep
# dispositions — the same "never eyeball the graph" move `rank-features` makes for
# `verifyGate`. The full contract is `references/select-outcome.md`.
#
# The outcome vocabularies are NOT re-listed here: they are `VerifyOutcome` and
# `FixOutcome` (via EXIT_OUTCOMES), and `test_select_outcome.py`'s parity guard
# pins those aliases to the forge-verify/forge-fix skill-body outcome tables.
#
# Three outcomes cannot be read off disk, because the fact that distinguishes each
# is runtime-only: an operational failure leaves NO state write (so disk shows the
# prior state), and an explicit user deferral is byte-identical on disk to a
# nested/manual `applied`. The caller asserts those with a signal flag
# (`--op-failure`, `--user-deferred`, `--decisions-open`); every other outcome is
# pure disk derivation.

#: `VERIFY-{mode}-{YYYY-MM-DD}.md`, or `-round{N}.md` for a same-day re-run (N>=2).
#: The un-suffixed base file is round 1. Naming is owned by
#: `skills/forge-verify/references/findings-template.md` § Findings Document Template.
_VERIFY_REPORT_RE: Final = re.compile(
    r"^VERIFY-(?P<mode>[a-z]+)-(?P<date>\d{4}-\d{2}-\d{2})"
    r"(?:-round(?P<round>\d+))?\.md$"
)

#: A `- **Severity:** {value}` line under `## Findings`. Blocking = error + gap.
_SEVERITY_LINE_RE: Final = re.compile(
    r"^-\s*\*\*Severity:\*\*\s*([A-Za-z-]+)", re.MULTILINE
)


class _VerifyReport(NamedTuple):
    """One findings report on disk, ordered by (date, round)."""

    path: Path
    date: str
    round: int


class _ReportFacts(NamedTuple):
    """The machine-readable facts a findings report carries.

    Blocking-finding tallies come from the `## Findings` severities (ground truth),
    never from the human-written `## Summary` line. The fix-side fields read the
    `## Fix Progress` section the fix pass appends — its `[APPLIED]` steps and the
    sweep dispositions (`FIXED`/`JUSTIFIED`/`FALSE-POSITIVE`).
    """

    total: int
    errors: int
    gaps: int
    blocking: int
    has_fix_progress: bool
    applied_steps: int
    fixed: int
    justified: int
    false_positive: int


def _read_report_text(path: Path) -> str:
    """Read a findings report as UTF-8, downgrading an unreadable file to ``""``."""
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _verify_reports(feature_dir: Path, mode: str) -> list[_VerifyReport]:
    """Every ``VERIFY-{mode}-*.md`` report in ``.verification/``, oldest first.

    The last element is therefore the newest round of the newest day — the report a
    consumer means by "the latest". A tie on date breaks by round.
    """
    vdir = feature_dir / ".verification"
    if not vdir.is_dir():
        return []
    reports: list[_VerifyReport] = []
    for entry in vdir.iterdir():
        if not entry.is_file():
            continue
        match = _VERIFY_REPORT_RE.match(entry.name)
        if match is None or match.group("mode") != mode:
            continue
        rnd = int(match.group("round")) if match.group("round") else 1
        reports.append(_VerifyReport(entry, match.group("date"), rnd))
    # (date, round) is the ordering key; the filename tiebreaks so the sort is total
    # even for the pathological `…-round1.md` alias of the un-suffixed base file.
    reports.sort(key=lambda r: (r.date, r.round, r.path.name))
    return reports


def _section_body(text: str, title: str) -> str:
    """Return the body of the ``## {title}`` section, up to the next ``## `` heading.

    Level-3 (``### ``) finding subsections stay inside their level-2 section, so a
    ``## Findings`` body keeps every ``### V-NNN`` block. Returns ``""`` when the
    heading is absent.
    """
    body: list[str] = []
    capturing = False
    for line in text.splitlines():
        if line.startswith("## "):
            if capturing:
                break
            capturing = line[3:].strip().lower() == title.lower()
            continue
        if capturing:
            body.append(line)
    return "\n".join(body)


def _parse_report_facts(text: str) -> _ReportFacts:
    """Extract the blocking tallies and fix-progress dispositions from a report."""
    findings = _section_body(text, "Findings")
    errors = gaps = inconsistencies = improvements = other = 0
    for match in _SEVERITY_LINE_RE.finditer(findings):
        sev = match.group(1).strip().lower()
        if sev == "error":
            errors += 1
        elif sev == "gap":
            gaps += 1
        elif sev == "inconsistency":
            inconsistencies += 1
        elif sev == "improvement":
            improvements += 1
        else:
            other += 1
    total = errors + gaps + inconsistencies + improvements + other

    has_fp = re.search(r"^##\s+Fix Progress\s*$", text, re.MULTILINE) is not None
    fp_body = _section_body(text, "Fix Progress")
    applied = len(re.findall(r"\[APPLIED\]", fp_body))
    fixed = len(re.findall(r"→\s*FIXED", fp_body))
    justified = len(re.findall(r"→\s*JUSTIFIED", fp_body))
    false_positive = len(re.findall(r"→\s*FALSE-POSITIVE", fp_body))
    return _ReportFacts(
        total=total,
        errors=errors,
        gaps=gaps,
        blocking=errors + gaps,
        has_fix_progress=has_fp,
        applied_steps=applied,
        fixed=fixed,
        justified=justified,
        false_positive=false_positive,
    )


def _verify_outcome(
    status: str | None, facts: _ReportFacts | None, *, op_failure: bool
) -> tuple[str, str]:
    """Map the disk record + the one verify signal to a ``VerifyOutcome``."""
    if op_failure:
        return "failed", (
            "caller asserted an operational failure (a dispatch, a check, or the "
            "state write failed); no verification result was persisted"
        )
    if status == "skipped":
        return "skipped", (
            "the served stage's verification was explicitly deferred and persisted "
            "(state-verify --status skipped)"
        )
    if status == "findings-reported":
        if facts is None:
            return "findings", (
                "the verify entry records findings-reported, but its report file is "
                "absent or unreadable on disk"
            )
        return "findings", (
            f"the recorded verification wrote a report with {facts.blocking} blocking "
            "finding(s) (error/gap)"
        )
    if status == "passed":
        return "passed", (
            "the recorded verification is passed (a clean report, an advisory-only "
            "report, or accepted residual findings)"
        )
    raise UsageError(
        "forge-verify has recorded no terminal result for served stage "
        f"({status or 'no verify entry'}); run state-verify first, or pass "
        "--op-failure if the run failed before it could record one"
    )


def _fix_outcome(
    status: str | None,
    *,
    has_reports: bool,
    fix_applied: bool,
    op_failure: bool,
    user_deferred: bool,
    decisions_open: bool,
) -> tuple[str, str]:
    """Map the disk record + the three fix signals to a ``FixOutcome``."""
    if op_failure:
        return "failed", (
            "caller asserted an operational failure (a fix step, a validation, a "
            "commit, or a state write failed); nothing advanced"
        )
    if user_deferred:
        return "deferred", (
            "caller asserted the user explicitly deferred the fix pass or the "
            "mandatory re-verify; the served stage's verification stays outstanding"
        )
    if decisions_open:
        return "decisions", (
            "caller asserted unresolved user decisions block the remaining fixes; "
            "no advancement"
        )
    if not has_reports:
        return "no-findings", (
            "no VERIFY findings document exists for the served stage — nothing to fix"
        )
    if status == "findings-applied":
        return "applied", (
            "fixes are recorded (findings-applied) and no passing re-verify has yet "
            "cleared them; a re-verify is still owed"
        )
    if status == "passed":
        # A forge-fix pass reaches a `passed` served stage only by re-verifying it:
        # Step 1.5 resolves the served stage to an UNRESOLVED verify entry
        # (findings-reported, findings-applied, or a pending debt), never an already
        # resolved `passed`, so a `passed` entry at a fix exit is the mandatory
        # re-verify's own passing result. `fix_applied` is deliberately not consulted —
        # it reads every round on disk and so cannot tell this pass's fixes from an
        # earlier cycle's, and the reason must not claim "this pass" of either.
        return "reverified", (
            "the served stage's verification is passing — the mandatory re-verify "
            "recorded a passing result and cleared the applied fixes"
        )
    if status == "findings-reported":
        if fix_applied:
            return "reverify-findings", (
                "fixes were applied and a re-verify reopened blocking findings for "
                "the served stage"
            )
        raise UsageError(
            "forge-fix ended with the served stage still findings-reported and no "
            "fixes recorded; pass --decisions-open, --user-deferred, or --op-failure "
            "to name the runtime reason, or run forge-fix to apply the plan"
        )
    if not fix_applied:
        return "no-findings", (
            "no unresolved findings are owed for the served stage "
            f"(verify entry: {status or 'absent'})"
        )
    raise UsageError(
        "forge-fix reached an inconsistent state — fixes are recorded on disk but the "
        f"served stage's verify entry is {status or 'absent'}; re-run state-verify to "
        "record the result before selecting an outcome"
    )


def select_outcome(
    feature: str,
    served_stage: str,
    skill: str,
    specs_dir: Path,
    epic: str | None,
    *,
    op_failure: bool,
    user_deferred: bool,
    decisions_open: bool,
) -> dict:
    """Derive the deterministic ``stage-exit --outcome`` for a verify/fix run.

    Returns ``{"outcome", "reason", "evidence": [...]}``. Raises ``UsageError`` (the
    fail-closed exit-2 path) rather than guessing when the disk record cannot name a
    terminal outcome and no runtime signal was supplied.
    """
    if served_stage not in VERIFY_TOKEN_BY_STAGE:
        raise UsageError(
            f"--served-stage {served_stage!r} carries no verify entry; select-outcome "
            f"serves {', '.join(VERIFY_TOKEN_BY_STAGE)} (forge-0-epic and forge-6-docs "
            "are out of scope)"
        )
    if skill == "verify" and (user_deferred or decisions_open):
        raise UsageError(
            "--user-deferred and --decisions-open are forge-fix signals; forge-verify's "
            "only runtime signal is --op-failure"
        )

    token = VERIFY_TOKEN_BY_STAGE[served_stage]
    verify_key = f"forge-verify-{token}"
    feature_dir = _resolve_feature_dir(specs_dir, feature, epic)
    state = _read_state(feature_dir / PIPELINE_STATE_FILENAME)
    entry = _verify_entry(state, verify_key)
    raw_status = entry.get("status")
    status = raw_status if isinstance(raw_status, str) else None

    reports = _verify_reports(feature_dir, token)
    # verify consumes only the latest report; fix additionally needs the any-fix-applied
    # flag and the sweep tallies, which require parsing every round.
    if skill == "fix":
        facts = [_parse_report_facts(_read_report_text(r.path)) for r in reports]
    else:
        facts = (
            [_parse_report_facts(_read_report_text(reports[-1].path))] if reports else []
        )
    latest_facts = facts[-1] if facts else None
    fix_applied = any(f.applied_steps >= 1 for f in facts)

    evidence: list[str] = [f"{verify_key} status = {status or 'absent'}"]
    if reports and latest_facts is not None:
        latest = reports[-1]
        rel = latest.path.relative_to(feature_dir).as_posix()
        evidence.append(
            f"latest report {rel} (round {latest.round}): {latest_facts.blocking} "
            f"blocking = {latest_facts.errors} error + {latest_facts.gaps} gap, "
            f"{latest_facts.total} total finding(s)"
        )
        evidence.append(f"round reports on disk: {len(reports)}")
        if skill == "fix" and fix_applied:
            fixed = sum(f.fixed for f in facts)
            justified = sum(f.justified for f in facts)
            false_positive = sum(f.false_positive for f in facts)
            applied = sum(f.applied_steps for f in facts)
            evidence.append(
                f"fix progress: {applied} step(s) applied; sweep {fixed} fixed / "
                f"{justified} justified / {false_positive} false-positive"
            )
    else:
        evidence.append("no VERIFY report on disk for this mode")

    if skill == "verify":
        outcome, reason = _verify_outcome(status, latest_facts, op_failure=op_failure)
    else:
        outcome, reason = _fix_outcome(
            status,
            has_reports=bool(reports),
            fix_applied=fix_applied,
            op_failure=op_failure,
            user_deferred=user_deferred,
            decisions_open=decisions_open,
        )
    return {"outcome": outcome, "reason": reason, "evidence": evidence}


# --------------------------------------------------------------------------- #
# verify-state — deterministic upstream-verification classification
# --------------------------------------------------------------------------- #
#
# forge-4-backlog, forge-5-loop and forge-6-docs each open by reading a served
# stage's `stages.forge-verify-*` entry and answering one question — "has the
# upstream artifact been verified, and what do I say if not?" — with a different
# hand-rolled branch set (2, 4 and 5 cases). This verb derives that answer from the
# authoritative on-disk entry instead: one `VerifyStateCase`, one message table
# (`VERIFY_STATE_MESSAGES`), the same "never eyeball the graph" move `select-outcome`
# makes for the exit outcome. The full contract is `references/verify-state.md`;
# `test_verify_state.py` pins the enum to the three skill bodies.
#
# It reads raw entry status per served stage — exactly as the three gates do today —
# and does NOT apply the version-aware freshness `verify_state()` computes for the
# navigator's most-recent-stage gate: a `passed` entry is `passed` regardless of the
# stage version, because that is what the gates read. Reusing `verify_state()` would
# inject a re-verify-on-revision the gates do not have, so it would not be additive.


def verify_state_for_stage(
    feature: str,
    for_stage: str,
    specs_dir: Path,
    epic: str | None,
) -> dict:
    """Classify one served stage's ``forge-verify-*`` entry into a ``VerifyStateCase``.

    Returns ``{case, verified, stale, message, nextCommand}``. ``verified`` is true
    only for ``passed``; ``stale`` only for ``findings-applied`` (resolved once, but a
    re-verify is still owed). ``nextCommand`` is the forge-verify retry for every case
    that is not already ``passed`` (which needs no action → ``None``). Never raises for
    a missing or torn state file — an absent or unreadable entry classifies ``never``,
    the same fail-safe the three gates take.
    """
    token = VERIFY_TOKEN_BY_STAGE[for_stage]
    verify_key = f"forge-verify-{token}"
    command = f"/skill:forge-verify {feature} {token}"
    feature_dir = _resolve_feature_dir(specs_dir, feature, epic)
    state = _read_state(feature_dir / PIPELINE_STATE_FILENAME)
    entry = _verify_entry(state, verify_key)
    raw_status = entry.get("status")
    status = raw_status if isinstance(raw_status, str) else None

    # Classification mirrors verify_state()'s status ordering (an explicit skip and
    # recorded auto-verify debt ahead of the generic bucket, so neither falls through
    # to `never`), but keys on the raw per-stage status the three gates read — no
    # version-aware freshness.
    if status == "skipped":
        case = "skipped"
    elif status == "auto-verify-pending":
        # Owed-but-unrun debt with unusable scheduling metadata still stays owed; it
        # warns once (REQ-DEBT-02), exactly as verify_state() does.
        if _scheduled_stage_version(entry) is None:
            _warn_auto_verify_debt_metadata(verify_key)
        case = "auto-verify-pending"
    elif status == "findings-reported":
        case = "findings-reported"
    elif status == "findings-applied":
        case = "findings-applied"
    elif status == "passed":
        case = "passed"
    else:
        # A present status that is torn (non-str) or outside the known vocabulary is
        # flagged once (#148) then treated as `never` — the same answer an absent
        # entry gets. A known `pending` (or absent) is quiet, as in verify_state().
        if raw_status is not None and (
            not isinstance(raw_status, str) or raw_status not in KNOWN_VERIFY_STATUSES
        ):
            _warn_unknown_verify_status(verify_key, raw_status)
        case = "never"

    if case == "auto-verify-pending":
        # The `message` is the gates' base owed-debt sentence (+ the version-advance
        # clause when the schedule predates the artifact). The extra "metadata is
        # missing/malformed" detail (AUTO_VERIFY_DEBT_METADATA_DIAGNOSTIC) is a
        # navigator-only warnings entry the three gates do NOT carry, so it stays out
        # of the message and is surfaced once on stderr by the warn above — exactly as
        # verify_state() does. Enriching the message would diverge from the gates this
        # verb unifies.
        message = auto_pending_message(
            feature,
            for_stage,
            command,
            _scheduled_stage_version(entry),
            _stage_version(state, for_stage),
        )
    else:
        message = VERIFY_STATE_MESSAGES[case].format(
            subject=feature, stage=for_stage, command=command
        )

    return {
        "case": case,
        "verified": case == "passed",
        "stale": case == "findings-applied",
        "message": message,
        "nextCommand": None if case == "passed" else command,
    }


__all__ = [
    "_VerifyReport",
    "_ReportFacts",
    "_classify_verify_entry",
    "_verify_state_for",
    "_read_report_text",
    "_verify_reports",
    "_section_body",
    "_parse_report_facts",
    "_verify_outcome",
    "_fix_outcome",
    "select_outcome",
    "verify_state_for_stage",
]
