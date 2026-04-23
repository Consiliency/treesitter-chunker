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
from .boundary_ir import BoundaryIRExporter, write_boundary_ir
from .json_export import JSONExporter, JSONLExporter
from .relationships import ASTRelationshipTracker
from .structured_exporter import StructuredExportOrchestrator

__all__ = [
    "ASTRelationshipTracker",
    "BoundaryIRExporter",
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
    "write_boundary_ir",
]

# Only expose Parquet if available
if StructuredParquetExporter is not None:
    __all__.append("StructuredParquetExporter")
