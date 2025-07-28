"""Unit tests for incremental processing without tree-sitter dependency."""

import shutil
import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from chunker.incremental import (
    DefaultChangeDetector,
    DefaultChunkCache,
    DefaultIncrementalProcessor,
    SimpleIncrementalIndex,
)
from chunker.interfaces.incremental import ChangeType, ChunkChange, ChunkDiff
from chunker.types import CodeChunk


@pytest.fixture()
def sample_chunks():
    """Create sample chunks for testing."""
    return [
        CodeChunk(
            language="python",
            file_path="test.py",
            node_type="function_definition",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="",
            content="def hello():\n    print('Hello')\n    return True\n",
            chunk_id="chunk1",
        ),
        CodeChunk(
            language="python",
            file_path="test.py",
            node_type="function_definition",
            start_line=7,
            end_line=10,
            byte_start=101,
            byte_end=200,
            parent_context="",
            content="def world():\n    print('World')\n",
            chunk_id="chunk2",
        ),
        CodeChunk(
            language="python",
            file_path="test.py",
            node_type="class_definition",
            start_line=12,
            end_line=20,
            byte_start=201,
            byte_end=400,
            parent_context="",
            content="class MyClass:\n    def __init__(self):\n        pass\n",
            chunk_id="chunk3",
        ),
    ]


