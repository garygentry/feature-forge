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

The installer no longer writes anything into `.github/copilot-instructions.md`; Copilot loads the
skills and agents from the native mirrors.

### Upgrading an install from installer 0.3.9 or earlier

Installer 0.3.9 and earlier (feature-forge 0.21.0 and earlier) put the whole bundle at
`.github/feature-forge/` in both scopes (personal installs under `~/.github/`), with skills as
`skills/<name>/<name>.md`, and wrote a pointer block between
`<!-- feature-forge:managed:start -->` / `<!-- feature-forge:managed:end -->` in
`.github/copilot-instructions.md`. Run `npx @garygentry/feature-forge update -a copilot` (add `-g`
for a personal install) to migrate it; `list` flags such an install as `legacy-layout:true`.

- The update writes and hash-verifies the new runtime and native mirrors first, then removes only
  the files the old manifest recorded, then writes the new manifest. A personal install moves from
  `~/.github/feature-forge/` to `~/.copilot/feature-forge/`. If the update fails partway, re-run it.
- A symlinked old runtime is unlinked, never followed, so the package it pointed at is untouched
  (it may already be gone from the npx cache).
- The pointer block is removed only if you never edited it. Your own text in the file stays. An
  edited block is kept, and `list` reports it as `retired-block:edited` until you run
  `update --force`, which strips only the sentinel-bounded block.
- To remove an old install without upgrading, run `uninstall -a copilot` (with `-g` for a personal
  install). It removes the old runtime, its manifest and an unedited block.
- An old copy install cannot switch straight to `--symlink`: update without `--symlink`, or add
  `--force` to replace it.

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
