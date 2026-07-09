---
# GENERATED — DO NOT EDIT. Source: skills/forge-4-backlog/SKILL.md. Regenerate: python3 scripts/build-adapters.py
name: forge-4-backlog
description: Generate a structured backlog.json from forge implementation specs, then validate it via the loop runner. Use when user runs /feature-forge:forge-4-backlog or asks to create a backlog for a forge feature after specs are complete. This is the canonical backlog generator for the forge pipeline. Do NOT trigger for standalone backlog creation outside the forge pipeline context.
---

# forge-4-backlog — Backlog Generator (pipeline orchestrator)

Generate a complete, validated `backlog.json` from the implementation spec
suite, ready for the loop runner.

This skill is a **thin orchestrator**: it owns the *pipeline* concerns
(prerequisite checks, spec loading, plan review, validation, pipeline-state and
commit). The actual **authoring craft** — granularity, acceptance criteria,
`agentDelegation`, the schema, examples — lives in the rauf plugin's
**`author-backlog`** skill, which this skill delegates to. That keeps a single
home for backlog-authoring knowledge, shared with the repo-wide ad-hoc flow.

## Prerequisites

Read and follow `references/shared-conventions.md` for feature name validation, configuration reading, and force mode handling before proceeding. Resolve the feature directory `{resolvedFeatureDir}` via the **Feature Directory Resolution** block in `references/shared-conventions.md` — do not hardcode `{specsDir}/{feature}/` (see Step 1).

Resolve the **backlog directory** `{backlogDir}`:
- **`backlogDir` unset (default):** the backlog lives at the resolved feature directory — `{resolvedFeatureDir}/backlog.json` — for both flat and nested features, exactly as today.
- **`backlogDir` configured:** compose a **per-feature subpath** — `{backlogDir}/{feature}/` — so each epic member's backlog stays independent (the authored file lands at `{backlogDir}/{feature}/backlog.json`). A bare shared `backlogDir` would collide across a multi-feature epic and violate REQ-COMPAT-03; the `{feature}` segment prevents that. Standalone features under a configured `backlogDir` likewise resolve to `{backlogDir}/{feature}/`, which is backward-compatible because each standalone feature name is already unique.

This is the **single** place this rule is implemented. forge-5-loop's backlog-file check must read the same composed `{backlogDir}/{feature}/backlog.json` (that matching forge-5-loop edit lands in item 016), and forge-verify's backlog-mode load uses the same path. rauf itself is unchanged: backlogs remain per-feature and rauf is still launched against a single per-feature backlog path — only the *path composition* changes (REQ-COMPAT-03).

**Let `{resolvedBacklogDir}` denote the composed target of this rule** — i.e. `{backlogDir}/{feature}` when a `backlogDir` is configured, else `{resolvedFeatureDir}`. Every downstream step below (authoring, validation) uses `{resolvedBacklogDir}`, never the bare config value, so the per-feature `{feature}` segment is never dropped.

Resolve the **loop runner** from the `loopRunner` block in `forge.config.json`, filling missing fields from the defaults in `references/forge-config-schema.json` (defaults to rauf). You need its `bin`, `validateCommand`, `versionCommand`, `minRunnerVersion`, and `installHint`.

**Turn structure reminder:** Output analysis/context as text, then route ALL questions through the host's question mechanism. Never embed questions in text output — the user will not be prompted and the session will stall.

## Step 1: Validate Prerequisites

**Resolve the feature directory first.** Invoke the **Feature Directory Resolution** block in `references/shared-conventions.md` to turn the bare feature name into `{resolvedFeatureDir}` (exit 0 → stdout is the absolute dir; exit ≥ 1 → STOP and surface the finding verbatim). Read state and specs from `{resolvedFeatureDir}/` everywhere this skill previously wrote `{specsDir}/{feature}/`. Standalone features resolve to their flat path exactly as today.

**Prerequisite check:** Read `{resolvedFeatureDir}/.pipeline-state.json`. If not in force mode, stages `forge-1-prd`, `forge-2-tech`, and `forge-3-specs` must all be `complete`. If not, STOP and tell the user which prerequisites are missing.

**Verification check.** Check whether the specs have been verified. If not, use the host's question mechanism to warn with the cost of skipping: "Specs haven't been verified yet. Recommended: run `/feature-forge:forge-verify {feature}` first — unverified specs can carry gaps or contradictions that get baked into backlog items and only surface mid-loop, where they're far more expensive to fix. Continue anyway?" Offer **Verify first (recommended)** · **Continue without verifying**.

