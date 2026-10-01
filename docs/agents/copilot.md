---
title: "feature-forge on Copilot"
---

# feature-forge on Copilot

> Canonical skills for the feature-forge pipeline, installed onto Copilot.
> The skills are spec-pure; Copilot's adapter is generated from canon (do not hand-edit
> `adapters/copilot/`).

## Install

Install with the universal one-liner — this copies the generated `adapters/copilot/` bundle into
Copilot's config directory:

```bash
npx @garygentry/feature-forge install -a copilot
```

To see the exact destination on your machine without writing anything, run:

```bash
npx @garygentry/feature-forge install -a copilot --dry-run --json
```

The `--dry-run --json` plan reports the resolved install destination — use that as the
authoritative path. (The install destination is derived from the installer, not asserted here;
see the note below.)

> **Note (install path — best-known):** the npm installer does not yet place the native
> bundle where Copilot discovers skills and agents (see "Bundle layout and invoking skills"
> below; installer support is tracked in #325). It uses repository instructions
> (`.github/copilot-instructions.md` / `AGENTS.md`) instead: it stages the bundle under
> `.github/feature-forge/` so the workflow files are available, and writes a managed block (delimited by
> `<!-- feature-forge:managed:start -->` / `<!-- feature-forge:managed:end -->`) into
> `.github/copilot-instructions.md` pointing Copilot at them — merged without disturbing any
> existing content in that file. This path is **best-known**, not vendor-confirmed for skill
> auto-discovery — the install report labels it as such. Use the `--dry-run --json` plan for
> the exact resolved path.

## Bundle layout and invoking skills

The generated `adapters/copilot/` bundle uses Copilot's native layout: a `plugin.json` manifest
(the legacy Copilot plugin format, which declares its `skills/` and `agents/` roots; it is not an
Agent Plugins 1.0 manifest), one `skills/<name>/SKILL.md` per skill (with `argument-hint` where
the skill takes arguments), and `agents/<name>.agent.md` custom agents. The three worker agents
(`forge-researcher`, `forge-spec-writer`, `forge-verifier`) are subagent-only
(`user-invocable: false`) and carry least-privilege Copilot tool aliases.

Copilot names the same skill differently depending on how it was installed: a plugin install
exposes `/feature-forge:<name>`, a direct project or personal install exposes `/<name>`. The
bundle therefore never hard-codes either form — skill bodies, references, and the stage-exit
NEXT-STEPS block (`forge-session.py stage-exit --host copilot`) write
`invoke-skill: <name> [arguments]`, and each skill's closing "Host execution notes (GitHub
Copilot)" section maps that notation to whichever form your install provides.

## First-use check

1. List what got installed:
   ```bash
   npx @garygentry/feature-forge list -a copilot          # per-agent installed / up-to-date status
   ```
2. Invoke a forge skill on Copilot and confirm it fires. Copilot-specific invocation: ask
   Copilot Chat to "use feature-forge to run forge-init for a new feature" — Copilot should
   select the installed `forge-init` skill from its adapter catalog.

## Loop runner (forge-5-loop)

See [The default loop runner](claude.md#the-default-loop-runner) — feature-forge defaults to
rauf and selects the coding agent via the documented precedence.
