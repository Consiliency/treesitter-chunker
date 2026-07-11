"""Parser factory with caching and pooling for efficient parser management."""

from __future__ import annotations

import logging
import re
import threading
from collections import OrderedDict
from dataclasses import dataclass
from queue import Empty, Full, Queue
from typing import TYPE_CHECKING, Any

from tree_sitter import Parser, Range

from chunker.exceptions import LanguageNotFoundError, ParserConfigError, ParserInitError

if TYPE_CHECKING:
    from chunker._internal.registry import LanguageRegistry
logger = logging.getLogger(__name__)


@dataclass
class ParserConfig:
    """Configuration options for parser instances."""

    timeout_ms: int | None = None
    included_ranges: list[Range] | None = None
    logger: logging.Logger | None = None

    def validate(self):
        """Validate configuration values."""
        if self.timeout_ms is not None and (
            not isinstance(self.timeout_ms, int) or self.timeout_ms < 0
        ):
            raise ParserConfigError(
                "timeout_ms",
                self.timeout_ms,
                "Must be a non-negative integer",
            )
        if self.included_ranges is not None and not isinstance(
            self.included_ranges,
            list,
        ):
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
            self.cache.move_to_end(key)
            return self.cache[key]

    def pop(self, key: str) -> Parser | None:
        """Remove and return an idle parser from the cache."""
        with self.lock:
            return self.cache.pop(key, None)

    def put(self, key: str, value: Parser) -> None:
        """Add item to cache, evicting LRU item if needed."""
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
            else:
                if len(self.cache) >= self.maxsize:
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
        except Full:
            return False

    def size(self) -> int:
        """Get current pool size."""
        return self.pool.qsize()


