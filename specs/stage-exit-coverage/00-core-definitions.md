# 00 — Core Definitions

> Shared Python contracts for deterministic stage exits, branch rejoin routing,
> verification debt, duplicate-key diagnostics, and provenance. Every later document
> imports these definitions conceptually from `scripts/forge-session.py` or
> `scripts/forge_json.py`; no new package-level public API is introduced.

## Requirement Coverage

| REQ ID | Requirement | Section |
|---|---|---|
| REQ-EXIT-01..07 | Covered stages, ownership, one terminal block, capability-aware verify-first routing | §2–§5 |
| REQ-ROUTE-01..06 | Served-stage inference and complete branch outcome vocabulary | §2–§5 |
| REQ-PROD-01..06 | Loop/docs/epic outcome and handoff contracts | §2–§4 |
| REQ-DEBT-01..06 | Durable `auto-verify-pending` state and terminal replacement | §6 |
| REQ-STATE-01..04 | Full-hash new writes, legacy reads, targeted atomic mutation | §6–§7 |
| REQ-CONFIG-01..04 | General recursive duplicate-key result contract | §8 |
| REQ-REL-01..03 | Deterministic values, fail-closed input errors, recoverable debt | §2–§8 |
| REQ-OBS-01/02 | Machine-readable routing/debt and actionable diagnostics | §4, §6, §8 |
| REQ-SEC-01 | Safe identifiers and strict writer targeting | §2, §7 |
| REQ-COMPAT-01/02 | Additive state/config evolution and stages 0–4 compatibility | §3, §6–§8 |

## 1. Scope and Conventions

The implementation uses Python 3.10+ and the standard library. Definitions stay in the
flat executable scripts that own them:

- `scripts/forge-session.py` owns stage/outcome constants, request validation, routing,
  verification state transitions, state writer errors, and rendered payload types.
- `scripts/epic-manifest.py` mirrors verification vocabulary and owns manifest revision
  reads/mutations.
- `scripts/forge_json.py` owns duplicate-aware JSON loading and warning formatting.

The project convention is `TypedDict`, `Literal`, `Final`, plain dictionaries at JSON
boundaries, Google-style docstrings, and `UsageError` for failures that map to CLI exit 2.
Do not introduce Pydantic, dataclasses, or `jsonschema` at runtime.

## 2. Identifiers, Enums, and Constants

Add these exact domains in `scripts/forge-session.py`:

```python
from typing import Final, Literal, TypedDict

ProductionStage = Literal[
    "forge-0-epic",
    "forge-1-prd",
    "forge-2-tech",
    "forge-3-specs",
    "forge-4-backlog",
    "forge-5-loop",
    "forge-6-docs",
]
ExitStage = Literal[
    "forge-0-epic",
    "forge-1-prd",
    "forge-2-tech",
    "forge-3-specs",
    "forge-4-backlog",
    "forge-5-loop",
    "forge-6-docs",
    "forge-verify",
    "forge-fix",
]
VerifyMode = Literal["epic", "prd", "tech", "specs", "backlog", "impl"]
ExitOwner = Literal["direct", "nested"]
VerifyCapability = Literal["interactive", "manual"]
VerifyStateLabel = Literal[
    "fresh", "stale", "failing", "never", "auto-pending", "skipped", "none"
]
VerifyStatus = Literal[
    "pending",
    "auto-verify-pending",
    "passed",
    "findings-reported",
    "findings-applied",
    "skipped",
]
VerifyGate = Literal["none", "standard", "manual-print"]

LoopOutcome = Literal["complete", "partial", "blocked", "needs-human", "deferred"]
DocsOutcome = Literal["complete", "blocked"]
VerifyOutcome = Literal["passed", "findings", "skipped", "failed"]
FixOutcome = Literal[
    "no-findings",
    "decisions",
    "failed",
    "applied",
    "reverified",
    "reverify-findings",
    "deferred",
]

EXIT_STAGES: Final[tuple[str, ...]] = (
    "forge-0-epic", "forge-1-prd", "forge-2-tech", "forge-3-specs",
    "forge-4-backlog", "forge-5-loop", "forge-6-docs",
    "forge-verify", "forge-fix",
)
EXIT_OUTCOMES: Final[dict[str, frozenset[str]]] = {
    "forge-5-loop": frozenset({"complete", "partial", "blocked", "needs-human", "deferred"}),
    "forge-6-docs": frozenset({"complete", "blocked"}),
    "forge-verify": frozenset({"passed", "findings", "skipped", "failed"}),
    "forge-fix": frozenset({
        "no-findings", "decisions", "failed", "applied", "reverified",
        "reverify-findings", "deferred",
    }),
}
VERIFY_MODE_TO_STAGE: Final[dict[str, str]] = {
    "epic": "forge-0-epic",
    "prd": "forge-1-prd",
    "tech": "forge-2-tech",
    "specs": "forge-3-specs",
    "backlog": "forge-4-backlog",
    "impl": "forge-5-loop",
}
NEXT_STEPS_SENTINEL: Final = "─ forge: end of stage ─"
FULL_GIT_HASH_RE: Final = re.compile(r"[0-9a-fA-F]{40}")
```

