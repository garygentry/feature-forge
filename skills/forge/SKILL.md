---
name: forge
description: "Feature-forge pipeline navigator and status dashboard. Use when the user references the forge pipeline, asks about forge status or progress, types /feature-forge:forge, or wants to check what stage a feature is at in the forge pipeline. Do NOT use for general feature requests, project status, or tasks unrelated to the forge development pipeline."
argument-hint: "<feature-name> (optional — lists all active features if omitted)"
---

# Feature Forge — Pipeline Navigator

You are the navigator for the feature-forge development pipeline. Your job is to orient the user: show where they are, what's been done, and what's next.

## Behavior

### 1. Read Configuration

Read and follow `references/shared-conventions.md` for configuration reading (feature name validation, config defaults, force mode).

For pipeline architecture details, read `references/process-overview.md`.

### 2. Determine Context

**If a feature name is provided** (e.g., `/feature-forge:forge auth`):
- Look for `{specsDir}/{feature}/.pipeline-state.json`
- If found, display the pipeline status dashboard (see format below)
- If not found, ask: "No pipeline exists for '{feature}'. Want to start one? Run `/feature-forge:forge-1-prd {feature}` to begin."

**If no feature name is provided:**
- Scan `{specsDir}/` for all subdirectories containing `.pipeline-state.json`
- If exactly one active (non-complete) pipeline exists, show its dashboard
- If multiple exist, list them all with a one-line summary each and ask which one to focus on
- If none exist, say: "No active feature pipelines found. Start one with `/feature-forge:forge-1-prd <feature-name>`."

The feature name must be a single kebab-case token. If the user provides multiple words (e.g., "user auth flow"), convert to kebab-case: `user-auth-flow`.

### 3. Pipeline Status Dashboard

Write pipeline state conforming to `references/pipeline-state-schema.json`.

Display a clear, scannable status for the feature:

```
Feature: {feature}  [active]
Stage: {currentStage} ({status}, started {relative time})

✅ forge-1-prd     → PRD.md (v{n})
⬜ forge-verify     (prd)          ← show only if forge-1-prd is complete
✅ forge-2-tech    → tech-spec.md (v{n}, ⚠️ not yet verified)
⬜ forge-verify     (tech)         ← show only if forge-2-tech is complete
🔄 forge-3-specs   → in progress
⬜ forge-verify     (specs)        ← show only if forge-3-specs is complete
⬜ forge-4-backlog
⬜ forge-verify     (backlog)      ← show only if forge-4-backlog is complete
⬜ forge-5-docs

Next: Continue with /feature-forge:forge-3-specs {feature}
      Or verify tech-spec with /feature-forge:forge-verify {feature}

Notes: "{any persisted notes}"
```

Use these status indicators:
- ✅ = complete
- ✅⚠️ = complete but not yet verified
- 🔄 = in progress
- ⬜ = pending
- ❌ = verification found issues (not yet fixed)
- ✅🔍 = verified and fixes applied
- ⏭️ = verification skipped (user chose to proceed without verifying)
- ⚠️ = stale (built against an older version of an upstream artifact)

### 4. Notes Management

If the user says something like "note: switching to jose for JWT" or "remember: we decided X", update the `notes` field in `.pipeline-state.json`. This helps preserve context across session clears.

### 5. Available Commands Reference

When showing the dashboard, include a compact reference:

```
Commands:
  /feature-forge:forge-1-prd <feature>      Create requirements document
  /feature-forge:forge-2-tech <feature>     Create technical spec
  /feature-forge:forge-3-specs <feature>    Create implementation specs
  /feature-forge:forge-4-backlog <feature>  Generate ralph backlog
  /feature-forge:forge-5-docs <feature>     Generate architecture docs
  /feature-forge:forge-verify <feature>     Run verification on current stage
```

### 6. Pipeline Lifecycle Commands

Support these sub-commands for pipeline lifecycle management:
- `/feature-forge:forge pause {feature}` — Set `pipelineStatus` to `"paused"`. Do NOT modify `currentStage` or any stage statuses. The pipeline freezes exactly as-is. Show a confirmation.
- `/feature-forge:forge resume {feature}` — Set `pipelineStatus` back to `"active"`. Calculate how long the feature was paused (from `updatedAt` to now). If paused for more than 24 hours, show a hint: "This feature was paused for {duration}. Session context may have been lost — consider re-running `/feature-forge:forge-{currentStage} {feature}` to rebuild context."
- `/feature-forge:forge abandon {feature}` — Set `pipelineStatus` to `"abandoned"`. Confirm with user first. Note: abandoned pipelines can be resumed with `/feature-forge:forge resume {feature}` if the user changes their mind.

When listing features, show active pipelines by default. Include a count of paused/abandoned: "3 active pipelines (1 paused, 1 abandoned — use `/feature-forge:forge list all` to see them)."

## Gotchas

- Never modify any spec files, backlog files, or pipeline state beyond the `notes`, `updatedAt`, and `pipelineStatus` fields. The navigator is read-only except for notes and lifecycle commands.
- If a user asks to "continue" or "pick up where I left off" without naming a feature, check for active pipelines before asking. Only ask if ambiguous.
- The pipeline state file is the source of truth. Don't infer stage from the existence of files alone — a file might exist from a previous incomplete run.
