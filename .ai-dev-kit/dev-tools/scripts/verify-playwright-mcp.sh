#!/bin/bash
# Verify Playwright MCP setup for WSL2 environment
# Checks all prerequisites and configuration
#
# Usage:
#   ./verify-playwright-mcp.sh              # Human-readable output
#   ./verify-playwright-mcp.sh --json      # JSON output for programmatic use
#   ./verify-playwright-mcp.sh --auto-launch # Attempt to launch Chrome if not running
#
# Exit codes:
#   0 = Playwright MCP ready to use
#   1 = Not configured or missing dependencies
#   2 = Chrome debugging endpoint not running

# Don't use set -e for JSON mode - we want to collect all status info
if [ "$1" != "--json" ] && [ "$1" != "--auto-launch" ]; then
    set -e
fi

JSON_OUTPUT=false
AUTO_LAUNCH=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --json)
            JSON_OUTPUT=true
            shift
            ;;
        --auto-launch)
            AUTO_LAUNCH=true
            shift
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

# Initialize status variables
NPX_AVAILABLE=false
MCP_AVAILABLE=false
MCP_CONFIGURED=false
CDP_ENDPOINT=""
CHROME_DEBUGGING_ACCESSIBLE=false
CHROME_FOUND=false
IS_WSL2=false
ERRORS=0
WARNINGS=0

# Helper function for output
output() {
    if [ "$JSON_OUTPUT" = true ]; then
        return  # JSON output handled separately
    else
        echo "$@"
    fi
}

# Check 1: npx availability
if [ "$JSON_OUTPUT" != true ]; then
    output "🔍 Verifying Playwright MCP Setup"
    output "=================================="
    output ""
    output "1. Checking npx availability..."
fi

if command -v npx &> /dev/null; then
    NPX_VERSION=$(npx --version)
    NPX_AVAILABLE=true
    if [ "$JSON_OUTPUT" != true ]; then
        output "   ✅ npx found (version: $NPX_VERSION)"
    fi
else
    if [ "$JSON_OUTPUT" != true ]; then
        output "   ❌ npx not found. Install Node.js: https://nodejs.org/"
    fi
    ((ERRORS++))
fi

if [ "$JSON_OUTPUT" != true ]; then
    output ""
fi

# Check 2: Playwright MCP package
if [ "$JSON_OUTPUT" != true ]; then
    output "2. Checking Playwright MCP package..."
fi

if npx -y @playwright/mcp@latest --version &> /dev/null; then
    MCP_VERSION=$(npx -y @playwright/mcp@latest --version 2>&1 | head -1)
    MCP_AVAILABLE=true
    if [ "$JSON_OUTPUT" != true ]; then
        output "   ✅ Playwright MCP available ($MCP_VERSION)"
    fi
else
    if [ "$JSON_OUTPUT" != true ]; then
        output "   ❌ Cannot access @playwright/mcp package"
    fi
    ((ERRORS++))
fi

if [ "$JSON_OUTPUT" != true ]; then
    output ""
fi

# Check 3: MCP configuration file
if [ "$JSON_OUTPUT" != true ]; then
    output "3. Checking .mcp.json configuration..."
fi

if [ -f ".mcp.json" ]; then
    if grep -q '"playwright"' .mcp.json; then
        PLAYWRIGHT_BLOCK=$(grep -A 5 '"playwright"' .mcp.json | head -6)
        if echo "$PLAYWRIGHT_BLOCK" | grep -q '"_disabled".*true'; then
            if [ "$JSON_OUTPUT" != true ]; then
                output "   ⚠️  Playwright MCP is configured but disabled"
            fi
            ((WARNINGS++))
        else
            MCP_CONFIGURED=true
            if [ "$JSON_OUTPUT" != true ]; then
                output "   ✅ Playwright MCP is configured in .mcp.json"
            fi

            # Check for CDP endpoint
            if grep -q "cdp-endpoint" .mcp.json; then
                CDP_ENDPOINT=$(grep -A 3 '"playwright"' .mcp.json | grep -o '"http://[^"]*"' | head -1 | tr -d '"')
                if [ -n "$CDP_ENDPOINT" ]; then
                    if [ "$JSON_OUTPUT" != true ]; then
                        output "   ✅ CDP endpoint configured: $CDP_ENDPOINT"
                    fi
                else
                    if [ "$JSON_OUTPUT" != true ]; then
                        output "   ⚠️  CDP endpoint not found in configuration"
                    fi
                    ((WARNINGS++))
                fi
            else
                if [ "$JSON_OUTPUT" != true ]; then
                    output "   ⚠️  CDP endpoint not found in configuration"
                fi
                ((WARNINGS++))
            fi
        fi
    else
        if [ "$JSON_OUTPUT" != true ]; then
            output "   ⚠️  Playwright MCP is not configured in .mcp.json"
        fi
        ((WARNINGS++))
    fi
