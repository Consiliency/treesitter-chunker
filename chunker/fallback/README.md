# Fallback Chunking System

## Overview

The fallback chunking system provides last-resort chunking strategies for files that cannot be parsed by Tree-sitter. This system should only be used when no Tree-sitter grammar is available for the file type.

**Important**: The fallback system always emits warnings to encourage users to request or contribute Tree-sitter grammar support instead.

## Architecture

```
chunker/fallback/
├── __init__.py              # Public API exports
├── base.py                  # Base fallback chunker implementation
├── fallback_manager.py      # Coordinates detection and chunking
├── detection/
│   ├── __init__.py
│   └── file_type.py         # File type and encoding detection
└── strategies/
    ├── __init__.py
    ├── line_based.py        # Basic line-based chunking
    ├── log_chunker.py       # Specialized log file chunking
    └── markdown.py          # Markdown-specific chunking
```

## Features

### File Type Detection
- Extension-based detection
- Content-based detection using patterns
- MIME type detection
- Binary file detection
- Encoding detection with automatic handling

### Supported File Types
- **Text files** (.txt) - Line-based chunking
- **Log files** (.log, .out, .err) - Time/severity-based chunking
- **Markdown** (.md, .markdown) - Header/section-based chunking
- **CSV files** (.csv, .tsv) - Row-based with header preservation
- **Config files** (.ini, .cfg, .yaml, .json) - Section-based chunking
- **Generic text** - Adaptive line-based chunking

### Chunking Strategies

#### Line-Based Chunking
- Fixed number of lines per chunk
- Optional overlap between chunks
- Adaptive chunking based on content density

#### Delimiter-Based Chunking
- Split on custom delimiters
- Option to include/exclude delimiters

#### Pattern-Based Chunking
- Use regex patterns to identify chunk boundaries
- Useful for structured text formats

#### Specialized Strategies

**Log Files:**
- Chunk by time windows
- Chunk by severity levels (ERROR, WARN, INFO, etc.)
- Chunk by session/request IDs
- Automatic timestamp format detection

**Markdown Files:**
- Chunk by header hierarchy
- Chunk by logical sections
- Extract code blocks separately
- Preserve document structure

**CSV Files:**
- Preserve header row in each chunk
- Configurable rows per chunk
- Handle large datasets efficiently

## Usage

### Basic Usage

```python
from chunker.fallback import FallbackManager

manager = FallbackManager()

# Check if file can be chunked
if manager.can_chunk("data.log"):
    chunks = manager.chunk_file("data.log")
    for chunk in chunks:
        print(f"Chunk: {chunk.start_line}-{chunk.end_line}")
```

### Direct Strategy Usage

```python
from chunker.fallback import LogChunker, MarkdownChunker

# Log chunking
log_chunker = LogChunker()
chunks = log_chunker.chunk_by_timestamp(log_content, time_window_seconds=300)

# Markdown chunking
md_chunker = MarkdownChunker()
chunks = md_chunker.chunk_by_headers(md_content, max_level=3)
```

### File Type Detection

```python
from chunker.fallback import FileTypeDetector

detector = FileTypeDetector()
file_type = detector.detect_file_type("config.yaml")
should_fallback, reason = detector.should_use_fallback("config.yaml")
```

## Warning System

All fallback chunking emits warnings to encourage Tree-sitter usage:

```
WARNING: Using fallback chunking for data.log
Reason: no_grammar_available

Tree-sitter provides deterministic, AST-based chunking that preserves code structure.
Fallback methods may split code at inappropriate boundaries.

To improve chunking for this file type:
1. Check if a Tree-sitter grammar exists: https://github.com/tree-sitter
2. Request grammar support: https://github.com/tree-sitter
3. Use the 'more-grammars' feature to add support

Current fallback method: line_based
```

## Limitations

1. **No AST awareness** - Fallback chunking is text-based and may split at inappropriate boundaries
2. **Less accurate** - Cannot understand code structure or semantics
3. **Limited context** - No understanding of language-specific constructs
4. **Performance** - May be slower for complex pattern matching

## Best Practices

1. **Always prefer Tree-sitter** when a grammar is available
2. **Use appropriate chunk sizes** - Too small loses context, too large defeats the purpose
3. **Test thoroughly** - Fallback chunking behavior varies by content
4. **Monitor warnings** - Track which file types need Tree-sitter support
5. **Contribute grammars** - Help add Tree-sitter support for missing languages

## Adding New Strategies

To add a new fallback strategy:

1. Create a new file in `strategies/`
2. Inherit from `FallbackChunker` base class
3. Implement required methods
4. Add to `FallbackManager.chunker_map`
5. Update file type detection if needed

Example:

```python
from ..base import FallbackChunker

class XMLChunker(FallbackChunker):
    """Specialized chunker for XML files."""
    
    def chunk_by_elements(self, content: str, element_name: str) -> List[CodeChunk]:
        # Implementation here
        pass
```

## Testing

Run fallback-specific tests:

```bash
python -m pytest tests/test_fallback_chunking.py -v
```

Run the demo:

```bash
python examples/fallback_demo.py
```

## Future Improvements

1. Add support for more file types (XML, SQL, etc.)
2. Implement smarter content-based detection
3. Add configurable chunking strategies
4. Support for multi-language files
5. Better handling of mixed content (e.g., markdown with multiple code languages)