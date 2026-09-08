"""Stage-exit routing engine — the branch/docs/loop terminus builders (#279).

Extracted verbatim from the ``forge-session.py`` monolith (issue #279, item 007):
``stage_exit`` (in :mod:`forge_session.exit`) consumes these; they consume only
shared primitives from :mod:`forge_session._common` and the write helpers in
:mod:`forge_session.state`. Nothing here imports the shim, so there is no circular
import. Behaviour is FROZEN: branch routing, exit codes, and the JSON payload shape
are unchanged from the monolith.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Final, NoReturn

from forge_session._common import (
    AUTO_VERIFY_DEBT_METADATA_DIAGNOSTIC,
    NEXT_STEPS_SENTINEL,
    PRODUCTION_STAGES,
    UsageError,
    _commit_state,
    _now_iso,
    _scheduled_stage_version,
    _stage_version,
    _verify_entry,
    auto_pending_message,
)
from forge_session.state import _load_verify_target, _verify_result_entry

#: Bundled beside ``forge-session.py`` (one dir above this package module), the
#: docs router shells out to the sibling ``epic-manifest.py`` there — never a bare
#: ``python3``. ``__file__`` here is ``<scripts>/forge_session/routes.py``, so the
#: sibling resolves one directory up.
_SCRIPTS_DIR: Final = Path(__file__).resolve().parent.parent

#: The route each branch outcome takes. Every value is a COMPLETE map over
#: ``EXIT_OUTCOMES[stage]``: REQ-ROUTE-05/06 require a terminus for every outcome and
#: forbid a fall-through, so a missing key is a bug, not a default. The four kinds:
#:
#:   ``successor``      rejoin the live production position after the served stage
#:   ``fix``            ``/skill:forge-fix FEATURE --served-stage SERVED``
#:   ``verify``         ``/skill:forge-verify FEATURE --served-stage SERVED``
#:   ``verify-if-owed`` ``verify`` while verification is still owed, else ``successor``
#:
#: Only ``successor`` advances. ``decisions``, ``failed``, ``deferred``, and
#: ``reverify-findings`` are deliberately absent from it: unresolved work never
#: reaches a production stage.
_BRANCH_ROUTE_KIND: Final[dict[str, dict[str, str]]] = {
    "forge-verify": {
        "passed": "successor",
        "findings": "fix",
        "skipped": "successor",
        "failed": "verify",
    },
    "forge-fix": {
        "no-findings": "verify-if-owed",
        "decisions": "fix",
        "failed": "fix",
        # `applied` is NOT `reverified`: the writer clears `verifiedStageVersion`, so
        # re-verification is mandatory and this may never route to production.
        "applied": "verify",
        "reverified": "successor",
        "reverify-findings": "fix",
        "deferred": "fix",
    },
}
#: The deterministic sentence each branch outcome renders inside its NEXT-STEPS block
#: (``_next_steps_block(..., outcome_text=...)``). Every non-advancing outcome names
#: the unresolved work explicitly, which is what is required of `decisions`,
#: `failed`, and `deferred`, and what is required of a `failed` verification.
_BRANCH_OUTCOME_TEXT: Final[dict[str, dict[str, str]]] = {
    "forge-verify": {
        "passed": (
            "Verification passed for {served} — the pipeline rejoins where the "
            "diversion left it."
        ),
        "findings": (
            "Verification reported findings for {served}. They are recorded and "
            "remain unresolved, so the pipeline does not advance until they are "
            "fixed and re-verification passes."
        ),
        "skipped": (
            "Verification for {served} was explicitly skipped and the skip is "
            "recorded, so the pipeline may continue."
        ),
        "failed": (
            "Verification for {served} could not run to a result — the dispatch, the "
            "check, or the state write failed. Nothing advances until it does: "
            "resolve the failure, then re-run the verification below."
        ),
    },
    "forge-fix": {
        "no-findings": (
            "No applicable findings were found for {served}, but its verification is "
            "still owed — the absence of applicable findings is not a pass, so "
            "verification runs before the pipeline advances."
        ),
        "decisions": (
            "The fix stopped on unresolved decisions for {served}. Answer them and "
            "re-run the fix below; the pipeline does not advance while they are open."
        ),
        "failed": (
            "The fix for {served} failed — a fix step, a validation, a commit, or a "
            "state write did not complete. The findings remain unresolved, so the "
            "pipeline does not advance; address the failure and re-run the fix below."
        ),
        "applied": (
            "Fixes were applied for {served}, but applied is not verified: the "
            "recorded freshness was cleared, so re-verification is mandatory before "
            "the pipeline advances."
        ),
        "reverified": (
            "Re-verification passed for {served} — the findings are resolved and the "
            "pipeline rejoins where the diversion left it."
        ),
        "reverify-findings": (
            "Re-verification reported further findings for {served}. They remain "
            "unresolved, so the pipeline does not advance."
        ),
        "deferred": (
            "Fix work for {served} was explicitly deferred. The findings remain "
            "UNRESOLVED — the pipeline does not advance until they are fixed and "
            "re-verification passes."
        ),
    },
}
#: `no-findings` is the one outcome whose terminus depends on live state, so it has a
#: second sentence for the already-resolved case.
_NO_FINDINGS_RESOLVED_TEXT: Final[str] = (
    "No applicable findings were found for {served}, and its verification is already "
    "resolved — the pipeline rejoins where the diversion left it."
)
def _host_command(command: str, host: str) -> str:
    """Rewrite a `/skill:` slash command to the host's surface.

    Pi's slash-command surface is `/skill:` (matching the adapter body's
    `/skill:` -> `/skill:` translation). The scripted stage-exit output bypasses
    that body translation, so it rewrites the commands it emits here. No-op for
    claude/generic, which keep the canonical `/skill:` form.
    """
    return command.replace("/skill:", "/skill:") if host == "pi" else command
def _next_steps_block(
    primary_command: str | None,
    host: str,
    reconcile: dict | None = None,
    deferred_command: str | None = None,
    outcome_text: str | None = None,
) -> str:
    """Render one sentinel-terminated terminal block.

    Args:
        primary_command: The sole fenced action, or None for a TERMINAL block — a
            finished epic (#248), where every command this exit could fence is the
            dashboard it was just run from, so fencing one is a self-loop. A terminal
            block carries NO fenced command; `outcome_text` states what finished and
            names any optional follow-on as inline prose.
        host: Command and fresh-session wording target.
        reconcile: Existing epic-backflow override metadata.
        deferred_command: Optional production action allowed only after the primary
            verification/recovery action succeeds.
        outcome_text: Optional deterministic loop/docs/branch outcome explanation.

    Returns:
        A string whose final line is exactly `NEXT_STEPS_SENTINEL`.

    The Claude wording uses the literal ``/clear`` slash-command; the generic
    wording is host-neutral (matching the adapter build's host-term table, so
    a non-Claude bundle invoking ``--host generic`` never instructs a fake
    slash-command).

    ``deferred_command`` is the caller's signal that ``primary_command`` is a
    verification/recovery action standing in front of a production successor: it
    is rendered only as unfenced conditional prose, and the fresh-session wording
    follows the primary action instead of promising "the next stage below"
    (REQ-EXIT-06). It is NEVER fenced, so it cannot be mistaken for the
    primary action.

    ``reconcile`` carries the epic-backflow routing (§Epic backflow in
    ``references/stage-exit-protocol.md``). When it marks a **blocking** request
    (``required: true``) AND the caller made the reconcile command primary, the
    fence carries it and the normal next stage is demoted to a follow-up line.
    When verification is still outstanding the caller keeps the verify command
    primary instead; the reconcile then becomes the FIRST deferred action, ahead
    of the ordinary production successor. When only **non-blocking**
    requests are present (``reminder: true``), a reminder line is appended.
    Either way the added prose is host-neutral (no literal ``/clear``) so it
    survives verbatim into a generic bundle.
    """
    verify_first = deferred_command is not None
    if host == "claude":
        clear_line = (
            "1. `/clear` — recommended unconditionally at this stage boundary; "
            "every artifact is on disk, so the work survives the clear. "
            "I can't `/clear` for you — you have to run it yourself."
        )
        navigator = "`/skill:forge`"
        fresh_prefix = "2. Then start a fresh session and run"
    elif host == "pi":
        # Pi's fresh-session command is `/new` (not `/clear`); its slash-command
        # surface is `/skill:` (the fenced command below is rewritten to match).
        clear_line = (
            "1. `/new` — recommended unconditionally at this stage boundary; every "
            "artifact is on disk, so the work survives starting a fresh session. "
            "I can't run `/new` for you — you have to run it yourself."
        )
        navigator = "`/skill:forge`"
        fresh_prefix = "2. Then, in the new session, run"
    else:
        clear_line = (
            "1. Clear your session / start a fresh session — recommended "
            "unconditionally at this stage boundary; every artifact is on "
            "disk, so the work survives it."
        )
        navigator = None
        fresh_prefix = "2. Then start a fresh session and run"
    resume = (
        f"re-run {navigator} to let the navigator resume from disk."
        if navigator
        else "re-run the forge navigator skill to resume from disk."
    )
    # The primary actionable command goes in a fenced block so mobile/remote hosts
    # get a native copy button (inline code is not tap-to-copy). The CALLER decides
    # which command is primary (the renderer fences exactly what it
    # is given); the fence sits before the sentinel, so the sentinel remains the
    # absolute last line. A terminal block fences nothing at all.
    terminal = primary_command is None
    fenced_command = "" if terminal else _host_command(primary_command, host)
    if terminal:
        # A deferred successor and a BLOCKING reconcile both presuppose a required next
        # action, so neither can coexist with "nothing further is required".
        # `stage_exit` already clears them; asserting it here keeps a future caller from
        # rendering a block that says nothing further and then names something further.
        # A non-blocking REMINDER is explicitly allowed — its inline line is an offer,
        # not an action, and suppressing it would drop a recorded request on the floor.
        assert deferred_command is None and not (
            reconcile and reconcile.get("required")
        ), "a terminal NEXT-STEPS block carries no deferred or blocking follow-up"
    if verify_first:
        # REQ-EXIT-06: the fresh-session guidance follows the PRIMARY action, and
        # must never tell the user to clear and run the production successor first.
        # It names what is actually FENCED: on a branch exit that is the fix standing
        # between recorded findings and the re-verification, not a verify
        # command. Every other case keeps the wording verbatim.
        action_noun = "fix" if "forge-fix " in fenced_command else "verification"
        next_line = (
            f"{fresh_prefix} the {action_noun} below — verification is still "
            "outstanding for this stage, so it comes before the next production "
            f"stage. Or {resume}"
        )
    elif terminal:
        # No "below" to point at: `fresh_prefix` numbers the step, and the sentence
        # says the pipeline is done rather than naming an action that does not exist.
        # The navigator resume stays available as prose — inspecting a finished epic is
        # not the same as being told to run it again.
        next_line = (
            "2. Nothing further is required here — there is no next pipeline command. "
            f"To inspect the finished state, {resume}"
        )
    else:
        next_line = f"{fresh_prefix} the next stage below — or {resume}"
    blocking = bool(reconcile and reconcile.get("required"))
    reconcile_is_primary = bool(
        blocking and _host_command(reconcile["command"], host) == fenced_command
    )
    lines = ["**Next steps**"]
    if outcome_text:
        lines.append(outcome_text)
    lines.append(clear_line)
    if reconcile_is_primary:
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
    if not terminal:
        lines.append(f"```\n{fenced_command}\n```")
    if blocking and not reconcile_is_primary:
        # Verification outranked the reconcile, so the reconcile is the FIRST
        # deferred action and the production successor stays subordinate to it.
        count = reconcile["count"]
        plural = "s" if count != 1 else ""
        lines.append(
            f"After verification passes, reconcile the epic first — {count} "
            f"blocking epic change request{plural} flagged: "
            f"`{_host_command(reconcile['command'], host)}`"
        )
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
    if verify_first and _host_command(deferred_command, host) != _host_command(
        (reconcile or {}).get("deferred") or "", host
    ):
        # Unfenced, conditional prose only. Suppressed when the
        # blocking reconcile above already demoted this same command, so one
        # command never appears twice in the deferred chain.
        lines.append(
            "After verification passes, continue with: "
            f"`{_host_command(deferred_command, host)}`"
        )
    lines.append(NEXT_STEPS_SENTINEL)
    return "\n".join(lines)
def _branch_route(
    stage: str,
    outcome: str,
    feature: str,
    served: str,
    successor_command: str | None,
    resolved: bool,
) -> tuple[str, str | None, str, bool]:
    """Route one verify/fix outcome back into the pipeline — the rejoin tables.

    A verify or fix diversion must rejoin the production stage it SERVED rather than
    dropping the pipeline thread (issue #176), so the served stage is carried forward
    in every branch command this returns. Commands are canonical, pre-`_host_command`
    forms; the renderer translates them.

    "Live successor" is the current production position, never a conversational
    assumption: `successor_command` is already the state-aware next production action
    after the served artifact, and it is None only at the end of the pipeline — a
    completed stage 6, which routes to the navigator completion action rather than a
    nonexistent stage 7.

    Args:
        stage: `forge-verify` or `forge-fix`.
        outcome: A member of `EXIT_OUTCOMES[stage]`, already validated.
        feature: The feature (or epic) the diversion served.
        served: The resolved served production stage.
        successor_command: Canonical live-successor command, or None at pipeline end.
        resolved: Whether the served stage's verification is settled. Consulted only
            by `no-findings`, the one outcome whose terminus depends on live state.

    Returns:
        `(primary_canonical, deferred_canonical, outcome_text, advancing)`.
        `deferred_canonical` is the demoted production successor, rendered only as
        unfenced prose, and is None whenever the primary command already advances.

    Two rows carry a precondition this router does NOT re-check: `skipped` is valid
    only after the skip is persisted and `reverified` only after a passing state is
    recorded. Both are the CALLER's obligation — the branch skills
    write through `state-verify` before invoking this exit, and a fix
    that merely skips re-verification reports `deferred`, not `reverified`. Rejecting
    the outcome here would make a valid member of `EXIT_OUTCOMES[stage]` exit 2, which
    is a different contract from the one `stage_exit` validates.
    """
    kind = _BRANCH_ROUTE_KIND[stage][outcome]
    if kind == "verify-if-owed":
        template = (
            _NO_FINDINGS_RESOLVED_TEXT if resolved else _BRANCH_OUTCOME_TEXT[stage][outcome]
        )
        kind = "successor" if resolved else "verify"
    else:
        template = _BRANCH_OUTCOME_TEXT[stage][outcome]
    text = template.format(served=served)

    if kind == "successor":
        return successor_command or f"/skill:forge {feature}", None, text, True

    branch = "forge-fix" if kind == "fix" else "forge-verify"
    return (
        f"/skill:{branch} {feature} --served-stage {served}",
        successor_command,
        text,
        False,
    )
#: Keys `_render_status` requires before it will route on a `render-status --json`
#: payload. `RenderStatus` is TOTAL: every key is always present, so an
#: empty `actionable` list is the answer "nothing is actionable" and a MISSING key
#: means the helper is not the contract this router was built against — an
#: actionable routing failure, never a silently-skipped check.
_RENDER_STATUS_REQUIRED: Final[tuple[str, ...]] = (
    "epic",
    "status",
    "features",
    "actionable",
    "rollup",
    "nextCommand",
)
#: The bound on the one subprocess the docs exit path makes. Matches every other
#: `subprocess.run` in this file (the git reads and the `forge-root.sh` resolver);
#: without it a hung or pathological epic would stall stage closure with no
#: diagnostic, defeating REQ-PERF-01.
_RENDER_STATUS_TIMEOUT: Final = 10
def _render_status_failure_detail(proc: subprocess.CompletedProcess) -> str:
    """Name WHY a nonzero ``render-status --json`` failed, in one deterministic line.

    Its first stderr line when it wrote one (a missing/unreadable manifest exits 2
    that way), else the first validation finding from the JSON on stdout — which is
    the only place an invalid graph reports itself (it exits 1 with
    ``{"valid": false, "findings": [...]}`` and a silent stderr).

    Args:
        proc: The completed ``render-status`` process.

    Returns:
        A single-line detail, or ``""`` when the helper said nothing usable.
    """
    lines = proc.stderr.strip().splitlines()
    if lines:
        return lines[0]
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return ""
    findings = payload.get("findings") if isinstance(payload, dict) else None
    if isinstance(findings, list) and findings and isinstance(findings[0], dict):
        message = findings[0].get("message")
        if isinstance(message, str):
            return f"first finding: {message}"
    return ""
def _render_status(specs_dir: Path, epic: str) -> dict:
    """Read LIVE epic status from the sibling ``epic-manifest.py``.

    The docs exit routes on the epic's real dependency/completion graph rather than
    re-deriving it here: dependency and completion derivation belong to
    ``epic-manifest.py``; duplicating them in this file is forbidden.

    ``<bundle-root>`` is NOT a path this router may guess. ``forge-session.py`` is
    copied verbatim into six adapter bundles and runs from an arbitrary cwd, so the
    helper is resolved as a SIBLING of this file — the ``RUNTIME_HELPERS`` guarantee
    that ships them together, matching the existing ``_resolve_plugin_root``
    convention — and invoked with ``sys.executable`` rather than a bare ``python3``,
    which may be absent or a different interpreter than the one running this script.

    Args:
        specs_dir: Configured specs directory, passed through to the helper.
        epic: The epic name; also the subject of every failure message.

    Returns:
        The parsed ``RenderStatus`` dict.

    Raises:
        UsageError: A missing sibling helper, a non-zero exit (which covers an
            invalid graph — ``render-status`` refuses to render one), a spawn
            failure, a timeout at the bound, unparseable stdout, or a missing or
            malformed required field. Every one is an actionable exit-2 routing
            failure that names the epic and the recovery command, so the caller
            emits no guessed member route and no sentinel (REQ-REL-02).

    Reads only the bounded local manifest/member-state set — no network call and no
    repository-history scan (REQ-PERF-01).
    """
    helper = _SCRIPTS_DIR / "epic-manifest.py"

    def fail(reason: str) -> NoReturn:
        raise UsageError(
            f"cannot route the documentation exit for epic {epic!r}: {reason}. "
            f"Run /skill:forge-0-epic {epic} to inspect the epic and "
            "resolve it, then re-run this exit."
        )

    if not helper.is_file():
        fail(f"the sibling epic-manifest.py is missing at {helper}")
    try:
        proc = subprocess.run(
            [
                sys.executable,
                str(helper),
                "render-status",
                epic,
                "--specs-dir",
                str(specs_dir),
                "--json",
            ],
            capture_output=True,
            text=True,
            timeout=_RENDER_STATUS_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        fail(f"render-status did not finish within {_RENDER_STATUS_TIMEOUT} seconds")
    except OSError as exc:
        fail(f"render-status could not be started ({exc})")
    if proc.returncode != 0:
        # An INVALID GRAPH exits 1 with its findings as JSON on stdout and nothing on
        # stderr, so quoting stderr alone would report a bare exit code for the one
        # failure the operator most needs named (REQ-OBS-02).
        detail = _render_status_failure_detail(proc)
        fail(f"render-status exited {proc.returncode}{f' ({detail})' if detail else ''}")
    try:
        status = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        fail(f"render-status did not emit parseable JSON ({exc})")
    if not isinstance(status, dict):
        fail("render-status emitted a non-object JSON payload")
    missing = [key for key in _RENDER_STATUS_REQUIRED if key not in status]
    if missing:
        fail(f"render-status omitted required field(s): {', '.join(missing)}")
    rollup = status["rollup"]
    if not isinstance(rollup, dict) or any(
        not isinstance(rollup.get(key), int) or isinstance(rollup.get(key), bool)
        for key in ("complete", "total")
    ):
        fail("render-status emitted a malformed rollup")
    if not isinstance(status["actionable"], list):
        fail("render-status emitted a malformed actionable list")
    if status["nextCommand"] is not None and not isinstance(status["nextCommand"], str):
        fail("render-status emitted a malformed nextCommand")
    if not isinstance(status["status"], str):
        # The manifest's own lifecycle status, which `_epic_terminal_state` reads so
        # `set-status complete` / `abandoned` reach the terminal exit. A non-string is a
        # torn or hand-edited manifest, not a routing answer.
        fail("render-status emitted a malformed status")
    return status
#: The deterministic sentence each documentation terminus renders inside its
#: NEXT-STEPS block. Every epic route names the epic; no `blocked` route claims the
#: pipeline is complete. `{new_feature}`/`{new_epic}` are host-translated INLINE
#: mentions: starting a new feature is allowed only as secondary unfenced text, and
#: `_next_steps_block` fences exactly the primary command and nothing else.
_DOCS_OUTCOME_TEXT: Final[dict[str, str]] = {
    "standalone-complete": (
        "Documentation is complete for {feature}, and with it the pipeline. The "
        "navigator command below is the authoritative completion action — it "
        "confirms the finished state from disk. Optionally, you can start a new "
        "feature with `{new_feature}` or group related work into an epic with "
        "`{new_epic}`; neither is required to finish here."
    ),
    "standalone-blocked": (
        "Documentation could not be completed for {feature}, so the pipeline is NOT "
        "complete. Only valid partial state was persisted. Run the navigator below "
        "to see what remains and recover from there."
    ),
    "epic-actionable": (
        "Documentation is complete for {feature}. Epic {epic} has more work that can "
        "be started now ({complete}/{total} members complete), so the pipeline "
        "continues with the next actionable member below."
    ),
    "epic-blocked-members": (
        "Documentation is complete for {feature}, but no member of epic {epic} is "
        "actionable right now ({complete}/{total} members complete) — the remaining "
        "work is blocked by unmet dependencies. Open the epic dashboard below to see "
        "what is holding it up."
    ),
    "epic-complete": (
        "Documentation is complete for {feature}, and every member of epic {epic} is "
        "now complete ({complete}/{total}). Open the epic dashboard below for its "
        "completion view."
    ),
    "epic-blocked": (
        "Documentation could not be completed for {feature}, so neither this feature "
        "nor epic {epic} is complete. Only valid partial state was persisted. Open "
        "the epic dashboard below to see the epic's live state and recover from there."
    ),
    # The `skipped` variants (#197): same routes as `complete`, honest wording — a
    # deliberate skip closes the pipeline without any stage claiming artifacts it
    # never produced, and the state says `skipped`, not `complete`.
    "standalone-skipped": (
        "Documentation was deliberately skipped for {feature} and recorded as "
        "`skipped` in state, closing the pipeline without claiming docs that were "
        "never written. The navigator command below is the authoritative completion "
        "action — it confirms the finished state from disk. Docs can still be "
        "generated later by re-running `{docs_stage}`. Optionally, you can start a "
        "new feature with `{new_feature}` or group related work into an epic with "
        "`{new_epic}`; neither is required to finish here."
    ),
    "epic-actionable-skipped": (
        "Documentation was deliberately skipped for {feature} and recorded as "
        "`skipped` in state. Epic {epic} has more work that can be started now "
        "({complete}/{total} members complete), so the pipeline continues with the "
        "next actionable member below."
    ),
    "epic-blocked-members-skipped": (
        "Documentation was deliberately skipped for {feature} and recorded as "
        "`skipped` in state, but no member of epic {epic} is actionable right now "
        "({complete}/{total} members complete) — the remaining work is blocked by "
        "unmet dependencies. Open the epic dashboard below to see what is holding "
        "it up."
    ),
    "epic-complete-skipped": (
        "Documentation was deliberately skipped for {feature} and recorded as "
        "`skipped` in state, and every member of epic {epic} is now complete "
        "({complete}/{total}). Open the epic dashboard below for its completion view."
    ),
}
def _production_stage_of(command: str) -> str | None:
    """The PRODUCTION stage a canonical `/skill:<stage> <name>` command runs.

    Reads the stage back out of a command another component already chose, so
    ``nextStage`` and ``nextCommand`` cannot disagree. None for a branch command
    (``forge-verify``/``forge-fix``), the navigator, or anything unrecognised — those
    are real answers with no production stage, not failures.

    This is a PARSE of a decision, never a re-derivation of one: nothing here decides
    where the pipeline goes (REQ-PROD-05 keeps that in `next_stage`/`epic-manifest.py`).
    """
    if not command.startswith("/skill:"):
        return None
    stage = command[len("/skill:"):].split(" ", 1)[0]
    return stage if stage in PRODUCTION_STAGES else None
def _epic_terminal_state(status: dict, epic: str) -> tuple[str, dict] | None:
    """Classify a `render-status` payload as a TERMINAL epic state, or not (#248).

    A completed epic used to have no terminus: with nothing actionable, the exit set
    ``primaryCommand`` back to ``/skill:forge-0-epic {epic}``, and re-running
    that command reproduced the same exit — the operator was prompted to run the same
    command indefinitely. This is the predicate that ends it.

    Three independent ways to be closed, deliberately kept distinct so the wording can
    stay honest about which one applies:

    - the MANIFEST says ``status: "abandoned"`` — checked FIRST, ahead of the rollup,
      because an abandoned epic whose members happen to be complete must not be
      announced as completed work;
    - the ROLLUP says every member is complete — the ordinary case, and the one that
      answers the reported defect; ``total > 0`` is required so an epic with no members
      declared yet is never called complete;
    - the MANIFEST says ``status: "complete"`` — the operator's explicit
      ``set-status complete``, which previously had NO effect on this routing at all.

    Nothing actionable is required by any of them: an epic with startable work left is
    not closed no matter what its manifest says. The fourth manifest status, ``paused``,
    is deliberately absent: a pause is an intent to resume, and the dashboard it keeps
    routing to is where resuming starts.

    In practice ``"declared"`` is NARROW, and deliberately so. ``actionable`` is "not
    complete and no unmet deps", so on a valid (acyclic) graph an incomplete member
    always has an actionable ancestor: ``actionable == []`` with ``total > 0`` already
    implies the rollup is full, and ``"complete"`` wins. What ``"declared"`` really
    reaches today is the epic with NO members yet, where the rollup reads ``0/0`` and
    only the operator can say it is finished. It is kept as a separate answer — rather
    than folded into the rollup rule — because the manifest is an independent signal
    that must not be silently ignored, and because a future derivation admitting an
    unactionable incomplete member would need exactly this branch. The wording it
    selects states the real counts for that reason.

    Args:
        status: A validated ``render-status`` payload.
        epic: The epic name, carried into the wording fields.

    Returns:
        ``(kind, fields)`` where kind keys ``_EPIC_TERMINAL_TEXT`` and fields carry the
        REAL member counts, or None when the epic is not closed.
    """
    if status["actionable"]:
        return None
    rollup = status["rollup"]
    if status["status"] == "abandoned":
        kind = "abandoned"
    elif rollup["total"] > 0 and rollup["complete"] >= rollup["total"]:
        kind = "complete"
    elif status["status"] == "complete":
        kind = "declared"
    else:
        return None
    return kind, {
        "epic": epic,
        "complete": rollup["complete"],
        "total": rollup["total"],
    }
def _docs_route(
    feature: str, epic: str | None, specs_dir: Path, outcome: str, host: str
) -> tuple[str, str | None, str, bool]:
    """Route the documentation exit — the live-state table.

    For an epic member the route comes from the live ``render-status`` payload, so a
    Step-1 snapshot taken before docs state changed is never trusted: an actionable
    next member routes to that member's own live command, and anything else (blocked
    remaining work, or every member complete) routes to the epic dashboard, which is
    also the dashboard's completion view. A ``blocked`` docs outcome routes to
    recovery and NEVER claims pipeline completion. A ``skipped`` outcome (#197)
    takes exactly the routes ``complete`` takes — the pipeline still ends here —
    but its wording says the docs were deliberately skipped, never that they exist.

    Args:
        feature: The feature whose documentation stage is closing.
        epic: The owning epic, or None for a standalone feature.
        specs_dir: Configured specs directory.
        outcome: `complete`, `blocked`, or `skipped`, already validated.
        host: Host surface, used only to translate the INLINE secondary mentions —
            the primary command is translated by the renderer.

    Returns:
        `(primary_canonical, deferred_canonical, outcome_text, advancing)`, matching
        `_branch_route`. `deferred_canonical` is always None: a docs terminus has no
        production successor to demote, because the pipeline ends here.

    A ``blocked`` epic exit deliberately does NOT call ``render-status``: its route is
    fixed at the epic dashboard regardless of what the live graph says, and a broken
    epic graph is precisely the state in which the recovery route must stay reachable
    rather than converting into a second failure.
    """
    if epic is None:
        text = _DOCS_OUTCOME_TEXT[f"standalone-{outcome}"].format(
            feature=feature,
            new_feature=_host_command("/skill:forge-1-prd <new-feature>", host),
            new_epic=_host_command("/skill:forge-0-epic <new-epic>", host),
            docs_stage=_host_command(f"/skill:forge-6-docs {feature}", host),
        )
        return f"/skill:forge {feature}", None, text, False

    dashboard = f"/skill:forge-0-epic {epic}"
    if outcome == "blocked":
        text = _DOCS_OUTCOME_TEXT["epic-blocked"].format(feature=feature, epic=epic)
        return dashboard, None, text, False

    skip_suffix = "-skipped" if outcome == "skipped" else ""
    status = _render_status(specs_dir, epic)
    rollup = status["rollup"]
    fields = {
        "feature": feature,
        "epic": epic,
        "complete": rollup["complete"],
        "total": rollup["total"],
    }
    next_command = status["nextCommand"]
    if status["actionable"] and next_command:
        return (
            next_command,
            None,
            _DOCS_OUTCOME_TEXT["epic-actionable" + skip_suffix].format(**fields),
            True,
        )
    # Nothing actionable. Under the current derivation that coincides with "every
    # member complete" (a valid graph is acyclic, so an incomplete member always has
    # an actionable ancestor), but the two cases are named separately and the
    # rollup is the observable that tells them apart — so the blocked wording stays
    # reachable if a future derivation admits an unactionable incomplete member. Both
    # route to the same epic command either way; only the explanation differs.
    key = "epic-complete" if rollup["complete"] >= rollup["total"] else "epic-blocked-members"
    return dashboard, None, _DOCS_OUTCOME_TEXT[key + skip_suffix].format(**fields), False
#: The route each loop outcome takes. A COMPLETE map over
#: ``EXIT_OUTCOMES["forge-5-loop"]``: REQ-PROD-01/02 require a deterministic resume or
#: recovery action for every result, so a missing key is a bug, not a default.
#:
#:   ``handoff``  verify-first implementation routing, then the live docs/epic handoff
#:   ``resume``   ``/skill:forge-5-loop FEATURE`` — state remains resumable
#:   ``recover``  ``/skill:forge FEATURE`` — the deterministic diagnostic action
#:
#: Only ``handoff`` (i.e. ``complete``) may reach a production stage. A runner's
#: successful process exit is NOT by itself ``complete``: the final backlog state
#: selects the outcome, and that selection is the skill's job.
_LOOP_ROUTE_KIND: Final[dict[str, str]] = {
    "complete": "handoff",
    "partial": "resume",
    "deferred": "resume",
    "resolved": "resume",
    "blocked": "recover",
    "needs-human": "recover",
}
#: The deterministic sentence each NON-complete loop outcome renders inside its
#: NEXT-STEPS block. Every one names the resume or recovery action and states that
#: nothing downstream is ready — no wording here may imply that documentation, or any
#: other downstream production stage, can start (REQ-PROD-02).
_LOOP_OUTCOME_TEXT: Final[dict[str, str]] = {
    "partial": (
        "The loop stopped for {feature} with backlog items still pending — the "
        "iteration limit was reached before every item was done. The recorded state "
        "is resumable and nothing downstream is ready: run the loop again below to "
        "continue from where it stopped."
    ),
    "deferred": (
        "The loop explicitly deferred items for {feature} — the runner gave up on "
        "them after retries rather than finishing them, so they were left for "
        "another pass. The recorded state is resumable and nothing downstream is "
        "ready: run the loop again below to pick the deferred items back up."
    ),
    "blocked": (
        "The loop is blocked for {feature} — one or more backlog items could not be "
        "completed. Nothing downstream is ready. Run the navigator below to see the "
        "live pipeline state from disk and choose how to recover."
    ),
    "needs-human": (
        "The loop stopped for {feature} on a decision only a human can make — one or "
        "more items asked a question it could not answer, and they were set aside. "
        "Nothing downstream is ready until those decisions are made. Run the "
        "navigator below to see the live pipeline state from disk and recover from "
        "there."
    ),
    "resolved": (
        "The needs-human stop for {feature} was resolved — the recorded decisions "
        "were applied and every affected item was verified, per item, to have left "
        "blocked/needsHuman, with the working tree clean. The recorded state is "
        "resumable and nothing downstream is ready: run the loop again below to "
        "continue from where it stopped."
    ),
}
#: The starvation variant of the `partial` next-steps sentence (REQ-ATTR-02): names
#: the unblock path instead of the iteration limit, which was NOT the binding
#: constraint. Selected only by ``--cause dependency-starvation`` (REQ-ATTR-04).
_LOOP_PARTIAL_STARVED_TEXT: Final[str] = (
    "The loop stopped for {feature} with backlog items still pending, but the "
    "iteration limit was NOT the constraint — no pending item was selectable because "
    "unblocked root items gate the rest of the backlog. The recorded state is "
    "resumable and nothing downstream is ready: unblock the roots named in the "
    "starvation report above, then run the loop again below to continue."
)
#: The `complete` preamble, selected by where the handoff actually lands. The epic
#: rows name the epic and its live rollup, so the operator can see WHY the handoff is
#: this member's own documentation rather than another member (or vice versa).
_LOOP_COMPLETE_TEXT: Final[dict[str, str]] = {
    "standalone": "Every backlog item is done for {feature}.",
    "epic-next-member": (
        "Every backlog item is done for {feature}, and the live status of epic "
        "{epic} ({complete}/{total} members complete) puts the next actionable work "
        "below."
    ),
    "epic-complete-docs": (
        "Every backlog item is done for {feature}, and every member of epic {epic} "
        "is now complete ({complete}/{total}) — documentation is the next step below."
    ),
    "epic-dashboard": (
        "Every backlog item is done for {feature}, and no member of epic {epic} is "
        "actionable right now ({complete}/{total} members complete). Open the epic "
        "dashboard below for its live state."
    ),
}
#: Appended to the `complete` preamble. REQ-EXIT-06/REQ-PROD-02: while implementation
#: verification is unresolved it is THE action and the handoff is demoted to unfenced
#: prose, so documentation never becomes primary before a pass or an explicit skip.
_LOOP_COMPLETE_OUTSTANDING: Final[str] = (
    " Implementation verification is still outstanding, so it comes first — nothing "
    "downstream becomes the primary action until it passes or is explicitly skipped."
)
_LOOP_COMPLETE_SETTLED: Final[str] = (
    " Its implementation verification is settled, so the pipeline continues with the "
    "action below."
)
_LOOP_COMPLETE_FINDINGS: Final[str] = (
    " Implementation verification already ran at this revision and reported findings, "
    "so applying them comes first — nothing downstream becomes the primary action "
    "until a re-verify passes or the verification is explicitly skipped."
)
#: The outcome sentence a loop or documentation exit renders when a blocking
#: epic change request DISPLACES its live continuation. Both route tables above name
#: that continuation "below"; once the fence carries the reconcile instead, the claim is
#: false, so the sentence is REPLACED rather than corrected after the fact. The displaced
#: command is deliberately not named here — the block's own "After reconciling, continue
#: the pipeline with" line is its single authoritative mention, so the two can never
#: disagree. Only used when the displaced command actually differs from the reconcile:
#: a route that already lands on the epic keeps its own accurate wording.
_RECONCILE_FIRST_TEXT: Final[dict[str, str]] = {
    "forge-5-loop": (
        "Every backlog item is done for {feature} and its implementation verification "
        "is settled, but {count} blocking epic change request{plural} recorded against "
        "epic {epic} must be reconciled first. Proceeding would build on a "
        "decomposition that is about to change, so the reconcile below comes before "
        "the continuation named under it."
    ),
    "forge-6-docs": (
        # "closed", not "complete": this wording also serves a `skipped` docs
        # outcome, which must never claim the docs exist (#197).
        "The documentation stage is closed for {feature}, but {count} blocking epic "
        "change request{plural} recorded against epic {epic} must be reconciled first. "
        "Handing off would build the next member on a decomposition that is about to "
        "change, so the reconcile below comes before the continuation named under it."
    ),
}
def _promote_reconcile(
    stage: str,
    epic_reconcile: dict,
    feature: str,
    epic_name: object,
    primary_canonical: str,
    deferred_canonical: str | None,
    outcome_text: str | None,
    advancing: bool,
) -> tuple[str, str | None, str | None]:
    """Reconcile-first promotion for the loop and documentation routes.

    Both routes compute their real primary from LIVE state (``render-status``), long
    after ``epicReconcile["deferred"]`` was seeded from the successor table. That seed
    is the wrong continuation for these two stages — for the loop it names this
    feature's own documentation, which the route deliberately did not choose, and for
    documentation it is None because the pipeline has no stage after it. So the
    continuation is re-derived here from the route's own result, never from the
    successor table (REQ-ROUTE-05/06: the live thread is what must survive).

    Args:
        stage: `forge-5-loop` or `forge-6-docs` — selects the replacement wording.
        epic_reconcile: The blocking reconcile directive, MUTATED in place.
        feature: The exiting feature.
        epic_name: The epic the reconcile is recorded against.
        primary_canonical: The route's own primary command.
        deferred_canonical: The route's own deferred continuation, if any.
        outcome_text: The route's own outcome sentence.
        advancing: Whether the route's primary advances the pipeline.

    Returns:
        `(primary_canonical, deferred_canonical, outcome_text)` after promotion.

    A route whose primary IS the epic command (the dashboard handoffs) is not
    displaced by a reconcile that names the same command: promoting it would leave a
    "continue the pipeline with" line pointing back at the fence, so its own accurate
    wording and an absent continuation are kept instead.
    """
    reconcile_command = epic_reconcile["command"]
    if not advancing:
        # Verification (or a recovery action) outranks the reconcile, so the reconcile
        # is the FIRST deferred action and the route's own continuation follows it.
        # Handing the renderer the same command the caller deferred is what collapses
        # the two conditional lines into one.
        epic_reconcile["deferred"] = deferred_canonical
        return primary_canonical, deferred_canonical, outcome_text
    if primary_canonical == reconcile_command:
        epic_reconcile["deferred"] = None
        return primary_canonical, None, outcome_text
    epic_reconcile["deferred"] = primary_canonical
    count = epic_reconcile["count"]
    return (
        reconcile_command,
        None,
        _RECONCILE_FIRST_TEXT[stage].format(
            feature=feature,
            epic=epic_name,
            count=count,
            plural="s" if count != 1 else "",
        ),
    )
def _loop_route(
    outcome: str,
    feature: str,
    epic: str | None,
    specs_dir: Path,
    successor_command: str | None,
    resolved: bool,
    verify_canonical: str,
    fix_canonical: str | None,
    cause: str | None = None,
) -> tuple[str, str | None, str, bool]:
    """Route one loop result — the outcome table.

    Every outcome lands on a deterministic action. Only ``complete`` may reach a
    production stage, and even then documentation is not primary until implementation
    verification passes or is explicitly skipped (REQ-PROD-02, REQ-EXIT-06). The four
    non-complete outcomes route to the loop resume (``partial``/``deferred``) or to
    the navigator (``blocked``/``needs-human``); their caller has already stripped the
    production successor, so no directive and no rendered line can imply that
    documentation is ready.

    Args:
        outcome: A member of `EXIT_OUTCOMES["forge-5-loop"]`, already validated.
        feature: The feature whose loop stage is closing.
        epic: The owning epic, or None for a standalone feature.
        specs_dir: Configured specs directory.
        successor_command: Canonical live-successor command (documentation), or None.
        resolved: Whether the implementation verification is settled.
        verify_canonical: Canonical implementation-verify command.
        fix_canonical: Canonical forge-fix command when a findings report is live
            at the current revision (see ``live_findings_report`` in ``stage_exit``),
            else None. A live report outranks a fresh verify on the ``complete``
            handoff: findings already exist at this exact revision, so the fenced
            action is applying them, exactly as on a production re-exit.
        cause: The already-validated attribution annotation — only
            ``"dependency-starvation"`` with ``outcome == "partial"``, else None.
            Swaps the partial next-steps sentence for the starvation variant; the
            route itself is unchanged (partial stays a resume either way).

    Returns:
        `(primary_canonical, deferred_canonical, outcome_text, advancing)`, matching
        `_branch_route` and `_docs_route`.

    For a completed EPIC MEMBER the handoff is delegated to the live
    ``render-status`` payload rather than re-deriving dependency or completion logic
    here, preserving the epic handoff this stage already performed:
    an actionable member routes to the epic's own live next command; nothing
    actionable with every member complete routes to this member's documentation; and
    anything else opens the epic dashboard. The ``total > 0`` guard is what stops an
    EMPTY epic's ``0/0`` from reading as complete. A helper failure is the same
    actionable ``UsageError`` the documentation exit raises, so a broken epic graph
    surfaces instead of being guessed around. A NON-complete outcome never calls the
    helper: a resume or recovery action must stay reachable exactly when the epic's
    own state is the thing that is broken.
    """
    kind = _LOOP_ROUTE_KIND[outcome]
    if kind != "handoff":
        primary = (
            f"/skill:forge-5-loop {feature}"
            if kind == "resume"
            else f"/skill:forge {feature}"
        )
        if outcome == "partial" and cause == "dependency-starvation":
            text = _LOOP_PARTIAL_STARVED_TEXT.format(feature=feature)
        else:
            text = _LOOP_OUTCOME_TEXT[outcome].format(feature=feature)
        return primary, None, text, False

    handoff = successor_command or f"/skill:forge {feature}"
    fields: dict[str, object] = {"feature": feature, "epic": epic}
    key = "standalone"
    if epic is not None:
        status = _render_status(specs_dir, epic)
        rollup = status["rollup"]
        fields["complete"] = rollup["complete"]
        fields["total"] = rollup["total"]
        next_command = status["nextCommand"]
        if status["actionable"] and next_command:
            handoff, key = next_command, "epic-next-member"
        elif rollup["total"] > 0 and rollup["complete"] >= rollup["total"]:
            # Nothing left to start and every member complete: the epic's remaining
            # work is this member's documentation, which `handoff` already names.
            key = "epic-complete-docs"
        else:
            handoff, key = f"/skill:forge-0-epic {epic}", "epic-dashboard"

    if resolved:
        tail = _LOOP_COMPLETE_SETTLED
    elif fix_canonical is not None:
        tail = _LOOP_COMPLETE_FINDINGS
    else:
        tail = _LOOP_COMPLETE_OUTSTANDING
    text = _LOOP_COMPLETE_TEXT[key].format(**fields) + tail
    if resolved:
        return handoff, None, text, True
    if fix_canonical is not None:
        # A live findings report outranks a fresh verify, exactly as on a
        # production re-exit: the fenced action is the fix, the handoff is demoted.
        return fix_canonical, handoff, text, False
    # Verify-first ordering, applied to the loop's own handoff rather than to
    # the fixed successor: the verification is fenced and the handoff is demoted.
    return verify_canonical, handoff, text, False
def _debt_metadata_warnings(
    entry: dict,
    verify_key: str | None,
    stage: str,
    subject: str,
    verify_command: str,
    current: int | None,
) -> list[str]:
    """Entries 2 and 3 of the ``warnings`` order, for owed automatic verification.

    Entry 2 is the legacy/malformed ``scheduledStageVersion`` advisory;
    entry 3 is the scheduled-vs-current revision mismatch note. They are
    mutually exclusive by construction — a mismatch is only detectable once the
    recorded revision is usable — but the order is fixed regardless so a later
    entry can be added without re-deriving it.

    Takes the already-resolved entry and revision rather than re-deriving them
    from a member state document: on an epic-scoped exit both come from
    ``.epic-state.json`` and the manifest revision, which a member state cannot
    supply (REQ-SEC-01).

    Args:
        entry: The verify entry the exit routed from (``{}`` when absent).
        verify_key: Its ``forge-verify-*`` key, or None for a tokenless stage.
        stage: The production stage the debt is owed on.
        subject: The feature or epic to name.
        verify_command: The host-translated retry command.
        current: The artifact's current revision, or None when unknown.
    """
    if verify_key is None or entry.get("status") != "auto-verify-pending":
        return []
    scheduled = _scheduled_stage_version(entry)
    if scheduled is None:
        return [
            AUTO_VERIFY_DEBT_METADATA_DIAGNOSTIC.format(
                subject=subject, verify_key=verify_key, command=verify_command
            )
        ]
    if current is not None and scheduled != current:
        return [
            auto_pending_message(subject, stage, verify_command, scheduled, current)
        ]
    return []
def _schedule_auto_verify_debt(
    specs_dir: Path, feature: str, epic: str | None, stage: str, verify_key: str
) -> None:
    """Persist `auto-verify-pending` for `stage` — the scheduling boundary.

    Called immediately BEFORE `stage_exit` returns a payload carrying
    ``runInStageVerify: true``, never after, so there is no window in which the
    model is told to verify while nothing on disk records that it was owed
    (REQ-DEBT-01, REQ-REL-03). The transition itself is `cmd_state_verify`'s —
    `_load_verify_target` selects the target and `_verify_result_entry` builds the
    entry — so a scheduled marker is byte-identical to one written through the CLI.

    Idempotent by target revision (REQ-REL-01): an entry already
    `auto-verify-pending` at the current revision returns without calling
    `_commit_state`, so `scheduledAt`, top-level `updatedAt`, and the file bytes
    are all untouched. A newer revision supersedes the older marker with exactly
    one write. The caller's `resolved` and live-report checks are what keep a
    fresh terminal entry, an explicit `skipped`, or a `findings-reported` entry
    at the current revision from ever reaching this function — the last because
    a write here REPLACES the entry and would delete its report metadata
    (REQ-EXIT-04).

    Unlike the `state-verify` CLI, a target whose artifact revision is unknown
    (no recorded `version`, or an epic with no readable manifest) records the debt
    with a null `scheduledStageVersion` rather than refusing: the obligation is
    real either way, and an unusable schedule is already classified as
    `auto-pending` plus a warning. Forgetting the debt because its revision is
    unknown is the REQ-DEBT-02 conflation, and refusing would turn a routine stage
    closing into an exit 2.

    Args:
        specs_dir: The configured specs directory.
        feature: The feature name, or the EPIC name for an epic-scoped exit.
        epic: The owning epic for a member, else None.
        stage: The production stage the debt is owed on (`forge-0-epic` for an
            epic-scoped exit).
        verify_key: The `forge-verify-*` key to write.

    Raises:
        UsageError: Unsafe/ambiguous/unresolvable target, corrupt state, or an
            atomic-write failure (→ exit 2, no payload and no dispatch directive).
    """
    is_epic_target = stage == "forge-0-epic"
    state_path, state, epic_revision = _load_verify_target(
        specs_dir, feature, epic, is_epic_target
    )
    if is_epic_target:
        current = epic_revision
    else:
        version = _stage_version(state, stage)
        current = (
            version
            if isinstance(version, int) and not isinstance(version, bool) and version >= 1
            else None
        )
    prior = _verify_entry(state, verify_key)
    if (
        prior.get("status") == "auto-verify-pending"
        and _scheduled_stage_version(prior) == current
    ):
        return
    state.setdefault("stages", {})[verify_key] = _verify_result_entry(
        "auto-verify-pending", prior, current, None, None, _now_iso()
    )
    _commit_state(state_path, state)

__all__ = [
    "_BRANCH_ROUTE_KIND",
    "_BRANCH_OUTCOME_TEXT",
    "_NO_FINDINGS_RESOLVED_TEXT",
    "_host_command",
    "_next_steps_block",
    "_branch_route",
    "_RENDER_STATUS_REQUIRED",
    "_RENDER_STATUS_TIMEOUT",
    "_render_status_failure_detail",
    "_render_status",
    "_DOCS_OUTCOME_TEXT",
    "_production_stage_of",
    "_epic_terminal_state",
    "_docs_route",
    "_LOOP_ROUTE_KIND",
    "_LOOP_OUTCOME_TEXT",
    "_LOOP_PARTIAL_STARVED_TEXT",
    "_LOOP_COMPLETE_TEXT",
    "_LOOP_COMPLETE_OUTSTANDING",
    "_LOOP_COMPLETE_SETTLED",
    "_LOOP_COMPLETE_FINDINGS",
    "_RECONCILE_FIRST_TEXT",
    "_promote_reconcile",
    "_loop_route",
    "_debt_metadata_warnings",
    "_schedule_auto_verify_debt",
]
