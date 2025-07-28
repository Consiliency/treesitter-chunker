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


class TestLRUCache:
    """Test LRU cache implementation."""

    def test_basic_operations(self):
        """Test basic get/put operations."""
        cache = LRUCache(max_size=3)

        # Test put and get
        cache.put("key1", "value1")
        assert cache.get("key1") == "value1"
        assert cache.get("nonexistent") is None

        # Test cache size
        assert cache.size() == 1

    def test_lru_eviction(self):
        """Test LRU eviction policy."""
        cache = LRUCache(max_size=3)

        # Fill cache
        cache.put("key1", "value1")
        cache.put("key2", "value2")
        cache.put("key3", "value3")

        # Access key1 to make it recently used
        cache.get("key1")

        # Add new item, should evict key2
        cache.put("key4", "value4")

        assert cache.get("key1") == "value1"  # Still there
        assert cache.get("key2") is None  # Evicted
        assert cache.get("key3") == "value3"  # Still there
        assert cache.get("key4") == "value4"  # New item

    def test_ttl_expiration(self):
        """Test TTL expiration."""
        cache = LRUCache(max_size=10)

        # Add item with 1 second TTL
        cache.put("key1", "value1", ttl_seconds=1)

        # Should be available immediately
        assert cache.get("key1") == "value1"

        # Wait for expiration
        time.sleep(1.1)

        # Should be expired
        assert cache.get("key1") is None

    def test_statistics(self):
        """Test cache statistics."""
        cache = LRUCache(max_size=10)

        # Generate some hits and misses
        cache.put("key1", "value1")
        cache.get("key1")  # Hit
        cache.get("key1")  # Hit
        cache.get("key2")  # Miss

        stats = cache.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 2 / 3
        assert stats["size"] == 1


class TestMultiLevelCache:
    """Test multi-level cache implementation."""

    def test_cache_routing(self):
        """Test that keys are routed to correct cache levels."""
        cache = MultiLevelCache()

        # Test different cache levels
        cache.put("ast:file.py:hash", "ast_data")
        cache.put("chunk:file.py:hash", "chunk_data")
        cache.put("query:pattern", "query_data")
        cache.put("unknown:key", "other_data")

        # Verify routing
        assert cache.get("ast:file.py:hash") == "ast_data"
        assert cache.get("chunk:file.py:hash") == "chunk_data"
        assert cache.get("query:pattern") == "query_data"
        assert cache.get("unknown:key") == "other_data"

    def test_pattern_invalidation(self):
        """Test pattern-based invalidation."""
        cache = MultiLevelCache()

        # Add multiple entries
        cache.put("ast:file1.py:hash1", "data1")
        cache.put("ast:file2.py:hash2", "data2")
        cache.put("chunk:file1.py:hash1", "chunks1")
        cache.put("chunk:file2.py:hash2", "chunks2")

        # Invalidate all ast entries for file1
        count = cache.invalidate_pattern("ast:file1.py:*")
        assert count == 1

        # Verify invalidation
        assert cache.get("ast:file1.py:hash1") is None
        assert cache.get("ast:file2.py:hash2") == "data2"
        assert cache.get("chunk:file1.py:hash1") == "chunks1"

    def test_statistics_aggregation(self):
        """Test statistics aggregation across levels."""
        cache = MultiLevelCache()

        # Generate activity on different levels
        cache.put("ast:key", "value")
        cache.get("ast:key")  # Hit
        cache.get("ast:missing")  # Miss

        cache.put("chunk:key", "value")
        cache.get("chunk:key")  # Hit

        stats = cache.get_stats()
        assert stats["total_hits"] == 2
        assert stats["total_misses"] == 1
        assert stats["overall_hit_rate"] == 2 / 3


