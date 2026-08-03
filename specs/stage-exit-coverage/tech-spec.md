# Stage Exit Coverage — Technical Specification

> Based on PRD v3. This document specifies HOW the deterministic exit contract expands; the PRD remains the source of WHAT is required. Every technical decision cites its governing requirement IDs.

## 1. Overview

Stage Exit Coverage extends the existing Python-stdlib control plane in `scripts/forge-session.py` so every pipeline-advancing production or branch skill closes through one deterministic routing API (REQ-EXIT-01..05, REQ-PROD-01..06). It does not introduce a service, package, database, or network dependency.

The design has six coordinated parts:

1. Expand `stage-exit` from stages 0–4 to the explicit nine-skill coverage set: `forge-0-epic` through `forge-6-docs`, plus direct `forge-verify` and `forge-fix` (REQ-EXIT-01/02, REQ-GUARD-01/02).
2. Add typed `--served-stage`, `--verify-mode`, `--outcome`, `--owner`, and `--verify-capability` inputs for branch/loop and verification-gate routing. New paths fail closed; existing stages 0–4 retain their tolerant state fallback while correcting unsafe verify-primary ordering (REQ-EXIT-06/07, REQ-ROUTE-01..06, REQ-REL-02, REQ-COMPAT-01).
3. Add a targeted `state-verify` writer and persist `auto-verify-pending` immediately before `runInStageVerify: true` is returned (REQ-DEBT-01..06, REQ-STATE-03).
4. Replace hand-written loop, docs, epic-edit, verify, and fix termini with the scripted sentinel contract while preserving current context-aware routing (REQ-EXIT-03/04, REQ-PROD-01..06).
5. Add recursive duplicate-key diagnostics through a small shared stdlib JSON parser while preserving last-key-wins compatibility (REQ-CONFIG-01..04).
6. Prove the expanded surface with unit/integration matrices, an explicit canonical coverage guard, and a separate verify → fix → re-verify compliance fixture that requires command-result evidence (REQ-GUARD-01..03, REQ-EVAL-01..03).

The configured project stack remains Python with `ruff check scripts/ eval/` and `bash scripts/validate.sh`. `smokeCommand` remains `null` by design (REQ-COMPAT-03).

## 2. Module Structure

### 2.1 Canonical implementation layout (REQ-EXIT-01/02, REQ-STATE-03, REQ-CONFIG-02, REQ-GUARD-01)

```text
scripts/
  forge-session.py               # expanded stage-exit, state-verify, routing tables
  epic-manifest.py               # verify-status parity; existing render-status CLI reused
  forge-bootstrap.py             # adopts shared duplicate-aware config read
  build-adapters.py              # unchanged; listed for orientation only

references/
  stage-exit-protocol.md         # one scripted contract for all covered exits
  pipeline-state-schema.json     # auto-verify-pending + scheduling metadata
  epic-manifest-schema.json      # additive integer revision for epic freshness
  shared-conventions.md          # register state-verify; immediate state-note recipe

skills/
  forge/SKILL.md                 # auto-pending rows + nested-owner dispatch wording
  forge-0-epic/SKILL.md
  forge-0-epic/references/edit-mode.md
  forge-1-prd/SKILL.md
  forge-2-tech/SKILL.md
  forge-3-specs/SKILL.md
  forge-4-backlog/SKILL.md
  forge-5-loop/SKILL.md
  forge-5-loop/references/result-reporting.md
  forge-5-loop/references/runner-contract.md   # stale --model wording correction (sole source)
  forge-6-docs/SKILL.md
  forge-verify/SKILL.md
  forge-verify/references/findings-template.md  # epic-state writes move to state-verify
  forge-fix/SKILL.md             # all covered direct exits use scripted invocation

eval/
  run-compliance-eval.py         # separate branch-path fixture/scorer
  README.md                       # linear baseline vs branch result

tests/
  test_stage_exit.py
  test_stage_exit_protocol.py
  test_auto_verify.py
  test_state_verbs.py
  test_state_schema_conformance.py
  test_stage_constants_parity.py
  test_effective_config.py
  test_compliance_eval.py
  test_build_adapters.py          # expanded host/runtime-copy assertions
  test_json_loader_parity.py      # mirrored loader drift guard
  test_forge_bootstrap.py         # duplicate commitPrefix warning + exit-2 policy
```

`forge-session.py` remains the public control-plane executable. Exit logic is not extracted into a new package: the repository already copies this flat helper into every adapter, and keeping state resolution, CLI validation, and routing together minimizes adapter import risk (REQ-COMPAT-02, REQ-PERF-01). The duplicate-aware parser is likewise **not** extracted: it is mirrored into `forge-session.py` and `forge-bootstrap.py` with a drift guard, because the flat scripts are copied verbatim into six bundles and share no import module by standing repository invariant (`01-architecture-layout.md` §3.4; REQ-CONFIG-02/04, REQ-COMPAT-02).

### 2.2 Generated output (REQ-COMPAT-02, REQ-GUARD-03)

No file under `adapters/` is hand-edited. `scripts/build-adapters.py` copies both runtime helpers and translates skill-body host commands as today. Canon, helper, and schema changes are followed by `python3 scripts/build-adapters.py`; generated adapters land in the same change.

## 3. Technical Decisions

