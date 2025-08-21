# Error Handling Package

## Overview

The error handling package provides intelligent error handling that detects language version compatibility issues and provides clear user guidance for the treesitter-chunker system.

## Package Structure

```
chunker/error_handling/
├── __init__.py          # Package initialization and exports
├── config.py            # Configuration management
├── utils.py             # Common utility functions
├── README.md            # This documentation
├── classifier.py         # Error classification system (Group C)
├── compatibility_detector.py  # Compatibility error detection (Group C)
└── syntax_analyzer.py   # Syntax error analysis (Group C)
```

## Components

### Core Infrastructure (Created by Primary Agent)

- **`__init__.py`**: Package initialization with dynamic imports for Group C components
- **`config.py`**: Configuration management with validation and environment variable support
- **`utils.py`**: Common utility functions for error analysis, formatting, and validation
- **`README.md`**: Package documentation and usage guide

### Group C Implementation Components

- **`classifier.py`**: Error classification system with severity, category, and source tracking
- **`compatibility_detector.py`**: Language version compatibility error detection
- **`syntax_analyzer.py`**: Syntax error analysis and pattern matching

## Usage

### Basic Import

```python
from chunker.error_handling import ErrorClassifier, CompatibilityErrorDetector

# The package will automatically import available components
# Components not yet implemented by Group C will be gracefully handled
```

### Configuration

```python
from chunker.error_handling.config import ErrorHandlingConfig, create_config_from_env

# Use default configuration
config = ErrorHandlingConfig()

# Or load from environment variables
config = create_config_from_env()

# Customize settings
config.error_reporting_level = ErrorReportingLevel.DETAILED
config.guidance_style = UserGuidanceStyle.INTERACTIVE
```

### Utility Functions

```python
from chunker.error_handling.utils import (
    extract_error_pattern,
    calculate_error_similarity,
    extract_file_context,
    format_error_message,
    generate_error_id
)

# Extract normalized error pattern
pattern = extract_error_pattern("SyntaxError: invalid syntax at line 42")

# Calculate similarity between errors
similarity = calculate_error_similarity(error1, error2)

# Extract file context
context = extract_file_context(Path("file.py"), 42, context_lines=3)

# Generate unique error ID
error_id = generate_error_id("SyntaxError", "invalid syntax", context)
```

## Configuration Options

### Error Reporting Levels

- **MINIMAL**: Basic error messages only
- **STANDARD**: Standard error + basic guidance
- **DETAILED**: Full error analysis + detailed guidance
- **DEBUG**: Full error analysis + debug information

### User Guidance Styles

- **CONCISE**: Short, actionable steps
- **DETAILED**: Comprehensive explanations
- **INTERACTIVE**: Step-by-step guidance
- **AUTOMATIC**: Automatic problem resolution

### Performance Settings

- **max_analysis_time**: Maximum time for error analysis (default: 30 seconds)
- **cache_error_patterns**: Enable pattern caching (default: True)
- **max_cached_patterns**: Maximum cached patterns (default: 1000)

## Environment Variables

The system can be configured via environment variables:

```bash
export ERROR_HANDLING_LOG_LEVEL=debug
export ERROR_HANDLING_REPORTING_LEVEL=detailed
export ERROR_HANDLING_GUIDANCE_STYLE=interactive
```

## Integration

The error handling system integrates with:

- **Language Version Detection** (Group A): For compatibility checking
- **Compatibility Database** (Group B): For version mapping
- **Main Chunker Pipeline**: For error reporting and user guidance

## Development Status

- **Infrastructure**: ✅ Complete (Primary Agent)
- **Group C Components**: 🚧 In Progress (Sub-agents)
- **Group D Components**: 📋 Planned (User Guidance)
- **Group E Components**: 📋 Planned (Integration & Testing)

## Future Enhancements

- **Group D**: Error message templates, guidance engine, troubleshooting database
- **Group E**: Full system integration, comprehensive testing, performance optimization
- **Production Features**: Error analytics, user feedback collection, automated resolution

## Contributing

When implementing components:

1. **Follow the established patterns** in existing files
2. **Use the utility functions** from `utils.py` to avoid duplication
3. **Respect the configuration system** for customizable behavior
4. **Implement comprehensive error handling** with graceful degradation
5. **Add proper logging** throughout your implementation
6. **Include type hints** and comprehensive docstrings

## Testing

Each component should include:

- **Unit tests** with 90%+ coverage
- **Integration tests** with other components
- **Error handling tests** for edge cases
- **Performance tests** for time-sensitive operations

## Dependencies

- **Standard Library**: Only use Python standard library modules
- **Internal Dependencies**: Import from completed Groups A and B
- **No External Dependencies**: Avoid adding new package requirements
