"""AST node type normalizers for language-specific handling.

This module provides a plugin architecture for normalizing AST node types
across different programming languages. Each language can have custom
logic for adjusting node types and spans during tree walking.

Classes:
    NodeNormalizer: Base class for language-specific node normalization.
    DartNormalizer: Normalizer for Dart language AST nodes.
    RNormalizer: Normalizer for R language AST nodes.
    DefaultNormalizer: Default pass-through normalizer.

Functions:
    get_normalizer: Get the appropriate normalizer for a language.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Node


class NodeNormalizer(ABC):
    """Base class for language-specific node normalization.

    Subclass this to implement custom normalization logic for a language.
    """

    @abstractmethod
    def normalize_type(
        self,
        node: Node,
        source: bytes,
    ) -> tuple[str, int, int]:
        """Normalize node type and adjust span if needed.

        Args:
            node: AST node to normalize.
            source: Source code bytes.

        Returns:
            tuple of (normalized_type, span_start, span_end)
        """

    @abstractmethod
    def should_force_chunk(self, node: Node, source: bytes) -> bool:
        """Check if node should be forced into a chunk.

        Args:
            node: AST node to check.
            source: Source code bytes.

        Returns:
            True if node should become a chunk regardless of type.
        """


class DartNormalizer(NodeNormalizer):
    """Normalizer for Dart language AST nodes.

    Handles Dart-specific node type mapping, particularly for
    converting signature nodes to their declaration counterparts.
    """

    SIGNATURE_TO_DECLARATION = {
        "function_signature": "function_declaration",
        "method_signature": "method_declaration",
        "getter_signature": "getter_declaration",
        "setter_signature": "setter_declaration",
        "constructor_signature": "constructor_declaration",
        "factory_constructor_signature": "factory_constructor",
    }

    def normalize_type(
        self,
        node: Node,
        source: bytes,
    ) -> tuple[str, int, int]:
        """Normalize Dart node types.

        Converts signature nodes to declaration nodes and adjusts
        span to include the function body when present.
        """
        span_start = node.start_byte
        span_end = node.end_byte
        node_type = node.type

        if node_type in self.SIGNATURE_TO_DECLARATION:
            node_type = self.SIGNATURE_TO_DECLARATION[node_type]
            span_end = self._find_body_end(node) or span_end
        elif node_type == "class_definition":
            node_type = "class_declaration"
        elif node_type == "type_alias":
            node_type = "type_declaration"

        return node_type, span_start, span_end

    def _find_body_end(self, node: Node) -> int | None:
        """Find function_body sibling and return its end byte.

        Args:
            node: The signature node to find the body for.

        Returns:
            End byte of the function body, or None if not found.
        """
        parent = getattr(node, "parent", None)
        if parent is None:
            return None

        try:
            children = list(parent.children)
            idx = children.index(node)
            for sib in children[idx + 1 :]:
                if sib.type == "function_body":
                    return sib.end_byte
        except (ValueError, IndexError):
            pass
        return None

    def should_force_chunk(self, node: Node, source: bytes) -> bool:
        """Dart doesn't have any forced chunk patterns."""
        return False


class RNormalizer(NodeNormalizer):
    """Normalizer for R language AST nodes.

    Handles R-specific patterns like S4 class definitions
    (setClass, setMethod, setGeneric calls).
    """

    FORCE_CHUNK_CALLS = frozenset({"setClass", "setMethod", "setGeneric"})

    def normalize_type(
        self,
        node: Node,
        source: bytes,
    ) -> tuple[str, int, int]:
        """R nodes pass through without type changes."""
        return node.type, node.start_byte, node.end_byte

    def should_force_chunk(self, node: Node, source: bytes) -> bool:
        """Check if this is an S4 class/method definition call.

        Args:
            node: AST node to check.
            source: Source code bytes.

        Returns:
            True if this is a setClass, setMethod, or setGeneric call.
        """
        if node.type != "call":
            return False

        children = getattr(node, "children", [])
        if not children:
            return False

        callee = children[0]
        if getattr(callee, "type", None) != "identifier":
            return False

        try:
            ident = source[callee.start_byte : callee.end_byte].decode(
                "utf-8",
                errors="ignore",
            )
            return ident in self.FORCE_CHUNK_CALLS
        except (AttributeError, IndexError):
            return False


class DefaultNormalizer(NodeNormalizer):
    """Default normalizer that passes through unchanged.

    Used for languages without specific normalization requirements.
    """

    def normalize_type(
        self,
        node: Node,
        source: bytes,
    ) -> tuple[str, int, int]:
        """Pass through node type and span unchanged."""
        return node.type, node.start_byte, node.end_byte

    def should_force_chunk(self, node: Node, source: bytes) -> bool:
        """Default implementation never forces chunking."""
        return False


# Registry of normalizers by language
NORMALIZERS: dict[str, type[NodeNormalizer]] = {
    "dart": DartNormalizer,
    "r": RNormalizer,
}


def get_normalizer(language: str) -> NodeNormalizer:
    """Get normalizer for language.

    Args:
        language: Programming language name.

    Returns:
        NodeNormalizer instance for the language.
        Returns DefaultNormalizer if no specific normalizer exists.
    """
    normalizer_class = NORMALIZERS.get(language.lower())
    if normalizer_class:
        return normalizer_class()
    return DefaultNormalizer()


__all__ = [
    "NORMALIZERS",
    "DartNormalizer",
    "DefaultNormalizer",
    "NodeNormalizer",
    "RNormalizer",
    "get_normalizer",
]
