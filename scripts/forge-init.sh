#!/usr/bin/env bash
# Initialize feature-forge configuration in the current project.
# Creates forge.config.json with sensible defaults.

set -euo pipefail

CONFIG_FILE="forge.config.json"

if [ -f "$CONFIG_FILE" ]; then
  echo "⚠️  $CONFIG_FILE already exists. Skipping."
  exit 0
fi

cat > "$CONFIG_FILE" << 'EOF'
{
  "specsDir": "./specs",
  "docsDir": "./docs/architecture",
  "backlogDir": null,
  "gitCommitAfterStage": true,
  "commitPrefix": "forge",
  "stack": null,
  "typeCheckCommand": null,
  "testCommand": null
}
EOF

echo "✅ Created $CONFIG_FILE with defaults."
echo ""
echo "Defaults:"
echo "  specsDir:            ./specs"
echo "  docsDir:             ./docs/architecture"
echo "  backlogDir:          null (defaults to {specsDir}/{feature}/backlog.json)"
echo "  gitCommitAfterStage: true"
echo "  commitPrefix:        forge"
echo "  stack:               null (auto-detected during forge-2-tech)"
echo "  typeCheckCommand:    null (auto-detected during forge-2-tech)"
echo "  testCommand:         null (auto-detected during forge-2-tech)"
echo ""
echo "Edit $CONFIG_FILE to customize paths and stack settings for your project."
