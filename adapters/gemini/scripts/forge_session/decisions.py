"""The ``decision-*`` verbs: the ``forge-decisions.json`` reader/writer.

Carved out of the ``forge-session.py`` monolith (#279 P4.1). This module owns the
one persistent artifact the loop-recovery feature adds — ``forge-decisions.json`` —
and the three verbs that read and write it (``decision-record``, ``decision-list``,
``decision-apply``). It is a pure move: verb names, flags, exit codes, and JSON
shapes are frozen, and the shim re-exports every symbol here so path-loaded tests
resolve them unchanged.

Every shared primitive it needs (``UsageError``, ``_now_iso``, ``_commit_state``,
``resolve_loop_runner``) is imported FROM ``forge_session._common`` — never from the
shim, which would be a circular import. Stdlib only, 3.10 baseline, Google-style
docstrings, matching the conventions of the monolith it was carved out of.
"""

from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Final

from forge_session._common import (
    UsageError,
    _commit_state,
    _now_iso,
    resolve_loop_runner,
)

#: The one persistent artifact this feature adds; only decision-* verbs write it.
DECISIONS_FILENAME: Final[str] = "forge-decisions.json"
#: Enum-locked at references/forge-decisions-schema.json; a bump is a breaking change.
DECISIONS_SCHEMA_VERSION: Final[str] = "1"


def _resolve_decisions_path(
    backlog_dir: Path,
    state_dir: str | None,
    config_path: Path,
    schema_path: Path,
) -> Path:
    """Resolve `{backlog_dir}/{stateDir}/forge-decisions.json`.

    When ``state_dir`` is None, ``stateDir`` is taken from the effective loopRunner
    config (schema default ``.rauf``) via ``resolve_loop_runner`` — the same resolver
    the loop itself uses — so the record lands beside the runner's own state and is
    covered by the ``**/.rauf/*`` ignore rule with zero ``.gitignore`` edits.

    Args:
        backlog_dir: The resolved backlog directory (e.g. ``specs/loop-recovery``).
        state_dir: An explicit state-dir name, or None to resolve from config.
        config_path: ``forge.config.json`` path (``_load_config`` tolerates absent).
        schema_path: ``forge-config-schema.json`` path (source of the default).

    Returns:
        The resolved path to the decision record (its parent may not yet exist).
    """
    if state_dir is None:
        resolved = resolve_loop_runner(config_path, schema_path)
        state_dir = str(resolved["stateDir"])
    return backlog_dir / state_dir / DECISIONS_FILENAME


def _read_decisions_for_write(path: Path, feature: str) -> dict:
    """Load the decisions document for mutation, or seed a fresh one on first write.

    A MISSING file is the first-write case → return a fresh skeleton whose parent
    dir is created on commit. An UNPARSEABLE or non-object existing file is a HARD
    failure (exit 2) — a write path must not inherit ``_read_state``'s corrupt→{}
    tolerance, which would atomically replace a recoverable record with a
    near-empty one.

    Args:
        path: The resolved decision-record path.
        feature: The feature label to stamp on a first write (backlog dir basename).

    Returns:
        The loaded (or freshly-seeded) decisions document, ready to mutate.

    Raises:
        UsageError: The existing file is unreadable/unparseable or not a JSON object.
    """
    if not path.exists():
        return {
            "schemaVersion": DECISIONS_SCHEMA_VERSION,
            "feature": feature,
            "createdAt": _now_iso(),
            "decisions": [],
        }
    try:
        parsed = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"unparseable decision record at {path}: {exc}") from exc
    if not isinstance(parsed, dict):
        raise UsageError(f"decision record at {path} is not a JSON object")
    return parsed


def _new_decision_entry(
    item_id: str,
    question: str,
    answer: str | None,
    deferred: bool,
    cluster_id: str | None,
    actor: str,
) -> dict:
    """Build one decision entry conforming to references/forge-decisions-schema.json.

    Args:
        item_id: The backlog item the decision answers.
        question: The needs-human question text (original text on a deferral).
        answer: The operator's answer, or None for a deferral.
        deferred: True iff this is a deferral / cancel-early entry.
        cluster_id: Shared clusterId for a consolidated decision, or None.
        actor: The session/actor label for ``recordedBy`` (never user identity).

    Returns:
        A dict carrying all eight required fields (``appliedAt``/``appliedBy`` null),
        plus ``clusterId`` when supplied.
    """
    entry: dict = {
        "itemId": item_id,
        "question": question,
        "answer": answer,
        "deferred": deferred,
        "decidedAt": _now_iso(),
        "recordedBy": actor,
        "appliedAt": None,
        "appliedBy": None,
    }
    if cluster_id is not None:
        entry["clusterId"] = cluster_id
    return entry


