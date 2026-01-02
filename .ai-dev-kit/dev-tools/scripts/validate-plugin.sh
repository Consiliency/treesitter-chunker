#!/bin/bash
# Validate the AI Dev Kit plugin structure and content
# Checks for common issues that would break marketplace installs

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
PLUGIN_DIR="${REPO_ROOT}/plugins/ai-dev-kit"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ERRORS=0
WARNINGS=0

echo "🔍 Validating AI Dev Kit plugin..."
echo ""

# Function to report error
error() {
  echo -e "${RED}ERROR:${NC} $1"
  ((ERRORS++))
}

# Function to report warning
warn() {
  echo -e "${YELLOW}WARN:${NC} $1"
  ((WARNINGS++))
}

# Function to report success
ok() {
  echo -e "${GREEN}✓${NC} $1"
}

# Check plugin structure
echo "📁 Checking plugin structure..."
if [ ! -f "${PLUGIN_DIR}/.claude-plugin/plugin.json" ]; then
  error ".claude-plugin/plugin.json not found"
else
  ok ".claude-plugin/plugin.json exists"
fi

for dir in commands agents skills templates; do
  if [ ! -d "${PLUGIN_DIR}/${dir}" ]; then
    error "${dir}/ directory not found"
  else
    ok "${dir}/ directory exists"
  fi
done

echo ""

# Check for non-existent path references
echo "📍 Checking for non-existent path references..."

# Check for ai-docs/internal (deprecated path)
if grep -rq "ai-docs/internal" "${PLUGIN_DIR}" --exclude="validate-plugin.sh" 2>/dev/null; then
  error "Found references to deprecated ai-docs/internal path:"
  grep -rn "ai-docs/internal" "${PLUGIN_DIR}" --exclude="validate-plugin.sh" | head -5
else
  ok "No ai-docs/internal references"
fi

# Check for .ai-kit directory creation (deprecated)
if grep -rq "mkdir.*\.ai-kit" "${PLUGIN_DIR}" --exclude="validate-plugin.sh" 2>/dev/null; then
  error "Found .ai-kit directory creation (deprecated):"
  grep -rn "mkdir.*\.ai-kit" "${PLUGIN_DIR}" --exclude="validate-plugin.sh" | head -3
else
  ok "No .ai-kit directory creation"
fi

echo ""

# Check command frontmatter
echo "📋 Checking command frontmatter..."
COMMANDS_WITHOUT_FM=0
for cmd in $(find "${PLUGIN_DIR}/commands" -name "*.md" -type f); do
  if ! head -1 "$cmd" | grep -q "^---$"; then
    warn "Missing frontmatter: ${cmd#${PLUGIN_DIR}/}"
    ((COMMANDS_WITHOUT_FM++))
  fi
done

if [ $COMMANDS_WITHOUT_FM -eq 0 ]; then
  ok "All commands have frontmatter"
fi

echo ""

# Check for placeholder URLs
echo "🔗 Checking for placeholder URLs..."
PLACEHOLDER_COUNT=$(grep -rE "(your-org|your-username)/ai-dev-kit" "${PLUGIN_DIR}" 2>/dev/null | wc -l || true)
if [ "$PLACEHOLDER_COUNT" -gt 0 ]; then
  error "Found ${PLACEHOLDER_COUNT} placeholder URL(s)"
else
  ok "No placeholder URLs found"
fi

echo ""

# Summary
echo "═══════════════════════════════════════"
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
  echo -e "${GREEN}✅ All checks passed!${NC}"
else
  echo -e "Errors: ${RED}${ERRORS}${NC}, Warnings: ${YELLOW}${WARNINGS}${NC}"
fi
echo "═══════════════════════════════════════"

exit $ERRORS
