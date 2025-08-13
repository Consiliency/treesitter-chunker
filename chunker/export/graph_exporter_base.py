"""Base class for graph export functionality."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from chunker.types import CodeChunk


class GraphNode:
    """Represents a node in the graph."""

    def __init__(self, chunk: CodeChunk):
        self.id = f"{chunk.file_path}:{chunk.start_line}:{chunk.end_line}"
        self.chunk = chunk
        chunk_type = (
            chunk.metadata.get(
                "chunk_type",
                chunk.node_type,
            )
            if chunk.metadata
            else chunk.node_type
        )
        self.label = chunk_type or "unknown"
        self.properties: dict[str, Any] = {
            "file_path": chunk.file_path,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "chunk_type": chunk_type,
            "node_type": chunk.node_type,
            "language": chunk.language,
        }
        if chunk.metadata:
            self.properties.update(chunk.metadata)


class GraphEdge:
    """Represents an edge between nodes in the graph."""

    def __init__(
        self,
        source_id: str,
        target_id: str,
        relationship_type: str,
        properties: dict[str, Any] | None = None,
    ):
        self.source_id = source_id
        self.target_id = target_id
        self.relationship_type = relationship_type
        self.properties = properties or {}


class GraphExporterBase(ABC):
    """Base class for exporting code chunks as graph data."""

    def __init__(self):
        self.nodes: dict[str, GraphNode] = {}
        self.edges: list[GraphEdge] = []

    def add_chunks(self, chunks: list[CodeChunk]) -> None:
        """Add chunks as nodes to the graph."""
        for chunk in chunks:
            node = GraphNode(chunk)
            self.nodes[node.id] = node

    def add_relationship(
        self,
        source_chunk: CodeChunk,
        target_chunk: CodeChunk,
        relationship_type: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        """Add a relationship between two chunks."""
        source_node = GraphNode(source_chunk)
        target_node = GraphNode(target_chunk)
        edge = GraphEdge(source_node.id, target_node.id, relationship_type, properties)
        self.edges.append(edge)

    def extract_relationships(self, chunks: list[CodeChunk]) -> None:
        """Extract relationships between chunks based on their metadata and structure.

        This base implementation extracts:
        - Parent-child relationships from hierarchy metadata and parent_chunk_id
        - Import/dependency relationships
        - Call relationships
        - DEFINES edges from parent to child
        - HAS_METHOD edges from class to method (language-aware)

        Subclasses can override to add more relationship types.
        """
        chunk_map = {self._get_chunk_id(chunk): chunk for chunk in chunks}
        chunk_id_map = {chunk.chunk_id: chunk for chunk in chunks if chunk.chunk_id}

        for chunk in chunks:
            # Handle legacy parent_id in metadata
            if chunk.metadata and "parent_id" in chunk.metadata:
                parent_id = chunk.metadata["parent_id"]
                if parent_id in chunk_map:
                    self.add_relationship(
                        chunk_map[parent_id],
                        chunk,
                        "CONTAINS",
                        {"relationship_source": "hierarchy"},
                    )

            # Handle parent_chunk_id for DEFINES relationship
            if chunk.parent_chunk_id and chunk.parent_chunk_id in chunk_id_map:
                parent_chunk = chunk_id_map[chunk.parent_chunk_id]
                self.add_relationship(
                    parent_chunk,
                    chunk,
                    "DEFINES",
                    {"relationship_source": "parent_chunk_id"},
                )

                # Add language-aware HAS_METHOD edge if parent is class and child is method
                if self._is_class_method_relationship(parent_chunk, chunk):
                    self.add_relationship(
                        parent_chunk,
                        chunk,
                        "HAS_METHOD",
                        {"relationship_source": "class_method_detection"},
                    )

            if chunk.metadata and "imports" in chunk.metadata:
                for import_info in chunk.metadata["imports"]:
                    for target_chunk in chunks:
                        if self._matches_import(import_info, target_chunk):
                            self.add_relationship(
                                chunk,
                                target_chunk,
                                "IMPORTS",
                                {"import_name": import_info},
                            )
            if chunk.metadata and "calls" in chunk.metadata:
                for call_info in chunk.metadata["calls"]:
                    for target_chunk in chunks:
                        if self._matches_call(call_info, target_chunk):
                            self.add_relationship(
                                chunk,
                                target_chunk,
                                "CALLS",
                                {"call_name": call_info},
                            )

    @staticmethod
    def _get_chunk_id(chunk: CodeChunk) -> str:
        """Generate a unique ID for a chunk."""
        return f"{chunk.file_path}:{chunk.start_line}:{chunk.end_line}"

    @staticmethod
    def _matches_import(import_name: str, chunk: CodeChunk) -> bool:
        """Check if an import name matches a chunk."""
        if chunk.metadata and "name" in chunk.metadata:
            return chunk.metadata["name"] == import_name
        return False

    @staticmethod
    def _matches_call(call_name: str, chunk: CodeChunk) -> bool:
        """Check if a call name matches a chunk."""
        if chunk.metadata and "name" in chunk.metadata:
            return chunk.metadata["name"] == call_name
        return False

    @staticmethod
    def _is_class_method_relationship(
        parent_chunk: CodeChunk, child_chunk: CodeChunk
    ) -> bool:
        """Check if parent is a class and child is a method (language-aware)."""
        # Define class types for different languages
        class_types = {
            "class_declaration",  # JavaScript, Python, Java, C#, etc.
            "class_definition",  # Python alternative
            "interface_declaration",  # TypeScript, Java, C#
            "struct_item",  # Rust
            "impl_item",  # Rust
            "type_declaration",  # Go
        }

        # Define method types for different languages
        method_types = {
            "method_definition",  # JavaScript, Python, Java, C#
            "function_definition",  # Python alternative
            "function_item",  # Rust
            "method_declaration",  # Java, C#
            "function_declaration",  # When inside a class context
            "arrow_function",  # JavaScript class properties
            "function_expression",  # JavaScript class properties
        }

        parent_type = parent_chunk.node_type
        child_type = child_chunk.node_type

        # Check if parent is a class-like structure and child is a method-like structure
        return parent_type in class_types and child_type in method_types

    def get_subgraph_clusters(self) -> dict[str, list[str]]:
        """Group nodes into clusters (e.g., by file or module).

        Returns a dict mapping cluster names to lists of node IDs.
        """
        clusters: dict[str, list[str]] = {}
        for node_id, node in self.nodes.items():
            file_path = str(node.chunk.file_path)
            if file_path not in clusters:
                clusters[file_path] = []
            clusters[file_path].append(node_id)
        return clusters

    @classmethod
    @abstractmethod
    def export(cls, output_path: Path, **options) -> None:
        """Export the graph to the specified format.

        Args:
            output_path: Path to write the output file
            **options: Format-specific options
        """
        raise NotImplementedError("Subclasses must implement export()")

    @classmethod
    @abstractmethod
    def export_string(cls, **options) -> str:
        """Export the graph as a string in the specified format.

        Args:
            **options: Format-specific options

        Returns:
            The graph representation as a string
        """
        raise NotImplementedError("Subclasses must implement export_string()")
