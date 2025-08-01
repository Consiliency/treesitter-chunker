"""Structure-preserving export interfaces.

Interfaces for exporting chunks with relationships, metadata,
and hierarchical structure intact.
"""
import io
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from chunker.types import CodeChunk


class ExportFormat(Enum):
    """Supported export formats."""
    JSON = "json"
    JSONL = "jsonl"
    PARQUET = "parquet"
    GRAPHML = "graphml"
    NEO4J = "neo4j"
    DOT = "dot"
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"


class RelationshipType(Enum):
    """Types of relationships between chunks."""
    PARENT_CHILD = "parent_child"
    CALLS = "calls"
    IMPORTS = "imports"
    INHERITS = "inherits"
    IMPLEMENTS = "implements"
    USES = "uses"
    DEFINES = "defines"
    REFERENCES = "references"
    DEPENDS_ON = "depends_on"


@dataclass
class ChunkRelationship:
    """Represents a relationship between two chunks.

    Attributes:
        source_chunk_id: ID of the source chunk
        target_chunk_id: ID of the target chunk
        relationship_type: Type of relationship
        metadata: Additional relationship metadata
    """
    source_chunk_id: str
    target_chunk_id: str
    relationship_type: RelationshipType
    metadata: dict[str, Any] = None


@dataclass
class ExportMetadata:
    """Metadata for an export operation.

    Attributes:
        fmt: Export fmt used
        version: Format version
        created_at: When export was created
        source_files: List of source files included
        chunk_count: Total number of chunks
        relationship_count: Total number of relationships
        options: Export options used
    """
    fmt: ExportFormat
    version: str
    created_at: str
    source_files: list[str]
    chunk_count: int
    relationship_count: int
    options: dict[str, Any]


class StructuredExporter(ABC):
    """Base interface for structured export."""

    @staticmethod
    @abstractmethod
    def export(chunks: list[CodeChunk], relationships: list[
        ChunkRelationship], output: (Path | io.IOBase), metadata: (
        ExportMetadata | None) = None) -> None:
        """Export chunks with relationships.

        Args:
            chunks: List of code chunks
            relationships: List of chunk relationships
            output: Output path or stream
            metadata: Export metadata
        """

    @staticmethod
    @abstractmethod
    def export_streaming(chunk_iterator: Any, relationship_iterator: Any,
        output: (Path | io.IOBase)) -> None:
        """Export using iterators for large datasets.

        Args:
            chunk_iterator: Iterator yielding chunks
            relationship_iterator: Iterator yielding relationships
            output: Output path or stream
        """

    @staticmethod
    @abstractmethod
    def supports_format(fmt: ExportFormat) -> bool:
        """Check if this exporter supports a fmt.

        Args:
            fmt: Export fmt to check

        Returns:
            True if fmt is supported
        """

    @staticmethod
    @abstractmethod
    def get_schema() -> dict[str, Any]:
        """Get the export schema.

        Returns:
            Schema definition for this exporter
        """


class RelationshipTracker(ABC):
    """Track relationships between chunks."""

    @staticmethod
    @abstractmethod
    def track_relationship(source: CodeChunk, target: CodeChunk,
        relationship_type: RelationshipType, metadata: (dict[str, Any] |
        None) = None) -> None:
        """Track a relationship between chunks.

        Args:
            source: Source chunk
            target: Target chunk
            relationship_type: Type of relationship
            metadata: Additional metadata
        """

    @staticmethod
    @abstractmethod
    def get_relationships(chunk: (CodeChunk | None) = None, relationship_type:
        (RelationshipType | None) = None) -> list[ChunkRelationship]:
        """Get tracked relationships.

        Args:
            chunk: Filter by specific chunk (None for all)
            relationship_type: Filter by type (None for all)

        Returns:
            List of relationships
        """

    @staticmethod
    @abstractmethod
    def infer_relationships(chunks: list[CodeChunk]) -> list[ChunkRelationship]:
        """Infer relationships from chunk data.

        Args:
            chunks: List of chunks to analyze

        Returns:
            List of inferred relationships
        """

    @staticmethod
    @abstractmethod
    def clear() -> None:
        """Clear all tracked relationships."""


class GraphExporter(StructuredExporter):
    """Specialized exporter for graph formats."""

    @staticmethod
    @abstractmethod
    def set_node_attributes(attributes: list[str]) -> None:
        """Set which chunk attributes to include as node properties.

        Args:
            attributes: List of attribute names
        """

    @staticmethod
    @abstractmethod
    def set_edge_attributes(attributes: list[str]) -> None:
        """Set which relationship attributes to include as edge properties.

        Args:
            attributes: List of attribute names
        """

    @staticmethod
    @abstractmethod
    def add_layout_hints(layout_algorithm: str) -> None:
        """Add layout hints for visualization.

        Args:
            layout_algorithm: Name of layout algorithm
        """


class DatabaseExporter(StructuredExporter):
    """Specialized exporter for database formats."""

    @staticmethod
    @abstractmethod
    def set_table_names(chunks_table: str, relationships_table: str) -> None:
        """Set custom table names.

        Args:
            chunks_table: Name for chunks table
            relationships_table: Name for relationships table
        """

    @staticmethod
    @abstractmethod
    def create_indexes(columns: list[str]) -> None:
        """Create indexes on specified columns.

        Args:
            columns: Column names to index
        """

    @staticmethod
    @abstractmethod
    def set_batch_size(size: int) -> None:
        """Set batch size for inserts.

        Args:
            size: Number of records per batch
        """


class HierarchicalExporter(StructuredExporter):
    """Exporter that preserves hierarchical structure."""

    @staticmethod
    @abstractmethod
    def export_tree(root_chunks: list[CodeChunk], output: (Path | io.IOBase),
        ) -> None:
        """Export chunks as a tree structure.

        Args:
            root_chunks: Top-level chunks
            output: Output path or stream
        """

    @staticmethod
    @abstractmethod
    def set_nesting_limit(limit: int) -> None:
        """Set maximum nesting depth.

        Args:
            limit: Maximum depth (0 for unlimited)
        """


class ExportFilter(ABC):
    """Filter chunks and relationships during export."""

    @staticmethod
    @abstractmethod
    def should_include_chunk(chunk: CodeChunk) -> bool:
        """Determine if a chunk should be exported.

        Args:
            chunk: Chunk to evaluate

        Returns:
            True if chunk should be included
        """

    @staticmethod
    @abstractmethod
    def should_include_relationship(relationship: ChunkRelationship) -> bool:
        """Determine if a relationship should be exported.

        Args:
            relationship: Relationship to evaluate

        Returns:
            True if relationship should be included
        """


class ExportTransformer(ABC):
    """Transform chunks during export."""

    @staticmethod
    @abstractmethod
    def transform_chunk(chunk: CodeChunk) -> dict[str, Any]:
        """Transform a chunk for export.

        Args:
            chunk: Chunk to transform

        Returns:
            Transformed chunk data
        """

    @staticmethod
    @abstractmethod
    def transform_relationship(relationship: ChunkRelationship) -> dict[str, Any,
        ]:
        """Transform a relationship for export.

        Args:
            relationship: Relationship to transform

        Returns:
            Transformed relationship data
        """
