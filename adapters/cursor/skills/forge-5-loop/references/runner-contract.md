# forge-5-loop — Loop-Runner Contract (launch, supervision, model precedence)

This file holds the detailed loop-runner contract relocated out of
`forge-5-loop/SKILL.md`: the event-stream vs. log-fallback **launch** detail
(Steps 3b/3d/3e), the structured-surface **monitoring** caveats, and the **model
precedence** rule. The agent-selection surface, its Claude-only model-alias guard,
and the optional-flags catalog live in `references/agent-selection.md`, which is
read **only** when the Step 2d `loopRunner.agentArgument` capability gate is on.
Every command below is rendered from `loopRunner` with token substitution, as in
the skill body.

## Model selection precedence (Step 2d)

The runner picks the per-iteration model by precedence (highest wins):

```
item.model  >  --model / options  >  project default  >  provider default
```

So a backlog item's own `model` field overrides a `--model` flag passed to the
run, which overrides the project's configured default, which overrides the
runner/provider default. Pass `--model <model>` to override the project default for
the whole run; it is catalogued with the run's other optional flags under
`## Optional flags catalog (Step 2d, rauf)` in `references/agent-selection.md` —
read that file only when Step 2d's `loopRunner.agentArgument` capability gate is on.

## Run mode (Step 2d, rauf)

**Applies only when `loopRunner.name == "rauf"`.** rauf's `--review` runs a review
pass after all iterations complete (an extra agent session that re-examines the
finished work and can file follow-up backlog items). feature-forge treats **running
with review as the recommended default** — a review pass is cheap relative to the
loop it audits, and catches gaps before the pipeline moves on to docs. So Step 2d
adds a **"Run mode"** question, via the host's question mechanism, to the confirmation surface with a
**fixed, non-improvised option order** (determinism is the point — the option set
must not vary run-to-run):

```
Run mode:
  1. Run with review pass (recommended)   → append `--review`   [DEFAULT]
     After all iterations, a review agent re-examines the finished work and may
     file follow-up items. Recommended for every forge run.
  2. Run without review                    → bare rendered command
     Skip the review pass — iterations only, no post-run audit.
  3. Review + retry blocked                → append `--review --retry-blocked`
     ONLY offered when Step 2a counted one or more `blocked` items. Runs the
     review pass and also unblocks/retries the previously blocked items.
```

**`loopRunner.reviewMode` gate (`"prompt"` default | `"always"` | `"never"`).**
The Run-mode question above is presented only when the effective
`loopRunner.reviewMode` is `"prompt"` — the default, byte-identical to today.
`"always"` **skips the question** and appends `--review` unconditionally; the
confirmation's rendered command line still shows `--review`, so the choice is
never hidden. `"never"` **skips the question** and launches the bare rendered
command. Under `"always"`/`"never"`, when — and only when — the Step 2a tally has
`blocked > 0`, present a **narrower situational question** in the question's
place offering only the retry-blocked choice (on yes, additionally append
`--retry-blocked`; the `--review` decision is already fixed by the mode and is
**not** re-asked); with no blocked items, the Run-mode surface asks nothing. An
unrecognized value behaves as `"prompt"`.

Notes:

- **Option 1 is the default** and the confirmation's rendered command line shows
  `--review` appended. On any pick, append the option's flags to the rendered run
  command before Step 3 (launch).
- **the host's question mechanism's built-in "Other"** already lets the user type ad-hoc flags
  (`--model <model>`, `--timeout <min>`, or any combination) — do **not** add a
  separate open-ended option for that.
- **Option 3 is conditional.** Include it only when the Step 2a tally has `blocked
  > 0`; otherwise present options 1 and 2 only.
- **Version floor.** rauf's explicit `review` signal ships in 0.5.0, below the
  `minRunnerVersion` floor (0.6.0) enforced at gate 1c — so `--review` is always
  available once the loop is cleared to launch. No extra version check is needed.
- **Non-rauf runners.** When `loopRunner.name != "rauf"`, add **no** Run-mode
  question — present the bare rendered command and let the user adjust via "Other",
  byte-identical to the pre-review-default behavior. `--review` is a rauf-specific
  flag; a swapped-in runner conforming to the contract need not support it.

## Launch detail (Step 3b — background process)

Launch the loop **backgrounded** so it survives session end and does not block the
session, then supervise it live via the runner's structured event file.

