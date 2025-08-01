"""Metadata extraction interfaces for enriching chunks with additional information."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from tree_sitter import Node


@dataclass
class ComplexityMetrics:
    """Code complexity metrics."""
    cyclomatic: int
    cognitive: int
    nesting_depth: int
    lines_of_code: int
    logical_lines: int


@dataclass
class SignatureInfo:
    """Function/method signature information."""
    name: str
    parameters: list[dict[str, Any]]
    return_type: str | None
    decorators: list[str]
    modifiers: list[str]


class MetadataExtractor(ABC):
    """Extract rich metadata from AST nodes."""

    @staticmethod
    @abstractmethod
    def extract_signature(node: Node, source: bytes) -> (SignatureInfo | None):
        """
        Extract function/method signature information.

        Args:
            node: AST node (should be a function/method)
            source: Source code bytes

        Returns:
            Signature information or None
        """

    @staticmethod
    @abstractmethod
    def extract_docstring(node: Node, source: bytes) -> (str | None):
        """
        Extract docstring/comment from a node.

        Args:
            node: AST node
            source: Source code bytes

        Returns:
            Docstring text or None
        """

    @staticmethod
    @abstractmethod
    def extract_imports(node: Node, source: bytes) -> list[str]:
        """
        Extract import statements used within a node.

        Args:
            node: AST node
            source: Source code bytes

        Returns:
            List of import statements
        """

    @staticmethod
    @abstractmethod
    def extract_dependencies(node: Node, source: bytes) -> set[str]:
        """
        Extract symbols that this chunk depends on.

        Args:
            node: AST node
            source: Source code bytes

        Returns:
            Set of dependency symbols
        """

    @staticmethod
    @abstractmethod
    def extract_exports(node: Node, source: bytes) -> set[str]:
        """
        Extract symbols that this chunk exports/defines.

        Args:
            node: AST node
            source: Source code bytes

        Returns:
            Set of exported symbols
        """


class ComplexityAnalyzer(ABC):
    """Analyze code complexity metrics."""

    @staticmethod
    @abstractmethod
    def calculate_cyclomatic_complexity(node: Node) -> int:
        """
        Calculate cyclomatic complexity of a code node.

        Counts decision points (if, while, for, etc.).

        Args:
            node: AST node

        Returns:
            Cyclomatic complexity score
        """

    @staticmethod
    @abstractmethod
    def calculate_cognitive_complexity(node: Node) -> int:
        """
        Calculate cognitive complexity of a code node.

        Considers nesting, recursion, and logical operators.

        Args:
            node: AST node

        Returns:
            Cognitive complexity score
        """

    @staticmethod
    @abstractmethod
    def calculate_nesting_depth(node: Node) -> int:
        """
        Calculate maximum nesting depth.

        Args:
            node: AST node

        Returns:
            Maximum nesting level
        """

    @staticmethod
    @abstractmethod
    def count_logical_lines(node: Node, source: bytes) -> int:
        """
        Count logical lines of code (excluding comments and blanks).

        Args:
            node: AST node
            source: Source code bytes

        Returns:
            Number of logical lines
        """

    @staticmethod
    @abstractmethod
    def analyze_complexity(node: Node, source: bytes) -> ComplexityMetrics:
        """
        Perform complete complexity analysis.

        Args:
            node: AST node
            source: Source code bytes

        Returns:
            All complexity metrics
        """