### 3.1 Explicit covered-skill and outcome tables (REQ-EXIT-01/02, REQ-GUARD-01/02, REQ-REL-01)

Replace the five-entry `EXIT_STAGES` assumption with an explicit immutable coverage set:

```python
EXIT_STAGES: Final[tuple[str, ...]] = (
    "forge-0-epic", "forge-1-prd", "forge-2-tech", "forge-3-specs",
    "forge-4-backlog", "forge-5-loop", "forge-6-docs",
    "forge-verify", "forge-fix",
)
```

Stage-specific outcome sets are explicit rather than free-form:

```python
EXIT_OUTCOMES: Final[dict[str, frozenset[str]]] = {
    "forge-5-loop": frozenset({"complete", "partial", "blocked", "needs-human", "deferred"}),
    "forge-6-docs": frozenset({"complete", "blocked"}),
    "forge-verify": frozenset({"passed", "findings", "skipped", "failed"}),
    "forge-fix": frozenset({
        "no-findings", "decisions", "failed", "applied", "reverified",
        "reverify-findings", "deferred",
    }),
}
```

Stages 0–4 need no `--outcome`; their current state-driven behavior remains the compatibility baseline. `forge-5-loop`, `forge-6-docs`, direct `forge-verify`, and direct `forge-fix` require an allowed outcome. Invalid stage/outcome combinations are `UsageError` (exit 2), never a fallback command (REQ-ROUTE-03, REQ-REL-02).

Alternative considered: one generic success/findings/failed vocabulary. Rejected because it cannot distinguish loop recovery or the complete fix/re-verify terminus matrix (REQ-PROD-02, REQ-ROUTE-05).

### 3.2 Typed branch context and terminal ownership (REQ-EXIT-03/04, REQ-ROUTE-01..06)

Extend the existing function rather than introduce a second routing entry point:

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
    ...
```

CLI additions:

```text
stage-exit --feature F --stage S
  [--served-stage forge-0-epic|forge-1-prd|...|forge-6-docs]
  [--verify-mode epic|prd|tech|specs|backlog|impl]
  [--outcome <stage-specific enum>]
  [--owner direct|nested]
  [--verify-capability interactive|manual]
  [existing --specs-dir/--config/--epic/--next-feature/--host/--json]
