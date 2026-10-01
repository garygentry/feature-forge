---
title: "feature-forge on Copilot"
---

# feature-forge on Copilot

> Canonical skills for the feature-forge pipeline, installed onto Copilot.
> The skills are spec-pure; Copilot's adapter is generated from canon (do not hand-edit
> `adapters/copilot/`).

## Install

Install with the universal one-liner. Project scope writes one complete runtime bundle at
`.github/feature-forge/` plus native discovery mirrors under `.github/skills/` and
`.github/agents/`:

```bash
npx @garygentry/feature-forge install -a copilot
```

Personal scope writes the complete runtime at `~/.copilot/feature-forge/` plus mirrors under
`~/.copilot/skills/` and `~/.copilot/agents/`:

```bash
npx @garygentry/feature-forge install -a copilot --global
```

To see the exact destination on your machine without writing anything, run:

```bash
npx @garygentry/feature-forge install -a copilot --dry-run --json
```

The `--dry-run --json` plan reports the resolved complete-runtime destination and every native
placement. GitHub documents project skills at `.github/skills/` and personal skills at
`~/.copilot/skills/`; fresh project and personal installs are runtime-verified on Copilot CLI
1.0.80 and therefore reported as `verified-current`.

The installer also still writes a transitional managed block into
`.github/copilot-instructions.md` (under the project or home directory). It is only a fallback
pointer to the complete runtime; Copilot loads the skills and agents from the native mirrors. The
block is delimited by
`<!-- feature-forge:managed:start -->` / `<!-- feature-forge:managed:end -->` and is merged
without disturbing user content. Its ownership-safe migration is separate from the fresh-install
layout.

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
2. Run `copilot skill list --json` and confirm the direct skills are visible.
3. Invoke one directly (for example `/forge-init`) and confirm it can resolve the complete
   runtime bundle for the active scope.

## Loop runner (forge-5-loop)

See [The default loop runner](claude.md#the-default-loop-runner) — feature-forge defaults to
rauf and selects the coding agent via the documented precedence.
