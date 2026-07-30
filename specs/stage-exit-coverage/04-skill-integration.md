# 04 — Canonical Skill Integration

## Requirement Coverage

| REQ ID | Requirement | Section |
|---|---|---|
| REQ-EXIT-01..07 | All nine skills use one capability-aware, sentinel-safe exit contract | §2–§4, §9 |
| REQ-ROUTE-01..06 | Direct/nested verify and fix ownership, inference, and complete outcome routing | §5 |
| REQ-PROD-01..06 | Loop, docs, and live epic-member handoffs | §6–§8 |
| REQ-FOLLOW-02 | Immediate sanctioned PRD/tech parking-lot persistence | §4.2 |
| REQ-CAP-01 | Preserve the completed loop runner-contract split and body caps | §6.3 |
| REQ-REL-01/02 | Deterministic outcome selection and fail-closed skill inputs | §3–§9 |
| REQ-COMPAT-01/02 | Preserve stages 0–4, epic/standalone, nested, and host workflows | §2–§9 |
| REQ-OBS-01/02 | Skills carry explicit routing/outcome metadata and surface actionable errors | §3–§9 |
| REQ-SEC-01 | Feature/epic identity remains resolver-owned and epic state remains scoped | §4–§8 |
| REQ-A11Y-01 | Capability-gated interactive choices retain labels and descriptions | §3.2, §5 |
| REQ-GUARD-01..03 | Canon exposes an explicit, mechanically checkable nine-skill surface | §2, §10 |

## 1. Purpose and Scope

This document specifies the canonical prose integration between the flat Python control
plane and these skill sources:

- `skills/forge-0-epic/SKILL.md` and `skills/forge-0-epic/references/edit-mode.md`;
- `skills/forge-1-prd/SKILL.md` through `skills/forge-6-docs/SKILL.md`;
- `skills/forge-5-loop/references/result-reporting.md`;
- `skills/forge-verify/SKILL.md` and `skills/forge-fix/SKILL.md`; and
- `references/stage-exit-protocol.md`.

Shared literals, payloads, `UsageError`, and target Python signatures are defined in
`00-core-definitions.md`; they are not redefined here. File ownership and adapter-copy
rules come from `01-architecture-layout.md`. This integration adds no Python package or
barrel export: skills execute `scripts/forge-session.py` through the existing portable
`forge-root.sh` prelude (REQ-EXIT-01/02, REQ-COMPAT-02).

## 2. Integration Map and Current Source Baseline

### 2.1 Direction of dependency (REQ-EXIT-01..05, REQ-GUARD-01/02)

```text
canonical skill body/reference
  -> portable forge-root.sh discovery
  -> scripts/forge-session.py stage-exit (typed serialized request)
  -> StageExitPayload from 00-core-definitions.md
  -> skill executes interactive/nested directives
  -> skill prints payload.nextSteps verbatim and stops output

forge-0-epic / forge-6-docs
  -> scripts/epic-manifest.py render-status ... --json
  -> live next member/dashboard data
  -> stage-exit request
```

The exact covered allow-list is the seven production skills `forge-0-epic` through
`forge-6-docs` plus direct `forge-verify` and `forge-fix`. Navigator, init, bootstrap,
guide, setup, and advisory skills are intentionally not terminal owners. The canonical
guard must therefore inspect exactly those nine skill sources, while accepting the
loop's call in `references/result-reporting.md` as a call owned by
`skills/forge-5-loop/SKILL.md` (REQ-GUARD-01..03).

### 2.2 Exact existing Python integration signatures (tech-spec §6.1)

The following signatures were read from `scripts/forge-session.py`:

```python
def _host_command(command: str, host: str) -> str: ...


def _next_steps_block(
    next_command: str, host: str, reconcile: dict | None = None
) -> str: ...


def stage_exit(
    feature: str,
    stage: str,
    specs_dir: Path,
    config_path: Path,
    epic: str | None,
    host: str,
    next_feature: str | None,
) -> dict: ...


def cmd_state_note(
    feature: str, note: str, specs_dir: Path, epic: str | None
) -> dict: ...
```

