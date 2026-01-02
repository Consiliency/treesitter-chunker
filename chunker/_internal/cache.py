"""Caching infrastructure for tree-sitter chunker.

This module provides SQLite-based caching for parsed ASTs and code chunks,
enabling significant performance improvements for repeated parsing operations.

Classes:
    ASTCache: Main cache implementation with integrity checking.

Example:
    cache = ASTCache(Path("~/.cache/chunker"))
    chunks = cache.get_cached_chunks(file_path, "python")
    if chunks is None:
        chunks = parse_file(file_path)
        cache.cache_chunks(file_path, "python", chunks)
"""

from __future__ import annotations

import hashlib
import logging
import pickle
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from chunker.types import CodeChunk

from .file_utils import get_file_metadata

logger = logging.getLogger(__name__)

# Cache version for compatibility checking
CACHE_VERSION = "1.0"


def _compute_checksum(data: bytes) -> str:
    """Compute SHA-256 checksum of data for integrity verification.

    Args:
        data: Bytes to compute checksum for.

    Returns:
        str: Hex-encoded SHA-256 checksum.
    """
    return hashlib.sha256(data).hexdigest()


def _verify_checksum(data: bytes, expected_checksum: str) -> bool:
    """Verify data integrity using checksum.

    Args:
        data: Bytes to verify.
        expected_checksum: Expected SHA-256 checksum.

    Returns:
        bool: True if checksum matches, False otherwise.
    """
    return _compute_checksum(data) == expected_checksum


class ASTCache:
    """SQLite-based cache for parsed AST chunks with file hashing."""

    def __init__(self, cache_dir: Path | None = None):
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "treesitter-chunker"
        cache_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = cache_dir / "ast_cache.db"
        self._init_db()

    def _init_db(self):
        """Initialize cache database schema."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS file_cache (
                        file_path TEXT NOT NULL,
                        file_hash TEXT NOT NULL,
                        file_size INTEGER NOT NULL,
                        mtime REAL NOT NULL,
                        language TEXT NOT NULL,
                        chunks_data BLOB NOT NULL,
                        data_checksum TEXT,
                        cache_version TEXT DEFAULT '1.0',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (file_path, language)
                    )
                """,
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_file_hash ON file_cache(file_hash)
                """,
                )
                # Add columns if they don't exist (migration for existing databases)
                try:
                    conn.execute(
                        "ALTER TABLE file_cache ADD COLUMN data_checksum TEXT",
                    )
                except sqlite3.OperationalError:
                    pass  # Column already exists
                try:
                    conn.execute(
                        "ALTER TABLE file_cache ADD COLUMN cache_version TEXT DEFAULT '1.0'",
                    )
                except sqlite3.OperationalError:
                    pass  # Column already exists
        except sqlite3.DatabaseError:
            # Database is corrupted, remove and recreate
            if self.db_path.exists():
                self.db_path.unlink()
            # Try again
            with self._get_connection() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS file_cache (
                        file_path TEXT NOT NULL,
                        file_hash TEXT NOT NULL,
                        file_size INTEGER NOT NULL,
                        mtime REAL NOT NULL,
                        language TEXT NOT NULL,
                        chunks_data BLOB NOT NULL,
                        data_checksum TEXT,
                        cache_version TEXT DEFAULT '1.0',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (file_path, language)
                    )
                """,
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_file_hash ON file_cache(file_hash)
                """,
                )

    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper cleanup."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def get_cached_chunks(self, path: Path, language: str) -> list[CodeChunk] | None:
        """Retrieve cached chunks if file hasn't changed.

        Includes integrity verification via checksum validation.
        """
        try:
            metadata = get_file_metadata(path)
        except OSError:
            return None

        with self._get_connection() as conn:
            result = conn.execute(
                """
                SELECT file_hash, mtime, chunks_data, data_checksum, cache_version
                FROM file_cache
                WHERE file_path = ? AND language = ?
            """,
                (str(path), language),
            ).fetchone()

            if result:
                cached_hash, cached_mtime, chunks_data, data_checksum, cache_version = (
                    result
                )
                # Check if file has changed
                if cached_hash == metadata.hash and cached_mtime == metadata.mtime:
                    # Verify cache version compatibility
                    if cache_version and cache_version != CACHE_VERSION:
                        logger.warning(
                            "Cache version mismatch for %s: got %s, expected %s",
                            path,
                            cache_version,
                            CACHE_VERSION,
                        )
                        self.invalidate_cache(path)
                        return None

                    # Verify data integrity with checksum
                    if data_checksum and not _verify_checksum(
                        chunks_data, data_checksum
                    ):
                        logger.warning(
                            "Cache checksum mismatch for %s - data may be corrupted",
                            path,
                        )
                        self.invalidate_cache(path)
                        return None

                    try:
                        # Deserialize chunks
                        chunks_dicts = pickle.loads(
                            chunks_data,
                        )
                        return [CodeChunk(**chunk_dict) for chunk_dict in chunks_dicts]
                    except (
                        pickle.UnpicklingError,
                        EOFError,
                        AttributeError,
                        ImportError,
                        IndexError,
                    ):
                        # Corrupted pickle data, invalidate this entry
                        logger.warning("Failed to unpickle cache data for %s", path)
                        self.invalidate_cache(path)
                        return None

        return None

    def cache_chunks(self, path: Path, language: str, chunks: list[CodeChunk]):
        """Cache chunks for a file with integrity checksum."""
        metadata = get_file_metadata(path)

        # Serialize chunks
        chunks_dicts = [asdict(chunk) for chunk in chunks]
        chunks_data = pickle.dumps(chunks_dicts)

        # Compute checksum for integrity verification
        data_checksum = _compute_checksum(chunks_data)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO file_cache
                (file_path, file_hash, file_size, mtime, language, chunks_data, data_checksum, cache_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    str(path),
                    metadata.hash,
                    metadata.size,
                    metadata.mtime,
                    language,
                    chunks_data,
                    data_checksum,
                    CACHE_VERSION,
                ),
            )

    def invalidate_cache(self, path: Path | None = None):
        """Invalidate cache for a specific file or all files."""
        with self._get_connection() as conn:
            if path:
                conn.execute("DELETE FROM file_cache WHERE file_path = ?", (str(path),))
            else:
                conn.execute("DELETE FROM file_cache")

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        with self._get_connection() as conn:
            total_files = conn.execute("SELECT COUNT(*) FROM file_cache").fetchone()[0]
            total_size = (
                conn.execute("SELECT SUM(file_size) FROM file_cache").fetchone()[0] or 0
            )

            return {
                "total_files": total_files,
                "total_size_bytes": total_size,
                "cache_db_size": (
                    self.db_path.stat().st_size if self.db_path.exists() else 0
                ),
            }
