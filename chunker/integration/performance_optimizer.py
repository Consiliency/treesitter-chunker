"""Performance Optimization System for treesitter-chunker - Task 1.9.2.

This module implements a comprehensive performance optimization system for the integrated
grammar management system, providing multi-level caching, memory management, concurrency
optimization, I/O optimization, and real-time performance monitoring.

Key Features:
- PerformanceOptimizer: Main orchestrator for all optimization strategies
- Multi-level caching system with LRU, TTL, and intelligent invalidation
- Memory optimization with object pooling and garbage collection tuning
- Concurrency optimization with dynamic thread pools and async operations
- I/O optimization with batch operations and connection pooling
- Real-time performance monitoring and bottleneck identification
- Auto-optimization with self-tuning based on usage patterns
- Integration with SystemIntegrator for unified system management

Optimization Strategies:
1. CacheOptimizer: Multi-level caching with intelligent invalidation
2. MemoryOptimizer: Memory pooling, GC tuning, object reuse
3. ConcurrencyOptimizer: Thread pools, async operations, lock optimization
4. IOOptimizer: Batch operations, connection pooling, async I/O
5. QueryOptimizer: Query optimization and index management

Performance Monitoring:
- Real-time metrics collection with minimal overhead
- Bottleneck identification and analysis
- Resource usage tracking (CPU, memory, I/O)
- Performance trend analysis and alert generation
- Auto-tuning based on performance patterns

This implementation provides production-ready performance optimization with
comprehensive monitoring, auto-tuning capabilities, and graceful fallback handling.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import contextlib
import gc
import hashlib
import json
import logging
import multiprocessing as mp
import os
import pickle
import sqlite3
import sys
import tempfile
import threading
import time
import weakref
from collections import OrderedDict, defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta, timezone
from enum import Enum
from functools import lru_cache, wraps
from pathlib import Path
from queue import Empty, PriorityQueue, Queue
from threading import Condition, Event, Lock, RLock, Semaphore
from typing import Any, Dict, Generic, List, Optional, Set, Tuple, TypeVar, Union

import psutil

# Import system integrator with graceful fallback
try:
    from .core_integration import SystemIntegrator, get_system_integrator

    CORE_INTEGRATION_AVAILABLE = True
except ImportError as e:
    logging.warning(f"Core integration not available: {e}")
    CORE_INTEGRATION_AVAILABLE = False
    SystemIntegrator = None
    get_system_integrator = None

# Import user config with graceful fallback
try:
    from ..grammar_management.config import UserConfig

    USER_CONFIG_AVAILABLE = True
except ImportError as e:
    logging.warning(f"User config not available: {e}")
    USER_CONFIG_AVAILABLE = False
    UserConfig = None


T = TypeVar("T")
K = TypeVar("K")
V = TypeVar("V")


class OptimizationLevel(Enum):
    """Performance optimization levels."""

    CONSERVATIVE = "conservative"
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"
    CUSTOM = "custom"


class PerformanceMetric(Enum):
    """Performance metrics tracked by the system."""

    CPU_USAGE = "cpu_usage"
    MEMORY_USAGE = "memory_usage"
    CACHE_HIT_RATE = "cache_hit_rate"
    RESPONSE_TIME = "response_time"
    THROUGHPUT = "throughput"
    ERROR_RATE = "error_rate"
    QUEUE_DEPTH = "queue_depth"
    THREAD_UTILIZATION = "thread_utilization"
    GC_FREQUENCY = "gc_frequency"
    IO_WAIT_TIME = "io_wait_time"


class AlertSeverity(Enum):
    """Alert severity levels."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class PerformanceAlert:
    """Performance alert information."""

    metric: PerformanceMetric
    severity: AlertSeverity
    threshold: float
    current_value: float
    timestamp: datetime
    message: str
    recommendations: list[str] = field(default_factory=list)


T = TypeVar("T")


@dataclass
class CacheEntry(Generic[T]):
    """Cache entry with metadata."""

    key: str
    value: T
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    ttl: timedelta | None = None
    size_bytes: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if entry has expired."""
        if self.ttl is None:
            return False
        return datetime.now(UTC) - self.created_at > self.ttl

    def touch(self) -> None:
        """Update access metadata."""
        self.last_accessed = datetime.now(UTC)
        self.access_count += 1


@dataclass
class MemoryPool:
    """Memory pool for object reuse."""

    name: str
    object_factory: Callable[[], Any]
    max_size: int = 100
    objects: Queue = field(default_factory=Queue)
    created_count: int = 0
    reused_count: int = 0
    lock: Lock = field(default_factory=Lock)

    def get_object(self) -> Any:
        """Get object from pool or create new one."""
        with self.lock:
            try:
                obj = self.objects.get_nowait()
                self.reused_count += 1
                return obj
            except Empty:
                obj = self.object_factory()
                self.created_count += 1
                return obj

    def return_object(self, obj: Any) -> None:
        """Return object to pool."""
        with self.lock:
            if self.objects.qsize() < self.max_size:
                # Reset object state if it has a reset method
                if hasattr(obj, "reset"):
                    obj.reset()
                self.objects.put_nowait(obj)

    def get_stats(self) -> dict[str, Any]:
        """Get pool statistics."""
        with self.lock:
            return {
                "name": self.name,
                "max_size": self.max_size,
                "current_size": self.objects.qsize(),
                "created_count": self.created_count,
                "reused_count": self.reused_count,
                "reuse_ratio": self.reused_count / max(self.created_count, 1),
            }


class LRUCache(Generic[K, V]):
    """Thread-safe LRU cache with TTL support."""

    def __init__(self, max_size: int = 1000, default_ttl: timedelta | None = None):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.cache: OrderedDict[K, CacheEntry[V]] = OrderedDict()
        self.lock = RLock()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def get(self, key: K, default: V | None = None) -> V | None:
        """Get value from cache."""
        with self.lock:
            if key not in self.cache:
                self.misses += 1
                return default

            entry = self.cache[key]
            if entry.is_expired():
                del self.cache[key]
                self.misses += 1
                return default

            # Move to end (most recently used)
            self.cache.move_to_end(key)
            entry.touch()
            self.hits += 1
            return entry.value

    def put(self, key: K, value: V, ttl: timedelta | None = None) -> None:
        """Put value in cache."""
        with self.lock:
            now = datetime.now(UTC)

            # Calculate size
            size_bytes = self._calculate_size(value)

            entry = CacheEntry(
                key=str(key),
                value=value,
                created_at=now,
                last_accessed=now,
                ttl=ttl or self.default_ttl,
                size_bytes=size_bytes,
            )

            if key in self.cache:
                # Update existing entry
                self.cache[key] = entry
                self.cache.move_to_end(key)
            else:
                # Add new entry
                self.cache[key] = entry

                # Evict if necessary
                while len(self.cache) > self.max_size:
                    oldest_key = next(iter(self.cache))
                    del self.cache[oldest_key]
                    self.evictions += 1

    def delete(self, key: K) -> bool:
        """Delete entry from cache."""
        with self.lock:
            if key in self.cache:
                del self.cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries from cache."""
        with self.lock:
            self.cache.clear()

    def cleanup_expired(self) -> int:
        """Remove expired entries and return count."""
        with self.lock:
            expired_keys = [
                key for key, entry in self.cache.items() if entry.is_expired()
            ]
            for key in expired_keys:
                del self.cache[key]
            return len(expired_keys)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        with self.lock:
            total_requests = self.hits + self.misses
            hit_rate = self.hits / max(total_requests, 1)

            total_size = sum(entry.size_bytes for entry in self.cache.values())

            return {
                "size": len(self.cache),
                "max_size": self.max_size,
                "hits": self.hits,
                "misses": self.misses,
                "evictions": self.evictions,
                "hit_rate": hit_rate,
                "total_size_bytes": total_size,
                "avg_entry_size": total_size / max(len(self.cache), 1),
            }

    def _calculate_size(self, obj: Any) -> int:
        """Calculate approximate size of object in bytes."""
        try:
            return len(pickle.dumps(obj, protocol=pickle.HIGHEST_PROTOCOL))
        except Exception:
            return sys.getsizeof(obj)


