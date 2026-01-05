"""Tests for performance optimization features."""

import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from chunker.performance.cache.lru import LRUCache
from chunker.performance.cache.manager import CacheManager
from chunker.performance.cache.multi_level import MultiLevelCache
from chunker.performance.enhanced_chunker import EnhancedChunker
from chunker.performance.optimization.batch import BatchProcessor
from chunker.performance.optimization.incremental import IncrementalParser
from chunker.performance.optimization.memory_pool import MemoryPool
from chunker.performance.optimization.monitor import PerformanceMonitor
from chunker.types import CodeChunk

# Mark all tests in this module as integration tests
pytestmark = pytest.mark.integration


class TestLRUCache:
    """Test LRU cache implementation."""

    @classmethod
    def test_basic_operations(cls):
        """Test basic get/put operations."""
        cache = LRUCache(max_size=3)
        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"
        assert cache.get("nonexistent") is None
        assert cache.size() == 1

    @classmethod
    def test_lru_eviction(cls):
        """Test LRU eviction policy."""
        cache = LRUCache(max_size=3)
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")
        cache.get("key1")
        cache.put("key4", "value4")
        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None
        assert cache.get("key3") == "value3"
        assert cache.get("key4") == "value4"

    @classmethod
    def test_ttl_expiration(cls):
        """Test TTL expiration."""
        cache = LRUCache(max_size=10)
        cache.put("key1", "value1", ttl_seconds=1)
        assert cache.get("key1") == "value1"
        time.sleep(1.1)
        assert cache.get("key1") is None

    @classmethod
    def test_statistics(cls):
        """Test cache statistics."""
        cache = LRUCache(max_size=10)
        cache.put("key1", "value1")
        cache.get("key1")
        cache.get("key1")
        cache.get("key2")
        stats = cache.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 2 / 3
        assert stats["size"] == 1


class TestMultiLevelCache:
    """Test multi-level cache implementation."""

    @classmethod
    def test_cache_routing(cls):
        """Test that keys are routed to correct cache levels."""
        cache = MultiLevelCache()
        cache.put("ast:file.py:hash", "ast_data")
        cache.put("chunk:file.py:hash", "chunk_data")
        cache.put("query:pattern", "query_data")
        cache.put("unknown:key", "other_data")
        assert cache.get("ast:file.py:hash") == "ast_data"
        assert cache.get("chunk:file.py:hash") == "chunk_data"
        assert cache.get("query:pattern") == "query_data"
        assert cache.get("unknown:key") == "other_data"

    @classmethod
    def test_pattern_invalidation(cls):
        """Test pattern-based invalidation."""
        cache = MultiLevelCache()
        cache.put("ast:file1.py:hash1", "data1")
        cache.put("ast:file2.py:hash2", "data2")
        cache.put("chunk:file1.py:hash1", "chunks1")
        cache.put("chunk:file2.py:hash2", "chunks2")
        count = cache.invalidate_pattern("ast:file1.py:*")
        assert count == 1
        assert cache.get("ast:file1.py:hash1") is None
        assert cache.get("ast:file2.py:hash2") == "data2"
        assert cache.get("chunk:file1.py:hash1") == "chunks1"

    @classmethod
    def test_statistics_aggregation(cls):
        """Test statistics aggregation across levels."""
        cache = MultiLevelCache()
        cache.put("ast:key", "value")
        cache.get("ast:key")
        cache.get("ast:missing")
        cache.put("chunk:key", "value")
        cache.get("chunk:key")
        stats = cache.get_stats()
        assert stats["total_hits"] == 2
        assert stats["total_misses"] == 1
        assert stats["overall_hit_rate"] == 2 / 3


class TestCacheManager:
    """Test cache manager implementation."""

    @classmethod
    def test_ast_caching(cls):
        """Test AST caching functionality."""
        manager = CacheManager()
        mock_ast = Mock()
        manager.cache_ast("file.py", "hash123", mock_ast, "python", 10.5)
        cached = manager.get_cached_ast("file.py", "hash123")
        assert cached is not None
        assert cached["ast"] == mock_ast
        assert cached["language"] == "python"
        assert cached["parse_time_ms"] == 10.5
        assert manager.get_cached_ast("file.py", "different_hash") is None

    @classmethod
    def test_chunk_caching(cls):
        """Test chunk caching functionality."""
        manager = CacheManager()
        chunks = [
            CodeChunk(
                language="python",
                file_path="test.py",
                node_type="function_definition",
                start_line=1,
                end_line=5,
                byte_start=0,
                byte_end=100,
                parent_context="",
                content="def test(): pass",
            ),
        ]
        manager.cache_chunks("test.py", "hash456", chunks)
        cached = manager.get_cached_chunks("test.py", "hash456")
        assert cached == chunks

    @classmethod
    def test_file_invalidation(cls):
        """Test invalidating all caches for a file."""
        manager = CacheManager()
        manager.cache_ast("test.py", "hash1", Mock(), "python", 5.0)
        manager.cache_chunks("test.py", "hash1", [])
        manager.put("query:test.py:pattern", "result")
        manager.put("metadata:test.py:info", "metadata")
        count = manager.invalidate_file("test.py")
        assert count >= 4
        assert manager.get_cached_ast("test.py", "hash1") is None
        assert manager.get_cached_chunks("test.py", "hash1") is None
        assert manager.get("query:test.py:pattern") is None
        assert manager.get("metadata:test.py:info") is None