`PRODUCTION_STAGES` remains the existing ordered six-stage tuple used by
`next_stage(state: dict) -> str | None`; `forge-0-epic` participates in exit and verify
routing but not the member production walk. `KNOWN_VERIFY_STATUSES` in both
`forge-session.py` and `epic-manifest.py` must be byte-identical and include
`auto-verify-pending`.

## 3. Request Validation Contract

The serialized request remains argparse flags, but the internal callable has the exact
signature below (existing first seven parameters stay positional for compatibility):

```python
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
) -> dict:
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
            verifier dispatch capabilities exist; otherwise `manual`.

    Returns:
        A JSON-serializable `StageExitPayload` dictionary.

    Raises:
        UsageError: Unsafe or ambiguous identity, unsupported stage/outcome,
            missing ownership/served-stage metadata, or conflicting inference.
    """
```

Validation order is deterministic and fail-closed:

1. Validate safe names and path containment before filesystem access on new strict paths.
2. Validate `stage`, then the stage-specific `outcome` requirement.
3. Require `owner` for `forge-verify` and `forge-fix`.
4. Resolve served stage from explicit `served_stage`, then unique `verify_mode` mapping.
   If both are supplied they must agree. Missing or conflicting metadata raises
   `UsageError`; conversational context is never an input.
5. Validate capability and host independently. Host translates commands; capability
   selects the gate.

Established stages 0–4 retain their existing tolerant read behavior. New branch, loop,
docs, state-mutation, and explicit member-routing paths use strict resolution.

## 4. Stage-Exit Result Types

```python
class EpicReconcile(TypedDict, total=False):
    """Existing epic backflow directive retained in expanded exits."""

    required: bool
    reminder: bool
    command: str
    count: int
    deferred: str | None


class StageExitDirectives(TypedDict, total=False):
    """Machine-readable decisions emitted by `stage_exit`."""

    stage: str
    servedStage: str | None
    verifyMode: str | None
    outcome: str | None
    owner: str | None
    terminalOwnedBy: Literal["self", "outer"]
    feature: str
    host: str
    verifyCapability: str
    verifyState: str
    verifyGate: str
    verifyCommand: str
    runInStageVerify: bool
    autoVerifyEffective: bool
    autoVerifyDebtRecorded: bool
    autoFixEligible: bool
    nextStage: str | None
    nextCommand: str | None
    primaryCommand: str | None
    deferredCommand: str | None
    invalidAutoVerifyKeys: list[str]
    gitRepo: bool
    cleanTree: bool | None
    warning: str
    epicReconcile: EpicReconcile


class StageExitPayload(TypedDict):
    """Serialized direct or nested exit result."""

    directives: StageExitDirectives
    nextSteps: str | None
    sentinel: str | None
```

A direct owner sets `terminalOwnedBy == "self"`, returns exactly one `nextSteps` block,
and ends that string with `NEXT_STEPS_SENTINEL`. A nested owner sets
`terminalOwnedBy == "outer"`, `nextSteps is None`, and `sentinel is None`; it never prints
a terminal block. Stages 0–6 are direct outer callers unless a future explicit contract
says otherwise.

`primaryCommand` is the only fenced command while verification is unresolved.
`deferredCommand` may name the production successor only as post-verification guidance.
`nextCommand` remains for compatibility and routing introspection; consumers must not
promote it over `primaryCommand`.

## 5. Rendering and Routing Function Contracts

Existing import path and signatures read from `scripts/forge-session.py`:

```python
def next_stage(state: dict) -> str | None: ...
def _host_command(command: str, host: str) -> str: ...
def _resolve_feature_dir(specs_dir: Path, feature: str, epic: str | None) -> Path: ...
def _resolve_feature_dir_for_write(
    specs_dir: Path, feature: str, epic: str | None
) -> Path: ...
```

Extend rendering to accept authoritative and deferred commands:

```python
def _next_steps_block(
    primary_command: str,
    host: str,
    reconcile: dict | None = None,
    deferred_command: str | None = None,
    outcome_text: str | None = None,
) -> str:
    """Render one sentinel-terminated terminal block.

    Args:
        primary_command: The sole fenced action.
        host: Command and fresh-session wording target.
        reconcile: Existing epic-backflow override metadata.
        deferred_command: Optional production action allowed only after the primary
            verification/recovery action succeeds.
        outcome_text: Optional deterministic loop/docs/branch outcome explanation.

    Returns:
        A string whose final line is exactly `NEXT_STEPS_SENTINEL`.
    """
```

Claude translates freshness to `/clear`, Pi to `/new`, and generic hosts to neutral
prose. `_host_command` continues translating canonical `/feature-forge:` commands to
Pi `/skill:` commands only. Capability, never host name, chooses `standard` versus
`manual-print`.

## 6. Verification State Model

Extend `references/pipeline-state-schema.json#/definitions/verifyEntry` additively:

