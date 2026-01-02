#!/bin/bash
# Execute a task using Ollama CLI
# Usage: ./query.sh "task description" [model]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORCHESTRATION_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
TASK="$1"
MODEL_INPUT="${2:-}"
MODEL_DEFAULT="${OLLAMA_MODEL:-llama3.2}"
MODEL="${MODEL_INPUT:-$MODEL_DEFAULT}"
TIMESTAMP=$(date -Iseconds)

if [ -z "$TASK" ]; then
  echo '{"success": false, "error": "No task provided", "agent": "ollama"}'
  exit 1
fi

if ! command -v ollama &> /dev/null; then
  echo '{"success": false, "error": "ollama CLI not found - install from https://ollama.com", "agent": "ollama"}'
  exit 1
fi

# Log usage
"$ORCHESTRATION_DIR/monitoring/log-usage.sh" ollama --task "$TASK" 2>/dev/null || true

RESULT=$(ollama run "$MODEL" "$TASK" 2>&1) || {
  echo "{\"success\": false, \"error\": \"Ollama execution failed\", \"raw\": $(echo "$RESULT" | jq -Rs .), \"agent\": \"ollama\", \"model\": \"$MODEL\", \"timestamp\": \"$TIMESTAMP\"}"
  exit 1
}

# Format as JSON
echo "{\"success\": true, \"output\": $(echo "$RESULT" | jq -Rs .), \"agent\": \"ollama\", \"model\": \"$MODEL\", \"timestamp\": \"$TIMESTAMP\"}"
