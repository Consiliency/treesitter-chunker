"""Base interfaces for tree-sitter chunker.

These are the foundation interfaces that all chunking strategies
and processors must implement.
"""
from abc import ABC, abstractmethod
from typing import Any

from tree_sitter import Node

from chunker.types import CodeChunk


class ChunkingStrategy(ABC):
    """Base interface for all chunking strategies.

    All chunking approaches (query-based, enhanced, fallback) must
    implement this interface to ensure compatibility.
    """

    @staticmethod
    @abstractmethod
    def can_handle(file_path: str, language: str) -> bool:
        """Check if this strategy can handle the given file.

        Args:
            file_path: Path to the file to chunk
            language: Language identifier (e.g., 'python', 'javascript')

        Returns:
            True if this strategy can handle the file, False otherwise
        """

    @staticmethod
    @abstractmethod
    def chunk(ast: Node, source: bytes, file_path: str, language: str) -> list[
        CodeChunk]:
        """Perform chunking on the AST.

        Args:
            ast: Root node of the parsed AST
            source: Original source code as bytes
            file_path: Path to the source file
            language: Language identifier

        Returns:
            List of code chunks extracted from the AST
        """

    @staticmethod
    @abstractmethod
    def configure(config: dict[str, Any]) -> None:
        """Configure the chunking strategy.

        Args:
            config: Configuration dictionary with strategy-specific options
        """


class ASTProcessor(ABC):
    """Base interface for AST processing.

    Provides a common interface for traversing and processing AST nodes.
    Used by context extractors, query engines, and visualizers.
    """

    @staticmethod
    @abstractmethod
    def process_node(node: Node, context: dict[str, Any]) -> Any:
        """Process a single AST node.

        Args:
            node: The AST node to process
            context: Processing context (parent, depth, etc.)

        Returns:
            Processing result (type depends on processor)
        """

    @staticmethod
    @abstractmethod
    def should_process_children(node: Node, context: dict[str, Any]) -> bool:
        """Determine if children of this node should be processed.

        Args:
            node: The current AST node
            context: Processing context

        Returns:
            True if children should be processed, False to skip
        """

    def traverse(self, node: Node, context: (dict[str, Any] | None) = None,
        ) -> Any:
        """Traverse the AST starting from the given node.

        This is a template method that uses process_node and
        should_process_children. Subclasses can override for
        custom traversal logic.

        Args:
            node: Starting node for traversal
            context: Initial context (default: empty dict)

        Returns:
            Accumulated results from processing
        """
        if context is None:
            context = {}
        result = self.process_node(node, context)
        if self.should_process_children(node, context):
            child_context = {**context, "parent": node}
            for child in node.children:
                self.traverse(child, child_context)
        return result


class ChunkFilter(ABC):
    """Interface for filtering chunks after extraction."""

    @staticmethod
    @abstractmethod
    def should_include(chunk: CodeChunk) -> bool:
        """Determine if a chunk should be included.

        Args:
            chunk: The chunk to evaluate

        Returns:
            True if chunk should be included, False to filter out
        """

    @staticmethod
    @abstractmethod
    def priority() -> int:
        """Get filter priority (lower numbers run first).

        Returns:
            Priority value for ordering multiple filters
        """


class ChunkMerger(ABC):
    """Interface for merging related chunks."""

    @staticmethod
    @abstractmethod
    def should_merge(chunk1: CodeChunk, chunk2: CodeChunk) -> bool:
        """Determine if two chunks should be merged.

        Args:
            chunk1: First chunk
            chunk2: Second chunk

        Returns:
            True if chunks should be merged
        """

    @staticmethod
    @abstractmethod
    def merge(chunks: list[CodeChunk]) -> CodeChunk:
        """Merge multiple chunks into one.

        Args:
            chunks: List of chunks to merge (at least 2)

        Returns:
            Merged chunk
        """