The implementation must evolve `stage_exit` and `_next_steps_block` to the exact target
signatures in `00-core-definitions.md` rather than creating a second skill-facing API.
`_print_stage_exit(payload: dict) -> None`, also in `scripts/forge-session.py`, remains
the non-JSON direct-print bridge, but must tolerate a nested payload with
`nextSteps is None` without printing a terminal section.

The live epic integration was read from `scripts/epic-manifest.py`:

```python
class RenderStatus(TypedDict):
    """Live epic status. Total — every key is always present, so an empty list is
    an answer ("none") and never a missing field."""

    # Epic name; equals the epic directory name under specsDir.
    epic: str
    # Epic-level lifecycle state, distinct from any member's stage progress. A
    # "complete" epic can still contain members with outstanding verification.
    status: Literal["active", "paused", "abandoned", "complete"]
    # Per-member status in manifest order — the authoritative member progress the
    # edit-mode exit routes on, instead of assuming forge-1-prd (REQ-PROD-05/06).
    features: list[FeatureStatus]
    # Member names that can be worked right now (dependencies satisfied). Empty
    # means nothing is actionable, not that the check was skipped.
    actionable: list[str]
    # Subset of `actionable` that may additionally run concurrently — members with
    # no dependency on each other. Always a subset; never contains a name absent
    # from `actionable`.
    parallelEligible: list[str]
    # Aggregate counts across members. Read-only here; owned by epic-manifest.py.
    rollup: Rollup
    # Host-rendered command for the epic's single best next action, or None when
    # nothing is actionable. Already host-translated — print verbatim.
    nextCommand: str | None
    # Non-fatal advisories (drift, latent name collisions, legacy manifests).
    # Empty list means checked and clean.
    warnings: list[str]


def render_status(epic_dir: Path, specs_dir: Path) -> RenderStatus: ...
```

Its executable import path is exactly:

```text
python3 "$R/scripts/epic-manifest.py" render-status "{epic}" \
  --specs-dir "{specsDir}" --json
```

WARNING: The enhanced `stage_exit` parameters `served_stage`, `verify_mode`, `outcome`,
`owner`, and `verify_capability` are not present in the current
`scripts/forge-session.py` callable/CLI — implement the target signature from
`00-core-definitions.md` before converting these skill call sites.

WARNING: No `cmd_state_verify` export exists in the current `scripts/forge-session.py`;
`forge-verify` and `forge-fix` currently hand-author verify state. Implement the exact
writer from `00-core-definitions.md` before adopting the branch flows in §5.

WARNING: Current `skills/forge-5-loop`, `skills/forge-6-docs`, `skills/forge-verify`, and
`skills/forge-fix` have no scripted `stage-exit` call site; their required calls are new,
not aliases for an existing export.

## 3. Shared Skill-Side Protocol

### 3.1 One canonical stamp and typed flags (REQ-EXIT-01..06, REQ-REL-01/02)

Replace the five-stage wording and legacy standard/warm variants in
`references/stage-exit-protocol.md` with one stamp usable by all nine direct exits. Each
stamp retains the existing portable root prelude and invokes:

```bash
python3 "$R/scripts/forge-session.py" stage-exit \
  --feature "{feature-or-epic}" --stage "{ExitStage}" \
  --specs-dir "{specsDir}" --host "{claude|pi|generic}" \
  --verify-capability "{interactive|manual}" \
  {stage-specific-typed-flags}
```

The caller passes only applicable flags:

| Caller | Required stage-specific flags |
|---|---|
| `forge-0-epic` | `--next-feature "{member}"` when a concrete member exists |
| `forge-1-prd`..`forge-4-backlog` | none beyond identity/capability; retain `--epic` for members |
| `forge-5-loop` | `--outcome complete|partial|blocked|needs-human|deferred`; retain `--epic` for members |
| `forge-6-docs` | `--outcome complete|blocked`; retain `--epic` for members |
| direct `forge-verify` | `--owner direct --outcome passed|findings|skipped|failed` and served-stage metadata |
| nested `forge-verify` | `--owner nested` plus outcome and served-stage metadata |
| direct/nested `forge-fix` | matching owner, a `FixOutcome`, and served-stage metadata |

