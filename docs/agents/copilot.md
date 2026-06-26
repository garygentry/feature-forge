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

> **Note (install path — best-known):** Copilot has no native skills loader; its documented
> customization surface is repository instructions (`.github/copilot-instructions.md` /
> `AGENTS.md`). The installer stages the bundle under `.github/feature-forge/` so the workflow
> files are available, and a follow-up change writes a managed block into
> `.github/copilot-instructions.md` pointing Copilot at them. This path is **best-known**, not
> vendor-confirmed for skill auto-discovery — the install report labels it as such. Use the
> `--dry-run --json` plan for the exact resolved path.

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
