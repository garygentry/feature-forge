---
name: forge-6-docs
description: "Generate developer-focused architecture documentation for a forge pipeline feature. Use when user runs /feature-forge:forge-6-docs or asks to generate docs after implementation is complete. Do NOT trigger for general documentation writing, README creation, or doc generation outside the forge pipeline."
argument-hint: "<feature-name>"
---

# forge-6-docs — Architecture Documentation Generator

Generate developer-focused architecture documentation for a feature, suitable for onboarding, reference, and maintenance.

## Prerequisites

Read and follow `references/shared-conventions.md` for feature name validation, configuration reading, and force mode handling before proceeding.

**Turn structure reminder:** Output analysis/context as text, then route ALL questions through `AskUserQuestion`. Never embed questions in text output — the user will not be prompted and the session will stall.

## Step 1: Read Context

Read `{specsDir}/{feature}/.pipeline-state.json` to understand what exists.

### Gather Sources

Load into context:
1. **Specs**: PRD.md, tech-spec.md, all implementation specs
2. **Implementation**: Read the actual source code for this feature's package
3. **Existing docs**: Check `{docsDir}/` for other features' docs to match conventions
4. **README**: Check if the feature package has its own README.md

### Implementation Completeness Check

Check `{specsDir}/{feature}/backlog.json` (or `{backlogDir}/backlog.json` if configured). Count items with status `complete` vs total. If implementation is less than 80% complete, use `AskUserQuestion` to warn: "Implementation is only N% complete. Documentation will be based primarily on specs and may need updates after implementation. Proceed?" If user proceeds, add a `PRE-IMPLEMENTATION` notice at the top of each generated doc.

Also check `.pipeline-state.json` for `stages.forge-5-rauf-loop`. If it exists and has status `in-progress` (some items incomplete), include this in the warning: "The rauf loop has not fully completed — {done}/{total} items done. Documentation may need updates after remaining items are implemented."

Read `references/doc-conventions.md` for documentation standards.

## Step 2: Plan Documentation Structure

Based on feature complexity and existing doc conventions, propose a doc plan:

**Minimum (simple feature):**
```
{docsDir}/{feature}/
├── README.md          — Overview, quick start, key concepts
└── api-reference.md   — Exported APIs, types, configuration
```

**Standard (typical feature):**
```
{docsDir}/{feature}/
├── README.md          — Overview, quick start, key concepts
├── architecture.md    — Design decisions, data flow, component relationships
├── api-reference.md   — Exported APIs, types, configuration
└── guides/
    └── integration.md — How to integrate this feature into an app
```

**Comprehensive (complex feature):**
```
{docsDir}/{feature}/
├── README.md          — Overview, quick start, key concepts
├── architecture.md    — Design decisions, data flow, component relationships
├── api-reference.md   — Exported APIs, types, configuration
├── configuration.md   — All configuration options with examples
├── guides/
│   ├── getting-started.md  — Step-by-step setup
│   ├── integration.md      — How to integrate with other packages
│   └── troubleshooting.md  — Common issues and solutions
└── decisions/
    └── adr-001-*.md   — Architecture decision records (if significant decisions were made)
```

Present the plan and use `AskUserQuestion` to get the user's confirmation.

## Step 3: Write Documentation

### Key Principles

**Write for the reader, not the writer.**
- A developer encountering this feature for the first time should be able to understand it from the docs alone
- Lead with the "what" and "why" before the "how"
- Include code examples for every exported API
- Don't assume familiarity with the spec documents

**Be accurate to the implementation, not the spec.**
- If the implementation diverged from the spec, document the implementation
- Specs are the source of truth for design intent; code is the source of truth for behavior
- Read the actual source code to verify your documentation is correct

**Match existing conventions.**
- If other features' docs use a specific heading structure, follow it
- If they include diagrams, include diagrams
- If they use a specific tone (formal, casual, tutorial-style), match it

### README.md Structure

```markdown
# {Feature Name}

{One-paragraph description of what this feature does and why it exists.}

## Quick Start

{Minimal code to get started — import, configure, use.}

## Key Concepts

{Explain the domain model and core abstractions in plain language.}

## Package Exports

{Table of subpath exports and what each contains.}

| Export / Entry Point | Description |
|---------------------|-------------|
| `{module}` | Shared types and utilities |
| `{module}/server` | Server-side functionality |
| ...    | ... |

Adapt export paths to match the project's module/package conventions.

## Configuration

{Key configuration options with defaults.}

## Further Reading

- [Architecture](./architecture.md) — Design decisions and data flow
- [API Reference](./api-reference.md) — Complete API documentation
- [Integration Guide](./guides/integration.md) — How to use with other packages
```

## Step 4: Review with User

Present the docs as text. Then use `AskUserQuestion` to collect feedback — do NOT include these questions in your text output:

"1. Does this accurately reflect the implementation? 2. Is the level of detail appropriate for your team? 3. Any areas that need more explanation?"

## Step 5: Update Pipeline State and Commit

Write pipeline state conforming to `references/pipeline-state-schema.json`.

1. Update `{specsDir}/{feature}/.pipeline-state.json`:
   - Set `currentStage` to `complete`
   - Record `artifacts`
   - Set `stages.forge-6-docs.basedOnVersions` to include versions for all completed upstream stages. Always include forge-1-prd, forge-2-tech, forge-3-specs. Include forge-4-backlog and forge-5-rauf-loop ONLY if they have status `complete`.
2. If `gitCommitAfterStage` is true, follow the Git Commit Protocol in `references/shared-conventions.md`: stage files (`git add {docsDir}/{feature}/ {specsDir}/{feature}/`), attempt commit with message `"{commitPrefix}({feature}): complete architecture docs"`, then set `stages.forge-6-docs.status` to `complete` with commit hash only on success. If commit fails, leave status as `in-progress`.
4. Tell user: "Documentation complete. Feature pipeline for '{feature}' is finished!\n  `/feature-forge:forge {feature}` to see the final pipeline status."

## Gotchas

- Don't just rephrase the specs. Documentation should explain the implemented system, not the planned system. Read the actual code.
- If the implementation doesn't exist yet (backlog hasn't been run), document based on specs but note prominently that docs are pre-implementation and may need updating.
- API reference should include actual function signatures from the code, not from the spec (they may differ).
- Don't generate docs that will immediately be stale. Focus on concepts, architecture, and patterns rather than line-by-line code walkthroughs.
- Include "When to use" and "When NOT to use" sections — they save developers more time than any other documentation pattern.
