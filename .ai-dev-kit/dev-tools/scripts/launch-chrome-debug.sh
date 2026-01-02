#!/bin/bash
# Launch Chrome with remote debugging enabled for Playwright MCP
# Usage: ./launch-chrome-debug.sh [port]
#
# This script launches Chrome on Windows from WSL2 with debugging enabled.
# The default port is 9222, which matches the Playwright MCP configuration.

set -e

# Check if Chrome is already running with debugging
if curl -s "http://localhost:${1:-9222}/json/version" > /dev/null 2>&1; then
    echo "✅ Chrome debugging endpoint is already accessible"
    echo "   No need to launch Chrome again."
    exit 0
fi

PORT="${1:-9222}"
USER_DATA_DIR="C:\\temp\\chrome-debug-profile"

# Detect if running under WSL
if [ -f /proc/version ] && grep -qi "microsoft" /proc/version 2>/dev/null; then
    IS_WSL2=true
else
    IS_WSL2=false
    echo "⚠️  Not running in WSL2. Attempting Linux/macOS Chrome launch..."
    # Try to find Chrome on Linux/macOS
    if command -v google-chrome &> /dev/null; then
        google-chrome --remote-debugging-port="$PORT" --user-data-dir="/tmp/chrome-debug-profile" > /dev/null 2>&1 &
        echo "✅ Chrome launched (Linux/macOS)"
        sleep 2
        if curl -s "http://localhost:$PORT/json/version" > /dev/null 2>&1; then
            echo "✅ Chrome debugging endpoint is accessible"
        fi
        exit 0
    elif command -v chromium-browser &> /dev/null; then
        chromium-browser --remote-debugging-port="$PORT" --user-data-dir="/tmp/chrome-debug-profile" > /dev/null 2>&1 &
        echo "✅ Chromium launched (Linux)"
        sleep 2
        if curl -s "http://localhost:$PORT/json/version" > /dev/null 2>&1; then
            echo "✅ Chromium debugging endpoint is accessible"
        fi
        exit 0
    else
        echo "❌ Chrome/Chromium not found. Please install Google Chrome."
        exit 1
    fi
fi

# Find Chrome executable
CHROME_PATHS=(
    "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"
    "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe"
    "/mnt/c/Users/*/AppData/Local/Google/Chrome/Application/chrome.exe"
)

CHROME_EXE=""
for path in "${CHROME_PATHS[@]}"; do
    # Expand glob patterns
    for expanded in $path; do
        if [ -f "$expanded" ]; then
            CHROME_EXE="$expanded"
            break 2
        fi
    done
done

if [ -z "$CHROME_EXE" ]; then
    echo "❌ Chrome not found. Please install Google Chrome on Windows."
    echo ""
    echo "Alternatively, launch Chrome manually with:"
    echo "  chrome.exe --remote-debugging-port=$PORT --user-data-dir=$USER_DATA_DIR"
    exit 1
fi

# Create user data directory on Windows if it doesn't exist
USER_DATA_DIR_WSL="/mnt/c/temp/chrome-debug-profile"
mkdir -p "$USER_DATA_DIR_WSL"

echo "🚀 Launching Chrome with remote debugging on port $PORT..."
echo "   User data directory: $USER_DATA_DIR"
echo ""

# Launch Chrome with debugging enabled
"$CHROME_EXE" \
    --remote-debugging-port="$PORT" \
    --user-data-dir="$USER_DATA_DIR" \
    > /dev/null 2>&1 &

CHROME_PID=$!
echo "✅ Chrome launched (PID: $CHROME_PID)"
echo ""
echo "Verifying connection..."

# Wait a moment for Chrome to start
sleep 2

# Test the CDP endpoint
if curl -s "http://localhost:$PORT/json/version" > /dev/null 2>&1; then
    echo "✅ Chrome debugging endpoint is accessible at http://localhost:$PORT"
    echo ""
    echo "You can now use Playwright MCP with this Chrome instance."
    echo "To verify, visit: http://localhost:$PORT/json/version"
else
    echo "⚠️  Chrome debugging endpoint not yet accessible."
    echo "   This may be normal - Chrome may need a few more seconds to start."
    echo "   Try visiting http://localhost:$PORT/json/version in a few seconds."
fi

