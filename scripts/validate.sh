#!/usr/bin/env bash
# Validate the feature-forge single-plugin marketplace.
#
# This repo IS the plugin: the repo root contains both the marketplace
# catalog (.claude-plugin/marketplace.json) and the plugin manifest
# (.claude-plugin/plugin.json), with the plugin registered as "source": ".".
#
# Adapted from the multi-plugin validator in garygentry/agent-plugins for the
# flattened, self-contained layout. Requires python3.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ERRORS=0
WARNINGS=0

echo "Validating feature-forge plugin structure..."
echo "============================================"

# 1. Validate marketplace.json
MARKETPLACE="$REPO_ROOT/.claude-plugin/marketplace.json"
if [ ! -f "$MARKETPLACE" ]; then
  echo "FAIL: Missing $MARKETPLACE"
  ERRORS=$((ERRORS + 1))
elif python3 -m json.tool "$MARKETPLACE" > /dev/null 2>&1; then
  echo "PASS: marketplace.json is valid JSON"
else
  echo "FAIL: marketplace.json is not valid JSON"
  ERRORS=$((ERRORS + 1))
fi

# 2. Validate the root plugin manifest
PLUGIN_JSON="$REPO_ROOT/.claude-plugin/plugin.json"
if [ ! -f "$PLUGIN_JSON" ]; then
  echo "FAIL: Missing plugin manifest: .claude-plugin/plugin.json"
  ERRORS=$((ERRORS + 1))
elif python3 -m json.tool "$PLUGIN_JSON" > /dev/null 2>&1; then
  echo "PASS: plugin.json is valid JSON"
else
  echo "FAIL: plugin.json is not valid JSON"
  ERRORS=$((ERRORS + 1))
fi

