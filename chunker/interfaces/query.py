"""Tree-sitter query interfaces.

Interfaces for implementing Tree-sitter's query language support,
enabling pattern-based chunk extraction.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from tree_sitter import Node

from ..types import CodeChunk
from .base import ChunkingStrategy


@dataclass
class QueryMatch:
    """Represents a match from a Tree-sitter query.

    Attributes:
        pattern_index: Index of the pattern that matched
        captures: Dictionary mapping capture names to nodes
        start_byte: Start byte position of the match
        end_byte: End byte position of the match
    """

    pattern_index: int
    captures: dict[str, Node]
    start_byte: int
    end_byte: int

    def get_capture(self, name: str) -> Node | None:
        """Get a captured node by name.

        Args:
            name: Capture name (e.g., 'function', 'class')

        Returns:
            Captured node or None if not found
        """
        return self.captures.get(name)


class Query(ABC):
    """Abstract representation of a parsed Tree-sitter query."""

    @abstractmethod
    def pattern_count(self) -> int:
        """Get the number of patterns in this query.

        Returns:
            Number of patterns
        """

    @abstractmethod
    def capture_names(self) -> list[str]:
        """Get all capture names defined in the query.

        Returns:
            List of capture names
        """

    @abstractmethod
    def disable_pattern(self, pattern_index: int) -> None:
        """Disable a specific pattern in the query.

        Args:
            pattern_index: Index of the pattern to disable
        """

    @abstractmethod
    def is_pattern_enabled(self, pattern_index: int) -> bool:
        """Check if a pattern is enabled.

        Args:
            pattern_index: Index of the pattern to check

        Returns:
            True if pattern is enabled
        """


class QueryEngine(ABC):
    """Engine for parsing and executing Tree-sitter queries."""

    @abstractmethod
    def parse_query(self, query_string: str, language: str) -> Query:
        """Parse a Tree-sitter query string.

        Args:
            query_string: Query in Tree-sitter query syntax
            language: Language the query is for

        Returns:
            Parsed query object

        Raises:
            QuerySyntaxError: If query syntax is invalid
        """

    @abstractmethod
    def execute_query(self, ast: Node, query: Query) -> list[QueryMatch]:
        """Execute a query on an AST.

        Args:
            ast: Root node of the AST to query
            query: Parsed query to execute

        Returns:
            List of matches found
        """

    @abstractmethod
    def validate_query(
        self,
        query_string: str,
        language: str,
    ) -> tuple[bool, str | None]:
        """Validate a query without executing it.

        Args:
            query_string: Query to validate
            language: Language the query is for

        Returns:
            Tuple of (is_valid, error_message)
        """


class QueryBasedChunker(ChunkingStrategy):
    """Chunking strategy that uses Tree-sitter queries."""

    @abstractmethod
    def set_query(self, query_string: str) -> None:
        """Set the query for chunking.

        Args:
            query_string: Tree-sitter query defining chunks
        """

    @abstractmethod
    def add_query(self, name: str, query_string: str) -> None:
        """Add a named query to the chunker.

        Args:
            name: Name for the query (e.g., 'functions', 'classes')
            query_string: Tree-sitter query
        """

    @abstractmethod
    def remove_query(self, name: str) -> None:
        """Remove a named query.

        Args:
            name: Name of the query to remove
        """

    @abstractmethod
    def list_queries(self) -> dict[str, str]:
        """Get all registered queries.

        Returns:
            Dictionary mapping query names to query strings
        """

    @abstractmethod
    def merge_query_results(
        self,
        matches: list[QueryMatch],
        source: bytes,
    ) -> list[CodeChunk]:
        """Convert query matches to chunks.

        Args:
            matches: List of query matches
            source: Original source code

        Returns:
            List of code chunks
        """


class QueryBuilder(ABC):
    """Interface for building queries programmatically."""

    @abstractmethod
    def match_node_type(self, node_type: str) -> "QueryBuilder":
        """Add a node type matcher.

        Args:
            node_type: Type of node to match

        Returns:
            Self for chaining
        """

    @abstractmethod
    def capture(self, name: str) -> "QueryBuilder":
        """Capture the current node.

        Args:
            name: Name for the capture

        Returns:
            Self for chaining
        """

    @abstractmethod
    def with_child(self, child_pattern: str) -> "QueryBuilder":
        """Add a child pattern requirement.

        Args:
            child_pattern: Pattern the node must have as a child

        Returns:
            Self for chaining
        """

    @abstractmethod
    def build(self) -> str:
        """Build the query string.

        Returns:
            Tree-sitter query string
        """


# Example query strings for documentation
EXAMPLE_QUERIES = {
    "python_async_functions": """
        (async_function_definition
            name: (identifier) @function_name
            parameters: (parameters) @params
            body: (block) @body) @async_function
    """,
    "javascript_classes": """
        (class_declaration
            name: (identifier) @class_name
            body: (class_body
                (method_definition) @method)) @class
    """,
    "decorated_functions": """
        (decorated_definition
            decorator: (decorator) @decorator
            definition: (function_definition
                name: (identifier) @function_name)) @decorated_func
    """,
}
