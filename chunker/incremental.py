"""Incremental processing implementation for efficient chunk updates."""

import difflib
import hashlib
import json
import math
import pickle
from bisect import bisect_right
from collections import Counter, defaultdict
from dataclasses import fields
from datetime import datetime
from operator import itemgetter
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, get_type_hints

from .chunker import chunk_text
from .interfaces.incremental import (
    CacheEntry,
    ChangeDetector,
    ChangeType,
    ChunkCache,
    ChunkChange,
    ChunkDiff,
    IncrementalIndex,
    IncrementalProcessor,
)
from .types import CodeChunk


class DefaultIncrementalProcessor(IncrementalProcessor):
    """Default implementation of incremental processing."""

    def __init__(self):
        """Initialize processor."""
        self.change_detector = DefaultChangeDetector()
        self.file_chunks: dict[str, list[CodeChunk]] = {}
        # Maintain a baseline snapshot used for (file_path, new_chunks) API diffs
        self._baseline: dict[str, list[CodeChunk]] = {}

    def store_chunks(self, file_path: str, chunks: list[CodeChunk]) -> None:
        """Store chunks for a file path."""
        self.file_chunks[str(file_path)] = chunks
        # Initialize baseline if not set to avoid spurious additions on first diff
        self._baseline.setdefault(str(file_path), chunks)

    def compute_diff(
        self,
        file_path_or_old_chunks: str | list[CodeChunk],
        new_chunks_or_content: list[CodeChunk] | str,
        language: str | None = None,
    ) -> ChunkDiff:
        """Compute difference - supports both file path and direct chunk APIs."""
        # Handle file path API: compute_diff(file_path, new_chunks)
        if isinstance(file_path_or_old_chunks, (str, Path)) and isinstance(
            new_chunks_or_content,
            list,
        ):
            file_path = str(file_path_or_old_chunks)
            new_chunks = new_chunks_or_content
            # Use latest if present; otherwise use baseline; both default to []
            old_chunks = self.file_chunks.get(
                file_path,
                self._baseline.get(file_path, []),
            )

            # Convert new chunks to old/new content format for diff
            if not old_chunks and not new_chunks:
                return ChunkDiff([], [], [], [], [], {})

            diff = self._compute_chunks_diff(old_chunks, new_chunks)
            # Promote new state into both latest and baseline for idempotent subsequent diffs
            self.file_chunks[file_path] = new_chunks
            self._baseline[file_path] = new_chunks
            return diff

        # Handle original API: compute_diff(old_chunks, new_content, language)
        if isinstance(file_path_or_old_chunks, list) and isinstance(
            new_chunks_or_content,
            str,
        ):
            if not language:
                raise ValueError("Language is required when using content-based diff")
            return self._compute_content_diff(
                file_path_or_old_chunks,
                new_chunks_or_content,
                language,
            )
        # Back-compat: handle (file_path_str, content_str, language)
        if isinstance(file_path_or_old_chunks, (str, Path)) and isinstance(
            new_chunks_or_content,
            str,
        ):
            if not language:
                raise ValueError("Language is required when using content-based diff")
            old_chunks = self.file_chunks.get(str(file_path_or_old_chunks), [])
            return self._compute_content_diff(
                old_chunks,
                new_chunks_or_content,
                language,
                str(file_path_or_old_chunks),
            )
        raise ValueError(
            "Invalid arguments: expected (file_path, new_chunks) or (old_chunks, new_content, language)",
        )

    @staticmethod
    def _identity_key(chunk: CodeChunk) -> str:
        return chunk.definition_id or chunk.chunk_id

    @classmethod
    def _identity_maps(
        cls, old_chunks: list[CodeChunk], new_chunks: list[CodeChunk]
    ) -> tuple[dict[str, CodeChunk], dict[str, CodeChunk]]:
        # A repeated definition route is not sufficient to identify an overload.
        # Use occurrence IDs on BOTH sides when either side has a collision.
        collisions = {
            key
            for chunks in (old_chunks, new_chunks)
            for key, count in Counter(cls._identity_key(c) for c in chunks).items()
            if count > 1
        }

        def keyed(chunks: list[CodeChunk]) -> dict[str, CodeChunk]:
            return {
                (
                    "occurrence:" + chunk.chunk_id
                    if cls._identity_key(chunk) in collisions
                    else "definition:" + cls._identity_key(chunk)
                ): chunk
                for chunk in chunks
            }

        return keyed(old_chunks), keyed(new_chunks)

    @staticmethod
    def _occurrence_fields(chunk: CodeChunk) -> tuple[str, str, str, int, int]:
        """Index key and row fields that can differ for identical content."""
        return (
            chunk.chunk_id,
            chunk.file_path,
            chunk.node_type,
            chunk.start_line,
            chunk.end_line,
        )

    def _compute_chunks_diff(
        self,
        old_chunks: list[CodeChunk],
        new_chunks: list[CodeChunk],
    ) -> ChunkDiff:
        """Compute diff between two chunk lists."""
        old_map, new_map = self._identity_maps(old_chunks, new_chunks)

        old_ids = set(old_map.keys())
        new_ids = set(new_map.keys())
        unchanged_ids = old_ids & new_ids

        occurrence_updates = []
        unchanged_chunks = []
        modified_chunks = []

        for chunk_id in unchanged_ids:
            old_chunk = old_map[chunk_id]
            new_chunk = new_map[chunk_id]
            if old_chunk.content != new_chunk.content:
                modified_chunks.append((old_chunk, new_chunk))
            else:
                unchanged_chunks.append(new_chunk)
                if self._occurrence_fields(old_chunk) != self._occurrence_fields(
                    new_chunk
                ):
                    occurrence_updates.append((old_chunk, new_chunk))

        added_ids = new_ids - old_ids
        deleted_ids = old_ids - new_ids

        added_chunks = [new_map[chunk_id] for chunk_id in added_ids]
        deleted_chunks = [old_map[chunk_id] for chunk_id in deleted_ids]

        changes = []

        # Add changes for added chunks
        for chunk in added_chunks:
            changes.append(
                ChunkChange(
                    chunk_id=chunk.chunk_id,
                    change_type=ChangeType.ADDED,
                    old_chunk=None,
                    new_chunk=chunk,
                    line_changes=[(chunk.start_line, chunk.end_line)],
                    confidence=1.0,
                ),
            )

        # Add changes for deleted chunks
        for chunk in deleted_chunks:
            changes.append(
                ChunkChange(
                    chunk_id=chunk.chunk_id,
                    change_type=ChangeType.DELETED,
                    old_chunk=chunk,
                    new_chunk=None,
                    line_changes=[(chunk.start_line, chunk.end_line)],
                    confidence=1.0,
                ),
            )

        # Add changes for modified chunks
        for old_chunk, new_chunk in modified_chunks:
            changes.append(
                ChunkChange(
                    chunk_id=new_chunk.chunk_id,
                    change_type=ChangeType.MODIFIED,
                    old_chunk=old_chunk,
                    new_chunk=new_chunk,
                    line_changes=[(new_chunk.start_line, new_chunk.end_line)],
                    confidence=0.9,
                ),
            )

        summary = {
            "total_old_chunks": len(old_chunks),
            "total_new_chunks": len(new_chunks),
            "added": len(added_chunks),
            "deleted": len(deleted_chunks),
            "modified": len(modified_chunks),
            "unchanged": len(unchanged_chunks),
        }
        diff = ChunkDiff(
            changes=changes,
            added_chunks=added_chunks,
            deleted_chunks=deleted_chunks,
            modified_chunks=modified_chunks,
            unchanged_chunks=unchanged_chunks,
            occurrence_updates=occurrence_updates,
            summary=summary,
        )
        # Back-compat properties expected by some integration tests
        diff.added = added_chunks  # type: ignore[attr-defined]
        diff.removed = deleted_chunks  # type: ignore[attr-defined]
        diff.modified = modified_chunks  # type: ignore[attr-defined]
        return diff

    def _compute_content_diff(
        self,
        old_chunks: list[CodeChunk],
        new_content: str,
        language: str,
        file_path: str | None = None,
    ) -> ChunkDiff:
        """Compute difference between old chunks and new content."""
        identity_path = file_path or (old_chunks[0].file_path if old_chunks else "")
        new_chunks = chunk_text(new_content, language, file_path=identity_path)
        old_map, new_map = self._identity_maps(old_chunks, new_chunks)
        old_ids = set(old_map.keys())
        new_ids = set(new_map.keys())
        unchanged_ids = old_ids & new_ids
        occurrence_updates = []
        unchanged_chunks = []
        modified_chunks = []
        for chunk_id in unchanged_ids:
            old_chunk = old_map[chunk_id]
            new_chunk = new_map[chunk_id]
            if old_chunk.content != new_chunk.content:
                modified_chunks.append((old_chunk, new_chunk))
            else:
                unchanged_chunks.append(new_chunk)
                if self._occurrence_fields(old_chunk) != self._occurrence_fields(
                    new_chunk
                ):
                    occurrence_updates.append((old_chunk, new_chunk))
        added_ids = new_ids - old_ids
        deleted_ids = old_ids - new_ids
        added_chunks = [new_map[chunk_id] for chunk_id in added_ids]
        deleted_chunks = [old_map[chunk_id] for chunk_id in deleted_ids]
        changes = []
        changes.extend(
            ChunkChange(
                chunk_id=chunk.chunk_id,
                change_type=ChangeType.ADDED,
                old_chunk=None,
                new_chunk=chunk,
                line_changes=[(chunk.start_line, chunk.end_line)],
                confidence=1.0,
            )
            for chunk in added_chunks
        )
        changes.extend(
            ChunkChange(
                chunk_id=chunk.chunk_id,
                change_type=ChangeType.DELETED,
                old_chunk=chunk,
                new_chunk=None,
                line_changes=[(chunk.start_line, chunk.end_line)],
                confidence=1.0,
            )
            for chunk in deleted_chunks
        )
        for old_chunk, new_chunk in modified_chunks:
            old_lines = old_chunk.content.splitlines(keepends=True)
            new_lines = new_chunk.content.splitlines(keepends=True)
            line_changes = []
            differ = difflib.SequenceMatcher(None, old_lines, new_lines)
            for tag, i1, i2, _j1, _j2 in differ.get_opcodes():
                if tag != "equal":
                    start_line = old_chunk.start_line + i1
                    end_line = old_chunk.start_line + i2
                    line_changes.append((start_line, end_line))
            changes.append(
                ChunkChange(
                    chunk_id=new_chunk.chunk_id,
                    change_type=ChangeType.MODIFIED,
                    old_chunk=old_chunk,
                    new_chunk=new_chunk,
                    line_changes=line_changes,
                    confidence=0.9,
                ),
            )
        moved_pairs = self.detect_moved_chunks(
            [old_map[key] for key in deleted_ids if key.startswith("definition:")],
            [new_map[key] for key in added_ids if key.startswith("definition:")],
        )
        for old_chunk, new_chunk in moved_pairs:
            added_chunks = [c for c in added_chunks if c.chunk_id != new_chunk.chunk_id]
            deleted_chunks = [
                c for c in deleted_chunks if c.chunk_id != old_chunk.chunk_id
            ]
            changes = [
                c
                for c in changes
                if c.chunk_id not in {old_chunk.chunk_id, new_chunk.chunk_id}
            ]
            changes.append(
                ChunkChange(
                    chunk_id=new_chunk.chunk_id,
                    change_type=ChangeType.MOVED,
                    old_chunk=old_chunk,
                    new_chunk=new_chunk,
                    line_changes=[(new_chunk.start_line, new_chunk.end_line)],
                    confidence=0.95,
                ),
            )
        summary = {
            "total_old_chunks": len(old_chunks),
            "total_new_chunks": len(new_chunks),
            "added": len(added_chunks),
            "deleted": len(deleted_chunks),
            "modified": len(modified_chunks),
            "moved": len(moved_pairs),
            "unchanged": len(unchanged_chunks),
        }
        return ChunkDiff(
            changes=changes,
            added_chunks=added_chunks,
            deleted_chunks=deleted_chunks,
            modified_chunks=modified_chunks,
            unchanged_chunks=unchanged_chunks,
            occurrence_updates=occurrence_updates,
            summary=summary,
        )

    def update_chunks(
        self,
        old_or_path: list[CodeChunk] | str,
        diff_or_new: ChunkDiff | list[CodeChunk],
    ) -> list[CodeChunk]:
        """Update chunks based on diff or directly with new_chunks for a file path.

        Supports:
        - update_chunks(old_chunks, diff)
        - update_chunks(file_path: str, new_chunks: list[CodeChunk])
        """
        # Overload: (file_path, new_chunks)
        if isinstance(old_or_path, (str, Path)) and isinstance(diff_or_new, list):
            # Back-compat path: if called with (file_path, new_chunks) simply replace
            new_chunks: list[CodeChunk] = diff_or_new
            file_path = str(old_or_path)
            # Persist into processor state so subsequent compute_diff() has baseline
            self.file_chunks[file_path] = list(new_chunks)
            self._baseline[file_path] = list(new_chunks)
            return list(new_chunks)

        # Original signature: (old_chunks, diff)
        old_chunks = old_or_path  # type: ignore[assignment]
        diff = diff_or_new  # type: ignore[assignment]
        # Backward-compatible: tests may pass a file_path string; treat as empty prior state
        if isinstance(old_chunks, str):
            chunk_map: dict[str, CodeChunk] = {}
        else:
            chunk_map = {chunk.chunk_id: chunk for chunk in old_chunks}
        for change in diff.changes:  # type: ignore[attr-defined]
            if change.change_type == ChangeType.DELETED:
                chunk_map.pop(change.chunk_id, None)
            elif (
                change.change_type
                in {ChangeType.ADDED, ChangeType.MODIFIED, ChangeType.MOVED}
                and change.new_chunk
            ):
                if change.old_chunk is not None:
                    chunk_map.pop(change.old_chunk.chunk_id, None)
                chunk_map[change.new_chunk.chunk_id] = change.new_chunk
        previous, unchanged = self._identity_maps(
            list(chunk_map.values()), diff.unchanged_chunks
        )
        for key, chunk in unchanged.items():
            if key in previous:
                chunk_map.pop(previous[key].chunk_id, None)
            chunk_map[chunk.chunk_id] = chunk
        result = list(chunk_map.values())
        result.sort(
            key=lambda c: (c.file_path, c.start_line, c.byte_start, -c.byte_end)
        )
        return result

    @staticmethod
    def detect_moved_chunks(
        old_chunks: list[CodeChunk],
        new_chunks: list[CodeChunk],
    ) -> list[tuple[CodeChunk, CodeChunk]]:
        """Detect chunks that have been moved."""
        moved_pairs = []
        collisions = {
            key
            for chunks in (old_chunks, new_chunks)
            for key, count in Counter(
                c.definition_id or c.chunk_id for c in chunks
            ).items()
            if count > 1
        }
        matched_targets = set()

        def source_order(chunk: CodeChunk) -> tuple[str, int, int, str]:
            return (chunk.file_path, chunk.byte_start, chunk.byte_end, chunk.chunk_id)

        ordered_new = sorted(new_chunks, key=source_order)
        for old_chunk in sorted(old_chunks, key=source_order):
            if (old_chunk.definition_id or old_chunk.chunk_id) in collisions:
                continue
            best_match = None
            best_similarity = 0.0
            for new_chunk in ordered_new:
                if (
                    old_chunk.node_type != new_chunk.node_type
                    or new_chunk.chunk_id in matched_targets
                    or (new_chunk.definition_id or new_chunk.chunk_id) in collisions
                ):
                    continue
                similarity = difflib.SequenceMatcher(
                    None,
                    old_chunk.content,
                    new_chunk.content,
                ).ratio()
                if (
                    similarity > 0.85
                    and (
                        old_chunk.start_line != new_chunk.start_line
                        or old_chunk.file_path != new_chunk.file_path
                    )
                    and similarity > best_similarity
                ):
                    best_match = new_chunk
                    best_similarity = similarity
            if best_match:
                moved_pairs.append((old_chunk, best_match))
                matched_targets.add(best_match.chunk_id)
        return moved_pairs

    @staticmethod
    def merge_incremental_results(
        full_chunks: list[CodeChunk],
        incremental_chunks: list[CodeChunk],
        changed_regions: list[tuple[int, int]],
    ) -> list[CodeChunk]:
        """Replace chunks intersecting inclusive changed regions across all files.

        Reversed spans are empty. Incremental chunks take precedence by occurrence
        ID and precede retained chunks when their file and start line tie.
        """
        intervals: list[tuple[int, int]] = []
        for start, end in sorted(changed_regions):
            if end < start:
                continue
            if intervals and start <= intervals[-1][1] + 1:
                left, right = intervals[-1]
                intervals[-1] = (left, max(right, end))
            else:
                intervals.append((start, end))

        result = list(incremental_chunks)
        processed_ids = {chunk.chunk_id for chunk in incremental_chunks}
        for chunk in full_chunks:
            if chunk.chunk_id in processed_ids:
                continue
            if chunk.start_line <= chunk.end_line:
                # Disjoint intervals have ascending ends as well as starts.
                i = bisect_right(intervals, chunk.end_line, key=itemgetter(0))
                if i and intervals[i - 1][1] >= chunk.start_line:
                    continue
            result.append(chunk)
        result.sort(key=lambda c: (c.file_path, c.start_line))
        return result


