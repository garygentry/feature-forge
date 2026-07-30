# 02 — Stage Exit Routing

## Requirement Coverage

| REQ ID | Requirement | Section |
|---|---|---|
| REQ-EXIT-01, REQ-EXIT-02 | Accept seven production stages and two direct branch skills | §2, §3 |
| REQ-EXIT-03, REQ-EXIT-04 | Exactly one direct terminal block; outer ownership for nested chains | §3, §6 |
| REQ-EXIT-05 | Preserve Claude, Pi, and generic command/session rendering | §5 |
| REQ-EXIT-06, REQ-EXIT-07 | Verify-first primary routing and capability-aware gates | §4, §5 |
| REQ-ROUTE-01..03 | Explicit/inferred served stage with fail-closed validation | §2, §3 |
| REQ-ROUTE-04..06 | Complete verify/fix outcome termini and production rejoin | §6 |
| REQ-PROD-01, REQ-PROD-02 | Deterministic complete and non-complete loop exits | §7 |
| REQ-PROD-03, REQ-PROD-04 | Scripted, context-aware docs exits | §8 |
| REQ-PROD-05, REQ-PROD-06 | Epic edit routes from live member state with safe fallback | §9 |
| REQ-REL-01, REQ-REL-02 | Deterministic output and fail-closed new routing inputs | §3–§10 |
| REQ-COMPAT-01, REQ-COMPAT-02 | Preserve stages 0–4, host, nested, standalone, and epic behavior | §3–§9 |
| REQ-PERF-01, REQ-PERF-02 | Bounded local state/config/manifest reads only | §8–§10 |
| REQ-OBS-01, REQ-OBS-02 | Expose routing/outcome decisions and actionable failures | §3, §6, §10 |
| REQ-SEC-01 | Retain strict identity containment and epic disambiguation | §3, §9, §10 |
| REQ-A11Y-01 | Explicit, labeled interactive verification choices | §5 |

## 1. Purpose and Scope

This document specifies the domain routing implemented by the nine-stage `stage-exit`
CLI in `scripts/forge-session.py`: request validation, branch ownership, verification
priority, host rendering, branch rejoin, loop outcomes, docs live-state routing, and epic
edit-mode member routing. Shared literals, `TypedDict` payloads, constants, and
`UsageError` are owned by `00-core-definitions.md` and MUST be imported/referenced rather
than redefined here. File placement and delivery order are owned by
`01-architecture-layout.md` (REQ-EXIT-01..07, tech-spec §§3.1–3.6).

This concern does not specify verification-state mutation internals, duplicate-key JSON
loading, schema evolution, compliance scoring, or adapter generation. It consumes those
contracts only where routing depends on them (REQ-COMPAT-02).

## 2. Real Integration Surface and Target API

### 2.1 Baseline found in source

The current implementation was inspected at executable module path
`scripts/forge-session.py`. Because the filename contains a hyphen, production consumers
do not use a Python package import; they execute
`python3 <bundle-root>/scripts/forge-session.py stage-exit ...`. The exact current callable
signature is:

```python
from pathlib import Path


def stage_exit(
    feature: str,
    stage: str,
    specs_dir: Path,
    config_path: Path,
    epic: str | None,
    host: str,
    next_feature: str | None,
) -> dict:
    ...
```

The exact current helper signatures found in the same file are:

```python
from pathlib import Path


def next_stage(state: dict) -> str | None:
    ...


def _verify_state_for(state: dict, stage: str) -> str:
    ...


def _resolve_feature_dir(
    specs_dir: Path, feature: str, epic: str | None
) -> Path:
    ...


def _resolve_feature_dir_for_write(
    specs_dir: Path, feature: str, epic: str | None
) -> Path:
    ...


def _host_command(command: str, host: str) -> str:
    ...


def _next_steps_block(
    next_command: str, host: str, reconcile: dict | None = None
) -> str:
    ...
```

The argparse registration currently exposes only stages 0–4 and does not expose
`--served-stage`, `--verify-mode`, `--outcome`, `--owner`, or
`--verify-capability` (REQ-EXIT-01/02, REQ-ROUTE-01, tech-spec §5.1).

> **WARNING: Could not locate the expanded nine-stage `stage_exit` export or its new
> typed CLI flags in `scripts/forge-session.py` — the implementation currently has the
> seven-argument stages-0–4 baseline and must be extended before canonical callers are
> converted.**

