# 03 — Verification State

> Atomic feature- and epic-scoped verification transitions, durable automatic
> verification debt, revision freshness, and commit provenance.

## Requirement Coverage

| REQ ID | Requirement | Section |
|---|---|---|
| REQ-DEBT-01 | Persist automatic verification debt before dispatch is directed | §4.1, §5.1 |
| REQ-DEBT-02 | Distinguish automatic debt from never/manual pending/skip | §2.1, §5.2 |
| REQ-DEBT-03 | Replace debt through the normal verified-state writer | §3.3, §4.2 |
| REQ-DEBT-04 | Preserve debt across dispatch failure or interruption | §4.1, §7.2 |
| REQ-DEBT-05 | Classifier, navigator, stage-exit, and status parity | §5 |
| REQ-DEBT-06 | Load legacy state without migration | §2.1, §6.2 |
| REQ-STATE-01 | Full 40-character hashes on new scripted writes | §3.4, §6.1 |
| REQ-STATE-02 | Continue reading legacy short hashes | §6.2 |
| REQ-STATE-03 | Atomic, targeted feature and epic state mutation | §3–§4, §7.1 |
| REQ-STATE-04 | Preserve two-commit provenance without amend | §6.3 |
| REQ-REL-01 | Deterministic and idempotent same-revision scheduling | §4.1 |
| REQ-REL-02 | Fail closed on unsafe or ambiguous state targets | §3.2, §7.1 |
| REQ-REL-03 | Make interrupted automatic verification recoverable | §4.1, §7.2 |
| REQ-REL-04 | Preserve the repository's single-writer state model | §3.2, §7.2 |
| REQ-COMPAT-02 | Preserve legacy standalone, member, and epic workflows | §2, §3.2, §6.2 |
| REQ-PERF-01 | Use bounded local state/manifest reads only | §4.1, §8 |
| REQ-OBS-01 | Expose distinct debt and transition information | §3.3, §5 |
| REQ-OBS-02 | Name the affected feature/epic, stage, and recovery action | §5.3, §7 |
| REQ-SEC-01 | Retain path safety and epic/member disambiguation | §3.2, §7.1 |

## 1. Purpose and Scope

This document specifies the `state-verify` domain concern: atomic feature- and
epic-scoped verification transitions, durable `auto-verify-pending` scheduling,
manifest revisions used as epic artifact versions, read-side classification parity,
and commit provenance. Shared literals, `VerifyEntry`, `UsageError`, and the public
writer signature are owned by `00-core-definitions.md`; this document applies those
definitions and does not redefine them. File placement and implementation order are
owned by `01-architecture-layout.md` (REQ-STATE-03, REQ-COMPAT-02).

The implementation remains in the Python 3.10+ standard-library executable
`scripts/forge-session.py`. `scripts/epic-manifest.py` remains self-contained and
mirrors only the constants and revision behavior identified below. There is no new
package, service, database, history scan, or network operation (REQ-PERF-01).

WARNING: Could not locate `cmd_state_verify` export in `scripts/forge-session.py` — verify before implementing. The function and CLI subcommand are new in this feature.

WARNING: Could not locate a dedicated `.epic-state.json` schema export in `references/` — verify before implementing. Its current minimal contract is documented in `skills/forge-verify/references/findings-template.md`; this feature must keep that file additive and must not treat `references/epic-manifest-schema.json` as its schema.

## 2. Persisted State Contracts

### 2.1 Feature and epic verification entries (REQ-DEBT-02/06, REQ-COMPAT-02)

Use `VerifyStatus` and `VerifyEntry` exactly as defined in
`00-core-definitions.md §2` and `§6`. Update
`references/pipeline-state-schema.json#/definitions/verifyEntry` additively:

- add `auto-verify-pending` to `status.enum`;
- add nullable ISO-8601 string `scheduledAt`;
- add nullable integer `scheduledStageVersion` with minimum `1`;
- retain all existing fields and do not add `additionalProperties: false`;
- do not add a length or hex pattern to `commitHash`, because loaded legacy short
  hashes remain valid compatibility inputs.

`pending` remains generic/manual work. `auto-verify-pending` exclusively means that
effective configuration scheduled unattended in-stage verification and no successful
result or explicit skip has replaced that obligation. It is neither `never`, `passed`,
`findings-applied`, nor `skipped` (REQ-DEBT-02/05).

