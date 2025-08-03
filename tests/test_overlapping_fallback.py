"""Tests for overlapping fallback chunker."""
import logging
import warnings

import pytest

from chunker.fallback.base import FallbackConfig, FallbackWarning
from chunker.fallback_overlap.chunker import (
    OverlappingFallbackChunker,
    OverlapStrategy,
    TreeSitterOverlapError,
)
from chunker.interfaces.fallback import ChunkingMethod


class TestOverlappingFallbackChunker:
    """Test overlapping fallback chunker implementation."""

    @classmethod
    @pytest.fixture
    def chunker(cls):
        """Create an overlapping fallback chunker instance."""
        return OverlappingFallbackChunker()

    @staticmethod
    @pytest.fixture
    def log_content():
        """Sample log file content."""
        return """2024-01-15 10:00:00 INFO Starting application
2024-01-15 10:00:01 DEBUG Loading configuration
2024-01-15 10:00:02 INFO Configuration loaded successfully
2024-01-15 10:00:03 ERROR Failed to connect to database
2024-01-15 10:00:04 WARN Retrying connection
2024-01-15 10:00:05 INFO Connection established
2024-01-15 10:00:06 DEBUG Executing query
2024-01-15 10:00:07 INFO Query completed
2024-01-15 10:00:08 DEBUG Processing results
2024-01-15 10:00:09 INFO Results processed
2024-01-15 10:00:10 INFO Application ready"""

    @staticmethod
    @pytest.fixture
    def markdown_content():
        """Sample markdown content."""
        return """# Project Documentation

## Introduction

This is a sample project that demonstrates various features.
The project includes multiple components and modules.

## Installation

To install the project, follow these steps:

1. Clone the repository
2. Install dependencies
3. Run the setup script

## Usage

The project can be used in several ways:

### Command Line

Use the CLI tool to interact with the system:

```bash
project-cli --help
```

### API

The API provides programmatic access:

```python
from project import Client
client = Client()
```

## Configuration

Configuration options are available in the config file.
You can customize various aspects of the behavior.

## Troubleshooting

If you encounter issues, check the following:

- Ensure all dependencies are installed
- Verify configuration settings
- Check the log files

## Contributing

Contributions are welcome! Please read the guidelines."""

    @staticmethod
    def test_treesitter_overlap_error_go(chunker):
        """Test that overlapping fails for Go files (Tree-sitter supported)."""
        with pytest.raises(TreeSitterOverlapError) as exc_info:
            chunker.chunk_with_overlap("package main\nfunc main() {}",
                "test.go", chunk_size=100, overlap_size=20)
        assert "go" in str(exc_info.value).lower()

    @staticmethod
    def test_treesitter_overlap_error_java(chunker):
        """Test that overlapping fails for Java files."""
        with pytest.raises(TreeSitterOverlapError) as exc_info:
            chunker.chunk_with_overlap("public class Test {}", "test.java",
                chunk_size=100, overlap_size=20)
        assert "java" in str(exc_info.value).lower()

    @staticmethod
    def test_treesitter_overlap_error_explicit_language(chunker):
        """Test that overlapping fails when language is explicitly provided."""
        with pytest.raises(TreeSitterOverlapError) as exc_info:
            chunker.chunk_with_overlap("some content", "file.txt",
                chunk_size=100, overlap_size=20, language="go")
        assert "go" in str(exc_info.value).lower()

    @staticmethod
    def test_fixed_overlap_by_lines(chunker, log_content):
        """Test fixed overlap strategy with line-based chunking."""
        with warnings.catch_warnings(record=True) as w:
            chunks = chunker.chunk_with_overlap(log_content, "app.log",
                chunk_size=3, overlap_size=1, strategy=OverlapStrategy.
                FIXED, unit="lines")
            fallback_warnings = [warn for warn in w if issubclass(warn.
                category, FallbackWarning)]
            assert len(fallback_warnings) == 1
            assert "overlapping fallback" in str(fallback_warnings[0].message,
                ).lower()
        assert len(chunks) > 1
        log_content.strip().split("\n")
        for i in range(1, len(chunks)):
            prev_lines = chunks[i - 1].content.strip().split("\n")
            curr_lines = chunks[i].content.strip().split("\n")
            assert prev_lines[-1] == curr_lines[0
                ], f"Chunk {i - 1} last line doesn't match chunk {i} first line"

    @staticmethod
    def test_fixed_overlap_by_characters(chunker, markdown_content):
        """Test fixed overlap strategy with character-based chunking."""
        with warnings.catch_warnings(record=True) as w:
            chunks = chunker.chunk_with_overlap(markdown_content,
                "README.md", chunk_size=200, overlap_size=50, strategy=OverlapStrategy.FIXED, unit="characters")
            fallback_warnings = [warn for warn in w if issubclass(warn.
                category, FallbackWarning)]
            assert len(fallback_warnings) == 1
            assert "overlapping fallback" in str(fallback_warnings[0].message,
                ).lower()
        for i in range(1, len(chunks)):
            prev_chunk = chunks[i - 1].content
            curr_chunk = chunks[i].content
            if i < len(chunks) - 1:
                assert len(curr_chunk,
                    ) > 50, f"Chunk {i} is too small: {len(curr_chunk)} chars"
            overlap_size = min(50, len(prev_chunk), len(curr_chunk))
            prev_end = prev_chunk[-overlap_size:]
            curr_start = curr_chunk[:overlap_size]
            assert prev_end == curr_start, f"No overlap between chunks {i - 1} and {i}"

    @staticmethod
    def test_percentage_overlap(chunker, log_content):
        """Test percentage-based overlap strategy."""
        with warnings.catch_warnings(record=True):
            chunks = chunker.chunk_with_overlap(log_content, "app.log",
                chunk_size=4, overlap_size=25, strategy=OverlapStrategy.
                PERCENTAGE, unit="lines")
        for i in range(1, len(chunks)):
            prev_lines = chunks[i - 1].content.strip().split("\n")
            curr_lines = chunks[i].content.strip().split("\n")
            assert prev_lines[-1] == curr_lines[0]

    @staticmethod
    def test_asymmetric_overlap(chunker, markdown_content):
        """Test asymmetric overlap with different before/after sizes."""
        with warnings.catch_warnings(record=True) as w:
            chunks = chunker.chunk_with_asymmetric_overlap(markdown_content,
                "README.md", chunk_size=300, overlap_before=50,
                overlap_after=100, unit="characters")
            fallback_warnings = [warn for warn in w if issubclass(warn.
                category, FallbackWarning)]
            assert len(fallback_warnings) == 1
            assert "asymmetric" in str(fallback_warnings[0].message).lower()
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk.content) > 0
            assert chunk.node_type == "fallback_asymmetric_chars"

    @staticmethod
    def test_dynamic_overlap(chunker, markdown_content):
        """Test dynamic overlap that adjusts based on content."""
        with warnings.catch_warnings(record=True) as w:
            chunks = chunker.chunk_with_dynamic_overlap(markdown_content,
                "README.md", chunk_size=400, min_overlap=50, max_overlap=150, unit="characters")
            fallback_warnings = [warn for warn in w if issubclass(warn.
                category, FallbackWarning)]
            assert len(fallback_warnings) == 1
            assert "dynamic" in str(fallback_warnings[0].message).lower()
        assert len(chunks) > 1
        for chunk in chunks:
            assert chunk.node_type == "fallback_dynamic_chars"

    @staticmethod
    def test_natural_boundary_detection(chunker):
        """Test finding natural boundaries for overlap."""
        content = """First paragraph ends here.

Second paragraph starts here and continues
with more text on multiple lines.

Third paragraph is shorter."""
        pos = chunker.find_natural_overlap_boundary(content, 30, 20)
        assert content[pos - 2:pos] == "\n\n"
        content2 = (
            "This is the first sentence. This is the second sentence. And the third."
            )
        pos = chunker.find_natural_overlap_boundary(content2, 35, 20)
        assert content2[pos - 2:pos] == ". "

    @staticmethod
    def test_chunk_metadata(chunker, log_content):
        """Test that chunks have correct metadata."""
        with warnings.catch_warnings(record=True):
            chunks = chunker.chunk_with_overlap(log_content, "server.log",
                chunk_size=3, overlap_size=1, strategy=OverlapStrategy.
                FIXED, unit="lines")
        for i, chunk in enumerate(chunks):
            assert chunk.file_path == "server.log"
            assert chunk.language == "log"
            assert chunk.node_type == "fallback_overlapping_lines"
            assert chunk.parent_context == f"overlapping_chunk_{i}"
            assert chunk.start_line > 0
            assert chunk.end_line >= chunk.start_line
            assert chunk.byte_start >= 0
            assert chunk.byte_end > chunk.byte_start

    @staticmethod
    def test_empty_content(chunker):
        """Test handling of empty content."""
        with warnings.catch_warnings(record=True):
            chunks = chunker.chunk_with_overlap("", "empty.txt", chunk_size=100, overlap_size=20)
        assert len(chunks) == 0

    @staticmethod
    def test_single_chunk_no_overlap(chunker):
        """Test content that fits in a single chunk."""
        content = "This is a short text."
        with warnings.catch_warnings(record=True):
            chunks = chunker.chunk_with_overlap(content, "short.txt",
                chunk_size=1000, overlap_size=100, unit="characters")
        assert len(chunks) == 1
        assert chunks[0].content == content

    @staticmethod
    def test_warning_logging(chunker, log_content, caplog):
        """Test that warnings are properly logged."""
        caplog.set_level(logging.WARNING)
        with warnings.catch_warnings(record=True):
            chunker.chunk_with_overlap(log_content, "app.log", chunk_size=100, overlap_size=20)
        assert any("overlapping fallback" in record.message.lower() for
            record in caplog.records)
        assert any("app.log" in record.message for record in caplog.records)

    @staticmethod
    def test_line_overlap_boundary_conditions(chunker):
        """Test edge cases for line-based overlap."""
        content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        with warnings.catch_warnings(record=True):
            chunks = chunker.chunk_with_overlap(content, "test.txt",
                chunk_size=2, overlap_size=3, strategy=OverlapStrategy.
                FIXED, unit="lines")
        assert len(chunks) > 0
        for chunk in chunks:
            assert len(chunk.content) > 0

    @staticmethod
    def test_character_overlap_boundary_conditions(chunker):
        """Test edge cases for character-based overlap."""
        content = "abcdefghijklmnopqrstuvwxyz"
        with warnings.catch_warnings(record=True):
            chunks = chunker.chunk_with_overlap(content, "alphabet.txt",
                chunk_size=5, overlap_size=5, strategy=OverlapStrategy.
                FIXED, unit="characters")
        assert len(chunks) > 0

    @staticmethod
    def test_unicode_content(chunker):
        """Test handling of Unicode content."""
        content = "Hello 👋 World 🌍! Testing émojis and spëcial characters™."
        with warnings.catch_warnings(record=True):
            chunks = chunker.chunk_with_overlap(content, "unicode.txt",
                chunk_size=20, overlap_size=5, unit="characters")
        assert len(chunks) > 0
        reconstructed = ""
        for i, chunk in enumerate(chunks):
            if i == 0:
                reconstructed = chunk.content
            else:
                overlap_size = 5
                non_overlap = chunk.content[overlap_size:]
                reconstructed += non_overlap
        assert content in reconstructed