class CacheOptimizer:
    """Multi-level caching with intelligent invalidation strategies."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__ + ".CacheOptimizer")

        # Multi-level caches
        self.l1_cache = LRUCache[str, Any](
            max_size=self.config.get("l1_cache_size", 500),
            default_ttl=timedelta(seconds=self.config.get("l1_ttl_seconds", 300)),
        )
        self.l2_cache = LRUCache[str, Any](
            max_size=self.config.get("l2_cache_size", 2000),
            default_ttl=timedelta(seconds=self.config.get("l2_ttl_seconds", 1800)),
        )
        self.l3_cache = LRUCache[str, Any](
            max_size=self.config.get("l3_cache_size", 10000),
            default_ttl=timedelta(seconds=self.config.get("l3_ttl_seconds", 7200)),
        )

        # Cache warming and invalidation
        self.invalidation_patterns: dict[str, set[str]] = defaultdict(set)
        self.warming_queue: Queue = Queue()
        self.cleanup_thread: threading.Thread | None = None
        self.warming_thread: threading.Thread | None = None
        self.shutdown_event = Event()

        # Performance tracking
        self.access_patterns: dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.hit_rates: deque = deque(maxlen=100)

        self._start_background_threads()

    def get(self, key: str, default: Any | None = None) -> Any | None:
        """Get value from multi-level cache."""
        # Track access pattern
        self.access_patterns[key].append(time.time())

        # Try L1 cache first
        value = self.l1_cache.get(key)
        if value is not None:
            return value

        # Try L2 cache
        value = self.l2_cache.get(key)
        if value is not None:
            # Promote to L1
            self.l1_cache.put(key, value)
            return value

        # Try L3 cache
        value = self.l3_cache.get(key)
        if value is not None:
            # Promote to L2 and L1
            self.l2_cache.put(key, value)
            self.l1_cache.put(key, value)
            return value

        return default

    def put(
        self,
        key: str,
        value: Any,
        level: int = 1,
        ttl: timedelta | None = None,
    ) -> None:
        """Put value in specified cache level."""
        if level <= 1:
            self.l1_cache.put(key, value, ttl)
        if level <= 2:
            self.l2_cache.put(key, value, ttl)
        if level <= 3:
            self.l3_cache.put(key, value, ttl)

    def invalidate(self, pattern: str) -> int:
        """Invalidate cache entries matching pattern."""
        invalidated = 0

        # Direct key invalidation
        if self.l1_cache.delete(pattern):
            invalidated += 1
        if self.l2_cache.delete(pattern):
            invalidated += 1
        if self.l3_cache.delete(pattern):
            invalidated += 1

        # Pattern-based invalidation
        patterns_to_invalidate = self.invalidation_patterns.get(pattern, set())
        for key_pattern in patterns_to_invalidate:
            for cache in [self.l1_cache, self.l2_cache, self.l3_cache]:
                with cache.lock:
                    keys_to_remove = [
                        key
                        for key in cache.cache.keys()
                        if str(key).find(key_pattern) != -1
                    ]
                    for key in keys_to_remove:
                        cache.delete(key)
                        invalidated += 1

        self.logger.debug(
            f"Invalidated {invalidated} cache entries for pattern: {pattern}",
        )
        return invalidated

    def register_invalidation_pattern(self, trigger: str, pattern: str) -> None:
        """Register pattern for automatic invalidation."""
        self.invalidation_patterns[trigger].add(pattern)

    def warm_cache(
        self,
        key: str,
        value_factory: Callable[[], Any],
        priority: int = 0,
    ) -> None:
        """Add cache warming task to queue."""
        self.warming_queue.put((priority, key, value_factory))

    def get_optimization_stats(self) -> dict[str, Any]:
        """Get comprehensive cache optimization statistics."""
        l1_stats = self.l1_cache.get_stats()
        l2_stats = self.l2_cache.get_stats()
        l3_stats = self.l3_cache.get_stats()

        overall_hit_rate = (
            l1_stats["hits"] + l2_stats["hits"] + l3_stats["hits"]
        ) / max(
            l1_stats["hits"]
            + l1_stats["misses"]
            + l2_stats["hits"]
            + l2_stats["misses"]
            + l3_stats["hits"]
            + l3_stats["misses"],
            1,
        )

        return {
            "l1_cache": l1_stats,
            "l2_cache": l2_stats,
            "l3_cache": l3_stats,
            "overall_hit_rate": overall_hit_rate,
            "invalidation_patterns": len(self.invalidation_patterns),
            "warming_queue_size": self.warming_queue.qsize(),
            "access_patterns_tracked": len(self.access_patterns),
        }

    def _start_background_threads(self) -> None:
        """Start background maintenance threads."""
        self.cleanup_thread = threading.Thread(
            target=self._cleanup_worker,
            name="CacheCleanup",
            daemon=True,
        )
        self.cleanup_thread.start()

        self.warming_thread = threading.Thread(
            target=self._warming_worker,
            name="CacheWarming",
            daemon=True,
        )
        self.warming_thread.start()

    def _cleanup_worker(self) -> None:
        """Background worker for cache cleanup."""
        while not self.shutdown_event.wait(60):  # Run every minute
            try:
                # Clean up expired entries
                expired_l1 = self.l1_cache.cleanup_expired()
                expired_l2 = self.l2_cache.cleanup_expired()
                expired_l3 = self.l3_cache.cleanup_expired()

                total_expired = expired_l1 + expired_l2 + expired_l3
                if total_expired > 0:
                    self.logger.debug(
                        f"Cleaned up {total_expired} expired cache entries",
                    )

                # Update hit rate tracking
                stats = self.get_optimization_stats()
                self.hit_rates.append(stats["overall_hit_rate"])

            except Exception as e:
                self.logger.error(f"Error in cache cleanup: {e}")

    def _warming_worker(self) -> None:
        """Background worker for cache warming."""
        while not self.shutdown_event.is_set():
            try:
                # Get warming task with timeout
                try:
                    _priority, key, value_factory = self.warming_queue.get(timeout=1.0)
                except Empty:
                    continue

                # Check if key already exists
                if self.get(key) is not None:
                    continue

                # Generate value and cache it
                try:
                    value = value_factory()
                    self.put(key, value, level=2)  # Put in L2 cache
                    self.logger.debug(f"Warmed cache for key: {key}")
                except Exception as e:
                    self.logger.warning(f"Failed to warm cache for key {key}: {e}")

            except Exception as e:
                self.logger.error(f"Error in cache warming: {e}")

    def shutdown(self) -> None:
        """Shutdown cache optimizer."""
        self.shutdown_event.set()
        if self.cleanup_thread and self.cleanup_thread.is_alive():
            self.cleanup_thread.join(timeout=5)
        if self.warming_thread and self.warming_thread.is_alive():
            self.warming_thread.join(timeout=5)


class MemoryOptimizer:
    """Memory optimization with object pooling and garbage collection tuning."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__ + ".MemoryOptimizer")

        # Object pools
        self.object_pools: dict[str, MemoryPool] = {}
        self.pool_lock = RLock()

        # Memory monitoring
        self.memory_thresholds = {
            "warning": self.config.get("memory_warning_mb", 1024),
            "critical": self.config.get("memory_critical_mb", 2048),
        }

        # GC tuning
        self.gc_config = {
            "auto_tune": self.config.get("gc_auto_tune", True),
            "target_frequency": self.config.get("gc_target_frequency", 10.0),
            "pressure_threshold": self.config.get("gc_pressure_threshold", 0.8),
        }

        # Memory tracking
        self.memory_samples: deque = deque(maxlen=1000)
        self.gc_stats: deque = deque(maxlen=100)
        self.allocation_tracker: dict[str, int] = defaultdict(int)

        # Background monitoring
        self.monitor_thread: threading.Thread | None = None
        self.shutdown_event = Event()

        self._configure_gc()
        self._start_monitoring()

    def create_pool(
        self,
        name: str,
        factory: Callable[[], Any],
        max_size: int = 100,
    ) -> MemoryPool:
        """Create object pool."""
        with self.pool_lock:
            if name in self.object_pools:
                self.logger.warning(f"Object pool {name} already exists")
                return self.object_pools[name]

            pool = MemoryPool(name=name, object_factory=factory, max_size=max_size)
            self.object_pools[name] = pool
            self.logger.info(f"Created object pool: {name} (max_size={max_size})")
            return pool

    def get_pool(self, name: str) -> MemoryPool | None:
        """Get object pool by name."""
        with self.pool_lock:
            return self.object_pools.get(name)

    def get_object(self, pool_name: str) -> Any | None:
        """Get object from pool."""
        pool = self.get_pool(pool_name)
        if pool:
            obj = pool.get_object()
            self.allocation_tracker[pool_name] += 1
            return obj
        return None

    def return_object(self, pool_name: str, obj: Any) -> None:
        """Return object to pool."""
        pool = self.get_pool(pool_name)
        if pool:
            pool.return_object(obj)

    def check_memory_pressure(self) -> tuple[float, str]:
        """Check current memory pressure."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()
            memory_mb = memory_info.rss / 1024 / 1024

            if memory_mb > self.memory_thresholds["critical"]:
                return memory_mb, "critical"
            if memory_mb > self.memory_thresholds["warning"]:
                return memory_mb, "warning"
            return memory_mb, "normal"
        except Exception:
            return 0.0, "unknown"

    def force_gc(self, generation: int | None = None) -> dict[str, Any]:
        """Force garbage collection."""
        start_time = time.time()

        if generation is not None:
            collected = gc.collect(generation)
        else:
            collected = gc.collect()

        gc_time = time.time() - start_time

        # Record GC stats
        gc_stats = {
            "timestamp": time.time(),
            "collected": collected,
            "duration": gc_time,
            "generation": generation,
        }
        self.gc_stats.append(gc_stats)

        self.logger.debug(f"Garbage collection: {collected} objects in {gc_time:.3f}s")
        return gc_stats

    def optimize_memory(self) -> dict[str, Any]:
        """Perform memory optimization."""
        optimization_results = {}

        # Check memory pressure
        memory_mb, pressure_level = self.check_memory_pressure()
        optimization_results["memory_pressure"] = {
            "memory_mb": memory_mb,
            "pressure_level": pressure_level,
        }

        # Force GC if under pressure
        if pressure_level in ["warning", "critical"]:
            gc_stats = self.force_gc()
            optimization_results["garbage_collection"] = gc_stats

        # Clean up object pools
        pool_stats = []
        with self.pool_lock:
            for pool in self.object_pools.values():
                stats = pool.get_stats()
                pool_stats.append(stats)

        optimization_results["object_pools"] = pool_stats

        return optimization_results

    def get_memory_stats(self) -> dict[str, Any]:
        """Get comprehensive memory statistics."""
        try:
            process = psutil.Process()
            memory_info = process.memory_info()

            pool_stats = {}
            with self.pool_lock:
                for name, pool in self.object_pools.items():
                    pool_stats[name] = pool.get_stats()

            gc_info = {
                "counts": gc.get_count(),
                "thresholds": gc.get_threshold(),
                "stats": gc.get_stats() if hasattr(gc, "get_stats") else None,
            }

            return {
                "process_memory": {
                    "rss_mb": memory_info.rss / 1024 / 1024,
                    "vms_mb": memory_info.vms / 1024 / 1024,
                    "percent": process.memory_percent(),
                },
                "gc_info": gc_info,
                "object_pools": pool_stats,
                "allocation_tracker": dict(self.allocation_tracker),
                "memory_samples": len(self.memory_samples),
                "gc_stats": len(self.gc_stats),
            }
        except Exception as e:
            self.logger.error(f"Error getting memory stats: {e}")
            return {"error": str(e)}

    def _configure_gc(self) -> None:
        """Configure garbage collection settings."""
        if not self.gc_config["auto_tune"]:
            return

        try:
            # Get current thresholds
            thresholds = gc.get_threshold()

            # Adjust thresholds based on memory pressure
            _memory_mb, pressure_level = self.check_memory_pressure()

            if pressure_level == "critical":
                # More aggressive GC
                new_thresholds = (
                    max(thresholds[0] // 2, 100),
                    max(thresholds[1] // 2, 10),
                    max(thresholds[2] // 2, 10),
                )
            elif pressure_level == "warning":
                # Slightly more aggressive GC
                new_thresholds = (
                    int(thresholds[0] * 0.8),
                    int(thresholds[1] * 0.8),
                    int(thresholds[2] * 0.8),
                )
            else:
                # Default thresholds
                new_thresholds = (700, 10, 10)

            gc.set_threshold(*new_thresholds)
            self.logger.debug(f"Updated GC thresholds: {new_thresholds}")

        except Exception as e:
            self.logger.error(f"Failed to configure GC: {e}")

    def _start_monitoring(self) -> None:
        """Start background memory monitoring."""
        self.monitor_thread = threading.Thread(
            target=self._monitor_worker,
            name="MemoryMonitor",
            daemon=True,
        )
        self.monitor_thread.start()

    def _monitor_worker(self) -> None:
        """Background worker for memory monitoring."""
        while not self.shutdown_event.wait(10):  # Sample every 10 seconds
            try:
                # Sample memory usage
                memory_mb, pressure_level = self.check_memory_pressure()
                self.memory_samples.append(
                    {
                        "timestamp": time.time(),
                        "memory_mb": memory_mb,
                        "pressure_level": pressure_level,
                    },
                )

                # Auto-tune GC if enabled
                if self.gc_config["auto_tune"]:
                    self._configure_gc()

                # Trigger optimization if under pressure
                if pressure_level == "critical":
                    self.optimize_memory()

            except Exception as e:
                self.logger.error(f"Error in memory monitoring: {e}")

    def shutdown(self) -> None:
        """Shutdown memory optimizer."""
        self.shutdown_event.set()
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)


class ConcurrencyOptimizer:
    """Concurrency optimization with dynamic thread pools and async operations."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__ + ".ConcurrencyOptimizer")

        # Thread pool configuration
        self.min_workers = self.config.get("min_workers", 2)
        self.max_workers = self.config.get(
            "max_workers",
            min(32, (os.cpu_count() or 1) + 4),
        )
        self.worker_timeout = self.config.get("worker_timeout", 60)

        # Thread pools
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.max_workers,
            thread_name_prefix="OptimizedWorker",
        )
        self.io_executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=min(8, self.max_workers),
            thread_name_prefix="IOWorker",
        )

        # Async event loop for I/O operations
        self.loop: asyncio.AbstractEventLoop | None = None
        self.loop_thread: threading.Thread | None = None

        # Task tracking
        self.active_tasks: set[concurrent.futures.Future] = set()
        self.completed_tasks: deque = deque(maxlen=1000)
        self.task_stats: dict[str, deque] = defaultdict(lambda: deque(maxlen=100))

        # Lock optimization
        self.lock_registry: dict[str, threading.Lock] = {}
        self.lock_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {"acquisitions": 0, "contentions": 0, "wait_time": 0.0},
        )

        # Performance monitoring
        self.utilization_samples: deque = deque(maxlen=1000)
        self.shutdown_event = Event()

        self._start_event_loop()
        self._start_monitoring()

    def submit_task(
        self,
        func: Callable,
        *args,
        priority: int = 0,
        **kwargs,
    ) -> concurrent.futures.Future:
        """Submit task to thread pool with priority."""
        future = self.executor.submit(func, *args, **kwargs)
        self.active_tasks.add(future)

        # Track task
        def task_done(f):
            self.active_tasks.discard(f)
            self.completed_tasks.append(
                {
                    "timestamp": time.time(),
                    "success": not f.exception(),
                    "duration": getattr(f, "_duration", 0),
                },
            )

        future.add_done_callback(task_done)
        return future

    def submit_io_task(
        self,
        func: Callable,
        *args,
        **kwargs,
    ) -> concurrent.futures.Future:
        """Submit I/O bound task to dedicated I/O thread pool."""
        future = self.io_executor.submit(func, *args, **kwargs)
        return future

    async def run_async_task(self, coro) -> Any:
        """Run async task in managed event loop."""
        if self.loop and not self.loop.is_closed():
            return await coro
        raise RuntimeError("Event loop not available")

    def get_optimized_lock(self, name: str) -> threading.Lock:
        """Get or create optimized lock."""
        if name not in self.lock_registry:
            self.lock_registry[name] = threading.Lock()
        return self.lock_registry[name]

    @contextlib.contextmanager
    def timed_lock(self, name: str):
        """Context manager for timed lock acquisition."""
        lock = self.get_optimized_lock(name)
        start_time = time.time()

        acquired = lock.acquire(blocking=False)
        if not acquired:
            # Track contention
            self.lock_stats[name]["contentions"] += 1
            lock.acquire()  # Block until acquired

        try:
            wait_time = time.time() - start_time
            self.lock_stats[name]["acquisitions"] += 1
            self.lock_stats[name]["wait_time"] += wait_time
            yield lock
        finally:
            lock.release()

    def optimize_thread_pool(self) -> dict[str, Any]:
        """Optimize thread pool size based on current load."""
        # Calculate current utilization
        active_count = len(self.active_tasks)
        max_workers = self.executor._max_workers
        utilization = active_count / max_workers if max_workers > 0 else 0

        self.utilization_samples.append(
            {
                "timestamp": time.time(),
                "utilization": utilization,
                "active_tasks": active_count,
                "max_workers": max_workers,
            },
        )

        # Adjust pool size if needed
        optimization_result = {
            "current_utilization": utilization,
            "active_tasks": active_count,
            "max_workers": max_workers,
            "action": "none",
        }

        # Simple auto-scaling logic
        if utilization > 0.8 and max_workers < self.max_workers:
            # High utilization, consider scaling up
            new_max = min(max_workers + 2, self.max_workers)
            optimization_result["action"] = f"scale_up_to_{new_max}"
        elif utilization < 0.2 and max_workers > self.min_workers:
            # Low utilization, consider scaling down
            new_max = max(max_workers - 1, self.min_workers)
            optimization_result["action"] = f"scale_down_to_{new_max}"

        return optimization_result

    def get_concurrency_stats(self) -> dict[str, Any]:
        """Get comprehensive concurrency statistics."""
        # Task statistics
        recent_tasks = list(self.completed_tasks)[-100:] if self.completed_tasks else []
        success_rate = sum(1 for t in recent_tasks if t["success"]) / max(
            len(recent_tasks),
            1,
        )
        avg_duration = sum(t["duration"] for t in recent_tasks) / max(
            len(recent_tasks),
            1,
        )

        # Thread pool stats
        executor_stats = {
            "max_workers": self.executor._max_workers,
            "active_tasks": len(self.active_tasks),
            "completed_tasks": len(self.completed_tasks),
        }

        # Lock statistics
        lock_stats = {}
        for name, stats in self.lock_stats.items():
            if stats["acquisitions"] > 0:
                lock_stats[name] = {
                    **stats,
                    "avg_wait_time": stats["wait_time"] / stats["acquisitions"],
                    "contention_rate": stats["contentions"] / stats["acquisitions"],
                }

        # Utilization statistics
        recent_utilization = [
            s["utilization"] for s in list(self.utilization_samples)[-100:]
        ]
        avg_utilization = sum(recent_utilization) / max(len(recent_utilization), 1)

        return {
            "executor": executor_stats,
            "task_performance": {
                "success_rate": success_rate,
                "avg_duration": avg_duration,
                "recent_task_count": len(recent_tasks),
            },
            "locks": lock_stats,
            "utilization": {
                "current": recent_utilization[-1] if recent_utilization else 0,
                "average": avg_utilization,
                "samples": len(self.utilization_samples),
            },
            "event_loop": {
                "running": (
                    self.loop is not None and not self.loop.is_closed()
                    if self.loop
                    else False
                ),
            },
        }

    def _start_event_loop(self) -> None:
        """Start async event loop in separate thread."""

        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            try:
                self.loop.run_forever()
            except Exception as e:
                self.logger.error(f"Event loop error: {e}")
            finally:
                self.loop.close()

        self.loop_thread = threading.Thread(
            target=run_loop,
            name="AsyncEventLoop",
            daemon=True,
        )
        self.loop_thread.start()

        # Wait for loop to start
        time.sleep(0.1)

    def _start_monitoring(self) -> None:
        """Start background monitoring thread."""
        monitor_thread = threading.Thread(
            target=self._monitor_worker,
            name="ConcurrencyMonitor",
            daemon=True,
        )
        monitor_thread.start()

    def _monitor_worker(self) -> None:
        """Background worker for concurrency monitoring."""
        while not self.shutdown_event.wait(30):  # Monitor every 30 seconds
            try:
                # Optimize thread pool
                self.optimize_thread_pool()

                # Clean up completed futures
                completed_futures = [f for f in list(self.active_tasks) if f.done()]
                for future in completed_futures:
                    self.active_tasks.discard(future)

            except Exception as e:
                self.logger.error(f"Error in concurrency monitoring: {e}")

    def shutdown(self) -> None:
        """Shutdown concurrency optimizer."""
        self.shutdown_event.set()

        # Shutdown executors
        self.executor.shutdown(wait=True)
        self.io_executor.shutdown(wait=True)

        # Stop event loop
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.loop.stop)

        if self.loop_thread and self.loop_thread.is_alive():
            self.loop_thread.join(timeout=5)


