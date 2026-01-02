"""Export format implementations."""

from .database import PostgreSQLExporter, SQLiteExporter
from .graph import DOTExporter, GraphMLExporter
from .json import StructuredJSONExporter, StructuredJSONLExporter
from .neo4j import Neo4jExporter
from .semantic_lens import SemanticLensExporter

# Make Parquet optional at import time to avoid heavy dependency import errors
try:  # pragma: no cover
    from .parquet import StructuredParquetExporter  # type: ignore

    _PARQUET_AVAILABLE = True
except Exception:  # pyarrow/numpy may be absent or broken in some envs
    StructuredParquetExporter = None  # type: ignore
    _PARQUET_AVAILABLE = False

__all__ = [
    "DOTExporter",
    "GraphMLExporter",
    "Neo4jExporter",
    "PostgreSQLExporter",
    "SemanticLensExporter",
    "SQLiteExporter",
    "StructuredJSONExporter",
    "StructuredJSONLExporter",
    # Parquet exporter is exported only if available
]

if _PARQUET_AVAILABLE:
    __all__.append("StructuredParquetExporter")
