#!/bin/bash
# Test packaging process for treesitter-chunker

set -e

echo "Testing packaging process..."

# Clean previous builds
echo "Cleaning previous builds..."
rm -rf dist build *.egg-info

# Install build dependencies
echo "Installing build dependencies..."
pip install -r requirements-build.txt

# Build grammars
echo "Building grammars..."
python scripts/fetch_grammars.py
python scripts/build_lib.py

# Build source distribution
echo "Building source distribution..."
python -m build --sdist

# Build wheel
echo "Building wheel..."
python -m build --wheel

# List built artifacts
echo
echo "Built artifacts:"
ls -lh dist/

# Test installation in a temporary virtual environment
echo
echo "Testing installation..."
TEMP_DIR=$(mktemp -d)
cd "$TEMP_DIR"

# Create test virtual environment
python -m venv test_env
source test_env/bin/activate

# Install the package
pip install "$OLDPWD"/dist/*.whl

# Test basic functionality
echo "Testing basic import..."
python -c "import chunker; print('Import successful')"

echo "Testing CLI..."
treesitter-chunker --version
treesitter-chunker --help

# Create a test file
echo "def test(): pass" > test.py

echo "Testing chunking..."
treesitter-chunker chunk test.py -l python

# Cleanup
deactivate
cd "$OLDPWD"
rm -rf "$TEMP_DIR"

echo
echo "Packaging test completed successfully!"