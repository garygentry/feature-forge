---
name: forge-5-rauf-loop
description: "Execute the rauf autonomous coding loop against a forge feature's backlog. Use when user runs /feature-forge:forge-5-rauf-loop or asks to run rauf/implement a forge feature after backlog is created and verified. Do NOT trigger for general rauf usage, standalone loop runs, or implementation tasks outside the forge pipeline."
argument-hint: "<feature-name>"
---

# forge-5-rauf-loop — Rauf Loop Executor

Execute the rauf autonomous coding loop against a forge feature's backlog. Rauf spawns a fresh Claude Code session per backlog item, implementing each task with full verification.

## Prerequisites

Read and follow `references/shared-conventions.md` for feature name validation, configuration reading, and force mode handling before proceeding.

**Turn structure reminder:** Output analysis/context as text, then route ALL questions through `AskUserQuestion`. Never embed questions in text output — the user will not be prompted and the session will stall.

## Step 1: Validate Prerequisites

### 1a. Pipeline State Check

Read `{specsDir}/{feature}/.pipeline-state.json`. If not in force mode, `stages.forge-4-backlog` must be `complete`. If not, STOP and tell the user: "Backlog hasn't been created yet. Run `/feature-forge:forge-4-backlog {feature}` first."

### 1b. Verification Check

Check if `stages.forge-verify-backlog` exists and has status `passed` or `findings-applied`. If not, use `AskUserQuestion` to warn:

"Backlog hasn't been verified yet. It's recommended to run `/feature-forge:forge-verify {feature}` first to catch issues before implementation. Continue anyway?"

### 1c. Rauf Installation Check

Check that `.rauf.json` exists in the project root. If not:

- **If a legacy `.ralph.json` (or a `.ralph/` directory) exists**, this is an
  un-migrated Ralph project. STOP and tell the user:

  "This project is still on the legacy **Ralph** layout. Run `rauf migrate .`
  first (the loop runner only understands `.rauf/` and `RAUF_*` signals), then
  re-run `/feature-forge:forge-5-rauf-loop {feature}`."

  Do not attempt to run the loop — an un-migrated `RALPH.md` instructs the agent
  to emit `RALPH_*` signals that the current parser rejects.

- **Otherwise** (no rauf and no legacy marker), STOP and tell the user:

  "Rauf is not installed in this project. Run `rauf install .` to set up rauf,
  then re-run `/feature-forge:forge-5-rauf-loop {feature}`."

### 1d. Backlog File Check

Resolve the backlog file path:
- If `backlogDir` is set in `forge.config.json`: use `{backlogDir}/backlog.json`
- Otherwise: use `{specsDir}/{feature}/backlog.json`

Verify the file exists on disk. If not, STOP and tell the user: "No backlog.json found at {path}. Run `/feature-forge:forge-4-backlog {feature}` to generate it."

## Step 2: Construct the Rauf Command

### 2a. Analyze Backlog

Read `backlog.json` and count items by status:
- `pending` — items to be implemented
- `in_progress` — items from a previous interrupted run
- `done` — already completed items
- `blocked` — items that failed previously

Calculate the iteration count: `ceil((pending + in_progress) * raufIterationMultiplier)` where `raufIterationMultiplier` comes from `forge.config.json` (default: 1.5). This headroom allows retries without exhausting iterations.

If there are no pending or in_progress items, STOP and tell the user: "All backlog items are already done or blocked. Nothing to run."

If there are `blocked` items, note them — the user may want `--retry-blocked`.

### 2b. Resolve Backlog Directory

The `--backlog` flag takes a **directory path** (not a file path), relative to the project root.

- If `backlogDir` is set: use that path relative to project root
- Otherwise: use `{specsDir}/{feature}` (the directory containing `backlog.json`)

**Example:** If `specsDir` is `./specs` and feature is `auth`, the backlog directory is `specs/auth`.

### 2c. Build Command

Construct the base command:

```
rauf loop run . --backlog {relativeBacklogDir} --iterations {iterationCount}
```

### 2d. Confirm with User

Use `AskUserQuestion` to present the command and options. The following block is the content for `AskUserQuestion` — do NOT output it as text:

```
Ready to run the rauf loop for {feature}:

  rauf loop run . --backlog {dir} --iterations {iterationCount}

Backlog summary:
  - Pending: {pending}
  - In progress: {in_progress}
  - Done: {done}
  - Blocked: {blocked}
  - Iterations: {iterationCount} ({activeItems} items x {raufIterationMultiplier} multiplier)

Optional flags you can add:
  --review          Run a review pass after all iterations (extra Claude session)
  --model <model>   Override Claude model (e.g., claude-sonnet-4-5-20250514)
  --timeout <min>   Per-session timeout in minutes (default: 60)
  --retry-blocked   Unblock and retry previously blocked items

Proceed with this command, or would you like to adjust?
```

