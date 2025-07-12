#!/bin/bash
# CRITICAL: Run this BEFORE creating worktrees or starting parallel development!

echo "=== COMMITTING ALL CHANGES BEFORE PARALLEL DEVELOPMENT ==="
echo ""
echo "This script will commit all your changes to prevent missing files in worktrees."
echo ""

# Show current status
echo "Current git status:"
git status --short
echo ""

# Add all files
echo "Adding all files..."
git add -A

# Create comprehensive commit message
git commit -m "Add complete implementation: ROADMAP, parser refactoring, parallel setup

- Added comprehensive ROADMAP.md with parallelization strategy
- Implemented parser module redesign (Phase 1.1):
  - Created LanguageRegistry with dynamic language discovery
  - Added ParserFactory with LRU caching and thread-safe pooling
  - Implemented comprehensive exception hierarchy
  - Refactored parser.py with backward compatibility
- Added comprehensive test suite (78 tests):
  - test_registry.py: 13 tests for LanguageRegistry
  - test_factory.py: 20 tests for ParserFactory, LRUCache, ParserPool
  - test_exceptions.py: 16 tests for exception hierarchy
  - test_integration.py: 10 tests for end-to-end scenarios
- Set up Git worktree parallelization:
  - Created PARALLEL_DEVELOPMENT_COMMANDS.md
  - Added worktree setup instructions to ROADMAP.md
  - Created WORKTREE_SETUP_CHECKLIST.md
- Added Claude Code configuration:
  - Created .claude/settings.json for project permissions
  - Added CLAUDE.md with project instructions
- Created helper scripts:
  - setup-worktree-env.sh for environment setup
  - launch-claude-sessions.sh for parallel development
  - build_lib.py for compiling tree-sitter grammars
- Added grammar files and build system
- Created CLI structure for chunking tool

All files are now properly tracked in git for parallel development."

# Push to origin
echo ""
echo "Pushing to origin/main..."
git push origin main

# Verify critical files
echo ""
echo "Verifying critical files are in git:"
git ls-tree -r HEAD | grep -E "(ROADMAP.md|parser.py|registry.py|factory.py)" | head -10

echo ""
echo "=== COMMIT COMPLETE ==="
echo ""
echo "Next steps:"
echo "1. If you have existing worktrees, run the fix commands from PARALLEL_DEVELOPMENT_COMMANDS.md"
echo "2. If creating new worktrees, follow the instructions in PARALLEL_DEVELOPMENT_COMMANDS.md"
echo ""
echo "Remember: ALWAYS commit before creating worktrees!"