A production stage is an outer terminal owner. Branch ownership is never inferred from
whether a user or another skill happened to phrase the invocation: the invoking path
carries `--owner direct|nested`. An invalid/missing enum or a conflicting served-stage
mapping is surfaced as the script's `Error:` line and the skill stops without inventing
next steps (REQ-EXIT-04, REQ-ROUTE-03, REQ-REL-02).

### 3.2 Host and capability determination (REQ-EXIT-05..07, REQ-A11Y-01)

Before the call, each outer/direct skill independently computes two inputs:

1. `--host` describes only the active adapter command surface: Claude, Pi, or generic.
2. `--verify-capability interactive` is passed only if **both** (a) a question tool
   equivalent to `AskUserQuestion` is available and (b) `forge-verifier` can be
   dispatched clean-room. If either is absent or capability cannot be proven, pass
   `manual`.

Do not use `host == claude` as a capability proxy. In particular, capable Pi is
`--host pi --verify-capability interactive`; Pi without the dispatchable verifier is
`manual`. Interactive gate options retain explicit labels, recommended defaults, and
one-line trade-off descriptions from `references/stage-exit-protocol.md`. The manual
path prints the verify command as the sole fenced primary action and mentions production
advancement only as unfenced post-pass guidance (REQ-EXIT-06/07, REQ-A11Y-01).

If clean-room dispatch advertised as available later returns
`CLEAN_ROOM_UNAVAILABLE` or a non-answer, treat verification as failed/not run, leave its
debt unresolved, and obtain a fresh stage-exit payload using manual capability. Never
reuse an earlier payload that promotes production advancement (REQ-REL-02).

### 3.3 Directive order, output ownership, and sentinel-last (REQ-EXIT-03/04/06)

Skills consume the `StageExitPayload` from `00-core-definitions.md` in this order:

1. Surface `invalidAutoVerifyKeys` and `warning` before terminal output.
2. If `runInStageVerify`, execute the nested verify/fix/re-verify chain synchronously.
3. Handle `verifyGate == standard`; a pass/finding/explicit skip must be persisted and
   routing recomputed before printing a block. A stop choice emits no advancing block.
4. For `manual-print`, do not dispatch inline; use the script's verify-first block.
5. Print `nextSteps` byte-for-byte only for `terminalOwnedBy == self`.

A direct payload must contain one occurrence of `─ forge: end of stage ─`, as its final
line. The skill emits no summary, sign-off, warning, command result, or acceptance text
after it. A nested payload has `nextSteps is None` and `sentinel is None`; nested
`forge-verify`/`forge-fix` return their structured result to the outer caller and print
no terminal block. The outer caller reruns `stage-exit` after nested state transitions so
its sole final block reflects the terminal result (REQ-EXIT-03/04, REQ-OBS-01).

## 4. Authoring Stages 1–4 and Parking-Lot Notes

### 4.1 Existing stage call sites (REQ-EXIT-01/03/05, REQ-COMPAT-01)

Retain the existing call locations and fixed stage identities in:

```text
skills/forge-1-prd/SKILL.md      -> --stage forge-1-prd
skills/forge-2-tech/SKILL.md     -> --stage forge-2-tech
skills/forge-3-specs/SKILL.md    -> --stage forge-3-specs
skills/forge-4-backlog/SKILL.md  -> --stage forge-4-backlog
```

Add `--verify-capability` determined by §3.2 and add `--epic "{epic}"` for a member.
Do not change their artifact/state-complete ordering. Their existing host translations,
fresh-session wording, auto-verify directives, and epic-reconcile behavior remain
script-owned, except unresolved verification now owns the primary command as required by
REQ-EXIT-06/07.

### 4.2 Immediate PRD/tech `state-note` path (REQ-FOLLOW-02, REQ-STATE-03, REQ-SEC-01)

In `skills/forge-1-prd/SKILL.md` and `skills/forge-2-tech/SKILL.md`, replace the parking-
lot promise to “note it” with an immediate call at the time the concern is raised:

```bash
python3 "$R/scripts/forge-session.py" state-note \
  --feature "{feature}" --note "<concise downstream concern>" \
  --specs-dir "{specsDir}"
```

