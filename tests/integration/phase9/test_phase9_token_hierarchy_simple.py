"""Simplified integration tests for token counting with hierarchy building."""

import pytest

from chunker import chunk_file
from chunker.hierarchy.builder import ChunkHierarchyBuilder
from chunker.token.counter import TiktokenCounter


class TestTokenHierarchyIntegrationSimple:
    """Test token counting integrated with hierarchy building."""

    @staticmethod
    @pytest.fixture
    def sample_python_file(tmp_path):
        """Create a sample Python file for testing."""
        file_path = tmp_path / "sample.py"
        file_path.write_text(
            """
class DataProcessor:
    \"\"\"Process data with various operations.\"\"\"

    def __init__(self, name: str):
        self.name = name
        self._data = []

    def add_data(self, item: Any) -> None:
        \"\"\"Add data item.\"\"\"
        self._data.append(item)

    def get_data(self) -> List[Any]:
        \"\"\"Get all data.\"\"\"
        return self._data.copy()

    def process(self) -> Dict[str, Any]:
        \"\"\"Process all data.\"\"\"
        return {
            "name": self.name,
            "count": len(self._data),
            "data": self._data
        }

    def clear(self) -> None:
        \"\"\"Clear all data.\"\"\"
        self._data.clear()

# Helper functions
def create_processor(name: str) -> DataProcessor:
    \"\"\"Create a new data processor.\"\"\"
    return DataProcessor(name)

def merge_processors(p1: DataProcessor, p2: DataProcessor) -> DataProcessor:
    \"\"\"Merge two processors.\"\"\"
    merged = DataProcessor(f"{p1.name}_{p2.name}")
    for item in p1.get_data() + p2.get_data():
        merged.add_data(item)
    return merged
""",
        )
        return file_path

    @classmethod
    def test_token_counts_in_chunks(cls, sample_python_file):
        """Test that we can add token counts to chunks."""
        token_counter = TiktokenCounter()
        chunks = chunk_file(sample_python_file, "python")
        for chunk in chunks:
            token_count = token_counter.count_tokens(chunk.content)
            chunk.metadata = chunk.metadata or {}
            chunk.metadata["tokens"] = token_count
        for chunk in chunks:
            assert "tokens" in chunk.metadata
            assert isinstance(chunk.metadata["tokens"], int)
            assert chunk.metadata["tokens"] > 0
        token_counts = [chunk.metadata["tokens"] for chunk in chunks]
        assert len(set(token_counts)) > 1, "Should have different token counts"

    @classmethod
    def test_token_hierarchy_building(cls, sample_python_file):
        """Test building hierarchy with token metadata."""
        token_counter = TiktokenCounter()
        hierarchy_builder = ChunkHierarchyBuilder()
        chunks = chunk_file(sample_python_file, "python")
        for i, chunk in enumerate(chunks):
            chunk.metadata = chunk.metadata or {}
            chunk.metadata["tokens"] = token_counter.count_tokens(
                chunk.content,
            )
            chunk.metadata["chunk_id"] = f"chunk_{i}"
        hierarchy = hierarchy_builder.build_hierarchy(chunks)
        assert (
            len(
                hierarchy.root_chunks,
            )
            > 0
        ), "Should have root chunks in hierarchy"
        assert len(hierarchy.chunk_map) > 0, "Should have chunks in hierarchy"

        # Check that chunks in hierarchy have token metadata
        for chunk in hierarchy.chunk_map.values():
            assert hasattr(chunk, "metadata")
            assert "tokens" in chunk.metadata
            assert chunk.metadata["tokens"] > 0

    @classmethod
    def test_token_aware_chunking(cls, tmp_path):
        """Test token-aware chunking that respects token limits."""
        large_file = tmp_path / "large.py"
        large_file.write_text(
            """
def process_data(items):
    \"\"\"Process a list of items with detailed documentation.

    This function processes each item in the list and performs various
    transformations and validations. It handles errors gracefully and
    provides detailed logging for debugging purposes.

    Args:
        items: List of items to process

    Returns:
        Dict containing processed results and statistics
    \"\"\"
    results = []
    errors = []

    for i, item in enumerate(items):
        try:
            # Validate item
            if not isinstance(item, dict):
                raise ValueError(f"Item {i} must be a dictionary")

            # Process item
            processed = {
                'id': item.get('id', i),
                'name': item.get('name', 'Unknown'),
                'value': float(item.get('value', 0)),
                'processed': True
            }

            results.append(processed)

        except (AttributeError, KeyError, TypeError) as e:
            errors.append({
                'index': i,
                'error': str(e)
            })

    return {
        'results': results,
        'errors': errors,
        'total': len(items),
        'success': len(results),
        'failed': len(errors)
    }
""",
        )

        # Parse file
        chunk_file(large_file, "python")

        # Create token-aware chunker
        from chunker.token.chunker import TreeSitterTokenAwareChunker

        token_chunker = TreeSitterTokenAwareChunker()
        token_limited_chunks = token_chunker.chunk_with_token_limit(
            str(large_file),
            "python",
            max_tokens=100,
        )
        for chunk in token_limited_chunks:
            assert hasattr(chunk, "metadata")
            assert "token_count" in chunk.metadata
            assert (
                chunk.metadata["token_count"] <= 100
            ), f"Token count {chunk.metadata['token_count']} exceeds limit"

    @staticmethod
    def test_hierarchy_with_parent_child_tokens(tmp_path):
        """Test that parent-child relationships preserve token information."""
        nested_file = tmp_path / "nested.py"
        nested_file.write_text(
            """
class OuterClass:
    \"\"\"Outer class with nested elements.\"\"\"

    class InnerClass:
        \"\"\"Inner class.\"\"\"

        def inner_method(self):
            \"\"\"Method in inner class.\"\"\"
            return "inner"

    def outer_method(self):
        \"\"\"Method in outer class.\"\"\"

        def nested_function():
            \"\"\"Nested function.\"\"\"
            return "nested"

        return nested_function()
""",
        )
        chunks = chunk_file(nested_file, "python")
        token_counter = TiktokenCounter()
        for chunk in chunks:
            chunk.metadata = chunk.metadata or {}
            chunk.metadata["tokens"] = token_counter.count_tokens(
                chunk.content,
            )
        hierarchy_builder = ChunkHierarchyBuilder()
        hierarchy = hierarchy_builder.build_hierarchy(chunks)

        class TreeNode:

            def __init__(self, chunk):
                self.chunk = chunk
                self.children = []

        # Build tree structure from hierarchy
        nodes = {}
        for chunk_id, chunk in hierarchy.chunk_map.items():
            nodes[chunk_id] = TreeNode(chunk)

        # Connect children
        for parent_id, child_ids in hierarchy.children_map.items():
            parent_node = nodes[parent_id]
            for child_id in child_ids:
                parent_node.children.append(nodes[child_id])

        # Get root nodes
        root_nodes = [nodes[chunk_id] for chunk_id in hierarchy.root_chunks]

        # Verify parent-child token relationships
        def check_parent_child_tokens(node):
            parent_tokens = node.chunk.metadata.get("tokens", 0)
            if node.children:
                for child in node.children:
                    child_tokens = child.chunk.metadata.get("tokens", 0)
                    assert (
                        parent_tokens >= child_tokens * 0.5
                    ), f"Parent tokens ({parent_tokens}) too small compared to child ({child_tokens})"
                    check_parent_child_tokens(child)

        for root in root_nodes:
            check_parent_child_tokens(root)
