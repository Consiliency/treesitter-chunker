"""Incremental processing interface for efficient chunk updates."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from chunker.types import CodeChunk


class ChangeType(Enum):
    """Types of changes in code."""
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    MOVED = "moved"
    RENAMED = "renamed"


@dataclass
class ChunkChange:
    """Represents a change to a chunk."""
    chunk_id: str
    change_type: ChangeType
    old_chunk: CodeChunk | None
    new_chunk: CodeChunk | None
    line_changes: list[tuple[int, int]]
    confidence: float


@dataclass
class ChunkDiff:
    """Diff between two sets of chunks."""
    changes: list[ChunkChange]
    added_chunks: list[CodeChunk]
    deleted_chunks: list[CodeChunk]
    modified_chunks: list[tuple[CodeChunk, CodeChunk]]
    unchanged_chunks: list[CodeChunk]
    summary: dict[str, int]


@dataclass
class CacheEntry:
    """Entry in the chunk cache."""
    file_path: str
    file_hash: str
    chunks: list[CodeChunk]
    timestamp: datetime
    language: str
    metadata: dict[str, Any]


class IncrementalProcessor(ABC):
    """Process only changed parts of code."""

    @staticmethod
    @abstractmethod
    def compute_diff(old_chunks: list[CodeChunk], new_content: str,
        language: str) -> ChunkDiff:
        """
        Compute difference between old chunks and new content.

        This should efficiently identify what has changed without
        reprocessing the entire file.

        Args:
            old_chunks: Previous chunks
            new_content: New file content
            language: Programming language

        Returns:
            Diff describing the changes
        """

    @staticmethod
    @abstractmethod
    def update_chunks(old_chunks: list[CodeChunk], diff: ChunkDiff) -> list[
        CodeChunk]:
        """
        Update chunks based on diff.

        This applies the changes described in the diff to produce
        an updated set of chunks.

        Args:
            old_chunks: Original chunks
            diff: Changes to apply

        Returns:
            Updated chunks
        """

    @staticmethod
    @abstractmethod
    def detect_moved_chunks(old_chunks: list[CodeChunk], new_chunks: list[
        CodeChunk]) -> list[tuple[CodeChunk, CodeChunk]]:
        """
        Detect chunks that have been moved.

        Args:
            old_chunks: Original chunks
            new_chunks: New chunks

        Returns:
            List of (old_chunk, new_chunk) pairs that represent moves
        """

    @staticmethod
    @abstractmethod
    def merge_incremental_results(full_chunks: list[CodeChunk],
        incremental_chunks: list[CodeChunk], changed_regions: list[tuple[
        int, int]]) -> list[CodeChunk]:
        """
        Merge incremental processing results with full chunks.

        Args:
            full_chunks: Complete chunks from last full processing
            incremental_chunks: Chunks from incremental processing
            changed_regions: Line ranges that changed

        Returns:
            Merged chunk list
        """


class ChunkCache(ABC):
    """Cache chunks for incremental processing."""

    @staticmethod
    @abstractmethod
    def store(file_path: str, chunks: list[CodeChunk], file_hash: str,
        metadata: (dict[str, Any] | None) = None) -> None:
        """
        Store chunks with file hash.

        Args:
            file_path: Path to the file
            chunks: Chunks to cache
            file_hash: Hash of file content
            metadata: Optional metadata to store
        """

    @staticmethod
    @abstractmethod
    def retrieve(file_path: str, file_hash: (str | None) = None) -> (CacheEntry |
        None):
        """
        Retrieve cached chunks.

        Args:
            file_path: Path to the file
            file_hash: Optional hash to verify

        Returns:
            Cache entry if found and valid
        """

    @staticmethod
    @abstractmethod
    def invalidate(file_path: (str | None) = None, older_than: (datetime |
        None) = None) -> int:
        """
        Invalidate cache entries.

        Args:
            file_path: Specific file to invalidate (all if None)
            older_than: Invalidate entries older than this

        Returns:
            Number of entries invalidated
        """

    @staticmethod
    @abstractmethod
    def get_statistics() -> dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dict with hit rate, size, age distribution, etc.
        """

    @staticmethod
    @abstractmethod
    def export_cache(output_path: str) -> None:
        """Export cache to file for persistence."""

    @staticmethod
    @abstractmethod
    def import_cache(input_path: str) -> None:
        """Import cache from file."""


class ChangeDetector(ABC):
    """Detect changes in code efficiently."""

    @staticmethod
    @abstractmethod
    def compute_file_hash(content: str) -> str:
        """
        Compute hash of file content.

        Args:
            content: File content

        Returns:
            Hash string
        """

    @staticmethod
    @abstractmethod
    def find_changed_regions(old_content: str, new_content: str) -> list[tuple
        [int, int]]:
        """
        Find regions that have changed.

        Args:
            old_content: Previous content
            new_content: New content

        Returns:
            List of (start_line, end_line) tuples
        """

    @staticmethod
    @abstractmethod
    def classify_change(old_chunk: CodeChunk, new_content: str,
        changed_lines: set[int]) -> ChangeType:
        """
        Classify the type of change to a chunk.

        Args:
            old_chunk: Original chunk
            new_content: New file content
            changed_lines: Set of changed line numbers

        Returns:
            Type of change
        """


class IncrementalIndex(ABC):
    """Incremental index updates for search."""

    @staticmethod
    @abstractmethod
    def update_chunk(old_chunk: (CodeChunk | None), new_chunk: (CodeChunk |
        None)) -> None:
        """
        Update index for a single chunk change.

        Args:
            old_chunk: Previous version (None if added)
            new_chunk: New version (None if deleted)
        """

    @staticmethod
    @abstractmethod
    def batch_update(diff: ChunkDiff) -> None:
        """
        Update index with multiple changes.

        Args:
            diff: Chunk diff to apply
        """

    @staticmethod
    @abstractmethod
    def get_update_cost(diff: ChunkDiff) -> float:
        """
        Estimate cost of applying updates.

        Args:
            diff: Proposed changes

        Returns:
            Cost estimate (0-1, where 1 means full rebuild)
        """
