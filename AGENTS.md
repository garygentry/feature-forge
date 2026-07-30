# AGENTS.md — feature-forge

> **Which task are you here for?**
> This file is for agents **contributing to the feature-forge repository itself** — building the
> adapters, running the checks, opening PRs against this repo.
> If you were asked to **install or use feature-forge in another project** (the user pasted this
> repo's URL, or said "set up feature-forge for me"), **stop reading this file** and follow
> [`AGENTS-SETUP.md`](AGENTS-SETUP.md) instead — it is the deterministic install-and-start
> procedure. Nothing below applies to that task.

feature-forge is a vendor-neutral, spec-pure skill canon that builds per-agent adapters
deterministically. This file is the cross-agent entry point: it tells any AI coding agent
(Claude, Codex, Copilot, Cursor, Gemini, or a future target) how to build, test, and
contribute to this repository.

## Build & Test

| Command | Purpose |
|---------|---------|
| `bash scripts/validate.sh` | **Single verify gate** — runs all checks (spec-purity, drift guard, tests). This is the only command you need before committing. |
| `python3 scripts/build-adapters.py` | Regenerate all per-agent adapter bundles under `adapters/`. Run this whenever you edit canon (`skills/`, `agents/`, `references/`). |
| `python3 scripts/build-adapters.py --check` | Check that `adapters/` matches a fresh generation without writing anything. Exits 0 if in sync, 1 if there is drift. |
| `python3 scripts/check-spec-purity.py` | Check that the canonical surfaces (`skills/`, `agents/`, `references/`) are free of vendor-specific frontmatter. |

`bash scripts/validate.sh` auto-provisions the pinned YAML dependency into `.venv-adapters`
the first time it runs — no manual setup is needed.

## Branching & merging

Every change reaches `main` **via a pull request** with green CI (`ci.yml` /
`os-matrix.yml`, which run `bash scripts/validate.sh`) — never a direct push to `main`:

1. Branch from an up-to-date `main`.
2. Make the change; run `bash scripts/validate.sh` locally until green (regenerate adapters if
   you touched canon — the drift guard blocks an out-of-date `adapters/` tree).
3. Push the branch, open a PR, let CI go green, then merge.

This mirrors the sibling **rauf** repo's process. The shared release principles across both
repos: (1) a merge to `main` **never publishes**; (2) publishing is **manual, owner-gated**
`workflow_dispatch`; (3) **bump the version before publishing** (npm rejects republishing a
version); (4) **offer, don't act** — suggest a release, never cut one yourself. rauf and
feature-forge are versioned **independently** (no lockstep); the only coupling is the
`RAUF_PIN` provisioned-default coordinate plus `COMPATIBILITY.md`.

## Repository Conventions

### Spec-pure canon

`skills/`, `agents/`, and `references/` are the **single source of truth** for all skill and
agent definitions. These directories are spec-pure: they carry only vendor-neutral frontmatter
fields. Per-agent output is **generated** into `adapters/` by `scripts/build-adapters.py` and
**never hand-edited**. If you need to change what an adapter emits, edit the canonical source
and regenerate.

### Hand-written adapter sources

Most of what lands in `adapters/` is generated from canon prose. The exception is real code
that a target agent loads at runtime — today Pi's `AskUserQuestion` TUI extension. Those
artifacts live under `adapter-src/<agent>/` and are read by `scripts/build-adapters.py` at
build time, which prepends the `GENERATED — DO NOT EDIT` header naming the `adapter-src` path.
Edit the file under `adapter-src/`, never the emitted copy, then regenerate.

**Source layout mirrors emitted layout.** `adapter-src/pi/extensions/…` becomes
`adapters/pi/extensions/…` at the same relative path. That is a correctness requirement, not
tidiness: the Pi extension resolves its own bundle root by walking up from `import.meta.url`,
so a source tree at a different depth would typecheck and test green in-tree while resolving
the wrong root once emitted.

**Not all of it is ours.** `adapter-src/pi/extensions/ask-user-question/` is a *vendored*
snapshot of the third-party `@juicesharp/rpiv-ask-user-question` package, carried with a
four-patch delta. Read `adapter-src/pi/UPSTREAM.md` before touching anything in that tree —
reformatting or refactoring it is friction at the next upstream refresh, and every local edit
has to be re-applied by hand. Files that cannot carry a line-comment header (`LICENSE`,
`locales/*.json`) are emitted verbatim; the regen-and-diff drift guard is what protects them.

**The Pi agent output follows a third-party schema, in two places.** `adapters/pi/package.json`
carries a top-level `pi-subagents` block declaring the bundle's `agents/` directory, and each
`adapters/pi/agents/<name>.md` carries frontmatter (`tools`, `turnBudget`, `thinking`, `memory`,
`skills`, `acceptanceRole`, `completionGuard`, `inheritProjectContext`) in the shape
[`pi-subagents`](https://github.com/nicobailon/pi-subagents) 0.35.1 expects. Pi core reads none of
it; the extension does, and that schema is not ours. The manifest key is kept out of the core-Pi
`pi` block precisely so the coupling stays visible, and it is emitted unconditionally because an
unread key is inert — the bundle must never require an extension it does not ship. Unknown keys are
tolerated by that loader, so schema drift degrades rather than breaks. **Two frontmatter shapes bite
silently, so they are verified against pi-subagents' real loader, not its README** (see the mapping
notes above `PiEmitter` in `scripts/build-adapters.py`): `turnBudget` is `JSON.parse`d and must be a
single-line JSON string, and Pi's line parser drops block-sequence `tools`/`skills`, so both are
emitted comma-joined. See `docs/agents/pi.md` for the user-facing behaviour and the full mapping.

The npm installer adds a **second** coupling to the same extension: the manifest key is only read
where the bundle sits in Pi's `packages` list, which the `-a pi` install (under `skills/`) is not.
So the Pi target carries a `mirror` placement copying `agents/*.md` into the directories
`pi-subagents` scans directly — `~/.pi/agent/agents/` (user scope) and `.pi/agents/` (project
scope). Those paths are a behavioural contract, not a schema, and were confirmed read-only against
pi-subagents 0.35.1's `discoverAgents` source rather than its README. If a future version renames
those scan dirs the mirror lands in the wrong place silently, so re-confirm them on an upgrade.

Each agent directory owns its own toolchain and opts into verification by exposing a `verify`
script in its `package.json`; `scripts/validate.sh` iterates `adapter-src/*/` and runs each one.
A directory with no `verify` script is reported as a visible `SKIP` — shipping unverified code
is allowed, but never silently. Pi's `verify` is `tsc --noEmit` over the whole tree plus
`node --test`, which drives the real extension through a fake `ExtensionAPI` and a headless
TUI — registration, the questionnaire state machine, the RPC fallback, and the validation
guards — so an upstream refresh that breaks a feature-forge contract fails before it ships.
Anything here is dev-only: `adapter-src/*/node_modules/` is gitignored and nothing from it is
published.

### Tooling — Python stdlib + pinned YAML; npm confined to two dirs

The generator is Python 3 (3.10+ baseline) + Bash + Markdown. There is exactly one runtime
dependency beyond the standard library: a pinned YAML library specified in
`scripts/requirements-adapters.txt`. `bash scripts/validate.sh` auto-provisions it into the
gitignored `.venv-adapters` virtual environment on first run; subsequent runs reuse the venv.
There is no `pnpm`.

Node/npm and TypeScript are confined to exactly two places, both gated by `validate.sh` and
neither part of the generator itself: `installer/` (the published CLI, built with `tsc` and
tested with `node --test`) and `adapter-src/<agent>/` (hand-written adapter sources, each
verified by its own toolchain). `bash scripts/validate.sh` remains the single verify command.

### The resolver/prelude pattern

`scripts/forge-root.sh` is the portable plugin-root resolver. It is copied **byte-identical**
into each adapter bundle (under `adapters/<agent>/scripts/forge-root.sh`) during generation.
The canonical bootstrap prelude is byte-identical everywhere it appears; the build step asserts
this with a SHA-256 comparison and fails loudly on any divergence.

### Generated-output provenance

Every file under `adapters/` that contains frontmatter carries a `GENERATED — DO NOT EDIT`
header naming its canonical source file and the command to regenerate it
(`python3 scripts/build-adapters.py`). If you see that header, do not edit the file directly —
edit the canonical source and regenerate.

## Installation

**Preferred — Claude Code marketplace / plugin install.** Installing via the Claude Code
marketplace or plugin path is the first-class, canonical install method. It gives you the
skills and agents as a managed plugin with automatic updates.

**Fallback — universal cross-agent install path.** For agents other than Claude Code, the
cross-agent installer (a separate tool, `cross-agent-installer`) copies the relevant
`adapters/<agent>/` bundle into the agent's config directory. Refer to that installer's
documentation for mechanics; this file does not duplicate them.

## Publishing to npm

The installer is published to npm as `@garygentry/feature-forge` — this is what backs
`npx @garygentry/feature-forge` and `npm i -g @garygentry/feature-forge`. Publishing is
**manual and deliberate; a merge to `main` never publishes**:

- A merge runs CI (`ci.yml`, `os-matrix.yml`) but **no publish step**. The only workflow that
  runs `npm publish` is `.github/workflows/npm-publish.yml`, whose **sole trigger is
  `workflow_dispatch`** (Actions → "npm Publish (manual)" → Run workflow).
- **Bump the version first.** Re-publishing the current `installer/package.json` `version` is
  rejected by npm (409). So a publish is always: bump `installer/package.json` `version` →
  merge → dispatch the publish workflow. The workflow's `prepack` builds `dist/` and bundles
  `adapters/` automatically.
- It uses npm Trusted Publishing (OIDC) — no token — and must be dispatched by the repository
  owner.

### Does this change impact the published build?

The npm package bundles `dist/` (built from `installer/src/`) **and** the generated `adapters/`
tree. So a change reaches `npx` users — and is **publish-worthy** — when it touches any of:

- `installer/` source, CLI behavior, `package.json`, or `prepack`/bundling;
- **canon** (`skills/`, `agents/`, `references/`) — because regenerating `adapters/` changes what
  the package ships (this is the easy one to miss: a docs-only edit to a SKILL.md still ships);
- `RAUF_PIN` / the provisioned rauf coordinate;
- anything else that lands in the npm tarball (`cd installer && npm pack --dry-run` to see it).

Pure-repo changes that **don't** ship (CI config, `scripts/` dev tooling, `AGENTS.md`/docs not
under canon, tests) are not publish-worthy on their own.

