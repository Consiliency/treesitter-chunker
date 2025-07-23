# Environment Variables Configuration

The Tree-sitter Chunker supports environment variables for configuration in two ways:

1. **Variable expansion in config files** - Use `${VAR}` syntax in configuration files
2. **Override configuration values** - Use `CHUNKER_*` environment variables

## Variable Expansion in Config Files

You can use environment variables directly in your configuration files using the `${VAR}` or `${VAR:default}` syntax.

### Basic Syntax

```toml
[chunker]
plugin_dirs = ["${HOME}/.chunker/plugins", "${CUSTOM_PLUGIN_DIR}"]
```

### With Default Values

```toml
[chunker.default_plugin_config]
min_chunk_size = "${MIN_CHUNK_SIZE:3}"  # Uses 3 if MIN_CHUNK_SIZE not set
```

### Examples

```yaml
# YAML example
chunker:
  plugin_dirs:
    - ${HOME}/.chunker/plugins
    - ${CHUNKER_PLUGINS:/opt/chunker/plugins}
  
languages:
  python:
    max_chunk_size: ${PYTHON_MAX_SIZE:500}
```

```json
// JSON example
{
  "chunker": {
    "plugin_dirs": ["${HOME}/.chunker/plugins", "${WORK_DIR}/plugins"]
  }
}
```

## Configuration Overrides

Environment variables with the `CHUNKER_` prefix can override configuration values at runtime.

### Global Settings

| Environment Variable | Description | Example |
|---------------------|-------------|---------|
| `CHUNKER_ENABLED_LANGUAGES` | Comma-separated list of enabled languages | `python,rust,javascript` |
| `CHUNKER_PLUGIN_DIRS` | Comma-separated list of plugin directories | `/path/one,/path/two` |

### Default Plugin Configuration

| Environment Variable | Description | Example |
|---------------------|-------------|---------|
| `CHUNKER_DEFAULT_PLUGIN_CONFIG_MIN_CHUNK_SIZE` | Default minimum chunk size | `5` |
| `CHUNKER_DEFAULT_PLUGIN_CONFIG_MAX_CHUNK_SIZE` | Default maximum chunk size | `1000` |

### Language-Specific Settings

For any language, you can set:

| Environment Variable Pattern | Description | Example |
|----------------------------|-------------|---------|
| `CHUNKER_LANGUAGES_<LANG>_ENABLED` | Enable/disable language | `CHUNKER_LANGUAGES_PYTHON_ENABLED=true` |
| `CHUNKER_LANGUAGES_<LANG>_MIN_CHUNK_SIZE` | Minimum chunk size | `CHUNKER_LANGUAGES_RUST_MIN_CHUNK_SIZE=10` |
| `CHUNKER_LANGUAGES_<LANG>_MAX_CHUNK_SIZE` | Maximum chunk size | `CHUNKER_LANGUAGES_RUST_MAX_CHUNK_SIZE=500` |
| `CHUNKER_LANGUAGES_<LANG>_CHUNK_TYPES` | Comma-separated chunk types | `CHUNKER_LANGUAGES_PYTHON_CHUNK_TYPES=function_definition,class_definition` |

### Custom Language Options

Any custom option for a language can be set:

```bash
# Python custom options
export CHUNKER_LANGUAGES_PYTHON_INCLUDE_DOCSTRINGS=true

# JavaScript custom options  
export CHUNKER_LANGUAGES_JAVASCRIPT_INCLUDE_JSX=false
```

## Usage Examples

### Example 1: Development vs Production

```bash
# Development environment
export CHUNKER_ENABLED_LANGUAGES=python,rust,javascript,go,java
export CHUNKER_DEFAULT_PLUGIN_CONFIG_MIN_CHUNK_SIZE=1

# Production environment
export CHUNKER_ENABLED_LANGUAGES=python,rust
export CHUNKER_DEFAULT_PLUGIN_CONFIG_MIN_CHUNK_SIZE=5
export CHUNKER_LANGUAGES_PYTHON_MAX_CHUNK_SIZE=1000
```

### Example 2: CI/CD Pipeline

```yaml
# GitHub Actions example
env:
  CHUNKER_ENABLED_LANGUAGES: python,javascript
  CHUNKER_PLUGIN_DIRS: ${{ github.workspace }}/plugins
  CHUNKER_LANGUAGES_PYTHON_MIN_CHUNK_SIZE: 10
```

### Example 3: Docker

```dockerfile
# Dockerfile
ENV CHUNKER_ENABLED_LANGUAGES=python,rust
ENV CHUNKER_DEFAULT_PLUGIN_CONFIG_MAX_CHUNK_SIZE=2000

# Or in docker-compose.yml
services:
  chunker:
    environment:
      - CHUNKER_ENABLED_LANGUAGES=python,rust,go
      - CHUNKER_PLUGIN_DIRS=/app/plugins,/opt/plugins
```

### Example 4: Shell Script

```bash
#!/bin/bash

# Configure chunker for large files
export CHUNKER_DEFAULT_PLUGIN_CONFIG_MAX_CHUNK_SIZE=5000
export CHUNKER_LANGUAGES_PYTHON_MAX_CHUNK_SIZE=3000

# Run with custom plugin directory
export CUSTOM_PLUGINS=/opt/custom-chunker-plugins

# Your chunker command here
python -m chunker.cli chunk large_file.py
```

## Precedence Order

When multiple configuration sources are present, they are applied in this order:

1. Default values in code
2. Configuration file values
3. Environment variable expansion in config files (`${VAR}`)
4. Environment variable overrides (`CHUNKER_*`)

This means environment variable overrides have the highest precedence.

## Disabling Environment Variables

If you need to disable environment variable support (e.g., for security reasons), you can do so programmatically:

```python
from chunker.chunker_config import ChunkerConfig

# Load config without environment variable support
config = ChunkerConfig(config_path, use_env_vars=False)
```

## Debugging

To see which environment variables are being used:

```python
from chunker.chunker_config import ChunkerConfig

# Get information about supported environment variables
env_info = ChunkerConfig.get_env_var_info()
for var, description in env_info.items():
    print(f"{var}: {description}")
```

## Best Practices

1. **Use descriptive variable names**: When using custom environment variables in config files, use clear names like `${CHUNKER_WORKSPACE}` instead of `${DIR}`

2. **Provide defaults**: Always provide sensible defaults using the `${VAR:default}` syntax

3. **Document your variables**: If you're using custom environment variables, document them in your project

4. **Validate values**: Environment variables are strings, so numeric values are converted. Make sure to handle potential conversion errors

5. **Security**: Be cautious about accepting environment variables from untrusted sources, especially in production environments