The current canonical `references/stage-exit-protocol.md` likewise says the loop keeps
bespoke exits and docs is terminal. Those statements are baseline behavior to replace,
not the target contract (REQ-PROD-01/03).

### 2.2 Required callable and CLI

Implement the exact target `stage_exit(...)` signature already defined, documented, and
typed in `00-core-definitions.md` §3. Do not duplicate its shared request/result types in
this document. The CLI entry remains `scripts/forge-session.py` and MUST serialize all
parameters as follows (REQ-EXIT-01/02, REQ-ROUTE-01/02):

```text
python3 <bundle-root>/scripts/forge-session.py stage-exit \
  --feature FEATURE \
  --stage {forge-0-epic,forge-1-prd,forge-2-tech,forge-3-specs,forge-4-backlog,forge-5-loop,forge-6-docs,forge-verify,forge-fix} \
  [--served-stage {forge-0-epic,forge-1-prd,forge-2-tech,forge-3-specs,forge-4-backlog,forge-5-loop,forge-6-docs}] \
  [--verify-mode {epic,prd,tech,specs,backlog,impl}] \
  [--outcome OUTCOME] [--owner {direct,nested}] \
  [--verify-capability {interactive,manual}] \
  [--next-feature FEATURE] [--epic EPIC] \
  [--specs-dir DIR] [--config PATH] \
  [--host {claude,pi,generic}] [--json]
```

Argparse choices MUST use `EXIT_STAGES` and the shared literal domains from
`00-core-definitions.md` §2. Stage-specific outcome validation occurs inside
`stage_exit`, because argparse cannot express a different outcome enum per stage.
Successful `--json` prints the `StageExitPayload`; successful human mode prints the
DIRECTIVES representation followed by the script-produced NEXT-STEPS block according to
the canonical protocol. Invalid input prints `Error: <actionable message>` to stderr and
returns exit 2 without a sentinel (REQ-REL-02).

## 3. Request Validation and Ownership

### 3.1 Deterministic validation sequence

`stage_exit` MUST validate in this order so the same invalid request always reports the
same first error (REQ-REL-01/02, REQ-SEC-01):

1. Validate `feature`, `epic`, and `next_feature` with the existing safe-name and
   contained-path rules before strict filesystem access.
2. Require `stage in EXIT_STAGES`.
3. For stages 0–4, reject a supplied `outcome`; preserve their state-driven behavior.
4. For loop, docs, verify, and fix, require `outcome` and require membership in
   `EXIT_OUTCOMES[stage]` from `00-core-definitions.md` §2.
5. Reject `owner` for stages 0–6; require `direct` or `nested` for verify/fix.
6. Validate `host` independently from `verify_capability`. A host never implies a
   capability.
7. For branch stages, resolve and validate the served production stage as in §3.2.
8. Reject branch-only `served_stage`/`verify_mode` on production-stage exits and reject
   `next_feature` except on `forge-0-epic`.

Stages 0–4 retain the tolerant `_resolve_feature_dir(...)` read policy after syntactic
validation. Loop, docs, branches, and explicit epic-member routing use strict resolution
or validated adjacent-script data; they MUST NOT silently select a same-named feature
from another epic (REQ-COMPAT-01, REQ-SEC-01).

### 3.2 Served-stage resolution

For direct or nested `forge-verify`/`forge-fix`, compute the served stage with the
`VERIFY_MODE_TO_STAGE` mapping from `00-core-definitions.md` §2 (REQ-ROUTE-01..03):

```python
def resolve_served_stage(
    served_stage: str | None,
    verify_mode: str | None,
) -> str:
    """Resolve one unambiguous production stage for a branch exit.

    Args:
        served_stage: Explicit production stage supplied by the branch caller.
        verify_mode: Optional authoritative mode mapped by VERIFY_MODE_TO_STAGE.

    Returns:
        A member of the shared ProductionStage domain.

    Raises:
        UsageError: The explicit stage is invalid, mode is invalid, both inputs
            disagree, or neither input identifies a stage.
    """
    ...
```

