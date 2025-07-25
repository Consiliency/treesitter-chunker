# Distribution Component Documentation

## Overview

The Distribution Component handles package distribution across multiple platforms for the treesitter-chunker project. It implements the DistributionContract and ReleaseManagementContract to provide comprehensive distribution and release management functionality.

## Architecture

### Core Components

1. **DistributionImpl** (`chunker/distribution/manager.py`)
   - Implements the DistributionContract
   - Handles PyPI publishing, Docker image building, Homebrew formula generation, and installation verification

2. **ReleaseManagementImpl** (`chunker/distribution/release.py`)
   - Implements the ReleaseManagementContract
   - Manages version bumping, changelog updates, git tagging, and release artifact creation

### Key Features

#### PyPI Publishing
- Validates package files using twine
- Calculates SHA256 checksums for security
- Supports both PyPI and TestPyPI repositories
- Dry-run mode for testing without actual uploads

#### Docker Image Building
- Creates multi-platform Docker images
- Supports linux/amd64 and linux/arm64 platforms
- Automatically creates Dockerfile if missing
- Uses multi-stage builds for optimization

#### Homebrew Formula Generation
- Creates valid Ruby formulae for macOS distribution
- Includes all dependencies (python, tree-sitter)
- Provides test cases for formula validation
- Supports both stable releases and HEAD builds

#### Installation Verification
- Tests installations across different methods (pip, docker, homebrew, conda)
- Verifies functionality after installation
- Creates isolated test environments
- Provides detailed error reporting

#### Release Management
- Semantic version validation and comparison
- Updates version in multiple files (setup.py, pyproject.toml, __init__.py)
- Maintains changelog with proper formatting
- Creates annotated git tags
- Generates release artifacts (sdist, wheel, checksums, release notes)

## Usage Examples

### Publishing to PyPI

```python
from chunker.distribution.manager import DistributionImpl

dist = DistributionImpl()

# Dry run to test
success, info = dist.publish_to_pypi(
    package_dir=Path("dist/"),
    repository="testpypi",
    dry_run=True
)

# Actual publish
if success:
    success, info = dist.publish_to_pypi(
        package_dir=Path("dist/"),
        repository="pypi",
        dry_run=False
    )
```

### Building Docker Images

```python
# Build multi-platform image
success, image_id = dist.build_docker_image(
    tag="treesitter-chunker:latest",
    platforms=["linux/amd64", "linux/arm64"]
)
```

### Creating Homebrew Formula

```python
# Generate formula for version 1.0.0
success, formula_path = dist.create_homebrew_formula(
    version="1.0.0",
    output_path=Path("homebrew/")
)
```

### Preparing a Release

```python
from chunker.distribution.release import ReleaseManagementImpl

release = ReleaseManagementImpl()

# Prepare release with version bump and changelog
success, info = release.prepare_release(
    version="1.0.0",
    changelog="## New Features\n- Added Python 3.12 support\n- Improved performance"
)

# Create release artifacts
if success:
    artifacts = release.create_release_artifacts(
        version="1.0.0",
        output_dir=Path("dist/")
    )
```

## Integration with CI/CD

The distribution component is designed to integrate seamlessly with CI/CD pipelines:

1. **Pre-release Checks**: Validate version numbers and ensure tests pass
2. **Build Artifacts**: Create wheels and source distributions
3. **Test Installation**: Verify packages install correctly before publishing
4. **Publish**: Upload to PyPI, build Docker images, update Homebrew formula
5. **Post-release**: Verify published packages work correctly

## Error Handling

The component provides comprehensive error handling:

- Returns `(success: bool, details: dict)` tuples for all operations
- Includes detailed error messages in the details dictionary
- Validates prerequisites before attempting operations
- Provides rollback information when operations fail

## Security Considerations

1. **Package Validation**: Uses twine to check packages before upload
2. **Checksum Generation**: Creates SHA256 hashes for all artifacts
3. **Credential Management**: Relies on environment variables or .pypirc for credentials
4. **Docker Security**: Uses non-root users in container images

## Testing

The component includes comprehensive unit tests:

- Test coverage for all contract methods
- Mock external dependencies (subprocess, file system)
- Validate error handling paths
- Test both success and failure scenarios

Run tests with:
```bash
pytest tests/test_distribution_impl.py -v
```

## Future Enhancements

1. **Conda Support**: Add conda-forge distribution
2. **GPG Signing**: Sign release artifacts with GPG
3. **Release Automation**: GitHub Actions workflow for automated releases
4. **Mirror Support**: Upload to multiple PyPI mirrors
5. **Rollback Capability**: Automated rollback on failed releases