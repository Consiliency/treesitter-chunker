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

    @abstractmethod
    def visualize(
        self,
        node: Node,
        source: bytes,
        format: VisualizationFormat = VisualizationFormat.TEXT,
    ) -> str:
        """Visualize an AST.

        Args:
            node: Root node to visualize
            source: Source code
            format: Output format

        Returns:
            Visualization in requested format
        """

    @abstractmethod
    def visualize_with_chunks(
        self,
        node: Node,
        source: bytes,
        chunks: list[CodeChunk],
        format: VisualizationFormat = VisualizationFormat.TEXT,
    ) -> str:
        """Visualize AST with chunk boundaries highlighted.

        Args:
            node: Root node
            source: Source code
            chunks: Chunks to highlight
            format: Output format

        Returns:
            Visualization with chunks
        """

    @abstractmethod
    def highlight_nodes(self, nodes: list[Node], style: HighlightStyle) -> None:
        """Highlight specific nodes in visualization.

        Args:
            nodes: Nodes to highlight
            style: Highlight style
        """

    @abstractmethod
    def set_max_depth(self, depth: int) -> None:
        """Set maximum depth to visualize.

        Args:
            depth: Maximum depth (0 for unlimited)
        """

    @abstractmethod
    def set_node_filter(self, filter_func: Any) -> None:  # Callable[[Node], bool]
        """Set filter for which nodes to include.

        Args:
            filter_func: Function that returns True to include node
        """

    @abstractmethod
    def export_interactive(self, output_path: str) -> None:
        """Export an interactive visualization.

        Args:
            output_path: Path to save interactive visualization
        """


class QueryDebugger(ABC):
    """Debug Tree-sitter queries."""

    @abstractmethod
    def debug_query(
        self,
        query: Query,
        node: Node,
        source: bytes,
    ) -> list[dict[str, Any]]:
        """Debug a query execution.

        Args:
            query: Query to debug
            node: AST to run query on
            source: Source code

        Returns:
            List of debug information for each step
        """

    @abstractmethod
    def visualize_matches(
        self,
        matches: list[QueryMatch],
        node: Node,
        source: bytes,
        format: VisualizationFormat = VisualizationFormat.TEXT,
    ) -> str:
        """Visualize query matches.

        Args:
            matches: Query matches to visualize
            node: AST root
            source: Source code
            format: Output format

        Returns:
            Visualization of matches
        """

    @abstractmethod
    def explain_query(self, query_string: str, language: str) -> str:
        """Explain what a query does in plain language.

        Args:
            query_string: Query to explain
            language: Language the query is for

        Returns:
            Human-readable explanation
        """

    @abstractmethod
    def validate_captures(
        self,
        query: Query,
        expected_captures: list[str],
    ) -> list[str]:
        """Validate that query has expected captures.

        Args:
            query: Query to validate
            expected_captures: Expected capture names

        Returns:
            List of missing captures
        """

    @abstractmethod
    def generate_test_cases(
        self,
        query_string: str,
        language: str,
    ) -> list[tuple[str, bool]]:
        """Generate test cases for a query.

        Args:
            query_string: Query to test
            language: Language for test cases

        Returns:
            List of (code_sample, should_match) tuples
        """


class ChunkDebugger(ABC):
    """Debug chunking behavior."""

    @abstractmethod
    def trace_chunking(
        self,
        node: Node,
        source: bytes,
        language: str,
    ) -> list[dict[str, Any]]:
        """Trace the chunking process.

        Args:
            node: AST to chunk
            source: Source code
            language: Language being chunked

        Returns:
            List of trace steps
        """

    @abstractmethod
    def analyze_chunk_distribution(self, chunks: list[CodeChunk]) -> dict[str, Any]:
        """Analyze statistical distribution of chunks.

        Args:
            chunks: Chunks to analyze

        Returns:
            Statistics about chunk distribution
        """

    @abstractmethod
    def find_orphaned_code(
        self,
        node: Node,
        source: bytes,
        chunks: list[CodeChunk],
    ) -> list[tuple[int, int]]:
        """Find code not included in any chunk.

        Args:
            node: Full AST
            source: Source code
            chunks: Generated chunks

        Returns:
            List of (start_byte, end_byte) ranges not chunked
        """

    @abstractmethod
    def suggest_chunk_improvements(self, chunks: list[CodeChunk]) -> list[str]:
        """Suggest improvements to chunking.

        Args:
            chunks: Current chunks

        Returns:
            List of improvement suggestions
        """


class NodeExplorer(ABC):
    """Interactive AST node explorer."""

    @abstractmethod
    def get_node_info(self, node: Node, source: bytes) -> NodeInfo:
        """Get detailed information about a node.

        Args:
            node: Node to inspect
            source: Source code

        Returns:
            Detailed node information
        """

    @abstractmethod
    def get_node_at_position(self, root: Node, line: int, column: int) -> Node | None:
        """Find node at specific position.

        Args:
            root: Root node
            line: Line number (0-based)
            column: Column number (0-based)

        Returns:
            Node at position or None
        """

    @abstractmethod
    def get_node_path(self, node: Node, root: Node) -> list[Node]:
        """Get path from root to node.

        Args:
            node: Target node
            root: Root node

        Returns:
            List of nodes from root to target
        """

    @abstractmethod
    def find_similar_nodes(
        self,
        node: Node,
        root: Node,
        max_results: int = 10,
    ) -> list[Node]:
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

    @abstractmethod
    def profile_parsing(
        self,
        source: bytes,
        language: str,
        iterations: int = 100,
    ) -> dict[str, float]:
        """Profile parsing performance.

        Args:
            source: Source to parse
            language: Language to use
            iterations: Number of iterations

        Returns:
            Performance metrics
        """

    @abstractmethod
    def profile_query(
        self,
        query: Query,
        node: Node,
        iterations: int = 100,
    ) -> dict[str, float]:
        """Profile query performance.

        Args:
            query: Query to profile
            node: AST to query
            iterations: Number of iterations

        Returns:
            Performance metrics
        """

    @abstractmethod
    def compare_strategies(
        self,
        strategies: list[str],
        source: bytes,
        language: str,
    ) -> dict[str, dict[str, float]]:
        """Compare performance of different strategies.

        Args:
            strategies: Strategy names to compare
            source: Source code
            language: Language

        Returns:
            Comparative metrics
        """
