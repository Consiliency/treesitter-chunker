#!/usr/bin/env python3
"""Demo of overlapping fallback chunker for non-Tree-sitter files."""

import warnings

from chunker.fallback_overlap import OverlappingFallbackChunker, OverlapStrategy


def demo_log_file_chunking():
    """Demonstrate overlapping chunks on a log file."""
    print("=== Log File Chunking Demo ===\n")

    # Sample log content
    log_content = """2024-01-15 10:00:00 INFO Starting application server
2024-01-15 10:00:01 DEBUG Loading configuration from config.yml
2024-01-15 10:00:02 INFO Configuration loaded successfully
2024-01-15 10:00:03 ERROR Failed to connect to database: timeout
2024-01-15 10:00:04 WARN Retrying database connection (attempt 1/3)
2024-01-15 10:00:05 INFO Database connection established
2024-01-15 10:00:06 DEBUG Executing startup queries
2024-01-15 10:00:07 INFO All systems operational
2024-01-15 10:00:08 DEBUG Starting request handler
2024-01-15 10:00:09 INFO Server ready on port 8080"""

    chunker = OverlappingFallbackChunker()

    # Chunk with line-based overlap
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # Suppress warnings for demo
        chunks = chunker.chunk_with_overlap(
            log_content,
            "server.log",
            chunk_size=4,  # 4 lines per chunk
            overlap_size=2,  # 2 lines overlap
            strategy=OverlapStrategy.FIXED,
            unit="lines",
        )

    print(f"Created {len(chunks)} overlapping chunks:\n")

    for i, chunk in enumerate(chunks):
        lines = chunk.content.strip().split("\n")
        print(f"Chunk {i} (lines {chunk.start_line}-{chunk.end_line}):")
        for line in lines:
            print(f"  {line}")
        print()


def demo_markdown_chunking():
    """Demonstrate overlapping chunks on markdown content."""
    print("=== Markdown Chunking Demo ===\n")

    markdown_content = """# Project README

## Introduction

This project demonstrates the overlapping fallback chunker.
It's designed for files without Tree-sitter support.

## Features

- Configurable overlap strategies
- Support for line and character-based chunking
- Natural boundary detection
- Clear warnings when used

## Usage

The chunker can be used programmatically:

```python
chunker = OverlappingFallbackChunker()
chunks = chunker.chunk_with_overlap(content, path)
```

## Configuration

You can configure overlap size and strategy.
"""

    chunker = OverlappingFallbackChunker()

    # Chunk with character-based overlap
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        chunks = chunker.chunk_with_overlap(
            markdown_content,
            "README.md",
            chunk_size=150,  # 150 chars per chunk
            overlap_size=30,  # 20% overlap
            strategy=OverlapStrategy.PERCENTAGE,
            unit="characters",
        )

    print(f"Created {len(chunks)} overlapping chunks:\n")

    for i, chunk in enumerate(chunks):
        print(f"Chunk {i} ({chunk.byte_start}-{chunk.byte_end} bytes):")
        print(
            (
                f"  Preview: {chunk.content[:60]}..."
                if len(chunk.content) > 60
                else f"  Content: {chunk.content}"
            ),
        )
        print()


def demo_error_on_code_file():
    """Demonstrate that code files with Tree-sitter support are rejected."""
    print("=== Error Demo for Code Files ===\n")

    chunker = OverlappingFallbackChunker()

    try:
        # This should fail because Go has Tree-sitter support
        chunker.chunk_with_overlap(
            "package main\n\nfunc main() {}",
            "main.go",
            chunk_size=100,
            overlap_size=20,
        )
    except Exception as e:
        print(f"Expected error occurred: {e}")
        print(
            "\nThis is correct behavior - overlapping chunks are ONLY for non-Tree-sitter files!",
        )


if __name__ == "__main__":
    demo_log_file_chunking()
    print("\n" + "=" * 50 + "\n")
    demo_markdown_chunking()
    print("\n" + "=" * 50 + "\n")
    demo_error_on_code_file()
