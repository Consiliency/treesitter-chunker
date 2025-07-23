"""Specialized processors for different file types and content.

This module provides processors for handling various content types
that require specialized chunking strategies beyond basic tree-sitter parsing.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from ..types import CodeChunk


@dataclass
class ProcessorConfig:
    """Configuration for specialized processors."""
    max_chunk_size: int = 1500  # Maximum tokens per chunk
    min_chunk_size: int = 100   # Minimum tokens per chunk
    overlap_size: int = 100     # Overlap between chunks
    preserve_structure: bool = True  # Preserve document structure
    
    
class SpecializedProcessor(ABC):
    """Base class for specialized content processors.
    
    This interface defines the contract for processors that handle
    specific file types (e.g., Markdown, RST, LaTeX) with custom
    chunking logic that respects the document structure.
    """
    
    def __init__(self, config: Optional[ProcessorConfig] = None):
        """Initialize processor with configuration.
        
        Args:
            config: Processor configuration (uses defaults if None)
        """
        self.config = config or ProcessorConfig()
        
    @abstractmethod
    def can_process(self, file_path: str, content: str) -> bool:
        """Check if this processor can handle the given content.
        
        Args:
            file_path: Path to the file
            content: File content as string
            
        Returns:
            True if this processor can handle the content
        """
        pass
        
    @abstractmethod
    def process(self, content: str, file_path: str) -> List[CodeChunk]:
        """Process content and return chunks.
        
        Args:
            content: Content to process
            file_path: Path to the source file
            
        Returns:
            List of code chunks
        """
        pass
        
    @abstractmethod
    def extract_structure(self, content: str) -> Dict[str, Any]:
        """Extract structural information from content.
        
        Args:
            content: Content to analyze
            
        Returns:
            Dictionary containing structural information
        """
        pass
        
    @abstractmethod
    def find_boundaries(self, content: str) -> List[Tuple[int, int, str]]:
        """Find natural chunk boundaries in content.
        
        Args:
            content: Content to analyze
            
        Returns:
            List of (start, end, boundary_type) tuples
        """
        pass
        
    def validate_chunk(self, chunk: CodeChunk) -> bool:
        """Validate that a chunk meets quality criteria.
        
        Args:
            chunk: Chunk to validate
            
        Returns:
            True if chunk is valid
        """
        # Default validation - can be overridden
        content_length = len(chunk.content.strip())
        return content_length >= self.config.min_chunk_size


class SlidingWindowEngine:
    """Interface for sliding window text processing.
    
    This will be implemented in the sliding-window worktree.
    """
    
    def __init__(self, window_size: int, overlap: int):
        """Initialize sliding window engine.
        
        Args:
            window_size: Size of the window in tokens
            overlap: Number of overlapping tokens between windows
        """
        self.window_size = window_size
        self.overlap = overlap
        
    def process_text(self, text: str, boundaries: Optional[List[Tuple[int, int]]] = None) -> List[Tuple[int, int]]:
        """Process text with sliding window, respecting boundaries.
        
        Args:
            text: Text to process
            boundaries: Optional list of (start, end) positions to respect
            
        Returns:
            List of (start, end) positions for chunks
        """
        # This is just the interface - implementation in sliding-window worktree
        raise NotImplementedError("SlidingWindowEngine implementation pending")


__all__ = ['SpecializedProcessor', 'ProcessorConfig', 'SlidingWindowEngine']