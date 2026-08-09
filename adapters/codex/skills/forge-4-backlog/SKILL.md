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

Resolve the **loop runner** with the command below — it merges this project's `loopRunner` block over the schema defaults deterministically (defaults to rauf), so do not read the config schema for defaults. Use the emitted object as the effective `loopRunner`; you need its `bin`, `validateCommand`, `versionCommand`, `minRunnerVersion`, and `installHint`. If the call exits 2, surface the plain `Error:` line from stderr verbatim and fall back to the documented rauf defaults.

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" effective-config --config ./forge.config.json --json
```

**Turn structure reminder:** Output analysis/context as text, then route ALL questions through the host's question mechanism. Never embed questions in text output — the user will not be prompted and the session will stall.

## Step 1: Validate Prerequisites

**Resolve the feature directory first.** Invoke the **Feature Directory Resolution** block in `references/shared-conventions.md` to turn the bare feature name into `{resolvedFeatureDir}` (exit 0 → stdout is the absolute dir; exit ≥ 1 → STOP and surface the finding verbatim). Read state and specs from `{resolvedFeatureDir}/` everywhere this skill previously wrote `{specsDir}/{feature}/`. Standalone features resolve to their flat path exactly as today.

**Prerequisite check:** Read `{resolvedFeatureDir}/.pipeline-state.json`. If not in force mode, stages `forge-1-prd`, `forge-2-tech`, and `forge-3-specs` must all be `complete`. If not, STOP and tell the user which prerequisites are missing.

After the prerequisite check, invoke the **Stage-Entry Guard** block in `references/shared-conventions.md` with `{stage}` = `forge-4-backlog` — it detects an interrupted or complete `backlog.json`, runs the resume/restart or new-version gate, and stamps entry before Step 2 loads the specs. (The backlog is a single artifact, so "resume" means: reuse the existing `backlog.json` if the previous run wrote it, rather than re-authoring from scratch.)

Then invoke the **Epic-Member Base Guard** block in `references/shared-conventions.md` (this stage does not run Epic Context Injection, so invoke it explicitly here). It self-gates to a no-op for standalone features; for a nested epic member on a branch that lacks the epic manifest it stops with a home-branch pointer (Issue #125).

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

**Return contract.** This is the **delegate-and-resume** posture of "Caller-side resumption: the declared resume point" in `references/stage-exit-protocol.md`. `author-backlog` is a sub-skill of this stage, not its terminal: when it returns, control returns to **this skill, at Step 5** — forge-4 still owns the stage and its terminal output. Two of the sub-skill's own instructions do not apply on this delegated path (it also serves direct user invocation, and those instructions are its direct-invocation posture): its wait-for-user-approval-before-writing gate is already satisfied by Step 3's approved plan — do not re-ask; and its closing "run `rauf backlog validate` … and confirm the validated result" posture is subsumed by Step 5, which owns validation (see Step 5's ownership note). Do not adopt the sub-skill's report-and-stop terminal — it is the freshest instruction in context after the return, but it belongs to the sub-skill: continue to Step 5 in the same turn; Steps 6 and 7 still run, and the stage closes only at Step 7's exit.

> **If the rauf plugin / `author-backlog` skill is not available:** fall back to
> authoring inline using the schema source rule (prefer the project's installed
> `{stateDir}/backlog.schema.json`, else the published `$id`
> `https://raw.githubusercontent.com/garygentry/rauf/main/schemas/backlog.schema.json`),
> and tell the user the rauf plugin provides richer authoring guidance.

