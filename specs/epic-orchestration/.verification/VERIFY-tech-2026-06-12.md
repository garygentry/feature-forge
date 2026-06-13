# Verification Report: epic-orchestration (tech)
Date: 2026-06-12
Pipeline Stage: forge-2-tech complete / forge-verify-tech
Artifacts Reviewed: specs/epic-orchestration/PRD.md, specs/epic-orchestration/tech-spec.md (plus repo source for CHECK-T05)

Executed 17 of 17 checks. Results: 12 pass, 4 fail, 1 not-applicable.

Per-check results:
- CHECK-T01 pass | CHECK-T02 pass | CHECK-T03 fail (V-001) | CHECK-T04 pass | CHECK-T05 pass | CHECK-T06 pass | CHECK-T07 pass | CHECK-T08 fail (V-002) | CHECK-T09 pass | CHECK-T10 pass | CHECK-T11 pass | CHECK-T12 pass | CHECK-T13 pass | CHECK-T14 fail (V-003) | CHECK-T15 not-applicable | CHECK-T16 fail (V-004) | CHECK-T17 pass

## Summary
- Total findings: 4
- Gaps: 2
- Inconsistencies: 1
- Improvements: 1
- Errors: 0

## Findings

### V-001: REQ-OBS-01 (timestamps + git-commit protocol) has no corresponding tech decision
- **Severity:** gap
- **Location:** tech-spec.md — no section addresses REQ-OBS-01; §4.1 manifest has `createdAt`/`updatedAt` only at the epic level
- **Issue:** PRD REQ-OBS-01 (P1) requires that "epic-affecting actions (creation, edits, feature completion, handoff prompts) must be reflected in the manifest with timestamps, and committed per the existing git-commit-after-stage protocol." The tech spec's manifest schema (§4.1) carries only top-level `createdAt`/`updatedAt`; it does not specify (a) that `updatedAt` is bumped on each mutator (`add-feature`/`remove-feature`/`reorder`/`set-dep`/`set-status`), nor (b) any per-action audit trail for feature completion/handoff prompts, nor (c) where the git-commit-after-stage protocol is invoked for `forge-0-epic` edits and handoff. REQ-OBS-01 is neither traced to a decision nor explicitly deferred.
- **Suggested fix:** Add a short "Observability / Audit" subsection (or extend §3.7 and §4.1) stating: every helper mutator updates `updatedAt`; specify whether per-action history is recorded (and if not, explicitly state that v1 records only `updatedAt` and defer an audit log with rationale); and state which skills invoke the git-commit-after-stage protocol after `forge-0-epic` creation/edits and after the §5.3 handoff. Add the REQ-OBS-01 trace ID.
- **References:** PRD.md REQ-OBS-01; tech-spec.md §4.1, §3.7, §5.3
- **Checklist:** CHECK-T01, CHECK-T03

### V-002: Required changes to existing skills under-specified for the `backlogDir` integration
- **Severity:** inconsistency
- **Location:** tech-spec.md §2.2 (forge-4-backlog row) and §5.7; vs. skills/forge-4-backlog/SKILL.md lines 23-25
- **Issue:** The tech spec states "backlogDir derives from the resolved feature dir (nested or flat)" (§2.2 forge-4 row; §5.7). But the actual forge-4-backlog skill resolves `{backlogDir}` as: if `backlogDir` is set in `forge.config.json`, use that value as-is (a single configured path); only when **unset** does it default to `{specsDir}/{feature}`. So an explicitly-configured `backlogDir` does **not** derive per-feature — it is a single global directory. For an epic with multiple member features all sharing one configured `backlogDir`, per-feature backlogs would collide at one path. The spec's blanket "derives from the resolved feature dir" contradicts the existing skill behavior and silently breaks the "per-feature backlogs remain independent" guarantee (REQ-COMPAT-03) when `backlogDir` is configured.
- **Suggested fix:** In §5.7 (and the §2.2 forge-4 row), specify the interaction with a configured `backlogDir`: either (a) require that when an epic is present and `backlogDir` is configured, the backlog path is composed as `{backlogDir}/{feature}` (or `{backlogDir}/{epic}/{feature}`) to keep per-feature independence, or (b) document that a globally-configured `backlogDir` is incompatible with multi-feature epics and must be left unset. State the exact resolution rule rather than "derives from the resolved feature dir."
- **References:** PRD.md REQ-COMPAT-03, REQ-DIR-03; tech-spec.md §2.2, §5.7; skills/forge-4-backlog/SKILL.md lines 23-25
- **Checklist:** CHECK-T08, CHECK-T02

