"""Parser factory with caching and pooling for efficient parser management."""

from __future__ import annotations

import logging
import threading
from collections import OrderedDict
from dataclasses import dataclass
from queue import Empty, Queue
from typing import TYPE_CHECKING, Any

from tree_sitter import Parser, Range

from .exceptions import LanguageNotFoundError, ParserConfigError, ParserInitError

if TYPE_CHECKING:
    from .registry import LanguageRegistry

logger = logging.getLogger(__name__)


@dataclass
class ParserConfig:
    """Configuration options for parser instances."""

    timeout_ms: int | None = None
    included_ranges: list[Range] | None = None
    logger: logging.Logger | None = None

    def validate(self):
        """Validate configuration values."""
        if self.timeout_ms is not None:
            if not isinstance(self.timeout_ms, int) or self.timeout_ms < 0:
                raise ParserConfigError(
                    "timeout_ms",
                    self.timeout_ms,
                    "Must be a non-negative integer",
                )

        if self.included_ranges is not None:
            if not isinstance(self.included_ranges, list):
                raise ParserConfigError(
                    "included_ranges",
                    self.included_ranges,
                    "Must be a list of Range objects",
                )


class LRUCache:
    """Thread-safe LRU cache implementation."""

    def __init__(self, maxsize: int):
        self.maxsize = maxsize
        self.cache: OrderedDict[str, Parser] = OrderedDict()
        self.lock = threading.RLock()

    def get(self, key: str) -> Parser | None:
        """Get item from cache, updating access order."""
        with self.lock:
            if key not in self.cache:
                return None
            # Move to end (most recently used)
            self.cache.move_to_end(key)
            return self.cache[key]

    def put(self, key: str, value: Parser) -> None:
        """Add item to cache, evicting LRU item if needed."""
        with self.lock:
            if key in self.cache:
                # Update existing
                self.cache.move_to_end(key)
            else:
                # Add new
                if len(self.cache) >= self.maxsize:
                    # Evict oldest
                    self.cache.popitem(last=False)
                self.cache[key] = value

    def clear(self) -> None:
        """Clear the cache."""
        with self.lock:
            self.cache.clear()


class ParserPool:
    """Thread-safe pool of parser instances for a specific language."""

    def __init__(self, language: str, max_size: int = 5):
        self.language = language
        self.max_size = max_size
        self.pool: Queue[Parser] = Queue(maxsize=max_size)
        self.created_count = 0
        self.lock = threading.RLock()

    def get(self, _timeout: float | None = None) -> Parser | None:
        """Get a parser from the pool."""
        try:
            return self.pool.get(block=False)
        except Empty:
            return None

    def put(self, parser: Parser) -> bool:
        """Return a parser to the pool."""
        try:
            self.pool.put(parser, block=False)
            return True
        except (AttributeError, KeyError, SyntaxError):
            # Pool is full
            return False

    def size(self) -> int:
        """Get current pool size."""
        return self.pool.qsize()


