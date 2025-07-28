"""Hierarchy building interfaces for chunk relationships."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from chunker.types import CodeChunk


@dataclass
class ChunkHierarchy:
    """Represents a hierarchical structure of chunks."""

    root_chunks: list[str]  # IDs of top-level chunks
    parent_map: dict[str, str]  # child_id -> parent_id
    children_map: dict[str, list[str]]  # parent_id -> [child_ids]
    chunk_map: dict[str, CodeChunk]  # id -> chunk

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

    @abstractmethod
    def build_hierarchy(self, chunks: list[CodeChunk]) -> ChunkHierarchy:
        """
        Build a hierarchical structure from flat chunks.

        Uses Tree-sitter AST information to determine parent-child relationships.

        Args:
            chunks: List of chunks to organize

        Returns:
            Hierarchical structure
        """

    @abstractmethod
    def find_common_ancestor(
        self,
        chunk1: CodeChunk,
        chunk2: CodeChunk,
        hierarchy: ChunkHierarchy,
    ) -> str | None:
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

    @abstractmethod
    def get_children(self, chunk_id: str, hierarchy: ChunkHierarchy) -> list[CodeChunk]:
        """
        Get direct children of a chunk.

        Args:
            chunk_id: ID of the parent chunk
            hierarchy: The chunk hierarchy

        Returns:
            List of child chunks
        """

    @abstractmethod
    def get_descendants(
        self,
        chunk_id: str,
        hierarchy: ChunkHierarchy,
    ) -> list[CodeChunk]:
        """
        Get all descendants of a chunk (children, grandchildren, etc.).

        Args:
            chunk_id: ID of the ancestor chunk
            hierarchy: The chunk hierarchy

        Returns:
            List of descendant chunks
        """

    @abstractmethod
    def get_ancestors(
        self,
        chunk_id: str,
        hierarchy: ChunkHierarchy,
    ) -> list[CodeChunk]:
        """
        Get all ancestors of a chunk (parent, grandparent, etc.).

        Args:
            chunk_id: ID of the chunk
            hierarchy: The chunk hierarchy

        Returns:
            List of ancestor chunks from immediate parent to root
        """

    @abstractmethod
    def get_siblings(self, chunk_id: str, hierarchy: ChunkHierarchy) -> list[CodeChunk]:
        """
        Get sibling chunks (same parent).

        Args:
            chunk_id: ID of the chunk
            hierarchy: The chunk hierarchy

        Returns:
            List of sibling chunks
        """

    @abstractmethod
    def filter_by_depth(
        self,
        hierarchy: ChunkHierarchy,
        min_depth: int = 0,
        max_depth: int | None = None,
    ) -> list[CodeChunk]:
        """
        Filter chunks by their depth in the hierarchy.

        Args:
            hierarchy: The chunk hierarchy
            min_depth: Minimum depth (inclusive)
            max_depth: Maximum depth (inclusive), None for no limit

        Returns:
            List of chunks within the depth range
        """

    @abstractmethod
    def get_subtree(self, chunk_id: str, hierarchy: ChunkHierarchy) -> ChunkHierarchy:
        """
        Extract a subtree rooted at the given chunk.

        Args:
            chunk_id: ID of the root chunk for the subtree
            hierarchy: The full hierarchy

        Returns:
            A new ChunkHierarchy containing only the subtree
        """