### V-003: Configuration approach for the new `forge.config.json` (stack/test/typecheck) is named but not specified
- **Severity:** gap
- **Location:** tech-spec.md §2.2 (last row: "`forge.config.json` (new, this repo)") and §8
- **Issue:** §2.2 introduces a new `forge.config.json` with fields `stack`, `testCommand`, `typeCheckCommand` for "stack persistence," but no section specifies the schema, defaults, who reads these fields, or how they interact with the existing config keys the Constraints require respecting (`specsDir`, `gitCommitAfterStage`, `commitPrefix`, `backlogDir`). CHECK-T14 (configuration approach specified) is only partially met: the epic feature relies on `specsDir` heavily (resolution, containment) and adds new config fields, yet the config contract is undocumented. It is unclear whether `testCommand`/`typeCheckCommand` are consumed by this feature at all (the helper uses pytest via validate.sh) or are incidental scaffolding.
- **Suggested fix:** Add a "Configuration" subsection listing the config keys this feature reads (at minimum `specsDir`, `backlogDir`, `gitCommitAfterStage`, `commitPrefix`) and their defaults, and either specify the schema/consumers of the new `stack`/`testCommand`/`typeCheckCommand` fields or remove that row if it is out of scope for epic orchestration.
- **References:** PRD.md Constraints (config keys); tech-spec.md §2.2, §8
- **Checklist:** CHECK-T14

### V-004: Resolution scan cost and depth-2 glob widening may surprise on large/legacy specs trees
- **Severity:** improvement
- **Location:** tech-spec.md §3.4 (resolution algorithm steps 2-3), §5.2 (depth-2 glob widening)
- **Issue:** The `resolve` algorithm globs `{specsDir}/*/{name}/.pipeline-state.json` and the uniqueness check (`check-name`) scans the entire specs tree on every resolution; §5.2 widens cross-feature globs to depth-2 in forge-2/3. Two implementation surprises are unaddressed: (1) standalone features whose directory name happens to collide with an epic name, or a nested feature whose name collides with a flat feature, are correctly rejected by REQ-DIR-04 — but the spec never says what happens to a *pre-existing* flat feature that already shares a name with a newly-created epic member (existing trees may already violate global uniqueness, and resolution would then error for previously-working standalone commands, contradicting REQ-COMPAT-01). (2) The depth-2 glob will now also match unrelated nested directories (e.g. `.verification/`, `tests/fixtures/…` under `{specsDir}/*/`) — the spec should bound the glob to feature-shaped dirs (those containing `.pipeline-state.json`).
- **Suggested fix:** In §3.4 add a note on pre-existing-collision handling (a one-time uniqueness audit at first epic creation, or a clear error path that does not regress standalone resolution). In §5.2, constrain the widened globs to directories containing `.pipeline-state.json` (or exclude `.verification`, `tests`, fixture dirs) so context-scan does not pick up non-feature subtrees.
- **References:** PRD.md REQ-DIR-03, REQ-DIR-04, REQ-COMPAT-01; tech-spec.md §3.4, §5.2
- **Checklist:** CHECK-T16

### Notes on passing / NA checks of interest
- **CHECK-T05** (verify referenced source exists): PASS. All referenced existing artifacts exist: `scripts/validate-traceability.py`, `scripts/validate.sh`, `references/shared-conventions.md`, `references/pipeline-state-schema.json`, `agents/forge-researcher.md`, `agents/forge-spec-writer.md`, all 10 `skills/forge-*`. The §9 claim that `forge-verify/SKILL.md` invokes `${CLAUDE_PLUGIN_ROOT}/scripts/validate-traceability.py` is accurate. The pipeline-state-schema currentStage enum and stages keys the spec proposes to extend (`forge-0-epic`, `forge-verify-epic`) are genuinely absent today, so the "add" change is correct.
- **CHECK-T15** (migration/deployment): NOT-APPLICABLE — REQ-COMPAT-02 mandates no migration and the spec correctly designs additive/optional fields; explicitly "no migration" is the right answer.
- **CHECK-T09/T10/T11**: PASS — alternatives are given for §3.1, §3.2, §3.4; error handling §6 is thorough; testing §7 covers helper (pytest, per-branch fixtures) and skill-prose-via-verify.