class IOOptimizer:
    """I/O optimization with batch operations and connection pooling.

    Supports context manager protocol for safe resource management.

    Example:
        with IOOptimizer(config) as optimizer:
            optimizer.batch_read(...)

    Can also be used directly:
        optimizer = IOOptimizer(config)
        optimizer.batch_read(...)
        optimizer.close()  # or optimizer.shutdown()
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__ + ".IOOptimizer")

        # Batch configuration
        self.batch_size = self.config.get("batch_size", 100)
        self.batch_timeout = self.config.get("batch_timeout", 1.0)

        # Connection pooling
        self.max_connections = self.config.get("max_connections", 10)
        self.connection_timeout = self.config.get("connection_timeout", 30)

        # Batch queues
        self.read_queue: Queue = Queue()
        self.write_queue: Queue = Queue()
        self.batch_processors: dict[str, threading.Thread] = {}

        # Connection pools
        self.db_pool: Queue = Queue()
        self._db_conn: sqlite3.Connection | None = None  # Single persistent connection
        self.file_handles: dict[str, Any] = {}
        self.handle_lock = RLock()

        # I/O statistics
        self.io_stats = {
            "reads": {"count": 0, "bytes": 0, "time": 0.0},
            "writes": {"count": 0, "bytes": 0, "time": 0.0},
            "batches": {"count": 0, "avg_size": 0.0},
        }
        self.io_lock = Lock()

        # Background processing
        self.shutdown_event = Event()
        self._start_batch_processors()

    def __enter__(self) -> IOOptimizer:
        """Enter context manager."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context manager, close all resources."""
        self.close()

    def _get_persistent_connection(self) -> sqlite3.Connection:
        """Get or create persistent in-memory database connection.

        Returns:
            sqlite3.Connection: Thread-safe connection.
        """
        if self._db_conn is None:
            self._db_conn = sqlite3.connect(":memory:", check_same_thread=False)
        return self._db_conn

    def close(self) -> None:
        """Close all resources. Alias for shutdown()."""
        self.shutdown()

    def __del__(self):
        """Destructor to ensure connection cleanup."""
        try:
            if self._db_conn:
                self._db_conn.close()
                self._db_conn = None
        except Exception:
            pass  # Ignore errors during destructor

    def batch_read(
        self,
        sources: list[str],
        callback: Callable[[list[Any]], None],
    ) -> None:
        """Queue batch read operation."""
        self.read_queue.put(
            {"sources": sources, "callback": callback, "timestamp": time.time()},
        )

    def batch_write(
        self,
        operations: list[tuple[str, Any]],
        callback: Callable | None = None,
    ) -> None:
        """Queue batch write operation."""
        self.write_queue.put(
            {"operations": operations, "callback": callback, "timestamp": time.time()},
        )

    def get_file_handle(self, path: str, mode: str = "r") -> Any:
        """Get cached file handle."""
        with self.handle_lock:
            key = f"{path}:{mode}"
            if key not in self.file_handles:
                try:
                    self.file_handles[key] = open(path, mode)
                except Exception as e:
                    self.logger.error(f"Failed to open file {path}: {e}")
                    raise
            return self.file_handles[key]

    def close_file_handle(self, path: str, mode: str = "r") -> None:
        """Close and remove file handle from cache."""
        with self.handle_lock:
            key = f"{path}:{mode}"
            if key in self.file_handles:
                try:
                    self.file_handles[key].close()
                except Exception as e:
                    self.logger.warning(f"Error closing file {path}: {e}")
                finally:
                    del self.file_handles[key]

    def get_db_connection(self) -> sqlite3.Connection | None:
        """Get database connection from pool."""
        try:
            return self.db_pool.get_nowait()
        except Empty:
            # Create new connection if pool is empty
            try:
                conn = sqlite3.connect(":memory:", check_same_thread=False)
                return conn
            except Exception as e:
                self.logger.error(f"Failed to create database connection: {e}")
                return None

    def return_db_connection(self, conn: sqlite3.Connection) -> None:
        """Return database connection to pool."""
        if self.db_pool.qsize() < self.max_connections:
            self.db_pool.put(conn)
        else:
            try:
                conn.close()
            except Exception as e:
                self.logger.warning(f"Error closing database connection: {e}")

    def optimize_io(self) -> dict[str, Any]:
        """Perform I/O optimization."""
        optimization_results = {}

        # Flush pending batches
        read_count = self.read_queue.qsize()
        write_count = self.write_queue.qsize()

        optimization_results["queue_status"] = {
            "pending_reads": read_count,
            "pending_writes": write_count,
        }

        # Close unused file handles
        with self.handle_lock:
            closed_handles = 0
            handles_to_close = []

            for key, handle in self.file_handles.items():
                try:
                    # Check if handle is still valid
                    if hasattr(handle, "closed") and handle.closed:
                        handles_to_close.append(key)
                except Exception:
                    handles_to_close.append(key)

            for key in handles_to_close:
                try:
                    if key in self.file_handles:
                        self.file_handles[key].close()
                        del self.file_handles[key]
                        closed_handles += 1
                except Exception as e:
                    self.logger.warning(f"Error cleaning up file handle {key}: {e}")

            optimization_results["file_handles"] = {
                "active": len(self.file_handles),
                "closed": closed_handles,
            }

        return optimization_results

    def get_io_stats(self) -> dict[str, Any]:
        """Get comprehensive I/O statistics."""
        with self.io_lock:
            stats = dict(self.io_stats)

        # Add queue statistics
        stats["queues"] = {
            "read_queue_size": self.read_queue.qsize(),
            "write_queue_size": self.write_queue.qsize(),
        }

        # Add connection pool statistics
        stats["connections"] = {
            "db_pool_size": self.db_pool.qsize(),
            "max_connections": self.max_connections,
        }

        # Add file handle statistics
        with self.handle_lock:
            stats["file_handles"] = {
                "active_handles": len(self.file_handles),
                "handle_keys": list(self.file_handles.keys()),
            }

        return stats

    def _start_batch_processors(self) -> None:
        """Start batch processing threads."""
        self.batch_processors["read"] = threading.Thread(
            target=self._process_read_batches,
            name="BatchReadProcessor",
            daemon=True,
        )
        self.batch_processors["read"].start()

        self.batch_processors["write"] = threading.Thread(
            target=self._process_write_batches,
            name="BatchWriteProcessor",
            daemon=True,
        )
        self.batch_processors["write"].start()

    def _process_read_batches(self) -> None:
        """Process read operations in batches."""
        batch = []
        last_batch_time = time.time()

        while not self.shutdown_event.is_set():
            try:
                # Get read operation with timeout
                try:
                    operation = self.read_queue.get(timeout=0.1)
                    batch.append(operation)
                except Empty:
                    pass

                # Process batch if full or timeout reached
                current_time = time.time()
                should_process = len(batch) >= self.batch_size or (
                    batch and current_time - last_batch_time >= self.batch_timeout
                )

                if should_process and batch:
                    self._execute_read_batch(batch)
                    batch = []
                    last_batch_time = current_time

            except Exception as e:
                self.logger.error(f"Error in read batch processing: {e}")

    def _process_write_batches(self) -> None:
        """Process write operations in batches."""
        batch = []
        last_batch_time = time.time()

        while not self.shutdown_event.is_set():
            try:
                # Get write operation with timeout
                try:
                    operation = self.write_queue.get(timeout=0.1)
                    batch.append(operation)
                except Empty:
                    pass

                # Process batch if full or timeout reached
                current_time = time.time()
                should_process = len(batch) >= self.batch_size or (
                    batch and current_time - last_batch_time >= self.batch_timeout
                )

                if should_process and batch:
                    self._execute_write_batch(batch)
                    batch = []
                    last_batch_time = current_time

            except Exception as e:
                self.logger.error(f"Error in write batch processing: {e}")

    def _execute_read_batch(self, batch: list[dict[str, Any]]) -> None:
        """Execute batch of read operations."""
        start_time = time.time()

        try:
            for operation in batch:
                sources = operation["sources"]
                callback = operation["callback"]

                # Read all sources
                results = []
                total_bytes = 0

                for source in sources:
                    try:
                        if isinstance(source, str) and Path(source).exists():
                            # File read
                            with open(source) as f:
                                data = f.read()
                                results.append(data)
                                total_bytes += len(data.encode("utf-8"))
                        else:
                            results.append(None)
                    except Exception as e:
                        self.logger.warning(f"Failed to read source {source}: {e}")
                        results.append(None)

                # Execute callback
                try:
                    callback(results)
                except Exception as e:
                    self.logger.error(f"Read batch callback failed: {e}")

                # Update statistics
                with self.io_lock:
                    self.io_stats["reads"]["count"] += len(sources)
                    self.io_stats["reads"]["bytes"] += total_bytes

            # Update batch statistics
            batch_time = time.time() - start_time
            with self.io_lock:
                self.io_stats["reads"]["time"] += batch_time
                self.io_stats["batches"]["count"] += 1

        except Exception as e:
            self.logger.error(f"Error executing read batch: {e}")

    def _execute_write_batch(self, batch: list[dict[str, Any]]) -> None:
        """Execute batch of write operations."""
        start_time = time.time()

        try:
            for operation in batch:
                operations = operation["operations"]
                callback = operation.get("callback")

                total_bytes = 0

                for target, data in operations:
                    try:
                        if isinstance(target, str):
                            # File write
                            Path(target).parent.mkdir(parents=True, exist_ok=True)
                            with open(target, "w") as f:
                                f.write(str(data))
                                total_bytes += len(str(data).encode("utf-8"))
                    except Exception as e:
                        self.logger.warning(f"Failed to write to {target}: {e}")

                # Execute callback
                if callback:
                    try:
                        callback()
                    except Exception as e:
                        self.logger.error(f"Write batch callback failed: {e}")

                # Update statistics
                with self.io_lock:
                    self.io_stats["writes"]["count"] += len(operations)
                    self.io_stats["writes"]["bytes"] += total_bytes

            # Update batch statistics
            batch_time = time.time() - start_time
            with self.io_lock:
                self.io_stats["writes"]["time"] += batch_time

        except Exception as e:
            self.logger.error(f"Error executing write batch: {e}")

    def shutdown(self) -> None:
        """Shutdown I/O optimizer."""
        self.shutdown_event.set()

        # Wait for batch processors to finish
        for name, thread in self.batch_processors.items():
            if thread.is_alive():
                thread.join(timeout=5)

        # Close all file handles
        with self.handle_lock:
            for handle in self.file_handles.values():
                try:
                    handle.close()
                except Exception as e:
                    self.logger.warning(f"Error closing file handle: {e}")
            self.file_handles.clear()

        # Close persistent database connection
        if self._db_conn:
            try:
                self._db_conn.close()
            except Exception as e:
                self.logger.warning(f"Error closing persistent db connection: {e}")
            self._db_conn = None

        # Close pooled database connections
        while not self.db_pool.empty():
            try:
                conn = self.db_pool.get_nowait()
                conn.close()
            except Exception as e:
                self.logger.warning(f"Error closing database connection: {e}")


