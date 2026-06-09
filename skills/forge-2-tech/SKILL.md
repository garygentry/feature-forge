---
name: forge-2-tech
description: "Create a technical specification from an existing PRD in the forge pipeline. Use when user runs /feature-forge:forge-2-tech or asks to create a tech spec for a forge feature after PRD completion. Do NOT trigger for general technical design discussions, architecture reviews, or tech specs outside the forge pipeline."
argument-hint: "<feature-name>"
---

# forge-2-tech — Technical Specification Driver

Create a thorough technical specification by interviewing the user about technology decisions, grounded in PRD requirements.

## Prerequisites

Read and follow `references/shared-conventions.md` for feature name validation, configuration reading, and force mode handling before proceeding.

## Step 1: Validate Prerequisites

**Prerequisite check:** Read `{specsDir}/{feature}/.pipeline-state.json`. If not in force mode and `forge-1-prd` is not `complete`, STOP and tell the user: "The PRD for '{feature}' isn't complete yet. Run `/feature-forge:forge-1-prd {feature}` first."

Read `{specsDir}/{feature}/PRD.md` into context. This is your foundation — every technology decision must trace back to a PRD requirement.

## Step 2: Examine Existing Context

Before interviewing, you need to understand the existing codebase. This involves reading many files across the project, which consumes context.

### Recommended: Delegate to forge-researcher Subagent

Spawn the `forge-researcher` subagent via the Agent tool to scan the codebase. Pass a prompt like: "Research the codebase for planning the {feature} feature. Focus on integration points, established patterns, and relevant packages."

The researcher runs in its own context window, reads the project structure, and returns a concise integration report. This keeps your main conversation context clean for the interactive interview.

If the `forge-researcher` subagent is not available, perform the research inline (steps below).

### Manual Research (fallback)

1. **Read the PRD thoroughly**: Understand all requirements and constraints
2. **Check for project-level stack decisions**: Look for `.claude/references/stack-decisions.md` in the project root. If present, read it — these are established technology choices that should be respected unless there's a strong reason to deviate.
3. **Read the plugin's default stack reference**: Read `references/stack-discovery-checklist.md` for general stack context (only if no project-level override exists)
4. **Examine the existing codebase**: Look at `package.json` files, existing packages, directory structure, and established patterns. Understand what conventions are already in place.
5. **Review other features' tech specs**: Check `{specsDir}/*/tech-spec.md` for consistency in approach and to identify shared infrastructure.
6. **Identify integration points**: For each existing package that this feature touches, read its exports, types, and public API. Document these as constraints.

### Stack Detection and Persistence

After researching the codebase, identify the primary stack (language, build tool, package manager, framework). Read `references/stack-resolution.md` for the full resolution protocol.

1. Check if `forge.config.json` already has a `stack` field — if so, use it
2. Otherwise, detect from project files and use `AskUserQuestion` to confirm: "I detected this as a {stack} project. Correct?"
3. Update `forge.config.json` with `stack`, `typeCheckCommand`, and `testCommand`
4. Verify that a matching stack profile exists at `references/stacks/{stack}.md`. If it does, load it for stack-specific guidance during this and all subsequent stages. If no profile exists, inform the user: "No dedicated profile for {stack}. Using generic fallback — spec conventions, verification checks, and examples will be language-neutral. Consider creating a project-level override at `.claude/references/stack-decisions.md`." Then load `references/stacks/_generic.md`.

## Step 3: Conduct the Interview

Interview the user about technology decisions. Unlike the PRD interview, here you SHOULD discuss specific technologies, libraries, patterns, and architecture.

### Interview Approach

**Turn structure:** Output your research findings, analysis, or technical proposals as regular text. Then use `AskUserQuestion` for the actual questions. NEVER put questions in your text output — they MUST go through `AskUserQuestion`.

**Pacing:** Present 1-2 decision areas per `AskUserQuestion` call and STOP to wait for the user's response before continuing. After receiving answers, probe deeper on anything incomplete before moving to the next topic. Signal progress in your text before the next question batch. Do NOT dump all decision areas in a single message — the interview is a conversation, not a document.

**First message pattern:** Output the research summary as text, then use `AskUserQuestion` to confirm the stack and ask about the first decision area (typically package/module structure). Wait for the user to respond before proceeding to subsequent areas.

**Question strategies** (use these as content for `AskUserQuestion`, not as inline prose):
- For each PRD requirement, propose a technical approach and ask for confirmation or alternatives
- Proactively suggest approaches consistent with the established stack
- Challenge over-engineering: does the feature need this, or is a simpler approach sufficient?
- Ask about every integration point and how the feature interacts with existing modules

**Parking lot:** If the user raises a concern that belongs to a different pipeline stage (e.g., backlog granularity, documentation format), acknowledge it and note it in the pipeline state's `notes` field: "Good point — I've noted that for the [specs/backlog/docs stage]. Let's continue with the tech spec."

