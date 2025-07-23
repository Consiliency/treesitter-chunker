"""Garbage Collection tuning for memory-intensive operations.

This module provides utilities for tuning Python's garbage collector
to optimize performance for large-scale code processing.
"""

import gc
import sys
import time
import weakref
from contextlib import contextmanager
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class GCStats:
    """Statistics about garbage collection."""
    collections: Dict[int, int]  # generation -> count
    collected: Dict[int, int]    # generation -> objects collected
    uncollectable: Dict[int, int]  # generation -> uncollectable objects
    elapsed_time: Dict[int, float]  # generation -> total time spent
    enabled: bool
    thresholds: tuple


class GCTuner:
    """Manages garbage collection tuning for optimal performance."""
    
    def __init__(self):
        """Initialize GC tuner."""
        self.original_thresholds = gc.get_threshold()
        self.stats_before = self._get_gc_stats()
        self.monitoring = False
        self._gc_was_enabled = gc.isenabled()
        
    def _get_gc_stats(self) -> Dict[int, Dict[str, int]]:
        """Get current GC statistics."""
        stats = {}
        for i in range(gc.get_count().__len__()):
            stats[i] = {
                'collections': gc.get_stats()[i]['collections'] if i < len(gc.get_stats()) else 0,
                'collected': gc.get_stats()[i]['collected'] if i < len(gc.get_stats()) else 0,
                'uncollectable': gc.get_stats()[i]['uncollectable'] if i < len(gc.get_stats()) else 0,
            }
        return stats
    
    def get_stats(self) -> GCStats:
        """Get comprehensive GC statistics."""
        current_stats = self._get_gc_stats()
        stats = GCStats(
            collections={},
            collected={},
            uncollectable={},
            elapsed_time={},
            enabled=gc.isenabled(),
            thresholds=gc.get_threshold()
        )
        
        # Calculate differences
        for gen in range(len(current_stats)):
            if gen in self.stats_before:
                stats.collections[gen] = (
                    current_stats[gen]['collections'] - 
                    self.stats_before[gen]['collections']
                )
                stats.collected[gen] = (
                    current_stats[gen]['collected'] - 
                    self.stats_before[gen]['collected']
                )
                stats.uncollectable[gen] = (
                    current_stats[gen]['uncollectable'] - 
                    self.stats_before[gen]['uncollectable']
                )
        
        return stats
    
    def tune_for_batch_processing(self, batch_size: int):
        """Tune GC for batch processing operations.
        
        Args:
            batch_size: Number of items in batch
        """
        if batch_size < 100:
            # Small batches - keep default settings
            gc.set_threshold(self.original_thresholds[0], 
                           self.original_thresholds[1], 
                           self.original_thresholds[2])
        elif batch_size < 1000:
            # Medium batches - reduce frequency slightly
            gc.set_threshold(1000, 15, 15)
        else:
            # Large batches - reduce GC frequency significantly
            gc.set_threshold(50000, 30, 30)
            
        logger.info(f"Tuned GC for batch size {batch_size}: thresholds={gc.get_threshold()}")
    
    def tune_for_streaming(self):
        """Tune GC for streaming operations."""
        # For streaming, we want more frequent gen0 collections
        # but less frequent higher generation collections
        gc.set_threshold(400, 20, 20)
        logger.info(f"Tuned GC for streaming: thresholds={gc.get_threshold()}")
    
    def tune_for_memory_intensive(self):
        """Tune GC for memory-intensive operations."""
        # Increase collection frequency to keep memory usage down
        gc.set_threshold(200, 5, 5)
        logger.info(f"Tuned GC for memory-intensive ops: thresholds={gc.get_threshold()}")
    
    def disable_during_critical_section(self):
        """Disable GC during critical performance sections."""
        self._gc_was_enabled = gc.isenabled()
        gc.disable()
        logger.debug("GC disabled for critical section")
    
    def restore_gc_state(self):
        """Restore GC to previous state."""
        if self._gc_was_enabled:
            gc.enable()
        gc.set_threshold(*self.original_thresholds)
        logger.debug("GC state restored")
    
    @contextmanager
    def optimized_for_task(self, task_type: str):
        """Context manager for task-specific GC optimization.
        
        Args:
            task_type: One of 'batch', 'streaming', 'memory_intensive', 'critical'
        """
        try:
            if task_type == 'batch':
                self.tune_for_batch_processing(1000)  # Default batch size
            elif task_type == 'streaming':
                self.tune_for_streaming()
            elif task_type == 'memory_intensive':
                self.tune_for_memory_intensive()
            elif task_type == 'critical':
                self.disable_during_critical_section()
            
            yield self
            
        finally:
            self.restore_gc_state()
    
    def collect_with_stats(self, generation: Optional[int] = None) -> Dict[str, Any]:
        """Perform garbage collection and return statistics.
        
        Args:
            generation: Specific generation to collect (None for all)
            
        Returns:
            Dictionary with collection statistics
        """
        before = time.perf_counter()
        before_count = gc.get_count()
        
        if generation is None:
            collected = gc.collect()
        else:
            collected = gc.collect(generation)
            
        elapsed = time.perf_counter() - before
        after_count = gc.get_count()
        
        return {
            'collected': collected,
            'elapsed_time': elapsed,
            'before_count': before_count,
            'after_count': after_count,
            'generation': generation
        }