Feature verification entries remain under
`{specsDir}/{feature}/.pipeline-state.json` (or the explicitly selected epic member)
at `stages.forge-verify-{prd|tech|specs|backlog|impl}`. Epic verification remains at
`{specsDir}/{epic}/.epic-state.json` under `stages.forge-verify-epic`; it must never be
written into a member state (REQ-STATE-03, REQ-SEC-01).

A newly written epic state has this complete minimal shape; legacy files lacking
`updatedAt` or new scheduling fields are accepted and enriched on their next successful
write (REQ-DEBT-06, REQ-COMPAT-02):

```json
{
  "epic": "auth-overhaul",
  "updatedAt": "2026-07-30T00:00:00Z",
  "stages": {
    "forge-verify-epic": {
      "status": "auto-verify-pending",
      "scheduledAt": "2026-07-30T00:00:00Z",
      "scheduledStageVersion": 3,
      "commitHash": null
    }
  }
}
```

No member status, rollup, dependency result, or manifest content is cached in this file.

### 2.2 Epic manifest revision (REQ-DEBT-01/05, REQ-REL-01)

Add a required top-level property to `references/epic-manifest-schema.json`:

```json
"revision": {
  "type": "integer",
  "minimum": 1,
  "description": "Canonical artifact revision for epic-scoped verification freshness."
}
```

Add `revision` to the schema's `required` array. Canonical epic creation writes
`revision: 1`. In `scripts/epic-manifest.py`, add `revision` to `_TOP_REQUIRED` and the
allowed top-level keys, and validate that it is an integer but not a boolean and is at
least `1`.

`load_manifest(epic_dir: Path) -> dict` presents a missing legacy revision as logical
`1` in the returned dictionary without eagerly rewriting the file. Therefore legacy
validation and rendering continue to work. The first successful semantic mutation of a
legacy manifest writes `revision: 2` (REQ-DEBT-06, REQ-COMPAT-02).

Every manifest mutation funnels through the existing `_bump_and_write` function and
increments exactly once. A validation failure, I/O failure, or semantic no-op leaves
both revision and bytes unchanged. `_bump_and_write` must compare the proposed manifest
with the on-disk manifest while ignoring only `updatedAt` and the synthesized revision;
if all semantic fields match, it returns `[]` without writing. Otherwise it validates,
sets `revision = current_revision + 1`, refreshes `updatedAt`, and invokes
`atomic_write` once (REQ-REL-01, REQ-STATE-03).

Epic `scheduledStageVersion` and `verifiedStageVersion` always carry this manifest
revision. They never carry a member production-stage version.

## 3. `state-verify` Writer

### 3.1 Public callable and CLI (REQ-DEBT-01/03, REQ-STATE-03)

The target callable is the exact shared signature from `00-core-definitions.md §6`:

```python
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
    """Write one verification transition or one commit-2 provenance update."""
```

Implementation/execution path: `scripts/forge-session.py`. This flat script is not a
hyphen-safe Python package import; production consumers execute it as:

```text
python3 <bundle-root>/scripts/forge-session.py state-verify ...
```

Register the following argparse surface beside the existing `state-*` parsers:

```text
state-verify --feature FEATURE
  --stage {forge-0-epic,forge-1-prd,forge-2-tech,forge-3-specs,forge-4-backlog,forge-5-loop}
  [--status {auto-verify-pending,passed,findings-reported,findings-applied,skipped}]
  [--findings-file PATH]
  [--findings-count N]
  [--verified-stage-version N]
  [--commit-hash HASH]
  [--epic EPIC]
  [--specs-dir DIR]
  [--json]
```

The dispatch branch calls `cmd_state_verify` with parsed values, emits JSON through the
existing `_emit` convention when requested, and maps `UsageError`/`OSError` through the
existing `main() -> int` exit-2 handler. The parser excludes `forge-6-docs`, which has no
verification token (REQ-REL-02).

### 3.2 Atomic target selection (REQ-STATE-03, REQ-REL-02, REQ-SEC-01)

Select the target before constructing or mutating an entry:

1. For `forge-1-prd` through `forge-5-loop`, map `stage` through existing
   `VERIFY_TOKEN_BY_STAGE`, then call
   `_load_state_for_write(specs_dir, feature, epic)`. The selected key is
   `forge-verify-{token}`. This preserves explicit member targeting and rejects an
   ambiguous bare feature.
