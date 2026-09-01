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
| 0.19.0        | config-driven (`loopRunner`, default rauf) | **0.14.0**       | 1                       | Floor raised to 0.14.0 — the version the package already pins (`RAUF_PIN`) and the floor for full needs-human recovery: rauf 0.14's `backlog answer` injects a recorded answer into the next iteration (below it, recovery degrades to `backlog unblock` and large Codex prompts can hit the pre-0.14 argv-size / `E2BIG` limit). The agent-selection surface (`--agent` / `rauf agents`, since 0.6.0) is subsumed. The floor now coincides with the installer pin, so the launch gate no longer green-lights a runner older than the package's own pin (#234). |
| 0.10.0        | config-driven (`loopRunner`, default rauf) | **0.6.0**        | 1                       | Requires rauf ≥ 0.6.0 — the floor that ships the agent-selection surface (`--agent` / `rauf agents`) consumed by `loopRunner.agentArgument` / `agentsProbeCommand`. Builds on rauf's v0.5.0 grammar + contract flip (unified exit codes across `status`/`loop run`, `loop run --detached` replacing `loop start`, explicit `review` signal, versioned `events.ndjson`), which 0.6.0 includes. Updated `followCommand` → `follow` and `watchCommand` → `status --json` for the new surface. |
| 0.9.0         | config-driven (`loopRunner`, default rauf) | **0.2.0**        | 1                       | Delegates authoring to rauf `author-backlog` and validation to `rauf backlog validate`. Enforces `minRunnerVersion` via `rauf version --json` before running. Requires rauf ≥ 0.2.0 (first release shipping `backlog validate` + `schemaVersion`). |
| 0.8.0         | `rauf` (hardcoded CLI) | —                | _(unversioned)_         | Structural extraction only. Invoked `rauf` exactly as 0.7.0 did. No `loopRunner` block; no `rauf backlog validate` dependency.    |

## Version gate

feature-forge **0.19.0+** requires rauf ≥ **0.14.0** (the version the package pins
and the floor for full needs-human recovery), set as `loopRunner.minRunnerVersion`;
0.10.0–0.18.x required ≥ 0.6.0 (the agent-selection surface); 0.9.0 required ≥ 0.2.0
(`backlog validate` + `schemaVersion`).
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
**`@garygentry/rauf@0.15.0`** (`installer/src/rauf.ts` `RAUF_PIN`). The **pin** is
distinct from the `minRunnerVersion` **floor** above (0.14.0): the floor is the
minimum rauf an existing install must satisfy, while the pin is the specific
known-good rauf a fresh install provisions. rauf 0.15.0 ships no new capability
feature-forge depends on (Codex provider sandbox/network config and a batch of
loop-runner fixes, none consumed by this package), so the floor stays at 0.14.0
while the pin advances ahead of it — the floor only rises when rauf ships a
surface feature-forge's stages actually require (as #234 did). The pin is
advanced on each feature-forge release to a newly published, compatible rauf;
rauf and feature-forge are versioned **independently** (no lockstep — this pin
and this matrix are the only coupling).

## Per-agent runner requirements

`minRunnerVersion` is a single floor applied to **every** agent. It is set to the
version the shipped stage actually depends on — **0.14.0**, the package pin and the
floor for full needs-human recovery — rather than the lowest version any single
capability needs. Earlier releases kept it at the lowest floor (0.6.0) and recorded
per-agent requirements here as prose; #234 reversed that, because a floor below the
pinned/recovery version let the launch gate green-light a runner the stage's own
contract could not fully support. Individual agents that need a *newer* rauf than
0.14.0 are still recorded here rather than by raising the floor for everyone.

- **Pi** — driving the loop with `--agent pi` needs rauf ≥ 0.13.0 (the release that
  ships the Pi agent preset), which the 0.14.0 floor already satisfies. `forge-5-loop`
  additionally discovers agents by probing `rauf agents --json` and offers one option
  per advertised row, so a rauf that predates a given preset simply never lists it —
  the pipeline degrades gracefully rather than failing. A fresh install provisions
  the pin above, which satisfies the floor and every current agent preset.
