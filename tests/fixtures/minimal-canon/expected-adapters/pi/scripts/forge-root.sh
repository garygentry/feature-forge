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
# plugin root iff BOTH sentinel files exist. Content-based, so it identifies a feature-forge
# install under ANY agent's directory layout.
is_root() {  # $1 = candidate dir
  [ -f "$1/scripts/epic-manifest.py" ] && [ -f "$1/.claude-plugin/plugin.json" ]
}

# ── Step 1: self-location — parent of this script's dir is the plugin root. ──────────────
self_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
root="$(cd -- "$self_dir/.." && pwd -P)"
if is_root "$root"; then
  printf '%s\n' "$root"
  exit 0
fi

# ── Step 2: candidate-root probe (authoritative multi-root list; extend here first). ─────
# Globs that match nothing expand to themselves; the is_root test rejects such literals.
for candidate in \
  "$HOME/.claude/skills/feature-forge" \
  "$HOME"/.claude/plugins/*/feature-forge \
; do
  if is_root "$candidate"; then
    printf '%s\n' "$candidate"
    exit 0
  fi
done

# ── Step 3: env fallback — the SINGLE sanctioned residual ${CLAUDE_PLUGIN_ROOT} (C-4). ───
if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && is_root "$CLAUDE_PLUGIN_ROOT"; then
  printf '%s\n' "$CLAUDE_PLUGIN_ROOT"
  exit 0
fi

# ── Step 4: failure — actionable message to stderr, exit 1 (REQ-RES-04). ─────────────────
echo "feature-forge: cannot locate plugin root. Set CLAUDE_PLUGIN_ROOT or run from an installed skill dir." >&2
exit 1
