"""Overlapping support for fallback chunker only - NOT for Tree-sitter chunks."""

from abc import abstractmethod
from typing import List, Optional, Literal
from enum import Enum

from ..fallback.base import FallbackChunker
from ..types import CodeChunk


class OverlapStrategy(Enum):
    """Strategy for calculating overlap size."""
    FIXED = "fixed"  # Fixed number of lines/characters
    PERCENTAGE = "percentage"  # Percentage of chunk size
    DYNAMIC = "dynamic"  # Adjust based on content
    ASYMMETRIC = "asymmetric"  # Different before/after overlap


class OverlappingFallbackChunker(FallbackChunker):
    """
    Add overlapping support to fallback chunking ONLY.
    
    This is specifically for non-Tree-sitter files where we need
    context preservation through overlapping windows.
    """
    
    @abstractmethod
    def chunk_with_overlap(self, content: str, file_path: str,
                          chunk_size: int = 1000,
                          overlap_size: int = 200,
                          strategy: OverlapStrategy = OverlapStrategy.FIXED,
                          unit: Literal["lines", "characters"] = "characters") -> List[CodeChunk]:
        """
        Chunk content with overlapping windows.
        
        This is ONLY for fallback files without Tree-sitter support.
        
        Args:
            content: Text content to chunk
            file_path: Path to source file
            chunk_size: Size of each chunk (lines or characters)
            overlap_size: Size of overlap (lines or characters)
            strategy: How to calculate overlap
            unit: Whether sizes are in lines or characters
            
        Returns:
            List of overlapping chunks
        """
        pass
    
    @abstractmethod
    def chunk_with_asymmetric_overlap(self, content: str, file_path: str,
                                    chunk_size: int = 1000,
                                    overlap_before: int = 100,
                                    overlap_after: int = 200,
                                    unit: Literal["lines", "characters"] = "characters") -> List[CodeChunk]:
        """
        Chunk with different overlap sizes before and after.
        
        Useful when context before is less important than context after.
        
        Args:
            content: Text content to chunk
            file_path: Path to source file
            chunk_size: Size of each chunk
            overlap_before: Overlap size with previous chunk
            overlap_after: Overlap size with next chunk
            unit: Whether sizes are in lines or characters
            
        Returns:
            List of overlapping chunks
        """
        pass
    
    @abstractmethod
    def chunk_with_dynamic_overlap(self, content: str, file_path: str,
                                 chunk_size: int = 1000,
                                 min_overlap: int = 50,
                                 max_overlap: int = 300,
                                 unit: Literal["lines", "characters"] = "characters") -> List[CodeChunk]:
        """
        Chunk with dynamically adjusted overlap based on content.
        
        Adjusts overlap size based on natural boundaries (paragraphs, sections).
        
        Args:
            content: Text content to chunk
            file_path: Path to source file
            chunk_size: Size of each chunk
            min_overlap: Minimum overlap size
            max_overlap: Maximum overlap size
            unit: Whether sizes are in lines or characters
            
        Returns:
            List of overlapping chunks
        """
        pass
    
    @abstractmethod
    def find_natural_overlap_boundary(self, content: str, 
                                    desired_position: int,
                                    search_window: int = 100) -> int:
        """
        Find a natural boundary for overlap near desired position.
        
        Looks for paragraph breaks, sentence ends, etc.
        
        Args:
            content: Text content
            desired_position: Where we want the overlap
            search_window: How far to search for natural boundary
            
        Returns:
            Best position for overlap boundary
        """
        pass