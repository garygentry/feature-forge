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
> as `.codex/agents/<name>.toml`, and the installer mirrors them flat into `.codex/agents/`
> (the location Codex loads custom agents from) alongside the primary bundle — no manual copy
> needed. `update`/`uninstall` reconcile the mirror together with the bundle.

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

## Supervising the loop (forge-5-loop)

Codex cannot wake a session when a background process prints or exits, so `forge-5-loop`
supervises a rauf loop from **inside the turn**: it launches the loop `--detached`, then repeats
`rauf loop wait … --since-seq N --run-id R --timeout 240s` (rauf ≥ 0.18.0) — one bounded wait per
shell call — printing each completed item's card and deciding from `rauf status --json` on any
exception, until the loop ends (`loop wait` exits 11). Add `--notify-cmd 'notify-send rauf
"$RAUF_CARD"'` for a desktop ping on exceptions and the end.

**Optional Stop hook.** If the session tries to end its turn while the loop still runs, rauf's
Stop hook blocks the stop and hands it the next `loop wait`; it does nothing for sessions not
supervising a loop. Wire it with explicit consent:

```bash
npx @garygentry/feature-forge install -a codex --codex-stop-hook
```

This adds one Stop entry to `~/.codex/hooks.json` (or `$CODEX_HOME/hooks.json`), keeping any
existing hooks; `--yes` alone never writes it. Hooks also need `[features] hooks = true` in
`~/.codex/config.toml`, and Codex asks you to trust a new hook before running it. To wire it by
hand instead, merge the output of `rauf hook codex-stop --print-config` into that file.
`forge-session.py doctor` reports whether it is wired (`loop-supervision`).
