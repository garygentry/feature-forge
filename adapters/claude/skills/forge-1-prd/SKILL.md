---
# GENERATED — DO NOT EDIT. Source: skills/forge-1-prd/SKILL.md. Regenerate: python3 scripts/build-adapters.py
name: forge-1-prd
description: Create a requirements PRD for a feature through structured interview. Use when user runs /feature-forge:forge-1-prd or explicitly asks to start the forge pipeline for a new feature. Do NOT trigger for general requirements discussions, project scoping outside forge, or PRD questions unrelated to the forge pipeline.
argument-hint: <feature-name>
---

# forge-1-prd — Requirements Interviewer

Create a thorough, requirements-only PRD through relentless structured interviewing. The PRD captures WHAT the feature must do, not HOW it will be built.

## Prerequisites

Read and follow `references/shared-conventions.md` for feature name validation, configuration reading, and force mode handling before proceeding.

## Step 1: Read Configuration and Check State

### Branch Setup (if using git)
Invoke the **Branch Setup** block in `references/shared-conventions.md` with `{label}` = `{feature}` and `{scope}` = `feature`. It self-gates (skips when not a git repo, when `branchPerFeature` is false, or for an epic member that inherits the epic's branch), detects whether you're on the default branch, and strongly recommends — still optionally — creating `{branchPrefix}{feature}` when you are. Do this before directory resolution.

Set the working directory by invoking the **Feature Directory Resolution** block in `references/shared-conventions.md`, which yields `{resolvedFeatureDir}`. Note one PRD-specific caveat: at PRD time a brand-new standalone feature may have NO directory yet, so resolution is expected to fail `not-found` for a never-started standalone feature — in that case forge-1 creates `{specsDir}/{feature}/` as today. For an epic member the directory already exists (created empty by forge-0-epic with an `epic` back-pointer), so resolution succeeds and yields the nested path.

If `.pipeline-state.json` exists for this feature and `forge-1-prd` is already marked complete, use `AskUserQuestion` to warn: "A PRD already exists for '{feature}'. Continuing will create a new version. Proceed?"

## Step 2: Examine Existing Context

Before starting the interview, invoke the **Epic Context Injection** block in `references/shared-conventions.md`. This block self-gates: it skips entirely if the feature has no `epic` back-pointer, so standalone behavior is unchanged. If this feature is an epic member, the injected charter's `exposes`/`consumes` are requirement inputs — every contract obligation must appear as a REQ in the PRD.

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

**Turn structure:** Output your analysis or context as regular text, then use `AskUserQuestion` for the actual questions. NEVER put questions in your text output — they MUST go through `AskUserQuestion`.

**Pacing:** Cover one topic area at a time, asking 2-3 related questions per `AskUserQuestion` call. After receiving answers, probe deeper on anything incomplete before moving to the next topic. Signal progress in your text before the next question batch.

**Question strategies** (use these as content for `AskUserQuestion`, not as inline prose). The PRD stays at the requirements level (the *what*, not the *how* — that's forge-2-tech), so most questions are open elicitation. But whenever you offer the user a *choice* (scope boundary, MVP cut, a non-functional target), apply the **Decision Support** protocol in `references/shared-conventions.md`: propose a sensible default with its trade-off rather than an empty menu — e.g. "I'd scope V1 to X and defer Y; that ships sooner but means Y waits. Agree?":
- Probe deeper after each answer: failure modes, stakeholders, minimum viable version
- Challenge assumptions: which users specifically, what does "fast" mean quantitatively
- Identify edge cases: empty input, concurrent access, scale
- Capture non-functional requirements: performance, security, accessibility, observability
- Ask about what's OUT of scope — as important as what's in scope; when proposing a scope line, recommend one and name what each side gives up

**Completion criteria:** The interview is complete when:
1. Every category in `references/prd-template.md` has been covered with at least one question
2. The user has confirmed there's nothing else to add
3. You can draft every PRD section without leaving TBD placeholders

Before moving to Step 4, summarize your coverage as text, then use `AskUserQuestion` to ask: "Anything I'm missing?"

**Parking lot:** If the user raises a concern that belongs to a different pipeline stage, acknowledge it and note it in the pipeline state's `notes` field: "Good point — I've noted that for the [tech spec/implementation specs]. Let's continue with [current stage]."

## Step 4: Write the PRD

Once the interview is thorough, write `{resolvedFeatureDir}/PRD.md` following the structure in `references/prd-template.md`.

Every requirement MUST have a unique ID (e.g., REQ-AUTH-01, REQ-PERF-01). These IDs are referenced by all downstream documents.

After writing the PRD (this is the point where `{specsDir}/{feature}/` is first created for a standalone feature), invoke the **Specs Directory Hygiene** block in `references/shared-conventions.md` to ensure `{specsDir}/AGENTS.md` (and `{specsDir}/CLAUDE.md` on the Claude host) exists. It is idempotent — it never overwrites an existing file.

## Step 5: Review with User

Present the complete PRD to the user. Ask:
- "Does this capture everything? Any requirements missing?"
- "Are the priorities correct?"
- "Anything in here that should be out of scope?"

Use `AskUserQuestion` to collect this feedback.

Iterate until the user confirms the PRD is complete.

## Step 6: Update Pipeline State and Commit

Write pipeline state conforming to `references/pipeline-state-schema.json`.

1. Create or update `{resolvedFeatureDir}/.pipeline-state.json`:
   - Set `currentStage` to `forge-2-tech`
   - Set `stages.forge-1-prd.version` to 1 (or increment if revising)
   - Record `artifacts`, `completedAt`
   - Set `stages.forge-1-prd.basedOnVersions` to `{}` (no upstream dependencies)
   - Check downstream stages (`forge-2-tech`, `forge-3-specs`, `forge-4-backlog`, `forge-5-loop`, `forge-6-docs`). If any have `basedOnVersions` referencing an older version of `forge-1-prd`, set their status to `stale`.
2. **Offer a note — don't force one.** As a statement (not a blocking question), let the user know they can jot anything worth preserving across sessions and you'll store it in the `notes` field. If they volunteer something, store it; otherwise proceed.
3. If `gitCommitAfterStage` is true, follow the Git Commit Protocol in `references/shared-conventions.md`: stage files (including `{specsDir}/AGENTS.md` / `{specsDir}/CLAUDE.md` if the Specs Directory Hygiene step just wrote them), attempt commit with message `"{commitPrefix}({feature}): complete PRD v{n}"` (marking `stages.forge-1-prd.status` `complete` with `commitHash: null` in that commit), then record the artifact-commit hash via the protocol's two-commit follow-up (never `--amend`) only on success. If commit fails, leave status as `in-progress`.
4. **Close with the Stage Exit Protocol** (single-sourced in `references/stage-exit-protocol.md`; do not improvise a "Next steps" list):

**Close this stage with the Scripted Stage Exit** (contract: `references/stage-exit-protocol.md`; do not improvise a "Next steps" list). Run:

```bash
R="$(bash -c 'for d in "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" stage-exit --feature "{feature}" --stage forge-1-prd --specs-dir "{specsDir}" --host claude
```

Obey the DIRECTIVES it prints, in order, per the directive contract: `runInStageVerify: true` → dispatch the in-stage clean-room verify now (honoring `autoFixEligible`); `verifyGate: "standard"` → present the Standard Verify Gate; `verifyGate: "manual-print"` → print the `verifyCommand` for the user; non-empty `invalidAutoVerifyKeys` → print a one-line warning. Then **print the NEXT-STEPS block verbatim as your absolute last output — nothing after its sentinel line.**

## Gotchas

- Users often front-load their feature description with tech decisions because that's how engineers think. Gently but firmly redirect to requirements. Don't be preachy about it — just reframe what they said.
- If the user provides a very detailed initial description, don't skip the interview. Use their description as a starting point but probe for what's missing. Long descriptions often have big gaps in edge cases and non-functional requirements.
- Don't number requirements sequentially across categories (REQ-01, REQ-02...). Use category prefixes (REQ-AUTH-01, REQ-PERF-01) so inserting new requirements doesn't require renumbering.
- The PRD should be readable by a non-technical stakeholder. If a section requires deep technical knowledge to understand, it probably belongs in the tech spec, not the PRD.
