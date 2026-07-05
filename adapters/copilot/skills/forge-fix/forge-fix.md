---
# GENERATED — DO NOT EDIT. Source: skills/forge-fix/SKILL.md. Regenerate: python3 scripts/build-adapters.py
name: forge-fix
description: Apply fixes from the most recent forge-verify findings document. Use when user runs /feature-forge:forge-fix or asks to apply verification fixes for a forge feature. Do NOT trigger for general code fixes, bug fixes, or repairs outside the forge verification workflow.
---

# forge-fix — Apply Verification Fixes

Apply fixes from the most recent forge-verify findings document, with step-level tracking for crash recovery.

Usually invoked by the user, but the `/feature-forge:forge` navigator may also invoke this skill
automatically when `autoFix: true` is configured **and** its preconditions hold (the findings
document has zero unresolved decision points, the working tree is clean, and a mandatory re-verify
passes afterward). Either way the behavior below is identical — this skill is not "auto-aware," it
always applies the latest findings document; the navigator owns the gating decision.

## Prerequisites

Read and follow `references/shared-conventions.md` for feature name validation, configuration reading, and force mode handling before proceeding.

**Turn structure reminder:** Output analysis/context as text, then route ALL questions through the host's question mechanism. Never embed questions in text output — the user will not be prompted and the session will stall.

## Step 1: Locate Findings Document

1. Read `forge.config.json` for `specsDir` (default: `./specs`)
2. Resolve the feature directory via the **Feature Directory Resolution** block in `references/shared-conventions.md` (a standalone feature resolves to its flat `{specsDir}/{feature}/` path exactly as today; an epic member resolves to its nested path). Then find the most recent `VERIFY-*-*.md` file in `{resolvedFeatureDir}/.verification/`.
3. If no findings document exists, tell the user: "No verification findings found. Run `/feature-forge:forge-verify {feature}` first."

## Step 2: Parse Fix Execution Plan

1. Read the "Fix Execution Plan" section of the findings document
2. Identify all execution steps and their dependencies
3. Check for a `## Fix Progress` section at the bottom of the findings document — if present, some steps were already applied in a previous interrupted run

## Step 3: Handle User Decisions

If the "User Decisions Required" section has unresolved items:
1. Present each decision to the user with the context from the findings, using the host's question mechanism for each decision point. Follow the **Decision Support** protocol in `references/shared-conventions.md`: lead with a recommended option and put the trade-off in each option's description. When the findings provide clear evidence, recommend with confidence and cite it. When they don't, still offer a sensible default with the trade-offs, but flag it plainly as a judgment call rather than going neutral — a defaulted recommendation beats an unguided option dump.
2. Wait for answers before proceeding
3. Record decisions in the findings document under the "User Decisions Required" section (mark each as resolved)

## Step 4: Execute Fix Steps

For each step in the "Execution Steps" section, in order:

1. **Check if already applied:** If the step appears in the "Fix Progress" section as `[APPLIED]`, skip it
2. **Check dependencies:** If the step depends on another step, verify that step is marked as applied
3. **Apply the fix:** Execute the change described in the step's "Action" field
4. **Verify the change:** Re-read the modified file and check that the change is correct and consistent with the step's rationale
5. **Record progress:** Append to the `## Fix Progress` section at the bottom of the findings document:
   ```
   - Step {N}: [APPLIED] {date} — {short summary of what was done}
   ```
6. If a step fails or produces unexpected results, STOP. Report the issue to the user. Do not continue to dependent steps.

## Step 5: Update Pipeline State and Commit

Follow the Git Commit Protocol in `references/shared-conventions.md`.

1. Update `{resolvedFeatureDir}/.pipeline-state.json`:
   - Set the relevant `forge-verify-*` entry status to `findings-applied`
   - Record `fixedAt` timestamp
   - Record `verifiedStageVersion` = the current `version` of the production stage entry
     this verify covers (e.g. fixing `tech` findings → `stages["forge-2-tech"].version`).
     This keeps the navigator's freshness ledger accurate after a fix, so the verified
     stage reads as `fresh` and auto-verify does not needlessly re-fire on an unchanged
     artifact. (If the fix itself bumped the production stage's `version`, use the new
     value so the ledger reflects what was actually verified/fixed.)
2. If `gitCommitAfterStage` is true, follow the Git Commit Protocol: stage files (`git add {resolvedFeatureDir}/` — or `{specsDir}/{epic}/` for an epic member so the member-state change commits atomically with the epic subtree), attempt commit with message `"{commitPrefix}({feature}): apply {mode} verification fixes"` (writing `commitHash: null` in that commit), then record the artifact-commit hash via the protocol's two-commit follow-up (never `--amend`) only on success.

## Step 6: Next Steps

Tell the user:
"Fixes applied. Next steps:
  - Run `/feature-forge:forge-verify {feature}` again to confirm all issues are resolved
  - Or `/feature-forge:forge {feature}` to see pipeline status"

---

## Host execution notes

This skill was authored Claude-first; the body above refers to "the host's question mechanism", "the host's subagent mechanism", and "the host's background-execution mechanism". Use your runtime's equivalent for each — and if your runtime has no such tool:

- **User input:** ask the question directly and wait for the answer before proceeding. Do not skip a required question or assume an answer.
- **Subagents:** if your host cannot dispatch the named custom agent, run that step inline yourself.
- **Background / monitoring:** run long-lived commands in the foreground (or your host's background facility) and report progress as it arrives.
