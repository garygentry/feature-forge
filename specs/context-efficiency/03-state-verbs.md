# 03 — State-Write Verbs (R4)

> **HOW to implement R4.** This document specifies the seven targeted
> `forge-session.py` state-write subcommands that eliminate the per-stage read of
> `pipeline-state-schema.json` and remove all hand-authored-JSON drift (PRD §3.4,
> tech-spec §3.4). It builds directly on `00-core-definitions.md` — script
> conventions (§3), the pipeline-state JSON shapes (§4), the touch-point inventory
> (§5), and the frozen-protocol invariants (§10). Those contracts are **not
> restated** here; they are referenced by section and turned into concrete,
> complete Python.
>
> Nothing in R4 changes runtime *behavior*. It changes only the *mechanic* by
> which the JSON is authored: where a skill step said "edit the JSON," it now
> says "run this verb." Every surrounding interactive protocol — Stage-Entry
> Guard classification, Branch Setup/Reconciliation prompts, the "offer a note"
> statement, and the two-commit Git Commit Protocol (never `--amend`) — keeps its
> exact prose and turn structure (REQ-BEHAV-02, C-1).

## Requirement Coverage

| REQ ID | Requirement | Section |
|--------|-------------|---------|
| REQ-R4-01 | Stages no longer read the full state schema per invocation | §2 (overview), §4–§10 (verbs replace hand-authored JSON) |
| REQ-R4-02 | Preferred mechanism is a `forge-session.py` state write helper | §2, §3 (shared write path) |
| REQ-R4-03 | Schema stays CI source of truth; verbs emit conforming state | §3.4, §11 (drift guard cross-ref), §12 (Verification) |
| REQ-R4-04 | ALL seven state-write touch points covered — no partial extraction | §4–§10 (one verb each), §11 (touch-point conversion map) |
| REQ-BEHAV-01 | Zero behavioral diff | §13 (prose-unchanged invariant) |
| REQ-BEHAV-02 | Frozen interactive protocols preserved verbatim | §6.5 (two-commit), §13 (before/after) |
| REQ-MAINT-01 (R4 slice) | Drift guard asserts each verb's output validates against the schema | §12, cross-ref `06-testing-strategy.md §4` |

---

## 1. Scope & Dependencies

**This document owns:** the R4 subcommands of `scripts/forge-session.py` — the
`_write_state` atomic helper, the shared resolve→load→mutate→refresh→write path,
the seven `state-*` verbs, the deterministic downstream staleness cascade folded
into `state-complete`, the two-commit `--commit-hash` follow-up, and the
touch-point conversion map that retires every hand-authored write.

**This document does NOT own:**

- The `effective-config` subcommand (R5) — see `04-effective-config.md`.
- The R4 drift guard's assertions — see `06-testing-strategy.md §4` (this doc
  states only the contract the guard enforces).
- The verify-stage write path (`verifyEntry` shape) — forge-verify/forge-fix keep
  their existing write mechanic; R4 covers only the production `stageEntry` touch
  points plus the two array types (`00-core-definitions.md §4.2`).

**Depends on (must be implemented / read first):**

- `00-core-definitions.md` — script conventions (§3), state JSON shapes (§4),
  touch-point inventory (§5), frozen invariants (§10). **Read first.**
- `references/pipeline-state-schema.json` — the unchanged data contract every
  verb's output must satisfy (REQ-R4-03).

**Cross-references:**

- `04-effective-config.md` — the sibling R5 subcommand added to the same script
  in the same style; also the reference for the `shared-conventions.md` edits
  that switch prose to verb calls.
- `06-testing-strategy.md §4` — the stdlib structural validator (no `jsonschema`)
  that CI runs against each verb's emitted state.

**Delivery note (tech-spec §3.7, `01-architecture-layout.md §4/§5`):** R4 ships
**after** R5. Both add functions to `forge-session.py`; the additions are
disjoint and independently named, so `git revert` of either PR leaves the other's
subcommands intact.

---

## 2. Overview

`forge-session.py` today only **reads** state (`_read_state`, L177, which
downgrades a missing/corrupt file to `{}`); it has **no state writer**. R4 adds
seven verbs that are the **first state writers** in this script, replacing every
hand-authored `.pipeline-state.json` edit across the pipeline (REQ-R4-04). Because
the script authors the JSON, the model never needs to read the 191-line
`pipeline-state-schema.json` to get the shape right (REQ-R4-01), and hand-authored
drift is eliminated (REQ-R4-02).

The seven verbs and their touch points (from `00-core-definitions.md §5`,
tech-spec §3.4):

| Subcommand | Touch point | Writes | Section |
|---|---|---|---|
| `state-enter` | Entry stamp | `stages.{stage}.status=in-progress`, `.startedAt`; top-level `currentStage`, `updatedAt` | §4 |
| `state-artifact` | Incremental `artifacts[]` | append to `stages.{stage}.artifacts` (idempotent — no dup paths) | §5 |
| `state-complete` | Completion | `status=complete`, `completedAt`, `version` bump, `basedOnVersions`, `artifacts`, `commitHash=null`; **+ deterministic downstream staleness cascade**; optional `--commit-hash` for Commit 2 | §6 |
| `state-note` | `notes` | set top-level `notes` | §7 |
| `state-decision` | `deferredDecisions[]` | append a decision item | §8 |
| `state-ecr` | `epicChangeRequests[]` | append an epic-change-request item | §9 |
| `state-branch` | `branch` | set top-level `branch` | §10 |

All verbs share: exit codes **0/2** (`00-core-definitions.md §3.2` — no exit 1);
a `--json` flag (`dest="json_output"`) that echoes the resulting state;
`--specs-dir` (default `./specs`); and the atomic write path (§3). Errors degrade
to data at exit 0 or surface as exit 2 under the script's single top-level
`try/except` (verified L1857–1862).

---

## 3. Shared machinery (every verb reuses this)

### 3.1 Module additions & existing reuse

The new code slots into the existing structure (`01-architecture-layout.md §2.1`):
module docstring → constants → helpers → `main()` with argparse subparsers + an
`if args.cmd == …` dispatch chain. **Reused verbatim, not re-implemented:**

| Existing symbol | Location (verified) | Reuse |
|---|---|---|
| `_read_state(state_path: Path) -> dict` | L177 | load current state (`{}` if absent → verbs create-or-update) |
| `_resolve_feature_dir(specs_dir, feature, epic) -> Path` | L1416 | resolve the feature dir |
| `PIPELINE_STATE_FILENAME` (`".pipeline-state.json"`) | L94 | the state filename |
| `UsageError(Exception)` | L168 | raised for bad args → exit 2 |
| `import os`, `import json`, `from datetime import datetime, timezone` | L79–84 | already present; `_write_state` and `_now_iso` need no new imports |

The `import os` and `import json` that `_write_state` needs are already imported
(verified L80–81), and `datetime`/`timezone` are already imported for `_now_iso`
(verified L84). **No new stdlib import is required** (C-2: stdlib-only, no
`jsonschema`).

