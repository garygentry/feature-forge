# Epic Orchestration — Product Requirements Document

## 1. Problem Statement

Some changes are too large or pervasive to be a single forge feature. Today the forge pipeline executes one feature at a time with no awareness of sibling features. When a big change is logically split into multiple discrete features — each with its own PRD, specs, backlog, and autonomous loop run — there is no overarching thread of execution: nothing records the decomposition, the dependencies between features, the shared contracts they must agree on, or what should happen next when one feature completes. Users must hold that orchestration in their heads across sessions.

This feature introduces the **epic**: a named grouping of related forge features with declared dependencies, a shared narrative/contract document, and orchestration behavior that carries the thread of execution from one feature to the next — without changing how a standalone single feature flows through the pipeline.

## 2. User Stories

- As a developer with a large change, I want a structured interview that decomposes it into discrete features with dependencies, so each feature is right-sized for the pipeline and the overall plan is recorded.
- As a developer working through an epic, I want each feature's PRD/tech-spec authored with knowledge of the epic's goals and the completed upstream features' contracts, so downstream features build against reality rather than guesses.
- As a developer finishing a feature, I want forge to tell me what's next in the epic and offer to start it, so the overarching thread of execution isn't lost between sessions.
- As a developer, I want to be warned when I try to run a feature's loop before its dependencies are complete, so I don't implement against unbuilt contracts.
- As a developer, I want to see an epic-level dashboard showing every feature's pipeline stage and the dependency graph, so I know the state of the whole effort at a glance.
- As a developer whose plans changed, I want to add, remove, or re-order features in an in-flight epic, so the epic stays a living plan rather than a stale artifact.
- As a single-feature user, I want everything to work exactly as it does today when no epic is involved.

## 3. Functional Requirements

### 3.1 Epic Creation and Decomposition

- REQ-EPIC-01: A dedicated pipeline stage (forge-0-epic) must create an epic through a structured interview that decomposes a large change into discrete features with dependency relationships.
  - Priority: P0
- REQ-EPIC-02: Epic creation must produce a machine-readable manifest recording: epic name, description, status, the ordered feature list with per-feature dependency declarations (`dependsOn`), per-feature status, and a pointer to the shared narrative document.
  - Priority: P0
- REQ-EPIC-03: Epic creation must produce a human-readable narrative document (EPIC.md) capturing the overall goal, the decomposition rationale, and the interface contracts between features (what each feature exposes and consumes).
  - Priority: P0
- REQ-EPIC-04: At epic creation, each feature receives only a short charter (one-paragraph scope statement plus contract obligations) — not a full PRD. Full PRDs/specs are authored just-in-time when the feature becomes actionable.
  - Priority: P0
  - Notes: Avoids staleness from authoring downstream specs before upstream contracts are real.
- REQ-EPIC-05: The dependency graph declared in an epic must be validated as acyclic at creation and after every modification.
  - Priority: P0
- REQ-EPIC-06: Re-running forge-0-epic on an existing epic must enter an edit mode supporting adding, removing, and re-ordering features and changing dependencies, with validation that the graph remains acyclic and a warning when modifications affect in-flight or completed features.
  - Priority: P1

### 3.2 Directory Layout and State Model

- REQ-DIR-01: An epic must be a self-contained subtree: `{specsDir}/{epic}/` containing the manifest, EPIC.md, and one subdirectory per member feature (`{specsDir}/{epic}/{feature}/`) holding that feature's standard pipeline artifacts.
  - Priority: P0
- REQ-DIR-02: Standalone (non-epic) features must continue to live flat at `{specsDir}/{feature}/` with no change in behavior or layout.
  - Priority: P0
- REQ-DIR-03: Feature discovery must handle both layouts: tooling must distinguish epic directories from feature directories and resolve a bare feature name to its directory regardless of nesting.
  - Priority: P0
- REQ-DIR-04: Feature names must be globally unique across the entire specs tree (flat and nested), so pipeline commands taking a bare feature name remain unambiguous. Creation of a duplicate name must be rejected with a clear error.
  - Priority: P0
- REQ-STATE-01: The epic manifest is the canonical record of epic membership; each member feature's pipeline state additionally carries an epic back-pointer for fast lookup. On conflict, the manifest wins.
  - Priority: P0
- REQ-STATE-02: Per-feature status shown at the epic level must be derived from each feature's own pipeline state at read time; any cached status in the manifest must be recomputed on read and never trusted when stale.
  - Priority: P0

### 3.3 Orchestration and Thread of Execution

- REQ-ORCH-01: A feature is considered complete for orchestration purposes when its pipeline reaches loop completion (forge-5-loop done; implementation verification, if run, passed). Merge status is not tracked in v1.
  - Priority: P0
- REQ-ORCH-02: When a member feature completes, forge must update the epic's view, announce completion, identify the next actionable feature(s) (all dependencies complete), and prompt the user to begin the next one — including offering to author its PRD if not yet written. The user confirms each transition (prompted handoff; no autonomous chaining in v1).
  - Priority: P0
- REQ-ORCH-03: When multiple features are simultaneously unblocked, execution is serial: the user is shown all unblocked features and picks one. The manifest must be expressive enough to identify parallel-eligible features for future use.
  - Priority: P0
- REQ-ORCH-04: Running the loop stage for a feature with incomplete dependencies must warn with the list of unmet dependencies and require explicit confirmation to proceed.
  - Priority: P0
