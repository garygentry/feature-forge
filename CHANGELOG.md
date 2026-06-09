# Changelog

All notable changes to feature-forge are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.9.0] — 2026-06-09

### Changed

- **The loop runner is now config-driven, not hardcoded.** Added a `loopRunner`
  block to `forge.config.json` (`references/forge-config-schema.json`) with
  templated commands (`{bin}`/`{backlogDir}`/`{specsDir}`/`{iterations}`),
  defaulting to rauf. Every previously hardcoded `rauf …` string in the skills
  now renders from `loopRunner`, so a different ralph-style runner conforming to
  rauf's `SPEC-BACKLOG-TOOL-CONTRACT.md` can be swapped in without editing a
  skill. See `references/ralph-loop-contract.md`.
- **`forge-5-rauf-loop` → `forge-5-loop`** (config-driven). Renders all commands
  from `loopRunner`; enforces `minRunnerVersion` (default rauf **0.2.0**) via
  `rauf version --json` (semver-compared) before running, stopping with the
  CLI-install hint if the runner is missing/too old. The pipeline-state stage key
  and `currentStage` enum migrated to `forge-5-loop`.
- **`forge-4-backlog` is now a thin orchestrator.** It delegates backlog
  *authoring* to the rauf plugin's `author-backlog` skill (single home for the
  granularity / acceptance-criteria / `agentDelegation` craft) and *validation*
  to the runner's `validate` verb — keeping only pipeline concerns (plan review,
  state, commit). Degrades gracefully when the runner isn't installed yet
  (authors, then skips validation with a warning), since it runs before forge-5's
  setup gate.
- Renamed config key `raufIterationMultiplier` → `loopIterationMultiplier`.

### Removed

- `scripts/validate-backlog.py` — the broken Python validator (it exited 0 with
  only a warning on rauf-invalid backlogs). Validation now routes through
  `rauf backlog validate` (exit 0/1/2). `forge-verify` uses the same command.
- `skills/forge-4-backlog/references/backlog-schema.json` and
  `backlog-examples.md` — the schema is owned by rauf (installed copy / `$id`),
  and the examples were migrated into rauf's `author-backlog` skill.

### Requires

- **rauf ≥ 0.2.0** (first release shipping `backlog validate` + backlog
  `schemaVersion`). See `COMPATIBILITY.md`.

## [0.8.0] — 2026-06-09

### Changed

- **Extracted to its own repository.** feature-forge now lives at
  [`garygentry/feature-forge`](https://github.com/garygentry/feature-forge)
  instead of inside the `garygentry/agent-plugins` monorepo. Full commit
  history was preserved via `git subtree split`.
- The repository root **is** the plugin: it carries both the marketplace
  catalog (`.claude-plugin/marketplace.json`, registered with `"source": "."`)
  and the plugin manifest (`.claude-plugin/plugin.json`).
- Added a self-contained `scripts/validate.sh` that validates the flattened
  single-plugin layout (the monorepo previously supplied a marketplace-wide
  validator).

### Install

```
/plugin marketplace add garygentry/feature-forge
/plugin install feature-forge@feature-forge
```

The previous `feature-forge@gwg-plugins` entry in `agent-plugins` remains as a
deprecated stub for one release cycle so existing installs keep working.

### Notes

- This release is a **pure structural move** — no skill behavior changed. The
  pipeline still invokes the `rauf` CLI exactly as in 0.7.0. Config-driven
  loop-runner indirection and delegation to rauf's backlog contract land in a
  later release (tracked in `COMPATIBILITY.md`).

## [0.7.0] and earlier

See git history (`git log`) for changes prior to the repository extraction,
including the `ralph` → `rauf` rename and the stack-agnostic profile system.
