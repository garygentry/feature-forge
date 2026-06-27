# Compatibility

feature-forge's pipeline ends in an autonomous **loop runner** that consumes a
`backlog.json` conforming to a published schema. The runner is configured via
the `loopRunner` block in `forge.config.json` and defaults to **rauf** (the
default and reference implementation). This document tracks which feature-forge
versions work with which rauf releases and backlog `schemaVersion`.

See `references/ralph-loop-contract.md` for the contract, and rauf's
[`SPEC-BACKLOG-TOOL-CONTRACT.md`](https://github.com/garygentry/rauf/blob/main/docs/SPEC-BACKLOG-TOOL-CONTRACT.md).

## feature-forge ↔ rauf ↔ schemaVersion

| feature-forge | Loop runner            | Min rauf version | Backlog `schemaVersion` | Notes                                                                                                                              |
| ------------- | ---------------------- | ---------------- | ----------------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| 0.10.0        | config-driven (`loopRunner`, default rauf) | **0.6.0**        | 1                       | Requires rauf ≥ 0.6.0 — the floor that ships the agent-selection surface (`--agent` / `rauf agents`) consumed by `loopRunner.agentArgument` / `agentsProbeCommand`. Builds on rauf's v0.5.0 grammar + contract flip (unified exit codes across `status`/`loop run`, `loop run --detached` replacing `loop start`, explicit `review` signal, versioned `events.ndjson`), which 0.6.0 includes. Updated `followCommand` → `follow` and `watchCommand` → `status --json` for the new surface. |
| 0.9.0         | config-driven (`loopRunner`, default rauf) | **0.2.0**        | 1                       | Delegates authoring to rauf `author-backlog` and validation to `rauf backlog validate`. Enforces `minRunnerVersion` via `rauf version --json` before running. Requires rauf ≥ 0.2.0 (first release shipping `backlog validate` + `schemaVersion`). |
| 0.8.0         | `rauf` (hardcoded CLI) | —                | _(unversioned)_         | Structural extraction only. Invoked `rauf` exactly as 0.7.0 did. No `loopRunner` block; no `rauf backlog validate` dependency.    |

## Version gate

feature-forge **0.10.0+** requires rauf ≥ **0.6.0** (the agent-selection surface,
built on the v0.5.0 grammar/contract flip), set as `loopRunner.minRunnerVersion`;
0.9.0 required ≥ 0.2.0 (`backlog validate` + `schemaVersion`).
`forge-5-loop` enforces it (`rauf version --json`, semver-compared) and stops
with `loopRunner.installHint` if the runner is missing or older — before
invoking the loop. `forge-4-backlog` degrades gracefully (authors, then skips
validation with a warning) when the runner isn't installed yet, since it runs
before forge-5's setup gate.

> An alternative ralph-style runner conforming to the contract can be supplied
> via `loopRunner` (its own `bin`, schema, and `validate` command) without
> editing any pipeline skill.

## Provisioned default pin (installer)

The cross-agent installer (`@garygentry/feature-forge`) records a single pinned
rauf coordinate as the provisioned default loop runner — currently
**`@garygentry/rauf@0.8.1`** (`installer/src/rauf.ts` `RAUF_PIN`). This **pin** is
distinct from the `minRunnerVersion` **floor** above: the floor is the minimum
rauf an existing install must satisfy (0.6.0), while the pin is the specific
known-good rauf a fresh install provisions. The pin is advanced on each
feature-forge release to a newly published, compatible rauf; rauf and
feature-forge are versioned **independently** (no lockstep — this pin and this
matrix are the only coupling).