For an epic member, append `--epic "{epic}"`; omission is an error and must not fall
back to a same-named flat feature. This uses the existing exact
`cmd_state_note(feature, note, specs_dir, epic) -> dict` integration and its strict,
atomic writer. It overwrites the single `notes` string, so when preserving an earlier
note the skill reads it and supplies a combined concise string; the model never edits or
round-trips JSON. This immediate interview-time call is separate from the optional
completion note and must not be deferred until stage closure (REQ-FOLLOW-02,
REQ-STATE-03).

On `UsageError`/exit 2, surface the named feature/epic and recovery instruction, then
stop claiming the concern was persisted. Epic decomposition changes continue through
`epicChangeRequests`, not `notes` (REQ-OBS-02, REQ-SEC-01).

## 5. Verify and Fix Branch Skills

### 5.1 Served-stage and owner capture (REQ-EXIT-02/04, REQ-ROUTE-01..03)

`skills/forge-verify/SKILL.md` serializes its explicit or auto-detected mode as
`--verify-mode`. The unique mapping from `00-core-definitions.md` determines the served
stage. When the caller already owns a stage, it additionally passes matching
`--served-stage`; disagreement fails closed. Ambiguous mode selection still uses
`AskUserQuestion` before any write. Epic mode remains rooted at
`{specsDir}/{epic}/.epic-state.json` (REQ-SEC-01).

`skills/forge-fix/SKILL.md` reads the selected findings report's mode/header and derives
that same served-stage mapping before mutation. It never uses conversational context,
`currentStage`, or the newest arbitrary feature stage. Missing, malformed, or ambiguous
metadata yields direct `no-findings` only when no applicable report exists; a report
whose served stage cannot be established is a fail-closed error with instructions to
select/re-run verification (REQ-ROUTE-02/03).

Both skills determine `direct|nested` at entry and preserve it through re-verify. A
nested fix invokes nested verify and returns to its outer stage; a direct fix remains the
terminal owner through its optional re-verify (REQ-EXIT-04).

### 5.2 Verify termini (REQ-ROUTE-04/06, REQ-EXIT-03)

After writing through `state-verify`, invoke `stage-exit` exactly once for the applicable
terminal result:

| Verify result | `--outcome` | Direct primary route | Nested behavior |
|---|---|---|---|
| Zero findings / clean | `passed` | Next live production action after served stage | Return pass to outer owner |
| Findings report written | `findings` | `forge-fix` carrying served stage | Return findings; outer decides/chains fix |
| Explicit user skip/defer | `skipped` | State-derived successor only after `skipped` is persisted | Return explicit skip |
| Dispatch/check/write failure requiring intervention | `failed` | Verify retry/recovery; never production | Return failure; outer cannot advance |

“Review findings first” is an explicit deferral and uses `skipped` only if the user
chooses to defer pipeline action and the skip is persisted; merely presenting the
findings is `findings`. A state-write failure is `failed`, and because authoritative
state is unknown no success block may be printed (REQ-ROUTE-06, REQ-REL-02).

### 5.3 Fix termini (REQ-ROUTE-04/05, REQ-EXIT-03/04)

Replace the current open-ended Step 6 with this complete matrix:

| Fix condition | `--outcome` | Authoritative action |
|---|---|---|
| No applicable findings document/steps | `no-findings` | Verify if still owed; otherwise state-derived advancement |
| User decisions remain unresolved | `decisions` | Resume `forge-fix`; no advancement |
| A fix step, validation, commit, or state write fails | `failed` | Fix/navigator recovery; no advancement |
| Fixes persisted; re-verify not yet run | `applied` | Re-run `forge-verify` for the same served stage |
| Mandatory re-verify passes | `reverified` | Next live production action |
| Mandatory re-verify reports findings | `reverify-findings` | `forge-fix` for the same served stage |
| User explicitly defers fix or re-verify | `deferred` | Deterministic fix/navigator resume; no advancement |

