---
name: forge-5-loop
description: "Execute the autonomous coding loop (rauf by default) against a forge feature's backlog. Use when user runs /feature-forge:forge-5-loop or /feature-forge:forge-5-rauf-loop, or asks to run rauf / run the loop / implement a forge feature after the backlog is created and verified. Do NOT trigger for general rauf usage, standalone loop runs, or implementation tasks outside the forge pipeline."
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

Check if `stages.forge-verify-backlog` exists and has status `passed` or `findings-applied`. If not, use `AskUserQuestion` to warn:

"Backlog hasn't been verified yet. It's recommended to run `/feature-forge:forge-verify {feature}` first to catch issues before implementation. Continue anyway?"

### 1b-epic. Epic Dependency Gate

Read the resolved feature's `.pipeline-state.json`. **If it has no `epic` key, skip this sub-step entirely** (standalone feature — REQ-COMPAT-01; standalone runs are unchanged). Otherwise:

1. Run `render-status "{epic}" --specs-dir "{specsDir}" --json` via the helper:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/epic-manifest.py" \
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
2. Parse `{ "version": "<semver>" }` from stdout. Do NOT use plain `rauf version` (its human output is `rauf v0.1.0` with a `v` prefix) — always the `--json` form.
3. **Semver-compare** (NOT string-compare) the reported version against `loopRunner.minRunnerVersion` (default `0.5.0`), numerically by major, then minor, then patch.

**Any of the following is a HARD GATE FAILURE — do NOT proceed to run the loop.** STOP, show `loopRunner.installHint`, and include the raw command output for diagnosis:

- The version command is not found or exits non-zero (the binary isn't installed).
- Its stdout is not valid JSON, has no `version` field, or `version` is not a valid semver string.
- The reported version is **< `minRunnerVersion`**.

For the version-too-old case, phrase it concretely, e.g.: "Your rauf is {reported}, but feature-forge needs ≥ {minRunnerVersion} (it relies on `backlog validate` + backlog schemaVersion). {installHint}". When the gate fails because the output couldn't be parsed, say so and show what the command printed before the `installHint`.

> `installHint` points at the runner **CLI** install/upgrade — distinct from
> `setupHint` (1d), which installs the runner's per-project artifacts.

### 1d. Runner Setup Check (precondition file)

Check that `loopRunner.preconditionFile` (default `.rauf.json`) exists in the project root. If not:

- **If `loopRunner.name == "rauf"` and a legacy `.ralph.json` (or `.ralph/` directory) exists**, this is an un-migrated Ralph project. STOP and tell the user:

  "This project is still on the legacy **Ralph** layout. Run `rauf migrate .` first (the loop runner only understands `.rauf/` and `RAUF_*` signals), then re-run `/feature-forge:forge-5-loop {feature}`."

- **Otherwise**, STOP and show `loopRunner.setupHint` (default: "Run `rauf install .` …"), e.g.:

  "The loop runner isn't set up in this project ({preconditionFile} is missing). {setupHint}"

### 1e. Backlog File Check

Resolve the backlog file path (matching forge-4-backlog's composition rule, item 015 / §6.2):
- If `backlogDir` is set in `forge.config.json`: use `{backlogDir}/{feature}/backlog.json` (the per-feature subpath, so each epic member's backlog stays independent — the `{feature}` segment prevents collisions across a multi-feature epic)
- Otherwise: use `{resolvedFeatureDir}/backlog.json`

Verify the file exists on disk. If not, STOP and tell the user: "No backlog.json found at {path}. Run `/feature-forge:forge-4-backlog {feature}` to generate it."

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

Optional flags you can add (rauf):
  --review          Run a review pass after all iterations (extra agent session)
  --model <model>   Override the model
  --timeout <min>   Per-session timeout in minutes (default: 60)
  --retry-blocked   Unblock and retry previously blocked items

Proceed with this command, or would you like to adjust?
```

If the user requests additional flags, append them to the rendered run command.

## Step 3: Execute the Loop

### 3a. Update Pipeline State

Before launching, update `{resolvedFeatureDir}/.pipeline-state.json`:
- Set `stages.forge-5-loop.status` to `in-progress`
- Set `stages.forge-5-loop.startedAt` to current ISO timestamp
- Set `currentStage` to `forge-5-loop`
- Update `updatedAt`

### 3b. Launch Background Process

Launch the loop **backgrounded** so it survives session end and does not block the
session, and prefer the machine-readable event stream so the session can supervise
it live.

- **If `loopRunner.eventStreamCommand` is configured (default for rauf):** render it
  (it appends `--ndjson` to the run) and launch via the Bash tool with
  `run_in_background: true`, redirecting stdout to a stable events file:

  ```
  mkdir -p {backlogDir}/{loopRunner.stateDir} && {rendered eventStreamCommand} > {backlogDir}/{loopRunner.stateDir}/events.ndjson 2>&1
  ```

  (The `mkdir -p` guards the very first run, before the runner has created its
  state dir.) This emits one JSON event per line **and** keeps the loop detached. The background
  task's exit notification remains the single authoritative terminal signal (Step 4).
- **Fallback (runner has no `eventStreamCommand`):** launch the plain `runCommand`
  with `run_in_background: true`. The session will then supervise by tailing the
  human log (3d fallback) instead of the NDJSON file.

Loop runs can take significant time (minutes to hours depending on backlog size).

### 3c. Inform User

Tell the user the run has started and that **this session is now actively
supervising it** — they don't need to babysit a terminal, but the commands below
are available if they want to watch directly. (Commands are the rendered
`loopRunner` monitoring commands.)

```
Loop started for {feature} ({N} items to process).
This session is now monitoring it live — I'll report milestones and stop you in if
the loop needs a human. The loop also runs detached and survives this session ending.
Each item gets a fresh agent session with full context from the backlog and specs.

Watch directly if you like (another terminal or `!` prefix):
  {rendered statusCommand}              # one-shot status
  {rendered followCommand}              # stream live events (human)
  {rendered logCommand}                 # tail log file
  {rendered listCommand}                # check item statuses

State files are at: {backlogDir}/{loopRunner.stateDir}/
  - state.json             (loop state)
  - events.ndjson          (structured event stream this session is watching)
  - {loopRunner.logFile}   (human event log)
  - iteration-status.json  (live activity, incl. stuckWarning)
```

### 3d. Arm a Monitor on the event stream

Arm the **`Monitor` tool** on the structured event stream so events flow back into
this session as they happen. Use **`persistent: true`** — runs can exceed `Monitor`'s
maximum `timeout_ms` (1 hour), and a bounded timeout would silently stop watching a
still-running loop.

**Coverage-complete filter (silence is not success).** The filter MUST match every
terminal and exception state, not just the happy path — otherwise a crash or hang
looks identical to "still running." Monitor command (NDJSON path):

```
tail -n +1 -f {backlogDir}/{loopRunner.stateDir}/events.ndjson 2>&1 \
  | jq -rc --unbuffered 'select(.type | test("item_completed|item_blocked|needs_human|signal_parsed|loop_completed|loop_error|loop_cancelled|llm_stuck_warning"))'
```

- **Fallback (log tail, no NDJSON):** match the runner's **structured prose
  prefixes**, never the `RAUF_*` tokens (those leak inside agent output and
  false-match). For rauf:

  ```
  tail -n +1 -f {backlogDir}/{loopRunner.stateDir}/{loopRunner.logFile} \
    | grep -E --line-buffered 'Item [^ ]+ (completed|blocked):|Item [^ ]+ needs human input|Loop completed|Loop error:|Circuit breaker:'
  ```

  (Match `needs human input` **without** a trailing colon — the runner writes
  `needs human input (set aside):`.)

If the Monitor is ever auto-stopped for event volume, re-arm with a tighter filter
(drop `item_completed`, keep the exception/terminal events).

### 3e. React to events as they land

Each Monitor event arrives as a message. React per type — but keep the user signal
high and the noise low:

- **`item_completed`** → increment a running tally. These land minutes apart, so they
  won't trip the volume auto-stop; still, surface a coalesced milestone ("12/30 done")
  rather than echoing every line. For an exact breakdown, run the one-shot
  `{rendered statusJsonCommand}` and report `done/total` from `backlogSummary`.
- **`needs_human`** (or `signal_parsed` with `signal: "needs_human"`) → **surface
  immediately** and send a **`PushNotification`** (an hours-long run means the user has
  likely stepped away). **Important — the loop is NOT paused:** the runner has set that
  item aside and kept working other items. So report *what* needs a human and *which*
  item, then either (a) collect the user's answer via `AskUserQuestion` to **stage a
  post-run retry**, or (b) offer to **cancel the run early** if the answer changes the
  whole plan. Do not tell the user the loop is waiting on their reply — it isn't.
- **`item_blocked`** → surface the blocked item + reason now (visibility) and
  accumulate for the final summary. Use `{rendered statusJsonCommand}` to distinguish a
  genuine `blocked` from a runner-`deferred` "false block" (`backlogSummary.deferred`).
- **`loop_error`** → a real failure (this is also what a circuit-breaker halt — too many
  consecutive infra failures — emits). Surface now and `PushNotification`. Offer
  inspection / `--force` / re-run as appropriate.
- **Stall detection** → rauf emits an **`llm_stuck_warning`** event when an iteration
  stops making progress; the filter above includes it, so surface it live (a hang
  warning, not yet a failure) and offer `--force` if it persists. If you instead want to
  probe on quiet, run `{rendered watchCommand}` (or read
  `{backlogDir}/{loopRunner.stateDir}/iteration-status.json`) and key off its
  `stuckWarning` flag. Do **not** infer a stall from `state.json.updatedAt` alone — it is
  not a liveness proof.

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
is not configured. You will already have most of this from the live tally in 3e.

### 4b. Report Results

Present a summary to the user. Pick every branch that applies (a run can be both
blocked and needs-human):

**All items done:**
```
Loop completed for {feature}. All {N} items implemented successfully.

Next steps:
  - /feature-forge:forge-verify {feature} impl   Verify the implementation
  - /feature-forge:forge-6-docs {feature}         Generate architecture docs
```

**Some items need a human:**
```
Loop completed for {feature}.
  Completed:   {done}/{total}
  Needs human: {needsHuman} items (set aside during the run)

These items asked a question the loop couldn't answer:
  - {id}: {title} — {reason}

Resolve, then retry:
  - Answer the question(s) above, then re-run `/feature-forge:forge-5-loop {feature}`
    (add --retry-blocked to pick the set-aside items back up).
```

**Some items blocked:**
```
Loop completed for {feature}.
  Completed: {done}/{total}
  Blocked:   {blocked} items

Blocked items:
  - {id}: {title}
  - {id}: {title}

Options:
  - Re-run with --retry-blocked to retry blocked items
  - Review blocked items manually: {bin} backlog show . {id} --backlog {backlogDir}
  - Continue to docs if blocking items are non-critical
```

**Some items deferred (runner gave up after retries — "false blocks"):**
```
Loop completed for {feature}.
  Completed: {done}/{total}
  Deferred:  {deferred} items (no signal after retries — likely just need another pass)

Re-run `/feature-forge:forge-5-loop {feature}` to retry deferred items.
```

**Some items still pending (iteration limit reached):**
```
Loop completed for {feature}.
  Completed: {done}/{total}
  Pending:   {pending} items (iteration limit reached)
  Blocked:   {blocked} items

Re-run `/feature-forge:forge-5-loop {feature}` to continue with remaining items.
```

## Step 5: Update Pipeline State

Update `{resolvedFeatureDir}/.pipeline-state.json`:

1. Set `stages.forge-5-loop`:
   - `status`: `"complete"` if all backlog items are `done`, otherwise `"in-progress"`
   - `completedAt`: current ISO timestamp (only if complete)
   - `basedOnVersions`: `{"forge-4-backlog": <current version from pipeline state>}`
   - `artifacts`: `["{backlogDir}/{loopRunner.stateDir}/state.json"]`
2. If all items complete: set `currentStage` to `"forge-6-docs"`
3. Update `updatedAt`

**No git commit is needed** — the loop runner commits atomically per completed item during the run. The implementation code is already committed.

> **Note:** Step 5's "no git commit needed" remark refers to *implementation code*, which the runner commits per-item. The epic handoff's commit in Step 6 below is of *pipeline state / manifest* — a distinct artifact — and applies only to epic members.

## Step 6: Epic Handoff

**Gate:** only run this step if (a) the resolved feature's `.pipeline-state.json` has an `epic` key **and** (b) Step 5 set `stages.forge-5-loop.status` to `complete` (all backlog items done). If either is false, **skip** — standalone features and partial runs end exactly as today (REQ-COMPAT-01).

1. **Offer impl-verify first (recommended, skippable).** Per the completion rule (`00-core-definitions.md §7`), a feature whose `forge-verify-impl.status == findings-reported` does **not** unblock dependents. Use `AskUserQuestion` (NOT inline prose) to offer:

   > "{feature}'s loop is done. Recommended: run `/feature-forge:forge-verify {feature} impl` before unblocking dependents. Run it now, or skip and continue the handoff?"

   The user may skip (then completion is judged on the §7 rule with impl-verify absent).
2. **Recompute and announce.** Run `render-status "{epic}" --specs-dir "{specsDir}" --json`. Announce the feature's completion and the epic rollup (e.g. "2/4 features complete") — derived live from disk, never re-computed in prose.
3. **Identify the next actionable feature(s).** Read `render-status`'s `actionable` set (features whose every dependency is now complete and that are not themselves complete) and `nextCommand`.
   - **None actionable** (everything done, or remaining features still blocked): say so.
     - If `rollup.total > 0` **AND** `rollup.complete == rollup.total`, suggest `/feature-forge:forge-6-docs {feature}` and note the epic-level documentation offer (§10). The `rollup.total > 0` guard prevents an **empty epic** (`0 == 0`) from being reported complete.
     - Otherwise, list what is still blocked and on which dependencies. End — do not prompt to start a feature that cannot start.
   - **One or more actionable:** use `AskUserQuestion` presenting **each actionable feature** as an option (plus "stop here"). Execution is **serial** — the user picks exactly one (REQ-ORCH-03). Do **not** autonomously chain into the next pipeline.
4. **Begin the chosen feature.** For the picked feature:
   - **PRD absent** (no `PRD.md`, or `stages.forge-1-prd` not complete): offer to author it now — "Start `/feature-forge:forge-1-prd {chosen}`?" (REQ-ORCH-02). On yes, hand off to forge-1-prd (which injects epic context per §5.1).
   - **PRD present:** point the user at the chosen feature's `nextCommand` from render-status.
5. **Commit (REQ-OBS-01).** When `gitCommitAfterStage` is true, commit the Step 5 completion write (and any manifest `updatedAt` bump) via the shared-conventions **Git Commit Protocol**, staging the epic subtree so the member state change commits atomically: `git add {specsDir}/{epic}/` then `{commitPrefix}({feature}): complete loop`. If `gitCommitAfterStage` is false, skip the commit.

## Gotchas

- `{backlogDir}` is a **directory path**, not a file path. Pass `specs/auth`, not `specs/auth/backlog.json`.
- rauf resolves `RAUF.md` with fallback: checks `{backlogDir}/.rauf/RAUF.md` first, then the project's `.rauf/RAUF.md`. As long as the runner is installed in the project, the prompt template will be found.
- State files (state.json, {loopRunner.logFile}, etc.) are created at `{backlogDir}/{loopRunner.stateDir}/` — this is within the feature's spec directory and is expected. State is isolated per backlog dir, so concurrent features don't collide.
- If the session disconnects during a long-running loop, the runner process continues independently. The user can check results later with the status / list commands.
- Never run the run command in the foreground (without `run_in_background`) — it blocks and will hit the Bash tool timeout for any non-trivial backlog. "Don't block the foreground" is NOT "stay silent": supervise via the `Monitor` tool (3d), which is harness-driven, not a sleep loop. Never `sleep`/poll in the foreground to wait for the loop.
- The `Monitor` on the event stream must use `persistent: true`, not a bounded `timeout_ms` — a multi-hour run would outlive the 1-hour `timeout_ms` cap and the watch would stop while the loop is still going.
- Monitor the **structured** surface (`events.ndjson` via `eventStreamCommand`), not the human log, and never filter on raw `RAUF_*` tokens — they appear inside agent prose in the log and produce false completion/blocked matches. Key off the runner's parsed event `type`s (or, in the log fallback, the `Item …`/`Loop …` prose prefixes).
- A `needs_human`/`blocked`/`review` signal does **not** pause the loop — the runner sets that item aside and keeps going. Surface it live for visibility, but don't tell the user the loop is waiting on their answer; resolution is a follow-up retry pass (or an early cancel).
- If a previous loop run left a stale lock, the user may need to pass `--force` to clear it. rauf will report this error clearly.
- The version gate (1c) uses the `--json` form on purpose; never parse `rauf version`'s human output.
