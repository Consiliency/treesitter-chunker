"""Incremental processing implementation for efficient chunk updates."""

import difflib
import hashlib
import json
import pickle
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

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

            # Early-out: if structurally identical, return empty diff
            if len(old_chunks) == len(new_chunks):
                same = True
                for o, n in zip(old_chunks, new_chunks, strict=False):
                    if not (
                        o.chunk_id == n.chunk_id
                        and o.node_type == n.node_type
                        and o.start_line == n.start_line
                        and o.end_line == n.end_line
                        and o.content == n.content
                    ):
                        same = False
                        break
                if same:
                    empty = ChunkDiff(
                        [],
                        [],
                        [],
                        [],
                        [],
                        {
                            "total_old_chunks": len(old_chunks),
                            "total_new_chunks": len(new_chunks),
                            "added": 0,
                            "deleted": 0,
                            "modified": 0,
                            "unchanged": len(new_chunks),
                        },
                    )
                    # Back-compat convenience lists
                    empty.added = []  # type: ignore[attr-defined]
                    empty.removed = []  # type: ignore[attr-defined]
                    empty.modified = []  # type: ignore[attr-defined]
                    return empty

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
            )
        raise ValueError(
            "Invalid arguments: expected (file_path, new_chunks) or (old_chunks, new_content, language)",
        )

    def _compute_chunks_diff(
        self,
        old_chunks: list[CodeChunk],
        new_chunks: list[CodeChunk],
    ) -> ChunkDiff:
        """Compute diff between two chunk lists."""
        old_map = {chunk.chunk_id: chunk for chunk in old_chunks}
        new_map = {chunk.chunk_id: chunk for chunk in new_chunks}

        old_ids = set(old_map.keys())
        new_ids = set(new_map.keys())
        unchanged_ids = old_ids & new_ids

        unchanged_chunks = []
        modified_chunks = []

        for chunk_id in unchanged_ids:
            old_chunk = old_map[chunk_id]
            new_chunk = new_map[chunk_id]
            if old_chunk.content != new_chunk.content:
                modified_chunks.append((old_chunk, new_chunk))
            else:
                unchanged_chunks.append(new_chunk)

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
    ) -> ChunkDiff:
        """Compute difference between old chunks and new content."""
        new_chunks = chunk_text(new_content, language, file_path="")
        old_map = {chunk.chunk_id: chunk for chunk in old_chunks}
        new_map = {chunk.chunk_id: chunk for chunk in new_chunks}
        old_ids = set(old_map.keys())
        new_ids = set(new_map.keys())
        unchanged_ids = old_ids & new_ids
        unchanged_chunks = []
        modified_chunks = []
        for chunk_id in unchanged_ids:
            old_chunk = old_map[chunk_id]
            new_chunk = new_map[chunk_id]
            if old_chunk.content != new_chunk.content:
                modified_chunks.append((old_chunk, new_chunk))
            else:
                unchanged_chunks.append(new_chunk)
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
        moved_pairs = self.detect_moved_chunks(deleted_chunks, added_chunks)
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
                chunk_map[change.new_chunk.chunk_id] = change.new_chunk
        for chunk in diff.unchanged_chunks:
            chunk_map[chunk.chunk_id] = chunk
        result = list(chunk_map.values())
        result.sort(key=lambda c: (c.file_path, c.start_line))
        return result

    @staticmethod
    def detect_moved_chunks(
        old_chunks: list[CodeChunk],
        new_chunks: list[CodeChunk],
    ) -> list[tuple[CodeChunk, CodeChunk]]:
        """Detect chunks that have been moved."""
        moved_pairs = []
        for old_chunk in old_chunks:
            best_match = None
            best_similarity = 0.0
            for new_chunk in new_chunks:
                if old_chunk.node_type != new_chunk.node_type:
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
        return moved_pairs

    @staticmethod
    def merge_incremental_results(
        full_chunks: list[CodeChunk],
        incremental_chunks: list[CodeChunk],
        changed_regions: list[tuple[int, int]],
    ) -> list[CodeChunk]:
        """Merge incremental processing results with full chunks."""
        changed_lines = set()
        for start, end in changed_regions:
            changed_lines.update(range(start, end + 1))
        result = []
        processed_ids = set()
        for chunk in incremental_chunks:
            result.append(chunk)
            processed_ids.add(chunk.chunk_id)
        for chunk in full_chunks:
            if chunk.chunk_id in processed_ids:
                continue
            chunk_lines = set(range(chunk.start_line, chunk.end_line + 1))
            if not chunk_lines & changed_lines:
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
        cache_path = self._get_cache_path(file_path)
        with Path(cache_path).open("wb") as f:
            pickle.dump(entry, f)
        self._index[file_path] = {
            "file_hash": file_hash,
            "timestamp": entry.timestamp.isoformat(),
            "chunk_count": len(chunks),
            "cache_file": str(cache_path.name),
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
        """Export cache to file for persistence."""
        export_data = {"index": self._index, "entries": {}}
        for file_path in self._index:
            entry = self.retrieve(file_path)
            if entry:
                export_data["entries"][file_path] = {
                    "file_hash": entry.file_hash,
                    "timestamp": entry.timestamp.isoformat(),
                    "language": entry.language,
                    "metadata": entry.metadata,
                    "chunks": [
                        {
                            "chunk_id": chunk.chunk_id,
                            "node_type": chunk.node_type,
                            "start_line": chunk.start_line,
                            "end_line": chunk.end_line,
                            "content": chunk.content,
                            "parent_context": chunk.parent_context,
                        }
                        for chunk in entry.chunks
                    ],
                }
        with Path(output_path).open("w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)

    def import_cache(self, input_path: str) -> None:
        """Import cache from file."""
        with Path(input_path).open("r", encoding="utf-8") as f:
            import_data = json.load(f)
        self.invalidate()
        for file_path, entry_data in import_data["entries"].items():
            chunks = []
            for chunk_data in entry_data["chunks"]:
                chunk = CodeChunk(
                    language=entry_data["language"],
                    file_path=file_path,
                    node_type=chunk_data["node_type"],
                    start_line=chunk_data["start_line"],
                    end_line=chunk_data["end_line"],
                    byte_start=0,
                    byte_end=0,
                    parent_context=chunk_data["parent_context"],
                    content=chunk_data["content"],
                    chunk_id=chunk_data["chunk_id"],
                )
                chunks.append(chunk)
            self.store(
                file_path=file_path,
                chunks=chunks,
                file_hash=entry_data["file_hash"],
                metadata=entry_data.get("metadata", {}),
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
        if old_chunk and old_chunk.chunk_id in self.index:
            del self.index[old_chunk.chunk_id]
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
        for change in diff.changes:
            self.update_chunk(change.old_chunk, change.new_chunk)

    def get_update_cost(self, diff: ChunkDiff) -> float:
        """Estimate cost of applying updates."""
        total_chunks = len(self.index)
        if total_chunks == 0:
            return 0.0
        changes = len(diff.changes)
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
