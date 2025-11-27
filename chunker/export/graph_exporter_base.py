"""Base class for graph export functionality."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from chunker.types import CodeChunk


@dataclass
class UnifiedGraphNode:
    """Unified graph node representation for xref, exporters, and APIs.

    This dataclass provides a consistent node schema across:
    - XRef builder (chunker/graph/xref.py)
    - GraphCut (chunker/graph/cut.py)
    - Graph exporters
    - HTTP API (api/server.py)

    Attributes:
        id: Unique node identifier (typically node_id or chunk_id).
        file: Source file path.
        lang: Programming language.
        symbol: Symbol identifier (e.g., function/class name), may be None.
        kind: Node type (e.g., 'function_definition', 'class_definition').
        attrs: Additional metadata attributes.
    """

    id: str
    file: str
    lang: str
    symbol: str | None
    kind: str
    attrs: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format for API/export."""
        return {
            "id": self.id,
            "file": self.file,
            "lang": self.lang,
            "symbol": self.symbol,
            "kind": self.kind,
            "attrs": self.attrs,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnifiedGraphNode":
        """Create from dictionary format."""
        return cls(
            id=data.get("id", ""),
            file=data.get("file", ""),
            lang=data.get("lang", ""),
            symbol=data.get("symbol"),
            kind=data.get("kind", ""),
            attrs=data.get("attrs", {}),
        )

    @classmethod
    def from_chunk(cls, chunk: CodeChunk) -> "UnifiedGraphNode":
        """Create from a CodeChunk."""
        return cls(
            id=chunk.node_id or chunk.chunk_id or "",
            file=str(chunk.file_path),
            lang=chunk.language,
            symbol=chunk.symbol_id,
            kind=chunk.node_type,
            attrs=chunk.metadata or {},
        )


@dataclass
class UnifiedGraphEdge:
    """Unified graph edge representation for xref, exporters, and APIs.

    This dataclass provides a consistent edge schema across:
    - XRef builder (chunker/graph/xref.py)
    - GraphCut (chunker/graph/cut.py)
    - Graph exporters
    - HTTP API (api/server.py)

    Attributes:
        src: Source node ID.
        dst: Destination node ID.
        type: Relationship type (e.g., 'CALLS', 'IMPORTS', 'DEFINES').
        weight: Edge weight for scoring/ranking (default 1.0).
    """

    src: str
    dst: str
    type: str
    weight: float = 1.0

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary format for API/export."""
        return {
            "src": self.src,
            "dst": self.dst,
            "type": self.type,
            "weight": self.weight,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "UnifiedGraphEdge":
        """Create from dictionary format."""
        return cls(
            src=data.get("src") or data.get("source_id", ""),
            dst=data.get("dst") or data.get("target_id", ""),
            type=data.get("type") or data.get("relationship_type", ""),
            weight=float(data.get("weight", 1.0)),
        )


class GraphNode:
    """Represents a node in the graph.

    .. deprecated::
        This class is deprecated. For new code, use :class:`UnifiedGraphNode`
        which provides a consistent schema across xref, GraphCut, exporters,
        and APIs. Use :meth:`to_unified` to convert to the new format.

    Note: This is the legacy GraphNode class maintained for backward compatibility.
    """

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

    def to_unified(self) -> UnifiedGraphNode:
        """Convert to UnifiedGraphNode format.

        Returns:
            UnifiedGraphNode with equivalent data.
        """
        return UnifiedGraphNode(
            id=self.chunk.node_id or self.chunk.chunk_id or self.id,
            file=str(self.chunk.file_path),
            lang=self.chunk.language,
            symbol=self.chunk.symbol_id,
            kind=self.chunk.node_type,
            attrs=self.properties,
        )


class GraphEdge:
    """Represents an edge between nodes in the graph.

    .. deprecated::
        This class is deprecated. For new code, use :class:`UnifiedGraphEdge`
        which provides a consistent schema. Use :meth:`to_unified` to convert.
    """

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

    def to_unified(self) -> UnifiedGraphEdge:
        """Convert to UnifiedGraphEdge format.

        Returns:
            UnifiedGraphEdge with equivalent data.
        """
        return UnifiedGraphEdge(
            src=self.source_id,
            dst=self.target_id,
            type=self.relationship_type,
            weight=float(self.properties.get("weight", 1.0)),
        )


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
        parent_chunk: CodeChunk,
        child_chunk: CodeChunk,
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
