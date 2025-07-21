"""LRU (Least Recently Used) cache implementation."""

from collections import OrderedDict
from datetime import datetime
from threading import RLock
from typing import Any, Optional, Tuple
import sys


class LRUCache:
    """Thread-safe LRU cache implementation using OrderedDict.
    
    This cache automatically evicts least recently used items
    when the maximum size is reached.
    """
    
    def __init__(self, max_size: int = 1000):
        """Initialize LRU cache.
        
        Args:
            max_size: Maximum number of entries in the cache
        """
        self.max_size = max_size
        self._cache: OrderedDict[str, Tuple[Any, datetime, Optional[int]]] = OrderedDict()
        self._lock = RLock()
        self._hits = 0
        self._misses = 0
        
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache, updating its position.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None if not found/expired
        """
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None
                
            value, created_at, ttl = self._cache[key]
            
            # Check if expired
            if ttl is not None:
                age = (datetime.now() - created_at).total_seconds()
                if age > ttl:
                    del self._cache[key]
                    self._misses += 1
                    return None
            
            # Move to end (most recently used)
            self._cache.move_to_end(key)
            self._hits += 1
            return value
    
    def put(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Put a value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl_seconds: Time to live in seconds (None for no expiry)
        """
        with self._lock:
            # Remove if exists to update position
            if key in self._cache:
                del self._cache[key]
            
            # Add to end
            self._cache[key] = (value, datetime.now(), ttl_seconds)
            
            # Evict oldest if over capacity
            if len(self._cache) > self.max_size:
                self._cache.popitem(last=False)
    
    def invalidate(self, key: str) -> bool:
        """Remove a specific key from cache.
        
        Args:
            key: Key to remove
            
        Returns:
            True if key was found and removed
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    def clear(self) -> None:
        """Clear all cache entries."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0
    
    def size(self) -> int:
        """Get current number of entries."""
        with self._lock:
            return len(self._cache)
    
    def memory_usage(self) -> int:
        """Estimate memory usage in bytes."""
        with self._lock:
            total = sys.getsizeof(self._cache)
            for key, (value, _, _) in self._cache.items():
                total += sys.getsizeof(key)
                total += sys.getsizeof(value)
            return total
    
    def evict_expired(self) -> int:
        """Remove all expired entries.
        
        Returns:
            Number of entries evicted
        """
        with self._lock:
            expired_keys = []
            now = datetime.now()
            
            for key, (_, created_at, ttl) in self._cache.items():
                if ttl is not None:
                    age = (now - created_at).total_seconds()
                    if age > ttl:
                        expired_keys.append(key)
            
            for key in expired_keys:
                del self._cache[key]
                
            return len(expired_keys)
    
    def get_stats(self) -> dict:
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = self._hits / total_requests if total_requests > 0 else 0.0
            
            return {
                'size': len(self._cache),
                'max_size': self.max_size,
                'hits': self._hits,
                'misses': self._misses,
                'hit_rate': hit_rate,
                'memory_usage_bytes': self.memory_usage()
            }