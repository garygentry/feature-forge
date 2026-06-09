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
from this block — there are no hardcoded `rauf …` strings in the skills.

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
  `RAUF_REVIEW`).
- **The state-dir layout** (per-`--backlog` isolation under `loopRunner.stateDir`).
- **The CLI verbs** mapped by `loopRunner`: run / validate / status / list /
  follow / log / version.
- **A `version` verb** (`{bin} version --json` → `{ version: <semver> }`) so
  feature-forge can enforce `loopRunner.minRunnerVersion` before running.

## rauf is the default and reference implementation

rauf owns the contract spec and is the runner feature-forge defaults to. The
authoring craft itself (how to decompose specs into well-scoped, verifiable
items) lives in rauf's **`author-backlog`** skill, which `forge-4-backlog`
delegates to — so the only thing binding feature-forge to a particular runner is
the schema + `validate` verb that this contract formalizes. A future runner swap
supplies its own `loopRunner` block (its own `bin`, schema, and `validate`
command) without touching any pipeline skill.

## Version gating

feature-forge requires a runner new enough to expose `backlog validate` +
backlog `schemaVersion`. For rauf that is **0.2.0** (`loopRunner.minRunnerVersion`).
`forge-5-loop` runs `{bin} version --json`, semver-compares the reported version
against `minRunnerVersion`, and on a missing-or-too-old runner stops with
`loopRunner.installHint` (the CLI install/upgrade command) — **before** invoking
the loop. See `COMPATIBILITY.md` for the version matrix.

> **Two different "installs."** `installHint` obtains/upgrades the runner **CLI
> binary** (e.g. rauf's `install-binary.sh`). `setupHint` installs the runner's
> **per-project artifacts** (rauf: `rauf install .`). A failing version gate is
> always the former, never the latter.
