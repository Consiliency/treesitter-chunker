# Overlapping Fallback Chunker

This module provides overlapping chunk support **ONLY** for files without Tree-sitter grammar support. It is specifically designed for text files, logs, configuration files, and other non-code content.

## CRITICAL: Tree-sitter Files Are NOT Supported

The overlapping fallback chunker will **raise an error** if you attempt to use it on files that have Tree-sitter support. This includes:

- Python (.py)
- JavaScript (.js, .jsx)
- TypeScript (.ts, .tsx)
- C/C++ (.c, .h, .cpp, .hpp)
- Rust (.rs)
- Go (.go)
- Java (.java)
- Ruby (.rb)
- And any other language with Tree-sitter grammar

For code files, use the standard Tree-sitter-based chunking which provides AST-aware chunking.

## Usage

```python
from chunker.fallback_overlap import OverlappingFallbackChunker, OverlapStrategy

# Create chunker instance
chunker = OverlappingFallbackChunker()

# Example: Chunk a text file with fixed overlap
chunks = chunker.chunk_with_overlap(
    content=text_content,
    file_path="document.txt",
    chunk_size=1000,  # 1000 characters per chunk
    overlap_size=200,  # 200 character overlap
    strategy=OverlapStrategy.FIXED,
    unit="characters"
)

# Example: Chunk by lines with percentage overlap
chunks = chunker.chunk_with_overlap(
    content=log_content,
    file_path="app.log",
    chunk_size=50,  # 50 lines per chunk
    overlap_size=20,  # 20% overlap (10 lines)
    strategy=OverlapStrategy.PERCENTAGE,
    unit="lines"
)

# Example: Asymmetric overlap (different before/after)
chunks = chunker.chunk_with_asymmetric_overlap(
    content=content,
    file_path="data.txt",
    chunk_size=1000,
    overlap_before=100,  # Small overlap with previous chunk
    overlap_after=300,   # Larger overlap with next chunk
    unit="characters"
)

# Example: Dynamic overlap based on natural boundaries
chunks = chunker.chunk_with_dynamic_overlap(
    content=content,
    file_path="document.txt",
    chunk_size=1000,
    min_overlap=50,
    max_overlap=300,
    unit="characters"
)
```

## Overlap Strategies

### Fixed Overlap
Uses a fixed number of lines or characters for overlap between chunks.

### Percentage Overlap
Calculates overlap as a percentage of the chunk size.

### Dynamic Overlap
Adjusts overlap size to align with natural content boundaries like:
- Paragraph breaks
- Sentence endings
- Line breaks
- Punctuation boundaries

### Asymmetric Overlap
Allows different overlap sizes before and after each chunk, useful when:
- Context before is less important than context after
- Processing sequential data where future context matters more

## Warnings and Logging

The chunker will:
1. Emit a warning when used (to ensure users know fallback is being used)
2. Log the overlap strategy and parameters
3. Raise `TreeSitterOverlapError` if used on supported code files

## File Type Support

Supported file types include:
- Text files (.txt)
- Log files (.log)
- Markdown (.md)
- CSV files (.csv)
- JSON (.json) - for non-code JSON data
- XML (.xml)
- YAML (.yaml, .yml)
- Configuration files (.ini, .cfg, .conf)
- Any other file without Tree-sitter support

## Implementation Details

The chunker:
- Performs boundary detection for optimal overlap points
- Preserves Unicode content correctly
- Handles empty and small files gracefully
- Supports both line-based and character-based chunking
- Provides detailed chunk metadata including positions and line numbers