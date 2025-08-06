"""Performance optimization interfaces.

Interfaces for caching, incremental parsing, and other
performance optimizations.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from tree_sitter import Node

from chunker.types import CodeChunk


@dataclass
class CacheEntry:
    """Represents a cached item.

    Attributes:
        key: Unique identifier for this entry
        value: Cached value
        created_at: When this entry was created
        accessed_at: When this entry was last accessed
        ttl_seconds: Time to live in seconds (None = no expiry)
        metadata: Additional metadata about the entry
    """

    key: str
    value: Any
    created_at: datetime
    accessed_at: datetime
    ttl_seconds: int | None = None
    metadata: dict[str, Any] = None

    def is_expired(self) -> bool:
        """Check if this entry has expired."""
        if self.ttl_seconds is None:
            return False
        age = (datetime.now() - self.created_at).total_seconds()
        return age > self.ttl_seconds


@dataclass
class ParseCache:
    """Cached parse result.

    Attributes:
        ast: Parsed AST root node
        source_hash: Hash of the source that was parsed
        language: Language that was parsed
        parse_time_ms: Time taken to parse in milliseconds
    """

    ast: Node
    source_hash: str
    language: str
    parse_time_ms: float


class CacheManager(ABC):
    """Manages various caches for performance."""

    @staticmethod
    @abstractmethod
    def get(key: str) -> Any | None:
        """Get a value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """

    @staticmethod
    @abstractmethod
    def put(key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Put a value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time to live (None for no expiry)
        """

    @staticmethod
    @abstractmethod
    def invalidate(key: str) -> bool:
        """Invalidate a cache entry.

        Args:
            key: Cache key to invalidate

        Returns:
            True if entry was found and invalidated
        """

    @staticmethod
    @abstractmethod
    def invalidate_pattern(pattern: str) -> int:
        """Invalidate all entries matching a pattern.

        Args:
            pattern: Pattern to match (e.g., 'file:*' for all files)

        Returns:
            Number of entries invalidated
        """

    @staticmethod
    @abstractmethod
    def clear() -> None:
        """Clear all cache entries."""

    @staticmethod
    @abstractmethod
    def size() -> int:
        """Get number of entries in cache.

        Returns:
            Number of cache entries
        """

    @staticmethod
    @abstractmethod
    def memory_usage() -> int:
        """Get approximate memory usage in bytes.

        Returns:
            Memory usage in bytes
        """

    @staticmethod
    @abstractmethod
    def evict_expired() -> int:
        """Remove all expired entries.

        Returns:
            Number of entries evicted
        """

    @staticmethod
    @abstractmethod
    def get_stats() -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with hit rate, size, memory usage, etc.
        """


class IncrementalParser(ABC):
    """Support for incremental parsing of file changes."""

    @staticmethod
    @abstractmethod
    def parse_incremental(
        old_tree: Node,
        source: bytes,
        changed_ranges: list[tuple[int, int, int, int]],
    ) -> Node:
        """Parse incrementally based on changes.

        Args:
            old_tree: Previous parse tree
            source: New source code
            changed_ranges: List of (start_byte, old_end_byte, new_end_byte, start_point)

        Returns:
            New parse tree
        """

    @staticmethod
    @abstractmethod
    def detect_changes(
        old_source: bytes,
        new_source: bytes,
    ) -> list[tuple[int, int, int, int]]:
        """Detect changed ranges between sources.

        Args:
            old_source: Previous source code
            new_source: New source code

        Returns:
            List of changed ranges
        """

    @staticmethod
    @abstractmethod
    def update_chunks(
        old_chunks: list[CodeChunk],
        old_tree: Node,
        new_tree: Node,
        changed_ranges: list[tuple[int, int, int, int]],
    ) -> list[CodeChunk]:
        """Update chunks based on incremental changes.

        Args:
            old_chunks: Previous chunks
            old_tree: Previous parse tree
            new_tree: New parse tree
            changed_ranges: Ranges that changed

        Returns:
            Updated chunk list
        """


class MemoryPool(ABC):
    """Pool for reusing expensive objects."""

    @staticmethod
    @abstractmethod
    def acquire(resource_type: str) -> Any:
        """Acquire a resource from the pool.

        Args:
            resource_type: Type of resource needed

        Returns:
            Resource instance
        """

    @staticmethod
    @abstractmethod
    def release(resource: Any) -> None:
        """Return a resource to the pool.

        Args:
            resource: Resource to return
        """

    @staticmethod
    @abstractmethod
    def size(resource_type: str) -> int:
        """Get current pool size for a resource type.

        Args:
            resource_type: Type to check

        Returns:
            Number of pooled resources
        """

    @staticmethod
    @abstractmethod
    def clear(resource_type: str | None = None) -> None:
        """Clear pooled resources.

        Args:
            resource_type: Type to clear (None for all)
        """


class PerformanceMonitor(ABC):
    """Monitor performance metrics."""

    @staticmethod
    @abstractmethod
    def start_operation(operation_name: str) -> str:
        """Start timing an operation.

        Args:
            operation_name: Name of the operation

        Returns:
            Operation ID for tracking
        """

    @staticmethod
    @abstractmethod
    def end_operation(operation_id: str) -> float:
        """End timing an operation.

        Args:
            operation_id: ID from start_operation

        Returns:
            Duration in milliseconds
        """

    @staticmethod
    @abstractmethod
    def record_metric(metric_name: str, value: float) -> None:
        """Record a performance metric.

        Args:
            metric_name: Name of the metric
            value: Metric value
        """

    @staticmethod
    @abstractmethod
    def get_metrics() -> dict[str, dict[str, float]]:
        """Get all recorded metrics.

        Returns:
            Dictionary of metrics with statistics
        """

    @staticmethod
    @abstractmethod
    def reset() -> None:
        """Reset all metrics."""


class BatchProcessor(ABC):
    """Process multiple files efficiently in batches."""

    @staticmethod
    @abstractmethod
    def add_file(file_path: str, priority: int = 0) -> None:
        """Add a file to the batch.

        Args:
            file_path: File to process
            priority: Processing priority (higher = sooner)
        """

    @staticmethod
    @abstractmethod
    def process_batch(
        batch_size: int = 10,
        parallel: bool = True,
    ) -> dict[str, list[CodeChunk]]:
        """Process a batch of files.

        Args:
            batch_size: Number of files to process
            parallel: Whether to process in parallel

        Returns:
            Dictionary mapping file paths to chunks
        """

    @staticmethod
    @abstractmethod
    def pending_count() -> int:
        """Get number of files pending processing.

        Returns:
            Number of pending files
        """
