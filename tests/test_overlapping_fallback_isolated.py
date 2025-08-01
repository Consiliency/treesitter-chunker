"""Tests for overlapping fallback chunker - isolated version."""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, Path(Path(Path(__file__).resolve().parent).parent))
from chunker.fallback.overlapping import OverlappingFallbackChunker, OverlapStrategy


class TestOverlappingFallbackChunker:
    """Test suite for overlapping fallback chunker."""

    @classmethod
    @pytest.fixture
    def chunker(cls):
        """Create a chunker instance."""
        return OverlappingFallbackChunker()

    @staticmethod
    @pytest.fixture
    def sample_text():
        """Sample text content for testing."""
        return """Line 1: Introduction
Line 2: This is a test document
Line 3: With multiple lines
Line 4: To test overlapping chunks

Line 6: Second paragraph starts here
Line 7: With more content
Line 8: And additional information
Line 9: To create meaningful chunks

Line 11: Third paragraph
Line 12: Contains even more text
Line 13: For comprehensive testing
Line 14: Of the chunking algorithm

Line 16: Final paragraph
Line 17: Wraps up the content
Line 18: With concluding remarks
Line 19: End of document"""

    @staticmethod
    @pytest.fixture
    def sample_markdown():
        """Sample markdown content."""
        return """# Main Title

This is the introduction paragraph with some context about the document.
It spans multiple lines to provide enough content for chunking.

## Section 1: Overview

Here we have the first section with detailed information.
This section contains multiple paragraphs to test overlap detection.

The chunker should ideally find natural boundaries at paragraph breaks.
This helps maintain context when processing chunks.

## Section 2: Details

More content in the second section.
We want to ensure overlapping works correctly.

### Subsection 2.1

Even more detailed content here.
Testing nested structure handling.

## Conclusion

Final thoughts and summary."""

    @staticmethod
    def test_fixed_overlap_by_lines(chunker, sample_text):
        """Test fixed overlap strategy with line-based chunking."""
        chunks = chunker.chunk_with_overlap(content=sample_text, file_path="test.txt", chunk_size=5, overlap_size=2, strategy=OverlapStrategy.FIXED, unit="lines")
        assert len(chunks) > 1
        for i, chunk in enumerate(chunks[:-1]):
            lines = chunk.content.count("\n") + 1
            if i == 0:
                assert lines == 5
            else:
                assert lines >= 5
        for i in range(len(chunks) - 1):
            chunk1_lines = chunks[i].content.splitlines()
            chunk2_lines = chunks[i + 1].content.splitlines()
            if len(chunk1_lines) >= 2 and len(chunk2_lines) >= 2:
                overlap_found = any(line in chunk2_lines for line in
                    chunk1_lines[-2:])
                assert overlap_found

    @staticmethod
    def test_fixed_overlap_by_characters(chunker, sample_text):
        """Test fixed overlap strategy with character-based chunking."""
        chunks = chunker.chunk_with_overlap(content=sample_text, file_path="test.txt", chunk_size=100, overlap_size=20, strategy=OverlapStrategy.FIXED, unit="characters")
        assert len(chunks) > 1
        for i in range(len(chunks) - 1):
            chunk1 = chunks[i].content
            chunk2 = chunks[i + 1].content
            if len(chunk1) >= 20:
                overlap_text = chunk1[-20:]
                assert overlap_text in chunk2

    @staticmethod
    def test_percentage_overlap(chunker, sample_text):
        """Test percentage-based overlap calculation."""
        chunks = chunker.chunk_with_overlap(content=sample_text, file_path="test.txt", chunk_size=100, overlap_size=20, strategy=OverlapStrategy.PERCENTAGE, unit="characters")
        assert len(chunks) > 1
        for i in range(len(chunks) - 1):
            if len(chunks[i].content) >= 20:
                overlap = chunks[i].content[-20:]
                assert overlap in chunks[i + 1].content

    @staticmethod
    def test_asymmetric_overlap(chunker, sample_text):
        """Test asymmetric overlap with different before/after sizes."""
        chunks = chunker.chunk_with_asymmetric_overlap(content=sample_text,
            file_path="test.txt", chunk_size=5, overlap_before=1,
            overlap_after=2, unit="lines")
        assert len(chunks) > 1
        for i in range(1, len(chunks) - 1):
            chunk = chunks[i]
            lines = chunk.content.splitlines()
            assert len(lines) >= 5

    @staticmethod
    def test_dynamic_overlap_markdown(chunker, sample_markdown):
        """Test dynamic overlap that adjusts based on content."""
        chunks = chunker.chunk_with_dynamic_overlap(content=sample_markdown,
            file_path="test.md", chunk_size=200, min_overlap=20,
            max_overlap=60, unit="characters")
        assert len(chunks) > 1
        overlap_sizes = []
        for i in range(len(chunks) - 1):
            chunk1 = chunks[i].content
            chunk2 = chunks[i + 1].content
            for overlap_size in range(min(len(chunk1), len(chunk2)), 0, -1):
                if chunk1[-overlap_size:] == chunk2[:overlap_size]:
                    overlap_sizes.append(overlap_size)
                    break
        if len(overlap_sizes) > 1:
            assert len(set(overlap_sizes)) > 1 or min(overlap_sizes) >= 20

    @staticmethod
    def test_natural_boundary_detection(chunker, sample_markdown):
        """Test natural boundary detection for overlap points."""
        position = 100
        boundary = chunker.find_natural_overlap_boundary(content=sample_markdown, desired_position=position, search_window=50)
        assert abs(boundary - position) <= 50
        if boundary > 0 and boundary < len(sample_markdown):
            before = sample_markdown[max(0, boundary - 2):boundary]
            assert any(char in before for char in [" ", "\n", ".", "!", "?"])

    @staticmethod
    def test_empty_content(chunker):
        """Test handling of empty content."""
        chunks = chunker.chunk_with_overlap(content="", file_path="empty.txt", chunk_size=100, overlap_size=20)
        assert len(chunks) == 0

    @staticmethod
    def test_single_line_content(chunker):
        """Test handling of very short content."""
        content = "This is a single line of text."
        chunks = chunker.chunk_with_overlap(content=content, file_path="single.txt", chunk_size=10, overlap_size=5, unit="characters")
        assert len(chunks) >= 1
        for chunk in chunks:
            assert chunk.content.strip()

    @staticmethod
    def test_chunk_metadata(chunker, sample_text):
        """Test that chunk metadata is correctly set."""
        chunks = chunker.chunk_with_overlap(content=sample_text, file_path="test.txt", chunk_size=100, overlap_size=20)
        for i, chunk in enumerate(chunks):
            assert chunk.file_path == "test.txt"
            assert chunk.language == "text"
            assert chunk.node_type == "fallback_overlap_chars"
            assert chunk.parent_context == f"overlap_chunk_{i}"
            assert chunk.start_line >= 1
            assert chunk.end_line >= chunk.start_line
            assert chunk.byte_start >= 0
            assert chunk.byte_end > chunk.byte_start
            assert chunk.chunk_id

    @staticmethod
    def test_large_overlap(chunker, sample_text):
        """Test handling when overlap size is larger than chunk size."""
        chunks = chunker.chunk_with_overlap(content=sample_text, file_path="test.txt", chunk_size=50, overlap_size=100, unit="characters")
        assert len(chunks) > 0
        for chunk in chunks:
            assert chunk.content

    @staticmethod
    def test_different_file_types(chunker):
        """Test language detection for different file types."""
        test_cases = [("test.txt", "text"), ("test.log", "log"), ("test.md",
            "markdown"), ("test.csv", "csv"), ("test.json", "json"), (
            "test.xml", "xml"), ("test.yaml", "yaml"), ("test.yml", "yaml"),
            ("test.ini", "ini"), ("test.cfg", "config"), ("test.conf",
            "config"), ("test.unknown", "unknown")]
        for file_path, expected_lang in test_cases:
            chunks = chunker.chunk_with_overlap(content="Test content",
                file_path=file_path, chunk_size=10)
            if chunks:
                assert chunks[0].language == expected_lang

    @staticmethod
    def test_unicode_content(chunker):
        """Test handling of Unicode content."""
        content = """Hello 世界
This is a test with émojis 🌟
And special characters: ñ, ü, ß
Mathematical: ∑, ∫, ∞
End of test."""
        chunks = chunker.chunk_with_overlap(content=content, file_path="unicode.txt", chunk_size=50, overlap_size=10, unit="characters")
        assert len(chunks) > 0
        reconstructed = ""
        for i, chunk in enumerate(chunks):
            if i == 0:
                reconstructed = chunk.content
            else:
                reconstructed += chunk.content[10:]
        assert "世界" in reconstructed
        assert "🌟" in reconstructed
        assert "∑" in reconstructed

    @staticmethod
    def test_line_ending_preservation(chunker):
        """Test that different line endings are preserved."""
        content_lf = "Line 1\nLine 2\nLine 3\n"
        chunks_lf = chunker.chunk_with_overlap(content=content_lf,
            file_path="test.txt", chunk_size=2, overlap_size=1, unit="lines")
        assert all("\n" in chunk.content for chunk in chunks_lf if len(
            chunk.content) > 1)
        content_crlf = "Line 1\r\nLine 2\r\nLine 3\r\n"
        chunks_crlf = chunker.chunk_with_overlap(content=content_crlf,
            file_path="test.txt", chunk_size=2, overlap_size=1, unit="lines")
        assert all("\r\n" in chunk.content for chunk in chunks_crlf if len(
            chunk.content) > 2)

    @staticmethod
    def test_performance_large_file(chunker):
        """Test performance with large file content."""
        large_content = "x" * 80 + "\n"
        large_content *= 12500
        start = time.time()
        chunks = chunker.chunk_with_overlap(content=large_content,
            file_path="large.txt", chunk_size=1000, overlap_size=100, unit="characters")
        elapsed = time.time() - start
        assert elapsed < 1.0
        assert len(chunks) > 100
        total_size = sum(len(chunk.content) for chunk in chunks)
        assert total_size > len(large_content)
