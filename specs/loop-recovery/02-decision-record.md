# 02 — Decision Record

> **HOW to implement the decision record.** This document specifies the one new
> persistent surface — `forge-decisions.json` — and the three `decision-*` verbs that
> are its *only* writers/readers: `decision-record`, `decision-list`, `decision-apply`.
> It gives the complete Python for each verb (signatures, docstrings, argparse
> registration, dispatch), the load→mutate→append→commit path, the append-only
> invariants, the R4 conformance contract the test in `07-testing-strategy.md`
> enforces, and the exit-2 error model. It builds on `00-core-definitions.md` — the
> schema, field semantics, constants, error model, and existing-helper contracts live
> there and are **referenced, not restated**.

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-DEC-01 | Decision persisted to a durable per-backlog record | §2 (path/lifecycle), §3 (`decision-record`) |
| REQ-DEC-02 | Record captures item/question/answer/decided/applied/actor | §3 (entry builder), refs `00 §4.1` |
| REQ-DEC-03 | Written by a scripted verb, atomically, never hand-authored | §3, §7 (atomic write via `_commit_state`) |
| REQ-DEC-04 | Read-back drives the named recovery procedure | §4 (`decision-list`); procedure named in `05` |
| REQ-DEC-05 | Enumerate not-yet-applied decisions (first-class) | §4 (`--unapplied` filter) |
| REQ-DEC-06 | Recorded on every branch incl. deferral / cancel-early | §3.2 (deferral shape), §6 (worked example) |
| REQ-DEC-07 | Append-only; latest-entry-per-item unapplied set | §5 (`decision-apply`), §6 (invariants) |
| REQ-STATE-01 | R4: schema + verb writer + conformance test | §2 (path), §8 (conformance contract) |
| REQ-SEC-01 | No secret-shaped fields; actor labels only | §9 |
| REQ-REL-01 | Single writer; atomic write-then-rename | §7 (write path) |
| REQ-REL-02 | A failed scripted write is surfaced verbatim, never claimed succeeded | §7 (error model) |

---

## 1. Scope & Dependencies

**In scope:** the file placement and its resolution; the three `decision-*` verb
functions in `scripts/forge-session.py` with full Python; append-only semantics; the
error model for the write side; and the R4 conformance contract (the *contract*; the
test is authored in `07-testing-strategy.md`).

**Out of scope (owned elsewhere):**
- The schema JSON, field semantics, and the loop-outcome vocabulary — `00-core-definitions.md`
  §4 (schema) and §5 (outcomes). This document does **not** restate the schema; it lands
  verbatim from `00 §4.1` at `references/forge-decisions-schema.json`.
- *Who* calls these verbs and in what order (the named Post-Run Recovery Procedure, the
  "record at collection" ordering of REQ-DEC-01, the runner-contract pointer edits of
  REQ-DEC-04) — `05-recovery-procedure.md`.
- The `backlog-topology`/clustering verbs (which mint the `clusterId` these verbs
  consume) — `06`.
- The conformance/schema/edge-case *tests* — `07-testing-strategy.md`.

**Depends on (must be implemented first):** `00-core-definitions.md`. This document
places the schema and reuses the existing helpers catalogued in `00 §10`
(`_now_iso`, `_write_state`, `_commit_state`, `UsageError`, `_emit`,
`resolve_loop_runner`).

## 2. File placement, path resolution & lifecycle (REQ-DEC-01, REQ-STATE-01)

### 2.1 Location