class TestOverlappingFallbackIntegration:
    """Integration tests for overlapping fallback chunker."""

    @classmethod
    def test_with_base_fallback_methods(cls):
        """Test that base fallback methods still work."""
        chunker = OverlappingFallbackChunker()
        content = "Line 1\nLine 2\nLine 3\nLine 4"
        assert chunker.can_handle("test.txt", "text")
        with warnings.catch_warnings(record=True):
            chunks = chunker.chunk_text(content, "test.txt")
        assert len(chunks) > 0

    @classmethod
    def test_configuration(cls):
        """Test configuration of overlapping chunker."""
        config = FallbackConfig(method=ChunkingMethod.LINE_BASED,
            chunk_size=50, overlap=10)
        chunker = OverlappingFallbackChunker(config=config)
        assert chunker.config.chunk_size == 50
        assert chunker.config.overlap == 10
        chunker.configure({"chunk_size": 100, "overlap": 20})
        assert chunker.config.chunk_size == 100
        assert chunker.config.overlap == 20

    @pytest.mark.parametrize(("extension", "should_fail"), [(".go", True),
        (".java", True), (".rb", True), (".cs", True), (".kt", True), (
        ".py", False), (".js", False), (".c", False), (".cpp", False), (
        ".rs", False), (".txt", False), (".log", False), (".md", False), (
        ".csv", False), (".json", False)])
    @classmethod
    def test_file_extension_detection(cls, extension, should_fail):
        """Test Tree-sitter support detection for various file extensions."""
        chunker = OverlappingFallbackChunker()
        if should_fail:
            with pytest.raises(TreeSitterOverlapError):
                chunker.chunk_with_overlap("content", f"test{extension}",
                    chunk_size=100, overlap_size=20)
        else:
            with warnings.catch_warnings(record=True):
                chunks = chunker.chunk_with_overlap("content",
                    f"test{extension}", chunk_size=100, overlap_size=20)
            assert isinstance(chunks, list)
