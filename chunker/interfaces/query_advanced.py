"""Advanced query interface for Phase 10 - searching and filtering chunks."""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum

from ..types import CodeChunk


class QueryType(Enum):
    """Types of queries supported."""
    NATURAL_LANGUAGE = "natural_language"
    STRUCTURED = "structured"
    REGEX = "regex"
    AST_PATTERN = "ast_pattern"


@dataclass
class QueryResult:
    """Result of a chunk query."""
    chunk: CodeChunk
    score: float  # Relevance score 0-1
    highlights: List[Tuple[int, int]]  # Character positions to highlight
    metadata: Dict[str, Any]  # Additional query-specific metadata


class ChunkQueryAdvanced(ABC):
    """Query chunks using natural language or structured queries."""
    
    @abstractmethod
    def search(self, query: str, chunks: List[CodeChunk], 
              query_type: QueryType = QueryType.NATURAL_LANGUAGE,
              limit: Optional[int] = None) -> List[QueryResult]:
        """
        Search chunks using various query types.
        
        Args:
            query: The search query
            chunks: Chunks to search through
            query_type: Type of query to perform
            limit: Maximum results to return
            
        Returns:
            List of query results sorted by relevance
        """
        pass
    
    @abstractmethod
    def filter(self, chunks: List[CodeChunk], 
              node_types: Optional[List[str]] = None,
              languages: Optional[List[str]] = None,
              min_lines: Optional[int] = None,
              max_lines: Optional[int] = None,
              metadata_filters: Optional[Dict[str, Any]] = None) -> List[CodeChunk]:
        """
        Filter chunks by structured criteria.
        
        Args:
            chunks: Chunks to filter
            node_types: Filter by node types (e.g., 'function_definition')
            languages: Filter by languages
            min_lines: Minimum line count
            max_lines: Maximum line count
            metadata_filters: Filter by metadata fields
            
        Returns:
            Filtered chunks
        """
        pass
    
    @abstractmethod
    def find_similar(self, chunk: CodeChunk, chunks: List[CodeChunk], 
                    threshold: float = 0.7, limit: Optional[int] = None) -> List[QueryResult]:
        """
        Find chunks similar to a given chunk.
        
        Args:
            chunk: Reference chunk
            chunks: Chunks to search
            threshold: Minimum similarity score (0-1)
            limit: Maximum results
            
        Returns:
            Similar chunks sorted by similarity
        """
        pass


class QueryIndexAdvanced(ABC):
    """Advanced index for fast chunk queries."""
    
    @abstractmethod
    def build_index(self, chunks: List[CodeChunk]) -> None:
        """
        Build search index from chunks.
        
        This should create appropriate data structures for fast searching,
        such as inverted indices, embedding vectors, or AST indices.
        
        Args:
            chunks: Chunks to index
        """
        pass
    
    @abstractmethod
    def add_chunk(self, chunk: CodeChunk) -> None:
        """Add a single chunk to the index."""
        pass
    
    @abstractmethod
    def remove_chunk(self, chunk_id: str) -> None:
        """Remove a chunk from the index."""
        pass
    
    @abstractmethod
    def update_chunk(self, chunk: CodeChunk) -> None:
        """Update an existing chunk in the index."""
        pass
    
    @abstractmethod
    def query(self, query: str, query_type: QueryType = QueryType.NATURAL_LANGUAGE,
             limit: int = 10) -> List[QueryResult]:
        """
        Query the index.
        
        Args:
            query: Search query
            query_type: Type of query
            limit: Maximum results
            
        Returns:
            Query results sorted by relevance
        """
        pass
    
    @abstractmethod
    def get_statistics(self) -> Dict[str, Any]:
        """Get index statistics (size, performance metrics, etc.)."""
        pass


class QueryOptimizer(ABC):
    """Optimize queries for better performance."""
    
    @abstractmethod
    def optimize_query(self, query: str, query_type: QueryType) -> str:
        """
        Optimize a query for better results.
        
        This might include query expansion, spell correction, or rewriting.
        
        Args:
            query: Original query
            query_type: Type of query
            
        Returns:
            Optimized query
        """
        pass
    
    @abstractmethod
    def suggest_queries(self, partial_query: str, chunks: List[CodeChunk]) -> List[str]:
        """
        Suggest query completions based on indexed content.
        
        Args:
            partial_query: Partial query string
            chunks: Available chunks
            
        Returns:
            List of suggested queries
        """
        pass