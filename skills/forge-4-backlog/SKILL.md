---
name: forge-4-backlog
description: "Generate a structured ralph backlog.json from forge implementation specs. Use when user runs /feature-forge:forge-4-backlog or asks to create a backlog for a forge feature after specs are complete. This is the canonical backlog generator for the forge pipeline — create-ralph-backlog in ralph-support is deprecated in favor of this skill. Do NOT trigger for standalone backlog creation outside the forge pipeline context."
argument-hint: "<feature-name>"
disable-model-invocation: true
---

# forge-4-backlog — Ralph Backlog Generator

Generate a complete, validated backlog.json from the implementation spec suite, ready for the ralph loop.

## Prerequisites

Read and follow `references/shared-conventions.md` for feature name validation, configuration reading, and force mode handling before proceeding.

Backlog defaults to `{specsDir}/{feature}/backlog.json`. If `backlogDir` is set in config, write to `{backlogDir}/backlog.json` instead.

## Step 1: Validate Prerequisites

**Prerequisite check:** Read `{specsDir}/{feature}/.pipeline-state.json`. If not in force mode, stages `forge-1-prd`, `forge-2-tech`, and `forge-3-specs` must all be `complete`. If not, STOP and tell the user which prerequisites are missing.

**Strongly recommended:** Check if `forge-verify-specs` has been run. If not, warn: "Specs haven't been verified yet. It's recommended to run `/feature-forge:forge-verify {feature}` first. Continue anyway?"

## Step 2: Load All Specs

Read all spec documents into context:
- `{specsDir}/{feature}/PRD.md`
- `{specsDir}/{feature}/tech-spec.md`
- `{specsDir}/{feature}/##-*.md` (all implementation specs)

Also read:
- `references/backlog-schema.json` for the exact JSON schema
- `references/backlog-examples.md` for gold-standard example items

If the spec suite is large (8+ documents), focus on loading the architecture layout (01-*), shared types (00-*), and testing strategy documents first. Load individual subsystem specs as needed when writing the corresponding backlog items, rather than loading all specs simultaneously.

## Step 3: Plan the Backlog

Before writing any JSON, create a backlog plan:

1. Identify all discrete work items by walking through the specs
2. Order them by dependency (foundation first, then layers)
3. Assign priorities (lower number = higher priority)
4. Check that each item is scoped for a single ralph loop iteration

Present the plan as a numbered list:
```
Proposed backlog for {feature} ({N} items):

  001 [P1] Scaffold module with project manifest, build config, and entry points
      Depends on: (none)
      Specs: 00-core-definitions.md, 01-architecture-layout.md

  002 [P1] Implement shared types and error hierarchy
      Depends on: 001
      Specs: 00-core-definitions.md

  003 [P2] Implement provider registry
      Depends on: 002
      Specs: 02-provider-registry.md
  ...
```

Ask the user: "Does this breakdown look right? Any items to split, merge, or reorder?"

Wait for confirmation before generating the JSON.

## Step 4: Generate backlog.json

Write `{specsDir}/{feature}/backlog.json` (or `{backlogDir}/backlog.json` if backlogDir is configured) following the schema EXACTLY. Read `references/backlog-schema.json` to confirm the structure.

### Item Quality Requirements

**Every item MUST have:**

- `id`: Zero-padded sequential string ("001", "002", etc.)
- `type`: One of "feature", "bugfix", "chore", "refactor", "test", "docs"
- `priority`: Integer, lower = higher priority. Items with no dependencies get lowest numbers.
- `title`: Concise (under 100 chars), describes what is created/changed
- `description`: Detailed enough for a FRESH AGENT with NO prior context to implement. Include:
  - Exact files to create or modify
  - Exact types, interfaces, or functions to implement (reference spec sections)
  - Exact import paths
  - Any gotchas or special considerations
  - Steps numbered 1, 2, 3...
