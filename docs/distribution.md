# Distribution Component Documentation

The Distribution component handles packaging and distributing the treesitter-chunker across multiple platforms and package managers.

## Overview

The distribution system provides:
- PyPI/TestPyPI publishing
- Docker image building with multi-platform support
- Homebrew formula generation for macOS
- Release management with version bumping
- Installation verification across all platforms

## Components

### PyPI Publisher

Handles uploading packages to PyPI and TestPyPI using twine.

```python
from chunker.distribution import PyPIPublisher

publisher = PyPIPublisher()

# Dry run to validate packages
success, info = publisher.publish(
    package_dir=Path("dist"),
    repository="testpypi",
    dry_run=True
)

# Actual upload
success, info = publisher.publish(
    package_dir=Path("dist"),
    repository="pypi"
)
```

**Features:**
- Package validation before upload
- Support for PyPI and TestPyPI
- Credential checking (.pypirc or environment variables)
- Dry run mode for testing

### Docker Builder

Builds Docker images with support for multiple platforms.

```python
from chunker.distribution import DockerBuilder

builder = DockerBuilder()

# Single platform build
success, image_id = builder.build_image(
    tag="treesitter-chunker:latest",
    platforms=["linux/amd64"]
)

# Multi-platform build (requires buildx)
success, image_id = builder.build_image(
    tag="treesitter-chunker:latest",
    platforms=["linux/amd64", "linux/arm64"]
)
```

**Features:**
- Single and multi-platform builds
- Automatic buildx detection and usage
- Docker daemon verification
- Image verification after build

### Homebrew Formula Generator

Creates Homebrew formulas for macOS distribution.

```python
from chunker.distribution import HomebrewFormulaGenerator

generator = HomebrewFormulaGenerator()

# Generate formula
success, formula_path = generator.generate_formula(
    version="1.0.0",
    output_path=Path("homebrew/")
)

# Update SHA256 after package upload
generator.update_sha256(
    formula_path,
    "https://files.pythonhosted.org/packages/.../treesitter-chunker-1.0.0.tar.gz"
)
```

**Features:**
- Automatic formula generation
- Package metadata extraction
- SHA256 hash updates
- Formula validation

### Release Manager

Manages the release process including version bumping and changelog updates.

```python
from chunker.distribution import ReleaseManager

manager = ReleaseManager()

# Prepare a new release
success, info = manager.prepare_release(
    version="1.0.0",
    changelog="Initial stable release with all features"
)

# Create release artifacts
artifacts = manager.create_release_artifacts(
    version="1.0.0",
    output_dir=Path("dist")
)
```

**Features:**
- Version validation and bumping
- Updates version in multiple files
- Changelog management
- Git tag creation
- Build artifact generation
- Checksum generation

### Installation Verifier

Verifies installations work correctly across different platforms and methods.

```python
from chunker.distribution import InstallationVerifier

verifier = InstallationVerifier()

# Verify pip installation
success, details = verifier.verify_installation(
    method="pip",
    platform="linux"
)

# Verify Docker installation
success, details = verifier.verify_installation(
    method="docker",
    platform="linux/amd64"
)
```

**Supported methods:**
- `pip`: Creates virtual environment and tests installation
- `conda`: Creates conda environment and tests
- `docker`: Runs container and verifies functionality
- `homebrew`: Tests brew installation on macOS

### Main Distributor

The main distributor class implements both `DistributionContract` and `ReleaseManagementContract`.

```python
from chunker.distribution import Distributor

distributor = Distributor()

# Full release workflow
results = distributor.full_release_workflow(
    version="1.0.0",
    changelog="Major release",
    publish=True  # Actually publish to channels
)
```

## Configuration

### PyPI Credentials

Configure PyPI credentials using one of:

1. Environment variables:
   ```bash
   export TWINE_USERNAME=__token__
   export TWINE_PASSWORD=pypi-your-api-token
   ```

2. `.pypirc` file:
   ```ini
   [pypi]
   username = __token__
   password = pypi-your-api-token

   [testpypi]
   username = __token__
   password = pypi-your-test-token
   ```

### Docker Requirements

- Docker daemon must be running
- For multi-platform builds, Docker Buildx is required
- Dockerfile must exist in project root

### Homebrew Requirements

- Formula follows Homebrew conventions
- Package must be available on PyPI
- SHA256 hash must be updated after package upload

## Error Handling

All methods return a tuple of `(success: bool, info: dict)` where:
- `success`: Whether the operation succeeded
- `info`: Detailed information including errors, warnings, and results

Example error handling:

```python
success, info = distributor.publish_to_pypi(package_dir)
if not success:
    print(f"Publishing failed: {info['error']}")
    # Handle specific errors
    if "twine not found" in info['error']:
        print("Please install twine: pip install twine")
```

## Testing

The distribution component includes comprehensive unit tests:

```bash
# Run all distribution tests
python -m pytest tests/unit/distribution/

# Run integration tests
python -m pytest tests/test_phase13_distribution_real.py
```

## Best Practices

1. **Always test locally first**:
   - Use TestPyPI before PyPI
   - Use dry run mode for validation
   - Test Docker builds locally

2. **Version management**:
   - Follow semantic versioning
   - Update changelog for every release
   - Create git tags for releases

3. **Security**:
   - Use API tokens for PyPI
   - Never commit credentials
   - Sign release artifacts when possible

4. **Platform support**:
   - Test on all target platforms
   - Provide platform-specific packages
   - Document platform requirements