class DefaultChunkCache(ChunkCache):
    """File-based chunk cache implementation."""

    def __init__(self, cache_dir: str = ".chunker_cache"):
        """
        Initialize cache.

        Args:
            cache_dir: Directory to store cache files
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True)
        self.stats = defaultdict(int)
        self._index: dict[str, dict[str, Any]] = self._load_index()

    def _load_index(self) -> dict[str, dict[str, Any]]:
        """Load cache index."""
        index_path = self.cache_dir / "index.json"
        if index_path.exists():
            try:
                with Path(index_path).open("r", encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, FileNotFoundError, IndexError):
                return {}
        return {}

    def _save_index(self) -> None:
        """Save cache index."""
        index_path = self.cache_dir / "index.json"
        with Path(index_path).open("w", encoding="utf-8") as f:
            json.dump(self._index, f, indent=2)

    def _get_cache_path(self, file_path: str) -> Path:
        """Get cache file path for a source file."""
        path_hash = hashlib.sha256(file_path.encode()).hexdigest()
        return self.cache_dir / f"{path_hash}.pkl"

    def store(
        self,
        file_path: str,
        chunks: list[CodeChunk],
        file_hash: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Store chunks with file hash."""
        entry = CacheEntry(
            file_path=file_path,
            file_hash=file_hash,
            chunks=chunks,
            timestamp=datetime.now(),
            language=chunks[0].language if chunks else "",
            metadata=metadata or {},
        )
        self._persist_entry(entry)

    def _persist_entry(self, entry: CacheEntry) -> None:
        cache_path = self._get_cache_path(entry.file_path)
        with cache_path.open("wb") as f:
            pickle.dump(entry, f)
        self._index[entry.file_path] = {
            "file_hash": entry.file_hash,
            "timestamp": entry.timestamp.isoformat(),
            "chunk_count": len(entry.chunks),
            "cache_file": cache_path.name,
        }
        self._save_index()
        self.stats["stores"] += 1

    def retrieve(
        self,
        file_path: str,
        file_hash: str | None = None,
    ) -> CacheEntry | None:
        """Retrieve cached chunks."""
        self.stats["retrievals"] += 1
        if file_path not in self._index:
            self.stats["misses"] += 1
            return None
        index_entry = self._index[file_path]
        if file_hash and index_entry["file_hash"] != file_hash:
            self.stats["hash_mismatches"] += 1
            return None
        cache_path = self._get_cache_path(file_path)
        if not cache_path.exists():
            self.stats["misses"] += 1
            return None
        try:
            with Path(cache_path).open("rb") as f:
                entry = pickle.load(f)
            self.stats["hits"] += 1
            return entry
        except (OSError, FileNotFoundError, IndexError):
            self.stats["errors"] += 1
            return None

    def invalidate(
        self,
        file_path: str | None = None,
        older_than: datetime | None = None,
    ) -> int:
        """Invalidate cache entries."""
        count = 0
        if file_path:
            if file_path in self._index:
                cache_path = self._get_cache_path(file_path)
                if cache_path.exists():
                    cache_path.unlink()
                del self._index[file_path]
                count = 1
        else:
            to_remove = []
            for path, info in self._index.items():
                if older_than:
                    timestamp = datetime.fromisoformat(info["timestamp"])
                    if timestamp < older_than:
                        to_remove.append(path)
                else:
                    to_remove.append(path)
            for path in to_remove:
                cache_path = self._get_cache_path(path)
                if cache_path.exists():
                    cache_path.unlink()
                del self._index[path]
                count += 1
        self._save_index()
        return count

    def get_statistics(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_size = sum(
            self._get_cache_path(path).stat().st_size
            for path in self._index
            if self._get_cache_path(path).exists()
        )
        hit_rate = (
            self.stats["hits"]
            / max(
                1,
                self.stats["retrievals"],
            )
            if self.stats["retrievals"] > 0
            else 0.0
        )
        return {
            "entries": len(self._index),
            "total_size_bytes": total_size,
            "total_size_mb": total_size / (1024 * 1024),
            "hit_rate": hit_rate,
            "stats": dict(self.stats),
        }

    def export_cache(self, output_path: str) -> None:
        """Write a complete v1 UTF-8 JSON snapshot, replacing the backup on success.

        Entry and chunk metadata must be ordinary JSON trees with string keys
        and finite numbers. Strings must be UTF-8 encodable. Tuples, non-string
        keys and cycles raise ValueError. On POSIX the new backup file is private
        to its owner, including when it replaces an existing backup.
        """
        entries = {}
        for path in self._index:
            entry = self.retrieve(path)
            if entry is None:
                raise ValueError(f"Missing indexed cache entry {path!r}")
            record: dict[str, Any] = {
                "file_hash": entry.file_hash,
                "timestamp": entry.timestamp.isoformat(timespec="microseconds"),
                "language": entry.language,
                "metadata": entry.metadata,
                "chunks": [
                    {f.name: getattr(chunk, f.name) for f in fields(CodeChunk)}
                    for chunk in entry.chunks
                ],
            }
            if entry.timestamp.fold:
                record["timestamp_fold"] = entry.timestamp.fold
            try:
                _validate_backup_entry(record)
            except (ValueError, RecursionError) as error:
                raise ValueError(f"Invalid cache entry {path!r}: {error}") from error
            entries[path] = record

        output = Path(output_path)
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output.parent,
            delete_on_close=False,
        ) as temp:
            json.dump(
                {"format_version": 1, "entries": entries},
                temp,
                ensure_ascii=False,
                allow_nan=False,
            )
            temp.close()
            Path(temp.name).replace(output)

    def import_cache(self, input_path: str) -> None:
        """Replace the cache with a validated v1 snapshot, preserving entry ages.

        Unversioned backups omit spans and identities. Rebuild from source
        when import raises a legacy-format ValueError.
        """
        with Path(input_path).open(encoding="utf-8") as src:
            snapshot = json.load(src, object_pairs_hook=_unique_backup_keys)
        if not isinstance(snapshot, dict):
            raise ValueError("Expected a cache backup object")
        if "format_version" not in snapshot:
            raise ValueError(
                "Legacy cache backup: spans and IDs cannot be recovered; rebuild from source"
            )
        version = snapshot["format_version"]
        if type(version) is not int or version != 1:
            raise ValueError(f"Unsupported cache format_version: {version!r}")
        records = snapshot.get("entries")
        if not isinstance(records, dict):
            raise ValueError("Expected entries object in cache backup")
        entries = []
        for path, record in records.items():
            try:
                # Check UTF-8 encodability before replacement.
                self._get_cache_path(path)
                entries.append(_decode_backup_entry(path, record))
            except (ValueError, RecursionError) as error:
                raise ValueError(f"Invalid cache entry {path!r}: {error}") from error
        self.invalidate()
        for entry in entries:
            self._persist_entry(entry)


