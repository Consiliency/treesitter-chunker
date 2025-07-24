"""
Contract for Debug Tools Component
Defines the interface for AST visualization and chunk inspection tools
"""

from abc import ABC, abstractmethod
from typing import Any


class DebugVisualizationContract(ABC):
    """Contract for AST and chunk visualization"""

    @abstractmethod
    def visualize_ast(
        self,
        file_path: str,
        language: str,
        output_format: str = "svg",
    ) -> str | bytes:
        """
        Generate visual representation of the AST for a file

        Args:
            file_path: Path to source file
            language: Programming language
            output_format: Output format (svg, png, dot, json)

        Returns:
            Visualization data in requested format

        Preconditions:
            - file_path exists and is readable
            - language is supported by the chunker
            - output_format is one of: svg, png, dot, json

        Postconditions:
            - Returns valid visualization data
            - Original file is unchanged
        """
        raise NotImplementedError("Debug Tools team will implement")

    @abstractmethod
    def inspect_chunk(
        self,
        file_path: str,
        chunk_id: str,
        include_context: bool = True,
    ) -> dict[str, Any]:
        """
        Inspect details of a specific chunk

        Args:
            file_path: Path to source file
            chunk_id: ID of chunk to inspect
            include_context: Include surrounding context

        Returns:
            Detailed chunk information including metadata, bounds, relationships

        Preconditions:
            - file_path exists
            - chunk_id is valid for this file

        Postconditions:
            - Returns complete chunk details
            - Includes all metadata and relationships
        """
        raise NotImplementedError("Debug Tools team will implement")

    @abstractmethod
    def profile_chunking(self, file_path: str, language: str) -> dict[str, Any]:
        """
        Profile the chunking process for performance analysis

        Args:
            file_path: Path to source file
            language: Programming language

        Returns:
            Performance metrics including timing, memory usage, chunk stats

        Preconditions:
            - file_path exists
            - language is supported

        Postconditions:
            - Returns comprehensive performance data
            - Includes timing for each phase
        """
        raise NotImplementedError("Debug Tools team will implement")

    @abstractmethod
    def debug_mode_chunking(
        self,
        file_path: str,
        language: str,
        breakpoints: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Run chunking in debug mode with detailed trace information

        Args:
            file_path: Path to source file
            language: Programming language
            breakpoints: List of node types to break on

        Returns:
            Step-by-step trace of chunking process

        Preconditions:
            - file_path exists
            - language is supported

        Postconditions:
            - Returns detailed trace information
            - Includes decision points and rule applications
        """
        raise NotImplementedError("Debug Tools team will implement")


class ChunkComparisonContract(ABC):
    """Contract for comparing chunking strategies"""

    @abstractmethod
    def compare_strategies(
        self,
        file_path: str,
        language: str,
        strategies: list[str],
    ) -> dict[str, Any]:
        """
        Compare different chunking strategies on the same file

        Args:
            file_path: Path to source file
            language: Programming language
            strategies: List of strategy names to compare

        Returns:
            Comparison data including chunk counts, sizes, overlaps

        Preconditions:
            - All strategies are valid
            - File and language are supported

        Postconditions:
            - Returns detailed comparison metrics
            - Includes visual diff if applicable
        """
        raise NotImplementedError("Debug Tools team will implement")
