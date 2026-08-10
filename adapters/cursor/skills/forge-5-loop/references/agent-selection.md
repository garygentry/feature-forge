# forge-5-loop — Agent Selection (Step 2d, conditional)

The agent-selection surface, its Claude-only model-alias guard, and the optional-
flags catalog. Loaded ONLY when `loopRunner.agentArgument` is present (the Step 2d
capability gate); when the gate is off, Step 2d is byte-identical to today and this
file is never read.

## Agent selection (Step 2d)

This section is **parallel** to `## Model selection precedence` in
`references/runner-contract.md`: it governs which **coding agent** rauf drives for the
run. The entire surface is
**presence-gated** on `loopRunner.agentArgument` — when that field is absent or
empty, there is no selector, no probe, and no `{agent}` substitution, and Step 2d /
Step 3c are byte-identical to today (capability gate;
`02-config-schema-and-gating.md`, REQ-PLUG-02). The rest assumes the gate is on.

**Precedence (highest wins):**

```
item.provider  >  --agent (run selection)  >  loopRunner.defaultAgent (project)  >  runner default (claude-cli)
```

**`loopRunner.agentMode` gate (`"prompt"` default | `"auto"`).** `"prompt"`
presents the Step 2d agent question (SKILL sub-step b) — byte-identical to today.
`"auto"` suppresses **only the interactive pick**: skip the agent question and
resolve as if the user made no per-run selection (`run_selection = None`, so
`defaultAgent` — or the runner default when unset — applies). Everything else on
this surface **still runs under `"auto"`**: the single probe, the availability
listing, the verdict classification below (UNKNOWN hard-reject before any loop
side-effect, UNAVAILABLE with its proceed-anyway/choose-another question,
probe-failure handling), and the Claude-only model-alias guard — those questions
are safety surfaces, not the pick, and are never suppressed. The resolved
`Agent: {id} (source: …)` line still shows in the confirmation and the Step 3c
template, so the choice is never hidden. Meaningless when
`loopRunner.agentArgument` is absent — the capability gate above already removes
the entire surface, and `agentMode` adds no second gate. An unrecognized value
behaves as `"prompt"`.

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
>
> **Follow-up (out of scope here — rauf repo).** The durable fix for the root/sandbox
> refusal (see "Root/sandbox env guard" under
> `## Launch detail (Step 3b — background process)` in `references/runner-contract.md`)
> is for **rauf itself** to honor
> `IS_SANDBOX` when it launches `claude --dangerously-skip-permissions` as root (or to
> detect root+flag-refused and emit a clear error instead of an opaque circuit-break).
> feature-forge's launch-time export is the mitigation; the upstream fix lives in the
> rauf plugin/repo. Track as a follow-up.

## Optional flags catalog (Step 2d, rauf)

These are the optional flags the user may add to the rendered run command. If the
user requests additional flags, append them to the rendered run command.

```
  --agent <id>      Coding agent rauf drives this run (see `## Agent selection` above).
                    Only the runner's advertised ids are valid; an unknown id is
                    rejected before launch. Shown only when the runner advertises
                    an agent surface (loopRunner.agentArgument present).
  --review          Run a review pass after all iterations (extra agent session)
  --model <model>   Override the model (see `## Model selection precedence` in
                    `references/runner-contract.md`)
  --timeout <min>   Per-session timeout in minutes (default: 60)
  --retry-blocked   Unblock and retry previously blocked items
```