def _unique_backup_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate cache backup key {key!r}")
        result[key] = value
    return result


def _validate_backup_text(value: str, location: str) -> None:
    if not value.isascii():
        try:
            value.encode("utf-8")
        except UnicodeEncodeError as error:
            raise ValueError(f"{location} requires UTF-8 encodable strings") from error


def _validate_backup_json(value: Any, location: str) -> None:
    """Reject coercions that Python's JSON encoder normally allows."""
    if type(value) is dict:
        for key, child in value.items():
            if type(key) is not str:
                raise ValueError(f"{location} requires string keys")
            _validate_backup_text(key, location)
            _validate_backup_json(child, f"{location}[{key!r}]")
    elif type(value) is list:
        for i, child in enumerate(value):
            _validate_backup_json(child, f"{location}[{i}]")
    elif type(value) is str:
        _validate_backup_text(value, location)
    elif type(value) is float:
        if not math.isfinite(value):
            raise ValueError(f"{location} requires a finite number")
    elif value is not None and type(value) not in (bool, int):
        raise ValueError(f"{location} cannot store {type(value).__name__} in JSON")


_CHUNK_BACKUP_TYPES = get_type_hints(CodeChunk)


def _validate_backup_chunk(record: Any, location: str) -> None:
    if not isinstance(record, dict) or record.keys() != _CHUNK_BACKUP_TYPES.keys():
        keys = set(record) if isinstance(record, dict) else set()
        raise ValueError(
            f"{location} has invalid fields: {keys ^ _CHUNK_BACKUP_TYPES.keys()}"
        )
    for name, expected in _CHUNK_BACKUP_TYPES.items():
        value = record[name]
        if expected == list[str]:
            valid = type(value) is list and all(type(v) is str for v in value)
        elif expected == dict[str, Any]:
            valid = isinstance(value, dict)
        elif expected == int:
            valid = type(value) is int
        else:
            valid = type(value) is str or (expected == (str | None) and value is None)
        if not valid:
            raise ValueError(f"{location}.{name} must be {expected}")


