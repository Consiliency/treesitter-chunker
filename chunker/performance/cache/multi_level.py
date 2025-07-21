"""Multi-level cache implementation for different data types."""

from typing import Any, Dict, Optional, List
from .lru import LRUCache
import fnmatch


class MultiLevelCache:
    """Multi-level cache with separate caches for different data types.
    
    This provides optimized caching for:
    - AST parse trees
    - Code chunks
    - Query results
    - File metadata
    """
    
    def __init__(self, 
                 ast_size: int = 100,
                 chunk_size: int = 1000, 
                 query_size: int = 500,
                 metadata_size: int = 500):
        """Initialize multi-level cache.
        
        Args:
            ast_size: Max entries for AST cache
            chunk_size: Max entries for chunk cache
            query_size: Max entries for query cache
            metadata_size: Max entries for metadata cache
        """
        self.caches = {
            'ast': LRUCache(ast_size),
            'chunk': LRUCache(chunk_size),
            'query': LRUCache(query_size),
            'metadata': LRUCache(metadata_size)
        }
        
        # Default cache for unknown types
        self.default_cache = LRUCache(1000)
        
    def _get_cache_for_key(self, key: str) -> LRUCache:
        """Determine which cache to use based on key prefix."""
        for prefix, cache in self.caches.items():
            if key.startswith(f"{prefix}:"):
                return cache
        return self.default_cache
    
    def get(self, key: str) -> Optional[Any]:
        """Get value from appropriate cache level."""
        cache = self._get_cache_for_key(key)
        return cache.get(key)
    
    def put(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Put value in appropriate cache level."""
        cache = self._get_cache_for_key(key)
        cache.put(key, value, ttl_seconds)
    
    def invalidate(self, key: str) -> bool:
        """Invalidate a specific key."""
        cache = self._get_cache_for_key(key)
        return cache.invalidate(key)
    
    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all entries matching a pattern.
        
        Args:
            pattern: Glob pattern to match (e.g., 'ast:*.py')
            
        Returns:
            Number of entries invalidated
        """
        count = 0
        
        for cache in list(self.caches.values()) + [self.default_cache]:
            # Get all keys (we need to iterate safely)
            keys_to_check = []
            with cache._lock:
                keys_to_check = list(cache._cache.keys())
            
            # Check each key against pattern
            for key in keys_to_check:
                if fnmatch.fnmatch(key, pattern):
                    if cache.invalidate(key):
                        count += 1
                        
        return count
    
    def clear(self) -> None:
        """Clear all cache levels."""
        for cache in self.caches.values():
            cache.clear()
        self.default_cache.clear()
    
    def size(self) -> int:
        """Get total number of entries across all levels."""
        total = sum(cache.size() for cache in self.caches.values())
        total += self.default_cache.size()
        return total
    
    def memory_usage(self) -> int:
        """Get total memory usage across all levels."""
        total = sum(cache.memory_usage() for cache in self.caches.values())
        total += self.default_cache.memory_usage()
        return total
    
    def evict_expired(self) -> int:
        """Evict expired entries from all levels."""
        total = sum(cache.evict_expired() for cache in self.caches.values())
        total += self.default_cache.evict_expired()
        return total
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics for all cache levels."""
        stats = {
            'total_size': self.size(),
            'total_memory_bytes': self.memory_usage(),
            'levels': {}
        }
        
        # Add per-level stats
        for name, cache in self.caches.items():
            stats['levels'][name] = cache.get_stats()
            
        stats['levels']['default'] = self.default_cache.get_stats()
        
        # Calculate overall hit rate
        total_hits = sum(cache._hits for cache in self.caches.values()) + self.default_cache._hits
        total_misses = sum(cache._misses for cache in self.caches.values()) + self.default_cache._misses
        total_requests = total_hits + total_misses
        
        stats['overall_hit_rate'] = total_hits / total_requests if total_requests > 0 else 0.0
        stats['total_hits'] = total_hits
        stats['total_misses'] = total_misses
        
        return stats