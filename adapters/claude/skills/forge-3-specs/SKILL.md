---
# GENERATED — DO NOT EDIT. Source: skills/forge-3-specs/SKILL.md. Regenerate: python3 scripts/build-adapters.py
name: forge-3-specs
description: Generate numbered implementation spec documents from PRD and tech spec in the forge pipeline. Use when user runs /feature-forge:forge-3-specs or asks to create detailed implementation specs for a forge feature after tech spec completion. Do NOT trigger for general specification writing, design docs, or implementation planning outside the forge pipeline.
argument-hint: <feature-name>
---

# forge-3-specs — Implementation Spec Suite Generator

Generate a comprehensive suite of numbered implementation specification documents that provide everything needed to implement a feature.

## Prerequisites

Read and follow `references/shared-conventions.md` for feature name validation, configuration reading, and force mode handling before proceeding.

**Turn structure reminder:** Output analysis/context as text, then route ALL questions through `AskUserQuestion`. Never embed questions in text output — the user will not be prompted and the session will stall.

## Step 1: Validate Prerequisites

**Resolve the feature directory first** via the **Feature Directory Resolution** block in `references/shared-conventions.md`, setting `{resolvedFeatureDir}`.

**Prerequisite check:** Read `{resolvedFeatureDir}/.pipeline-state.json`. If not in force mode, both `forge-1-prd` and `forge-2-tech` must be `complete`. If not, STOP and tell the user which prerequisites are missing.

After the prerequisite check, invoke the **Stage-Entry Guard** block in `references/shared-conventions.md` with `{stage}` = `forge-3-specs`. Because this stage writes a suite incrementally, the guard's **interrupted** arm uses the `stages.forge-3-specs.artifacts` array (already updated after each spec file — Step 3) to resume from the first unwritten document rather than regenerating the whole suite.

Read both `{resolvedFeatureDir}/PRD.md` and `{resolvedFeatureDir}/tech-spec.md` into context.

After reading the PRD and tech spec, invoke the **Epic Context Injection** block in `references/shared-conventions.md`. It self-gates on the resolved feature's `epic` back-pointer: for a standalone feature it is a no-op; for an epic member it loads EPIC.md, this feature's charter, and the completed direct dependencies' specs into context before the spec suite is planned.

## Step 2: Examine Existing Context

1. **Read the PRD and tech spec thoroughly**: These are your source of truth
2. **Examine the existing codebase**: Look at how other packages are structured, what patterns they follow, what types they export
3. **Check other features' implementation specs**: Look at `{specsDir}/*/[0-9][0-9]-*.md` AND `{specsDir}/*/*/[0-9][0-9]-*.md` (depth-2, for epic-nested features) for consistency in format and depth. Subject to the **feature-shaped-dir bound**: only treat a matched directory as a feature if it directly contains a `.pipeline-state.json` (per the Feature Directory Resolution block) — ignore `EPIC.md` directories and other non-feature subtrees. Flat-only trees gain no new matches from the depth-2 glob, so standalone behavior is unchanged (REQ-COMPAT-01).
4. **Read integration target code**: For every package listed as an integration point in the tech spec, read its actual source — types, exports, patterns. For every integration point, include the EXACT function signature and import path you read from the source code. Include the file path where you found it. If you cannot locate an expected export, say so explicitly: 'WARNING: Could not locate X export in {module} — verify this exists before implementing.'
5. **Read spec examples**: Read `references/spec-examples.md` for the expected depth and quality of spec sections. These examples are your quality bar.

## Step 3: Plan the Document Suite

Read `references/spec-archetypes.md` for the menu of document types.

Based on the feature's complexity, propose a document plan to the user before writing. Output the document list as text, then use `AskUserQuestion` for the question — do NOT include the question in your text output.

**Example text output (no question here):**
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
```

**Then call `AskUserQuestion`** following the **Decision Support** protocol in `references/shared-conventions.md`: recommend this plan as the default (it's your evidence-backed read of the feature's complexity) and name the trade-off so the user can push back knowingly — more documents means finer separation of concerns but more to keep in sync; fewer means tighter docs but risks one document carrying multiple concerns. Lead with: "I recommend this plan. Add or remove any documents?" Note the guidance below — resist splitting a concern into a sub-50-line document.

**Incremental artifact tracking:** After each spec document is written (by you or a writer subagent), immediately update the `artifacts` array in `.pipeline-state.json` with the new file path. This enables crash recovery if the session is interrupted mid-suite (see shared-conventions.md "Stage-Entry Guard").

## Step 4: Write the Spec Suite

The suite has a hard internal dependency: every domain/integration doc references the
shared types and layout from `00-core-definitions.md` and `01-architecture-layout.md`.
So author in two phases — a sequential foundation, then a parallel fan-out.

### 4a. Foundation pass (sequential, you author)

Write `00-core-definitions.md` and `01-architecture-layout.md` yourself, in the main
session, **before** anything else. Every later document depends on these shared types
and the directory/exports map, so they must exist and be stable first.

### 4b. Domain fan-out (parallel `forge-spec-writer` subagents)

Once the foundation is written, dispatch the remaining numbered docs in parallel — **one
`forge-spec-writer` subagent per document, in a single message with multiple Agent
calls** (the `superpowers:dispatching-parallel-agents` pattern). Each writer is given:
- the PRD and tech-spec,
- the just-written `00-core-definitions.md` and `01-architecture-layout.md` (so it builds
  on the shared types, not its own),
- the stack profile path `references/stacks/{stack}.md` (if `stack` is set in config),
- the quality bar in `references/spec-examples.md`,
- the **exact single filename it must write** and the archetype slice (from
  `references/spec-archetypes.md`) it covers.
- **(epic members only — additive context):** the relevant `EPIC.md` Contracts section(s)
  for this feature, and the `tech-spec.md` of each completed direct dependency at {paths} — so
  the doc is written against real upstream contracts, not guesses.

Each writer authors **only its one assigned file** and returns a short **manifest** of
the `REQ-XXX-NN` IDs it covered (feeds Step 5 traceability). Author `NN-testing-strategy.md`
last (it can be its own writer, or you author it once the others' shapes are known).

**Fallback (no subagents available):** author the documents yourself in batches of 3–5,
foundation first; after each batch, optionally commit
(`git add {specsDir}/{feature}/ && git commit -m "{commitPrefix}({feature}): specs batch {n}"`)
and re-read only `00-core-definitions.md` plus the upstream docs the next batch needs —
do not reload everything. This keeps quality up under context pressure.

### Quality requirements (every document, whoever writes it)

1. Number sequentially: `00-`, `01-`, `02-`, etc.
2. Every implementation detail MUST trace to either a PRD requirement (REQ-XXX-NN) or a tech-spec decision
3. Before the body, include a `## Requirement Coverage` table mapping every REQ-XXX-NN this document covers to the section that implements it
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