class QueryOptimizer:
    """Query optimization with SQL optimization and index management."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__ + ".QueryOptimizer")

        # Query caching
        self.query_cache = LRUCache[str, Any](
            max_size=self.config.get("query_cache_size", 1000),
            default_ttl=timedelta(seconds=self.config.get("query_cache_ttl", 300)),
        )

        # Query statistics
        self.query_stats: dict[str, dict[str, Any]] = defaultdict(
            lambda: {
                "count": 0,
                "total_time": 0.0,
                "avg_time": 0.0,
                "min_time": float("inf"),
                "max_time": 0.0,
            },
        )

        # Index recommendations
        self.index_recommendations: set[str] = set()
        self.slow_queries: deque = deque(maxlen=100)

        # Query patterns
        self.query_patterns: dict[str, int] = defaultdict(int)
        self.stats_lock = Lock()

    def optimize_query(self, query: str, params: tuple | None = None) -> str:
        """Optimize SQL query."""
        # Normalize query for pattern analysis
        normalized = self._normalize_query(query)

        with self.stats_lock:
            self.query_patterns[normalized] += 1

        # Basic query optimizations
        optimized_query = query

        # Remove unnecessary whitespace
        optimized_query = " ".join(optimized_query.split())

        # Suggest indexes for frequently used queries
        if self.query_patterns[normalized] > 10:
            self._analyze_for_indexes(optimized_query)

        return optimized_query

    def execute_cached_query(
        self,
        query: str,
        params: tuple | None = None,
        executor: Callable | None = None,
    ) -> Any:
        """Execute query with caching."""
        # Create cache key
        cache_key = self._get_cache_key(query, params)

        # Check cache first
        cached_result = self.query_cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        # Execute query
        start_time = time.time()
        try:
            if executor:
                result = executor(query, params)
            else:
                # Default execution (placeholder)
                result = None

            execution_time = time.time() - start_time

            # Cache result
            self.query_cache.put(cache_key, result)

            # Update statistics
            self._update_query_stats(query, execution_time)

            return result

        except Exception:
            execution_time = time.time() - start_time
            self._update_query_stats(query, execution_time, error=True)
            raise

    def get_index_recommendations(self) -> list[str]:
        """Get index recommendations based on query patterns."""
        return list(self.index_recommendations)

    def get_slow_queries(self, threshold: float = 1.0) -> list[dict[str, Any]]:
        """Get queries that exceed the time threshold."""
        return [
            query
            for query in list(self.slow_queries)
            if query.get("execution_time", 0) > threshold
        ]

    def get_query_stats(self) -> dict[str, Any]:
        """Get comprehensive query statistics."""
        with self.stats_lock:
            stats = dict(self.query_stats)

        cache_stats = self.query_cache.get_stats()

        return {
            "query_statistics": stats,
            "cache_statistics": cache_stats,
            "query_patterns": dict(self.query_patterns),
            "index_recommendations": list(self.index_recommendations),
            "slow_queries_count": len(self.slow_queries),
        }

    def _normalize_query(self, query: str) -> str:
        """Normalize query for pattern analysis."""
        # Convert to lowercase
        normalized = query.lower().strip()

        # Replace parameters with placeholders
        # This is a simple implementation
        import re

        normalized = re.sub(r"'[^']*'", "'?'", normalized)
        normalized = re.sub(r"\b\d+\b", "?", normalized)

        return normalized

    def _get_cache_key(self, query: str, params: tuple | None) -> str:
        """Generate cache key for query and parameters."""
        key_data = f"{query}:{params}"
        return hashlib.md5(key_data.encode()).hexdigest()

    def _update_query_stats(
        self,
        query: str,
        execution_time: float,
        error: bool = False,
    ) -> None:
        """Update query execution statistics."""
        normalized = self._normalize_query(query)

        with self.stats_lock:
            stats = self.query_stats[normalized]
            stats["count"] += 1

            if not error:
                stats["total_time"] += execution_time
                stats["avg_time"] = stats["total_time"] / stats["count"]
                stats["min_time"] = min(stats["min_time"], execution_time)
                stats["max_time"] = max(stats["max_time"], execution_time)

                # Track slow queries
                if execution_time > 1.0:  # Threshold for slow queries
                    self.slow_queries.append(
                        {
                            "query": query,
                            "execution_time": execution_time,
                            "timestamp": time.time(),
                        },
                    )

    def _analyze_for_indexes(self, query: str) -> None:
        """Analyze query for potential index recommendations."""
        query_lower = query.lower()

        # Simple heuristics for index recommendations
        if "where" in query_lower:
            # Look for WHERE clauses that might benefit from indexes
            import re

            where_matches = re.findall(r"where\s+(\w+)\s*[=<>]", query_lower)
            for column in where_matches:
                index_suggestion = f"CREATE INDEX idx_{column} ON table_name ({column})"
                self.index_recommendations.add(index_suggestion)

        if "order by" in query_lower:
            # Look for ORDER BY clauses
            order_matches = re.findall(r"order\s+by\s+(\w+)", query_lower)
            for column in order_matches:
                index_suggestion = (
                    f"CREATE INDEX idx_{column}_sort ON table_name ({column})"
                )
                self.index_recommendations.add(index_suggestion)

        if "join" in query_lower:
            # Look for JOIN operations
            join_matches = re.findall(
                r"join\s+\w+\s+on\s+\w+\.(\w+)\s*=\s*\w+\.(\w+)",
                query_lower,
            )
            for col1, col2 in join_matches:
                self.index_recommendations.add(
                    f"CREATE INDEX idx_{col1}_join ON table1 ({col1})",
                )
                self.index_recommendations.add(
                    f"CREATE INDEX idx_{col2}_join ON table2 ({col2})",
                )


class PerformanceMonitor:
    """Real-time performance monitoring and analysis."""

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self.logger = logging.getLogger(__name__ + ".PerformanceMonitor")

        # Monitoring configuration
        self.sample_interval = self.config.get("sample_interval", 5.0)
        self.history_size = self.config.get("history_size", 1000)

        # Metrics storage
        self.metrics: dict[PerformanceMetric, deque] = {
            metric: deque(maxlen=self.history_size) for metric in PerformanceMetric
        }

        # Alert system
        self.alert_thresholds = {
            PerformanceMetric.CPU_USAGE: 80.0,
            PerformanceMetric.MEMORY_USAGE: 85.0,
            PerformanceMetric.CACHE_HIT_RATE: 70.0,  # Minimum threshold
            PerformanceMetric.RESPONSE_TIME: 2.0,
            PerformanceMetric.ERROR_RATE: 5.0,
        }
        self.active_alerts: dict[PerformanceMetric, PerformanceAlert] = {}
        self.alert_callbacks: list[Callable[[PerformanceAlert], None]] = []

        # Background monitoring
        self.monitor_thread: threading.Thread | None = None
        self.shutdown_event = Event()
        self.metrics_lock = Lock()

        self._start_monitoring()

    def record_metric(self, metric: PerformanceMetric, value: float) -> None:
        """Record a performance metric."""
        with self.metrics_lock:
            self.metrics[metric].append({"timestamp": time.time(), "value": value})

        # Check for alerts
        self._check_alert_threshold(metric, value)

    def get_metric_history(
        self,
        metric: PerformanceMetric,
        duration: float | None = None,
    ) -> list[dict[str, Any]]:
        """Get metric history for specified duration."""
        with self.metrics_lock:
            data = list(self.metrics[metric])

        if duration is None:
            return data

        cutoff_time = time.time() - duration
        return [point for point in data if point["timestamp"] >= cutoff_time]

    def get_metric_stats(
        self,
        metric: PerformanceMetric,
        duration: float | None = None,
    ) -> dict[str, Any]:
        """Get statistical summary of metric."""
        history = self.get_metric_history(metric, duration)

        if not history:
            return {"count": 0, "min": 0, "max": 0, "avg": 0, "std": 0}

        values = [point["value"] for point in history]

        avg = sum(values) / len(values)
        variance = sum((x - avg) ** 2 for x in values) / len(values)
        std = variance**0.5

        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": avg,
            "std": std,
            "latest": values[-1] if values else 0,
        }

    def detect_bottlenecks(self) -> list[dict[str, Any]]:
        """Detect performance bottlenecks."""
        bottlenecks = []

        # Analyze each metric for bottlenecks
        for metric in PerformanceMetric:
            stats = self.get_metric_stats(metric, duration=300)  # Last 5 minutes

            if stats["count"] < 5:  # Need enough data points
                continue

            # Define bottleneck conditions
            is_bottleneck = False
            severity = "info"

            if metric == PerformanceMetric.CPU_USAGE and stats["avg"] > 70:
                is_bottleneck = True
                severity = "warning" if stats["avg"] < 90 else "critical"
            elif metric == PerformanceMetric.MEMORY_USAGE and stats["avg"] > 80:
                is_bottleneck = True
                severity = "warning" if stats["avg"] < 95 else "critical"
            elif metric == PerformanceMetric.RESPONSE_TIME and stats["avg"] > 1.0:
                is_bottleneck = True
                severity = "warning" if stats["avg"] < 3.0 else "critical"
            elif metric == PerformanceMetric.ERROR_RATE and stats["avg"] > 1.0:
                is_bottleneck = True
                severity = "warning" if stats["avg"] < 5.0 else "critical"
            elif metric == PerformanceMetric.CACHE_HIT_RATE and stats["avg"] < 60:
                is_bottleneck = True
                severity = "warning"

            if is_bottleneck:
                bottlenecks.append(
                    {
                        "metric": metric.value,
                        "severity": severity,
                        "current_value": stats["latest"],
                        "average_value": stats["avg"],
                        "recommendation": self._get_bottleneck_recommendation(
                            metric,
                            stats,
                        ),
                    },
                )

        return bottlenecks

    def add_alert_callback(self, callback: Callable[[PerformanceAlert], None]) -> None:
        """Add callback for alert notifications."""
        self.alert_callbacks.append(callback)

    def set_alert_threshold(self, metric: PerformanceMetric, threshold: float) -> None:
        """Set alert threshold for metric."""
        self.alert_thresholds[metric] = threshold

    def get_system_health_score(self) -> float:
        """Calculate overall system health score (0-100)."""
        scores = []

        for metric in PerformanceMetric:
            stats = self.get_metric_stats(metric, duration=300)
            if stats["count"] == 0:
                continue

            # Calculate metric score based on current value
            score = self._calculate_metric_score(metric, stats["latest"])
            scores.append(score)

        return sum(scores) / len(scores) if scores else 50.0

    def _start_monitoring(self) -> None:
        """Start background monitoring thread."""
        self.monitor_thread = threading.Thread(
            target=self._monitor_worker,
            name="PerformanceMonitor",
            daemon=True,
        )
        self.monitor_thread.start()

    def _monitor_worker(self) -> None:
        """Background worker for performance monitoring."""
        while not self.shutdown_event.wait(self.sample_interval):
            try:
                self._collect_system_metrics()
            except Exception as e:
                self.logger.error(f"Error collecting system metrics: {e}")

    def _collect_system_metrics(self) -> None:
        """Collect system performance metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            self.record_metric(PerformanceMetric.CPU_USAGE, cpu_percent)

            # Memory usage
            memory = psutil.virtual_memory()
            self.record_metric(PerformanceMetric.MEMORY_USAGE, memory.percent)

            # Process memory
            process = psutil.Process()
            process_memory = process.memory_percent()
            self.record_metric(PerformanceMetric.MEMORY_USAGE, process_memory)

        except Exception as e:
            self.logger.warning(f"Failed to collect system metrics: {e}")

    def _check_alert_threshold(self, metric: PerformanceMetric, value: float) -> None:
        """Check if metric value exceeds alert threshold."""
        threshold = self.alert_thresholds.get(metric)
        if threshold is None:
            return

        # Check threshold based on metric type
        exceeds_threshold = False
        if metric == PerformanceMetric.CACHE_HIT_RATE:
            # Cache hit rate should be above threshold
            exceeds_threshold = value < threshold
        else:
            # Other metrics should be below threshold
            exceeds_threshold = value > threshold

        if exceeds_threshold:
            # Create or update alert
            severity = self._determine_alert_severity(metric, value, threshold)
            alert = PerformanceAlert(
                metric=metric,
                severity=severity,
                threshold=threshold,
                current_value=value,
                timestamp=datetime.now(UTC),
                message=f"{metric.value} threshold exceeded: {value:.2f} (threshold: {threshold:.2f})",
                recommendations=self._get_alert_recommendations(metric, value),
            )

            self.active_alerts[metric] = alert

            # Notify callbacks
            for callback in self.alert_callbacks:
                try:
                    callback(alert)
                except Exception as e:
                    self.logger.error(f"Alert callback failed: {e}")
        elif metric in self.active_alerts:
            del self.active_alerts[metric]

    def _determine_alert_severity(
        self,
        metric: PerformanceMetric,
        value: float,
        threshold: float,
    ) -> AlertSeverity:
        """Determine alert severity based on how much threshold is exceeded."""
        if metric == PerformanceMetric.CACHE_HIT_RATE:
            ratio = threshold / max(value, 1)
        else:
            ratio = value / threshold

        if ratio > 2.0:
            return AlertSeverity.CRITICAL
        if ratio > 1.5:
            return AlertSeverity.WARNING
        return AlertSeverity.INFO

    def _get_alert_recommendations(
        self,
        metric: PerformanceMetric,
        value: float,
    ) -> list[str]:
        """Get recommendations for addressing alert."""
        recommendations = []

        if metric == PerformanceMetric.CPU_USAGE:
            recommendations.extend(
                [
                    "Consider reducing concurrent operations",
                    "Check for CPU-intensive tasks",
                    "Review thread pool sizing",
                ],
            )
        elif metric == PerformanceMetric.MEMORY_USAGE:
            recommendations.extend(
                [
                    "Force garbage collection",
                    "Review memory leaks",
                    "Optimize object pooling",
                ],
            )
        elif metric == PerformanceMetric.CACHE_HIT_RATE:
            recommendations.extend(
                [
                    "Increase cache size",
                    "Review cache TTL settings",
                    "Optimize cache warming strategy",
                ],
            )
        elif metric == PerformanceMetric.RESPONSE_TIME:
            recommendations.extend(
                [
                    "Check for I/O bottlenecks",
                    "Review database query performance",
                    "Consider caching frequently accessed data",
                ],
            )

        return recommendations

    def _calculate_metric_score(self, metric: PerformanceMetric, value: float) -> float:
        """Calculate health score for a metric (0-100)."""
        if (
            metric == PerformanceMetric.CPU_USAGE
            or metric == PerformanceMetric.MEMORY_USAGE
        ):
            return max(0, 100 - value)  # Lower is better
        if metric == PerformanceMetric.CACHE_HIT_RATE:
            return min(100, value)  # Higher is better
        if metric == PerformanceMetric.RESPONSE_TIME:
            return max(0, 100 - (value * 20))  # Lower is better, scale by 20
        if metric == PerformanceMetric.ERROR_RATE:
            return max(0, 100 - (value * 10))  # Lower is better, scale by 10
        return 50.0  # Default neutral score

    def _get_bottleneck_recommendation(
        self,
        metric: PerformanceMetric,
        stats: dict[str, Any],
    ) -> str:
        """Get recommendation for addressing bottleneck."""
        if metric == PerformanceMetric.CPU_USAGE:
            return "Reduce concurrent operations or optimize CPU-intensive tasks"
        if metric == PerformanceMetric.MEMORY_USAGE:
            return "Optimize memory usage with garbage collection and object pooling"
        if metric == PerformanceMetric.CACHE_HIT_RATE:
            return "Increase cache size or improve cache warming strategy"
        if metric == PerformanceMetric.RESPONSE_TIME:
            return "Optimize I/O operations and database queries"
        if metric == PerformanceMetric.ERROR_RATE:
            return "Investigate and fix sources of errors"
        return "Monitor metric trends and investigate anomalies"

    def shutdown(self) -> None:
        """Shutdown performance monitor."""
        self.shutdown_event.set()
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)


