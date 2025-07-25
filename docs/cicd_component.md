# CI/CD Pipeline Component

## Overview

The CI/CD Pipeline component provides GitHub Actions-based continuous integration and deployment functionality for the treesitter-chunker project. It implements the `CICDPipelineContract` to provide workflow validation, test matrix execution, distribution building, and release automation.

## Architecture

### Core Classes

- **CICDPipelineImpl**: Main implementation of the CI/CD pipeline functionality
- **WorkflowValidator**: Advanced validation utilities for GitHub Actions workflows

### Key Features

1. **Workflow Validation**
   - YAML syntax validation
   - GitHub Actions schema validation
   - Best practices enforcement
   - Warning for deprecated or non-standard patterns

2. **Test Matrix Execution**
   - Multi-platform testing (Linux, Windows, macOS)
   - Multiple Python version support
   - Parallel test execution
   - Result aggregation and reporting

3. **Distribution Building**
   - Platform-specific wheel generation
   - Source distribution creation
   - Checksum generation for all artifacts
   - Build log capture and reporting

4. **Release Automation**
   - GitHub release creation
   - Artifact upload management
   - Version tag management
   - Changelog generation support

## Usage

### Basic Usage

```python
from chunker.cicd.pipeline import CICDPipelineImpl

# Create pipeline instance
pipeline = CICDPipelineImpl()

# Validate a workflow
valid, errors = pipeline.validate_workflow_syntax(Path(".github/workflows/test.yml"))
if not valid:
    print(f"Workflow validation errors: {errors}")

# Run test matrix
results = pipeline.run_test_matrix(
    python_versions=["3.8", "3.9", "3.10"],
    platforms=["ubuntu-latest", "windows-latest", "macos-latest"]
)

# Build distributions
dist_info = pipeline.build_distribution(
    version="1.0.0",
    platforms=["linux", "darwin", "win32"]
)

# Create release
release_info = pipeline.create_release(
    version="1.0.0",
    artifacts=[Path("dist/package-1.0.0.whl")],
    changelog="## New Features\n- Initial release"
)
```

### Advanced Workflow Validation

```python
from chunker.cicd.workflow_validator import WorkflowValidator, validate_all_workflows

# Validate single workflow with detailed analysis
validator = WorkflowValidator()
is_valid, errors, warnings = validator.validate_file(Path("workflow.yml"))

# Validate all workflows in directory
results = validate_all_workflows(Path(".github/workflows"))
for workflow, (is_valid, errors, warnings) in results.items():
    print(f"{workflow}: {'Valid' if is_valid else 'Invalid'}")
    if warnings:
        print(f"  Warnings: {warnings}")
```

## GitHub Actions Workflows

The component includes three main workflow files:

### test.yml
- Runs on push, pull request, and manual dispatch
- Tests across multiple Python versions and platforms
- Includes linting, type checking, and test coverage
- Caches dependencies for faster runs

### build.yml
- Triggered by version tags or manual dispatch
- Builds platform-specific wheels
- Creates manylinux wheels for Linux compatibility
- Generates source distributions
- Calculates checksums for all artifacts

### release.yml
- Creates GitHub releases with changelog
- Triggers build workflow
- Publishes to PyPI (with Test PyPI validation)
- Builds and pushes Docker images
- Manages version tags

## Integration with Other Components

The CI/CD component integrates with:

- **Developer Tooling**: Pre-commit checks before CI runs
- **Build System**: For compiling platform-specific artifacts
- **Distribution**: For publishing to package repositories
- **Debug Tools**: For performance analysis in CI environment

## Testing

The component includes comprehensive unit tests:

```bash
# Run CI/CD unit tests
pytest tests/test_cicd_pipeline.py

# Run workflow validator tests
pytest tests/test_workflow_validator.py

# Run integration tests
pytest tests/test_phase15_integration.py -k cicd
```

## Configuration

### Environment Variables

- `GITHUB_TOKEN`: Required for release creation
- `PYPI_API_TOKEN`: Required for PyPI publishing
- `DOCKER_USERNAME`/`DOCKER_TOKEN`: For Docker Hub publishing

### Workflow Customization

Workflows can be customized by modifying the YAML files in `.github/workflows/`. The validator ensures changes maintain GitHub Actions compatibility.

## Best Practices

1. **Always validate workflows** before committing changes
2. **Use matrix builds** to test across multiple environments
3. **Generate checksums** for all distribution artifacts
4. **Test on Test PyPI** before publishing to production
5. **Include comprehensive changelogs** in releases

## Troubleshooting

### Common Issues

1. **Workflow validation failures**
   - Check YAML syntax
   - Ensure all required fields are present
   - Verify job and step structure

2. **Test matrix failures**
   - Review platform-specific issues
   - Check Python version compatibility
   - Examine error logs for specific failures

3. **Distribution build errors**
   - Verify build dependencies
   - Check platform compatibility
   - Ensure version format is correct

4. **Release creation failures**
   - Verify GitHub token permissions
   - Check artifact paths exist
   - Ensure version doesn't already exist