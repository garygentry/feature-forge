#!/usr/bin/env bash
set -euo pipefail

# Check if forge.config.json exists in the current working directory
if [[ -f "forge.config.json" ]]; then
  exit 0
fi

# Check if any pipeline state files exist under specs/
if compgen -G "specs/**/.pipeline-state.json" > /dev/null 2>&1 || \
   find specs/ -name ".pipeline-state.json" -print -quit 2>/dev/null | grep -q .; then
  echo "⚠ Feature forge pipeline state found but no forge.config.json. Run /feature-forge:forge-init to create configuration."
fi

exit 0
