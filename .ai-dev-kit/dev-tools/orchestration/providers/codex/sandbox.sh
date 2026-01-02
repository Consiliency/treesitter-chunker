#!/bin/bash
# Execute a task in Codex sandbox mode (read-only, isolated)
# Usage: ./sandbox.sh "task description"

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Forward to execute.sh with read-only sandbox
exec "$SCRIPT_DIR/execute.sh" "$1" "read-only"