`findings-applied` no longer claims freshness: the targeted writer clears
`verifiedStageVersion`, and only `reverified` after a passing verify permits advancement.
A direct interactive “skip re-verify” is therefore `deferred`, not `reverified`. Manual
capability uses a verify-first printed primary command. Nested `applied` returns to the
outer caller, which performs mandatory nested re-verify; it does not emit its own block
(REQ-ROUTE-04/05, REQ-EXIT-06).

Every `AskUserQuestion` decision uses the labels/trade-offs already prescribed by the
shared protocol. A cancellation, unavailable tool, or non-answer maps to `deferred` or
`failed` according to whether it was an explicit user choice or an operational failure
(REQ-A11Y-01, REQ-ROUTE-05).

## 6. Loop Integration

### 6.1 Deterministic selection across every report branch (REQ-PROD-01/02, REQ-REL-01)

`skills/forge-5-loop/references/result-reporting.md` continues to render factual counts
but removes hand-written standard/warm terminal commands. After `state-complete`, choose
one `LoopOutcome` deterministically from authoritative final counts:

1. `needs-human` when `needsHuman > 0` (even if blocked also exists);
2. otherwise `blocked` when genuine `blocked > 0`;
3. otherwise `deferred` when runner-deferred items exist;
4. otherwise `partial` when pending/in-progress items remain because the iteration limit
   was reached;
5. otherwise `complete` only when every item is done.

The report may still describe every simultaneously applicable count, but there is one
stage-exit invocation and one terminal block. `partial` and `deferred` fence
`forge-5-loop` resume. `blocked` and `needs-human` fence the navigator recovery action.
None may recommend docs as ready. `complete` delegates standalone/epic and verify-first
routing to the script (REQ-PROD-01/02).

Exact terminal call shape:

```bash
python3 "$R/scripts/forge-session.py" stage-exit \
  --feature "{feature}" --stage forge-5-loop --outcome "{LoopOutcome}" \
  --specs-dir "{specsDir}" --host "{host}" \
  --verify-capability "{capability}" {--epic "{epic}"}
```

Operational failure before authoritative counts are available does not fabricate an
outcome; surface recovery and do not close the stage. A loop runner's successful process
exit is not by itself `complete`; final backlog state controls the outcome (REQ-REL-02).

### 6.2 Complete epic member behavior (REQ-PROD-01/02/04)

For completed epic members, the stage-exit router consumes live epic status rather than
the skill's current bespoke Step 6 standard block. It routes an actionable next member
to that member's `nextCommand`, no-actionable/blocked state to the epic dashboard, and a
completed epic to its completion/dashboard view. The skill may announce the rollup
before invoking stage-exit, but no hand-authored terminal action follows it
(REQ-COMPAT-02).

### 6.3 Body-cap and prerequisite constraint (REQ-CAP-01)

Before any loop body edit, confirm Step 2d remains single-sourced in
`skills/forge-5-loop/references/runner-contract.md` as established by commit `c174b55`.
Do not copy run-mode details back into `SKILL.md` or make the conditional agent-selection
reference always-loaded. After replacing bespoke exits, enforce **body** limits of at
most 300 lines and 5,000 words. The current file is 302 total lines/4,512 total words;
tests must count the body using the repository's existing frontmatter-aware convention,
not use raw total lines as a false failure (REQ-CAP-01).

## 7. Documentation Stage Integration

### 7.1 Scripted docs exit (REQ-PROD-03/04, REQ-EXIT-03)

Replace `skills/forge-6-docs/SKILL.md` Step 5's hand-written terminal paragraph with:

```bash
python3 "$R/scripts/forge-session.py" stage-exit \
  --feature "{feature}" --stage forge-6-docs --outcome complete \
  --specs-dir "{specsDir}" --host "{host}" \
  --verify-capability "{capability}" {--epic "{epic}"}
```

For an epic member, stage-exit executes/consumes the exact `render-status` integration in
§2.2: actionable member -> its live command; blocked/no actionable -> epic dashboard;
all complete -> dashboard completion view. It must not trust a Step 1 snapshot after docs
state changes. For standalone completion, `/feature-forge:forge {feature}` is the fenced
completion action; new-feature and epic creation suggestions remain secondary unfenced
text (REQ-PROD-04).

