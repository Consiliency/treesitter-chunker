"""Main structured export orchestrator with streaming support."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from chunker.exceptions import ChunkerError
from chunker.interfaces.export import (
    ChunkRelationship,
    ExportFilter,
    ExportFormat,
    ExportMetadata,
    ExportTransformer,
    StructuredExporter,
)

if TYPE_CHECKING:
    import io
    from collections.abc import Iterator

    from chunker.types import CodeChunk


class StructuredExportOrchestrator(StructuredExporter):
    """Main orchestrator for structured exports with streaming support."""

    def __init__(self):
        self._exporters: dict[ExportFormat, StructuredExporter] = {}
        self._filters: list[ExportFilter] = []
        self._transformers: list[ExportTransformer] = []
        self._batch_size = 1000

    def register_exporter(self, fmt: ExportFormat, exporter: StructuredExporter,
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
        """Add a transformer to the export pipeline.

        Args:
            transformer: Transformer to add
        """
        self._transformers.append(transformer)

    def export(self, chunks: list[CodeChunk], relationships: list[
        ChunkRelationship], output: (Path | io.IOBase), metadata: (
        ExportMetadata | None) = None) -> None:
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
        filtered_chunks = self._apply_chunk_filters(chunks)
        filtered_relationships = self._apply_relationship_filters(relationships,
            )
        if metadata is None:
            metadata = self._create_metadata(fmt, filtered_chunks,
                filtered_relationships)
        exporter = self._exporters[fmt]
        exporter.export(filtered_chunks, filtered_relationships, output,
            metadata)

    def export_streaming(self, chunk_iterator: Iterator[CodeChunk],
        relationship_iterator: Iterator[ChunkRelationship], output: (Path |
        io.IOBase)) -> None:
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
        filtered_chunks = self._filter_chunk_iterator(chunk_iterator)
        filtered_relationships = self._filter_relationship_iterator(
            relationship_iterator)
        exporter.export_streaming(filtered_chunks, filtered_relationships,
            output)

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
        return {"supported_formats": [f.value for f in self._exporters],
            "filters": len(self._filters), "transformers": len(self.
            _transformers), "batch_size": self._batch_size}

    def set_batch_size(self, size: int) -> None:
        """Set batch size for streaming operations.

        Args:
            size: Batch size
        """
        self._batch_size = size

    @classmethod
    def _determine_format(cls, output: (Path | io.IOBase), metadata: (
        ExportMetadata | None)) -> ExportFormat:
        """Determine export fmt from output or metadata."""
        if metadata and metadata.fmt:
            return metadata.fmt
        if isinstance(output, str | Path):
            path = Path(output)
            ext = path.suffix.lower()
            format_map = {".json": ExportFormat.JSON, ".jsonl":
                ExportFormat.JSONL, ".parquet": ExportFormat.PARQUET,
                ".graphml": ExportFormat.GRAPHML, ".dot": ExportFormat.DOT,
                ".db": ExportFormat.SQLITE, ".sqlite": ExportFormat.SQLITE,
                ".sqlite3": ExportFormat.SQLITE, ".cypher": ExportFormat.
                NEO4J, ".cql": ExportFormat.NEO4J}
            if ext in format_map:
                return format_map[ext]
        raise ChunkerError("Cannot determine export fmt from output path")

    def _apply_chunk_filters(self, chunks: list[CodeChunk]) -> list[CodeChunk]:
        """Apply all filters to chunks."""
        result = chunks
        for filter_func in self._filters:
            result = [c for c in result if filter_func.should_include_chunk(c)]
        return result

    def _apply_relationship_filters(self, relationships: list[
        ChunkRelationship]) -> list[ChunkRelationship]:
        """Apply all filters to relationships."""
        result = relationships
        for filter_func in self._filters:
            result = [r for r in result if filter_func.
                should_include_relationship(r)]
        return result

    def _apply_chunk_transformers(self, chunks: list[CodeChunk]) -> list[dict
        [str, Any]]:
        """Apply all transformers to chunks."""
        result = []
        for chunk in chunks:
            transformed = chunk.__dict__.copy()
            for transformer in self._transformers:
                transformed = transformer.transform_chunk(chunk)
            result.append(transformed)
        return result

    def _apply_relationship_transformers(self, relationships: list[
        ChunkRelationship]) -> list[dict[str, Any]]:
        """Apply all transformers to relationships."""
        result = []
        for rel in relationships:
            transformed = {"source_chunk_id": rel.source_chunk_id,
                "target_chunk_id": rel.target_chunk_id, "relationship_type":
                rel.relationship_type.value, "metadata": rel.metadata or {}}
            for transformer in self._transformers:
                transformed = transformer.transform_relationship(rel)
            result.append(transformed)
        return result

    def _create_metadata(self, fmt: ExportFormat, chunks: list[Any],
        relationships: list[Any]) -> ExportMetadata:
        """Create export metadata."""
        source_files = list({(c.file_path if hasattr(c, "file_path") else c
            .get("file_path", "")) for c in chunks})
        return ExportMetadata(fmt=fmt, version="1.0", created_at=datetime.
            now(timezone.utc).isoformat(), source_files=source_files,
            chunk_count=len(chunks), relationship_count=len(relationships),
            options={"filters": len(self._filters), "transformers": len(
            self._transformers), "batch_size": self._batch_size})

    def _filter_chunk_iterator(self, iterator: Iterator[CodeChunk]) -> Iterator[
        CodeChunk]:
        """Create a filtering iterator for chunks."""
        for chunk in iterator:
            should_include = all(filter_func.should_include_chunk(chunk) for
                filter_func in self._filters)
            if should_include:
                yield chunk

    def _filter_relationship_iterator(self, iterator: Iterator[
        ChunkRelationship]) -> Iterator[ChunkRelationship]:
        """Create a filtering iterator for relationships."""
        for rel in iterator:
            should_include = all(filter_func.should_include_relationship(
                rel) for filter_func in self._filters)
            if should_include:
                yield rel

    def _transform_chunk_iterator(self, iterator: Iterator[CodeChunk],
        ) -> Iterator[dict[str, Any]]:
        """Create a transforming iterator for chunks."""
        for chunk in iterator:
            transformed = chunk.__dict__.copy()
            for transformer in self._transformers:
                transformed = transformer.transform_chunk(chunk)
            yield transformed

    def _transform_relationship_iterator(self, iterator: Iterator[
        ChunkRelationship]) -> Iterator[dict[str, Any]]:
        """Create a transforming iterator for relationships."""
        for rel in iterator:
            transformed = {"source_chunk_id": rel.source_chunk_id,
                "target_chunk_id": rel.target_chunk_id, "relationship_type":
                rel.relationship_type.value, "metadata": rel.metadata or {}}
            for transformer in self._transformers:
                transformed = transformer.transform_relationship(rel)
            yield transformed