**Forge-specific item requirements** layered on top of `author-backlog`'s output:
- `specReferences` must be paths **relative to the project root** (e.g. `specs/auth/00-core-definitions.md`), NOT relative to the backlog file. The validator resolves them from the project root (not from `--specs-dir`, which only gates the check).
- **Epic members — cross-member shared-state coupling (#144).** When authoring the backlog for an epic member, check whether this feature writes or migrates a file that a *sibling* member's already-shipped tests pin (its `mutatesShared[]` hint in `epic-manifest.json`, or a shared data corpus / generated fixture its specs say it mutates). If so, schedule a **reconciliation item up front** — before the first mutating item — that regenerates or re-pins the sibling's fixture (or updates the sibling test to the new shape), so the sibling suite stays green instead of red-gating every commit mid-loop. This is the authoring counterpart to forge-verify's CHECK-E10.
- **Generated-artifact freshness vs. `testCommand` `--check` gates (#145).** If the project's `testCommand` gates on staleness of generated artifacts (`<generator> --check`-style sub-commands that fail when a checked-in generated file is out of date), then any item that regenerates **one** such artifact must regenerate **and commit all** the sibling artifacts those `--check` gates depend on — enumerate the whole gated set, not just the artifact the item is "about", or the item passes locally yet red-gates on the stale-generated check. Pass this to `author-backlog` alongside `testCommand` so the full regeneration sequence lands in each affected item; forge-verify's CHECK-B26 flags a partial set or an ungated regenerator after the fact.
- **Lifecycle-gated artifacts — no test item forcing a forbidden transition (#150).** A test/e2e item whose acceptance asserts a *published / released / approved / human-reviewed* artifact state must either (a) `dependsOn` an explicit, human-gated publish/review item that legitimately produces that state, or (b) assert the state via a **dev-build / fixture path**. A test item must **never** be the only thing forcing a lifecycle transition another item pins the other way (e.g. one item keeps artifact `X` *draft* while a test demands it *published*, with nothing between to publish it) — the loop, unable to publish or obtain a human sign-off, will **fabricate** the provenance. `author-backlog` owns the general rule; forge-verify's CHECK-B27 flags a contradictory pair with no publisher in the dependency closure after the fact.

> **Backlog schema & rauf contract are unchanged (REQ-COMPAT-03).** Epic membership adds **no** fields to backlog items — dependency edges live in the epic manifest, never in any backlog item. The JSON written here is byte-for-byte the same shape as a pre-epic standalone feature's backlog, and rauf is still launched against a single per-feature backlog path. Only the *path composition* changes (the `{feature}` segment in the backlog-directory rule above), not the schema or rauf's CLI surface.

## Step 5: Validate via the loop runner

**Validation ownership.** This step is authoritative for validation, whether or not `author-backlog` already ran its own `rauf backlog validate`: this stage carries the degradation rules for a missing/old/not-set-up runner (below) that the sub-skill does not, and this step's result is what Step 6 reports. A validate the sub-skill already ran cleanly makes this a cheap idempotent re-run, never a reason to skip it — and the sub-skill's validate never discharges this step.

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

## Step 5b: Topology Report (advisory)

After validation (or a recorded skip), report the backlog's dependency topology. Pipe the runner's **list command** (`loopRunner.listCommand`, rendered with `{resolvedBacklogDir}` — the rauf default shown below) into the topology verb. It is a pure function over the runner's item array and never takes a `backlog.json` path:

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
rauf backlog list . --backlog {resolvedBacklogDir} --json | python3 "$R/scripts/forge-session.py" backlog-topology --items-stdin --json
```

ALWAYS print the metrics, citing the runner counts from the payload:

```
Topology: {itemCount} items, {rootCount} roots, max chain depth {maxChainDepth}.
Per-root fan-out (gated subtree size): {id}→{gatedCount}, … (largest first).
```

Only when the payload's `warnings` array is non-empty, also render this block, including only the bullet(s) for warnings that actually fired:

```
⚠️ Fragile topology (advisory — does not block authoring):
  - single-root-fanout: root {id} gates {gatedCount}/{itemCount} items (≥50%).
  - chain-depth: max chain depth {maxChainDepth} is ≥50% of {itemCount} items.
A single defect in a high-fan-out root or a long chain can strand most of the backlog
(the loop-recovery incident: 3 roots gating 81%, 13-deep chain). Consider splitting the
gating root's subtree or flattening the chain — this is a heads-up, not a gate.
```

This step is **guidance only — it never fails authoring**. If the topology command itself errors, note the error and continue to Step 6 (advisory).

## Step 6: Review with User

Present a summary: total items N, dependency-chain depth, estimated loop iterations (`ceil(pendingItems * loopIterationMultiplier)`). Note whether validation passed or was skipped (runner not yet available).

This is a **non-blocking review (invitation)** — per the **Stage Review Gate** in `references/shared-conventions.md`: sibling stages block here; this stage deliberately does not, and the invitation obliges you to continue, not stop.

State that the backlog is ready and invite adjustments before committing — a statement, not a forced gate: "Backlog is ready. Tell me if you want any items split, merged, or reordered; otherwise I'll record state and commit." **Proceed to Step 7 in this same turn** unless the user asks for changes — emitting the invitation and stopping strands the stage before Step 7 runs.

## Step 7: Update Pipeline State and Commit

Before writing state or running the stage exit, invoke the **Stage-Completion Re-check** block in `references/shared-conventions.md` with `{stage}` = `forge-4-backlog` — a resumed mid-stage continuation must not overwrite a committed `backlog.json` or re-fire a finished exit.

Pipeline state is written by the `state-*` verbs — see the Pipeline State Protocol in `references/shared-conventions.md`. Follow the Git Commit Protocol in `references/shared-conventions.md`.

1. Record completion by running `state-complete` (below) with `--version`, `--artifact backlog.json`, and `--based-on forge-1-prd=<current version> --based-on forge-2-tech=<current version> --based-on forge-3-specs=<current version>`. It sets `status: "complete"`, `completedAt`, the version and `basedOnVersions`, and applies the downstream staleness cascade deterministically, so no downstream status is set by hand.
2. **Offer a note — don't force one.** As a statement (not a blocking question), let the user know they can jot anything worth preserving across sessions and you'll store it in the `notes` field. If they volunteer something, store it; otherwise proceed.
3. If `gitCommitAfterStage` is true, follow the Git Commit Protocol: stage files, attempt commit (marking `stages.forge-4-backlog.status` `complete` with `commitHash: null` in that commit), then record the artifact-commit hash via the protocol's two-commit follow-up (never `--amend`) only on success. If commit fails, leave status as `in-progress`.
4. If verification was available but the user chose to skip it, persist that skip through `state-verify` using the fence below — never by hand. The choice to proceed unverified is durable state owned by the scripted writer.
5. **Close with the Stage Exit Protocol** (single-sourced in `references/stage-exit-protocol.md`; do not improvise a "Next steps" list). Lead with the item count ("Backlog complete with {N} items."), then:

The `state-complete` call for item 1 — and the `state-note` call only when the user volunteered a note in item 2 — with the portable plugin-root prelude. Add `--epic "{epic}"` to each call when this feature is an epic member — required, per the Pipeline State Protocol in `references/shared-conventions.md`:

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" state-complete \
  --feature "{feature}" --stage forge-4-backlog --version {n} \
  --based-on "forge-1-prd=<n>" --based-on "forge-2-tech=<n>" --based-on "forge-3-specs=<n>" \
  --artifact backlog.json --specs-dir "{specsDir}"
# ONLY run the next call if the user volunteered a note in item 2 — otherwise stop here.
python3 "$R/scripts/forge-session.py" state-note \
  --feature "{feature}" --note "<what the user volunteered>" --specs-dir "{specsDir}"
```

The `state-verify` call for item 4 — **only** when verification was available and the user explicitly chose to skip it. A verifier that could not be dispatched is not a skip, so do not run this on an unavailable-tool path. And only over an entry that is absent or unresolved: if `stages.forge-verify-backlog` already records `passed` or `findings-applied`, do **not** run the call — those statuses are resolved, the verb refuses to demote them to `skipped` (#203), and the existing result stands with nothing written. Add `--epic "{epic}"` when this feature is an epic member — required, per the Pipeline State Protocol in `references/shared-conventions.md`:

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" state-verify \
  --feature "{feature}" --stage forge-4-backlog --status skipped --specs-dir "{specsDir}"
```

If that verb exits 2, surface its plain `Error:` line verbatim and stop — the skip is not persisted, so the exit below would route on state that does not exist on disk.

**Determine `--verify-capability` before running the exit** (full rule: `references/stage-exit-protocol.md`; summary: **Verify Capability** in `references/shared-conventions.md`). Pass `interactive` only when a question mechanism equivalent to the host's question mechanism is available **and** a clean-room `forge-verifier` may be dispatched; otherwise pass `manual`. Dispatch capability means **permitted** dispatch, not a listed tool — the test is "may I dispatch `forge-verifier` right now", not "is a dispatch tool in my tool surface". A session that bars *unsolicited* dispatch while offering a question mechanism is therefore **`interactive`, not `manual`**: the gate's affirmative choice is the user request that authorizes the dispatch. Such a bar is never grounds to skip verification, and never grounds to fence the production successor while verification is unresolved — on the `runInStageVerify: true` path the emitted `verifyGate` stays `none`, so reuse the Standard Verify Gate block for consent with **choice 2 omitted**, leaving exactly two choices: *Verify now* (recommended) and *Skip for now*. The clean-room `forge-verifier` is **dispatched on the affirmative choice**, never merely printed for the user to run later; *Skip for now* is persisted as an explicit `skipped` before any advancing block. Add `--epic "{epic}"` to the call below when this feature is an epic member.

**Close this stage with the Scripted Stage Exit** (contract: `references/stage-exit-protocol.md`; do not improvise a "Next steps" list). Run:

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/forge-session.py" stage-exit --feature "{feature}" --stage forge-4-backlog --specs-dir "{specsDir}" --host generic --verify-capability "{verify-capability}"
```

Obey the DIRECTIVES it prints, in the consumption order this protocol fixes: surface `invalidAutoVerifyKeys` and every `warnings` entry first; `runInStageVerify: true` → run the in-stage clean-room verify chain now (honoring `autoFixEligible`, and asking through the Standard Verify Gate first when you may not dispatch unsolicited); `verifyGate: "standard"` → present the Standard Verify Gate; `verifyGate: "manual-print"` → print the `verifyCommand` for the user and do **not** dispatch inline. Then, and only when `terminalOwnedBy` is `"self"`, **print the NEXT-STEPS block verbatim as your absolute last output — nothing after its sentinel line.** A `terminalOwnedBy: "outer"` payload carries `nextSteps: null`: return your structured result to the caller and print no terminal block at all.

## Gotchas

- The loop runs each item in a FRESH context. Every item description must be self-contained — `author-backlog` enforces this, but double-check Step-3 plan items aren't "same as above."
- Spec references must be project-root-relative paths that actually exist — the validate command enforces this when `--specs-dir` is passed (resolving them from the project root).
- Don't present a backlog to the user before it validates (or before you've explicitly recorded that validation was skipped because the runner isn't installed yet).

---

## Host execution notes (Codex)

This skill was authored Claude-first; the body above refers to "the host's question mechanism", "the host's subagent mechanism", and "the host's background-execution mechanism". On Codex:

- **User input:** Codex has no structured question tool — ask the question directly and wait for the user's reply before proceeding. Never skip a required question or assume an answer.
- **Subagents:** spawn a Codex subagent using the named custom agent under `.codex/agents/<name>.toml`. Codex spawns a subagent only when explicitly asked; if the custom agent is unavailable, run that step inline yourself.
- **Background / monitoring:** run long-lived runner commands in your shell session and report progress as it arrives — there is no Claude-style background or monitoring tool to arm.
