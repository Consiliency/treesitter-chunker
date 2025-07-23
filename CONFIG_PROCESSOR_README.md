# Config File Processor

This module implements the ConfigProcessor for Phase 11 of the tree-sitter-chunker project. It provides intelligent section-based chunking for configuration files.

## Overview

The ConfigProcessor handles various configuration file formats:
- **INI files** (.ini, .cfg, .conf) - Section-based with [sections] and key=value pairs
- **TOML files** (.toml) - Tables with [[array.tables]] support
- **YAML files** (.yaml, .yml) - Indentation-aware with nested structures
- **JSON files** (.json) - Object and array chunking

## Features

1. **Format Auto-detection**: Automatically detects configuration format from file extension or content
2. **Section-based Chunking**: Preserves logical sections and configuration groups
3. **Comment Preservation**: Maintains comments as documentation
4. **Related Section Grouping**: Can group small related sections (e.g., server1, server2)
5. **Structure Preservation**: Keeps configuration relationships intact
6. **Environment Variable Support**: Recognizes ${VAR} patterns
7. **Graceful Error Handling**: Handles malformed configs without crashing

## Architecture

```
chunker/processors/
├── __init__.py
├── base.py          # SpecializedProcessor interface
└── config.py        # ConfigProcessor implementation
```

### Key Classes

- **SpecializedProcessor**: Base interface for all specialized processors
- **ConfigProcessor**: Main implementation for config file processing
- **ProcessorConfig**: Configuration options for processing behavior

## Usage

```python
from chunker.processors.config import ConfigProcessor, ProcessorConfig

# Create processor with custom config
config = ProcessorConfig(
    chunk_size=50,           # Target chunk size
    preserve_structure=True,  # Keep sections intact
    group_related=True,      # Group related sections
    include_comments=True    # Include comments
)
processor = ConfigProcessor(config)

# Process a configuration file
with open('config.ini', 'r') as f:
    content = f.read()

chunks = processor.process('config.ini', content)

# Each chunk contains:
# - content: The actual configuration text
# - start_line/end_line: Line boundaries
# - node_type: Type of configuration section
# - metadata: Format-specific information
```

## Format-Specific Behavior

### INI Files
- Chunks by [sections]
- Handles global settings before first section
- Groups numbered sections (server1, server2)
- Preserves comments and inline documentation

### TOML Files
- Separates root-level keys from tables
- Distinguishes [[array.tables]] from [tables]
- Maintains table hierarchy
- Handles inline tables and arrays

### YAML Files
- Chunks by top-level keys
- Preserves indentation structure
- Handles multi-line values (|, >)
- Maintains document structure

### JSON Files
- Small objects: Single chunk
- Large objects: Chunks by top-level keys
- Arrays: Chunks by element groups
- Preserves JSON validity in each chunk

## Testing

Run tests with:
```bash
python -m pytest tests/test_config_processor.py -v
```

Run the demo:
```bash
python test_config_processor_demo.py
```

## Example Output

For an INI file:
```ini
[database]
host = localhost
port = 5432

[cache]
host = redis
```

Produces chunks:
1. Chunk 1: [database] section with its settings
2. Chunk 2: [cache] section with its settings

## Integration with SlidingWindowEngine

The ConfigProcessor is designed to work with the SlidingWindowEngine interface:
- Provides structured chunks that can be processed by sliding window
- Maintains semantic boundaries for configuration sections
- Supports overlapping windows while preserving config integrity

## Dependencies

- Python standard library: configparser, json, re
- Optional: toml (for TOML support)
- Optional: yaml/PyYAML (for YAML support)

## Future Enhancements

1. Support for more config formats (.env, .properties)
2. Schema validation for known config types
3. Cross-reference detection between sections
4. Config migration support
5. Diff-friendly chunking for version control