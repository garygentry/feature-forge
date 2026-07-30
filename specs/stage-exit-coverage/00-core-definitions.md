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
    # Reconcile explicitly deferred by the user, carrying the reason; None means
    # not deferred. A deferred reconcile never blocks, whatever `required` says.
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
    # For a verify/fix branch exit, the production stage the diversion served and
    # rejoins. None on a production-stage exit, which serves only itself.
    servedStage: str | None
    # Verify mode in play (`prd`, `tech`, `specs`, `backlog`, `impl`, `epic`), keyed
    # by VERIFY_MODE_TO_STAGE. None when this exit is not a verify/fix exit.
    verifyMode: str | None
    # Terminal outcome for stages with a multi-way result. Must be a member of
    # EXIT_OUTCOMES[stage] (§2) — consult that table rather than this comment,
    # which is deliberately not a second copy of the domain. None for stages
    # whose exit has a single outcome.
    outcome: str | None
    # Branch ownership for a verify/fix exit — ExitOwner, i.e. exactly "direct"
    # (this call owns and prints the terminal block) or "nested" (an outer
    # authoring stage owns it). REQUIRED for forge-verify/forge-fix and REJECTED
    # for stages 0–6, which are always direct owners (§3, `02` §3.1 step 5).
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
    # Whether the host can dispatch a clean-room verifier subagent —
    # VerifyCapability, i.e. exactly "interactive" or "manual". A manual host
    # receives verify-first ordering with copy-paste commands instead of an
    # interactive gate; capable Pi is interactive, not manual (REQ-EXIT-07).
    verifyCapability: str
    # Current verification state of the served artifact, as classified by
    # `verify_state` — including "auto-pending" for unrun scheduled verification.
    verifyState: str
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
    # True only if the auto-verify-pending marker was durably persisted. False with
    # `runInStageVerify: True` means the debt write failed — the caller must not
    # treat scheduling as done (REQ-DEBT-01/04).
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
    # verify command, never the downstream stage. The one fenced command in the
    # rendered block. None only when the pipeline has no further action.
    primaryCommand: str | None
    # Post-verification guidance shown as prose, never fenced, so it cannot be
    # mistaken for the primary action. None when there is nothing deferred.
    deferredCommand: str | None
    # Keys in autoVerifyStages that name no verify-capable stage — a config typo.
    # Empty list means the config was checked and clean; the key is always present
    # when config was read at all, so [] and absent differ.
    invalidAutoVerifyKeys: list[str]
    # Whether the working directory is a git repository at all.
    gitRepo: bool
    # Clean-tree snapshot taken BEFORE the pending-debt write, so the sanctioned
    # state mutation does not dirty its own precondition. None when `gitRepo` is
    # False — unknown, not clean.
    cleanTree: bool | None
    # Human-readable non-fatal advisory. Present only when there is something to
    # warn about; absence means no warning, not an empty one.
    warning: str
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
    """Feature or epic verification state persisted by `state-verify`.

    `total=False` is load-bearing: terminal writes DELETE the scheduling keys rather
    than nulling them (03 §3.3), so an absent `scheduledAt` means "not scheduled"
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

## Public API and Internal Surface

This document declares no CLI command of its own — it is the shared vocabulary every other
numbered spec imports. Signatures live in the sections cited below and are not repeated here.

- **User-facing CLI:** none. The commands that expose these definitions belong to
  `02-stage-exit-routing.md` (`stage-exit`), `03-verification-state.md` (`state-verify`), and
  `05-config-and-distribution.md` (config loading).
- **Repository-internal, importable by sibling modules and tests:** the §2 literals
  `EXIT_STAGES`, `EXIT_OUTCOMES`, `VERIFY_MODE_TO_STAGE`, `NEXT_STEPS_SENTINEL`, and
  `FULL_GIT_HASH_RE`; the §4 result types `EpicReconcile`, `StageExitDirectives`, and
  `StageExitPayload`; the §6 `VerifyEntry`; the §7 `UsageError`; and the §8 duplicate-aware
  helpers `load_json_with_duplicates` and `warn_duplicate_keys` (defined in the new
  `scripts/forge_json.py`, the one genuinely importable module this feature adds). The §5
  `stage_exit`, `next_stage`, and §6 `cmd_state_verify` entry points are declared here and
  implemented by their owning documents.
- **Private helpers (leading underscore, no cross-module contract):** `_host_command`,
  `_resolve_feature_dir`, `_resolve_feature_dir_for_write`, `_next_steps_block`,
  `_verify_state_for`, `_load_state_for_write`, and `_commit_state`. They appear here only so
  callers can be typed against them; their behavior is owned by §5–§7 and by the existing
  source they already exist in. Renaming one is an internal change, not a contract break.
- **Test/eval-only:** none. Compliance and fixture types are owned by
  `06-compliance-and-coverage.md`.

`scripts/forge-session.py` and `scripts/epic-manifest.py` are executable scripts, not an
installed package: there is no `__all__` and no exports map, so "importable" here means
imported by sibling scripts and by `tests/` via the project's existing path convention.

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