```

Rules:

- `forge-verify` and `forge-fix` require `--owner` (REQ-EXIT-04).
- `--owner nested` returns a machine-readable payload with `directives.terminalOwnedBy = "outer"`, routing/result fields, `nextSteps = null`, and `sentinel = null`. The nested skill prints no terminal block (REQ-EXIT-04).
- `--owner direct` emits exactly one sentinel-terminated block (REQ-EXIT-03).
- Direct branch calls accept explicit `--served-stage` and/or serialized `--verify-mode` metadata. `--verify-mode` maps uniquely (`prd→forge-1-prd`, `tech→forge-2-tech`, `specs→forge-3-specs`, `backlog→forge-4-backlog`, `impl→forge-5-loop`, `epic→forge-0-epic`). If both inputs are present, they must map to the same production stage; disagreement exits 2. Otherwise explicit `--served-stage` takes precedence, then the unique mode mapping. Missing metadata exits 2 with an actionable instruction to pass one of these flags (REQ-ROUTE-01..03).
- Direct `forge-verify` obtains `verify_mode` from its explicit mode argument or pipeline-state auto-detection. Direct `forge-fix` obtains it from the selected findings filename/header before invoking `stage-exit`; it never guesses from conversational context. Nested callers pass the served stage they already own.
- Epic verification remains epic-scoped; it never resolves or writes a member `.pipeline-state.json` (REQ-SEC-01).
- `--verify-capability interactive` means the caller has both a question mechanism and a dispatchable clean-room verifier; `manual` means either capability is absent. The skill determines this from the actual tool surface before invoking the script—never from `--host` alone (REQ-EXIT-07).

The direct branch routing table is outcome-driven:

- verify `passed` → next applicable production action after the served stage;
- verify `findings` → `forge-fix` with the served stage carried forward;
- verify `skipped` → next applicable production action;
- verify `failed` → direct `forge-verify` retry/recovery command;
- fix `applied` → `forge-verify` for the same served stage;
- fix `reverified` → next applicable production action;
- fix `reverify-findings` → `forge-fix` for the same served stage;
- fix `no-findings` → `forge-verify` when verification is still required, otherwise state-derived advancement;
- fix `decisions`, `failed`, or `deferred` → a deterministic `forge-fix`/navigator recovery command with outcome text, never silent advancement.

### 3.3 Verify-first primary action and capability-aware gates (REQ-EXIT-06/07, REQ-A11Y-01, REQ-COMPAT-01)

Verification state controls the authoritative terminal action before production-stage routing is rendered:

- If verification is `fresh` or explicitly `skipped`, the production successor remains the fenced primary command.
- If auto-verify is effective, the outer stage runs the nested verify/fix chain before any terminal block; only a passed result or explicit skip permits the production successor to become primary. The emitted gate on this path is `none`. Where the caller may not dispatch unsolicited but has a question mechanism, it still needs *consent* before dispatching, so it reuses the Standard Verify Gate block with **choice 2 omitted** — auto-verify is already effective, so "enable auto-verify going forward" carries no trade-off. The consent form is two choices: *Verify now* (recommended) and *Skip for now*. The emitted `verifyGate` value stays `none` rather than becoming `standard`, because changing it would alter directive values for the existing stages 0–4 (REQ-COMPAT-01). This is the only case where the rendered gate and the emitted `verifyGate` differ, and it exists because the gate here supplies consent rather than selecting policy.
- If verification is outstanding and `--verify-capability interactive`, emit `verifyGate: "standard"` for Claude **or Pi**. The skill presents the Standard Verify Gate. Choosing verify must complete the verify/fix/re-verify path before printing an advancing block; choosing skip first records `skipped`; choosing stop emits no terminal advancement.
- If verification is outstanding and capability is `manual`, emit `verifyGate: "manual-print"` and render `verifyCommand` as the fenced primary command. Render the production `nextCommand` only as unfenced follow-up text: "After verification passes, continue with …". The fresh-session instruction follows verification rather than preceding it.

`--host` now controls only command translation and fresh-session wording. It does not imply interactive or clean-room capability. This removes the current `host == "claude"` branch: capable Pi receives the same interactive gate, while Pi/generic/Claude without clean-room support receive the safe verify-first fallback.

The output directives expose both routing layers without ambiguity:

```json
{
  "verifyGate": "manual-print",
  "primaryCommand": "/skill:forge-verify feature tech",
  "deferredCommand": "/skill:forge-3-specs feature",
  "nextStage": "forge-3-specs"
}
```

`_next_steps_block(...)` accepts primary and optional deferred commands rather than always fencing the production successor. No path may fence or recommend the deferred production command while verification remains unresolved (REQ-EXIT-06).

Alternative considered: classify all Pi sessions as interactive. Rejected because `forge-verifier` is extension-provided and may be unavailable; explicit runtime capability preserves the manual fallback without treating capable Pi as generic.

### 3.4 Compatibility-split error policy (REQ-PROD-06, REQ-REL-02, REQ-COMPAT-01)

The current `_resolve_feature_dir(...) -> Path` remains the tolerant read path for established stages 0–4: unreadable state falls back to the existing fixed successor. New explicit-routing paths use `_resolve_feature_dir_for_write` or an equivalent strict resolver and fail on unsafe/ambiguous feature, epic, served-stage, or outcome input.

Epic member routing is the one documented tolerant new case: if `forge-0-epic --next-feature` cannot resolve readable member state, it falls back to creation-mode `forge-1-prd <member>` and emits a named warning directive; it never fabricates later progress (REQ-PROD-05/06). This fallback does not apply when member state resolves successfully.

### 3.5 Live progress routing for epic edit and docs (REQ-PROD-03..06)

For `forge-0-epic --next-feature <member>`, resolve the member state and call the verified existing `next_stage(state: dict) -> str | None`. The resulting command uses the member's actual first incomplete production stage. Creation mode remains unchanged because a new member has no completed production stage (REQ-PROD-05, REQ-COMPAT-01).

For epic-member `forge-6-docs`, call the adjacent deterministic helper rather than reimplementing dependency and completion rules:

```text
python3 <bundle-root>/scripts/epic-manifest.py render-status <epic> \
  --specs-dir <specsDir> --json
```

The stage-exit router consumes `nextCommand`, actionable/blocked state, and rollup from that result. An actionable member routes to its live command; a blocked/no-actionable epic routes to the epic dashboard; completed epic routes to the dashboard completion view. Standalone docs completion uses `/feature-forge:forge <feature>` as the authoritative fenced command, with new-feature guidance as secondary text (REQ-PROD-04).

The subprocess is local, bounded by the small manifest/state files, and introduces no network or history scan (REQ-PERF-01).

### 3.6 Loop outcome routing (REQ-PROD-01/02, REQ-REL-01)

Every result template invokes the same scripted stamp after state persistence:

- `complete` → existing impl-verify/docs or epic-member handoff logic, represented by scripted directives;
- `partial` and `deferred` → `/feature-forge:forge-5-loop <feature>` as the fenced primary command;
- `blocked` and `needs-human` → `/feature-forge:forge <feature>` as the fenced primary diagnostic/recovery command;
- no non-complete outcome routes to `forge-6-docs` or marks downstream readiness.

Outcome-specific explanatory text is emitted inside NEXT-STEPS above the sentinel. Skills do not append prose after the block (REQ-EXIT-03).

### 3.7 Durable auto-verify debt and unified verify writer (REQ-DEBT-01..06, REQ-STATE-03, REQ-OBS-01/02)

Add `auto-verify-pending` to the verify status vocabulary in both `forge-session.py` and `epic-manifest.py`, and to `references/pipeline-state-schema.json`. Add optional scheduling metadata to `verifyEntry`:

```json
{
  "status": "auto-verify-pending",
  "scheduledAt": "2026-07-30T00:00:00Z",
  "scheduledStageVersion": 1
}
```

Epic freshness uses one canonical artifact revision. Add required integer `revision >= 1` to `epic-manifest-schema.json`; epic creation initializes it to `1`, and every successful manifest/edit-mode mutation increments it exactly once in the same atomic write. Validation/read paths treat a legacy manifest with no field as revision `1`; its first successful mutation writes `revision: 2`. Failed or semantic no-op edits do not increment it. Epic `scheduledStageVersion` and `verifiedStageVersion` store this manifest revision, never a member stage version.

Add one targeted atomic writer with separate result-transition and commit-2 provenance modes:

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
    ...
```