- REQ-ORCH-05: Epic lifecycle states (active, paused, abandoned, complete) must be supported, consistent with existing per-feature lifecycle semantics. Pausing or abandoning an epic must not silently alter member features' own states; the relationship must be made explicit to the user.
  - Priority: P1

### 3.4 Context Injection

- REQ-CTX-01: When stages 1–3 (PRD, tech spec, implementation specs) run for a feature belonging to an epic, they must automatically load as context: EPIC.md, the feature's charter, and the PRDs/tech-specs of completed upstream dependency features.
  - Priority: P0
- REQ-CTX-02: Context injection must surface the feature's contract obligations from the epic (what it must expose to dependents, what it consumes from dependencies) so requirements and specs are written against them.
  - Priority: P0

### 3.5 Visibility

- REQ-VIS-01: The forge navigator must provide an epic dashboard showing: epic status, the dependency graph, each member feature's pipeline stage/status (using existing status indicators), which features are blocked vs. actionable, and the recommended next command.
  - Priority: P0
- REQ-VIS-02: The navigator's no-argument discovery view must list epics alongside standalone features, with a roll-up summary per epic (e.g., 2/4 features complete).
  - Priority: P1

### 3.6 Verification and Docs

- REQ-VERIFY-01: forge-verify must support an epic mode checking: manifest/state consistency, dependency-graph acyclicity, charter coverage (every feature has a charter and contract obligations), and contract drift (completed features' specs vs. the contracts declared in EPIC.md).
  - Priority: P1
- REQ-DOCS-01: forge-6-docs must be epic-aware: when all member features are complete, offer to synthesize an epic-level architecture document spanning the features, in addition to per-feature docs.
  - Priority: P2

## 4. Non-Functional Requirements

### 4.1 Compatibility
- REQ-COMPAT-01: All existing single-feature workflows, commands, artifacts, and state files must work unchanged when no epic is involved. Epic support is purely additive.
  - Priority: P0
- REQ-COMPAT-02: Existing projects with flat `{specsDir}/{feature}/` layouts and existing `.pipeline-state.json` files must require no migration.
  - Priority: P0
- REQ-COMPAT-03: The loop runner contract (rauf) must require no changes; per-feature backlogs remain independent and dependencies are resolved only at feature granularity.
  - Priority: P0

### 4.2 Robustness
- REQ-ROBUST-01: Epic state must survive across sessions: any session can reconstruct the epic's full status from files on disk with no in-memory state.
  - Priority: P0
- REQ-ROBUST-02: A corrupted or hand-edited manifest must fail validation with actionable errors (e.g., unknown feature reference, cycle detected, duplicate names) rather than undefined behavior.
  - Priority: P1

### 4.3 Observability
- REQ-OBS-01: Epic-affecting actions (creation, edits, feature completion, handoff prompts) must be reflected in the manifest with timestamps, and committed per the existing git-commit-after-stage protocol.
  - Priority: P1

## 5. Constraints

- Must integrate with the existing forge pipeline skills (forge, forge-1-prd … forge-6-docs, forge-verify, forge-fix) and their shared conventions (feature-name validation, AskUserQuestion protocol, pipeline-state schema, git commit protocol).
- Must work with the existing loop runner contract (rauf by default) without modifying rauf or the backlog schema.
- Epic and feature names follow the existing kebab-case single-token convention.
- Configuration continues to flow through `forge.config.json`; epic support must respect `specsDir`, `gitCommitAfterStage`, `commitPrefix`, and `backlogDir` semantics.

## 6. Out of Scope

- Cross-backlog item-level dependencies (a backlog item in feature B depending on an item in feature A). Dependencies are feature-granular only; interleaving at item level signals the features should be one feature.
- Autonomous (unconfirmed) chaining from one feature's loop into the next feature's pipeline.
- Parallel execution of unblocked features (worktrees/branches); v1 is serial, though the manifest expresses parallel eligibility.
- Merge/PR-status tracking as a completion criterion.
- Nested epics (epics containing epics) and feature membership in multiple epics.
- Migration tooling to move an existing standalone feature into an epic (manual move + manifest edit is acceptable in v1).

## 7. Open Questions

- Should the prompted handoff after feature completion also offer to run forge-verify (impl) on the just-completed feature before unblocking dependents, as a recommended default?
- When an epic is edited and a completed feature is removed, how should its directory and artifacts be treated (leave in place vs. relocate to flat specs)?
- Should EPIC.md contract sections have a lightweight structure (per-feature exposes/consumes lists) to make REQ-VERIFY-01 contract-drift checking tractable, or remain free-form?

## 8. Success Criteria

- A large change can be decomposed via forge-0-epic into ≥2 features with dependencies; the manifest and EPIC.md are created, validated, and committed.
- Running stages 1–3 on a member feature demonstrably incorporates epic context (charter, contracts, completed upstream specs).
- Attempting forge-5-loop on a blocked feature produces the dependency warning and confirmation gate.
- Completing a member feature triggers the prompted handoff identifying the correct next feature per the dependency graph.
- The epic dashboard accurately reflects per-feature stages, blocked/actionable status, and the next recommended command, reconstructed purely from disk state in a fresh session.
- All existing single-feature flows pass unchanged in a project with no epics.
