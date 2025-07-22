"""Incremental processing interface for efficient chunk updates."""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Set, Tuple, Any
from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from ..types import CodeChunk


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
    old_chunk: Optional[CodeChunk]
    new_chunk: Optional[CodeChunk]
    line_changes: List[Tuple[int, int]]  # (start_line, end_line) of changes
    confidence: float  # Confidence in change detection


@dataclass
class ChunkDiff:
    """Diff between two sets of chunks."""
    changes: List[ChunkChange]
    added_chunks: List[CodeChunk]
    deleted_chunks: List[CodeChunk]
    modified_chunks: List[Tuple[CodeChunk, CodeChunk]]  # (old, new)
    unchanged_chunks: List[CodeChunk]
    summary: Dict[str, int]  # Statistics about the diff


@dataclass
class CacheEntry:
    """Entry in the chunk cache."""
    file_path: str
    file_hash: str
    chunks: List[CodeChunk]
    timestamp: datetime
    language: str
    metadata: Dict[str, Any]


class IncrementalProcessor(ABC):
    """Process only changed parts of code."""
    
    @abstractmethod
    def compute_diff(self, old_chunks: List[CodeChunk], 
                    new_content: str, language: str) -> ChunkDiff:
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
        pass
    
    @abstractmethod
    def update_chunks(self, old_chunks: List[CodeChunk], 
                     diff: ChunkDiff) -> List[CodeChunk]:
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
        pass
    
    @abstractmethod
    def detect_moved_chunks(self, old_chunks: List[CodeChunk], 
                           new_chunks: List[CodeChunk]) -> List[Tuple[CodeChunk, CodeChunk]]:
        """
        Detect chunks that have been moved.
        
        Args:
            old_chunks: Original chunks
            new_chunks: New chunks
            
        Returns:
            List of (old_chunk, new_chunk) pairs that represent moves
        """
        pass
    
    @abstractmethod
    def merge_incremental_results(self, 
                                 full_chunks: List[CodeChunk],
                                 incremental_chunks: List[CodeChunk],
                                 changed_regions: List[Tuple[int, int]]) -> List[CodeChunk]:
        """
        Merge incremental processing results with full chunks.
        
        Args:
            full_chunks: Complete chunks from last full processing
            incremental_chunks: Chunks from incremental processing
            changed_regions: Line ranges that changed
            
        Returns:
            Merged chunk list
        """
        pass


class ChunkCache(ABC):
    """Cache chunks for incremental processing."""
    
    @abstractmethod
    def store(self, file_path: str, chunks: List[CodeChunk], 
             file_hash: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Store chunks with file hash.
        
        Args:
            file_path: Path to the file
            chunks: Chunks to cache
            file_hash: Hash of file content
            metadata: Optional metadata to store
        """
        pass
    
    @abstractmethod
    def retrieve(self, file_path: str, 
                file_hash: Optional[str] = None) -> Optional[CacheEntry]:
        """
        Retrieve cached chunks.
        
        Args:
            file_path: Path to the file
            file_hash: Optional hash to verify
            
        Returns:
            Cache entry if found and valid
        """
        pass
    
    @abstractmethod
    def invalidate(self, file_path: Optional[str] = None,
                  older_than: Optional[datetime] = None) -> int:
        """
        Invalidate cache entries.
        
        Args:
            file_path: Specific file to invalidate (all if None)
            older_than: Invalidate entries older than this
            
        Returns:
            Number of entries invalidated
        """
        pass
    
    @abstractmethod
    def get_statistics(self) -> Dict[str, Any]:
        """
        Get cache statistics.
        
        Returns:
            Dict with hit rate, size, age distribution, etc.
        """
        pass
    
    @abstractmethod
    def export_cache(self, output_path: str) -> None:
        """Export cache to file for persistence."""
        pass
    
    @abstractmethod
    def import_cache(self, input_path: str) -> None:
        """Import cache from file."""
        pass


class ChangeDetector(ABC):
    """Detect changes in code efficiently."""
    
    @abstractmethod
    def compute_file_hash(self, content: str) -> str:
        """
        Compute hash of file content.
        
        Args:
            content: File content
            
        Returns:
            Hash string
        """
        pass
    
    @abstractmethod
    def find_changed_regions(self, old_content: str, 
                            new_content: str) -> List[Tuple[int, int]]:
        """
        Find regions that have changed.
        
        Args:
            old_content: Previous content
            new_content: New content
            
        Returns:
            List of (start_line, end_line) tuples
        """
        pass
    
    @abstractmethod
    def classify_change(self, old_chunk: CodeChunk, 
                       new_content: str,
                       changed_lines: Set[int]) -> ChangeType:
        """
        Classify the type of change to a chunk.
        
        Args:
            old_chunk: Original chunk
            new_content: New file content
            changed_lines: Set of changed line numbers
            
        Returns:
            Type of change
        """
        pass


class IncrementalIndex(ABC):
    """Incremental index updates for search."""
    
    @abstractmethod
    def update_chunk(self, old_chunk: Optional[CodeChunk], 
                    new_chunk: Optional[CodeChunk]) -> None:
        """
        Update index for a single chunk change.
        
        Args:
            old_chunk: Previous version (None if added)
            new_chunk: New version (None if deleted)
        """
        pass
    
    @abstractmethod
    def batch_update(self, diff: ChunkDiff) -> None:
        """
        Update index with multiple changes.
        
        Args:
            diff: Chunk diff to apply
        """
        pass
    
    @abstractmethod
    def get_update_cost(self, diff: ChunkDiff) -> float:
        """
        Estimate cost of applying updates.
        
        Args:
            diff: Proposed changes
            
        Returns:
            Cost estimate (0-1, where 1 means full rebuild)
        """
        pass