This helper is private to `scripts/forge-session.py`; it uses shared definitions and does
not create a second public API. If both inputs are supplied, they MUST map to the same
stage. If only `served_stage` is supplied, accept any shared `ProductionStage`, including
`forge-6-docs`. If only `verify_mode` is supplied, use the unique mapping. If neither is
supplied, raise:

```text
Error: forge-verify requires --served-stage or an unambiguous --verify-mode; rerun with the production stage this verification served
```

Direct `forge-verify` callers may derive `verify_mode` from authoritative pipeline state
before invoking `stage-exit`. Direct `forge-fix` callers may derive it only from the
selected findings file/header. Conversational prose and `currentStage` are not valid
inference sources (REQ-ROUTE-02/03, REQ-SEC-01).

### 3.3 Terminal ownership

- Production stages 0–6 are outer terminal owners.
- Branch `owner == "direct"` sets `terminalOwnedBy: "self"` and emits exactly one
  sentinel-terminated block.
- Branch `owner == "nested"` sets `terminalOwnedBy: "outer"`, preserves machine-readable
  routing/outcome directives, and returns `nextSteps: None`, `sentinel: None`.
- A nested verify → fix → re-verify chain MUST never call the human terminal printer.
  The authoring-stage caller evaluates the final nested result and alone prints its
  terminal block (REQ-EXIT-03/04).

## 4. Verify-First Primary Routing

Verification freshness is evaluated before production successor rendering. Consume the
shared `VerifyStateLabel`, `VerifyGate`, and `StageExitDirectives` contracts from
`00-core-definitions.md` §§2, 4, and 6 (REQ-EXIT-06/07).

For any authoring-stage exit with verification capability:

| State/config | Primary action | Deferred action | Gate |
|---|---|---|---|
| `fresh` or `skipped` | production successor | none | `none` |
| auto-verify effective and outstanding | nested verify/fix chain | production successor until chain passes/skips | `none`; `runInStageVerify: true` |
| outstanding + `interactive` | interactive verification choice | production successor until pass/explicit skip | `standard` |
| outstanding + `manual` | `verifyCommand` | production successor | `manual-print` |

`primaryCommand` is the sole fenced command. While verification is outstanding,
`deferredCommand` may be rendered only as unfenced conditional prose: “After verification
passes, continue with …”. Fresh-session guidance follows the primary verification action;
it MUST NOT tell the user to clear and run the production successor first. `nextCommand`
remains compatibility/routing metadata but MUST NOT override `primaryCommand`
(REQ-EXIT-06, REQ-COMPAT-01).

If nested auto-verification fails to dispatch, returns a non-answer, produces unresolved
findings, or is interrupted, the outer caller MUST recompute/retain verify-first output;
it MUST NOT print an advancing production command as primary (REQ-REL-02, tech-spec
§3.3). Durable debt recording is specified outside this concern; this router consumes
its distinct `auto-pending` label and treats it as outstanding.

## 5. Capability Gate and Host Rendering

### 5.1 Capability-aware Standard Verify Gate

The canonical skill caller passes `verify_capability == "interactive"` only when its
actual tool surface has both (a) a question mechanism and (b) dispatchable clean-room
`forge-verifier`. Otherwise it passes `manual`. `stage_exit` MUST NOT inspect `host` to
infer either capability (REQ-EXIT-07).

For `verifyGate == "standard"`, `references/stage-exit-protocol.md` MUST present three
explicitly labeled choices with descriptions and the recommended default (REQ-A11Y-01):

1. **Verify now** (recommended).
2. **Verify now + enable auto-verify going forward**.
3. **Skip for now**.

Advancement is allowed only after a passing result or after choice 3 has been persisted as
an explicit skip. Choosing to stop or losing the interaction produces no advancing
terminal block. Capable Pi therefore receives the same logical gate as capable Claude;
incapable Claude, Pi, or generic callers receive manual verify-first output
(REQ-EXIT-07).

### 5.2 Rendering contract

Extend the exact baseline helper at `scripts/forge-session.py::_next_steps_block` to the
target signature specified in `00-core-definitions.md` §5. `_host_command` remains the
sole runtime command translator (REQ-EXIT-05, tech-spec §3.10):

| Host | Fresh-session wording | Command surface |
|---|---|---|
| `claude` | `/clear`; user must run it | `/feature-forge:<skill>` |
| `pi` | `/new`; user must run it | `/skill:<skill>` |
| `generic` | host-neutral “clear/start a fresh session” | canonical host-neutral forge skill wording |