class PerformanceOptimizer:
    """
    Main performance optimization orchestrator that coordinates all optimization strategies.

    This class provides a unified interface for performance optimization across the
    treesitter-chunker system, integrating with SystemIntegrator for cohesive operation.
    """

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        system_integrator: Any | None = None,
    ):
        self.config = config or {}
        self.logger = logging.getLogger(__name__ + ".PerformanceOptimizer")

        # System integration
        self.system_integrator = system_integrator
        if self.system_integrator is None and CORE_INTEGRATION_AVAILABLE:
            try:
                self.system_integrator = get_system_integrator()
            except Exception as e:
                self.logger.warning(f"Could not get system integrator: {e}")

        # Optimization level
        self.optimization_level = OptimizationLevel(
            self.config.get("optimization_level", "balanced"),
        )

        # Initialize optimization components
        self.cache_optimizer = CacheOptimizer(self.config.get("cache", {}))
        self.memory_optimizer = MemoryOptimizer(self.config.get("memory", {}))
        self.concurrency_optimizer = ConcurrencyOptimizer(
            self.config.get("concurrency", {}),
        )
        self.io_optimizer = IOOptimizer(self.config.get("io", {}))
        self.query_optimizer = QueryOptimizer(self.config.get("query", {}))
        self.performance_monitor = PerformanceMonitor(self.config.get("monitoring", {}))

        # Auto-optimization
        self.auto_optimize_enabled = self.config.get("auto_optimize", True)
        self.auto_optimize_interval = self.config.get(
            "auto_optimize_interval",
            300,
        )  # 5 minutes

        # Performance tracking
        self.optimization_history: deque = deque(maxlen=100)
        self.last_optimization_time = 0.0

        # Background optimization
        self.optimization_thread: threading.Thread | None = None
        self.shutdown_event = Event()

        # Alert handling
        self.performance_monitor.add_alert_callback(self._handle_performance_alert)

        self._configure_optimization_level()
        if self.auto_optimize_enabled:
            self._start_auto_optimization()

    def optimize_system(self, force: bool = False) -> dict[str, Any]:
        """
        Perform comprehensive system optimization.

        Args:
            force: Force optimization even if recently performed

        Returns:
            Dict containing optimization results
        """
        current_time = time.time()

        # Check if optimization was recently performed
        if not force and (current_time - self.last_optimization_time) < 60:
            return {"status": "skipped", "reason": "recently_optimized"}

        self.logger.info("Starting comprehensive system optimization")
        start_time = time.time()

        optimization_results = {
            "timestamp": datetime.now(UTC).isoformat(),
            "optimization_level": self.optimization_level.value,
            "components": {},
        }

        try:
            # Cache optimization
            cache_results = self.cache_optimizer.get_optimization_stats()
            optimization_results["components"]["cache"] = cache_results

            # Memory optimization
            memory_results = self.memory_optimizer.optimize_memory()
            optimization_results["components"]["memory"] = memory_results

            # Concurrency optimization
            concurrency_results = self.concurrency_optimizer.optimize_thread_pool()
            optimization_results["components"]["concurrency"] = concurrency_results

            # I/O optimization
            io_results = self.io_optimizer.optimize_io()
            optimization_results["components"]["io"] = io_results

            # Update system health score
            health_score = self.performance_monitor.get_system_health_score()
            optimization_results["health_score"] = health_score

            # Detect bottlenecks
            bottlenecks = self.performance_monitor.detect_bottlenecks()
            optimization_results["bottlenecks"] = bottlenecks

            # Auto-tune based on performance
            if self.auto_optimize_enabled:
                tuning_results = self._auto_tune_system(health_score, bottlenecks)
                optimization_results["auto_tuning"] = tuning_results

            optimization_time = time.time() - start_time
            optimization_results["optimization_time"] = optimization_time
            optimization_results["status"] = "success"

            # Record optimization
            self.optimization_history.append(
                {
                    "timestamp": current_time,
                    "duration": optimization_time,
                    "health_score": health_score,
                    "bottlenecks_count": len(bottlenecks),
                },
            )

            self.last_optimization_time = current_time

            self.logger.info(
                f"System optimization completed in {optimization_time:.2f}s. "
                f"Health score: {health_score:.1f}/100",
            )

        except Exception as e:
            self.logger.error(f"System optimization failed: {e}")
            optimization_results["status"] = "error"
            optimization_results["error"] = str(e)

        return optimization_results

    def get_performance_report(self) -> dict[str, Any]:
        """
        Generate comprehensive performance report.

        Returns:
            Dict containing detailed performance analysis
        """
        report = {
            "timestamp": datetime.now(UTC).isoformat(),
            "system_overview": {},
            "optimization_components": {},
            "performance_trends": {},
            "recommendations": [],
        }

        try:
            # System overview
            health_score = self.performance_monitor.get_system_health_score()
            bottlenecks = self.performance_monitor.detect_bottlenecks()

            report["system_overview"] = {
                "health_score": health_score,
                "optimization_level": self.optimization_level.value,
                "auto_optimize_enabled": self.auto_optimize_enabled,
                "bottlenecks_count": len(bottlenecks),
                "bottlenecks": bottlenecks,
            }

            # Component statistics
            report["optimization_components"] = {
                "cache": self.cache_optimizer.get_optimization_stats(),
                "memory": self.memory_optimizer.get_memory_stats(),
                "concurrency": self.concurrency_optimizer.get_concurrency_stats(),
                "io": self.io_optimizer.get_io_stats(),
                "query": self.query_optimizer.get_query_stats(),
            }

            # Performance trends
            for metric in PerformanceMetric:
                stats = self.performance_monitor.get_metric_stats(
                    metric,
                    duration=3600,
                )  # Last hour
                if stats["count"] > 0:
                    report["performance_trends"][metric.value] = stats

            # Generate recommendations
            recommendations = self._generate_recommendations(
                health_score,
                bottlenecks,
                report,
            )
            report["recommendations"] = recommendations

            # System integration status
            if self.system_integrator:
                try:
                    integration_health = self.system_integrator.get_system_diagnostics()
                    report["system_integration"] = {
                        "available": True,
                        "health_summary": integration_health.get("system_health", {}),
                    }
                except Exception as e:
                    report["system_integration"] = {"available": False, "error": str(e)}
            else:
                report["system_integration"] = {"available": False}

        except Exception as e:
            self.logger.error(f"Failed to generate performance report: {e}")
            report["error"] = str(e)

        return report

    def configure_optimization(self, level: OptimizationLevel, **kwargs) -> None:
        """
        Configure optimization level and parameters.

        Args:
            level: Optimization level to apply
            **kwargs: Additional configuration parameters
        """
        self.optimization_level = level
        self.logger.info(f"Configured optimization level: {level.value}")

        # Update component configurations
        if "cache" in kwargs:
            self.cache_optimizer.config.update(kwargs["cache"])
        if "memory" in kwargs:
            self.memory_optimizer.config.update(kwargs["memory"])
        if "concurrency" in kwargs:
            self.concurrency_optimizer.config.update(kwargs["concurrency"])
        if "io" in kwargs:
            self.io_optimizer.config.update(kwargs["io"])

        # Apply optimization level settings
        self._configure_optimization_level()

    def _configure_optimization_level(self) -> None:
        """Configure components based on optimization level."""
        if self.optimization_level == OptimizationLevel.CONSERVATIVE:
            # Conservative settings
            self.performance_monitor.set_alert_threshold(
                PerformanceMetric.CPU_USAGE,
                90.0,
            )
            self.performance_monitor.set_alert_threshold(
                PerformanceMetric.MEMORY_USAGE,
                90.0,
            )

        elif self.optimization_level == OptimizationLevel.BALANCED:
            # Balanced settings (default)
            self.performance_monitor.set_alert_threshold(
                PerformanceMetric.CPU_USAGE,
                80.0,
            )
            self.performance_monitor.set_alert_threshold(
                PerformanceMetric.MEMORY_USAGE,
                85.0,
            )

        elif self.optimization_level == OptimizationLevel.AGGRESSIVE:
            # Aggressive settings
            self.performance_monitor.set_alert_threshold(
                PerformanceMetric.CPU_USAGE,
                70.0,
            )
            self.performance_monitor.set_alert_threshold(
                PerformanceMetric.MEMORY_USAGE,
                75.0,
            )

            # More aggressive GC tuning
            self.memory_optimizer.gc_config["target_frequency"] = 15.0
            self.memory_optimizer.gc_config["pressure_threshold"] = 0.6

    def _auto_tune_system(
        self,
        health_score: float,
        bottlenecks: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Auto-tune system based on performance metrics."""
        tuning_results = {"actions_taken": [], "recommendations": []}

        # Auto-tune based on health score
        if health_score < 60:
            # Poor health, take corrective actions
            if any(b["metric"] == "memory_usage" for b in bottlenecks):
                # Memory pressure
                gc_result = self.memory_optimizer.force_gc()
                tuning_results["actions_taken"].append(
                    f"Forced garbage collection: {gc_result}",
                )

            if any(b["metric"] == "cache_hit_rate" for b in bottlenecks):
                # Poor cache performance
                # Clear some L3 cache to make room for more relevant data
                self.cache_optimizer.l3_cache.clear()
                tuning_results["actions_taken"].append("Cleared L3 cache for refresh")

        elif health_score > 85:
            # Good health, optimize for performance
            tuning_results["recommendations"].append(
                "System performing well, consider more aggressive optimization",
            )

        # Auto-tune cache sizes based on hit rates
        cache_stats = self.cache_optimizer.get_optimization_stats()
        overall_hit_rate = cache_stats.get("overall_hit_rate", 0)

        if overall_hit_rate < 0.7:  # Less than 70% hit rate
            tuning_results["recommendations"].append("Consider increasing cache sizes")

        return tuning_results

    def _generate_recommendations(
        self,
        health_score: float,
        bottlenecks: list[dict[str, Any]],
        report: dict[str, Any],
    ) -> list[str]:
        """Generate optimization recommendations."""
        recommendations = []

        # Health-based recommendations
        if health_score < 50:
            recommendations.append(
                "CRITICAL: System health is poor. Immediate optimization required.",
            )
        elif health_score < 70:
            recommendations.append(
                "WARNING: System health is degraded. Consider optimization.",
            )
        elif health_score > 90:
            recommendations.append("EXCELLENT: System is performing optimally.")

        # Bottleneck-specific recommendations
        for bottleneck in bottlenecks:
            metric = bottleneck["metric"]
            if metric == "cpu_usage":
                recommendations.append(
                    "CPU bottleneck detected: Reduce concurrent operations",
                )
            elif metric == "memory_usage":
                recommendations.append(
                    "Memory bottleneck detected: Optimize memory usage",
                )
            elif metric == "cache_hit_rate":
                recommendations.append(
                    "Cache bottleneck detected: Increase cache size or improve strategy",
                )

        # Component-specific recommendations
        components = report.get("optimization_components", {})

        # Cache recommendations
        cache_stats = components.get("cache", {})
        if cache_stats.get("overall_hit_rate", 1.0) < 0.6:
            recommendations.append(
                "Cache hit rate is low. Consider increasing cache sizes.",
            )

        # Memory recommendations
        memory_stats = components.get("memory", {})
        process_memory = memory_stats.get("process_memory", {})
        if process_memory.get("percent", 0) > 80:
            recommendations.append(
                "High memory usage detected. Consider memory optimization.",
            )

        # Query recommendations
        query_stats = components.get("query", {})
        if query_stats.get("slow_queries_count", 0) > 10:
            recommendations.append(
                "Multiple slow queries detected. Review query optimization.",
            )

        return recommendations

    def _handle_performance_alert(self, alert: PerformanceAlert) -> None:
        """Handle performance alerts from monitor."""
        self.logger.warning(f"Performance alert: {alert.message}")

        # Take immediate action for critical alerts
        if alert.severity == AlertSeverity.CRITICAL:
            if alert.metric == PerformanceMetric.MEMORY_USAGE:
                # Force garbage collection for critical memory alerts
                self.memory_optimizer.force_gc()
                self.logger.info(
                    "Forced garbage collection due to critical memory alert",
                )
            elif alert.metric == PerformanceMetric.CPU_USAGE:
                # Could implement CPU throttling or task reduction
                self.logger.info("Critical CPU usage alert - consider reducing load")

        # Trigger optimization if system integrator is available
        if self.system_integrator and hasattr(
            self.system_integrator,
            "monitor_system_health",
        ):
            try:
                self.system_integrator.monitor_system_health()
            except Exception as e:
                self.logger.error(f"Failed to trigger system health monitoring: {e}")

    def _start_auto_optimization(self) -> None:
        """Start background auto-optimization thread."""
        self.optimization_thread = threading.Thread(
            target=self._auto_optimization_worker,
            name="AutoOptimization",
            daemon=True,
        )
        self.optimization_thread.start()

    def _auto_optimization_worker(self) -> None:
        """Background worker for auto-optimization."""
        while not self.shutdown_event.wait(self.auto_optimize_interval):
            try:
                health_score = self.performance_monitor.get_system_health_score()

                # Only auto-optimize if health score is below threshold
                if health_score < 75:
                    self.logger.info(
                        f"Auto-optimization triggered (health score: {health_score:.1f})",
                    )
                    self.optimize_system()

            except Exception as e:
                self.logger.error(f"Error in auto-optimization: {e}")

    def shutdown(self) -> None:
        """Shutdown performance optimizer and all components."""
        self.logger.info("Shutting down performance optimizer")

        self.shutdown_event.set()

        # Shutdown components
        try:
            self.cache_optimizer.shutdown()
            self.memory_optimizer.shutdown()
            self.concurrency_optimizer.shutdown()
            self.io_optimizer.shutdown()
            self.performance_monitor.shutdown()
        except Exception as e:
            self.logger.error(f"Error during component shutdown: {e}")

        # Wait for optimization thread to finish
        if self.optimization_thread and self.optimization_thread.is_alive():
            self.optimization_thread.join(timeout=10)

        self.logger.info("Performance optimizer shutdown completed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.shutdown()


# Factory functions for easy instantiation
def create_performance_optimizer(
    config: dict[str, Any] | None = None,
    optimization_level: OptimizationLevel = OptimizationLevel.BALANCED,
) -> PerformanceOptimizer:
    """
    Create and configure a performance optimizer instance.

    Args:
        config: Configuration dictionary
        optimization_level: Optimization level to apply

    Returns:
        Configured PerformanceOptimizer instance
    """
    # Default configuration
    default_config = {
        "optimization_level": optimization_level.value,
        "auto_optimize": True,
        "auto_optimize_interval": 300,
        "cache": {
            "l1_cache_size": 500,
            "l2_cache_size": 2000,
            "l3_cache_size": 10000,
            "l1_ttl_seconds": 300,
            "l2_ttl_seconds": 1800,
            "l3_ttl_seconds": 7200,
        },
        "memory": {
            "memory_warning_mb": 1024,
            "memory_critical_mb": 2048,
            "gc_auto_tune": True,
            "gc_target_frequency": 10.0,
            "gc_pressure_threshold": 0.8,
        },
        "concurrency": {
            "min_workers": 2,
            "max_workers": min(32, (os.cpu_count() or 1) + 4),
            "worker_timeout": 60,
        },
        "io": {
            "batch_size": 100,
            "batch_timeout": 1.0,
            "max_connections": 10,
            "connection_timeout": 30,
        },
        "query": {"query_cache_size": 1000, "query_cache_ttl": 300},
        "monitoring": {"sample_interval": 5.0, "history_size": 1000},
    }

    # Merge with provided config
    if config:

        def deep_merge(target, source):
            for key, value in source.items():
                if (
                    key in target
                    and isinstance(target[key], dict)
                    and isinstance(value, dict)
                ):
                    deep_merge(target[key], value)
                else:
                    target[key] = value

        deep_merge(default_config, config)

    # Get system integrator if available
    system_integrator = None
    if CORE_INTEGRATION_AVAILABLE:
        try:
            system_integrator = get_system_integrator()
        except Exception:
            pass  # Continue without system integrator

    return PerformanceOptimizer(default_config, system_integrator)


# Example usage and integration functions
def optimize_treesitter_performance(
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Convenience function to perform system-wide performance optimization.

    Args:
        config: Optional configuration override

    Returns:
        Optimization results
    """
    with create_performance_optimizer(config) as optimizer:
        return optimizer.optimize_system(force=True)


def get_treesitter_performance_report(
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Convenience function to generate performance report.

    Args:
        config: Optional configuration override

    Returns:
        Performance report
    """
    with create_performance_optimizer(config) as optimizer:
        return optimizer.get_performance_report()
