from abc import ABC, abstractmethod

from tree_sitter import Node


class ExtendedLanguagePluginContract(ABC):
    """Extended contract that all new language plugins must implement"""

    @staticmethod
    @abstractmethod
    def get_semantic_chunks(node: Node, source: bytes) -> list[dict[str, any]]:
        """Extract semantic chunks specific to this language

        Args:
            node: Tree-sitter parse tree root
            source: Source code bytes

        Returns:
            List of chunk dictionaries with metadata

        Preconditions:
            - node must be valid parse tree
            - source must match the parsed content

        Postconditions:
            - Returns non-overlapping chunks
            - Each chunk has required fields: type, start_line, end_line, content
        """

    @staticmethod
    @abstractmethod
    def get_chunk_node_types() -> set[str]:
        """Get language-specific node types that form chunks

        Returns:
            Set of tree-sitter node type strings

        Preconditions:
            - None

        Postconditions:
            - Returns non-empty set
            - Node types are valid for this language's grammar
        """

    @staticmethod
    @abstractmethod
    def should_chunk_node(node: Node) -> bool:
        """Determine if a specific node should be chunked

        Args:
            node: Tree-sitter node to evaluate

        Returns:
            True if node should form a chunk

        Preconditions:
            - node must be from this language's parse tree

        Postconditions:
            - Consistent results for same node type
        """

    @staticmethod
    @abstractmethod
    def get_node_context(node: Node, source: bytes) -> str | None:
        """Extract meaningful context for a node

        Args:
            node: Tree-sitter node
            source: Source code bytes

        Returns:
            Context string or None

        Preconditions:
            - node must be valid

        Postconditions:
            - Returns language-appropriate context
        """
