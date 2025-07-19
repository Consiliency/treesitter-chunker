#!/bin/bash
# Script to run the integration coordinator setup from the main repository

# Ensure we're in the main repository
cd /home/jenner/code/treesitter-chunker

# Do a dry run first
echo "=== Running dry-run to preview actions ==="
uv run python -m tests.integration.run_coordinator \
  --setup-worktrees \
  --pull-coordinator \
  --dry-run

# Ask user to continue
echo -e "\n=== Do you want to proceed with the actual setup? (y/n) ==="
read -r response

if [[ "$response" =~ ^([yY][eE][sS]|[yY])$ ]]; then
    echo -e "\n=== Running actual setup ==="
    uv run python -m tests.integration.run_coordinator \
      --setup-worktrees \
      --pull-coordinator
    
    echo -e "\n=== Setup complete! Next steps: ==="
    echo "1. Check worktree status: git worktree list"
    echo "2. Verify setup: uv run python -m tests.integration.run_coordinator --dry-run"
    echo "3. Run tests: uv run python -m tests.integration.run_coordinator"
else
    echo "Setup cancelled."
fi