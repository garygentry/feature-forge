---
name: forge-3-specs
description: "Generate numbered implementation spec documents from PRD and tech spec in the forge pipeline. Use when user runs /feature-forge:forge-3-specs or asks to create detailed implementation specs for a forge feature after tech spec completion. Do NOT trigger for general specification writing, design docs, or implementation planning outside the forge pipeline."
argument-hint: "<feature-name>"
disable-model-invocation: true
---

# forge-3-specs — Implementation Spec Suite Generator

Generate a comprehensive suite of numbered implementation specification documents that provide everything needed to implement a feature.

## Prerequisites

Read and follow `references/shared-conventions.md` for feature name validation, configuration reading, and force mode handling before proceeding.

## Step 1: Validate Prerequisites

**Prerequisite check:** Read `{specsDir}/{feature}/.pipeline-state.json`. If not in force mode, both `forge-1-prd` and `forge-2-tech` must be `complete`. If not, STOP and tell the user which prerequisites are missing.

Read both `{specsDir}/{feature}/PRD.md` and `{specsDir}/{feature}/tech-spec.md` into context.

## Step 2: Examine Existing Context

1. **Read the PRD and tech spec thoroughly**: These are your source of truth
2. **Examine the existing codebase**: Look at how other packages are structured, what patterns they follow, what types they export
3. **Check other features' implementation specs**: Look at `{specsDir}/*/[0-9][0-9]-*.md` for consistency in format and depth
4. **Read integration target code**: For every package listed as an integration point in the tech spec, read its actual source — types, exports, patterns. For every integration point, include the EXACT function signature and import path you read from the source code. Include the file path where you found it. If you cannot locate an expected export, say so explicitly: 'WARNING: Could not locate X export in {module} — verify this exists before implementing.'
5. **Read spec examples**: Read `references/spec-examples.md` for the expected depth and quality of spec sections. These examples are your quality bar.

## Step 3: Plan the Document Suite

Read `references/spec-archetypes.md` for the menu of document types.

Based on the feature's complexity, propose a document plan to the user before writing:

```
I'll create the following spec documents for {feature}:

Required:
  00-core-definitions.md     — Type definitions, error hierarchy, shared contracts
  01-architecture-layout.md   — Directory structure, exports map, dependency graph
  NN-testing-strategy.md      — Test approach, coverage targets, fixture patterns

Feature-specific:
  02-{subsystem-a}.md         — {Brief description}
  03-{subsystem-b}.md         — {Brief description}
  04-integration-points.md    — Integration with existing project modules

Does this look right? Should I add or remove any documents?
```

Wait for user confirmation before proceeding.

### Context Management

If the spec suite requires more than 5 documents:
1. Write documents in batches of 3-5
2. After each batch, present to the user for review
3. If `gitCommitAfterStage` is true:
     `git add {specsDir}/{feature}/ && git commit -m "{commitPrefix}({feature}): specs batch {n}"`
4. For the next batch, re-read only the shared types document (00-core-definitions.md) and the specific upstream docs relevant to the next batch — do not re-load everything
5. Continue until all documents are complete

This prevents quality degradation from context pressure. The first documents you write should be the foundation (types, architecture) since later documents reference them.

**Incremental artifact tracking:** After writing each spec document, immediately update the `artifacts` array in `.pipeline-state.json` with the new file path. This enables crash recovery if the session is interrupted mid-batch (see shared-conventions.md "Crash Recovery").

## Step 4: Write the Spec Suite

For each document:

1. Number sequentially: `00-`, `01-`, `02-`, etc.
2. Every implementation detail MUST trace to either a PRD requirement (REQ-XXX-NN) or a tech-spec decision
3. Before writing each spec document, include a `## Requirement Coverage` table at the top mapping every REQ-XXX-NN this document covers to the section that implements it
4. Include complete type definitions, data structures, and function signatures in the project's language — not pseudocode. If a stack profile exists at `references/stacks/{stack}.md` (where `{stack}` comes from `forge.config.json`), follow its conventions for type definitions, error hierarchies, and documentation comments.
5. Include error handling for every operation
6. Include example usage where it aids clarity
7. Cross-reference other spec documents by filename when one document depends on definitions from another

### Document Conventions

- Filename format: `{specsDir}/{feature}/##-<descriptive-name>.md`
- Each document should be self-contained enough that an engineer could implement it without reading other spec docs (though cross-references help for context)
- Include a "Dependencies" section listing which other spec docs must be implemented first
- Include a "Verification" section describing how to confirm the implementation matches the spec

## Step 5: Cross-Reference Validation

After writing all documents, verify:

1. Every PRD requirement has coverage in at least one spec document
2. Every tech-spec decision is reflected in the implementation specs
3. Cross-references between spec documents are consistent (no broken references)
4. Type definitions used across documents are consistent
5. No orphaned implementation details that don't trace to requirements
6. Produce a traceability matrix: a markdown table mapping every REQ-XXX-NN from the PRD to the spec document and section that implements it. Write this to `{specsDir}/{feature}/TRACEABILITY.md`

List any gaps or inconsistencies found and resolve them.

## Step 6: Review with User

Present a summary of all documents created, with key decisions highlighted. Ask:
- "Does the level of detail match what you need?"
- "Any areas that need more depth?"
- "Any missing subsystems or concerns?"

## Step 7: Update Pipeline State and Commit

Write pipeline state conforming to `references/pipeline-state-schema.json`.

1. Update `{specsDir}/{feature}/.pipeline-state.json`:
   - Set `currentStage` to `forge-4-backlog` (or verification if they want to verify first)
   - Record all created files in `artifacts`, including `TRACEABILITY.md`
   - Set `stages.forge-3-specs.basedOnVersions` to `{"forge-1-prd": <current version>, "forge-2-tech": <current version>}`
   - Check downstream stages (forge-4-backlog, forge-5-docs). If any have `basedOnVersions` referencing older versions, set their status to `stale`
2. Ask about notes to persist
3. If `gitCommitAfterStage` is true, follow the Git Commit Protocol in `references/shared-conventions.md`: stage files, attempt commit with message `"{commitPrefix}({feature}): complete implementation specs v{n}"`, then set `stages.forge-3-specs.status` to `complete` with commit hash only on success. If commit fails, leave status as `in-progress`.
5. Tell user next steps: `/feature-forge:forge-verify {feature}` (strongly recommended) or `/feature-forge:forge-4-backlog {feature}`

## Gotchas

- Don't create specs for things that are already fully specified in the tech spec. If the tech spec has complete type definitions, the implementation spec should reference them, not duplicate them.
- Every spec document should include complete type definitions and function signatures in the project's language with documentation comments. The backlog generator and implementing engineer depend on these being exact, not approximate.
- Resist the urge to create too many documents. Each document should represent a major concern. If a "document" would be under 50 lines, it probably belongs as a section in another document.
- Watch for implicit dependencies between subsystems. If subsystem A's types are used by subsystem B, the spec should explicitly state this and ensure the types are defined in the shared types document.
- If the feature is large, the spec suite might be 8-12 documents. If it's simple, 3-4 is fine. Match complexity to the feature, not a fixed template.