def _validate_backup_entry(record: Any) -> datetime:
    if not isinstance(record, dict):
        raise ValueError("Expected an entry object")
    for name in ("file_hash", "language", "timestamp"):
        if type(record.get(name)) is not str:
            raise ValueError(f"Expected string field {name}")
    try:
        timestamp = datetime.fromisoformat(record["timestamp"])
    except ValueError as error:
        raise ValueError("Invalid timestamp") from error
    if (
        record["timestamp"]
        not in (
            timestamp.isoformat(timespec="seconds"),
            timestamp.isoformat(timespec="microseconds"),
        )
        or timestamp.tzinfo is not None
    ):
        raise ValueError("Expected a local ISO timestamp with seconds or microseconds")
    if not isinstance(record.get("chunks"), list):
        raise ValueError("Expected chunks array")
    if not isinstance(record.get("metadata"), dict):
        raise ValueError("Expected metadata object")
    _validate_backup_json(record, "entry")
    fold = record.get("timestamp_fold", 0)
    if type(fold) is not int or fold not in (0, 1):
        raise ValueError("Expected timestamp_fold to be 0 or 1")
    for i, chunk in enumerate(record["chunks"]):
        _validate_backup_chunk(chunk, f"chunks[{i}]")
    return timestamp.replace(fold=fold)


