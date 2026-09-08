#!/usr/bin/env bash
# scripts/dev-plugin.sh — assemble an out-of-repo, self-contained plugin dir from a
# BUILT adapter bundle, for running the LOCAL SOURCE of feature-forge via
# `claude --plugin-dir <dir>` (or another host's equivalent). Dev-only (source dogfood).
#
# WHY THIS EXISTS (see docs/DOGFOODING.md and #305):
#   • A skill's prose `Read references/X` resolves SKILL-LOCAL — relative to
#     `skills/<name>/`, not the plugin root. Canon skills are the build SOURCE and are
#     intentionally NOT self-contained: their shared references are fanned into the
#     built `adapters/<host>/` bundles at build time (#132), never into canon. So running
#     RAW CANON (a repo-root symlink) dead-references them mid-stage. A BUILT bundle has
#     the refs skill-local, so it resolves correctly. This script points a plugin dir at
#     the built bundle.
#   • `adapters/<host>/` has a neutral `.feature-forge-bundle.json` but NO
#     `.claude-plugin/plugin.json`, so `claude --plugin-dir adapters/claude` loads with the
#     wrong identity (`claude@inline`, version "unknown" — the directory name). This script
#     writes a REAL `.claude-plugin/plugin.json` (correct name + version) into an
#     OUT-OF-REPO dir and symlinks the bundle's component trees in — so it loads as
#     `feature-forge@inline` at the right version, and the manifest NEVER enters the
#     repo tree the marketplace ships via `source: "."` (so it can never become a nested
#     duplicate plugin in a standard install).
#   • The component trees are SYMLINKS into the live built bundle, so a canon edit takes
#     effect after a rebuild (`python3 scripts/build-adapters.py`) with no re-run of this
#     script. Re-run it only to change agent/version or after moving the checkout.
#
# Session-only + reversible: `--plugin-dir` loads for one session, takes precedence over
# an installed marketplace version FOR THAT SESSION, and touches no global config. Nothing
# here modifies ~/.claude, the repo tree, or any standard install.
#
# Usage:
#   scripts/dev-plugin.sh [--agent <claude|codex|copilot|cursor|gemini|pi>] [--out <dir>] [--force]
#   Then run the printed command, e.g.:  claude --plugin-dir <dir>
set -euo pipefail

agent="claude"
out=""
force=0
while [ $# -gt 0 ]; do
  case "$1" in
    -a|--agent) agent="${2:?--agent needs a value}"; shift 2 ;;
    -o|--out)   out="${2:?--out needs a value}"; shift 2 ;;
    -f|--force) force=1; shift ;;
    -h|--help)
      cat <<'USAGE'
dev-plugin.sh — assemble an out-of-repo, self-contained plugin dir from a BUILT
adapter bundle, for running the LOCAL SOURCE via `claude --plugin-dir <dir>`.

Usage: scripts/dev-plugin.sh [--agent <claude|codex|copilot|cursor|gemini|pi>] [--out <dir>] [--force]

  -a, --agent <id>  Which built adapters/<id> bundle to expose (default: claude).
  -o, --out <dir>   Where to assemble the plugin dir. Must be OUTSIDE the repo (the
                    manifest must never ship). Default:
                    ${XDG_CACHE_HOME:-~/.cache}/feature-forge-dev/<agent>.
  -f, --force       Overwrite <dir> even if it does not look like a prior assembly.
  -h, --help        This help.

Then run the printed command, e.g.:  claude --plugin-dir <dir>
See docs/DOGFOODING.md.
USAGE
      exit 0 ;;
    *) echo "dev-plugin: unknown argument: $1" >&2; exit 2 ;;
  esac
done

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
bundle="$repo_root/adapters/$agent"
if [ ! -d "$bundle" ]; then
  echo "dev-plugin: no built bundle at adapters/$agent — run 'python3 scripts/build-adapters.py' first." >&2
  exit 1
fi

# Version is the single source of record (repo-root plugin manifest).
version="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["version"])' \
  "$repo_root/.claude-plugin/plugin.json")"

# Default target: an out-of-repo cache dir, keyed by agent. NEVER inside the repo (the
# marketplace ships the repo via source: "."; a manifest there could become a nested dup).
out="${out:-${XDG_CACHE_HOME:-$HOME/.cache}/feature-forge-dev/$agent}"
# Canonicalize to an absolute PHYSICAL path first, so the in-repo guard below cannot be
# bypassed by a relative or symlinked --out that actually resolves inside the checkout.
case "$out" in /*) : ;; *) out="$PWD/$out" ;; esac
_p="$out"; _tail=""
while [ ! -e "$_p" ] && [ "$_p" != "/" ]; do
  _tail="/$(basename -- "$_p")$_tail"; _p="$(dirname -- "$_p")"
done
out="$(cd -- "$_p" && pwd -P)$_tail"
case "$out" in
  "$repo_root"|"$repo_root"/*)
    echo "dev-plugin: refusing --out inside the repo ($out); the manifest must not ship. Pick a path outside $repo_root." >&2
    exit 2 ;;
esac

# A prior assembly is recognized by the sentinel SYMLINK we create (test the link itself with
# -L, not -e: -e follows the link and a moved/rebuilt bundle leaves it dangling).
if [ -e "$out" ] && [ "$force" -eq 0 ] && [ ! -L "$out/.feature-forge-bundle.json" ]; then
  echo "dev-plugin: $out exists and does not look like a prior assembly; pass --force to overwrite." >&2
  exit 1
fi

rm -rf "$out"
mkdir -p "$out/.claude-plugin"

# Real manifest — correct identity + version, so it loads as feature-forge@inline.
cat > "$out/.claude-plugin/plugin.json" <<JSON
{
  "name": "feature-forge",
  "version": "$version",
  "description": "feature-forge — LOCAL SOURCE bundle (adapters/$agent) for dev via --plugin-dir. Not for distribution.",
  "author": { "name": "Gary Gentry" }
}
JSON

# Symlink the live built bundle's component trees + sentinel. Edits take effect after a
# rebuild with no re-run. forge-root.sh self-locates through the scripts symlink (-P) to
# the real bundle, so $R and skill-local refs both resolve to adapters/$agent.
linked=()
for entry in skills agents references scripts .feature-forge-bundle.json; do
  if [ -e "$bundle/$entry" ]; then
    ln -sfn "$bundle/$entry" "$out/$entry"
    linked+=("$entry")
  fi
done
if [ "${#linked[@]}" -eq 0 ]; then
  echo "dev-plugin: adapters/$agent carries none of skills/agents/references/scripts — rebuild with 'python3 scripts/build-adapters.py'." >&2
  exit 1
fi

echo "dev-plugin: assembled feature-forge@$version ($agent) at:"
echo "  $out"
echo "  linked: ${linked[*]}  ->  $bundle/"
echo
echo "Run the local source in a session (takes precedence over any installed version, for that session):"
echo "  claude --plugin-dir \"$out\""
echo
echo "After editing canon, rebuild the bundle (no need to re-run this script):"
echo "  python3 \"$repo_root/scripts/build-adapters.py\""
