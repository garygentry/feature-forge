# Changelog

All notable changes to feature-forge are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- **rauf pin advanced to `@garygentry/rauf@0.10.0`.** rauf shipped 0.9.0 (Effort B2)
  and 0.10.0 (Codex packaging + a dedicated, telemetry-capable `CodexCliProvider` that
  fixes the broken codex loop — `--ask-for-approval` is a top-level flag current Codex
  rejects after `exec`), so `RAUF_PIN` advances `0.8.1 → 0.10.0` (superseding the
  still-unreleased 0.8.1 bump) — the version a fresh install provisions as the default
  loop runner. Canonical `installHint` (`references/forge-config-schema.json`),
  regenerated adapters, `COMPATIBILITY.md`, installer docs, and the installer pin tests
  updated. `minRunnerVersion` stays `0.6.0` (no compatibility floor change across B2/C);
  rauf and feature-forge remain independently versioned. The install-time check is a
  read-only `npm view` resolvability probe — existing installs are unaffected.

## [0.11.0] — 2026-06-26

This release completes the agent-agnostic remediation: a non-Claude user can now
install **and run** the full feature-forge workflow, with each agent's bundle placed
where that agent actually loads it, while Claude stays the rich, byte-identical default
path. Generated bundles are self-contained; the installer is per-agent honest about
install confidence; and the local gate now matches CI.

### Added

- **Installer second-root placements (manifest v2).** The cross-agent installer now
  writes the two per-agent placements that the single-`destination` model could not
  express: Codex custom agents are mirrored flat into `.codex/agents/*.toml` (where
  Codex loads them) alongside the primary `.agents/skills/feature-forge` bundle, and
  Copilot — which has no skills loader — gets a sentinel-delimited managed block in
  `.github/copilot-instructions.md` pointing at the staged `.github/feature-forge`
  bundle. The managed block is merged idempotently, preserving any existing user
  content; `update` leaves a user-edited block alone unless `--force`, and `uninstall`
  strips only the block (removing the file only if nothing else remains). The install
  manifest is bumped to `schemaVersion: 2` with an additive `placements[]` array; v1
  manifests (no placements) are still read and reconciled on the next update.

- **Host-specific instruction translation for non-Claude targets.** The adapter
  generator now applies a deterministic per-target body transform to NON-Claude skill
  and agent bodies: it strips Claude-only tooling idioms (`AskUserQuestion`, the
  `Agent`/`Task tool` dispatch, `subagent_type=`, `run_in_background`, `` `Monitor` ``)
  and appends a per-target "Host execution notes" overlay (Codex-native for codex,
  neutral elsewhere) so the workflow reads correctly on each host. The Claude emitter is
  unchanged — it emits canon **byte-identical** — the strongest "never disrupt Claude"
  guarantee.

- **Self-contained adapter bundles for true cross-agent installs.** Every
  generated per-agent bundle now ships the neutral `.feature-forge-bundle.json`
  sentinel plus byte-identical copies of every runtime helper a skill can invoke
  (`forge-root.sh`, `forge-init.sh`, `epic-manifest.py`,
  `validate-traceability.py`, `forge-bootstrap.py`). The portable root resolver
  (`scripts/forge-root.sh`) now self-locates on the neutral sentinel (not the
  Claude-only `.claude-plugin/plugin.json`), probes the agent-neutral
  `.agents/skills/feature-forge` roots (project + `$HOME`) alongside the Claude
  paths, and honors a neutral `FEATURE_FORGE_ROOT` override (keeping
  `CLAUDE_PLUGIN_ROOT` as a backwards-compatible Claude fallback). The bootstrap
  prelude was widened to discover the resolver under non-Claude install roots, so
  helper-backed skills run after a `--agent codex` (etc.) install — previously
  the first helper-backed skill could fail even after a successful install. The
  installer's bundle-integrity check now requires these files on every agent.

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

- **Cross-agent installer published to npm** as `@garygentry/feature-forge`
  (independent version line; `0.1.1` adds a package README and validates the
  OIDC trusted-publishing CI path). The one-liner is now
  `npx @garygentry/feature-forge install` — the bare `feature-forge` name on npm
  belongs to an unrelated package. The package now bundles the generated
  `adapters/` at pack time (`prepack`), so it resolves agent bundles when
  installed from npm; Python build artifacts are filtered out. A manual
  `npm-publish.yml` (`workflow_dispatch`) workflow was added.

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

### Changed

- **Codex adapter uses current Codex skill/agent shapes.** Codex skills are now
  emitted as `skills/<name>/SKILL.md` (the documented Codex skill directory shape)
  instead of `skills/<name>/<name>.md`, and Codex subagents are emitted as
  standalone `agents/<name>.toml` custom-agent files
  (`name`/`description`/`developer_instructions`) — the current Codex custom-agent
  format — replacing the aggregate `agents/openai.yaml` that Codex does not load.
  Claude-only structural keys (tools/model/maxTurns/effort/memory/skills) are
  drop-recorded in `GENERATION-REPORT.md`, so no Claude model aliases leak into
  Codex config. The Claude adapter is unchanged.

- **Installer per-agent install strategy + honest confidence.** The installer's
  per-agent table now splits detection from placement: `configDirName` (the
  detection probe) is decoupled from `installBaseDir`/`installSubpath` (the install
  location AND the containment root), so each agent installs where it actually loads
  content — codex under `.agents/skills/feature-forge`, copilot under
  `.github/feature-forge`, cursor/gemini unchanged. A widened confidence vocabulary
  (`confirmed`/`verified-current`/`best-known`/`unsupported`, with an optional
  project-scope override) plus a per-target docs URL are surfaced in the run report,
  so users see honestly when an install path is best-known rather than vendor-confirmed.

- **Neutral stack-decisions resolution path.** Project stack overrides now resolve
  `.feature-forge/stack-decisions.md` → `.agents/references/stack-decisions.md` →
  `.claude/references/stack-decisions.md` (legacy alias) → `references/stacks/{stack}.md`
  → `_generic.md`, so non-Claude users get a neutral, documented override location
  while existing Claude paths keep working.

- **Local gate parity + portable root-probe coverage.** `scripts/validate.sh` now
  runs `ruff check scripts/ [eval/]` (hard-fail when ruff is present, warn when
  absent) so the local gate matches CI's Quality Gate. The portable resolver
  `scripts/forge-root.sh` now probes every supported agent's install destination
  under both global and project scope (adding cursor `.cursor/rules`, copilot
  `.github/feature-forge`, and project-scope `.claude`/`.gemini`), closing a
  first-use gap where a helper invoked from a project root could not locate a
  cursor/copilot install.

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
