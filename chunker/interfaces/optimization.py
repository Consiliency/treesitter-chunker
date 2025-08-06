"""Chunk optimization interface for adapting chunks to specific use cases."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from chunker.types import CodeChunk


class OptimizationStrategy(Enum):
    """Optimization strategies."""

    AGGRESSIVE = "aggressive"
    CONSERVATIVE = "conservative"
    BALANCED = "balanced"


@dataclass
class OptimizationMetrics:
    """Metrics for optimization results."""

    original_count: int
    optimized_count: int
    avg_tokens_before: float
    avg_tokens_after: float
    coherence_score: float
    token_efficiency: float


class ChunkOptimizer(ABC):
    """Optimize chunk boundaries for specific use cases."""

    @staticmethod
    @abstractmethod
    def optimize_for_llm(
        chunks: list[CodeChunk],
        model: str,
        max_tokens: int,
        strategy: OptimizationStrategy = OptimizationStrategy.BALANCED,
    ) -> tuple[list[CodeChunk], OptimizationMetrics]:
        """
        Optimize chunks for LLM consumption.

        This should consider the model's context window, optimal chunk sizes,
        and maintaining semantic coherence.

        Args:
            chunks: Original chunks
            model: LLM model name (e.g., 'gpt-4', 'claude-3')
            max_tokens: Maximum tokens per chunk
            strategy: Optimization strategy

        Returns:
            Tuple of (optimized chunks, metrics)
        """

    @staticmethod
    @abstractmethod
    def merge_small_chunks(
        chunks: list[CodeChunk],
        min_tokens: int,
        preserve_boundaries: bool = True,
    ) -> list[CodeChunk]:
        """
        Merge chunks that are too small.

        Args:
            chunks: Chunks to process
            min_tokens: Minimum tokens per chunk
            preserve_boundaries: If True, only merge related chunks

        Returns:
            Merged chunks
        """

    @staticmethod
    @abstractmethod
    def split_large_chunks(
        chunks: list[CodeChunk],
        max_tokens: int,
        split_points: list[str] | None = None,
    ) -> list[CodeChunk]:
        """
        Split chunks that are too large.

        Args:
            chunks: Chunks to process
            max_tokens: Maximum tokens per chunk
            split_points: Preferred split points (e.g., ['def ', 'class ', '\\n\\n'])

        Returns:
            Split chunks
        """

    @staticmethod
    @abstractmethod
    def rebalance_chunks(
        chunks: list[CodeChunk],
        target_tokens: int,
        variance: float = 0.2,
    ) -> list[CodeChunk]:
        """
        Rebalance chunks to have similar sizes.

        Args:
            chunks: Chunks to rebalance
            target_tokens: Target token count per chunk
            variance: Acceptable variance (0.2 = ±20%)

        Returns:
            Rebalanced chunks
        """

    @staticmethod
    @abstractmethod
    def optimize_for_embedding(
        chunks: list[CodeChunk],
        embedding_model: str,
        max_tokens: int = 512,
    ) -> list[CodeChunk]:
        """
        Optimize chunks for embedding generation.

        Embedding models often have stricter token limits and benefit from
        semantically coherent chunks.

        Args:
            chunks: Original chunks
            embedding_model: Embedding model name
            max_tokens: Maximum tokens for embedding

        Returns:
            Optimized chunks
        """


class ChunkBoundaryAnalyzer(ABC):
    """Analyze and suggest optimal chunk boundaries."""

    @staticmethod
    @abstractmethod
    def find_natural_boundaries(content: str, language: str) -> list[int]:
        """
        Find natural boundary points in code.

        Args:
            content: Code content
            language: Programming language

        Returns:
            List of character positions that are good split points
        """

    @staticmethod
    @abstractmethod
    def score_boundary(content: str, position: int, language: str) -> float:
        """
        Score how good a boundary point is.

        Args:
            content: Code content
            position: Character position
            language: Programming language

        Returns:
            Score 0-1, higher is better
        """

    @staticmethod
    @abstractmethod
    def suggest_merge_points(chunks: list[CodeChunk]) -> list[tuple[int, int, float]]:
        """
        Suggest which chunks to merge.

        Args:
            chunks: List of chunks

        Returns:
            List of (chunk1_idx, chunk2_idx, score) tuples
        """


class OptimizationConfig:
    """Configuration for chunk optimization."""

    def __init__(self):
        self.preserve_structure = True
        self.maintain_context = True
        self.optimize_imports = True
        self.min_chunk_tokens = 50
        self.max_chunk_tokens = 2000
        self.target_chunk_tokens = 500
        self.merge_threshold = 0.7
        self.split_threshold = 0.3
