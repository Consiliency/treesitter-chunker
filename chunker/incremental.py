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

    def compute_diff(
        self,
        old_chunks: list[CodeChunk],
        new_content: str,
        language: str,
    ) -> ChunkDiff:
        """Compute difference between old chunks and new content."""
        # First, chunk the new content
        new_chunks = chunk_text(new_content, language, file_path="")

        # Build lookup maps for efficient comparison
        old_map = {chunk.chunk_id: chunk for chunk in old_chunks}
        new_map = {chunk.chunk_id: chunk for chunk in new_chunks}

        # Find what changed
        old_ids = set(old_map.keys())
        new_ids = set(new_map.keys())

        # Direct matches (unchanged)
        unchanged_ids = old_ids & new_ids
        unchanged_chunks = []

        # Check if "unchanged" chunks actually changed content
        modified_chunks = []
        for chunk_id in unchanged_ids:
            old_chunk = old_map[chunk_id]
            new_chunk = new_map[chunk_id]
            if old_chunk.content != new_chunk.content:
                modified_chunks.append((old_chunk, new_chunk))
            else:
                unchanged_chunks.append(new_chunk)

        # Added and deleted
        added_ids = new_ids - old_ids
        deleted_ids = old_ids - new_ids

        added_chunks = [new_map[chunk_id] for chunk_id in added_ids]
        deleted_chunks = [old_map[chunk_id] for chunk_id in deleted_ids]

        # Build change list
        changes = []

        # Added chunks
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

        # Deleted chunks
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

        # Modified chunks
        for old_chunk, new_chunk in modified_chunks:
            # Find specific line changes
            old_lines = old_chunk.content.splitlines(keepends=True)
            new_lines = new_chunk.content.splitlines(keepends=True)

            line_changes = []
            differ = difflib.SequenceMatcher(None, old_lines, new_lines)
            for tag, i1, i2, j1, j2 in differ.get_opcodes():
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

        # Check for moved chunks
        moved_pairs = self.detect_moved_chunks(deleted_chunks, added_chunks)
        for old_chunk, new_chunk in moved_pairs:
            # Remove from added/deleted and add as moved
            added_chunks = [c for c in added_chunks if c.chunk_id != new_chunk.chunk_id]
            deleted_chunks = [
                c for c in deleted_chunks if c.chunk_id != old_chunk.chunk_id
            ]

            # Update changes list
            changes = [
                c
                for c in changes
                if c.chunk_id not in (old_chunk.chunk_id, new_chunk.chunk_id)
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

        # Summary statistics
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
        old_chunks: list[CodeChunk],
        diff: ChunkDiff,
    ) -> list[CodeChunk]:
        """Update chunks based on diff."""
        # Build a map of old chunks
        chunk_map = {chunk.chunk_id: chunk for chunk in old_chunks}

        # Apply changes
        for change in diff.changes:
            if change.change_type == ChangeType.DELETED:
                chunk_map.pop(change.chunk_id, None)
            elif change.change_type in (
                ChangeType.ADDED,
                ChangeType.MODIFIED,
                ChangeType.MOVED,
            ):
                if change.new_chunk:
                    chunk_map[change.new_chunk.chunk_id] = change.new_chunk

        # Add unchanged chunks (ensure they're in the map)
        for chunk in diff.unchanged_chunks:
            chunk_map[chunk.chunk_id] = chunk

        # Return sorted by position
        result = list(chunk_map.values())
        result.sort(key=lambda c: (c.file_path, c.start_line))
        return result

    def detect_moved_chunks(
        self,
        old_chunks: list[CodeChunk],
        new_chunks: list[CodeChunk],
    ) -> list[tuple[CodeChunk, CodeChunk]]:
        """Detect chunks that have been moved."""
        moved_pairs = []

        # Use content similarity to detect moves
        for old_chunk in old_chunks:
            best_match = None
            best_similarity = 0.0

            for new_chunk in new_chunks:
                # Skip if types don't match
                if old_chunk.node_type != new_chunk.node_type:
                    continue

                # Calculate similarity
                similarity = difflib.SequenceMatcher(
                    None,
                    old_chunk.content,
                    new_chunk.content,
                ).ratio()

                # High similarity and different location = moved
                if similarity > 0.85 and (
                    old_chunk.start_line != new_chunk.start_line
                    or old_chunk.file_path != new_chunk.file_path
                ):
                    if similarity > best_similarity:
                        best_match = new_chunk
                        best_similarity = similarity

            if best_match:
                moved_pairs.append((old_chunk, best_match))

        return moved_pairs

    def merge_incremental_results(
        self,
        full_chunks: list[CodeChunk],
        incremental_chunks: list[CodeChunk],
        changed_regions: list[tuple[int, int]],
    ) -> list[CodeChunk]:
        """Merge incremental processing results with full chunks."""
        # Convert changed regions to a set of line numbers for fast lookup
        changed_lines = set()
        for start, end in changed_regions:
            changed_lines.update(range(start, end + 1))

        # Build result list
        result = []
        processed_ids = set()

        # First, add all incremental chunks
        for chunk in incremental_chunks:
            result.append(chunk)
            processed_ids.add(chunk.chunk_id)

        # Then add full chunks that don't overlap with changed regions
        for chunk in full_chunks:
            if chunk.chunk_id in processed_ids:
                continue

            # Check if chunk overlaps with changed regions
            chunk_lines = set(range(chunk.start_line, chunk.end_line + 1))
            if not chunk_lines & changed_lines:
                result.append(chunk)

        # Sort by position
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
                with open(index_path) as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_index(self) -> None:
        """Save cache index."""
        index_path = self.cache_dir / "index.json"
        with open(index_path, "w") as f:
            json.dump(self._index, f, indent=2)

    def _get_cache_path(self, file_path: str) -> Path:
        """Get cache file path for a source file."""
        # Use hash of file path to avoid filesystem issues
        path_hash = hashlib.md5(file_path.encode()).hexdigest()
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

        # Save to file
        cache_path = self._get_cache_path(file_path)
        with open(cache_path, "wb") as f:
            pickle.dump(entry, f)

        # Update index
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

        # Check index
        if file_path not in self._index:
            self.stats["misses"] += 1
            return None

        # Verify hash if provided
        index_entry = self._index[file_path]
        if file_hash and index_entry["file_hash"] != file_hash:
            self.stats["hash_mismatches"] += 1
            return None

        # Load from file
        cache_path = self._get_cache_path(file_path)
        if not cache_path.exists():
            self.stats["misses"] += 1
            return None

        try:
            with open(cache_path, "rb") as f:
                entry = pickle.load(f)
            self.stats["hits"] += 1
            return entry
        except Exception:
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
            # Invalidate specific file
            if file_path in self._index:
                cache_path = self._get_cache_path(file_path)
                if cache_path.exists():
                    cache_path.unlink()
                del self._index[file_path]
                count = 1
        else:
            # Invalidate based on age
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
            self.stats["hits"] / max(1, self.stats["retrievals"])
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
        export_data = {
            "index": self._index,
            "entries": {},
        }

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

        with open(output_path, "w") as f:
            json.dump(export_data, f, indent=2)

    def import_cache(self, input_path: str) -> None:
        """Import cache from file."""
        with open(input_path) as f:
            import_data = json.load(f)

        # Clear existing cache
        self.invalidate()

        # Import entries
        for file_path, entry_data in import_data["entries"].items():
            chunks = []
            for chunk_data in entry_data["chunks"]:
                chunk = CodeChunk(
                    language=entry_data["language"],
                    file_path=file_path,
                    node_type=chunk_data["node_type"],
                    start_line=chunk_data["start_line"],
                    end_line=chunk_data["end_line"],
                    byte_start=0,  # Not preserved in export
                    byte_end=0,  # Not preserved in export
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

    def compute_file_hash(self, content: str) -> str:
        """Compute hash of file content."""
        return hashlib.sha256(content.encode()).hexdigest()

    def find_changed_regions(
        self,
        old_content: str,
        new_content: str,
    ) -> list[tuple[int, int]]:
        """Find regions that have changed."""
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        differ = difflib.SequenceMatcher(None, old_lines, new_lines)
        changed_regions = []

        for tag, i1, i2, j1, j2 in differ.get_opcodes():
            if tag != "equal":
                # Convert to 1-based line numbers
                start_line = i1 + 1
                end_line = i2  # inclusive end
                end_line = max(end_line, start_line)
                changed_regions.append((start_line, end_line))

        return changed_regions

    def classify_change(
        self,
        old_chunk: CodeChunk,
        new_content: str,
        changed_lines: set[int],
    ) -> ChangeType:
        """Classify the type of change to a chunk."""
        chunk_lines = set(range(old_chunk.start_line, old_chunk.end_line + 1))

        if not chunk_lines:
            return ChangeType.DELETED

        overlap = chunk_lines & changed_lines

        if not overlap:
            # No overlap - chunk unchanged
            return ChangeType.MODIFIED  # Should not happen in practice

        overlap_ratio = len(overlap) / len(chunk_lines)

        if overlap_ratio == 1.0:
            # Entire chunk changed - likely deleted or heavily modified
            return ChangeType.DELETED
        if overlap_ratio > 0.5:
            # Most of chunk changed
            return ChangeType.MODIFIED
        # Small portion changed
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
                "content": new_chunk.content.lower(),  # Simple case-insensitive indexing
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
                    "delete"
                    if not new_chunk
                    else ("add" if not old_chunk else "update")
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

        # Count changes
        changes = len(diff.changes)

        # Simple cost model: ratio of changes to total indexed chunks
        cost = min(1.0, changes / max(1, total_chunks))

        # Adjust based on change types
        major_changes = sum(
            1
            for change in diff.changes
            if change.change_type in (ChangeType.DELETED, ChangeType.ADDED)
        )

        if major_changes > total_chunks * 0.5:
            # More than half the chunks changed - might as well rebuild
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
