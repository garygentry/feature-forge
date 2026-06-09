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
| 0.9.0         | config-driven (`loopRunner`, default rauf) | **0.2.0**        | 1                       | Delegates authoring to rauf `author-backlog` and validation to `rauf backlog validate`. Enforces `minRunnerVersion` via `rauf version --json` before running. Requires rauf ≥ 0.2.0 (first release shipping `backlog validate` + `schemaVersion`). |
| 0.8.0         | `rauf` (hardcoded CLI) | —                | _(unversioned)_         | Structural extraction only. Invoked `rauf` exactly as 0.7.0 did. No `loopRunner` block; no `rauf backlog validate` dependency.    |

## Version gate

feature-forge 0.9.0+ requires a runner that exposes `backlog validate` + backlog
`schemaVersion`. For rauf that is **0.2.0**, set as `loopRunner.minRunnerVersion`.
`forge-5-loop` enforces it (`rauf version --json`, semver-compared) and stops
with `loopRunner.installHint` if the runner is missing or older — before
invoking the loop. `forge-4-backlog` degrades gracefully (authors, then skips
validation with a warning) when the runner isn't installed yet, since it runs
before forge-5's setup gate.

> An alternative ralph-style runner conforming to the contract can be supplied
> via `loopRunner` (its own `bin`, schema, and `validate` command) without
> editing any pipeline skill.
