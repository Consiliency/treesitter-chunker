"""Enhanced chunker with performance optimizations."""

import logging
from pathlib import Path
from typing import Any

from chunker.chunker import _walk
from chunker.types import CodeChunk

from .cache.manager import CacheManager
from .optimization.incremental import IncrementalParser
from .optimization.memory_pool import MemoryPool
from .optimization.monitor import PerformanceMonitor

logger = logging.getLogger(__name__)


class EnhancedChunker:
    """High-performance chunker with caching and incremental parsing.

    This class provides:
    - Multi-level caching for ASTs and chunks
    - Incremental parsing for file changes
    - Parser pooling for efficiency
    - Performance monitoring
    """

    def __init__(
        self,
        cache_manager: CacheManager | None = None,
        memory_pool: MemoryPool | None = None,
        performance_monitor: PerformanceMonitor | None = None,
        enable_incremental: bool = True,
    ):
        """Initialize enhanced chunker.

        Args:
            cache_manager: Cache manager instance
            memory_pool: Memory pool for parsers
            performance_monitor: Performance monitor
            enable_incremental: Enable incremental parsing
        """
        self._cache = cache_manager or CacheManager()
        self._pool = memory_pool or MemoryPool()
        self._monitor = performance_monitor or PerformanceMonitor()
        self._incremental_parser = IncrementalParser() if enable_incremental else None
        self._file_state: dict[str, dict[str, Any]] = (
            {}
        )  # Track file state for incremental

        logger.info(
            "Initialized EnhancedChunker with caching and performance optimizations",
        )

    def chunk_file(
        self,
        path: str | Path,
        language: str,
        force_reparse: bool = False,
    ) -> list[CodeChunk]:
        """Parse file with caching and performance optimizations.

        Args:
            path: File path
            language: Programming language
            force_reparse: Force re-parsing even if cached

        Returns:
            List of code chunks
        """
        file_path = str(path)

        with self._monitor.measure("enhanced_chunk_file"):
            # Read file content
            src = Path(path).read_bytes()
            source_hash = CacheManager.compute_source_hash(src)

            # Check chunk cache first (fastest)
            if not force_reparse:
                cached_chunks = self._cache.get_cached_chunks(file_path, source_hash)
                if cached_chunks is not None:
                    self._monitor.record_metric("cache.chunk_hits", 1)
                    logger.debug("Returning cached chunks for %s", file_path)
                    return cached_chunks

            self._monitor.record_metric("cache.chunk_misses", 1)

            # Check AST cache
            cached_ast_data = None
            if not force_reparse:
                cached_ast_data = self._cache.get_cached_ast(file_path, source_hash)

            if cached_ast_data is not None:
                # Use cached AST
                self._monitor.record_metric("cache.ast_hits", 1)
                tree = cached_ast_data["ast"]
                parse_time_ms = 0  # No parsing needed
                logger.debug("Using cached AST for %s", file_path)
            else:
                # Parse the file
                self._monitor.record_metric("cache.ast_misses", 1)
                tree, parse_time_ms = self._parse_file(file_path, src, language)

                # Cache the AST
                self._cache.cache_ast(
                    file_path,
                    source_hash,
                    tree,
                    language,
                    parse_time_ms,
                )

            # Generate chunks
            with self._monitor.measure("chunk_generation"):
                chunks = self._generate_chunks(tree.root_node, src, language, file_path)

            # Cache the chunks
            self._cache.cache_chunks(file_path, source_hash, chunks)

            # Update file state for incremental parsing
            if self._incremental_parser:
                self._file_state[file_path] = {
                    "tree": tree,
                    "source": src,
                    "source_hash": source_hash,
                    "chunks": chunks,
                }

            return chunks

    def chunk_file_incremental(
        self,
        path: str | Path,
        language: str,
    ) -> list[CodeChunk]:
        """Parse file incrementally if it has changed.

        This method uses Tree-sitter's incremental parsing to efficiently
        handle file changes.

        Args:
            path: File path
            language: Programming language

        Returns:
            List of code chunks
        """
        if not self._incremental_parser:
            # Fall back to regular parsing
            return self.chunk_file(path, language)

        file_path = str(path)

        with self._monitor.measure("incremental_chunk_file"):
            # Read current file content
            new_source = Path(path).read_bytes()
            new_hash = CacheManager.compute_source_hash(new_source)

            # Check if we have previous state
            if file_path not in self._file_state:
                # First time parsing this file
                return self.chunk_file(path, language)

            old_state = self._file_state[file_path]

            # Check if file actually changed
            if old_state["source_hash"] == new_hash:
                # No change, return cached chunks
                self._monitor.record_metric("incremental.no_change", 1)
                return old_state["chunks"]

            # Detect changes
            old_source = old_state["source"]
            old_tree = old_state["tree"]

            with self._monitor.measure("detect_changes"):
                changes = self._incremental_parser.detect_changes(
                    old_source,
                    new_source,
                )

            if not changes:
                # No structural changes despite hash difference
                return self.chunk_file(path, language, force_reparse=True)

            # Parse incrementally
            with self._monitor.measure("incremental_parse"):
                new_tree = self._incremental_parser.parse_incremental(
                    old_tree,
                    new_source,
                    changes,
                )

            # Update chunks incrementally
            with self._monitor.measure("incremental_chunk_update"):
                new_chunks = self._incremental_parser.update_chunks(
                    old_state["chunks"],
                    old_tree,
                    new_tree,
                    changes,
                )

            # For areas that need re-chunking, generate new chunks
            if len(new_chunks) < len(old_state["chunks"]):
                # Some chunks were removed, need to re-chunk affected areas
                with self._monitor.measure("incremental_rechunk"):
                    full_chunks = self._generate_chunks(
                        new_tree.root_node,
                        new_source,
                        language,
                        file_path,
                    )
                    new_chunks = full_chunks

            # Update caches
            self._cache.cache_ast(file_path, new_hash, new_tree, language, 0)
            self._cache.cache_chunks(file_path, new_hash, new_chunks)

            # Update file state
            self._file_state[file_path] = {
                "tree": new_tree,
                "source": new_source,
                "source_hash": new_hash,
                "chunks": new_chunks,
            }

            self._monitor.record_metric("incremental.success", 1)
            logger.info("Incremental parse of %s: %s changes", file_path, len(changes))

            return new_chunks

    def _parse_file(self, file_path: str, source: bytes, language: str) -> tuple:
        """Parse a file and return tree with timing.

        Args:
            file_path: Path to file
            source: File content
            language: Programming language

        Returns:
            Tuple of (tree, parse_time_ms)
        """
        # Get parser from pool
        parser = self._pool.acquire_parser(language)

        try:
            # Parse with timing
            op_id = self._monitor.start_operation("parse_file")
            tree = parser.parse(source)
            parse_time_ms = self._monitor.end_operation(op_id)

            logger.debug("Parsed %s in %sms", file_path, parse_time_ms:.2f)

            return tree, parse_time_ms

        finally:
            # Return parser to pool
            self._pool.release_parser(parser, language)

    def _generate_chunks(
        self,
        root_node,
        source: bytes,
        language: str,
        file_path: str,
    ) -> list[CodeChunk]:
        """Generate chunks from AST.

        Args:
            root_node: Root node of AST
            source: Source code bytes
            language: Programming language
            file_path: Path to file

        Returns:
            List of chunks
        """
        chunks = _walk(root_node, source, language)

        # Set file paths
        for chunk in chunks:
            chunk.file_path = file_path

        self._monitor.record_metric("chunks.generated", len(chunks))

        return chunks

    def invalidate_file(self, path: str | Path) -> None:
        """Invalidate all caches for a file.

        Args:
            path: File path
        """
        file_path = str(path)

        # Clear from cache
        count = self._cache.invalidate_file(file_path)

        # Clear from incremental state
        if file_path in self._file_state:
            del self._file_state[file_path]

        logger.info("Invalidated %s cache entries for %s", count, file_path)

    def get_stats(self) -> dict[str, Any]:
        """Get performance statistics.

        Returns:
            Dictionary of statistics
        """
        stats = {
            "cache": self._cache.get_stats(),
            "pool": self._pool.get_stats(),
            "metrics": self._monitor.get_metrics(),
            "incremental_files": len(self._file_state),
        }

        return stats

    def warm_up(self, languages: list[str]) -> None:
        """Pre-warm caches and pools.

        Args:
            languages: List of languages to prepare for
        """
        logger.info("Warming up for languages: %s", languages)

        # Pre-create parsers
        for language in languages:
            self._pool.warm_up(f"parser:{language}", 2)

        # Could also pre-load common files here

    def clear_caches(self) -> None:
        """Clear all caches and reset state."""
        self._cache.clear()
        self._file_state.clear()
        self._monitor.reset()
        logger.info("Cleared all caches and state")
