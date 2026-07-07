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
  "testCommand": null,
  "loopIterationMultiplier": 1.5,
  "autoInvokeNextStage": true,
  "contextWindowTokens": null,
  "contextWarnThreshold": 0.7,
  "autoVerify": false,
  "autoVerifyStages": {},
  "autoFix": false
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
echo "  loopIterationMultiplier: 1.5 (multiplier for loop iterations)"
echo "  autoInvokeNextStage: true (navigator auto-starts the next stage after you confirm)"
echo "  contextWindowTokens: null (infer; set to 1000000 on a 1M-context model)"
echo "  contextWarnThreshold: 0.7 (suggest a clean session past this fraction of the window)"
echo "  autoVerify:          false (set true to run forge-verify automatically after each stage)"
echo "  autoVerifyStages:    {} (per-stage overrides for autoVerify)"
echo "  autoFix:             false (set true to chain forge-fix after an auto-verify finds issues)"
echo ""
echo "The loop runner defaults to rauf. To target a different ralph-style runner,"
echo "add a \"loopRunner\" block (see references/forge-config-schema.json)."
echo ""
echo "Edit $CONFIG_FILE to customize paths and stack settings for your project."