2. For `forge-0-epic`, branch before `VERIFY_TOKEN_BY_STAGE`. `feature` names the epic;
   `epic` must be `None` or exactly equal to `feature`. Strictly resolve
   `{specsDir}/{feature}`, require its `epic-manifest.json`, require the manifest's
   `epic` value to equal `feature`, and load its canonical revision. Read or lazily
   create sibling `.epic-state.json`, requiring a JSON object whose existing `epic`
   is absent or equal to `feature` and whose `stages` is absent or an object.
3. Reject unsafe names, containment escapes, missing/mismatched manifests, corrupt
   files, non-object states, ambiguous members, and unsupported stages with
   `UsageError` before mutation. Never fall back from an epic target to a feature
   state or vice versa.

Feature writes finish through existing `_commit_state`; epic writes use the same atomic
`_write_state` mechanism and set top-level `updatedAt` before one replacement. Both
write only the selected verify entry and top-level `updatedAt`; unrelated keys and
entries survive byte-for-data-equivalent serialization (REQ-STATE-03).

**Single-writer model (REQ-REL-04).** These writers are read-modify-write over a whole
document, and that is deliberate. Atomic replacement protects against an *interrupted*
write; it is not mutual exclusion between simultaneous writers, and this feature does not
make it so. Concurrent state-mutating commands from multiple sessions remain out of scope,
exactly as they already are for `_write_state` ("single writer assumed, matching
epic-manifest.py") and for epic manifest writes (the `epic-orchestration` PRD's Robustness
requirement, §4.2). No
lock, lease, or optimistic-version check is introduced here: the repository-wide invariant
is not this feature's to overturn, and no concurrency threat model has been established.
A real multi-session need is a separate feature with its own PRD; see PRD REQ-REL-04 for the
known candidate (concurrent sessions on two members of one epic, sharing `epic-manifest.json`
and `.epic-state.json`, where a lost `revision` increment could make a stale epic verification
read as fresh — §5.2).

### 3.3 Transition validation and mutation (REQ-DEBT-02/03, REQ-OBS-01)

Exactly one mode is valid: result mode has `status is not None` and
`commit_hash is None`; commit-2 mode has `commit_hash is not None` and every result
field is `None`. Reject a request with neither mode or mixed modes before any write.

Apply this result-mode matrix:

| Status | Required input | Forbidden/validated input | Mutation |
|---|---|---|---|
| `auto-verify-pending` | none; current target revision is derived | reject findings metadata and `verified_stage_version` | replace with pending status, `scheduledAt`, `scheduledStageVersion=current`, `commitHash=null`; clear terminal timestamps/version/findings |
| `passed` | `verified_stage_version=current` | findings count, if supplied, must be `0`; reject stale/non-positive version | replace pending; set `verifiedAt`, current `verifiedStageVersion`, `commitHash=null`; clear scheduling and fix metadata |
| `findings-reported` | current `verified_stage_version`, non-negative `findings_count`, and a non-empty `findings_file` that is **relative** and contained by the resolved feature/epic directory | reject stale/non-positive version; reject an absolute `findings_file`, any `..` segment, and NUL/control characters — before any mutation | replace pending; set report metadata, `verifiedAt`, current version, `commitHash=null`; clear scheduling/fix metadata |
| `findings-applied` | an existing `findings-reported` or `findings-applied` entry | reject `verified_stage_version`; supplied findings metadata must equal the existing report | preserve report metadata, set `fixedAt`, set `commitHash=null`, delete `verifiedStageVersion`, clear scheduling/`verifiedAt` |
| `skipped` | none | reject findings metadata and `verified_stage_version` | replace pending with `skipped`, set `commitHash=null`, clear scheduling, report, verified, fixed, and version fields |

For feature targets, `current` is the selected production stage entry's positive integer
`version`; result statuses other than `skipped` fail if that artifact version is absent.
For epic targets, `current` is the manifest revision. `findings-applied` deliberately
has no verified version: interruption before re-verification remains unresolved and
cannot advance the pipeline (REQ-DEBT-03/04).

Terminal result writes remove both `scheduledAt` and `scheduledStageVersion`, rather
than setting them to null. This makes replacement unambiguous while remaining valid
against additive legacy schemas (REQ-DEBT-03, REQ-OBS-01).

