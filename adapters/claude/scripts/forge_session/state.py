"""Write-side ``state-*`` verbs and their state-mutation machinery.

Every verb that MUTATES a feature's ``.pipeline-state.json`` (or an epic's
``.epic-state.json``) lives here, carved out of the ``forge-session.py`` monolith
(#279 P4.1): ``state-enter``, ``state-artifact``, ``state-complete``, ``state-skip``,
``state-branch``, ``state-note``, ``state-decision``, ``state-ecr`` and
``state-verify``, plus the fail-closed resolvers, the atomic writer, the verify-entry
builder and the one-line human printers they share. All verb names, flags, exit
codes and JSON shapes are FROZEN; ``tests/test_state_verbs.py`` and
``tests/test_auto_verify.py`` are the oracle.

This is a pure move. The write path keeps its atomic-write + commit discipline
(``_write_state``/``_commit_state`` from ``_common`` — a loop runner may crash
mid-write, so an interrupted write must never leave a partial state file). Shared
read-side primitives and the frozen domain constants come from ``_common`` (never
from the shim, which would be circular); the shim re-exports every symbol below so
the path-loaded test oracle resolves it unchanged.

3.10 baseline, Google-style docstrings, stdlib only — matching the conventions of
the monolith it was carved out of.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Final

from forge_session._common import (
    EPIC_STATE_FILENAME,
    FULL_GIT_HASH_RE,
    MANIFEST_FILENAME,
    PIPELINE_STATE_FILENAME,
    PRODUCTION_STAGES,
    SAFE_NAME_RE,
    VERIFY_RESULT_STATUSES,
    VERIFY_STAGES,
    VERIFY_TOKEN_BY_STAGE,
    UsageError,
    _commit_state,
    _DONE_STATUS,
    _now_iso,
    _SKIP_PROTECTED_PRIOR,
    _stage_version,
    _verify_entry,
)

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


def _assert_safe_name(name: str, label: str) -> None:
    """Reject a name that could steer a write outside ``{specsDir}/{name}``.

    Args:
        name: The bare name supplied on the command line.
        label: The flag to name in the error (e.g. ``--feature``).

    Raises:
        UsageError: Empty, absolute, separator-bearing, ``..``, or not a single
            kebab-case token (→ exit 2, nothing read or written).
    """
    if (
        not name
        or name == ".."
        or "/" in name
        or "\\" in name
        or os.path.isabs(name)
        or not SAFE_NAME_RE.match(name)
    ):
        raise UsageError(f"unsafe name {name!r} for {label}")


def _load_epic_state_for_write(
    specs_dir: Path, epic_name: str, epic: str | None
) -> tuple[Path, dict, int]:
    """Resolve an EPIC's ``.epic-state.json`` and its manifest revision, for mutation.

    The epic counterpart of ``_load_state_for_write``, and deliberately NOT a
    variant of it: epic verification is epic-scoped and must never resolve, read,
    create, or write a member's ``.pipeline-state.json`` (REQ-SEC-01). There is no
    fallback in either direction — an epic whose manifest is missing or whose
    identity disagrees is an error, not a feature lookup.

    Resolution is strict where the member resolver is tolerant: the name must be a
    safe single token, the joined path must stay inside ``specs_dir`` after symlink
    resolution, ``epic-manifest.json`` must exist, and the manifest's own ``epic``
    value must equal ``epic_name``. The revision comes from the manifest, which is
    the canonical artifact version for epic freshness — never a member's
    production-stage version. A legacy manifest with no ``revision`` is
    presented as logical ``1`` here, matching ``epic-manifest.py::load_manifest``,
    and its bytes are not rewritten.

    Args:
        specs_dir: The configured specs directory (``--specs-dir``).
        epic_name: The epic name — what ``--feature`` carries for this stage.
        epic: The ``--epic`` value, which must be absent or equal to ``epic_name``.

    Returns:
        A ``(state_path, state, revision)`` tuple. ``state`` is the lazily created
        minimal shell (``epic`` + ``stages``) when no epic state exists yet.

    Raises:
        UsageError: Conflicting ``--feature``/``--epic``, unsafe name, containment
            escape, missing/unparseable/non-object/identity-mismatched manifest,
            invalid manifest revision, or an unparseable/non-object epic state or
            ``stages`` value (→ exit 2, nothing written).
    """
    if epic is not None and epic != epic_name:
        raise UsageError(
            f"--stage forge-0-epic writes epic-scoped state, so --feature names the "
            f"epic: --feature {epic_name!r} and --epic {epic!r} disagree. Drop --epic "
            f"or make it match."
        )
    _assert_safe_name(epic_name, "--feature")
    base_real = specs_dir.resolve()
    epic_dir = (base_real / epic_name).resolve()
    if epic_dir != base_real and base_real not in epic_dir.parents:
        raise UsageError(
            f"resolved epic path escapes the specs dir: {specs_dir / epic_name}"
        )

    manifest_path = epic_dir / MANIFEST_FILENAME
    if not manifest_path.is_file():
        raise UsageError(
            f"no epic manifest at {manifest_path} — --stage forge-0-epic verifies an "
            f"epic, and {epic_name!r} is not one. Nothing was written."
        )
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise UsageError(f"{manifest_path} is not valid JSON ({exc})") from exc
    if not isinstance(manifest, dict):
        raise UsageError(f"{manifest_path} is not a JSON object")
    if manifest.get("epic") != epic_name:
        raise UsageError(
            f"{manifest_path} declares epic {manifest.get('epic')!r}, not "
            f"{epic_name!r}; refusing to write verification state for a mismatched "
            f"epic identity"
        )
    revision = _require_positive_int(
        manifest.get("revision", 1), f"{epic_name}/{MANIFEST_FILENAME} revision"
    )

    state_path = epic_dir / EPIC_STATE_FILENAME
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
        recorded = state.get("epic")
        if recorded is not None and recorded != epic_name:
            raise UsageError(
                f"{state_path} records epic {recorded!r}, not {epic_name!r}; "
                f"refusing to overwrite it."
            )
        stages = state.get("stages")
        if stages is not None and not isinstance(stages, dict):
            raise UsageError(
                f"{state_path} has a non-object 'stages' value ({type(stages).__name__}); "
                f"refusing to overwrite it."
            )
    else:
        state = {}
    # Seed the minimal state shape in its documented key order. ``updatedAt`` is
    # a placeholder: every caller stamps it through ``_commit_state`` immediately
    # before the single atomic replacement, so the null never reaches disk.
    state.setdefault("epic", epic_name)
    state.setdefault("updatedAt", None)
    state.setdefault("stages", {})
    return state_path, state, revision


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
        UsageError: A ``--path`` that is empty, absolute, ``..``-bearing,
            control-character-bearing, or escaping the feature directory; an
            unknown feature directory, an unparseable state file, or a failed
            atomic write (→ exit 2).
    """
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    # Containment is checked against the resolved feature dir, which only the load
    # produces; every path is validated before any of them is appended, so a
    # rejected value in a repeated --path list leaves the file untouched.
    target_dir = state_path.parent
    for path in paths:
        _validated_findings_file(path, target_dir, label="--path")
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
       ``stageEntry``'s ``required: ["status"]``) at exit 0. The value must be a
       full 40-hex object hash (REQ-STATE-01), checked before anything is loaded.
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
            else set commitHash to None (Commit 1). Full 40-hex only on a new
            write — an abbreviation is rejected rather than expanded.
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
            ``--version`` below 1, a short or non-hex ``--commit-hash``, a
            ``--commit-hash`` follow-up against a stage that is not complete, an
            unknown feature directory, an unparseable state file, or a failed
            atomic write (→ exit 2).
    """
    if resumable and status == "complete":
        raise UsageError(
            "--resumable implies --status in-progress; do not pass --status complete"
        )
    # The write path must not accept a version the read path refuses; checked before
    # the state file is loaded for mutation, so a rejection touches nothing.
    _require_positive_int(version, "--version")
    if commit_hash is not None:
        # Branch 1's first act: full 40-hex only, validated BEFORE the
        # state file is loaded for mutation and long before _commit_state. Legacy
        # short hashes already recorded in state keep loading unmigrated.
        _assert_full_commit_hash(commit_hash)
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


def cmd_state_skip(feature: str, stage: str, specs_dir: Path, epic: str | None) -> dict:
    """Record a deliberate skip of the documentation stage (#197).

    Writes a REPLACEMENT ``stages.forge-6-docs`` entry ``{"status": "skipped",
    "skippedAt": …, "commitHash": null}`` — the honest terminal for a feature
    that ships without architecture docs. ``skipped`` counts as done for
    next-stage selection (``_DONE_STATUSES``), so the pipeline reads
    ``complete: true`` / ``nextStage: null`` without any stage claiming
    artifacts it never produced.

    Scoped to ``forge-6-docs`` on purpose: a skipped PRD or specs stage is a
    different and much worse proposition, so both the CLI (``choices``) and this
    callable refuse any other stage.

    The skip must not DESTROY a record of docs that exist: a prior entry whose
    ``artifacts`` list is non-empty is refused. A prior ``complete`` entry with
    no recorded artifacts is exactly the dishonest workaround this verb replaces
    (``state-complete`` with no ``--artifact``), so it may be corrected to
    ``skipped`` — that is the sanctioned migration path for such state.

    Args:
        feature: Feature name.
        stage: Must be ``"forge-6-docs"`` (kept explicit so the scoping shows up
            in every call site).
        specs_dir: Specs directory.
        epic: Owning epic name, or None.

    Returns:
        The mutated state dict (for the --json echo).

    Raises:
        UsageError: A stage other than forge-6-docs, a prior entry recording
            artifacts, an unknown feature directory, an unparseable state file,
            or a failed atomic write (→ exit 2).
    """
    if stage != "forge-6-docs":
        raise UsageError(
            f"state-skip is scoped to forge-6-docs; a skipped {stage} is not a "
            "representable pipeline state"
        )
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    prior = state.get("stages", {}).get(stage)
    if isinstance(prior, dict) and prior.get("artifacts"):
        raise UsageError(
            f"{stage} already records {len(prior['artifacts'])} artifact(s) "
            f"(status: {prior.get('status')!r}); skipping now would erase the "
            "record that docs exist. Re-run forge-6-docs to refresh them instead."
        )
    state.setdefault("stages", {})[stage] = {
        "status": "skipped",
        "skippedAt": _now_iso(),
        "commitHash": None,
    }
    return _commit_state(state_path, state)


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


def _require_positive_int(value: object, label: str) -> int:
    """Return ``value`` as a positive int, or raise ``UsageError``.

    ``bool`` is rejected explicitly: it is an ``int`` subclass, so ``True`` would
    otherwise sail through as version 1 and record a freshness ledger entry for an
    artifact revision that never existed.

    Args:
        value: The candidate revision/version.
        label: The flag or field name to name in the error.

    Returns:
        The validated positive integer.

    Raises:
        UsageError: Not an int, a bool, or below 1 (→ exit 2).
    """
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise UsageError(f"{label} must be a positive integer; got {value!r}")
    return value


def _validated_findings_file(
    value: str, target_dir: Path, label: str = "--findings-file"
) -> str:
    """Return ``value`` if it is a safe relative path inside ``target_dir``.

    ``findingsFile`` is defined as relative to the
    feature directory, and downstream consumers (forge-fix selecting the report)
    follow the stored value verbatim. So it gets the same fail-closed containment
    treatment as the write target itself (REQ-SEC-01): an absolute path, a ``..``
    segment, a NUL/control character, or a symlinked escape is rejected BEFORE any
    mutation rather than persisted for a later reader to resolve.

    The same containment contract governs every stored path a caller asserts is
    inside the feature directory, so the flag being validated is a parameter: the
    diagnostic must name the flag the user actually passed.

    Args:
        value: The candidate path, as supplied on the command line.
        target_dir: The resolved feature (or epic) directory it must sit inside.
        label: The flag to name in the error.

    Returns:
        The value unchanged, once validated.

    Raises:
        UsageError: Empty, absolute, ``..``-bearing, control-character-bearing, or
            escaping the target directory (→ exit 2).
    """
    if not value:
        raise UsageError(f"{label} must not be empty")
    bad = next((ch for ch in value if ord(ch) < 32 or ord(ch) == 127), None)
    if bad is not None:
        raise UsageError(
            f"{label} contains a control character ({bad!r}); "
            f"expected a plain relative path"
        )
    candidate = Path(value)
    if candidate.is_absolute():
        raise UsageError(
            f"{label} {value!r} is absolute; it must be relative to the "
            f"feature directory ({target_dir})"
        )
    if ".." in candidate.parts:
        raise UsageError(
            f"{label} {value!r} contains a '..' segment; it must stay inside "
            f"the feature directory ({target_dir})"
        )
    root = target_dir.resolve()
    resolved = (target_dir / candidate).resolve()
    if resolved == root or root not in resolved.parents:
        raise UsageError(
            f"{label} {value!r} escapes the feature directory ({target_dir}); "
            f"refusing to record it"
        )
    return value


def _current_artifact_version(state: dict, stage: str) -> int:
    """Return the artifact revision a verify result is being recorded against.

    For a feature target that is the selected production stage's ``version``.
    Only the statuses that consume it resolve it: `passed` and
    `findings-reported` write it into the freshness ledger, and
    `auto-verify-pending` writes it as the revision the debt is owed on.
    `skipped` and `findings-applied` never read it and skip the lookup, so both
    stay recordable on a completed stage with no recorded ``version``.

    Args:
        state: The loaded state document.
        stage: The production stage the verify entry serves.

    Returns:
        The stage's current positive-integer version.

    Raises:
        UsageError: The stage has no recorded (or no valid) ``version`` (→ exit 2).
    """
    version = _stage_version(state, stage)
    if version is None:
        raise UsageError(
            f"{stage} has no recorded version in this feature's state, so there is no "
            f"artifact revision to verify against; run state-complete for {stage} first"
        )
    return _require_positive_int(version, f"{stage}.version")


def _assert_full_commit_hash(commit_hash: object) -> None:
    """Reject a ``--commit-hash`` that is not exactly 40 hexadecimal characters.

    REQ-STATE-01 constrains WRITES, not reads. New provenance is a
    full ``git rev-parse HEAD`` object hash; an abbreviation is rejected rather than
    expanded, because expanding one would mean shelling out to Git from a script
    whose whole contract is bounded local file reads. Caller case is preserved —
    the regex accepts either case and nothing normalizes it.

    Nothing constrains the schema, so a legacy short hash already recorded in state
    keeps loading through ``_read_state``, ``_load_state_for_write``, the manifest
    status readers, the navigator, and stage exit unmigrated (REQ-STATE-02).

    Args:
        commit_hash: The supplied value, typed loosely so a non-string reaching the
            callable in-process is refused here rather than at serialization time.

    Raises:
        UsageError: The value is not a 40-character hex string (→ exit 2, before
            any load-for-mutation and always before ``_commit_state``).
    """
    if isinstance(commit_hash, str) and FULL_GIT_HASH_RE.fullmatch(commit_hash):
        return
    raise UsageError(
        f"--commit-hash must be the full 40-character Git object hash "
        f"(`git rev-parse HEAD`); got {commit_hash!r}. An abbreviation is rejected "
        f"rather than expanded. Nothing was written."
    )


def _load_verify_target(
    specs_dir: Path, feature: str, epic: str | None, is_epic_target: bool
) -> tuple[Path, dict, int | None]:
    """Resolve the state document ``state-verify`` will mutate — epic or feature.

    An epic target NEVER falls back to the member writer, and a member target never
    reaches the epic root: the two resolvers are disjoint (REQ-SEC-01). Both result
    mode and commit-2 mode go through here, so neither can drift onto the other's
    resolver.

    Args:
        specs_dir: The configured specs directory.
        feature: The feature name, or the epic name for an epic target.
        epic: The owning epic for a member, else None.
        is_epic_target: True when ``--stage forge-0-epic`` selected the epic root.

    Returns:
        ``(state_path, state, revision)``. ``revision`` is the epic's manifest
        revision for an epic target, and None for a feature target (whose artifact
        version is read per-stage out of its own state).

    Raises:
        UsageError: Any resolution or load failure (→ exit 2, nothing written).
    """
    if is_epic_target:
        return _load_epic_state_for_write(specs_dir, feature, epic)
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    return state_path, state, None


def _verify_result_entry(
    status: str,
    prior: dict,
    current: int | None,
    findings_file: str | None,
    findings_count: int | None,
    now: str,
) -> dict:
    """Build the replacement ``forge-verify-*`` entry for one result transition.

    Each status REPLACES the entry rather than patching it, which is what makes the
    the "clear …" rules exact: a terminal write cannot leave a stale
    ``scheduledAt``/``scheduledStageVersion`` behind, and the keys are DELETED
    rather than nulled (``VerifyEntry`` is ``total=False``, so absent means "not
    scheduled" while present-but-null would be malformed). ``findings-applied`` is
    the one status that carries prior state forward — the report metadata — and it
    deliberately writes no ``verifiedStageVersion``: fixes landed, nothing
    re-verified them, so freshness stays unresolved until a later ``passed``.
    ``passed`` may record NEW attached-report metadata of its own (a clean report,
    an advisory-only report, or the escalation-acceptance rules in
    ``cmd_state_verify``).

    Args:
        status: The validated result status.
        prior: The existing entry (``{}`` when absent).
        current: The current artifact revision, or None for ``skipped`` and
            ``findings-applied`` (which never consume it).
        findings_file: Validated relative report path, when supplied.
        findings_count: Validated non-negative count, when supplied.
        now: The shared ISO-8601 timestamp for this write.

    Returns:
        The complete new entry dict.
    """
    if status == "auto-verify-pending":
        return {
            "status": status,
            "scheduledAt": now,
            "scheduledStageVersion": current,
            "commitHash": None,
        }
    if status == "passed":
        entry: dict = {"status": status}
        if findings_file is not None:
            # An attached clean/advisory report, or residual findings the user
            # explicitly accepted at the escalation gate, resolves as `passed`
            # so it never routes to forge-fix while the audit artifact stays
            # attached. A bare zero count records no report keys, preserving the
            # legacy plain "verified clean" shape.
            entry["findingsFile"] = findings_file
            entry["findingsCount"] = findings_count
        entry["verifiedAt"] = now
        entry["verifiedStageVersion"] = current
        entry["commitHash"] = None
        return entry
    if status == "findings-reported":
        return {
            "status": status,
            "findingsFile": findings_file,
            "findingsCount": findings_count,
            "verifiedAt": now,
            "verifiedStageVersion": current,
            "commitHash": None,
        }
    if status == "findings-applied":
        entry: dict = {"status": status}
        for key in ("findingsFile", "findingsCount"):
            if key in prior:
                entry[key] = prior[key]
        entry["fixedAt"] = now
        entry["commitHash"] = None
        return entry
    return {"status": status, "commitHash": None}   # skipped


def cmd_state_verify(
    feature: str,
    stage: str,
    specs_dir: Path,
    epic: str | None,
    status: str | None = None,
    findings_file: str | None = None,
    findings_count: int | None = None,
    verified_stage_version: int | None = None,
    commit_hash: str | None = None,
) -> dict:
    """Write one verify result transition or one provenance follow-up.

    Args:
        feature: The feature name, or the EPIC name when `stage == "forge-0-epic"`.
            Resolved through the same path-safety and containment rules as every
            other state write.
        stage: The production stage this verify entry serves — one of
            `VERIFY_MODE_TO_STAGE`'s values, or `"forge-0-epic"` for an epic-target
            write. Selects `stages["forge-verify-{suffix}"]`.
        specs_dir: Root of the specs tree, as configured by `specsDir`.
        epic: Epic name when `feature` is a member, else None. REQUIRED for members
            so the bare name is never resolved ambiguously. For
            `stage == "forge-0-epic"` it must be absent or equal to `feature`.
        status: Result mode. Mutually exclusive with `commit_hash`. Each status
            admits only the metadata below; everything else is refused before any
            write, so a contradictory call never lands a partial entry:

            - `passed` — REQUIRES `verified_stage_version`. MAY carry an attached
              report (`findings_file` + `findings_count` together, count >= 0) in
              three protocol cases: a CLEAN zero-finding round report (a fix
              pass's re-verify — valid audit evidence that lets the stage advance
              instead of stranding at `findings-applied`, #237), an ADVISORY-ONLY
              report (no blocking `error`/`gap` findings, count >= 1), and
              residual findings the user explicitly ACCEPTED at the round-ledger
              escalation (recorded first as a `state-decision`; see "Escalation"
              in stage-exit-protocol.md). In every case the stage resolves
              without routing to forge-fix and the report stays attached. Half a
              pairing is refused: a file without a count, or a positive count
              without a file. A bare `passed` (neither flag) is also accepted and
              records the report-free clean shape. Unaccepted blocking findings
              belong to `findings-reported`.
            - `findings-reported` — REQUIRES all three of `verified_stage_version`,
              `findings_file`, and a non-negative `findings_count`.
            - `findings-applied` — REFUSES `verified_stage_version`. Applying fixes
              is not verifying them, so this status deliberately CLEARS the recorded
              freshness and leaves the stage's verification outstanding until a later
              `passed` records a revision.
            - `skipped` and `auto-verify-pending` — accept none of the three.

            `passed` and `findings-reported` additionally refuse a
            `verified_stage_version` that is stale against the served stage's current
            version. The persisted shape is `references/pipeline-state-schema.json`.
        findings_file: Path to the findings document, relative to and contained by
            the resolved feature/epic directory. Required by `findings-reported`,
            optional on `passed` (the attached-report cases above); rejected when
            absolute, containing `..`, or carrying NUL/control characters
            (REQ-SEC-01).
        findings_count: Number of findings in `findings_file`. Required alongside it.
        verified_stage_version: The served stage's `version` at verification time,
            feeding the navigator's freshness ledger. Cleared by
            `findings-applied`, which deliberately does not claim freshness.
        commit_hash: Commit-2 mode. Full 40-hex only, validated by
            `FULL_GIT_HASH_RE.fullmatch`; abbreviations are rejected rather than
            expanded. Mutually exclusive with `status`.

    Returns:
        The emitted JSON result: the written verify entry plus the resolved target
        path, so the caller can report what landed without re-reading state.

    Raises:
        UsageError: Mixed modes, invalid metadata, invalid hash, missing entry,
            unsafe/ambiguous target, or atomic write failure.
    """
    # --- Mode exclusivity, before anything is resolved or loaded. -------------
    if status is None and commit_hash is None:
        raise UsageError(
            "state-verify needs exactly one mode: --status <result> to record a "
            "verification transition, or --commit-hash <40-hex> to record Commit-2 "
            "provenance for an existing entry"
        )
    if status is not None and commit_hash is not None:
        raise UsageError(
            "--status and --commit-hash are mutually exclusive: a result write "
            "records commitHash null (Commit 1), and the hash lands in a separate "
            "commit-2 call"
        )
    if commit_hash is not None:
        # Commit-2 carries provenance for an entry that ALREADY exists, so every
        # result field must be absent: a hash arriving next to findings metadata
        # means the caller conflated the two writes.
        for label, value in (
            ("--findings-file", findings_file),
            ("--findings-count", findings_count),
            ("--verified-stage-version", verified_stage_version),
        ):
            if value is not None:
                raise UsageError(
                    f"--commit-hash records provenance for an existing entry and "
                    f"changes only its commitHash, so it does not accept {label}. "
                    f"Record the result with --status first, commit, then re-run "
                    f"with --commit-hash alone."
                )
        _assert_full_commit_hash(commit_hash)
    elif status not in VERIFY_RESULT_STATUSES:
        known = ", ".join(VERIFY_RESULT_STATUSES)
        raise UsageError(f"unknown --status {status!r}; expected one of {known}")

    # --- Target selection: epic before the token map. --------------
    is_epic_target = stage == "forge-0-epic"
    if is_epic_target:
        verify_key = "forge-verify-epic"
    else:
        token = VERIFY_TOKEN_BY_STAGE.get(stage)
        if token is None:
            raise UsageError(
                f"{stage} has no verification token, so it has no forge-verify-* entry "
                f"to write; expected one of {', '.join(VERIFY_STAGES)}"
            )
        verify_key = f"forge-verify-{token}"

    # --- Commit-2 provenance mode. ---------------------------------
    # Commit 1 recorded the result with `commitHash: null`; this second, targeted
    # write records the hash of THAT commit. Nothing here invokes Git, rewrites
    # history, or amends — the two commits stay two commits (REQ-STATE-04).
    if commit_hash is not None:
        state_path, state, _ = _load_verify_target(
            specs_dir, feature, epic, is_epic_target
        )
        entry = _verify_entry(state, verify_key)
        if not entry:
            raise UsageError(
                f"--commit-hash records provenance for an existing {verify_key} "
                f"entry, and {feature} has none. Record the verification result "
                f"with --status first, commit it, then re-run with --commit-hash."
            )
        # In place, so status, findings metadata, scheduling metadata, timestamps
        # and versions are all left exactly as Commit 1 wrote them.
        entry["commitHash"] = commit_hash
        written = _commit_state(state_path, state)
        return {
            "feature": feature,
            "stage": stage,
            "verifyKey": verify_key,
            "statePath": str(state_path),
            "entry": entry,
            "updatedAt": written["updatedAt"],
        }

    # --- Metadata validation that needs no state. ------------------
    if verified_stage_version is not None:
        _require_positive_int(verified_stage_version, "--verified-stage-version")
    if findings_count is not None and (
        isinstance(findings_count, bool) or not isinstance(findings_count, int)
    ):
        raise UsageError(f"--findings-count must be an integer; got {findings_count!r}")

    if status in ("auto-verify-pending", "skipped"):
        for label, value in (
            ("--findings-file", findings_file),
            ("--findings-count", findings_count),
            ("--verified-stage-version", verified_stage_version),
        ):
            if value is not None:
                raise UsageError(f"--status {status} does not accept {label}")
    elif status == "passed":
        if findings_file is not None and findings_count is None:
            raise UsageError(
                "--status passed with --findings-file requires --findings-count N "
                "(zero for a clean report, or the number of advisory/residual "
                "findings it lists)"
            )
        if findings_count is not None:
            if findings_count < 0:
                raise UsageError(
                    f"--findings-count must not be negative; got {findings_count!r}"
                )
            if findings_count > 0 and findings_file is None:
                raise UsageError(
                    f"--status passed with --findings-count {findings_count} requires "
                    f"--findings-file <advisory report>: a positive count with no "
                    f"report to read is unrecoverable. Blocking findings belong to "
                    f"--status findings-reported instead."
                )
        if verified_stage_version is None:
            raise UsageError(
                "--status passed requires --verified-stage-version <current version>"
            )
    elif status == "findings-reported":
        if verified_stage_version is None:
            raise UsageError(
                "--status findings-reported requires --verified-stage-version "
                "<current version>"
            )
        if findings_file is None:
            raise UsageError(
                "--status findings-reported requires --findings-file <path relative "
                "to the feature directory>"
            )
        if findings_count is None:
            raise UsageError("--status findings-reported requires --findings-count N")
        if findings_count < 0:
            raise UsageError(
                f"--findings-count must not be negative; got {findings_count!r}"
            )
    elif verified_stage_version is not None:   # findings-applied
        raise UsageError(
            "--status findings-applied does not accept --verified-stage-version: "
            "applying fixes deliberately CLEARS freshness, so only a later "
            "--status passed may record a verified revision"
        )

    state_path, state, epic_revision = _load_verify_target(
        specs_dir, feature, epic, is_epic_target
    )
    target_dir = state_path.parent
    if findings_file is not None:
        _validated_findings_file(findings_file, target_dir)

    if status in ("skipped", "findings-applied"):
        # Neither status consumes the artifact revision: `skipped` records no
        # freshness, and `findings-applied` deliberately clears it (the entry is
        # built from the prior report plus `fixedAt`). Resolving it anyway would
        # make both unrecordable on a completed stage whose `version` was never
        # written — exactly the state that needs the recovery path (#202).
        current = None
    elif is_epic_target:
        # The epic's artifact revision is the manifest revision — never a member's
        # production-stage version.
        current = epic_revision
    else:
        current = _current_artifact_version(state, stage)
    if status in ("passed", "findings-reported") and verified_stage_version != current:
        at = (
            f"{feature}'s manifest is at revision {current}"
            if is_epic_target
            else f"{stage} is at version {current}"
        )
        raise UsageError(
            f"--verified-stage-version {verified_stage_version} is stale: {at}. "
            f"Re-run verification against the current artifact."
        )

    prior = _verify_entry(state, verify_key)
    if status == "skipped" and prior.get("status") in _SKIP_PROTECTED_PRIOR:
        # The #203 demotion trap: `skipped` over a complete-for-orchestration
        # status silently dropped the member from its epic rollup and re-blocked
        # every dependent. Fail closed; a deferral needs no write at all.
        raise UsageError(
            f"--status skipped would demote {verify_key} from "
            f"{prior.get('status')!r}: that status counts as resolved (and, for an "
            f"epic member, complete-for-orchestration), so replacing it with "
            f"skipped would drop the member from its epic rollup and re-block its "
            f"dependents. A deferral needs no write — the recorded result already "
            f"stands. Re-run verification to refresh it, or record --status passed "
            f"(with the report attached) to accept residual findings. "
            f"Nothing was written."
        )
    if status == "auto-verify-pending" and prior.get("status") == "findings-reported":
        # `_verify_result_entry` REPLACES the entry, so scheduling over a report
        # for the current revision would delete its `findingsFile`/`findingsCount`
        # and break the later `findings-applied` precondition (REQ-EXIT-04's
        # forbidden clobber, reached through the CLI instead of a branch exit).
        # A report against a since-revised artifact is superseded normally.
        reported = prior.get("verifiedStageVersion")
        if (
            isinstance(reported, int)
            and not isinstance(reported, bool)
            and current is not None
            and reported == current
        ):
            raise UsageError(
                f"--status auto-verify-pending would replace {verify_key}'s "
                f"findings-reported entry for the current revision and delete its "
                f"report metadata ({prior.get('findingsFile')!r}, "
                f"findingsCount {prior.get('findingsCount')!r}). Apply the report "
                f"via forge-fix (--status findings-applied) or re-verify to a "
                f"terminal status; scheduling is valid only after the artifact "
                f"is revised."
            )
    if status == "findings-applied":
        if prior.get("status") not in ("findings-reported", "findings-applied"):
            raise UsageError(
                f"--status findings-applied requires an existing {verify_key} entry "
                f"with status findings-reported (or findings-applied); found "
                f"{prior.get('status')!r}"
            )
        for label, key, supplied in (
            ("--findings-file", "findingsFile", findings_file),
            ("--findings-count", "findingsCount", findings_count),
        ):
            if supplied is not None and supplied != prior.get(key):
                raise UsageError(
                    f"{label} {supplied!r} does not match the recorded report "
                    f"({key}: {prior.get(key)!r}); fix the value or omit the flag"
                )

    entry = _verify_result_entry(
        status, prior, current, findings_file, findings_count, _now_iso()
    )
    state.setdefault("stages", {})[verify_key] = entry
    written = _commit_state(state_path, state)
    return {
        "feature": feature,
        "stage": stage,
        "verifyKey": verify_key,
        "statePath": str(state_path),
        "entry": entry,
        "updatedAt": written["updatedAt"],
    }


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


def _print_state_skip(state: dict, stage: str) -> None:
    """Print the one-line human summary for `state-skip`."""
    print(
        f"recorded {stage} as skipped for {state['feature']} "
        "(deliberate — no docs claimed)"
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


def _print_state_verify(result: dict, commit_hash: str | None = None) -> None:
    """Print the one-line human summary for `state-verify` (one per mode).

    Takes the verb's RESULT dict (entry + resolved path), not a state document —
    `state-verify` is the one verb whose echo is the written entry rather than the
    whole file. Commit-2 mode gets its own line: reporting the untouched status
    would read as if the result had just been re-written.
    """
    entry = result["entry"]
    if commit_hash is not None:
        print(f"recorded {result['verifyKey']} commitHash: {commit_hash}")
        return
    detail = ""
    if entry.get("findingsFile"):
        detail = f" ({entry.get('findingsCount')} in {entry['findingsFile']})"
    elif entry.get("scheduledStageVersion") is not None:
        detail = f" (scheduled at v{entry['scheduledStageVersion']})"
    elif entry.get("verifiedStageVersion") is not None:
        detail = f" (v{entry['verifiedStageVersion']})"
    print(
        f"recorded {result['verifyKey']} = {entry['status']} for "
        f"{result['feature']}{detail}"
    )


def _print_state_ecr(state: dict) -> None:
    """Print the one-line human summary for `state-ecr` (the item appended)."""
    item = state["epicChangeRequests"][-1]
    blocks = "true" if item["blocksCurrent"] else "false"
    print(
        f"epic change request recorded ({item['kind']} → {item['target']}, "
        f"blocksCurrent={blocks})"
    )
