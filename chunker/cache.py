from __future__ import annotations

import pickle
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path

from .streaming import get_file_metadata
from .types import CodeChunk


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
        """Retrieve cached chunks if file hasn't changed."""
        try:
            metadata = get_file_metadata(path)
        except OSError:
            return None

        with self._get_connection() as conn:
            result = conn.execute(
                """
                SELECT file_hash, mtime, chunks_data 
                FROM file_cache 
                WHERE file_path = ? AND language = ?
            """,
                (str(path), language),
            ).fetchone()

            if result:
                cached_hash, cached_mtime, chunks_data = result
                # Check if file has changed
                if cached_hash == metadata.hash and cached_mtime == metadata.mtime:
                    try:
                        # Deserialize chunks
                        chunks_dicts = pickle.loads(chunks_data)
                        return [CodeChunk(**chunk_dict) for chunk_dict in chunks_dicts]
                    except (
                        pickle.UnpicklingError,
                        EOFError,
                        AttributeError,
                        ImportError,
                        IndexError,
                    ):
                        # Corrupted pickle data, invalidate this entry
                        self.invalidate_cache(path)
                        return None

        return None

    def cache_chunks(self, path: Path, language: str, chunks: list[CodeChunk]):
        """Cache chunks for a file."""
        metadata = get_file_metadata(path)

        # Serialize chunks
        chunks_dicts = [asdict(chunk) for chunk in chunks]
        chunks_data = pickle.dumps(chunks_dicts)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO file_cache 
                (file_path, file_hash, file_size, mtime, language, chunks_data)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    str(path),
                    metadata.hash,
                    metadata.size,
                    metadata.mtime,
                    language,
                    chunks_data,
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
