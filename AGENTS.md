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
