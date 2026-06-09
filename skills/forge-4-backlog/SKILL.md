---
name: forge-4-backlog
description: "Generate a structured backlog.json from forge implementation specs, then validate it via the loop runner. Use when user runs /feature-forge:forge-4-backlog or asks to create a backlog for a forge feature after specs are complete. This is the canonical backlog generator for the forge pipeline. Do NOT trigger for standalone backlog creation outside the forge pipeline context."
argument-hint: "<feature-name>"
---

# forge-4-backlog — Backlog Generator (pipeline orchestrator)

Generate a complete, validated `backlog.json` from the implementation spec
suite, ready for the loop runner.

This skill is a **thin orchestrator**: it owns the *pipeline* concerns
(prerequisite checks, spec loading, plan review, validation, pipeline-state and
commit). The actual **authoring craft** — granularity, acceptance criteria,
`agentDelegation`, the schema, examples — lives in the rauf plugin's
**`author-backlog`** skill, which this skill delegates to. That keeps a single
home for backlog-authoring knowledge, shared with the repo-wide ad-hoc flow.

## Prerequisites

Read and follow `references/shared-conventions.md` for feature name validation, configuration reading, and force mode handling before proceeding.

Resolve the **backlog directory** `{backlogDir}`:
- If `backlogDir` is set in `forge.config.json`: `{backlogDir}`.
- Otherwise: `{specsDir}/{feature}` (backlog.json lands at `{specsDir}/{feature}/backlog.json`).

Resolve the **loop runner** from the `loopRunner` block in `forge.config.json`, filling missing fields from the defaults in `references/forge-config-schema.json` (defaults to rauf). You need its `bin`, `validateCommand`, `versionCommand`, `minRunnerVersion`, and `installHint`.

**Turn structure reminder:** Output analysis/context as text, then route ALL questions through `AskUserQuestion`. Never embed questions in text output — the user will not be prompted and the session will stall.

## Step 1: Validate Prerequisites

**Prerequisite check:** Read `{specsDir}/{feature}/.pipeline-state.json`. If not in force mode, stages `forge-1-prd`, `forge-2-tech`, and `forge-3-specs` must all be `complete`. If not, STOP and tell the user which prerequisites are missing.

**Strongly recommended:** Check if specs have been verified. If not, use `AskUserQuestion` to warn: "Specs haven't been verified yet. It's recommended to run `/feature-forge:forge-verify {feature}` first. Continue anyway?"

## Step 2: Load All Specs

Read all spec documents into context:
- `{specsDir}/{feature}/PRD.md`
- `{specsDir}/{feature}/tech-spec.md`
- `{specsDir}/{feature}/##-*.md` (all implementation specs)

If the spec suite is large (8+ documents), focus on loading the architecture layout (01-*), shared types (00-*), and testing strategy documents first. Load individual subsystem specs as needed when writing the corresponding backlog items, rather than loading all specs simultaneously.

## Step 3: Plan the Backlog

Before writing any JSON, walk the specs and create a backlog plan: discrete work items, ordered by dependency (foundation first), with priorities, each scoped for a single loop iteration.

Present the plan as a numbered list:
```
Proposed backlog for {feature} ({N} items):

  001 [P1] Scaffold module with project manifest, build config, and entry points
      Depends on: (none)
      Specs: 00-core-definitions.md, 01-architecture-layout.md

  002 [P1] Implement shared types and error hierarchy
      Depends on: 001
      Specs: 00-core-definitions.md
  ...
```

After presenting the plan as text, use `AskUserQuestion` to ask: "Does this breakdown look right? Any items to split, merge, or reorder?" Do NOT include this question in your text output. Wait for the user's response before generating the JSON.

## Step 4: Author backlog.json — delegate to `author-backlog`

**Invoke the rauf plugin's `author-backlog` skill** (via the Skill tool) to write
`{backlogDir}/backlog.json`. Pass it:

- the target backlog directory `{backlogDir}`,
- the approved plan from Step 3,
- the spec context loaded in Step 2,
- the project's `typeCheckCommand` / `testCommand` (from `forge.config.json`) so acceptance criteria are concrete and runnable.