@pytest.fixture()
def temp_cache_dir():
    """Create temporary cache directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


class TestIncrementalProcessor:
    """Test incremental processor implementation."""

    @patch("chunker.incremental.chunk_text")
    def test_compute_diff_no_changes(self, mock_chunk_text, sample_chunks):
        """Test diff computation with no changes."""
        # Mock chunk_text to return the same chunks
        mock_chunk_text.return_value = sample_chunks

        processor = DefaultIncrementalProcessor()
        content = "\n".join([chunk.content for chunk in sample_chunks])

        diff = processor.compute_diff(sample_chunks, content, "python")

        assert len(diff.unchanged_chunks) == len(sample_chunks)
        assert len(diff.added_chunks) == 0
        assert len(diff.deleted_chunks) == 0
        assert len(diff.modified_chunks) == 0

    @patch("chunker.incremental.chunk_text")
    def test_compute_diff_with_modifications(self, mock_chunk_text, sample_chunks):
        """Test diff computation with modified content."""
        # Create modified version of first chunk
        modified_chunk = CodeChunk(
            language="python",
            file_path="test.py",
            node_type="function_definition",
            start_line=1,
            end_line=5,
            byte_start=0,
            byte_end=100,
            parent_context="",
            content="def hello():\n    print('Hello, World!')\n    return True\n",
            chunk_id="chunk1",
        )

        mock_chunk_text.return_value = [modified_chunk, *sample_chunks[1:]]

        processor = DefaultIncrementalProcessor()
        modified_content = "modified content"

        diff = processor.compute_diff(sample_chunks, modified_content, "python")

        assert len(diff.modified_chunks) == 1
        assert diff.summary["modified"] == 1

    @patch("chunker.incremental.chunk_text")
    def test_compute_diff_with_additions(self, mock_chunk_text, sample_chunks):
        """Test diff computation with added content."""
        # Add a new chunk
        new_chunk = CodeChunk(
            language="python",
            file_path="test.py",
            node_type="function_definition",
            start_line=22,
            end_line=25,
            byte_start=401,
            byte_end=500,
            parent_context="",
            content="def new_function():\n    pass\n",
            chunk_id="chunk4",
        )

        mock_chunk_text.return_value = [*sample_chunks, new_chunk]

        processor = DefaultIncrementalProcessor()
        diff = processor.compute_diff(sample_chunks, "modified content", "python")

        assert len(diff.added_chunks) == 1
        assert diff.summary["added"] == 1

    @patch("chunker.incremental.chunk_text")
    def test_compute_diff_with_deletions(self, mock_chunk_text, sample_chunks):
        """Test diff computation with deleted content."""
        # Remove the second chunk
        mock_chunk_text.return_value = [sample_chunks[0], sample_chunks[2]]

        processor = DefaultIncrementalProcessor()
        diff = processor.compute_diff(sample_chunks, "modified content", "python")

        assert len(diff.deleted_chunks) == 1
        assert diff.summary["deleted"] == 1

    def test_detect_moved_chunks(self, sample_chunks):
        """Test detection of moved chunks."""
        processor = DefaultIncrementalProcessor()

        # Create chunks with same content but different positions
        old_chunks = [sample_chunks[0]]
        new_chunks = [
            CodeChunk(
                language="python",
                file_path="test.py",
                node_type="function_definition",
                start_line=10,  # Different position
                end_line=14,
                byte_start=200,
                byte_end=300,
                parent_context="",
                content=sample_chunks[0].content,  # Same content
                chunk_id="chunk1_moved",
            ),
        ]

        moved_pairs = processor.detect_moved_chunks(old_chunks, new_chunks)

        assert len(moved_pairs) == 1
        assert moved_pairs[0][0].content == moved_pairs[0][1].content
        assert moved_pairs[0][0].start_line != moved_pairs[0][1].start_line

    def test_update_chunks(self, sample_chunks):
        """Test updating chunks based on diff."""
        processor = DefaultIncrementalProcessor()

        # Create a simple diff
        added_chunk = CodeChunk(
            language="python",
            file_path="test.py",
            node_type="function_definition",
            start_line=25,
            end_line=28,
            byte_start=500,
            byte_end=600,
            parent_context="",
            content="def added():\n    pass\n",
            chunk_id="added_chunk",
        )

        diff = ChunkDiff(
            changes=[
                ChunkChange(
                    chunk_id="chunk2",
                    change_type=ChangeType.DELETED,
                    old_chunk=sample_chunks[1],
                    new_chunk=None,
                    line_changes=[(7, 10)],
                    confidence=1.0,
                ),
                ChunkChange(
                    chunk_id="added_chunk",
                    change_type=ChangeType.ADDED,
                    old_chunk=None,
                    new_chunk=added_chunk,
                    line_changes=[(25, 28)],
                    confidence=1.0,
                ),
            ],
            added_chunks=[added_chunk],
            deleted_chunks=[sample_chunks[1]],
            modified_chunks=[],
            unchanged_chunks=[sample_chunks[0], sample_chunks[2]],
            summary={"added": 1, "deleted": 1, "modified": 0, "unchanged": 2},
        )

        updated_chunks = processor.update_chunks(sample_chunks, diff)

        # Should have 3 chunks: chunk1, chunk3, and added_chunk
        assert len(updated_chunks) == 3
        chunk_ids = [c.chunk_id for c in updated_chunks]
        assert "chunk1" in chunk_ids
        assert "chunk2" not in chunk_ids
        assert "chunk3" in chunk_ids
        assert "added_chunk" in chunk_ids

    def test_merge_incremental_results(self, sample_chunks):
        """Test merging incremental results."""
        processor = DefaultIncrementalProcessor()

        # Create some incremental chunks
        incremental_chunks = [
            CodeChunk(
                language="python",
                file_path="test.py",
                node_type="function_definition",
                start_line=7,
                end_line=10,
                byte_start=101,
                byte_end=200,
                parent_context="",
                content="def world_modified():\n    print('Modified')\n",
                chunk_id="chunk2_new",
            ),
        ]

        changed_regions = [(7, 10)]

        merged = processor.merge_incremental_results(
            sample_chunks,
            incremental_chunks,
            changed_regions,
        )

        # Should contain chunks from both sets
        assert len(merged) > 0
        # Should not contain old chunk2 since it's in changed region
        old_chunk2_ids = [c.chunk_id for c in merged if c.chunk_id == "chunk2"]
        assert len(old_chunk2_ids) == 0
        # Should contain the new chunk
        new_chunk_ids = [c.chunk_id for c in merged if c.chunk_id == "chunk2_new"]
        assert len(new_chunk_ids) == 1


class TestChunkCache:
    """Test chunk cache implementation."""

    def test_store_and_retrieve(self, sample_chunks, temp_cache_dir):
        """Test storing and retrieving chunks."""
        cache = DefaultChunkCache(temp_cache_dir)

        file_hash = "test_hash_123"
        cache.store("test.py", sample_chunks, file_hash)

        # Retrieve with correct hash
        entry = cache.retrieve("test.py", file_hash)
        assert entry is not None
        assert entry.file_path == "test.py"
        assert entry.file_hash == file_hash
        assert len(entry.chunks) == len(sample_chunks)

    def test_retrieve_with_wrong_hash(self, sample_chunks, temp_cache_dir):
        """Test retrieving with wrong hash."""
        cache = DefaultChunkCache(temp_cache_dir)

        cache.store("test.py", sample_chunks, "correct_hash")

        # Retrieve with wrong hash
        entry = cache.retrieve("test.py", "wrong_hash")
        assert entry is None

    def test_invalidate_specific_file(self, sample_chunks, temp_cache_dir):
        """Test invalidating specific file."""
        cache = DefaultChunkCache(temp_cache_dir)

        cache.store("test1.py", sample_chunks, "hash1")
        cache.store("test2.py", sample_chunks, "hash2")

        # Invalidate one file
        count = cache.invalidate("test1.py")
        assert count == 1

        # test1.py should be gone, test2.py should remain
        assert cache.retrieve("test1.py") is None
        assert cache.retrieve("test2.py") is not None

    def test_invalidate_by_age(self, sample_chunks, temp_cache_dir):
        """Test invalidating by age."""
        cache = DefaultChunkCache(temp_cache_dir)

        # Store entry
        cache.store("test.py", sample_chunks, "hash")

        # Invalidate entries older than 1 hour from now (should remove everything)
        future_time = datetime.now() + timedelta(hours=1)
        count = cache.invalidate(older_than=future_time)
        assert count == 1

        assert cache.retrieve("test.py") is None

    def test_cache_statistics(self, sample_chunks, temp_cache_dir):
        """Test cache statistics."""
        cache = DefaultChunkCache(temp_cache_dir)

        cache.store("test.py", sample_chunks, "hash")

        # Make some retrievals
        cache.retrieve("test.py", "hash")  # hit
        cache.retrieve("test.py", "wrong_hash")  # miss
        cache.retrieve("nonexistent.py")  # miss

        stats = cache.get_statistics()
        assert stats["entries"] == 1
        assert stats["hit_rate"] > 0
        assert stats["stats"]["hits"] == 1
        assert stats["stats"]["misses"] == 1  # Only nonexistent.py counts as miss
        assert stats["stats"]["hash_mismatches"] == 1  # wrong hash is a mismatch

    def test_export_import_cache(self, sample_chunks, temp_cache_dir):
        """Test exporting and importing cache."""
        cache1 = DefaultChunkCache(temp_cache_dir + "_1")
        cache2 = DefaultChunkCache(temp_cache_dir + "_2")

        # Store in first cache
        cache1.store("test.py", sample_chunks, "hash")

        # Export
        export_path = temp_cache_dir + "/export.json"
        cache1.export_cache(export_path)

        # Import into second cache
        cache2.import_cache(export_path)

        # Verify
        entry = cache2.retrieve("test.py")
        assert entry is not None
        assert len(entry.chunks) == len(sample_chunks)


class TestChangeDetector:
    """Test change detector implementation."""

    def test_compute_file_hash(self):
        """Test file hash computation."""
        detector = DefaultChangeDetector()

        content = "Hello, World!"
        hash1 = detector.compute_file_hash(content)
        hash2 = detector.compute_file_hash(content)
        hash3 = detector.compute_file_hash(content + " ")

        assert hash1 == hash2  # Same content, same hash
        assert hash1 != hash3  # Different content, different hash

    def test_find_changed_regions(self):
        """Test finding changed regions."""
        detector = DefaultChangeDetector()

        old_content = """line 1
