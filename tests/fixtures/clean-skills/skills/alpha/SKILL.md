---
name: alpha
description: A valid skill description.
---
# Alpha

Run a bundled script:

```bash
R="$(bash -c '[ -z "${FEATURE_FORGE_ROOT:-}" ] || [ -x "$FEATURE_FORGE_ROOT/scripts/forge-root.sh" ] || { echo "feature-forge: FEATURE_FORGE_ROOT=$FEATURE_FORGE_ROOT has no scripts/forge-root.sh" >&2; exit 2; }; for d in "${FEATURE_FORGE_ROOT:-}" "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/cache/*/feature-forge/* "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/epic-manifest.py" --json
```