If the user requests additional flags, incorporate them into the command.

## Step 3: Execute the Loop

### 3a. Update Pipeline State

Before launching, update `{specsDir}/{feature}/.pipeline-state.json`:
- Set `stages.forge-5-rauf-loop.status` to `in-progress`
- Set `stages.forge-5-rauf-loop.startedAt` to current ISO timestamp
- Set `currentStage` to `forge-5-rauf-loop`
- Update `updatedAt`

### 3b. Launch Background Process

Run the constructed command via the Bash tool with `run_in_background: true`. This is critical — rauf loop runs can take significant time (minutes to hours depending on backlog size) and must not block the session.

### 3c. Inform User

Output to the user:

```
Rauf loop started for {feature} ({N} items to process).

The loop runs as a background process and will continue even if this session ends.
Each item gets a fresh Claude Code session with full context from the backlog and specs.

Monitor progress (run these in another terminal or via `!` prefix):
  rauf status . --backlog {dir}              # one-shot status
  rauf status . --backlog {dir} --watch      # continuous polling
  rauf loop follow . --backlog {dir}         # stream live events
  rauf log . --backlog {dir} --follow        # tail log file
  rauf backlog list . --backlog {dir}        # check item statuses

State files are at: {specsDir}/{feature}/.rauf/
  - state.json      (loop state)
  - rauf.log       (event log)
  - iteration-status.json (live activity)
```

### 3d. Wait for Completion

Wait for the background task completion notification. Do NOT poll or sleep — the system will notify you when the process exits.

## Step 4: Check Results

When the background process completes:

### 4a. Get Final Backlog State

Run via Bash: `rauf backlog list . --backlog {dir} --json`

Parse the JSON output to count items by status.

### 4b. Report Results

Present a summary to the user:

**All items done:**
```
Rauf loop completed for {feature}. All {N} items implemented successfully.

Next steps:
  - /feature-forge:forge-verify {feature} impl   Verify the implementation
  - /feature-forge:forge-6-docs {feature}         Generate architecture docs
```

**Some items blocked:**
```
Rauf loop completed for {feature}.
  Completed: {done}/{total}
  Blocked:   {blocked} items

Blocked items:
  - {id}: {title}
  - {id}: {title}

Options:
  - Re-run with --retry-blocked to retry blocked items
  - Review blocked items manually: rauf backlog show . {id} --backlog {dir}
  - Continue to docs if blocking items are non-critical
```

**Some items still pending (iteration limit reached):**
```
Rauf loop completed for {feature}.
  Completed: {done}/{total}
  Pending:   {pending} items (iteration limit reached)
  Blocked:   {blocked} items

Re-run `/feature-forge:forge-5-rauf-loop {feature}` to continue with remaining items.
```

## Step 5: Update Pipeline State

Update `{specsDir}/{feature}/.pipeline-state.json`:

1. Set `stages.forge-5-rauf-loop`:
   - `status`: `"complete"` if all backlog items are `done`, otherwise `"in-progress"`
   - `completedAt`: current ISO timestamp (only if complete)
   - `basedOnVersions`: `{"forge-4-backlog": <current version from pipeline state>}`
   - `artifacts`: `["{specsDir}/{feature}/.rauf/state.json"]`
2. If all items complete: set `currentStage` to `"forge-6-docs"`
3. Update `updatedAt`

**No git commit is needed** — rauf commits atomically per completed item during the loop. The implementation code is already committed.

## Gotchas

- The `--backlog` flag takes a **directory path**, not a file path. Pass `specs/auth`, not `specs/auth/backlog.json`.
- Rauf resolves `RAUF.md` with fallback: checks `{backlogDir}/.rauf/RAUF.md` first, then the project's `.rauf/RAUF.md`. As long as rauf is installed in the project, the prompt template will be found.
- State files (state.json, rauf.log, etc.) are created at `{specsDir}/{feature}/.rauf/` — this is within the feature's spec directory and is expected.
- If the session disconnects during a long-running loop, the rauf process continues independently. The user can check results later with `rauf status` or `rauf backlog list`.
- Never run `rauf loop run` in the foreground (without `run_in_background`) — it blocks and will hit the Bash tool timeout for any non-trivial backlog.
- If a previous loop run left a stale lock, the user may need to pass `--force` to clear it. Rauf will report this error clearly.
