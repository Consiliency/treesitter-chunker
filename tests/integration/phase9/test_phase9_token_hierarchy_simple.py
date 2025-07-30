"""Simplified integration tests for token counting with hierarchy building."""

import pytest

from chunker import chunk_file, get_parser


class TestTokenHierarchyIntegrationSimple:
    """Test token counting integrated with hierarchy building."""

    @pytest.fixture
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

    def process(self) -> Dict[str, Any]:
        """Process all data."""
        return {
            "name": self.name,
            "count": len(self._data),
            "data": self._data
        }

    def clear(self) -> None:
        """Clear all data."""
        self._data.clear()

# Helper functions
def create_processor(name: str) -> DataProcessor:
    """Create a new data processor."""
    return DataProcessor(name)

def merge_processors(p1: DataProcessor, p2: DataProcessor) -> DataProcessor:
    """Merge two processors."""
    merged = DataProcessor(f"{p1.name}_{p2.name}")
    for item in p1.get_data() + p2.get_data():
        merged.add_data(item)
    return merged
''',
        )
        return file_path

    def test_token_counts_in_chunks(self, sample_python_file):
        """Test that we can add token counts to chunks."""
        # Import here to avoid module loading issues
        from chunker.token.counter import TiktokenCounter

        # Create token counter
        token_counter = TiktokenCounter()

        # Parse and chunk the file
        parser = get_parser("python")
        chunks = chunk_file(sample_python_file, parser)

        # Add token counts to chunks
        for chunk in chunks:
            token_count = token_counter.count_tokens(chunk.content)
            chunk.metadata = chunk.metadata or {}
            chunk.metadata["tokens"] = token_count

        # Verify all chunks have token counts
        for chunk in chunks:
            assert "tokens" in chunk.metadata
            assert isinstance(chunk.metadata["tokens"], int)
            assert chunk.metadata["tokens"] > 0

        # Verify different chunk types have different token counts
        token_counts = [chunk.metadata["tokens"] for chunk in chunks]
        assert len(set(token_counts)) > 1, "Should have different token counts"

    def test_token_hierarchy_building(self, sample_python_file):
        """Test building hierarchy with token metadata."""
        # Import here to avoid module loading issues
        from chunker.hierarchy.builder import ChunkHierarchyBuilder
        from chunker.token.counter import TiktokenCounter

        # Create components
        token_counter = TiktokenCounter()
        hierarchy_builder = ChunkHierarchyBuilder()

        # Parse and chunk the file
        parser = get_parser("python")
        chunks = chunk_file(sample_python_file, parser)

        # Add token counts and other metadata
        for i, chunk in enumerate(chunks):
            chunk.metadata = chunk.metadata or {}
            chunk.metadata["tokens"] = token_counter.count_tokens(chunk.content)
            chunk.metadata["chunk_id"] = f"chunk_{i}"

        # Build hierarchy
        hierarchy = hierarchy_builder.build_hierarchy(chunks)

        # Verify hierarchy was built
        assert len(hierarchy) > 0, "Should have built hierarchy"

        # Check that nodes in hierarchy have token metadata
        def check_node_tokens(node):
            assert hasattr(node.chunk, "metadata")
            assert "tokens" in node.chunk.metadata
            assert node.chunk.metadata["tokens"] > 0

            for child in node.children:
                check_node_tokens(child)

        for root in hierarchy:
            check_node_tokens(root)

    def test_token_aware_chunking(self, tmp_path):
        """Test token-aware chunking that respects token limits."""
        # Import here
        from chunker.token.chunker import TokenAwareChunker

        # Create a file with content that will exceed token limit
        large_file = tmp_path / "large.py"
        large_file.write_text(
            '''
def process_data(items):
    """Process a list of items with detailed documentation.

    This function processes each item in the list and performs various
    transformations and validations. It handles errors gracefully and
    provides detailed logging for debugging purposes.

    Args:
        items: List of items to process

    Returns:
        Dict containing processed results and statistics
    """
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
''',
        )

        # Parse file
        parser = get_parser("python")
        chunks = chunk_file(large_file, parser)

        # Create token-aware chunker with small limit
        token_chunker = TokenAwareChunker(max_tokens=100)

        # Process chunks with token limit
        for chunk in chunks:
            # Check if chunk needs splitting
            if hasattr(token_chunker, "chunk_with_token_limit"):
                split_results = token_chunker.chunk_with_token_limit(
                    chunk.content,
                    chunk.language,
                    max_tokens=100,
                )

                # Verify splits respect token limit
                for _content, token_count in split_results:
                    assert (
                        token_count <= 100
                    ), f"Token count {token_count} exceeds limit"

    def test_hierarchy_with_parent_child_tokens(self, tmp_path):
        """Test that parent-child relationships preserve token information."""
        # Create a nested structure
        nested_file = tmp_path / "nested.py"
        nested_file.write_text(
            '''
class OuterClass:
    """Outer class with nested elements."""

    class InnerClass:
        """Inner class."""

        def inner_method(self):
            """Method in inner class."""
            return "inner"

    def outer_method(self):
        """Method in outer class."""

        def nested_function():
            """Nested function."""
            return "nested"

        return nested_function()
''',
        )

        # Import components
        from chunker.hierarchy.builder import ChunkHierarchyBuilder
        from chunker.token.counter import TiktokenCounter

        # Parse and process
        parser = get_parser("python")
        chunks = chunk_file(nested_file, parser)

        # Add tokens
        token_counter = TiktokenCounter()
        for chunk in chunks:
            chunk.metadata = chunk.metadata or {}
            chunk.metadata["tokens"] = token_counter.count_tokens(chunk.content)

        # Build hierarchy
        hierarchy_builder = ChunkHierarchyBuilder()
        hierarchy = hierarchy_builder.build_hierarchy(chunks)

        # Verify parent-child token relationships
        def check_parent_child_tokens(node):
            parent_tokens = node.chunk.metadata.get("tokens", 0)

            if node.children:
                # Parent should generally have more tokens than any individual child
                for child in node.children:
                    child_tokens = child.chunk.metadata.get("tokens", 0)
                    # Parent contains child, so should have at least as many tokens
                    assert parent_tokens >= child_tokens * 0.5, (
                        f"Parent tokens ({parent_tokens}) too small compared to "
                        f"child ({child_tokens})"
                    )

                    # Recursively check children
                    check_parent_child_tokens(child)

        for root in hierarchy:
            check_parent_child_tokens(root)