### 3.4 Commit-2 mode (REQ-STATE-01/03/04)

Commit-2 mode requires an existing selected verify entry. Validate with
`FULL_GIT_HASH_RE.fullmatch(commit_hash)` from `00-core-definitions.md`; accept exactly
40 hexadecimal characters and preserve caller case. Reject short, long, non-hex, empty,
or mixed-mode input before mutation.

On success change only the selected entry's `commitHash` and top-level `updatedAt`, then
perform one atomic write. Status, findings metadata, scheduling metadata, timestamps,
and versions remain unchanged. This mode is valid for feature and epic entries and does
not invoke Git or amend a commit.

## 4. Scheduling and Replacement Flow

### 4.1 Stage-exit scheduling boundary (REQ-DEBT-01/04, REQ-REL-01/03)

`stage_exit` computes repository cleanliness and `autoFixEligible` before any sanctioned
state mutation. After it has determined that effective configuration owes automatic
verification, but immediately before it returns a payload with
`directives.runInStageVerify == true`, it invokes the same internal transition used by
`cmd_state_verify` with `status="auto-verify-pending"` (REQ-DEBT-01).

The scheduling transition is idempotent by target revision:

- if the selected entry is already `auto-verify-pending` with
  `scheduledStageVersion == current`, return the existing state without calling
  `_commit_state`, refreshing `updatedAt`, replacing the file, or changing
  `scheduledAt`;
- if the target revision is newer, write a new `scheduledAt`, the new revision, and
  null provenance exactly once;
- a pending marker for an older revision is superseded by the new schedule;
- a terminal entry fresh for the current revision prevents scheduling;
- an explicit `skipped` entry remains resolved under the existing compatibility rule
  and is not automatically overwritten.

Only after the atomic write succeeds may the result set
`autoVerifyDebtRecorded: true` and `runInStageVerify: true`. A write failure raises
`UsageError` and no dispatch directive is returned. Thus a crash after the write but
before dispatch leaves durable debt; a crash before the write cannot falsely claim the
debt was recorded (REQ-DEBT-04, REQ-REL-03).

For `forge-0-epic`, stage exit reads `.epic-state.json` and the manifest revision
directly. It must not use `_resolve_feature_dir`, a member stage version, or the
placeholder first actionable member for epic verification state (REQ-SEC-01).

### 4.2 Verify/fix replacement (REQ-DEBT-03/04, REQ-STATE-04)

`forge-verify` and `forge-fix` invoke `state-verify` for every result instead of
model-authoring JSON. The sequence is:

1. verification result transition writes report/state with `commitHash: null`;
2. Commit 1 records the report and state;
3. `state-verify --commit-hash <40-hex-Commit-1-hash>` records provenance in Commit 2;
4. findings fixes write `findings-applied`, which clears freshness;
5. only a subsequent `passed` result restores current `verifiedStageVersion`.

A failed dispatch, compaction, process interruption, or model non-adherence performs no
terminal transition, so `auto-verify-pending` remains intact. An explicit user skip must
be persisted as `skipped` before routing may advance (REQ-DEBT-03/04).

## 5. Read-Side Parity

### 5.1 Session classifiers and navigator (REQ-DEBT-05, REQ-OBS-01)

Update the existing functions at `scripts/forge-session.py` without changing their
signatures:

```python
def verify_state(state: dict) -> tuple[str | None, str]: ...
def pending_verify(state: dict) -> str | None: ...
def _verify_state_for(state: dict, stage: str) -> str: ...
def build_rows(specs_dir: Path, config: dict | None = None) -> list[FeatureRow]: ...
```

Classification rules are ordered before generic unresolved handling:

- matching `auto-verify-pending.scheduledStageVersion` returns `auto-pending`;
- pending with a missing/invalid version is still `auto-pending` and emits an actionable
  legacy/malformed metadata warning rather than becoming `never`;
- pending for an older revision remains `auto-pending` (owed work is not erased by a
  later edit), and its message states that the artifact has advanced;
- `pending_verify` returns the served production stage for `auto-pending`;
- `build_rows` sets `verifyPending=true`, `verifyState="auto-pending"`, and a non-null
  `verifyCommand`; it never treats the feature as verification-complete;
- `_verify_state_for` applies identical labels for stage-exit routing.

