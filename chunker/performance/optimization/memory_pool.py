"""Memory pool implementation for reusing expensive objects."""

import logging
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
        # Use plain sets for in-use tracking to support non-weakref types
        self._in_use: dict[str, set[Any]] = defaultdict(set)
        self._max_size = max_pool_size
        self._lock = RLock()
        self._stats = defaultdict(
            lambda: {"acquired": 0, "released": 0, "created": 0},
        )
        logger.info(
            "Initialized MemoryPool with max size %s per type",
            max_pool_size,
        )

    def acquire(self, resource_type: str) -> Any:
        """Acquire a resource from the pool.

        Args:
            resource_type: Type of resource needed (e.g., 'parser:python')

        Returns:
            Resource instance
        """
        with self._lock:
            pool = self._pools[resource_type]
            if pool:
                resource = pool.popleft()
                self._stats[resource_type]["acquired"] += 1
                logger.debug(
                    "Acquired %s from pool (pool size: %d)",
                    resource_type,
                    len(pool),
                )
            else:
                resource = self._create_resource(resource_type)
                self._stats[resource_type]["created"] += 1
                self._stats[resource_type]["acquired"] += 1
                logger.debug(
                    "Created new %s (no pooled instances)",
                    resource_type,
                )
            self._in_use[resource_type].add(resource)
            return resource

    def release(self, resource: Any) -> None:
        """Return a resource to the pool.

        Args:
            resource: Resource to return
        """
        resource_type = self._get_resource_type(resource)
        with self._lock:
            if resource in self._in_use[resource_type]:
                self._in_use[resource_type].discard(resource)
            pool = self._pools[resource_type]
            if len(pool) < self._max_size:
                self._reset_resource(resource)
                pool.append(resource)
                self._stats[resource_type]["released"] += 1
                logger.debug(
                    "Released %s to pool (pool size: %d)",
                    resource_type,
                    len(pool),
                )
            else:
                logger.debug(
                    "Pool full for %s, discarding resource",
                    resource_type,
                )

    def size(self, resource_type: str) -> int:
        """Get current pool size for a resource type."""
        with self._lock:
            return len(self._pools[resource_type])

    def clear(self, resource_type: str | None = None) -> None:
        """Clear pooled resources."""
        with self._lock:
            if resource_type:
                if resource_type in self._pools:
                    count = len(self._pools[resource_type])
                    self._pools[resource_type].clear()
                    logger.info(
                        "Cleared %s pooled %s resources",
                        count,
                        resource_type,
                    )
            else:
                total = sum(len(pool) for pool in self._pools.values())
                self._pools.clear()
                self._in_use.clear()
                self._stats.clear()
                logger.info(
                    "Cleared all %s pooled resources",
                    total,
                )

    def get_stats(self) -> dict[str, dict[str, int]]:
        """Get pool statistics."""
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

    @classmethod
    def _create_resource(cls, resource_type: str) -> Any:
        """Create a new resource based on type."""
        if resource_type.startswith("parser:"):
            language = resource_type.split(":", 1)[1]
            return get_parser(language)
        if resource_type == "byte_buffer":
            return bytearray(1024 * 1024)
        if resource_type == "chunk_list":
            return []
        raise ValueError(f"Unknown resource type: {resource_type}")

    @staticmethod
    def _get_resource_type(resource: Any) -> str:
        """Determine the type of a resource."""
        if isinstance(resource, Parser):
            return "parser:unknown"
        if isinstance(resource, bytearray):
            return "byte_buffer"
        if isinstance(resource, list):
            return "chunk_list"
        return "unknown"

    @staticmethod
    def _reset_resource(resource: Any) -> None:
        """Reset a resource before returning to pool."""
        if isinstance(resource, list):
            resource.clear()
        elif isinstance(resource, bytearray):
            resource[:1024] = b"\x00" * min(1024, len(resource))

    def acquire_parser(self, language: str) -> Parser:
        """Acquire a parser for a specific language."""
        return self.acquire(f"parser:{language}")

    def release_parser(self, parser: Parser, language: str) -> None:
        """Release a parser back to the pool."""
        with self._lock:
            resource_type = f"parser:{language}"
            if parser in self._in_use[resource_type]:
                self._in_use[resource_type].discard(parser)
            pool = self._pools[resource_type]
            if len(pool) < self._max_size:
                pool.append(parser)
                self._stats[resource_type]["released"] += 1
                logger.debug("Released parser:%s to pool", language)

    def warm_up(self, resource_type: str, count: int) -> None:
        """Pre-create resources for the pool."""
        with self._lock:
            pool = self._pools[resource_type]
            current_size = len(pool)
            to_create = min(count, self._max_size - current_size)
            for _ in range(to_create):
                resource = self._create_resource(resource_type)
                pool.append(resource)
                self._stats[resource_type]["created"] += 1
            logger.info(
                "Warmed up %s %s resources",
                to_create,
                resource_type,
            )
