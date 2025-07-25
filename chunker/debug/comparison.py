"""
Chunk comparison implementation
"""

from typing import Any

from chunker.contracts.debug_contract import ChunkComparisonContract

from .tools.comparison import ChunkComparison as ToolsChunkComparison


class ChunkComparisonImpl(ChunkComparisonContract):
    """Implementation of chunk comparison contract"""

    def __init__(self) -> None:
        # Use the existing implementation from tools
        self._impl = ToolsChunkComparison()

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
        """
        return self._impl.compare_strategies(file_path, language, strategies)
