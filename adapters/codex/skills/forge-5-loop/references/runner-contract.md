# forge-5-loop — Loop-Runner Contract (launch, supervision, model precedence)

This file holds the detailed loop-runner contract relocated out of
`forge-5-loop/SKILL.md`: the event-stream vs. log-fallback **launch** detail
(Steps 3b/3d/3e), the structured-surface **monitoring** caveats, the **model
precedence** rule, and the **optional-flags catalog** referenced from Step 2d.
Every command below is rendered from `loopRunner` with token substitution, as in
the skill body.

## Model selection precedence (Step 2d)

The runner picks the per-iteration model by precedence (highest wins):

```
item.model  >  --model / options  >  project default  >  provider default
```

So a backlog item's own `model` field overrides a `--model` flag passed to the
run, which overrides the project's configured default, which overrides the
runner/provider default. Pass `--model <model>` (optional flag below) to override
the project default for the whole run.

## Optional flags catalog (Step 2d, rauf)

These are the optional flags the user may add to the rendered run command. If the
user requests additional flags, append them to the rendered run command.

```
  --review          Run a review pass after all iterations (extra agent session)
  --model <model>   Override the model (see precedence above)
  --timeout <min>   Per-session timeout in minutes (default: 60)
  --retry-blocked   Unblock and retry previously blocked items
```

## Launch detail (Step 3b — background process)

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

## Arm a Monitor on the event stream (Step 3d)

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

## Inform-user output template (Step 3c)

This is the verbatim "Loop started…" output the session shows the user after
launch. Commands are the rendered `loopRunner` monitoring commands.

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
