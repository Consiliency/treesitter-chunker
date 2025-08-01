"""Hierarchy building interfaces for chunk relationships."""
from abc import ABC, abstractmethod
from dataclasses import dataclass

from chunker.types import CodeChunk


@dataclass
class ChunkHierarchy:
    """Represents a hierarchical structure of chunks."""
    root_chunks: list[str]
    parent_map: dict[str, str]
    children_map: dict[str, list[str]]
    chunk_map: dict[str, CodeChunk]

    def get_depth(self, chunk_id: str) -> int:
        """Get the depth of a chunk in the hierarchy (root = 0)."""
        depth = 0
        current = chunk_id
        while current in self.parent_map:
            depth += 1
            current = self.parent_map[current]
        return depth


class ChunkHierarchyBuilder(ABC):
    """Build hierarchical structure from chunks."""

    @staticmethod
    @abstractmethod
    def build_hierarchy(chunks: list[CodeChunk]) -> ChunkHierarchy:
        """
        Build a hierarchical structure from flat chunks.

        Uses Tree-sitter AST information to determine parent-child relationships.

        Args:
            chunks: List of chunks to organize

        Returns:
            Hierarchical structure
        """

    @staticmethod
    @abstractmethod
    def find_common_ancestor(chunk1: CodeChunk, chunk2: CodeChunk,
        hierarchy: ChunkHierarchy) -> (str | None):
        """
        Find the common ancestor of two chunks.

        Args:
            chunk1: First chunk
            chunk2: Second chunk
            hierarchy: The chunk hierarchy

        Returns:
            ID of common ancestor or None
        """


class HierarchyNavigator(ABC):
    """Navigate chunk hierarchies."""

    @staticmethod
    @abstractmethod
    def get_children(chunk_id: str, hierarchy: ChunkHierarchy) -> list[CodeChunk
        ]:
        """
        Get direct children of a chunk.

        Args:
            chunk_id: ID of the parent chunk
            hierarchy: The chunk hierarchy

        Returns:
            List of child chunks
        """

    @staticmethod
    @abstractmethod
    def get_descendants(chunk_id: str, hierarchy: ChunkHierarchy) -> list[
        CodeChunk]:
        """
        Get all descendants of a chunk (children, grandchildren, etc.).

        Args:
            chunk_id: ID of the ancestor chunk
            hierarchy: The chunk hierarchy

        Returns:
            List of descendant chunks
        """

    @staticmethod
    @abstractmethod
    def get_ancestors(chunk_id: str, hierarchy: ChunkHierarchy) -> list[
        CodeChunk]:
        """
        Get all ancestors of a chunk (parent, grandparent, etc.).

        Args:
            chunk_id: ID of the chunk
            hierarchy: The chunk hierarchy

        Returns:
            List of ancestor chunks from immediate parent to root
        """

    @staticmethod
    @abstractmethod
    def get_siblings(chunk_id: str, hierarchy: ChunkHierarchy) -> list[CodeChunk
        ]:
        """
        Get sibling chunks (same parent).

        Args:
            chunk_id: ID of the chunk
            hierarchy: The chunk hierarchy

        Returns:
            List of sibling chunks
        """

    @staticmethod
    @abstractmethod
    def filter_by_depth(hierarchy: ChunkHierarchy, min_depth: int = 0,
        max_depth: (int | None) = None) -> list[CodeChunk]:
        """
        Filter chunks by their depth in the hierarchy.

        Args:
            hierarchy: The chunk hierarchy
            min_depth: Minimum depth (inclusive)
            max_depth: Maximum depth (inclusive), None for no limit

        Returns:
            List of chunks within the depth range
        """

    @staticmethod
    @abstractmethod
    def get_subtree(chunk_id: str, hierarchy: ChunkHierarchy) -> ChunkHierarchy:
        """
        Extract a subtree rooted at the given chunk.

        Args:
            chunk_id: ID of the root chunk for the subtree
            hierarchy: The full hierarchy

        Returns:
            A new ChunkHierarchy containing only the subtree
        """
