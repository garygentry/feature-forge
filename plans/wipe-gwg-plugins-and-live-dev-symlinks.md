# Wipe legacy `agent-plugins` & set up live development for `feature-forge` (+ `rauf`)

## Context

`feature-forge` was extracted from the `garygentry/agent-plugins` monorepo into its own
standalone single-plugin marketplace repo (v0.8.0 → now v0.9.0). But the way it is **installed**
in Claude Code never moved: it is still installed via the legacy `gwg-plugins` marketplace
(sourced from `garygentry/agent-plugins`) as a **cache copy pinned at v0.6.0**. Because
marketplace installs copy the plugin into `~/.claude/plugins/cache/<mkt>/<plugin>/<version>/`
and only refresh when the pinned `version` changes, every edit made in the live source repo
(`/home/gary/workspace/feature-forge`, now v0.9.0) has been **silently ignored** — Claude Code
keeps running the stale 0.6.0 cache. This is the "minor updates are hard to tell if active"
problem in the request.

Two goals:
1. **Wipe** the legacy `agent-plugins` / `gwg-plugins` footprint from this machine's Claude
   Code install (marketplace, both installed plugins, on-disk caches/clone, settings entries).
2. **Replace** the cache-based install with a **live, in-place** development setup so edits to
   the source repos take effect immediately, with no version-bump/refresh dance.

### Decision (confirmed with user)
- **Live-dev mechanism:** skills-directory plugin via symlink (`~/.claude/skills/<name>` →
  source repo). Loads every session, in every project, read **in-place** (no cache, no version
  pinning) as `<name>@skills-dir`. `SKILL.md` edits are live instantly; `/reload-plugins` picks
  up hook/agent/MCP changes. Same `/feature-forge:*` skill namespace as today.
- **rauf companion:** wire up the same way (`~/.claude/skills/rauf` → `/home/gary/workspace/rauf`)
  so the loop-runner skills that `forge-4-backlog`/`forge-5` delegate to are also live. The rauf
  **CLI binary** is a separate concern (installed via curl), out of scope unless missing.
- **diagramming:** fully wipe `gwg-plugins` even though it still lists the (uninstalled)
  `diagramming` plugin. The separate `~/.claude/skills/diagram-generator` skill is unaffected.

### Why this is idiomatic (per current docs, code.claude.com)
- `~/.claude/skills/<name>/.claude-plugin/plugin.json` → auto-loads as `<name>@skills-dir`,
  "discovered in place rather than copied into the plugin cache." Personal scope has no trust
  restrictions, so hooks/agents load fully.
- Precedent already on disk: `~/.claude/skills/find-skills` is a working symlink, confirming
  Claude Code follows symlinked entries in the skills directory.
- Both repos satisfy the requirement: each has `.claude-plugin/plugin.json` with a `name`
  (`feature-forge`, `rauf`) and a `skills/` dir (feature-forge also `agents/` + `hooks/`).
  Neither has internal symlinks, and in-place loading wouldn't skip them anyway.

## Current state (verified on disk)

Legacy footprint to remove (all under user `gary`):
- `~/.claude/settings.json` → `enabledPlugins`: `feature-forge@gwg-plugins`, `ralph-support@gwg-plugins`
- `~/.claude/settings.json` → `extraKnownMarketplaces.gwg-plugins`
- `~/.claude/plugins/known_marketplaces.json` → `gwg-plugins` entry
- `~/.claude/plugins/installed_plugins.json` → `feature-forge@gwg-plugins`, `ralph-support@gwg-plugins`
- `~/.claude/plugins/cache/gwg-plugins/` (stale 0.6.0 + ralph-support 1.0.0 copies)
- `~/.claude/plugins/marketplaces/gwg-plugins/` (git clone of agent-plugins)
- `~/.claude.json` → `enabledPlugins` `feature-forge@gwg-plugins` (and any `ralph-support@gwg-plugins`)
- `/home/gary/workspace/agent-plugins/.claude/settings.local.json` → stale `Bash(... cache/gwg-plugins/feature-forge/0.6.0/scripts/forge-init.sh)` permission + wrong `additionalDirectories: /home/gary/workspace/ralph`

Already clean / keep:
- `feature-forge/.claude/settings.local.json` is already correct (`additionalDirectories: /home/gary/workspace/rauf`).
- claude CLI v2.1.170 at `/home/gary/.local/bin/claude` (supports all `claude plugin …` subcommands).

## Plan

> Run the `claude plugin …` mutations from a **plain terminal** (or via the `!` prefix), not
> relied upon mid-session, and **restart Claude Code** afterward so the wipe + new symlinks are
> picked up cleanly and no live session re-writes `settings.json` on exit.