# 3. Every plugin listed in marketplace.json must resolve to a plugin.json.
#    For this single-plugin repo the only entry uses "source": "." -> root.
if [ -f "$MARKETPLACE" ]; then
  while IFS=$'\t' read -r PNAME PSOURCE; do
    [ -n "$PNAME" ] || continue
    RESOLVED="$REPO_ROOT/$PSOURCE/.claude-plugin/plugin.json"
    if [ -f "$RESOLVED" ]; then
      echo "PASS: marketplace entry '$PNAME' (source: $PSOURCE) resolves to a plugin.json"
    else
      echo "FAIL: marketplace entry '$PNAME' (source: $PSOURCE) has no plugin.json at $PSOURCE/.claude-plugin/plugin.json"
      ERRORS=$((ERRORS + 1))
    fi
  done < <(python3 -c "
import json
with open('$MARKETPLACE') as f:
    data = json.load(f)
for p in data.get('plugins', []):
    print(p['name'] + '\t' + p.get('source', '.'))
" 2>/dev/null || true)
fi

# 4. Validate skill frontmatter (name + description required)
echo ""
echo "Checking skill frontmatter..."
for SKILL_FILE in "$REPO_ROOT"/skills/*/SKILL.md; do
  [ -f "$SKILL_FILE" ] || continue
  REL_PATH="${SKILL_FILE#$REPO_ROOT/}"
  HAS_NAME=$(sed -n '/^---$/,/^---$/p' "$SKILL_FILE" | grep -c '^name:' || true)
  HAS_DESC=$(sed -n '/^---$/,/^---$/p' "$SKILL_FILE" | grep -c '^description:' || true)
  if [ "$HAS_NAME" -eq 0 ]; then
    echo "FAIL: $REL_PATH missing 'name' in frontmatter"
    ERRORS=$((ERRORS + 1))
  fi
  if [ "$HAS_DESC" -eq 0 ]; then
    echo "FAIL: $REL_PATH missing 'description' in frontmatter"
    ERRORS=$((ERRORS + 1))
  fi
  if [ "$HAS_NAME" -gt 0 ] && [ "$HAS_DESC" -gt 0 ]; then
    echo "PASS: $REL_PATH has required frontmatter"
  fi
done

# 5. Validate agent frontmatter (name + description required)
echo ""
echo "Checking agent frontmatter..."
for AGENT_FILE in "$REPO_ROOT"/agents/*.md; do
  [ -f "$AGENT_FILE" ] || continue
  REL_PATH="${AGENT_FILE#$REPO_ROOT/}"
  HAS_NAME=$(sed -n '/^---$/,/^---$/p' "$AGENT_FILE" | grep -c '^name:' || true)
  HAS_DESC=$(sed -n '/^---$/,/^---$/p' "$AGENT_FILE" | grep -c '^description:' || true)
  if [ "$HAS_NAME" -eq 0 ]; then
    echo "FAIL: $REL_PATH missing 'name' in frontmatter"
    ERRORS=$((ERRORS + 1))
  fi
  if [ "$HAS_DESC" -eq 0 ]; then
    echo "FAIL: $REL_PATH missing 'description' in frontmatter"
    ERRORS=$((ERRORS + 1))
  fi
  if [ "$HAS_NAME" -gt 0 ] && [ "$HAS_DESC" -gt 0 ]; then
    echo "PASS: $REL_PATH has required frontmatter"
  fi
done

# 6. Check script permissions
echo ""
echo "Checking script permissions..."
for SCRIPT in "$REPO_ROOT"/scripts/*.sh; do
  [ -f "$SCRIPT" ] || continue
  REL_PATH="${SCRIPT#$REPO_ROOT/}"
  if [ -x "$SCRIPT" ]; then
    echo "PASS: $REL_PATH is executable"
  else
    echo "FAIL: $REL_PATH is not executable (run: chmod +x $REL_PATH)"
    ERRORS=$((ERRORS + 1))
  fi
done

# 6a. Spec-purity gate (REQ-VER-01..03) — a TOP-LEVEL step, OUTSIDE the
#     `if [ -f "$HELPER" ]` epic-manifest guard, so it runs UNCONDITIONALLY.
#     python3 stdlib only (no pyyaml), so it is always available; under
#     `set -euo pipefail` a non-zero exit fails validate.sh immediately.
#     This is a HARD gate — it is NEVER soft-skipped (unlike the pytest step).
echo ""
echo "Checking spec purity..."
if python3 "$REPO_ROOT/scripts/check-spec-purity.py"; then
  echo "PASS: spec-purity checker (all canonical surfaces clean)"
else
  echo "FAIL: spec-purity checker reported violations (see above)"
  ERRORS=$((ERRORS + 1))
fi

# 6b. Adapters regen-and-diff drift guard (REQ-CI-01..04, tech-spec §3.8, D4) —
#     a TOP-LEVEL step, OUTSIDE the `if [ -f "$HELPER" ]` epic-manifest guard, so
#     it runs UNCONDITIONALLY. It provisions an isolated, gitignored venv with the
#     pinned YAML dep (C-4; never mutates system Python, avoids PEP-668), then runs
#     `build-adapters.py --check`: regenerate to a temp dir, diff -r vs the
#     committed adapters/. Under `set -euo pipefail` a non-zero --check exit fails
#     validate.sh immediately. This is a HARD gate — NEVER soft-skipped (unlike the
#     pytest step), because generated artifacts must never silently drift from canon.
echo ""
echo "Checking adapters/ is in sync with canon..."
ADAPTERS_VENV="$REPO_ROOT/.venv-adapters"
ADAPTERS_REQS="$REPO_ROOT/scripts/requirements-adapters.txt"
ADAPTERS_PY="$ADAPTERS_VENV/bin/python3"
# Provision (create-or-reuse) the isolated venv and install the pinned dep. -q
# keeps output quiet; the install is cached after the first run. A provisioning
# failure is a real error (the verify command must run with no manual setup, C-4).
if [ ! -x "$ADAPTERS_PY" ]; then
  python3 -m venv "$ADAPTERS_VENV"
fi
if "$ADAPTERS_PY" -m pip install -q -r "$ADAPTERS_REQS"; then
  if "$ADAPTERS_PY" "$REPO_ROOT/scripts/build-adapters.py" --check; then
    echo "PASS: adapters/ matches a fresh generation (no drift)"
  else
    echo "FAIL: adapters/ is out of date — run 'python3 scripts/build-adapters.py' and commit the result"
    ERRORS=$((ERRORS + 1))
  fi
else
  echo "FAIL: could not provision .venv-adapters from scripts/requirements-adapters.txt"
  echo "      (environment/setup fault, NOT a canon error or drift — check network access,"
  echo "       PEP-668/externally-managed Python, or a corrupt requirements-adapters.txt)"
  ERRORS=$((ERRORS + 1))
fi

# 7. Compile-check and test epic-manifest helper
echo ""
echo "Checking epic-manifest helper..."
HELPER="$REPO_ROOT/scripts/epic-manifest.py"
if [ -f "$HELPER" ]; then
  if python3 -m py_compile "$HELPER" 2>/dev/null; then
    echo "PASS: scripts/epic-manifest.py compiles (py_compile)"
  else
    echo "FAIL: scripts/epic-manifest.py failed py_compile"
    ERRORS=$((ERRORS + 1))
  fi
  if python3 -c "import pytest" 2>/dev/null; then
    if python3 -m pytest "$REPO_ROOT/tests" -q; then
      echo "PASS: epic-manifest pytest suite"
    else
      echo "FAIL: epic-manifest pytest suite"
      ERRORS=$((ERRORS + 1))
    fi
  else
    echo "SKIP: pytest not installed; skipping epic-manifest test suite (non-fatal)"
    WARNINGS=$((WARNINGS + 1))
  fi
else
  echo "SKIP: scripts/epic-manifest.py not found; skipping helper checks (non-fatal)"
  WARNINGS=$((WARNINGS + 1))
fi

echo ""
echo "Building + testing the cross-agent installer..."
if command -v npm >/dev/null 2>&1; then
  if ( cd "$REPO_ROOT/installer" && npm ci --silent && npm run build --silent && npm test ); then
    echo "PASS: installer build + node:test suite"
  else
    echo "FAIL: installer build/test (see above)"
    ERRORS=$((ERRORS + 1))
  fi
else
  echo "FAIL: node/npm not found — required to build + test the installer (install Node >= 18)"
  ERRORS=$((ERRORS + 1))
fi

echo ""
echo "============================================"
if [ "$ERRORS" -eq 0 ]; then
  echo "All checks passed!"
  if [ "$WARNINGS" -gt 0 ]; then
    echo "$WARNINGS warning(s)."
  fi
else
  echo "$ERRORS error(s) found."
  exit 1
fi
