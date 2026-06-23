# Feature Forge Pipeline Overview

This document describes the end-to-end feature development pipeline managed by the feature-forge plugin. All forge skills reference this document to understand the overall flow and their position within it.

The pipeline compiles a fuzzy feature idea into a machine-executable `backlog.json`. Each stage narrows the idea down and adds structure, verification gates catch gaps before they reach later stages, and a swappable autonomous loop runner (rauf by default) implements the backlog in fresh per-item sessions.

## Pipeline Stages

```
[forge-0-epic] → forge-1-prd → forge-2-tech → forge-3-specs → forge-verify → forge-4-backlog → forge-verify → forge-5-loop → forge-verify → forge-6-docs
   (optional)
```

### Stage 0: Epic (`/feature-forge:forge-0-epic <epic>`), optional
**Input:** A change too large for one feature
**Output:** `{specsDir}/{epic}/epic-manifest.json` + `EPIC.md` + one member-feature dir per feature
**Method:** Decomposition interview splitting the change into member features with declared dependencies and `exposes`/`consumes` contracts. Purely additive: single-feature flows are unchanged. See [docs/architecture/epic-orchestration/README.md](../docs/architecture/epic-orchestration/README.md).

### Stage 1: PRD (`/feature-forge:forge-1-prd <feature>`)
**Input:** User's feature idea and domain knowledge
**Output:** `{specsDir}/{feature}/PRD.md`
**Method:** Structured interview focused exclusively on requirements. No technology decisions.

### Stage 2: Tech Spec (`/feature-forge:forge-2-tech <feature>`)
**Input:** PRD.md
**Output:** `{specsDir}/{feature}/tech-spec.md`
**Method:** Structured interview for technology decisions, grounded in PRD requirements.

### Stage 3: Implementation Specs (`/feature-forge:forge-3-specs <feature>`)
**Input:** PRD.md + tech-spec.md
**Output:** `{specsDir}/{feature}/##-<name>.md` (suite of numbered documents)
**Method:** Generate detailed implementation documents from spec archetypes.

### Verification Gate (`/feature-forge:forge-verify <feature>`)
**Input:** All artifacts from current and prior stages
**Output:** `{specsDir}/{feature}/.verification/VERIFY-<stage>-<timestamp>.md` (includes both findings and a Fix Execution Plan)
**Method:** Clean-context analysis producing actionable findings with an ordered fix plan.

After verification, fixes can be applied via:
- `/feature-forge:forge-fix <feature>` — reads the Fix Execution Plan from the findings document and applies changes (works in any session)
- Plan mode workflow — enter plan mode, run verify, review plan, exit and execute
- Manual — read findings and apply fixes by hand

### Stage 4: Backlog (`/feature-forge:forge-4-backlog <feature>`)
**Input:** Full spec suite
**Output:** `{specsDir}/{feature}/backlog.json` (or `{backlogDir}/{feature}/backlog.json` if backlogDir is configured)
**Method:** Generate structured backlog items with spec references, acceptance criteria, and dependencies. Backlog is collocated with feature specs by default.

### Stage 5: Rauf Loop (`/feature-forge:forge-5-loop <feature>`)
**Input:** `backlog.json` from Stage 4
**Output:** Implemented source code (committed per-item by rauf)
**Method:** Execute the autonomous coding loop against the feature's backlog. Spawns a fresh session per backlog item with full spec context. rauf is the default runner but is swappable via the `loopRunner` block in `forge.config.json`; see [`references/ralph-loop-contract.md`](./ralph-loop-contract.md).

### Stage 6: Documentation (`/feature-forge:forge-6-docs <feature>`)
**Input:** Specs + implementation
**Output:** `{docsDir}/{feature}/` documentation suite
**Method:** Generate developer-focused architecture documentation.

## Pipeline State

State is tracked in `{specsDir}/{feature}/.pipeline-state.json` and persists across session clears. The `/feature-forge:forge <feature>` navigator reads this file to show current progress.

## Git Discipline

Every stage completion should be followed by a git commit:
- Commit message format: `{commitPrefix}({feature}): <action>`
- Examples: `forge(auth): complete PRD v1`, `forge(auth): apply spec verification fixes`
- Before applying verification fixes, commit current state first (so pre-fix state is recoverable)
- After applying fixes, commit again

## Configuration

Read `forge.config.json` from project root for path overrides. See `references/forge-config-schema.json` for the full schema. If no config file exists, use defaults:
- specsDir: `./specs`
- docsDir: `./docs/architecture`
- backlogDir: (null — backlog defaults to {specsDir}/{feature}/backlog.json)
- gitCommitAfterStage: `true`
- commitPrefix: `forge`

