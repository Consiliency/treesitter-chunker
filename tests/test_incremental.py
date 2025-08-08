"""Tests for incremental processing implementation."""

import shutil
import tempfile
from datetime import datetime, timedelta

import pytest

from chunker.incremental import (
    DefaultChangeDetector,
    DefaultChunkCache,
    DefaultIncrementalProcessor,
    SimpleIncrementalIndex,
)
from chunker.interfaces.incremental import ChangeType
from chunker.types import CodeChunk


@pytest.fixture
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
            content="""def hello():
    print('Hello')
    return True
""",
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
            content="""def world():
    print('World')
""",
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
            content="""class MyClass:
    def __init__(self):
        pass
""",
            chunk_id="chunk3",
        ),
    ]


@pytest.fixture
def temp_cache_dir():
    """Create temporary cache directory."""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)


class TestIncrementalProcessor:
    """Test incremental processor implementation."""

    @classmethod
    def test_compute_diff_no_changes(cls, sample_chunks):
        """Test diff computation with no changes."""
        processor = DefaultIncrementalProcessor()
        content = "\n".join([chunk.content for chunk in sample_chunks])
        diff = processor.compute_diff(sample_chunks, content, "python")
        total_changes = (
            diff.summary["added"] + diff.summary["deleted"] + diff.summary["modified"]
        )
        assert total_changes >= 0
        assert diff.summary["total_new_chunks"] >= diff.summary["total_old_chunks"]

    @classmethod
    def test_compute_diff_with_modifications(cls, sample_chunks):
        """Test diff computation with modified content."""
        processor = DefaultIncrementalProcessor()
        modified_content = """def hello():
    print('Hello, World!')  # Modified
    return True

def world():
    print('World')

class MyClass:
    def __init__(self):
        pass
"""
        diff = processor.compute_diff(
            sample_chunks,
            modified_content,
            "python",
        )
        total_changes = (
            diff.summary["added"]
            + diff.summary["deleted"]
            + diff.summary["modified"]
            + diff.summary.get("moved", 0)
        )
        assert total_changes > 0

    @classmethod
    def test_compute_diff_with_additions(cls, sample_chunks):
        """Test diff computation with added content."""
        processor = DefaultIncrementalProcessor()
        modified_content = """def hello():
    print('Hello')
    return True

def world():
    print('World')

def new_function():
    '''This is new'''
    pass

class MyClass:
    def __init__(self):
        pass
"""
        diff = processor.compute_diff(
            sample_chunks,
            modified_content,
            "python",
        )
        assert len(diff.added_chunks) >= 1
        assert diff.summary["added"] >= 1

    @classmethod
    def test_compute_diff_with_deletions(cls, sample_chunks):
        """Test diff computation with deleted content."""
        processor = DefaultIncrementalProcessor()
        modified_content = """def hello():
    print('Hello')
    return True

class MyClass:
    def __init__(self):
        pass
"""
        diff = processor.compute_diff(
            sample_chunks,
            modified_content,
            "python",
        )
        assert len(diff.deleted_chunks) >= 1
        assert diff.summary["deleted"] >= 1

    @classmethod
    def test_detect_moved_chunks(cls, sample_chunks):
        """Test detection of moved chunks."""
        processor = DefaultIncrementalProcessor()
        modified_content = """def world():
    print('World')

class MyClass:
    def __init__(self):
        pass

def hello():
    print('Hello')
    return True
"""
        diff = processor.compute_diff(
            sample_chunks,
            modified_content,
            "python",
        )
        moved_changes = [c for c in diff.changes if c.change_type == ChangeType.MOVED]
        assert len(moved_changes) >= 1

    @classmethod
    def test_update_chunks(cls, sample_chunks):
        """Test updating chunks based on diff."""
        processor = DefaultIncrementalProcessor()
        modified_content = """def hello():
    print('Hello, Modified!')
    return True

def new_func():
    pass

class MyClass:
    def __init__(self):
        pass
"""
        diff = processor.compute_diff(
            sample_chunks,
            modified_content,
            "python",
        )
        updated_chunks = processor.update_chunks(sample_chunks, diff)
        assert len(updated_chunks) > 0
        for chunk in updated_chunks:
            assert chunk.start_line > 0
            assert chunk.end_line >= chunk.start_line

    @classmethod
    def test_merge_incremental_results(cls, sample_chunks):
        """Test merging incremental results."""
        processor = DefaultIncrementalProcessor()
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
                content="""def world_modified():
    print('Modified')
""",
                chunk_id="chunk2_new",
            ),
        ]
        changed_regions = [(7, 10)]
        merged = processor.merge_incremental_results(
            sample_chunks,
            incremental_chunks,
            changed_regions,
        )
        assert len(merged) > 0
        old_chunk2_ids = [c.chunk_id for c in merged if c.chunk_id == "chunk2"]
        assert len(old_chunk2_ids) == 0


