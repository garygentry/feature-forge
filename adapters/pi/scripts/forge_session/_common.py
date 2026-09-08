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
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, Literal, TypedDict


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



# --------------------------------------------------------------------------- #
# Shared pipeline-state readers and the recency-ranked feature rows
#
# The read-side chain the discover/reconcile/epic-base cluster needs (via
# ``build_rows``) and that the state/outcome clusters will share too. Copied here
# from the ``forge-session.py`` shim, which keeps its own inline copies for its
# not-yet-extracted body and the degraded bare-copy layout (a lone forge-session.py
# whose stage-exit/doctor paths reach this chain). A pure move, byte-identical to
# the shim; later #279 items drain the shim's copies once every reader lives here.
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


#: The terminal status the completion writer records (and the commit-hash
#: follow-up requires) — NOT the whole "done for selection" set below.
_DONE_STATUS: Final = "complete"
#: Production stage statuses that count as "done" for next-stage selection.
#: `skipped` is legal only on forge-6-docs (schema: `docsStageEntry`) — an
#: explicitly skipped documentation stage ends the pipeline without claiming
#: artifacts it never produced (#197). Selection treats the status as done
#: wherever it appears; the schema is what confines it to the docs stage.
_DONE_STATUSES: Final = frozenset({_DONE_STATUS, "skipped"})
#: The authoritative forge-verify status vocabulary. SOURCE OF TRUTH:
#: references/pipeline-state-schema.json (definitions.verifyEntry.properties.status.enum).
#: A status outside this set is unrecognized and must not be silently interpreted (#148).
#: NOTE: epic-manifest.py keeps a byte-identical copy — flat, self-contained scripts have
#: no shared import module (each is copied verbatim into per-agent adapter bundles).
KNOWN_VERIFY_STATUSES: Final = frozenset(
    {
        "pending",
        "auto-verify-pending",
        "passed",
        "findings-reported",
        "findings-applied",
        "skipped",
    }
)
#: Verify statuses that count as "resolved" (no outstanding verify needed). A STRICT
#: subset of KNOWN_VERIFY_STATUSES — not collapsible into it (different meaning).
#: `auto-verify-pending` is deliberately ABSENT: owed-but-unrun debt is not resolved.
_VERIFY_RESOLVED: Final = frozenset({"passed", "findings-applied", "skipped"})


#: Per-process dedupe for the unknown-verify-status diagnostic (#148) so a single
#: bogus status is flagged once, not once per verify_state() call in a command.
_UNKNOWN_VERIFY_WARNED: set[str] = set()
#: Per-process dedupe for the auto-verify debt-metadata diagnostic, same reason.
_AUTO_VERIFY_DEBT_WARNED: set[str] = set()
#: The single normative sentence every read-side emitter uses for owed-but-unrun
#: automatic verification. One line naming the
#: subject, the served stage, and the retry command — never a state-file dump.
AUTO_PENDING_DIAGNOSTIC: Final = (
    "{subject}: automatic verification is still pending for {stage}; "
    "run {command} to resolve it."
)