Keep `KNOWN_VERIFY_STATUSES` byte-identical in `scripts/forge-session.py` and
`scripts/epic-manifest.py`, including `auto-verify-pending`. Keep `_VERIFY_RESOLVED`
unchanged: pending debt is not resolved (REQ-DEBT-05).

### 5.2 Epic manifest status parity (REQ-DEBT-02/05, REQ-OBS-02)

In `scripts/epic-manifest.py`:

- `_verify_status_warnings` recognizes `auto-verify-pending` as known, so it does not
  emit the misleading unknown-status warning;
- `is_complete_for_orchestration` continues to return `False` for an implementation
  verification entry with this status;
- `derive_status` treats it as in-progress, never complete;
- `_next_command` routes an otherwise production-complete member with
  `auto-verify-pending` to `/feature-forge:forge-verify <member>`, reserving
  `/feature-forge:forge-fix <member>` for `findings-reported`;
- `render_status` appends a deterministic warning naming the member, served stage, and
  verify retry command when a member carries automatic debt. This is an obligation
  warning, not an unknown-value warning, and remains visible in JSON `warnings` and
  human status output.

Epic-root verification freshness compares `.epic-state.json` version metadata to the
manifest revision: missing state is `never`; matching pending is `auto-pending`; matching
`passed` is `fresh`; matching `findings-reported` is `failing`; `findings-applied` with
no version is `stale`; mismatched or missing terminal version is `stale`; `skipped` is
resolved under the compatibility rule (REQ-DEBT-05/06).

### 5.3 Human diagnostics (REQ-DEBT-05, REQ-OBS-02)

Navigator, stage-exit, doctor/status, and epic dashboard text must say:

```text
<feature-or-epic>: automatic verification is still pending for <served-stage>;
run <host-translated forge-verify command> to resolve it.
```

When the recorded scheduled revision differs from current, append both revision numbers.
Do not dump or reformat the full state file. JSON output carries three named keys, not
prose: `verifyState` (the stable `"auto-pending"` label), `verifyStage` (the production
stage the debt is owed on — `StageExitDirectives.verifyStage` in `00` §4 on the stage-exit
side, `FeatureRow.verifyStage` on the navigator side), and `verifyCommand` (the retry
command). Naming them here is what keeps the two emitters reporting the same thing;
without `verifyStage` a stage-exit consumer would have to invent an undeclared key,
because `servedStage` is branch-exit-only and is None on a production-stage exit.
Warnings stay on stderr unless they are an existing structured `warnings` field
(REQ-OBS-01/02).

### 5.4 Downstream pre-flight parity (REQ-DEBT-05)

REQ-DEBT-05 names four consumer classes, and the fourth — **downstream pre-flight
checks** — is not covered by §5.1 (session classifiers), §5.2 (epic manifest), or §5.3
(diagnostic text). Specify it here, because the pre-flight gates are enumerations in skill
bodies rather than classifier functions, and an enumeration that predates
`auto-verify-pending` does not fail loudly when it meets one — it silently takes whichever
branch the value happens not to match.

Any canon gate that reads a `stages.forge-verify-*` entry MUST treat `auto-verify-pending`
as an **explicit third case**: outstanding, not resolved, and not the same as `never`.
Falling into a resolved-and-proceed branch treats owed debt as discharged; falling into a
never-scheduled branch reports it as un-attempted, which is exactly the conflation
REQ-DEBT-02 forbids. The diagnostic wording is §5.3's — naming the served stage and the
retry command.

Two live call sites are in scope, and `04-skill-integration.md` owns their edits (§7.2 for
docs, §6 for the loop):

- `skills/forge-6-docs/SKILL.md` Step 1 branches on an explicit status enumeration — warn
  when `stages.forge-verify-impl` is absent or `skipped`, proceed silently on
  `findings-applied | findings-reported | passed`. `auto-verify-pending` matches neither
  branch today, and the likely reading (not in the warn set) proceeds silently.
- `skills/forge-5-loop/SKILL.md` Step 1b warns "Backlog hasn't been verified yet" for
  anything outside `{passed, findings-applied}`, which reports owed-and-dropped
  auto-verify as never-scheduled.

## 6. Hash Compatibility and Provenance

### 6.1 Full-hash new writes (REQ-STATE-01)