class TestCacheManager:
    """Test cache manager implementation."""

    def test_ast_caching(self):
        """Test AST caching functionality."""
        manager = CacheManager()

        # Mock AST object
        mock_ast = Mock()

        # Cache AST
        manager.cache_ast("file.py", "hash123", mock_ast, "python", 10.5)

        # Retrieve cached AST
        cached = manager.get_cached_ast("file.py", "hash123")
        assert cached is not None
        assert cached["ast"] == mock_ast
        assert cached["language"] == "python"
        assert cached["parse_time_ms"] == 10.5

        # Wrong hash should miss
        assert manager.get_cached_ast("file.py", "different_hash") is None

    def test_chunk_caching(self):
        """Test chunk caching functionality."""
        manager = CacheManager()

        # Create test chunks
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

        # Cache chunks
        manager.cache_chunks("test.py", "hash456", chunks)

        # Retrieve cached chunks
        cached = manager.get_cached_chunks("test.py", "hash456")
        assert cached == chunks

    def test_file_invalidation(self):
        """Test invalidating all caches for a file."""
        manager = CacheManager()

        # Cache multiple items for a file
        manager.cache_ast("test.py", "hash1", Mock(), "python", 5.0)
        manager.cache_chunks("test.py", "hash1", [])
        manager.put("query:test.py:pattern", "result")
        manager.put("metadata:test.py:info", "metadata")

        # Invalidate file
        count = manager.invalidate_file("test.py")
        assert count >= 4  # At least 4 entries

        # Verify all are gone
        assert manager.get_cached_ast("test.py", "hash1") is None
        assert manager.get_cached_chunks("test.py", "hash1") is None
        assert manager.get("query:test.py:pattern") is None
        assert manager.get("metadata:test.py:info") is None


class TestIncrementalParser:
    """Test incremental parsing functionality."""

    def test_change_detection(self):
        """Test detecting changes between sources."""
        parser = IncrementalParser()

        old_source = b"line 1\nline 2\nline 3\n"
        new_source = b"line 1\nmodified line 2\nline 3\n"

        changes = parser.detect_changes(old_source, new_source)

        assert len(changes) > 0
        # Should detect change in line 2

    def test_no_changes(self):
        """Test when sources are identical."""
        parser = IncrementalParser()

        source = b"line 1\nline 2\nline 3\n"

        changes = parser.detect_changes(source, source)

        # Should detect no changes
        assert len(changes) == 0 or all(
            old_end == new_end for _, old_end, new_end, _ in changes
        )


class TestMemoryPool:
    """Test memory pool functionality."""

    def test_parser_pooling(self):
        """Test parser pooling."""
        pool = MemoryPool(max_pool_size=5)

        # Acquire parser
        parser1 = pool.acquire_parser("python")
        assert parser1 is not None

        # Release parser
        pool.release_parser(parser1, "python")

        # Acquire again - should get same instance
        parser2 = pool.acquire_parser("python")
        assert parser2 is parser1  # Same instance reused

        # Check statistics
        stats = pool.get_stats()
        assert stats["parser:python"]["created"] == 1
        assert stats["parser:python"]["acquired"] == 2
        assert stats["parser:python"]["released"] == 1

    def test_pool_size_limit(self):
        """Test pool size limits."""
        pool = MemoryPool(max_pool_size=2)

        # Create and release 3 parsers
        parsers = []
        for _i in range(3):
            p = pool.acquire_parser("python")
            parsers.append(p)

        for p in parsers:
            pool.release_parser(p, "python")

        # Pool should only keep 2
        assert pool.size("parser:python") == 2

    def test_warm_up(self):
        """Test pool warm-up."""
        pool = MemoryPool(max_pool_size=10)

        # Warm up pool
        pool.warm_up("parser:python", 3)

        # Should have 3 parsers ready
        assert pool.size("parser:python") == 3

        stats = pool.get_stats()
        assert stats["parser:python"]["created"] == 3


