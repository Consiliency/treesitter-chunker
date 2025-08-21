"""Performance optimization module for Tree-sitter chunker.

This module provides performance optimizations including:
- Multi-level caching for ASTs, chunks, and queries
- Incremental parsing for file changes
- Memory pooling for parser instances
- Performance monitoring and metrics
- Batch processing for multiple files
- Core performance framework (Phase 3)
"""

from .cache.manager import CacheManager as CacheManagerImpl

# Phase 3: Core performance framework
from .core import (
    MetricsCollector,
    OptimizationEngine,
    PerformanceBudget,
    PerformanceManager,
    PerformanceMetric,
    PerformanceProfile,
    PerformanceUtils,
)
from .optimization.batch import BatchProcessor as BatchProcessorImpl
from .optimization.incremental import IncrementalParser as IncrementalParserImpl
from .optimization.memory_pool import MemoryPool as MemoryPoolImpl
from .optimization.monitor import PerformanceMonitor as PerformanceMonitorImpl

__all__ = [
    # Phase 2 components
    "BatchProcessorImpl",
    "CacheManagerImpl",
    "IncrementalParserImpl",
    "MemoryPoolImpl",
    "MetricsCollector",
    "OptimizationEngine",
    "PerformanceBudget",
    "PerformanceManager",
    # Phase 3 core framework
    "PerformanceMetric",
    "PerformanceMonitorImpl",
    "PerformanceProfile",
    "PerformanceUtils",
]
