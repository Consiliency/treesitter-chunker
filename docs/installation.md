# Installation Guide

TreeSitter Chunker supports multiple installation methods across different platforms. Choose the method that best suits your needs.

## Table of Contents

- [Quick Start](#quick-start)
- [Installation Methods](#installation-methods)
  - [PyPI (pip)](#pypi-pip)
  - [Conda](#conda)
  - [Homebrew (macOS/Linux)](#homebrew-macoslinux)
  - [Docker](#docker)
  - [From Source](#from-source)
- [Platform-Specific Instructions](#platform-specific-instructions)
  - [Windows](#windows)
  - [macOS](#macos)
  - [Linux](#linux)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

## Quick Start

The quickest way to install TreeSitter Chunker:

```bash
pip install treesitter-chunker
```

## Installation Methods

### PyPI (pip)

The recommended installation method for most users:

```bash
# Basic installation
pip install treesitter-chunker

# With visualization support
pip install treesitter-chunker[viz]

# With all optional dependencies
pip install treesitter-chunker[all]

# Development installation
pip install treesitter-chunker[dev]
```

#### Virtual Environment (Recommended)

```bash
# Create virtual environment
python -m venv venv

# Activate virtual environment
# On Windows:
venv\Scripts\activate
# On macOS/Linux:
source venv/bin/activate

# Install
pip install treesitter-chunker
```

### Conda

Install via Conda for better dependency management:

```bash
# From conda-forge channel (when available)
conda install -c conda-forge treesitter-chunker

# Or using pip within conda environment
conda create -n chunker python=3.11
conda activate chunker
pip install treesitter-chunker
```

### Homebrew (macOS/Linux)

For macOS and Linux users who prefer Homebrew:

```bash
# Add the tap (if not already added)
brew tap consiliency/treesitter-chunker

# Install
brew install treesitter-chunker
```

### Docker

Run TreeSitter Chunker in a container:

```bash
# Pull the image
docker pull ghcr.io/consiliency/treesitter-chunker:latest

# Run with local files
docker run -v $(pwd):/workspace ghcr.io/consiliency/treesitter-chunker chunk /workspace/code.py -l python

# Interactive shell
docker run -it --entrypoint /bin/bash ghcr.io/consiliency/treesitter-chunker

# Alpine-based image (smaller)
docker pull ghcr.io/consiliency/treesitter-chunker:alpine
```

#### Building Docker Image Locally

```bash
# Clone the repository
git clone https://github.com/Consiliency/treesitter-chunker.git
cd treesitter-chunker

# Build standard image
docker build -t treesitter-chunker .

# Build Alpine image
docker build -f Dockerfile.alpine -t treesitter-chunker:alpine .
```

### From Source

For development or to get the latest features:

```bash
# Clone the repository
git clone https://github.com/Consiliency/treesitter-chunker.git
cd treesitter-chunker

# Install with uv (recommended)
uv venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
uv pip install -e ".[dev]"

# Or install with pip
pip install -e ".[dev]"

# Build grammars
python scripts/fetch_grammars.py
python scripts/build_lib.py
```

## Platform-Specific Instructions

### Windows

#### Prerequisites

1. Python 3.10 or higher
2. Visual Studio Build Tools or Visual Studio 2019/2022
   - Download from: https://visualstudio.microsoft.com/downloads/
   - Install "Desktop development with C++" workload

#### Installation Steps

```powershell
# Using pip
pip install treesitter-chunker

# If you encounter issues, try:
pip install --no-binary :all: treesitter-chunker
```

#### Common Windows Issues

- **Missing C++ compiler**: Install Visual Studio Build Tools
- **DLL not found**: Install Visual C++ Redistributable
- **Permission errors**: Run as Administrator or use `--user` flag

### macOS

#### Prerequisites

1. Python 3.10 or higher
2. Xcode Command Line Tools

```bash
# Install Xcode Command Line Tools
xcode-select --install
```

#### Installation Steps

```bash
# Using Homebrew (recommended)
brew install treesitter-chunker

# Or using pip
pip install treesitter-chunker
```

#### Apple Silicon (M1/M2) Support

TreeSitter Chunker provides universal binaries for Apple Silicon:

```bash
# Native ARM64 installation
arch -arm64 pip install treesitter-chunker

# Intel emulation (if needed)
arch -x86_64 pip install treesitter-chunker
```

### Linux

#### Prerequisites

Most Linux distributions include necessary build tools. If not:

```bash
# Debian/Ubuntu
sudo apt-get update
sudo apt-get install python3-dev build-essential

# Fedora/RHEL/CentOS
sudo dnf install python3-devel gcc gcc-c++

# Arch Linux
sudo pacman -S python base-devel
```

#### Installation Steps

```bash
# Using system pip
pip install treesitter-chunker

# Using pipx for isolated installation
pipx install treesitter-chunker

# From distribution package (when available)
# Ubuntu/Debian:
sudo apt install python3-treesitter-chunker
# Fedora:
sudo dnf install python3-treesitter-chunker
```

## Verification

After installation, verify everything is working:

```bash
# Check version
treesitter-chunker --version

# List available languages
treesitter-chunker list-languages

# Test with a simple file
echo "def hello(): print('world')" > test.py
treesitter-chunker chunk test.py -l python
```

## Troubleshooting

### Common Issues

#### ImportError: No module named 'tree_sitter'

```bash
# Reinstall with updated dependencies
pip install --upgrade treesitter-chunker
```

#### Grammar compilation errors

```bash
# Manually rebuild grammars
cd $(python -c "import chunker; print(chunker.__path__[0])")
python scripts/fetch_grammars.py
python scripts/build_lib.py
```

#### ABI version mismatch

```bash
# Install compatible tree-sitter version
pip uninstall tree-sitter
pip install git+https://github.com/tree-sitter/py-tree-sitter.git
pip install --force-reinstall treesitter-chunker
```

#### Permission denied errors

```bash
# Install for current user only
pip install --user treesitter-chunker

# Or use virtual environment
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install treesitter-chunker
```

### Getting Help

If you encounter issues:

1. Check the [FAQ](https://github.com/Consiliency/treesitter-chunker/wiki/FAQ)
2. Search [existing issues](https://github.com/Consiliency/treesitter-chunker/issues)
3. Create a new issue with:
   - Platform details (OS, Python version)
   - Installation method used
   - Complete error message
   - Output of `pip list | grep tree`

## Next Steps

- Read the [User Guide](../user-guide.md) to learn how to use TreeSitter Chunker
- Check out [Examples](../examples/) for common use cases
- See [API Reference](../api-reference.md) for detailed documentation