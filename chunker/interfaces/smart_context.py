"""Smart context interface for intelligent chunk context selection."""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass

from ..types import CodeChunk


@dataclass
class ContextMetadata:
    """Metadata about selected context."""
    relevance_score: float
    relationship_type: str  # 'dependency', 'usage', 'semantic', 'structural'
    distance: int  # How far away in the code structure
    token_count: int


class SmartContextProvider(ABC):
    """Provides intelligent context for chunks."""
    
    @abstractmethod
    def get_semantic_context(self, chunk: CodeChunk, max_tokens: int = 2000) -> Tuple[str, ContextMetadata]:
        """
        Get semantically relevant context for a chunk.
        
        This should include related functions, classes, or modules that are
        semantically connected to the chunk (similar functionality, same domain).
        
        Args:
            chunk: The chunk to get context for
            max_tokens: Maximum tokens for context
            
        Returns:
            Tuple of (context_string, metadata)
        """
        pass
    
    @abstractmethod
    def get_dependency_context(self, chunk: CodeChunk, chunks: List[CodeChunk]) -> List[Tuple[CodeChunk, ContextMetadata]]:
        """
        Get chunks that this chunk depends on.
        
        This includes imports, function calls, class inheritance, etc.
        
        Args:
            chunk: The chunk to analyze
            chunks: All available chunks to search
            
        Returns:
            List of (chunk, metadata) tuples for dependencies
        """
        pass
    
    @abstractmethod
    def get_usage_context(self, chunk: CodeChunk, chunks: List[CodeChunk]) -> List[Tuple[CodeChunk, ContextMetadata]]:
        """
        Get chunks that use this chunk.
        
        This includes all places where this chunk is imported, called, or referenced.
        
        Args:
            chunk: The chunk to analyze
            chunks: All available chunks to search
            
        Returns:
            List of (chunk, metadata) tuples for usages
        """
        pass
    
    @abstractmethod
    def get_structural_context(self, chunk: CodeChunk, chunks: List[CodeChunk]) -> List[Tuple[CodeChunk, ContextMetadata]]:
        """
        Get structurally related chunks.
        
        This includes parent classes, sibling methods, nested functions, etc.
        
        Args:
            chunk: The chunk to analyze
            chunks: All available chunks to search
            
        Returns:
            List of (chunk, metadata) tuples for structural relations
        """
        pass


class ContextStrategy(ABC):
    """Strategy for selecting context."""
    
    @abstractmethod
    def select_context(self, chunk: CodeChunk, candidates: List[Tuple[CodeChunk, ContextMetadata]], 
                      max_tokens: int) -> List[CodeChunk]:
        """
        Select the most relevant context chunks.
        
        Args:
            chunk: The main chunk
            candidates: List of (chunk, metadata) tuples to select from
            max_tokens: Maximum tokens to include
            
        Returns:
            Selected chunks ordered by relevance
        """
        pass
    
    @abstractmethod
    def rank_candidates(self, chunk: CodeChunk, 
                       candidates: List[Tuple[CodeChunk, ContextMetadata]]) -> List[Tuple[CodeChunk, float]]:
        """
        Rank candidate chunks by relevance.
        
        Args:
            chunk: The main chunk
            candidates: List of (chunk, metadata) tuples
            
        Returns:
            List of (chunk, score) tuples sorted by score descending
        """
        pass


class ContextCache(ABC):
    """Cache for context computations."""
    
    @abstractmethod
    def get(self, chunk_id: str, context_type: str) -> Optional[List[Tuple[CodeChunk, ContextMetadata]]]:
        """Get cached context if available."""
        pass
    
    @abstractmethod
    def set(self, chunk_id: str, context_type: str, 
            context: List[Tuple[CodeChunk, ContextMetadata]]) -> None:
        """Cache context for a chunk."""
        pass
    
    @abstractmethod
    def invalidate(self, chunk_ids: Optional[Set[str]] = None) -> None:
        """Invalidate cache entries."""
        pass