class MemoryOptimizer:
    """Optimizes memory usage patterns for large-scale processing."""
    
    def __init__(self):
        """Initialize memory optimizer."""
        self.gc_tuner = GCTuner()
        self._object_pools = {}
        self._weak_refs = {}
        
    def create_object_pool(self, 
                          object_type: type,
                          factory: Callable,
                          max_size: int = 100) -> 'ObjectPool':
        """Create an object pool for frequently created/destroyed objects.
        
        Args:
            object_type: Type of objects to pool
            factory: Function to create new objects
            max_size: Maximum pool size
            
        Returns:
            ObjectPool instance
        """
        pool = ObjectPool(object_type, factory, max_size)
        self._object_pools[object_type.__name__] = pool
        return pool
    
    def use_weak_references(self, obj: Any, callback: Optional[Callable] = None) -> weakref.ref:
        """Create a weak reference to an object.
        
        Args:
            obj: Object to reference weakly
            callback: Optional callback when object is garbage collected
            
        Returns:
            Weak reference to object
        """
        ref = weakref.ref(obj, callback)
        self._weak_refs[id(obj)] = ref
        return ref
    
    def memory_efficient_batch(self, items: list, batch_size: int = 1000):
        """Process items in memory-efficient batches.
        
        Args:
            items: List of items to process
            batch_size: Size of each batch
        """
        with self.gc_tuner.optimized_for_task('batch'):
            for i in range(0, len(items), batch_size):
                batch = items[i:i + batch_size]
                yield batch
                
                # Clear batch from memory
                del batch
                
                # Collect garbage every few batches
                if (i // batch_size) % 10 == 0:
                    self.gc_tuner.collect_with_stats(0)
    
    def optimize_for_file_processing(self, file_count: int):
        """Optimize memory settings for processing multiple files.
        
        Args:
            file_count: Number of files to process
        """
        if file_count < 10:
            # Few files - standard settings
            pass
        elif file_count < 100:
            # Moderate number - tune for batch
            self.gc_tuner.tune_for_batch_processing(file_count)
        else:
            # Many files - aggressive memory management
            self.gc_tuner.tune_for_memory_intensive()
            
            # Pre-allocate pools if needed
            if 'Parser' not in self._object_pools:
                logger.info("Creating parser object pool for large-scale processing")
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get current memory usage statistics."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        return {
            'rss': memory_info.rss,  # Resident Set Size
            'vms': memory_info.vms,  # Virtual Memory Size
            'percent': process.memory_percent(),
            'available': psutil.virtual_memory().available,
            'gc_stats': self.gc_tuner.get_stats(),
            'object_pools': {
                name: pool.get_stats() 
                for name, pool in self._object_pools.items()
            }
        }


class ObjectPool:
    """Generic object pool for reducing allocation overhead."""
    
    def __init__(self, object_type: type, factory: Callable, max_size: int = 100):
        """Initialize object pool.
        
        Args:
            object_type: Type of objects to pool
            factory: Function to create new objects
            max_size: Maximum pool size
        """
        self.object_type = object_type
        self.factory = factory
        self.max_size = max_size
        self._pool = []
        self._in_use = set()
        self._created_count = 0
        self._reused_count = 0
        
    def acquire(self) -> Any:
        """Acquire an object from the pool."""
        if self._pool:
            obj = self._pool.pop()
            self._reused_count += 1
        else:
            obj = self.factory()
            self._created_count += 1
            
        self._in_use.add(id(obj))
        return obj
    
    def release(self, obj: Any):
        """Release an object back to the pool."""
        obj_id = id(obj)
        if obj_id in self._in_use:
            self._in_use.remove(obj_id)
            
            if len(self._pool) < self.max_size:
                # Reset object state if it has a reset method
                if hasattr(obj, 'reset'):
                    obj.reset()
                self._pool.append(obj)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            'type': self.object_type.__name__,
            'pool_size': len(self._pool),
            'in_use': len(self._in_use),
            'created': self._created_count,
            'reused': self._reused_count,
            'reuse_rate': self._reused_count / max(1, self._created_count + self._reused_count)
        }
    
    def clear(self):
        """Clear the pool."""
        self._pool.clear()
        self._in_use.clear()


# Global memory optimizer instance
_memory_optimizer = None


def get_memory_optimizer() -> MemoryOptimizer:
    """Get the global memory optimizer instance."""
    global _memory_optimizer
    if _memory_optimizer is None:
        _memory_optimizer = MemoryOptimizer()
    return _memory_optimizer


# Convenience functions
def tune_gc_for_batch(batch_size: int):
    """Tune GC for batch processing."""
    optimizer = get_memory_optimizer()
    optimizer.gc_tuner.tune_for_batch_processing(batch_size)


def tune_gc_for_streaming():
    """Tune GC for streaming operations."""
    optimizer = get_memory_optimizer()
    optimizer.gc_tuner.tune_for_streaming()


@contextmanager
def optimized_gc(task_type: str = 'batch'):
    """Context manager for optimized GC settings."""
    optimizer = get_memory_optimizer()
    with optimizer.gc_tuner.optimized_for_task(task_type) as tuner:
        yield tuner


@contextmanager
def gc_disabled():
    """Context manager to temporarily disable GC."""
    was_enabled = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if was_enabled:
            gc.enable()