---
title: "feature-forge on Claude"
---

# feature-forge on Claude

> Canonical skills for the feature-forge pipeline, installed onto Claude Code.
> The skills are spec-pure; Claude's adapter is generated from canon (do not hand-edit
> `adapters/claude/`).

## Install

Claude Code is the first-class, preferred surface. Install via the plugin marketplace:

```bash
/plugin marketplace add garygentry/feature-forge
/plugin install feature-forge@feature-forge
```

Alternatively, install with the universal one-liner — this copies the generated
`adapters/claude/` bundle into Claude's config directory:

```bash
npx @garygentry/feature-forge install -a claude
```

To see the exact destination on your machine without writing anything, run:

```bash
npx @garygentry/feature-forge install -a claude --dry-run --json
```

The `--dry-run --json` plan reports the resolved install destination. Claude installs under
`~/.claude`.

> **Note (install path):** Claude's `~/.claude` destination is the only one treated as
> well-known. For the other agents (codex/copilot/cursor/gemini) the install destination is
> taken from the installer's `--dry-run --json` plan rather than hard-coded, because the
> cross-agent installer treats those config-dir conventions as best-known but unverified.

> **Claude bundle manifest (#322):** the built `adapters/claude/` bundle carries its own
> `.claude-plugin/plugin.json`, so Claude's plugin loader recognises it whether it is installed
> via `install -a claude`, added from a marketplace, or loaded with `claude --plugin-dir
> adapters/claude`. (`forge-root.sh` still self-locates on the neutral `.feature-forge-bundle.json`
> sentinel every bundle carries; the plugin manifest is the additional file Claude's own loader
> needs.) The equivalent host-native manifest for the other agents is tracked separately and does
> not block install/first-use here.

## First-use check

1. List what got installed:
   ```bash
   npx @garygentry/feature-forge list -a claude          # per-agent installed / up-to-date status
   ```
2. Invoke a forge skill on Claude and confirm it fires. Claude-specific invocation: type
   `/feature-forge:forge-init` (or `/feature-forge:forge` for a pipeline status check) at the
   Claude Code prompt — the slash command should resolve to the installed skill.

## Loop runner (forge-5-loop)

See [The default loop runner](#the-default-loop-runner) — feature-forge defaults to rauf and
selects the coding agent via the precedence below.

## The default loop runner

`forge-5-loop` hands the generated `backlog.json` to a loop runner that implements each item.
With no `loopRunner` block in `forge.config.json`, feature-forge **defaults to rauf** and
announces "defaulting to the rauf loop runner."

**Agent selection** flows forge → rauf with this precedence:

> `item (rauf backlog) > run (forge --agent) > project (forge loopRunner.defaultAgent) >
> rauf default (claude-cli)`

- **item** — `BacklogItem.provider` in the backlog; rauf applies it, forge passes it through
  (forge never reads, writes, or overrides it — a deliberate per-item agent always wins).
- **run** — `forge --agent <id>` for this run (forge-5-loop selector, Step 2d).
- **project** — `loopRunner.defaultAgent` in `forge.config.json`.
- **default** — rauf's own default, `claude-cli`, when forge sends nothing.

Backlog **`validate`** (forge-4-backlog / forge-verify) is **agent-agnostic** — it runs the
`validate` verb and never passes an agent (`--agent`, `{agent}`, or any id). Only execution
(forge-5-loop) carries the agent dimension.

feature-forge floors the runner at **rauf 0.14.0** (`loopRunner.minRunnerVersion`) — the version
the package pins and the floor for full needs-human recovery (it subsumes the older 0.6.0
agent-surface floor: the `--agent` flag, the `agents` probe, and the preset agent registry) — and
checks `rauf version --json` before any run.

**Machine-local runner override (#324).** *Which* rauf binary drives a repo is a machine fact, not
a project fact: the fleet standardises three named binaries — `rauf` (published npm pin, every
host), `rauf-dev` (workspace source, dev boxes), `rauf-stable` (compiled dogfood snapshot, dev
boxes) — see [rauf's `docs/DOGFOODING.md`](https://github.com/garygentry/rauf/blob/main/docs/DOGFOODING.md).
Rather than commit a machine name into `forge.config.json`, drop a gitignored **`forge.config.local.json`**
next to it — it is deep-merged over the committed config (local wins), scoped to the whole config
(so machine facts like a 1M `contextWindowTokens` get the same home):

```json
{ "loopRunner": { "bin": "rauf-dev" } }
```

`FEATURE_FORGE_LOOP_RUNNER_BIN` overrides `loopRunner.bin` above both (one-shot `rauf-dev` runs,
CI). Precedence: **env > local > committed > schema default**. `forge-session.py doctor --json`
reports the effective `bin` and which layer set it; `forge-session.py effective-config` prints the
resolved block with each key's layer. Keep the local file gitignored — `doctor`'s
`config-local-ignored` check warns (and names `.gitignore`) if it is not.
*(rauf is published to npm as [`@garygentry/rauf`](https://www.npmjs.com/package/@garygentry/rauf) —
install the CLI with `npx @garygentry/rauf` (or `npm i -g @garygentry/rauf`), or its binary script:
`curl -fsSL https://raw.githubusercontent.com/garygentry/rauf/main/scripts/install-binary.sh | bash`.)*

See [the loop-runner contract](https://github.com/garygentry/feature-forge/blob/main/references/ralph-loop-contract.md) for the full spec.
