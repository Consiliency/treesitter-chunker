"""Advanced query interface for Phase 10 - searching and filtering chunks."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from chunker.types import CodeChunk


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
    highlights: list[tuple[int, int]]  # Character positions to highlight
    metadata: dict[str, Any]  # Additional query-specific metadata


class ChunkQueryAdvanced(ABC):
    """Query chunks using natural language or structured queries."""

    @abstractmethod
    def search(
        self,
        query: str,
        chunks: list[CodeChunk],
        query_type: QueryType = QueryType.NATURAL_LANGUAGE,
        limit: int | None = None,
    ) -> list[QueryResult]:
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

    @abstractmethod
    def filter(
        self,
        chunks: list[CodeChunk],
        node_types: list[str] | None = None,
        languages: list[str] | None = None,
        min_lines: int | None = None,
        max_lines: int | None = None,
        metadata_filters: dict[str, Any] | None = None,
    ) -> list[CodeChunk]:
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

    @abstractmethod
    def find_similar(
        self,
        chunk: CodeChunk,
        chunks: list[CodeChunk],
        threshold: float = 0.7,
        limit: int | None = None,
    ) -> list[QueryResult]:
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


class QueryIndexAdvanced(ABC):
    """Advanced index for fast chunk queries."""

    @abstractmethod
    def build_index(self, chunks: list[CodeChunk]) -> None:
        """
        Build search index from chunks.

        This should create appropriate data structures for fast searching,
        such as inverted indices, embedding vectors, or AST indices.

        Args:
            chunks: Chunks to index
        """

    @abstractmethod
    def add_chunk(self, chunk: CodeChunk) -> None:
        """Add a single chunk to the index."""

    @abstractmethod
    def remove_chunk(self, chunk_id: str) -> None:
        """Remove a chunk from the index."""

    @abstractmethod
    def update_chunk(self, chunk: CodeChunk) -> None:
        """Update an existing chunk in the index."""

    @abstractmethod
    def query(
        self,
        query: str,
        query_type: QueryType = QueryType.NATURAL_LANGUAGE,
        limit: int = 10,
    ) -> list[QueryResult]:
        """
        Query the index.

        Args:
            query: Search query
            query_type: Type of query
            limit: Maximum results

        Returns:
            Query results sorted by relevance
        """

    @abstractmethod
    def get_statistics(self) -> dict[str, Any]:
        """Get index statistics (size, performance metrics, etc.)."""


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

    @abstractmethod
    def suggest_queries(self, partial_query: str, chunks: list[CodeChunk]) -> list[str]:
        """
        Suggest query completions based on indexed content.

        Args:
            partial_query: Partial query string
            chunks: Available chunks

        Returns:
            List of suggested queries
        """
