---
title: "feature-forge on Codex"
---

# feature-forge on Codex

> Canonical skills for the feature-forge pipeline, installed onto Codex.
> The skills are spec-pure; Codex's adapter is generated from canon (do not hand-edit
> `adapters/codex/`).

## Install

Install with the universal one-liner — this copies the generated `adapters/codex/` bundle into
Codex's config directory:

```bash
npx @garygentry/feature-forge install -a codex
```

To see the exact destination on your machine without writing anything, run:

```bash
npx @garygentry/feature-forge install -a codex --dry-run --json
```

The `--dry-run --json` plan reports the resolved install destination — use that as the
authoritative path. (The install destination is derived from the installer, not asserted here;
see the note below.)

> **Note (install path):** Codex skills install to the agent-neutral
> `.agents/skills/feature-forge/` (project) or `~/.agents/skills/feature-forge/` (global) —
> the location Codex discovers skills from (verified against current Codex docs, 2026-06-26).
> Codex detects on `.codex`; the install location is decoupled from it. Use the
> `--dry-run --json` plan for the exact resolved path on your machine.
>
> Codex custom agents (`forge-researcher` / `forge-spec-writer` / `forge-verifier`) are emitted
> as `.codex/agents/<name>.toml`; the installer placing them into `.codex/agents/` lands in a
> follow-up change (until then, copy them from the installed bundle's `agents/` dir).

> **Runtime helpers:** installed bundles are self-contained — every runtime helper
> (`forge-root.sh`, `forge-init.sh`, `epic-manifest.py`, `validate-traceability.py`,
> `forge-bootstrap.py`) plus the neutral `.feature-forge-bundle.json` sentinel ship in the
> bundle, so `scripts/forge-root.sh` self-locates from the installed location.

## First-use check

1. List what got installed:
   ```bash
   npx @garygentry/feature-forge list -a codex          # per-agent installed / up-to-date status
   ```
2. Invoke a forge skill on Codex and confirm it fires. Codex-specific invocation: prompt the
   agent with "use feature-forge to run forge-init for a new feature" — Codex should select the
   installed `forge-init` skill from its adapter catalog.

## Loop runner (forge-5-loop)

See [The default loop runner](claude.md#the-default-loop-runner) — feature-forge defaults to
rauf and selects the coding agent via the documented precedence.
