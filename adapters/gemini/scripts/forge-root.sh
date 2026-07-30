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

# Completeness gate (#152). A dir can carry the sentinel yet be a partial/stale install —
# a skill-only extraction, or an install predating the shared-reference fan-out — where the
# scripts/references the skills load at every stage are absent. Such a root looks usable but
# runs DEGRADED silently (hand-improvised state schema, skipped Mint Guard + scripted exit).
# These are the assets a complete install MUST carry beyond the sentinel; a resolved root
# missing any of them is reported as degraded rather than handed back as if it were whole.
CORE_ASSETS=(
  "scripts/forge-session.py"
  "references/pipeline-state-schema.json"
  "references/stage-exit-protocol.md"
)

# Echo the first missing core asset (relative path) for $1, or nothing when complete.
first_missing_asset() {  # $1 = candidate dir
  local a
  for a in "${CORE_ASSETS[@]}"; do
    [ -f "$1/$a" ] || { printf '%s' "$a"; return 0; }
  done
}

# A sentinel-bearing candidate that lacks a core asset is remembered here (first one wins)
# so a COMPLETE root found later in the probe order still takes precedence; only if the probe
# ends with no complete root do we report this degraded install (step 4).
partial_root=""
partial_missing=""

# Given a candidate that already passed is_root: print + exit 0 if it is complete; otherwise
# record it as the degraded fallback and return so probing continues. Always returns 0 on the
# fall-through path so `set -e` never aborts the resolver on a partial candidate.
accept_root() {  # $1 = candidate dir (already is_root)
  local miss
  miss="$(first_missing_asset "$1")"
  if [ -z "$miss" ]; then
    printf '%s\n' "$1"
    exit 0
  fi
  if [ -z "$partial_root" ]; then
    partial_root="$1"
    partial_missing="$miss"
  fi
  return 0
}

# ── Step 1: self-location — parent of this script's dir is the install root. ─────────────
# This is the PRIMARY path: a bundle ships its own scripts/forge-root.sh, so the parent of
# this script's dir is that bundle's root under any agent's layout.
self_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
root="$(cd -- "$self_dir/.." && pwd -P)"
if is_root "$root"; then
  accept_root "$root"
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
    accept_root "$candidate"
  fi
done < <(ls -t "$HOME"/.claude/plugins/cache/*/feature-forge/*/.claude-plugin/plugin.json 2>/dev/null || true)

# ── Step 2: candidate-root probe (authoritative multi-agent root list; extend here first). ─
# Globs that match nothing expand to themselves; the is_root test rejects such literals. Covers
# every supported agent's install destination under BOTH global ($HOME) and project ($PWD) scope,
# matching the installer's per-agent layout: claude .claude/skills, codex .agents/skills, copilot
# .github/feature-forge, cursor .cursor/rules, gemini .gemini/extensions, pi .pi/skills or
# $PI_CODING_AGENT_DIR/skills. The cache glob repeats step 2a's path for a cache install that
# carries only the neutral bundle sentinel (no plugin.json for ls -t to key on).
if [ -n "${PI_CODING_AGENT_DIR:-}" ]; then
  for candidate in \
    "$PI_CODING_AGENT_DIR/skills/feature-forge" \
    "$PI_CODING_AGENT_DIR"/git/*/feature-forge/adapters/pi \
    "$PI_CODING_AGENT_DIR"/git/*/*/feature-forge/adapters/pi \
    "$PI_CODING_AGENT_DIR"/packages/*/feature-forge/adapters/pi \
    "$PI_CODING_AGENT_DIR"/npm/*/@garygentry/feature-forge/adapters/pi \
    "$PI_CODING_AGENT_DIR"/node_modules/@garygentry/feature-forge/adapters/pi \
  ; do
    if is_root "$candidate"; then
      accept_root "$candidate"
    fi
  done
fi

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
  "$HOME/.pi/agent/skills/feature-forge" \
  "$PWD/.pi/skills/feature-forge" \
  "$HOME"/.pi/agent/git/*/feature-forge/adapters/pi \
  "$HOME"/.pi/agent/git/*/*/feature-forge/adapters/pi \
  "$HOME"/.pi/agent/packages/*/feature-forge/adapters/pi \
  "$HOME"/.pi/agent/npm/*/@garygentry/feature-forge/adapters/pi \
  "$HOME"/.pi/agent/node_modules/@garygentry/feature-forge/adapters/pi \
  "$PWD"/.pi/git/*/feature-forge/adapters/pi \
  "$PWD"/.pi/git/*/*/feature-forge/adapters/pi \
  "$PWD"/.pi/packages/*/feature-forge/adapters/pi \
  "$PWD"/.pi/npm/*/@garygentry/feature-forge/adapters/pi \
  "$PWD"/.pi/node_modules/@garygentry/feature-forge/adapters/pi \
; do
  if is_root "$candidate"; then
    accept_root "$candidate"
  fi
done

# Project-scoped Pi installs may be discovered from a subdirectory of the repository. Probe
# ancestor .pi roots up to the filesystem root; this is bounded by path depth and avoids
# recursive globs. Scoped to .pi ONLY — every other agent's project layout is probed at $PWD
# in the fixed list above, and widening those to ancestors here would silently change
# established discovery behaviour for agents this bundle did not introduce.
probe_dir="$PWD"
while :; do
  candidate="$probe_dir/.pi/skills/feature-forge"
  if is_root "$candidate"; then
    accept_root "$candidate"
  fi
  [ "$probe_dir" = "/" ] && break
  next_probe_dir="$(dirname -- "$probe_dir")"
  [ "$next_probe_dir" = "$probe_dir" ] && break
  probe_dir="$next_probe_dir"
done

# ── Step 3: env fallback — neutral FEATURE_FORGE_ROOT, then the legacy CLAUDE_PLUGIN_ROOT. ─
# The neutral override works for every agent; CLAUDE_PLUGIN_ROOT is kept only for backwards
# compatibility with existing Claude installs (C-4).
if [ -n "${FEATURE_FORGE_ROOT:-}" ] && is_root "$FEATURE_FORGE_ROOT"; then
  accept_root "$FEATURE_FORGE_ROOT"
fi
if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && is_root "$CLAUDE_PLUGIN_ROOT"; then
  accept_root "$CLAUDE_PLUGIN_ROOT"
fi

# ── Step 4: failure. A sentinel-bearing but asset-incomplete root found along the way is a
# DEGRADED install (#152) — report it distinctly and actionably rather than the generic
# cannot-locate message, so the operator knows to reinstall/update rather than reconfigure. ─
if [ -n "$partial_root" ]; then
  echo "feature-forge: install incomplete/degraded at $partial_root (missing $partial_missing) — reinstall with 'npx @garygentry/feature-forge' (or 'feature-forge update' for a stale install)." >&2
  exit 1
fi
echo "feature-forge: cannot locate install root. Set FEATURE_FORGE_ROOT to the bundle dir, or run from an installed skill dir." >&2
exit 1