The renderer MUST:

1. start with `**Next steps**`;
2. include deterministic `outcome_text` when supplied;
3. fence exactly `primary_command` after `_host_command` translation;
4. render an optional deferred command only inline/unfenced and conditionally;
5. preserve existing blocking/non-blocking `epicReconcile` precedence without allowing a
   production reconcile action to bypass unresolved verification;
6. append `NEXT_STEPS_SENTINEL` as the final line, with no trailing content.

When verification and blocking epic reconciliation coexist, verification remains primary;
reconciliation becomes the first deferred production action, and the ordinary production
successor remains subordinate to reconciliation (REQ-EXIT-06, REQ-COMPAT-01).

## 6. Direct Verify/Fix Rejoin Routing

Branch commands carry the resolved served stage through every emitted command. Commands
shown below are canonical before `_host_command` translation (REQ-ROUTE-01/04..06).

### 6.1 `forge-verify`

| Outcome | Primary route | Error/recovery behavior |
|---|---|---|
| `passed` | Live successor after served stage | If successor resolution fails on a strict path, exit 2; do not guess |
| `findings` | `/feature-forge:forge-fix FEATURE --served-stage SERVED` | Findings metadata must already be durably recorded |
| `skipped` | Live successor after served stage | Valid only after explicit skip persistence |
| `failed` | `/feature-forge:forge-verify FEATURE --served-stage SERVED` | Include actionable user-intervention/retry text; never advance |

### 6.2 `forge-fix`

| Outcome | Primary route | Required meaning |
|---|---|---|
| `no-findings` | re-verify if verification remains owed; otherwise live successor | No silent assumption that absence of applicable findings equals a pass |
| `decisions` | `/feature-forge:forge-fix FEATURE --served-stage SERVED` | Name unresolved decision work and stop advancement |
| `failed` | `/feature-forge:forge-fix FEATURE --served-stage SERVED` or navigator recovery | Name failure/recovery action and stop advancement |
| `applied` | `/feature-forge:forge-verify FEATURE --served-stage SERVED` | Re-verification is mandatory |
| `reverified` | live successor after served stage | Allowed only after passed state is recorded |
| `reverify-findings` | `/feature-forge:forge-fix FEATURE --served-stage SERVED` | Continue recovery; never advance |
| `deferred` | deterministic fix/navigator resume command | Explicitly state that findings remain unresolved |

“Live successor” uses current production position, not conversational stage assumptions.
For stages 0–5, it is the first applicable production action after the served artifact;
completed stage 6 routes to its context-appropriate completion action rather than a
nonexistent stage 7. Every direct outcome sets `servedStage`, `outcome`, `nextStage`,
`primaryCommand`, and `terminalOwnedBy` in directives so tests and downstream tools can
distinguish rejoin, recovery, and defer outcomes (REQ-OBS-01).

## 7. Loop Outcome Routing

`forge-5-loop` MUST invoke the scripted contract after persisting its result, passing one
shared `LoopOutcome` value (REQ-PROD-01/02):

| Outcome | Primary route | Constraint |
|---|---|---|
| `complete` | Verify-first impl routing, then live docs/epic-member handoff | Docs is never primary until verification passes or is explicitly skipped |
| `partial` | `/feature-forge:forge-5-loop FEATURE` | State remains resumable; no docs readiness claim |
| `deferred` | `/feature-forge:forge-5-loop FEATURE` | Explain explicit deferral; no docs readiness claim |
| `blocked` | `/feature-forge:forge FEATURE` | Navigator is the deterministic diagnostic/recovery action |
| `needs-human` | `/feature-forge:forge FEATURE` | Name the human decision/recovery need; no docs readiness claim |

Every row is rendered by `_next_steps_block(..., outcome_text=...)`; result-reporting prose
MUST NOT append a bespoke exit or content after the sentinel. Invalid/missing outcomes
raise `UsageError` before output (REQ-EXIT-03, REQ-REL-02).

## 8. Docs Live-State Routing

`forge-6-docs` requires `complete` or `blocked` and always uses `stage-exit`
(REQ-PROD-03/04).

For an epic member, consume the adjacent executable integration:

```text
python3 <bundle-root>/scripts/epic-manifest.py render-status EPIC \
  --specs-dir SPECS_DIR --json
```

The exact callable found in `scripts/epic-manifest.py` is:

```python
from pathlib import Path


def render_status(epic_dir: Path, specs_dir: Path) -> RenderStatus:
    ...
```

The router consumes the command result's live `nextCommand`, actionable/blocked state,
and rollup; it MUST NOT duplicate dependency or completion derivation in
`forge-session.py` (tech-spec §3.5):

- actionable next member → that member's live command;
- no actionable member because remaining work is blocked → epic dashboard
  `/feature-forge:forge-0-epic EPIC`;
- all members complete → epic dashboard completion view using the same epic command;
- `blocked` docs outcome → navigator/epic dashboard recovery, never completion.

Standalone `complete` fences `/feature-forge:forge FEATURE` as the existing navigator
completion action and may mention starting a new feature only as secondary text.
Standalone `blocked` also routes to the navigator with recovery wording. Manifest command
nonzero, malformed JSON, missing required fields, timeout, or invalid graph is an
actionable exit-2 routing failure; no guessed member command or sentinel is emitted
(REQ-REL-02, REQ-OBS-02). The local subprocess reads only the bounded manifest/member
state set and performs no network/history scan (REQ-PERF-01).

## 9. Epic Edit-Mode Live Member Routing

For `forge-0-epic --next-feature MEMBER`, resolve exactly that member under the selected
epic, load its `.pipeline-state.json`, and call the existing exact integration
`scripts/forge-session.py::next_stage(state: dict) -> str | None` (REQ-PROD-05,
REQ-SEC-01).

- If state resolves, route to the returned first incomplete production stage. A progressed
  member therefore resumes at tech/specs/backlog/loop/docs instead of being sent back to
  PRD.
- If all production stages are complete, route to the epic dashboard rather than
  fabricating another member stage.
- If state is absent, unreadable, malformed, ambiguous, escapes containment, or cannot be
  associated with the selected epic, emit a named warning directive and fall back only to
  `/feature-forge:forge-1-prd MEMBER`. Do not crash stage closure and do not infer later
  progress (REQ-PROD-06).
- Creation mode remains unchanged: a newly created member with no progress routes to PRD.

Explicit unsafe member names remain `UsageError`; the tolerant PRD fallback applies to
unreadable/unresolvable progress after identity containment, not to path traversal
(REQ-REL-02, REQ-SEC-01).

## 10. Error Handling and Determinism

All errors use `UsageError` from `00-core-definitions.md` §7 and the existing main CLI
handler (REQ-REL-01/02):

| Operation | Failure | Required result |
|---|---|---|
| Stage/outcome validation | unsupported or missing value | exit 2, name stage and allowed outcomes, no payload/sentinel |
| Branch ownership | owner absent/invalid | exit 2, instruct `--owner direct` or `nested` |
| Served-stage inference | absent, invalid, or conflicting metadata | exit 2, name both supplied values and recovery flag |
| Capability/host validation | unknown value | exit 2; never downgrade unknown capability silently |
| Strict feature/epic resolution | unsafe, missing, ambiguous, wrong epic | exit 2 without filesystem mutation or guessed route |
| Established stage 0–4 state read | missing/corrupt | preserve fixed-successor compatibility, except named epic-member fallback in §9 |
| Epic docs status | command/JSON/graph failure | exit 2 with epic and recovery command; no guessed member |
| Terminal rendering | no primary route available | exit 2 rather than emit an empty fence |
| Nested branch routing | successful nested result | structured payload with no block/sentinel; not an error |

Given byte-identical state, config, host, capability, served stage, and outcome, routing
and rendering MUST be byte-identical. Do not include timestamps, unordered set iteration,
network results, repository history, or model-generated prose. Sort any diagnostic lists
before rendering. Human errors name feature, stage/outcome, and the action required; they
must not dump complete state files (REQ-REL-01, REQ-OBS-02, REQ-PERF-01/02).

### Example: direct findings route

```bash
python3 "$R/scripts/forge-session.py" stage-exit \
  --feature payments --stage forge-verify \
  --served-stage forge-2-tech --verify-mode tech \
  --outcome findings --owner direct \
  --verify-capability interactive --host pi --json
```

