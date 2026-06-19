# AGENTS.md — feature-forge

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

### Tooling — stdlib + pinned YAML, no pnpm/TypeScript gate

The generator is Python 3 (3.10+ baseline) + Bash + Markdown. There is exactly one runtime
dependency beyond the standard library: a pinned YAML library specified in
`scripts/requirements-adapters.txt`. `bash scripts/validate.sh` auto-provisions it into the
gitignored `.venv-adapters` virtual environment on first run; subsequent runs reuse the venv.
There is no `pnpm`, no `npm`, and no TypeScript build step — `bash scripts/validate.sh` is
the single verify command.

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

**Agent guidance — offer, don't act.** When a merged change is user-facing and worth getting to
`npx` users (an installer fix, a new adapter, a CLI behavior change), proactively **suggest** a
publish and spell out the steps (version bump + manual dispatch). Never run `npm publish`
yourself, and don't treat a merge as implying a release — the human decides when to cut one.

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
