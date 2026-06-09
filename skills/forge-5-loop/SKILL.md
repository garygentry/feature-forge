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
hardcoded `rauf …` strings in this skill.

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

Read `{specsDir}/{feature}/.pipeline-state.json`. If not in force mode, `stages.forge-4-backlog` must be `complete`. If not, STOP and tell the user: "Backlog hasn't been created yet. Run `/feature-forge:forge-4-backlog {feature}` first."

### 1b. Verification Check

Check if `stages.forge-verify-backlog` exists and has status `passed` or `findings-applied`. If not, use `AskUserQuestion` to warn:

"Backlog hasn't been verified yet. It's recommended to run `/feature-forge:forge-verify {feature}` first to catch issues before implementation. Continue anyway?"

### 1c. Runner Version Gate

Enforce `loopRunner.minRunnerVersion` **before** doing anything else with the runner. This is what turns "the runner is missing or too old" into a clear, actionable stop instead of a cryptic mid-run failure.

1. Run the **version command** (`loopRunner.versionCommand`, default `rauf version --json`) via Bash.
2. **If the command is not found / errors** (the binary isn't installed): STOP and show `loopRunner.installHint`.
3. Parse `{ "version": "<semver>" }` from stdout. Do NOT use plain `rauf version` (its human output is `rauf v0.1.0` with a `v` prefix) — always the `--json` form.
4. **Semver-compare** (NOT string-compare) the reported version against `loopRunner.minRunnerVersion` (default `0.2.0`). Compare numerically by major, then minor, then patch.
5. **If reported < minRunnerVersion**: STOP and show `loopRunner.installHint`, e.g.:
   "Your rauf is {reported}, but feature-forge needs ≥ {minRunnerVersion} (it relies on `backlog validate` + backlog schemaVersion). {installHint}"

> `installHint` points at the runner **CLI** install/upgrade — distinct from
> `setupHint` (1d), which installs the runner's per-project artifacts.

### 1d. Runner Setup Check (precondition file)

Check that `loopRunner.preconditionFile` (default `.rauf.json`) exists in the project root. If not:

- **If `loopRunner.name == "rauf"` and a legacy `.ralph.json` (or `.ralph/` directory) exists**, this is an un-migrated Ralph project. STOP and tell the user:

  "This project is still on the legacy **Ralph** layout. Run `rauf migrate .` first (the loop runner only understands `.rauf/` and `RAUF_*` signals), then re-run `/feature-forge:forge-5-loop {feature}`."

- **Otherwise**, STOP and show `loopRunner.setupHint` (default: "Run `rauf install .` …"), e.g.:

  "The loop runner isn't set up in this project ({preconditionFile} is missing). {setupHint}"

### 1e. Backlog File Check

Resolve the backlog file path:
- If `backlogDir` is set in `forge.config.json`: use `{backlogDir}/backlog.json`
- Otherwise: use `{specsDir}/{feature}/backlog.json`

Verify the file exists on disk. If not, STOP and tell the user: "No backlog.json found at {path}. Run `/feature-forge:forge-4-backlog {feature}` to generate it."

## Step 2: Construct the Loop Command

### 2a. Analyze Backlog

Run the **list command** (`loopRunner.listCommand`, default `rauf backlog list . --backlog {backlogDir} --json`) and count items by status: `pending`, `in_progress`, `done`, `blocked`.

Calculate the iteration count: `ceil((pending + in_progress) * loopIterationMultiplier)` where `loopIterationMultiplier` comes from `forge.config.json` (default: 1.5). This headroom allows retries without exhausting iterations.

If there are no pending or in_progress items, STOP and tell the user: "All backlog items are already done or blocked. Nothing to run."

If there are `blocked` items, note them — the user may want `--retry-blocked`.

### 2b. Resolve Backlog Directory

`{backlogDir}` is a **directory path** (not a file path), relative to the project root.

- If `backlogDir` is set in config: use that path.
- Otherwise: use `{specsDir}/{feature}` (the directory containing `backlog.json`).

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

Before launching, update `{specsDir}/{feature}/.pipeline-state.json`:
- Set `stages.forge-5-loop.status` to `in-progress`
- Set `stages.forge-5-loop.startedAt` to current ISO timestamp
- Set `currentStage` to `forge-5-loop`
- Update `updatedAt`

### 3b. Launch Background Process

Run the rendered run command via the Bash tool with `run_in_background: true`. This is critical — loop runs can take significant time (minutes to hours depending on backlog size) and must not block the session.

### 3c. Inform User

Output to the user (commands below are the rendered `loopRunner` monitoring commands):

```
Loop started for {feature} ({N} items to process).

The loop runs as a background process and will continue even if this session ends.
Each item gets a fresh agent session with full context from the backlog and specs.

Monitor progress (run these in another terminal or via `!` prefix):
  {rendered statusCommand}              # one-shot status
  {rendered statusCommand} --watch      # continuous polling
  {rendered followCommand}              # stream live events
  {rendered logCommand}                 # tail log file
  {rendered listCommand}                # check item statuses

State files are at: {backlogDir}/{loopRunner.stateDir}/
  - state.json      (loop state)
  - rauf.log       (event log)
  - iteration-status.json (live activity)
```

### 3d. Wait for Completion

Wait for the background task completion notification. Do NOT poll or sleep — the system will notify you when the process exits.

## Step 4: Check Results

When the background process completes:

### 4a. Get Final Backlog State

Run the **list command** (`loopRunner.listCommand`). Parse the JSON output to count items by status.

### 4b. Report Results

Present a summary to the user:

**All items done:**
```
Loop completed for {feature}. All {N} items implemented successfully.

Next steps:
  - /feature-forge:forge-verify {feature} impl   Verify the implementation
  - /feature-forge:forge-6-docs {feature}         Generate architecture docs
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
  - Review blocked items manually: rauf backlog show . {id} --backlog {backlogDir}
  - Continue to docs if blocking items are non-critical
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

Update `{specsDir}/{feature}/.pipeline-state.json`:

1. Set `stages.forge-5-loop`:
   - `status`: `"complete"` if all backlog items are `done`, otherwise `"in-progress"`
   - `completedAt`: current ISO timestamp (only if complete)
   - `basedOnVersions`: `{"forge-4-backlog": <current version from pipeline state>}`
   - `artifacts`: `["{backlogDir}/{loopRunner.stateDir}/state.json"]`
2. If all items complete: set `currentStage` to `"forge-6-docs"`
3. Update `updatedAt`

**No git commit is needed** — the loop runner commits atomically per completed item during the run. The implementation code is already committed.

## Gotchas

- `{backlogDir}` is a **directory path**, not a file path. Pass `specs/auth`, not `specs/auth/backlog.json`.
- rauf resolves `RAUF.md` with fallback: checks `{backlogDir}/.rauf/RAUF.md` first, then the project's `.rauf/RAUF.md`. As long as the runner is installed in the project, the prompt template will be found.
- State files (state.json, rauf.log, etc.) are created at `{backlogDir}/{loopRunner.stateDir}/` — this is within the feature's spec directory and is expected. State is isolated per backlog dir, so concurrent features don't collide.
- If the session disconnects during a long-running loop, the runner process continues independently. The user can check results later with the status / list commands.
- Never run the run command in the foreground (without `run_in_background`) — it blocks and will hit the Bash tool timeout for any non-trivial backlog.
- If a previous loop run left a stale lock, the user may need to pass `--force` to clear it. rauf will report this error clearly.
- The version gate (1c) uses the `--json` form on purpose; never parse `rauf version`'s human output.
