---
name: forge-5-loop
description: "Execute the autonomous coding loop (rauf by default) against a forge feature's backlog. Use when user runs /feature-forge:forge-5-loop or /feature-forge:forge-5-rauf-loop, or asks to run rauf / run the loop / implement a forge feature after the backlog is created and verified. Do NOT trigger for general rauf usage, standalone loop runs, or implementation tasks outside the forge pipeline."
metadata:
  argument-hint: "<feature-name>"
---

# forge-5-loop — Autonomous Loop Executor

Execute the autonomous coding loop against a forge feature's backlog. The loop
spawns a fresh agent session per backlog item, implementing each task with full
verification.

The loop **runner** is configured, not hardcoded. feature-forge talks to it
through the `loopRunner` block in `forge.config.json`; rauf is the default and
reference implementation (see `references/ralph-loop-contract.md`). Every command
below is rendered from `loopRunner` with token substitution — there are no
hardcoded `rauf …` commands in this skill, and even the human log filename is
tokenized as `{loopRunner.logFile}`.

## Resolve the loop runner

Read `forge.config.json`. Build the effective `loopRunner` by taking its
`loopRunner` block (if present) and filling any missing field from the defaults
in `references/forge-config-schema.json`. **If `forge.config.json` has no
`loopRunner` block at all, state plainly: "No loopRunner configured — defaulting
to the rauf loop runner."** then proceed with the full default block.

Token substitution applies to every `*Command` string. Substitute:

- `{bin}` → `loopRunner.bin` (default `rauf`)
- `{backlogDir}` → the resolved backlog directory (Step 1d / 2b), relative to project root
- `{specsDir}` → `specsDir` from config
- `{iterations}` → the computed iteration count (Step 2a)

Whenever this skill says "run the **run command**" / "**status command**" /
etc., it means the corresponding substituted `loopRunner.*Command`.

**Turn structure reminder:** Output analysis/context as text, then route ALL questions through `AskUserQuestion`. Never embed questions in text output — the user will not be prompted and the session will stall.

## Step 1: Validate Prerequisites

Read and follow `references/shared-conventions.md` for feature name validation, configuration reading, and force mode handling.

### 1a. Pipeline State Check

**Resolve the feature directory first.** Invoke the **Feature Directory Resolution** block in `references/shared-conventions.md` to turn the bare feature name into `{resolvedFeatureDir}` (exit 0 → stdout is the absolute dir; exit ≥ 1 → STOP and surface the finding verbatim). Read state from `{resolvedFeatureDir}/` everywhere this skill previously wrote `{specsDir}/{feature}/` (the 1e backlog path and the Step 3a / Step 5 state writes). Standalone features resolve to their flat path exactly as today.

Read `{resolvedFeatureDir}/.pipeline-state.json`. If not in force mode, `stages.forge-4-backlog` must be `complete`. If not, STOP and tell the user: "Backlog hasn't been created yet. Run `/feature-forge:forge-4-backlog {feature}` first."

### 1b. Verification Check

Check if `stages.forge-verify-backlog` exists and has status `passed` or `findings-applied`. If not, use `AskUserQuestion` to warn with the cost of skipping:

"Backlog hasn't been verified yet. Recommended: run `/feature-forge:forge-verify {feature}` first — the loop implements items autonomously and commits as it goes, so a bad item (wrong scope, missing dependency, untestable acceptance criteria) is far cheaper to catch now than after several commits build on it. Continue anyway?" Offer **Verify first (recommended)** · **Continue without verifying**.

### 1b-epic. Epic Dependency Gate

Read the resolved feature's `.pipeline-state.json`. **If it has no `epic` key, skip this sub-step entirely** (standalone feature — REQ-COMPAT-01; standalone runs are unchanged). Otherwise:

1. Run `render-status "{epic}" --specs-dir "{specsDir}" --json` via the helper:

   ```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/epic-manifest.py" \
  render-status "{epic}" --specs-dir "{specsDir}" --json
   ```