class ParserLease:
    """Exclusive checkout of a parser managed by :class:`ParserFactory`."""

    def __init__(
        self,
        factory: ParserFactory,
        language: str,
        parser: Parser,
        *,
        reusable: bool,
    ) -> None:
        self._factory = factory
        self._language = language
        self._parser: Parser | None = parser
        self._reusable = reusable

    def __enter__(self) -> Parser:
        if self._parser is None:
            raise RuntimeError("Parser lease has already been released")
        return self._parser

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.release()

    def release(self) -> None:
        """Return this parser to the factory once, if it is reusable."""
        if self._parser is not None:
            self._factory._release_parser(
                self._language,
                self._parser,
                reusable=self._reusable,
            )
            self._parser = None


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
        self._thread_local = threading.local()
        self._cache_generation = 0
        self._parser_count = 0
        logger.info(
            "Initialized ParserFactory with cache_size=%d, pool_size=%d",
            cache_size,
            pool_size,
        )

    def _create_parser(self, language: str) -> Parser:
        """Create a new parser instance for the language."""
        try:
            lang = self._registry.get_language(language)
            parser = Parser()
            parser.language = lang
            self._parser_count += 1
            logger.debug(
                "Created new parser for '%s' (total: %d)",
                language,
                self._parser_count,
            )
            return parser
        except ValueError as e:
            if "Incompatible Language version" in str(e):
                # Try using tree-sitter-language-pack as a fallback
                try:
                    from tree_sitter_language_pack import get_parser as get_pack_parser

                    logger.info(
                        "Grammar version incompatible, falling back to tree-sitter-language-pack for '%s'",
                        language,
                    )
                    parser = get_pack_parser(language)
                    self._parser_count += 1
                    logger.debug(
                        "Created parser from language pack for '%s' (total: %d)",
                        language,
                        self._parser_count,
                    )
                    return parser
                except Exception as pack_error:
                    match = re.search(
                        r"version (\d+)\. Must be between (\d+) and (\d+)",
                        str(e),
                    )
                    if match:
                        grammar_ver, min_ver, max_ver = match.groups()
                        raise ParserInitError(
                            language,
                            f"Grammar compiled with language version {grammar_ver}, but tree-sitter library supports versions {min_ver}-{max_ver}. "
                            f"Fallback to tree-sitter-language-pack also failed: {pack_error}",
                        ) from e
                    raise ParserInitError(language, str(e)) from e
            raise ParserInitError(language, str(e)) from e
        except Exception as e:
            raise ParserInitError(language, str(e)) from e

    def _get_pool(self, language: str) -> ParserPool:
        """Get or create a parser pool for the language."""
        with self._lock:
            if language not in self._pools:
                self._pools[language] = ParserPool(language, self._pool_size)
            return self._pools[language]

    @staticmethod
    def _apply_config(parser: Parser, config: ParserConfig) -> None:
        """Apply configuration to a parser instance."""
        if config.timeout_ms is not None:
            timeout_micros = config.timeout_ms * 1000
            if hasattr(parser, "set_timeout_micros"):
                parser.set_timeout_micros(timeout_micros)
            elif hasattr(parser, "timeout_micros"):
                parser.timeout_micros = timeout_micros
        if config.included_ranges is not None:
            parser.included_ranges = config.included_ranges
        if config.logger is not None:
            pass

    def _validate_request(
        self,
        language: str,
        config: ParserConfig | None,
    ) -> None:
        if not self._registry.has_language(language):
            available = self._registry.list_languages()
            raise LanguageNotFoundError(language, available)
        if config:
            config.validate()

    def _thread_parsers(self) -> dict[str, Parser]:
        if getattr(self._thread_local, "generation", None) != self._cache_generation:
            self._thread_local.parsers = {}
            self._thread_local.generation = self._cache_generation
        return self._thread_local.parsers

    def get_parser(
        self,
        language: str,
        config: ParserConfig | None = None,
    ) -> Parser:
        """Get a parser owned exclusively by the calling thread.

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
        self._validate_request(language, config)
        if config is not None:
            parser = self._create_parser(language)
            self._apply_config(parser, config)
            return parser
        with self._lock:
            parsers = self._thread_parsers()
            parser = parsers.get(language)
            if parser is None:
                parser = self._create_parser(language)
                parsers[language] = parser
            return parser

    def acquire_parser(
        self,
        language: str,
        config: ParserConfig | None = None,
    ) -> ParserLease:
        """Exclusively lease a parser until the returned lease is released."""
        self._validate_request(language, config)
        with self._lock:
            parser = self._cache.pop(language)
            if parser is None:
                parser = self._get_pool(language).get()
            if parser is None:
                parser = self._create_parser(language)
            if config is not None:
                self._apply_config(parser, config)
            return ParserLease(
                self,
                language,
                parser,
                reusable=config is None,
            )

    def _release_parser(
        self,
        language: str,
        parser: Parser,
        *,
        reusable: bool,
    ) -> None:
        with self._lock:
            if not reusable:
                logger.debug(
                    "Discarded configured parser for '%s' after lease", language
                )
                return
            if self._cache.get(language) is None:
                self._cache.put(language, parser)
                logger.debug("Returned parser for '%s' to cache", language)
                return
            if self._get_pool(language).put(parser):
                logger.debug("Returned parser for '%s' to pool", language)
            else:
                logger.debug("Pool for '%s' is full, parser discarded", language)

    def return_parser(self, language: str, parser: Parser) -> None:
        """Accept the legacy return call without sharing a raw parser.

        Args:
            language: Language name
            parser: Parser instance to return
        """
        logger.debug(
            "Ignored legacy return_parser call for '%s'; use acquire_parser for leases",
            language,
        )

    def clear_cache(self) -> None:
        """Clear the parser cache."""
        with self._lock:
            self._cache.clear()
            self._pools.clear()
            self._cache_generation += 1
        logger.info("Cleared parser cache")

    def get_stats(self) -> dict[str, Any]:
        """Get factory statistics.

        Returns:
            Dictionary with stats about parsers, cache, and pools
        """
        with self._lock:
            pool_stats = {
                lang: {"size": pool.size(), "created": pool.created_count}
                for lang, pool in self._pools.items()
            }
            return {
                "total_parsers_created": self._parser_count,
                "cache_size": len(self._cache.cache),
                "pools": pool_stats,
            }
