#!/bin/bash
# Execute a query using Gemini CLI
# Usage: ./query.sh "your question" [file1] [file2] ...

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORCHESTRATION_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
TASK="$1"
shift
FILES="$@"
TIMESTAMP=$(date -Iseconds)

# Validate input
if [ -z "$TASK" ]; then
    echo '{"success": false, "error": "No task provided", "agent": "gemini"}'
    exit 1
fi

# Check if gemini CLI is available
if ! command -v gemini &> /dev/null; then
    echo '{"success": false, "error": "gemini CLI not found - install with: npm install -g @google/gemini-cli", "agent": "gemini"}'
    exit 1
fi

# Build file arguments
FILE_ARGS=""
for FILE in $FILES; do
    if [ -f "$FILE" ]; then
        FILE_ARGS="$FILE_ARGS --file $FILE"
    fi
done

# Log usage
"$ORCHESTRATION_DIR/monitoring/log-usage.sh" gemini --task "$TASK" 2>/dev/null || true

# Execute Gemini
RESULT=$(gemini -p "$TASK" $FILE_ARGS 2>&1) || {
    echo "{\"success\": false, \"error\": \"Gemini execution failed\", \"raw\": $(echo "$RESULT" | jq -Rs .), \"agent\": \"gemini\", \"timestamp\": \"$TIMESTAMP\"}"
    exit 1
}

# Format as JSON
echo "{\"success\": true, \"output\": $(echo "$RESULT" | jq -Rs .), \"agent\": \"gemini\", \"timestamp\": \"$TIMESTAMP\"}"