## Step 2: Load All Specs

Read all spec documents into context:
- `{resolvedFeatureDir}/PRD.md`
- `{resolvedFeatureDir}/tech-spec.md`
- `{resolvedFeatureDir}/##-*.md` (all implementation specs)

If the spec suite is large (8+ documents), focus on loading the architecture layout (01-*), shared types (00-*), and testing strategy documents first. Load individual subsystem specs as needed when writing the corresponding backlog items, rather than loading all specs simultaneously.

## Step 3: Plan the Backlog

Before writing any JSON, walk the specs and create a backlog plan: discrete work items, ordered by dependency (foundation first), with priorities, each scoped for a single loop iteration.

Present the plan as a numbered list:
```
Proposed backlog for {feature} ({N} items):

  001 [P1] Scaffold module with project manifest, build config, and entry points
      Depends on: (none)
      Specs: 00-core-definitions.md, 01-architecture-layout.md

  002 [P1] Implement shared types and error hierarchy
      Depends on: 001
      Specs: 00-core-definitions.md
  ...
```

After presenting the plan as text, use the host's question mechanism following the **Decision Support** protocol in `references/shared-conventions.md`: recommend this breakdown as the default (it's your evidence-backed read of the specs and dependency order) and name the trade-off that governs item granularity — finer items are each easier to verify in one loop iteration but multiply coordination and dependency edges; coarser items mean fewer handoffs but risk an item too big to complete or verify in a single iteration. Lead with: "I recommend this breakdown. Any items to split, merge, or reorder?" Do NOT include this question in your text output. Wait for the user's response before generating the JSON.

## Step 4: Author backlog.json — delegate to `author-backlog`

**Invoke the rauf plugin's `author-backlog` skill** (via the Skill tool) to write
`{resolvedBacklogDir}/backlog.json`. Pass it:

- the target backlog directory `{resolvedBacklogDir}`,
- the approved plan from Step 3,
- the spec context loaded in Step 2,
- the project's `typeCheckCommand` / `testCommand` (from `forge.config.json`) so acceptance criteria are concrete and runnable.

`author-backlog` owns all item-quality rules (granularity hard limits, self-contained descriptions, acceptance criteria, `agentDelegation`, the correct `type`/`status` enums, `dependsOn`, `specReferences`, the schema source). Do not re-encode them here — follow whatever it produces.

> **If the rauf plugin / `author-backlog` skill is not available:** fall back to
> authoring inline using the schema source rule (prefer the project's installed
> `{stateDir}/backlog.schema.json`, else the published `$id`
> `https://raw.githubusercontent.com/garygentry/rauf/main/schemas/backlog.schema.json`),
> and tell the user the rauf plugin provides richer authoring guidance.

**Forge-specific item requirements** layered on top of `author-backlog`'s output:
- `specReferences` must be paths **relative to the project root** (e.g. `specs/auth/00-core-definitions.md`), NOT relative to the backlog file. The validator resolves them from the project root (not from `--specs-dir`, which only gates the check).

> **Backlog schema & rauf contract are unchanged (REQ-COMPAT-03).** Epic membership adds **no** fields to backlog items — dependency edges live in the epic manifest, never in any backlog item. The JSON written here is byte-for-byte the same shape as a pre-epic standalone feature's backlog, and rauf is still launched against a single per-feature backlog path. Only the *path composition* changes (the `{feature}` segment in the backlog-directory rule above), not the schema or rauf's CLI surface.

## Step 5: Validate via the loop runner

Validate the generated backlog by running the runner's **validate command**
(`loopRunner.validateCommand`), rendered with `{resolvedBacklogDir}` and `{specsDir}`
substituted — the rauf default:

```bash
rauf backlog validate . --backlog {resolvedBacklogDir} --specs-dir {specsDir} --json
```

Interpret the result:
- **exit 0** → valid (warnings allowed). Proceed.
- **exit 1** → validation findings. Parse `{ valid, findings[] }`, fix the items, re-run. Do NOT present the backlog to the user until it validates.
- **exit 2** → usage/IO error (unreadable file, bad JSON). Fix and re-run.