## Git Workflow

Recommended: forge work lives on an isolated `forge/{feature}` (or `forge/{epic}`) branch so all commits land together and review as one branch. The entry stages (`forge-1-prd`, `forge-0-epic`) detect whether you're on the default branch (main/master) and **strongly recommend** creating that branch when you are — still letting you decline and stay. The chosen branch is recorded in `.pipeline-state.json`, and `forge-5-loop` re-checks it before the autonomous loop starts committing per item. After implementation, merge to your development branch.

To customize: `branchPrefix` (default `forge/`) sets the branch name, and `branchPerFeature: false` disables the prompt entirely (forge then works on whatever branch is checked out). Branch Setup is gated only on the project using git — independent of `gitCommitAfterStage`.

If you prefer manual commit control, set `gitCommitAfterStage: false` in `forge.config.json`.

## Cross-Cutting Concerns

### Feature Name is Required
Every forge skill requires a feature name as the first argument. If not provided, STOP and ask. Never guess.

### Reference Existing Code
When creating specs, always examine the existing codebase for patterns, conventions, and integration points. Check:
- Other feature specs in `{specsDir}/`
- Existing documentation in `{docsDir}/`
- Module/package structure and exports in the project
- Shared types, utilities, and conventions

### Stack Context
The project's stack is detected during forge-2-tech and persisted in `forge.config.json` (the `stack`, `typeCheckCommand`, and `testCommand` fields). See `references/stack-resolution.md` for the full resolution protocol. The project may also have a `stack-decisions.md` in `.claude/references/` with established technology decisions — if present, it takes highest precedence.

## Subagents

The plugin includes three specialized subagents in `agents/` that enhance specific
pipeline steps. They use **model aliases** (`opus`/`sonnet`) rather than pinned IDs, so
they track the current model tier automatically.

### forge-verifier
- **Purpose:** Read-only verification of pipeline artifacts
- **Used by:** `forge-verify` skill (delegation via Agent tool)
- **Tools:** Read, Glob, Grep, Bash (read-only operations only)
- **Model:** Opus (judgement-heavy gap/inconsistency analysis)
- **Memory:** Project-scoped persistent memory — accumulates knowledge about recurring issues and project-specific patterns across sessions
- **Parallel:** For large modes (specs/backlog/impl), `forge-verify` dispatches several instances in parallel, one per **dimension group** (e.g. types/contracts, traceability, testing), and the parent merges their findings. An opt-in adversarial "deep verify" pass re-checks high-severity findings with a skeptic instance to cut false positives. A purely mechanical dimension (e.g. traceability validation) could run on a cheaper tier (Haiku) if cost matters.
- **Why a subagent:** Verification reads the entire spec suite, backlog, and potentially source code. Running this in a separate context window prevents context pressure on the main conversation. The read-only tool restriction also makes it impossible to accidentally modify specs during verification.

### forge-researcher
- **Purpose:** Codebase exploration and integration mapping
- **Used by:** `forge-2-tech` skill (spawned before the tech-spec interview)
- **Tools:** Read, Glob, Grep, Bash (read-only)
- **Model:** Sonnet (cost-efficient for exploration tasks)
- **Parallel:** For a large codebase or uncertain scope, `forge-2-tech` may dispatch several researchers in parallel, each with a disjoint focus (structure/conventions, per-subsystem integration surfaces), and merge the reports.
- **Why a subagent:** Tech-spec planning requires reading many files across the project to understand integration points. Running this in a separate context returns a concise report without consuming the main session's context, keeping the interview focused.

### forge-spec-writer
- **Purpose:** Author exactly one numbered implementation spec document to the forge-3-specs quality bar
- **Used by:** `forge-3-specs` skill (parallel fan-out after the shared foundation docs are written)
- **Tools:** Read, Glob, Grep, Bash, **Write** (the only authoring agent — constrained to write its single assigned file)
- **Model:** Opus (spec authoring is detail- and judgement-heavy)
- **Why a subagent:** Authoring the whole suite in the main session serializes the work and pressures context. Writing the foundation (00/01) first, then fanning out one writer per remaining doc, parallelizes authoring while the parent keeps the cross-reference + traceability finish in view.

All three subagents are optional. If the agents are not installed or the environment doesn't support subagents, the corresponding skills fall back to running inline (or, for spec authoring, batched in the main session).
