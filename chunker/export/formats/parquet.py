"""Export chunks and relationships to Apache Parquet fmt."""

from __future__ import annotations

import io
import json
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import pyarrow as pa
import pyarrow.parquet as pq

from chunker.exceptions import ChunkerError
from chunker.interfaces.export import (
    ChunkRelationship,
    ExportFormat,
    ExportMetadata,
    StructuredExporter,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from chunker.types import CodeChunk


class StructuredParquetExporter(StructuredExporter):
    """Export chunks and relationships to Parquet fmt with full structure."""

    def __init__(
        self,
        compression: str = "snappy",
        partition_by: list[str] | None = None,
    ):
        """Initialize the Parquet exporter.

        Args:
            compression: Compression codec ('snappy', 'gzip', 'brotli', 'lz4', 'zstd', None)
            partition_by: List of columns to partition by (e.g., ['language', 'file_path'])
        """
        self.compression = compression
        self.partition_by = partition_by
        self._batch_size = 10000
        self._chunks_schema = self._create_chunks_schema()
        self._relationships_schema = self._create_relationships_schema()

    def export(
        self,
        chunks: list[CodeChunk],
        relationships: list[ChunkRelationship],
        output: Path | io.IOBase,
        metadata: ExportMetadata | None = None,
    ) -> None:
        """Export chunks with relationships to Parquet.

        For run.v1.parquet the flat files are run.v1_chunks.parquet and
        run.v1_relationships.parquet, plus run.v1_metadata.parquet when
        metadata is supplied. With recognized partition columns, read chunks
        using pyarrow.dataset.dataset("run.v1_chunks", format="parquet").
        Each leaf retains the typed partition columns. Directory values use
        UTF-8 percent encoding. Case-insensitive component collisions within
        one export raise ChunkerError before any leaf is written.

        Reusing a root replaces matching leaves and retains other partitions.
        Use a fresh root for a clean snapshot. To migrate older shared-parent
        datasets, re-export the original chunks into a named root.

        Args:
            chunks: List of code chunks
            relationships: List of chunk relationships
            output: Output path (base name for files)
            metadata: Export metadata
        """
        if isinstance(output, io.IOBase):
            raise ChunkerError("Parquet export requires a file path, not a stream")
        base_path = Path(output).with_suffix("")
        chunks_path = f"{base_path}_chunks.parquet"
        self._export_chunks(chunks, chunks_path)
        relationships_path = f"{base_path}_relationships.parquet"
        self._export_relationships(relationships, relationships_path)
        if metadata:
            metadata_path = f"{base_path}_metadata.parquet"
            self._export_metadata(metadata, metadata_path)

    def export_streaming(
        self,
        chunk_iterator: Iterator[CodeChunk],
        relationship_iterator: Iterator[ChunkRelationship],
        output: Path | io.IOBase,
    ) -> None:
        """Write <base>_chunks.parquet followed by <base>_relationships.parquet.

        Each exhausted stream produces a typed file, including empty streams.
        An iterator failure before the first batch leaves that artifact untouched.
        Previously flushed batches and completed artifacts remain readable.
        """
        if isinstance(output, io.IOBase):
            raise ChunkerError("Parquet export requires a file path, not a stream")
        base_path = Path(output).with_suffix("")
        chunks_path = f"{base_path}_chunks.parquet"
        self._stream_records(
            map(self._chunk_to_dict, chunk_iterator), self._chunks_schema, chunks_path
        )
        relationships_path = f"{base_path}_relationships.parquet"
        self._stream_records(
            map(self._relationship_to_dict, relationship_iterator),
            self._relationships_schema,
            relationships_path,
        )

    @staticmethod
    def supports_format(fmt: ExportFormat) -> bool:
        """Check if this exporter supports a fmt."""
        return fmt == ExportFormat.PARQUET

    def get_schema(self) -> dict[str, Any]:
        """Get the export schema."""
        return {
            "fmt": "parquet",
            "version": "2.6",
            "compression": self.compression,
            "partition_by": self.partition_by,
            "batch_size": self._batch_size,
            "schemas": {
                "chunks": self._chunks_schema.to_string(),
                "relationships": self._relationships_schema.to_string(),
            },
        }

    def set_batch_size(self, size: int) -> None:
        """Set batch size for streaming operations."""
        self._batch_size = size

    @staticmethod
    def _create_chunks_schema() -> pa.Schema:
        """Create PyArrow schema for chunks."""
        return pa.schema(
            [
                pa.field("chunk_id", pa.string(), nullable=False),
                pa.field("language", pa.string(), nullable=False),
                pa.field("file_path", pa.string(), nullable=False),
                pa.field("node_type", pa.string(), nullable=False),
                pa.field("start_line", pa.int64(), nullable=False),
                pa.field("end_line", pa.int64(), nullable=False),
                pa.field("byte_start", pa.int64(), nullable=False),
                pa.field("byte_end", pa.int64(), nullable=False),
                pa.field("parent_context", pa.string()),
                pa.field("content", pa.string(), nullable=False),
                pa.field("parent_chunk_id", pa.string()),
                pa.field("references", pa.list_(pa.string())),
                pa.field("dependencies", pa.list_(pa.string())),
                pa.field("lines_of_code", pa.int64()),
                pa.field("byte_size", pa.int64()),
            ],
        )

    @staticmethod
    def _create_relationships_schema() -> pa.Schema:
        """Create PyArrow schema for relationships."""
        return pa.schema(
            [
                pa.field("source_chunk_id", pa.string(), nullable=False),
                pa.field("target_chunk_id", pa.string(), nullable=False),
                pa.field("relationship_type", pa.string(), nullable=False),
                pa.field("metadata", pa.string()),
            ],
        )

    @staticmethod
    def _create_metadata_schema() -> pa.Schema:
        """Create PyArrow schema for metadata."""
        return pa.schema(
            [
                pa.field("fmt", pa.string()),
                pa.field("version", pa.string()),
                pa.field("created_at", pa.string()),
                pa.field("source_files", pa.list_(pa.string())),
                pa.field("chunk_count", pa.int64()),
                pa.field("relationship_count", pa.int64()),
                pa.field("options", pa.string()),
            ],
        )

    @staticmethod
    def _chunk_to_dict(chunk: CodeChunk) -> dict[str, Any]:
        """Convert a CodeChunk to a dictionary."""
        return {
            "chunk_id": chunk.chunk_id,
            "language": chunk.language,
            "file_path": chunk.file_path,
            "node_type": chunk.node_type,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "byte_start": chunk.byte_start,
            "byte_end": chunk.byte_end,
            "parent_context": chunk.parent_context or "",
            "content": chunk.content,
            "parent_chunk_id": chunk.parent_chunk_id or "",
            "references": chunk.references,
            "dependencies": chunk.dependencies,
            "lines_of_code": chunk.end_line - chunk.start_line + 1,
            "byte_size": chunk.byte_end - chunk.byte_start,
        }

    @staticmethod
    def _relationship_to_dict(rel: ChunkRelationship) -> dict[str, Any]:
        """Convert a ChunkRelationship to a dictionary."""
        return {
            "source_chunk_id": rel.source_chunk_id,
            "target_chunk_id": rel.target_chunk_id,
            "relationship_type": rel.relationship_type.value,
            "metadata": json.dumps(rel.metadata) if rel.metadata else "",
        }

    def _export_chunks(self, chunks: list[CodeChunk], output_path: str | Path) -> None:
        """Export chunks to Parquet file."""
        records = [self._chunk_to_dict(chunk) for chunk in chunks]
        table = pa.Table.from_pylist(records, schema=self._chunks_schema)
        columns = [col for col in self.partition_by or [] if col in table.column_names]
        if not columns:
            with pa.OSFile(str(output_path), "wb") as sink:
                pq.write_table(table, sink, compression=self.compression)
            return

        root = Path(output_path).with_suffix("")
        partitions: dict[tuple[Any, ...], list[int]] = {}
        partition_columns = [table.column(col) for col in columns]
        for index, values in enumerate(zip(*partition_columns, strict=True)):
            key = tuple(value.as_py() for value in values)
            partitions.setdefault(key, []).append(index)

        # Validate each directory component, including shared intermediate ones,
        # before touching any leaf. This also catches aliases on Linux.
        seen: dict[tuple[Path, str], Any] = {}
        leaves = {}
        for key, indices in partitions.items():
            directory = root
            for column, value in zip(columns, key, strict=True):
                encoded = quote(str(value), safe="")
                stem = encoded.rstrip(".")
                component = f"{column}={stem}" + "%2E" * (len(encoded) - len(stem))
                alias = (directory, component.lower())
                if seen.setdefault(alias, value) != value:
                    raise ChunkerError(
                        f"Partition path collision at {directory / component}"
                    )
                directory /= component
            leaves[directory] = indices

        root.mkdir(parents=True, exist_ok=True)
        for directory, indices in leaves.items():
            directory.mkdir(parents=True, exist_ok=True)
            with pa.OSFile(str(directory / "data.parquet"), "wb") as sink:
                pq.write_table(table.take(indices), sink, compression=self.compression)

    def _export_relationships(
        self,
        relationships: list[ChunkRelationship],
        output_path: str | Path,
    ) -> None:
        """Export relationships to Parquet file."""
        records = [self._relationship_to_dict(rel) for rel in relationships]
        table = pa.Table.from_pylist(records, schema=self._relationships_schema)
        with pa.OSFile(str(output_path), "wb") as sink:
            pq.write_table(table, sink, compression=self.compression)

    def _export_metadata(
        self,
        metadata: ExportMetadata,
        output_path: str | Path,
    ) -> None:
        """Export metadata to Parquet file."""
        record = {
            "fmt": metadata.fmt.value,
            "version": metadata.version,
            "created_at": metadata.created_at,
            "source_files": metadata.source_files,
            "chunk_count": metadata.chunk_count,
            "relationship_count": metadata.relationship_count,
            "options": json.dumps(metadata.options),
        }
        table = pa.Table.from_pylist([record], schema=self._create_metadata_schema())
        with pa.OSFile(str(output_path), "wb") as sink:
            pq.write_table(table, sink, compression=self.compression)

    def _stream_records(
        self, records: Iterator[dict[str, Any]], schema: pa.Schema, output_path: str
    ) -> None:
        def tables() -> Iterator[pa.Table]:
            batch = []
            for record in records:
                batch.append(record)
                if len(batch) >= self._batch_size:
                    yield pa.Table.from_pylist(batch, schema=schema)
                    batch.clear()
            if batch:
                yield pa.Table.from_pylist(batch, schema=schema)

        batches = tables()
        # Consume and convert the first batch before truncating an existing file.
        # Normal exhaustion yields an empty table with the same declared schema.
        first = next(batches, None)
        with (
            pa.OSFile(output_path, "wb") as sink,
            pq.ParquetWriter(
                sink, schema=schema, compression=self.compression
            ) as writer,
        ):
            writer.write_table(first if first is not None else schema.empty_table())
            del first
            for batch in batches:
                writer.write_table(batch)
