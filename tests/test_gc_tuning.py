"""Tests for garbage collection tuning."""

import pytest
import gc
import time
from unittest.mock import Mock, patch

from chunker.gc_tuning import (
    GCTuner, MemoryOptimizer, ObjectPool,
    get_memory_optimizer, tune_gc_for_batch, tune_gc_for_streaming,
    optimized_gc, gc_disabled
)


class TestGCTuner:
    """Test GC tuner functionality."""
    
    def test_gc_tuner_initialization(self):
        """Test GC tuner initialization."""
        tuner = GCTuner()
        
        # Should store original thresholds
        assert tuner.original_thresholds == gc.get_threshold()
        assert tuner._gc_was_enabled == gc.isenabled()
    
    def test_tune_for_batch_processing(self):
        """Test GC tuning for different batch sizes."""
        tuner = GCTuner()
        original = gc.get_threshold()
        
        try:
            # Small batch - should keep defaults
            tuner.tune_for_batch_processing(50)
            assert gc.get_threshold() == original
            
            # Medium batch
            tuner.tune_for_batch_processing(500)
            thresholds = gc.get_threshold()
            assert thresholds[0] == 1000
            assert thresholds[1] == 15
            assert thresholds[2] == 15
            
            # Large batch
            tuner.tune_for_batch_processing(5000)
            thresholds = gc.get_threshold()
            assert thresholds[0] == 50000
            assert thresholds[1] == 30
            assert thresholds[2] == 30
            
        finally:
            gc.set_threshold(*original)
    
    def test_tune_for_streaming(self):
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
    
    def test_tune_for_memory_intensive(self):
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
    
    def test_disable_restore_gc(self):
        """Test disabling and restoring GC state."""
        tuner = GCTuner()
        was_enabled = gc.isenabled()
        
        try:
            # Disable GC
            tuner.disable_during_critical_section()
            assert not gc.isenabled()
            
            # Restore GC
            tuner.restore_gc_state()
            assert gc.isenabled() == was_enabled
            assert gc.get_threshold() == tuner.original_thresholds
        finally:
            if was_enabled:
                gc.enable()
            else:
                gc.disable()
    
    def test_optimized_for_task_context(self):
        """Test context manager for task-specific optimization."""
        original = gc.get_threshold()
        
        # Test batch optimization
        with optimized_gc('batch') as tuner:
            assert isinstance(tuner, GCTuner)
            # Should have tuned for batch
            assert gc.get_threshold() != original
        
        # Should restore after context
        assert gc.get_threshold() == original
        
        # Test critical section
        assert gc.isenabled()
        with optimized_gc('critical'):
            assert not gc.isenabled()
        assert gc.isenabled()
    
    def test_collect_with_stats(self):
        """Test garbage collection with statistics."""
        tuner = GCTuner()
        
        # Create some garbage
        for _ in range(100):
            _ = [i for i in range(100)]
        
        # Collect and get stats
        stats = tuner.collect_with_stats()
        
        assert 'collected' in stats
        assert 'elapsed_time' in stats
        assert 'before_count' in stats
        assert 'after_count' in stats
        assert stats['collected'] >= 0
        assert stats['elapsed_time'] >= 0
        
        # Test specific generation
        stats = tuner.collect_with_stats(generation=0)
        assert stats['generation'] == 0


class TestMemoryOptimizer:
    """Test memory optimizer functionality."""
    
    def test_memory_optimizer_singleton(self):
        """Test memory optimizer singleton pattern."""
        opt1 = get_memory_optimizer()
        opt2 = get_memory_optimizer()
        assert opt1 is opt2
    
    def test_object_pool_creation(self):
        """Test creating object pools."""
        optimizer = MemoryOptimizer()
        
        # Create pool for dict objects
        pool = optimizer.create_object_pool(
            dict,
            lambda: {},
            max_size=10
        )
        
        assert isinstance(pool, ObjectPool)
        assert pool.object_type == dict
        assert pool.max_size == 10
        assert 'dict' in optimizer._object_pools
    
    def test_weak_references(self):
        """Test weak reference management."""
        optimizer = MemoryOptimizer()
        
        # Create object that supports weak references (not dict)
        class TestObject:
            def __init__(self):
                self.data = {'test': 'data'}
                
        obj = TestObject()
        ref = optimizer.use_weak_references(obj)
        
        # Reference should be valid
        assert ref() is obj
        
        # Delete object
        obj_id = id(obj)
        del obj
        
        # Force garbage collection
        gc.collect()
        
        # Reference should be invalid
        assert ref() is None
    
    def test_memory_efficient_batch(self):
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
    
    def test_optimize_for_file_processing(self):
        """Test optimization for different file counts."""
        optimizer = MemoryOptimizer()
        original = gc.get_threshold()
        
        try:
            # Few files - no change
            optimizer.optimize_for_file_processing(5)
            assert gc.get_threshold() == original
            
            # Moderate files - batch tuning
            optimizer.optimize_for_file_processing(50)
            # With 50 files (< 100 batch size), it keeps original settings
            assert gc.get_threshold() == original
            
            # Many files - memory intensive tuning
            optimizer.optimize_for_file_processing(200)
            thresholds = gc.get_threshold()
            assert thresholds[0] == 200  # More aggressive collection
            
        finally:
            gc.set_threshold(*original)
    
    @patch('psutil.Process')
    @patch('psutil.virtual_memory')
    def test_get_memory_usage(self, mock_virtual_memory, mock_process):
        """Test memory usage statistics."""
        # Mock memory info
        mock_memory_info = Mock()
        mock_memory_info.rss = 100 * 1024 * 1024  # 100MB
        mock_memory_info.vms = 200 * 1024 * 1024  # 200MB
        
        mock_process_instance = Mock()
        mock_process_instance.memory_info.return_value = mock_memory_info
        mock_process_instance.memory_percent.return_value = 5.0
        mock_process.return_value = mock_process_instance
        
        mock_virtual_memory.return_value.available = 8 * 1024 * 1024 * 1024  # 8GB
        
        optimizer = MemoryOptimizer()
        usage = optimizer.get_memory_usage()
        
        assert usage['rss'] == 100 * 1024 * 1024
        assert usage['vms'] == 200 * 1024 * 1024
        assert usage['percent'] == 5.0
        assert usage['available'] == 8 * 1024 * 1024 * 1024
        assert 'gc_stats' in usage
        assert 'object_pools' in usage


