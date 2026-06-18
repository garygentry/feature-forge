# feature-forge on Codex

> Canonical skills for the feature-forge pipeline, installed onto Codex.
> The skills are spec-pure; Codex's adapter is generated from canon (do not hand-edit
> `adapters/codex/`).

## Install

> **Not yet on npm** — the `npx feature-forge` one-liner isn't available yet (the npm name is
> taken by an unrelated package; tracked in [#9](https://github.com/garygentry/feature-forge/issues/9)).
> Install from a built clone — see the repo [README §(b)](../../README.md#b-any-agent--from-source)
> for the one-time `installer` build.

This copies the generated `adapters/codex/` bundle into Codex's config directory:

```bash
node installer/dist/cli.js install -a codex
```

To see the exact destination on your machine without writing anything, run:

```bash
node installer/dist/cli.js install -a codex --dry-run --json
```

The `--dry-run --json` plan reports the resolved install destination — use that as the
authoritative path. (The install destination is derived from the installer, not asserted here;
see the note below.)

> **Note (install path):** the destination for Codex is taken from the installer's
> `--dry-run --json` plan, not hard-coded in this doc — the cross-agent installer treats the
> codex config-dir convention as best-known but unverified. (Only Claude's `~/.claude`
> destination is treated as well-known.)

> **Known gap (installed-bundle self-location):** an installed `adapters/codex/` bundle does not
> currently carry `epic-manifest.py` / `.claude-plugin/plugin.json`, so the portable resolver
> `scripts/forge-root.sh` cannot self-locate from an installed bundle. This is a known
> limitation owned by the adapter generator; it does not block install/first-use here.

## First-use check

1. List what got installed:
   ```bash
   node installer/dist/cli.js list -a codex          # per-agent installed / up-to-date status
   ```
2. Invoke a forge skill on Codex and confirm it fires. Codex-specific invocation: prompt the
   agent with "use feature-forge to run forge-init for a new feature" — Codex should select the
   installed `forge-init` skill from its adapter catalog.

## Loop runner (forge-5-loop)

See [The default loop runner](claude.md#the-default-loop-runner) — feature-forge defaults to
rauf and selects the coding agent via the documented precedence.
