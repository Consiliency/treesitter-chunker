#!/bin/bash
# Setup environment for a worktree

echo "Setting up environment for worktree: $(pwd)"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
uv venv

# Activate it
echo "Activating virtual environment..."
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
uv pip install -e ".[dev]"

# Install py-tree-sitter from GitHub for ABI 15 support
echo "Installing py-tree-sitter from GitHub..."
uv pip install git+https://github.com/tree-sitter/py-tree-sitter.git

# Fetch grammars
echo "Fetching grammars..."
python scripts/fetch_grammars.py

# Build the language library
echo "Building language library..."
python scripts/build_lib.py

echo ""
echo "Environment setup complete!"
echo ""
echo "To activate this environment in the future, run:"
echo "  source .venv/bin/activate"
echo ""
echo "You can now start Claude Code in this directory with:"
echo '  claude "Your task description"'