line 2
line 3
line 4
line 5"""

        new_content = """line 1
line 2 modified
line 3
new line
line 5"""

        regions = detector.find_changed_regions(old_content, new_content)

        assert len(regions) > 0
        # Should detect changes around line 2 and line 4
        assert any(r[0] <= 2 <= r[1] for r in regions)

    def test_classify_change(self, sample_chunks):
        """Test change classification."""
        detector = DefaultChangeDetector()

        chunk = sample_chunks[0]

        # All lines changed - should be DELETED
        changed_lines = set(range(chunk.start_line, chunk.end_line + 1))
        change_type = detector.classify_change(chunk, "", changed_lines)
        assert change_type == ChangeType.DELETED

        # Partial change - should be MODIFIED
        changed_lines = {chunk.start_line}
        change_type = detector.classify_change(chunk, "", changed_lines)
        assert change_type == ChangeType.MODIFIED


class TestIncrementalIndex:
    """Test incremental index implementation."""

    def test_update_chunk(self, sample_chunks):
        """Test updating single chunk."""
        index = SimpleIncrementalIndex()

        chunk = sample_chunks[0]
        index.update_chunk(None, chunk)

        assert chunk.chunk_id in index.index
        assert index.index[chunk.chunk_id]["content"] == chunk.content.lower()

    def test_batch_update(self, sample_chunks):
        """Test batch update."""
        index = SimpleIncrementalIndex()

        # Create a simple diff
        diff = ChunkDiff(
            changes=[
                ChunkChange(
                    chunk_id="chunk1",
                    change_type=ChangeType.MODIFIED,
                    old_chunk=sample_chunks[0],
                    new_chunk=sample_chunks[0],
                    line_changes=[(1, 5)],
                    confidence=0.9,
                ),
            ],
            added_chunks=[],
            deleted_chunks=[],
            modified_chunks=[(sample_chunks[0], sample_chunks[0])],
            unchanged_chunks=sample_chunks[1:],
            summary={"modified": 1},
        )

        index.batch_update(diff)

        # Check update log
        assert len(index.update_log) == len(diff.changes)

    def test_get_update_cost(self, sample_chunks):
        """Test update cost estimation."""
        index = SimpleIncrementalIndex()

        # Populate index
        for chunk in sample_chunks:
            index.update_chunk(None, chunk)

        # Small change
        small_diff = ChunkDiff(
            changes=[
                ChunkChange(
                    chunk_id="chunk1",
                    change_type=ChangeType.MODIFIED,
                    old_chunk=sample_chunks[0],
                    new_chunk=sample_chunks[0],
                    line_changes=[(1, 5)],
                    confidence=0.9,
                ),
            ],
            added_chunks=[],
            deleted_chunks=[],
            modified_chunks=[(sample_chunks[0], sample_chunks[0])],
            unchanged_chunks=sample_chunks[1:],
            summary={"modified": 1, "total": 3},
        )
        small_cost = index.get_update_cost(small_diff)
        assert small_cost < 0.5

        # Large change (all chunks changed)
        large_diff = ChunkDiff(
            changes=[
                ChunkChange(
                    chunk_id=chunk.chunk_id,
                    change_type=ChangeType.DELETED,
                    old_chunk=chunk,
                    new_chunk=None,
                    line_changes=[(chunk.start_line, chunk.end_line)],
                    confidence=1.0,
                )
                for chunk in sample_chunks
            ],
            added_chunks=[],
            deleted_chunks=sample_chunks,
            modified_chunks=[],
            unchanged_chunks=[],
            summary={"deleted": len(sample_chunks), "total": len(sample_chunks)},
        )
        large_cost = index.get_update_cost(large_diff)
        assert large_cost >= 0.5

    def test_search(self, sample_chunks):
        """Test search functionality."""
        index = SimpleIncrementalIndex()

        # Add chunks to index
        for chunk in sample_chunks:
            index.update_chunk(None, chunk)

        # Search for content
        results = index.search("hello")
        assert len(results) == 1
        assert results[0] == "chunk1"

        results = index.search("print")
        assert len(results) >= 2  # Both hello and world functions have print