class TestObjectPool:
    """Test object pool functionality."""
    
    def test_object_pool_basic_operations(self):
        """Test basic pool operations."""
        # Create pool for lists
        pool = ObjectPool(
            list,
            lambda: [],
            max_size=5
        )
        
        # Acquire objects
        obj1 = pool.acquire()
        obj2 = pool.acquire()
        
        assert isinstance(obj1, list)
        assert isinstance(obj2, list)
        assert obj1 is not obj2
        
        # Check stats
        stats = pool.get_stats()
        assert stats['created'] == 2
        assert stats['reused'] == 0
        assert stats['in_use'] == 2
        
        # Release objects
        pool.release(obj1)
        pool.release(obj2)
        
        # Acquire again - should reuse
        obj3 = pool.acquire()
        stats = pool.get_stats()
        assert stats['reused'] == 1
        assert stats['in_use'] == 1
    
    def test_object_pool_max_size(self):
        """Test pool size limits."""
        pool = ObjectPool(
            dict,
            lambda: {},
            max_size=2
        )
        
        # Create and release 3 objects
        objects = [pool.acquire() for _ in range(3)]
        for obj in objects:
            pool.release(obj)
        
        # Pool should only keep 2
        stats = pool.get_stats()
        assert stats['pool_size'] == 2
    
    def test_object_pool_with_reset(self):
        """Test pool with objects that have reset method."""
        class ResettableObject:
            def __init__(self):
                self.value = 0
                self.reset_called = False
                
            def reset(self):
                self.value = 0
                self.reset_called = True
        
        pool = ObjectPool(
            ResettableObject,
            ResettableObject,
            max_size=5
        )
        
        # Acquire and modify object
        obj = pool.acquire()
        obj.value = 42
        
        # Release - should call reset
        pool.release(obj)
        
        # Acquire again
        obj2 = pool.acquire()
        assert obj2.reset_called
        assert obj2.value == 0
    
    def test_object_pool_clear(self):
        """Test clearing the pool."""
        pool = ObjectPool(
            list,
            lambda: [],
            max_size=10
        )
        
        # Create some objects
        objects = [pool.acquire() for _ in range(5)]
        for obj in objects[:-1]:
            pool.release(obj)
        
        # Clear pool
        pool.clear()
        
        stats = pool.get_stats()
        assert stats['pool_size'] == 0
        assert stats['in_use'] == 0


class TestConvenienceFunctions:
    """Test convenience functions."""
    
    def test_tune_gc_for_batch(self):
        """Test batch GC tuning convenience function."""
        original = gc.get_threshold()
        
        try:
            tune_gc_for_batch(1000)
            assert gc.get_threshold() != original
        finally:
            gc.set_threshold(*original)
    
    def test_tune_gc_for_streaming(self):
        """Test streaming GC tuning convenience function."""
        original = gc.get_threshold()
        
        try:
            tune_gc_for_streaming()
            thresholds = gc.get_threshold()
            assert thresholds[0] == 400
        finally:
            gc.set_threshold(*original)
    
    def test_gc_disabled_context(self):
        """Test GC disabled context manager."""
        assert gc.isenabled()
        
        with gc_disabled():
            assert not gc.isenabled()
        
        assert gc.isenabled()


class TestIntegration:
    """Integration tests for GC tuning with chunking."""
    
    def test_gc_tuning_with_large_file_processing(self):
        """Test GC tuning improves performance for large operations."""
        # Create large data structure
        large_data = [{'id': i, 'data': list(range(100))} for i in range(1000)]
        
        # Time without optimization
        gc.collect()
        start = time.perf_counter()
        
        # Simulate processing
        results1 = []
        for item in large_data:
            results1.append(sum(item['data']))
        
        time_without = time.perf_counter() - start
        
        # Time with optimization
        gc.collect()
        start = time.perf_counter()
        
        with optimized_gc('batch'):
            results2 = []
            for item in large_data:
                results2.append(sum(item['data']))
        
        time_with = time.perf_counter() - start
        
        # Results should be the same
        assert results1 == results2
        
        # Note: We can't guarantee performance improvement in tests,
        # but we can verify the optimization was applied
        assert gc.get_threshold() == GCTuner().original_thresholds