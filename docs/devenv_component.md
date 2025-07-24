# Development Environment Component

## Overview

The Development Environment Component provides comprehensive tools for maintaining code quality, setting up development environments, and generating CI/CD configurations for the treesitter-chunker project.

## Features

### Pre-commit Hook Management
- Automated installation and configuration of pre-commit hooks
- Integration with existing `.pre-commit-config.yaml`
- Git repository validation
- Hook verification after installation

### Code Linting
- Multi-tool linting support (ruff, mypy)
- Configurable paths and auto-fix capabilities
- Detailed issue reporting with file, line, and column information
- JSON output parsing for structured error data

### Code Formatting
- Support for both ruff and black formatters
- Check-only mode for CI validation
- Automatic file modification tracking
- Fallback mechanism between formatters

### CI/CD Configuration Generation
- GitHub Actions workflow generation
- Multi-platform support (Linux, macOS, Windows)
- Matrix strategy for Python versions
- Complete job pipeline (test, build, deploy)
- Coverage reporting integration

### Quality Assurance
- Type coverage analysis using mypy
- Test coverage analysis using pytest-cov
- Detailed coverage reports with file breakdowns
- Configurable minimum coverage thresholds

## Usage

### Setting Up Pre-commit Hooks

```python
from chunker.devenv import DevelopmentEnvironment

dev_env = DevelopmentEnvironment()
success = dev_env.setup_pre_commit_hooks(Path("/path/to/project"))
```

### Running Linting

```python
# Lint specific files
success, issues = dev_env.run_linting(["src/main.py", "tests/"])

# Lint with auto-fix
success, issues = dev_env.run_linting(fix=True)

# Process issues
for issue in issues:
    print(f"{issue['file']}:{issue['line']}:{issue['column']} "
          f"[{issue['tool']}] {issue['code']}: {issue['message']}")
```

### Formatting Code

```python
# Check formatting without modifying
success, files = dev_env.format_code(check_only=True)

# Auto-format files
success, modified = dev_env.format_code(["src/"])
print(f"Modified files: {modified}")
```

### Generating CI Configuration

```python
config = dev_env.generate_ci_config(
    platforms=["ubuntu-latest", "macos-latest", "windows-latest"],
    python_versions=["3.10", "3.11", "3.12"]
)

# Save as GitHub Actions workflow
import yaml
with open(".github/workflows/ci.yml", "w") as f:
    yaml.dump(config, f)
```

### Checking Code Quality

```python
from chunker.devenv import QualityAssurance

qa = QualityAssurance()

# Check type coverage
type_coverage, type_report = qa.check_type_coverage(min_coverage=80.0)
print(f"Type coverage: {type_coverage:.1f}%")

# Check test coverage
test_coverage, test_report = qa.check_test_coverage(min_coverage=80.0)
print(f"Test coverage: {test_coverage:.1f}%")
```

## Configuration

The component automatically detects and uses tools available in the system PATH:
- `ruff` - Fast Python linter and formatter
- `black` - Python code formatter
- `mypy` - Static type checker
- `pre-commit` - Git hook framework
- `pytest` - Testing framework with coverage plugin

## Error Handling

All methods handle missing tools gracefully:
- Returns appropriate error messages when tools are not found
- Provides fallback mechanisms (e.g., black when ruff is unavailable)
- Catches and reports subprocess errors without crashing

## Integration with CI/CD

The generated CI configuration includes:
- Dependency installation with uv
- Grammar fetching and building
- Linting and type checking
- Test execution with coverage
- Build artifact generation
- Automated PyPI deployment on tags

## Best Practices

1. **Pre-commit Setup**: Always ensure the project is a git repository with a valid `.pre-commit-config.yaml`
2. **Linting**: Run linting before commits to catch issues early
3. **Formatting**: Use check-only mode in CI to validate formatting
4. **Coverage**: Set realistic coverage thresholds (80% is a good default)
5. **CI Configuration**: Customize the generated config for project-specific needs

## Troubleshooting

### Pre-commit Installation Fails
- Ensure `pre-commit` is installed: `pip install pre-commit`
- Verify the project is a git repository: `git init`
- Check `.pre-commit-config.yaml` exists and is valid

### Linting Tools Not Found
- Install development dependencies: `pip install -e ".[dev]"`
- Verify tools are in PATH: `which ruff mypy`

### Coverage Reports Missing
- Ensure pytest-cov is installed: `pip install pytest-cov`
- Check that tests exist and can be discovered by pytest

## Implementation Details

### Architecture
- **DevelopmentEnvironment**: Handles environment setup, linting, and formatting
- **QualityAssurance**: Manages code quality metrics and coverage analysis
- Contract-based design following `DevelopmentEnvironmentContract` and `QualityAssuranceContract`

### Tool Integration
- Subprocess execution with proper error handling
- Output parsing for both structured (JSON) and text formats
- Executable discovery using `shutil.which()`

### Performance Considerations
- Tool outputs are parsed efficiently
- Subprocess calls use `capture_output` to avoid blocking
- Coverage reports are cached by the tools themselves

## Future Enhancements

1. Support for additional linters (pylint, flake8)
2. Integration with more CI platforms (GitLab CI, CircleCI)
3. Incremental linting for large codebases
4. Custom rule configuration management
5. Visual coverage reports generation