Before writing `TRACEABILITY.md` or running the stage exit, invoke the **Stage-Completion Re-check** block in `references/shared-conventions.md` with `{stage}` = `forge-3-specs` — a resumed mid-stage continuation must not overwrite a committed `TRACEABILITY.md` or re-fire a finished exit.

After writing all documents, verify:

1. Every PRD requirement has coverage in at least one spec document
2. Every tech-spec decision is reflected in the implementation specs
3. Cross-references between spec documents are consistent (no broken references)
4. Type definitions used across documents are consistent
5. No orphaned implementation details that don't trace to requirements
6. Produce a traceability matrix: a markdown table mapping every REQ-XXX-NN from the PRD to the spec document and section that implements it. Write this to `{resolvedFeatureDir}/TRACEABILITY.md`

List any gaps or inconsistencies found and resolve them.

## Step 6: Review with User

Present a summary of all documents created as text, with key decisions highlighted. Then use `AskUserQuestion` to collect feedback — do NOT include these questions in your text output:

"1. Does the level of detail match what you need? 2. Any areas that need more depth? 3. Any missing subsystems or concerns?"

## Step 7: Update Pipeline State and Commit

Write pipeline state conforming to `references/pipeline-state-schema.json`.

1. Update `{resolvedFeatureDir}/.pipeline-state.json`:
   - Set `currentStage` to `forge-4-backlog` (or verification if they want to verify first)
   - Record all created files in `artifacts`, including `TRACEABILITY.md`
   - Set `stages.forge-3-specs.basedOnVersions` to `{"forge-1-prd": <current version>, "forge-2-tech": <current version>}`
   - Check downstream stages (forge-4-backlog, forge-5-loop, forge-6-docs). If any have `basedOnVersions` referencing older versions, set their status to `stale`
2. **Offer a note — don't force one.** As a statement (not a blocking question), let the user know they can jot anything worth preserving across sessions and you'll store it in the `notes` field. If they volunteer something, store it; otherwise proceed.
3. If `gitCommitAfterStage` is true, follow the Git Commit Protocol in `references/shared-conventions.md`: stage files, attempt commit with message `"{commitPrefix}({feature}): complete implementation specs v{n}"` (marking `stages.forge-3-specs.status` `complete` with `commitHash: null` in that commit), then record the artifact-commit hash via the protocol's two-commit follow-up (never `--amend`) only on success. If commit fails, leave status as `in-progress`.
4. **Close with the Stage Exit Protocol** (single-sourced in `references/stage-exit-protocol.md`; do not improvise a "Next steps" list). Specs feed every downstream stage, so the verify gate matters here:

**Close this stage with the Scripted Stage Exit** (contract: `references/stage-exit-protocol.md`; do not improvise a "Next steps" list). Run:

```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" stage-exit --feature "{feature}" --stage forge-3-specs --specs-dir "{specsDir}" --host claude
```

Obey the DIRECTIVES it prints, in order, per the directive contract: `runInStageVerify: true` → dispatch the in-stage clean-room verify now (honoring `autoFixEligible`); `verifyGate: "standard"` → present the Standard Verify Gate; `verifyGate: "manual-print"` → print the `verifyCommand` for the user; non-empty `invalidAutoVerifyKeys` → print a one-line warning. Then **print the NEXT-STEPS block verbatim as your absolute last output — nothing after its sentinel line.**

## Gotchas

- Don't create specs for things that are already fully specified in the tech spec. If the tech spec has complete type definitions, the implementation spec should reference them, not duplicate them.
- Every spec document should include complete type definitions and function signatures in the project's language with documentation comments. The backlog generator and implementing engineer depend on these being exact, not approximate.
- Resist the urge to create too many documents. Each document should represent a major concern. If a "document" would be under 50 lines, it probably belongs as a section in another document.
- Watch for implicit dependencies between subsystems. If subsystem A's types are used by subsystem B, the spec should explicitly state this and ensure the types are defined in the shared types document.
- If the feature is large, the spec suite might be 8-12 documents. If it's simple, 3-4 is fine. Match complexity to the feature, not a fixed template.