> **Clean-tree precondition.** rauf refuses to run with uncommitted changes
> (*"Refusing to run the loop with uncommitted changes… pass --force"*). Step 3a's
> in-progress `.pipeline-state.json` write is itself an uncommitted change, so it
> **must be committed before launch** (Step 3a) — otherwise the first launch on an
> otherwise-clean repo always fails. If the tree still has unrelated uncommitted
> changes after that commit, surface it and let the user commit/stash or pass
> `--force`; never auto-pass `--force`.

> **Root/sandbox env guard.** On a hosted remote (e.g. Claude.ai) the loop often runs
> **as root**. rauf's default Claude launch is `claude -p --dangerously-skip-permissions
> …`, which the Claude CLI **refuses under root unless `IS_SANDBOX` is set** — the remote
> container is a legitimate ephemeral sandbox, but without the flag every spawn exits and
> rauf circuit-breaks (*"3 consecutive infra failures — halting"*) with no hint of the
> cause. So when — and only when — the launcher is root (`[ "$(id -u)" = 0 ]`), export
> `IS_SANDBOX="${IS_SANDBOX:-1}"` in front of the launch (an explicitly-set value is
> honored; the `:-1` only supplies a default). Non-root/local runs are unaffected — the
> guard is a no-op. **Surface a one-line note** when you set it — e.g. *"running as root →
> setting IS_SANDBOX=1 so the sandboxed runner can use --dangerously-skip-permissions"* —
> so the behavior is never silent. `forge-session.py doctor` also reports this condition.
> Both launch commands below already carry the guard.

**Do NOT redirect the run's stdout into `{loopRunner.stateDir}`.** rauf **persists
its own** `{stateDir}/events.ndjson` (structured) and `{stateDir}/{logFile}` (human)
natively, and **rotates** them at the start of every run (the prior run's files are
renamed into `{stateDir}/archive/`). A redirect like `… --ndjson >
{stateDir}/events.ndjson` therefore (a) is **redundant** — the runner writes that
file regardless — and (b) **collides** with the runner's own writer: the shell holds
a descriptor on the file the runner immediately rotates away, so the redirected
`--ndjson` stdout is orphaned into a bogus `archive/` file while the live
`events.ndjson` is the runner's native stream. It only *looks* clean by accident of
rotation timing. So:

- **Self-persisting runner (default — rauf writes `{stateDir}/events.ndjson`):**
  launch the **plain `runCommand`** with the host's background-execution mechanism and **no
  redirect** — the Bash tool already captures the run's stdout/stderr to the
  background task's output file (use it to diagnose a launch refusal). Supervise by
  arming the Monitor on the runner's **native** `{backlogDir}/{stateDir}/events.ndjson`
  (Step 3d). Guard the very first run with the state dir:

  ```
  mkdir -p {backlogDir}/{loopRunner.stateDir} && { [ "$(id -u)" = 0 ] && export IS_SANDBOX="${IS_SANDBOX:-1}" || true; } && {rendered runCommand}
  ```

  (Note: the `--ndjson` stdout stream and `loopRunner.eventStreamCommand` are **not**
  used on this path — the native file already carries the same structured records.)
- **Stdout-only runner (no native event file):** render `eventStreamCommand` (it adds
  `--ndjson`) and redirect its stdout to a file **outside `{stateDir}`** so it cannot
  collide with any native file or be swept into `archive/`, then Monitor that file:

  ```
  mkdir -p {backlogDir}/{loopRunner.stateDir} && { [ "$(id -u)" = 0 ] && export IS_SANDBOX="${IS_SANDBOX:-1}" || true; } && {rendered eventStreamCommand} > {backlogDir}/forge-events.ndjson 2>&1
  ```

The background task's exit notification remains the single authoritative terminal
signal (Step 4). Loop runs can take significant time (minutes to hours depending on
backlog size).

## Arm a Monitor on the event stream (Step 3d)

Arm the **host's monitoring mechanism** on the structured event stream so events flow back into
this session as they happen. Use **`persistent: true`** — runs can exceed the host's monitoring mechanism's
maximum `timeout_ms` (1 hour), and a bounded timeout would silently stop watching a
still-running loop.

**Coverage-complete filter (silence is not success).** The filter MUST match every
terminal and exception state, not just the happy path — otherwise a crash or hang
looks identical to "still running." Monitor command (NDJSON path):

```
tail -n +1 -F {backlogDir}/{loopRunner.stateDir}/events.ndjson 2>/dev/null \
  | jq -rc --unbuffered 'select(.type | test("item_completed|item_blocked|needs_human|signal_parsed|loop_completed|loop_error|loop_cancelled|llm_stuck_warning"))'