CLI:

```text
state-verify --feature F --stage <verify-capable production stage>
  [--status auto-verify-pending|passed|findings-reported|findings-applied|skipped]
  [--findings-file P] [--findings-count N]
  [--verified-stage-version N] [--commit-hash HASH]
  [--epic E] [--specs-dir D] [--json]
```

Exactly one mode is required: a result transition supplies `--status`; commit-2 provenance supplies only `--commit-hash` plus identity/path flags. Initial terminal result writes set `commitHash: null`. Commit-2 mode requires an existing applicable verify entry, validates `re.fullmatch(r"[0-9a-fA-F]{40}", value)` before mutation, updates only `commitHash` and the state file's `updatedAt`, and rejects status/findings/version metadata. Missing entries, short/non-hex hashes, or mixed modes fail before mutation. No amend path exists.

For feature stages, the writer maps the production stage through `VERIFY_TOKEN_BY_STAGE`, resolves with `_load_state_for_write(...)`, mutates only that verify entry, refreshes `updatedAt`, and persists with `_commit_state(...)` (REQ-STATE-03). `forge-0-epic` is an explicit branch before that map: `feature` is the epic name, `epic` must be absent or equal to it, the writer strictly resolves `{specsDir}/{feature}/epic-manifest.json`, reads its canonical revision, and atomically mutates only `stages.forge-verify-epic` plus top-level `updatedAt` in the sibling `.epic-state.json`. It never invokes the member-feature writer. Unsafe names, a missing/mismatched manifest, or ambiguous/conflicting epic inputs fail before mutation. The epic path supports both writer modes and all statuses with the same metadata validation, hash validation, and atomic-failure guarantees as feature state.

Read-side behavior is equally explicit: epic `stage_exit`, pending-debt selection, navigator/dashboard rows, rollups, and freshness classification load the epic root's `.epic-state.json` and compare `scheduledStageVersion`/`verifiedStageVersion` to the current manifest revision. They never call feature `_resolve_feature_dir` for epic verification and never inspect a member version. Missing epic state means never verified; matching pending revision means `auto-pending`; matching terminal revision means fresh; a mismatched or legacy result with no recorded revision means stale. This same read path makes pending debt and terminal replacement visible to direct and nested routing.

For `findings-applied`, the writer records `fixedAt` but deletes any existing `verifiedStageVersion` and rejects a supplied `--verified-stage-version`. This deliberately leaves verification freshness unresolved until a subsequent `passed` write records the current artifact revision (feature production-stage version or epic manifest revision); interruption between fix and re-verify therefore cannot advance the pipeline.

`stage_exit()` computes the clean-tree/auto-fix directives first, then, immediately before returning a payload with `runInStageVerify: true`, calls the same internal writer with `auto-verify-pending`. The pending write is idempotent for the same `scheduledStageVersion`: repeated stage-exit calls do not rewrite timestamps or churn bytes (REQ-REL-01). A newer feature-stage version or epic manifest revision creates a new schedule timestamp/version. Terminal writes remove `scheduledAt`/`scheduledStageVersion`, set the existing verified/fixed metadata as applicable, and replace the pending status. Dispatch failure or non-adherence performs no terminal write, so debt remains visible (REQ-DEBT-03/04).

The pending state is classified distinctly:

- `verify_state()` returns a new label `auto-pending`;
- `_verify_state_for()` reports `auto-pending`, never `never`;
- `pending_verify()` returns the served stage;
- `build_rows()`, navigator output, epic rollups, stage-exit directives, and downstream pre-flight text name the auto-verify obligation;
- `auto-verify-pending` is not resolved, not skipped, and never treated as completion.

The expected pending state-file modification is a sanctioned control-plane mutation. The pre-scheduling clean-tree snapshot determines `autoFixEligible`; subsequent verify/fix commits include the verify-state transition rather than treating the marker itself as unrelated user dirt.

Alternative considered: a debt-only command. Rejected because it would duplicate strict resolution and mutation logic and leave existing hand-authored terminal verify writes in place.

### 3.8 Full hashes on new writes, permissive legacy reads (REQ-STATE-01/02/04)

Validate `--commit-hash` at each targeted writer boundary with `re.fullmatch(r"[0-9a-fA-F]{40}", value)`. `cmd_state_complete(...)` and `cmd_state_verify(...)` reject any new short or non-hex hash before mutation; the latter uses the explicit commit-2 mode in §3.7 for both feature and epic verification state.

Do not add a restrictive schema pattern to legacy `commitHash` fields and do not reject a loaded short hash. Existing state therefore remains readable without migration (REQ-STATE-02). The two-commit protocol remains unchanged: Commit 1 writes artifacts/state with `commitHash: null`; Commit 2 records the full artifact hash; no amend path is introduced (REQ-STATE-04).

### 3.9 Recursive duplicate-key diagnostics (REQ-CONFIG-01..04, REQ-PERF-02)

Mirror an identical stdlib helper pair into both config-reading scripts:

