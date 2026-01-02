#!/bin/bash
# Automatically launch Chrome with debugging if not already running
# This script checks if Chrome debugging is available and launches it if needed
# Designed to be called from activate-env.sh or other automation scripts

set -e

PORT="${1:-9222}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LAUNCH_SCRIPT="$SCRIPT_DIR/launch-chrome-debug.sh"

# Check if Chrome debugging endpoint is already accessible
if curl -s "http://localhost:$PORT/json/version" > /dev/null 2>&1; then
    # Chrome debugging is already running
    exit 0
fi

# Check if we should auto-launch (controlled by environment variable)
if [ "${AUTO_LAUNCH_CHROME_DEBUG:-false}" != "true" ]; then
    # Auto-launch is disabled, silently exit
    exit 0
fi

# Attempt to launch Chrome
if [ -f "$LAUNCH_SCRIPT" ]; then
    echo "🔧 Auto-launching Chrome with debugging for Playwright MCP..."
    "$LAUNCH_SCRIPT" "$PORT" > /dev/null 2>&1 || true
fi

