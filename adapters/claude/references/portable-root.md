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
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
```

## Usage

Prepend the prelude to a fenced shell block once, then invoke bundled scripts via `$R`:
`python3 "$R/scripts/<x>"` or `bash "$R/scripts/<x>"`. One prelude per fenced block — if a block
makes several calls, add the prelude once and reuse `$R` for each. A fresh block gets its own
prelude (per-block re-resolution). Worked example:

```bash
R="$(bash -c 'for d in "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/epic-manifest.py" render-status "{epic}" --specs-dir "{specsDir}" --json
```

## Invariants (do NOT "fix" these)

1. **First hint is the Claude plugin-root env var; the rest are paths.** The prelude's
   `for d in …` list leads with the `CLAUDE_PLUGIN_ROOT` env var (in default-empty `:-` form)
   — the exact bundle dir Claude exports in every marketplace/plugin session — followed by the
   directory-path candidates. The hint gives exact, glob-free resolution on any current/future
   Claude layout (no version-skew window); when unset it expands to empty and is harmlessly
   skipped, so other hosts fall through to the path candidates unchanged. This is the **one
   sanctioned** appearance of that variable in canonical surfaces: spec-purity rule 3 allows it
   by stripping the byte-pinned prelude before its residual-var scan (so a stray var anywhere
   else — including the default-empty form — still fails), and `forge-agent-adapters-build`
   translates it to `FEATURE_FORGE_ROOT` for non-Claude bundles (which `forge-root.sh` already
   prefers). The exact literal is shown only in the fenced prelude above and audited in
   `vendor-construct-inventory.md`.
2. **First-discoverable-resolver-wins.** The `exec` inside the `$(…)` command substitution means
   the loop stops at the first directory holding an executable `forge-root.sh` and delegates ALL
   final root resolution to that script. The `for` list is a discovery order for `forge-root.sh`
   itself, not a fallback chain for the plugin root. Removing the `exec` to "keep looping" is a
   regression — once `exec`'d, the loop is replaced by the resolver process and never advances.
3. **Prelude candidate set is an agent-neutral bootstrap subset (after the env hint).** The
   prelude's `for d` list exists only to bootstrap-discover `forge-root.sh`; the authoritative
   multi-root probe lives in `forge-root.sh` step 2. After the leading env-var hint (invariant 1),
   the list enumerates install roots across agents — the Claude
   skill/plugin dirs — including the marketplace-cache layout
   `~/.claude/plugins/cache/<marketplace>/feature-forge/<version>/`, listed before the
   single-star plugins glob so a versioned cache install always beats the marketplace clone —
   **and** the agent-neutral `.agents/skills/feature-forge` dirs (`$HOME` and the
   project-relative `./.agents/...`) — so a non-Claude install (e.g. Codex under `.agents/skills`)
   can still discover the resolver. When adding an install root, update `forge-root.sh` first;
   extend the prelude only if the new root is needed to bootstrap-discover `forge-root.sh` itself.

## The resolver

The prelude delegates to [`scripts/forge-root.sh`](../scripts/forge-root.sh) — the portable
skill/plugin-root resolver. It takes no arguments, prints the absolute plugin root to stdout and
exits `0`, or writes an actionable message to stderr and exits `1`. It resolves the root by
self-location → candidate-root probe → plugin-root environment-variable fallback → actionable failure,
and never sources or executes a discovered path — it only ever prints a directory string. The
spec-purity checker (rule 5) enforces that every prelude occurrence across the canon is
byte-identical to the fenced block in this file.
