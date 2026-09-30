#!/usr/bin/env bash
set -euo pipefail

# Check if forge.config.json exists in the current working directory
if [[ -f "forge.config.json" ]]; then
  exit 0
fi

# Check if any pipeline state files exist at any depth under specs/. Use find, not a
# `specs/**/…` glob: without `shopt -s globstar` the `**` collapses to a single level
# and would miss epic-member state (specs/<epic>/<member>/.pipeline-state.json).
if find specs/ -name ".pipeline-state.json" -print -quit 2>/dev/null | grep -q .; then
  echo "⚠ Feature forge pipeline state found but no forge.config.json. Run /feature-forge:forge-init to create configuration."
fi

exit 0
