#!/bin/bash
# Codex Setup Script for treesitter-chunker project
# This script configures the environment for Codex to work with this project

set -e  # Exit on error

echo "Setting up Codex environment for treesitter-chunker..."

# Install UV package manager
echo "Installing UV package manager..."
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.cargo/bin:$PATH"

# Create and activate virtual environment
echo "Creating virtual environment..."
uv venv
source .venv/bin/activate || source .venv/Scripts/activate 2>/dev/null

# Install project dependencies
echo "Installing project dependencies..."
uv pip install -e ".[dev]"

# Install py-tree-sitter from GitHub for ABI 15 support
echo "Installing py-tree-sitter with ABI 15 support..."
uv pip install git+https://github.com/tree-sitter/py-tree-sitter.git

# Fetch and build tree-sitter grammars
echo "Fetching tree-sitter grammars..."
python scripts/fetch_grammars.py

echo "Building tree-sitter language library..."
python scripts/build_lib.py

# Install additional development tools
echo "Installing additional development tools..."
uv pip install pyright ruff black isort mypy

# Create directories if they don't exist
mkdir -p build
mkdir -p grammars

# Verify installation
echo "Verifying installation..."
python -c "import tree_sitter; print(f'tree-sitter version: {tree_sitter.__version__}')"
python -c "from chunker.parser import list_languages; print(f'Available languages: {list_languages()}')"

# Run tests to ensure everything is working
echo "Running tests to verify setup..."
python -m pytest -xvs tests/test_parser.py::TestParserAPI::test_get_parser_basic || true

echo "Codex environment setup complete!"
echo ""
echo "Environment variables have been configured for:"
echo "- UV package manager"
echo "- Python virtual environment"
echo "- Tree-sitter with ABI 15 support"
echo "- All project dependencies"
echo ""
echo "The agent can now work with the treesitter-chunker project."