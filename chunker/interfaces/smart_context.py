"""Smart context interface for intelligent chunk context selection."""
import builtins
from abc import ABC, abstractmethod
from dataclasses import dataclass

from chunker.types import CodeChunk


@dataclass
class ContextMetadata:
    """Metadata about selected context."""
    relevance_score: float
    relationship_type: str
    distance: int
    token_count: int


class SmartContextProvider(ABC):
    """Provides intelligent context for chunks."""

    @staticmethod
    @abstractmethod
    def get_semantic_context(chunk: CodeChunk, max_tokens: int = 2000) -> tuple[
        str, ContextMetadata]:
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

    @staticmethod
    @abstractmethod
    def get_dependency_context(chunk: CodeChunk, chunks: list[CodeChunk],
        ) -> list[tuple[CodeChunk, ContextMetadata]]:
        """
        Get chunks that this chunk depends on.

        This includes imports, function calls, class inheritance, etc.

        Args:
            chunk: The chunk to analyze
            chunks: All available chunks to search

        Returns:
            List of (chunk, metadata) tuples for dependencies
        """

    @staticmethod
    @abstractmethod
    def get_usage_context(chunk: CodeChunk, chunks: list[CodeChunk]) -> list[
        tuple[CodeChunk, ContextMetadata]]:
        """
        Get chunks that use this chunk.

        This includes all places where this chunk is imported, called, or referenced.

        Args:
            chunk: The chunk to analyze
            chunks: All available chunks to search

        Returns:
            List of (chunk, metadata) tuples for usages
        """

    @staticmethod
    @abstractmethod
    def get_structural_context(chunk: CodeChunk, chunks: list[CodeChunk],
        ) -> list[tuple[CodeChunk, ContextMetadata]]:
        """
        Get structurally related chunks.

        This includes parent classes, sibling methods, nested functions, etc.

        Args:
            chunk: The chunk to analyze
            chunks: All available chunks to search

        Returns:
            List of (chunk, metadata) tuples for structural relations
        """


class ContextStrategy(ABC):
    """Strategy for selecting context."""

    @staticmethod
    @abstractmethod
    def select_context(chunk: CodeChunk, candidates: list[tuple[CodeChunk,
        ContextMetadata]], max_tokens: int) -> list[CodeChunk]:
        """
        Select the most relevant context chunks.

        Args:
            chunk: The main chunk
            candidates: List of (chunk, metadata) tuples to select from
            max_tokens: Maximum tokens to include

        Returns:
            Selected chunks ordered by relevance
        """

    @staticmethod
    @abstractmethod
    def rank_candidates(chunk: CodeChunk, candidates: list[tuple[CodeChunk,
        ContextMetadata]]) -> list[tuple[CodeChunk, float]]:
        """
        Rank candidate chunks by relevance.

        Args:
            chunk: The main chunk
            candidates: List of (chunk, metadata) tuples

        Returns:
            List of (chunk, score) tuples sorted by score descending
        """


class ContextCache(ABC):
    """Cache for context computations."""

    @staticmethod
    @abstractmethod
    def get(chunk_id: str, context_type: str) -> (list[tuple[CodeChunk,
        ContextMetadata]] | None):
        """Get cached context if available."""

    @staticmethod
    @abstractmethod
    def set(chunk_id: str, context_type: str, context: list[tuple[CodeChunk,
        ContextMetadata]]) -> None:
        """Cache context for a chunk."""

    @staticmethod
    @abstractmethod
    def invalidate(chunk_ids: (builtins.set[str] | None) = None) -> None:
        """Invalidate cache entries."""