else
    if [ "$JSON_OUTPUT" != true ]; then
        output "   ❌ .mcp.json not found"
    fi
    ((ERRORS++))
fi

if [ "$JSON_OUTPUT" != true ]; then
    output ""
fi

# Check 4: WSL2 detection
if [ "$JSON_OUTPUT" != true ]; then
    output "4. Checking environment..."
fi

if [ -f /proc/version ] && grep -qi "microsoft" /proc/version 2>/dev/null; then
    IS_WSL2=true
    if [ "$JSON_OUTPUT" != true ]; then
        output "   ✅ WSL2 detected"
    fi
else
    if [ "$JSON_OUTPUT" != true ]; then
        output "   ℹ️  Not running in WSL2 (Linux/macOS detected)"
    fi
fi

if [ "$JSON_OUTPUT" != true ]; then
    output ""
fi

# Check 5: Chrome debugging endpoint
if [ "$IS_WSL2" = true ]; then
    if [ "$JSON_OUTPUT" != true ]; then
        output "5. Checking Chrome debugging endpoint..."
    fi

    # Get Windows host IP for NAT mode fallback
    WINDOWS_HOST_IP=""
    if [ -f /etc/resolv.conf ]; then
        WINDOWS_HOST_IP=$(grep nameserver /etc/resolv.conf | awk '{print $2}' | head -1)
    fi

    # Try localhost first (mirrored mode), then Windows host IP (NAT mode)
    CHROME_ENDPOINT=""
    if curl -s "http://localhost:9222/json/version" > /dev/null 2>&1; then
        CHROME_ENDPOINT="http://localhost:9222"
        CHROME_DEBUGGING_ACCESSIBLE=true
    elif [ -n "$WINDOWS_HOST_IP" ] && curl -s "http://$WINDOWS_HOST_IP:9222/json/version" > /dev/null 2>&1; then
        CHROME_ENDPOINT="http://$WINDOWS_HOST_IP:9222"
        CHROME_DEBUGGING_ACCESSIBLE=true
        if [ "$JSON_OUTPUT" != true ]; then
            output "   ⚠️  Port mirroring not enabled - using Windows host IP: $WINDOWS_HOST_IP"
            output "   💡 Consider enabling WSL2 port mirroring for better compatibility"
        fi
    fi

    if [ "$CHROME_DEBUGGING_ACCESSIBLE" = true ]; then
        CHROME_INFO=$(curl -s "$CHROME_ENDPOINT/json/version" 2>/dev/null | head -1)
        if [ "$JSON_OUTPUT" != true ]; then
            output "   ✅ Chrome debugging endpoint is accessible at $CHROME_ENDPOINT"
            output "   ℹ️  Chrome info: $CHROME_INFO"
        fi
    else
        # Try auto-launch if enabled
        if [ "$AUTO_LAUNCH" = true ]; then
            SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
            LAUNCH_SCRIPT="$SCRIPT_DIR/launch-chrome-debug.sh"
            if [ -f "$LAUNCH_SCRIPT" ]; then
                if [ "$JSON_OUTPUT" != true ]; then
                    output "   🔧 Attempting to launch Chrome with debugging..."
                fi
                "$LAUNCH_SCRIPT" 9222 > /dev/null 2>&1 || true
                sleep 3
                # Re-check after launch attempt
                if curl -s "http://localhost:9222/json/version" > /dev/null 2>&1; then
                    CHROME_DEBUGGING_ACCESSIBLE=true
                    if [ "$JSON_OUTPUT" != true ]; then
                        output "   ✅ Chrome debugging endpoint is now accessible"
                    fi
                fi
            fi
        fi

        if [ "$CHROME_DEBUGGING_ACCESSIBLE" = false ]; then
            if [ "$JSON_OUTPUT" != true ]; then
                output "   ❌ Chrome debugging endpoint not accessible"
                output "      Tried: http://localhost:9222"
                if [ -n "$WINDOWS_HOST_IP" ]; then
                    output "      Tried: http://$WINDOWS_HOST_IP:9222"
                fi
                output "      Launch Chrome with: ./dev-tools/scripts/launch-chrome-debug.sh"
                output "      Or manually from Windows PowerShell:"
                output "        & \"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe\" --remote-debugging-port=9222 --user-data-dir=C:\\temp\\chrome-debug-profile"
            fi
            ((ERRORS++))
        fi
    fi

    if [ "$JSON_OUTPUT" != true ]; then
        output ""
    fi

    # Check 6: Chrome executable
    if [ "$JSON_OUTPUT" != true ]; then
        output "6. Checking Chrome installation..."
    fi

    CHROME_PATHS=(
        "/mnt/c/Program Files/Google/Chrome/Application/chrome.exe"
        "/mnt/c/Program Files (x86)/Google/Chrome/Application/chrome.exe"
    )

    for path in "${CHROME_PATHS[@]}"; do
        if [ -f "$path" ]; then
            CHROME_FOUND=true
            if [ "$JSON_OUTPUT" != true ]; then
                output "   ✅ Chrome found at: $path"
            fi
            break
        fi
    done

    if [ "$CHROME_FOUND" = false ]; then
        if [ "$JSON_OUTPUT" != true ]; then
            output "   ⚠️  Chrome not found in standard locations"
            output "      Install Google Chrome on Windows or use a custom path"
        fi
        ((WARNINGS++))
    fi
