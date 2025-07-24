"""Simple integration tests for Phase 9 features that are actually available."""

import pytest

from chunker import (
    BaseMetadataExtractor,
    ChunkHierarchyBuilder,
    ImportBlockRule,
    OverlappingFallbackChunker,
    RepoConfig,
    RepoProcessorImpl,
    TiktokenCounter,
    TodoCommentRule,
    TreeSitterSemanticMerger,
    chunk_file,
)


class TestPhase9SimpleIntegration:
    """Test Phase 9 features with actual available APIs."""

    @pytest.fixture()
    def test_file(self, tmp_path):
        """Create a simple test file."""
        test_file = tmp_path / "example.py"
        test_file.write_text(
            '''
import os
import sys

# TODO: Add error handling
def process_data(data):
    """Process the data."""
    # TODO: Validate input
    result = []
    for item in data:
        result.append(item * 2)
    return result

class DataHandler:
    """Handle data operations."""
    
    def __init__(self):
        self.data = []
    
    def add(self, item):
        """Add item to data."""
        self.data.append(item)
    
    def get_all(self):
        """Get all data."""
        return self.data
''',
        )
        return test_file

    def test_token_counting_integration(self, test_file):
        """Test token counting with chunking."""
        # Get chunks
        chunks = chunk_file(test_file, "python")
        assert chunks

        # Count tokens
        counter = TiktokenCounter()
        for chunk in chunks:
            tokens = counter.count_tokens(chunk.content)
            assert tokens > 0
            assert isinstance(tokens, int)

    def test_hierarchy_building(self, test_file):
        """Test hierarchy building."""
        chunks = chunk_file(test_file, "python")

        builder = ChunkHierarchyBuilder()
        hierarchy = builder.build_hierarchy(chunks)

        # Should have root chunks
        assert hierarchy.root_chunks

        # Find class chunk
        class_chunks = [c for c in chunks if "class DataHandler" in c.content]
        if class_chunks:
            class_chunk = class_chunks[0]
            # Should have methods as children
            children = hierarchy.get_children(class_chunk.chunk_id)
            assert len(children) >= 2  # __init__ and other methods

    def test_metadata_extraction(self, test_file):
        """Test metadata extraction."""
        chunks = chunk_file(test_file, "python")

        extractor = BaseMetadataExtractor()
        for chunk in chunks:
            metadata = extractor.extract_metadata(chunk)
            assert metadata is not None
            assert isinstance(metadata, dict)

    def test_custom_rules(self, test_file):
        """Test custom rules."""
        chunks = chunk_file(test_file, "python")

        # Test TODO rule
        todo_rule = TodoCommentRule()
        todos_found = False
        for chunk in chunks:
            if todo_rule.matches(chunk):
                todos = todo_rule.extract(chunk)
                if todos:
                    todos_found = True
                    assert isinstance(todos, list)

        assert todos_found  # Should find TODO comments

        # Test import rule
        import_rule = ImportBlockRule()
        imports_found = False
        for chunk in chunks:
            if import_rule.matches(chunk):
                imports = import_rule.extract(chunk)
                if imports:
                    imports_found = True
                    assert isinstance(imports, list)

        assert imports_found  # Should find imports

    def test_semantic_merging(self, test_file):
        """Test semantic merging."""
        chunks = chunk_file(test_file, "python")
        original_count = len(chunks)

        merger = TreeSitterSemanticMerger()
        merged = merger.merge_chunks(chunks)

        # Should have chunks
        assert merged
        # May have fewer chunks after merging
        assert len(merged) <= original_count

    def test_repo_processing(self, tmp_path):
        """Test repository processing."""
        # Create a simple repo structure
        src_dir = tmp_path / "src"
        src_dir.mkdir()

        # Create a few Python files
        (src_dir / "main.py").write_text("def main():\n    pass\n")
        (src_dir / "utils.py").write_text("def helper():\n    return 42\n")

        # Process repository
        processor = RepoProcessorImpl()
        config = RepoConfig(include_patterns=["**/*.py"])

        results = processor.process_repository(str(tmp_path), config)

        assert results.total_files >= 2
        assert results.processed_files >= 2
        assert len(results.chunks) >= 2

    def test_overlapping_fallback(self, tmp_path):
        """Test overlapping fallback chunker."""
        # Create a text file
        text_file = tmp_path / "document.txt"
        text_file.write_text(
            """
This is line 1 of the document.
This is line 2 of the document.
This is line 3 of the document.
This is line 4 of the document.
This is line 5 of the document.
This is line 6 of the document.
This is line 7 of the document.
This is line 8 of the document.
This is line 9 of the document.
This is line 10 of the document.
""".strip(),
        )

        # Use overlapping fallback chunker
        chunker = OverlappingFallbackChunker()

        # Chunk with small size to force multiple chunks
        chunks = chunker.chunk_with_overlap(
            text_file.read_text(),
            str(text_file),
            chunk_size=100,  # Small chunks
            overlap_size=20,  # Some overlap
        )

        assert len(chunks) > 1  # Should create multiple chunks

        # Verify chunks have content
        for chunk in chunks:
            assert chunk.content
            assert chunk.file_path == str(text_file)
