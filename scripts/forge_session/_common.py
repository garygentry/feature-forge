"""Low-level primitives shared across the ``forge_session`` package modules.

The foundation layer of the ``forge-session.py`` split (#279): the TypedDicts and
the ``UsageError`` exception the verbs return/raise, plus the ``VerifyStatus``
vocabulary alias several verbs share. Every other package module imports what it
needs FROM here — never from the ``forge-session.py`` shim, which re-exports these
names back out for the path-loaded test oracle and the CLI. Only genuinely shared
primitives live here; each cluster module owns its own internals. (The mirrored
``load_json_with_duplicates``/``warn_duplicate_keys`` pair deliberately stays in the
shim body, byte-identical to ``scripts/forge-bootstrap.py`` — see
``tests/test_json_loader_parity.py`` — so it is NOT extracted here.)

3.10 baseline, Google-style docstrings, stdlib only — matching the conventions of
the monolith it was carved out of.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, TypedDict


class UsageError(Exception):
    """A usage or I/O failure that must exit 2."""


#: The persisted verify-entry status vocabulary; mirrors KNOWN_VERIFY_STATUSES and
#: references/pipeline-state-schema.json's verifyEntry.status.enum.
VerifyStatus = Literal[
    "pending",
    "auto-verify-pending",
    "passed",
    "findings-reported",
    "findings-applied",
    "skipped",
]


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


class EpicReconcile(TypedDict, total=False):
    """Existing epic backflow directive retained in expanded exits.

    Present only for epic members; absent entirely for a standalone feature.
    """

    # True when backflow must run before the member may advance; False when it is
    # merely advisable. Drives whether the exit blocks or only mentions it.
    required: bool
    # True to surface the reminder text in the rendered block. Independent of
    # `required`: a required reconcile with `reminder: False` still blocks silently
    # in `--json` consumers.
    reminder: bool
    # Host-rendered command that performs the reconcile. Already passed through
    # `_host_command`; consumers print it verbatim and never re-translate it.
    command: str
    # Number of member changes awaiting backflow. 0 is meaningful — it means
    # reconcile was evaluated and found nothing, distinct from the key being absent
    # because the feature is not an epic member.
    count: int
    # Canonical (untranslated) production command demoted behind a blocking
    # reconcile — rendered as the unfenced "After reconciling, continue the
    # pipeline with: …" line and passed through `_host_command` at render time.
    # Present only when `required: True`; None/absent otherwise. It is a COMMAND,
    # never a user-supplied reason: the live writer sets it to `next_command`
    # (scripts/forge-session.py) and `_next_steps_block` translates it for the
    # host. Repurposing it to carry prose would send free text through
    # `_host_command` and strip the blocking follow-up line of its source
    # (REQ-COMPAT-01).
    deferred: str | None


class StageExitDirectives(TypedDict, total=False):
    """Machine-readable decisions emitted by `stage_exit`.

    `total=False` throughout: a key's ABSENCE means "not applicable to this exit",
    which is never the same as a present-but-null value. `servedStage: None` says
    the exit resolved no served stage; a missing `servedStage` says the concept does
    not apply. Consumers must distinguish the two.
    """

    # The stage whose exit this is — always one of EXIT_STAGES. Always present.
    stage: str
    # Human-readable noun for this stage's artifact, used by
    # references/stage-exit-protocol.md's "{stageNoun}" slots (the auto-verify
    # heading and the "Verify {stageNoun} now" gate label). Always present;
    # STAGE_NOUN.get(stage, stage), so it defaults to the stage id when unmapped.
    # Pre-existing key, retained verbatim for REQ-COMPAT-01.
    stageNoun: str
    # For a verify/fix branch exit, the production stage the diversion served and
    # rejoins. None on a production-stage exit, which serves only itself.
    servedStage: str | None
    # Verify mode in play (`prd`, `tech`, `specs`, `backlog`, `impl`, `epic`), keyed
    # by VERIFY_MODE_TO_STAGE. None when this exit is not a verify/fix exit.
    verifyMode: str | None
    # Terminal outcome for stages with a multi-way result. Must be a member of
    # EXIT_OUTCOMES[stage] — consult that table rather than this comment,
    # which is deliberately not a second copy of the domain. None for stages
    # whose exit has a single outcome.
    outcome: str | None
    # Branch ownership for a verify/fix exit — ExitOwner, i.e. exactly "direct"
    # (this call owns and prints the terminal block) or "nested" (an outer
    # authoring stage owns it). REQUIRED for forge-verify/forge-fix and REJECTED
    # for stages 0–6, which are always direct owners.
    # None only on a production-stage exit, where the concept does not apply.
    owner: str | None
    # Who prints the terminal block. "self" — this caller renders exactly one
    # sentinel-terminated block. "outer" — a nested invocation that must print
    # nothing terminal, leaving ownership with the outermost authoring stage.
    terminalOwnedBy: Literal["self", "outer"]
    # Feature (or epic) name this exit concerns. Always present.
    feature: str
    # Resolved host: "claude", "pi", or "generic". Selects command syntax and
    # fresh-session wording; never inferred downstream, always decided here.
    host: str
    # Whether the host may dispatch a clean-room verifier subagent —
    # VerifyCapability, i.e. exactly "interactive" or "manual". A manual host
    # receives verify-first ordering with copy-paste commands instead of an
    # interactive gate; capable Pi is interactive, not manual (REQ-EXIT-07).
    # "May", not "has the tool": a session that bars unsolicited dispatch but
    # offers a question tool is interactive, since the gate's prompt makes the
    # dispatch solicited. Only no-question-tool-and-no-dispatch is manual.
    verifyCapability: str
    # Current verification state of the served artifact, as classified by
    # `verify_state` — including "auto-pending" for unrun scheduled verification.
    verifyState: str
    # Production stage the outstanding/owed verification belongs to — the value
    # `pending_verify()` returns; mirrors FeatureRow.verifyStage so navigator rows
    # and stage-exit JSON report the same thing. None when nothing is outstanding.
    # DISTINCT from `servedStage`, which is branch-exit-only: on a production-stage
    # exit `servedStage` is None while `verifyStage` names the stage the debt is
    # owed on (REQ-OBS-01, REQ-DEBT-05).
    verifyStage: str | None
    # Which gate form to render, derived from verifyState and verifyCapability.
    verifyGate: str
    # Host-rendered verify command. Present whenever verification is reachable,
    # even if it is not the primary action.
    verifyCommand: str
    # True when the caller must run in-stage verification before returning control.
    # When True, the auto-verify-pending debt write has already been attempted —
    # see `autoVerifyDebtRecorded` for whether it landed.
    runInStageVerify: bool
    # Effective autoVerify for THIS stage after applying autoVerifyStages overrides
    # over the autoVerify default. Not the raw config value.
    autoVerifyEffective: bool
    # True whenever `runInStageVerify` is True — the scheduling boundary
    # persists the auto-verify-pending marker BEFORE this payload exists, and a
    # failed debt write raises UsageError with no payload at all. So
    # `runInStageVerify: True` with `autoVerifyDebtRecorded: False` is UNREACHABLE;
    # the field is carried so tests and downstream tools can assert that invariant
    # rather than infer it. False with `runInStageVerify: False` simply means no
    # debt was owed (REQ-DEBT-01/04, REQ-REL-02).
    autoVerifyDebtRecorded: bool
    # True when an autoFix chain may run unattended: autoFix configured, zero
    # unresolved decision points, and a clean tree at the pre-scheduling snapshot.
    autoFixEligible: bool
    # Next production stage in pipeline order, or None at the end of the pipeline.
    # Routing introspection only — never promote it over `primaryCommand`.
    nextStage: str | None
    # Host-rendered command for `nextStage`. Retained for compatibility; see the
    # promotion rule below. None when `nextStage` is None.
    nextCommand: str | None
    # THE authoritative single action. While verification is unresolved this is the
    # verify command — or the forge-fix command when a findings report is live at
    # the current revision — never the downstream stage. The one fenced command in
    # the rendered block. None only when the pipeline has no further action: a
    # FINISHED EPIC (#248), whose block fences nothing at all because every command
    # such an exit could fence is the dashboard it was just run from. A null here is
    # terminal, not a gap to fill from `nextCommand` (which is null too).
    primaryCommand: str | None
    # Post-verification guidance shown as prose, never fenced, so it cannot be
    # mistaken for the primary action. None when there is nothing deferred.
    deferredCommand: str | None
    # Keys in autoVerifyStages that name no verify-capable stage — a config typo.
    # Empty list means the config was checked and clean; the key is always present
    # when config was read at all, so [] and absent differ. Each key renders as
    # exactly:
    #   Warning: autoVerifyStages key "{key}" names no verify-capable stage; it is
    #   ignored. Valid keys are forge-1-prd, forge-2-tech, forge-3-specs,
    #   forge-4-backlog, forge-5-loop.
    # Keys are rendered in sorted order, per the determinism rule
    # (REQ-OBS-02, REQ-REL-01).
    invalidAutoVerifyKeys: list[str]
    # Whether the working directory is a git repository at all.
    gitRepo: bool
    # Clean-tree snapshot taken BEFORE the pending-debt write, so the sanctioned
    # state mutation does not dirty its own precondition. None when `gitRepo` is
    # False — unknown, not clean.
    cleanTree: bool | None
    # Human-readable non-fatal advisories, in a fixed deterministic order:
    # (1) the epic-member unreadable-state fallback, (2) the legacy/malformed
    # scheduledStageVersion metadata warning, (3) the scheduled-vs-current
    # revision mismatch note. A LIST,
    # not a string, because these are independently triggerable and can co-occur
    # on one call; a single string would force an implementer to drop or
    # concatenate them, and REQ-REL-01's byte-identical-output requirement needs a
    # defined order to assert against. Mirrors RenderStatus.warnings,
    # which is already a list. Empty list means checked and clean; the key is
    # always present, so [] and absent differ. Each entry names its affected
    # feature/stage/key AND the recovery action (REQ-OBS-02).
    warnings: list[str]
    # Epic backflow directive; see EpicReconcile. Absent for standalone features.
    epicReconcile: EpicReconcile


class StageExitPayload(TypedDict):
    """Serialized direct or nested exit result.

    Total (not `total=False`): all three keys are always present, and a nested
    exit carries explicit nulls rather than omitting them.
    """

    # Always populated, for both direct and nested exits.
    directives: StageExitDirectives
    # The rendered terminal block for a direct owner. MUST be None when
    # `terminalOwnedBy == "outer"` — a nested caller has nothing to print.
    nextSteps: str | None
    # NEXT_STEPS_SENTINEL when this payload owns the terminal block, else None.
    # When non-None, `nextSteps` ends with exactly this string and nothing follows
    # it (REQ-EXIT-03). Carried explicitly so a consumer can verify termination
    # without importing the constant.
    sentinel: str | None


class VerifyEntry(TypedDict, total=False):
    """Feature or epic verification state persisted by `state-verify`.

    `total=False` is load-bearing: terminal writes DELETE the scheduling keys rather
    than nulling them, so an absent `scheduledAt` means "not scheduled"
    while a present-but-null one would be a malformed entry. Legacy entries written
    before this feature simply lack the newer keys and load unmigrated
    (REQ-DEBT-06).
    """

    # The entry's state. Always present on a written entry; a wholly absent entry
    # means never verified, which is distinct from every value here.
    status: VerifyStatus
    # Path to the findings document, relative to the feature directory. Non-empty
    # for `findings-reported`/`findings-applied`; absent otherwise.
    findingsFile: str | None
    # Findings count. 0 is legal and meaningful for `findings-reported` — verified
    # with nothing found — and is not the same as the key being absent.
    findingsCount: int | None
    # UTC ISO-8601 timestamp of the terminal verification result. Absent while
    # scheduling is pending.
    verifiedAt: str | None
    # UTC ISO-8601 timestamp set by `findings-applied`. Its presence alongside a
    # deleted `verifiedStageVersion` is exactly what marks fixes-landed-but-
    # unconfirmed.
    fixedAt: str | None
    # Full 40-character hash of the artifact commit for this entry, or null between
    # commit 1 and commit 2 of the two-commit protocol. Never a short hash on a new
    # write; legacy short hashes still READ (REQ-STATE-01/02).
    commitHash: str | None
    # Artifact revision this result verified — the production stage's `version` for
    # a feature, the manifest `revision` for an epic. Deleted by `findings-applied`
    # on purpose, so freshness stays unresolved until a later `passed` write.
    verifiedStageVersion: int | None
    # UTC ISO-8601 timestamp of the auto-verify schedule. Deleted (not nulled) by
    # any terminal result.
    scheduledAt: str | None
    # Artifact revision current when verification was scheduled. Makes rescheduling
    # idempotent — an identical revision does not rewrite the entry (REQ-REL-01) —
    # and lets a read distinguish debt owed on the current artifact from debt
    # stranded on an older one. Deleted by any terminal result.
    scheduledStageVersion: int | None


# --------------------------------------------------------------------------- #
# Config readers and loop-runner resolution
#
# These are the shared config/state primitives the package modules need. They are
# the package-internal home for logic the ``forge-session.py`` shim also carries
# inline: the shim keeps its own copies for its not-yet-extracted body and for the
# degraded bare-copy layout (a lone forge-session.py with no sibling package), so
# the two coexist until later #279 items drain the shim's inline copies. The
# behaviour is identical either way — a pure move, never a re-derivation.
#
# The duplicate-aware JSON loader below is deliberately a SEPARATE copy from the
# ``load_json_with_duplicates``/``warn_duplicate_keys`` pair mirrored across the flat
# scripts (forge-session.py / forge-bootstrap.py, byte-identical per
# tests/test_json_loader_parity.py). That mirror exists because the flat scripts are
# copied verbatim into per-agent bundles and share no import module; the package
# layer, by contrast, IS a shared import module, so it reads config through this
# copy rather than reaching back into the shim (which would be a circular import).
# --------------------------------------------------------------------------- #


def load_json_with_duplicates(path: Path) -> tuple[object, list[str]]:
    """Load JSON with last-key-wins values and ordered duplicate key names.

    Args:
        path: UTF-8 JSON file to read.

    Returns:
        The parsed JSON value and duplicate key names in deterministic decoder-hook
        order. A repeated occurrence is appended whenever its key was already seen
        in that same object. Objects at every nesting depth use the hook.

    Raises:
        OSError: The path cannot be read as UTF-8 text.
        json.JSONDecodeError: The file is not valid JSON.
    """
    duplicate_keys: list[str] = []

    def object_from_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                duplicate_keys.append(key)
            result[key] = value
        return result

    text = path.read_text(encoding="utf-8")
    value = json.loads(text, object_pairs_hook=object_from_pairs)
    return value, duplicate_keys


def warn_duplicate_keys(path: Path, duplicate_keys: list[str]) -> None:
    """Write one deterministic warning for each reported duplicate occurrence.

    Args:
        path: Source file whose duplicate key was accepted.
        duplicate_keys: Ordered names returned by `load_json_with_duplicates`.

    Raises:
        OSError: The process cannot write to stderr.
    """
    for key in duplicate_keys:
        rendered_key = json.dumps(key, ensure_ascii=False)
        print(
            f"Warning: duplicate JSON key {rendered_key} in {path}; "
            "using the last value.",
            file=sys.stderr,
        )


def _load_config(config_path: Path) -> dict:
    """Read config into a dict, warning on duplicates and tolerating bad input."""
    try:
        value, duplicate_keys = load_json_with_duplicates(config_path)
    except (OSError, ValueError, RecursionError):  # bad JSON, bad UTF-8, absurd nesting
        return {}
    try:
        warn_duplicate_keys(config_path, duplicate_keys)
    except OSError:
        pass  # a diagnostic write failure must not break a total read path
    return value if isinstance(value, dict) else {}


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


# --------------------------------------------------------------------------- #
# State writes (shared machinery for the state-* and decision-* writers)
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
    assumed, matching epic-manifest.py; decision record:
    references/decisions/single-writer-threat-model.md, issue #180).

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


def _commit_state(state_path: Path, state: dict) -> dict:
    """Refresh ``updatedAt`` and write ``state`` atomically; return it for echo.

    Every verb calls this exactly once, after its mutation, so ``updatedAt`` is
    always refreshed on a successful write and the write is atomic.

    Args:
        state_path: The resolved state-file path — a feature's
            ``.pipeline-state.json``, or an epic's ``.epic-state.json``. The helper
            is target-agnostic: it stamps and writes whatever document it is given,
            so an epic write reuses the same atomic mechanism without
            going anywhere near the member resolver.
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


__all__ = [
    "UsageError",
    "VerifyStatus",
    "FeatureRow",
    "EpicReconcile",
    "StageExitDirectives",
    "StageExitPayload",
    "VerifyEntry",
    "load_json_with_duplicates",
    "warn_duplicate_keys",
    "_load_config",
    "_loop_runner_defaults",
    "resolve_loop_runner",
    "_now_iso",
    "_write_state",
    "_commit_state",
]
