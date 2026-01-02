#!/bin/bash
# Log usage for a specific provider
# Usage: ./log-usage.sh <provider> [--task "description"] [--tokens N]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TODAY=$(date +%Y%m%d)
TIMESTAMP=$(date -Iseconds)
LOG_DIR="${HOME}/.ai-dev-kit/logs"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Parse arguments
PROVIDER=""
TASK=""
TOKENS=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --task)
            TASK="$2"
            shift 2
            ;;
        --tokens)
            TOKENS="$2"
            shift 2
            ;;
        *)
            if [ -z "$PROVIDER" ]; then
                PROVIDER="$1"
            fi
            shift
            ;;
    esac
done

if [ -z "$PROVIDER" ]; then
    echo "Usage: log-usage.sh <provider> [--task \"description\"] [--tokens N]"
    echo "Providers: claude, openai, gemini, cursor, opencode, ollama"
    exit 1
fi

# Validate provider
case "$PROVIDER" in
    claude|openai|gemini|cursor|opencode|ollama) ;;
    *)
        echo "Error: Unknown provider '$PROVIDER'"
        echo "Valid providers: claude, openai, gemini, cursor"
        exit 1
        ;;
esac

# Increment daily counter
COUNTER_FILE="$LOG_DIR/agent-calls-${PROVIDER}-${TODAY}"
if [ -f "$COUNTER_FILE" ]; then
    COUNT=$(cat "$COUNTER_FILE")
else
    COUNT=0
fi
COUNT=$((COUNT + 1))
echo "$COUNT" > "$COUNTER_FILE"

# Append to detailed log
DETAIL_LOG="$LOG_DIR/usage-detail-${TODAY}.jsonl"
echo "{\"timestamp\": \"$TIMESTAMP\", \"provider\": \"$PROVIDER\", \"task\": \"$TASK\", \"tokens\": $TOKENS, \"daily_count\": $COUNT}" >> "$DETAIL_LOG"

# Output confirmation
echo "{\"provider\": \"$PROVIDER\", \"daily_count\": $COUNT, \"logged\": true}"