def _read_state(state_path: Path) -> dict:
    """Read a `.pipeline-state.json`, tolerating missing/corrupt files.

    A missing, unreadable, or unparseable state downgrades to ``{}`` rather than
    crashing the scan — the navigator simply treats that feature as not-started.
    """
    try:
        parsed = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, ValueError, RecursionError):  # bad JSON, bad UTF-8, absurd nesting
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
    status is not in ``_DONE_STATUSES`` (a missing/pending/in-progress/stale
    stage all count as "not done"; ``complete`` and a forge-6-docs ``skipped``
    both count as done). Returns ``None`` when every production stage is done
    (nothing left to run).

    This is the derived "what runs next" value — the single source of truth for
    the next stage. It is intentionally distinct from the stored
    ``currentStage`` field ("where the pipeline IS"; see the schema): the next
    stage is computed from ``stages[].status`` here, never read from
    ``currentStage``.
    """
    for stage in PRODUCTION_STAGES:
        if _stage_status(state, stage) not in _DONE_STATUSES:
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


def _scheduled_stage_version(entry: dict) -> int | None:
    """Return an ``auto-verify-pending`` entry's usable ``scheduledStageVersion``.

    ``None`` when the field is absent, a bool, a non-integer, or below 1 — i.e.
    legacy state written before the scheduling fields existed, or hand-edited
    state. The caller stays ``auto-pending`` either way: unusable metadata is a
    reason to warn, never a reason to forget the debt.
    """
    version = entry.get("scheduledStageVersion")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        return None
    return version


def _warn_auto_verify_debt_metadata(verify_key: str) -> None:
    """Flag an ``auto-verify-pending`` entry whose scheduled revision is unusable.

    Without a recorded revision the debt cannot be compared against the current
    artifact, so it can be neither discharged as fresh nor described as advanced.
    It REMAINS outstanding — the alternative (degrading to ``never``) is exactly
    the conflation REQ-DEBT-02 forbids — but the operator needs to know why the
    row carries no revision detail, so say it once per process.
    """
    if verify_key in _AUTO_VERIFY_DEBT_WARNED:
        return
    _AUTO_VERIFY_DEBT_WARNED.add(verify_key)
    print(
        f"feature-forge: {verify_key} is auto-verify-pending but its "
        "scheduledStageVersion is missing or malformed (legacy or hand-edited "
        "state); the debt stays outstanding — re-run forge-verify to resolve it "
        "and record a usable schedule",
        file=sys.stderr,
    )


def auto_pending_message(
    subject: str,
    stage: str,
    command: str,
    scheduled_version: int | None = None,
    current_version: int | None = None,
) -> str:
    """Render the diagnostic for owed-but-unrun automatic verification.

    Args:
        subject: The feature or epic the debt belongs to.
        stage: The served production stage the debt is owed on.
        command: The host-translated forge-verify retry command.
        scheduled_version: Revision the debt was recorded against, if usable.
        current_version: The artifact's current revision, if known.

    Returns:
        One sentence, with both revision numbers appended when the recorded
        schedule predates the current artifact. Never a state-file dump.
    """
    message = AUTO_PENDING_DIAGNOSTIC.format(
        subject=subject, stage=stage, command=command
    )
    if (
        scheduled_version is not None
        and current_version is not None
        and scheduled_version != current_version
    ):
        message += (
            f" The artifact has advanced since it was scheduled "
            f"(scheduled at revision {scheduled_version}, now at revision "
            f"{current_version})."
        )
    return message


def verify_state(state: dict) -> tuple[str | None, str]:
    """Classify verify freshness for the most-recently-completed stage.

    Returns ``(stage, state_label)`` where ``state_label`` is one of:

    - ``fresh``   — the entry is ``passed`` AND its ``verifiedStageVersion`` matches
      the stage's current ``version`` (so no re-verify is needed). ``passed`` is the
      ONLY status that reaches ``fresh``: ``findings-applied`` and ``skipped`` are
      resolved but never fresh, for the reasons given below.
    - ``stale``   — verify was resolved once, but the stage version has since moved
      (artifact revised) OR the entry predates the freshness ledger (no
      ``verifiedStageVersion``), OR the entry is ``findings-applied``, which never
      classifies ``fresh`` regardless of any version it carries (§4.2 step 4).
      A revised artifact must be re-verified.
    - ``failing`` — verify ran and reported findings that are not yet applied
      (``findings-reported``).
    - ``auto-pending`` — effective configuration scheduled unattended in-stage
      verification and nothing has discharged it: the obligation is RECORDED and
      owed. Deliberately distinct from ``never`` (nobody ever asked for it), from
      manual ``pending`` work, and from every resolved label — a dropped
      ``runInStageVerify`` directive is precisely what this makes visible (#163,
      REQ-DEBT-02). Classified BEFORE the generic unresolved handling below, and
      never downgraded when its scheduling metadata is missing or malformed.
    - ``never``   — the stage completed but verify has not run at all.
    - ``skipped`` — the user explicitly chose to proceed without verifying. A
      resolved, non-pending state: it is deliberately NOT re-offered or
      auto-verified, and (unlike a genuine verification result) it does not go
      stale on an artifact revision — skip writers record no version to compare
      against, and re-surfacing would override an explicit human decision.
    - ``none``    — no completed verify-capable stage (nothing to verify), stage
      is ``None``.

    Only the most-recent completed production stage is considered, matching the
    navigator's "verify before continuing" gate. A ``findings-applied`` entry is
    treated as ``stale`` UNCONDITIONALLY — applying fixes is not verifying them —
    and an absent ``verifiedStageVersion`` on a ``passed`` entry (legacy state) is
    likewise ``stale``: verify rather than skip.
    """
    for stage in reversed(PRODUCTION_STAGES):
        if _stage_status(state, stage) not in _DONE_STATUSES:
            continue
        token = VERIFY_TOKEN_BY_STAGE.get(stage)
        if token is None:
            continue  # forge-6-docs has no verify step
        entry = _verify_entry(state, f"forge-verify-{token}")
        status = entry.get("status")
        if status is not None and not isinstance(status, str):
            # A torn or hand-edited entry can carry any JSON type here; an
            # unhashable one would raise TypeError at the frozenset membership
            # below, crashing the navigator on one bad file. Same answer as an
            # absent entry — and the same #148 diagnostic as an unknown string,
            # so the degradation is never silent.
            _warn_unknown_verify_status(f"forge-verify-{token}", status)
            return stage, "never"
        if status == "skipped":
            # An explicit skip is resolved and non-pending — preserve the user's
            # decision. It never goes stale (no recorded version to compare), so
            # the freshness check below deliberately does not apply.
            return stage, "skipped"
        if status == "auto-verify-pending":
            # Ordered ahead of the generic unresolved branch so recorded debt can
            # never fall through to "never". Unusable metadata warns and stays
            # owed; a superseded revision stays owed too.
            if _scheduled_stage_version(entry) is None:
                _warn_auto_verify_debt_metadata(f"forge-verify-{token}")
            return stage, "auto-pending"
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
        if status == "findings-applied":
            # Applying fixes is not verifying them: §4.2 step 4 says `findings-applied`
            # CLEARS freshness, and only a later `passed` restores it. The writer builds
            # the entry without `verifiedStageVersion`, but the read side may not rely on
            # that — REQ-DEBT-06 requires loading legacy state without migration, and a
            # pre-writer entry can still carry the key. Without this guard such an entry
            # reads `fresh`, `pending_verify` returns None, and the verification debt for
            # a fixed-but-never-re-verified stage disappears silently.
            return stage, "stale"
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

    A row whose verify classifies ``auto-pending`` carries recorded-but-undischarged
    automatic verification: ``verifyPending`` is True, ``verifyState`` is
    ``auto-pending``, and ``verifyCommand`` is non-null, so no consumer can read it
    as verification-complete. The named sentence goes to stderr (this is the
    one emitter that knows the feature name); stdout keeps the three stable JSON
    keys — ``verifyState``, ``verifyStage``, ``verifyCommand`` — and no prose.
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
        verify_command = f"/skill:forge-verify {name}" if verify_pending else None
        if vlabel == "auto-pending" and vstage is not None and verify_command:
            token = VERIFY_TOKEN_BY_STAGE.get(vstage)
            entry = _verify_entry(state, f"forge-verify-{token}") if token else {}
            print(
                auto_pending_message(
                    name,
                    vstage,
                    verify_command,
                    _scheduled_stage_version(entry),
                    _stage_version(state, vstage),
                ),
                file=sys.stderr,
            )
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
            "verifyCommand": verify_command,
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


def _git_output(args: list[str]) -> str | None:
    """Run a read-only git command and return stripped stdout, or None.

    Any failure (git missing, not a repo, nonzero exit, timeout) degrades to
    ``None`` — doctor reports absence rather than crashing.
    """
    try:
        proc = subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=10,
        )
    except (OSError, ValueError, subprocess.TimeoutExpired):  # ValueError: undecodable output
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    return out or None


def _default_branch() -> str | None:
    """The repo's default branch: origin/HEAD target, else `main`/`master` if present."""
    ref = _git_output(["symbolic-ref", "--quiet", "refs/remotes/origin/HEAD"])
    if ref:
        return ref.rsplit("/", 1)[-1]
    for cand in ("main", "master"):
        if _git_output(["rev-parse", "--verify", "--quiet", f"refs/heads/{cand}"]) is not None:
            return cand
    return None


