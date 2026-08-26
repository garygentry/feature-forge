# Portable Script-Root Resolution

This file is the **single canonical home** of the feature-forge bootstrap prelude and the
portable invocation convention. Each fenced shell block an agent runs is a separate process
with no persisted state, so the plugin root must be re-resolved within the same block as every
bundled-script call. The prelude below is the fixed, byte-identical snippet that does this by
discovering and delegating to `scripts/forge-root.sh`. Downstream consumers
(`forge-agent-adapters-build`, `cross-agent-installer`) and the spec-purity checker treat this
file as authoritative: the checker's rule 5 compares every prelude occurrence across the canon
against the fenced block here, byte-for-byte.

## Canonical bootstrap prelude

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/{.claude/skills,.agents/skills,.copilot}/feature-forge "$HOME"/{.claude/plugins/{cache/*/feature-forge/*,*/feature-forge},.copilot/installed-plugins/*/feature-forge} "$PWD"/.agents/skills/feature-forge;do test -x "$d/scripts/forge-root.sh"&&exec "$d/scripts/forge-root.sh";done;for((;;));do d="$PWD/.github/feature-forge";test -x "$d/scripts/forge-root.sh"&&exec "$d/scripts/forge-root.sh";[ "${PWD#/}" ]||break;cd ..||break;done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
```

## Usage

Prepend the prelude to a fenced shell block once, then invoke bundled scripts via `$R`:
`python3 "$R/scripts/<x>"` or `bash "$R/scripts/<x>"`. One prelude per fenced block — if a block
makes several calls, add the prelude once and reuse `$R` for each. A fresh block gets its own
prelude (per-block re-resolution). Worked example:

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/{.claude/skills,.agents/skills,.copilot}/feature-forge "$HOME"/{.claude/plugins/{cache/*/feature-forge/*,*/feature-forge},.copilot/installed-plugins/*/feature-forge} "$PWD"/.agents/skills/feature-forge;do test -x "$d/scripts/forge-root.sh"&&exec "$d/scripts/forge-root.sh";done;for((;;));do d="$PWD/.github/feature-forge";test -x "$d/scripts/forge-root.sh"&&exec "$d/scripts/forge-root.sh";[ "${PWD#/}" ]||break;cd ..||break;done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/epic-manifest.py" render-status "{epic}" --specs-dir "{specsDir}" --json
```

## Invariants (do NOT "fix" these)

1. **First hint is the neutral operator override; the legacy Claude hint is second.** The
   prelude's `for d in …` list leads with `FEATURE_FORGE_ROOT` (default-empty `:-` form), then
   `CLAUDE_PLUGIN_ROOT` for existing Claude marketplace/plugin sessions, followed by bounded
   directory candidates. The neutral hint is an explicit, glob-free operator choice and must
   win over conventional installs. The legacy hint is the **one sanctioned** appearance of the
   Claude variable in canonical surfaces: spec-purity rule 3 allows it by stripping the
   byte-pinned prelude before its residual-var scan (so a stray variable anywhere else still
   fails). `forge-agent-adapters-build` removes the redundant legacy hint from non-Claude
   bundles. The exact literal is shown only in this fixed prelude and audited in
   `vendor-construct-inventory.md`.
2. **First-discoverable-resolver-wins.** The `exec` inside the `$(…)` command substitution means
   the loop stops at the first directory holding an executable `forge-root.sh` and delegates ALL
   final root resolution to that script. The `for` list is a discovery order for `forge-root.sh`
   itself, not a fallback chain for the plugin root. Removing the `exec` to "keep looping" is a
   regression — once `exec`'d, the loop is replaced by the resolver process and never advances.
3. **Prelude candidates are a bounded bootstrap subset.** The prelude exists only to discover
   `forge-root.sh`; the resolver owns final validation and precedence. After the environment
   hints, the fixed list covers Claude's skill/plugin/cache roots, Copilot's managed-plugin and
   personal runtime roots, and the agent-neutral `.agents/skills/feature-forge` roots. A bounded
   ancestor loop additionally checks `<ancestor>/.github/feature-forge` so a Copilot project
   install can bootstrap from a nested working directory. The Copilot emitter probes that
   project scope immediately after the explicit override, then Copilot's managed/personal roots,
   then other hosts' conventional roots. This prevents unrelated host installs from shadowing a
   loaded Copilot package while retaining normal project-over-global precedence. The prelude uses
   quoted variables and no recursive
   filesystem search, preserving spaces and shell metacharacters. When adding an
   install root, update `forge-root.sh` first; extend this subset only when that root is also
   needed to bootstrap the resolver itself.

## The resolver

The prelude delegates to [`scripts/forge-root.sh`](../scripts/forge-root.sh) — the portable
skill/plugin-root resolver. It takes no arguments, prints the absolute plugin root to stdout and
exits `0`, or writes an actionable message to stderr and exits `1`. It never sources or executes a
discovered root — it only ever prints a directory string. Its precedence is explicit
`FEATURE_FORGE_ROOT` → self-location → bounded conventional/ancestor probes
→ legacy `CLAUDE_PLUGIN_ROOT` → actionable degraded/generic failure. Copilot never depends on the
unavailable generic `PLUGIN_ROOT` variable. The spec-purity checker (rule 5) enforces that every
prelude occurrence across the canon is
byte-identical to the fenced block in this file.
