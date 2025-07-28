#!/bin/bash
# Post-tool use hook for Claude Code
# This script runs after Claude executes any tool

# Environment variables available:
# CLAUDE_TOOL - The tool that was used
# CLAUDE_COMMAND - The command that was executed
# CLAUDE_EXIT_CODE - The exit code of the tool
# CLAUDE_PROJECT_ROOT - The project root directory

# Example: Log successful file modifications
if [[ "$CLAUDE_TOOL" == "Write" || "$CLAUDE_TOOL" == "Edit" ]] && [[ "$CLAUDE_EXIT_CODE" == "0" ]]; then
    # Log file changes (uncomment to enable)
    # echo "$(date): Modified file via $CLAUDE_TOOL" >> .claude/logs/file_changes.log
    :
fi

# Example: Auto-format code after edits
if [[ "$CLAUDE_TOOL" == "Edit" && "$CLAUDE_EXIT_CODE" == "0" ]]; then
    # Run formatter if configured (uncomment and modify as needed)
    # if [[ -f "package.json" ]] && command -v npm &> /dev/null; then
    #     npm run format --silent
    # fi
    :
fi

# Example: Run tests after code changes
if [[ ("$CLAUDE_TOOL" == "Write" || "$CLAUDE_TOOL" == "Edit") && "$CLAUDE_EXIT_CODE" == "0" ]]; then
    # Auto-run tests for changed files (uncomment to enable)
    # if [[ -f "package.json" ]] && command -v npm &> /dev/null; then
    #     npm test --silent
    # fi
    :
fi

# Example: Git operations tracking
if [[ "$CLAUDE_TOOL" == "Bash" && "$CLAUDE_COMMAND" =~ ^git[[:space:]] ]]; then
    # Track git operations (uncomment to enable)
    # echo "$(date): Git operation: $CLAUDE_COMMAND" >> .claude/logs/git_ops.log
    :
fi

# Always exit 0 - post hooks should not block operations
exit 0