```python
class VerifyEntry(TypedDict, total=False):
    """Feature or epic verification state persisted by `state-verify`."""

    status: VerifyStatus
    findingsFile: str | None
    findingsCount: int | None
    verifiedAt: str | None
    fixedAt: str | None
    commitHash: str | None
    verifiedStageVersion: int | None
    scheduledAt: str | None
    scheduledStageVersion: int | None
```

State meanings:

- `pending`: existing generic/manual pending state.
- `auto-verify-pending`: automatic verification was scheduled but no terminal result
  replaced it. It is reported as `auto-pending`, remains outstanding, and never counts as
  success or ordinary `never`.
- `passed`: clean verification; requires current artifact revision.
- `findings-reported`: findings exist; requires current artifact revision and count.
- `findings-applied`: fixes landed, clears `verifiedStageVersion`, and remains unresolved
  until a later `passed` write.
- `skipped`: explicit user resolution with no verified revision.

Exact targeted writer signature:

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
    """Write one verify result transition or one provenance follow-up.

    Raises:
        UsageError: Mixed modes, invalid metadata, invalid hash, missing entry,
            unsafe/ambiguous target, or atomic write failure.
    """
```

Exactly one mode is accepted:

1. **Result mode:** `status` is present and `commit_hash` absent. Initial terminal writes
   set `commitHash` to `None`. Scheduling is idempotent for an equal
   `scheduledStageVersion` and does not churn timestamps/bytes.
2. **Commit-2 mode:** only `commit_hash` plus target flags are present. It requires an
   existing verify entry and changes only `commitHash` and top-level `updatedAt`.

Feature writes reuse `_load_state_for_write(...) -> tuple[Path, dict]` and
`_commit_state(state_path: Path, state: dict) -> dict` from
`scripts/forge-session.py`. Epic writes target `{specsDir}/{epic}/.epic-state.json`,
read the current manifest revision, and never pass through member-feature resolution.

Update existing classifiers without changing import paths:

```python
def verify_state(state: dict) -> tuple[str | None, str]: ...
def pending_verify(state: dict) -> str | None: ...
def _verify_state_for(state: dict, stage: str) -> str: ...
def build_rows(specs_dir: Path, config: dict | None = None) -> list[FeatureRow]: ...
```

All four recognize `auto-verify-pending` distinctly. `FeatureRow.verifyState` may carry
`"auto-pending"`; its pending and command fields remain true/non-null.

## 7. Errors, Safety, and Provenance

```python
class UsageError(Exception):
    """A usage or I/O failure printed as `Error: ...` and mapped to exit 2."""
```

No new public exception hierarchy is needed. Every strict failure raises `UsageError`
before mutation. State writes remain sibling-temp-file + flush + `fsync` + `os.replace`.
Existing exact integration signatures from `scripts/forge-session.py` are:

```python
def _load_state_for_write(
    specs_dir: Path, feature: str, epic: str | None
) -> tuple[Path, dict]: ...
def _commit_state(state_path: Path, state: dict) -> dict: ...
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

`cmd_state_complete` and `cmd_state_verify` validate every **new** non-null hash with
`FULL_GIT_HASH_RE.fullmatch`. Existing loaded short hashes remain readable because schema
and read paths stay permissive. The two-commit protocol is unchanged: Commit 1 writes
`commitHash: null`; Commit 2 records the full artifact hash; no code or skill uses
`--amend`.

## 8. Duplicate-Aware JSON Types

Create `scripts/forge_json.py` with this exact importable API:

```python
from pathlib import Path


def load_json_with_duplicates(path: Path) -> tuple[object, list[str]]:
    """Load JSON with last-key-wins values and ordered duplicate key names.

    Args:
        path: UTF-8 JSON file to read.

    Returns:
        A pair of the parsed JSON value and duplicate key names in encounter order.
        A key is reported for every object level, not only the root.

    Raises:
        OSError: The file cannot be read.
        json.JSONDecodeError: The text is malformed JSON.
    """


def warn_duplicate_keys(path: Path, duplicate_keys: list[str]) -> None:
    """Write one deterministic warning per duplicate key to stderr."""
```

The parser uses `json.loads(text, object_pairs_hook=hook)`. The hook assigns every pair
to a normal dict so the last value wins, while appending a key when it already exists in
the current object. Warnings name both path and key, never contaminate JSON stdout, and
never change success/failure semantics. `_load_config(config_path: Path) -> dict` in
`forge-session.py` and the corresponding bootstrap config read import this helper.

## Dependencies

None. This is the foundation contract for `01-architecture-layout.md` and every domain
document.

## Verification

- [ ] `EXIT_STAGES` contains exactly the nine required identifiers.
- [ ] Every outcome set and verify-mode mapping equals the literals above.
- [ ] Direct payloads contain one final sentinel; nested payloads contain none.
- [ ] `auto-verify-pending` appears in schema and both script vocabulary constants.
- [ ] `cmd_state_verify` rejects mixed result/provenance modes before mutation.
- [ ] New short/non-hex hashes fail; legacy loaded short hashes still parse.
- [ ] Duplicate keys at root and nested objects warn while preserving the final value.
