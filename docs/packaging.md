# Packaging and Distribution Guide

This guide covers the packaging and distribution process for treesitter-chunker.

## Overview

TreeSitter Chunker is distributed through multiple channels:
- PyPI (Python Package Index)
- Conda/Conda-forge
- Homebrew (macOS/Linux)
- Docker Hub / GitHub Container Registry
- Direct downloads (GitHub Releases)

## Building Packages

### Prerequisites

Install build dependencies:
```bash
pip install -r requirements-build.txt
```

### Quick Build

Use the automated packaging script:
```bash
python scripts/package.py --clean --release
```

### Manual Build Process

#### 1. Build Grammars
```bash
python scripts/fetch_grammars.py
python scripts/build_lib.py
```

#### 2. Build Source Distribution
```bash
python -m build --sdist
```

#### 3. Build Wheels

Standard wheel:
```bash
python -m build --wheel
```

Platform-specific wheels:
```bash
python scripts/build_wheels.py --platform auto
```

Cross-platform wheels using cibuildwheel:
```bash
cibuildwheel --platform auto
```

### Platform-Specific Builds

#### Windows
```bash
scripts\build_windows.bat
```

#### macOS
```bash
./scripts/build_macos.sh
```

#### Linux (manylinux)
```bash
python scripts/build_wheels.py --platform manylinux
```

## Publishing

### PyPI

Test PyPI first:
```bash
python scripts/package.py --test-upload
```

Production PyPI:
```bash
python scripts/package.py --upload
```

Manual upload:
```bash
twine upload --repository testpypi dist/*
twine upload dist/*
```

### Docker

Build images:
```bash
docker build -t treesitter-chunker:latest .
docker build -f Dockerfile.alpine -t treesitter-chunker:alpine .
```

Push to registry:
```bash
docker push ghcr.io/consiliency/treesitter-chunker:latest
docker push ghcr.io/consiliency/treesitter-chunker:alpine
```

### Homebrew

Update formula with new version and SHA256:
```bash
# Calculate SHA256
shasum -a 256 dist/treesitter-chunker-*.tar.gz

# Update homebrew/treesitter-chunker.rb
# Submit PR to homebrew tap
```

### Conda

Update meta.yaml and submit to conda-forge:
```bash
# Update conda/meta.yaml with new version
# Submit PR to conda-forge/staged-recipes
```

## Release Process

### 1. Update Version

Update version in:
- `pyproject.toml`
- `chunker/__init__.py` (if applicable)
- `conda/meta.yaml`
- `homebrew/treesitter-chunker.rb`

### 2. Update Changelog

Update `CHANGELOG.md` with release notes.

### 3. Create Git Tag

```bash
git tag -a v0.1.0 -m "Release v0.1.0"
git push origin v0.1.0
```

### 4. GitHub Release

The GitHub Actions workflow will automatically:
1. Build all wheels and distributions
2. Create Docker images
3. Create GitHub release with artifacts
4. Upload to PyPI (if configured)

### 5. Post-Release

1. Update Homebrew formula
2. Submit conda-forge PR
3. Update documentation
4. Announce release

## Testing Packages

### Local Testing

```bash
./scripts/test_packaging.sh
```

### Test Installation

PyPI:
```bash
pip install -i https://test.pypi.org/simple/ treesitter-chunker
```

Docker:
```bash
docker run --rm treesitter-chunker:latest --version
```

### Verification

```bash
# Check imports
python -c "import chunker; print(chunker.__version__)"

# Check CLI
treesitter-chunker --version
treesitter-chunker list-languages

# Test functionality
echo "def test(): pass" | treesitter-chunker chunk - -l python
```

## Troubleshooting

### Common Issues

1. **Grammar compilation fails**
   - Ensure C/C++ compiler is installed
   - Check tree-sitter version compatibility

2. **Wheel building fails**
   - Install Visual Studio Build Tools (Windows)
   - Install Xcode Command Line Tools (macOS)
   - Use manylinux Docker image (Linux)

3. **Import errors after installation**
   - Verify grammars are included in wheel
   - Check platform compatibility
   - Reinstall with `--force-reinstall`

### Debug Commands

```bash
# Check wheel contents
unzip -l dist/*.whl | grep -E "\.so|\.dll|\.dylib"

# Verify package metadata
python -m pip show treesitter-chunker

# Test in isolated environment
python -m venv test_env
source test_env/bin/activate
pip install dist/*.whl
python -m chunker.parser
```

## Maintenance

### Updating Dependencies

1. Update `pyproject.toml`
2. Update `conda/meta.yaml`
3. Update `homebrew/treesitter-chunker.rb`
4. Test all installation methods

### Adding New Languages

1. Add grammar to `scripts/fetch_grammars.py`
2. Update language list in documentation
3. Add tests for new language
4. Rebuild all packages

### Security

- Sign releases with GPG
- Use 2FA for PyPI account
- Verify checksums in all distribution methods
- Regular dependency updates

## Resources

- [Python Packaging Guide](https://packaging.python.org/)
- [cibuildwheel Documentation](https://cibuildwheel.readthedocs.io/)
- [Homebrew Formula Cookbook](https://docs.brew.sh/Formula-Cookbook)
- [Conda-forge Documentation](https://conda-forge.org/docs/)
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/)