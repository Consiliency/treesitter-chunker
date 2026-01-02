#!/bin/bash
# Execute a web search query using Gemini CLI with grounding
# Usage: ./search.sh "your search query"

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ORCHESTRATION_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")"
QUERY="$1"
TIMESTAMP=$(date -Iseconds)

# Validate input
if [ -z "$QUERY" ]; then
    echo '{"success": false, "error": "No query provided", "agent": "gemini"}'
    exit 1
fi

# Check if gemini CLI is available
if ! command -v gemini &> /dev/null; then
    echo '{"success": false, "error": "gemini CLI not found - install with: npm install -g @google/gemini-cli", "agent": "gemini"}'
    exit 1
fi

# Log usage
"$ORCHESTRATION_DIR/monitoring/log-usage.sh" gemini --task "$QUERY" 2>/dev/null || true

# Execute Gemini with web search/grounding enabled
# Note: The exact flag may vary based on CLI version
RESULT=$(gemini -p "Search the web and answer: $QUERY" --search 2>&1) || {
    # Fallback without --search flag if not supported
    RESULT=$(gemini -p "Search the web and provide current information about: $QUERY" 2>&1) || {
        echo "{\"success\": false, \"error\": \"Gemini search failed\", \"raw\": $(echo "$RESULT" | jq -Rs .), \"agent\": \"gemini\", \"timestamp\": \"$TIMESTAMP\"}"
        exit 1
    }
}

# Format as JSON
echo "{\"success\": true, \"output\": $(echo "$RESULT" | jq -Rs .), \"agent\": \"gemini\", \"type\": \"web_search\", \"timestamp\": \"$TIMESTAMP\"}"