### Key Decision Areas to Cover

Work through these areas across multiple turns, grouping related areas (1-2 per message):

- **Package/module structure**: Where does this live in the project? What are its exports? (For non-monorepo projects, this becomes module organization — where the code lives, how it's organized, and what its exports are.)
- **Data model**: What are the key entities, their schemas, and storage approach?
- **API design**: What endpoints or interfaces does this expose?
- **Dependencies**: What external and internal packages are needed?
- **Patterns**: Which established patterns from the codebase apply here?
- **Error handling**: How are errors surfaced, propagated, and recovered from?
- **Testing strategy**: Unit, integration, e2e — what approach for this feature?
- **Configuration**: What's configurable? How is it configured?
- **Migration/deployment**: Any special rollout considerations?

### Requirement Traceability

Every technical decision MUST reference the PRD requirement(s) it addresses. Use the format:

```
### JWT-based Session Tokens (REQ-AUTH-01, REQ-SEC-02)
Sessions will use signed JWT tokens with...
```

If you find yourself writing a technical section that doesn't trace to any PRD requirement, STOP and ask: "I'm about to specify X, but I can't find a PRD requirement for it. Should we add one, or is this unnecessary?"

## Step 4: Integration Analysis (Required)

Before finalizing the tech spec, this section is MANDATORY:

1. List every existing package this feature depends on
2. List every existing package that will need to import from this feature
3. For each integration point, document:
   - Which types or contracts are shared
   - How data flows between packages
   - Any patterns established by existing code that must be followed
   - The EXACT function signatures and import paths verified from source code. If you cannot locate an expected export, note explicitly: "WARNING: Could not locate X export in {module} — verify this exists before implementing."
4. Check for potential conflicts with in-progress features (other spec directories)

## Step 5: Write the Tech Spec

Write `{specsDir}/{feature}/tech-spec.md` with this structure:

```markdown
# {Feature Name} — Technical Specification

## 1. Overview
Brief technical summary and key architectural decisions.

## 2. Module Structure
Project location, directory layout, public API surface.

## 3. Technical Decisions
### 3.1 {Decision Area} (REQ-XXX-NN)
Decision, rationale, alternatives considered.

## 4. Data Model
Schemas, types, storage approach.

## 5. API Design
Endpoints, interfaces, contracts.

## 6. Integration Points
How this feature connects to existing packages.

## 7. Error Handling
Error types, propagation, recovery.

## 8. Testing Approach
Strategy, tooling, coverage targets.

## 9. Dependencies
External packages, internal packages, version constraints.

## 10. Open Technical Questions
Unresolved technical decisions.
```

## Step 6: Review with User

Present the complete tech spec. Ask:
- "Does this capture all the technical decisions correctly?"
- "Any patterns from the existing codebase I missed?"
- "Are the integration points complete?"

Use `AskUserQuestion` to collect this feedback.

## Step 7: Update Pipeline State and Commit

Write pipeline state conforming to `references/pipeline-state-schema.json`.

1. Update `{specsDir}/{feature}/.pipeline-state.json`:
   - Set `currentStage` to `forge-3-specs`
   - Record `artifacts`, `completedAt`, `version`
   - Set `stages.forge-2-tech.basedOnVersions` to `{"forge-1-prd": <current forge-1-prd version>}`
   - Check downstream stages (forge-3-specs, forge-4-backlog, forge-5-rauf-loop, forge-6-docs). If any have `basedOnVersions` referencing an older version of forge-2-tech, set their status to `stale`
2. Use `AskUserQuestion` to ask about notes to persist
3. If `gitCommitAfterStage` is true, follow the Git Commit Protocol in `references/shared-conventions.md`: stage files, attempt commit with message `"{commitPrefix}({feature}): complete tech-spec v{n}"`, then set `stages.forge-2-tech.status` to `complete` with commit hash only on success. If commit fails, leave status as `in-progress`.
5. Tell the user: "Tech spec complete. Next steps:\n  - `/feature-forge:forge-verify {feature}` to verify the tech spec\n  - `/feature-forge:forge-3-specs {feature}` to create implementation specs\n  - `/feature-forge:forge {feature}` to see full pipeline status"

## Gotchas

- Don't duplicate the PRD. The tech spec answers HOW, not WHAT. If you find yourself restating requirements, reference them by ID instead.
- When the user's stack decisions differ from what you'd recommend, document their choice AND note your concern as an "Alternatives Considered" item — don't silently override their preference.
- Integration points are the #1 source of implementation surprises. Spend extra time here. Read the actual code of packages this feature touches, don't just guess at their APIs.
- If the existing codebase has inconsistent patterns (it happens), call it out and ask which pattern should be followed for this feature.