The successful payload has `terminalOwnedBy: "self"`, `servedStage:
"forge-2-tech"`, and a Pi-translated primary fix command. Its `nextSteps` contains one
sentinel as its final line. Changing `--verify-mode` to `prd` conflicts with the explicit
served stage and exits 2 without a NEXT-STEPS block (REQ-ROUTE-01..04,
REQ-EXIT-03/05).

## Public API and Internal Surface

- **User-facing CLI:** `python3 scripts/forge-session.py stage-exit --feature F --stage S ...` —
  **§2.2 is the authoritative flag contract, including every enum domain**; this bullet
  deliberately does not restate the flags, so the summary cannot drift from the contract the
  way a partial copy does. This is the surface skills invoke and the only one this document
  exposes to users; its stdout (the sentinel-terminated NEXT-STEPS block) and its `--json`
  payload are both contracts. Note in particular that `--host` is `{claude,pi,generic}`: Pi is
  a first-class host, and a capable Pi session is `interactive`, never `manual`
  (REQ-EXIT-05/07, §5.1–§5.2).
- **Repository-internal, importable:** `stage_exit(...)` (§2.2, the callable behind the CLI),
  `resolve_served_stage(...)` (§3.2), and `next_stage(state)` (§2.1). Tests import these
  directly; the shapes they return are `00-core-definitions.md` §4.
- **Private helpers:** `_verify_state_for`, `_host_command`, `_next_steps_block`,
  `_resolve_feature_dir`, and `_resolve_feature_dir_for_write`. `_next_steps_block` in
  particular is private *and* load-bearing — it is the single renderer that guarantees
  sentinel-last output (REQ-EXIT-03), so the coverage guard in `06-compliance-and-coverage.md`
  asserts against its rendered output rather than calling it.
- **Consumed, not owned:** `render_status(epic_dir, specs_dir)` belongs to
  `scripts/epic-manifest.py`; the epic route (§9) reads it and must not reimplement it.
  `cmd_state_verify` belongs to `03-verification-state.md`; §4's scheduling boundary calls it.
- **Test/eval-only:** none.

## Dependencies

Implement these specifications first:

- `00-core-definitions.md` — shared stage/outcome/capability/owner literals,
  `StageExitPayload`, `StageExitDirectives`, sentinel, mappings, and `UsageError`.
- `01-architecture-layout.md` — file ownership, runtime executable paths, canonical
  caller locations, and implementation sequence.

Runtime dependencies:

- `scripts/forge-session.py` — exact baseline integrations quoted in §§2, 5, and 9.
- `scripts/epic-manifest.py` — exact `render_status` callable and `render-status` CLI in
  §8.
- `references/stage-exit-protocol.md` — canonical outer/nested directive execution and
  terminal-print behavior; update its baseline five-stage/bespoke-loop statements when
  implementing this spec.

No external package or network dependency is added.

## Verification

- [ ] The CLI accepts exactly seven production and two branch stage identifiers.
- [ ] Every loop/docs/verify/fix outcome accepts only its shared stage-specific enum;
  stages 0–4 reject outcomes.
- [ ] Explicit and inferred served stages agree; missing/conflicting metadata exits 2
  with no sentinel.
- [ ] Every direct path emits one block ending at the sole sentinel; every nested branch
  emits no block and no sentinel.
- [ ] Verify outstanding on manual capability fences verify and renders production only
  as post-pass guidance.
- [ ] Capable Pi and Claude both select `standard`; incapable hosts select
  `manual-print`, independently of host name.
- [ ] Claude uses `/clear`, Pi uses `/new` and `/skill:`, and generic output remains
  host-neutral.
- [ ] Every verify/fix outcome reaches the route in §6, including recovery and deferral.
- [ ] Loop partial/deferred resume loop; blocked/needs-human use navigator; none imply
  docs readiness.
- [ ] Docs standalone and epic-member cases use the routes in §8, including malformed
  live-status failure.
- [ ] Epic edit members at each production position route via `next_stage`; unreadable
  state emits the named PRD fallback warning.
- [ ] Repeated identical fixtures produce byte-identical directives and NEXT-STEPS.
- [ ] Implementation tests execute the real CLI for Claude, Pi, and generic hosts and
  assert stderr, exit code, fenced primary command, and sentinel-last invariants.