```python
def load_json_with_duplicates(path: Path) -> tuple[object, list[str]]:
    """Return last-key-wins JSON data and ordered duplicate key names."""
    ...
```

It uses `json.loads(..., object_pairs_hook=...)`, records duplicates at every object nesting level, and assigns each repeated key normally so the last value wins. Callers retain their current malformed/missing-file policy. A shared warning formatter writes one warning per duplicate key/source to stderr, preserving JSON stdout. `forge-session.py::_load_config(config_path: Path) -> dict`, effective config, stage exit, navigator/status consumers, and `forge-bootstrap.py` use this parser. Duplicate detection is general and includes nested objects such as `loopRunner` and `autoVerifyStages`; it is not specialized to `autoVerify` (REQ-CONFIG-04).

`scripts/build-adapters.py` is unchanged: `RUNTIME_HELPERS` stays at six entries, no new file is emitted, and no import has to resolve inside a bundle. `tests/test_json_loader_parity.py` holds the two copies identical.

### 3.10 Canonical scripted exit and explicit guard (REQ-EXIT-03..07, REQ-GUARD-01..03)

`references/stage-exit-protocol.md` becomes the sole contract for all nine covered direct invocations. The existing standard and warm bespoke blocks are removed/replaced with scripted stamps. Canonical skill bodies/references pass stage-specific typed inputs; direct branch invocations pass `--owner direct`; auto/nested chains pass `--owner nested` and return to the outer caller.

`tests/test_stage_exit_protocol.py` owns an explicit allow-list of exactly the nine covered skills and verifies each direct path contains the canonical invocation/terminal-print contract. Navigator, init, bootstrap, guide, and advisory skills remain explicitly excluded. Existing tests that assert bespoke loop exits or terminal docs behavior are replaced with positive scripted-contract assertions, not deleted without coverage (REQ-GUARD-03).

Host behavior remains two-layered and tested:

- build-time skill-body translation in `scripts/build-adapters.py`;
- runtime `_host_command(command: str, host: str) -> str` and `_next_steps_block(...)` rendering.

Claude uses `/clear` and `/feature-forge:*`, Pi uses `/new` and `/skill:*`, and generic output remains host-neutral. Gate selection comes from `--verify-capability`, so capable Pi is interactive and every manual host receives verify-first ordering (REQ-EXIT-05..07, REQ-COMPAT-01).

### 3.11 Focused prerequisite/follow-ups (REQ-CAP-01, REQ-FOLLOW-01/02)

Commit `c174b55` already satisfied the Step 2d runner-contract prerequisite. Implementation verifies this before touching `skills/forge-5-loop/SKILL.md` and preserves both body caps.

Correct the stale wording in `skills/forge-5-loop/references/runner-contract.md` — the sole runner-contract source — that calls `--model` an "optional flag below", without making the agent-selection reference unconditional (REQ-FOLLOW-01).

Add an immediate sanctioned `state-note` invocation to the PRD/tech parking-lot instructions, including `--epic` for members, so promised persistence never relies on hand-authored JSON (REQ-FOLLOW-02).

## 4. Data Model

### 4.1 Verification entry evolution (REQ-DEBT-01..06, REQ-COMPAT-02)

`verifyEntry.status` becomes:

```text
pending | auto-verify-pending | passed | findings-reported |
findings-applied | skipped
```

`pending` retains its existing generic/manual meaning. `auto-verify-pending` means effective configuration scheduled unattended in-stage verification but no terminal result has replaced the debt. Existing files need no migration.

New optional fields:

| Field | Type | Meaning |
|---|---|---|
| `scheduledAt` | ISO-8601 string/null | When automatic verification became owed |
| `scheduledStageVersion` | integer/null | Artifact revision owed verification: feature production-stage version or epic manifest revision |

Existing `findingsFile`, `findingsCount`, `verifiedAt`, `fixedAt`, `commitHash`, and `verifiedStageVersion` remain schema-compatible. For epic state, the version fields carry the manifest revision and top-level `updatedAt` is maintained by every write. Transition semantics are tightened: a `findings-applied` write clears `verifiedStageVersion`, and only a subsequent passing verification restores the current artifact revision. Scheduling metadata is cleared by terminal result writes.

### 4.2 Exit request/result model (REQ-OBS-01, REQ-REL-01)

The CLI remains the serialized request contract. The JSON result preserves existing top-level keys and adds branch metadata without renaming compatibility fields:

```json
{
  "directives": {
    "stage": "forge-verify",
    "servedStage": "forge-2-tech",
    "verifyMode": "tech",
    "outcome": "findings",
    "owner": "direct",
    "terminalOwnedBy": "self",
    "verifyCapability": "interactive",
    "nextStage": "forge-fix",
    "nextCommand": "/feature-forge:forge-fix feature --served-stage forge-2-tech",
    "primaryCommand": "/feature-forge:forge-fix feature --served-stage forge-2-tech",
    "deferredCommand": null,
    "verifyState": "failing",
    "autoVerifyDebtRecorded": false
  },
  "nextSteps": "...sentinel-terminated block...",
  "sentinel": "─ forge: end of stage ─"
}
```

Nested branch output sets `terminalOwnedBy: "outer"`, `nextSteps: null`, and `sentinel: null`. Tests treat this as intentional non-terminal structured output, not a missing exit (REQ-EXIT-04).

