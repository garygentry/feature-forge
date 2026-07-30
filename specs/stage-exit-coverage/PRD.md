# Stage Exit Coverage — Product Requirements Document

## 1. Problem Statement

feature-forge's deterministic stage-exit contract covers only `forge-0-epic` through
`forge-4-backlog`. The pipeline paths most likely to branch or divert are outside that coverage:
`forge-5-loop` and `forge-6-docs` hand-roll exits, while `forge-verify` and `forge-fix` have no
complete terminus. This creates three user-visible failures:

1. a skill can prescribe a `stage-exit` command that the script rejects (#172);
2. a verify/fix diversion can complete and silently drop the pipeline thread (#176); and
3. epic edit-mode can route a progressed member back to `forge-1-prd` because the exit ignores
   the member's actual state (#175).

A related observability gap makes configured in-stage auto-verification disappear without a trace:
if the model drops the `runInStageVerify` directive, an owed verify is indistinguishable from one
that was never scheduled (#163). The existing compliance evaluation cannot detect these failures
because it exercises only the already-scripted `forge-1-prd` path.

The feature must make every pipeline-advancing exit deterministic, preserve current context-aware
handoffs, persist auto-verify debt before control can be lost, and prove branch-path compliance.

## 2. User Stories

- As a forge user, I want every production stage to end with an authoritative next action so that I
  never have to reconstruct where the pipeline should continue.
- As a user running verify or fix, I want the diversion to rejoin the production stage it served so
  that successful audit work does not lose the original pipeline thread.
- As an epic editor, I want the exit to use the selected member's actual progress so that I am not
  sent into destructive-looking re-authoring of completed artifacts.
- As a loop operator, I want complete, partial, blocked, and needs-human loop outcomes to have
  deterministic resume/continue guidance.
- As a pipeline operator, I want configured-but-unrun auto-verification to remain visible in state so
  that dropped work is distinguishable from work never scheduled.
- As a maintainer, I want a mechanical coverage guard and branch-path compliance fixture so that a
  new or edited pipeline skill cannot silently omit its exit.
- As a project maintainer, I want duplicate keys in `forge.config.json` reported without breaking
  existing projects so that last-key-wins behavior is never silent.

## 3. Functional Requirements

### 3.1 Scripted Exit Coverage

- **REQ-EXIT-01 (P0):** The scripted stage-exit interface MUST accept all pipeline-advancing
  production stages: `forge-0-epic`, `forge-1-prd`, `forge-2-tech`, `forge-3-specs`,
  `forge-4-backlog`, `forge-5-loop`, and `forge-6-docs`.
- **REQ-EXIT-02 (P0):** The scripted stage-exit interface MUST accept the branch skills
  `forge-verify` and `forge-fix` when they are responsible for returning control to the user.
- **REQ-EXIT-03 (P0):** Every covered direct invocation MUST emit exactly one sentinel-terminated
  NEXT-STEPS block as its final user-facing output, with no content after the sentinel.
- **REQ-EXIT-04 (P0):** Nested auto-verify/auto-fix chains MUST leave terminal-exit ownership with
  the outermost authoring-stage caller; nested verify/fix invocations MUST NOT emit competing or
  duplicate terminal exits.
- **REQ-EXIT-05 (P0):** Existing host-specific command forms and fresh-session wording MUST remain
  correct for Claude, Pi, and generic adapter hosts.

### 3.2 Branch Diversion and Rejoin Routing

- **REQ-ROUTE-01 (P0):** A direct `forge-verify` or `forge-fix` exit MUST accept an explicit
  production stage that the branch operation served and route from that stage's current pipeline
  position.
- **REQ-ROUTE-02 (P0):** When the served production stage is omitted, the system MUST infer it from
  the verify mode or equivalent authoritative metadata where the mapping is unique.
- **REQ-ROUTE-03 (P0):** If no explicit stage is provided and inference is missing or ambiguous,
  routing MUST fail closed with actionable guidance rather than guess a stage.
- **REQ-ROUTE-04 (P0):** A clean verify MUST return to the next applicable production action; verify
  findings MUST route to fix; fixes that require re-verification MUST route to re-verify before
  advancing.
- **REQ-ROUTE-05 (P0):** `forge-fix` MUST define a terminus for every outcome, including no
  applicable findings, unresolved decisions, failed fix work, fixes applied, re-verify success,
  re-verify findings, and an explicit user deferral.
- **REQ-ROUTE-06 (P0):** `forge-verify` MUST define a terminus for every outcome, including pass,
  findings reported, skipped/deferred action, and failures that require user intervention.

### 3.3 Production-Stage Handoffs

- **REQ-PROD-01 (P0):** `forge-5-loop` MUST use the scripted exit contract for every outcome,
  including complete, partial/iteration-limited, blocked, and needs-human runs.
- **REQ-PROD-02 (P0):** A non-complete loop outcome MUST point to an appropriate deterministic
  resume or recovery action and MUST NOT imply that downstream production stages are ready.
- **REQ-PROD-03 (P0):** `forge-6-docs` MUST use the scripted exit contract rather than prescribe an
  unsupported command or hand-roll state/next-step output.
- **REQ-PROD-04 (P0):** The docs exit MUST preserve current context-aware behavior: epic members
  route to the next actionable member or epic dashboard, while standalone completion offers the
  existing navigator/new-feature completion actions.
- **REQ-PROD-05 (P0):** `forge-0-epic` edit-mode exit with a concrete next member MUST resolve that
  member's state and route to its actual next production stage; creation-mode behavior MUST remain
  unchanged.
- **REQ-PROD-06 (P1):** Unresolvable or unreadable epic-member state MUST degrade safely to the
  documented default handoff without crashing stage closure or fabricating progress.

### 3.4 Auto-Verify Debt

- **REQ-DEBT-01 (P0):** When effective configuration requires in-stage auto-verify, the system MUST
  persist `auto-verify-pending` before emitting the directive that schedules the verify.
- **REQ-DEBT-02 (P0):** The marker MUST distinguish "auto-verify was owed but has not successfully
  run" from "verification was never scheduled," manual pending work, and explicit skip.
- **REQ-DEBT-03 (P0):** A verify result MUST replace `auto-verify-pending` with the applicable
  terminal/finding status (`passed`, `findings-reported`, `findings-applied`, or `skipped`) through
  the normal verified-state write path.
- **REQ-DEBT-04 (P0):** Dispatch failure, interruption, compaction, or model non-adherence MUST leave
  the marker visible until verification runs or a user explicitly resolves/skips it.
- **REQ-DEBT-05 (P0):** Navigator, stage-exit, status rendering, and downstream pre-flight checks
  MUST recognize and clearly report `auto-verify-pending`; they MUST NOT classify it as ordinary
  `never` or as a successful terminal state.
- **REQ-DEBT-06 (P1):** Existing state files without the new status MUST continue to load and retain
  their current meaning without migration.

### 3.5 State and Provenance Integrity

- **REQ-STATE-01 (P0):** New scripted commit-hash writes MUST store and validate the full 40-character
  Git object hash convention.
- **REQ-STATE-02 (P1):** Legacy state carrying a short commit hash MUST remain readable; it MAY emit
  a warning but MUST NOT be rejected solely for that legacy format.
- **REQ-STATE-03 (P0):** State mutations introduced by this feature MUST use atomic, targeted state
  writers and MUST NOT require model-authored JSON or whole-file JSON round-tripping.
- **REQ-STATE-04 (P0):** State writes and exit generation MUST preserve the two-commit provenance
  protocol and MUST never use amend-based hash recording.

### 3.6 Configuration Diagnostics

- **REQ-CONFIG-01 (P1):** Duplicate object keys in `forge.config.json` MUST produce a visible warning
  naming the duplicated key rather than resolving silently.
- **REQ-CONFIG-02 (P1):** Duplicate-key warnings MUST be applied consistently through the shared
  configuration-reading path used by effective config, stage exit, initialization/validation, and
  other forge config consumers.
- **REQ-CONFIG-03 (P1):** Duplicate keys MUST remain warning-only in this release; the effective
  value MUST retain today's last-key-wins compatibility.
- **REQ-CONFIG-04 (P1):** Duplicate-key detection MUST be general JSON-object behavior, not a special
  case limited to `autoVerify`.

### 3.7 Mechanical and Evaluation Coverage

- **REQ-GUARD-01 (P0):** A canonical guard MUST explicitly enumerate every pipeline-advancing skill
  required to end through the deterministic exit contract.
- **REQ-GUARD-02 (P0):** The guard MUST cover the production stages and direct branch skills while
  excluding navigator, setup, bootstrap, and advisory skills intentionally.
- **REQ-GUARD-03 (P0):** Existing tests that require bespoke loop exits or terminal docs behavior
  MUST be replaced with assertions for the new scripted contract rather than weakened or deleted
  without equivalent coverage.
- **REQ-EVAL-01 (P0):** The compliance evaluation MUST add a fixture that drives
  verify → fix → re-verify and scores whether one correct terminal sentinel emerges from the full
  branch path.
- **REQ-EVAL-02 (P0):** The new fixture MUST test both successful rejoin and findings/recovery paths,
  including actual command execution evidence rather than scoring prose alone.
- **REQ-EVAL-03 (P1):** Evaluation documentation MUST state that the original `forge-1-prd` baseline
  measured only the already-scripted linear path and that branch coverage is a separate result.

### 3.8 Focused Follow-ups and Prerequisite

- **REQ-CAP-01 (P0):** Before any other Phase 1 edit to `skills/forge-5-loop/SKILL.md`, the Step 2d
  run-mode detail MUST be single-sourced in `references/runner-contract.md`, leaving a compact body
  pointer and regenerated adapters. This prerequisite was completed in commit `c174b55`.
- **REQ-FOLLOW-01 (P1):** The stale `runner-contract.md` phrase that describes `--model` as an
  "optional flag below" after the catalog split MUST be corrected without making the conditional
  agent-selection reference always-loaded.
- **REQ-FOLLOW-02 (P1):** PRD and tech-stage parking-lot instructions that promise to persist a note
  MUST have a sanctioned immediate `state-note` path, including epic-member targeting, rather than
  relying on an implied hand-authored state edit.

## 4. Non-Functional Requirements

### 4.1 Determinism and Reliability

- **REQ-REL-01 (P0):** Identical state, configuration, host, served stage, and outcome MUST produce
  byte-identical directive and NEXT-STEPS structures.
- **REQ-REL-02 (P0):** Exit routing and debt recording MUST fail closed on unsafe or ambiguous input
  and provide an actionable error; no path may silently choose a different feature or stage.
- **REQ-REL-03 (P0):** A crash between scheduling auto-verify and dispatching it MUST leave recoverable
  durable state that exposes the outstanding obligation.

### 4.2 Compatibility

- **REQ-COMPAT-01 (P0):** Existing scripted exits for stages 0–4 MUST preserve their user-visible
  prompts, verify-gate routing, directives, host translations, and sentinel placement except where
  #175 intentionally corrects epic edit-mode routing.
- **REQ-COMPAT-02 (P0):** Existing direct, nested auto-verify, standalone, and epic workflows MUST
  remain supported with no required migration of project config or pipeline state.
- **REQ-COMPAT-03 (P0):** `smokeCommand: null` MUST remain valid and CHECK-I21 MUST remain
  not-applicable for this repository by design.

### 4.3 Performance and Scale

- **REQ-PERF-01 (P1):** Exit generation and config diagnostics MUST remain bounded by the existing
  small state/config files and MUST not introduce network calls, repository-wide history scans, or
  additional model turns.
- **REQ-PERF-02 (P1):** The common no-duplicate config path and existing stages 0–4 exit path SHOULD
  remain operationally negligible relative to current script execution.

### 4.4 Observability

- **REQ-OBS-01 (P0):** Machine-readable stage-exit directives MUST expose enough routing and debt
  information for tests and downstream tools to distinguish next action, verify obligation, and
  failure/defer outcomes.
- **REQ-OBS-02 (P1):** Human-facing warnings MUST name the affected feature/stage/key and the action
  required to recover, without dumping or reformatting the complete state file.

### 4.5 Security and Accessibility

- **REQ-SEC-01 (P0):** All feature/stage resolution and state writes MUST retain existing path-safety,
  epic-member disambiguation, and fail-closed containment behavior.
- **REQ-A11Y-01 (P1):** New interactive choices MUST continue to use `AskUserQuestion` with explicit
  labels, recommended defaults, and text descriptions; no color-only or layout-only distinction may
  carry required meaning.

## 5. Constraints

- Canon in `skills/`, `agents/`, and `references/` is vendor-neutral and spec-pure.
- Generated `adapters/` must be regenerated in the same commit as every canon or copied-script edit.
- `bash scripts/validate.sh` is the verification command; pytest alone is insufficient.
- `ruff check scripts/ eval/` must run locally even though it is CI-only.
- CI has no `jsonschema`; runtime/config validation must remain Python-stdlib compatible.
- Existing pipeline state and config files are compatibility inputs, not disposable fixtures.
- Stage exits must preserve the sentinel protocol and host-specific command translation.
- This feature is focused on #163, #172, #175, #176, V-012, compliance/guard/docs coverage, and the
  two Phase 0 self-review follow-ups.

## 6. Out of Scope

- Zero-prompt configuration fields (`reviewMode`, `agentMode`, `docsStage`) planned for Phase 2.
- Epic charter mutation and final-member docs gating planned for Phase 3.
- Semantic verify-completeness sweeps planned for Phase 4.
- General adapter host-term translation planned for Phase 5.
- Changes to rauf itself, including issue #82.
- Raising this repository's `smokeCommand` from `null` or changing CHECK-I21 semantics.
- Strict rejection of duplicate config keys or legacy short commit hashes.
- Redesigning the full forge state model or introducing a generic arbitrary JSON patch command.

## 7. Open Questions

None. Interview decisions:

- direct verify/fix accepts an explicit served stage with deterministic inference fallback;
- the outermost caller owns nested auto-fix exits;
- every loop outcome is covered;
- auto-verify debt is a distinct `auto-verify-pending` status written at scheduling time;
- docs retains context-aware terminal handoff;
- duplicate config keys warn everywhere but remain last-key-wins;
- new writes use full hashes while legacy short hashes remain readable; and
- the exit guard uses an explicit allow-list.

## 8. Success Criteria

1. All nine covered stage/branch identifiers are accepted by the scripted exit interface and every
   direct pipeline-advancing path ends with exactly one authoritative sentinel.
2. Reproductions for #172, #175, and #176 route correctly without hand-authored state or pipeline
   thread loss.
3. A deliberately dropped auto-verify dispatch leaves `auto-verify-pending` visible to status,
   navigator, stage exit, and downstream pre-flight; a completed verify replaces it correctly.
4. The verify → fix → re-verify compliance fixture passes its offline validity/scorer tests and can
   measure the branch path independently from the original PRD fixture.
5. The explicit canonical coverage guard fails when any covered skill's exit is removed.
6. Duplicate config keys emit consistent non-breaking warnings, including outside `autoVerify`.
7. New commit-hash writes are full-length while a legacy short-hash fixture still loads.
8. `skills/forge-5-loop/SKILL.md` remains within both spec-purity body caps, and every canon/script
   change ships with fresh adapters in the same commit.
9. `bash scripts/validate.sh` and `ruff check scripts/ eval/` pass with no adapter or docs drift.
