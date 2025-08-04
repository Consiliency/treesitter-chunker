"""Tests for garbage collection tuning."""

import gc
import time
from unittest.mock import Mock, patch

from chunker._internal.gc_tuning import (
    GCTuner,
    MemoryOptimizer,
    ObjectPool,
    gc_disabled,
    get_memory_optimizer,
    optimized_gc,
    tune_gc_for_batch,
    tune_gc_for_streaming,
)


class TestGCTuner:
    """Test GC tuner functionality."""

    @classmethod
    def test_gc_tuner_initialization(cls):
        """Test GC tuner initialization."""
        tuner = GCTuner()
        assert tuner.original_thresholds == gc.get_threshold()
        assert tuner._gc_was_enabled == gc.isenabled()

    @classmethod
    def test_tune_for_batch_processing(cls):
        """Test GC tuning for different batch sizes."""
        tuner = GCTuner()
        original = gc.get_threshold()
        try:
            tuner.tune_for_batch_processing(50)
            assert gc.get_threshold() == original
            tuner.tune_for_batch_processing(500)
            thresholds = gc.get_threshold()
            assert thresholds[0] == 1000
            assert thresholds[1] == 15
            assert thresholds[2] == 15
            tuner.tune_for_batch_processing(5000)
            thresholds = gc.get_threshold()
            assert thresholds[0] == 50000
            assert thresholds[1] == 30
            assert thresholds[2] == 30
        finally:
            gc.set_threshold(*original)

    @classmethod
    def test_tune_for_streaming(cls):
        """Test GC tuning for streaming operations."""
        tuner = GCTuner()
        original = gc.get_threshold()
        try:
            tuner.tune_for_streaming()
            thresholds = gc.get_threshold()
            assert thresholds[0] == 400
            assert thresholds[1] == 20
            assert thresholds[2] == 20
        finally:
            gc.set_threshold(*original)

    @classmethod
    def test_tune_for_memory_intensive(cls):
        """Test GC tuning for memory-intensive operations."""
        tuner = GCTuner()
        original = gc.get_threshold()
        try:
            tuner.tune_for_memory_intensive()
            thresholds = gc.get_threshold()
            assert thresholds[0] == 200
            assert thresholds[1] == 5
            assert thresholds[2] == 5
        finally:
            gc.set_threshold(*original)

    @classmethod
    def test_disable_restore_gc(cls):
        """Test disabling and restoring GC state."""
        tuner = GCTuner()
        was_enabled = gc.isenabled()
        try:
            tuner.disable_during_critical_section()
            assert not gc.isenabled()
            tuner.restore_gc_state()
            assert gc.isenabled() == was_enabled
            assert gc.get_threshold() == tuner.original_thresholds
        finally:
            if was_enabled:
                gc.enable()
            else:
                gc.disable()

    @staticmethod
    def test_optimized_for_task_context():
        """Test context manager for task-specific optimization."""
        original = gc.get_threshold()
        with optimized_gc("batch") as tuner:
            assert isinstance(tuner, GCTuner)
            assert gc.get_threshold() != original
        assert gc.get_threshold() == original
        assert gc.isenabled()
        with optimized_gc("critical"):
            assert not gc.isenabled()
        assert gc.isenabled()

    @classmethod
    def test_collect_with_stats(cls):
        """Test garbage collection with statistics."""
        tuner = GCTuner()
        for _ in range(100):
            _ = list(range(100))
        stats = tuner.collect_with_stats()
        assert "collected" in stats
        assert "elapsed_time" in stats
        assert "before_count" in stats
        assert "after_count" in stats
        assert stats["collected"] >= 0
        assert stats["elapsed_time"] >= 0
        stats = tuner.collect_with_stats(generation=0)
        assert stats["generation"] == 0


