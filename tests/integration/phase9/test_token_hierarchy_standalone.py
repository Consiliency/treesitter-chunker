"""Standalone integration tests for token counting with hierarchy building."""

import pytest


class TestTokenHierarchyStandalone:
    """Test token counting integrated with hierarchy building - standalone version."""

    @pytest.fixture()
    def sample_python_file(self, tmp_path):
        """Create a sample Python file for testing."""
        file_path = tmp_path / "sample.py"
        file_path.write_text(
            '''
class DataProcessor:
    """Process data with various operations."""

    def __init__(self, name: str):
        self.name = name
        self._data = []

    def add_data(self, item: Any) -> None:
        """Add data item."""
        self._data.append(item)

    def get_data(self) -> List[Any]:
        """Get all data."""
        return self._data.copy()
''',
        )
        return file_path

    def test_basic_token_counting(self, sample_python_file):
        """Test basic token counting functionality."""
        # Import only what we need
        from chunker.chunker import chunk_file
        from chunker.token.counter import TiktokenCounter

        # Parse and chunk
        chunks = chunk_file(sample_python_file, "python")

        # Create token counter
        token_counter = TiktokenCounter()

        # Count tokens for each chunk
        token_counts = []
        for chunk in chunks:
            count = token_counter.count_tokens(chunk.content)
            token_counts.append(count)
            assert count > 0, "Token count should be positive"

        # Should have multiple chunks with different counts
        assert len(chunks) > 0, "Should have chunks"
        assert len(set(token_counts)) > 1, "Should have different token counts"

    def test_hierarchy_building(self, sample_python_file):
        """Test hierarchy building with chunks."""
        # Import components
        from chunker.chunker import chunk_file
        from chunker.hierarchy.builder import ChunkHierarchyBuilder

        # Parse and chunk
        chunks = chunk_file(sample_python_file, "python")

        # Build hierarchy
        builder = ChunkHierarchyBuilder()
        hierarchy = builder.build_hierarchy(chunks)

        # Verify hierarchy structure
        assert hierarchy is not None, "Should have hierarchy"
        assert len(hierarchy.root_chunks) > 0, "Should have root chunks"

        # Check that we have chunks in the hierarchy
        assert len(hierarchy.chunk_map) > 0, "Should have chunks in hierarchy"

        # Check parent-child relationships
        if hierarchy.children_map:
            # At least one chunk should have children
            has_children = any(
                len(children) > 0 for children in hierarchy.children_map.values()
            )
            assert has_children, "Should have parent-child relationships"
