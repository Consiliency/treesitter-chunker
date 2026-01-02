#!/bin/bash
# Execute a task using OpenAI Codex CLI
# Usage: ./execute.sh "task description" [sandbox_mode]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORCHESTRATION_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
TASK="$1"
SANDBOX="${2:-workspace-write}"
TIMESTAMP=$(date -Iseconds)

# Validate input
if [ -z "$TASK" ]; then
    echo '{"success": false, "error": "No task provided", "agent": "codex"}'
    exit 1
fi

# Check if codex CLI is available
if ! command -v codex &> /dev/null; then
    echo '{"success": false, "error": "codex CLI not found - install with: npm install -g @openai/codex", "agent": "codex"}'
    exit 1
fi

# Validate sandbox mode
case "$SANDBOX" in
    read-only|workspace-write|full-access) ;;
    *)
        echo '{"success": false, "error": "Invalid sandbox mode. Use: read-only, workspace-write, or full-access", "agent": "codex"}'
        exit 1
        ;;
esac

# Log usage
"$ORCHESTRATION_DIR/monitoring/log-usage.sh" openai --task "$TASK" 2>/dev/null || true

# Execute Codex
RESULT=$(codex exec "$TASK" --json --sandbox "$SANDBOX" 2>&1) || {
    echo "{\"success\": false, \"error\": \"Codex execution failed\", \"raw\": $(echo "$RESULT" | jq -Rs .), \"agent\": \"codex\", \"sandbox\": \"$SANDBOX\", \"timestamp\": \"$TIMESTAMP\"}"
    exit 1
}

# Parse and enhance output
if echo "$RESULT" | jq . &>/dev/null; then
    echo "$RESULT" | jq --arg agent "codex" --arg sandbox "$SANDBOX" --arg ts "$TIMESTAMP" \
        '. + {agent: $agent, sandbox: $sandbox, timestamp: $ts}'
else
    echo "{\"success\": true, \"output\": $(echo "$RESULT" | jq -Rs .), \"agent\": \"codex\", \"sandbox\": \"$SANDBOX\", \"timestamp\": \"$TIMESTAMP\"}"
fi
