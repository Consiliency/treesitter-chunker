"""Cache manager implementation."""

import hashlib
import logging
from typing import Any

from chunker.interfaces.performance import CacheManager as CacheManagerInterface

from .multi_level import MultiLevelCache

logger = logging.getLogger(__name__)


class CacheManager(CacheManagerInterface):
    """Implementation of CacheManager interface with multi-level caching."""

    def __init__(
        self,
        ast_size: int = 100,
        chunk_size: int = 1000,
        query_size: int = 500,
        metadata_size: int = 500,
    ):
        """Initialize cache manager.

        Args:
            ast_size: Max entries for AST cache
            chunk_size: Max entries for chunk cache
            query_size: Max entries for query cache
            metadata_size: Max entries for metadata cache
        """
        self._cache = MultiLevelCache(ast_size, chunk_size, query_size, metadata_size)
        logger.info(
            "Initialized CacheManager with sizes - AST: %d, Chunk: %d, Query: %d, Metadata: %d",
            ast_size,
            chunk_size,
            query_size,
            metadata_size,
        )

    def get(self, key: str) -> Any | None:
        """Get a value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        value = self._cache.get(key)
        if value is not None:
            logger.debug("Cache hit for key: %s", key)
        else:
            logger.debug("Cache miss for key: %s", key)
        return value

    def put(self, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Put a value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time to live (None for no expiry)
        """
        self._cache.put(key, value, ttl_seconds)
        logger.debug("Cached value for key: %s (TTL: %ss)", key, ttl_seconds)

    def invalidate(self, key: str) -> bool:
        """Invalidate a cache entry.

        Args:
            key: Cache key to invalidate

        Returns:
            True if entry was found and invalidated
        """
        result = self._cache.invalidate(key)
        if result:
            logger.debug("Invalidated cache key: %s", key)
        return result

    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all entries matching a pattern.

        Args:
            pattern: Pattern to match (e.g., 'file:*' for all files)

        Returns:
            Number of entries invalidated
        """
        count = self._cache.invalidate_pattern(pattern)
        if count > 0:
            logger.info(
                "Invalidated %d cache entries matching pattern: %s",
                count,
                pattern,
            )
        return count

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        logger.info("Cleared all cache entries")

    def size(self) -> int:
        """Get number of entries in cache.

        Returns:
            Number of cache entries
        """
        return self._cache.size()

    def memory_usage(self) -> int:
        """Get approximate memory usage in bytes.

        Returns:
            Memory usage in bytes
        """
        return self._cache.memory_usage()

    def evict_expired(self) -> int:
        """Remove all expired entries.

        Returns:
            Number of entries evicted
        """
        count = self._cache.evict_expired()
        if count > 0:
            logger.info("Evicted %s expired cache entries", count)
        return count

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with hit rate, size, memory usage, etc.
        """
        return self._cache.get_stats()

    def cache_ast(
        self,
        file_path: str,
        source_hash: str,
        ast: Any,
        language: str,
        parse_time_ms: float,
    ) -> None:
        """Cache a parsed AST.

        Args:
            file_path: Path to the file
            source_hash: Hash of the source code
            ast: Parsed AST
            language: Language of the file
            parse_time_ms: Time taken to parse
        """
        key = f"ast:{file_path}:{source_hash}"
        value = {
            "ast": ast,
            "language": language,
            "parse_time_ms": parse_time_ms,
            "source_hash": source_hash,
        }
        self.put(key, value, ttl_seconds=3600)

    def get_cached_ast(self, file_path: str, source_hash: str) -> dict[str, Any] | None:
        """Get cached AST if available.

        Args:
            file_path: Path to the file
            source_hash: Hash of the source code

        Returns:
            Cached AST data or None
        """
        key = f"ast:{file_path}:{source_hash}"
        return self.get(key)

    def cache_chunks(
        self,
        file_path: str,
        source_hash: str,
        chunks: Any,
    ) -> None:
        """Cache code chunks.

        Args:
            file_path: Path to the file
            source_hash: Hash of the source code
            chunks: List of code chunks
        """
        key = f"chunk:{file_path}:{source_hash}"
        self.put(key, chunks, ttl_seconds=1800)

    def get_cached_chunks(self, file_path: str, source_hash: str) -> Any | None:
        """Get cached chunks if available.

        Args:
            file_path: Path to the file
            source_hash: Hash of the source code

        Returns:
            Cached chunks or None
        """
        key = f"chunk:{file_path}:{source_hash}"
        return self.get(key)

    def invalidate_file(self, file_path: str) -> int:
        """Invalidate all cache entries for a file.

        Args:
            file_path: Path to the file

        Returns:
            Number of entries invalidated
        """
        patterns = [
            f"ast:{file_path}:*",
            f"chunk:{file_path}:*",
            f"query:{file_path}:*",
            f"metadata:{file_path}:*",
        ]
        total = 0
        for pattern in patterns:
            total += self.invalidate_pattern(pattern)
        return total

    @staticmethod
    def compute_source_hash(source: bytes) -> str:
        """Compute hash of source code.

        Args:
            source: Source code bytes

        Returns:
            Hash string
        """
        return hashlib.sha256(source).hexdigest()[:16]
