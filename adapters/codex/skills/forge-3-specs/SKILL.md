---
# GENERATED — DO NOT EDIT. Source: skills/forge-3-specs/SKILL.md. Regenerate: python3 scripts/build-adapters.py
name: forge-3-specs
description: Generate numbered implementation spec documents from PRD and tech spec in the forge pipeline. Use when user runs /feature-forge:forge-3-specs or asks to create detailed implementation specs for a forge feature after tech spec completion. Do NOT trigger for general specification writing, design docs, or implementation planning outside the forge pipeline.
---

# forge-3-specs — Implementation Spec Suite Generator

Generate a comprehensive suite of numbered implementation specification documents that provide everything needed to implement a feature.

## Prerequisites

Read and follow `references/shared-conventions.md` for feature name validation, configuration reading, and force mode handling before proceeding.

**Turn structure reminder:** Output analysis/context as text, then route ALL questions through the host's question mechanism. Never embed questions in text output — the user will not be prompted and the session will stall.

## Step 1: Validate Prerequisites

**Resolve the feature directory first** via the **Feature Directory Resolution** block in `references/shared-conventions.md`, setting `{resolvedFeatureDir}`.

**Prerequisite check:** Read `{resolvedFeatureDir}/.pipeline-state.json`. If not in force mode, both `forge-1-prd` and `forge-2-tech` must be `complete`. If not, STOP and tell the user which prerequisites are missing.

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

Based on the feature's complexity, propose a document plan to the user before writing. Output the document list as text, then use the host's question mechanism for the question — do NOT include the question in your text output.

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

**Then call the host's question mechanism** following the **Decision Support** protocol in `references/shared-conventions.md`: recommend this plan as the default (it's your evidence-backed read of the feature's complexity) and name the trade-off so the user can push back knowingly — more documents means finer separation of concerns but more to keep in sync; fewer means tighter docs but risks one document carrying multiple concerns. Lead with: "I recommend this plan. Add or remove any documents?" Note the guidance below — resist splitting a concern into a sub-50-line document.

**Incremental artifact tracking:** After each spec document is written (by you or a writer subagent), immediately update the `artifacts` array in `.pipeline-state.json` with the new file path. This enables crash recovery if the session is interrupted mid-suite (see shared-conventions.md "Crash Recovery").

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
`forge-spec-writer` subagent per document, in a single message with multiple subagent
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

After writing all documents, verify:

1. Every PRD requirement has coverage in at least one spec document
2. Every tech-spec decision is reflected in the implementation specs
3. Cross-references between spec documents are consistent (no broken references)
4. Type definitions used across documents are consistent
5. No orphaned implementation details that don't trace to requirements
6. Produce a traceability matrix: a markdown table mapping every REQ-XXX-NN from the PRD to the spec document and section that implements it. Write this to `{resolvedFeatureDir}/TRACEABILITY.md`

List any gaps or inconsistencies found and resolve them.

## Step 6: Review with User

Present a summary of all documents created as text, with key decisions highlighted. Then use the host's question mechanism to collect feedback — do NOT include these questions in your text output:

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

**This stage is done — walk the user through the Stage Exit Protocol** before moving on. The order is fixed, and step 2 is something only the user can do:

1. **Verify the implementation specs first — if it isn't already verified.** When this stage has no fresh verification on record (`verifyState` is **missing or stale**) **and** `autoVerify` is off for it, verify **now, before clearing**. If verify already ran, is pending under auto-verify, or the stage was explicitly skipped, say so and go straight to step 2. Present the **Standard Verify Gate** using the host's question mechanism with exactly these three options — but only when the host has a question mechanism **and** the clean-room path is available (the `Agent` tool plus a dispatchable `forge-verifier` subagent):
   - **Verify the implementation specs now** *(recommended)* — dispatch the clean-room `forge-verifier` subagent from this session in require-clean mode; the digest returns here so any fix decision keeps its context. One-time — it does **not** change config.
   - **Verify now + enable auto-verify going forward** — verify now **and** patch `"autoVerify": true` into `forge.config.json` in place (preserve formatting and every other key) so future stages verify automatically, no prompt. This complements the `forge-init` opt-in. **Do not auto-commit this config change** — treat it like `notes`: a user-facing edit the user commits on their own cadence, never folded into a stage's artifact commit.
   - **Skip for now** — go straight to clear your session / start a fresh session and the next command without verifying. Record this stage's verify status as `"skipped"` in pipeline state (mirroring the existing skip handling) **only** on an explicit skip — a skip does not go stale.

   **Host / clean-room fallback (not a user-selectable option):** if the question mechanism, the `Agent` tool, or the `forge-verifier` subagent is unavailable, do **not** run clean-room — degrade to printing `/feature-forge:forge-verify {feature}` for the user to run inline/manually (mirroring `autoInvokeNextStage`), and offer the auto-verify enable as plain text only if a config write is possible.
2. **Then clear your session / start a fresh session.** Recommended **unconditionally** at this boundary for a clean start — independent of how full the context window is. Every artifact is on disk, so the work survives the clear. **I can't clear your session / start a fresh session for you — you have to run it yourself.**
3. **Then run `/feature-forge:forge-4-backlog {feature}`** in the fresh session — or re-run `/feature-forge:forge` to let the navigator resume from disk.

## Gotchas

- Don't create specs for things that are already fully specified in the tech spec. If the tech spec has complete type definitions, the implementation spec should reference them, not duplicate them.
- Every spec document should include complete type definitions and function signatures in the project's language with documentation comments. The backlog generator and implementing engineer depend on these being exact, not approximate.
- Resist the urge to create too many documents. Each document should represent a major concern. If a "document" would be under 50 lines, it probably belongs as a section in another document.
- Watch for implicit dependencies between subsystems. If subsystem A's types are used by subsystem B, the spec should explicitly state this and ensure the types are defined in the shared types document.
- If the feature is large, the spec suite might be 8-12 documents. If it's simple, 3-4 is fine. Match complexity to the feature, not a fixed template.

---

## Host execution notes (Codex)

This skill was authored Claude-first; the body above refers to "the host's question mechanism", "the host's subagent mechanism", and "the host's background-execution mechanism". On Codex:

- **User input:** Codex has no structured question tool — ask the question directly and wait for the user's reply before proceeding. Never skip a required question or assume an answer.
- **Subagents:** spawn a Codex subagent using the named custom agent under `.codex/agents/<name>.toml`. Codex spawns a subagent only when explicitly asked; if the custom agent is unavailable, run that step inline yourself.
- **Background / monitoring:** run long-lived runner commands in your shell session and report progress as it arrives — there is no Claude-style background or monitoring tool to arm.