At the beginning of the existing `cmd_state_complete` commit-hash branch and the new
`cmd_state_verify` commit-2 branch, require
`FULL_GIT_HASH_RE.fullmatch(commit_hash)`. Validation occurs before loading for mutation
where possible and always before `_commit_state`/`_write_state`. This applies to feature
stage completion, feature verification, and epic verification.

### 6.2 Legacy reads (REQ-STATE-02, REQ-DEBT-06)

Do not add a schema regex/minLength/maxLength for either stage or verification
`commitHash`. `_read_state`, `_load_state_for_write`, manifest status readers, navigator,
and stage exit continue loading an existing short string. A reader may warn that the
legacy hash will be replaced by a full hash on the next provenance write, but it must not
reject, migrate, truncate, or resolve it through Git solely because of its length.

### 6.3 Two-commit protocol (REQ-STATE-04)

Result/completion mode writes `commitHash: null` in Commit 1. Commit-2 mode writes the
full Commit-1 object hash in a separate targeted state commit. No implementation command
runs `git commit --amend`, rewrites history, uses a broad whole-file model patch, or
records the hash of Commit 2 in its own state. The existing exact source signature that
receives corresponding completion provenance is:

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
    status: str | None = None,
    preserve_commit_hash: bool = False,
    resumable: bool = False,
) -> dict: ...
```

## 7. Error Handling

### 7.1 Fail-closed mutation errors (REQ-STATE-03, REQ-REL-02, REQ-SEC-01)

All writer validation failures raise the shared `UsageError`, print as `Error: ...` on
stderr, and exit `2`. They produce no success JSON and leave the prior target
byte-identical. Covered failures include:

- unsupported/non-verifiable stage or unknown status;
- neither or both writer modes;
- contradictory findings/version metadata;
- missing, stale, boolean, or non-positive artifact revision;
- missing prior findings for `findings-applied`;
- missing entry for commit-2;
- short/non-hex hash on a new write;
- unsafe name, mismatched epic identity, ambiguous member, path escape;
- a `findings_file` that is absolute, contains a `..` segment, carries NUL/control
  characters, or otherwise escapes the resolved feature/epic directory. `00` §6 defines
  the field as relative to the feature directory, and downstream consumers (`forge-fix`
  selecting the report, `04` §5.1) follow the stored value, so it gets the same
  fail-closed containment treatment as the write target itself (REQ-SEC-01);
- missing/corrupt/non-object state or manifest;
- malformed `stages` objects;
- temp creation, serialization, flush/fsync, or `os.replace` failure.

Validation and mutation operate on an in-memory copy or on state not yet committed.
Atomic replacement uses a sibling temp file; cleanup failure must not hide the original
write error. No partial state is accepted as success.

### 7.2 Read and interruption behavior (REQ-DEBT-04/05, REQ-REL-03)

Read-only navigator/status scans retain their tolerant behavior for missing or corrupt
feature files, but must surface a named warning when an expected debt record cannot be
read. Strict writers never inherit tolerant `{}` fallback. Once scheduling succeeds,
all later failures leave the pending marker as the authoritative state and route to
verification recovery, never to the downstream production stage.

An interrupted write is never partially applied: it either completed its `os.replace` or
never began one, so no cleanup step exists or is needed (REQ-REL-04). Recovery from an
interruption is therefore re-running the verb, not repairing a file.

## 8. Exact Existing Integration Surface

The following signatures and paths were read from current source and must be reused or
extended in place (REQ-STATE-03, REQ-COMPAT-02):

From `scripts/forge-session.py`:

```python
def _verify_state_for(state: dict, stage: str) -> str: ...
def _resolve_feature_dir(specs_dir: Path, feature: str, epic: str | None) -> Path: ...
def _resolve_feature_dir_for_write(
    specs_dir: Path, feature: str, epic: str | None
) -> Path: ...
def _load_state_for_write(
    specs_dir: Path, feature: str, epic: str | None
) -> tuple[Path, dict]: ...
def _commit_state(state_path: Path, state: dict) -> dict: ...
def _write_state(state_path: Path, state: dict) -> None: ...
def _now_iso() -> str: ...
```

From `scripts/epic-manifest.py` (execution path also supports
`render-status <epic> --specs-dir <dir> --json`):

```python
def load_manifest(epic_dir: Path) -> dict: ...
def atomic_write(path: Path, data: dict) -> None: ...
def is_complete_for_orchestration(state: dict) -> bool: ...
def derive_status(feature_dir: Path) -> FeatureStatus: ...
def render_status(epic_dir: Path, specs_dir: Path) -> RenderStatus: ...
def _bump_and_write(
    epic_dir: Path, specs_dir: Path, manifest: dict
) -> list[Finding]: ...
```

All reads and writes are bounded to the selected config/state/manifest and the existing
one-level feature scan. No repository-wide Git history query or network call is added
(REQ-PERF-01).

## Public API and Internal Surface

- **User-facing CLI:** `python3 scripts/forge-session.py state-verify --feature F --stage S
  [--status ...] [--findings-file P] [--findings-count N] [--verified-stage-version N]
  [--commit-hash HASH] [--epic E] [--specs-dir D] [--json]` — full contract in §3.1. This is
  the eighth `state-*` verb and the only new command this document adds.
- **Repository-internal, importable:** `cmd_state_verify(...)` (§3.1, the callable behind the
  CLI) and the read-side classifiers `verify_state`, `pending_verify`, and `build_rows` (§5),
  which the navigator and `epic-manifest.py` parity paths consume.
- **Private helpers:** `_verify_state_for`, `_load_state_for_write`, `_commit_state`,
  `_write_state`, `_now_iso`, and `_bump_and_write`. This feature adds no new private
  helper to the write path: the only sanctioned way to mutate state is through a `state-*`
  verb, and no skill, adapter, or external caller writes state files directly.
- **Not an API surface:** `.pipeline-state.json` and `.epic-state.json` are *data*, not a
  contract for hand-editing. The R4 state-verb work and this feature's `state-verify` exist
  precisely so that nothing hand-authors these documents.
- **Test/eval-only:** none. This document introduces no test-only seam, injectable constant,
  or environment override — the writers are exercised through the real CLI exactly as
  production invokes them (`07-testing-strategy.md` §4.2–§4.3).

## 9. Dependencies

Implement these specifications first:

- `00-core-definitions.md` — shared verification literals, entry shape, full-hash
  constant, writer signature, and `UsageError`.
- `01-architecture-layout.md` — file ownership, adapter-copy boundary, and sequencing.

This concern must be implemented before the stage-exit routing/canonical-skill concern
that emits `runInStageVerify`, because dispatch must never precede durable debt. It also
depends on the existing atomic writer machinery in `scripts/forge-session.py` and
manifest mutator funnel in `scripts/epic-manifest.py` quoted in §8.

## 10. Verification

Confirm the implementation with focused tests followed by repository gates:

- [ ] `references/pipeline-state-schema.json` accepts all six statuses and scheduling
  fields; a legacy file without them still validates.
- [ ] New manifests start at revision 1; legacy missing revision reads as 1; the first
  semantic mutation writes 2; every later mutation increments once; no-op/failure does
  not change bytes.
- [ ] Feature and epic `state-verify` result transitions mutate only the selected entry
  and `updatedAt`; ambiguous and mismatched targets leave every candidate untouched.
- [ ] Same-revision automatic scheduling is byte-idempotent, including timestamps.
- [ ] A simulated failure after pending persistence leaves `auto-verify-pending`; a
  terminal result or explicit skip removes scheduling metadata.
- [ ] `findings-applied` clears freshness, and only subsequent `passed` restores the
  current revision.
- [ ] `verify_state`, `_verify_state_for`, `pending_verify`, `build_rows`, doctor/status,
  epic rollups, and retry commands agree on `auto-pending`.
- [ ] `KNOWN_VERIFY_STATUSES` remains equal in both scripts and to schema status values.
- [ ] New feature/epic completion and verification writes reject short/non-hex hashes
  without mutation; a loaded legacy short hash remains readable.
- [ ] Commit-2 changes only `commitHash` and `updatedAt`; no amend command exists.
- [ ] Every writer sequence conforms after each step, not only at sequence end.

Expected test locations are `tests/test_auto_verify.py`, `tests/test_state_verbs.py`,
`tests/test_state_schema_conformance.py`, `tests/test_stage_constants_parity.py`,
`tests/test_stage_exit.py`, and the existing epic-manifest tests. Run:

```text
python3 scripts/build-adapters.py
bash scripts/validate.sh
ruff check scripts/ eval/
```

`bash scripts/validate.sh` remains the full gate. `smokeCommand` stays `null`; no runtime
smoke command is introduced by this concern.
