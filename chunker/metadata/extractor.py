"""Base metadata extraction implementation."""

from abc import ABC

from tree_sitter import Node

from ..interfaces.metadata import MetadataExtractor


class BaseMetadataExtractor(MetadataExtractor, ABC):
    """Base implementation with common metadata extraction logic."""

    def __init__(self, language: str):
        """
        Initialize the metadata extractor.

        Args:
            language: Programming language name
        """
        self.language = language

    def _get_node_text(self, node: Node, source: bytes) -> str:
        """
        Extract text content from a node.

        Args:
            node: Tree-sitter node
            source: Source code bytes

        Returns:
            Text content of the node
        """
        return source[node.start_byte : node.end_byte].decode("utf-8", errors="replace")

    def _find_child_by_type(self, node: Node, node_type: str) -> Node | None:
        """
        Find first child node of specific type.

        Args:
            node: Parent node
            node_type: Type to search for

        Returns:
            Child node or None
        """
        for child in node.children:
            if child.type == node_type:
                return child
        return None

    def _find_all_children_by_type(self, node: Node, node_type: str) -> list[Node]:
        """
        Find all child nodes of specific type.

        Args:
            node: Parent node
            node_type: Type to search for

        Returns:
            List of matching child nodes
        """
        return [child for child in node.children if child.type == node_type]

    def _walk_tree(self, node: Node, callback, depth: int = 0):
        """
        Walk the AST tree and apply callback.

        Args:
            node: Starting node
            callback: Function to call for each node
            depth: Current depth in tree
        """
        callback(node, depth)
        for child in node.children:
            self._walk_tree(child, callback, depth + 1)

    def _extract_identifiers(self, node: Node, source: bytes) -> set[str]:
        """
        Extract all identifiers from a node.

        Args:
            node: AST node
            source: Source code bytes

        Returns:
            Set of identifier names
        """
        identifiers = set()

        def collect_identifiers(n: Node, depth: int):
            if n.type == "identifier":
                identifiers.add(self._get_node_text(n, source))

        self._walk_tree(node, collect_identifiers)
        return identifiers

    def _is_comment_node(self, node: Node) -> bool:
        """
        Check if node is a comment.

        Args:
            node: Node to check

        Returns:
            True if node is a comment
        """
        return node.type in ("comment", "line_comment", "block_comment")

    def _extract_leading_comment(self, node: Node, source: bytes) -> str | None:
        """
        Extract comment immediately before a node.

        Args:
            node: AST node
            source: Source code bytes

        Returns:
            Comment text or None
        """
        if not node.parent:
            return None

        # Find this node's position among siblings
        siblings = node.parent.children
        node_index = None
        for i, sibling in enumerate(siblings):
            if sibling == node:
                node_index = i
                break

        if node_index is None or node_index == 0:
            return None

        # Check previous sibling
        prev_sibling = siblings[node_index - 1]
        if self._is_comment_node(prev_sibling):
            return self._get_node_text(prev_sibling, source)

        return None
