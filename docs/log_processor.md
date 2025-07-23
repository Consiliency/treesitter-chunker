# Log Processor Documentation

The `LogProcessor` is a specialized text processor designed to handle various log file formats with intelligent chunking capabilities. It supports timestamp-based chunking, session detection, log level grouping, and error context extraction.

## Features

- **Multi-format Support**: Automatically detects and parses various log formats (syslog, Apache, ISO timestamps, Log4j, etc.)
- **Flexible Chunking Strategies**: Time-based, line-based, session-based, or log level-based chunking
- **Session Detection**: Identifies session boundaries for user activity tracking
- **Error Context Extraction**: Groups error messages with surrounding context lines
- **Streaming Support**: Process large log files efficiently with streaming API
- **Multi-line Entry Handling**: Correctly handles stack traces and multi-line log entries
- **Timezone Awareness**: Parses timestamps with various timezone formats
- **Custom Pattern Support**: Add your own log format patterns

## Installation

The LogProcessor is part of the treesitter-chunker package:

```bash
pip install treesitter-chunker
```

## Basic Usage

```python
from chunker.processors.logs import LogProcessor

# Create a processor with default settings
processor = LogProcessor()

# Process a log file
with open('application.log', 'r') as f:
    content = f.read()
    
chunks = processor.process(content)

# Each chunk contains:
for chunk in chunks:
    print(f"Lines {chunk.start_line}-{chunk.end_line}")
    print(f"Formats detected: {chunk.metadata['formats']}")
    print(f"Log levels: {chunk.metadata['levels']}")
```

## Configuration Options

### Chunking Strategies

```python
# Time-based chunking (default)
processor = LogProcessor(config={
    'chunk_by': 'time',
    'time_window': 300  # 5 minutes
})

# Line-based chunking
processor = LogProcessor(config={
    'chunk_by': 'lines',
    'max_chunk_lines': 1000
})

# Session-based chunking
processor = LogProcessor(config={
    'chunk_by': 'session',
    'detect_sessions': True
})

# Log level-based chunking
processor = LogProcessor(config={
    'chunk_by': 'level'
})
```

### Error Context Grouping

```python
processor = LogProcessor(config={
    'group_errors': True,
    'context_lines': 5  # Include 5 lines before/after errors
})
```

### Custom Patterns

```python
# Add custom log format patterns
processor = LogProcessor(config={
    'patterns': {
        'custom_app': r'^(?P<timestamp>\d{2}:\d{2}:\d{2})\s+\[(?P<level>\w+)\]\s+(?P<message>.*)'
    }
})
```

## Supported Log Formats

### Built-in Formats

1. **Syslog Format**
   ```
   Jan  1 00:00:00 hostname process[pid]: message
   ```

2. **Apache Common/Combined Log Format**
   ```
   192.168.1.1 - - [01/Jan/2024:00:00:00 +0000] "GET / HTTP/1.1" 200 1234
   ```

3. **ISO Timestamp Format**
   ```
   2024-01-01 12:00:00,000 [INFO] message
   2024-01-01T12:00:00.000Z [DEBUG] message
   ```

4. **Java/Log4j Format**
   ```
   2024-01-01 12:00:00,000 INFO [Thread-1] com.example.Class - message
   ```

### Log Level Detection

The processor recognizes standard log levels:
- CRITICAL/FATAL/EMERGENCY
- ERROR/ERR/SEVERE
- WARNING/WARN
- INFO/INFORMATION/NOTICE
- DEBUG/TRACE/VERBOSE

## Advanced Usage

### Streaming Large Files

```python
def process_large_log(file_path):
    processor = LogProcessor(config={
        'chunk_by': 'time',
        'time_window': 60
    })
    
    def line_generator():
        with open(file_path, 'r') as f:
            for line in f:
                yield line
    
    for chunk in processor.process_stream(line_generator()):
        # Process each chunk as it's generated
        process_chunk(chunk)
```

### Session Tracking

```python
processor = LogProcessor(config={
    'chunk_by': 'session',
    'detect_sessions': True
})

chunks = processor.process(log_content)

# Group chunks by session
sessions = {}
for chunk in chunks:
    session_id = chunk.metadata.get('session_id')
    if session_id:
        sessions.setdefault(session_id, []).append(chunk)
```

### Error Analysis

```python
processor = LogProcessor(config={
    'group_errors': True,
    'context_lines': 10
})

chunks = processor.process(log_content)

# Find chunks with errors
error_chunks = [c for c in chunks if c.metadata.get('has_errors')]

for chunk in error_chunks:
    print(f"Found {chunk.metadata['error_count']} errors")
    # Analyze error patterns, extract stack traces, etc.
```

## Chunk Metadata

Each chunk includes metadata about its contents:

```python
{
    'entry_count': 42,              # Number of log entries
    'formats': ['syslog', 'iso'],  # Detected log formats
    'levels': ['INFO', 'ERROR'],    # Log levels present
    'start_time': '2024-01-01T00:00:00',  # First timestamp
    'end_time': '2024-01-01T00:05:00',    # Last timestamp
    'session_id': 'session_1',      # Session identifier (if applicable)
    'has_errors': True,             # Contains error messages
    'error_count': 3,               # Number of errors
    'log_level': 'ERROR'            # Primary level (for level-based chunking)
}
```

## Performance Considerations

1. **Memory Usage**: The processor buffers log entries for chunking. For very large files, use streaming mode.

2. **Timestamp Parsing**: Complex timestamp formats may impact performance. Consider using simpler formats or custom patterns for better performance.

3. **Pattern Matching**: Each line is matched against multiple patterns. Reduce the number of patterns for better performance.

4. **Chunk Size**: Smaller chunks (shorter time windows or fewer lines) create more chunks but use less memory.

## Best Practices

1. **Choose Appropriate Chunking Strategy**:
   - Use time-based for time-series analysis
   - Use session-based for user activity tracking
   - Use level-based for error analysis
   - Use line-based for simple splitting

2. **Configure Time Windows**: Match your time windows to your log rotation schedule or analysis needs.

3. **Handle Multi-line Entries**: The processor automatically handles stack traces and multi-line entries. Ensure your logs use consistent formatting.

4. **Test Format Detection**: Verify that your log formats are correctly detected. Add custom patterns if needed.

5. **Monitor Memory Usage**: For production use with large files, implement monitoring and use streaming mode when appropriate.

## Examples

See the `examples/logs/` directory for sample log files and `examples/demo_log_processor.py` for comprehensive usage examples.