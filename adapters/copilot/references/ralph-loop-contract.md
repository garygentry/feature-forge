# The Loop-Runner Contract (consumer side)

feature-forge's pipeline ends by handing a `backlog.json` to an autonomous
**loop runner** that implements each item. feature-forge does not embed any
runner's internals — it talks to the runner through one indirection point: the
**`loopRunner`** block in `forge.config.json`.

## The seam

Every command feature-forge runs against the runner is a template in
`loopRunner`, with `{bin}`, `{backlogDir}`, `{specsDir}`, and `{iterations}`
substituted at call time. `forge-5-loop` (execution), `forge-4-backlog`
(validation), and `forge-verify` (backlog validation) all render their commands
from this block — there are no hardcoded `rauf …` commands in the skills, and
even the human log filename is tokenized via `{loopRunner.logFile}`.

When `forge.config.json` has no `loopRunner` block, feature-forge uses the
built-in defaults (see `references/forge-config-schema.json`) and announces
"defaulting to the rauf loop runner."

## The contract a runner MUST satisfy

A conforming runner MUST implement the **backlog-tool / loop-runner contract**
defined authoritatively in rauf's
[`SPEC-BACKLOG-TOOL-CONTRACT.md`](https://github.com/garygentry/rauf/blob/main/docs/SPEC-BACKLOG-TOOL-CONTRACT.md)
(Part A). In summary, it must provide:

- **A backlog schema** with the published `$id` and an optional `schemaVersion`,
  whose `type`/`status` vocabularies match the contract
  (`type ∈ bug|bugfix|refactor|feature|chore|test`,
  `status ∈ pending|in_progress|done|blocked`).
- **A `validate` verb** with exit codes `0` (valid) / `1` (findings) / `2`
  (usage/IO) that emits `{ valid, findings[] }` under `--json`. This is the
  single check feature-forge trusts — it never re-implements validation.
- **The signal protocol** (`RAUF_DONE` / `RAUF_BLOCKED` / `RAUF_NEEDS_HUMAN` /
  `RAUF_REVIEW`). These are emitted by the *coding agent* into its stdout and
  parsed by the runner — they are not runner-authored log lines, so consumers key
  off the runner's parsed events (below), never the raw `RAUF_*` tokens (which can
  also appear inside an agent's prose and produce false matches).
- **A machine-readable event stream** for live supervision (`loopRunner.eventStreamCommand`,
  rauf: `loop run … --ndjson`): one JSON event per line with a stable `type`
  vocabulary — `item_completed` / `item_blocked` / `needs_human` / `signal_parsed`
  / `loop_completed` / `loop_error` / `loop_cancelled` / `llm_stuck_warning` (a
  circuit-breaker halt surfaces as `loop_error`) — plus a
  derived-status JSON (`loopRunner.statusJsonCommand`, rauf: `status … --json`) and
  per-iteration telemetry with a `stuckWarning` flag (`loopRunner.watchCommand`,
  rauf: `status … --json` — the `loop watch` verb was removed in v0.5.0). `forge-5-loop` supervises the run through these,
  **not** by parsing the human log. `followCommand` / `logCommand` are
  human-formatted streams for a person watching in a terminal, not machine surfaces.
- **The state-dir layout** (per-`--backlog` isolation under `loopRunner.stateDir`).
- **The CLI verbs** mapped by `loopRunner`: run (+ event-stream) / validate /
  status (+ `--json`) / list / follow / log / version.
- **A `version` verb** (`{bin} version --json` → `{ version: <semver> }`) so
  feature-forge can enforce `loopRunner.minRunnerVersion` before running.

> **The runner does not pause for human input.** When the coding agent signals
> `RAUF_NEEDS_HUMAN`/`RAUF_BLOCKED`/`RAUF_REVIEW`, a conforming runner sets that
> item aside and **keeps working other runnable items to completion** (rauf:
> `runner.ts` needs_human handler). So a supervising session can surface those
> events live (visibility) and cancel early, but it cannot inject an answer and
> resume the set-aside item mid-run — resolution is a follow-up retry pass. A
> first-class pause/resume-with-answer capability is a desirable runner
> enhancement (see `plans/rauf-enhancement-recommendations.md`).

## rauf is the default and reference implementation

rauf owns the contract spec and is the runner feature-forge defaults to. The
authoring craft itself (how to decompose specs into well-scoped, verifiable
items) lives in rauf's **`author-backlog`** skill, which `forge-4-backlog`
delegates to — so the only thing binding feature-forge to a particular runner is
the schema + `validate` verb that this contract formalizes. A future runner swap
supplies its own `loopRunner` block (its own `bin`, schema, and `validate`
command) without touching any pipeline skill.

The coding-agent dimension this contract adds (below) is **additive and
presence-gated**: it exists only when the `loopRunner` block advertises it via
`agentArgument`. A runner that omits that field has no agent dimension at all —
the seam degrades to exactly today's behavior with no error, so default-to-rauf
and pluggability are unchanged. See `## Agent selection`.

## Agent selection

This section is **contract-level**: it states what a conforming runner exposes
and what forge does with it, and defers every algorithm to the owning specs
(`02`/`03`/`04`/`05`).

### What a conforming runner exposes (the consumed surface)

A runner that carries a coding-agent dimension exposes, in its `loopRunner`
block:

- an **`agentArgument`** template (rauf default `--agent {agent}`) — the
  tokenized launch-time flag; its **presence** advertises the agent surface;
- an **`agentsProbeCommand`** (rauf default `{bin} agents --json`) emitting
  `{ agents: [{ id, displayName, available, detail? }] }` and **always exiting
  0**;
- an optional **`defaultAgent`** project-default id.

These three fields are specified in full in `references/forge-config-schema.json`
and are the schema half of this contract. forge consumes rauf's existing
`--agent <id>` flag, `rauf agents` probe, `BacklogItem.provider`, and 5-layer
precedence — it conforms to them, it does not redesign them.

### Precedence and the run-layer mapping

The agent-selection precedence is **`item > run > project > default`**,
deliberately parallel to the model-selection precedence (`item.model >
--model/options > project default > provider default`). It is realized as:

- **item** — `BacklogItem.provider`, applied by **rauf** from the backlog. forge
  **never reads, writes, or overrides** it (pass-through), so a deliberate
  per-item agent always wins.
- **run** — forge's per-run selector (`forge-5-loop` Step 2d).
- **project** — forge's `loopRunner.defaultAgent`.
- **default** — the runner's own default (`claude-cli` for rauf) when forge sends
  nothing.

forge owns **only** the run and project layers. It collapses run-over-project
*inside itself* into the **single** `--agent {agent}` value it emits at the
**run layer**, and lets rauf apply the item override *above* that. forge **never
re-implements rauf's resolver**. The resolution algorithm itself lives in
`03-selection-resolution-observability.md`.

### Availability probe + unknown/unavailable disambiguation

When the resolved agent is a **non-default** id, forge runs `agentsProbeCommand`
**once (no retries)** before any loop side-effect, parses the advertised
`agents[]`, and builds the advertised id set. Because the probe **always exits
0**, an unknown id is distinguished from a known-but-unavailable one **only by
set membership**, not by exit code:

- **Unknown id** (not in the advertised set — a typo or unsupported agent):
  **hard-reject before launch**, listing the valid ids. No proceed-anyway path.
  No value is interpolated into `{agent}`.
- **Known but unavailable** (`available: false`): **warn** (showing the probe's
  `detail`) and let the user **proceed-anyway or choose another** — never
  silently abort, never silently proceed.
- **Available**: proceed.

The advertised id set is also the **allow-list**: the only value ever
interpolated into `{agent}` is a validated, advertised id. The **default /
claude path never reaches the probe** — it incurs no extra cost. The
`classify(...)` algorithm and the rejection-error text live in
`04-availability-precheck.md`.

### Capability gate + version floor

Agent selection is **capability-gated** on the runner advertising
`agentArgument`: a runner whose `loopRunner` omits (or empties) that field
exposes no agent surface, so the per-run selector, the probe, and any `{agent}`
substitution **vanish entirely** and no agent argument is sent — byte-identical
to today. Degradation is **silent, not an error**, keeping alternate (non-rauf)
runners first-class. The gate condition is owned by
`02-config-schema-and-gating.md`.

Independently, the **version gate** floors at the runner version that ships the
agent surface. For rauf that is **0.6.0** (`loopRunner.minRunnerVersion`): the
`--agent` flag, the `agents` probe, and the preset agent registry are present in
rauf source at 0.6.0. A successful gate therefore guarantees those surfaces
exist before any run. See `## Version gating` and
`05-runner-discovery-version-gate.md`.

**This document — the `## Agent selection` section, the `## Per-stage agent
applicability` table, and the `## validate is agent-agnostic` note — together
with the augmented `loopRunner` schema block in
`references/forge-config-schema.json` constitute the `forge-loop-runner-contract`
expose, consumed by the `packaging-docs-ci` capstone as documentation input.**

## Per-stage agent applicability

Every forge stage that invokes the loop runner is classified here. Only
`forge-5-loop` (execution) carries the coding-agent dimension; the two
validation-only stages are agent-agnostic.

| Stage | Runner verbs | Agent dimension |
|-------|-------------|-----------------|
| `forge-5-loop` | run / eventStream / status / version | **Full** — selector, probe, `--agent` |
| `forge-4-backlog` | `validate` | **None** — agent-agnostic |
| `forge-verify` | `validate` | **None** — agent-agnostic |

- **`forge-5-loop`** is the executor: it drives the run, so it renders the run /
  event-stream / status / version verbs (and `list`) and carries the full agent
  surface — the Step 2d selector, the availability probe, and the rendered
  `agentArgument`.
- **`forge-4-backlog`** authors and then *validates* the backlog; its only runner
  call is `validateCommand`. It also reads `versionCommand` for a graceful-degrade
  check, but **passes no agent** and never runs `loop run`.
- **`forge-verify`** (backlog mode) re-runs the same `validateCommand` to surface
  validation findings. It carries no agent dimension. This is **contract
  coverage** of forge-verify (it is classified here), with an explicit agnostic
  note (below) — **not** a new agent-driven run in forge-verify.

### `validate` is agent-agnostic

The `validate` verb (`loopRunner.validateCommand`) checks a `backlog.json`
against the backlog schema and spec references. **It does not run a coding agent
and has no agent dimension.** No agent argument — `--agent`, the `{agent}` token,
or any agent id — may **ever** be passed to backlog validation, in **any** stage
(`forge-4-backlog`, `forge-verify`, or any future caller). Backlog validation is
a pure, deterministic check; the coding agent is irrelevant to it. A contributor
who later adds agent selection to a *new* stage MUST confirm that stage runs the
*execution* surface (like `forge-5-loop`), not `validate` — agent selection
belongs to execution only. If you find yourself adding `--agent` near a
`validateCommand` render, that is a bug.

## Version gating

feature-forge requires a runner exposing `backlog validate` + backlog
`schemaVersion`, and the unified exit-code/status contract it reads. The floor is
now the **agent-surface floor**: the runner version that ships the `--agent`
flag, the `agents` probe, and the preset agent registry. For rauf that is
**0.6.0** (`loopRunner.minRunnerVersion`).
`forge-5-loop` runs `{bin} version --json`, semver-compares the reported version
against `minRunnerVersion`, and on a missing-or-too-old runner stops with
`loopRunner.installHint` (the CLI install/upgrade command) — **before** invoking
the loop. See `COMPATIBILITY.md` for the version matrix.

> **Two different "installs."** `installHint` obtains/upgrades the runner **CLI
> binary** (e.g. rauf's `install-binary.sh`). `setupHint` installs the runner's
> **per-project artifacts** (rauf: `rauf install .`). A failing version gate is
> always the former, never the latter.
