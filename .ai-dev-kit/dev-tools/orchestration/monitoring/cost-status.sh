#!/bin/bash
# Display current usage status across all AI providers
# Usage: ./cost-status.sh [--json]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/../config.json"
TODAY=$(date +%Y%m%d)
LOG_DIR="${HOME}/.ai-dev-kit/logs"

# Ensure log directory exists
mkdir -p "$LOG_DIR"

# Parse arguments
OUTPUT_JSON=false
if [[ "$1" == "--json" ]]; then
    OUTPUT_JSON=true
fi

# Read config for provider settings
get_daily_max() {
    local provider=$1
    if command -v jq &> /dev/null && [ -f "$CONFIG_FILE" ]; then
        jq -r ".providers.${provider}.daily_max // 100" "$CONFIG_FILE"
    else
        # Defaults if jq not available
        case "$provider" in
            claude) echo 500 ;;
            openai) echo 800 ;;
            gemini) echo 1000 ;;
            cursor) echo 50 ;;
            opencode) echo 300 ;;
            ollama) echo 0 ;;
            *) echo 100 ;;
        esac
    fi
}

get_tier_name() {
    local provider=$1
    case "$provider" in
        claude) echo "Max 20x" ;;
        openai) echo "Pro" ;;
        gemini) echo "Ultra" ;;
        cursor) echo "Pro" ;;
        opencode) echo "Flex" ;;
        ollama) echo "Local" ;;
        *) echo "Unknown" ;;
    esac
}

get_usage() {
    local provider=$1
    local counter_file="$LOG_DIR/agent-calls-${provider}-${TODAY}"
    if [ -f "$counter_file" ]; then
        cat "$counter_file"
    else
        echo 0
    fi
}

build_progress_bar() {
    local pct=$1
    local width=20
    local filled=$((pct * width / 100))
    local empty=$((width - filled))

    local bar=""
    for ((i=0; i<filled; i++)); do bar+="█"; done
    for ((i=0; i<empty; i++)); do bar+="░"; done
    echo "$bar"
}

get_status_icon() {
    local pct=$1
    if [ "$pct" -ge 90 ]; then
        echo "🔴"
    elif [ "$pct" -ge 70 ]; then
        echo "🟡"
    else
        echo "🟢"
    fi
}

# JSON output
if $OUTPUT_JSON; then
    echo "{"
    echo '  "timestamp": "'$(date -Iseconds)'",'
    echo '  "providers": {'

    first=true
    for provider in claude openai gemini cursor opencode ollama; do
        max=$(get_daily_max "$provider")
        calls=$(get_usage "$provider")
        tier=$(get_tier_name "$provider")

        if [ "$max" -gt 0 ]; then
            pct=$((calls * 100 / max))
        else
            pct=0
        fi

        if ! $first; then echo ","; fi
        first=false

        echo -n "    \"$provider\": {\"calls\": $calls, \"max\": $max, \"pct\": $pct, \"tier\": \"$tier\"}"
    done

    echo ""
    echo "  }"
    echo "}"
    exit 0
fi

# Human-readable output
echo "═══════════════════════════════════════════════════════════════"
echo "  Multi-Agent Usage Status - $(date '+%Y-%m-%d %H:%M')"
echo "═══════════════════════════════════════════════════════════════"
echo ""

for provider in claude openai gemini cursor opencode ollama; do
    max=$(get_daily_max "$provider")
    calls=$(get_usage "$provider")
    tier=$(get_tier_name "$provider")

    if [ "$max" -gt 0 ]; then
        pct=$((calls * 100 / max))
    else
        pct=0
    fi

    bar=$(build_progress_bar "$pct")
    icon=$(get_status_icon "$pct")

    printf "  %s %-8s [%s] %4d/%-4d (%3d%%) - %s\n" \
        "$icon" "$provider" "$bar" "$calls" "$max" "$pct" "$tier"
done

echo ""
echo "───────────────────────────────────────────────────────────────"
echo "  Legend: 🟢 Available  🟡 Warning (>70%)  🔴 Critical (>90%)"
echo "  Counters reset daily. 5-hour windows reset independently."
echo "═══════════════════════════════════════════════════════════════"