### Agent guidance — prompt after merge, then offer to run the runbook

When a **publish-worthy** change (per above) is merged to `main`, **proactively prompt the user**:
note that the change is now on `main` but not yet on npm, and ask whether they want to publish.
Do **not** publish unprompted and do **not** treat a merge as implying a release — but once the
user approves, **offer to run the full runbook below on their behalf** rather than just handing
them steps. Publishing is owner-gated, but with explicit user approval you may bump, dispatch the
workflow, and verify.

### Publish runbook

1. **Decide the version.** Compare `installer/package.json` `version` against npm
   (`npm view @garygentry/feature-forge version`). If local is **already ahead** and unpublished
   (a prior change bumped it), reuse it — **do not double-bump**. Otherwise bump
   `installer/package.json` `version` (independent line; npm rejects republishing a version, 409).
   This repo **does not git-tag releases** — don't create a tag.
2. **CHANGELOG.** Ensure the change is recorded under `## [Unreleased]` in `CHANGELOG.md` (the
   installer is an independent version line, so no dated heading rename is required for an
   installer-only publish).
3. **Regenerate + verify** if canon changed: `python3 scripts/build-adapters.py` then
   `bash scripts/validate.sh` (green). Any version bump / changelog edit goes through a PR with
   green CI — never a direct push to `main`.
