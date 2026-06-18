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

Alternatively, install from a built clone (the `npx feature-forge` one-liner is
[not yet on npm](https://github.com/garygentry/feature-forge/issues/9) — see the repo
[README §(b)](../../README.md#b-any-agent--from-source) for the one-time `installer` build).
This copies the generated `adapters/claude/` bundle into Claude's config directory:

```bash
node installer/dist/cli.js install -a claude
```

To see the exact destination on your machine without writing anything, run:

```bash
node installer/dist/cli.js install -a claude --dry-run --json
```

The `--dry-run --json` plan reports the resolved install destination. Claude installs under
`~/.claude`.

> **Note (install path):** Claude's `~/.claude` destination is the only one treated as
> well-known. For the other agents (codex/copilot/cursor/gemini) the install destination is
> taken from the installer's `--dry-run --json` plan rather than hard-coded, because the
> cross-agent installer treats those config-dir conventions as best-known but unverified.

> **Known gap (installed-bundle self-location):** an installed non-Claude `adapters/<agent>/`
> bundle does not currently carry `epic-manifest.py` / `.claude-plugin/plugin.json`, so the
> portable resolver `scripts/forge-root.sh` cannot self-locate from an installed bundle. This
> is a known limitation owned by the adapter generator; it does not block install/first-use
> here.

## First-use check

1. List what got installed:
   ```bash
   node installer/dist/cli.js list -a claude          # per-agent installed / up-to-date status
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

feature-forge floors the runner at **rauf 0.6.0** (`loopRunner.minRunnerVersion`) — the version
that ships the `--agent` flag, the `agents` probe, and the preset agent registry — and checks
`rauf version --json` before any run.
*(rauf provisioning via `npx rauf@…` will be available once rauf is published to npm —
[garygentry/rauf#28](https://github.com/garygentry/rauf/issues/28). Today, install rauf via its
binary script: `curl -fsSL https://raw.githubusercontent.com/garygentry/rauf/main/scripts/install-binary.sh | bash`.)*

See [the loop-runner contract](../../references/ralph-loop-contract.md) for the full spec.