def _default_actor() -> str:
    """Return the default recordedBy/appliedBy label: ``forge-5-loop@<host>``.

    The host segment is a machine label, not a user identity (REQ-SEC-01).
    """
    return f"forge-5-loop@{socket.gethostname()}"


def _unapplied_decisions(decisions: list[dict]) -> list[dict]:
    """Return the latest entry per itemId whose ``appliedAt`` is None (REQ-DEC-05).

    Walks entries in stored (append) order keeping the LAST entry seen per itemId,
    then keeps only those still unapplied. Deferrals (never applied) are included
    (REQ-DEC-06); an item whose latest entry is applied drops out; a later
    per-item entry supersedes an earlier consolidated (clusterId) one for that item
    only (REQ-DEC-07). Output is sorted by itemId for deterministic reporting.

    Args:
        decisions: The document's ``decisions`` array, in stored order.

    Returns:
        The unapplied entries, one per item, sorted by ``itemId``.
    """
    latest: dict[str, dict] = {}
    for entry in decisions:
        latest[entry["itemId"]] = entry
    return [
        entry for _item_id, entry in sorted(latest.items())
        if entry.get("appliedAt") is None
    ]


def cmd_decision_record(
    backlog_dir: Path,
    item_ids: list[str],
    question: str,
    answer: str | None,
    deferred: bool,
    cluster_id: str | None,
    actor: str,
    state_dir: str | None,
    config_path: Path,
    schema_path: Path,
) -> dict:
    """Append one needs-human decision entry per ``--item`` (append-only).

    Records a decision at the moment it is collected (REQ-DEC-01), on EVERY branch:
    an answered decision (``--answer``), and a deferral or cancel-early
    (``--deferred`` → ``answer: null``, REQ-DEC-06). With ``--cluster`` the per-item
    entries of ONE consolidated decision share a ``clusterId`` (REQ-CLU-04) yet stay
    independently re-decidable (REQ-DEC-07). The file and its
    ``schemaVersion``/``feature``/``createdAt`` stamp are created on first write.
    Existing entries are never mutated (append-only).

    Args:
        backlog_dir: The resolved backlog directory; its basename stamps ``feature``.
        item_ids: One or more backlog item ids; one entry is appended per id.
        question: The needs-human question text (original text on a deferral).
        answer: The operator's answer, or None for a deferral.
        deferred: True iff this is a deferral / cancel-early entry.
        cluster_id: Shared ``clusterId`` for a consolidated decision, or None.
        actor: Session/actor label for ``recordedBy`` (never user identity).
        state_dir: State-dir name override, or None to resolve from config.
        config_path: ``forge.config.json`` path (for the stateDir default).
        schema_path: ``forge-config-schema.json`` path (source of the default).

    Returns:
        The mutated decisions document (for the ``--json`` echo).

    Raises:
        UsageError: Missing backlog dir; both/neither of ``--answer``/``--deferred``;
            an unparseable existing record; or a failed atomic write (→ exit 2).
    """
    # Defense in depth: the argparse mutually-exclusive group rejects both/neither
    # first, but a direct call must fail the same way. Valid states are exactly
    # (answered, not deferred) or (deferred, no answer).
    if deferred == (answer is not None):
        raise UsageError("exactly one of --answer or --deferred is required")
    if not backlog_dir.is_dir():
        raise UsageError(f"no backlog directory at {backlog_dir}")

    path = _resolve_decisions_path(backlog_dir, state_dir, config_path, schema_path)
    doc = _read_decisions_for_write(path, backlog_dir.resolve().name)
    for item_id in item_ids:
        doc["decisions"].append(
            _new_decision_entry(item_id, question, answer, deferred, cluster_id, actor)
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    return _commit_state(path, doc)


def cmd_decision_list(
    backlog_dir: Path,
    unapplied: bool,
    state_dir: str | None,
    config_path: Path,
    schema_path: Path,
) -> dict:
    """Read the decision record back — the full log, or the unapplied set.

    With ``--unapplied`` returns the REQ-DEC-05 set (``_unapplied_decisions``).
    Without it, echoes the full on-disk document. A missing record returns an
    empty result at exit 0 (nothing recorded yet is not a failure). This verb
    never mutates the file; it parses an existing record **strictly** (exit 2 on
    corruption) for both the plain and ``--unapplied`` forms — it never
    downgrades a corrupt record to ``{}``.

    Args:
        backlog_dir: The resolved backlog directory.
        unapplied: Return only the latest-unapplied-per-item set.
        state_dir: State-dir name override, or None to resolve from config.
        config_path: ``forge.config.json`` path (for the stateDir default).
        schema_path: ``forge-config-schema.json`` path (source of the default).

    Returns:
        On a plain read: the full document ``{schemaVersion, feature, createdAt,
        updatedAt, decisions}`` (or ``{"decisions": []}`` when none recorded).
        On ``--unapplied``: a report view ``{"feature", "unapplied": [...],
        "count": N}`` (NOT the on-disk shape; it is never written).

    Raises:
        UsageError: Missing backlog dir, or an unparseable existing record (→ exit 2).
    """
    if not backlog_dir.is_dir():
        raise UsageError(f"no backlog directory at {backlog_dir}")
    path = _resolve_decisions_path(backlog_dir, state_dir, config_path, schema_path)

    if not path.exists():
        return {"feature": backlog_dir.resolve().name, "unapplied": [], "count": 0} \
            if unapplied else {"decisions": []}

    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise UsageError(f"unparseable decision record at {path}: {exc}") from exc

    if not unapplied:
        return doc
    pending = _unapplied_decisions(doc.get("decisions", []))
    return {"feature": doc.get("feature"), "unapplied": pending, "count": len(pending)}


def cmd_decision_apply(
    backlog_dir: Path,
    item_id: str,
    actor: str,
    state_dir: str | None,
    config_path: Path,
    schema_path: Path,
) -> dict:
    """Stamp ``appliedAt``/``appliedBy`` on the LATEST entry for ``item_id``.

    Append-only mutation (REQ-DEC-07): only the most recent entry for the item is
    touched, and only its ``appliedAt`` (→ ``_now_iso()``) and ``appliedBy``
    (→ ``actor``) fields. Called by the Post-Run Recovery Procedure only AFTER
    the runner apply for the item succeeded, so the record's applied state
    tracks the runner's (REQ-UNB-01).

    Args:
        backlog_dir: The resolved backlog directory.
        item_id: The backlog item whose latest decision to stamp applied.
        actor: The session/actor label for ``appliedBy``.
        state_dir: State-dir name override, or None to resolve from config.
        config_path: ``forge.config.json`` path (for the stateDir default).
        schema_path: ``forge-config-schema.json`` path (source of the default).

    Returns:
        The mutated decisions document (for the ``--json`` echo).

    Raises:
        UsageError: Missing backlog dir; no decision recorded for the item; the
            item's latest entry is already applied (nothing unapplied); an
            unparseable record; or a failed atomic write (→ exit 2).
    """
    if not backlog_dir.is_dir():
        raise UsageError(f"no backlog directory at {backlog_dir}")
    path = _resolve_decisions_path(backlog_dir, state_dir, config_path, schema_path)
    doc = _read_decisions_for_write(path, backlog_dir.resolve().name)

    latest_index: int | None = None
    for index, entry in enumerate(doc["decisions"]):
        if entry["itemId"] == item_id:
            latest_index = index  # keep the LAST match — stored order is chronological
    if latest_index is None:
        raise UsageError(f"no decision recorded for item {item_id!r}")
    entry = doc["decisions"][latest_index]
    if entry["appliedAt"] is not None:
        raise UsageError(
            f"latest decision for item {item_id!r} is already applied "
            f"(at {entry['appliedAt']}) — nothing unapplied"
        )

    entry["appliedAt"] = _now_iso()
    entry["appliedBy"] = actor
    path.parent.mkdir(parents=True, exist_ok=True)
    return _commit_state(path, doc)


def _print_decision_record(doc: dict) -> None:
    """One-line human summary for ``decision-record``."""
    print(f"decision recorded — {len(doc['decisions'])} entr"
          f"{'y' if len(doc['decisions']) == 1 else 'ies'} on record for {doc['feature']}")


def _print_decision_list(view: dict) -> None:
    """One-line-per-entry human summary for ``decision-list``."""
    if "unapplied" in view:
        print(f"{view['count']} unapplied decision(s)")
        for entry in view["unapplied"]:
            kind = "deferred" if entry["deferred"] else "answered"
            print(f"  {entry['itemId']}: {kind} — {entry['question']}")
    else:
        print(f"{len(view.get('decisions', []))} decision(s) on record")


def _print_decision_apply(doc: dict) -> None:
    """One-line human summary naming the just-applied entry (max appliedAt)."""
    applied = [d for d in doc["decisions"] if d["appliedAt"] is not None]
    entry = max(applied, key=lambda d: d["appliedAt"])
    print(f"applied decision for item {entry['itemId']} ({entry['appliedBy']})")