```

> **Use `tail -F` (follow by name), not `-f` (follow by descriptor).** The runner
> **rotates** `events.ndjson` at the start of each run (renames the prior file into
> `archive/`, creates a fresh one). A Monitor that attaches with `-f` during that
> brief rotation window would follow the **archived** inode and then see silence —
> indistinguishable from a healthy quiet loop. `-F` re-opens the live file by name,
> so it always tracks the runner's current native stream. (Send `tail`'s own
> rotation chatter to `/dev/null` so it can't reach the `jq` filter.)

- **Fallback (log tail, no NDJSON):** match the runner's **structured prose
  prefixes**, never the `RAUF_*` tokens (those leak inside agent output and
  false-match). For rauf:

  ```
  tail -n +1 -F {backlogDir}/{loopRunner.stateDir}/{loopRunner.logFile} 2>/dev/null \
    | grep -E --line-buffered 'Item [^ ]+ (completed|blocked):|Item [^ ]+ needs human input|Loop completed|Loop error:|Circuit breaker:'
  ```

  (Match `needs human input` **without** a trailing colon — the runner writes
  `needs human input (set aside):`.)

If the Monitor is ever auto-stopped for event volume, re-arm with a tighter filter
(drop `item_completed`, keep the exception/terminal events).

## React to events as they land (Step 3e)

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
  item, then either (a) collect the user's answer via the host's question mechanism and **record it via
  `decision-record` now** — SKILL Step 4c's unconditional **Post-Run Recovery Procedure**
  pass (`references/recovery-procedure.md`) applies it after the run ends — or (b) offer
  to **cancel the run early** (also recorded via `decision-record` — a deferral) if the
  answer changes the whole plan. Do not tell the user the loop is waiting on their reply
  — it isn't.
- **`item_blocked`** → surface the blocked item + reason now (visibility) and
  accumulate for the final summary. Use `{rendered statusJsonCommand}` to distinguish a
  genuine `blocked` from a runner-`deferred` "false block" (`backlogSummary.deferred`).
  No action is needed now: Step 4c's recovery pass offers the unblock after the run
  ends — a blocked-only run (no `needs_human` event) still enters it.
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

## Inform-user output template (Step 3c)

Step 3c's instruction, relocated verbatim from the SKILL body:

> Tell the user the run has started and that **this session is now actively
> supervising it** — they don't need to babysit a terminal — and surface the rendered
> `loopRunner` monitoring commands (`statusCommand` / `followCommand` / `logCommand` /
> `listCommand`) and the state-file locations under
> `{backlogDir}/{loopRunner.stateDir}/` so they can watch directly if they like. The
> verbatim "Loop started…" inform-user output template is in
> `references/runner-contract.md`.

This is the verbatim "Loop started…" output the session shows the user after
launch. Commands are the rendered `loopRunner` monitoring commands.

When the agent surface is gated on (`loopRunner.agentArgument` present), add the
`Coding agent:` line shown below immediately after the opening `Loop started …`
line, using the same `sourceLabel` mapping as the Step 2d confirmation
(`RUN` → `"per-run selection"`, `PROJECT` →
`"project default (loopRunner.defaultAgent)"`, `DEFAULT` →
`"runner default — claude-cli"`). When the gate is off, the line is **absent** and
the template is byte-identical to today (REQ-PLUG-02). When the launch proceeded via
the UNAVAILABLE *proceed-anyway* path, use the audit variant instead:

```
Coding agent: {resolved.agent or claude-cli} (source: {sourceLabel}).
Coding agent: {resolved.agent} (source: {sourceLabel}; proceeded despite unavailability warning).
```

(The two lines above are alternatives — the first is the normal line; the second
replaces it only on the proceed-anyway path. This is session-side prose only; it
introduces no new event type, so the Step 3d Monitor filter is unchanged.)

```
Loop started for {feature} ({N} items to process).
Coding agent: {resolved.agent or claude-cli} (source: {sourceLabel}).   # only when the agent surface is gated on
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
