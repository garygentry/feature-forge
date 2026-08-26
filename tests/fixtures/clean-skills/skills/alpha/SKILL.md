---
name: alpha
description: A valid skill description.
---
# Alpha

Run a bundled script:

```bash
R="$(bash -c 'for d in "${FEATURE_FORGE_ROOT:-}" "${CLAUDE_PLUGIN_ROOT:-}" "$HOME"/{.claude/skills,.agents/skills,.copilot}/feature-forge "$HOME"/{.claude/plugins/{cache/*/feature-forge/*,*/feature-forge},.copilot/installed-plugins/*/feature-forge} "$PWD"/.agents/skills/feature-forge;do test -x "$d/scripts/forge-root.sh"&&exec "$d/scripts/forge-root.sh";done;for((;;));do d="$PWD/.github/feature-forge";test -x "$d/scripts/forge-root.sh"&&exec "$d/scripts/forge-root.sh";[ "${PWD#/}" ]||break;cd ..||break;done')"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
python3 "$R/scripts/epic-manifest.py" --json
```
