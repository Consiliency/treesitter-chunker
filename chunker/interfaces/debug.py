"""AST visualization and debugging interfaces.

Interfaces for tools that help developers understand and debug
Tree-sitter ASTs, queries, and chunking behavior.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from tree_sitter import Node

from chunker.types import CodeChunk

from .query import Query, QueryMatch


class VisualizationFormat(Enum):
    """Output formats for visualization."""
    TEXT = "text"
    HTML = "html"
    SVG = "svg"
    DOT = "dot"
    JSON = "json"
    INTERACTIVE = "interactive"


class HighlightStyle(Enum):
    """Styles for highlighting nodes."""
    SELECTED = "selected"
    MATCHED = "matched"
    CHUNK = "chunk"
    ERROR = "error"
    CONTEXT = "context"
    CAPTURE = "capture"


@dataclass
class NodeInfo:
    """Detailed information about an AST node.

    Attributes:
        node_type: Type of the node
        start_position: Start line and column
        end_position: End line and column
        field_name: Field name if this is a field
        is_named: Whether this is a named node
        has_error: Whether this node contains errors
        text: Text content of the node
        children_count: Number of children
    """
    node_type: str
    start_position: tuple[int, int]
    end_position: tuple[int, int]
    field_name: str | None
    is_named: bool
    has_error: bool
    text: str
    children_count: int


class ASTVisualizer(ABC):
    """Visualize Tree-sitter ASTs."""

    @staticmethod
    @abstractmethod
    def visualize(node: Node, source: bytes, fmt: VisualizationFormat =
        VisualizationFormat.TEXT) -> str:
        """Visualize an AST.

        Args:
            node: Root node to visualize
            source: Source code
            fmt: Output fmt

        Returns:
            Visualization in requested fmt
        """

    @staticmethod
    @abstractmethod
    def visualize_with_chunks(node: Node, source: bytes, chunks: list[
        CodeChunk], fmt: VisualizationFormat = VisualizationFormat.TEXT) -> str:
        """Visualize AST with chunk boundaries highlighted.

        Args:
            node: Root node
            source: Source code
            chunks: Chunks to highlight
            fmt: Output fmt

        Returns:
            Visualization with chunks
        """

    @staticmethod
    @abstractmethod
    def highlight_nodes(nodes: list[Node], style: HighlightStyle) -> None:
        """Highlight specific nodes in visualization.

        Args:
            nodes: Nodes to highlight
            style: Highlight style
        """

    @staticmethod
    @abstractmethod
    def set_max_depth(depth: int) -> None:
        """Set maximum depth to visualize.

        Args:
            depth: Maximum depth (0 for unlimited)
        """

    @staticmethod
    @abstractmethod
    def set_node_filter(filter_func: Any) -> None:
        """Set filter for which nodes to include.

        Args:
            filter_func: Function that returns True to include node
        """

    @staticmethod
    @abstractmethod
    def export_interactive(output_path: str) -> None:
        """Export an interactive visualization.

        Args:
            output_path: Path to save interactive visualization
        """


class QueryDebugger(ABC):
    """Debug Tree-sitter queries."""

    @staticmethod
    @abstractmethod
    def debug_query(query: Query, node: Node, source: bytes) -> list[dict[
        str, Any]]:
        """Debug a query execution.

        Args:
            query: Query to debug
            node: AST to run query on
            source: Source code

        Returns:
            List of debug information for each step
        """

    @staticmethod
    @abstractmethod
    def visualize_matches(matches: list[QueryMatch], node: Node, source:
        bytes, fmt: VisualizationFormat = VisualizationFormat.TEXT) -> str:
        """Visualize query matches.

        Args:
            matches: Query matches to visualize
            node: AST root
            source: Source code
            fmt: Output fmt

        Returns:
            Visualization of matches
        """

    @staticmethod
    @abstractmethod
    def explain_query(query_string: str, language: str) -> str:
        """Explain what a query does in plain language.

        Args:
            query_string: Query to explain
            language: Language the query is for

        Returns:
            Human-readable explanation
        """

    @staticmethod
    @abstractmethod
    def validate_captures(query: Query, expected_captures: list[str]) -> list[
        str]:
        """Validate that query has expected captures.

        Args:
            query: Query to validate
            expected_captures: Expected capture names

        Returns:
            List of missing captures
        """

    @staticmethod
    @abstractmethod
    def generate_test_cases(query_string: str, language: str) -> list[tuple[
        str, bool]]:
        """Generate test cases for a query.

        Args:
            query_string: Query to test
            language: Language for test cases

        Returns:
            List of (code_sample, should_match) tuples
        """


class ChunkDebugger(ABC):
    """Debug chunking behavior."""

    @staticmethod
    @abstractmethod
    def trace_chunking(node: Node, source: bytes, language: str) -> list[dict
        [str, Any]]:
        """Trace the chunking process.

        Args:
            node: AST to chunk
            source: Source code
            language: Language being chunked

        Returns:
            List of trace steps
        """

    @staticmethod
    @abstractmethod
    def analyze_chunk_distribution(chunks: list[CodeChunk]) -> dict[str, Any]:
        """Analyze statistical distribution of chunks.

        Args:
            chunks: Chunks to analyze

        Returns:
            Statistics about chunk distribution
        """

    @staticmethod
    @abstractmethod
    def find_orphaned_code(node: Node, source: bytes, chunks: list[CodeChunk],
        ) -> list[tuple[int, int]]:
        """Find code not included in any chunk.

        Args:
            node: Full AST
            source: Source code
            chunks: Generated chunks

        Returns:
            List of (start_byte, end_byte) ranges not chunked
        """

    @staticmethod
    @abstractmethod
    def suggest_chunk_improvements(chunks: list[CodeChunk]) -> list[str]:
        """Suggest improvements to chunking.

        Args:
            chunks: Current chunks

        Returns:
            List of improvement suggestions
        """


class NodeExplorer(ABC):
    """Interactive AST node explorer."""

    @staticmethod
    @abstractmethod
    def get_node_info(node: Node, source: bytes) -> NodeInfo:
        """Get detailed information about a node.

        Args:
            node: Node to inspect
            source: Source code

        Returns:
            Detailed node information
        """

    @staticmethod
    @abstractmethod
    def get_node_at_position(root: Node, line: int, column: int) -> (Node | None
        ):
        """Find node at specific position.

        Args:
            root: Root node
            line: Line number (0-based)
            column: Column number (0-based)

        Returns:
            Node at position or None
        """

    @staticmethod
    @abstractmethod
    def get_node_path(node: Node, root: Node) -> list[Node]:
        """Get path from root to node.

        Args:
            node: Target node
            root: Root node

        Returns:
            List of nodes from root to target
        """

    @staticmethod
    @abstractmethod
    def find_similar_nodes(node: Node, root: Node, max_results: int = 10) -> list[
        Node]:
        """Find nodes similar to given node.

        Args:
            node: Example node
            root: Root to search
            max_results: Maximum results to return

        Returns:
            List of similar nodes
        """


class PerformanceProfiler(ABC):
    """Profile Tree-sitter performance."""

    @staticmethod
    @abstractmethod
    def profile_parsing(source: bytes, language: str, iterations: int = 100,
        ) -> dict[str, float]:
        """Profile parsing performance.

        Args:
            source: Source to parse
            language: Language to use
            iterations: Number of iterations

        Returns:
            Performance metrics
        """

    @staticmethod
    @abstractmethod
    def profile_query(query: Query, node: Node, iterations: int = 100) -> dict[
        str, float]:
        """Profile query performance.

        Args:
            query: Query to profile
            node: AST to query
            iterations: Number of iterations

        Returns:
            Performance metrics
        """

    @staticmethod
    @abstractmethod
    def compare_strategies(strategies: list[str], source: bytes, language: str,
        ) -> dict[str, dict[str, float]]:
        """Compare performance of different strategies.

        Args:
            strategies: Strategy names to compare
            source: Source code
            language: Language

        Returns:
            Comparative metrics
        """
