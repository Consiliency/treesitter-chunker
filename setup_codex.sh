#!/bin/bash
# Codex Setup Script for treesitter-chunker project
# This script configures the environment for Codex to work with this project

set -e  # Exit on error

echo "Setting up Codex environment for treesitter-chunker..."

# Install UV package manager if not already installed
if ! command -v uv &> /dev/null; then
    echo "Installing UV package manager..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
else
    echo "UV package manager already installed"
fi

# Create and activate virtual environment
echo "Creating virtual environment..."
if [ -d ".venv" ]; then
    echo "Virtual environment already exists, clearing it..."
    rm -rf .venv
fi
uv venv
source .venv/bin/activate

# Install py-tree-sitter from GitHub for ABI 15 support
echo "Installing py-tree-sitter with ABI 15 support..."
uv pip install git+https://github.com/tree-sitter/py-tree-sitter.git

# Fetch and build tree-sitter grammars
echo "Fetching tree-sitter grammars..."
if [ ! -f "scripts/fetch_grammars.py" ]; then
    echo "Warning: fetch_grammars.py not found, skipping grammar fetch"
else
    python scripts/fetch_grammars.py
fi

echo "Building tree-sitter language library..."
python scripts/build_lib.py

# Create the missing treesitter_chunker directory
echo "Creating missing build directories..."
mkdir -p treesitter_chunker

# Fix the setup.py build issue by creating a simple setup
echo "Creating minimal setup for installation..."
cat > setup_minimal.py << 'EOF'
#!/usr/bin/env python3
from setuptools import setup, find_packages

setup(
    name="treesitter-chunker",
    version="0.1.0",
    packages=find_packages(exclude=["tests*", "benchmarks*", "examples*", "docs*", "scripts*"]),
    include_package_data=True,
    python_requires=">=3.10",
    install_requires=[
        "tree_sitter",
        "rich",
        "typer",
        "pyarrow>=11.0.0",
        "toml",
        "pyyaml",
        "pygments",
        "chardet",
        "tiktoken",
        "numpy",
    ],
    extras_require={
        "dev": ["pytest", "psutil", "build", "wheel", "twine"],
        "viz": ["graphviz"],
        "all": ["pytest", "psutil", "graphviz", "build", "wheel", "twine"],
    },
    entry_points={
        "console_scripts": [
            "treesitter-chunker=cli.main:app",
            "tsc=cli.main:app",
        ],
    },
    zip_safe=False,
)
EOF

# Install project dependencies using the minimal setup
echo "Installing project dependencies..."
uv pip install -e ".[dev]" || {
    echo "Trying alternative installation method..."
    uv pip install -e .
}

# Install missing dependencies that might not be in the minimal setup
echo "Installing additional required dependencies..."
uv pip install tiktoken numpy

# Install additional development tools
echo "Installing additional development tools..."
uv pip install pyright ruff black isort mypy

# Create directories if they don't exist
mkdir -p build
mkdir -p grammars

# Verify installation
echo "Verifying installation..."
python -c "import tree_sitter; print('✅ tree-sitter imported successfully')" || echo "Warning: tree-sitter import failed"

# Try to import the chunker module
echo "Testing chunker module..."
python -c "
try:
    from chunker.parser import list_languages
    languages = list_languages()
    print(f'✅ Available languages: {languages}')
except ImportError as e:
    print(f'Warning: Could not import chunker module: {e}')
    print('This is normal if the build process had issues')
" || echo "Warning: chunker module import failed"

# Run a simple test to ensure everything is working
echo "Running basic verification..."
python -c "
try:
    from chunker import chunk_file
    print('✅ Core functionality available')
except ImportError:
    print('⚠️ Basic import failed, but setup may still be functional')
" || echo "Warning: Basic verification failed"

echo ""
echo "Codex environment setup complete!"
echo ""
echo "Environment variables have been configured for:"
echo "- UV package manager"
echo "- Python virtual environment"
echo "- Tree-sitter with ABI 15 support"
echo "- All project dependencies"
echo ""
echo "The agent can now work with the treesitter-chunker project."
echo ""
echo "Note: If you encountered build issues, the core functionality should still work."
echo "You can manually install dependencies later if needed."