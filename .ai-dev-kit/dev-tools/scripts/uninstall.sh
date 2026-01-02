#!/bin/bash
# AI Dev Kit - Uninstall Script
# Removes the template from a project

set -e

PROJECT_ROOT="$(pwd)"

echo "🗑️  AI Dev Kit Uninstaller"
echo "========================="
echo ""
echo "Project root: $PROJECT_ROOT"
echo ""

# Confirm
read -p "⚠️  This will remove AI Dev Kit from this project. Continue? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "🗑️  Removing symlinks..."

# Remove root symlinks
rm -f "$PROJECT_ROOT/CLAUDE.md" 2>/dev/null && echo "   ✅ Removed CLAUDE.md"
rm -f "$PROJECT_ROOT/AGENT.md" 2>/dev/null && echo "   ✅ Removed AGENT.md"
rm -f "$PROJECT_ROOT/AGENTS.md" 2>/dev/null && echo "   ✅ Removed AGENTS.md"
rm -f "$PROJECT_ROOT/GEMINI.md" 2>/dev/null && echo "   ✅ Removed GEMINI.md"

# Remove legacy .ai-kit directory if it exists (deprecated)
if [ -d "$PROJECT_ROOT/.ai-kit" ]; then
    echo "🗑️  Removing legacy .ai-kit directory..."
    rm -rf "$PROJECT_ROOT/.ai-kit" && echo "   ✅ Removed .ai-kit/"
fi

# Optionally remove tool configs
read -p "Remove tool configurations (.claude/, .cursor/, .gemini/)? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$PROJECT_ROOT/.claude" 2>/dev/null && echo "   ✅ Removed .claude/"
    rm -rf "$PROJECT_ROOT/.cursor" 2>/dev/null && echo "   ✅ Removed .cursor/"
    rm -rf "$PROJECT_ROOT/.gemini" 2>/dev/null && echo "   ✅ Removed .gemini/"
fi

# Optionally remove ai-docs and specs
read -p "Remove ai-docs/ and specs/ directories? (y/N) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$PROJECT_ROOT/ai-docs" 2>/dev/null && echo "   ✅ Removed ai-docs/"
    rm -rf "$PROJECT_ROOT/specs" 2>/dev/null && echo "   ✅ Removed specs/"
fi

echo ""
echo "✅ Uninstall complete!"
echo ""
