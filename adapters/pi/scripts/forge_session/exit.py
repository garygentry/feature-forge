"""The ``stage-exit`` verb — the Scripted Stage Exit (#279).

Extracted verbatim from the ``forge-session.py`` monolith (issue #279, item 007).
``stage_exit`` is the pipeline's largest verb; its routing engine lives in
:mod:`forge_session.routes`, its outcome logic in :mod:`forge_session.outcomes`,
and its write helpers in :mod:`forge_session.state`. This module imports those and
the shared primitives in :mod:`forge_session._common`; it never imports the shim,
so there is no circular import. The CLI contract — flags, branch routing, exit
codes, and the full JSON payload shape — is FROZEN.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Final, get_args

from forge_session._common import (
    EPIC_MEMBER_FALLBACK_WARNING,
    EPIC_STATE_FILENAME,
    EXIT_HOSTS,
    EXIT_OUTCOMES,
    EXIT_STAGES,
    INVALID_AUTO_VERIFY_KEY_WARNING,
    MANIFEST_FILENAME,
    NEXT_STEPS_SENTINEL,
    PIPELINE_STATE_FILENAME,
    PRODUCTION_STAGES,
    ProductionStage,
    SAFE_NAME_RE,
    STAGE_NOUN,
    StageExitPayload,
    UsageError,
    VERIFY_MODE_TO_STAGE,
    VERIFY_TOKEN_BY_STAGE,
    ExitOwner,
    VerifyCapability,
    _EXIT_VERIFY_TOKEN,
    _git_output,
    _load_config,
    _read_state,
    _resolve_feature_dir,
    _stage_version,
    _verify_entry,
    auto_verify_for,
    invalid_auto_verify_keys,
    next_stage,
    pending_verify,
)
from forge_session.outcomes import _classify_verify_entry, _verify_state_for
from forge_session.routes import (
    _branch_route,
    _debt_metadata_warnings,
    _docs_route,
    _epic_terminal_state,
    _host_command,
    _loop_route,
    _next_steps_block,
    _production_stage_of,
    _promote_reconcile,
    _render_status,
    _schedule_auto_verify_debt,
)
from forge_session.state import _assert_safe_name

#: The seven production stages as a ROUTING domain. Deliberately not
#: ``PRODUCTION_STAGES``, which is the six-stage member walk that excludes
#: ``forge-0-epic``; derived from the shared ``ProductionStage`` alias so the two
#: cannot drift.
_EXIT_PRODUCTION_STAGES: Final[tuple[str, ...]] = get_args(ProductionStage)
#: The two direct branch skills — every exit stage that is not a production stage.
#: Derived, so adding a branch skill to ``ExitStage`` lands here automatically.
_BRANCH_STAGES: Final[tuple[str, ...]] = tuple(
    stage for stage in EXIT_STAGES if stage not in _EXIT_PRODUCTION_STAGES
)
#: Inverse of ``VERIFY_MODE_TO_STAGE``. The mapping is injective, so the inverse is
#: total over its values; stages with no mode (``forge-6-docs``) are simply absent.
_STAGE_TO_VERIFY_MODE: Final[dict[str, str]] = {
    stage: mode for mode, stage in VERIFY_MODE_TO_STAGE.items()
}
#: The stage each exit hands off to when pipeline state cannot say better. Also the
#: production-successor table a branch exit walks from its RESOLVED SERVED stage:
#: ``forge-6-docs`` is absent because the pipeline ends there — a docs exit routes to
#: a completion action, never to a nonexistent stage 7.
_EXIT_NEXT_STAGE: Final[dict[str, str]] = {
    "forge-0-epic": "forge-1-prd",
    "forge-1-prd": "forge-2-tech",
    "forge-2-tech": "forge-3-specs",
    "forge-3-specs": "forge-4-backlog",
    "forge-4-backlog": "forge-5-loop",
    "forge-5-loop": "forge-6-docs",
}
def _epic_verify_context(specs_dir: Path, epic_name: str) -> tuple[dict, int | None]:
    """Read an epic's verification entry and manifest revision — tolerantly.

    An epic's verification state lives in ``{specsDir}/{epic}/.epic-state.json``
    and its artifact revision is the sibling manifest's ``revision``. Neither ever
    comes from a member ``.pipeline-state.json``, and a member production-stage
    ``version`` is never the epic's revision (REQ-SEC-01). This
    is the READ half: it degrades to ``({}, None)`` on anything missing or
    malformed, matching stage-exit's "never crash a stage closing" posture. The
    strict, fail-closed resolution lives on the WRITE path
    (``_load_epic_state_for_write``).

    A legacy manifest with no ``revision`` reads as logical ``1``, matching
    ``epic-manifest.py::load_manifest``; its bytes are not rewritten
    (REQ-DEBT-06).

    Args:
        specs_dir: The configured specs directory.
        epic_name: The epic — what ``--feature`` carries on an epic-scoped exit.

    Returns:
        ``(verify_entry, revision)``; ``revision`` is None when the manifest is
        missing or its revision unusable.
    """
    epic_dir = specs_dir / epic_name
    revision: int | None = None
    manifest = _read_state(epic_dir / MANIFEST_FILENAME)
    if manifest:
        raw = manifest.get("revision", 1)
        if isinstance(raw, int) and not isinstance(raw, bool) and raw >= 1:
            revision = raw
    entry = _verify_entry(_read_state(epic_dir / EPIC_STATE_FILENAME), "forge-verify-epic")
    return entry, revision
def _same_named_candidates(specs_dir: Path, epic: str, member: str) -> list[Path]:
    """Directories OTHER than ``{specsDir}/{epic}/{member}`` carrying that name's state.

    Read-only, and used only to tell "no such feature anywhere" apart from "that
    name belongs to someone else" when the selected epic does not contain the
    member. Sorted, so the ambiguity error it feeds is deterministic.
    """
    contained = specs_dir / epic / member
    out: list[Path] = []
    flat = specs_dir / member
    if flat != contained and (flat / PIPELINE_STATE_FILENAME).is_file():
        out.append(flat)
    if specs_dir.is_dir():
        out.extend(
            sorted(
                p
                for p in specs_dir.glob(f"*/{member}")
                if p != contained and (p / PIPELINE_STATE_FILENAME).is_file()
            )
        )
    return out
def _epic_member_state(specs_dir: Path, epic: str, member: str) -> tuple[dict, str | None]:
    """Resolve ONE epic member's live pipeline state for edit-mode routing.

    Identity containment comes first: the member is read from
    ``{specsDir}/{epic}/{member}`` and nowhere else, so a same-named flat feature
    or a member of a different epic can never be substituted for it (REQ-SEC-01).
    ``_assert_safe_name`` has already rejected traversal by the time this runs.

    Progress is then TOLERATED rather than demanded: an absent, unreadable,
    malformed, or foreign-epic state yields a reason instead of an exception, so
    the caller can degrade DOWN to ``forge-1-prd`` with a named warning rather
    than crash a stage closing or infer progress it could not read (REQ-PROD-06).
    This is the one documented new tolerant case.

    Identity itself still fails closed: a member that is not under the selected
    epic at all and whose bare name matches more than one other candidate cannot
    be pinned to a single feature, and guessing would route a DIFFERENT feature's
    pipeline (REQ-REL-02).

    Args:
        specs_dir: The configured specs directory.
        epic: The selected epic — what ``--feature`` carries on an epic exit.
        member: The selected member (``--next-feature``), already name-checked.

    Returns:
        ``(state, None)`` when the member's state resolved, else ``({}, reason)``
        where ``reason`` is a member of ``EPIC_MEMBER_FALLBACK_REASONS``.

    Raises:
        UsageError: The member is not under the selected epic and its bare name is
            ambiguous across the specs tree (→ exit 2, no route guessed).
    """
    member_dir = specs_dir / epic / member
    state_path = member_dir / PIPELINE_STATE_FILENAME
    # ``exists`` rather than ``is_file``: something occupying the state file's name
    # that cannot be read as one is `unreadable`, not absent.
    if not state_path.exists():
        if member_dir.is_dir():
            # Contained, just not started yet — the creation-mode case.
            return {}, "missing"
        elsewhere = _same_named_candidates(specs_dir, epic, member)
        if len(elsewhere) > 1:
            listed = ", ".join(str(p) for p in elsewhere)
            raise UsageError(
                f"ambiguous member {member!r} for epic {epic}: it is not under "
                f"{member_dir} and {len(elsewhere)} other directories carry a state "
                f"file for that name ({listed}) — refusing to guess which feature to "
                f"route to. Re-run naming the epic that owns it."
            )
        return {}, "not a member of this epic" if elsewhere else "missing"
    try:
        raw = state_path.read_text(encoding="utf-8")
    except OSError:
        return {}, "unreadable"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}, "malformed"
    if not isinstance(parsed, dict):
        return {}, "malformed"
    back_pointer = parsed.get("epic")
    if isinstance(back_pointer, str) and back_pointer != epic:
        # The file sits under this epic but claims another one. Trusting either
        # side would assert progress for a feature we cannot identify.
        return {}, "not a member of this epic"
    return parsed, None
def resolve_served_stage(
    served_stage: str | None,
    verify_mode: str | None,
) -> str:
    """Resolve one unambiguous production stage for a branch exit.

    Args:
        served_stage: Explicit production stage supplied by the branch caller.
        verify_mode: Optional authoritative mode mapped by VERIFY_MODE_TO_STAGE.

    Returns:
        A member of the shared ProductionStage domain.

    Raises:
        UsageError: The explicit stage is invalid, mode is invalid, both inputs
            disagree, or neither input identifies a stage.
    """
    if served_stage is not None and served_stage not in _EXIT_PRODUCTION_STAGES:
        raise UsageError(
            f"--served-stage {served_stage!r} is not a production stage; expected "
            f"one of {', '.join(_EXIT_PRODUCTION_STAGES)}"
        )
    if verify_mode is not None and verify_mode not in VERIFY_MODE_TO_STAGE:
        raise UsageError(
            f"--verify-mode {verify_mode!r} is not a known verify mode; expected "
            f"one of {', '.join(VERIFY_MODE_TO_STAGE)}"
        )
    if served_stage is not None and verify_mode is not None:
        mapped = VERIFY_MODE_TO_STAGE[verify_mode]
        if mapped != served_stage:
            # Both were supplied and they disagree. Name both flags and both
            # resolutions — picking one silently is exactly the guess REQ-ROUTE-03
            # forbids.
            raise UsageError(
                f"--served-stage {served_stage} conflicts with --verify-mode "
                f"{verify_mode} (which maps to {mapped}); supply one, or supply "
                "values that agree"
            )
        return served_stage
    if served_stage is not None:
        # Explicit stage takes precedence, and accepts any ProductionStage —
        # including forge-6-docs, which no verify mode maps to.
        return served_stage
    if verify_mode is not None:
        return VERIFY_MODE_TO_STAGE[verify_mode]
    raise UsageError(
        "forge-verify requires --served-stage or an unambiguous --verify-mode; "
        "rerun with the production stage this verification served"
    )
#: The deterministic sentence a TERMINAL epic exit renders (issue #248). Every route
#: fences NOTHING — a closed epic has no next pipeline command, and re-fencing the
#: dashboard is exactly the self-loop this text replaces — so the start-new-work
#: pointers are host-translated INLINE mentions, never the primary action.
#:
#:   ``complete``   every member is genuinely done (the rollup says so)
#:   ``declared``   the operator set the manifest `status` to `complete`; the counts are
#:                  stated as they really are, so the wording never claims members are
#:                  finished when they are not
#:   ``abandoned``  the operator set the manifest `status` to `abandoned`. Checked
#:                  FIRST, ahead of the rollup: an abandoned epic whose members happen
#:                  to be complete must not be announced as completed work.
_EPIC_TERMINAL_TEXT: Final[dict[str, str]] = {
    "complete": (
        "Epic {epic} is complete — every member is done ({complete}/{total}) and "
        "nothing is actionable, so there is no next pipeline command to run. "
        "Optionally, you can start a new feature with `{new_feature}` or group "
        "related work into an epic with `{new_epic}`; neither is required to finish "
        "here. Re-open `{dashboard}` any time to inspect the epic's state."
    ),
    "declared": (
        "Epic {epic} is marked complete in its manifest and nothing is actionable "
        "({complete}/{total} members complete), so there is no next pipeline command "
        "to run. If that count is not what you expect, re-open `{dashboard}` to "
        "inspect the epic; otherwise you can start a new feature with "
        "`{new_feature}` or a new epic with `{new_epic}`."
    ),
    "abandoned": (
        "Epic {epic} is marked abandoned in its manifest, so the pipeline stops here "
        "and nothing further runs against it — this is NOT a completion "
        "({complete}/{total} members had been completed before it was abandoned). "
        "Re-open `{dashboard}` to inspect or revive it, or start a new feature with "
        "`{new_feature}`."
    ),
}
def stage_exit(
    feature: str,
    stage: str,
    specs_dir: Path,
    config_path: Path,
    epic: str | None,
    host: str,
    next_feature: str | None,
    served_stage: str | None = None,
    verify_mode: str | None = None,
    outcome: str | None = None,
    owner: str | None = None,
    verify_capability: str = "manual",
    cause: str | None = None,
) -> StageExitPayload:
    """Compute a deterministic stage-exit payload.

    Args:
        feature: Safe feature name, or epic name for an epic-scoped exit.
        stage: One member of `EXIT_STAGES`.
        specs_dir: Configured specs directory.
        config_path: Path to `forge.config.json`.
        epic: Owning epic for a nested member, otherwise None.
        host: Command-rendering host: `claude`, `pi`, or `generic`.
        next_feature: Explicit epic handoff member, when applicable.
        served_stage: Production stage served by direct verify/fix.
        verify_mode: Verify mode used to infer `served_stage` when unique.
        outcome: Required stage-specific outcome for loop/docs/verify/fix.
        owner: Required for verify/fix: `direct` or `nested`.
        verify_capability: `interactive` only when both question and clean-room
            verifier dispatch capabilities exist; otherwise `manual`. Dispatch
            capability is permission, not tool presence: a dispatch permitted
            only once the user has asked is still `interactive`, because the
            `standard` gate's own prompt supplies that request.
        cause: Pending-attribution annotation (`dependency-starvation`), valid
            only with `--stage forge-5-loop --outcome partial` (REQ-ATTR-04).
            It swaps the partial next-steps sentence for the starvation variant
            and changes no routing.

    Returns:
        A JSON-serializable `StageExitPayload` dictionary.

    Raises:
        UsageError: Unsafe or ambiguous identity, unsupported stage/outcome,
            missing ownership/served-stage metadata, or conflicting inference.

    Directive semantics (the contract in ``references/stage-exit-protocol.md``):

    - ``runInStageVerify`` — the effective auto-verify (per-stage override,
      else global; strict-true) is on AND this stage's verify is not already
      resolved (fresh/skipped) AND no findings report exists at the current
      revision (that state routes to forge-fix instead — scheduling over the
      report would delete its metadata, REQ-EXIT-04). The skill then dispatches
      the clean-room verify in-session (principle #2: verify before the clear).
    - ``autoVerifyDebtRecorded`` — the ``auto-verify-pending`` marker for this
      stage is durably on disk. Written BEFORE this payload exists, so
      a failed write raises ``UsageError`` and returns no payload at all and
      ``runInStageVerify: True`` with ``autoVerifyDebtRecorded: False`` is
      unreachable. Scheduling is idempotent by target revision: a repeat at the
      same revision touches neither ``scheduledAt`` nor top-level ``updatedAt``.
    - ``autoFixEligible`` — ``autoFix`` is strict-true AND the in-stage verify
      runs AND the working tree is clean. Findings-level preconditions (zero
      unresolved decisions) remain the skill's runtime check. Its clean-tree
      snapshot is taken BEFORE the debt write, so that sanctioned control-plane
      mutation cannot dirty its own precondition.
    - ``verifyState``/``warnings``/``cleanTree`` — all PRE-mutation snapshots:
      they describe the state the routing decision was made from, which is why a
      first exit reports ``never`` while the debt it just recorded reads
      ``auto-pending`` on the next one. Only ``autoVerifyDebtRecorded`` reports
      the write.
    - ``verifyGate`` — ``none`` when verify is resolved (including a tokenless
      stage), the in-stage run covers it, or a live findings report routes to
      forge-fix (the fenced fix IS the one action — a "verify now?" prompt
      beside it would be a second, contradictory ask); ``standard`` when
      auto-verify is off, verification is outstanding, and the CALLER declared
      ``--verify-capability interactive``; ``manual-print`` for the same state
      under ``manual`` (print ``verifyCommand`` instead of presenting the gate).
      Never a function of ``--host``: capable Pi is ``standard`` and incapable
      Claude is ``manual-print`` (REQ-EXIT-07).
    - ``primaryCommand``/``deferredCommand`` — the verify-first pair. While
      verification is unresolved ``primaryCommand`` is the verify command — or
      the forge-fix command when a findings report is live at the current
      revision — and is the ONLY fenced command; ``deferredCommand`` names the
      production successor as unfenced conditional prose. ``nextCommand`` stays
      compatibility/routing metadata and never overrides ``primaryCommand``
      (REQ-EXIT-06). Both are None on the one TERMINAL exit — a finished epic
      (see ``forge-0-epic`` below) — where the block fences nothing.
    - ``nextStage``/``nextCommand`` — from pipeline state when it already
      records this stage complete (first non-complete production stage), else
      the fixed successor. ``--next-feature`` names the first actionable
      feature for the epic handoff; without it an epic exit hands back to the
      epic dashboard rather than naming a member it cannot resolve.
      With it, the handoff is derived from THAT member's live state via
      ``next_stage``: a progressed member resumes where it actually is,
      a fully complete member hands back to the epic dashboard, and a member
      whose state cannot be resolved falls back to ``forge-1-prd`` with
      ``warnings`` entry 1 naming it.
    - ``forge-0-epic`` — no route hands back the dashboard as the SOLE remaining
      action (#248). An ACTIONABLE member with no next production stage owes
      verification, so the exit routes to ``render-status``'s own answer for that
      member (``forge-verify``/``forge-fix``, or ``forge-1-prd`` when its PRD is
      missing) rather than to the dashboard. And a CLOSED epic exits terminally:
      when live ``render-status`` reports nothing actionable AND the epic is
      complete, declared complete, or abandoned (see ``_epic_terminal_state``),
      ``primaryCommand``/``nextCommand``/``nextStage`` are all None
      and the block fences nothing. The dashboard is still the answer where it is a
      real action rather than a re-run: a ``UsageError`` recovery, a blocking
      reconcile, and an active epic with no members decomposed yet.
      Previously this state handed back
      ``/skill:forge-0-epic {epic}`` — the command that produced it — so the
      operator was prompted to re-run it indefinitely. The terminal answer applies
      only where the routing already landed on that dashboard, so verify-first
      ordering, a live findings report, and an open epic change request all keep
      precedence, and a ``render-status`` failure still degrades to the recoverable
      dashboard route rather than claiming completion.
    - ``epicReconcile`` — present only when the exiting member carries
      ``open`` ``epicChangeRequests`` (epic-backflow). ``required: true`` (any
      ``blocksCurrent: true`` request) interposes a reconcile-first exit: the
      NEXT-STEPS primary command becomes ``/skill:forge-0-epic {epic}``
      and the normal next stage is deferred. Only non-blocking requests set
      ``reminder: true`` and append a non-blocking reminder line. Absent when
      there are no open requests (common path) or the epic name is unresolvable.
    - ``servedStage``/``verifyMode``/``outcome``/``owner``/``terminalOwnedBy`` —
      branch metadata. A production exit serves only itself, so ``servedStage``
      is None there; ``verifyStage`` is the DISTINCT value ``pending_verify``
      returns, naming the stage outstanding verification is owed on.
      On a branch exit the outcome table in ``_branch_route`` — not
      verify-first ordering — supplies ``primaryCommand``: a diversion rejoins
      the production stage it served, and every recovery/defer route carries
      ``--served-stage`` forward so the thread is never dropped (issue #176).
    - ``forge-5-loop`` — routed by its required ``--outcome``. ``complete``
      keeps verify-first ordering in front of the documentation/epic-member handoff,
      which for a member is delegated to the live ``render-status`` payload rather
      than re-derived here. The other four outcomes route to the loop resume
      (``partial``/``deferred``) or the navigator (``blocked``/``needs-human``) and
      suppress every downstream signal: ``nextStage``/``nextCommand`` are None,
      ``runInStageVerify`` is False, no debt is scheduled, and ``verifyGate`` is
      ``none`` — a loop still in flight has no finished implementation to verify and
      nothing downstream may read as ready (REQ-PROD-02).
    - ``forge-6-docs`` — the documentation terminus is decided by LIVE epic
      state, never by the successor table: for an epic member the adjacent
      ``epic-manifest.py render-status`` supplies the next actionable member's own
      command, and anything else routes to the epic dashboard. A ``blocked``
      outcome routes to recovery and never claims completion. Any helper failure
      is an actionable ``UsageError`` — exit 2 with no payload, so no guessed
      member command and no sentinel can escape (REQ-REL-02).
    - ``warnings`` — non-fatal advisories in the documented fixed order. Always
      present; ``[]`` means checked-and-clean, which is not the same as absent.

    Read-only and deterministic. Syntactic validation fails closed with
    ``UsageError`` (exit 2, no payload and no sentinel); everything after it
    degrades to defaults rather than crashing a stage closing.
    """
    # ---- Deterministic validation order ----------------------------------- #
    # 1. Safe names and containment, before any strict filesystem access.
    _assert_safe_name(feature, "--feature")
    if epic is not None:
        _assert_safe_name(epic, "--epic")
    if next_feature is not None:
        _assert_safe_name(next_feature, "--next-feature")

    # 2. The stage domain itself.
    if stage not in EXIT_STAGES:
        raise UsageError(
            f"unsupported --stage {stage!r}; expected one of {', '.join(EXIT_STAGES)}"
        )

    # 3./4. Stages 0-4 reject an outcome; loop/docs/verify/fix require their own.
    # argparse cannot express a different enum per stage, so the domain check is here.
    allowed_outcomes = EXIT_OUTCOMES.get(stage)
    if allowed_outcomes is None:
        if outcome is not None:
            raise UsageError(
                f"--outcome is not accepted for {stage}; its exit is state-driven "
                "and has a single outcome"
            )
    elif outcome is None:
        raise UsageError(
            f"{stage} requires --outcome; expected one of "
            f"{', '.join(sorted(allowed_outcomes))}"
        )
    elif outcome not in allowed_outcomes:
        raise UsageError(
            f"--outcome {outcome!r} is not valid for {stage}; expected one of "
            f"{', '.join(sorted(allowed_outcomes))}"
        )

    # --cause is a forge-5-loop/partial-only attribution annotation (REQ-ATTR-04).
    # argparse `choices` already restricts the value; this restricts the combination.
    if cause is not None and not (stage == "forge-5-loop" and outcome == "partial"):
        raise UsageError(
            "--cause dependency-starvation is valid only with "
            "--stage forge-5-loop --outcome partial"
        )

    # 5. Ownership: required for the branch skills, rejected for stages 0-6.
    if stage in _BRANCH_STAGES:
        if owner is None:
            raise UsageError(
                f"{stage} requires --owner direct (this call prints the terminal "
                "block) or --owner nested (an outer stage owns it)"
            )
        if owner not in get_args(ExitOwner):
            raise UsageError(
                f"--owner {owner!r} is not valid; expected direct or nested"
            )
    elif owner is not None:
        raise UsageError(
            f"--owner is not accepted for {stage}; only forge-verify and forge-fix "
            "carry branch ownership, and stages 0-6 are always direct owners"
        )

    # 6. Host and capability, independently. A host NEVER implies a capability.
    if host not in EXIT_HOSTS:
        raise UsageError(
            f"unknown --host {host!r}; expected one of {', '.join(EXIT_HOSTS)}"
        )
    if verify_capability not in get_args(VerifyCapability):
        raise UsageError(
            f"unknown --verify-capability {verify_capability!r}; expected "
            f"{' or '.join(get_args(VerifyCapability))}"
        )

    # 7./8. Served stage for branch exits; branch-only flags rejected elsewhere.
    if stage in _BRANCH_STAGES:
        resolved_served: str | None = resolve_served_stage(served_stage, verify_mode)
    else:
        if served_stage is not None or verify_mode is not None:
            raise UsageError(
                "--served-stage and --verify-mode are branch-only; "
                f"{stage} is a production stage and serves only itself"
            )
        resolved_served = None
    if next_feature is not None and stage != "forge-0-epic":
        raise UsageError(
            f"--next-feature is accepted only for forge-0-epic, not {stage}"
        )

    # A loop that did not complete has NO production successor and owes no
    # implementation verification yet. Everything downstream is suppressed below —
    # `nextStage`/`nextCommand`, the epic-reconcile deferred line, the in-stage
    # verify chain, its debt write, and the verify gate — because each of them
    # would assert that the implementation is finished enough to move on, which is
    # exactly the readiness claim REQ-PROD-02 forbids.
    loop_incomplete = stage == "forge-5-loop" and outcome != "complete"

    config = _load_config(config_path)
    invalid_keys = invalid_auto_verify_keys(config)
    for key in invalid_keys:   # already sorted; advisory, never fatal
        print(
            INVALID_AUTO_VERIFY_KEY_WARNING.format(
                key=key, valid=", ".join(VERIFY_TOKEN_BY_STAGE)
            ),
            file=sys.stderr,
        )
    feature_dir = _resolve_feature_dir(specs_dir, feature, epic)
    state = _read_state(feature_dir / PIPELINE_STATE_FILENAME)

    # Epic edit-mode: resolve the SELECTED member's live progress here, before
    # the scheduling boundary below, so an ambiguous identity exits 2 without having
    # mutated anything. `--next-feature` is accepted only for `forge-0-epic` (step 1),
    # so this is exactly the epic edit-mode selection. Read-only: no candidate state
    # file is opened for writing on this path.
    member_state: dict = {}
    member_reason: str | None = None
    if next_feature is not None:
        member_state, member_reason = _epic_member_state(specs_dir, feature, next_feature)

    # The clean-tree snapshot is taken HERE, before the sanctioned debt write
    # below, so the pending marker cannot dirty its own precondition.
    # Every other directive is likewise a pre-mutation snapshot; only
    # `autoVerifyDebtRecorded` describes what the write did.
    git_repo = _git_output(["rev-parse", "--git-dir"]) is not None
    clean_tree: bool | None = None
    if git_repo:
        porcelain = _git_output(["status", "--porcelain"])
        clean_tree = porcelain is None or porcelain == ""

    # A branch exit routes from the production stage it SERVED, never from itself:
    # `forge-verify` has no artifact, no verify token, and no successor of its own.
    # For a production exit the two are the same stage, so stages 0-4 are unchanged.
    route_stage = resolved_served if resolved_served is not None else stage

    # Verification context for the routed stage. An epic-scoped route reads
    # `.epic-state.json` and the manifest revision DIRECTLY — never
    # `_resolve_feature_dir`, never a member stage version (REQ-SEC-01).
    verify_token = _EXIT_VERIFY_TOKEN.get(route_stage)
    verify_key = f"forge-verify-{verify_token}" if verify_token else None
    if route_stage == "forge-0-epic":
        # EPIC-scoped: the entry and the revision come from `.epic-state.json` and the
        # manifest, never from a member stage version, so this branch cannot route
        # through the stage-scoped helper below. `forge-0-epic` always has a token.
        verify_entry, verify_current = _epic_verify_context(specs_dir, feature)
        verify_label = _classify_verify_entry(verify_entry, verify_key, verify_current)
    else:
        verify_entry = _verify_entry(state, verify_key) if verify_key else {}
        verify_current = _stage_version(state, route_stage) if verify_key else None
        # Classify through `_verify_state_for`, the designated stage-exit routing
        # classifier, rather than re-deriving its two steps inline. The inline copy
        # left `_verify_state_for` with no runtime
        # caller, so `tests/test_auto_verify.py` could pin routing labels through a
        # function the CLI never executed. It repeats the `_EXIT_VERIFY_TOKEN` lookup
        # and `_classify_verify_entry` call above and returns "none" for a tokenless
        # stage (forge-6-docs), where there is no verification to owe.
        verify_label = _verify_state_for(state, route_stage)
    # ``none`` is resolved for routing purposes: no verify command is promoted.
    resolved = verify_label in ("fresh", "skipped", "none")
    # A findings report AT THE CURRENT revision is live evidence, not owed debt.
    # Scheduling over it would REPLACE the entry (`_verify_result_entry` builds
    # replacements, not patches) and delete `findingsFile`/`findingsCount` —
    # the same REQ-EXIT-04 clobber the branch-exit guard below forbids, reached
    # instead from a production re-exit. The outstanding obligation is the FIX,
    # so this exit routes to forge-fix and never re-schedules; a report left
    # behind by a since-revised artifact is superseded normally.
    reported_version = verify_entry.get("verifiedStageVersion")
    live_findings_report = (
        verify_label == "failing"
        and isinstance(reported_version, int)
        and not isinstance(reported_version, bool)
        and verify_current is not None
        and reported_version == verify_current
    )
    effective_auto_verify = auto_verify_for(config, route_stage)
    # A BRANCH exit is already inside the verification diversion, so it never owes
    # an in-stage verify chain and never schedules debt. Without this a
    # `forge-verify --outcome findings` exit would both direct a re-dispatch of
    # itself and overwrite the `findings-reported` entry it had just written with
    # a fresh `auto-verify-pending` marker, losing the report (REQ-EXIT-04).
    # Branch rejoin routing belongs to the outcome tables, not this boundary.
    run_in_stage = (
        effective_auto_verify
        and not resolved
        and not live_findings_report
        and stage not in _BRANCH_STAGES
        and not loop_incomplete
    )
    auto_fix_eligible = (
        config.get("autoFix") is True and run_in_stage and clean_tree is True
    )

    # ---- Scheduling boundary ---------------------------------------------- #
    # The debt lands BEFORE the payload exists, so a crash between here and the
    # dispatch leaves durable state exposing the obligation, and a failed write
    # raises UsageError with no payload at all — `runInStageVerify: True` with
    # `autoVerifyDebtRecorded: False` is therefore unreachable.
    auto_verify_debt_recorded = False
    if run_in_stage and verify_key is not None:
        _schedule_auto_verify_debt(specs_dir, feature, epic, route_stage, verify_key)
        auto_verify_debt_recorded = True
    # Priority table. The gate is a pure function of the verification state
    # and the caller's declared capability: `--host` selects command syntax and
    # fresh-session wording ONLY. A capable Pi session gets `standard`; an
    # incapable Claude session gets `manual-print` (REQ-EXIT-07). Whether the
    # caller needed user consent to dispatch is the CALLER's determination
    # and is invisible here — a consent-required caller sends
    # `interactive` and gets `standard`, which is the intended path.
    #
    # A BRANCH exit is already inside the diversion and its outcome table
    # names the one action to take, so there is nothing left to gate: offering
    # "verify now?" beside a fenced fix command would be a second, contradictory
    # ask. The table's `verify` routes ARE the verification prompt.
    #
    # A non-complete loop outcome is gateless for the same reason it never
    # schedules debt: there is no finished implementation to verify, so offering
    # "verify now?" beside a fenced loop resume would ask for a verification of
    # work that is still in flight.
    # A live findings report is likewise gateless: the fenced forge-fix route IS
    # the one action, and a "verify now?" prompt beside it would be a second,
    # contradictory ask for a verification that already ran at this revision.
    if (
        resolved
        or run_in_stage
        or live_findings_report
        or stage in _BRANCH_STAGES
        or loop_incomplete
    ):
        verify_gate = "none"
    elif verify_capability == "interactive":
        verify_gate = "standard"
    else:
        verify_gate = "manual-print"

    next_stage_id = _EXIT_NEXT_STAGE.get(route_stage)
    state_next = next_stage(state)
    if (
        route_stage in PRODUCTION_STAGES
        and state_next is not None
        and PRODUCTION_STAGES.index(state_next) > PRODUCTION_STAGES.index(route_stage)
    ):
        # State records this stage complete AND its walk lands beyond it —
        # trust it (it skips stages already completed out of order). A missing
        # or behind-the-stage walk (state not yet flushed, corrupt file) falls
        # back to the fixed successor, never to an earlier stage.
        next_stage_id = state_next
    # Keyed off the ROUTED stage, so a branch exit that served the epic decomposition
    # hands off the same way the epic's own exit does. Identical to the previous
    # behavior for every production exit, where `route_stage is stage`.
    # Set when live epic state says this epic is FINISHED (#248). Carried to the single
    # application point after the primary chain, so verify-first ordering, a live
    # findings report, and a blocking reconcile all keep their precedence — a terminal
    # epic is only ever allowed to replace a dashboard self-loop, never a real action.
    epic_terminal: tuple[str, dict] | None = None
    if route_stage == "forge-0-epic" and next_feature is None:
        # A branch exit (verify/fix) that served forge-0-epic cannot carry
        # --next-feature (the CLI rejects it for non-epic stages), so the member
        # must be resolved HERE from live epic state.  Creation-mode exits pass
        # --next-feature and skip this block entirely (#230).
        try:
            status = _render_status(specs_dir, feature)
            actionable = status["actionable"]
            epic_terminal = _epic_terminal_state(status, feature)
            if actionable:
                resolved_member = actionable[0]
                ms, mr = _epic_member_state(specs_dir, feature, resolved_member)
                if mr is not None:
                    next_stage_id = "forge-1-prd"
                    next_command = f"/skill:forge-1-prd {resolved_member}"
                else:
                    member_next = next_stage(ms)
                    if member_next is None:
                        # An ACTIONABLE member with no next production stage has
                        # finished all six but is not complete for orchestration —
                        # it owes verification (`auto-verify-pending`) or carries an
                        # unapplied report (`findings-reported`). Handing back the
                        # dashboard here was the #248 self-loop on a not-quite-complete
                        # epic: the dashboard's own exit reproduces this state and
                        # re-fences itself. `render-status` already resolved the right
                        # answer for exactly this member — `forge-verify` or
                        # `forge-fix`, per its own debt rules — so it is used rather
                        # than re-derived here (derivation belongs to epic-manifest.py).
                        #
                        # It is USUALLY a branch command, but not always: the helper
                        # answers `forge-1-prd` for a member whose `PRD.md` is missing
                        # from disk, ahead of its debt fork. So `nextStage` is read back
                        # OUT of the command it chose rather than assumed None —
                        # reporting a production command with `nextStage: null` would
                        # break this payload's own contract (see `nextCommand` above).
                        next_command = (
                            status["nextCommand"]
                            or f"/skill:forge-0-epic {feature}"
                        )
                        next_stage_id = _production_stage_of(next_command)
                    else:
                        next_stage_id = member_next
                        next_command = f"/skill:{member_next} {resolved_member}"
            else:
                next_stage_id = None
                next_command = f"/skill:forge-0-epic {feature}"
        except UsageError:
            next_stage_id = None
            next_command = f"/skill:forge-0-epic {feature}"
    else:
        next_arg = next_feature or feature
        next_command = (
            f"/skill:{next_stage_id} {next_arg}" if next_stage_id else None
        )

    # ---- Epic edit-mode live member routing (issue #175) -------------------- #
    # The fixed `forge-0-epic -> forge-1-prd` successor above is a CREATION-mode
    # answer: a member that has just been decomposed has no completed production
    # stage, so PRD is right. In edit mode the selected member may be anywhere in
    # the pipeline, and sending it back to PRD would ask for work already done.
    # The live position comes from the member's own state via `next_stage`, never
    # from the epic's state, the successor table, or conversational context.
    epic_member_warning: str | None = None
    if next_feature is not None:
        if member_reason is not None:
            # Degrade DOWN, never up: an unreadable member cannot be assumed to
            # have progressed, and inferring a later stage would fabricate the
            # very progress this exit failed to read (REQ-PROD-06).
            epic_member_warning = EPIC_MEMBER_FALLBACK_WARNING.format(
                member=next_feature, epic=feature, reason=member_reason
            )
            next_stage_id = "forge-1-prd"
            next_command = f"/skill:forge-1-prd {next_feature}"
        else:
            member_next = next_stage(member_state)
            if member_next is None:
                # Every production stage is complete. There is no stage 7 to
                # fabricate, so the handoff is the epic dashboard itself — unless the
                # EPIC is finished too, in which case that hand-back is the #248
                # self-loop and the exit goes terminal instead. Only this path can
                # reach the dashboard, so it is the only one that pays for the extra
                # render-status read; an unreadable graph degrades to the hand-back
                # rather than converting a stage closing into a failure.
                next_stage_id = None
                next_command = f"/skill:forge-0-epic {feature}"
                try:
                    epic_terminal = _epic_terminal_state(
                        _render_status(specs_dir, feature), feature
                    )
                except UsageError:
                    epic_terminal = None
            else:
                next_stage_id = member_next
                next_command = f"/skill:{member_next} {next_feature}"

    if loop_incomplete:
        # The pipeline has no next production stage from here, exactly as it has
        # none after `forge-6-docs`. Cleared BEFORE the epic-backflow block below,
        # so a blocking reconcile's `deferred` line cannot re-introduce
        # `/skill:forge-6-docs` as text the loop resume did not earn.
        next_stage_id = None
        next_command = None

    # Epic backflow routing: an exiting member may carry epic-level change requests
    # (recorded by forge-1-prd/forge-2-tech). A `blocksCurrent: true` request means
    # the current feature's next stage would build on a soon-to-change decomposition,
    # so the exit interposes a reconcile-first step; only-`false` requests append a
    # non-blocking reminder. Read-only; the common path (no open requests) is a no-op.
    # The epic name comes from the `--epic` arg or the state's `epic` back-pointer.
    epic_reconcile: dict | None = None
    epic_name = epic or state.get("epic")
    # The epic a documentation or completed-loop exit routes against:
    # the explicit `--epic`, else the state's back-pointer. A back-pointer is
    # untrusted on-disk data, so it is name-checked here rather than reaching the
    # helper's argv (REQ-SEC-01); an unusable value degrades to the standalone route
    # rather than crashing a stage closing. `--epic` itself was already validated in
    # step 1.
    route_epic = (
        epic_name if isinstance(epic_name, str) and SAFE_NAME_RE.match(epic_name) else None
    )
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

    # ---- Verify-first primary routing ------------------------------------- #
    # While verification is unresolved the verify command is THE action — except
    # under a live findings report, whose one action is the forge-fix that applies
    # it. Either way the production successor is demoted to unfenced conditional
    # prose. No path may fence or recommend the deferred production command first
    # (REQ-EXIT-06).
    verify_canonical = f"/skill:forge-verify {feature}"
    # The one action a live findings report promotes, on every route that can
    # reach it: findings already exist at this exact revision, so re-dispatching
    # verify would only restate them. The served stage is carried so the fix
    # rejoins this production thread.
    fix_canonical = f"/skill:forge-fix {feature} --served-stage {route_stage}"
    verify_command = _host_command(verify_canonical, host)
    blocking_reconcile = bool(epic_reconcile and epic_reconcile.get("required"))
    primary_canonical: str | None
    deferred_canonical: str | None
    outcome_text: str | None = None
    if stage in _BRANCH_STAGES:
        # The outcome table alone decides a branch terminus — verify-first
        # ordering does not apply, because the branch IS the verification work.
        primary_canonical, deferred_canonical, outcome_text, advancing = _branch_route(
            stage,
            outcome,
            feature,
            resolved_served,
            next_command,
            resolved,
        )
        if advancing and blocking_reconcile:
            # An advancing rejoin is subject to the same reconcile-first rule as a
            # production exit; a non-advancing one already outranks the reconcile.
            primary_canonical = epic_reconcile["command"]
            deferred_canonical = None
    elif stage == "forge-5-loop":
        # Every loop result gets a deterministic resume or recovery action.
        # `complete` keeps verify-first ordering (the table applies it to its own
        # handoff); the other four never reach a production stage at all.
        primary_canonical, deferred_canonical, outcome_text, advancing = _loop_route(
            outcome,
            feature,
            route_epic,
            specs_dir,
            next_command,
            resolved,
            verify_canonical,
            fix_canonical if live_findings_report else None,
            cause,
        )
        if blocking_reconcile:
            # Same reconcile-first rule as every other advancing route — but the
            # continuation carried forward is the LOOP's, not the successor table's
            # documentation stage, which this route deliberately did not choose.
            primary_canonical, deferred_canonical, outcome_text = _promote_reconcile(
                stage,
                epic_reconcile,
                feature,
                epic_name,
                primary_canonical,
                deferred_canonical,
                outcome_text,
                advancing,
            )
    elif stage == "forge-6-docs":
        # The documentation terminus is decided by LIVE epic state, not by
        # the successor table — the pipeline ends here, so there is no next stage
        # to fence and no verification to put first (docs is tokenless).
        primary_canonical, deferred_canonical, outcome_text, advancing = _docs_route(
            feature,
            route_epic,
            specs_dir,
            outcome,
            host,
        )
        if blocking_reconcile:
            # Same reconcile-first rule as an advancing branch rejoin: handing off to
            # the next member would build it on a decomposition that is about to
            # change. A non-advancing docs route already lands on the epic itself. The
            # successor table has no entry for this stage, so its seeded continuation
            # is None — the live route's own primary is what must be carried forward.
            primary_canonical, deferred_canonical, outcome_text = _promote_reconcile(
                stage,
                epic_reconcile,
                feature,
                epic_name,
                primary_canonical,
                deferred_canonical,
                outcome_text,
                advancing,
            )
    elif live_findings_report:
        primary_canonical = fix_canonical
        deferred_canonical = next_command
    elif not resolved:
        primary_canonical = verify_canonical
        deferred_canonical = next_command
    elif blocking_reconcile:
        # Verification is settled, so the blocking reconcile is the primary
        # action and `epicReconcile["deferred"]` carries the demoted successor.
        primary_canonical = epic_reconcile["command"]
        deferred_canonical = None
    else:
        primary_canonical = next_command or "/skill:forge"
        deferred_canonical = None

    # ---- Terminal epic exit (issue #248) ---------------------------------- #
    # A finished epic gets a genuinely terminal block: no fenced command at all,
    # because every command this exit could fence is the dashboard it was just run
    # from. The equality guard below is what makes this safe to apply so late — it
    # fires ONLY where the routing above already landed on the epic dashboard, so
    # verify-first ordering (primary is the verify command), a live findings report
    # (primary is the fix), and a `blocked` docs recovery all keep their precedence
    # untouched. `not blocking_reconcile` is a SEPARATE, load-bearing guard rather than
    # a restatement of anything above: the reconcile command is the same STRING as the
    # dashboard when the exiting feature IS the epic, so without it a blocking reconcile
    # would be silently swallowed by the equality test.
    #
    # A NON-blocking reminder does not block the terminal answer, and must not: fencing
    # the dashboard for an optional reconcile reinstates the #248 loop (decline it,
    # re-run, get the same block) while promoting a change the exit itself calls
    # non-blocking to the one required action. The reminder survives as the inline line
    # `_next_steps_block` already renders for it — an offer beside "nothing is
    # required", which is exactly what a non-blocking request is.
    epic_dashboard = f"/skill:forge-0-epic {feature}"
    if (
        epic_terminal is not None
        and not blocking_reconcile
        and primary_canonical == epic_dashboard
    ):
        terminal_kind, terminal_fields = epic_terminal
        terminal_text = _EPIC_TERMINAL_TEXT[terminal_kind].format(
            **terminal_fields,
            new_feature=_host_command("/skill:forge-1-prd <new-feature>", host),
            new_epic=_host_command("/skill:forge-0-epic <new-epic>", host),
            dashboard=_host_command(epic_dashboard, host),
        )
        # A branch exit arrives with its own outcome sentence ("verification passed…"),
        # which is still true and still worth saying; the terminal sentence follows it.
        outcome_text = f"{outcome_text} {terminal_text}" if outcome_text else terminal_text
        primary_canonical = None
        deferred_canonical = None
        # Downstream signals are suppressed for the same reason the fence is: there is
        # no next stage, so `nextCommand` must not offer one for a consumer to promote.
        next_command = None
        next_stage_id = None

    # Fixed order: entry 1 is the epic-member unreadable-state fallback,
    # then the debt-metadata and revision-mismatch entries.
    warnings: list[str] = []
    if epic_member_warning is not None:
        warnings.append(epic_member_warning)
    warnings.extend(
        _debt_metadata_warnings(
            verify_entry, verify_key, route_stage, feature, verify_command, verify_current
        )
    )

    # `owner == "nested"` means an outer authoring stage prints the terminal block.
    # The routing directives survive; the human-facing block does not exist at all,
    # so a nested chain can never emit a second sentinel (REQ-EXIT-03/04).
    nested = owner == "nested"

    directives = {
        "stage": stage,
        "stageNoun": STAGE_NOUN.get(stage, stage),
        "servedStage": resolved_served,
        "verifyMode": _STAGE_TO_VERIFY_MODE.get(resolved_served or ""),
        "outcome": outcome,
        "owner": owner,
        "terminalOwnedBy": "outer" if nested else "self",
        "feature": feature,
        "runInStageVerify": run_in_stage,
        "verifyGate": verify_gate,
        "verifyCapability": verify_capability,
        "autoFixEligible": auto_fix_eligible,
        "verifyState": verify_label,
        "verifyStage": pending_verify(state),
        "verifyCommand": verify_command,
        "autoVerifyEffective": effective_auto_verify,
        "autoVerifyDebtRecorded": auto_verify_debt_recorded,
        "nextStage": next_stage_id,
        "nextCommand": _host_command(next_command, host) if next_command else next_command,
        "primaryCommand": (
            _host_command(primary_canonical, host) if primary_canonical else None
        ),
        "deferredCommand": (
            _host_command(deferred_canonical, host) if deferred_canonical else None
        ),
        "invalidAutoVerifyKeys": invalid_keys,
        "warnings": warnings,
        "gitRepo": git_repo,
        "cleanTree": clean_tree,
        "host": host,
    }
    if epic_reconcile is not None:
        directives["epicReconcile"] = epic_reconcile
    if nested:
        return {"directives": directives, "nextSteps": None, "sentinel": None}
    return {
        "directives": directives,
        "nextSteps": _next_steps_block(
            primary_canonical,
            host,
            epic_reconcile,
            deferred_command=deferred_canonical,
            outcome_text=outcome_text,
        ),
        "sentinel": NEXT_STEPS_SENTINEL,
    }
def _print_stage_exit(payload: dict) -> None:
    """Print DIRECTIVES then the NEXT-STEPS block (the skill-facing form).

    A NESTED branch payload carries ``nextSteps is None``: an outer authoring stage
    owns the terminal block, so this printer emits the directives and stops. Printing
    a terminal section here — even an empty one — is the ownership leak REQ-EXIT-04
    forbids.
    """
    print("DIRECTIVES:")
    print(json.dumps(payload["directives"], indent=2, ensure_ascii=False))
    if payload.get("nextSteps") is None:
        return
    print(
        "NEXT-STEPS (print this block verbatim as your absolute last output — "
        "nothing after the sentinel):"
    )
    print(payload["nextSteps"])

__all__ = [
    "_EXIT_PRODUCTION_STAGES",
    "_BRANCH_STAGES",
    "_STAGE_TO_VERIFY_MODE",
    "_EXIT_NEXT_STAGE",
    "_epic_verify_context",
    "_same_named_candidates",
    "_epic_member_state",
    "resolve_served_stage",
    "_EPIC_TERMINAL_TEXT",
    "stage_exit",
    "_print_stage_exit",
]