def _counts(specs_dir: Path) -> dict[str, int]:
    """Tally active/paused/abandoned pipelines across the specs tree."""
    tally = {"active": 0, "paused": 0, "abandoned": 0}
    for _name, _epic, state in _scan_features(specs_dir):
        status = state.get("pipelineStatus", "active")
        if isinstance(status, str) and status in tally:
            tally[status] += 1
    return tally


def _config_duplicate_keys(config_path: Path) -> list[str]:
    """Duplicate key names in the config file, for doctor's health report.

    Empty on a missing/unreadable/invalid config — those conditions are
    reported by doctor's ``configExists`` field, not here.
    """
    try:
        return load_json_with_duplicates(config_path)[1]
    except (OSError, ValueError, RecursionError):  # bad JSON, bad UTF-8, absurd nesting
        return []


def invalid_auto_verify_keys(config: dict) -> list[str]:
    """Return ``autoVerifyStages`` keys outside the verify-capable stage ids.

    An unknown/typo key (e.g. ``forge-1-prod``) would silently never take effect,
    turning an intended off-switch into a no-op. Surfacing it lets the navigator
    warn instead of failing quietly. Mirrors the schema's ``propertyNames.enum``.

    Sorted, not insertion-ordered: every diagnostic list must be
    sorted before rendering, so two configs that differ only in key order produce
    byte-identical output.
    """
    stages = config.get("autoVerifyStages")
    if not isinstance(stages, dict):
        return []
    return sorted(key for key in stages if key not in VERIFY_TOKEN_BY_STAGE)


