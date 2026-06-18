# Drifted prelude reference

This reference carries the prelude sentinel but is NOT byte-identical to canon
(the second line's message was altered), so rule 5 must flag it:

```bash
R="$(for d in "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/*/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done)"
[ -n "$R" ] || { echo "DRIFTED: not the canonical message" >&2; exit 1; }
python3 "$R/scripts/epic-manifest.py"
```