## 5. API Design

### 5.1 `stage-exit` command (REQ-EXIT-01..07, REQ-ROUTE-01..06)

```text
forge-session.py stage-exit
  --feature FEATURE
  --stage {forge-0-epic,...,forge-6-docs,forge-verify,forge-fix}
  [--served-stage {forge-0-epic,...,forge-6-docs}]
  [--verify-mode {epic,prd,tech,specs,backlog,impl}]
  [--outcome <validated per-stage value>]
  [--owner {direct,nested}]
  [--verify-capability {interactive,manual}]
  [--next-feature FEATURE]
  [--epic EPIC]
  [--specs-dir DIR]
  [--config PATH]
  [--host {claude,pi,generic}]
  [--json]
```

Exit codes remain 0 success / 2 usage-I/O error. Stages 0–4 keep read-tolerant state closure, but unresolved verification changes the primary command per §3.3. Invalid explicit branch context is a usage error with a plain `Error:` stderr line.

### 5.2 `state-verify` command (REQ-DEBT-01..04, REQ-STATE-03)

The exact command, dual-mode function signature, and commit-2 guards are specified in §3.7. Terminal statuses require their applicable metadata: `passed`/`findings-reported` require `--verified-stage-version`; findings status requires non-negative `--findings-count`; `skipped` records no verified version; `findings-applied` records `fixedAt`, requires no verified version, and clears any prior `verifiedStageVersion` so re-verification remains durably outstanding. Contradictory combinations fail before mutation. Commit-2 mode accepts only a validated full `--commit-hash` and identity/path flags, requires an existing entry, and changes only `commitHash` plus `updatedAt`. For `--stage forge-0-epic`, `--feature` names the epic and both modes read the manifest revision and write only the epic root's `.epic-state.json`; all other stages retain strict feature-state resolution.

### 5.3 Duplicate-aware JSON helper (REQ-CONFIG-01..04)

`load_json_with_duplicates(path: Path) -> tuple[object, list[str]]` raises the standard `OSError`/`json.JSONDecodeError`; each caller preserves its current handling. The helper performs no file writes and no schema validation.

## 6. Integration Points

### 6.1 Existing packages/modules this feature depends on (REQ-STATE-03/04, REQ-SEC-01, REQ-COMPAT-01)

This repository has no Python package graph; integrations are executable scripts and canon consumers.

1. **`scripts/forge-session.py`**
   - `next_stage(state: dict) -> str | None`: authoritative production-stage walk.
   - `verify_state(state: dict) -> tuple[str | None, str]`: navigator freshness classifier.
   - `pending_verify(state: dict) -> str | None`: outstanding verify selector.
   - `build_rows(specs_dir: Path, config: dict | None = None) -> list[FeatureRow]`: navigator rows.
   - `_load_config(config_path: Path) -> dict`: shared config consumer replaced internally by duplicate-aware loading.
   - `_resolve_feature_dir(specs_dir: Path, feature: str, epic: str | None) -> Path`: tolerant exit read path.
   - `_resolve_feature_dir_for_write(specs_dir: Path, feature: str, epic: str | None) -> Path`: strict mutation path.
   - `_load_state_for_write(...) -> tuple[Path, dict]`, `_commit_state(state_path: Path, state: dict) -> dict`: targeted atomic state-write path.
   - `cmd_state_complete(...) -> dict`: two-commit completion/provenance writer; gains full-hash input validation only.
   - `cmd_state_verify(...) -> dict`: validates verification transitions, writes feature verify entries through the existing strict writer, and branches explicitly to atomic epic-root `.epic-state.json` writes for `forge-0-epic`.
   - `_host_command(...)`: preserved command translation surface.
   - `_next_steps_block(primary_command: str, host: str, reconcile: dict | None = None, deferred_command: str | None = None) -> str`: extended rendering surface that fences verification while production advancement is deferred.

2. **`scripts/epic-manifest.py`**
   - CLI import path: `scripts/epic-manifest.py render-status <epic> --specs-dir D --json`.
   - Supplies live epic completion/actionable routing; its `KNOWN_VERIFY_STATUSES` copy must remain byte-identical with `forge-session.py`.
   - Reads legacy missing `revision` as `1`, initializes new manifests at `1`, and increments the revision exactly once in every successful atomic mutation path.

3. **State schemas**
   - `references/pipeline-state-schema.json` remains the source of truth for feature `verifyEntry` and receives additive status/fields only.
   - `references/epic-manifest-schema.json` adds required integer `revision >= 1`; compatibility readers supply the documented legacy default before validation.

4. **`scripts/build-adapters.py`**
   - `RUNTIME_HELPERS` copies all six flat helpers — `forge-root.sh`, `forge-init.sh`, `epic-manifest.py`, `forge-session.py`, `validate-traceability.py`, `forge-bootstrap.py` — to every adapter. The set is unchanged by this feature; `forge-session.py` and `forge-bootstrap.py` simply carry the mirrored loader inside their existing copies.
   - Existing Claude/Pi/generic host substitutions remain the build-time translation layer.

5. **Canonical skills and references**
   - `forge-0-epic` creation/edit, `forge-5-loop` result branches, `forge-6-docs`, `forge-verify`, and `forge-fix` import the scripted contract by command invocation and print its output last.
   - Stages 1–4 retain their state-driven routing and host wording, add the capability input, and adopt verify-first primary ordering when verification is unresolved.