> **WARNING: could not confirm an existing `_now_iso` helper.** `grep` of
> `forge-session.py` found **no** `_now_iso`/`now_iso`/`_iso` helper; the script
> generates timestamps inline (`datetime.now(timezone.utc)` at L435; parses with
> `datetime.fromisoformat(...replace("Z","+00:00"))` at L371). `epic-manifest.py`
> writes timestamps as `datetime.now(timezone.utc).isoformat()` (L1093). R4
> therefore **introduces** a small `_now_iso()` helper (§3.2) rather than reusing
> one. `00-core-definitions.md §3.3` describes it as "the module's existing …
> formatter"; that phrasing anticipates the helper — this doc adds it. Verify at
> implementation time that no equivalent helper was added between spec and build.

### 3.2 Timestamp helper — `_now_iso()`

Every verb refreshes `updatedAt` (and some fields set `startedAt`/`completedAt`)
to a UTC ISO-8601 timestamp. The pipeline's stored timestamps use a `Z` suffix
(the state schema's `format: date-time` values, and the codebase's parse path
normalizes a trailing `Z`, L371). Emit a `Z`-suffixed, second-precision UTC
stamp so new writes match existing on-disk values:

```python
def _now_iso() -> str:
    """Return the current UTC time as a Z-suffixed, second-precision ISO-8601 string.

    Matches the `.pipeline-state.json` timestamp convention already on disk
    (schema `format: date-time`; the read path at L371 normalizes a trailing
    `Z`). Second precision keeps `updatedAt`/`startedAt`/`completedAt` visually
    consistent with the values other pipeline writers produce.

    Returns:
        A timestamp like ``"2026-07-20T03:30:00Z"``.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
```

### 3.3 Atomic write — `_write_state()`

`forge-session.py` has never written state, so R4 introduces the atomic writer.
It mirrors `epic-manifest.py`'s `atomic_write` (L315: temp file **in the same
directory** + flush + fsync + `os.replace`, verified) so a crash can never leave a
half-written state file. The canonical signature is fixed by
`00-core-definitions.md §3.3`:

```python
def _write_state(state_path: Path, state: dict) -> None:
    """Atomically write a `.pipeline-state.json` (temp file + os.replace).

    Mirrors epic-manifest.py's atomic_write (L315): write to a sibling temp file
    in the same directory as the target, flush + fsync the bytes, then
    os.replace() the temp file onto the target. os.replace is atomic on POSIX
    within one filesystem, so an interrupted write never leaves a partial or
    corrupt state file. Concurrent multi-session mutation is out of scope
    (single-writer assumed, matching epic-manifest.py).

    Args:
        state_path: Destination path, e.g.
            ``{specsDir}/{feature}/.pipeline-state.json``.
        state: The fully-formed state dict to serialize.

    Raises:
        OSError: If the temp file cannot be created/written or the replace
            fails. Surfaces as exit 2 under main()'s top-level handler; the temp
            file is removed on failure so no debris is left behind.
    """
    parent = state_path.parent
    fd, tmp_name = tempfile.mkstemp(
        prefix=f".{state_path.name}.", suffix=".tmp", dir=parent
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, state_path)
    except OSError:
        tmp_path.unlink(missing_ok=True)
        raise
```

> **Import note.** `tempfile` is **not** currently imported by `forge-session.py`
> (verified: the imports at L79–86 are `argparse, json, os, subprocess, sys`,
> `datetime`, `Path`, `typing`). The `tempfile.mkstemp` form above requires adding
> `import tempfile` to the module import block. `00-core-definitions.md §3.3`
> shows a simpler `state_path.with_suffix(...).write_text(...)` + `os.replace`
> form that needs **no** new import but skips the fsync/temp-in-dir hardening.
> **Decision for this spec:** use the `tempfile.mkstemp` + fsync form (mirrors the
> proven `epic-manifest.py` pattern exactly) and add `import tempfile`. If a
> reviewer prefers zero new imports, the `00 §3.3` `with_suffix` variant is an
> acceptable, behavior-equivalent fallback — but it must still write to a sibling
> path in the same directory and `os.replace` onto the target.

### 3.4 The shared mutation path

Every `state-*` verb follows the same **resolve → load → mutate → refresh
`updatedAt` → write-back** sequence (`00-core-definitions.md §3.3`). Rather than
duplicate resolve/load/write in seven handlers, factor a small context helper the
handlers call:

```python
def _load_state_for_write(
    specs_dir: Path, feature: str, epic: str | None
) -> tuple[Path, dict]:
    """Resolve a feature's state path and load its current state for mutation.

    Reuses the existing resolver (_resolve_feature_dir, L1416) and reader
    (_read_state, L177). A missing/corrupt state downgrades to ``{}`` so a verb
    can create-or-update. The verb mutates the returned dict in place, then calls
    _commit_state() to refresh updatedAt and write atomically.

    Args:
        specs_dir: The configured specs directory (``--specs-dir``).
        feature: The feature name (``--feature``).
        epic: The owning epic name for a nested member, else None (``--epic``).

    Returns:
        A ``(state_path, state)`` tuple. ``state`` is ``{}`` when no state file
        exists yet.

    Raises:
        OSError: Propagated from the resolver if the specs tree is unreadable
            (→ exit 2).
    """
    state_dir = _resolve_feature_dir(specs_dir, feature, epic)
    state_path = state_dir / PIPELINE_STATE_FILENAME
    return state_path, _read_state(state_path)


def _commit_state(state_path: Path, state: dict) -> dict:
    """Refresh ``updatedAt`` and write ``state`` atomically; return it for echo.

    Every verb calls this exactly once, after its mutation, so ``updatedAt`` is
    always refreshed on a successful write (00-core-definitions §3.3 invariant)
    and the write is atomic (_write_state).

    Args:
        state_path: The resolved ``.pipeline-state.json`` path.
        state: The mutated state dict.

    Returns:
        The same ``state`` dict (now carrying a fresh ``updatedAt``), so the verb
        can echo it under ``--json``.

    Raises:
        OSError: If the atomic write fails (→ exit 2).
    """
    state["updatedAt"] = _now_iso()
    _write_state(state_path, state)
    return state
```

Each verb's handler is therefore: `_load_state_for_write(...)` → verb-specific
mutation → `_commit_state(...)` → emit `--json` echo or a human-readable printer.
`updatedAt` is refreshed on **every** mutation (never skipped), satisfying the
`00 §3.3` invariant.

### 3.5 `stages` sub-object bootstrap

Verbs that write into `stages.{stage}` (`state-enter`, `state-artifact`,
`state-complete`) must tolerate a `{}` state or an absent `stages` object. A small
mutator keeps that logic in one place:

```python
def _stage_entry(state: dict, stage: str) -> dict:
    """Return (creating if absent) the mutable ``stages.{stage}`` sub-object.

    Bootstraps ``state["stages"]`` and ``state["stages"][stage]`` as empty dicts
    when missing, so a verb can write into a brand-new state ({}), and returns the
    stage dict for in-place mutation.

    Args:
        state: The full state dict (mutated in place).
        stage: A production stage id (e.g. ``"forge-1-prd"``).

    Returns:
        The mutable ``stages.{stage}`` dict.
    """
    stages = state.setdefault("stages", {})
    return stages.setdefault(stage, {})
```

### 3.6 Argument validation & exit-2 conditions common to all verbs

