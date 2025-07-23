# Log Processor Implementation

This directory contains the implementation of the LogProcessor for Phase 11 of the treesitter-chunker project.

## Overview

The LogProcessor is a specialized text processor designed to handle various log file formats with intelligent chunking capabilities. It provides:

- **Multi-format Support**: Automatically detects and parses syslog, Apache, ISO timestamps, Log4j, and custom formats
- **Flexible Chunking**: Time-based, line-based, session-based, or log level-based chunking strategies
- **Advanced Features**: Session detection, error context extraction, multi-line entry handling, and streaming support

## Key Files

### Implementation
- `chunker/processors/base.py` - Base interface for specialized processors
- `chunker/processors/logs.py` - Main LogProcessor implementation
- `chunker/processors/__init__.py` - Package exports

### Tests
- `tests/test_log_processor.py` - Comprehensive unit tests
- `tests/test_log_processor_integration.py` - Real-world integration scenarios

### Documentation
- `docs/log_processor.md` - Detailed usage documentation
- `examples/demo_log_processor.py` - Interactive demonstration script
- `examples/logs/` - Sample log files in various formats

## Features Implemented

### 1. Timestamp-based Chunking
- Configurable time windows (default: 5 minutes)
- Handles multiple timestamp formats with timezone support
- Groups related events within time periods

### 2. Multi-format Support
Built-in patterns for:
- Syslog format
- Apache Common/Combined Log Format  
- ISO timestamps (various formats)
- Java/Log4j format
- Custom patterns via configuration

### 3. Session Detection
- Identifies login/logout patterns
- Groups user activity into sessions
- Configurable session markers

### 4. Error Context Extraction
- Groups error messages with surrounding context
- Configurable context lines (before/after)
- Handles multi-line stack traces

### 5. Streaming Support
- Process large files without loading into memory
- Yields chunks as they're completed
- Suitable for tailing active logs

### 6. Log Level Analysis
- Detects standard levels (ERROR, WARNING, INFO, DEBUG, etc.)
- Supports level-based chunking
- Groups related error sequences

## Usage Example

```python
from chunker.processors.logs import LogProcessor

# Create processor with time-based chunking
processor = LogProcessor(config={
    'chunk_by': 'time',
    'time_window': 300,  # 5 minutes
    'group_errors': True,
    'context_lines': 5
})

# Process a log file
with open('application.log', 'r') as f:
    content = f.read()
    chunks = processor.process(content)

# Analyze chunks
for chunk in chunks:
    print(f"Time range: {chunk.metadata.get('start_time')} - {chunk.metadata.get('end_time')}")
    print(f"Log levels: {chunk.metadata.get('levels')}")
    if chunk.metadata.get('has_errors'):
        print(f"Contains {chunk.metadata['error_count']} errors")
```

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| chunk_by | str | 'time' | Chunking strategy: 'time', 'lines', 'session', 'level' |
| time_window | int | 300 | Time window in seconds for time-based chunking |
| max_chunk_lines | int | 1000 | Maximum lines per chunk |
| context_lines | int | 5 | Lines to include before/after errors |
| detect_sessions | bool | True | Enable session boundary detection |
| group_errors | bool | True | Group errors with context |
| patterns | dict | {} | Custom log format patterns |

## Performance Considerations

- **Memory Efficient**: Streaming mode for large files
- **Pattern Matching**: Optimized regex patterns with proper ordering
- **Lazy Processing**: Chunks generated on-demand in streaming mode
- **Configurable Limits**: Control chunk sizes to manage memory usage

## Testing

Run unit tests:
```bash
python -m pytest tests/test_log_processor.py -v
```

Run integration tests:
```bash
python -m pytest tests/test_log_processor_integration.py -v
```

Run the demo:
```bash
python examples/demo_log_processor.py
```

## Future Enhancements

Potential improvements for future phases:
- Machine learning for anomaly detection
- Real-time alerting capabilities
- Log format auto-detection with confidence scores
- Integration with log aggregation systems
- Performance metrics and statistics
- Parallel processing for very large files