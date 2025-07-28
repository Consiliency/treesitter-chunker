#!/bin/bash
# Pre-tool use hook for Claude Code
# This script runs before Claude executes any tool

# Environment variables available:
# CLAUDE_TOOL - The tool being used (e.g., "Bash", "Edit", "Write")
# CLAUDE_COMMAND - The command or action being performed
# CLAUDE_PROJECT_ROOT - The project root directory

# Example: Block dangerous commands
if [[ "$CLAUDE_TOOL" == "Bash" ]]; then
    # Block potentially dangerous rm commands
    if [[ "$CLAUDE_COMMAND" =~ ^rm[[:space:]]+-rf[[:space:]]+(\*|/|~|\.\./) ]]; then
        echo "Error: Dangerous rm command blocked for safety"
        exit 1
    fi
    
    # Block commands that might affect system files
    if [[ "$CLAUDE_COMMAND" =~ ^(sudo|rm|mv|cp).*[[:space:]](/etc|/usr|/bin|/sbin|/boot|/dev|/proc|/sys) ]]; then
        echo "Error: System directory modification blocked"
        exit 1
    fi
fi

# Example: Validate file paths
if [[ "$CLAUDE_TOOL" == "Write" || "$CLAUDE_TOOL" == "Edit" ]]; then
    # Add any file path validation here
    # e.g., ensure files are within project directory
    :
fi

# Example: Log tool usage (uncomment to enable)
# echo "$(date): $CLAUDE_TOOL - $CLAUDE_COMMAND" >> .claude/logs/tool_usage.log

# Exit 0 to allow the tool to run
# Exit non-zero to block the tool execution
exit 0