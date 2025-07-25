"""
Debug visualization implementation
"""

from typing import Any, Union

from chunker.contracts.debug_contract import DebugVisualizationContract

from .tools.visualization import DebugVisualization as ToolsDebugVisualization


class DebugVisualizationImpl(DebugVisualizationContract):
    """Implementation of debug visualization contract"""

    def __init__(self) -> None:
        # Use the existing implementation from tools
        self._impl = ToolsDebugVisualization()

    def visualize_ast(
        self,
        file_path: str,
        language: str,
        output_format: str = "svg",
    ) -> Union[str, bytes]:
        """
        Generate visual representation of the AST for a file

        Args:
            file_path: Path to source file
            language: Programming language
            output_format: Output format (svg, png, dot, json)

        Returns:
            Visualization data in requested format
        """
        return self._impl.visualize_ast(file_path, language, output_format)

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
        """
        return self._impl.inspect_chunk(file_path, chunk_id, include_context)

    def profile_chunking(self, file_path: str, language: str) -> dict[str, Any]:
        """
        Profile the chunking process for performance analysis

        Args:
            file_path: Path to source file
            language: Programming language

        Returns:
            Performance metrics including timing, memory usage, chunk stats
        """
        return self._impl.profile_chunking(file_path, language)

    def debug_mode_chunking(
        self,
        file_path: str,
        language: str,
        breakpoints: Union[list[str], None] = None,
    ) -> dict[str, Any]:
        """
        Run chunking in debug mode with detailed trace information

        Args:
            file_path: Path to source file
            language: Programming language
            breakpoints: List of node types to break on

        Returns:
            Step-by-step trace of chunking process
        """
        return self._impl.debug_mode_chunking(file_path, language, breakpoints)