### 6.2 Existing consumers that import/call this feature (REQ-EXIT-01/02, REQ-DEBT-05)

- All nine covered direct skills call `forge-session.py stage-exit`.
- Stage authoring and navigator auto-verify paths call branch skills with `--owner nested`.
- Every scripted stage-exit caller passes `--verify-capability interactive` only when both `AskUserQuestion` and clean-room `forge-verifier` dispatch are available; otherwise it passes `manual`.
- `forge-verify` and `forge-fix` call `state-verify` for result transitions; direct calls serialize their mode as `--verify-mode`, while nested calls carry their owning `--served-stage`.
- Navigator/status rendering consumes the new `auto-pending` label.
- `forge-bootstrap.py` and all `forge-session.py` config consumers route through their own mirrored copy of the duplicate-aware read.
- Tests and compliance eval execute the real CLI via subprocess; no production code imports test helpers.

### 6.3 Data flow (REQ-DEBT-01..05, REQ-ROUTE-04/05)

```text
authoring stage commits artifact/state
  -> stage-exit reads config + current state
  -> if auto verify owed: state-verify(auto-verify-pending), atomically
  -> stage-exit returns directives
  -> outer skill dispatches nested forge-verify
  -> forge-verify writes passed/findings through state-verify
  -> commit 1 lands report/state with commitHash null
  -> state-verify(commit_hash) records the full artifact hash in commit 2
  -> findings optionally invoke nested forge-fix
  -> forge-fix writes findings-applied and clears verifiedStageVersion
  -> interruption still reads stale/unresolved
  -> outer caller mandates nested re-verify and only passed records the current artifact revision
  -> outer caller alone prints one terminal NEXT-STEPS block
```

A direct verify/fix begins at the branch skill, passes `--owner direct`, and that branch call owns the one terminal block.

### 6.4 In-progress/conflicting feature analysis (REQ-COMPAT-01/02)

- `context-efficiency` introduced the current stage-exit/state-verb machinery and loop body/reference splits. Its behavior-preservation guards are updated to the intentional new contract; loop body ≤300 lines and ≤5,000 words remains mandatory.
- `epic-orchestration` owns `render-status`, edit mode, member handoff, and docs behavior. This feature reuses its live state derivation instead of duplicating dependency logic.
- `forge-bootstrap` owns config creation and independently reads `forge.config.json`; it must adopt its own mirrored copy of the duplicate-aware parser.
- No other active feature is editing these surfaces. Completed feature specs are compatibility evidence, not alternative sources of truth.

## 7. Error Handling

### 7.1 Usage and routing failures (REQ-ROUTE-03, REQ-REL-02, REQ-SEC-01)

Unsafe names, ambiguous strict resolution, unsupported outcomes, missing direct-branch ownership, absent inference metadata, conflicting `--served-stage`/`--verify-mode`, and invalid epic-state targets raise `UsageError` and exit 2 with an actionable `Error:` line. No NEXT-STEPS block is emitted on an invalid request because a guessed command would violate fail-closed routing.

Existing stages 0–4 continue to degrade unreadable state to their fixed successor. Epic member unreadability uses only the documented `forge-1-prd` fallback with a warning directive (REQ-PROD-06).

### 7.2 Auto-verify interruption (REQ-DEBT-03/04, REQ-REL-03)

Once `auto-verify-pending` is written, dispatch failure, compaction, non-answer, or process interruption leaves it untouched. Navigator/stage exit surfaces the debt and retry command. Only a successful result or explicit skip replaces it through `state-verify`.

### 7.3 State/config writes (REQ-STATE-03/04, REQ-CONFIG-03)

State mutation retains sibling-temp-file + flush/fsync + `os.replace` atomicity. No model authors whole JSON. Duplicate config keys warn to stderr but do not fail parsing; malformed JSON retains each caller's current fallback/error semantics.

### 7.4 Commit provenance (REQ-STATE-01/02/04)

New invalid hashes fail before state mutation. Legacy short hashes remain readable. No amend, force, broad staging, or alternate provenance path is introduced.

## 8. Testing Approach

### 8.1 Routing and output matrix (REQ-EXIT-01..05, REQ-ROUTE-01..06, REQ-PROD-01..06)

Extend `tests/test_stage_exit.py` to cover:

- all nine accepted stage identifiers;
- every per-stage outcome and every invalid stage/outcome combination;
- explicit served stage, every `--verify-mode` mapping, matching dual inputs, conflicting inputs, and missing-metadata fail-closed cases;
- direct verify mode from explicit/auto-detected pipeline mode and direct fix mode parsed from the selected findings report;
- direct ownership emits one sentinel; nested ownership emits none;
- verify → fix → re-verify success and recovery routing, including interruption after `findings-applied` proving freshness remains unresolved;
- loop complete/partial/blocked/needs-human/deferred routing;
- docs standalone/actionable/blocked/complete epic routing;
- epic edit member at every production stage plus unreadable fallback;
- byte-identical repeated requests and sentinel-last invariant;
- Claude, Pi, and generic command/fresh-session forms;
- a combined capable-Pi case proving `verifyGate: standard` when verification is outstanding;
- fallback Pi/generic cases proving `verifyCommand` is fenced, the production successor is deferred, and no advancement occurs without pass/skip;
- explicit-skip persistence before production advancement;
- unchanged stages 0–4 snapshots except the intended epic edit and verify-primary/capability corrections.

