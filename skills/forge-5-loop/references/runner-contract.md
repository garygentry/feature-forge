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

## Agent selection (Step 2d)

This section is **parallel** to `## Model selection precedence` above: it governs
which **coding agent** rauf drives for the run. The entire surface is
**presence-gated** on `loopRunner.agentArgument` — when that field is absent or
empty, there is no selector, no probe, and no `{agent}` substitution, and Step 2d /
Step 3c are byte-identical to today (capability gate;
`02-config-schema-and-gating.md`, REQ-PLUG-02). The rest assumes the gate is on.

**Precedence (highest wins):**

```
item.provider  >  --agent (run selection)  >  loopRunner.defaultAgent (project)  >  runner default (claude-cli)
```

**Run-layer mapping — why forge never re-implements rauf's resolver.** forge owns
**only** its run and project layers and collapses them into **one** value
(`resolve()`: `run_selection or defaultAgent or none`), which it emits as a single
`--agent {agent}` occupying rauf's **run layer only**. rauf alone resolves
item-vs-run via its own 5-layer resolver, sitting the per-item `BacklogItem.provider`
**above** forge's run layer — so a run selection can never clobber a deliberate
per-item agent. forge **never reads, writes, or overrides** `BacklogItem.provider`
(REQ-AGENT-05). When forge sends nothing (the default path), rauf applies its own
default `claude-cli`, byte-identical to today. Empty/whitespace selections are
treated as unset, and an explicit pick of the runner default id collapses to the
default path (append nothing, run no probe). See
`03-selection-resolution-observability.md §3–§4`.

**Availability pre-check + disambiguation.** For a **non-default** resolved id only,
forge runs `loopRunner.agentsProbeCommand` **once** (no retries) and classifies the
id by **membership** in the advertised set (`{ row.id for row in agents }`), then the
matching row's `available` flag — **never** by exit code, because `rauf agents
--json` always exits 0 (an unknown id is simply absent; a known-unavailable one is
present with `available: false`):

- **UNKNOWN** (`∉` advertised set): hard-reject **before any loop side-effect**,
  listing the sorted valid ids; **no proceed-anyway**; the value never interpolates
  into `{agent}` (the advertised set IS the allow-list — REQ-SEC-01).
- **UNAVAILABLE** (member, `available == False`): warn with the row's `detail`, then
  offer **proceed-anyway OR choose-another** — never silent.
- **AVAILABLE** (member, `available == True`): proceed; the validated id fills
  `{agent}`.
- **Probe failure** (non-zero exit / unparseable / wrong shape / empty `agents[]` /
  row missing `id`): surface it and offer **choose-another OR abort**; never launch
  the non-default agent unvalidated, never silently fall back to the default.

The default / `claude-cli` path runs **no** probe (zero extra cost). See
`04-availability-precheck.md` for the full pre-check, classification, and allow-list,
and `02-config-schema-and-gating.md` for the capability gate.

> **Probe false-negative for Claude Code installs (advisory).** `rauf agents` may
> report `claude-cli` **unavailable** (e.g. *"credentials file not found:
> ~/.config/claude-code/credentials.json"*) even when a working `claude` CLI
> authenticates elsewhere — the probe's credential heuristic doesn't cover every
> install. This is a rauf probe concern, not something forge-5-loop fixes. The
> **default-agent path skips the probe entirely**, so an ordinary default run is
> unaffected; only an **explicit** `--agent claude-cli` would be flagged UNAVAILABLE,
> and the existing **proceed-anyway** path (above) covers it. Do not attempt to
> patch rauf's probe from here.

### Claude-only model-alias guard (Step 2d, sub-step d-model)

When the resolved agent is **non-default** (not the default / `claude-cli` path),
forge must guard against a backlog whose items pin **Claude-specific** model aliases.
forge-4-backlog (via the rauf author-backlog skill) writes Claude tier aliases
(`opus` / `sonnet`) into each item's `model`. Because rauf's precedence puts
`item.model` **above** `--agent`, the alias is forwarded verbatim to the selected
agent; a non-Claude agent (e.g. codex) then 400s — *"The 'sonnet' model is not
supported when using Codex with a ChatGPT account."* — so **every** spawn exits 1 and
rauf reports *"Circuit breaker: 3 consecutive infra failures — halting"* with no hint
of the real cause. forge-5-loop therefore detects Claude-specific `model` aliases in
the backlog (tier aliases `opus`/`sonnet`/`haiku` or `claude-*` ids) and, before
launch, **warns** and offers (via `AskUserQuestion`) to **strip `model` for this run**
(remove the key from each affected item so each spawn uses the agent's own default) or
**proceed as-is**. forge only ever touches the `model` field — never `provider`. The
default / `claude-cli` path skips this guard (the aliases are valid there).

> **Follow-up (out of scope here — rauf repo).** The durable fix would be for the
> rauf `author-backlog` skill to keep `model` **provider-neutral** by default (or to
> document that writing a tier alias binds the backlog to Claude agents). That lives
> in the separate rauf plugin/repo, not feature-forge; tracked as a follow-up.

## Optional flags catalog (Step 2d, rauf)

These are the optional flags the user may add to the rendered run command. If the
user requests additional flags, append them to the rendered run command.

```
  --agent <id>      Coding agent rauf drives this run (see Agent selection below).
                    Only the runner's advertised ids are valid; an unknown id is
                    rejected before launch. Shown only when the runner advertises
                    an agent surface (loopRunner.agentArgument present).
  --review          Run a review pass after all iterations (extra agent session)
  --model <model>   Override the model (see precedence above)
  --timeout <min>   Per-session timeout in minutes (default: 60)
  --retry-blocked   Unblock and retry previously blocked items
```

## Launch detail (Step 3b — background process)

Launch the loop **backgrounded** so it survives session end and does not block the
session, and prefer the machine-readable event stream so the session can supervise
it live.

> **Clean-tree precondition.** rauf refuses to run with uncommitted changes
> (*"Refusing to run the loop with uncommitted changes… pass --force"*). Step 3a's
> in-progress `.pipeline-state.json` write is itself an uncommitted change, so it
> **must be committed before launch** (Step 3a) — otherwise the first launch on an
> otherwise-clean repo always fails. If the tree still has unrelated uncommitted
> changes after that commit, surface it and let the user commit/stash or pass
> `--force`; never auto-pass `--force`.

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
