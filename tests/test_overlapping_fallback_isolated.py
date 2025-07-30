"""Tests for overlapping fallback chunker - isolated version."""

import os

# Import only what we need, avoiding the problematic plugin imports
import sys
from pathlib import Path

import pytest

sys.path.insert(0, Path(os.path.dirname(Path(__file__).resolve().parent)))

from chunker.fallback.overlapping import OverlappingFallbackChunker, OverlapStrategy


class TestOverlappingFallbackChunker:
    """Test suite for overlapping fallback chunker."""

    @pytest.fixture
    def chunker(self):
        """Create a chunker instance."""
        return OverlappingFallbackChunker()

    @pytest.fixture
    def sample_text(self):
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

    @pytest.fixture
    def sample_markdown(self):
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

    def test_fixed_overlap_by_lines(self, chunker, sample_text):
        """Test fixed overlap strategy with line-based chunking."""
        chunks = chunker.chunk_with_overlap(
            content=sample_text,
            file_path="test.txt",
            chunk_size=5,  # 5 lines per chunk
            overlap_size=2,  # 2 lines overlap
            strategy=OverlapStrategy.FIXED,
            unit="lines",
        )

        assert len(chunks) > 1

        # Check that chunks have correct size (except possibly the last one)
        for i, chunk in enumerate(chunks[:-1]):
            lines = chunk.content.count("\n") + 1
            # First chunk has no backward overlap
            if i == 0:
                assert lines == 5
            else:
                # Other chunks include overlap from previous
                assert lines >= 5

        # Verify overlap exists between consecutive chunks
        for i in range(len(chunks) - 1):
            chunk1_lines = chunks[i].content.splitlines()
            chunk2_lines = chunks[i + 1].content.splitlines()

            # Check that end of chunk1 appears in beginning of chunk2
            if len(chunk1_lines) >= 2 and len(chunk2_lines) >= 2:
                # Some overlap should exist
                overlap_found = any(line in chunk2_lines for line in chunk1_lines[-2:])
                assert overlap_found

    def test_fixed_overlap_by_characters(self, chunker, sample_text):
        """Test fixed overlap strategy with character-based chunking."""
        chunks = chunker.chunk_with_overlap(
            content=sample_text,
            file_path="test.txt",
            chunk_size=100,  # 100 chars per chunk
            overlap_size=20,  # 20 chars overlap
            strategy=OverlapStrategy.FIXED,
            unit="characters",
        )

        assert len(chunks) > 1

        # Verify overlap between consecutive chunks
        for i in range(len(chunks) - 1):
            chunk1 = chunks[i].content
            chunk2 = chunks[i + 1].content

            # End of chunk1 should appear in beginning of chunk2
            if len(chunk1) >= 20:
                overlap_text = chunk1[-20:]
                assert overlap_text in chunk2

    def test_percentage_overlap(self, chunker, sample_text):
        """Test percentage-based overlap calculation."""
        chunks = chunker.chunk_with_overlap(
            content=sample_text,
            file_path="test.txt",
            chunk_size=100,
            overlap_size=20,  # 20% of chunk_size = 20 chars
            strategy=OverlapStrategy.PERCENTAGE,
            unit="characters",
        )

        assert len(chunks) > 1

        # With 20% overlap of 100 chars = 20 chars overlap
        for i in range(len(chunks) - 1):
            if len(chunks[i].content) >= 20:
                overlap = chunks[i].content[-20:]
                assert overlap in chunks[i + 1].content

    def test_asymmetric_overlap(self, chunker, sample_text):
        """Test asymmetric overlap with different before/after sizes."""
        chunks = chunker.chunk_with_asymmetric_overlap(
            content=sample_text,
            file_path="test.txt",
            chunk_size=5,  # 5 lines base
            overlap_before=1,  # 1 line before
            overlap_after=2,  # 2 lines after
            unit="lines",
        )

        assert len(chunks) > 1

        # Verify asymmetric overlap
        for i in range(1, len(chunks) - 1):
            chunk = chunks[i]
            lines = chunk.content.splitlines()

            # Should have backward overlap of 1 line
            # and forward overlap of 2 lines
            # Total lines should be around 5 + 1 + 2 = 8
            # (less for edge chunks)
            assert len(lines) >= 5

    def test_dynamic_overlap_markdown(self, chunker, sample_markdown):
        """Test dynamic overlap that adjusts based on content."""
        chunks = chunker.chunk_with_dynamic_overlap(
            content=sample_markdown,
            file_path="test.md",
            chunk_size=200,
            min_overlap=20,
            max_overlap=60,
            unit="characters",
        )

        assert len(chunks) > 1

        # Dynamic overlap should vary between chunks
        overlap_sizes = []
        for i in range(len(chunks) - 1):
            chunk1 = chunks[i].content
            chunk2 = chunks[i + 1].content

            # Find actual overlap
            for overlap_size in range(min(len(chunk1), len(chunk2)), 0, -1):
                if chunk1[-overlap_size:] == chunk2[:overlap_size]:
                    overlap_sizes.append(overlap_size)
                    break

        # Should have varying overlap sizes
        if len(overlap_sizes) > 1:
            assert len(set(overlap_sizes)) > 1 or min(overlap_sizes) >= 20

    def test_natural_boundary_detection(self, chunker, sample_markdown):
        """Test natural boundary detection for overlap points."""
        # Test with markdown content
        position = 100
        boundary = chunker.find_natural_overlap_boundary(
            content=sample_markdown,
            desired_position=position,
            search_window=50,
        )

        # Should find a boundary near the position
        assert abs(boundary - position) <= 50

        # Boundary should be at a natural break point
        if boundary > 0 and boundary < len(sample_markdown):
            # Check what comes before the boundary
            before = sample_markdown[max(0, boundary - 2) : boundary]
            # Should be at a space, newline, or punctuation
            assert any(char in before for char in [" ", "\n", ".", "!", "?"])

    def test_empty_content(self, chunker):
        """Test handling of empty content."""
        chunks = chunker.chunk_with_overlap(
            content="",
            file_path="empty.txt",
            chunk_size=100,
            overlap_size=20,
        )

        assert len(chunks) == 0

    def test_single_line_content(self, chunker):
        """Test handling of very short content."""
        content = "This is a single line of text."
        chunks = chunker.chunk_with_overlap(
            content=content,
            file_path="single.txt",
            chunk_size=10,
            overlap_size=5,
            unit="characters",
        )

        assert len(chunks) >= 1
        # All chunks should contain valid content
        for chunk in chunks:
            assert chunk.content.strip()

    def test_chunk_metadata(self, chunker, sample_text):
        """Test that chunk metadata is correctly set."""
        chunks = chunker.chunk_with_overlap(
            content=sample_text,
            file_path="test.txt",
            chunk_size=100,
            overlap_size=20,
        )

        for i, chunk in enumerate(chunks):
            # Check required fields
            assert chunk.file_path == "test.txt"
            assert chunk.language == "text"
            assert chunk.node_type == "fallback_overlap_chars"
            assert chunk.parent_context == f"overlap_chunk_{i}"

            # Check position fields
            assert chunk.start_line >= 1
            assert chunk.end_line >= chunk.start_line
            assert chunk.byte_start >= 0
            assert chunk.byte_end > chunk.byte_start
            assert chunk.chunk_id  # Should have generated ID

    def test_large_overlap(self, chunker, sample_text):
        """Test handling when overlap size is larger than chunk size."""
        # This should still work but overlap will be limited
        chunks = chunker.chunk_with_overlap(
            content=sample_text,
            file_path="test.txt",
            chunk_size=50,
            overlap_size=100,  # Larger than chunk size
            unit="characters",
        )

        assert len(chunks) > 0
        # Should still produce valid chunks
        for chunk in chunks:
            assert chunk.content

    def test_different_file_types(self, chunker):
        """Test language detection for different file types."""
        test_cases = [
            ("test.txt", "text"),
            ("test.log", "log"),
            ("test.md", "markdown"),
            ("test.csv", "csv"),
            ("test.json", "json"),
            ("test.xml", "xml"),
            ("test.yaml", "yaml"),
            ("test.yml", "yaml"),
            ("test.ini", "ini"),
            ("test.cfg", "config"),
            ("test.conf", "config"),
            ("test.unknown", "unknown"),
        ]

        for file_path, expected_lang in test_cases:
            chunks = chunker.chunk_with_overlap(
                content="Test content",
                file_path=file_path,
                chunk_size=10,
            )

            if chunks:
                assert chunks[0].language == expected_lang

    def test_unicode_content(self, chunker):
        """Test handling of Unicode content."""
        content = """Hello 世界
This is a test with émojis 🌟
And special characters: ñ, ü, ß
Mathematical: ∑, ∫, ∞
End of test."""

        chunks = chunker.chunk_with_overlap(
            content=content,
            file_path="unicode.txt",
            chunk_size=50,
            overlap_size=10,
            unit="characters",
        )

        assert len(chunks) > 0

        # Verify content is preserved correctly
        reconstructed = ""
        for i, chunk in enumerate(chunks):
            if i == 0:
                reconstructed = chunk.content
            else:
                # Find where the overlap ends and new content begins
                # This is approximate due to overlap
                reconstructed += chunk.content[10:]  # Skip overlap

        # Original content should be mostly preserved
        assert "世界" in reconstructed
        assert "🌟" in reconstructed
        assert "∑" in reconstructed

    def test_line_ending_preservation(self, chunker):
        """Test that different line endings are preserved."""
        # Unix line endings
        content_lf = "Line 1\nLine 2\nLine 3\n"
        chunks_lf = chunker.chunk_with_overlap(
            content=content_lf,
            file_path="test.txt",
            chunk_size=2,
            overlap_size=1,
            unit="lines",
        )

        assert all(
            "\n" in chunk.content for chunk in chunks_lf if len(chunk.content) > 1
        )

        # Windows line endings
        content_crlf = "Line 1\r\nLine 2\r\nLine 3\r\n"
        chunks_crlf = chunker.chunk_with_overlap(
            content=content_crlf,
            file_path="test.txt",
            chunk_size=2,
            overlap_size=1,
            unit="lines",
        )

        assert all(
            "\r\n" in chunk.content for chunk in chunks_crlf if len(chunk.content) > 2
        )

    def test_performance_large_file(self, chunker):
        """Test performance with large file content."""
        # Generate large content (1MB)
        large_content = "x" * 80 + "\n"  # 81 bytes per line
        large_content = large_content * 12500  # ~1MB

        import time

        start = time.time()

        chunks = chunker.chunk_with_overlap(
            content=large_content,
            file_path="large.txt",
            chunk_size=1000,
            overlap_size=100,
            unit="characters",
        )

        elapsed = time.time() - start

        # Should complete in reasonable time (< 1 second for 1MB)
        assert elapsed < 1.0
        assert len(chunks) > 100  # Should produce many chunks

        # Verify all chunks are valid
        total_size = sum(len(chunk.content) for chunk in chunks)
        assert total_size > len(large_content)  # Due to overlap