### 8.2 State/schema/provenance tests (REQ-DEBT-01..06, REQ-STATE-01..04)

- `tests/test_auto_verify.py`: distinct `auto-pending` classification in `verify_state`, `pending_verify`, navigator rows, status rendering, and stage exit.
- `tests/test_state_verbs.py`: `state-verify` legal/illegal transitions, idempotent same-revision scheduling, atomic failure behavior, feature/epic disambiguation, direct `.epic-state.json` pass/findings/applied/skipped writes, wrong-file non-mutation, result replacement, and `findings-applied` clearing `verifiedStageVersion` until re-verification passes.
- Epic revision tests: creation at 1, legacy missing-field read as 1, first mutation to 2, exactly-once increments, no-op/failure stability, same-revision pending idempotency, manifest edits making verification stale, pending visibility, and pass replacement.
- Verify provenance tests: feature and epic commit-2 success with full hashes, short/non-hex and missing-entry rejection without mutation, mixed-mode rejection, and proof that only `commitHash`/`updatedAt` change with no amend path.
- `tests/test_state_schema_conformance.py`: every writer sequence validates; legacy files without new status load; short legacy hashes load.
- hash tests: 40-hex new writes pass; short/non-hex new writes fail without mutation.
- `tests/test_stage_constants_parity.py`: schema/session/manifest verify vocabularies remain aligned.

### 8.3 Config diagnostics (REQ-CONFIG-01..04)

`tests/test_effective_config.py` and bootstrap-focused tests cover top-level and nested duplicate keys, key names in stderr warnings, valid JSON stdout, last-key-wins values, malformed input compatibility, and no-warning common path.

### 8.4 Canon, adapter, and cap guards (REQ-GUARD-01..03, REQ-COMPAT-01/02)

`tests/test_stage_exit_protocol.py` explicitly enumerates the nine required skills and rejects missing/duplicate terminal contracts. `tests/test_build_adapters.py` confirms no new runtime helper ships and all new stamp sites translate for Claude/Pi/generic; `tests/test_json_loader_parity.py` guards the mirrored loader. Existing adapter-neutrality, spec-purity, drift, and forge-5-loop body-cap tests remain hard gates.

### 8.5 Compliance evaluation (REQ-EVAL-01..03)

Add a separate branch probe to `eval/run-compliance-eval.py`; do not overwrite the linear PRD baseline. Fixtures cover:

1. verify findings → fix applied → re-verify passed → correct production rejoin;
2. re-verify findings/failure → correct recovery command.

Transcript normalization pairs each Bash command request with its command result/exit status. The scorer requires ordered successful execution evidence for the real stage-exit commands, exactly one terminal sentinel across the full path, a verbatim expected block, a fenced next command, and nothing after the sentinel. Negative fixtures include missing result, non-zero result, reordered calls, duplicate sentinel, nested sentinel, and prose-only claims.

`eval/README.md` and historical baseline docs state that the original forge-1-prd result measured only the already-scripted linear path; branch compliance is reported separately.

### 8.6 Verification commands (REQ-COMPAT-03)

```text
python3 scripts/build-adapters.py
bash scripts/validate.sh
ruff check scripts/ eval/
```

`smokeCommand` stays `null`; CHECK-I21 remains not-applicable for this repository.

## 9. Dependencies

### 9.1 External dependencies (REQ-PERF-01, project constraints)

None added. Runtime remains Python 3.10+ standard library. Existing pinned YAML remains generator-only; no `jsonschema`, network client, database, or service is introduced.

### 9.2 Internal dependencies (REQ-COMPAT-01/02, REQ-SEC-01)

- `scripts/forge-session.py`: CLI, routing, state/config integration.
- `scripts/epic-manifest.py`: live epic status and verify vocabulary parity.
- mirrored duplicate-aware parsing in both config-reading scripts (no shared module).
- `references/pipeline-state-schema.json`: additive feature-state contract.
- `references/epic-manifest-schema.json`: canonical integer epic revision contract.
- `scripts/build-adapters.py`: deterministic distribution and host translation.
- Canonical skill/reference files named in §2 and tests named in §8.

No version constraints change. No rauf behavior changes.

## 10. Open Technical Questions

None. Interview decisions are closed:

- extend `forge-session.py` rather than extract exit routing;
- use typed explicit flags and per-stage outcome enums;
- use one unified `state-verify` command with explicit feature-state and epic-state write branches;
- encode direct/nested ownership explicitly;
- derive epic/docs progress from live state;
- preserve tolerant stages 0–4 while new branch paths fail closed;
- share recursive duplicate-aware JSON parsing;
- enforce full hashes only on new writes;
- prove behavior with a layered matrix plus branch compliance eval;
- route partial/deferred loops directly back to the loop, blocked/needs-human via navigator; and
- use the navigator as the standalone docs completion action;
- make outstanding verification the primary terminal action until pass or explicit skip; and
- select the Standard Verify Gate from actual question + clean-room capabilities, including capable Pi sessions, rather than from the host name.
