#!/bin/bash
# Execute an agentic task using Cursor CLI
# Usage: ./agent.sh "task description" [model]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORCHESTRATION_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
TASK="$1"
MODEL="${2:-auto}"
TIMESTAMP=$(date -Iseconds)

# Validate input
if [ -z "$TASK" ]; then
    echo '{"success": false, "error": "No task provided", "agent": "cursor"}'
    exit 1
fi

# Check if cursor-agent CLI is available
if ! command -v cursor-agent &> /dev/null; then
    echo '{"success": false, "error": "cursor-agent CLI not found - install from cursor.com", "agent": "cursor"}'
    exit 1
fi

# Check for API key (required for non-interactive/headless)
if [ -z "$CURSOR_API_KEY" ] && [ ! -t 0 ]; then
    echo '{"success": false, "error": "CURSOR_API_KEY required for headless execution", "agent": "cursor"}'
    exit 1
fi

# Log usage
"$ORCHESTRATION_DIR/monitoring/log-usage.sh" cursor --task "$TASK" 2>/dev/null || true

# Execute Cursor agent
RESULT=$(cursor-agent -p "$TASK" --model "$MODEL" --output-format json 2>&1) || {
    echo "{\"success\": false, \"error\": \"Cursor execution failed\", \"raw\": $(echo "$RESULT" | jq -Rs .), \"agent\": \"cursor\", \"model\": \"$MODEL\", \"timestamp\": \"$TIMESTAMP\"}"
    exit 1
}

# Parse and enhance output
if echo "$RESULT" | jq . &>/dev/null; then
    echo "$RESULT" | jq --arg agent "cursor" --arg model "$MODEL" --arg ts "$TIMESTAMP" \
        '. + {agent: $agent, model: $model, timestamp: $ts}'
else
    echo "{\"success\": true, \"output\": $(echo "$RESULT" | jq -Rs .), \"agent\": \"cursor\", \"model\": \"$MODEL\", \"timestamp\": \"$TIMESTAMP\"}"
fi
