"""Memory pool implementation for reusing expensive objects."""

import logging
import weakref
from collections import defaultdict, deque
from threading import RLock
from typing import Any

from tree_sitter import Parser

from chunker.interfaces.performance import MemoryPool as MemoryPoolInterface
from chunker.parser import get_parser

logger = logging.getLogger(__name__)


class MemoryPool(MemoryPoolInterface):
    """Pool for reusing expensive objects like parsers and AST nodes.

    This implementation provides thread-safe object pooling with
    automatic cleanup of unused resources.
    """

    def __init__(self, max_pool_size: int = 50):
        """Initialize memory pool.

        Args:
            max_pool_size: Maximum number of objects per type to pool
        """
        self._pools: dict[str, deque[Any]] = defaultdict(deque)
        self._in_use: dict[str, weakref.WeakSet] = defaultdict(weakref.WeakSet)
        self._max_size = max_pool_size
        self._lock = RLock()
        self._stats = defaultdict(lambda: {"acquired": 0, "released": 0, "created": 0})

        logger.info(f"Initialized MemoryPool with max size {max_pool_size} per type")

    def acquire(self, resource_type: str) -> Any:
        """Acquire a resource from the pool.

        Args:
            resource_type: Type of resource needed (e.g., 'parser:python')

        Returns:
            Resource instance
        """
        with self._lock:
            pool = self._pools[resource_type]

            # Try to get from pool
            if pool:
                resource = pool.popleft()
                self._stats[resource_type]["acquired"] += 1
                logger.debug(
                    f"Acquired {resource_type} from pool (pool size: {len(pool)})",
                )
            else:
                # Create new resource
                resource = self._create_resource(resource_type)
                self._stats[resource_type]["created"] += 1
                logger.debug(f"Created new {resource_type} (no pooled instances)")

            # Track in-use resources
            self._in_use[resource_type].add(resource)

            return resource

    def release(self, resource: Any) -> None:
        """Return a resource to the pool.

        Args:
            resource: Resource to return
        """
        resource_type = self._get_resource_type(resource)

        with self._lock:
            # Remove from in-use tracking
            if resource in self._in_use[resource_type]:
                self._in_use[resource_type].discard(resource)

            pool = self._pools[resource_type]

            # Only pool if under limit
            if len(pool) < self._max_size:
                # Reset resource before pooling
                self._reset_resource(resource)
                pool.append(resource)
                self._stats[resource_type]["released"] += 1
                logger.debug(
                    f"Released {resource_type} to pool (pool size: {len(pool)})",
                )
            else:
                # Pool is full, let it be garbage collected
                logger.debug(f"Pool full for {resource_type}, discarding resource")

    def size(self, resource_type: str) -> int:
        """Get current pool size for a resource type.

        Args:
            resource_type: Type to check

        Returns:
            Number of pooled resources
        """
        with self._lock:
            return len(self._pools[resource_type])

    def clear(self, resource_type: str | None = None) -> None:
        """Clear pooled resources.

        Args:
            resource_type: Type to clear (None for all)
        """
        with self._lock:
            if resource_type:
                if resource_type in self._pools:
                    count = len(self._pools[resource_type])
                    self._pools[resource_type].clear()
                    logger.info(f"Cleared {count} pooled {resource_type} resources")
            else:
                total = sum(len(pool) for pool in self._pools.values())
                self._pools.clear()
                self._in_use.clear()
                self._stats.clear()
                logger.info(f"Cleared all {total} pooled resources")

    def get_stats(self) -> dict[str, dict[str, int]]:
        """Get pool statistics.

        Returns:
            Dictionary of statistics per resource type
        """
        with self._lock:
            stats = {}
            for resource_type, pool in self._pools.items():
                stats[resource_type] = {
                    "pooled": len(pool),
                    "in_use": len(self._in_use[resource_type]),
                    "acquired": self._stats[resource_type]["acquired"],
                    "released": self._stats[resource_type]["released"],
                    "created": self._stats[resource_type]["created"],
                }
            return stats

    def _create_resource(self, resource_type: str) -> Any:
        """Create a new resource based on type.

        Args:
            resource_type: Type of resource to create

        Returns:
            New resource instance
        """
        if resource_type.startswith("parser:"):
            # Create parser for specific language
            language = resource_type.split(":", 1)[1]
            return get_parser(language)
        if resource_type == "byte_buffer":
            # Create reusable byte buffer
            return bytearray(1024 * 1024)  # 1MB buffer
        if resource_type == "chunk_list":
            # Create reusable list for chunks
            return []
        raise ValueError(f"Unknown resource type: {resource_type}")

    def _get_resource_type(self, resource: Any) -> str:
        """Determine the type of a resource.

        Args:
            resource: Resource instance

        Returns:
            Resource type string
        """
        if isinstance(resource, Parser):
            # For parsers, we need to determine the language
            # This is simplified - in practice we'd track this better
            return "parser:unknown"
        if isinstance(resource, bytearray):
            return "byte_buffer"
        if isinstance(resource, list):
            return "chunk_list"
        return "unknown"

    def _reset_resource(self, resource: Any) -> None:
        """Reset a resource before returning to pool.

        Args:
            resource: Resource to reset
        """
        if isinstance(resource, list):
            resource.clear()
        elif isinstance(resource, bytearray):
            # Reset buffer to zeros (first 1KB only for efficiency)
            resource[:1024] = b"\0" * min(1024, len(resource))
        # Parsers don't need resetting

    # Convenience methods for common resources

    def acquire_parser(self, language: str) -> Parser:
        """Acquire a parser for a specific language.

        Args:
            language: Language name

        Returns:
            Parser instance
        """
        return self.acquire(f"parser:{language}")

    def release_parser(self, parser: Parser, language: str) -> None:
        """Release a parser back to the pool.

        Args:
            parser: Parser to release
            language: Language of the parser
        """
        # Override the type detection for proper pooling
        with self._lock:
            resource_type = f"parser:{language}"

            # Remove from in-use tracking
            if parser in self._in_use[resource_type]:
                self._in_use[resource_type].discard(parser)

            pool = self._pools[resource_type]

            if len(pool) < self._max_size:
                pool.append(parser)
                self._stats[resource_type]["released"] += 1
                logger.debug(f"Released parser:{language} to pool")

    def warm_up(self, resource_type: str, count: int) -> None:
        """Pre-create resources for the pool.

        Args:
            resource_type: Type of resource
            count: Number to pre-create
        """
        with self._lock:
            pool = self._pools[resource_type]
            current_size = len(pool)

            to_create = min(count, self._max_size - current_size)

            for _ in range(to_create):
                resource = self._create_resource(resource_type)
                pool.append(resource)

            logger.info(f"Warmed up {to_create} {resource_type} resources")
