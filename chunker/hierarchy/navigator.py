"""Implementation of HierarchyNavigator for navigating chunk hierarchies."""

from collections import deque

from chunker.interfaces.hierarchy import (
    ChunkHierarchy,
)
from chunker.interfaces.hierarchy import (
    HierarchyNavigator as HierarchyNavigatorInterface,
)
from chunker.types import CodeChunk


class HierarchyNavigator(HierarchyNavigatorInterface):
    """Navigate chunk hierarchies with various traversal methods."""

    def get_children(self, chunk_id: str, hierarchy: ChunkHierarchy) -> list[CodeChunk]:
        """
        Get direct children of a chunk.

        Args:
            chunk_id: ID of the parent chunk
            hierarchy: The chunk hierarchy

        Returns:
            List of child chunks, empty list if no children
        """
        if chunk_id not in hierarchy.children_map:
            return []

        child_ids = hierarchy.children_map[chunk_id]
        return [hierarchy.chunk_map[child_id] for child_id in child_ids]

    def get_descendants(
        self,
        chunk_id: str,
        hierarchy: ChunkHierarchy,
    ) -> list[CodeChunk]:
        """
        Get all descendants of a chunk (children, grandchildren, etc.).

        Uses breadth-first traversal to collect all descendants.

        Args:
            chunk_id: ID of the ancestor chunk
            hierarchy: The chunk hierarchy

        Returns:
            List of descendant chunks in breadth-first order
        """
        descendants: list[CodeChunk] = []
        queue = deque([chunk_id])
        visited: set[str] = {chunk_id}

        while queue:
            current_id = queue.popleft()

            # Get children of current chunk
            if current_id in hierarchy.children_map:
                for child_id in hierarchy.children_map[current_id]:
                    if child_id not in visited:
                        visited.add(child_id)
                        descendants.append(hierarchy.chunk_map[child_id])
                        queue.append(child_id)

        return descendants

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
        ancestors: list[CodeChunk] = []
        current_id = chunk_id

        while current_id in hierarchy.parent_map:
            parent_id = hierarchy.parent_map[current_id]
            if parent_id in hierarchy.chunk_map:
                ancestors.append(hierarchy.chunk_map[parent_id])
            current_id = parent_id

        return ancestors

    def get_siblings(self, chunk_id: str, hierarchy: ChunkHierarchy) -> list[CodeChunk]:
        """
        Get sibling chunks (same parent).

        Args:
            chunk_id: ID of the chunk
            hierarchy: The chunk hierarchy

        Returns:
            List of sibling chunks (excluding the chunk itself)
        """
        # If no parent, check root chunks
        if chunk_id not in hierarchy.parent_map:
            siblings = [
                hierarchy.chunk_map[root_id]
                for root_id in hierarchy.root_chunks
                if root_id != chunk_id and root_id in hierarchy.chunk_map
            ]
            return siblings

        # Get parent and its children
        parent_id = hierarchy.parent_map[chunk_id]
        if parent_id not in hierarchy.children_map:
            return []

        sibling_ids = hierarchy.children_map[parent_id]
        siblings = [
            hierarchy.chunk_map[sibling_id]
            for sibling_id in sibling_ids
            if sibling_id != chunk_id and sibling_id in hierarchy.chunk_map
        ]

        return siblings

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
        filtered_chunks: list[CodeChunk] = []

        for chunk_id, chunk in hierarchy.chunk_map.items():
            depth = hierarchy.get_depth(chunk_id)

            if depth >= min_depth:
                if max_depth is None or depth <= max_depth:
                    filtered_chunks.append(chunk)

        # Sort by file path and start line for consistent ordering
        filtered_chunks.sort(key=lambda c: (c.file_path, c.start_line))

        return filtered_chunks

    def get_subtree(self, chunk_id: str, hierarchy: ChunkHierarchy) -> ChunkHierarchy:
        """
        Extract a subtree rooted at the given chunk.

        Creates a new ChunkHierarchy containing only the specified chunk
        and all its descendants.

        Args:
            chunk_id: ID of the root chunk for the subtree
            hierarchy: The full hierarchy

        Returns:
            A new ChunkHierarchy containing only the subtree
        """
        if chunk_id not in hierarchy.chunk_map:
            # Return empty hierarchy if chunk not found
            return ChunkHierarchy(
                root_chunks=[],
                parent_map={},
                children_map={},
                chunk_map={},
            )

        # Collect all chunks in subtree
        subtree_chunks: set[str] = {chunk_id}
        queue = deque([chunk_id])

        while queue:
            current_id = queue.popleft()

            if current_id in hierarchy.children_map:
                for child_id in hierarchy.children_map[current_id]:
                    if child_id not in subtree_chunks:
                        subtree_chunks.add(child_id)
                        queue.append(child_id)

        # Build new hierarchy with only subtree chunks
        new_chunk_map = {cid: hierarchy.chunk_map[cid] for cid in subtree_chunks}
        new_parent_map = {}
        new_children_map = {}

        for cid in subtree_chunks:
            # Add parent mapping if parent is in subtree
            if cid in hierarchy.parent_map:
                parent_id = hierarchy.parent_map[cid]
                if parent_id in subtree_chunks:
                    new_parent_map[cid] = parent_id

            # Add children mappings
            if cid in hierarchy.children_map:
                children_in_subtree = [
                    child_id
                    for child_id in hierarchy.children_map[cid]
                    if child_id in subtree_chunks
                ]
                if children_in_subtree:
                    new_children_map[cid] = children_in_subtree

        return ChunkHierarchy(
            root_chunks=[chunk_id],  # The specified chunk is the root of the subtree
            parent_map=new_parent_map,
            children_map=new_children_map,
            chunk_map=new_chunk_map,
        )

    def get_level_order_traversal(
        self,
        hierarchy: ChunkHierarchy,
    ) -> list[list[CodeChunk]]:
        """
        Get chunks organized by level (depth) in the hierarchy.

        Returns a list where each element is a list of chunks at that depth level.

        Args:
            hierarchy: The chunk hierarchy

        Returns:
            List of lists, where index represents depth level
        """
        levels: list[list[CodeChunk]] = []

        # Start with root chunks
        if not hierarchy.root_chunks:
            return levels

        current_level = [
            hierarchy.chunk_map[root_id]
            for root_id in hierarchy.root_chunks
            if root_id in hierarchy.chunk_map
        ]

        while current_level:
            levels.append(current_level)

            # Get next level
            next_level: list[CodeChunk] = []
            for chunk in current_level:
                children = self.get_children(chunk.chunk_id, hierarchy)
                next_level.extend(children)

            current_level = next_level

        return levels

    def find_chunks_by_type(
        self,
        node_type: str,
        hierarchy: ChunkHierarchy,
        subtree_root: str | None = None,
    ) -> list[CodeChunk]:
        """
        Find all chunks of a specific node type within the hierarchy.

        Args:
            node_type: The tree-sitter node type to search for
            hierarchy: The chunk hierarchy
            subtree_root: Optional chunk ID to limit search to a subtree

        Returns:
            List of chunks matching the node type
        """
        if subtree_root:
            # Search within subtree
            subtree = self.get_subtree(subtree_root, hierarchy)
            search_map = subtree.chunk_map
        else:
            # Search entire hierarchy
            search_map = hierarchy.chunk_map

        matching_chunks = [
            chunk for chunk in search_map.values() if chunk.node_type == node_type
        ]

        # Sort by file path and start line
        matching_chunks.sort(key=lambda c: (c.file_path, c.start_line))

        return matching_chunks