If docs work cannot complete, persist only valid partial state and invoke the same call
with `--outcome blocked`; its primary action is navigator/recovery and it never claims
pipeline completion. Failure before a safe state write stops without a success exit
(REQ-PROD-03, REQ-REL-02).

### 7.2 Backstop interaction (REQ-EXIT-06/07, REQ-COMPAT-02)

The existing impl-verify backstop remains, but an unresolved result cannot be bypassed by
the docs terminal wording. An explicit “generate anyway” choice must persist `skipped`
before docs can complete. Operationally unavailable verification is not an implicit
skip; the scripted exit remains verify-first/manual until pass or explicit skip
(REQ-EXIT-06/07).

## 8. Epic Creation and Edit Integration

### 8.1 Creation compatibility (REQ-PROD-05, REQ-COMPAT-01)

Keep the creation call in `skills/forge-0-epic/SKILL.md` at Step C8 with
`--feature "{epic}" --stage forge-0-epic --next-feature
"{first-actionable-feature}"`, adding capability. A newly created member has no completed
production stage, so the existing PRD handoff remains unchanged (REQ-PROD-05).

### 8.2 Edit-mode live routing (REQ-PROD-05/06, REQ-SEC-01)

Replace the dashboard-only closing prose in
`skills/forge-0-epic/references/edit-mode.md` with a fresh `render-status` call after the
successful mutation/commit. When `actionable` supplies a concrete next member, pass it
as `--next-feature`; `stage_exit` resolves that member's `.pipeline-state.json`, calls
the existing `next_stage(state: dict) -> str | None`, and routes to its first incomplete
production stage. A member with completed PRD must not be sent back to PRD.

If no member is actionable, invoke epic stage-exit without a concrete member and route
to the epic dashboard/completion view; do not pass the literal placeholder. If the
selected member state is missing, unreadable, unsafe, or ambiguous, the script emits a
named warning and degrades only to `forge-1-prd <member>`. The skill surfaces that
warning before the block and does not derive a later stage itself (REQ-PROD-06,
REQ-OBS-02, REQ-SEC-01).

A failed/invalid `render-status` prevents mutation-follow-up guessing: surface findings
and use the safe epic dashboard recovery path, never an arbitrary member (REQ-REL-02).

## 9. Error and Recovery Contract

All strict script failures use `UsageError` from `00-core-definitions.md` and CLI exit 2.
Skill handling is operation-specific:

| Failure | Skill response |
|---|---|
| Plugin root cannot be located | Surface existing stderr and stop; no terminal block |
| Invalid stage/outcome/owner/capability | Surface `Error:` verbatim, correct the typed call, retry at most once |
| Missing/conflicting served-stage metadata | Ask for/select authoritative mode, then retry; never guess |
| `state-note` failure | State that the note was not persisted; preserve prior state and stop claiming success |
| Verify/fix state transition failure | Use `failed`; do not route downstream |
| Clean-room unavailable/non-answer | Leave verification outstanding and regenerate manual verify-first exit |
| Epic member unreadable | Use only the script's named PRD fallback warning |
| `render-status` invalid graph | Surface findings and route to dashboard/recovery, never a member |
| Nested branch failure | Return structured failure to outer owner; emit no sentinel |
| Direct successful exit | Print exactly one block and stop at sentinel |

Skills must not catch an error and append a hand-written “Next steps” list. No recovery
path mutates JSON directly, guesses a feature directory, or treats an unavailable tool
as an explicit user skip (REQ-REL-02, REQ-SEC-01).

## 10. Migration and Canon Guard

Implementation order for canon is: update the shared protocol; update verify/fix; update
loop result reporting/body; update docs; update epic edit/creation; add capability flags
to stages 1–4; then regenerate every adapter. Never edit `adapters/` directly
(REQ-COMPAT-02, tech-spec §3.10).

`tests/test_stage_exit_protocol.py` must enumerate exactly these ownership sites — and it
already does, via `CANONICAL_EXIT_SITES` in `06-compliance-and-coverage.md` §2.1, which is the
**single** declaration of the covered set. This document does not re-list the nine names: two
hand-maintained allow-lists in one module is the drift REQ-GUARD-01 exists to prevent, and the
`06` tuple is the richer of the two (it carries the `contract_paths` the guard actually reads).

