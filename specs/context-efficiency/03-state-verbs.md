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
| `import os`, `import json`, `from datetime import datetime, timezone` | L79–86 | already present; `_now_iso` needs no new import |
| `PRODUCTION_STAGES` | L99 (6 entries, **order-sensitive**) | `STATE_VERB_STAGES` is derived from it (§3.7); **never redefined** |

`os` and `json` are already imported (verified L80–81), and `datetime`/`timezone` are
already imported for `_now_iso` (verified L84). **`tempfile` is the one new stdlib import
R4 adds** (§3.3, the canonical `mkstemp`+`fsync` form); everything else the verbs need is
already present (C-2: stdlib-only, no `jsonschema`).

> **WARNING: could not confirm an existing `_now_iso` helper.** `grep` of
> `forge-session.py` found **no** `_now_iso`/`now_iso`/`_iso` helper; the script
> generates timestamps inline (`datetime.now(timezone.utc)` at L435; parses with
> `datetime.fromisoformat(...replace("Z","+00:00"))` at L371). `epic-manifest.py`
> writes timestamps as `datetime.now(timezone.utc).isoformat()` (L1093). R4
> therefore **introduces** a small `_now_iso()` helper (§3.2) rather than reusing
> one. `00-core-definitions.md §3.3` says the same ("the R4 work **introduces**"),
> so the two documents agree. Re-confirm at implementation time that no equivalent
> helper landed between spec and build.

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

    Reuses the existing resolver (_resolve_feature_dir, L1416). Deliberately does
    NOT reuse _read_state (L177): that reader downgrades a *corrupt* file to {}
    because the navigator's read-only sweep can safely treat it as not-started.
    A writer that inherited it would atomically replace a corrupt-but-recoverable
    state file with a near-empty one at exit 0. So: absent -> {}; present but
    unparseable -> refuse.

    The verbs never create a feature directory; an unknown --feature is a usage
    error, not a silent create.

    Args:
        specs_dir: The configured specs directory (``--specs-dir``).
        feature: The feature name (``--feature``).
        epic: The owning epic name for a nested member, else None (``--epic``).

    Returns:
        A ``(state_path, state)`` tuple. ``state`` is a schema-shaped shell when
        no state file exists yet (see the seeding below).

    Raises:
        UsageError: the feature directory does not exist, or the state file
            exists but is not a JSON object (→ exit 2).
    """
    state_dir = _resolve_feature_dir(specs_dir, feature, epic)
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

    # Seed the six schema-required top-level fields for EVERY verb, not just
    # state-enter. Branch Setup fires state-branch before the entry stamp
    # (shared-conventions.md L217), so without this a first-write state-branch
    # would persist {"branch": ..., "updatedAt": ...} -- missing every required
    # field -- at exit 0. setdefault keeps an existing state untouched.
    state.setdefault("feature", feature)
    state.setdefault("createdAt", _now_iso())
    state.setdefault("pipelineStatus", "active")
    state.setdefault("stages", {})
    state.setdefault("currentStage", PRODUCTION_STAGES[0])
    return state_path, state


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

    Bootstraps ``state["stages"]`` and ``state["stages"][stage]`` when missing, so
    a verb can write into a brand-new state ({}), and returns the stage dict for
    in-place mutation. The bootstrap seeds ``{"status": "pending"}`` rather than
    ``{}`` because ``stageEntry`` declares ``required: ["status"]`` -- an entry
    created by state-artifact (which sets only ``artifacts``) would otherwise be
    schema-invalid at exit 0.

    Args:
        state: The full state dict (mutated in place).
        stage: A production stage id (e.g. ``"forge-1-prd"``).

    Returns:
        The mutable ``stages.{stage}`` dict.
    """
    stages = state.setdefault("stages", {})
    return stages.setdefault(stage, {"status": "pending"})
