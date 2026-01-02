"""Export module for treesitter-chunker."""

from .formats import (
    DOTExporter,
    GraphMLExporter,
    Neo4jExporter,
    PostgreSQLExporter,
    SemanticLensExporter,
    SQLiteExporter,
    StructuredJSONExporter,
    StructuredJSONLExporter,
)

try:  # optional parquet
    from .formats import StructuredParquetExporter  # type: ignore[attr-defined]
except Exception:
    StructuredParquetExporter = None  # type: ignore[assignment]
from .formatters import SchemaType, get_formatter
from .json_export import JSONExporter, JSONLExporter
from .relationships import ASTRelationshipTracker
from .structured_exporter import StructuredExportOrchestrator

__all__ = [
    "ASTRelationshipTracker",
    "DOTExporter",
    "GraphMLExporter",
    # Legacy exports
    "JSONExporter",
    "JSONLExporter",
    "Neo4jExporter",
    "PostgreSQLExporter",
    "SQLiteExporter",
    "SchemaType",
    "SemanticLensExporter",
    # Structured exports
    "StructuredExportOrchestrator",
    "StructuredJSONExporter",
    "StructuredJSONLExporter",
    "get_formatter",
]

# Only expose Parquet if available
if StructuredParquetExporter is not None:
    __all__.append("StructuredParquetExporter")
