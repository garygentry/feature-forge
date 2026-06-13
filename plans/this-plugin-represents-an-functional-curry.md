# feature-forge Modernization Plan

## Context

`feature-forge` is a PRD→Build pipeline plugin (v0.9.0): `forge-init → forge-1-prd
→ forge-2-tech → forge-3-specs → forge-4-backlog → forge-5-loop → forge-6-docs`,
with `forge-verify`/`forge-fix` gates and two subagents (`forge-researcher`,
`forge-verifier`). It was authored against an earlier Claude Code and has not been
revisited as platform capabilities advanced. This review covers the whole pipeline
and produces a phased plan to bring it up to current best practice.

The single most important finding is in the called-out focus area, **forge-5-loop**.
It launches the rauf loop as a background process and then explicitly instructs:
*"Do NOT poll or sleep — the system will notify you when the process exits."*
(`skills/forge-5-loop/SKILL.md:186-187`). For a run that takes "minutes to hours,"
the agent goes completely dark and only reacts at the very end. This **directly
contradicts the stated intent** — "it's up to the agent to periodically check status
and update user or take subsequent steps." rauf already emits everything needed for
live monitoring, but the skill watches none of it: `RAUF_NEEDS_HUMAN` mid-run is
invisible until the loop ends.

The modern primitive for exactly this — streaming events from a long-running process
back into the conversation — is the **`Monitor` tool**, which did not exist when the
skill was written. It is the centerpiece of this plan. Two supporting primitives that
also postdate the skill round out the design: **`PushNotification`** (pull the user
back when they've walked away from an hours-long run) and a corrected understanding of
**`AskUserQuestion`** in this context.

> **This revision corrects the prior draft against the actual rauf source and the
> live `Monitor` tool schema.** Three things the prior draft got wrong and this plan
> fixes (details inline): (1) the proposed grep tokens
> (`item_done|RAUF_NEEDS_HUMAN|...`) match **neither** rauf's log **nor** its JSON
> event stream — the real surfaces and vocabularies are documented below; (2) rauf
> does **not** pause the loop on `needs_human`/`blocked`/`review` — it sets the item
> aside and keeps running, so "answer the question mid-run and resume" is not
> mechanically possible today; live monitoring delivers **visibility + early-cancel +
> post-run remediation**, not mid-loop Q&A injection; (3) `Monitor`'s `timeout_ms`
> caps at 3,600,000 ms (1 hour) — for multi-hour runs the watch **must** use
> `persistent: true`, not a bounded timeout.

Scope (per user decisions): all edits land in feature-forge only; rauf enhancement
ideas go into a **separate handoff document**; parallel subagent fan-out is adopted
for verify and spec authoring.

---

## What the monitoring surface actually is (ground truth)

The redesign depends on what rauf really emits. Verified against rauf source
(`/home/gary/workspace/rauf`):

- **`rauf.log` is plain human-readable text**, not JSON and not `key=value`:
  `[YYYY-MM-DD HH:MM:SS] <message>` (`packages/core/src/status.ts:500-509`). Its
  stable line vocabulary (the patterns rauf's own status-derivation depends on,
  `packages/core/src/schemas.ts:328-337`) is prose like `Item <id> completed: …`,
  `Item <id> blocked: …`, `Item <id> needs human input (set aside): …`,
  `Loop completed`, `Loop error: …`, `Signal: needs_human (…)`, `--- Iteration N / M ---`.
  **None of the prior draft's tokens (`item_done`, `RAUF_NEEDS_HUMAN`, `loop_error`)
  appear in the log.** Worse, the log's `Signal text (source=…)` line dumps up to 500
  chars of raw agent stdout — which can contain a literal `RAUF_DONE`/`RAUF_BLOCKED`
  mid-paragraph — so a naive `grep RAUF_DONE` fires on agent chatter, not completion.
- **The machine-readable surface is `rauf loop run … --ndjson`** (`packages/cli/src/
  loop-commands.ts:782-784, 941-965`): one JSON `LoopEvent` per stdout line plus a
  trailing `LoopResult`. The event union (`schemas.ts:552-576`) has base fields
  `{type, timestamp, projectPath}` and the discriminating `type` values we care about:
  `item_completed{itemId,title}`, `item_blocked{itemId,reason}`,
  `needs_human{itemId,reason}`, `signal_parsed{itemId,signal,reason?}`,
  `loop_completed`, `loop_error`, `loop_cancelled` (plus iteration/tool/review events).
  **This is the correct thing to monitor** — stable, structured, no false-positive
  hazard.
- **The `RAUF_DONE/BLOCKED/NEEDS_HUMAN/REVIEW` signals are emitted by the *coding
  agent* into its stdout**, parsed by rauf (`packages/loop/src/signal-parser.ts:40-68`),
  and surfaced as the `Signal:` log line + the NDJSON `needs_human`/`signal_parsed`
  events. They are **not** rauf-authored log lines, so a filter keys off the parsed
  events/log lines, never the raw `RAUF_*` tokens.
- **rauf does not halt on a human signal.** `needs_human` sets the item aside as
  `blocked + needsHuman`, emits the event, and **continues the loop**
  (`packages/loop/src/runner.ts:679-701`: *"Do NOT halt the loop — keep working other
  still-runnable items"*). `blocked` and `review` likewise don't pause. The whole run
  finishes, then `DONE`/status classifies `PAUSED_HUMAN` if any human items remain.
- **Liveness and stall are already computed by rauf.** `iteration-status.json`
  (`packages/core/src/iteration-status.ts`, schema `schemas.ts:595-607`) is written
  ~1/sec during an iteration with `currentTool`, `lastActivityAt`, and a `stuckWarning`
  boolean, and is **deleted when the iteration ends**. `rauf loop watch --json`
  surfaces it. `state.json.updatedAt` alone is **not** a liveness proof — rauf derives
  RUNNING/PAUSED from `.loop.lock` PID liveness, not state-file staleness.
- **Richer status than `backlog list`:** `rauf status --json` returns a `DerivedStatus`
  (`schemas.ts:263-276`) with `loopState` (UPPERCASE enum) and
  `backlogSummary{pending,inProgress,blocked,needsHuman,deferred,done,total}` — the
  right shape for milestone updates and the final summary, and it distinguishes the
  three flavors of "not done": genuine `blocked`, `needsHuman`, and runner-`deferred`
  ("false blocks"). The config's current `statusCommand` lacks `--json`.

Implication: the central bet (use `Monitor`) is correct, but the **thing monitored**
must be the NDJSON event stream (or, as fallback, the corrected log-line patterns),
and the **runner command** that produces it must be config-rendered (rauf-specific
`--ndjson`), not hardcoded. This couples Change 1 to the config schema and the rauf
handoff more tightly than the prior draft acknowledged.

---

## Findings Summary (ranked by impact)

1. **forge-5-loop is fire-and-forget.** No interim progress, no mid-run surfacing of
   blocked/needs-human/review/deferred events, no stall detection. Conflicts with intent.
2. **The monitored surface and event vocabulary in the prior draft were wrong** — they
   matched neither rauf's text log nor its JSON stream. Corrected above.
3. **forge-verify runs ~15–38 checklist items serially in one Opus agent** (single
   `forge-verifier` dispatch, `skills/forge-verify/SKILL.md:13-18`). Slow and shallow
   vs. a parallel per-dimension fan-out with adversarial confirmation.
4. **forge-3-specs writes the whole spec suite in the main session** in 3–5-doc batches
   (`skills/forge-3-specs/SKILL.md:54-66`) — heavy main-context pressure, serialized.
5. **forge-2-tech dispatches a single researcher** (`skills/forge-2-tech/SKILL.md:25-31`)
   even when the codebase is large — parallel researchers would cut latency, deepen coverage.
6. **Model references are already alias-based and clean.** Verified: the only `model:`
   declarations are `agents/forge-verifier.md:5` (`opus`) and `agents/forge-researcher.md:5`
   (`sonnet`); **no stale pinned `claude-*` IDs exist in shipping code.** Change 5 shrinks
   to a confirmation pass (the one stale `claude-opus-4-6` literal lives in *rauf's*
   examples — a handoff item).
7. **rauf's machine-readable surface is real but undocumented as a contract** (the NDJSON
   vocabulary, the `status --json` shape, the `iteration-status.json` stuck signal) — and
   has one internal bug (the `needsHuman` log-pattern in `schemas.ts` expects
   `needs human input:` but the runner writes `needs human input (set aside):`). Addressed
   in the handoff doc.

---

## Change 1 — forge-5-loop: proactive monitoring (PRIMARY)

**Files:** `skills/forge-5-loop/SKILL.md`, `references/forge-config-schema.json`,
`references/ralph-loop-contract.md`

Replace the fire-and-forget model (Steps 3b–3d + the "Never poll or sleep" gotcha) with
a **launch-then-watch** model. Keep the config-driven, runner-agnostic design — every
command still renders from the `loopRunner` block.

### Architecture (hybrid: durable launch + structured-event watch)

This shape gives all three of: the loop survives session end (today's promise,
`SKILL.md:169`), a clean machine-readable event stream, and a single
completion signal.

- **3b — launch the structured-event run, backgrounded.** Render a **new config
  field** `loopRunner.eventStreamCommand`
  (`{bin} loop run . --backlog {backlogDir} --iterations {iterations} --ndjson`) and run
  it via Bash `run_in_background: true`, redirecting stdout to a stable events file in
  the state dir (e.g. `{stateDir}/events.ndjson`). This keeps the loop detached/durable
  **and** emits structured events. The background-process **exit notification** remains
  the single authoritative terminal signal (reached at Step 4).
  - *Fallback:* if the runner advertises no NDJSON (`eventStreamCommand` absent), fall
    back to today's `runCommand` and tail `rauf.log` with the **corrected** text filter
    (anchored prefixes, never `RAUF_*` tokens — see 3d fallback).

- **3d — arm a `Monitor` on the event stream.** `Monitor` with **`persistent: true`**
  (NOT a bounded `timeout_ms` — its max is 1 hour and runs can exceed that), command:
  `tail -n +1 -f {stateDir}/events.ndjson 2>&1 | jq -rc --unbuffered 'select(.type | test("…"))'`
  with a **coverage-complete** type alternation (per Monitor's "silence is not success"
  rule — the filter must catch every terminal/exception state, not just the happy path):

  ```
  item_completed|item_blocked|needs_human|signal_parsed|loop_completed|loop_error|loop_cancelled|llm_stuck_warning
  ```

  - *Log-tail fallback filter* (no NDJSON): grep the **structured prose prefixes**, not
    signal tokens — `^\[.*\] (Item \S+ (completed|blocked):|Item \S+ needs human input|Loop completed|Loop error:|Circuit breaker:)`.
    Note the rauf log-pattern quirk: needs-human is written `needs human input (set aside):`,
    so match `needs human input` **without** a trailing colon.
  - Use `jq`/`grep` with line-buffering (`--unbuffered`/`--line-buffered`) so events
    aren't trapped in pipe buffers.

- **3e — react to events as they land:**
  - `item_completed` → keep a running tally. These arrive minutes apart for tens of
    items, so they will **not** trip Monitor's flood auto-stop; still, summarize a
    milestone ("12/30 done") rather than echoing each line verbatim. Pull richer counts
    with a one-shot `{statusCommand} --json` (add `--json` to the rendered status command)
    when you want the `done/total/blocked/needsHuman/deferred` breakdown.
  - `needs_human` / `signal_parsed{signal:"needs_human"}` → **surface immediately** and
    **`PushNotification`** the user (an hours-long run means they've likely walked away).
    **Reality check that changes the prior draft:** rauf has already *set the item aside
    and kept running* — answering now does **not** resume that item mid-loop. So the
    correct live action is: report the question + item, optionally collect the user's
    answer via `AskUserQuestion` **to stage post-run remediation**, and offer to
    **cancel early** (write the `CANCEL` sentinel / stop the run) if the answer changes
    the whole plan. Do not imply the loop is paused waiting on the reply.
  - `item_blocked` → surface the blocked item + reason now (visibility), accumulate for
    the final summary's `--retry-blocked` offer. Distinguish genuine `blocked` from
    runner-`deferred` ("false blocks") using the `status --json` `backlogSummary`.
  - `loop_error` → surface now; this is a real failure, `PushNotification` (a
    circuit-breaker halt is emitted as `loop_error` — there is no distinct
    `circuit_breaker` event).
  - **Stall detection — consume rauf's own signal, don't reinvent.** rauf emits an
    `llm_stuck_warning` event (in the filter above) when an iteration stops progressing;
    surface it live. To probe on quiet, one-shot `{watchCommand}` (`rauf loop watch
    --json`, a new config field) or read `{stateDir}/iteration-status.json` and check
    `stuckWarning` / `lastActivityAt`. Only flag a hang/offer `--force` when rauf reports stuck —
    `state.json.updatedAt` is not a reliable liveness proxy.

- **Step 4 (keep) — final reconciliation, reached via the background-exit notification**
  (the authoritative terminal signal; the `loop_completed` event is the live heads-up).
  Run `{statusCommand} --json` for the final `backlogSummary`. **Extend the existing
  all-done / blocked / iteration-limit branches** to also report `needsHuman` and
  `deferred` counts as distinct outcomes (today Step 4 only knows done/blocked/pending),
  each with its remediation (`--retry-blocked`, answer-then-retry for needs-human,
  re-run for deferred).

- **Reconcile the gotcha.** The existing "Do NOT poll or sleep / never foreground-sleep"
  warning was correct about *foreground blocking* but is now misread as "stay silent."
  Rewrite to: never block the session in the foreground; use `Monitor` (harness-driven,
  event-streamed — not a sleep loop) for live updates, and `PushNotification` for
  walk-away alerts.

Net effect: the loop becomes a supervised run that reports progress live, distinguishes
the four terminal outcomes, pulls the human back at action-worthy moments, and detects
stalls using rauf's own telemetry — fulfilling the original design intent within what
rauf actually supports today. (True mid-loop pause/answer/resume is a rauf capability —
Change 6 handoff.)

## Change 2 — forge-verify: parallel dimensioned verification

**Files:** `skills/forge-verify/SKILL.md`, `agents/forge-verifier.md`

- Split the per-mode checklist (`skills/forge-verify/references/verification-checklists.md`,
  e.g. specs = CHECK-S01..S38) into **dimension groups** (types/contracts,
  architecture/layout, cross-reference/traceability, testing, integration). Dispatch one
  `forge-verifier` agent **per group in parallel** (single message, multiple Agent calls)
  — the pattern in `superpowers:dispatching-parallel-agents`.
- Use the current **structured-output** convention: have each verifier return its findings
  as a compact JSON object (severity/check-id/file/line/rationale), so the main session
  merges machine-readably instead of re-parsing prose.
- Main session **dedups + synthesizes** findings into the single
  `VERIFY-{mode}-{date}.md` and Fix Execution Plan (format unchanged, so `forge-fix`
  needs no change).
- **Adversarial confirmation pass (opt-in "deep verify"):** re-check `error`/`gap`
  severity findings with a second short skeptic agent prompted to **refute** (default to
  "refuted" when uncertain), to cut false positives before they reach the user — the same
  "silence is not success" discipline applied to claims rather than logs.
- `forge-verifier.md`: add a "dimension/group" parameter to its protocol and a note that
  it may be one of several parallel instances; keep `memory: project`, read-only tools,
  `model: opus`. Lower `maxTurns` per instance (currently 40) since scope is narrower.

## Change 3 — forge-3-specs: parallel spec authoring

**Files:** `skills/forge-3-specs/SKILL.md`, **new** `agents/forge-spec-writer.md`

- After the document-suite plan is **approved** (Step 3, unchanged — still a human gate),
  dispatch parallel `forge-spec-writer` subagents, **one per numbered doc**, each given
  the PRD, tech-spec, stack profile, and the specific archetype slice to write.
- Keep `00-core-definitions` / `01-architecture-layout` as a **first sequential pass**
  (shared types the domain docs depend on), *then* fan out the domain docs in parallel.
- New agent `agents/forge-spec-writer.md`: needs `Write` (unlike the read-only agents),
  `model: opus`, scoped to author exactly one spec doc to the quality bar in
  `references/spec-examples.md`, constrained to write **only** its assigned file. Have it
  return a small structured manifest of the REQ IDs it covered, to feed the traceability
  assembly.
- Main session retains the **serial finish**: cross-reference validation,
  requirement-coverage tables, and `TRACEABILITY.md` assembly (these need the whole suite
  in view).

## Change 4 — forge-2-tech: optional parallel research

**File:** `skills/forge-2-tech/SKILL.md`

Allow dispatching **multiple `forge-researcher` agents in parallel** (by subsystem /
integration area) when the codebase is large or scope is uncertain, instead of the single
researcher (`SKILL.md:25-31`). Keep the single-researcher path as the default for
small/known scopes. No agent change required — `forge-researcher.md` already returns a
self-contained report; dispatch N with disjoint focuses and merge.

## Change 5 — Model-reference + capability confirmation (small)

**Files:** `agents/*.md`, `references/process-overview.md`, `README.md`

Scope is smaller than first thought: a repo grep confirms **no stale pinned model IDs in
shipping code** — agents already use `opus`/`sonnet` aliases (`forge-verifier.md:5`,
`forge-researcher.md:5`), and skills reference no model at all.

- Confirm the aliases still resolve to the intended tiers (current: Opus 4.8 / Sonnet 4.6
  / Haiku 4.5 / Fable 5).
- Note where a cheaper tier (Haiku 4.5) suits mechanical checks (e.g. the traceability /
  cross-reference verification dimension in Change 2) vs. Opus for judgement-heavy
  verification.
- The only stale literal (`claude-opus-4-6`) is in *rauf's* `author-backlog` example — a
  Change 6 handoff item, not a feature-forge edit.

## Change 6 — rauf enhancement handoff document

**New file:** `plans/rauf-enhancement-recommendations.md` (handoff for the rauf dev agent)

Capture, without implementing, the rauf-side changes that make feature-forge monitoring
cleaner and unlock capabilities the plan wants but can't have today:

- **Document the NDJSON event vocabulary as a stable contract.** The `LoopEvent` union
  (`item_completed`, `item_blocked`, `needs_human`, `signal_parsed`, `loop_completed`,
  `loop_error`, `loop_cancelled`, `llm_stuck_warning`, …; a circuit-breaker halt is emitted
  as `loop_error`, not a distinct event) is what Change 1's monitor depends
  on; treat its `type` strings + payload fields as a versioned contract, surfaced in
  `SPEC-BACKLOG-TOOL-CONTRACT.md`.
- **`status --json` as the documented status surface** (the `DerivedStatus` /
  `backlogSummary` shape), so supervisors don't parse the human log.
- **Pause/resume-with-answer (the big one).** Today `needs_human` sets the item aside and
  the loop runs on; there is no way to inject a human answer mid-run. A first-class
  "pause on needs_human" mode and/or a `resume --answer <itemId> <text>` verb would let a
  supervising session do true mid-loop Q&A (Change 1 stages the answer; rauf would consume
  it). Also surface `NEEDS_HUMAN` via an exit/status a supervisor can detect without
  tailing.
- **Fix the internal `needsHuman` log-pattern bug:** `schemas.ts` LOG_PATTERN expects
  `needs human input:` but the runner writes `needs human input (set aside):`, so rauf's
  own log-derived status can miss it.
- **De-risk the log false-positive:** the `Signal text (source=…)` dump leaks raw agent
  `RAUF_*` tokens into `rauf.log`; consider redaction or a separate machine channel so
  text-grep consumers aren't misled.
- **Cross-repo:** refresh the stale `"model": "claude-opus-4-6"` example in rauf's
  `author-backlog` references.

---

## Critical files

- `skills/forge-5-loop/SKILL.md` — monitoring redesign (primary)
- `references/forge-config-schema.json` — **new** `eventStreamCommand`, `watchCommand`;
  add `--json` to `statusCommand`
- `references/ralph-loop-contract.md` — document the NDJSON event stream as the monitored
  seam (and that `loop follow`/`log --follow` are human-formatted, not machine-readable)
- `skills/forge-verify/SKILL.md`, `agents/forge-verifier.md` — parallel verification
- `skills/forge-3-specs/SKILL.md`, `agents/forge-spec-writer.md` (new) — parallel authoring
- `skills/forge-2-tech/SKILL.md` — optional parallel research
- `agents/*.md`, `references/process-overview.md`, `README.md` — model-ref confirmation
- `plans/rauf-enhancement-recommendations.md` (new) — rauf handoff

## Suggested sequencing

1. **Change 1 (forge-5-loop)** — highest impact, matches the explicit ask. Land the
   config-schema fields (`eventStreamCommand`, `watchCommand`, `statusCommand --json`)
   first, then the skill redesign.
2. **Change 6 (rauf handoff doc)** — write alongside Change 1 while the contract is fresh
   (the NDJSON vocabulary and pause/resume gap are discovered here).
3. **Change 2 (forge-verify fan-out)** — independent, high value.
4. **Change 3 (forge-3-specs fan-out)** + new spec-writer agent.
5. **Change 4 (parallel research)** and **Change 5 (model confirmation)** — small, do last.

## Verification

- **forge-5-loop:** seed a tiny throwaway backlog (2–3 items, one deliberately ambiguous
  to trigger `needs_human`) in a scratch repo with rauf installed; run
  `/feature-forge:forge-5-loop`. Confirm: (a) interim `item_completed` progress messages
  appear during the run; (b) the `needs_human` event is surfaced mid-run with a
  `PushNotification` and the user is correctly told the item was set aside (not that the
  loop is paused); (c) stall detection reads `iteration-status.json.stuckWarning` rather
  than guessing from `state.json`; (d) the final summary distinguishes
  done/blocked/needsHuman/deferred; (e) no foreground blocking / Bash timeout. Then append
  a synthetic `{"type":"loop_error",…}` line to the events file and confirm the monitor
  filter fires (silence-is-not-success check). Use rauf's
  `test-sandbox/scenarios/stream-needs-human.sh` to drive a realistic `needs_human`.
- **forge-verify:** run on an existing spec suite; confirm parallel agents produce a single
  merged `VERIFY-*.md` whose findings match (or exceed) the prior single-agent run, and
  that `forge-fix` still parses the Fix Execution Plan unchanged.
- **forge-3-specs:** run on a small feature; confirm parallel writers produce the numbered
  docs, the sequential finish builds `TRACEABILITY.md`, and cross-references resolve. Run
  `scripts/validate-traceability.py` for full REQ coverage.
- **Regression:** `forge` navigator still renders state; `bash scripts/validate.sh` passes
  against an updated `forge.config.json` (new `loopRunner` fields must be optional /
  back-compatible).
- **Models:** grep for `claude-opus`/`claude-sonnet`/`claude-haiku` literals; confirm none
  reference retired IDs (expected: none in shipping code).