### Phase 1 — Wipe the legacy `gwg-plugins` / `agent-plugins` footprint
Prefer the idiomatic CLI (it updates all four bookkeeping files and removes the cache/clone):
```bash
claude plugin uninstall feature-forge@gwg-plugins -y
claude plugin uninstall ralph-support@gwg-plugins -y
claude plugin marketplace remove gwg-plugins
```
Then **verify zero residue** and clean anything left by hand:
```bash
grep -rn "gwg-plugins\|agent-plugins" ~/.claude/settings.json ~/.claude.json \
  ~/.claude/plugins/known_marketplaces.json ~/.claude/plugins/installed_plugins.json
ls -d ~/.claude/plugins/cache/gwg-plugins ~/.claude/plugins/marketplaces/gwg-plugins 2>/dev/null
```
- If any key remains: remove the `feature-forge@gwg-plugins` / `ralph-support@gwg-plugins`
  entries from `enabledPlugins` and the `gwg-plugins` block from `extraKnownMarketplaces` in
  `~/.claude/settings.json` and `~/.claude.json`; remove the `gwg-plugins` objects from
  `known_marketplaces.json` / `installed_plugins.json` (Edit tool — JSON, keep commas valid).
- If any dir remains: `rm -rf ~/.claude/plugins/cache/gwg-plugins ~/.claude/plugins/marketplaces/gwg-plugins`.
- Fix the dead-repo settings: in `/home/gary/workspace/agent-plugins/.claude/settings.local.json`
  drop the stale `cache/gwg-plugins/...forge-init.sh` permission and correct/remove the
  `/home/gary/workspace/ralph` directory entry (it should be `rauf`, or just delete it since
  that repo is deprecated).

### Phase 2 — Live development setup (skills-dir symlinks)
```bash
ln -s /home/gary/workspace/feature-forge ~/.claude/skills/feature-forge
ln -s /home/gary/workspace/rauf          ~/.claude/skills/rauf
```
Notes:
- No `enabledPlugins` entry is needed — `@skills-dir` plugins auto-load. (To disable later:
  `claude plugin disable feature-forge@skills-dir`.)
- Sequence matters: do this **after** the gwg-plugins wipe so two plugins named `feature-forge`
  never coexist.
- rauf CLI binary check (separate from skills): `command -v rauf || echo "rauf CLI missing"`.
  If missing and the user wants forge-5 to actually run loops, install per
  `references/forge-config-schema.json` `loopRunner.installHint`
  (`curl -fsSL https://raw.githubusercontent.com/garygentry/rauf/main/scripts/install-binary.sh | bash`).
  Authoring/validation skills work without it; loop execution needs it.

### Phase 3 — Document the workflow
Add a short "Local development" section to `feature-forge/README.md` (and mirror in `rauf` if
desired) capturing the canonical setup so it is reproducible and the staleness trap is recorded:
- Install for live dev: the two `ln -s` commands above.
- Daily loop: edit `SKILL.md` → effect is immediate; edit `hooks/`, `agents/`, `references/`
  consumed by hooks, or `.mcp.json` → run `/reload-plugins` (or restart).
- Verify active version: `claude plugin list | grep feature-forge` should show
  `feature-forge@skills-dir` (never a `@gwg-plugins` cache version again).
- Distribution unchanged: end users still `/plugin marketplace add garygentry/feature-forge`
  + `/plugin install feature-forge@feature-forge` (omit/bump `version` appropriately for releases).

## Critical files
- `~/.claude/settings.json`, `~/.claude.json` — remove legacy `enabledPlugins` / `extraKnownMarketplaces` entries.
- `~/.claude/plugins/known_marketplaces.json`, `~/.claude/plugins/installed_plugins.json` — remove `gwg-plugins` records.
- `~/.claude/plugins/cache/gwg-plugins/`, `~/.claude/plugins/marketplaces/gwg-plugins/` — delete.
- `~/.claude/skills/feature-forge`, `~/.claude/skills/rauf` — new symlinks (the core change).
- `/home/gary/workspace/agent-plugins/.claude/settings.local.json` — drop stale permission / `ralph` dir.
- `/home/gary/workspace/feature-forge/README.md` — add "Local development" section.

## Verification (end-to-end)
1. **Legacy gone:** `grep -rn "gwg-plugins" ~/.claude/settings.json ~/.claude.json ~/.claude/plugins/*.json`
   returns nothing; `ls ~/.claude/plugins/{cache,marketplaces}/gwg-plugins` → not found;
   `claude plugin marketplace list` does not list `gwg-plugins`.
2. **Live plugins loaded:** restart Claude Code, then `claude plugin list` shows
   `feature-forge@skills-dir` and `rauf@skills-dir` (enabled). `/help` lists `/feature-forge:*`
   skills under the namespace.
3. **Edits are live:** make a trivial visible edit to a `feature-forge` `SKILL.md` (e.g. the
   `forge` navigator) and confirm the change appears the same session (skills) / after
   `/reload-plugins` (hooks/agents) — no version bump, no cache.
4. **Functional smoke:** run `/feature-forge:forge` (status navigator) in a project; confirm it
   resolves config and references files in-place from the source repo. If rauf CLI is installed,
   `rauf version --json` succeeds so `forge-4`/`forge-5` delegation/version-gate works.