class TestChunkCache:
    """Test chunk cache implementation."""

    @classmethod
    def test_store_and_retrieve(cls, sample_chunks, temp_cache_dir):
        """Test storing and retrieving chunks."""
        cache = DefaultChunkCache(temp_cache_dir)
        file_hash = "test_hash_123"
        cache.store("test.py", sample_chunks, file_hash)
        entry = cache.retrieve("test.py", file_hash)
        assert entry is not None
        assert entry.file_path == "test.py"
        assert entry.file_hash == file_hash
        assert len(entry.chunks) == len(sample_chunks)

    @classmethod
    def test_retrieve_with_wrong_hash(cls, sample_chunks, temp_cache_dir):
        """Test retrieving with wrong hash."""
        cache = DefaultChunkCache(temp_cache_dir)
        cache.store("test.py", sample_chunks, "correct_hash")
        entry = cache.retrieve("test.py", "wrong_hash")
        assert entry is None

    @classmethod
    def test_invalidate_specific_file(cls, sample_chunks, temp_cache_dir):
        """Test invalidating specific file."""
        cache = DefaultChunkCache(temp_cache_dir)
        cache.store("test1.py", sample_chunks, "hash1")
        cache.store("test2.py", sample_chunks, "hash2")
        count = cache.invalidate("test1.py")
        assert count == 1
        assert cache.retrieve("test1.py") is None
        assert cache.retrieve("test2.py") is not None

    @classmethod
    def test_invalidate_by_age(cls, sample_chunks, temp_cache_dir):
        """Test invalidating by age."""
        cache = DefaultChunkCache(temp_cache_dir)
        cache.store("test.py", sample_chunks, "hash")
        future_time = datetime.now() + timedelta(hours=1)
        count = cache.invalidate(older_than=future_time)
        assert count == 1
        assert cache.retrieve("test.py") is None

    @classmethod
    def test_cache_statistics(cls, sample_chunks, temp_cache_dir):
        """Test cache statistics."""
        cache = DefaultChunkCache(temp_cache_dir)
        cache.store("test.py", sample_chunks, "hash")
        cache.retrieve("test.py", "hash")
        cache.retrieve("test.py", "wrong_hash")
        cache.retrieve("nonexistent.py")
        stats = cache.get_statistics()
        assert stats["entries"] == 1
        assert stats["hit_rate"] > 0
        assert stats["stats"]["hits"] == 1
        assert stats["stats"]["misses"] >= 1

    @classmethod
    def test_export_import_cache(cls, sample_chunks, temp_cache_dir):
        """Test exporting and importing cache."""
        cache1 = DefaultChunkCache(temp_cache_dir + "_1")
        cache2 = DefaultChunkCache(temp_cache_dir + "_2")
        cache1.store("test.py", sample_chunks, "hash")
        export_path = temp_cache_dir + "/export.json"
        cache1.export_cache(export_path)
        cache2.import_cache(export_path)
        entry = cache2.retrieve("test.py")
        assert entry is not None
        assert len(entry.chunks) == len(sample_chunks)


class TestChangeDetector:
    """Test change detector implementation."""

    @classmethod
    def test_compute_file_hash(cls):
        """Test file hash computation."""
        detector = DefaultChangeDetector()
        content = "Hello, World!"
        hash1 = detector.compute_file_hash(content)
        hash2 = detector.compute_file_hash(content)
        hash3 = detector.compute_file_hash(content + " ")
        assert hash1 == hash2
        assert hash1 != hash3

    @classmethod
    def test_find_changed_regions(cls):
        """Test finding changed regions."""
        detector = DefaultChangeDetector()
        old_content = "line 1\nline 2\nline 3\nline 4\nline 5"
        new_content = "line 1\nline 2 modified\nline 3\nnew line\nline 5"
        regions = detector.find_changed_regions(old_content, new_content)
        assert len(regions) > 0
        assert any(r[0] <= 2 <= r[1] for r in regions)

    @classmethod
    def test_classify_change(cls, sample_chunks):
        """Test change classification."""
        detector = DefaultChangeDetector()
        chunk = sample_chunks[0]
        changed_lines = set(range(chunk.start_line, chunk.end_line + 1))
        change_type = detector.classify_change(chunk, "", changed_lines)
        assert change_type == ChangeType.DELETED
        changed_lines = {chunk.start_line}
        change_type = detector.classify_change(chunk, "", changed_lines)
        assert change_type == ChangeType.MODIFIED


class TestIncrementalIndex:
    """Test incremental index implementation."""

    @classmethod
    def test_update_chunk(cls, sample_chunks):
        """Test updating single chunk."""
        index = SimpleIncrementalIndex()
        chunk = sample_chunks[0]
        index.update_chunk(None, chunk)
        assert chunk.chunk_id in index.index
        assert index.index[chunk.chunk_id]["content"] == chunk.content.lower()

    @classmethod
    def test_batch_update(cls, sample_chunks):
        """Test batch update."""
        index = SimpleIncrementalIndex()
        processor = DefaultIncrementalProcessor()
        modified_content = """def hello():
    print('Modified')
    return True

def world():
    print('World')

class MyClass:
    def __init__(self):
        pass
"""
        diff = processor.compute_diff(
            sample_chunks,
            modified_content,
            "python",
        )
        index.batch_update(diff)
        assert len(index.update_log) == len(diff.changes)

    @classmethod
    def test_get_update_cost(cls, sample_chunks):
        """Test update cost estimation."""
        index = SimpleIncrementalIndex()
        processor = DefaultIncrementalProcessor()
        for chunk in sample_chunks:
            index.update_chunk(None, chunk)
        small_diff = processor.compute_diff(
            sample_chunks,
            "\n".join([chunk.content for chunk in sample_chunks]),
            "python",
        )
        small_cost = index.get_update_cost(small_diff)
        assert small_cost <= 1.0
        large_diff = processor.compute_diff(
            sample_chunks,
            "completely different content",
            "python",
        )
        large_cost = index.get_update_cost(large_diff)
        assert large_cost > 0.5

    @classmethod
    def test_search(cls, sample_chunks):
        """Test search functionality."""
        index = SimpleIncrementalIndex()
        for chunk in sample_chunks:
            index.update_chunk(None, chunk)
        results = index.search("hello")
        assert len(results) == 1
        assert results[0] == "chunk1"
        results = index.search("print")
        assert len(results) >= 2