## Fix Execution Plan

### User Decisions Required
- **V-002:** [RESOLVED 2026-06-12] Compose per-feature subpath — when `backlogDir` is configured, resolve to `{backlogDir}/{feature}/` to preserve per-feature independence (REQ-COMPAT-03).
- **V-003:** [RESOLVED 2026-06-12] In scope — keep `stack`/`testCommand`/`typeCheckCommand` and fully specify schema, defaults, and consumers (new §2.4 Configuration).

### Execution Steps

#### Step 1: Specify backlogDir resolution for epics
- **Files:** specs/epic-orchestration/tech-spec.md (§5.7, §2.2 forge-4 row)
- **Addresses:** V-002
- **Checklist:** CHECK-T08, CHECK-T02
- **Action:** Replace "backlogDir derives from the resolved feature dir" with an exact rule covering the configured-`backlogDir` case, per the user's decision; reaffirm per-feature independence (REQ-COMPAT-03).
- **Depends on:** user decision (V-002)
- **Rationale:** Grouped first because it gates a real correctness/independence guarantee and needs a decision.

#### Step 2: Add Configuration subsection
- **Files:** specs/epic-orchestration/tech-spec.md (new subsection in §2 or §8)
- **Addresses:** V-003
- **Checklist:** CHECK-T14
- **Action:** Document config keys read (specsDir, backlogDir, gitCommitAfterStage, commitPrefix) and defaults; specify or remove the new `stack`/`testCommand`/`typeCheckCommand` fields per user decision.
- **Depends on:** user decision (V-003)
- **Rationale:** Config contract touches the same forge-4 integration area as Step 1; do together.

#### Step 3: Add observability/audit + git-commit coverage for REQ-OBS-01
- **Files:** specs/epic-orchestration/tech-spec.md (§3.7, §4.1, §5.3)
- **Addresses:** V-001
- **Checklist:** CHECK-T01, CHECK-T03
- **Action:** State that mutators bump `updatedAt`; decide and document per-action history vs. deferral with rationale; name the skills that invoke git-commit-after-stage for forge-0-epic edits and handoff; add the REQ-OBS-01 trace.
- **Depends on:** none
- **Rationale:** Self-contained; closes a P1 requirement trace.

#### Step 4: Bound resolution/glob scope and pre-existing-collision handling
- **Files:** specs/epic-orchestration/tech-spec.md (§3.4, §5.2)
- **Addresses:** V-004
- **Checklist:** CHECK-T16
- **Action:** Add pre-existing name-collision handling that does not regress standalone resolution; constrain widened depth-2 globs to dirs containing `.pipeline-state.json` (exclude `.verification`/`tests`/fixtures).
- **Depends on:** none
- **Rationale:** Robustness hardening; independent of the other steps.

## Fix Progress
- Step 1: [APPLIED] 2026-06-12 — V-002: §2.2 forge-4 row + §5.7 now specify per-feature `backlogDir` composition (`{backlogDir}/{feature}/`) when configured; unset default unchanged.
- Step 2: [APPLIED] 2026-06-12 — V-003: added §2.4 Configuration documenting read config keys/defaults and full schema + consumers for `stack`/`testCommand`/`typeCheckCommand`; §2.2 row cross-references §2.4.
- Step 3: [APPLIED] 2026-06-12 — V-001: §3.7 adds Observability/audit (mutators bump `updatedAt`, per-action history deferred with rationale, git-commit-after-stage on creation/edits/handoff); §4.1 annotates `updatedAt`; §5.3 handoff notes commit. REQ-OBS-01 now traced.
- Step 4: [APPLIED] 2026-06-12 — V-004: §3.4 bounds resolution/uniqueness globs to feature-shaped dirs and adds pre-existing-collision handling (no standalone regression; CHECK-E08 audit); §5.2 constrains depth-2 globs to dirs containing `.pipeline-state.json`.