- `--feature` is `required=True` on every verb; argparse emits a usage error (its
  own exit) if absent — consistent with existing subcommands (e.g. `stage-exit`,
  L1753).
- `--stage` on the three `stages`-writing verbs uses
  `choices=PRODUCTION_STAGES` (see §4) so an unknown stage id is rejected at parse
  time.
- Any I/O failure (unreadable specs tree, unwritable state dir) raises `OSError`,
  caught by the top-level handler → **exit 2** with `Error: …` on stderr
  (`00-core-definitions.md §3.2`).
- A semantically-invalid argument that argparse cannot express (e.g. a
  `--based-on` token without `=`, §6.2; a non-boolean `--blocks-current`, §9.2)
  raises `UsageError` → **exit 2**.
- There is **no exit 1** (`00-core-definitions.md §3.2`).

### 3.7 Production-stage constant

Add a module constant for the production stage ids the verbs accept (mirrors the
existing `EXIT_STAGES` tuple style, L1349):

```python
#: Production stage ids that carry a stageEntry (the R4 state verbs' --stage domain).
#: Superset of EXIT_STAGES: adds forge-5-loop and forge-6-docs, which also complete.
PRODUCTION_STAGES: Final[tuple[str, ...]] = (
    "forge-0-epic",
    "forge-1-prd",
    "forge-2-tech",
    "forge-3-specs",
    "forge-4-backlog",
    "forge-5-loop",
    "forge-6-docs",
)
```

> **WARNING: verify the `--stage` domain at implementation time.** The staleness
> cascade (§6.3) marks `forge-3-specs..forge-6-docs` stale, and the schema's
> `currentStage` enum (verified) includes all seven production stages plus
> `complete`. `state-enter`/`state-complete` for `forge-5-loop`/`forge-6-docs` are
> included for completeness; if the backlog restricts state verbs to the five
> `EXIT_STAGES`, narrow the `choices` accordingly (the cascade logic in §6.3 is
> independent of this and stays correct either way).

---

## 4. `state-enter` — Entry Stamp (touch point 1)

Replaces the hand-authored **Entry Stamp** write in the Stage-Entry Guard
(`references/shared-conventions.md`, L266–269): `stages.{stage}.status →
"in-progress"`, `stages.{stage}.startedAt → now`, top-level `currentStage →
"{stage}"`, and `updatedAt`. The write stays **uncommitted** until the stage's
exit commit (`00-core-definitions.md §10`, R4 invariant) — the verb writes to disk
only; committing is the skill's separate Git Commit Protocol step.

### 4.1 Argparse registration (in `main()`)

```python
    p_enter = sub.add_parser(
        "state-enter", help="Stamp a stage as in-progress (Entry Stamp)"
    )
    p_enter.add_argument("--feature", required=True, help="Feature name")
    p_enter.add_argument("--stage", required=True, choices=PRODUCTION_STAGES,
                         help="The authoring stage being entered")
    p_enter.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_enter.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_enter.add_argument("--json", action="store_true", dest="json_output")
```

### 4.2 Handler

```python
def cmd_state_enter(
    feature: str, stage: str, specs_dir: Path, epic: str | None
) -> dict:
    """Apply the Entry Stamp: mark ``stage`` in-progress and set currentStage.

    Idempotent on re-entry within the same run: re-stamping an already
    in-progress stage simply refreshes startedAt/updatedAt (the interactive
    resume-vs-restart decision is the skill's, not the verb's — the verb never
    prompts). Leaves the write uncommitted; the exit commit stages it later.

    Args:
        feature: Feature name.
        stage: Production stage id being entered.
        specs_dir: Specs directory.
        epic: Owning epic name, or None.

    Returns:
        The mutated state dict (for --json echo).

    Raises:
        OSError: On unreadable/unwritable state path (→ exit 2).
    """
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    entry = _stage_entry(state, stage)
    entry["status"] = "in-progress"
    entry["startedAt"] = _now_iso()
    state["currentStage"] = stage
    state.setdefault("feature", feature)
    return _commit_state(state_path, state)
```

> **`feature` seeding.** On a brand-new `{}` state, the schema requires
> `feature`, `createdAt`, `pipelineStatus` (§4.1 of doc 00). `state-enter` is the
> first write for a standalone feature's own state, so it seeds `feature`. It does
> **not** invent `createdAt`/`pipelineStatus` unless absent; add them defensively
> so a from-`{}` create validates:
>
> ```python
>     state.setdefault("createdAt", _now_iso())
>     state.setdefault("pipelineStatus", "active")
> ```
>
> For epic members, `epic-manifest.py` already seeds the member state stub
> (verified: `atomic_write(member_state, stub)`, L1402), so these `setdefault`s
> are no-ops there.

### 4.3 `--json` payload shape

The verb echoes the **full resulting state**, e.g. (elided):

```jsonc
{
  "feature": "context-efficiency",
  "createdAt": "2026-07-20T03:30:00Z",
  "updatedAt": "2026-07-20T03:30:00Z",
  "currentStage": "forge-1-prd",
  "pipelineStatus": "active",
  "stages": {
    "forge-1-prd": { "status": "in-progress", "startedAt": "2026-07-20T03:30:00Z" }
  }
}
```

Non-`--json`: a one-line human printer, e.g.
`entered forge-1-prd (in-progress) for context-efficiency`.

### 4.4 Worked example

```bash
python3 "$R/scripts/forge-session.py" state-enter \
  --feature context-efficiency --stage forge-1-prd --specs-dir ./specs --json
```

### 4.5 Error cases (exit 2)

- Missing `--feature`/`--stage` → argparse usage error.
- `--stage` not in `PRODUCTION_STAGES` → argparse `choices` error.
- Unwritable state directory → `OSError` → exit 2.

---

## 5. `state-artifact` — incremental `artifacts[]` (touch point 2)

Replaces the hand-authored incremental-artifact-tracking write
(`references/shared-conventions.md` "Incremental artifact tracking", L275): after
each artifact file is written, append its path to `stages.{stage}.artifacts`.
**Idempotent — never appends a duplicate path** (so a resumed run re-recording an
already-tracked file is a no-op).

### 5.1 Argparse registration

```python
    p_art = sub.add_parser(
        "state-artifact", help="Append an artifact path to a stage (idempotent)"
    )
    p_art.add_argument("--feature", required=True, help="Feature name")
    p_art.add_argument("--stage", required=True, choices=PRODUCTION_STAGES,
                       help="The stage producing the artifact")
    p_art.add_argument("--path", required=True, help="Artifact path (relative to feature dir)")
    p_art.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_art.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_art.add_argument("--json", action="store_true", dest="json_output")
```

### 5.2 Handler

```python
def cmd_state_artifact(
    feature: str, stage: str, path: str, specs_dir: Path, epic: str | None
) -> dict:
    """Append ``path`` to ``stages.{stage}.artifacts`` if not already present.

    Idempotent: an already-tracked path is a no-op (no duplicate append), so a
    resumed run that re-records files it wrote earlier does not bloat the array.
    updatedAt is still refreshed even on the no-op branch, keeping "state was
    touched" honest.

    Args:
        feature: Feature name.
        stage: The producing stage id.
        path: Artifact path relative to the feature dir (e.g. "PRD.md").
        specs_dir: Specs directory.
        epic: Owning epic name, or None.

    Returns:
        The mutated state dict (for --json echo).

    Raises:
        OSError: On unreadable/unwritable state path (→ exit 2).
    """
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    entry = _stage_entry(state, stage)
    artifacts = entry.setdefault("artifacts", [])
    if path not in artifacts:
        artifacts.append(path)
    return _commit_state(state_path, state)
```

