# Feature Forge Pipeline Overview

This document describes the end-to-end feature development pipeline managed by the feature-forge plugin. All forge skills reference this document to understand the overall flow and their position within it.

## Pipeline Stages

```
forge-1-prd → forge-2-tech → forge-3-specs → forge-verify → forge-4-backlog → forge-verify → forge-5-ralph-loop → forge-verify → forge-6-docs
```

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
**Output:** `{specsDir}/{feature}/backlog.json` (or `{backlogDir}/backlog.json` if backlogDir is configured)
**Method:** Generate structured backlog items with spec references, acceptance criteria, and dependencies. Backlog is collocated with feature specs by default.

### Stage 5: Ralph Loop (`/feature-forge:forge-5-ralph-loop <feature>`)
**Input:** `backlog.json` from Stage 4
**Output:** Implemented source code (committed per-item by ralph)
**Method:** Execute the ralph autonomous coding loop against the feature's backlog. Spawns a fresh Claude Code session per backlog item with full spec context.

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

Recommended: create a `forge/{feature}` branch before starting the pipeline. All forge commits go to this branch. After implementation, merge to your development branch.

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

The plugin includes two specialized subagents in `agents/` that enhance specific pipeline steps:

### forge-verifier
- **Purpose:** Read-only verification of pipeline artifacts
- **Used by:** `forge-verify` skill (delegation via Agent tool)
- **Tools:** Read, Glob, Grep, Bash (read-only operations only)
- **Memory:** Project-scoped persistent memory — accumulates knowledge about recurring issues and project-specific patterns across sessions
- **Why a subagent:** Verification reads the entire spec suite, backlog, and potentially source code. Running this in a separate context window prevents context pressure on the main conversation. The read-only tool restriction also makes it impossible to accidentally modify specs during verification.

### forge-researcher
- **Purpose:** Codebase exploration and integration mapping
- **Used by:** `forge-2-tech` skill (spawned before the tech-spec interview)
- **Tools:** Read, Glob, Grep, Bash (read-only)
- **Model:** Sonnet (cost-efficient for exploration tasks)
- **Why a subagent:** Tech-spec planning requires reading many files across the project to understand integration points. Running this in a separate context returns a concise report without consuming the main session's context, keeping the interview focused.

Both subagents are optional. If the agents are not installed or the environment doesn't support subagents, the corresponding skills fall back to running inline.
