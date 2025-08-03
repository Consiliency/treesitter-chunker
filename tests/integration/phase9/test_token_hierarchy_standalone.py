"""Standalone integration tests for token counting with hierarchy building."""
import pytest

from chunker.core import chunk_file
from chunker.hierarchy.builder import ChunkHierarchyBuilder
from chunker.token.counter import TiktokenCounter


class TestTokenHierarchyStandalone:
    """Test token counting integrated with hierarchy building - standalone version."""

    @staticmethod
    @pytest.fixture
    def sample_python_file(tmp_path):
        """Create a sample Python file for testing."""
        file_path = tmp_path / "sample.py"
        file_path.write_text(
            """
class DataProcessor:
    ""\"Process data with various operations.""\"

    def __init__(self, name: str):
        self.name = name
        self._data = []

    def add_data(self, item: Any) -> None:
        ""\"Add data item.""\"
        self._data.append(item)

    def get_data(self) -> List[Any]:
        ""\"Get all data.""\"
        return self._data.copy()
""",
            )
        return file_path

    @classmethod
    def test_basic_token_counting(cls, sample_python_file):
        """Test basic token counting functionality."""
        chunks = chunk_file(sample_python_file, "python")
        token_counter = TiktokenCounter()
        token_counts = []
        for chunk in chunks:
            count = token_counter.count_tokens(chunk.content)
            token_counts.append(count)
            assert count > 0, "Token count should be positive"
        assert len(chunks) > 0, "Should have chunks"
        assert len(set(token_counts)) > 1, "Should have different token counts"

    @classmethod
    def test_hierarchy_building(cls, sample_python_file):
        """Test hierarchy building with chunks."""
        chunks = chunk_file(sample_python_file, "python")
        builder = ChunkHierarchyBuilder()
        hierarchy = builder.build_hierarchy(chunks)
        assert hierarchy is not None, "Should have hierarchy"
        assert len(hierarchy.root_chunks) > 0, "Should have root chunks"
        assert len(hierarchy.chunk_map) > 0, "Should have chunks in hierarchy"
        if hierarchy.children_map:
            has_children = any(len(children) > 0 for children in hierarchy.
                children_map.values())
            assert has_children, "Should have parent-child relationships"
