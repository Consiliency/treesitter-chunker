"""Integration tests for Phase 9 overlapping fallback with other features."""

import pytest

from chunker import BaseMetadataExtractor as MetadataExtractor
from chunker import (
    ChunkHierarchyBuilder,
    FallbackChunker,
    FallbackStrategy,
    TiktokenCounter,
)


class TestOverlappingFallbackIntegration:
    """Test overlapping fallback working with other Phase 9 features."""

    @pytest.fixture
    def complex_file(self, tmp_path):
        """Create a complex file that benefits from overlapping."""
        test_file = tmp_path / "complex.py"
        test_file.write_text(
            '''
import os
import sys
from typing import List, Dict, Optional

# Global configuration
CONFIG = {
    "debug": True,
    "max_retries": 3,
    "timeout": 30
}

class DataProcessor:
    """Process data with various transformations."""

    def __init__(self, config: Dict):
        self.config = config
        self.data = []
        self.errors = []

    def load_data(self, path: str) -> List[Dict]:
        """Load data from file.

        This method reads data from the specified path and
        returns a list of dictionaries. It handles various
        file formats and encodings.
        """
        try:
            with Path(path).open('r') as f:
                # Process line by line for memory efficiency
                for line in f:
                    if line.strip():
                        self.data.append(self._parse_line(line))
        except FileNotFoundError:
            self.errors.append(f"File not found: {path}")
        except (FileNotFoundError, IOError, IndexError) as e:
            self.errors.append(f"Error loading data: {e}")
        return self.data

    def _parse_line(self, line: str) -> Dict:
        """Parse a single line of data."""
        parts = line.strip().split(',')
        return {
            'id': parts[0],
            'value': parts[1] if len(parts) > 1 else None,
            'timestamp': parts[2] if len(parts) > 2 else None
        }

    def transform_data(self) -> List[Dict]:
        """Apply transformations to loaded data.

        Transformations include:
        - Normalization
        - Validation
        - Enrichment
        """
        transformed = []
        for item in self.data:
            # Validate item
            if not self._validate_item(item):
                self.errors.append(f"Invalid item: {item}")
                continue

            # Normalize values
            item['value'] = self._normalize_value(item.get('value'))

            # Enrich with metadata
            item['processed_at'] = datetime.now()
            item['version'] = '1.0'

            transformed.append(item)

        return transformed

    def _validate_item(self, item: Dict) -> bool:
        """Validate a data item."""
        return (
            item.get('id') is not None and
            item.get('value') is not None
        )

    def _normalize_value(self, value: Optional[str]) -> Optional[str]:
        """Normalize a value."""
        if value is None:
            return None
        return value.strip().lower()

    def save_results(self, output_path: str) -> None:
        """Save processed results to file."""
        with Path(output_path).open('w') as f:
            for item in self.transform_data():
                f.write(f"{item}\\n")

# Helper functions
def process_file(input_path: str, output_path: str) -> None:
    """Process a file using DataProcessor."""
    processor = DataProcessor(CONFIG)
    processor.load_data(input_path)
    processor.save_results(output_path)

def main():
    """Main entry point."""
    if len(sys.argv) < 3:
        print("Usage: script.py <input> <output>")
        sys.exit(1)

    process_file(sys.argv[1], sys.argv[2])

if __name__ == "__main__":
    main()
''',
        )
        return test_file

    def test_overlapping_with_token_counting(self, complex_file):
        """Test overlapping chunks with token limits."""
        # Create fallback chunker with overlap
        chunker = FallbackChunker(
            chunk_size=50,  # Small chunks to force overlapping
            chunk_overlap=10,  # 10 line overlap
            strategy=FallbackStrategy.PREFER_SEMANTIC,
            min_chunk_size=20,
        )

        counter = TiktokenCounter()

        # Process file with overlapping
        chunks = chunker.chunk_file(str(complex_file), "python")

        # Verify overlapping
        for i in range(len(chunks) - 1):
            current = chunks[i]
            next_chunk = chunks[i + 1]

            # Check overlap exists
            current_lines = current.content.split("\n")
            next_lines = next_chunk.content.split("\n")

            # Last few lines of current should appear in next
            overlap_found = any(
                line in next_lines for line in current_lines[-5:] if line.strip()
            )
            assert overlap_found or i == len(chunks) - 2  # Last chunk might not overlap

            # Count tokens
            current_tokens = counter.count_tokens(current.content)
            assert current_tokens > 0

    def test_overlapping_with_hierarchy(self, complex_file):
        """Test overlapping preserves hierarchy information."""
        chunker = FallbackChunker(
            chunk_size=40,
            chunk_overlap=5,
            preserve_hierarchy=True,
        )

        hierarchy_builder = ChunkHierarchyBuilder()

        # Get chunks with overlap
        chunks = chunker.chunk_file(str(complex_file), "python")

        # Build hierarchy
        hierarchy = hierarchy_builder.build_hierarchy(chunks)

        # Class chunks should still be parents
        class_chunks = [c for c in chunks if "class DataProcessor" in c.content]
        assert class_chunks

        # Methods should be children even with overlap
        method_chunks = [
            c for c in chunks if "def " in c.content and "class" not in c.content
        ]
        for method_chunk in method_chunks:
            # At least one class chunk should be parent
            parent = hierarchy.get_parent(method_chunk.chunk_id)
            if parent:
                parent_chunk = next((c for c in chunks if c.chunk_id == parent), None)
                assert parent_chunk
                assert "class" in parent_chunk.content

    def test_overlapping_with_metadata(self, complex_file):
        """Test overlapping chunks maintain metadata."""
        chunker = FallbackChunker(
            chunk_size=30,
            chunk_overlap=5,
        )

        extractor = MetadataExtractor()

        # Get overlapping chunks
        chunks = chunker.chunk_file(str(complex_file), "python")

        # Extract metadata
        for chunk in chunks:
            chunk.metadata = extractor.extract_metadata(chunk)

        # Verify metadata in overlapping regions
        for i in range(len(chunks) - 1):
            current = chunks[i]
            next_chunk = chunks[i + 1]

            # If both chunks contain same function, should have similar metadata
            if (
                "def load_data" in current.content
                and "def load_data" in next_chunk.content
            ):
                assert current.metadata.get("signatures") or next_chunk.metadata.get(
                    "signatures",
                )

    def test_fallback_strategies(self, complex_file):
        """Test different fallback strategies."""
        # Line-based strategy
        line_chunker = FallbackChunker(
            chunk_size=30,
            strategy=FallbackStrategy.LINE_BASED,
        )
        line_chunks = line_chunker.chunk_file(str(complex_file), "python")

        # Semantic strategy
        semantic_chunker = FallbackChunker(
            chunk_size=30,
            strategy=FallbackStrategy.PREFER_SEMANTIC,
        )
        semantic_chunks = semantic_chunker.chunk_file(str(complex_file), "python")

        # Syntax-aware strategy
        syntax_chunker = FallbackChunker(
            chunk_size=30,
            strategy=FallbackStrategy.SYNTAX_AWARE,
        )
        syntax_chunker.chunk_file(str(complex_file), "python")

        # Different strategies should produce different results
        assert (
            len(line_chunks) != len(semantic_chunks)
            or line_chunks[0].content != semantic_chunks[0].content
        )

        # Semantic should try to keep functions together
        semantic_contents = [c.content for c in semantic_chunks]
        complete_functions = sum(
            1
            for content in semantic_contents
            if "def " in content and content.count("def ") == 1 and "return" in content
        )
        assert complete_functions > 0

    def test_overlapping_edge_cases(self, tmp_path):
        """Test overlapping with edge cases."""
        # Very small file
        small_file = tmp_path / "small.py"
        small_file.write_text("def foo():\n    pass\n")

        chunker = FallbackChunker(chunk_size=10, chunk_overlap=5)
        chunks = chunker.chunk_file(str(small_file), "python")
        assert len(chunks) == 1  # Should not create overlap for tiny files

        # File with long lines
        long_line_file = tmp_path / "long.py"
        long_line_file.write_text(
            "x = '" + "a" * 200 + "'\n" + "y = '" + "b" * 200 + "'\n",
        )

        chunks = chunker.chunk_file(str(long_line_file), "python")
        assert all(chunk.content for chunk in chunks)  # No empty chunks

    def test_overlapping_with_unsupported_language(self, tmp_path):
        """Test fallback behavior for unsupported languages."""
        # Create file with unsupported extension
        strange_file = tmp_path / "config.strange"
        strange_file.write_text(
            """
[section1]
key1 = value1
key2 = value2

[section2]
key3 = value3
key4 = value4

# Comment line
[section3]
key5 = value5
""",
        )

        chunker = FallbackChunker(
            chunk_size=5,
            chunk_overlap=2,
            strategy=FallbackStrategy.LINE_BASED,
        )

        # Should fall back to line-based chunking
        chunks = chunker.chunk_file(str(strange_file), None)  # No language specified
        assert chunks
        assert len(chunks) > 1  # Should create multiple chunks

        # Verify overlap
        for i in range(len(chunks) - 1):
            current_lines = chunks[i].content.strip().split("\n")
            next_lines = chunks[i + 1].content.strip().split("\n")
            # Some overlap should exist
            if current_lines and next_lines:
                assert any(line in next_lines for line in current_lines[-2:] if line)
