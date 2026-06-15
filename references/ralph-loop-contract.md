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

## Version gating

feature-forge requires a runner exposing `backlog validate` + backlog
`schemaVersion`, and (from v0.5.0) the unified exit-code/status contract it reads.
For rauf that is **0.5.0** (`loopRunner.minRunnerVersion`).
`forge-5-loop` runs `{bin} version --json`, semver-compares the reported version
against `minRunnerVersion`, and on a missing-or-too-old runner stops with
`loopRunner.installHint` (the CLI install/upgrade command) — **before** invoking
the loop. See `COMPATIBILITY.md` for the version matrix.

> **Two different "installs."** `installHint` obtains/upgrades the runner **CLI
> binary** (e.g. rauf's `install-binary.sh`). `setupHint` installs the runner's
> **per-project artifacts** (rauf: `rauf install .`). A failing version gate is
> always the former, never the latter.
