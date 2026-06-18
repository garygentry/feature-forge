---
name: alpha
description: A valid skill description.
---
# Alpha

```bash
R="$(for d in "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/*/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done)"
[ -n  "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
```
