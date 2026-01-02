#!/bin/bash
# Execute a task using OpenCode CLI
# Usage: ./execute.sh "task description" [model]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORCHESTRATION_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
TASK="$1"
MODEL_INPUT="${2:-}"
MODEL_DEFAULT="${OPENCODE_MODEL:-anthropic/claude-sonnet-4-5}"
MODEL="${MODEL_INPUT:-$MODEL_DEFAULT}"
TIMESTAMP=$(date -Iseconds)

if [ -z "$TASK" ]; then
  echo '{"success": false, "error": "No task provided", "agent": "opencode"}'
  exit 1
fi

if ! command -v opencode &> /dev/null; then
  echo '{"success": false, "error": "opencode CLI not found - install with: npm install -g opencode-ai", "agent": "opencode"}'
  exit 1
fi

# Log usage
"$ORCHESTRATION_DIR/monitoring/log-usage.sh" opencode --task "$TASK" 2>/dev/null || true

RESULT=$(opencode run --model "$MODEL" "$TASK" 2>&1) || {
  echo "{\"success\": false, \"error\": \"OpenCode execution failed\", \"raw\": $(echo "$RESULT" | jq -Rs .), \"agent\": \"opencode\", \"model\": \"$MODEL\", \"timestamp\": \"$TIMESTAMP\"}"
  exit 1
}

# Format as JSON
echo "{\"success\": true, \"output\": $(echo "$RESULT" | jq -Rs .), \"agent\": \"opencode\", \"model\": \"$MODEL\", \"timestamp\": \"$TIMESTAMP\"}"
