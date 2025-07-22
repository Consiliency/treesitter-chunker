#!/bin/bash
# Build script for macOS (Intel and Apple Silicon)

set -e

echo "Building treesitter-chunker for macOS..."

# Detect architecture
ARCH=$(uname -m)
echo "Detected architecture: $ARCH"

# Check for Xcode Command Line Tools
if ! xcode-select -p &> /dev/null; then
    echo "Error: Xcode Command Line Tools not installed"
    echo "Please run: xcode-select --install"
    exit 1
fi

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 not found"
    echo "Please install Python 3.10 or higher"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "Using Python $PYTHON_VERSION"

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip wheel setuptools

# Install build dependencies
echo "Installing build dependencies..."
pip install build cibuildwheel delocate

# Fetch and build grammars
echo "Fetching grammars..."
python scripts/fetch_grammars.py

echo "Building grammars..."
python scripts/build_lib.py

# Build universal wheel if on Apple Silicon
if [ "$ARCH" = "arm64" ]; then
    echo "Building universal wheel for Apple Silicon..."
    
    # Set environment variables for universal build
    export ARCHFLAGS="-arch x86_64 -arch arm64"
    export _PYTHON_HOST_PLATFORM="macosx-10.9-universal2"
    
    # Build wheel
    python -m build --wheel --outdir dist
    
    # Ensure wheel is universal
    cd dist
    for wheel in *.whl; do
        if [[ $wheel != *"universal2"* ]]; then
            # Rename to universal2
            new_name=$(echo $wheel | sed 's/arm64/universal2/g' | sed 's/x86_64/universal2/g')
            if [ "$wheel" != "$new_name" ]; then
                mv "$wheel" "$new_name"
                echo "Renamed $wheel to $new_name"
            fi
        fi
    done
    cd ..
else
    echo "Building wheel for Intel Mac..."
    python -m build --wheel --outdir dist
fi

# Repair wheels using delocate
echo "Repairing wheels..."
for wheel in dist/*.whl; do
    delocate-wheel -w dist -v "$wheel"
done

# Generate checksums
echo "Generating checksums..."
cd dist
shasum -a 256 *.whl > checksums.txt
cd ..

echo
echo "Build complete! Wheels available in dist/"
echo
echo "Checksums:"
cat dist/checksums.txt
echo
echo "To install: pip install dist/treesitter_chunker-*.whl"
echo

# Deactivate virtual environment
deactivate