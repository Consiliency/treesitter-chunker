# Configuration File Processor

The Configuration File Processor is a specialized component of the tree-sitter-chunker that intelligently handles various configuration file formats with section-based chunking.

## Overview

The ConfigProcessor provides intelligent chunking for configuration files by preserving logical sections and maintaining configuration relationships. It supports multiple formats including INI, TOML, YAML, and JSON.

## Supported Formats

### INI Files (.ini, .cfg, .conf)
- Section-based structure with `[sections]`
- Key-value pairs with `key = value` format
- Comment preservation
- Multi-line value support

### TOML Files (.toml)
- Table-based structure with `[table]` and `[[array.tables]]`
- Nested table support
- Type-aware value handling
- Array and inline table support

### YAML Files (.yaml, .yml)
- Indentation-aware parsing
- Nested structure preservation
- Multi-document support (---)
- Anchor and alias handling

### JSON Files (.json)
- Object and array chunking
- Nested structure preservation
- Pretty-print aware parsing
- Schema-based chunking options

## Features

### Format Auto-detection
The processor automatically detects the configuration format based on:
- File extension
- Content patterns
- Syntax markers

### Section-based Chunking
- Preserves logical configuration sections
- Maintains parent-child relationships
- Groups related sections when appropriate
- Respects configuration boundaries

### Comment Preservation
- Maintains inline and block comments
- Associates comments with their sections
- Preserves documentation value

### Structure Preservation
- Keeps nested configurations intact
- Maintains references between sections
- Preserves import/include directives
- Handles environment variable references

## Usage

### Basic Usage
```python
from chunker.processors.config import ConfigProcessor

processor = ConfigProcessor()
chunks = processor.process_file("config.toml")
```

### With Custom Configuration
```python
from chunker.processors.config import ConfigProcessor, ProcessorConfig

config = ProcessorConfig(
    chunk_size=100,           # Target lines per chunk
    preserve_structure=True,  # Keep sections intact
    group_related=True,       # Group related sections
    include_comments=True     # Include comments in chunks
)

processor = ConfigProcessor(config)
chunks = processor.process_file("app.ini")
```

### Integration with Main Chunker
The ConfigProcessor is automatically used by the intelligent fallback system:

```python
from chunker import IntelligentFallbackChunker

chunker = IntelligentFallbackChunker()
chunks = chunker.chunk_text(config_content, "config.yaml")
```

## Examples

### INI File Chunking
```ini
[database]
host = localhost
port = 5432
user = admin

[cache]
enabled = true
ttl = 3600
```

This would produce chunks preserving each section with its configuration values.

### TOML File Chunking
```toml
[package]
name = "my-app"
version = "1.0.0"

[[dependencies]]
name = "lib1"
version = "2.0"

[[dependencies]]
name = "lib2"
version = "3.0"
```

Array tables are kept together while maintaining relationships.

### YAML File Chunking
```yaml
server:
  host: localhost
  port: 8080
  
database:
  primary:
    host: db1.example.com
  replica:
    host: db2.example.com
```

Nested structures are preserved with proper indentation context.

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `chunk_size` | int | 50 | Target lines per chunk |
| `preserve_structure` | bool | True | Keep configuration sections intact |
| `group_related` | bool | True | Group small related sections |
| `include_comments` | bool | True | Include comments in chunks |
| `min_section_size` | int | 3 | Minimum lines to create separate chunk |
| `max_section_size` | int | 200 | Maximum lines per section chunk |

## Best Practices

1. **Section Integrity**: The processor prioritizes keeping configuration sections intact over strict size limits.

2. **Related Grouping**: Small related sections (like server1, server2) can be grouped for better context.

3. **Comment Association**: Comments immediately preceding sections are included with those sections.

4. **Format Detection**: While auto-detection works well, specifying the format explicitly can improve performance.

## Integration with Phase 11

The ConfigProcessor is part of Phase 11's text processing capabilities and integrates with:
- Sliding Window Fallback system
- Intelligent Fallback Chunker
- Token limit handling
- Multi-format processing pipeline

## See Also

- [Intelligent Fallback](intelligent_fallback.md) - Automatic processor selection
- [Log Processor](log_processor.md) - Log file processing
- [Token Limits](token_limits.md) - Token-aware chunking