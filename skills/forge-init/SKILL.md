---
name: forge-init
description: "Initialize feature-forge configuration in the current project. Use when user runs /feature-forge:forge-init or asks to set up forge for the first time. Creates forge.config.json with defaults. Do NOT trigger for general project initialization or setup tasks outside the forge pipeline."
---

# Initialize Feature Forge

Run the initialization script to create `forge.config.json` with default settings:

```bash
R="$(for d in "$HOME"/.claude/skills/feature-forge "$HOME"/.claude/plugins/*/feature-forge "$HOME"/.agents/skills/feature-forge ./.agents/skills/feature-forge; do [ -x "$d/scripts/forge-root.sh" ] && exec "$d/scripts/forge-root.sh"; done)"
[ -n "$R" ] || { echo "feature-forge: cannot locate plugin root" >&2; exit 1; }
bash "$R/scripts/forge-init.sh"
```

After initialization, the config file will contain defaults for:
- `specsDir`: `./specs`
- `docsDir`: `./docs/architecture`
- `backlogDir`: `null` (backlog lives alongside specs)
- `gitCommitAfterStage`: `true`
- `commitPrefix`: `forge`
- `stack`: `null` (detected during `/feature-forge:forge-2-tech`)
- `typeCheckCommand`: `null` (set during `/feature-forge:forge-2-tech`)
- `testCommand`: `null` (set during `/feature-forge:forge-2-tech`)

If `forge.config.json` already exists, the script will not overwrite it.

After initialization, start the pipeline with `/feature-forge:forge-1-prd <feature-name>`.
