"""Base implementation of context filtering.

Provides functionality to filter context items for relevance to chunks.
"""

from tree_sitter import Node

from chunker.interfaces.context import ContextFilter, ContextItem, ContextType


class BaseContextFilter(ContextFilter):
    """Base implementation of context filtering with common functionality."""

    def __init__(self, language: str):
        """Initialize the context filter.

        Args:
            language: Language identifier
        """
        self.language = language
        self._relevance_cache: dict[str, float] = {}

    def is_relevant(self, context_item: ContextItem, chunk_node: Node) -> bool:
        """Determine if a context item is relevant to a chunk.

        Args:
            context_item: Context item to evaluate
            chunk_node: Node representing the chunk

        Returns:
            True if context is relevant
        """
        if context_item.type == ContextType.IMPORT:
            return True
        if context_item.type == ContextType.PARENT_SCOPE:
            return self._is_ancestor(context_item.node, chunk_node)
        if context_item.type == ContextType.DECORATOR:
            return self._is_decorator_for_node(context_item.node, chunk_node)
        score = self.score_relevance(context_item, chunk_node)
        return score > 0.5

    def score_relevance(
        self,
        context_item: ContextItem,
        chunk_node: Node,
    ) -> float:
        """Score the relevance of a context item (0.0-1.0).

        Args:
            context_item: Context item to score
            chunk_node: Node representing the chunk

        Returns:
            Relevance score between 0.0 and 1.0
        """
        cache_key = f"{id(context_item)}:{id(chunk_node)}"
        if cache_key in self._relevance_cache:
            return self._relevance_cache[cache_key]
        score = 0.0
        type_scores = {
            ContextType.IMPORT: 0.9,
            ContextType.TYPE_DEF: 0.8,
            ContextType.DECORATOR: 0.7,
            ContextType.PARENT_SCOPE: 0.9,
            ContextType.DEPENDENCY: 0.6,
            ContextType.NAMESPACE: 0.5,
            ContextType.CONSTANT: 0.4,
            ContextType.GLOBAL_VAR: 0.4,
        }
        base_score = type_scores.get(context_item.type, 0.3)
        score = base_score
        distance = self._calculate_ast_distance(context_item.node, chunk_node)
        if distance >= 0:
            distance_penalty = min(distance * 0.1, 0.5)
            score -= distance_penalty
        line_distance = abs(context_item.line_number - self._get_node_line(chunk_node))
        if line_distance < 10:
            score += 0.1
        elif line_distance < 50:
            score += 0.05
        elif line_distance > 200:
            score -= 0.1
        if self._chunk_references_context(chunk_node, context_item):
            score += 0.3
        score = max(0.0, min(1.0, score))
        self._relevance_cache[cache_key] = score
        return score

    @staticmethod
    def _is_ancestor(potential_ancestor: Node, node: Node) -> bool:
        """Check if one node is an ancestor of another.

        Args:
            potential_ancestor: Node that might be an ancestor
            node: Node to check

        Returns:
            True if potential_ancestor is an ancestor of node
        """
        current = node.parent
        while current:
            if current == potential_ancestor:
                return True
            current = current.parent
        return False

    def _is_decorator_for_node(
        self,
        decorator_node: Node,
        target_node: Node,
    ) -> bool:
        """Check if a decorator applies to a specific node.

        Args:
            decorator_node: Decorator node
            target_node: Node that might be decorated

        Returns:
            True if decorator applies to target
        """
        if not decorator_node.parent:
            return False
        siblings = decorator_node.parent.children
        decorator_index = -1
        target_index = -1
        for i, sibling in enumerate(siblings):
            if sibling == decorator_node:
                decorator_index = i
            elif sibling == target_node:
                target_index = i
        if (
            decorator_index >= 0
            and target_index >= 0
            and decorator_index < target_index
        ):
            for i in range(decorator_index + 1, target_index):
                if not self._is_decorator_node(siblings[i]):
                    return False
            return True
        return False

    def _calculate_ast_distance(self, node1: Node, node2: Node) -> int:
        """Calculate the distance between two nodes in the AST.

        Args:
            node1: First node
            node2: Second node

        Returns:
            Distance in tree hops, or -1 if nodes are unrelated
        """
        ancestors1 = self._get_ancestors(node1)
        ancestors2 = self._get_ancestors(node2)
        common_ancestor = None
        for ancestor in ancestors1:
            if ancestor in ancestors2:
                common_ancestor = ancestor
                break
        if not common_ancestor:
            return -1
        distance1 = ancestors1.index(common_ancestor)
        distance2 = ancestors2.index(common_ancestor)
        return distance1 + distance2

    @staticmethod
    def _get_ancestors(node: Node) -> list[Node]:
        """Get all ancestors of a node.

        Args:
            node: Starting node

        Returns:
            List of ancestors from node to root
        """
        ancestors = [node]
        current = node.parent
        while current:
            ancestors.append(current)
            current = current.parent
        return ancestors

    @staticmethod
    def _get_node_line(_node: Node) -> int:
        """Get the line number of a node.

        Args:
            node: Node to get line for

        Returns:
            Line number (1-based)
        """
        return 0

    @staticmethod
    def _chunk_references_context(
        _chunk_node: Node,
        _context_item: ContextItem,
    ) -> bool:
        """Check if a chunk references symbols from a context item.

        Args:
            chunk_node: Chunk node
            context_item: Context item

        Returns:
            True if chunk references the context
        """
        return False

    @staticmethod
    def _is_decorator_node(_node: Node) -> bool:
        """Check if a node is a decorator.

        Args:
            node: Node to check

        Returns:
            True if node is a decorator
        """
        return False
