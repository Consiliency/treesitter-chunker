"""Caching infrastructure for tree-sitter chunker.

This module provides SQLite-based caching for extracted code chunks,
enabling significant performance improvements for repeated parsing operations.

Classes:
    ASTCache: Main cache implementation with integrity checking.

Each entry is keyed by file path, language and an extraction identity: the
extraction mode (``"core"`` or ``"streaming"``), the chunker, Tree-sitter and
language-pack versions, the loaded grammar's ABI, node count, symbol and
provenance, and a fingerprint of the effective language configuration and
metadata extractors. When the grammar has no recorded provenance (today, every
language except Python and JavaScript) or the configuration cannot be
fingerprinted, there is no identity and the cache is bypassed: nothing is read
or written for that language.

Example:
    cache = ASTCache(Path("~/.cache/chunker"))
    chunks = cache.get_cached_chunks(file_path, "python")
    if chunks is None:
        chunks = parse_file(file_path)
        cache.cache_chunks(file_path, "python", chunks)
"""

from __future__ import annotations

import hashlib
import json
import logging
import pickle
import sqlite3
from contextlib import contextmanager
from dataclasses import asdict, is_dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from chunker.types import CodeChunk

from .file_utils import get_file_metadata

logger = logging.getLogger(__name__)

# Cache version for compatibility checking. 3.0 moved entries to the
# ``chunk_cache`` table keyed by extraction identity (treesitter-chunker#358).
CACHE_VERSION = "3.0"

#: Extraction modes whose chunk output the cache keeps apart.
EXTRACTION_MODES = frozenset({"core", "streaming"})

_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS chunk_cache (
        file_path TEXT NOT NULL,
        language TEXT NOT NULL,
        extraction TEXT NOT NULL,
        extraction_identity TEXT NOT NULL,
        file_hash TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        mtime REAL NOT NULL,
        chunks_data BLOB NOT NULL,
        data_checksum TEXT NOT NULL,
        cache_version TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (file_path, language, extraction_identity)
    )