> **forge-4 runs before forge-5's install gate**, so the runner may not be set
> up yet. Degrade gracefully rather than hard-failing:
> 1. First run `loopRunner.versionCommand` (`rauf version --json`). If the
>    binary is **missing**, or its version is **< `minRunnerVersion`**
>    (semver-compare), do NOT block authoring: keep the authored backlog, emit a
>    loud warning with `loopRunner.installHint`, mark validation as skipped, and
>    continue to Step 6. forge-5 will enforce the gate before running.
> 2. If the binary is present and new enough but the project isn't set up
>    (`validate` reports the project marker missing), likewise warn and continue
>    — validation will run cleanly once `rauf install .` has been done.

## Step 6: Review with User

Present a summary: total items N, dependency-chain depth, estimated loop iterations (`ceil(pendingItems * loopIterationMultiplier)`). Note whether validation passed or was skipped (runner not yet available).

State that the backlog is ready and invite adjustments before committing — a statement, not a forced gate: "Backlog is ready. Tell me if you want any items split, merged, or reordered; otherwise I'll record state and commit." Proceed to Step 7 unless the user asks for changes.

## Step 7: Update Pipeline State and Commit

Write pipeline state conforming to `references/pipeline-state-schema.json`. Follow the Git Commit Protocol in `references/shared-conventions.md`.

1. Update `{resolvedFeatureDir}/.pipeline-state.json`:
   - Record `artifacts` (path to backlog.json)
   - Set `stages.forge-4-backlog.basedOnVersions` to `{"forge-1-prd": <current version>, "forge-2-tech": <current version>, "forge-3-specs": <current version>}`
   - Set `currentStage` to `forge-5-loop`
   - Check downstream stages (`forge-5-loop`, `forge-6-docs`). If any have `basedOnVersions` referencing an older version of `forge-4-backlog`, set their status to `stale`.
2. **Offer a note — don't force one.** As a statement (not a blocking question), let the user know they can jot anything worth preserving across sessions and you'll store it in the `notes` field. If they volunteer something, store it; otherwise proceed.
3. If `gitCommitAfterStage` is true, follow the Git Commit Protocol: stage files, attempt commit (marking `stages.forge-4-backlog.status` `complete` with `commitHash: null` in that commit), then record the artifact-commit hash via the protocol's two-commit follow-up (never `--amend`) only on success. If commit fails, leave status as `in-progress`.
4. If verification was available but the user chose to skip it, record `stages.forge-verify-backlog.status` as `"skipped"` in pipeline state.
5. **Close with the Stage Exit Protocol** (single-sourced in `references/stage-exit-protocol.md`; do not improvise a "Next steps" list). Lead with the item count ("Backlog complete with {N} items."), then:

**Close this stage with the Scripted Stage Exit** (contract: `references/stage-exit-protocol.md`; do not improvise a "Next steps" list). Run:

```bash
R="$(bash -c 'for d in "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" stage-exit --feature "{feature}" --stage forge-4-backlog --specs-dir "{specsDir}" --host generic
```

Obey the DIRECTIVES it prints, in order, per the directive contract: `runInStageVerify: true` → dispatch the in-stage clean-room verify now (honoring `autoFixEligible`); `verifyGate: "standard"` → present the Standard Verify Gate; `verifyGate: "manual-print"` → print the `verifyCommand` for the user; non-empty `invalidAutoVerifyKeys` → print a one-line warning. Then **print the NEXT-STEPS block verbatim as your absolute last output — nothing after its sentinel line.**

## Gotchas

- The loop runs each item in a FRESH context. Every item description must be self-contained — `author-backlog` enforces this, but double-check Step-3 plan items aren't "same as above."
- Spec references must be project-root-relative paths that actually exist — the validate command enforces this when `--specs-dir` is passed (resolving them from the project root).
- Don't present a backlog to the user before it validates (or before you've explicitly recorded that validation was skipped because the runner isn't installed yet).

---

## Host execution notes

This skill was authored Claude-first; the body above refers to "the host's question mechanism", "the host's subagent mechanism", and "the host's background-execution mechanism". Use your runtime's equivalent for each — and if your runtime has no such tool:

- **User input:** ask the question directly and wait for the answer before proceeding. Do not skip a required question or assume an answer.
- **Subagents:** if your host cannot dispatch the named custom agent, run that step inline yourself.
- **Background / monitoring:** run long-lived commands in the foreground (or your host's background facility) and report progress as it arrives.