class TestPerformanceMonitor:
    """Test performance monitoring."""

    def test_operation_timing(self):
        """Test timing operations."""
        monitor = PerformanceMonitor()

        # Time an operation
        op_id = monitor.start_operation("test_op")
        time.sleep(0.1)  # Simulate work
        duration = monitor.end_operation(op_id)

        assert duration >= 100  # At least 100ms

        # Check metrics
        metrics = monitor.get_metrics()
        assert "operation.test_op" in metrics
        assert metrics["operation.test_op"]["count"] == 1
        assert metrics["operation.test_op"]["mean"] >= 100

    def test_metric_recording(self):
        """Test recording custom metrics."""
        monitor = PerformanceMonitor()

        # Record some metrics
        monitor.record_metric("file_size", 1000)
        monitor.record_metric("file_size", 2000)
        monitor.record_metric("file_size", 3000)

        metrics = monitor.get_metrics()
        assert metrics["file_size"]["count"] == 3
        assert metrics["file_size"]["mean"] == 2000
        assert metrics["file_size"]["min"] == 1000
        assert metrics["file_size"]["max"] == 3000

    def test_context_manager(self):
        """Test context manager for timing."""
        monitor = PerformanceMonitor()

        with monitor.measure("test_operation"):
            time.sleep(0.05)

        metrics = monitor.get_metrics()
        assert "operation.test_operation" in metrics
        assert metrics["operation.test_operation"]["mean"] >= 50


class TestBatchProcessor:
    """Test batch processing functionality."""

    def test_priority_queue(self):
        """Test priority-based processing."""
        processor = BatchProcessor(max_workers=1)

        # Add files with different priorities
        processor.add_file("low_priority.py", priority=1)
        processor.add_file("high_priority.py", priority=10)
        processor.add_file("medium_priority.py", priority=5)

        assert processor.pending_count() == 3

    def test_duplicate_prevention(self):
        """Test that duplicates are prevented."""
        processor = BatchProcessor()

        processor.add_file("test.py", priority=5)
        processor.add_file("test.py", priority=10)  # Same file

        assert processor.pending_count() == 1  # Only one entry

    def test_batch_size(self):
        """Test batch size limits."""
        processor = BatchProcessor(max_workers=1)

        # Add 10 files
        for i in range(10):
            processor.add_file(f"file_{i}.py")

        # Process batch of 5
        with patch.object(processor, "_process_file", return_value=[]):
            results = processor.process_batch(batch_size=5, parallel=False)

        assert len(results) <= 5
        assert processor.pending_count() == 5  # 5 remaining


class TestEnhancedChunker:
    """Test enhanced chunker with all optimizations."""

    def test_caching_behavior(self):
        """Test that caching works correctly."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def test(): pass")
            test_file = Path(f.name)

        try:
            chunker = EnhancedChunker()

            # First call - should cache
            chunks1 = chunker.chunk_file(test_file, "python")

            # Second call - should use cache
            chunks2 = chunker.chunk_file(test_file, "python")

            assert chunks1 == chunks2

            # Check cache stats
            stats = chunker.get_stats()
            cache_stats = stats["cache"]
            assert cache_stats["total_hits"] > 0  # Should have cache hits

        finally:
            test_file.unlink()

    def test_cache_invalidation(self):
        """Test cache invalidation."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("def test(): pass")
            test_file = Path(f.name)

        try:
            chunker = EnhancedChunker()

            # Cache file
            chunks1 = chunker.chunk_file(test_file, "python")

            # Invalidate
            chunker.invalidate_file(test_file)

            # Should reparse
            chunks2 = chunker.chunk_file(test_file, "python")

            # Results should be same but reparsed
            assert chunks1 == chunks2

        finally:
            test_file.unlink()

    def test_warm_up(self):
        """Test cache warm-up."""
        chunker = EnhancedChunker()

        # Warm up for Python and JavaScript
        chunker.warm_up(["python", "javascript"])

        # Check pool has pre-created parsers
        pool_stats = chunker._pool.get_stats()
        assert "parser:python" in pool_stats
        assert pool_stats["parser:python"]["pooled"] > 0
        assert "parser:javascript" in pool_stats
        assert pool_stats["parser:javascript"]["pooled"] > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