def _decode_backup_entry(path: str, record: Any) -> CacheEntry:
    timestamp = _validate_backup_entry(record)
    chunks = []
    for values in record["chunks"]:
        # __post_init__ derives identities, including those explicitly cleared
        # after construction. Restore the complete validated state verbatim.
        chunk = CodeChunk.__new__(CodeChunk)
        vars(chunk).update(values)
        chunks.append(chunk)
    return CacheEntry(
        file_path=path,
        file_hash=record["file_hash"],
        timestamp=timestamp,
        language=record["language"],
        metadata=record["metadata"],
        chunks=chunks,
    )


class DefaultChangeDetector(ChangeDetector):
    """Default change detection implementation."""

    @staticmethod
    def compute_file_hash(content: str) -> str:
        """Compute hash of file content."""
        return hashlib.sha256(content.encode()).hexdigest()

    @staticmethod
    def find_changed_regions(
        old_content: str,
        new_content: str,
    ) -> list[tuple[int, int]]:
        """Find regions that have changed."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)
        differ = difflib.SequenceMatcher(None, old_lines, new_lines)
        changed_regions = []
        for tag, i1, i2, _j1, _j2 in differ.get_opcodes():
            if tag != "equal":
                start_line = i1 + 1
                end_line = i2
                end_line = max(end_line, start_line)
                changed_regions.append((start_line, end_line))
        return changed_regions

    @staticmethod
    def classify_change(
        old_chunk: CodeChunk,
        _new_content: str,
        changed_lines: set[int],
    ) -> ChangeType:
        """Classify the type of change to a chunk."""
        chunk_lines = set(range(old_chunk.start_line, old_chunk.end_line + 1))
        if not chunk_lines:
            return ChangeType.DELETED
        overlap = chunk_lines & changed_lines
        if not overlap:
            return ChangeType.MODIFIED
        overlap_ratio = len(overlap) / len(chunk_lines)
        if overlap_ratio == 1.0:
            return ChangeType.DELETED
        if overlap_ratio > 0.5:
            return ChangeType.MODIFIED
        return ChangeType.MODIFIED


class SimpleIncrementalIndex(IncrementalIndex):
    """Simple in-memory incremental index implementation."""

    def __init__(self):
        """Initialize index."""
        self.index: dict[str, dict[str, Any]] = {}
        self.update_log: list[dict[str, Any]] = []

    def update_chunk(
        self,
        old_chunk: CodeChunk | None,
        new_chunk: CodeChunk | None,
    ) -> None:
        """Update index for a single chunk change."""
        if old_chunk:
            self.index.pop(old_chunk.chunk_id, None)
        self._publish_update(old_chunk, new_chunk)

    def _publish_update(
        self, old_chunk: CodeChunk | None, new_chunk: CodeChunk | None
    ) -> None:
        if new_chunk:
            self.index[new_chunk.chunk_id] = {
                "content": new_chunk.content.lower(),
                "node_type": new_chunk.node_type,
                "file_path": new_chunk.file_path,
                "line_range": (new_chunk.start_line, new_chunk.end_line),
            }
        self.update_log.append(
            {
                "timestamp": datetime.now(),
                "old_id": old_chunk.chunk_id if old_chunk else None,
                "new_id": new_chunk.chunk_id if new_chunk else None,
                "action": (
                    "delete" if not new_chunk else "add" if not old_chunk else "update"
                ),
            },
        )

    def batch_update(self, diff: ChunkDiff) -> None:
        """Update index with multiple changes."""
        pairs = [(change.old_chunk, change.new_chunk) for change in diff.changes]
        pairs.extend(diff.occurrence_updates)
        # A destination can reuse another pair's old ID.
        for old_chunk, _ in pairs:
            if old_chunk:
                self.index.pop(old_chunk.chunk_id, None)
        for old_chunk, new_chunk in pairs:
            self._publish_update(old_chunk, new_chunk)

    def get_update_cost(self, diff: ChunkDiff) -> float:
        """Estimate cost of applying updates."""
        total_chunks = len(self.index)
        if total_chunks == 0:
            return 0.0
        changes = len(diff.changes) + len(diff.occurrence_updates)
        cost = min(1.0, changes / max(1, total_chunks))
        major_changes = sum(
            1
            for change in diff.changes
            if change.change_type in {ChangeType.DELETED, ChangeType.ADDED}
        )
        if major_changes > total_chunks * 0.5:
            cost = 1.0
        return cost

    def search(self, query: str) -> list[str]:
        """Simple search functionality."""
        query_lower = query.lower()
        results = []
        for chunk_id, data in self.index.items():
            if query_lower in data["content"]:
                results.append(chunk_id)
        return results