### 5.3 `--json` payload shape

Full state echo; the mutated slice of interest:

```jsonc
{ "stages": { "forge-3-specs": { "status": "in-progress",
  "artifacts": ["00-core-definitions.md", "01-architecture-layout.md", "03-state-verbs.md"] } } }
```

Non-`--json`: `tracked forge-3-specs artifact: 03-state-verbs.md (3 total)`.

### 5.4 Worked example (forge-3-specs, per spec file)

```bash
python3 "$R/scripts/forge-session.py" state-artifact \
  --feature context-efficiency --stage forge-3-specs \
  --path 03-state-verbs.md --specs-dir ./specs
```

### 5.5 Error cases (exit 2)

- Missing `--feature`/`--stage`/`--path` → argparse usage error.
- `--stage` not in `PRODUCTION_STAGES` → argparse `choices` error.
- Unwritable state directory → `OSError`.

> The verb does **not** stat the file — it records the path the skill asserts it
> wrote. Whether the file exists on disk is the skill's concern (the Interrupted
> inventory in the Stage-Entry Guard cross-checks disk vs. this array).

---

## 6. `state-complete` — completion, version bump, staleness cascade (touch point 3)

The largest verb. Replaces the hand-authored completion write (each stage's
"Update Pipeline State" step — e.g. forge-1-prd Step 6 item 1,
`skills/forge-1-prd/SKILL.md` L129–134). It performs, deterministically:

1. `stages.{stage}.status → "complete"`, `completedAt → now`.
2. `stages.{stage}.version` bump (or set from `--version`).
3. `stages.{stage}.basedOnVersions` set from the `--based-on K=V` pairs.
4. `stages.{stage}.artifacts` set from the `--artifact P` values (final canonical
   list; supersedes incremental tracking).
5. `stages.{stage}.commitHash → null` (Commit 1 of the two-commit protocol) —
   **unless** `--commit-hash` is given, which is the Commit-2 follow-up (§6.5).
6. **Downstream staleness cascade** (§6.3): mark `forge-3-specs..forge-6-docs`
   `stale` when their `basedOnVersions` reference an **older** version of the
   just-completed stage — logic that is model prose today (forge-1-prd L134) and
   becomes deterministic.

### 6.1 Argparse registration

```python
    p_comp = sub.add_parser(
        "state-complete", help="Mark a stage complete; bump version; cascade staleness"
    )
    p_comp.add_argument("--feature", required=True, help="Feature name")
    p_comp.add_argument("--stage", required=True, choices=PRODUCTION_STAGES,
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
    p_comp.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_comp.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_comp.add_argument("--json", action="store_true", dest="json_output")
```

### 6.2 `--based-on` parsing

```python
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
```

### 6.3 Staleness cascade (deterministic — the folded-in gain)

This is the algorithm that was model prose (forge-1-prd L134: *"If any [downstream
stage] have `basedOnVersions` referencing an older version of `forge-1-prd`, set
their status to `stale`."*). It becomes deterministic Python:

```python
#: Stages the staleness cascade may mark stale (downstream authored artifacts).
#: forge-1-prd/forge-2-tech are never marked stale by a later completion (nothing
#: downstream feeds back into them); the cascade scope is specs..docs.
_CASCADE_TARGETS: Final[tuple[str, ...]] = (
    "forge-3-specs",
    "forge-4-backlog",
    "forge-5-loop",
    "forge-6-docs",
)


def _cascade_staleness(state: dict, completed_stage: str, new_version: int) -> list[str]:
    """Mark downstream stages ``stale`` when they were built on an OLDER version.

    Deterministic replacement for the model-prose rule in each stage's completion
    step. For every downstream target (specs..docs), if its recorded
    ``basedOnVersions[completed_stage]`` is an integer strictly less than
    ``new_version`` AND the stage is currently ``complete``, flip it to ``stale``.
    A downstream stage that never referenced this upstream, or already references
    the new version, is untouched. A ``pending``/``in-progress``/already-``stale``
    downstream stage is not re-flipped (only a ``complete`` artifact can go stale).

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
        if isinstance(recorded, int) and recorded < new_version:
            entry["status"] = "stale"
            newly_stale.append(target)
    return newly_stale
```

> **Behavior-equivalence note (REQ-BEHAV-01).** The prose says "referencing an
> older version." "Older" = strictly-less-than (`recorded < new_version`); an
> equal version is not stale. Only `complete` downstream artifacts are flipped —
> a `pending` stage has no artifact to stale, and re-flipping an already-`stale`
> stage is a no-op. This matches what a careful model applying the prose would do,
> and the drift guard (§12) asserts the cascade against fixtures.

### 6.4 Handler

```python
def cmd_state_complete(
    feature: str,
    stage: str,
    version: int,
    based_on: dict[str, int],
    artifacts: list[str],
    commit_hash: str | None,
    specs_dir: Path,
    epic: str | None,
) -> dict:
    """Mark ``stage`` complete, bump version, record provenance, cascade staleness.

    Sets status=complete, completedAt, version, basedOnVersions, artifacts, and
    commitHash. commitHash is set to ``None`` (Commit 1 of the two-commit Git
    Commit Protocol) UNLESS ``commit_hash`` is provided, in which case this is the
    Commit-2 follow-up recording the real artifact-commit hash (§6.5) and no other
    field is disturbed beyond what a follow-up write should touch. Runs the
    deterministic downstream staleness cascade (§6.3).

    Args:
        feature: Feature name.
        stage: The completing stage id.
        version: The stage's new version.
        based_on: Parsed ``{upstreamStage: version}`` provenance map.
        artifacts: Final canonical artifact path list for this stage.
        commit_hash: If given, record it as the stage's commitHash (Commit 2);
            else set commitHash to None (Commit 1).
        specs_dir: Specs directory.
        epic: Owning epic name, or None.

    Returns:
        The mutated state dict, plus a synthetic ``_cascadedStale`` key stripped
        before schema validation but surfaced in the --json echo/printer.

    Raises:
        OSError: On unreadable/unwritable state path (→ exit 2).
    """
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    entry = _stage_entry(state, stage)
    if commit_hash is not None:
        # Commit-2 follow-up: record the real hash, leave everything else intact.
        entry["commitHash"] = commit_hash
        cascaded: list[str] = []
    else:
        entry["status"] = "complete"
        entry["completedAt"] = _now_iso()
        entry["version"] = version
        entry["basedOnVersions"] = based_on
        entry["artifacts"] = artifacts
        entry["commitHash"] = None
        cascaded = _cascade_staleness(state, stage, version)
    result = _commit_state(state_path, state)
    # Surface the cascade result for the caller without persisting it in state.
    echo = dict(result)
    echo["_cascadedStale"] = cascaded
    return echo
```

