# rauf Enhancement Recommendations (handoff from feature-forge)

> **Historical note (superseded by rauf v0.5.0 grammar).** This planning document predates
> rauf's v0.5.0 CLI grammar change and references removed verbs. In current rauf: `loop follow`
> is now the top-level **`follow`**, and `loop watch` was **removed** (its tool/token detail is
> available via `follow` or `status --json`). Mentions of `loop follow` / `loop watch` /
> `loop start` below are kept as-written for historical accuracy — map them to the current
> grammar when acting on this doc.

This is a **handoff document for the rauf maintainer/dev agent**, not a feature-forge
work item. It captures rauf-side changes that would make feature-forge's live loop
supervision (the `forge-5-loop` monitoring redesign) cleaner and unlock a capability the
pipeline wants but cannot have today. Nothing here is implemented in rauf by feature-forge;
these are requests/recommendations.

Context: `forge-5-loop` now launches the loop backgrounded and **supervises it live** via
the `Monitor` tool watching a machine-readable event stream, surfacing milestones and
exceptions to the user as they happen, with stall detection and walk-away push
notifications. That redesign leans on several rauf surfaces. The findings below come from
reading rauf source (`/home/gary/workspace/rauf`).

## 1. Treat the NDJSON event vocabulary as a published contract

`rauf loop run … --ndjson` (`packages/cli/src/loop-commands.ts:782-784, 941-965`) emits one
`LoopEvent` per stdout line plus a trailing `LoopResult`. This is the cleanest thing to
supervise. The discriminated union lives at `packages/core/src/schemas.ts:552-576`. The
`type` strings feature-forge depends on:

- `item_completed { itemId, title }`
- `item_blocked { itemId, reason }`
- `needs_human { itemId, reason }`
- `signal_parsed { itemId, signal, reason? }` (note: `signal` collapses `review`→`done`,
  `runner.ts:607` — worth documenting)
- `loop_completed`, `loop_error`, `loop_cancelled` (a circuit-breaker halt is emitted as
  `loop_error`, `runner.ts:1173` — there is no distinct `circuit_breaker` event)
- `llm_stuck_warning` (live stall signal)
- (iteration/tool/review events)

Every event carries `{ type, timestamp (ISO), projectPath }`.

**Ask:** document this `type` vocabulary + payload fields as a **versioned contract** in
`docs/SPEC-BACKLOG-TOOL-CONTRACT.md` (the same place the backlog schema + `validate` verb
are formalized), so downstream supervisors can rely on it not silently changing. Today it
is implementation, not contract.

## 2. Document `status --json` as the status surface

`rauf status … --json` (`status-commands.ts:74-77, 113-116`) returns a `DerivedStatus`
(`schemas.ts:263-276`) with `loopState` (UPPERCASE enum) and
`backlogSummary { pending, inProgress, blocked, needsHuman, deferred, done, total }`, plus
`lock { present, pid, alive, stale }`. feature-forge uses this for milestone tallies and
the final summary because it cleanly separates the three non-done outcomes (genuine
`blocked` vs `needsHuman` vs runner-`deferred` "false blocks").

**Ask:** treat the `DerivedStatus` shape as part of the documented contract. It is the
right machine surface for "where is the run"; `loop follow` / `log --follow` are
human-formatted (see §5) and should not be the recommended programmatic surface.

## 3. Pause / resume-with-answer for `needs_human` (the high-value one)

Today, when the coding agent emits `RAUF_NEEDS_HUMAN`, the runner **sets the item aside as
`blocked + needsHuman` and keeps running** other items to completion — it does **not** halt
for input (`packages/loop/src/runner.ts:679-701`: *"Do NOT halt the loop — keep working
other still-runnable items"*). There is no way to inject the human's answer and resume that
item mid-run; resolution is a follow-up retry pass.

This caps what a supervising session can do: it can surface the question live and cancel
early, but it cannot do true mid-loop Q&A. Two enhancements would unlock it:

- **A `--pause-on-needs-human` run mode** that halts the loop (status `PAUSED_HUMAN`,
  which already exists in the state enum, `schemas.ts:159-173`) and waits, so a supervisor
  can detect the pause and gather an answer.
- **A `resume --answer <itemId> "<text>"` verb** (or equivalent) that injects the answer
  back into the set-aside item and re-queues it, so the supervisor's collected answer is
  actually consumed.

Also: surface `NEEDS_HUMAN` through an **exit/status code** a supervisor can detect without
tailing logs (status already exits `2` for `PAUSED_HUMAN`, `status-commands.ts:353` — make
that reachable mid-run under the pause mode).

## 4. Fix the internal `needsHuman` log-pattern drift

`LOG_PATTERNS.needsHuman` (`packages/core/src/schemas.ts:328-337`) expects
`Item <id> needs human input: <reason>`, but the runner actually writes
`Item <id> needs human input (set aside): <reason>` (`runner.ts:699`). The `: ` the regex
anchors on is preceded by ` (set aside)`, so the pattern **does not match** the real line —
rauf's own log-derived status can miss needs-human events. Either align the regex
(`needs human input.*:`) or align the emitted string.

## 5. Don't let raw agent signals leak into the human log as false matches

The `Signal text (source=…)` line (`runner.ts:615-618`) dumps up to ~500 chars of raw agent
stdout into `rauf.log` — which can contain a literal `RAUF_DONE` / `RAUF_BLOCKED` mid-prose.
Any consumer that greps the log for `RAUF_*` tokens will false-match on agent chatter rather
than a real terminal signal. feature-forge already avoids this (it monitors the NDJSON
stream, and in the log fallback keys off the structured `Item …` / `Loop …` prose prefixes,
not the tokens). Still, consider redacting the dump or routing it to a separate diagnostic
channel so the human log stays grep-safe. Relatedly, clarify in docs that `loop follow`
(direct mode) and `log --follow` are **human-formatted** tails, not machine surfaces.

## 6. Cross-repo: refresh the stale model id in rauf's examples

rauf's `author-backlog` references still show `"model": "claude-opus-4-6"`. Refresh to a
current alias/id (prefer the `opus` alias so it tracks the tier). feature-forge's own
shipping code is already alias-based and carries no stale pinned IDs — this is the only
stale literal in the two repos' relevant surfaces.

---

### Summary of what feature-forge now depends on from rauf

| Surface | rauf command | Used by forge-5 for | Status |
|---|---|---|---|
| NDJSON event stream | `loop run … --ndjson` | live supervision (Monitor) | exists; please contract-document (§1) |
| Derived status JSON | `status … --json` | milestones + final summary | exists; please contract-document (§2) |
| Iteration telemetry | `loop watch … --json` (`stuckWarning`) | stall detection | exists |
| Pause/resume on needs-human | — | true mid-loop Q&A | **does not exist** (§3) |

feature-forge degrades gracefully where a runner lacks these (falls back to the human log
and a post-run retry model), so none of this blocks the pipeline — but §1–§3 would make the
integration first-class.