4. **Pre-flight the package locally** to catch build/bundle failures before spending a CI run:
   `cd installer && npm ci && npm run prepack && npm pack --dry-run`. Confirm the new version and
   that `adapters/` carries your change (`grep -rl <marker> adapters/`). **Clean up afterward:**
   `prepack` copies the repo `adapters/` tree into `installer/adapters/` (gitignored, so it never
   commits) — but if left in place it pollutes the test glob and makes `bash scripts/validate.sh`
   report **false failures** (e.g. template `smoke.test.ts` files failing with
   `Cannot find package 'vitest'`). Remove it before re-validating: `rm -rf installer/adapters`.
   CI never hits this (fresh checkout), so a failure that disappears after that `rm` is the
   leftover copy, not your change.
5. **Dispatch the publish workflow** (only after the version bump is on `main`):
   `gh workflow run npm-publish.yml -f dist-tag=latest`, then watch it:
   `gh run watch <run-id> --exit-status`. It uses npm Trusted Publishing (OIDC) — no token.
6. **Verify it's live:** `npm view @garygentry/feature-forge version dist-tags` shows the new
   version under `latest`.

**Human prerequisites:** the npm **Trusted Publisher (OIDC)** must be configured on the package
(one-time, already done — every prior release used it). The publish must be **dispatched by / on
behalf of the repository owner**; there is no npm login or token for the agent to manage.

### On a new rauf release — advance the pin

`installer/src/rauf.ts` `RAUF_PIN` pins the rauf coordinate a fresh install provisions as the
default loop runner. When rauf publishes a new compatible release, advance it (PR like any
change):

1. Set `RAUF_PIN` to the new `@garygentry/rauf@X.Y.Z` (update the prose pin in
   `references/forge-config-schema.json`'s `installHint` and the installer doc-comments/README
   too — `grep -rn "@garygentry/rauf@" references installer/src installer/README.md`).
2. Update the installer's tests that assert the pin (`installer/test/*.ts`).
3. Regenerate adapters (`python3 scripts/build-adapters.py`) so the schema `installHint`
   propagates; the drift guard fails otherwise.
4. Bump `installer/package.json` `version` (independent line) and add a `CHANGELOG.md` note.
5. Update `COMPATIBILITY.md` (the pin coordinate; `minRunnerVersion` only changes if rauf
   raised the agent-surface floor).

The pin is a **dependency** advance, not version coupling — rauf and feature-forge version
independently.

## Dependency Upgrades

Upgrading the pinned YAML library version in `scripts/requirements-adapters.txt` is a
**behavior change**, not a routine version bump. The YAML library controls how frontmatter
is serialized in every generated file. After changing the pin:

1. Regenerate all adapters: `python3 scripts/build-adapters.py`
2. Review the diff against the previously committed `adapters/` tree.
3. Commit the regenerated tree together with the version bump.

The drift guard (`python3 scripts/build-adapters.py --check`, wired into
`bash scripts/validate.sh`) will fail the gate if the committed `adapters/` tree does not
match a fresh generation — so a version bump without regeneration will block CI.