> **`_cascadedStale` is echo-only.** It is added to the returned dict for the
> `--json` echo/printer, **not** written to disk (`_commit_state` wrote the real
> `state`; `echo` is a copy). This keeps the persisted state schema-clean
> (`additionalProperties` at the array shapes; the top level tolerates extra keys
> but we still avoid a non-schema field on disk).

### 6.5 The two-commit `--commit-hash` follow-up (REQ-BEHAV-02, C-1)

The Git Commit Protocol (`references/shared-conventions.md` L236–249) is a **frozen
interactive protocol** and must not change (`00-core-definitions.md §10`, R4 row).
R4 preserves it exactly; only the JSON-authoring mechanic inside it changes:

- **Commit 1 (artifact commit).** The skill calls `state-complete … --version N
  --based-on … --artifact …` (no `--commit-hash`). The verb sets `status:
  "complete"` and `commitHash: null`, writes state uncommitted, then the skill
  runs `git add {specsDir}/{feature}/` + `git commit` per the protocol. The
  provenance hash is this commit's.
- **Commit 2 (record the hash).** The skill captures `git rev-parse HEAD`, then
  calls `state-complete … --commit-hash <h>` — the **same verb**, reusing OQ-3's
  decision (tech-spec §10, `00-core-definitions.md §5`) to avoid a separate
  hash-writing verb. This branch (`commit_hash is not None`, §6.4) sets **only**
  `commitHash`, leaving `status`/`version`/`artifacts` intact, then the skill
  commits that one-line change.

**NEVER `--amend`.** The verb does no git work; it only writes JSON. The
"never-amend" guarantee is upheld by the skill's unchanged protocol prose. The
verb's split of "set null on completion / set hash on follow-up" is exactly what
makes the recorded `commitHash` point at the artifact commit (Commit 1), never an
orphaned amend.

### 6.6 `--json` payload shape

```jsonc
{
  "currentStage": "forge-2-tech",
  "stages": {
    "forge-1-prd": { "status": "complete", "version": 2, "completedAt": "2026-07-20T04:00:00Z",
                     "artifacts": ["PRD.md"], "basedOnVersions": {}, "commitHash": null },
    "forge-3-specs": { "status": "stale" }
  },
  "_cascadedStale": ["forge-3-specs"]
}
```

Non-`--json`: `completed forge-1-prd v2 (commitHash: null); marked stale: forge-3-specs`.

### 6.7 Worked examples

Commit 1 (forge-1-prd, no upstream deps):

```bash
python3 "$R/scripts/forge-session.py" state-complete \
  --feature context-efficiency --stage forge-1-prd --version 2 \
  --artifact PRD.md --specs-dir ./specs --json
```

Commit 1 (forge-3-specs, built on PRD v2 + tech v1):

```bash
python3 "$R/scripts/forge-session.py" state-complete \
  --feature context-efficiency --stage forge-3-specs --version 1 \
  --based-on forge-1-prd=2 --based-on forge-2-tech=1 \
  --artifact 00-core-definitions.md --artifact 03-state-verbs.md \
  --artifact TRACEABILITY.md --specs-dir ./specs
```

Commit 2 (record the hash after the artifact commit):

```bash
python3 "$R/scripts/forge-session.py" state-complete \
  --feature context-efficiency --stage forge-1-prd \
  --version 2 --commit-hash "$(git rev-parse HEAD)" --specs-dir ./specs
```

> `--version` remains `required=True` on the Commit-2 call for argparse
> simplicity; the handler ignores it on the `commit_hash is not None` branch (it
> touches only `commitHash`). The skill passes the same `--version` it used for
> Commit 1.

### 6.8 Error cases (exit 2)

- Missing `--feature`/`--stage`/`--version` → argparse usage error.
- `--version` not an integer → argparse `type=int` error.
- Malformed `--based-on` token (no `=`, or non-int value) → `UsageError` (§6.2).
- `--stage` not in `PRODUCTION_STAGES` → argparse `choices` error.
- Unwritable state directory → `OSError`.

---

## 7. `state-note` — `notes` (touch point 4)

Replaces the hand-authored `notes` write in the stage-exit "offer a note" step
(e.g. forge-1-prd Step 6 item 2, L135). The verb sets the top-level `notes`
string; it does **not** prompt — the "offer a note, don't force one" statement
stays in the skill prose verbatim (`00-core-definitions.md §10`, R4 row), and the
verb runs only if the user volunteered something.

### 7.1 Argparse registration

```python
    p_note = sub.add_parser("state-note", help="Set the top-level notes field")
    p_note.add_argument("--feature", required=True, help="Feature name")
    p_note.add_argument("--note", required=True, help="Note text to persist")
    p_note.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_note.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_note.add_argument("--json", action="store_true", dest="json_output")
```

### 7.2 Handler

```python
def cmd_state_note(
    feature: str, note: str, specs_dir: Path, epic: str | None
) -> dict:
    """Set the top-level ``notes`` field to ``note``.

    Overwrites any existing note (the field is a single free-text string, not an
    append log — matching the schema's ``notes: string``). The skill's
    "offer a note — don't force one" statement is unchanged; this verb runs only
    when the user volunteered text.

    Args:
        feature: Feature name.
        note: The note text.
        specs_dir: Specs directory.
        epic: Owning epic name, or None.

    Returns:
        The mutated state dict (for --json echo).

    Raises:
        OSError: On unreadable/unwritable state path (→ exit 2).
    """
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    state["notes"] = note
    return _commit_state(state_path, state)
```

### 7.3 `--json` payload / example

```jsonc
{ "notes": "Cache backend deferred to forge-2-tech; see deferredDecisions." }
```

```bash
python3 "$R/scripts/forge-session.py" state-note \
  --feature context-efficiency --note "Rebaselined tokens at impl time." --specs-dir ./specs
```

Non-`--json`: `note set for context-efficiency (48 chars)`.

### 7.4 Error cases (exit 2)

- Missing `--feature`/`--note` → argparse usage error.
- Unwritable state directory → `OSError`.

---

## 8. `state-decision` — `deferredDecisions[]` (touch point 5)

Replaces the hand-authored `deferredDecisions[]` append in the deferred-decisions
rule (`references/stage-exit-protocol.md` L184–192). Appends a
`{question, rationale?, targetStage?, raisedBy, raisedAt, status:"open"}` item
(shape from `00-core-definitions.md §4.3`; `additionalProperties: false` — emit
exactly these keys). The recorder always writes `status:"open"`.

### 8.1 Argparse registration

```python
    p_dec = sub.add_parser(
        "state-decision", help="Append a deferred decision (status: open)"
    )
    p_dec.add_argument("--feature", required=True, help="Feature name")
    p_dec.add_argument("--question", required=True,
                       help="The deferred decision, phrased for the target stage")
    p_dec.add_argument("--raised-by", required=True, dest="raised_by",
                       choices=("forge-1-prd", "forge-2-tech", "forge-3-specs", "forge-4-backlog"),
                       help="The stage deferring the decision")
    p_dec.add_argument("--rationale", default=None, help="Why it is deferred (optional)")
    p_dec.add_argument("--target-stage", default=None, dest="target_stage",
                       choices=("forge-1-prd", "forge-2-tech", "forge-3-specs",
                                "forge-4-backlog", "forge-5-loop", "forge-6-docs"),
                       help="The stage that should resolve it (optional)")
    p_dec.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_dec.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_dec.add_argument("--json", action="store_true", dest="json_output")
```