```

### 3.6 Argument validation & exit-2 conditions common to all verbs

- `--feature` is `required=True` on every verb; argparse emits a usage error (its
  own exit) if absent — consistent with existing subcommands (e.g. `stage-exit`,
  L1753).
- `--stage` on the three `stages`-writing verbs uses
  `choices=STATE_VERB_STAGES` (see §4) so an unknown stage id is rejected at parse
  time.
- Any I/O failure (unreadable specs tree, unwritable state dir) raises `OSError`,
  caught by the top-level handler → **exit 2** with `Error: …` on stderr
  (`00-core-definitions.md §3.2`).
- A semantically-invalid argument that argparse cannot express (e.g. a
  `--based-on` token without `=`, §6.2; a non-boolean `--blocks-current`, §9.2)
  raises `UsageError` → **exit 2**.
- There is **no exit 1** (`00-core-definitions.md §3.2`).

### 3.7 The `--stage` domain constant

> **`PRODUCTION_STAGES` ALREADY EXISTS — do NOT redefine it.** `scripts/forge-session.py`
> L99 defines it as a **6-entry, order-sensitive** tuple with no `forge-0-epic`, and live
> logic depends on that order: `next_stage()` walks it (L245), `verify_state` walks
> `reversed(...)` (L317), and `stage_exit` compares
> `PRODUCTION_STAGES.index(state_next) > PRODUCTION_STAGES.index(stage)` (L1602–1604).
> A second module-level assignment wins at import time, so redefining it with
> `forge-0-epic` first would make `next_stage()` return `forge-0-epic` for **every**
> standalone feature — a stage standalone features never record — breaking the navigator's
> "what runs next" and the scripted stage-exit's successor comparison. That is a runtime
> behavior change, forbidden by REQ-BEHAV-01.

The verbs accept a **superset** of that tuple, so they get their own name, derived from
the existing constant rather than duplicating it:

```python
#: The --stage domain for the R4 state verbs: the six existing PRODUCTION_STAGES
#: (L99, order-sensitive — do NOT redefine) plus forge-0-epic, which also carries
#: a stageEntry but is excluded from the next-stage walk.
STATE_VERB_STAGES: Final[tuple[str, ...]] = ("forge-0-epic", *PRODUCTION_STAGES)
```

Every verb's argparse registration uses `choices=STATE_VERB_STAGES` (§4.1, §5.1, §6.1).
The staleness cascade (§6.3) keys off its own `_CASCADE_TARGETS` map and is unaffected.

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
    p_enter.add_argument("--stage", required=True, choices=STATE_VERB_STAGES,
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
- `--stage` not in `STATE_VERB_STAGES` → argparse `choices` error.
- Unwritable state directory / failed atomic write → `UsageError` (wrapped `OSError`, §3.3) → exit 2.
- Feature directory does not exist, or state file unparseable → `UsageError` (§3.4).

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
    p_art.add_argument("--stage", required=True, choices=STATE_VERB_STAGES,
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
- `--stage` not in `STATE_VERB_STAGES` → argparse `choices` error.
- Unwritable state directory / failed atomic write → `UsageError` (wrapped `OSError`, §3.3) → exit 2.
- Feature directory does not exist, or state file unparseable → `UsageError` (§3.4).

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
6. **Downstream staleness cascade** (§6.3): mark `forge-2-tech..forge-6-docs`
   `stale` when their `basedOnVersions` reference an **older** version of the
   just-completed stage — logic that is model prose today (forge-1-prd L134) and
   becomes deterministic.

### 6.1 Argparse registration

```python
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
    p_comp.add_argument("--status", default="complete",
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
#: The scope is tech..docs, matching the pre-R4 canon this cascade replaces —
#: forge-1-prd L134 named `forge-2-tech` FIRST among the stages a PRD revision
#: invalidates. forge-1-prd is never marked stale by a later completion (nothing
#: downstream feeds back into it).
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
    step. For every downstream target (tech..docs), if its recorded
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
    status: str = "complete",
    preserve_commit_hash: bool = False,
    resumable: bool = False,
) -> dict:
    """Mark ``stage`` complete, bump version, record provenance, cascade staleness.

    Sets status (default "complete"), completedAt, version, basedOnVersions,
    artifacts, and commitHash. commitHash is set to ``None`` (Commit 1 of the
    Commit Protocol) UNLESS ``commit_hash`` is provided, in which case this is the
    Commit-2 follow-up recording the real artifact-commit hash (§6.5) and no other
    field is disturbed beyond what a follow-up write should touch. Runs the
    deterministic downstream staleness cascade (§6.3).

    **Exception -- ``resumable``:** the failed-Commit-1 revert (§6.5) records ONLY
    ``status = "in-progress"`` plus the ``updatedAt`` refresh -- no completedAt, no
    version bump, no basedOnVersions/artifacts write, no commitHash reset, no
    cascade. This is gated on ``resumable``, NOT on ``status == "in-progress"``:
    forge-5-loop's PARTIAL completion also passes ``--status in-progress`` but is a
    real completion-with-artifacts and keeps every field (§11.2 row 14).

    Args:
        feature: Feature name.
        stage: The completing stage id.
        version: The stage's new version.
        based_on: Parsed ``{upstreamStage: version}`` provenance map.
        artifacts: Final canonical artifact path list for this stage.
        commit_hash: If given, record it as the stage's commitHash (Commit 2);
            else set commitHash to None (Commit 1). Requires the stage to already
            be complete -- see §6.8.
        status: Terminal status to record. "complete" (default) or "in-progress"
            for a partial forge-5-loop run -- which still records completedAt,
            version, basedOnVersions and artifacts; only the status differs (§6.5).
        preserve_commit_hash: Skip the ``commitHash = None`` reset, for the Git
            Commit Protocol's "Nothing to commit" branch (L248, §6.5).
        resumable: Failed-Commit-1 revert (L245, §6.5). Record only the status;
            implies status "in-progress". Distinct from a bare ``status=
            "in-progress"``, which is forge-5-loop's partial completion.
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
    elif resumable:
        # Failed-Commit-1 revert (L245). The frozen contract is "leave state as
        # in-progress so the stage can be resumed" -- so record ONLY the status.
        # Writing completedAt would stamp a completion on a stage that never
        # completed; bumping version and cascading would mark downstream stages
        # stale off a commit that did not land; resetting commitHash would
        # discard a recoverable hash. All four are behavioral changes in a
        # zero-behavioral-diff feature (owner decision, 2026-07-29).
        #
        # NOTE this is gated on --resumable, NOT on status == "in-progress":
        # forge-5-loop's PARTIAL completion also passes --status in-progress but
        # is a real completion-with-artifacts, so it must fall through to the
        # branch below and keep its completedAt/version/basedOnVersions/artifacts
        # (SS 11.2 row 14). Conflating the two silently discards --based-on.
        entry["status"] = "in-progress"
        cascaded = []
    else:
        entry["status"] = status                      # "complete" | "in-progress" (partial)
        entry["completedAt"] = _now_iso()
        entry["version"] = version
        entry["basedOnVersions"] = based_on
        entry["artifacts"] = artifacts
        if not preserve_commit_hash:
            entry["commitHash"] = None                 # Commit 1; see §6.5
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

**The protocol's two recovery branches stay executable.** Both are frozen prose that
R4 must keep working without any site hand-authoring JSON:

- **"If Commit 1 fails … leave state as `in-progress` so the stage can be resumed"**
  (L245). The sanctioned revert is `state-complete --feature … --stage … --version N
  --resumable`. Use this, **not** `state-enter` — `state-enter` also rewrites
  `startedAt` and `currentStage`, side effects that are wrong for a failed-commit
  revert and that nobody has sanctioned for this use (owner decision, 2026-07-29).
  This branch records **only** `status` (plus the usual `updatedAt` refresh): it does
  **not** write `completedAt`, `version`, `basedOnVersions` or `artifacts`, does
  **not** reset `commitHash`, and fires **no** staleness cascade (owner decision,
  2026-07-29). All would contradict "leave state as `in-progress` so the stage can be
  resumed".

  **`--resumable`, not a bare `--status in-progress`.** The flag exists because
  `in-progress` has a *second*, opposite caller: `forge-5-loop`'s partial completion
  (§11.2 row 14) is a real completion-with-artifacts that happens not to be finished,
  and it *must* keep `completedAt`, `version`, `basedOnVersions` and `artifacts` —
  item 013 passes `--based-on forge-4-backlog=N` on exactly that call. Gating the
  status-only branch on `status == "in-progress"` would silently discard those flags.

  Schema validation **cannot** catch a regression in either direction — `stageEntry`
  declares `status` and `completedAt` as independent optional properties, so a state
  carrying both validates cleanly. Assert both branches with dedicated tests instead.
- **"Nothing to commit → mark the stage `complete`, leave `commitHash` at its existing
  value, skip Commit 2"** (L248). Pass `--preserve-commit-hash` so the completion
  branch does **not** execute `entry["commitHash"] = None`; without it, re-completing a
  stage that already carries a hash destroys it before any commit is attempted.

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
- `--stage` not in `STATE_VERB_STAGES` → argparse `choices` error.
- `--commit-hash` against a stage whose `status` is not `complete` → `UsageError`:
  `--commit-hash requires {stage} to be complete (status: {actual!r}); run
  state-complete without --commit-hash first`. Without this guard the branch writes a
  lone `{"commitHash": …}` entry, which violates `stageEntry`'s `required: ["status"]`
  at exit 0 (§3.5 covers the create path; this covers the typo'd-`--stage` path).
- Feature directory does not exist → `UsageError` (§3.4).
- State file present but unparseable → `UsageError`; the original file is left byte-intact
  (§3.4).
- Unwritable state directory / failed atomic write → `UsageError` wrapping the `OSError`
  (§3.3): `atomic write to {state_path} failed: {exc}`.

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
- Unwritable state directory / failed atomic write → `UsageError` (wrapped `OSError`, §3.3) → exit 2.
- Feature directory does not exist, or state file unparseable → `UsageError` (§3.4).

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
- Unwritable state directory / failed atomic write → `UsageError` (wrapped `OSError`, §3.3) → exit 2.
- Feature directory does not exist, or state file unparseable → `UsageError` (§3.4).

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
- Unwritable state directory / failed atomic write → `UsageError` (wrapped `OSError`, §3.3) → exit 2.
- Feature directory does not exist, or state file unparseable → `UsageError` (§3.4).

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
- Unwritable state directory / failed atomic write → `UsageError` (wrapped `OSError`, §3.3) → exit 2.
- Feature directory does not exist, or state file unparseable → `UsageError` (§3.4).

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
| `skills/forge-5-loop/SKILL.md` — pre-launch marker (L188–189) | set `stages.forge-5-loop.status=in-progress`, `.startedAt`, `currentStage` | `state-enter --feature … --stage forge-5-loop` |
| `skills/forge-5-loop/SKILL.md` — Step 5 completion (L258–263) | completion / partial + `completedAt` + `basedOnVersions` + `artifacts` | `state-complete --stage forge-5-loop --based-on forge-4-backlog=N --status {complete\|in-progress}` |
| `skills/forge-6-docs/SKILL.md` — Step 5 (L173–182) | completion + `currentStage=complete` + `basedOnVersions` + `artifacts` | `state-complete --stage forge-6-docs --based-on …` |
| `skills/forge/SKILL.md` — navigator note capture (L185) | set top-level `notes` | `state-note --feature … --note …` |

> **`forge-5-loop`'s conditional completion.** Step 5 records `complete` only when every
> backlog item is done, and leaves `in-progress` otherwise. That conditional is expressed
> by `state-complete --status` (§6.1), added for exactly this case (owner decision,
> 2026-07-29) — the skill evaluates the condition and passes the resulting value.
>
> **Explicitly out of scope (five sites).** Recorded here so each omission reads as
> deliberate rather than as a missed site, and so the repo-wide R4 census acceptance
> criterion (item **013**, which is R4's last conversion to execute) enumerates every
> deliberate exclusion. Item 013 carries two criteria: one scoped to the four bodies it
> converts itself, and the repo-wide census — the latter is only achievable there,
> because items 011 and 012 must land first:
>
> 1. The navigator's `pipelineStatus` writes (`skills/forge/SKILL.md` **L205–207** —
>    the three pause / resume / abandon bullets). REQ-R4-04 enumerates seven touch points
>    and `pipelineStatus` is not among them, so these keep their existing write path and
>    R4 adds no verb for them (owner decision, 2026-07-29). **The previously recorded
>    L215–228 range was wrong** — that span is the Epic lifecycle block, which mutates the
>    epic *manifest* via `epic-manifest.py set-status`, not `.pipeline-state.json` at all,
>    and is out of scope for a different reason.
> 2. `skills/forge-verify/SKILL.md` Step 6's `verifyEntry` write path — R4 adds no verb
>    for verify entries, so it stays hand-authored.
> 3. `skills/forge-0-epic/references/edit-mode.md` — **two** sites. (i) The **Member
>    State Example (creation C7)** member-subdir stub write: none of the seven verbs
>    writes the `epic` back-pointer a brand-new member stub needs, so conversion is
>    impossible without an eighth verb; forge-0-epic also has only 8 body lines of
>    headroom. (ii) The **E0-read Apply step's ECR status flip** (~L61–67), which flips
>    an existing `epicChangeRequests[]` item's `status` from `"open"` to `"applied"`.
>    `state-ecr` only **appends**, always with `status: "open"` (§9), so no verb mutates
>    an existing array item. Both deliberately excluded (owner decision, 2026-07-29).
> 4. `skills/forge-fix/SKILL.md` **Step 5** (~L66–74) — the `forge-verify-*` entry /
>    `fixedAt` / `verifiedStageVersion` write. Same `verifyEntry` class as site 2, and
>    R4 adds no verb for verify entries. Deliberately excluded (owner decision,
>    2026-07-29).
>
> Sites that **match a naive grep but need no exclusion**: `skills/forge-guide/SKILL.md`
> L165 is an *anti*-instruction ("don't hand-edit `.pipeline-state.json`"), and
> `skills/forge-5-loop/references/runner-contract.md` L176 is descriptive prose. The
> census criterion is therefore worded "no site *other than those named* **instructs**
> hand-authoring" rather than as a raw hit count.

> **`shared-conventions.md` prose caveat.** These edits switch the *mechanic*
> (the fenced "edit the JSON" / "write to `.pipeline-state.json`" step becomes a
> fenced verb call), never the *prose* of the surrounding protocol
> (`00-core-definitions.md §10`; §13 below shows a concrete before/after). The
> exact edited lines are specified in **§13.3** below. Every new fenced call site uses
> the full `BOOTSTRAP_PRELUDE`, **inlined inside its own fence** — never reused from an
> earlier fence, because `$R` does not survive between fences
> (`01-architecture-layout.md` §2.2.1); there is no compact form, because R2 is scoped
> out (PRD §3.2).

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
re-described as a hand edit).

`forge-1-prd` carries a full prelude at L31, **above** this call site — but `$R` is set
*inside that fence* and does not survive to a separate fence at ~L127, so this site
**inlines** its own prelude like every other R4/R5 target. The inline form below is
therefore the **universal** case, not merely the representative one: no call site
anywhere reuses a prelude from an earlier fence (`01-architecture-layout.md` §2.2.1,
which also carries the per-skill table and line budget).

> 1. Record completion by running the `state-complete` verb (it sets
>    `status: "complete"`, `completedAt`, the version bump, `basedOnVersions`, the
>    artifact list, `commitHash: null`, and applies the downstream staleness
>    cascade deterministically):
>    ```bash
>    R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
>    [ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
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

### 13.3 `references/shared-conventions.md` — before/after per touch point

This file is the largest R4 surface outside `forge-session.py`: 295 lines, read
unconditionally by ~10 skills, and its protocol prose is **frozen** by REQ-BEHAV-02. This
document owns these edits (an earlier draft misattributed them to
`04-effective-config.md`, which is the R5 subcommand spec and never mentions this file).
In every case the *mechanic* swaps and the *prose* does not.

**1. Stage-Entry Guard — Entry Stamp (L266–271).**

> **Before:** "write to `{resolvedFeatureDir}/.pipeline-state.json` and update
> `updatedAt`: `stages.{stage}.status` → `"in-progress"`; `stages.{stage}.startedAt` →
> current ISO-8601 UTC timestamp; top-level `currentStage` → `"{stage}"`"
>
> **After:** "record the entry stamp by running `state-enter --feature {feature} --stage
> {stage} --specs-dir {specsDir}` (it sets `status`, `startedAt`, `currentStage` and
> refreshes `updatedAt` in one atomic write)"

The following sentence — *"This write is **left uncommitted**: it is staged and committed
as part of this stage's existing exit commit"* — is unchanged and still true; the verb
writes the file, it does not commit it.

**2. Incremental artifact tracking (L275).**

> **Before:** "update the `stages.{stage}.artifacts` array in `.pipeline-state.json` after
> writing each file"
>
> **After:** "run `state-artifact --feature {feature} --stage {stage} --path <file>` after
> writing each file"

**3. Branch Setup — "Record the branch" (L217).**

> **Before:** "write the resulting branch name to the feature's `.pipeline-state.json`
> top-level `branch` field (create/update it when the state file is first written for this
> stage)"
>
> **After:** "run `state-branch --feature {feature} --branch <name> --specs-dir
> {specsDir}` **once the feature directory exists** — i.e. after Feature Directory
> Resolution and the Entry Stamp, not at this block"

**The timing qualifier is load-bearing and must survive the swap.** Branch Setup runs
*before* Feature Directory Resolution and *before* the Stage-Entry Guard
(`skills/forge-1-prd/SKILL.md` L20–21, L41), and at PRD time a brand-new standalone
feature may have no directory yet (L23). A `state-branch` call fired at the Branch Setup
block itself would hit a nonexistent directory and exit 2 at the very start of
forge-1-prd, where nothing fails today. §3.4's seeding covers the other half (a
first-write verb can no longer persist a state missing the six required top-level fields),
but the ordering must still be stated here.

**4. Branch Reconciliation — `adopt-current` (L230).**

> **Before:** "Write `newBranch` into the state `branch` field with a visible one-line
> note"
>
> **After:** "run `state-branch --feature {feature} --branch {newBranch}`, and print the
> same visible one-line note"

The note's wording, and the "never silently / never push the user back" rules, are
unchanged.

**5. Git Commit Protocol (L243, L244, L248).**

> **Before (L243):** "In `.pipeline-state.json`, set this stage's `status: "complete"` and
> `commitHash: null`, then `git commit …`"
>
> **After:** "run `state-complete --feature {feature} --stage {stage} --version N …`
> (which sets `status`, `completedAt`, `version`, `basedOnVersions`, `artifacts`,
> `commitHash: null` and applies the staleness cascade), then `git commit …`"

> **Before (L244):** "Write it into this stage's `commitHash` in `.pipeline-state.json`,
> then commit only that one-line change"
>
> **After:** "run `state-complete --feature {feature} --stage {stage} --version N
> --commit-hash $(git rev-parse HEAD)`, then commit only that one-line change"

The two-commit sequence, the "never `--amend`" rule, and the L245/L248 failure branches
are unchanged in prose; §6.5 specifies how each failure branch stays executable
(`--resumable` for L245 — **not** a bare `--status in-progress`, which is forge-5-loop's
partial completion — and `--preserve-commit-hash` for L248).

---

## 14. Verb-failure handling at the call site

R4 introduces a **new runtime failure surface**: seven protocol touch points that today
are hand-edits (which cannot fail with an exit code) become subprocess calls that can
exit 2. The pipeline already has a convention for this — `shared-conventions.md` L160,
for `render-status`: *"on exit 2, surface the plain `Error:` line from stderr verbatim."*
The state verbs follow it:

> If a `state-*` verb exits 2, surface the plain `Error:` line from stderr **verbatim**,
> do **not** proceed to the next step of the surrounding protocol, and do **not**
> hand-author the JSON as a workaround. The stage remains resumable because the entry
> stamp is already on disk — re-run the verb once the cause is fixed.

Concretely, the three failures an operator will actually hit and what each means:

| Message | Cause | What the skill does |
|---|---|---|
| `no feature directory at …` | typo'd `--feature`, or a nested epic member invoked without `--epic` | surface verbatim; do not create the directory |
| `… exists but is not valid JSON …; refusing to overwrite it` | a corrupt state file | surface verbatim; the original bytes are intact, so the user can repair or move it |
| `atomic write to … failed: …` | unwritable directory, disk full | surface verbatim |

Hand-authoring JSON to route around any of these re-introduces exactly the drift R4
exists to remove (REQ-R4-02), so it is never the fallback.

## 15. `currentStage` advancement — owner decision (item 020, 2026-07-29)

Items 012 and 013 removed the `Set currentStage to <next stage>` bullet from every
completion step, and the `currentStage → complete` write from forge-6-docs Step 5,
because `state-complete` does not write the field and §13.1's after-block omits it.
`state-enter` is now the only writer. This section adjudicates the two questions
that left open; both were flagged "for owner review" in `progress.md` at the time.

### 15.1 Should `currentStage` still advance on completion? **NO — accepted as-is.**

The field keeps its schema meaning: *the most recently **started** stage*. It moves
only when a stage is entered.

The deciding evidence is that `references/pipeline-state-schema.json` is
**byte-identical to the pre-feature baseline** (`9a29e846`) and already said so
before R4 began:

> "Where the pipeline IS: the most recently started stage … A stage skill sets this
> to its own id when it starts. This is deliberately NOT 'the next stage to run':
> the next stage is DERIVED, never stored … Consumers that need 'what runs next'
> compute it from `stages[].status`, not from this field."

The removed bullets set the field to the **next** stage — i.e. baseline canon
contradicted the baseline schema, in the exact terms the schema had pre-emptively
ruled out. REQ-R4-03 makes the schema the source of truth, so R4 resolved the
contradiction in the schema's favour. Restoring the bullets would re-introduce a
documented contradiction, and no verb can express them anyway (`state-enter` also
stamps the target stage `in-progress`, which is wrong for a stage that has not
started).

**This is not free.** One consumer had been written against the contradicting
behaviour and regressed silently: `_next_command` in `epic-manifest.py` recommended
`/feature-forge:{currentStage}`, whose docstring asserted `currentStage` *was* "its
next un-run stage". Post-R4 the epic rollup therefore recommended **re-running the
stage the member had just finished**, for the whole window between a stage completing
and its successor being entered — the window in which a user actually consults the
rollup. It was also self-sustaining: advancing `currentStage` requires entering the
next stage, which is the command the rollup declined to give.

The fix is the one the schema prescribes for every consumer — derive, don't read.
`epic-manifest.py` gains `_next_production_stage()`, the epic-side mirror of
`next_stage()` in `forge-session.py`, and `_next_command` uses it. This restores the
pre-R4 recommendation and additionally fixes two cases the old code got wrong
regardless of R4: a legacy state with no `currentStage`, and an all-stages-complete
member still actionable on unapplied findings (which pre-R4 emitted as the literal
`/feature-forge:complete`, not a command). Regression tests live in
`tests/test_epic_manifest.py` and assert the recommendation is **identical** under
both write conventions — the property that proves the field is no longer consulted.

No other consumer was affected: `build_rows` (forge-session.py) falls back to
`complete` only when `currentStage` is falsy, so it neither compensates nor breaks;
`derive_status` uses the field for the member's *displayed* stage but keys
completeness off `is_complete_for_orchestration`; and no consumer anywhere compares
`currentStage == "complete"`.

### 15.2 Should the `complete` value still be produced? **NO — accepted as-is.**

`complete` is not a stage that can be "most recently started"; it is a pipeline-level
fact. Producing it would require a writer that contradicts §15.1, and completeness is
already derived and available on every surface: `next_stage()` returns `None`,
surfaced as `nextStage: null` and `complete: true`.

The enum value is **retained** — pre-0.14 state files carry it and must keep
validating — but it is now documented as legacy and never-written. This is the one
canon edit item 020 makes: the `currentStage` **description** in
`references/pipeline-state-schema.json`. The clause "`complete` here means the whole
pipeline is done" was the sentence that would lead a future consumer to test
`currentStage == "complete"` and never see a finished pipeline.

The edit is prose-only, and that is asserted rather than claimed:
`tests/test_state_schema_conformance.py` now pins a digest of the schema with every
`description` recursively stripped, which is **unchanged from the pre-R4 baseline**.
(The previous raw-byte digest could only have been re-pinned, which proves nothing.)

### 15.3 Display surfaces — confirmed acceptable

Both surfaces the item names were checked against a fixture with all six stages
complete:

| Surface | Finished-pipeline display | Verdict |
|---|---|---|
| Navigator dashboard | `Stage: forge-6-docs`; the completion branch keys off `nextStage is null`, **not** `currentStage`, so the Completion hand-off still fires | accurate — it *is* the last stage started, and the ✅ ladder plus the hand-off carry "done" |
| Epic member rollup | `m1: complete (stage forge-6-docs)`; coarse status from `is_complete_for_orchestration`, no next command, rollup `1/1 complete` | correct |

Neither surface ever displayed a bare `currentStage` as the completion signal, which
is why the change is cosmetic there while being load-bearing in `_next_command`.

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
