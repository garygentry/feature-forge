---
name: forge-1-prd
description: "Create a requirements PRD for a feature through structured interview. Use when user runs /feature-forge:forge-1-prd or explicitly asks to start the forge pipeline for a new feature. Do NOT trigger for general requirements discussions, project scoping outside forge, or PRD questions unrelated to the forge pipeline."
metadata:
  argument-hint: "<feature-name> [--force-standalone]"
---

# forge-1-prd — Requirements Interviewer

Create a thorough, requirements-only PRD through relentless structured interviewing. The PRD captures WHAT the feature must do, not HOW it will be built.

## Prerequisites

Read and follow `references/shared-conventions.md` for feature name validation, configuration reading, and force mode handling before proceeding.

**`--force-standalone` (forge-1-prd only).** A distinct flag from `--force`: it bypasses only the **Mint Guard** in Step 1 (letting you intentionally fork a name that is a known epic member into a detached standalone feature). It does **not** imply `--force` — prerequisite checks and the Stage-Entry Guard still run. Use it only when you genuinely mean to create a standalone feature that shares a name with an epic member on another branch.

## Step 1: Read Configuration and Check State

### Branch Setup (if using git)
Invoke the **Branch Setup** block in `references/shared-conventions.md` with `{label}` = `{feature}` and `{scope}` = `feature`. It self-gates (skips when not a git repo, when `branchPerFeature` is false, or for an epic member that inherits the epic's branch), detects whether you're on the default branch, and strongly recommends — still optionally — creating `{branchPrefix}{feature}` when you are. Do this before directory resolution.

Set the working directory by invoking the **Feature Directory Resolution** block in `references/shared-conventions.md`, which yields `{resolvedFeatureDir}`. Note one PRD-specific caveat: at PRD time a brand-new standalone feature may have NO directory yet, so resolution is expected to fail for a never-started standalone feature — as `not-found` (exit 1) when `{specsDir}/` already exists (other features present), or as `specs dir not found` (exit 2) when `{specsDir}/` itself does not exist yet (the very first feature, or a branch that never had a specs tree). In **both** of those "about to create a brand-new standalone" cases forge-1 creates `{specsDir}/{feature}/` as today. (The *other* exit-2 errors — `unsafe-name`, a path-containment escape — are genuine STOPs, never a mint.) For an epic member the directory already exists (created empty by forge-0-epic with an `epic` back-pointer), so resolution succeeds and yields the nested path.

### Mint Guard: refuse to fork a known epic member into a detached standalone (Issue #125)

Run this sub-step **whenever forge-1 is about to mint a brand-new flat standalone `{specsDir}/{feature}/`** — that is, when Feature Directory Resolution returned either `not-found` (exit 1) **or** `specs dir not found` (the exit-2 missing-specs-dir flavor, e.g. a clean default branch that has never had a specs tree). The exit-2 case is the *cleanest* split-brain trigger: on a branch that predates the epic, `{specsDir}/` may not exist at all, yet cross-branch discovery still sees the member on the epic branch. It prevents the split-brain-epic failure where a member of an epic (whose manifest lives on a *different, unmerged* branch) is silently forged as a disjoint standalone feature carrying no `epic` back-pointer. Skip it entirely when resolution succeeded (an epic member's directory already exists — resolution yields the nested path, so this never fires), on the other exit-2 errors (`unsafe-name` / path-containment — those STOP, they never mint), and when `--force-standalone` was passed (see below).

1. Run cross-branch discovery for this exact name (branch-agnostic — it scans all refs regardless of current HEAD):
   ```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" discover-feature "{feature}" --specs-dir "{specsDir}" --json
   ```
2. **If any candidate has `isEpicMember: true` → HARD STOP.** This is not the soft switch/fetch/treat-as-new menu from the Feature Directory Resolution block — do **not** create any directory and do **not** fall through to the interview. Emit verbatim (filling `{epic}` and `{stateBranch}` from that candidate's `epic` and `stateBranch`):
   > `{feature}` is a member of epic `{epic}` (recorded on branch `{stateBranch}`). You appear to be on a branch that does not contain that epic. Switch to `{stateBranch}` and run `/feature-forge:forge-1-prd {feature}` there, or pass `--force-standalone` to intentionally fork a detached standalone feature.
3. **If candidates exist but none are epic members** → keep today's soft behavior: this is the ordinary cross-branch-discovery case already handled by the Feature Directory Resolution block's **Candidates found** menu (switch / fetch+switch / treat-as-new / stop). Defer to it.
4. **If nothing was found** (no candidates) → proceed to mint the flat standalone feature as today.
5. **If `--force-standalone` was passed** → skip this guard entirely, log a one-line warning ("Forking `{feature}` as a detached standalone despite epic membership on `{stateBranch}`"), and proceed to create the flat feature. `--force-standalone` is distinct from `--force` and does **not** imply it (see the Force Mode note below).

After resolution, invoke the **Stage-Entry Guard** block in `references/shared-conventions.md` with `{stage}` = `forge-1-prd`. It classifies re-entry (fresh / interrupted / re-authoring), runs the resume-vs-restart gate and the "create a new version?" warning as applicable, and applies the entry stamp on the authoring paths. For a brand-new standalone feature there is no state file yet, so the guard's **fresh** arm applies with nothing to prompt; the entry stamp lands when the state file is first created in Step 6.

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

**Epic-level concern (backflow):** The parking lot above is for concerns about a *later stage of THIS feature*. If instead the interview reveals the **epic decomposition itself** is wrong — a **sibling feature must be added**, a **frozen boundary between features must move**, a feature must **split**, or a **dependency edge is wrong** — that is an *epic-level* concern and does **not** go in `notes`. It only applies when this feature is an epic member (its `.pipeline-state.json` has an `epic` back-pointer); for a standalone feature there is no epic to reconcile, so treat the concern as same-feature or out of scope. To record one, append an entry to the member state's `epicChangeRequests[]` array (same direct-edit path as `notes`; schema in `references/pipeline-state-schema.json`): `kind` (`add-feature`|`redep`|`move-boundary`|`split`), `target`, `rationale`, `raisedBy: "forge-1-prd"`, `raisedAt` (ISO-8601 UTC), `status: "open"`, and `blocksCurrent`. Set `blocksCurrent: true` when the change alters a contract (`exposes`/`consumes`) or dependency edge this feature relies on for its *next* stage (proceeding would build specs on a soon-to-change decomposition); `false` for a peer/downstream change this feature does not consume. When the change touches a contract/dep edge and the classification is genuinely ambiguous, confirm `blocksCurrent` with a single `AskUserQuestion`, defaulting to `true` (a false negative silently diverges two members' contracts). **Do not** edit `epic-manifest.json` here — recording is not applying; only `/feature-forge:forge-0-epic` edit mode mutates the epic. Then acknowledge without blocking: "That's an epic-level change — I've recorded it so `forge-0-epic` can reconcile it. [Blocking: We'll want to reconcile the epic before writing specs. | Non-blocking: We can finish this feature first and reconcile when convenient.]" and continue the interview.

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

Before writing state or running the stage exit, invoke the **Stage-Completion Re-check** block in `references/shared-conventions.md` with `{stage}` = `forge-1-prd` — a resumed mid-stage continuation must not overwrite a committed `PRD.md` or re-fire a finished exit.

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
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" stage-exit --feature "{feature}" --stage forge-1-prd --specs-dir "{specsDir}" --host claude
```

Obey the DIRECTIVES it prints, in order, per the directive contract: `runInStageVerify: true` → dispatch the in-stage clean-room verify now (honoring `autoFixEligible`); `verifyGate: "standard"` → present the Standard Verify Gate; `verifyGate: "manual-print"` → print the `verifyCommand` for the user; non-empty `invalidAutoVerifyKeys` → print a one-line warning. Then **print the NEXT-STEPS block verbatim as your absolute last output — nothing after its sentinel line.**

## Gotchas

- Users often front-load their feature description with tech decisions because that's how engineers think. Gently but firmly redirect to requirements. Don't be preachy about it — just reframe what they said.
- If the user provides a very detailed initial description, don't skip the interview. Use their description as a starting point but probe for what's missing. Long descriptions often have big gaps in edge cases and non-functional requirements.
- Don't number requirements sequentially across categories (REQ-01, REQ-02...). Use category prefixes (REQ-AUTH-01, REQ-PERF-01) so inserting new requirements doesn't require renumbering.
- The PRD should be readable by a non-technical stakeholder. If a section requires deep technical knowledge to understand, it probably belongs in the tech spec, not the PRD.
