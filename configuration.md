# Configuration Reference

Tree-sitter Chunker supports flexible configuration through multiple formats and sources. This guide covers all configuration options, file formats, and best practices.

## Table of Contents

1. [Configuration Overview](#configuration-overview)
2. [Configuration Files](#configuration-files)
3. [File Formats](#file-formats)
4. [Configuration Options](#configuration-options)
5. [Plugin Configuration](#plugin-configuration)
6. [CLI Configuration](#cli-configuration)
7. [Environment Variables](#environment-variables)
8. [Configuration Precedence](#configuration-precedence)
9. [Examples](#examples)
10. [Best Practices](#best-practices)

## Configuration Overview

Tree-sitter Chunker can be configured through:

1. **Configuration files** - `.chunkerrc`, `chunker.config.toml`, etc.
2. **Command-line arguments** - Override specific settings
3. **Environment variables** - System-wide settings
4. **Programmatic configuration** - In-code configuration

## Configuration Files

### File Locations

The configuration system searches for files in the following order:

1. Current directory: `.chunkerrc`, `chunker.config.*`
2. Parent directories (up to root)
3. User home directory: `~/.chunker/config.*`
4. System-wide: `/etc/chunker/config.*`

### File Names

Supported configuration file names:
- `.chunkerrc` (TOML format by default)
- `chunker.config.toml`
- `chunker.config.yaml` / `chunker.config.yml`
- `chunker.config.json`

### Discovery

```python
from chunker import ChunkerConfig

# Automatically find configuration
config = ChunkerConfig.find_config()

# Or specify explicit path
config = ChunkerConfig("/path/to/config.toml")
```

## File Formats

### TOML (Recommended)

```toml
# chunker.config.toml

# Global settings
chunk_types = ["function_definition", "class_definition", "method_definition"]
min_chunk_size = 3
max_chunk_size = 200

# File filtering
include_patterns = ["*.py", "*.js", "*.rs"]
exclude_patterns = ["*test*", "*__pycache__*", "*.min.js"]

# Processing options
parallel_workers = 4
cache_enabled = true
cache_size = 100

# Plugin directories
plugin_dirs = ["./plugins", "~/.chunker/plugins"]

# Language-specific settings
[languages.python]
enabled = true
chunk_types = ["function_definition", "class_definition", "async_function_definition"]
min_chunk_size = 5
max_chunk_size = 300

[languages.python.custom_options]
include_docstrings = true
include_type_hints = true
skip_private = false

[languages.javascript]
enabled = true
chunk_types = ["function_declaration", "arrow_function", "class_declaration"]
include_jsx = true

[languages.rust]
enabled = true
chunk_types = ["function_item", "impl_item", "trait_item", "struct_item"]
include_tests = false

# Export settings
[export]
default_format = "json"
compression = true
include_metadata = true

[export.json]
indent = 2
schema_type = "nested"

[export.parquet]
compression = "snappy"
partition_by = ["language", "file_path"]
```

### YAML

```yaml
# chunker.config.yaml

# Global settings
chunk_types:
  - function_definition
  - class_definition
  - method_definition
min_chunk_size: 3
max_chunk_size: 200

# File filtering
include_patterns:
  - "*.py"
  - "*.js"
  - "*.rs"
exclude_patterns:
  - "*test*"
  - "*__pycache__*"
  - "*.min.js"

# Processing options
parallel_workers: 4
cache_enabled: true
cache_size: 100

# Plugin directories
plugin_dirs:
  - ./plugins
  - ~/.chunker/plugins

# Language-specific settings
languages:
  python:
    enabled: true
    chunk_types:
      - function_definition
      - class_definition
      - async_function_definition
    min_chunk_size: 5
    max_chunk_size: 300
    custom_options:
      include_docstrings: true
      include_type_hints: true
      skip_private: false
  
  javascript:
    enabled: true
    chunk_types:
      - function_declaration
      - arrow_function
      - class_declaration
    include_jsx: true
  
  rust:
    enabled: true
    chunk_types:
      - function_item
      - impl_item
      - trait_item
      - struct_item
    include_tests: false

# Export settings
export:
  default_format: json
  compression: true
  include_metadata: true
  
  json:
    indent: 2
    schema_type: nested
  
  parquet:
    compression: snappy
    partition_by:
      - language
      - file_path
```

### JSON

```json
{
  "chunk_types": [
    "function_definition",
    "class_definition",
    "method_definition"
  ],
  "min_chunk_size": 3,
  "max_chunk_size": 200,
  "include_patterns": ["*.py", "*.js", "*.rs"],
  "exclude_patterns": ["*test*", "*__pycache__*", "*.min.js"],
  "parallel_workers": 4,
  "cache_enabled": true,
  "cache_size": 100,
  "plugin_dirs": ["./plugins", "~/.chunker/plugins"],
  "languages": {
    "python": {
      "enabled": true,
      "chunk_types": [
        "function_definition",
        "class_definition",
        "async_function_definition"
      ],
      "min_chunk_size": 5,
      "max_chunk_size": 300,
      "custom_options": {
        "include_docstrings": true,
        "include_type_hints": true,
        "skip_private": false
      }
    }
  },
  "export": {
    "default_format": "json",
    "compression": true,
    "include_metadata": true,
    "json": {
      "indent": 2,
      "schema_type": "nested"
    },
    "parquet": {
      "compression": "snappy",
      "partition_by": ["language", "file_path"]
    }
  }
}
```

## Configuration Options

### Global Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `chunk_types` | List[str] | Language defaults | Node types to extract as chunks |
| `min_chunk_size` | int | 0 | Minimum chunk size in lines |
| `max_chunk_size` | int | 1000000 | Maximum chunk size in lines |
| `include_patterns` | List[str] | [] | File patterns to include |
| `exclude_patterns` | List[str] | [] | File patterns to exclude |
| `parallel_workers` | int | CPU count | Number of parallel workers |
| `cache_enabled` | bool | true | Enable AST caching |
| `cache_size` | int | 100 | Maximum cache entries |
| `plugin_dirs` | List[str] | [] | Additional plugin directories |
| `enabled_languages` | List[str] | All | Languages to enable |
| `log_level` | str | "INFO" | Logging level |

### Language-Specific Options

Each language can have its own configuration under the `languages` section:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `enabled` | bool | true | Enable this language |
| `chunk_types` | List[str] | Plugin defaults | Override chunk types |
| `min_chunk_size` | int | Global value | Language-specific minimum |
| `max_chunk_size` | int | Global value | Language-specific maximum |
| `file_extensions` | List[str] | Plugin defaults | File extensions to process |
| `custom_options` | Dict | {} | Plugin-specific options |

### Export Options

Configure export formats under the `export` section:

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `default_format` | str | "json" | Default export format |
| `compression` | bool | false | Enable compression |
| `include_metadata` | bool | true | Include chunk metadata |

#### JSON Export Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `indent` | int | 2 | JSON indentation |
| `schema_type` | str | "flat" | Schema type: flat, nested, relational |
| `include_line_numbers` | bool | true | Include line numbers |

#### Parquet Export Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `compression` | str | "snappy" | Compression: snappy, gzip, brotli, lz4, zstd |
| `partition_by` | List[str] | [] | Columns to partition by |
| `row_group_size` | int | 5000 | Rows per group |

## Plugin Configuration

### Plugin Discovery

```toml
# Enable/disable plugin discovery
[plugins]
auto_discover = true
entry_points = true  # Discover from Python entry points
builtin = true       # Load built-in plugins

# Additional plugin directories
plugin_dirs = [
    "./my_plugins",
    "~/.chunker/plugins",
    "/usr/local/share/chunker/plugins"
]

# Explicitly load plugins
load_plugins = ["swift", "kotlin", "scala"]
```

### Per-Plugin Configuration

```toml
[plugins.python]
enabled = true
chunk_types = ["function_definition", "class_definition"]
min_chunk_size = 3
max_chunk_size = 500

# Plugin-specific options
[plugins.python.custom_options]
include_docstrings = true
include_decorators = true
include_type_hints = true
skip_private = false
skip_tests = false

[plugins.javascript]
enabled = true
include_jsx = true
include_typescript = true
es_module_syntax = true

[plugins.rust]
enabled = true
include_tests = false
include_docs = true
include_macros = false
```

## CLI Configuration

### .chunkerrc for CLI

The CLI looks for `.chunkerrc` files for default options:

```toml
# .chunkerrc - CLI-specific configuration

# Default language (for auto-detection)
default_language = "python"

# Output options
output_format = "table"  # table, json, jsonl, csv
show_progress = true
quiet = false
verbose = false

# Processing options
recursive = true
follow_symlinks = false
ignore_errors = true

# Default chunk filtering
chunk_types = ["function_definition", "class_definition"]
min_lines = 3
max_lines = 200

# File patterns
include = ["*.py", "*.js", "*.rs"]
exclude = ["test_*.py", "*_test.py", "*.min.js"]
```

### Command-Line Override

Command-line arguments override configuration files:

```bash
# Override configuration file settings
chunker chunk src/ --lang python --min-size 5 --max-size 100

# Use different config file
chunker chunk src/ --config production.toml

# Disable configuration
chunker chunk src/ --no-config
```

## Environment Variables

Environment variables provide system-wide defaults:

### General Variables

```bash
# Configuration file location
export CHUNKER_CONFIG_PATH=/etc/chunker/config.toml

# Logging
export CHUNKER_LOG_LEVEL=DEBUG
export CHUNKER_LOG_FILE=/var/log/chunker.log

# Performance
export CHUNKER_CACHE_SIZE=200
export CHUNKER_PARALLEL_WORKERS=8

# Plugin directories
export CHUNKER_PLUGIN_PATH=/opt/chunker/plugins:/usr/local/lib/chunker
```

### Language-Specific Variables

```bash
# Python configuration
export CHUNKER_PYTHON_ENABLED=true
export CHUNKER_PYTHON_MIN_SIZE=5
export CHUNKER_PYTHON_INCLUDE_DOCSTRINGS=true

# JavaScript configuration
export CHUNKER_JAVASCRIPT_ENABLED=true
export CHUNKER_JAVASCRIPT_INCLUDE_JSX=true

# Rust configuration
export CHUNKER_RUST_ENABLED=true
export CHUNKER_RUST_INCLUDE_TESTS=false
```

## Configuration Precedence

Configuration sources are applied in the following order (later sources override earlier ones):

1. Built-in defaults
2. System configuration (`/etc/chunker/config.*`)
3. User configuration (`~/.chunker/config.*`)
4. Project configuration (`.chunkerrc`, `chunker.config.*`)
5. Environment variables
6. Command-line arguments
7. Programmatic configuration

### Example Precedence

```python
# Built-in default: min_chunk_size = 0
# User config: min_chunk_size = 3
# Project config: min_chunk_size = 5
# Environment: CHUNKER_MIN_SIZE = 10
# CLI: --min-size 15

# Final value: min_chunk_size = 15
```

## Examples

### Basic Configuration

Simple configuration for a Python project:

```toml
# .chunkerrc
chunk_types = ["function_definition", "class_definition"]
min_chunk_size = 5
exclude_patterns = ["*test*.py", "__pycache__"]
```

### Multi-Language Project

Configuration for a project with multiple languages:

```toml
# chunker.config.toml

# Global defaults
min_chunk_size = 3
max_chunk_size = 300
parallel_workers = 4

# Python files
[languages.python]
chunk_types = ["function_definition", "class_definition", "async_function_definition"]
exclude_patterns = ["*_test.py", "test_*.py"]

[languages.python.custom_options]
include_docstrings = true
skip_private = true

# JavaScript/TypeScript files
[languages.javascript]
chunk_types = ["function_declaration", "arrow_function", "class_declaration"]
file_extensions = [".js", ".jsx", ".ts", ".tsx"]
include_jsx = true

# Rust files
[languages.rust]
chunk_types = ["function_item", "impl_item", "trait_item"]
include_tests = false
include_docs = false
```

### CI/CD Configuration

Configuration for continuous integration:

```toml
# ci.config.toml

# Strict settings for CI
min_chunk_size = 1  # Don't skip small functions
max_chunk_size = 500  # Flag large functions
parallel_workers = 2  # Limit resource usage

# Only process source files
include_patterns = ["src/**/*.py", "lib/**/*.js"]
exclude_patterns = ["**/*test*", "**/vendor/**", "**/node_modules/**"]

# Export settings for analysis
[export]
default_format = "json"
compression = false  # Faster processing
include_metadata = true

[export.json]
indent = 0  # Compact output
schema_type = "flat"  # Simple structure
```

### Development Configuration

Configuration for local development:

```toml
# dev.config.toml

# Verbose output for debugging
log_level = "DEBUG"
show_progress = true
verbose = true

# Include everything for analysis
include_tests = true
include_docs = true
min_chunk_size = 0  # Show all chunks

# Fast iteration
cache_enabled = true
cache_size = 500  # Large cache for development

# Custom plugin development
plugin_dirs = ["./dev_plugins", "./experimental_plugins"]

[plugins.my_custom_plugin]
enabled = true
debug_mode = true
```

## Best Practices

### 1. Use Version Control

Always version control your configuration files:

```bash
# .gitignore
# Don't ignore project configuration
!.chunkerrc
!chunker.config.toml

# But ignore personal configuration
.chunkerrc.local
chunker.config.local.toml
```

### 2. Environment-Specific Configs

Use different configurations for different environments:

```python
import os
from chunker import ChunkerConfig

env = os.getenv("CHUNKER_ENV", "development")
config_file = f"chunker.config.{env}.toml"
config = ChunkerConfig(config_file)
```

### 3. Validate Configuration

Always validate configuration files:

```python
from chunker import ChunkerConfig

try:
    config = ChunkerConfig("chunker.config.toml")
    config.validate()
except Exception as e:
    print(f"Invalid configuration: {e}")
```

### 4. Document Custom Options

Document all custom options in your configuration:

```toml
# chunker.config.toml

# Custom options for our Python analyzer
[languages.python.custom_options]
# Skip functions with "deprecated" in their name or docstring
skip_deprecated = true

# Minimum complexity score to include a function
min_complexity = 5

# Extract type annotations as separate metadata
extract_type_annotations = true
```

### 5. Use Hierarchical Configuration

Organize configuration hierarchically:

```toml
# Base configuration
[base]
min_chunk_size = 3
max_chunk_size = 200

# Language-specific overrides
[languages.python]
min_chunk_size = 5  # Python tends to have more boilerplate

[languages.rust]
max_chunk_size = 150  # Rust functions are typically more concise
```

### 6. Secure Sensitive Information

Never store sensitive information in configuration files:

```toml
# DON'T DO THIS
api_key = "sk-1234567890abcdef"

# DO THIS INSTEAD
api_key_env = "CHUNKER_API_KEY"  # Read from environment
```

### 7. Performance Tuning

Profile and tune configuration for performance:

```toml
# Performance tuning
[performance]
# Adjust based on system resources
parallel_workers = 8  # Number of CPU cores
cache_size = 200     # Based on available memory

# File size thresholds
streaming_threshold = 10485760  # 10MB - use streaming for larger files
batch_size = 100  # Process files in batches

# Language-specific tuning
[languages.python.performance]
parser_timeout = 5000  # 5 seconds for complex files
```

## See Also

- [API Reference](api-reference.md) - Complete API documentation
- [Plugin Development](plugin-development.md) - Creating custom plugins
- [CLI Reference](cli-reference.md) - Command-line options
- [User Guide](user-guide.md) - General usage guide