- `acceptanceCriteria`: Array of objectively verifiable strings. Each criterion should be checkable by running a command or reading code. NOT subjective ("works well") but specific ("{typeCheckCommand} passes for {module}" — use the values from `forge.config.json`, e.g., "bun run typecheck passes for @repo/auth", "mypy src/auth/ passes", "go vet ./auth/... passes")
- `status`: "pending" for all new items
- `completedAt`: null
- `dependsOn`: Array of item IDs this item requires to be complete first
- `notes`: Any additional context, warnings, or tips
- `estimatedIterations`: Integer, almost always 1. Use 2+ only for genuinely large items that can't be broken down further.
- `specReferences`: Array of relative paths to spec files this item implements. Spec references must be paths relative to the project root (e.g., `specs/auth/00-core-definitions.md`), NOT relative to the backlog file location.

### Granularity Rules

- Each item should produce a WORKING increment — after completing it, the code should typecheck and any new tests should pass
- An item should touch at most 5-8 files (fewer is better)
- If an item's description exceeds 300 words, STOP and split it before continuing. If an item modifies more than 6 files, it MUST be split — no exceptions. These are hard limits, not suggestions
- Foundation items (scaffold, types, errors) should be separate from feature items
- Integration wiring (connecting the new feature to existing packages) should be its own item(s), not buried in feature items
- Test items can be standalone or integrated into feature items via acceptance criteria — match what the user prefers

## Step 5: Validate

Run the validation script bundled with this skill:

```bash
python ${CLAUDE_PLUGIN_ROOT}/scripts/validate-backlog.py {specsDir}/{feature}/backlog.json --specs-dir {specsDir}/{feature}
```

If validation fails, fix the issues and re-validate. Do NOT present the backlog to the user until validation passes.

## Step 6: Review with User

Present a summary:
- Total items: N
- Dependency chain depth: N levels
- Estimated ralph loop iterations: N

Ask: "Ready to proceed, or any adjustments needed?"

## Step 7: Update Pipeline State and Commit

Write pipeline state conforming to `references/pipeline-state-schema.json`. Follow the Git Commit Protocol in `references/shared-conventions.md`.

1. Update `{specsDir}/{feature}/.pipeline-state.json`:
   - Record `artifacts` (path to backlog.json)
   - Set `stages.forge-4-backlog.basedOnVersions` to `{"forge-1-prd": <current version>, "forge-2-tech": <current version>, "forge-3-specs": <current version>}`
   - Check downstream stage (`forge-5-docs`). If it has `basedOnVersions` referencing an older version of `forge-4-backlog`, set its status to `stale`.
2. Ask about notes to persist
3. If `gitCommitAfterStage` is true, follow the Git Commit Protocol: stage files, attempt commit, then set status to `complete` with commit hash only on success. If commit fails, leave status as `in-progress`.
4. If verification was available but the user chose to skip it, record `stages.forge-verify-backlog.status` as `"skipped"` in pipeline state.
5. Tell user: "Backlog complete with {N} items. Next steps:\n  - `/feature-forge:forge-verify {feature}` to verify the backlog\n  - Run the ralph loop externally to implement\n  - `/feature-forge:forge {feature}` to see full pipeline status"

## Gotchas

- The ralph loop runs each item in a FRESH context. Every item description must be self-contained. Don't write "same as above" or "continue from previous item."
- Spec references must be relative paths that actually exist. Validate them.
- The most common backlog mistake is items that are too large. If an item creates more than 3-4 files AND implements complex logic, it should probably be split.
- The second most common mistake is missing dependency declarations. If item 005 imports types created by item 002, it MUST list "002" in dependsOn, even if it seems obvious.
- Acceptance criteria like "code works correctly" are useless. Instead: "ProviderRegistry.get('openai') returns an OpenAI provider instance" or "bun test src/server/registry.test.ts passes".
- Don't forget items for module scaffold, entry point exports, and initial configuration. These are easy to skip but block everything.