> `--raised-by` and `--target-stage` `choices` mirror the schema enums
> (`00-core-definitions.md §4.3`; verified against `pipeline-state-schema.json`
> L103–106 and L98–101), so an out-of-enum value is rejected at parse time.

### 8.2 Handler

```python
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

    Emits exactly the schema keys (00-core-definitions §4.3;
    additionalProperties: false): required question/raisedBy/raisedAt/status,
    plus rationale/targetStage only when provided. status is always "open"
    (the recorder never resolves; the target stage flips it to "addressed").

    Args:
        feature: Feature name.
        question: The deferred decision, phrased for the target stage.
        raised_by: The deferring stage id.
        rationale: Optional reason for deferring.
        target_stage: Optional resolving stage id.
        specs_dir: Specs directory.
        epic: Owning epic name, or None.

    Returns:
        The mutated state dict (for --json echo).

    Raises:
        OSError: On unreadable/unwritable state path (→ exit 2).
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
```

### 8.3 `--json` payload / example

```jsonc
{ "deferredDecisions": [
  { "question": "Which cache backend?", "rationale": "forge-2-tech designs it",
    "targetStage": "forge-2-tech", "raisedBy": "forge-1-prd",
    "raisedAt": "2026-07-20T04:00:00Z", "status": "open" } ] }
```

```bash
python3 "$R/scripts/forge-session.py" state-decision \
  --feature context-efficiency \
  --question "Which cache backend?" --rationale "forge-2-tech designs it" \
  --target-stage forge-2-tech --raised-by forge-1-prd --specs-dir ./specs
```

Non-`--json`: `deferred decision recorded (raisedBy forge-1-prd → forge-2-tech)`.

### 8.4 Error cases (exit 2)

- Missing `--feature`/`--question`/`--raised-by` → argparse usage error.
- `--raised-by`/`--target-stage` out of enum → argparse `choices` error.
- Unwritable state directory → `OSError`.

---

## 9. `state-ecr` — `epicChangeRequests[]` (touch point 6)

Replaces the hand-authored `epicChangeRequests[]` append in epic-backflow
recording (forge-1-prd / forge-2-tech, per the epic-backflow rule). Appends a
`{kind, target, rationale, blocksCurrent, raisedBy, raisedAt, status:"open"}` item
(shape from `00-core-definitions.md §4.4`; `additionalProperties: false`). The
`blocksCurrent` boolean drives stage-exit routing, so it is **required**.

### 9.1 Argparse registration

```python
    p_ecr = sub.add_parser(
        "state-ecr", help="Append an epic change request (status: open)"
    )
    p_ecr.add_argument("--feature", required=True, help="Feature name")
    p_ecr.add_argument("--kind", required=True,
                       choices=("add-feature", "redep", "move-boundary", "split"),
                       help="The decomposition change kind")
    p_ecr.add_argument("--target", required=True,
                       help="The sibling feature to add, or the feature/boundary affected")
    p_ecr.add_argument("--rationale", required=True, help="Why the epic must change")
    p_ecr.add_argument("--raised-by", required=True, dest="raised_by",
                       choices=("forge-1-prd", "forge-2-tech"),
                       help="The stage that detected the epic-level concern")
    p_ecr.add_argument("--blocks-current", required=True, dest="blocks_current",
                       help="true → pause-now (reconcile before proceeding); false → finish-then-edit")
    p_ecr.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_ecr.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_ecr.add_argument("--json", action="store_true", dest="json_output")
```

### 9.2 Boolean parsing (`--blocks-current`)

`--blocks-current` takes an explicit `true|false` string (the CLI signature is
`--blocks-current BOOL`, tech-spec §5). Parse it strictly — a typo must fail, not
silently coerce (mirrors the fail-closed spirit of `auto_verify_for`, L544):

```python
def _parse_bool(raw: str, flag: str) -> bool:
    """Parse an explicit boolean CLI value; fail closed on anything else.

    Args:
        raw: The raw flag value (e.g. from ``--blocks-current``).
        flag: The flag name, for the error message.

    Returns:
        ``True`` for ``"true"``, ``False`` for ``"false"`` (case-insensitive).

    Raises:
        UsageError: For any other value (→ exit 2), so a typo like ``"yes"`` or
            ``"True "`` is rejected rather than silently misrouting stage-exit.
    """
    normalized = raw.strip().lower()
    if normalized == "true":
        return True
    if normalized == "false":
        return False
    raise UsageError(f"{flag} expects true|false, got: {raw!r}")
```

### 9.3 Handler

```python
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

    Emits exactly the schema keys (00-core-definitions §4.4;
    additionalProperties: false). status is always "open" (only forge-0-epic
    edit mode flips it). blocksCurrent drives stage-exit routing, so it is a
    required, strictly-parsed boolean (§9.2).

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
        The mutated state dict (for --json echo).

    Raises:
        OSError: On unreadable/unwritable state path (→ exit 2).
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
```

### 9.4 `--json` payload / example

```jsonc
{ "epicChangeRequests": [
  { "kind": "add-feature", "target": "shared-conventions-split",
    "rationale": "R7 emerged as a distinct feature", "blocksCurrent": false,
    "raisedBy": "forge-2-tech", "raisedAt": "2026-07-20T04:00:00Z", "status": "open" } ] }
```

```bash
python3 "$R/scripts/forge-session.py" state-ecr \
  --feature context-efficiency --kind add-feature --target shared-conventions-split \
  --rationale "R7 emerged as a distinct feature" \
  --raised-by forge-2-tech --blocks-current false --specs-dir ./specs
```

Non-`--json`: `epic change request recorded (add-feature → shared-conventions-split, blocksCurrent=false)`.

### 9.5 Error cases (exit 2)

- Missing any required flag → argparse usage error.
- `--kind`/`--raised-by` out of enum → argparse `choices` error.
- `--blocks-current` not `true|false` → `UsageError` (§9.2).
- Unwritable state directory → `OSError`.

---

## 10. `state-branch` — `branch` (touch point 7)

