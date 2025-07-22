# Overlapping Fallback Chunker

## Overview

The overlapping fallback chunker provides sliding window chunking for files that **do not have Tree-sitter support**. This is useful for maintaining context across chunk boundaries in text files, logs, markdown documents, and other non-code content.

## Key Features

- **Tree-sitter Protection**: Automatically detects and rejects files with Tree-sitter support, ensuring code files use proper AST-based chunking
- **Configurable Overlap**: Support for fixed size, percentage-based, asymmetric, and dynamic overlap strategies
- **Line or Character Based**: Chunk by lines (useful for logs) or characters (useful for prose)
- **Natural Boundary Detection**: Can find paragraph breaks, sentence ends, and other natural boundaries for overlap points
- **Clear Warnings**: Emits warnings when overlapping fallback is used, making it clear this is not AST-based chunking

## Usage

### Basic Overlapping Chunks

```python
from chunker.fallback_overlap import OverlappingFallbackChunker, OverlapStrategy

chunker = OverlappingFallbackChunker()

# Chunk a log file with line-based overlap
chunks = chunker.chunk_with_overlap(
    content=log_content,
    file_path="app.log",
    chunk_size=100,      # 100 lines per chunk
    overlap_size=10,     # 10 lines overlap
    strategy=OverlapStrategy.FIXED,
    unit="lines"
)
```

### Overlap Strategies

#### Fixed Overlap
The simplest strategy - use a fixed number of lines or characters for overlap:

```python
chunks = chunker.chunk_with_overlap(
    content, "file.txt",
    chunk_size=1000,
    overlap_size=200,  # Fixed 200 character overlap
    strategy=OverlapStrategy.FIXED,
    unit="characters"
)
```

#### Percentage-Based Overlap
Overlap size as a percentage of chunk size:

```python
chunks = chunker.chunk_with_overlap(
    content, "file.md",
    chunk_size=1000,
    overlap_size=20,  # 20% overlap (200 chars)
    strategy=OverlapStrategy.PERCENTAGE,
    unit="characters"
)
```

#### Asymmetric Overlap
Different overlap sizes before and after each chunk:

```python
chunks = chunker.chunk_with_asymmetric_overlap(
    content, "file.log",
    chunk_size=100,
    overlap_before=5,   # 5 lines from previous chunk
    overlap_after=10,   # 10 lines into next chunk
    unit="lines"
)
```

#### Dynamic Overlap
Automatically adjust overlap based on natural boundaries:

```python
chunks = chunker.chunk_with_dynamic_overlap(
    content, "document.txt",
    chunk_size=1000,
    min_overlap=50,
    max_overlap=200,
    unit="characters"
)
```

## Tree-sitter Protection

The chunker will **raise an error** if you try to use it on files with Tree-sitter support:

```python
# This will raise TreeSitterOverlapError
try:
    chunks = chunker.chunk_with_overlap(
        "def foo(): pass",
        "script.py",  # Python has Tree-sitter support!
        chunk_size=100,
        overlap_size=20
    )
except TreeSitterOverlapError as e:
    print(f"Error: {e}")
    # Use regular Tree-sitter chunking instead
```

## Supported File Types

The overlapping chunker is designed for:
- Log files (`.log`)
- Markdown documents (`.md`)
- Plain text files (`.txt`)
- CSV files (`.csv`)
- Configuration files (`.conf`, `.ini`)
- Any file without Tree-sitter grammar support

## Warnings and Logging

The chunker emits clear warnings when used:

```
WARNING: Using overlapping fallback chunker for app.log. This file has no Tree-sitter support. Overlap strategy: fixed, size: 10 lines
```

This ensures users are aware they're not getting AST-based chunking.

## Natural Boundary Detection

The chunker can find natural boundaries for overlap placement:

```python
# Find the best overlap boundary near a desired position
boundary = chunker.find_natural_overlap_boundary(
    content,
    desired_position=500,
    search_window=100
)
```

Priority order for boundaries:
1. Paragraph breaks (`\n\n`)
2. Line breaks (`\n`)
3. Sentence ends (`. `, `! `, `? `)
4. Clause boundaries (`, `, `; `, `: `)
5. Word boundaries (spaces)

## Performance Considerations

- Overlapping chunks increase the total data size (each overlap is duplicated)
- For large files, consider using larger chunk sizes to reduce the number of chunks
- Character-based chunking is more expensive than line-based for large files

## Example: Processing Server Logs

```python
# Read log file
with open("server.log", "r") as f:
    log_content = f.read()

# Create overlapping chunks for context-aware analysis
chunker = OverlappingFallbackChunker()
chunks = chunker.chunk_with_overlap(
    log_content,
    "server.log",
    chunk_size=100,     # 100 lines per chunk
    overlap_size=10,    # 10 lines overlap for context
    strategy=OverlapStrategy.FIXED,
    unit="lines"
)

# Process chunks with context preserved across boundaries
for chunk in chunks:
    # Each chunk has overlap with neighbors
    # ensuring log entries aren't cut off mid-context
    analyze_log_chunk(chunk)
```

## Integration with Existing Fallback System

The overlapping chunker extends the base fallback chunker, so it inherits all standard fallback functionality while adding overlap support. It can be used as a drop-in replacement when overlap is needed for non-Tree-sitter files.