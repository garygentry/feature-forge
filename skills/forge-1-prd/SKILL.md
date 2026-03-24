---
name: forge-1-prd
description: "Create a requirements PRD for a feature through structured interview. Use when user runs /feature-forge:forge-1-prd or explicitly asks to start the forge pipeline for a new feature. Do NOT trigger for general requirements discussions, project scoping outside forge, or PRD questions unrelated to the forge pipeline."
argument-hint: "<feature-name>"
---

# forge-1-prd — Requirements Interviewer

Create a thorough, requirements-only PRD through relentless structured interviewing. The PRD captures WHAT the feature must do, not HOW it will be built.

## Prerequisites

Read and follow `references/shared-conventions.md` for feature name validation, configuration reading, and force mode handling before proceeding.

## Step 1: Read Configuration and Check State

### Branch Setup (if using git)
If `gitCommitAfterStage` is true and the project uses git, offer: "Want me to create a `forge/{feature}` branch for this pipeline? (Recommended — keeps forge work isolated.)" If yes, create and checkout the branch before proceeding.

Set the working directory: `{specsDir}/{feature}/`

If `.pipeline-state.json` exists for this feature and `forge-1-prd` is already marked complete, warn the user: "A PRD already exists for '{feature}'. Continuing will create a new version. Proceed?"

## Step 2: Examine Existing Context

Before starting the interview:

1. **Check the project structure**: Read the project's build configuration and dependency manifests to understand what modules/packages exist. Look for `package.json`, `pyproject.toml`, `go.mod`, `Cargo.toml`, `pom.xml`, workspace configs, or equivalent.
2. **Check existing specs**: Look at `{specsDir}/` for other features' PRDs to understand conventions and the overall system
3. **Check existing docs**: Look at the docs directory for architecture documentation
4. **Note integration surfaces**: Identify which existing packages might be relevant to this feature

This context helps you ask informed questions and spot gaps the user might not think of.

## Step 3: Conduct the Interview

Interview the user relentlessly. Your goal is to extract complete, unambiguous requirements.

Read `references/prd-template.md` for the interview structure and question categories. Cover every category. Don't rush — missing a requirement now costs 10x to fix later.

### CRITICAL GUARDRAIL: No Technology Decisions

The PRD is EXCLUSIVELY about requirements. You MUST enforce this boundary:

**When the user says something like:**
- "I want to use Zod for validation" → Capture as: "Runtime schema validation with type inference is required." Note their Zod preference as a constraint but not a requirement.
- "We'll store it in Drizzle/PostgreSQL" → Capture as: "Persistent storage required for X data with Y query patterns."
- "I want a React component that..." → Capture as: "A user interface is required that allows users to..."
- "We should use WebSockets for..." → Capture as: "Real-time updates are required when X changes, with latency under Y."
- "I want a REST API" → Capture as: "An HTTP-accessible interface is required for X operations"
- "We need a microservice for X" → Capture as: "X must be independently deployable and scalable"
- "Use a queue for Y" → Capture as: "Y must be processed asynchronously with guaranteed delivery"

**When YOU start drifting into technology:**
If you catch yourself writing about specific libraries, API designs, database schemas, or implementation patterns — STOP. Ask yourself: "Is this a requirement or an implementation choice?" Rewrite it as the underlying requirement.

**The one exception:** When a technology choice IS the requirement (e.g., "must integrate with the existing @repo/auth package" or "must work with our Hono backend"). These are constraints, and they belong in the Constraints section of the PRD, clearly labeled as such.

A technology constraint is valid when it stems from organizational mandate, existing infrastructure, or team expertise — not from preference. Ask "Why must it be X specifically?" If the answer is "because we already run X in production," that's a legitimate constraint. If the answer is "because it's fast," capture the performance requirement instead.

### Interview Approach