`author-backlog` owns all item-quality rules (granularity hard limits, self-contained descriptions, acceptance criteria, `agentDelegation`, the correct `type`/`status` enums, `dependsOn`, `specReferences`, the schema source). Do not re-encode them here — follow whatever it produces.

> **If the rauf plugin / `author-backlog` skill is not available:** fall back to
> authoring inline using the schema source rule (prefer the project's installed
> `{stateDir}/backlog.schema.json`, else the published `$id`
> `https://raw.githubusercontent.com/garygentry/rauf/main/schemas/backlog.schema.json`),
> and tell the user the rauf plugin provides richer authoring guidance.

**Forge-specific item requirements** layered on top of `author-backlog`'s output:
- `specReferences` must be paths **relative to the project root** (e.g. `specs/auth/00-core-definitions.md`), NOT relative to the backlog file. The validator resolves them from the project root (not from `--specs-dir`, which only gates the check).

## Step 5: Validate via the loop runner

Validate the generated backlog by running the runner's **validate command**
(`loopRunner.validateCommand`), rendered with `{backlogDir}` and `{specsDir}`
substituted — the rauf default:

```bash
rauf backlog validate . --backlog {backlogDir} --specs-dir {specsDir} --json
```

Interpret the result:
- **exit 0** → valid (warnings allowed). Proceed.
- **exit 1** → validation findings. Parse `{ valid, findings[] }`, fix the items, re-run. Do NOT present the backlog to the user until it validates.
- **exit 2** → usage/IO error (unreadable file, bad JSON). Fix and re-run.

> **forge-4 runs before forge-5's install gate**, so the runner may not be set
> up yet. Degrade gracefully rather than hard-failing:
> 1. First run `loopRunner.versionCommand` (`rauf version --json`). If the
>    binary is **missing**, or its version is **< `minRunnerVersion`**
>    (semver-compare), do NOT block authoring: keep the authored backlog, emit a
>    loud warning with `loopRunner.installHint`, mark validation as skipped, and
>    continue to Step 6. forge-5 will enforce the gate before running.
> 2. If the binary is present and new enough but the project isn't set up
>    (`validate` reports the project marker missing), likewise warn and continue
>    — validation will run cleanly once `rauf install .` has been done.

## Step 6: Review with User

Present a summary: total items N, dependency-chain depth, estimated loop iterations (`ceil(pendingItems * loopIterationMultiplier)`). Note whether validation passed or was skipped (runner not yet available).

Use `AskUserQuestion` to ask: "Ready to proceed, or any adjustments needed?"

## Step 7: Update Pipeline State and Commit

Write pipeline state conforming to `references/pipeline-state-schema.json`. Follow the Git Commit Protocol in `references/shared-conventions.md`.

1. Update `{specsDir}/{feature}/.pipeline-state.json`:
   - Record `artifacts` (path to backlog.json)
   - Set `stages.forge-4-backlog.basedOnVersions` to `{"forge-1-prd": <current version>, "forge-2-tech": <current version>, "forge-3-specs": <current version>}`
   - Set `currentStage` to `forge-5-loop`
   - Check downstream stages (`forge-5-loop`, `forge-6-docs`). If any have `basedOnVersions` referencing an older version of `forge-4-backlog`, set their status to `stale`.
2. Use `AskUserQuestion` to ask about notes to persist
3. If `gitCommitAfterStage` is true, follow the Git Commit Protocol: stage files, attempt commit, then set status to `complete` with commit hash only on success. If commit fails, leave status as `in-progress`.
4. If verification was available but the user chose to skip it, record `stages.forge-verify-backlog.status` as `"skipped"` in pipeline state.
5. Tell user: "Backlog complete with {N} items. Next steps:\n  - `/feature-forge:forge-verify {feature}` to verify the backlog\n  - `/feature-forge:forge-5-loop {feature}` to run the loop\n  - `/feature-forge:forge {feature}` to see full pipeline status"

## Gotchas

- The loop runs each item in a FRESH context. Every item description must be self-contained — `author-backlog` enforces this, but double-check Step-3 plan items aren't "same as above."
- Spec references must be project-root-relative paths that actually exist — the validate command enforces this when `--specs-dir` is passed (resolving them from the project root).
- Don't present a backlog to the user before it validates (or before you've explicitly recorded that validation was skipped because the runner isn't installed yet).
