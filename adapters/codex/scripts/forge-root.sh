#!/usr/bin/env bash
# scripts/forge-root.sh — the portable skill/plugin-root resolver
# (exposed contract: portable-skill-root-resolver; REQ-RES-01..05, REQ-SEC-01).
#
# Prints the absolute feature-forge plugin root to stdout and exits 0, or writes an
# actionable error to stderr and exits 1. Takes no arguments. Idempotent and
# side-effect-free: it NEVER sources or executes a discovered path — it only prints a
# directory (REQ-SEC-01). Resolution is bounded to the candidate roots below plus this
# script's own on-disk location.
#
# This file is copied VERBATIM into per-agent script mirrors by the downstream adapter
# generator (REQ-RES-05); keep it dependency-free beyond POSIX/Bash + the sentinel files.
set -euo pipefail

# Sentinel predicate (00-core-definitions.md §2 / SENTINEL_FILES). A directory is a valid
# feature-forge root iff it carries the neutral bundle sentinel `.feature-forge-bundle.json`
# (emitted into EVERY per-agent adapter bundle) OR the legacy Claude plugin manifest
# `.claude-plugin/plugin.json` (the canon repo root + the Claude bundle). Content-based, so it
# identifies a feature-forge install under ANY agent's directory layout — not just Claude's.
is_root() {  # $1 = candidate dir
  [ -f "$1/.feature-forge-bundle.json" ] || [ -f "$1/.claude-plugin/plugin.json" ]
}

# ── Step 1: self-location — parent of this script's dir is the install root. ─────────────
# This is the PRIMARY path: a bundle ships its own scripts/forge-root.sh, so the parent of
# this script's dir is that bundle's root under any agent's layout.
self_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
root="$(cd -- "$self_dir/.." && pwd -P)"
if is_root "$root"; then
  printf '%s\n' "$root"
  exit 0
fi

# ── Step 2a: Claude marketplace-cache installs — ~/.claude/plugins/cache/<mp>/<plugin>/<ver>/.
# This is where Claude Code actually installs marketplace plugins (three segments below
# plugins/, so the single-star plugins/*/feature-forge glob below can never match it). Version
# dirs can coexist after upgrades, so probe newest plugin.json first — a stale version must
# never shadow the current install. Deliberately ordered BEFORE the plugins/* glob: that glob
# can match the marketplace *clone* (~/.claude/plugins/marketplaces/<mp>/ when the marketplace
# repo root is itself a plugin root), which may sit at a different commit than the installed
# skills — the versioned cache install must always win to prevent that version skew.
while IFS= read -r manifest; do
  candidate="${manifest%/.claude-plugin/plugin.json}"
  if is_root "$candidate"; then
    printf '%s\n' "$candidate"
    exit 0
  fi
done < <(ls -t "$HOME"/.claude/plugins/cache/*/feature-forge/*/.claude-plugin/plugin.json 2>/dev/null || true)

# ── Step 2: candidate-root probe (authoritative multi-agent root list; extend here first). ─
# Globs that match nothing expand to themselves; the is_root test rejects such literals. Covers
# every supported agent's install destination under BOTH global ($HOME) and project ($PWD) scope,
# matching the installer's per-agent layout: claude .claude/skills, codex .agents/skills, copilot
# .github/feature-forge, cursor .cursor/rules, gemini .gemini/extensions. The cache glob repeats
# step 2a's path for a cache install that carries only the neutral bundle sentinel (no
# plugin.json for ls -t to key on).
for candidate in \
  "$HOME/.claude/skills/feature-forge" \
  "$PWD/.claude/skills/feature-forge" \
  "$HOME"/.claude/plugins/cache/*/feature-forge/* \
  "$HOME"/.claude/plugins/*/feature-forge \
  "$HOME/.agents/skills/feature-forge" \
  "$PWD/.agents/skills/feature-forge" \
  "$HOME/.github/feature-forge" \
  "$PWD/.github/feature-forge" \
  "$HOME/.cursor/rules/feature-forge" \
  "$PWD/.cursor/rules/feature-forge" \
  "$HOME/.gemini/extensions/feature-forge" \
  "$PWD/.gemini/extensions/feature-forge" \
; do
  if is_root "$candidate"; then
    printf '%s\n' "$candidate"
    exit 0
  fi
done

# ── Step 3: env fallback — neutral FEATURE_FORGE_ROOT, then the legacy CLAUDE_PLUGIN_ROOT. ─
# The neutral override works for every agent; CLAUDE_PLUGIN_ROOT is kept only for backwards
# compatibility with existing Claude installs (C-4).
if [ -n "${FEATURE_FORGE_ROOT:-}" ] && is_root "$FEATURE_FORGE_ROOT"; then
  printf '%s\n' "$FEATURE_FORGE_ROOT"
  exit 0
fi
if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && is_root "$CLAUDE_PLUGIN_ROOT"; then
  printf '%s\n' "$CLAUDE_PLUGIN_ROOT"
  exit 0
fi

# ── Step 4: failure — actionable message to stderr, exit 1 (REQ-RES-04). ─────────────────
echo "feature-forge: cannot locate install root. Set FEATURE_FORGE_ROOT to the bundle dir, or run from an installed skill dir." >&2
exit 1