def _default_schema_path() -> Path:
    """Return the bundled forge-config-schema.json path (sibling references/ dir).

    Resolved relative to this module so it works from any cwd. This module lives at
    ``<scripts>/forge_session/_common.py`` — one level deeper than the legacy shim —
    so it walks three parents to the bundle root, matching the shim's target.
    Overridable via the ``--schema`` flag (chiefly for tests).

    Returns:
        The Path to ``references/forge-config-schema.json`` at the bundle root.
    """
    return Path(__file__).resolve().parent.parent.parent / "references" / "forge-config-schema.json"


#: Verify token per exit stage. Extends the production map with the epic stage,
#: whose verify entry is recorded under ``forge-verify-epic``. The shim keeps a
#: byte-equal inline copy for its not-yet-extracted stage-exit routing body; this
#: is the package-side source the outcomes module reads (#279 P4.1).
_EXIT_VERIFY_TOKEN: Final[dict[str, str]] = {
    **VERIFY_TOKEN_BY_STAGE,
    "forge-0-epic": "epic",
}

#: The one message table the three upstream-verify gates read instead of each
#: phrasing "not verified" its own way — one canonical operator sentence per
#: ``VerifyStateCase``. ``{subject}`` is the feature (or epic member), ``{stage}``
#: the production stage whose verification this describes, ``{command}`` the
#: forge-verify retry invocation. ``auto-verify-pending`` is NOT looked up here at
#: runtime: that case routes through ``auto_pending_message()`` (which reads this
#: same ``AUTO_PENDING_DIAGNOSTIC`` and appends the version-advance clause when the
#: schedule predates the artifact), so the value is a *reference* to that shared
#: constant, not a copy that could drift. It stays in the table so the map is
#: complete: one entry per case, the invariant ``test_one_message_per_case`` pins.
VERIFY_STATE_MESSAGES: Final[dict[str, str]] = {
    "passed": "{subject}'s {stage} verification passed; proceed.",
    "findings-reported": (
        "{subject}'s {stage} verification reported unresolved blocking findings; "
        "apply and re-verify them — run {command}."
    ),
    "findings-applied": (
        "Fixes were applied to {subject}'s {stage} but nothing re-verified them; "
        "re-verification is still outstanding — run {command}."
    ),
    "auto-verify-pending": AUTO_PENDING_DIAGNOSTIC,
    "skipped": (
        "{subject}'s {stage} verification was explicitly skipped; "
        "run {command} to verify it after all."
    ),
    "never": "{subject}'s {stage} hasn't been verified yet — run {command}.",
}


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
    "PIPELINE_STATE_FILENAME",
    "MANIFEST_FILENAME",
    "PRODUCTION_STAGES",
    "VERIFY_TOKEN_BY_STAGE",
    "KNOWN_VERIFY_STATUSES",
    "_DONE_STATUSES",
    "AUTO_PENDING_DIAGNOSTIC",
    "_read_state",
    "_scan_features",
    "_stage_status",
    "next_stage",
    "_stage_version",
    "_verify_entry",
    "_scheduled_stage_version",
    "auto_pending_message",
    "verify_state",
    "auto_verify_for",
    "_parse_ts",
    "build_rows",
    "_git_output",
    "_default_branch",
    "_counts",
    "_config_duplicate_keys",
    "invalid_auto_verify_keys",
    "_default_schema_path",
    "_EXIT_VERIFY_TOKEN",
    "VERIFY_STATE_MESSAGES",
    "_resolve_feature_dir",
]
