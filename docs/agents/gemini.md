---
title: "feature-forge on Gemini"
---

# feature-forge on Gemini

> Canonical skills for the feature-forge pipeline, installed onto Gemini.
> The skills are spec-pure; Gemini's adapter is generated from canon (do not hand-edit
> `adapters/gemini/`).

## Install

Install with the universal one-liner — this copies the generated `adapters/gemini/` bundle into
Gemini's config directory:

```bash
npx @garygentry/feature-forge install -a gemini
```

To see the exact destination on your machine without writing anything, run:

```bash
npx @garygentry/feature-forge install -a gemini --dry-run --json
```

The `--dry-run --json` plan reports the resolved install destination — use that as the
authoritative path. (The install destination is derived from the installer, not asserted here;
see the note below.)

> **Note (install path):** Gemini installs as a CLI extension. **Global** scope
> (`~/.gemini/extensions/feature-forge/`) matches current Gemini docs (verified-current).
> **Project** scope (`.gemini/extensions/feature-forge/`) is **best-known** — project-scoped
> extension install is not clearly documented, so the install report labels it as such; prefer
> `--global` for Gemini. Use the `--dry-run --json` plan for the exact resolved path.

> **Runtime helpers:** installed bundles are self-contained — every runtime helper
> (`forge-root.sh`, `forge-init.sh`, `epic-manifest.py`, `validate-traceability.py`,
> `forge-bootstrap.py`) plus the neutral `.feature-forge-bundle.json` sentinel ship in the
> bundle, so `scripts/forge-root.sh` self-locates from the installed location.

## First-use check

1. List what got installed:
   ```bash
   npx @garygentry/feature-forge list -a gemini          # per-agent installed / up-to-date status
   ```
2. Invoke a forge skill on Gemini and confirm it fires. Gemini-specific invocation: prompt the
   Gemini CLI agent with "use feature-forge to run forge-init for a new feature" — Gemini should
   select the installed `forge-init` extension command from its adapter catalog.

## Loop runner (forge-5-loop)

See [The default loop runner](claude.md#the-default-loop-runner) — feature-forge defaults to
rauf and selects the coding agent via the documented precedence.
