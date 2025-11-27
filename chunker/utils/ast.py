"""AST traversal safety utilities.

This module provides safe accessors for tree-sitter AST node children,
preventing IndexError exceptions from malformed or unexpected AST shapes.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node

logger = logging.getLogger(__name__)


def safe_get_child(
    node: Node | None,
    index: int,
    default: Node | None = None,
) -> Node | None:
    """Safely get a child node by index.

    Handles both positive and negative indices safely, returning a default
    value instead of raising IndexError for out-of-bounds access.

    Args:
        node: Parent node, or None.
        index: Child index (supports negative indexing like Python lists).
        default: Value to return if index is out of bounds or node is None.

    Returns:
        Child node at the specified index, or the default value.

    Example:
        >>> first = safe_get_child(node, 0)
        >>> last = safe_get_child(node, -1)
        >>> third = safe_get_child(node, 2, default=None)
    """
    if node is None:
        return default

    children = getattr(node, "children", None)
    if not children:
        return default

    try:
        return children[index]
    except (IndexError, TypeError):
        return default


def safe_children_access(
    node: Node | None,
    min_count: int = 0,
) -> list:
    """Safely access a node's children list with optional minimum count check.

    Args:
        node: The AST node to access children from, or None.
        min_count: Minimum number of children required. If the node has fewer
            children than this, an empty list is returned and a debug message
            is logged.

    Returns:
        The node's children list, or an empty list if the node is None,
        has no children attribute, or has fewer than min_count children.

    Example:
        >>> children = safe_children_access(node, min_count=2)
        >>> if children:
        ...     first, second = children[0], children[1]
    """
    if node is None:
        return []

    children = getattr(node, "children", None)
    if children is None:
        return []

    if min_count > 0 and len(children) < min_count:
        logger.debug(
            "Unexpected AST shape for %s: expected at least %d children, got %d",
            getattr(node, "type", "unknown"),
            min_count,
            len(children),
        )
        return []

    return list(children)


def has_children(node: Node | None, min_count: int = 1) -> bool:
    """Check if a node has at least the specified number of children.

    Args:
        node: The AST node to check, or None.
        min_count: Minimum number of children required (default 1).

    Returns:
        True if the node has at least min_count children, False otherwise.
    """
    if node is None:
        return False
    children = getattr(node, "children", None)
    if children is None:
        return False
    return len(children) >= min_count


def find_child_by_type(node: Node | None, *types: str) -> Node | None:
    """Find the first child of a node matching any of the given types.

    Args:
        node: The parent node to search, or None.
        *types: One or more node type strings to match.

    Returns:
        The first matching child node, or None if not found.

    Example:
        >>> name_node = find_child_by_type(func_node, "identifier", "name")
    """
    if node is None:
        return None

    children = getattr(node, "children", None)
    if not children:
        return None

    type_set = set(types)
    for child in children:
        if getattr(child, "type", None) in type_set:
            return child
    return None