2. Find this feature's entry; read its `unmetDeps` (the direct `dependsOn` not yet complete-for-orchestration per `00-core-definitions.md §7`).
3. **If `unmetDeps` is empty**, proceed to 1c with no prompt.
4. **If `unmetDeps` is non-empty**, use `AskUserQuestion` (do NOT inline the question as prose) to warn that the feature depends on the unmet dependencies, which are not yet complete, and that running the loop now means implementing against contracts that may still change:

   > "{feature} depends on {unmetDeps joined}, which are not yet complete. Running the loop now means implementing against contracts that may still change. Proceed anyway, or stop and finish the dependencies first?"

   Require an **explicit "Proceed anyway"** choice to continue (REQ-ORCH-04). "Stop" aborts before any runner setup. `--force` (shared-conventions Force Mode) also bypasses this gate with the standard force warning.
5. If `render-status` fails, **STOP** — do not silently run a loop whose dependency state is unverifiable (REQ-ROBUST-02). Surface per the exit-1/exit-2 split in the **Feature Directory Resolution** block of `references/shared-conventions.md` (exit 1 → parse `{findings[]}` from stdout; exit 2 → surface the plain `Error:` stderr line verbatim — no findings JSON to parse).

This gate runs **before** the runner version/setup gates (1c/1d) so a blocked feature stops early, before any runner side-effects.

### 1c. Runner Version Gate

Enforce `loopRunner.minRunnerVersion` **before** doing anything else with the runner. This is what turns "the runner is missing or too old" into a clear, actionable stop instead of a cryptic mid-run failure.

1. Run the **version command** (`loopRunner.versionCommand`, default `rauf version --json`) via Bash.
2. Parse `{ "version": "<semver>" }` from stdout. Do NOT use plain `rauf version` (its human output is `rauf v0.6.0` with a `v` prefix) — always the `--json` form.
3. **Semver-compare** (NOT string-compare) the reported version against `loopRunner.minRunnerVersion` (default `0.6.0`), numerically by major, then minor, then patch.

**Any of the following is a HARD GATE FAILURE — do NOT proceed to run the loop.** STOP, show `loopRunner.installHint`, and include the raw command output for diagnosis:

- The version command is not found or exits non-zero (the binary isn't installed).
- Its stdout is not valid JSON, has no `version` field, or `version` is not a valid semver string.
- The reported version is **< `minRunnerVersion`**.

For the version-too-old case, phrase it concretely, e.g.: "Your rauf is {reported}, but feature-forge needs ≥ {minRunnerVersion} — 0.6.0 is the floor that ships the agent-selection surface (`--agent` / `rauf agents`) the loop relies on. {installHint}". When the gate fails because the output couldn't be parsed, say so and show what the command printed before the `installHint`.

> `installHint` points at the runner **CLI** install/upgrade — distinct from
> `setupHint` (1d), which installs the runner's per-project artifacts.

### 1d. Runner Setup Check (precondition file)

Check that `loopRunner.preconditionFile` (default `.rauf.json`) exists in the project root. If not:

- **If `loopRunner.name == "rauf"` and a legacy `.ralph.json` (or `.ralph/` directory) exists**, this is an un-migrated Ralph project. STOP: "This project is still on the legacy **Ralph** layout. Run `rauf migrate .` first (the loop runner only understands `.rauf/` and `RAUF_*` signals), then re-run `/feature-forge:forge-5-loop {feature}`."
- **Otherwise**, STOP and show `loopRunner.setupHint` (default: "Run `rauf install .` …"), e.g. "The loop runner isn't set up in this project ({preconditionFile} is missing). {setupHint}"

### 1e. Backlog File Check

Resolve the backlog file path (matching forge-4-backlog's composition rule, item 015 / §6.2):
- If `backlogDir` is set in `forge.config.json`: use `{backlogDir}/{feature}/backlog.json` (the per-feature subpath, so each epic member's backlog stays independent — the `{feature}` segment prevents collisions across a multi-feature epic)
- Otherwise: use `{resolvedFeatureDir}/backlog.json`

Verify the file exists on disk. If not, STOP and tell the user: "No backlog.json found at {path}. Run `/feature-forge:forge-4-backlog {feature}` to generate it."

### 1f. Branch Pre-flight (if using git)

The runner commits each item onto the current branch. Skip if not a git repo or `branchPerFeature` is false. Otherwise run the **Branch Reconciliation** block in `references/shared-conventions.md` (it runs `reconcile-branch` and, on `warn-drift` — you are on the default branch — strongly recommends creating `{branchPrefix}{feature}` via `AskUserQuestion` before the loop commits; on `adopt-current` it updates the recorded branch to the current one, never pushing you back to a stale/imposed branch). Never hard-stop.

## Step 2: Construct the Loop Command

### 2a. Analyze Backlog

Run the **list command** (`loopRunner.listCommand`, default `rauf backlog list . --backlog {backlogDir} --json`) and count items by status: `pending`, `in_progress`, `done`, `blocked`.

Calculate the iteration count: `ceil((pending + in_progress) * loopIterationMultiplier)` where `loopIterationMultiplier` comes from `forge.config.json` (default: 1.5). This headroom allows retries without exhausting iterations.

If there are no pending or in_progress items, STOP and tell the user: "All backlog items are already done or blocked. Nothing to run."

If there are `blocked` items, note them — the user may want `--retry-blocked`.

### 2b. Resolve Backlog Directory

`{backlogDir}` is a **directory path** (not a file path), relative to the project root.

- If `backlogDir` is set in config: use the per-feature subpath `{backlogDir}/{feature}` (matching the 1e composition rule and forge-4-backlog §6.2).
- Otherwise: use `{resolvedFeatureDir}` (the directory containing `backlog.json`).

**Example:** If `specsDir` is `./specs` and feature is `auth`, `{backlogDir}` is `specs/auth`.

### 2c. Build Command

Render the **run command** (`loopRunner.runCommand`) with token substitution, e.g. the rauf default becomes:

```
rauf loop run . --backlog specs/auth --iterations 15
```

### 2d. Confirm with User

Use `AskUserQuestion` to present the rendered run command and options. The following block is the content for `AskUserQuestion` — do NOT output it as text:

```
Ready to run the loop for {feature}:

  {rendered runCommand}

Backlog summary:
  - Pending: {pending}
  - In progress: {in_progress}
  - Done: {done}
  - Blocked: {blocked}
  - Iterations: {iterationCount} ({activeItems} items x {loopIterationMultiplier} multiplier)

Optional flags you can add (rauf): --review, --model <model>, --timeout <min>,
--retry-blocked. For the full optional-flags catalog and the model-selection
precedence (item.model > --model/options > project default > provider default),
read references/runner-contract.md.

Proceed with this command, or would you like to adjust?
```

For the full loop-runner contract — event-stream vs. log-fallback launch, the live-supervision/monitor rules, and the model-selection precedence — read `references/runner-contract.md`. If the user requests additional flags, append them to the rendered run command.

#### Agent selection (gated on `loopRunner.agentArgument`)

**Capability gate.** Everything below applies **only when** the effective `loopRunner.agentArgument` is present and non-empty. **When it is absent or empty, Step 2d is exactly the confirmation above — no probe, no agent question, no availability listing, no `Agent:` line — byte-identical to today** (REQ-PLUG-02, REQ-COMPAT-01). The full algorithm, precedence, and verbatim message shapes are in `## Agent selection` of `references/runner-contract.md`; read it. When the gate is on, augment Step 2d in order:

- **(a) Probe once.** Before confirming, run `loopRunner.agentsProbeCommand` (default `{bin} agents --json`) **exactly once** (no retries, no second probe); it exits 0 with `{ agents: [...] }`. Parse `agents[]`; build the advertised set `{ row.id }` — this one parsed array drives (b)–(d).
- **(b) Agent question.** Add an **"agent"** question to the same `AskUserQuestion` surface: **one option per advertised row** labelled `"{displayName} ({id}) — available/not found"`, **plus an explicit `"default (claude-cli)"` choice mapping to `run_selection = None`**. Resolve the pick (run > project, empty/whitespace unset, an explicit runner-default pick collapses to the default path) into `{resolved.agent, resolved.source}`. Precedence: `item.provider > --agent > project defaultAgent > runner default` (forge never reads a backlog item's provider).
- **(c) Availability listing.** From the **same** parsed `agents[]` (no second probe), list `id` / `displayName` / available (`yes`/`no`, `detail` on unavailable rows).
- **(d) Verdict** — only for a **non-default** resolved agent (default path `None`/`claude-cli` → no probe, byte-identical to today). Classify by **membership** then `available` (never by exit code): **UNKNOWN** (`∉` set) → **hard-reject BEFORE any loop side-effect**, error lists the **sorted** valid ids, **NO proceed-anyway**; **UNAVAILABLE** (member, `available False`) → warn with `detail`, `AskUserQuestion` offering **proceed-anyway OR choose-another** (re-presents the same `agents[]`), never silent; **AVAILABLE** → proceed, the validated id fills `{agent}`; **probe failure** (non-zero exit / unparseable / missing or empty `agents[]` / row lacking `id`) → surface it, offer **choose-another OR abort**, **never launch the non-default agent unvalidated** and never silently fall back to the default.
- **(d-model) Claude-only model-alias guard.** Runs **only** when the resolved agent is **non-default** (not the default / `claude-cli` path). Read the backlog.json (Step 1e path); collect items whose `model` is a **Claude-specific alias** (tier `opus`/`sonnet`/`haiku` or a `claude-*` id). **If none, skip silently.** Otherwise warn before launch via `AskUserQuestion` (NOT prose): `item.model` outranks `--agent`, so the alias is forwarded verbatim to `{agent}`, which will likely reject it (e.g. codex 400 *"The 'sonnet' model is not supported…"*) — every spawn exits 1 and rauf circuit-breaks (*"3 consecutive infra failures — halting"*) with no hint of the cause. Offer: **(1) Strip `model` for this run (recommended)** — rewrite backlog.json removing the `model` key from each affected item (persistent edit; re-run forge-4-backlog to restore), then proceed; **(2) Proceed as-is** — only safe if `{agent}` understands the pinned ids. forge touches only `model`, never `provider`. Full rationale: `references/runner-contract.md`.
- **(e) Optional-flags line.** Replace the confirmation's optional-flags line with one that lists `--agent <id>` first plus the agent precedence pointer (`item.provider > --agent > project defaultAgent > runner default`) alongside the model precedence.
- **(f) Resolved-agent line.** Add to the confirmation block: `Agent: {resolved.agent or claude-cli} (source: {sourceLabel})` — `sourceLabel`: `RUN` → `"per-run selection"`, `PROJECT` → `"project default (loopRunner.defaultAgent)"`, `DEFAULT` → `"runner default — claude-cli"`.

## Step 3: Execute the Loop

### 3a. Update Pipeline State

Before launching, update `{resolvedFeatureDir}/.pipeline-state.json`:
- Set `stages.forge-5-loop.status` to `in-progress`
- Set `stages.forge-5-loop.startedAt` to current ISO timestamp
- Set `currentStage` to `forge-5-loop`
- Update `updatedAt`

Then commit this state write before launching (mandatory). The runner refuses to run with uncommitted changes (*"…pass --force"*), and this marker is itself one — so an otherwise-clean repo fails its first launch unless committed. Commit it via the shared-conventions **Git Commit Protocol** (epic members: stage `{specsDir}/{epic}/`): `{commitPrefix}({feature}): forge-5-loop in-progress` — a launch precondition, required regardless of `gitCommitAfterStage`. Unrelated leftover changes still trip the refusal; surface it, never auto-pass `--force`. See `references/runner-contract.md`.

### 3b. Launch Background Process

Launch the loop **backgrounded** (`run_in_background: true`) so it survives session end and does not block the session. For a runner that **persists its own structured event file** (the default — rauf writes `{stateDir}/events.ndjson` natively and rotates it per run), launch the **plain `runCommand`** with **no stdout redirect** and supervise the runner's **native** `events.ndjson` directly; do **not** redirect `--ndjson` into `{stateDir}` (it is redundant and collides with the runner's own writer — see `references/runner-contract.md`). Only a stdout-only runner (no native event file) uses `eventStreamCommand`, redirected to a file **outside** `{stateDir}`. The background task's exit notification is the single authoritative terminal signal (Step 4). Loop runs can take significant time (minutes to hours depending on backlog size). For the exact launch commands (incl. the `mkdir -p` state-dir guard) and the self-persisting vs. stdout-only detail, read `references/runner-contract.md`.

### 3c. Inform User

Tell the user the run has started and that **this session is now actively
supervising it** — they don't need to babysit a terminal — and surface the rendered
`loopRunner` monitoring commands (`statusCommand` / `followCommand` / `logCommand` /
`listCommand`) and the state-file locations under
`{backlogDir}/{loopRunner.stateDir}/` so they can watch directly if they like. The
verbatim "Loop started…" inform-user output template is in
`references/runner-contract.md`.

### 3d. Arm a Monitor on the event stream, and react to events

Arm the **`Monitor` tool** on the structured event stream (the NDJSON file, or the
human log as fallback) so events flow back into this session as they happen. Use
**`persistent: true`** — runs can exceed `Monitor`'s maximum `timeout_ms` (1 hour),
and a bounded timeout would silently stop watching a still-running loop. The filter
MUST match every terminal and exception state, not just the happy path (silence is
not success). Monitor the **structured** surface, never raw `RAUF_*` tokens.

Each Monitor event arrives as a message; react per type — surface `needs_human` /
`loop_error` immediately with a `PushNotification`, coalesce `item_completed` into
milestones, and treat `llm_stuck_warning` as a hang warning. A `needs_human` /
`blocked` signal does **not** pause the loop — the runner sets the item aside and
keeps going.

For the exact Monitor commands (NDJSON `jq` filter and the log-fallback `grep`
prefixes), the coverage-complete filter event list, and the full per-event reaction
rules, read `references/runner-contract.md`.

### 3f. Reach completion

Step 4 is reached when the backgrounded process exits (its completion notification is
authoritative); the `loop_completed` / `loop_error` / `loop_cancelled` event is the live
heads-up that it's imminent. Stop the Monitor (it ends on its own when `tail` sees the
process-ended log, or via `TaskStop`) and proceed to Step 4. Do NOT foreground-sleep
or poll — the harness drives both the Monitor events and the completion notification.

## Step 4: Check Results

When the background process completes (its exit notification):

### 4a. Get Final Backlog State

Run the **status-json command** (`loopRunner.statusJsonCommand`) and read
`backlogSummary` for the authoritative counts — it separates the three non-done
outcomes: genuine `blocked`, `needsHuman`, and runner-`deferred` ("false blocks").
Fall back to the **list command** (`loopRunner.listCommand`) if `statusJsonCommand`
is not configured. You will already have most of this from the live tally in 3e. If the run used a review flag (e.g. rauf's `--review`), also read any `review_completed` event (event stream, or `{loopRunner.stateDir}/events.ndjson`) for its `itemsCreated`/`summary` to surface in 4b — see `references/result-reporting.md`.

### 4b. Report Results

Present a summary to the user. Pick **every** branch that applies (a run can be both
blocked and needs-human) and render its report. The five verbatim result-report
output templates — **all-done**, **needs-human**, **blocked**, **deferred**, and
**pending** (iteration limit reached) — are in `references/result-reporting.md`.

## Step 5: Update Pipeline State

Update `{resolvedFeatureDir}/.pipeline-state.json`:

1. Set `stages.forge-5-loop`: `status` = `"complete"` if all backlog items are `done`, else `"in-progress"`; `completedAt` = current ISO timestamp (only if complete); `basedOnVersions` = `{"forge-4-backlog": <current version from pipeline state>}`; `artifacts` = `["{backlogDir}/{loopRunner.stateDir}/state.json"]`.
2. If all items complete: set `currentStage` to `"forge-6-docs"`
3. Update `updatedAt`

**No git commit is needed** — the loop runner commits implementation code atomically per completed item during the run. (Step 6's commit, epic members only, is of pipeline state / manifest — a distinct artifact.)

## Step 5b: Offer Impl-Verify (standalone path)

**Gate:** run only if (a) the feature's `.pipeline-state.json` has **no** `epic` key **and** (b) Step 5 set `stages.forge-5-loop.status` to `complete`. Otherwise **skip** — partial runs end as today, and epic members get the equivalent offer in Step 6.1 (do **not** prompt twice). This standalone counterpart to Step 6.1 nudges verification interactively rather than via the easily-missed "Next steps" text. Use `AskUserQuestion` (NOT inline prose) to offer: *"{feature}'s loop is complete. Recommended: run `/feature-forge:forge-verify {feature} impl` to audit the implementation before generating docs. Run it now, or skip to forge-6-docs?"* On **run**, hand off to `/feature-forge:forge-verify {feature} impl`. On **skip**, record `stages.forge-verify-impl.status` as `"skipped"` (mirrors `forge-4-backlog`'s skip handling) and point the user at `/feature-forge:forge-6-docs {feature}` — the forge-6-docs backstop re-surfaces the skip.

## Step 6: Epic Handoff

**Gate:** only run this step if (a) the resolved feature's `.pipeline-state.json` has an `epic` key **and** (b) Step 5 set `stages.forge-5-loop.status` to `complete` (all backlog items done). If either is false, **skip** — standalone completed features are handled by Step 5b, and partial runs end as today (REQ-COMPAT-01).

1. **Offer impl-verify first (recommended, skippable).** Per the completion rule (`00-core-definitions.md §7`), a feature whose `forge-verify-impl.status == findings-reported` does **not** unblock dependents. Use `AskUserQuestion` (NOT inline prose) to offer: *"{feature}'s loop is done. Recommended: run `/feature-forge:forge-verify {feature} impl` before unblocking dependents. Run it now, or skip and continue the handoff?"* The user may skip (then completion is judged on the §7 rule with impl-verify absent).
2. **Recompute and announce.** Run `render-status "{epic}" --specs-dir "{specsDir}" --json`. Announce the feature's completion and the epic rollup (e.g. "2/4 features complete") — derived live from disk, never re-computed in prose.
3. **Identify the next actionable feature(s).** Read `render-status`'s `actionable` set (every dependency now complete, not itself complete) and `nextCommand`. **None actionable:** say so — if `rollup.total > 0` **AND** `rollup.complete == rollup.total`, suggest `/feature-forge:forge-6-docs {feature}` and note the epic-level documentation offer (§10) (the `rollup.total > 0` guard prevents an **empty epic** `0 == 0` from reading as complete); otherwise list what is still blocked and on which dependencies, then end (do not prompt to start a feature that cannot start). **One or more actionable:** use `AskUserQuestion` presenting **each actionable feature** as an option (plus "stop here"). Execution is **serial** — the user picks exactly one (REQ-ORCH-03); do **not** autonomously chain into the next pipeline.
4. **Begin the chosen feature.** **PRD absent** (no `PRD.md`, or `stages.forge-1-prd` not complete): offer to author it now — "Start `/feature-forge:forge-1-prd {chosen}`?" (REQ-ORCH-02); on yes, hand off to forge-1-prd (which injects epic context per §5.1). **PRD present:** point the user at the chosen feature's `nextCommand` from render-status.
5. **Commit (REQ-OBS-01).** When `gitCommitAfterStage` is true, commit the Step 5 completion write (and any manifest `updatedAt` bump) via the shared-conventions **Git Commit Protocol**, staging the epic subtree so the member state change commits atomically: `git add {specsDir}/{epic}/` then `{commitPrefix}({feature}): complete loop`. If `gitCommitAfterStage` is false, skip the commit.
6. **Close the handoff with the Stage Exit Protocol.** Finishing feature `{feature}` → starting the picked feature `{chosen}`'s PRD is a **cold** stage boundary (single-sourced in `references/stage-exit-protocol.md`). Feature `{feature}`'s impl-verify was already offered in Step 6.1, so step 1's gate self-suppresses when it ran or was skipped — the block collapses to `/clear` → next-command. Present it only when the chosen feature's PRD is absent (a PRD-present pick just runs its `nextCommand`):

**This stage is done — walk the user through the Stage Exit Protocol** before moving on. The order is fixed, and step 2 is something only the user can do:

1. **Verify feature {feature}'s loop first — if it isn't already verified.** If verify already ran in this session — via the in-stage auto-verify on the authoring stages, or the interactive impl-verify offered above on the loop — or is already fresh on record, or the stage was explicitly skipped, say so and go straight to step 2. Only when `autoVerify` is off for this stage **and** verify is **missing or stale** do you present the **Standard Verify Gate**: verify **now, before clearing**, using `AskUserQuestion` with exactly these three options — but only when the host has a question mechanism **and** the clean-room path is available (the `Agent` tool plus a dispatchable `forge-verifier` subagent):
   - **Verify feature {feature}'s loop now** *(recommended)* — dispatch the clean-room `forge-verifier` subagent from this session in require-clean mode; the digest returns here so any fix decision keeps its context. One-time — it does **not** change config.
   - **Verify now + enable auto-verify going forward** — verify now **and** patch `"autoVerify": true` into `forge.config.json` in place (preserve formatting and every other key) so future stages verify automatically, no prompt. This complements the `forge-init` opt-in. **Do not auto-commit this config change** — treat it like `notes`: a user-facing edit the user commits on their own cadence, never folded into a stage's artifact commit.
   - **Skip for now** — go straight to `/clear` and the next command without verifying. Record this stage's verify status as `"skipped"` in pipeline state (mirroring the existing skip handling) **only** on an explicit skip — a skip does not go stale.

   **Host / clean-room fallback (not a user-selectable option):** if the question mechanism, the `Agent` tool, or the `forge-verifier` subagent is unavailable, do **not** run clean-room — degrade to printing `/feature-forge:forge-verify {feature} impl` for the user to run inline/manually (mirroring `autoInvokeNextStage`), and offer the auto-verify enable as plain text only if a config write is possible.
2. **Then `/clear`.** Recommended **unconditionally** at this boundary for a clean start — independent of how full the context window is. Every artifact is on disk, so the work survives the clear. **I can't `/clear` for you — you have to run it yourself.**
3. **Then run `/feature-forge:forge-1-prd {chosen}`** in the fresh session — or re-run `/feature-forge:forge` to let the navigator resume from disk.

## Gotchas

- **Plugin-root discovery (1b-epic helper) covers installed paths, not workspace-dev checkouts.** The `forge-root.sh` search in 1b-epic probes `~/.claude/skills/feature-forge`, `~/.claude/plugins/cache/*/feature-forge/*` (marketplace-cache installs), `~/.claude/plugins/*/feature-forge`, and `./.agents/skills/feature-forge` — the locations of an **installed** plugin. A feature-forge **source checkout** (e.g. `~/workspace/feature-forge`) is not on that list, so the helper exits "cannot locate plugin root." That is expected in a dev environment, not a bug; run the epic-manifest script from the checkout directly (`python3 <checkout>/scripts/epic-manifest.py …`). The bootstrap prelude wraps its candidate loop in `bash -c` so the `~/.claude/plugins/*/feature-forge` glob is zsh-safe: an empty expansion no longer aborts the loop under zsh's `nomatch`.
- `{backlogDir}` is a **directory path**, not a file path. Pass `specs/auth`, not `specs/auth/backlog.json`.
- rauf resolves `RAUF.md` with fallback: checks `{backlogDir}/.rauf/RAUF.md` first, then the project's `.rauf/RAUF.md`. As long as the runner is installed in the project, the prompt template will be found.
- State files (state.json, {loopRunner.logFile}, etc.) are created at `{backlogDir}/{loopRunner.stateDir}/` — this is within the feature's spec directory and is expected. State is isolated per backlog dir, so concurrent features don't collide.
- If the session disconnects during a long-running loop, the runner process continues independently. The user can check results later with the status / list commands.
- Never run the run command in the foreground (without `run_in_background`) — it blocks and will hit the Bash tool timeout for any non-trivial backlog. "Don't block the foreground" is NOT "stay silent": supervise via the `Monitor` tool (3d), never `sleep`/poll in the foreground. The `Monitor` must use `persistent: true` (not a bounded `timeout_ms`), watch the **structured** surface (`events.ndjson`), and never filter on raw `RAUF_*` tokens — they appear in agent prose and false-match. A `needs_human`/`blocked`/`review` signal does **not** pause the loop — the runner sets the item aside and keeps going; surface it live but don't tell the user the loop is waiting. See `references/runner-contract.md` for the full monitoring rules.
- If a previous loop run left a stale lock, the user may need to pass `--force` to clear it. rauf will report this error clearly.
- The version gate (1c) uses the `--json` form on purpose; never parse `rauf version`'s human output.
- **Implementation artifacts must not cite specs.** The loop should **read** the specs and `backlog.json` freely — they are the source of truth for what to build, and the backlog rightly references specs for provenance. But the artifacts the loop **writes into the target repo** (source code, generated `SKILL.md`/agent files, configs, code comments) must be **self-contained**: they must NOT reference feature-forge spec files (no `See specs/{feature}/NN-*.md`, no "source spec" provenance notes in shipped output). Specs are pre-implementation inputs that may be archived or deleted once the feature ships; the implementation must stand on its own. This applies only to shipped implementation output — never to the backlog or spec documents, which should keep citing specs.
