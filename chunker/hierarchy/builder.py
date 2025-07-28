"""Implementation of ChunkHierarchyBuilder for building chunk hierarchies from Tree-sitter AST."""

from collections import defaultdict

from ..interfaces.hierarchy import (
    ChunkHierarchy,
)
from ..interfaces.hierarchy import (
    ChunkHierarchyBuilder as ChunkHierarchyBuilderInterface,
)
from ..types import CodeChunk


class ChunkHierarchyBuilder(ChunkHierarchyBuilderInterface):
    """Builds hierarchical structure from chunks using Tree-sitter AST relationships."""

    def build_hierarchy(self, chunks: list[CodeChunk]) -> ChunkHierarchy:
        """
        Build a hierarchical structure from flat chunks.

        Uses Tree-sitter AST information to determine parent-child relationships
        based on the parent_chunk_id field in each chunk.

        Args:
            chunks: List of chunks to organize

        Returns:
            Hierarchical structure with parent-child mappings
        """
        # Initialize data structures
        root_chunks: list[str] = []
        parent_map: dict[str, str] = {}
        children_map: dict[str, list[str]] = defaultdict(list)
        chunk_map: dict[str, CodeChunk] = {}

        # First pass: build chunk_map
        for chunk in chunks:
            chunk_map[chunk.chunk_id] = chunk

        # Second pass: build parent-child relationships
        for chunk in chunks:
            if chunk.parent_chunk_id is None:
                # This is a root chunk
                root_chunks.append(chunk.chunk_id)
            else:
                # This chunk has a parent
                parent_map[chunk.chunk_id] = chunk.parent_chunk_id
                # Add to parent's children list
                if chunk.parent_chunk_id in chunk_map:
                    children_map[chunk.parent_chunk_id].append(chunk.chunk_id)
                else:
                    # Parent chunk not in our list, treat this as root
                    root_chunks.append(chunk.chunk_id)

        # Convert defaultdict to regular dict
        children_map = dict(children_map)

        # Sort root chunks by their start line for consistent ordering
        root_chunks.sort(key=lambda cid: chunk_map[cid].start_line)

        # Sort children lists by start line
        for parent_id in children_map:
            children_map[parent_id].sort(key=lambda cid: chunk_map[cid].start_line)

        return ChunkHierarchy(
            root_chunks=root_chunks,
            parent_map=parent_map,
            children_map=children_map,
            chunk_map=chunk_map,
        )

    def find_common_ancestor(
        self,
        chunk1: CodeChunk,
        chunk2: CodeChunk,
        hierarchy: ChunkHierarchy,
    ) -> str | None:
        """
        Find the common ancestor of two chunks.

        Uses the parent_map to traverse up the hierarchy from both chunks
        until a common ancestor is found.

        Args:
            chunk1: First chunk
            chunk2: Second chunk
            hierarchy: The chunk hierarchy

        Returns:
            ID of common ancestor or None if no common ancestor exists
        """
        # Get all ancestors of chunk1 (including itself)
        ancestors1: set[str] = {chunk1.chunk_id}
        current = chunk1.chunk_id

        while current in hierarchy.parent_map:
            current = hierarchy.parent_map[current]
            ancestors1.add(current)

        # Traverse ancestors of chunk2 until we find one in ancestors1
        current = chunk2.chunk_id
        if current in ancestors1:
            return current

        while current in hierarchy.parent_map:
            current = hierarchy.parent_map[current]
            if current in ancestors1:
                return current

        # No common ancestor found
        return None

    def get_path_to_root(self, chunk_id: str, hierarchy: ChunkHierarchy) -> list[str]:
        """
        Get the path from a chunk to the root.

        Helper method that returns a list of chunk IDs from the given chunk
        to the root of the hierarchy.

        Args:
            chunk_id: ID of the chunk
            hierarchy: The chunk hierarchy

        Returns:
            List of chunk IDs from the chunk to root (inclusive)
        """
        path: list[str] = [chunk_id]
        current = chunk_id

        while current in hierarchy.parent_map:
            current = hierarchy.parent_map[current]
            path.append(current)

        return path

    def validate_hierarchy(self, hierarchy: ChunkHierarchy) -> bool:
        """
        Validate the integrity of a hierarchy.

        Checks for:
        - Cycles in parent-child relationships
        - Orphaned chunks
        - Consistency between parent_map and children_map

        Args:
            hierarchy: The hierarchy to validate

        Returns:
            True if valid, raises ValueError if invalid
        """
        # Check for cycles
        visited: set[str] = set()

        def has_cycle(chunk_id: str, path: set[str]) -> bool:
            if chunk_id in path:
                return True
            if chunk_id in visited:
                return False

            path.add(chunk_id)
            visited.add(chunk_id)

            if chunk_id in hierarchy.parent_map:
                if has_cycle(hierarchy.parent_map[chunk_id], path):
                    return True

            path.remove(chunk_id)
            return False

        for chunk_id in hierarchy.chunk_map:
            if has_cycle(chunk_id, set()):
                raise ValueError(f"Cycle detected involving chunk {chunk_id}")

        # Check parent_map and children_map consistency
        for child_id, parent_id in hierarchy.parent_map.items():
            if parent_id not in hierarchy.children_map:
                raise ValueError(f"Parent {parent_id} has no children_map entry")
            if child_id not in hierarchy.children_map[parent_id]:
                raise ValueError(
                    f"Child {child_id} not in parent {parent_id}'s children list",
                )

        # Check that all chunks in children_map have correct parent_map entries
        for parent_id, children in hierarchy.children_map.items():
            for child_id in children:
                if child_id not in hierarchy.parent_map:
                    raise ValueError(f"Child {child_id} has no parent_map entry")
                if hierarchy.parent_map[child_id] != parent_id:
                    raise ValueError(f"Inconsistent parent for {child_id}")

        return True
