"""Main structured export orchestrator with streaming support."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import fields
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from chunker.exceptions import ChunkerError
from chunker.interfaces.export import (
    ChunkRelationship,
    ExportFilter,
    ExportFormat,
    ExportMetadata,
    ExportTransformer,
    RelationshipType,
    StructuredExporter,
)

from chunker.types import CodeChunk

if TYPE_CHECKING:
    import io
    from collections.abc import Iterator

_Record = TypeVar("_Record", CodeChunk, ChunkRelationship)
_CHUNK_FIELDS = frozenset(field.name for field in fields(CodeChunk))
_RELATIONSHIP_FIELDS = frozenset(field.name for field in fields(ChunkRelationship))


def _same_field(original: Any, value: Any) -> bool:
    """An echoed protected field must preserve scalar and list element types."""
    if type(original) is not type(value):
        return False
    if isinstance(original, list):
        return len(original) == len(value) and all(
            _same_field(a, b) for a, b in zip(original, value, strict=True)
        )
    return bool(original == value)


def _apply_field(record: CodeChunk | ChunkRelationship, name: str, value: Any) -> None:
    if name == "metadata":
        if isinstance(record, ChunkRelationship) and value is None:
            record.metadata = value
        elif isinstance(value, dict) and all(isinstance(k, str) for k in value):
            record.metadata = deepcopy(value)
        else:
            raise ValueError("expected string-keyed metadata")
    elif isinstance(record, CodeChunk) and name == "content":
        if not isinstance(value, str):
            raise ValueError("expected string content")
        record.content = deepcopy(value)
    elif isinstance(record, ChunkRelationship) and name == "relationship_type":
        if not isinstance(value, (RelationshipType, str)):
            raise ValueError("expected a RelationshipType member or its string value")
        record.relationship_type = RelationshipType(value)
    else:
        known = _CHUNK_FIELDS if isinstance(record, CodeChunk) else _RELATIONSHIP_FIELDS
        if name not in known:
            raise ValueError("unknown field")
        if not _same_field(getattr(record, name), value):
            raise ValueError("protected field")


def _transform(record: _Record, stages: tuple[ExportTransformer, ...]) -> _Record:
    """Apply a snapshot of registrations to one retained record."""
    if isinstance(record, CodeChunk):
        label = f"chunk {record.chunk_id!r}"
    else:
        label = f"relationship {record.source_chunk_id!r} -> {record.target_chunk_id!r}"
    for position, stage in enumerate(stages, 1):
        operation = "copying input"
        try:
            if position == 1:
                # Preserve legacy IDs: dataclass reconstruction invokes __post_init__.
                record = deepcopy(record)
            argument = deepcopy(record)
            operation = "invoking hook"
            if isinstance(argument, CodeChunk):
                patch = stage.transform_chunk(argument)
            else:
                patch = stage.transform_relationship(argument)
            operation = "validating patch"
            if not isinstance(patch, dict):
                raise TypeError("expected a dict of field replacements")
            for name, value in patch.items():
                operation = "validating field name"
                if not isinstance(name, str):
                    raise TypeError("expected a string field name")
                operation = f"applying field {name!r}"
                _apply_field(record, name, value)
        except Exception as exc:
            raise ChunkerError(
                f"Transformer {position} ({type(stage).__name__}) failed "
                f"on {label} while {operation}"
            ) from exc
    return record


class StructuredExportOrchestrator(StructuredExporter):
    """Main orchestrator for structured exports with streaming support."""

    def __init__(self):
        self._exporters: dict[ExportFormat, StructuredExporter] = {}
        self._filters: list[ExportFilter] = []
        self._transformers: list[ExportTransformer] = []
        self._batch_size = 1000

    def register_exporter(
        self,
        fmt: ExportFormat,
        exporter: StructuredExporter,
    ) -> None:
        """Register an exporter for a specific fmt.

        Args:
            fmt: Export fmt
            exporter: Exporter instance
        """
        self._exporters[fmt] = exporter

    def add_filter(self, filter_func: ExportFilter) -> None:
        """Add a filter_func to the export pipeline.

        Args:
            filter_func: Filter to add
        """
        self._filters.append(filter_func)

    def add_transformer(self, transformer: ExportTransformer) -> None:
        """Append a patch stage, including duplicate registrations.

        Each export snapshots the stages before filtering. Retained records
        pass through them in registration order (on demand when streaming).
        """
        self._transformers.append(transformer)

    def export(
        self,
        chunks: list[CodeChunk],
        relationships: list[ChunkRelationship],
        output: Path | io.IOBase,
        metadata: ExportMetadata | None = None,
    ) -> None:
        """Export chunks with relationships.

        Args:
            chunks: List of code chunks
            relationships: List of chunk relationships
            output: Output path or stream
            metadata: Export metadata
        """
        fmt = self._determine_format(output, metadata)
        if fmt not in self._exporters:
            raise ChunkerError(f"No exporter registered for fmt: {fmt}")
        exporter = self._exporters[fmt]
        stages = tuple(self._transformers)
        filtered_chunks = self._apply_chunk_filters(chunks)
        filtered_relationships = self._apply_relationship_filters(
            relationships,
        )
        if stages:
            filtered_chunks = [_transform(chunk, stages) for chunk in filtered_chunks]
            filtered_relationships = [
                _transform(rel, stages) for rel in filtered_relationships
            ]
        if metadata is None:
            metadata = self._create_metadata(
                fmt,
                filtered_chunks,
                filtered_relationships,
                len(stages),
            )
        exporter.export(filtered_chunks, filtered_relationships, output, metadata)

    def export_streaming(
        self,
        chunk_iterator: Iterator[CodeChunk],
        relationship_iterator: Iterator[ChunkRelationship],
        output: Path | io.IOBase,
    ) -> None:
        """Export using iterators for large datasets.

        Args:
            chunk_iterator: Iterator yielding chunks
            relationship_iterator: Iterator yielding relationships
            output: Output path or stream
        """
        fmt = self._determine_format(output, None)
        if fmt not in self._exporters:
            raise ChunkerError(f"No exporter registered for fmt: {fmt}")
        exporter = self._exporters[fmt]
        stages = tuple(self._transformers)
        filtered_chunks = self._filter_chunk_iterator(chunk_iterator)
        filtered_relationships = self._filter_relationship_iterator(
            relationship_iterator,
        )
        if stages:
            filtered_chunks = (_transform(chunk, stages) for chunk in filtered_chunks)
            filtered_relationships = (
                _transform(rel, stages) for rel in filtered_relationships
            )
        exporter.export_streaming(filtered_chunks, filtered_relationships, output)

    def supports_format(self, fmt: ExportFormat) -> bool:
        """Check if this exporter supports a fmt.

        Args:
            fmt: Export fmt to check

        Returns:
            True if fmt is supported
        """
        return fmt in self._exporters

    def get_schema(self) -> dict[str, Any]:
        """Get the export schema.

        Returns:
            Schema definition for this exporter
        """
        return {
            "supported_formats": [f.value for f in self._exporters],
            "filters": len(self._filters),
            "transformers": len(self._transformers),
            "batch_size": self._batch_size,
        }

    def set_batch_size(self, size: int) -> None:
        """Set batch size for streaming operations.

        Args:
            size: Batch size
        """
        self._batch_size = size

    @classmethod
    def _determine_format(
        cls,
        output: Path | io.IOBase,
        metadata: ExportMetadata | None,
    ) -> ExportFormat:
        """Determine export fmt from output or metadata."""
        if metadata and metadata.fmt:
            return metadata.fmt
        if isinstance(output, str | Path):
            path = Path(output)
            ext = path.suffix.lower()
            format_map = {
                ".json": ExportFormat.JSON,
                ".jsonl": ExportFormat.JSONL,
                ".parquet": ExportFormat.PARQUET,
                ".graphml": ExportFormat.GRAPHML,
                ".dot": ExportFormat.DOT,
                ".db": ExportFormat.SQLITE,
                ".sqlite": ExportFormat.SQLITE,
                ".sqlite3": ExportFormat.SQLITE,
                ".cypher": ExportFormat.NEO4J,
                ".cql": ExportFormat.NEO4J,
                ".slb": ExportFormat.SEMANTIC_LENS,
            }
            if ext in format_map:
                return format_map[ext]
        raise ChunkerError("Cannot determine export fmt from output path")

    def _apply_chunk_filters(self, chunks: list[CodeChunk]) -> list[CodeChunk]:
        """Apply all filters to chunks."""
        result = chunks
        for filter_func in self._filters:
            result = [c for c in result if filter_func.should_include_chunk(c)]
        return result

    def _apply_relationship_filters(
        self,
        relationships: list[ChunkRelationship],
    ) -> list[ChunkRelationship]:
        """Apply all filters to relationships."""
        result = relationships
        for filter_func in self._filters:
            result = [r for r in result if filter_func.should_include_relationship(r)]
        return result

    def _create_metadata(
        self,
        fmt: ExportFormat,
        chunks: list[CodeChunk],
        relationships: list[ChunkRelationship],
        transformer_count: int,
    ) -> ExportMetadata:
        """Create export metadata."""
        source_files = list({chunk.file_path for chunk in chunks})
        return ExportMetadata(
            fmt=fmt,
            version="1.0",
            created_at=datetime.now(UTC).isoformat(),
            source_files=source_files,
            chunk_count=len(chunks),
            relationship_count=len(relationships),
            options={
                "filters": len(self._filters),
                "transformers": transformer_count,
                "batch_size": self._batch_size,
            },
        )

    def _filter_chunk_iterator(
        self,
        iterator: Iterator[CodeChunk],
    ) -> Iterator[CodeChunk]:
        """Create a filtering iterator for chunks."""
        for chunk in iterator:
            should_include = all(
                filter_func.should_include_chunk(chunk) for filter_func in self._filters
            )
            if should_include:
                yield chunk

    def _filter_relationship_iterator(
        self,
        iterator: Iterator[ChunkRelationship],
    ) -> Iterator[ChunkRelationship]:
        """Create a filtering iterator for relationships."""
        for rel in iterator:
            should_include = all(
                filter_func.should_include_relationship(rel)
                for filter_func in self._filters
            )
            if should_include:
                yield rel