Replaces the hand-authored top-level `branch` write in Branch Setup ("Record the
branch", `references/shared-conventions.md` L217) and Branch Reconciliation
(`adopt-current`, L230). The verb sets the top-level `branch` string; the
surrounding prompts, the "self-healing hint" narration, and the "never silently /
never push the user back" caveats stay in the skill prose verbatim
(`00-core-definitions.md §10`, R4 row).

### 10.1 Argparse registration

```python
    p_br = sub.add_parser("state-branch", help="Set the top-level branch field")
    p_br.add_argument("--feature", required=True, help="Feature name")
    p_br.add_argument("--branch", required=True, help="Branch name to record")
    p_br.add_argument("--specs-dir", default="./specs", help="Specs directory")
    p_br.add_argument("--epic", default=None, help="Epic name for a nested member")
    p_br.add_argument("--json", action="store_true", dest="json_output")
```

### 10.2 Handler

```python
def cmd_state_branch(
    feature: str, branch: str, specs_dir: Path, epic: str | None
) -> dict:
    """Set the top-level ``branch`` field to ``branch``.

    Records the branch resolved by Branch Setup / Branch Reconciliation. The verb
    only writes the field; the interactive prompts and the visible one-line
    reconciliation note (shared-conventions.md) are unchanged skill prose.

    Args:
        feature: Feature name.
        branch: The branch name to record.
        specs_dir: Specs directory.
        epic: Owning epic name, or None.

    Returns:
        The mutated state dict (for --json echo).

    Raises:
        OSError: On unreadable/unwritable state path (→ exit 2).
    """
    state_path, state = _load_state_for_write(specs_dir, feature, epic)
    state["branch"] = branch
    return _commit_state(state_path, state)
```

### 10.3 `--json` payload / example

```jsonc
{ "branch": "forge/context-efficiency" }
```

```bash
python3 "$R/scripts/forge-session.py" state-branch \
  --feature context-efficiency --branch forge/context-efficiency --specs-dir ./specs
```

Non-`--json`: `recorded branch for context-efficiency: forge/context-efficiency`.

### 10.4 Error cases (exit 2)

- Missing `--feature`/`--branch` → argparse usage error.
- Unwritable state directory → `OSError`.

---

## 11. `main()` wiring & touch-point conversion map

### 11.1 Dispatch branches (in `main()`'s `if args.cmd == …` chain, before the final `raise UsageError`)

```python
        if args.cmd == "state-enter":
            payload = cmd_state_enter(
                args.feature, args.stage, Path(args.specs_dir), args.epic
            )
            _emit(payload, args.json_output, _print_state_enter)
            return 0

        if args.cmd == "state-artifact":
            payload = cmd_state_artifact(
                args.feature, args.stage, args.path, Path(args.specs_dir), args.epic
            )
            _emit(payload, args.json_output, _print_state_artifact)
            return 0

        if args.cmd == "state-complete":
            payload = cmd_state_complete(
                args.feature, args.stage, args.version,
                _parse_based_on(args.based_on), args.artifacts, args.commit_hash,
                Path(args.specs_dir), args.epic,
            )
            _emit(payload, args.json_output, _print_state_complete)
            return 0

        if args.cmd == "state-note":
            payload = cmd_state_note(
                args.feature, args.note, Path(args.specs_dir), args.epic
            )
            _emit(payload, args.json_output, _print_state_note)
            return 0

        if args.cmd == "state-decision":
            payload = cmd_state_decision(
                args.feature, args.question, args.raised_by, args.rationale,
                args.target_stage, Path(args.specs_dir), args.epic,
            )
            _emit(payload, args.json_output, _print_state_decision)
            return 0

        if args.cmd == "state-ecr":
            payload = cmd_state_ecr(
                args.feature, args.kind, args.target, args.rationale, args.raised_by,
                _parse_bool(args.blocks_current, "--blocks-current"),
                Path(args.specs_dir), args.epic,
            )
            _emit(payload, args.json_output, _print_state_ecr)
            return 0

        if args.cmd == "state-branch":
            payload = cmd_state_branch(
                args.feature, args.branch, Path(args.specs_dir), args.epic
            )
            _emit(payload, args.json_output, _print_state_branch)
            return 0
```

The existing top-level `except UsageError/OSError → return 2` tail (L1857–1862)
catches every verb's failures unchanged — no new exit-code semantics. `_emit` is a
tiny shared dispatcher matching the existing pattern (`json.dumps(..., indent=2,
ensure_ascii=False)` on `--json`, else the human printer):

```python
def _emit(payload: dict, json_output: bool, printer) -> None:
    """Emit a verb result: JSON on --json (matching existing subcommands), else printer."""
    if json_output:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        printer(payload)
```

### 11.2 Touch-point conversion map (REQ-R4-04 — every hand-authored write retired)

Each row is a write that hand-authored JSON **today** and becomes a verb call.
No site may keep authoring JSON (a partial extraction is not acceptable, PRD
REQ-R4-04). Prose stays verbatim (§13); only the mechanic swaps.

| Owning surface | Hand-authored write today (source) | Becomes verb call |
|---|---|---|
| `references/shared-conventions.md` — Stage-Entry Guard, Entry Stamp (L266–269) | set `stages.{stage}.status=in-progress`, `.startedAt`, `currentStage` | `state-enter --feature … --stage …` |
| `references/shared-conventions.md` — Incremental artifact tracking (L275) | append to `stages.{stage}.artifacts` after each file | `state-artifact --feature … --stage … --path …` |
| `references/shared-conventions.md` — Branch Setup "Record the branch" (L217) + Branch Reconciliation `adopt-current` (L230) | set top-level `branch` | `state-branch --feature … --branch …` |
| `references/shared-conventions.md` — Git Commit Protocol (L243/L244) | Commit 1 `commitHash:null`; Commit 2 record hash | `state-complete … (no --commit-hash)` then `state-complete … --commit-hash <h>` |
| `references/stage-exit-protocol.md` — deferred-decisions rule (L184–192) | append `deferredDecisions[]` item | `state-decision --feature … --question … --raised-by …` |
| `skills/forge-0-epic/SKILL.md` — epic decomposition completion / member stubbing | set epic-stage completion + member `branch` | `state-complete` (+ `state-branch` for members) |
| `skills/forge-1-prd/SKILL.md` — Step 6 Update Pipeline State (L129–134) + offer-a-note (L135) | completion + version bump + staleness cascade + `notes` | `state-complete …` (+ cascade folded in) and `state-note …` if volunteered |
| `skills/forge-1-prd` / `skills/forge-2-tech` — epic-backflow recording | append `epicChangeRequests[]` item | `state-ecr --feature … --kind … --target … --blocks-current …` |
| `skills/forge-2-tech/SKILL.md` — completion step | completion + version bump + `basedOnVersions` + cascade | `state-complete --based-on forge-1-prd=N …` |
| `skills/forge-3-specs/SKILL.md` — per-spec incremental writes + completion | incremental `artifacts[]` per file; completion | `state-artifact` (per file) then `state-complete …` |
| `skills/forge-4-backlog/SKILL.md` — completion step | completion + version bump + `basedOnVersions` + cascade | `state-complete --based-on … …` |
| `skills/forge-verify/SKILL.md` — production-stage entry/exit stamps it authors (NOT the verifyEntry) | any `stageEntry` writes it performs | matching `state-*` verb (verifyEntry path unchanged, `00 §4.2`) |

> **`shared-conventions.md` prose caveat.** These edits switch the *mechanic*
> (the fenced "edit the JSON" / "write to `.pipeline-state.json`" step becomes a
> fenced verb call), never the *prose* of the surrounding protocol
> (`00-core-definitions.md §10`; §13 below shows a concrete before/after). The
> exact edited lines and the compact-prelude form the fenced calls use are owned
> by `04-effective-config.md` (the shared-conventions edits) and
> `05-instruction-relocations.md` (the R2 prelude form); this doc specifies the
> verb contracts those calls invoke.

---

## 12. Schema conformance & drift guard (REQ-R4-03, REQ-MAINT-01 R4 slice)

`pipeline-state-schema.json` is **unchanged** and remains the CI/validation
authority (REQ-R4-03). Because the verbs construct state programmatically,
malformed state is a **code bug caught in CI**, not a runtime user error
(tech-spec §7). The contract the drift guard (`06-testing-strategy.md §4`)
enforces:

- Each `state-*` verb, run against a temp fixture, produces a
  `.pipeline-state.json` that validates against `pipeline-state-schema.json` using
  the **stdlib** structural validator (reusing `epic-manifest.py`'s hand-rolled
  `_schema_findings()` pattern — **no `jsonschema`**, C-2 / `00-core-definitions.md
  §3.4`).
- `state-decision` / `state-ecr` items carry **exactly** the schema keys
  (`additionalProperties: false`, `00-core-definitions.md §4.3/§4.4`) — no extra
  keys, all required keys present.
- The staleness cascade (§6.3) is asserted against a fixture where a downstream
  `complete` stage references an older upstream version → it flips to `stale`;
  an equal/absent reference does not.
- The persisted state never contains the echo-only `_cascadedStale` key (§6.4).

This doc does not restate the guard's assertions — it fixes the behavior they
verify.

---

## 13. Prose-unchanged invariant (REQ-BEHAV-01/02, C-1)

R4 changes **only** the JSON-authoring mechanic. The frozen protocols
(`00-core-definitions.md §10`, R4 row) keep exact prose and turn structure. The
verb call slots in **where the "edit the JSON" step was** — nowhere else.

### 13.1 Concrete before/after (forge-1-prd Step 6, item 1)

**Before** (`skills/forge-1-prd/SKILL.md` L129–134, verbatim):

> 1. Create or update `{resolvedFeatureDir}/.pipeline-state.json`:
>    - Set `currentStage` to `forge-2-tech`
>    - Set `stages.forge-1-prd.version` to 1 (or increment if revising)
>    - Record `artifacts`, `completedAt`
>    - Set `stages.forge-1-prd.basedOnVersions` to `{}` (no upstream dependencies)
>    - Check downstream stages (`forge-2-tech`, `forge-3-specs`, `forge-4-backlog`,
>      `forge-5-loop`, `forge-6-docs`). If any have `basedOnVersions` referencing an
>      older version of `forge-1-prd`, set their status to `stale`.

**After** (mechanic swapped; the deterministic cascade is now the verb's job, so
the manual "check downstream stages" bullet is *executed by* the call rather than
re-described as a hand edit):

> 1. Record completion by running the `state-complete` verb (it sets
>    `status: "complete"`, `completedAt`, the version bump, `basedOnVersions`, the
>    artifact list, `commitHash: null`, and applies the downstream staleness
>    cascade deterministically):
>    ```bash
>    Resolve `$R` via the plugin-root prelude shown at the top of this skill, then run:
>    python3 "$R/scripts/forge-session.py" state-complete \
>      --feature "{feature}" --stage forge-1-prd --version {n} \
>      --artifact PRD.md --specs-dir "{specsDir}"
>    ```

The **surrounding** protocol is byte-identical: item 2 ("Offer a note — don't
force one") is unchanged (the `notes` write, if the user volunteers, becomes a
`state-note` call); item 3 (the Git Commit Protocol reference, two-commit,
never-`--amend`) is unchanged, with the Commit-2 hash write becoming
`state-complete … --commit-hash`; item 4 (Scripted Stage Exit) is unchanged.

### 13.2 What must NOT change (drift-guard-enforced, `00-core-definitions.md §10`)

- Stage-Entry Guard classification (fresh / interrupted / re-authoring) and its
  `AskUserQuestion` prompts.
- Branch Setup / Branch Reconciliation prompts and the visible one-line adopt
  note.
- The "offer a note — don't force one" **statement** (not a blocking question).
- The two-commit Git Commit Protocol order, and **never** `--amend`/`--no-verify`/
  `-A`/`--force`.
- The entry stamp stays **uncommitted** until the stage's exit commit.

If moving any of that text forces a wording change, it MUST be flagged in review,
never silently adapted (REQ-BEHAV-02).

---

## Dependencies

- **`00-core-definitions.md`** — script conventions (§3, incl. exit-code contract
  and the `_write_state` canonical signature), state JSON shapes (§4),
  touch-point inventory (§5), frozen-protocol invariants (§10). **Must be read
  first; its contracts are not restated here.**
- **`references/pipeline-state-schema.json`** — the unchanged data contract every
  verb's output must satisfy (REQ-R4-03).
- **Ships after R5** (`04-effective-config.md`) per the delivery sequence
  (`01-architecture-layout.md §5`); R5 establishes the "new forge-session
  subcommand + stdlib schema drift-guard" pattern this doc reuses at scale.

## Verification

An implementation matches this spec when:

- [ ] `forge-session.py` gains `_write_state` (atomic, temp-in-dir + `os.replace`,
      mirroring `epic-manifest.py` L315) and `_now_iso` (`Z`-suffixed UTC), with
      `import tempfile` added if the `mkstemp` form is used (§3.2/§3.3).
- [ ] All seven verbs (`state-enter`, `state-artifact`, `state-complete`,
      `state-note`, `state-decision`, `state-ecr`, `state-branch`) are registered
      as argparse subparsers in `main()` and dispatched in the `if args.cmd == …`
      chain, before the final `raise UsageError` (§11.1).
- [ ] Every verb refreshes `updatedAt` on every successful write (via
      `_commit_state`) and writes atomically (§3.4).
- [ ] Exit codes are **0/2 only** — no exit 1; `UsageError`/`OSError` degrade to
      exit 2 under the existing top-level handler (`00-core-definitions.md §3.2`).
- [ ] `--json` on every verb emits `json.dumps(payload, indent=2,
      ensure_ascii=False)` to stdout; each verb has a human-readable printer.
- [ ] `state-complete` bumps the version, records `basedOnVersions` from
      `--based-on`, sets `commitHash: null` on completion, and runs the
      deterministic downstream staleness cascade (§6.3); a second call with
      `--commit-hash` records the hash and touches nothing else (§6.5).
- [ ] The cascade marks a `complete` downstream stage `stale` **iff** its
      `basedOnVersions[stage]` is an integer strictly less than the new version;
      equal/absent/non-`complete` are untouched (§6.3).
- [ ] `state-decision` / `state-ecr` emit **exactly** the schema keys
      (`additionalProperties: false`), always `status:"open"` (§8/§9).
- [ ] `--blocks-current` is strictly parsed `true|false`; any other value → exit 2
      (§9.2).
- [ ] The stdlib drift guard (`06-testing-strategy.md §4`) confirms each verb's
      output validates against `pipeline-state-schema.json` (no `jsonschema`,
      REQ-R4-03).
- [ ] Every hand-authored state write in the conversion map (§11.2) is retired —
      **no** pipeline surface still hand-authors `.pipeline-state.json` (REQ-R4-04).
- [ ] The frozen protocols in §13.2 are byte-identical to their pre-R4 wording;
      only the "edit the JSON" mechanic changed (`grep`/diff against the prior
      revision; drift guards in `06-testing-strategy.md`).
- [ ] `ruff check scripts/ eval/` passes and no third-party import was added
      beyond stdlib (C-2).