else
    if [ "$JSON_OUTPUT" != true ]; then
        output "5. Skipping Chrome check (not WSL2)"
        output ""
    fi
fi

# Generate JSON output if requested
if [ "$JSON_OUTPUT" = true ]; then
    READY_STATUS="false"
    if [ $ERRORS -eq 0 ]; then
        READY_STATUS="true"
    fi

    EXIT_CODE=0
    if [ $ERRORS -gt 0 ]; then
        if [ "$CHROME_DEBUGGING_ACCESSIBLE" = false ] && [ "$IS_WSL2" = true ]; then
            EXIT_CODE=2
        else
            EXIT_CODE=1
        fi
    fi

    cat <<EOF
{
  "npx_available": $NPX_AVAILABLE,
  "mcp_available": $MCP_AVAILABLE,
  "mcp_configured": $MCP_CONFIGURED,
  "cdp_endpoint": "$CDP_ENDPOINT",
  "chrome_debugging_accessible": $CHROME_DEBUGGING_ACCESSIBLE,
  "chrome_found": $CHROME_FOUND,
  "is_wsl2": $IS_WSL2,
  "errors": $ERRORS,
  "warnings": $WARNINGS,
  "ready": $READY_STATUS
}
EOF
    exit $EXIT_CODE
fi

# Human-readable summary
output "=================================="
output "Summary:"
output "  Errors: $ERRORS"
output "  Warnings: $WARNINGS"
output ""

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    output "✅ All checks passed! Playwright MCP is ready to use."
    exit 0
elif [ $ERRORS -eq 0 ]; then
    output "⚠️  Setup complete with warnings. Review above for details."
    exit 0
else
    output "❌ Setup incomplete. Please fix the errors above."
    # Return exit code 2 if Chrome debugging is the issue, 1 otherwise
    if [ "$CHROME_DEBUGGING_ACCESSIBLE" = false ] && [ "$IS_WSL2" = true ]; then
        exit 2
    else
        exit 1
    fi
fi