- Ask questions one topic area at a time, not all at once
- After each answer, probe deeper: "What happens when X fails?", "Who else needs to see this?", "What's the minimum viable version?"
- Challenge assumptions: "You said 'users' — which users specifically?", "When you say 'fast', what's the acceptable latency?"
- Identify edge cases: "What if the input is empty?", "What about concurrent access?", "What happens at scale?"
- Capture non-functional requirements explicitly: performance, security, accessibility, observability
- Ask about what's OUT of scope — this is as important as what's in scope

**Completion criteria:** The interview is complete when:
1. Every category in `references/prd-template.md` has been covered with at least one question
2. The user has confirmed there's nothing else to add
3. You can draft every PRD section without leaving TBD placeholders

Before moving to Step 4, summarize: "I believe I have enough to draft the PRD. Here's what I'll cover: [list sections with key points]. Anything I'm missing?"

**Interview pacing:** Ask 2-3 related questions per message. After receiving answers, probe deeper on anything incomplete before moving to the next topic area. Signal progress: "That covers the functional requirements. Moving to error handling and edge cases."

**Parking lot:** If the user raises a concern that belongs to a different pipeline stage, acknowledge it and note it in the pipeline state's `notes` field: "Good point — I've noted that for the [tech spec/implementation specs]. Let's continue with [current stage]."

## Step 4: Write the PRD

Once the interview is thorough, write `{specsDir}/{feature}/PRD.md` following the structure in `references/prd-template.md`.

Every requirement MUST have a unique ID (e.g., REQ-AUTH-01, REQ-PERF-01). These IDs are referenced by all downstream documents.

## Step 5: Review with User

Present the complete PRD to the user. Ask:
- "Does this capture everything? Any requirements missing?"
- "Are the priorities correct?"
- "Anything in here that should be out of scope?"

Iterate until the user confirms the PRD is complete.

## Step 6: Update Pipeline State and Commit

Write pipeline state conforming to `references/pipeline-state-schema.json`.

1. Create or update `{specsDir}/{feature}/.pipeline-state.json`:
   - Set `currentStage` to `forge-2-tech`
   - Set `stages.forge-1-prd.version` to 1 (or increment if revising)
   - Record `artifacts`, `completedAt`
   - Set `stages.forge-1-prd.basedOnVersions` to `{}` (no upstream dependencies)
   - Check downstream stages (`forge-2-tech`, `forge-3-specs`, `forge-4-backlog`, `forge-5-docs`). If any have `basedOnVersions` referencing an older version of `forge-1-prd`, set their status to `stale`.
2. Ask the user: "Anything you want to note before we wrap? (preserved across sessions)"
   - If yes, store in the `notes` field
3. If `gitCommitAfterStage` is true, follow the Git Commit Protocol in `references/shared-conventions.md`: stage files, attempt commit with message `"{commitPrefix}({feature}): complete PRD v{n}"`, then set `stages.forge-1-prd.status` to `complete` with commit hash only on success. If commit fails, leave status as `in-progress`.
5. Tell the user: "PRD complete. Next steps:\n  - `/feature-forge:forge-verify {feature}` to verify the PRD\n  - `/feature-forge:forge-2-tech {feature}` to start the tech spec\n  - `/feature-forge:forge {feature}` to see full pipeline status"

## Gotchas

- Users often front-load their feature description with tech decisions because that's how engineers think. Gently but firmly redirect to requirements. Don't be preachy about it — just reframe what they said.
- If the user provides a very detailed initial description, don't skip the interview. Use their description as a starting point but probe for what's missing. Long descriptions often have big gaps in edge cases and non-functional requirements.
- Don't number requirements sequentially across categories (REQ-01, REQ-02...). Use category prefixes (REQ-AUTH-01, REQ-PERF-01) so inserting new requirements doesn't require renumbering.
- The PRD should be readable by a non-technical stakeholder. If a section requires deep technical knowledge to understand, it probably belongs in the tech spec, not the PRD.