class TestIncrementalParser:
    """Test incremental parsing functionality."""

    @classmethod
    def test_change_detection(cls):
        """Test detecting changes between sources."""
        parser = IncrementalParser()
        old_source = b"line 1\nline 2\nline 3\n"
        new_source = b"line 1\nmodified line 2\nline 3\n"
        changes = parser.detect_changes(old_source, new_source)
        assert len(changes) > 0

    @classmethod
    def test_no_changes(cls):
        """Test when sources are identical."""
        parser = IncrementalParser()
        source = b"line 1\nline 2\nline 3\n"
        changes = parser.detect_changes(source, source)
        assert len(changes) == 0 or all(
            old_end == new_end for _, old_end, new_end, _ in changes
        )


class TestMemoryPool:
    """Test memory pool functionality."""

    @classmethod
    def test_parser_pooling(cls):
        """Test parser pooling."""
        pool = MemoryPool(max_pool_size=5)
        parser1 = pool.acquire_parser("python")
        assert parser1 is not None
        pool.release_parser(parser1, "python")
        parser2 = pool.acquire_parser("python")
        assert parser2 is parser1
        stats = pool.get_stats()
        assert stats["parser:python"]["created"] == 1
        assert stats["parser:python"]["acquired"] == 2
        assert stats["parser:python"]["released"] == 1

    @classmethod
    def test_pool_size_limit(cls):
        """Test pool size limits."""
        pool = MemoryPool(max_pool_size=2)
        parsers = []
        for _i in range(3):
            p = pool.acquire_parser("python")
            parsers.append(p)
        for p in parsers:
            pool.release_parser(p, "python")
        assert pool.size("parser:python") == 2

    @classmethod
    def test_warm_up(cls):
        """Test pool warm-up."""
        pool = MemoryPool(max_pool_size=10)
        pool.warm_up("parser:python", 3)
        assert pool.size("parser:python") == 3
        stats = pool.get_stats()
        assert stats["parser:python"]["created"] == 3


class TestPerformanceMonitor:
    """Test performance monitoring."""

    @classmethod
    def test_operation_timing(cls):
        """Test timing operations."""
        monitor = PerformanceMonitor()
        op_id = monitor.start_operation("test_op")
        time.sleep(0.1)
        duration = monitor.end_operation(op_id)
        assert duration >= 100
        metrics = monitor.get_metrics()
        assert "operation.test_op" in metrics
        assert metrics["operation.test_op"]["count"] == 1
        assert metrics["operation.test_op"]["mean"] >= 100

    @classmethod
    def test_metric_recording(cls):
        """Test recording custom metrics."""
        monitor = PerformanceMonitor()
        monitor.record_metric("file_size", 1000)
        monitor.record_metric("file_size", 2000)
        monitor.record_metric("file_size", 3000)
        metrics = monitor.get_metrics()
        assert metrics["file_size"]["count"] == 3
        assert metrics["file_size"]["mean"] == 2000
        assert metrics["file_size"]["min"] == 1000
        assert metrics["file_size"]["max"] == 3000

    @classmethod
    def test_context_manager(cls):
        """Test context manager for timing."""
        monitor = PerformanceMonitor()
        with monitor.measure("test_operation"):
            time.sleep(0.05)
        metrics = monitor.get_metrics()
        assert "operation.test_operation" in metrics
        assert metrics["operation.test_operation"]["mean"] >= 50


class TestBatchProcessor:
    """Test batch processing functionality."""

    @classmethod
    def test_priority_queue(cls):
        """Test priority-based processing."""
        processor = BatchProcessor(max_workers=1)
        processor.add_file("low_priority.py", priority=1)
        processor.add_file("high_priority.py", priority=10)
        processor.add_file("medium_priority.py", priority=5)
        assert processor.pending_count() == 3

    @classmethod
    def test_duplicate_prevention(cls):
        """Test that duplicates are prevented."""
        processor = BatchProcessor()
        processor.add_file("test.py", priority=5)
        processor.add_file("test.py", priority=10)
        assert processor.pending_count() == 1

    @classmethod
    def test_batch_size(cls):
        """Test batch size limits."""
        processor = BatchProcessor(max_workers=1)
        for i in range(10):
            processor.add_file(f"file_{i}.py")
        with patch.object(processor, "_process_file", return_value=[]):
            results = processor.process_batch(batch_size=5, parallel=False)
        assert len(results) <= 5
        assert processor.pending_count() == 5


class TestEnhancedChunker:
    """Test enhanced chunker with all optimizations."""

    @classmethod
    def test_caching_behavior(cls):
        """Test that caching works correctly."""
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
            f.write("def test(): pass")
            test_file = Path(f.name)
        try:
            chunker = EnhancedChunker()
            chunks1 = chunker.chunk_file(test_file, "python")
            chunks2 = chunker.chunk_file(test_file, "python")
            assert chunks1 == chunks2
            stats = chunker.get_stats()
            cache_stats = stats["cache"]
            assert cache_stats["total_hits"] > 0
        finally:
            test_file.unlink()

    @classmethod
    def test_cache_invalidation(cls):
        """Test cache invalidation."""
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            mode="w",
            suffix=".py",
            delete=False,
        ) as f:
            f.write("def test(): pass")
            test_file = Path(f.name)
        try:
            chunker = EnhancedChunker()
            chunks1 = chunker.chunk_file(test_file, "python")
            chunker.invalidate_file(test_file)
            chunks2 = chunker.chunk_file(test_file, "python")
            assert chunks1 == chunks2
        finally:
            test_file.unlink()

    @classmethod
    def test_warm_up(cls):
        """Test cache warm-up."""
        chunker = EnhancedChunker()
        chunker.warm_up(["python", "javascript"])
        pool_stats = chunker._pool.get_stats()
        assert "parser:python" in pool_stats
        assert pool_stats["parser:python"]["pooled"] > 0
        assert "parser:javascript" in pool_stats
        assert pool_stats["parser:javascript"]["pooled"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