Where a plain name tuple is convenient, derive it — never re-author it:

```python
COVERED_SKILLS: tuple[str, ...] = tuple(site.skill for site in CANONICAL_EXIT_SITES)
```

The guard verifies a canonical invocation, applicable typed flags, direct sentinel-last
instruction, and nested no-terminal wording. It replaces assertions for the loop's
standard/warm blocks and docs' terminal prose with positive scripted-contract assertions;
it does not delete equivalent coverage (REQ-GUARD-01..03).

## Public API and Internal Surface

This document adds **no Python API**. It specifies how the nine canonical skills consume the
surfaces owned by `02-stage-exit-routing.md` and `03-verification-state.md`, so its own
"public surface" is the prose contract skills follow and the commands users type.

- **User-facing:** the slash commands the NEXT-STEPS block prescribes — `/feature-forge:*` on
  Claude, `/skill:*` on Pi, and the host-neutral generic forms (§3.2). These are a
  compatibility surface: §3.2's host determination and the build-time translation in
  `05-config-and-distribution.md` must keep all three correct, and changing a rendered command
  string is a user-visible break (REQ-EXIT-05).
- **Skill-side contract (internal to the canon, enforced mechanically):** the single canonical
  stamp of §3.1, the directive order and sentinel-last rule of §3.3, and terminal-ownership
  capture in §5.1. `06-compliance-and-coverage.md` enforces all three against
  `CANONICAL_EXIT_SITES`; a skill that hand-rolls an exit instead of stamping fails that guard.
- **Consumed, not owned:** `stage_exit`, `cmd_state_note`, `cmd_state_verify`,
  `_host_command`, `_next_steps_block`, and `render_status` — every signature in §2.2 is read
  from existing source or owned by another document and is cited there, never redefined here.
- **Declares no constant of its own.** The covered-skill allow-list is owned by
  `06-compliance-and-coverage.md` §2.1 (`CANONICAL_EXIT_SITES`); §10 derives `COVERED_SKILLS`
  from it rather than re-listing the names, so there is exactly one place a newly added
  pipeline skill must be registered.
- **Test/eval-only:** none.

## Dependencies

- `00-core-definitions.md` — implement first; owns all shared literals, payloads,
  `UsageError`, `stage_exit`, rendering, and `cmd_state_verify` target signatures.
- `01-architecture-layout.md` — implement first; owns file placement, sequencing, and
  adapter distribution.
- The state/debt implementation spec that provides `state-verify` must precede §5 and
  auto-verify skill conversion.
- The routing implementation spec that expands `stage_exit` must precede all canonical
  call-site conversions.
- Existing `scripts/epic-manifest.py render-status` and `scripts/forge-session.py
  cmd_state_note` integrations quoted in §2 must remain available.

## Verification

- [ ] Search the nine canonical ownership sites and find one scripted direct terminal
  contract per skill; find no bespoke standard/warm/docs terminal block.
- [ ] Run every verify outcome and every fix outcome directly and nested; direct output
  has one final sentinel, nested output has none.
- [ ] Exercise matching, inferred, absent, and conflicting served-stage/mode metadata.
- [ ] Exercise loop complete, partial, blocked, needs-human, and deferred, including
  simultaneous blocked + needs-human; only one deterministic exit is emitted.
- [ ] Confirm non-complete loop outcomes never route to docs.
- [ ] Exercise standalone docs plus actionable, blocked, and complete epic docs routes.
- [ ] Exercise epic edit against members currently at every production stage and the
  unreadable-member PRD fallback.
- [ ] Verify capable Claude and Pi select `standard`; incapable Claude/Pi/generic select
  manual verify-first output with correct `/clear`, `/new`, or neutral wording.
- [ ] Confirm PRD/tech parking-lot concerns invoke `state-note` immediately and include
  `--epic` for members.
- [ ] Confirm `skills/forge-5-loop/SKILL.md` retains the Step 2d pointer and passes both
  body caps.
- [ ] Regenerate adapters and run `bash scripts/validate.sh` plus
  `ruff check scripts/ eval/`; no generated drift remains.
