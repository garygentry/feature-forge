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

> **Note (install path):** the destination for Cursor is taken from the installer's
> `--dry-run --json` plan, not hard-coded in this doc — the cross-agent installer treats the
> cursor config-dir convention as best-known but unverified. (Only Claude's `~/.claude`
> destination is treated as well-known.)

> **Known gap (installed-bundle self-location):** an installed `adapters/cursor/` bundle does not
> currently carry `epic-manifest.py` / `.claude-plugin/plugin.json`, so the portable resolver
> `scripts/forge-root.sh` cannot self-locate from an installed bundle. This is a known
> limitation owned by the adapter generator; it does not block install/first-use here.

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
