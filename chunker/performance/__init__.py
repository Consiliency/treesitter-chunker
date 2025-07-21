"""Performance optimization module for Tree-sitter chunker.

This module provides performance optimizations including:
- Multi-level caching for ASTs, chunks, and queries
- Incremental parsing for file changes
- Memory pooling for parser instances
- Performance monitoring and metrics
- Batch processing for multiple files
"""

from .cache.manager import CacheManager as CacheManagerImpl
from .optimization.incremental import IncrementalParser as IncrementalParserImpl
from .optimization.memory_pool import MemoryPool as MemoryPoolImpl
from .optimization.monitor import PerformanceMonitor as PerformanceMonitorImpl
from .optimization.batch import BatchProcessor as BatchProcessorImpl

__all__ = [
    'CacheManagerImpl',
    'IncrementalParserImpl', 
    'MemoryPoolImpl',
    'PerformanceMonitorImpl',
    'BatchProcessorImpl'
]