"""
_INDEX_SQL = "CREATE INDEX IF NOT EXISTS idx_chunk_cache_hash ON chunk_cache(file_hash)"


def _distribution_version(distribution: str) -> str | None:
    try:
        return version(distribution)
    except PackageNotFoundError:
        return None


class _UnidentifiableError(Exception):
    """Raised while fingerprinting state that has no reliable identity."""


def _code_identity(cls: type) -> str:
    """Name chunker-owned code; code outside the package is not identified."""
    module = getattr(cls, "__module__", "") or ""
    if module != "chunker" and not module.startswith("chunker."):
        raise _UnidentifiableError(f"{module}.{cls.__qualname__}")
    return f"{module}:{cls.__qualname__}"


def _stable_state(value: object) -> object:
    """Return a JSON-stable form of configuration state, or raise."""
    from chunker.languages.base import LanguageConfig

    if value is None or isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, set | frozenset):
        items = [_stable_state(item) for item in value]
        return {"set": sorted(items, key=lambda item: json.dumps(item, sort_keys=True))}
    if isinstance(value, list | tuple):
        return [_stable_state(item) for item in value]
    if isinstance(value, dict):
        if not all(isinstance(key, str) for key in value):
            raise _UnidentifiableError("non-string mapping key")
        return {key: _stable_state(item) for key, item in value.items()}
    if isinstance(value, LanguageConfig) or (
        is_dataclass(value) and not isinstance(value, type)
    ):
        return {
            "class": _code_identity(type(value)),
            "state": _stable_state(vars(value)),
        }
    raise _UnidentifiableError(type(value).__qualname__)


def _configuration_fingerprint(language: str) -> object:
    """Fingerprint the language configuration and extractors chunking consults.

    Raises:
        _UnidentifiableError: If any of them is code outside the chunker package or
            holds state (for example a function) without a stable value.
    """
    from chunker.languages import language_config_registry
    from chunker.metadata import MetadataExtractorFactory

    config = language_config_registry.get(language)
    extractor = MetadataExtractorFactory._extractors.get(language.lower())
    analyzer = MetadataExtractorFactory._analyzers.get(language.lower())
    return {
        "language_config": None if config is None else _stable_state(config),
        "extractor": None if extractor is None else _code_identity(extractor),
        "analyzer": None if analyzer is None else _code_identity(analyzer),
    }


def chunk_cache_identity(language: str, extraction: str = "core") -> str | None:
    """Return the cache identity for ``language`` chunks extracted in ``extraction`` mode.

    The identity is a SHA-256 over the cache version, the extraction mode, the
    installed chunker, Tree-sitter and language-pack versions, the selected
    grammar's ABI version, node-kind count, symbol name and provenance (for
    example ``official:tree-sitter-python@0.25.0``), and a fingerprint of the
    effective language configuration and metadata extractor classes. Loading
    the grammar to read this metadata is the same load extraction performs.

    Returns ``None`` when there is no reliable identity: the selected grammar
    has no recorded provenance (the registry records it only for Python and
    JavaScript), or the configuration includes code outside the chunker
    package or state without a stable value. Callers must then bypass the
    cache.

    Raises:
        ValueError: If ``extraction`` is not one of :data:`EXTRACTION_MODES`.
        LanguageNotFoundError, ParserError: If the grammar cannot be loaded.
    """
    if extraction not in EXTRACTION_MODES:
        msg = (
            f"Unknown extraction mode {extraction!r}; "
            f"expected one of {sorted(EXTRACTION_MODES)}"
        )
        raise ValueError(msg)
    from chunker.parser import get_language_info

    metadata = get_language_info(language)
    source = metadata.capabilities.get("grammar_source")
    if not isinstance(source, str) or not source:
        return None
    try:
        configuration = _configuration_fingerprint(language)
    except _UnidentifiableError as reason:
        logger.debug(
            "No chunk-cache identity for %s configuration: %s", language, reason
        )
        return None
    payload = {
        "cache_version": CACHE_VERSION,
        "extraction": extraction,
        "language": language,
        "tool": _distribution_version("treesitter-chunker"),
        "tree_sitter": _distribution_version("tree-sitter"),
        "language_pack": _distribution_version("tree-sitter-language-pack"),
        "grammar": {
            "abi": metadata.version,
            "node_kinds": metadata.node_types_count,
            "symbol": metadata.symbol_name,
            "source": source,
        },
        "configuration": configuration,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _identity_or_none(language: str, extraction: str) -> str | None:
    """Return the identity, or ``None`` if the grammar cannot be identified."""
    from chunker.exceptions import ChunkerError

    try:
        return chunk_cache_identity(language, extraction)
    except ChunkerError:
        return None


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
    """SQLite-based cache for extracted chunks with file hashing.

    Entries written before cache version 3.0 live in the legacy ``file_cache``
    table. They are never read or modified; delete ``ast_cache.db`` to reclaim
    their space once no older chunker release shares the directory.
    """

    def __init__(self, cache_dir: Path | None = None):
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "treesitter-chunker"
        cache_dir.mkdir(parents=True, exist_ok=True)

        self.db_path = cache_dir / "ast_cache.db"
        self._init_db()

    def _create_schema(self) -> None:
        with self._get_connection() as conn:
            conn.execute(_TABLE_SQL)
            conn.execute(_INDEX_SQL)

    def _init_db(self):
        """Initialize cache database schema."""
        try:
            self._create_schema()
        except sqlite3.DatabaseError as exc:
            if getattr(exc, "sqlite_errorcode", 0) & 0xFF not in (
                sqlite3.SQLITE_CORRUPT,
                sqlite3.SQLITE_NOTADB,
            ):
                raise
            # Database is corrupted, remove and recreate
            if self.db_path.exists():
                self.db_path.unlink()
            self._create_schema()

    @contextmanager
    def _get_connection(self):
        """Get a database connection with proper cleanup."""
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def get_cached_chunks(
        self,
        path: Path,
        language: str,
        *,
        extraction: str = "core",
    ) -> list[CodeChunk] | None:
        """Return cached chunks for an unchanged file and matching identity.

        ``extraction`` names the mode that produced the chunks (``"core"`` for
        :func:`chunker.chunk_file`, ``"streaming"`` for
        :func:`chunker.streaming.chunk_file_streaming`). Entries from another
        mode or identity are not returned. Without an identity (see
        :func:`chunk_cache_identity`), or when the grammar cannot be loaded,
        nothing is read and this returns ``None``, so the caller extracts.
        Includes integrity verification via checksum validation.
        """
        identity = _identity_or_none(language, extraction)
        if identity is None:
            return None
        try:
            metadata = get_file_metadata(path)
        except OSError:
            return None

        with self._get_connection() as conn:
            result = conn.execute(
                """
                SELECT file_hash, mtime, chunks_data, data_checksum, cache_version
                FROM chunk_cache
                WHERE file_path = ? AND language = ? AND extraction_identity = ?
            """,
                (str(path), language, identity),
            ).fetchone()

        if not result:
            return None
        cached_hash, cached_mtime, chunks_data, data_checksum, cache_version = result
        # Check if file has changed
        if cached_hash != metadata.hash or cached_mtime != metadata.mtime:
            return None
        if cache_version != CACHE_VERSION:
            logger.warning(
                "Cache version mismatch for %s: got %s, expected %s",
                path,
                cache_version,
                CACHE_VERSION,
            )
            self._delete_entry(path, language, identity)
            return None
        # Verify data integrity with checksum
        if not _verify_checksum(chunks_data, data_checksum):
            logger.warning(
                "Cache checksum mismatch for %s - data may be corrupted",
                path,
            )
            self._delete_entry(path, language, identity)
            return None
        try:
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
            logger.warning("Failed to unpickle cache data for %s", path)
            self._delete_entry(path, language, identity)
            return None

    def cache_chunks(
        self,
        path: Path,
        language: str,
        chunks: list[CodeChunk],
        *,
        extraction: str = "core",
    ) -> bool:
        """Cache chunks produced by ``extraction`` mode with an integrity checksum.

        Returns ``False`` without writing when there is no identity (see
        :func:`chunk_cache_identity`) or the grammar cannot be loaded. A write
        also removes this file's entries for the same language and mode under
        any older identity.
        """
        identity = _identity_or_none(language, extraction)
        if identity is None:
            return False
        metadata = get_file_metadata(path)

        # Serialize chunks
        chunks_dicts = [asdict(chunk) for chunk in chunks]
        chunks_data = pickle.dumps(chunks_dicts)

        # Compute checksum for integrity verification
        data_checksum = _compute_checksum(chunks_data)

        with self._get_connection() as conn:
            conn.execute(
                """
                DELETE FROM chunk_cache
                WHERE file_path = ? AND language = ? AND extraction = ?
                AND extraction_identity <> ?
            """,
                (str(path), language, extraction, identity),
            )
            conn.execute(
                """
                INSERT OR REPLACE INTO chunk_cache
                (file_path, language, extraction, extraction_identity, file_hash,
                 file_size, mtime, chunks_data, data_checksum, cache_version)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    str(path),
                    language,
                    extraction,
                    identity,
                    metadata.hash,
                    metadata.size,
                    metadata.mtime,
                    chunks_data,
                    data_checksum,
                    CACHE_VERSION,
                ),
            )
        return True

    def _delete_entry(self, path: Path, language: str, identity: str) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                DELETE FROM chunk_cache
                WHERE file_path = ? AND language = ? AND extraction_identity = ?
            """,
                (str(path), language, identity),
            )

    def invalidate_cache(self, path: Path | None = None):
        """Invalidate every entry for a specific file, or all entries."""
        with self._get_connection() as conn:
            if path:
                conn.execute(
                    "DELETE FROM chunk_cache WHERE file_path = ?", (str(path),)
                )
            else:
                conn.execute("DELETE FROM chunk_cache")

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        with self._get_connection() as conn:
            total_files = conn.execute("SELECT COUNT(*) FROM chunk_cache").fetchone()[0]
            total_size = (
                conn.execute("SELECT SUM(file_size) FROM chunk_cache").fetchone()[0]
                or 0
            )

            return {
                "total_files": total_files,
                "total_size_bytes": total_size,
                "cache_db_size": (
                    self.db_path.stat().st_size if self.db_path.exists() else 0
                ),
            }
