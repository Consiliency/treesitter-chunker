#!/bin/bash
# Execute a task using Claude Code CLI
# Usage: ./spawn.sh "task description" [model]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORCHESTRATION_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
TASK="$1"
MODEL="${2:-sonnet}"
TIMESTAMP=$(date -Iseconds)

# Validate input
if [ -z "$TASK" ]; then
    echo '{"success": false, "error": "No task provided", "agent": "claude-code"}'
    exit 1
fi

# Verify subscription auth (warn if API key is set)
if [ -n "$ANTHROPIC_API_KEY" ]; then
    echo '{"success": false, "error": "ANTHROPIC_API_KEY is set - unset to use subscription auth", "agent": "claude-code"}' >&2
    # Continue anyway, but warn
fi

# Check if claude CLI is available
if ! command -v claude &> /dev/null; then
    echo '{"success": false, "error": "claude CLI not found - install with: npm install -g @anthropic-ai/claude-code", "agent": "claude-code"}'
    exit 1
fi

# Map model shorthand to full name
case "$MODEL" in
    opus)
        MODEL_FLAG="--model opus"
        ;;
    haiku)
        MODEL_FLAG="--model haiku"
        ;;
    sonnet|*)
        MODEL_FLAG="--model sonnet"
        MODEL="sonnet"
        ;;
esac

# Log usage
"$ORCHESTRATION_DIR/monitoring/log-usage.sh" claude --task "$TASK" 2>/dev/null || true

# Execute Claude Code
# Note: claude CLI output format may vary - this attempts to capture it
RESULT=$(claude -p "$TASK" $MODEL_FLAG --output-format json 2>&1) || {
    echo "{\"success\": false, \"error\": \"Claude execution failed\", \"raw\": $(echo "$RESULT" | jq -Rs .), \"agent\": \"claude-code\", \"model\": \"$MODEL\", \"timestamp\": \"$TIMESTAMP\"}"
    exit 1
}

# Parse and enhance output
if echo "$RESULT" | jq . &>/dev/null; then
    # Valid JSON - enhance it
    echo "$RESULT" | jq --arg agent "claude-code" --arg model "$MODEL" --arg ts "$TIMESTAMP" \
        '. + {agent: $agent, model: $model, timestamp: $ts}'
else
    # Not valid JSON - wrap it
    echo "{\"success\": true, \"output\": $(echo "$RESULT" | jq -Rs .), \"agent\": \"claude-code\", \"model\": \"$MODEL\", \"timestamp\": \"$TIMESTAMP\"}"
fi