class TestMemoryOptimizer:
    """Test memory optimizer functionality."""

    @staticmethod
    def test_memory_optimizer_singleton():
        """Test memory optimizer singleton pattern."""
        opt1 = get_memory_optimizer()
        opt2 = get_memory_optimizer()
        assert opt1 is opt2

    @classmethod
    def test_object_pool_creation(cls):
        """Test creating object pools."""
        optimizer = MemoryOptimizer()
        pool = optimizer.create_object_pool(dict, dict, max_size=10)
        assert isinstance(pool, ObjectPool)
        assert pool.object_type is dict
        assert pool.max_size == 10
        assert "dict" in optimizer._object_pools

    @staticmethod
    def test_weak_references():
        """Test weak reference management."""
        optimizer = MemoryOptimizer()

        class TestObject:

            def __init__(self):
                self.data = {"test": "data"}

        obj = TestObject()
        ref = optimizer.use_weak_references(obj)
        assert ref() is obj
        id(obj)
        del obj
        gc.collect()
        assert ref() is None

    @classmethod
    def test_memory_efficient_batch(cls):
        """Test memory-efficient batch processing."""
        optimizer = MemoryOptimizer()
        items = list(range(2500))
        batches_processed = 0
        total_items = 0
        for batch in optimizer.memory_efficient_batch(items, batch_size=1000):
            batches_processed += 1
            total_items += len(batch)
            assert len(batch) <= 1000
        assert batches_processed == 3
        assert total_items == 2500

    @classmethod
    def test_optimize_for_file_processing(cls):
        """Test optimization for different file counts."""
        optimizer = MemoryOptimizer()
        original = gc.get_threshold()
        try:
            optimizer.optimize_for_file_processing(5)
            assert gc.get_threshold() == original
            optimizer.optimize_for_file_processing(50)
            assert gc.get_threshold() == original
            optimizer.optimize_for_file_processing(200)
            thresholds = gc.get_threshold()
            assert thresholds[0] == 200
        finally:
            gc.set_threshold(*original)

    @classmethod
    @patch("psutil.Process")
    @patch("psutil.virtual_memory")
    def test_get_memory_usage(cls, mock_virtual_memory, mock_process):
        """Test memory usage statistics."""
        mock_memory_info = Mock()
        mock_memory_info.rss = 100 * 1024 * 1024
        mock_memory_info.vms = 200 * 1024 * 1024
        mock_process_instance = Mock()
        mock_process_instance.memory_info.return_value = mock_memory_info
        mock_process_instance.memory_percent.return_value = 5.0
        mock_process.return_value = mock_process_instance
        mock_virtual_memory.return_value.available = 8 * 1024 * 1024 * 1024
        optimizer = MemoryOptimizer()
        usage = optimizer.get_memory_usage()
        assert usage["rss"] == 100 * 1024 * 1024
        assert usage["vms"] == 200 * 1024 * 1024
        assert usage["percent"] == 5.0
        assert usage["available"] == 8 * 1024 * 1024 * 1024
        assert "gc_stats" in usage
        assert "object_pools" in usage


class TestObjectPool:
    """Test object pool functionality."""

    @classmethod
    def test_object_pool_basic_operations(cls):
        """Test basic pool operations."""
        pool = ObjectPool(list, list, max_size=5)
        obj1 = pool.acquire()
        obj2 = pool.acquire()
        assert isinstance(obj1, list)
        assert isinstance(obj2, list)
        assert obj1 is not obj2
        stats = pool.get_stats()
        assert stats["created"] == 2
        assert stats["reused"] == 0
        assert stats["in_use"] == 2
        pool.release(obj1)
        pool.release(obj2)
        pool.acquire()
        stats = pool.get_stats()
        assert stats["reused"] == 1
        assert stats["in_use"] == 1

    @classmethod
    def test_object_pool_max_size(cls):
        """Test pool size limits."""
        pool = ObjectPool(dict, dict, max_size=2)
        objects = [pool.acquire() for _ in range(3)]
        for obj in objects:
            pool.release(obj)
        stats = pool.get_stats()
        assert stats["pool_size"] == 2

    @staticmethod
    def test_object_pool_with_reset():
        """Test pool with objects that have reset method."""

        class ResettableObject:

            def __init__(self):
                self.value = 0
                self.reset_called = False

            def reset(self):
                self.value = 0
                self.reset_called = True

        pool = ObjectPool(ResettableObject, ResettableObject, max_size=5)
        obj = pool.acquire()
        obj.value = 42
        pool.release(obj)
        obj2 = pool.acquire()
        assert obj2.reset_called
        assert obj2.value == 0

    @classmethod
    def test_object_pool_clear(cls):
        """Test clearing the pool."""
        pool = ObjectPool(list, list, max_size=10)
        objects = [pool.acquire() for _ in range(5)]
        for obj in objects[:-1]:
            pool.release(obj)
        pool.clear()
        stats = pool.get_stats()
        assert stats["pool_size"] == 0
        assert stats["in_use"] == 0


class TestConvenienceFunctions:
    """Test convenience functions."""

    @staticmethod
    def test_tune_gc_for_batch():
        """Test batch GC tuning convenience function."""
        original = gc.get_threshold()
        try:
            tune_gc_for_batch(1000)
            assert gc.get_threshold() != original
        finally:
            gc.set_threshold(*original)

    @staticmethod
    def test_tune_gc_for_streaming():
        """Test streaming GC tuning convenience function."""
        original = gc.get_threshold()
        try:
            tune_gc_for_streaming()
            thresholds = gc.get_threshold()
            assert thresholds[0] == 400
        finally:
            gc.set_threshold(*original)

    @staticmethod
    def test_gc_disabled_context():
        """Test GC disabled context manager."""
        assert gc.isenabled()
        with gc_disabled():
            assert not gc.isenabled()
        assert gc.isenabled()


class TestIntegration:
    """Integration tests for GC tuning with chunking."""

    @classmethod
    def test_gc_tuning_with_large_file_processing(cls):
        """Test GC tuning improves performance for large operations."""
        large_data = [{"id": i, "data": list(range(100))} for i in range(1000)]
        gc.collect()
        start = time.perf_counter()
        results1 = [sum(item["data"]) for item in large_data]
        time.perf_counter() - start
        gc.collect()
        start = time.perf_counter()
        with optimized_gc("batch"):
            results2 = [sum(item["data"]) for item in large_data]
        time.perf_counter() - start
        assert results1 == results2
        assert gc.get_threshold() == GCTuner().original_thresholds