The record lives at `{resolvedBacklogDir}/{stateDir}/forge-decisions.json`
(canonical statement in `00 §3`). `stateDir` is the effective-config
`loopRunner.stateDir`, default `.rauf`, so for a default feature this resolves to
`specs/{feature}/.rauf/forge-decisions.json`. Being under `**/.rauf/*` it is
git-ignored **by construction** (#195) — durable across session end/context clear, yet
untracked, so a decision write never dirties the working tree the tree-reconciliation
gate (`05 §3.5`) inspects (REQ-DEC-01).

### 2.2 The verbs resolve their own path — they are NOT feature-state verbs

The `decision-*` verbs take `--backlog-dir` (plus optional `--state-dir`). They do
**not** call `_load_state_for_write` / `_resolve_feature_dir_for_write` — those resolve a
*feature* directory for `.pipeline-state.json` and are the wrong target (`00 §10`, note).
They reuse only the **target-agnostic** `_write_state`/`_commit_state`
(`forge-session.py:4097,4388` — `_commit_state`'s docstring states it "is
target-agnostic: it stamps and writes whatever document it is given"). Path resolution
is one new helper:

```python
from pathlib import Path
from typing import Final

#: The one persistent artifact this feature adds; only decision-* verbs write it.
DECISIONS_FILENAME: Final[str] = "forge-decisions.json"
#: Enum-locked at the schema (00 §4.1); a bump is a breaking change.
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
    covered by the ``**/.rauf/*`` ignore rule with zero ``.gitignore`` edits (00 §3).

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
```

`resolve_loop_runner(config_path, schema_path)` is the existing resolver at
`forge-session.py:4029`; `schema_path` comes from the existing `_default_schema_path()`
(`forge-session.py:3969`). No new config surface is introduced.

### 2.3 First-write file creation & the read-for-write helper

On the **first** write the file does not exist: the verb seeds a fresh skeleton
(`schemaVersion`, `feature`, `createdAt`, empty `decisions[]`) — `_commit_state` then
stamps `updatedAt` and writes atomically, so all five top-level required fields
(`00 §4.1`) are present at exit 0. `feature` is the backlog dir's basename, stamped once
and never mutated. An **existing** file is loaded strictly — unlike the navigator's
tolerant `_read_state` (`forge-session.py:691`, which downgrades corrupt → `{}`), a
write path must **never** silently discard a recoverable record (the exact lesson the
`state-*` corrupt-file refusal enforces, `test_state_schema_conformance.py:474`):

```python
import json

from pathlib import Path


def _read_decisions_for_write(path: Path, feature: str) -> dict:
    """Load the decisions document for mutation, or seed a fresh one on first write.

    A MISSING file is the first-write case → return a fresh skeleton whose parent
    dir is created on commit. An UNPARSEABLE or non-object existing file is a HARD
    failure (exit 2) — a write path must not inherit ``_read_state``'s corrupt→{}
    tolerance, which would atomically replace a recoverable record with an
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
```

The state dir (`.rauf`) may not exist yet when a decision is recorded before the loop
ever launches, so every mutating verb calls `path.parent.mkdir(parents=True,
exist_ok=True)` before `_commit_state`. An **unwritable** parent surfaces from
`_write_state` as `UsageError` — this is the real "unknown backlog dir" case: the dir is
created on first write, so failure means an unwritable/parent-missing path, not a
lookup miss (§7).

### 2.4 The shared entry builder

Every appended entry is built by one helper so the eight required fields (`00 §4.1`) are
never partially populated; the optional `clusterId` is added only when present:

```python
def _new_decision_entry(
    item_id: str,
    question: str,
    answer: str | None,
    deferred: bool,
    cluster_id: str | None,
    actor: str,
) -> dict:
    """Build one schema-conformant decision entry (00 §4.1).

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
```

## 3. `decision-record` (REQ-DEC-01/02/03/06)

Appends **one entry per `--item`**. `--answer A` and `--deferred` are mutually exclusive
and exactly one is required (neither/both ⇒ exit 2, §7). `--cluster CID` sets a shared
`clusterId` across every appended entry (REQ-CLU-04, consumed from `06`). `--actor LABEL`
overrides the default `forge-5-loop@<host>` label.

### 3.1 Signature

```python
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
    # Defense in depth: the argparse mutually-exclusive group (§3.3) rejects
    # both/neither first, but a direct call must fail the same way. Valid states are
    # exactly (answered, not deferred) or (deferred, no answer).
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
```

### 3.2 Deferral & cancel-early shape (REQ-DEC-06)

There is **no third form** (`00 §4.2`). Both "operator cancels the run early" and
"operator defers a consolidated decision" call `decision-record --deferred` — recording
`answer: null`, `deferred: true`, `question` carrying the original needs-human text. The
cancellation rationale is conversational and is never written into `answer`. A deferral
therefore re-surfaces through `decision-list --unapplied` on the next launch identically
to any other unapplied entry (§4).

### 3.3 argparse registration (mirrors `state-note` at `forge-session.py:5746`)

```python
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
```

The `add_mutually_exclusive_group(required=True)` gives the neither/both rejection its
exit-2 `Error:` form for free, because every subparser inherits `_ErrorPrefixParser`
(`forge-session.py:5567`, whose `error()` prints `Error: …` and exits 2); the in-body
guard in §3.1 keeps a direct Python call honest.

### 3.4 dispatch (mirrors the `state-note` block at `forge-session.py:5970`)

```python
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
```

with the default-actor helper (stdlib `socket`, a machine label only — never user
identity, REQ-SEC-01):

```python
import socket


def _default_actor() -> str:
    """Return the default recordedBy/appliedBy label: ``forge-5-loop@<host>``.

    The host segment is a machine label, not a user identity (REQ-SEC-01, §9).
    """
    return f"forge-5-loop@{socket.gethostname()}"
```

and its one-line printer (mirrors `_print_state_note`, `forge-session.py:5461`):

```python
def _print_decision_record(doc: dict) -> None:
    """One-line human summary for ``decision-record``."""
    print(f"decision recorded — {len(doc['decisions'])} entr"
          f"{'y' if len(doc['decisions']) == 1 else 'ies'} on record for {doc['feature']}")
```

## 4. `decision-list` (REQ-DEC-04, REQ-DEC-05)

Read-back is a **first-class** operation (REQ-DEC-05), not a side effect — the Post-Run
Recovery Procedure (`05`) enumerates the unapplied set as its Step 1. Plain
`decision-list` echoes the full on-disk document; `--unapplied` returns the REQ-DEC-05
set. A missing record (nothing ever recorded) is not an error: it returns an empty set at
exit 0, so a truly first launch enumerates cleanly.

### 4.1 The unapplied filter (the exact REQ-DEC-05 algorithm)

The unapplied set is *the latest entry per `itemId` whose `appliedAt is None`*
(`00 §4.3`). Because entries are append-only and never reordered, stored order **is**
chronological, so "last seen per item" is "latest":

```python
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
```

### 4.2 Signature

```python
def cmd_decision_list(
    backlog_dir: Path,
    unapplied: bool,
    state_dir: str | None,
    config_path: Path,
    schema_path: Path,
) -> dict:
    """Read the decision record back — the full log, or the unapplied set.

    With ``--unapplied`` returns the REQ-DEC-05 set (§4.1). Without it, echoes the
    full on-disk document. A missing record returns an empty result at exit 0
    (nothing recorded yet is not a failure). This verb never mutates the file; it
    parses an existing record **strictly** (exit 2 on corruption) for both the plain
    and ``--unapplied`` forms — it never downgrades a corrupt record to ``{}``.

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
```

`decision-list` is read-only and MUST parse an existing file strictly (exit 2 on
corruption) rather than downgrade to `{}` — a recovery procedure that silently saw "no
unapplied decisions" against a corrupt record would falsely claim recovery complete
(REQ-REL-02 spirit). It is the one verb that never calls `_commit_state`.

### 4.3 argparse + dispatch + printer

```python
p_dlist = sub.add_parser("decision-list", help="Read the decision record (or the unapplied set)")
p_dlist.add_argument("--backlog-dir", required=True, dest="backlog_dir",
                     help="Resolved backlog directory")
p_dlist.add_argument("--unapplied", action="store_true",
                     help="Return only the latest-unapplied-per-item set (REQ-DEC-05)")
p_dlist.add_argument("--state-dir", default=None, dest="state_dir",
                     help="State-dir name (default: effective loopRunner.stateDir)")
p_dlist.add_argument("--config", default="./forge.config.json", help="forge.config.json path")
p_dlist.add_argument("--json", action="store_true", dest="json_output")
```

```python
if args.cmd == "decision-list":
    payload = cmd_decision_list(
        Path(args.backlog_dir), args.unapplied, args.state_dir,
        Path(args.config), _default_schema_path(),
    )
    _emit(payload, args.json_output, _print_decision_list)
    return 0


def _print_decision_list(view: dict) -> None:
    """One-line-per-entry human summary for ``decision-list``."""
    if "unapplied" in view:
        print(f"{view['count']} unapplied decision(s)")
        for entry in view["unapplied"]:
            kind = "deferred" if entry["deferred"] else "answered"
            print(f"  {entry['itemId']}: {kind} — {entry['question']}")
    else:
        print(f"{len(view.get('decisions', []))} decision(s) on record")
```

The recovery procedure always passes `--json` and consumes the structured payload;
the printer is the human fallback.

## 5. `decision-apply` (REQ-DEC-07)

The **one** operation that mutates an existing entry, and it touches only `appliedAt`
and `appliedBy` on the **latest** entry for `--item ID` (`00 §4.3`). Every earlier audit
field is immutable. It exits 2 when the item has nothing unapplied (unknown id, or a
double-apply) — a silent no-op would let a recovery report claim an apply that never
happened.

```python
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
    (→ ``actor``) fields. Called by the recovery procedure only AFTER the runner
    apply for the item succeeded (``05`` Step 5), so the record's applied state
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
```

argparse + dispatch + printer:

```python
p_dapply = sub.add_parser("decision-apply", help="Mark the latest decision for an item applied")
p_dapply.add_argument("--backlog-dir", required=True, dest="backlog_dir",
                      help="Resolved backlog directory")
p_dapply.add_argument("--item", required=True, dest="item_id", metavar="ID",
                      help="Backlog item whose latest decision to stamp applied")
p_dapply.add_argument("--actor", default=None,
                      help="Session/actor label for appliedBy (default forge-5-loop@<host>)")
p_dapply.add_argument("--state-dir", default=None, dest="state_dir",
                      help="State-dir name (default: effective loopRunner.stateDir)")
p_dapply.add_argument("--config", default="./forge.config.json", help="forge.config.json path")
p_dapply.add_argument("--json", action="store_true", dest="json_output")
```

```python
if args.cmd == "decision-apply":
    payload = cmd_decision_apply(
        Path(args.backlog_dir), args.item_id, args.actor or _default_actor(),
        args.state_dir, Path(args.config), _default_schema_path(),
    )
    _emit(payload, args.json_output, _print_decision_apply)
    return 0


def _print_decision_apply(doc: dict) -> None:
    """One-line human summary naming the just-applied entry (max appliedAt)."""
    applied = [d for d in doc["decisions"] if d["appliedAt"] is not None]
    entry = max(applied, key=lambda d: d["appliedAt"])
    print(f"applied decision for item {entry['itemId']} ({entry['appliedBy']})")
```

## 6. Append-only semantics — worked multi-entry example (REQ-DEC-06, REQ-DEC-07)

The invariants, restated from `00 §4.3` and made concrete:

1. A later decision for the same item **appends**; it never edits an earlier entry.
2. `decision-apply` is the sole mutator, and only of `appliedAt`/`appliedBy` on the
   **latest** entry for one item.
3. The unapplied set (§4.1) is the *latest undecided-or-unapplied entry per item*.
4. Cluster members (shared `clusterId`) remain independently re-decidable — a later
   per-item entry supersedes the cluster entry for that item alone.

**Sequence** (`--backlog-dir specs/loop-recovery`, `.rauf` state dir):

**Step A** — `decision-record --item 4 --question "Which cache backend?" --answer "redis"`
appends entry₀. **Step B** — `decision-record --item 7 --question "Missing API key" --deferred`
appends entry₁. On-disk (`decisions[]`, abbreviated):

```jsonc
[
  { "itemId": "4", "question": "Which cache backend?", "answer": "redis",
    "deferred": false, "decidedAt": "…T10:00:00Z", "recordedBy": "forge-5-loop@host",
    "appliedAt": null, "appliedBy": null },
  { "itemId": "7", "question": "Missing API key", "answer": null,
    "deferred": true,  "decidedAt": "…T10:01:00Z", "recordedBy": "forge-5-loop@host",
    "appliedAt": null, "appliedBy": null }
]
```

`decision-list --unapplied` → both item 4 and item 7 (latest per item, both unapplied).

**Step C** — the operator revises item 4: `decision-record --item 4 --question "Which
cache backend?" --answer "memcached"` **appends** entry₂ (entry₀ is untouched — its audit
survives). `--unapplied` now returns entry₂ for item 4 (the latest) and entry₁ for item 7;
entry₀ is superseded but **retained**.

**Step D** — after the runner apply for item 4 succeeds, `decision-apply --item 4` stamps
only entry₂:

```jsonc
{ "itemId": "4", "answer": "memcached", "deferred": false,
  "appliedAt": "…T10:05:00Z", "appliedBy": "forge-5-loop@host", "…": "…" }
```

`decision-list --unapplied` → **item 7 only** (its deferral is still unapplied); item 4
dropped because its latest entry is now applied. entry₀ and entry₁ are unchanged. This is
exactly the "survives session end" property (REQ-DEC-01/06): on the next launch, Step 1 of
`05` re-enumerates item 7's deferral.

## 7. Error handling (REQ-DEC-03, REQ-REL-01/02)

Every failure raises `UsageError` (`forge-session.py:682`) → **exit 2**, an
`Error:`-prefixed line on **stderr**, empty stdout (`00 §7`). There is no exit 1. Writes
are atomic (`_write_state` → `mkstemp` → `fsync` → `os.replace`, single-writer assumed,
REQ-REL-01) so an interrupted write never corrupts the record. Skills surface the line
**verbatim** and stop the surrounding protocol; they never hand-author the JSON
(REQ-DEC-03) and never report a failed write as recorded (REQ-REL-02).

| Case | Trigger | Exit | Message shape (`Error:` prefix added by the exit-2 path) |
|------|---------|------|-----------------------------------------------------------|
| Missing backlog dir | `--backlog-dir` is not an existing directory | 2 | `no backlog directory at {path}` |
| Illegal flag combo | `decision-record` with both `--answer` and `--deferred`, or neither | 2 | argparse group → `argument --deferred: not allowed with argument --answer` / group-required; in-body guard → `exactly one of --answer or --deferred is required` |
| Unparseable record | existing `forge-decisions.json` is corrupt / not an object | 2 | `unparseable decision record at {path}: {err}` |
| Failed atomic write | unwritable state dir / parent (the real "unknown dir" case, §2.3) | 2 | `atomic write to {path} failed: {err}` (from `_write_state`) |
| Unknown item on apply | `decision-apply --item ID` with no entry for ID | 2 | `no decision recorded for item {ID!r}` |
| Nothing unapplied on apply | `decision-apply` when the latest entry for ID is already applied | 2 | `latest decision for item {ID!r} is already applied (at {ts}) — nothing unapplied` |

The failed-write and nothing-unapplied cases are *distinct* signals the recovery
procedure relies on (REQ-REL-02): a failed apply stops **before** the per-item unblock
proof (`04`), whereas a ran-but-nothing-moved failure is that proof failing — the decision
record's own errors belong to the former class.

## 8. R4 conformance contract (REQ-STATE-01)

The schema (`references/forge-decisions-schema.json`, verbatim from `00 §4.1`) is the
**source of truth**; these verbs are its only writers; and the conformance test
(`tests/test_decisions_schema_conformance.py`, authored in `07-testing-strategy.md`)
guards the pairing. This document states the **contract that test enforces**:

1. **Validator wrapper.** `tests/_state_schema.py` gains a module-level
   `_DECISIONS_SCHEMA` load and a `validate_decisions()` wrapper mirroring
   `_STATE_SCHEMA`/`validate_state` (`_state_schema.py:26-31,98`):

   ```python
   _DECISIONS_SCHEMA = json.loads(
       (REPO_ROOT / "references" / "forge-decisions-schema.json").read_text(encoding="utf-8")
   )


   def validate_decisions(record: dict) -> list[str]:
       """Validate a forge-decisions object against references/forge-decisions-schema.json.

       Args:
           record: An on-disk ``forge-decisions.json`` document.

       Returns:
           Human-readable violation strings; empty when the record conforms.
       """
       return _check(record, _DECISIONS_SCHEMA, _DECISIONS_SCHEMA, "$")
   ```

   The schema uses only the draft-07 subset the stdlib `_check` supports (`type`,
   `required`, `properties`, `enum`, `items`, `additionalProperties: false`, `$ref` to
   `#/definitions/*`) — no `oneOf`/`pattern`/`format` (`00 §4.1`). The module docstring's
   "Both entry points" scoping sentence updates to three.

2. **Registry completeness.** A regex scan asserts every registered `decision-*` verb
   appears in the test's `VERB_INVOCATIONS` — cloning
   `test_state_schema_conformance.py:97-103`'s guard but keyed to the **`decision-`**
   prefix, e.g. `re.findall(r'add_parser\(\s*"(decision-[a-z-]+)"', source)`. The distinct
   prefix keeps the existing `state-*` guard (which expects exactly eight `state-` verbs)
   untouched — `state-decision` (a different, pipeline-level verb writing
   `deferredDecisions[]`) is **not** a `decision-*` verb and must not be swept in
   (`00 §3`, tech-spec §3.1 naming note).

3. **Per-write conformance.** Every `decision-*` invocation, run **out-of-process**
   (`sys.executable`, matching `_run` at `test_state_schema_conformance.py:72`) against a
   temp backlog dir, produces an on-disk file that passes `validate_decisions() == []` —
   including the first-write skeleton and every subsequent append.

4. **Append-only invariants across a multi-verb sequence.** A realistic sequence
   `record → defer → re-record → apply` (the §6 shape) validates after **every** step and
   asserts: entry count only grows; earlier entries' audit fields are byte-identical after
   later writes; `decision-apply` changes only `appliedAt`/`appliedBy` on the latest entry;
   and `decision-list --unapplied` returns exactly the latest-unapplied-per-item set at
   each step (REQ-DEC-07/05). The unapplied *report* view (§4.2) is a synthetic shape and
   is **not** schema-validated — only the on-disk document is.

## 9. Security (REQ-SEC-01)

Decision records hold operator-authored free text and are treated as repo-visible,
non-sensitive content (untracked per REQ-DEC-01, never a secret store):

- **No credential-shaped field.** The schema (`00 §4.1`) has no field intended for
  secrets. `answer` is free text; the recovery procedure's prompts (`05`) explicitly
  instruct the operator never to paste secrets.
- **Actor labels only.** `recordedBy`/`appliedBy` are set from `--actor` (default
  `forge-5-loop@<host>` via `_default_actor()`, §3.4) — a session/machine label, **never**
  a user identity, email, or credential.
- **No secret solicitation by these verbs.** The verbs accept only the flags in §§3–5;
  none prompts for or derives a secret.

## Dependencies

- **`00-core-definitions.md`** — the schema (`§4.1`), field semantics (`§4`), append-only
  and unapplied-set definitions (`§4.3`), the error model (`§7`), and the existing-helper
  contracts (`§10`: `_now_iso`, `_write_state`, `_commit_state`, `UsageError`, `_emit`,
  `resolve_loop_runner`). Implement `00` first: the schema file this document's verbs
  write must exist, and `resolve_loop_runner`/`_default_schema_path` must be available (they
  already are in `forge-session.py`).

Downstream (implemented after this doc): `05-recovery-procedure.md` (the caller of these
verbs, the REQ-DEC-01 record-at-collection ordering, the REQ-DEC-04 pointer edits) and
`07-testing-strategy.md` (the conformance test §8 specifies).

## Verification

- [ ] `references/forge-decisions-schema.json` exists byte-for-byte from `00 §4.1` and
      loads under `tests/_state_schema.py`'s subset (no unsupported constructs).
- [ ] `decision-record`/`decision-list`/`decision-apply` are registered, each with the
      §§3–5 flags; `--backlog-dir` is required and `--state-dir` defaults from
      `resolve_loop_runner` (`.rauf`).
- [ ] `decision-record --item X --item Y --answer A` appends **two** entries sharing the
      answer; `--deferred` records `answer: null, deferred: true`; both/neither of
      `--answer`/`--deferred` exit 2 with an `Error:` line.
- [ ] First write creates `{backlog-dir}/.rauf/forge-decisions.json` with
      `schemaVersion:"1"`, `feature` = backlog-dir basename, `createdAt`, and (via
      `_commit_state`) `updatedAt`; the file is under `**/.rauf/*` and does not appear in
      `git status --porcelain`.
- [ ] `decision-list --unapplied --json` returns the latest-entry-per-item set where
      `appliedAt is null` — deferrals included, applied items excluded — sorted by
      `itemId`; a missing record returns an empty set at exit 0.
- [ ] `decision-apply --item X` stamps only `appliedAt`/`appliedBy` on the latest entry
      for X and leaves every other field/entry byte-identical; a double-apply or unknown
      id exits 2.
- [ ] A corrupt existing record makes every mutating verb (and `decision-list`) exit 2
      with the bytes untouched (no corrupt→{} downgrade on the write path).
- [ ] `validate_decisions()` exists in `tests/_state_schema.py` and returns `[]` for
      every verb's on-disk output across the `record → defer → re-record → apply` sequence
      (the `07` conformance test), and the registry-completeness scan covers every
      `decision-*` verb without disturbing the `state-*` guard.
- [ ] `ruff check scripts/ eval/` passes and `python3 scripts/build-adapters.py` leaves no
      drift (`00 §10`, `01 §6`).
