---
title: "feature-forge on Cursor"
---

# feature-forge on Cursor

> Canonical skills for the feature-forge pipeline, installed onto Cursor.
> The skills are spec-pure; Cursor's adapter is generated from canon (do not hand-edit
> `adapters/cursor/`).

## Install

Install with the universal one-liner — this copies the generated `adapters/cursor/` bundle into
Cursor's config directory:

```bash
npx @garygentry/feature-forge install -a cursor
```

To see the exact destination on your machine without writing anything, run:

```bash
npx @garygentry/feature-forge install -a cursor --dry-run --json
```

The `--dry-run --json` plan reports the resolved install destination — use that as the
authoritative path. (The install destination is derived from the installer, not asserted here;
see the note below.)

> **Note (install path):** Cursor rules install to `.cursor/rules/feature-forge/` (project) or
> `~/.cursor/rules/feature-forge/` (global) as `.mdc` rule files — confirmed against current
> Cursor docs (2026-06-26). Use the `--dry-run --json` plan for the exact resolved path.

> **Runtime helpers:** installed bundles are self-contained — every runtime helper
> (`forge-root.sh`, `forge-init.sh`, `epic-manifest.py`, `validate-traceability.py`,
> `forge-bootstrap.py`) plus the neutral `.feature-forge-bundle.json` sentinel ship in the
> bundle, so `scripts/forge-root.sh` self-locates from the installed location.

## First-use check

1. List what got installed:
   ```bash
   npx @garygentry/feature-forge list -a cursor          # per-agent installed / up-to-date status
   ```
2. Invoke a forge skill on Cursor and confirm it fires. Cursor-specific invocation: ask the
   Cursor agent to "use feature-forge to run forge-init for a new feature" — Cursor should
   select the installed `forge-init` skill from its adapter catalog.

## Loop runner (forge-5-loop)

See [The default loop runner](claude.md#the-default-loop-runner) — feature-forge defaults to
rauf and selects the coding agent via the documented precedence.
