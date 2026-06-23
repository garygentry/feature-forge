# Changelog

All notable changes to feature-forge are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Reliable, state-aware branch setup at pipeline entry.** The new-feature /
  epic branch prompt was previously gated on `gitCommitAfterStage`, soft, and
  blind to the current branch — so features often started on the default branch.
  A centralized **Branch Setup** block (`shared-conventions.md`, invoked by
  `forge-1-prd` and `forge-0-epic`) now gates on a new `branchPerFeature` config
  (default `true`, independent of `gitCommitAfterStage`), detects the current vs.
  default branch, and **strongly recommends (still declinable)** creating
  `{branchPrefix}{label}` (default prefix `forge/`) when on the default branch;
  it skips silently on a topic branch, and epic members inherit the epic branch.
  The chosen branch is recorded in `.pipeline-state.json` (`branch` field), and
  `forge-5-loop` re-checks it in a pre-flight guard before the loop commits
  per item. New config: `branchPerFeature`, `branchPrefix`.

### Fixed

- **`npx @garygentry/feature-forge` / `npm i -g` silently did nothing on
  Linux/macOS (installer `0.1.4`).** Two compounding bugs in the published bin:
  (1) `dist/cli.js` shipped without a `#!/usr/bin/env node` shebang (ENOEXEC →
  `/bin/sh` fallback → JS syntax error); and (2) the process-entry shim compared
  `import.meta.url` to `process.argv[1]` **without resolving symlinks** — but
  npm/npx install the bin as a symlink, so the comparison never matched and
  `main()` never ran (silent exit 0, no output). Added the shebang and made the
  entry shim resolve the symlink (`realpathSync`) before comparing. Both are
  guarded by new tests (shebang presence + spawn-through-a-symlink). Masked
  until now because CI and the test suite invoke `node dist/cli.js` / `main()`
  directly — never the real symlinked bin — and npm's Windows `.cmd` shims call
  `node` explicitly. (`0.1.3` shipped only the shebang half of this fix.)

### Added

- **Cross-agent installer published to npm** as `@garygentry/feature-forge`
  (independent version line; `0.1.1` adds a package README and validates the
  OIDC trusted-publishing CI path). The one-liner is now
  `npx @garygentry/feature-forge install` — the bare `feature-forge` name on npm
  belongs to an unrelated package. The package now bundles the generated
  `adapters/` at pack time (`prepack`), so it resolves agent bundles when
  installed from npm; Python build artifacts are filtered out. A manual
  `npm-publish.yml` (`workflow_dispatch`) workflow was added.

### Changed

- **rauf pin advanced to `@garygentry/rauf@0.8.0` (installer `0.1.5`).** rauf
  released 0.8.0 (provider-neutral backlogs + `rauf loop run --no-model`), so
  `RAUF_PIN` advances `0.7.0 → 0.8.0` — the version a fresh install provisions as
  the default loop runner. Canonical `installHint`, regenerated adapters, and
  `COMPATIBILITY.md` updated to the new coordinate. `minRunnerVersion` stays
  `0.6.0` (the agent-surface floor — 0.8.0's `--no-model` doesn't raise it). rauf
  and feature-forge remain independently versioned; the pin is the only coupling.
- **Install docs** (README + `docs/agents/*.md`) restored to the scoped
  `npx @garygentry/feature-forge` one-liner (they had been pointed at a
  from-source path while the package was unpublished).
- **rauf pin reconciled (installer `0.1.2`).** rauf is now published to npm
  (rauf#28), so `RAUF_PIN` advances from the unpublished `rauf@0.6.0` to the
  scoped, published `@garygentry/rauf@0.7.0` (the bare `rauf` name is blocked by
  npm's similarity filter). The install-time resolvability preflight now passes
  by default — the `--skip-rauf` flag remains as an opt-out (e.g. offline
  installs) rather than a workaround for an unpublished pin. The
  `installHint` schema default + regenerated adapters and install docs were
  updated to the scoped coordinate. (`minRunnerVersion` stays `0.6.0` — that is
  the rauf *binary* agent-surface floor, distinct from the npm pin.)

## [0.10.0] — 2026-06-13

### Added

- **CI gates (GitHub Actions, net-new).** `ci.yml` (per-PR blocking deterministic
  gate via the `quality-gate` composite action), `os-matrix.yml` (installer
  `--dry-run` + `uninstall` on Ubuntu/macOS/Windows), and `eval.yml` (advisory
  trigger-accuracy, `workflow_dispatch` + weekly schedule, non-blocking).
- **SKILL.md frontmatter JSON Schema** (`references/skill-frontmatter.schema.json`)
  as the single source of truth for the spec-pure key set; `check-spec-purity.py`
  now loads its allowed/required keys from it.
- **Shell + Python lint gates** — `shellcheck` over `scripts/*.sh` (`.shellcheckrc`)
  and `ruff` over `scripts/*.py` + `eval/*.py` (`ruff.toml`).
- **Trigger-accuracy eval harness** (`eval/run-eval.py` + `eval/fixtures/<skill>.json`).
- **Per-agent setup docs** (`docs/agents/{claude,codex,copilot,cursor,gemini}.md`).
- **MIT `LICENSE`** (previously none).
- **`.gitattributes`** — LF normalization (`* text=auto eol=lf`) + `export-ignore`
  for dev-only trees.

### Changed

- **README rewritten install-first** — Claude marketplace install, universal
  `npx feature-forge install` one-liner, and a per-surface agent table.
- **Version fields reconciled to `0.10.0`** — `marketplace.json` `0.9.0` → `0.10.0`
  (hand-edit) and `adapters/gemini/gemini-extension.json` `0.0.0` → `0.10.0`
  (via the `GEMINI_EXTENSION_VERSION` generator constant). `plugin.json` was
  already `0.10.0`. `installer/package.json` keeps its independent line.
- **Requires rauf ≥ 0.6.0.** Bumped `loopRunner.minRunnerVersion` default
  `0.2.0` → `0.6.0`. 0.6.0 is the floor that ships the **agent-selection
  surface** (`--agent` / `rauf agents`) this release's `loopRunner`
  (`agentArgument` / `agentsProbeCommand`) consumes. It builds on rauf's
  **v0.5.0 grammar + contract flip** — unified exit codes across `status` /
  `loop run`, `loop run --detached` replacing `loop start`, an explicit `review`
  signal, and versioned `events.ndjson` — which 0.6.0 includes. feature-forge
  reads both the unified exit-code / status surface and the agent-selection
  surface, so `forge-5-loop` now gates on 0.6.0 (`rauf version --json`,
  semver-compared) before running.
- **Updated `loopRunner` command defaults to the v0.5.0 rauf surface:**
  `followCommand` `{bin} loop follow …` → `{bin} follow …` (`loop follow` was
  promoted to the top-level `follow` verb in rauf's Phase-1 monitor clean-break),
  and `watchCommand` `{bin} loop watch … --json` → `{bin} status … --json` (the
  `loop watch` verb was removed; stall telemetry — `stuckWarning` — is now read
  from `status --json` / `iteration-status.json`). A project that pins these
  commands in its own `forge.config.json` should update them likewise.

### Requires

- **rauf ≥ 0.6.0.** See `COMPATIBILITY.md`.

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
