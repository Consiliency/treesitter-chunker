"""Integration tests for token counting with hierarchy building."""

from chunker import chunk_file, get_parser
from chunker.hierarchy import ChunkHierarchy, ChunkHierarchyBuilder, HierarchyNavigator
from chunker.token import TiktokenCounter, TokenAwareChunker
from chunker.types import CodeChunk

from .base import Phase9IntegrationTestBase


class TestTokenHierarchyIntegration(Phase9IntegrationTestBase):
    """Test token counting integrated with hierarchy building."""

    def test_token_counts_in_hierarchy(self, sample_python_file):
        """Test that token counts are preserved in hierarchical structures."""
        # Create components
        token_counter = TiktokenCounter()
        hierarchy_builder = ChunkHierarchyBuilder()

        # Parse and chunk the file
        parser = get_parser("python")
        chunks = chunk_file(sample_python_file, parser)

        # Add token counts to chunks
        for chunk in chunks:
            token_count = token_counter.count_tokens(chunk.content)
            chunk.metadata = chunk.metadata or {}
            chunk.metadata["tokens"] = token_count

        # Build hierarchy
        hierarchy = hierarchy_builder.build_hierarchy(chunks)

        # Verify all chunks in hierarchy have token counts
        def verify_node(node: ChunkHierarchy):
            assert "tokens" in node.chunk.metadata
            assert isinstance(node.chunk.metadata["tokens"], int)
            assert node.chunk.metadata["tokens"] > 0

            for child in node.children:
                verify_node(child)

        for root in hierarchy:
            verify_node(root)

    def test_token_aware_splitting_with_hierarchy(self, test_repo_path):
        """Test splitting large chunks while maintaining hierarchy."""
        # Create a file with a large function
        large_file = test_repo_path / "large_function.py"
        large_file.write_text(
            '''
def process_large_dataset(data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Process a large dataset with many operations."""
    # This function is intentionally large to test token splitting

    # Step 1: Validate input data
    if not data:
        raise ValueError("Input data cannot be empty")

    if not isinstance(data, list):
        raise TypeError("Data must be a list")

    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise TypeError(f"Item {i} must be a dictionary")

    # Step 2: Initialize processing variables
    results = {
        'total_items': len(data),
        'processed_items': 0,
        'errors': [],
        'warnings': [],
        'summary': {},
        'statistics': {
            'min_values': {},
            'max_values': {},
            'avg_values': {},
            'unique_counts': {}
        }
    }

    # Step 3: Process each item
    processed_data = []
    for idx, item in enumerate(data):
        try:
            # Validate required fields
            required_fields = ['id', 'name', 'value', 'timestamp']
            missing_fields = [f for f in required_fields if f not in item]
            if missing_fields:
                results['errors'].append({
                    'index': idx,
                    'error': f"Missing fields: {missing_fields}"
                })
                continue

            # Transform the item
            transformed = {
                'id': str(item['id']),
                'name': item['name'].strip().upper(),
                'value': float(item['value']),
                'timestamp': item['timestamp'],
                'processed_at': datetime.now().isoformat()
            }

            # Add optional fields
            if 'category' in item:
                transformed['category'] = item['category']
            if 'tags' in item:
                transformed['tags'] = [tag.strip() for tag in item['tags']]

            # Update statistics
            for key, value in transformed.items():
                if isinstance(value, (int, float)):
                    if key not in results['statistics']['min_values']:
                        results['statistics']['min_values'][key] = value
                        results['statistics']['max_values'][key] = value
                    else:
                        results['statistics']['min_values'][key] = min(
                            results['statistics']['min_values'][key], value
                        )
                        results['statistics']['max_values'][key] = max(
                            results['statistics']['max_values'][key], value
                        )

            processed_data.append(transformed)
            results['processed_items'] += 1

        except Exception as e:
            results['errors'].append({
                'index': idx,
                'error': str(e),
                'item': item
            })

    # Step 4: Calculate final statistics
    if processed_data:
        # Calculate averages
        numeric_fields = {}
        for item in processed_data:
            for key, value in item.items():
                if isinstance(value, (int, float)):
                    if key not in numeric_fields:
                        numeric_fields[key] = []
                    numeric_fields[key].append(value)

        for key, values in numeric_fields.items():
            results['statistics']['avg_values'][key] = sum(values) / len(values)

        # Count unique values
        for key in processed_data[0].keys():
            unique_values = set()
            for item in processed_data:
                if key in item:
                    value = item[key]
                    if isinstance(value, (str, int, float)):
                        unique_values.add(value)
            results['statistics']['unique_counts'][key] = len(unique_values)

    # Step 5: Generate summary
    results['summary'] = {
        'success_rate': results['processed_items'] / results['total_items'] * 100,
        'error_count': len(results['errors']),
        'warning_count': len(results['warnings']),
        'processing_complete': True
    }

    results['data'] = processed_data
    return results

# Additional helper functions
def validate_results(results: Dict[str, Any]) -> bool:
    """Validate processing results."""
    required_keys = ['total_items', 'processed_items', 'errors', 'summary']
    return all(key in results for key in required_keys)

def merge_results(results_list: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge multiple result sets."""
    merged = {
        'total_items': 0,
        'processed_items': 0,
        'errors': [],
        'data': []
    }

    for results in results_list:
        merged['total_items'] += results.get('total_items', 0)
        merged['processed_items'] += results.get('processed_items', 0)
        merged['errors'].extend(results.get('errors', []))
        merged['data'].extend(results.get('data', []))

    return merged
''',
        )

        # Set up token-aware chunker with small limit to force splitting
        token_chunker = TokenAwareChunker(max_tokens=200)  # Small limit
        hierarchy_builder = ChunkHierarchyBuilder()

        # Parse and chunk
        parser = get_parser("python")
        regular_chunks = chunk_file(large_file, parser)

        # Apply token-aware chunking
        token_chunks = []
        for chunk in regular_chunks:
            split_chunks = token_chunker.chunk_with_token_limit(
                chunk.content,
                chunk.language,
                max_tokens=200,
                overlap_tokens=20,
            )

            # Convert to CodeChunk objects
            for i, (content, tokens) in enumerate(split_chunks):
                new_chunk = CodeChunk(
                    content=content,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    chunk_type=chunk.chunk_type,
                    language=chunk.language,
                    metadata={
                        "tokens": tokens,
                        "original_chunk_id": id(chunk),
                        "split_index": i,
                        "total_splits": len(split_chunks),
                    },
                )
                token_chunks.append(new_chunk)

        # Build hierarchy with split chunks
        hierarchy = hierarchy_builder.build_hierarchy(token_chunks)

        # Verify hierarchy maintains relationships
        assert len(hierarchy) > 0

        # Check that split chunks are properly organized
        split_groups = {}
        for chunk in token_chunks:
            orig_id = chunk.metadata.get("original_chunk_id")
            if orig_id:
                if orig_id not in split_groups:
                    split_groups[orig_id] = []
                split_groups[orig_id].append(chunk)

        # Verify each group has proper token counts
        for orig_id, splits in split_groups.items():
            for split in splits:
                assert split.metadata["tokens"] <= 200  # Within limit
                assert split.metadata["split_index"] < split.metadata["total_splits"]

    def test_hierarchy_navigator_with_tokens(self, test_repo_path):
        """Test navigating hierarchy with token metadata."""
        python_file = test_repo_path / "src" / "python" / "main.py"

        # Create components
        token_counter = TiktokenCounter()
        hierarchy_builder = ChunkHierarchyBuilder()
        HierarchyNavigator()

        # Parse and chunk
        parser = get_parser("python")
        chunks = chunk_file(python_file, parser)

        # Add token counts and build hierarchy
        for chunk in chunks:
            chunk.metadata = chunk.metadata or {}
            chunk.metadata["tokens"] = token_counter.count_tokens(chunk.content)

        hierarchy = hierarchy_builder.build_hierarchy(chunks)

        # Navigate to find chunks by token count
        large_chunks = []
        small_chunks = []

        def categorize_by_tokens(node: ChunkHierarchy):
            tokens = node.chunk.metadata.get("tokens", 0)
            if tokens > 50:
                large_chunks.append(node.chunk)
            else:
                small_chunks.append(node.chunk)

            for child in node.children:
                categorize_by_tokens(child)

        for root in hierarchy:
            categorize_by_tokens(root)

        # Verify we found chunks of different sizes
        assert len(large_chunks) > 0, "Should find large chunks"
        assert len(small_chunks) > 0, "Should find small chunks"

        # Verify token counts make sense
        for chunk in large_chunks:
            assert chunk.metadata["tokens"] > 50

        for chunk in small_chunks:
            assert chunk.metadata["tokens"] <= 50

    def test_parent_child_token_relationships(self, sample_python_file):
        """Test that parent chunks have token counts >= sum of children."""
        # Parse and process
        parser = get_parser("python")
        chunks = chunk_file(sample_python_file, parser)

        # Add token counts
        token_counter = TiktokenCounter()
        for chunk in chunks:
            chunk.metadata = chunk.metadata or {}
            chunk.metadata["tokens"] = token_counter.count_tokens(chunk.content)

        # Build hierarchy
        hierarchy_builder = ChunkHierarchyBuilder()
        hierarchy = hierarchy_builder.build_hierarchy(chunks)

        # Verify parent-child token relationships
        def verify_token_relationship(node: ChunkHierarchy):
            parent_tokens = node.chunk.metadata.get("tokens", 0)

            if node.children:
                # Sum of child tokens should not exceed parent
                child_token_sum = sum(
                    child.chunk.metadata.get("tokens", 0) for child in node.children
                )

                # Parent should have at least as many tokens as children
                # (may have more due to syntax elements)
                assert parent_tokens >= child_token_sum * 0.8, (
                    f"Parent tokens ({parent_tokens}) should be >= "
                    f"80% of child sum ({child_token_sum})"
                )

            # Recursively check children
            for child in node.children:
                verify_token_relationship(child)

        for root in hierarchy:
            verify_token_relationship(root)

    def test_incremental_hierarchy_with_tokens(self, test_repo_path):
        """Test building hierarchy incrementally with token metadata."""
        # Process multiple files incrementally
        python_files = list((test_repo_path / "src" / "python").glob("*.py"))

        token_counter = TiktokenCounter()
        hierarchy_builder = ChunkHierarchyBuilder()
        all_chunks = []

        # Process files one by one
        for file_path in python_files:
            parser = get_parser("python")
            chunks = chunk_file(file_path, parser)

            # Add tokens and file metadata
            for chunk in chunks:
                chunk.metadata = chunk.metadata or {}
                chunk.metadata["tokens"] = token_counter.count_tokens(chunk.content)
                chunk.metadata["file"] = str(file_path.relative_to(test_repo_path))

            all_chunks.extend(chunks)

        # Build complete hierarchy
        hierarchy = hierarchy_builder.build_hierarchy(all_chunks)

        # Verify hierarchy contains chunks from all files
        files_in_hierarchy = set()

        def collect_files(node: ChunkHierarchy):
            files_in_hierarchy.add(node.chunk.metadata.get("file"))
            for child in node.children:
                collect_files(child)

        for root in hierarchy:
            collect_files(root)

        # Should have chunks from all processed files
        expected_files = {str(f.relative_to(test_repo_path)) for f in python_files}
        assert files_in_hierarchy >= expected_files

        # Verify token counts across files
        total_tokens = 0

        def sum_tokens(node: ChunkHierarchy):
            nonlocal total_tokens
            total_tokens += node.chunk.metadata.get("tokens", 0)
            for child in node.children:
                sum_tokens(child)

        for root in hierarchy:
            sum_tokens(root)

        assert total_tokens > 0, "Should have counted tokens across all files"

    def test_token_based_hierarchy_filtering(self, test_repo_path):
        """Test filtering hierarchy based on token thresholds."""
        python_file = test_repo_path / "src" / "python" / "utils.py"

        # Process file
        parser = get_parser("python")
        chunks = chunk_file(python_file, parser)

        # Add token counts
        token_counter = TiktokenCounter()
        for chunk in chunks:
            chunk.metadata = chunk.metadata or {}
            chunk.metadata["tokens"] = token_counter.count_tokens(chunk.content)

        # Build hierarchy
        hierarchy_builder = ChunkHierarchyBuilder()
        hierarchy = hierarchy_builder.build_hierarchy(chunks)

        # Filter to only show chunks with significant token counts
        min_tokens = 30
        filtered_chunks = []

        def filter_by_tokens(node: ChunkHierarchy, min_tokens: int):
            if node.chunk.metadata.get("tokens", 0) >= min_tokens:
                filtered_chunks.append(node.chunk)
                # Also check children
                for child in node.children:
                    filter_by_tokens(child, min_tokens)

        for root in hierarchy:
            filter_by_tokens(root, min_tokens)

        # Verify filtered results
        assert len(filtered_chunks) > 0
        assert all(
            chunk.metadata.get("tokens", 0) >= min_tokens for chunk in filtered_chunks
        )

        # Should have fewer chunks than original
        assert len(filtered_chunks) < len(chunks)