class ParserFactory:
    """Factory for creating and managing parser instances with caching and pooling."""

    def __init__(
        self,
        registry: LanguageRegistry,
        cache_size: int = 10,
        pool_size: int = 5,
    ):
        """Initialize the parser factory.

        Args:
            registry: Language registry instance
            cache_size: Maximum number of parsers to cache
            pool_size: Maximum number of parsers per language in pool
        """
        self._registry = registry
        self._cache = LRUCache(cache_size)
        self._pools: dict[str, ParserPool] = {}
        self._pool_size = pool_size
        self._lock = threading.RLock()
        self._parser_count = 0

        logger.info(
            f"Initialized ParserFactory with cache_size={cache_size}, pool_size={pool_size}",
        )

    def _create_parser(self, language: str) -> Parser:
        """Create a new parser instance for the language."""
        try:
            lang = self._registry.get_language(language)
            parser = Parser()

            # Use the new API - direct assignment
            parser.language = lang

            self._parser_count += 1
            logger.debug(
                f"Created new parser for '{language}' (total: {self._parser_count})",
            )

            return parser

        except ValueError as e:
            # Check for version compatibility error
            if "Incompatible Language version" in str(e):
                # Extract version info from error message
                import re

                match = re.search(
                    r"version (\d+)\. Must be between (\d+) and (\d+)",
                    str(e),
                )
                if match:
                    grammar_ver, min_ver, max_ver = match.groups()
                    raise ParserInitError(
                        language,
                        f"Grammar compiled with language version {grammar_ver}, "
                        f"but tree-sitter library supports versions {min_ver}-{max_ver}. "
                        f"Consider updating tree-sitter library or recompiling grammars.",
                    )
            raise ParserInitError(language, str(e))
        except (IndexError, KeyError, SyntaxError) as e:
            raise ParserInitError(language, str(e))

    def _get_pool(self, language: str) -> ParserPool:
        """Get or create a parser pool for the language."""
        with self._lock:
            if language not in self._pools:
                self._pools[language] = ParserPool(language, self._pool_size)
            return self._pools[language]

    def _apply_config(self, parser: Parser, config: ParserConfig) -> None:
        """Apply configuration to a parser instance."""
        if config.timeout_ms is not None:
            # Use the property assignment style
            parser.timeout_micros = config.timeout_ms * 1000

        if config.included_ranges is not None:
            parser.included_ranges = config.included_ranges

        if config.logger is not None:
            # Tree-sitter doesn't support custom loggers directly
            # This is a placeholder for future enhancement
            pass

    def get_parser(self, language: str, config: ParserConfig | None = None) -> Parser:
        """Get or create a parser for the language.

        Args:
            language: Language name
            config: Optional parser configuration

        Returns:
            Configured parser instance

        Raises:
            LanguageNotFoundError: If language is not available
            ParserInitError: If parser creation fails
            ParserConfigError: If configuration is invalid
        """
        # Validate language exists
        if not self._registry.has_language(language):
            available = self._registry.list_languages()
            raise LanguageNotFoundError(language, available)

        # Validate config if provided
        if config:
            config.validate()

        # Generate cache key
        cache_key = language
        if config and (config.timeout_ms or config.included_ranges):
            # Don't cache configured parsers
            parser = self._create_parser(language)
            self._apply_config(parser, config)
            return parser

        # Check cache first
        parser = self._cache.get(cache_key)
        if parser:
            logger.debug(f"Retrieved parser for '{language}' from cache")
            return parser

        # Check pool
        pool = self._get_pool(language)
        parser = pool.get()
        if parser:
            logger.debug(f"Retrieved parser for '{language}' from pool")
            self._cache.put(cache_key, parser)
            return parser

        # Create new parser
        parser = self._create_parser(language)
        if config:
            self._apply_config(parser, config)

        # Add to cache
        self._cache.put(cache_key, parser)

        return parser

    def return_parser(self, language: str, parser: Parser) -> None:
        """Return a parser to the pool for reuse.

        Args:
            language: Language name
            parser: Parser instance to return
        """
        pool = self._get_pool(language)
        if pool.put(parser):
            logger.debug(f"Returned parser for '{language}' to pool")
        else:
            logger.debug(f"Pool for '{language}' is full, parser discarded")

    def clear_cache(self) -> None:
        """Clear the parser cache."""
        self._cache.clear()
        logger.info("Cleared parser cache")

    def get_stats(self) -> dict[str, Any]:
        """Get factory statistics.

        Returns:
            Dictionary with stats about parsers, cache, and pools
        """
        with self._lock:
            pool_stats = {
                lang: {
                    "size": pool.size(),
                    "created": pool.created_count,
                }
                for lang, pool in self._pools.items()
            }

            return {
                "total_parsers_created": self._parser_count,
                "cache_size": len(self._cache.cache),
                "pools": pool_stats,
            }
