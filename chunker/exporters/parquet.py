"""Parquet export functionality for code chunks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from chunker.chunker import CodeChunk


class ParquetExporter:
    """Export code chunks to Apache Parquet format with nested schema support."""

    def __init__(
        self,
        columns: list[str] | None = None,
        partition_by: list[str] | None = None,
        compression: str = "snappy",
    ):
        """
        Initialize the Parquet exporter.

        Args:
            columns: List of columns to include in export. If None, includes all.
            partition_by: List of columns to partition by (e.g., ['language', 'file_path'])
            compression: Compression codec ('snappy', 'gzip', 'brotli', 'lz4', 'zstd', None)
        """
        self.columns = columns
        self.partition_by = partition_by
        self.compression = compression
        self._schema = self._create_schema()

    def _create_schema(self) -> pa.Schema:
        """Create the PyArrow schema with nested structure for metadata."""
        # Base fields
        fields = [
            pa.field("language", pa.string()),
            pa.field("file_path", pa.string()),
            pa.field("node_type", pa.string()),
            pa.field("content", pa.string()),
            pa.field("parent_context", pa.string()),
        ]

        # Nested metadata structure
        metadata_fields = [
            pa.field("start_line", pa.int64()),
            pa.field("end_line", pa.int64()),
            pa.field("byte_start", pa.int64()),
            pa.field("byte_end", pa.int64()),
        ]
        metadata_struct = pa.struct(metadata_fields)
        fields.append(pa.field("metadata", metadata_struct))

        # Computed fields
        fields.extend(
            [
                pa.field("lines_of_code", pa.int64()),
                pa.field("byte_size", pa.int64()),
            ],
        )

        return pa.schema(fields)

    def _chunk_to_dict(self, chunk: CodeChunk) -> dict[str, Any]:
        """Convert a CodeChunk to a dictionary with nested metadata."""
        return {
            "language": chunk.language,
            "file_path": chunk.file_path,
            "node_type": chunk.node_type,
            "content": chunk.content,
            "parent_context": chunk.parent_context,
            "metadata": {
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "byte_start": chunk.byte_start,
                "byte_end": chunk.byte_end,
            },
            "lines_of_code": chunk.end_line - chunk.start_line + 1,
            "byte_size": chunk.byte_end - chunk.byte_start,
        }

    def _filter_columns(self, data: dict[str, Any]) -> dict[str, Any]:
        """Filter data to include only selected columns."""
        if not self.columns:
            return data

        filtered = {}
        for col in self.columns:
            if col in data:
                filtered[col] = data[col]
            elif col == "metadata":
                # Special handling for nested metadata
                filtered[col] = data.get("metadata", {})

        return filtered

    def export(self, chunks: list[CodeChunk], output_path: Path | str) -> None:
        """
        Export chunks to Parquet file(s).

        Args:
            chunks: List of CodeChunk objects to export
            output_path: Path to output file or directory (if partitioned)
        """
        output_path = Path(output_path)

        # Convert chunks to dictionaries
        records = [self._chunk_to_dict(chunk) for chunk in chunks]

        # Filter columns if specified
        if self.columns:
            records = [self._filter_columns(record) for record in records]
            # Create filtered schema
            schema_fields = [f for f in self._schema if f.name in self.columns]
            schema = pa.schema(schema_fields)
        else:
            schema = self._schema

        # Create PyArrow table
        table = pa.Table.from_pylist(records, schema=schema)

        # Write to Parquet
        if self.partition_by:
            # Partitioned dataset
            pq.write_to_dataset(
                table,
                root_path=str(output_path),
                partition_cols=self.partition_by,
                compression=self.compression,
            )
        else:
            # Single file
            pq.write_table(
                table,
                str(output_path),
                compression=self.compression,
            )

    def export_streaming(
        self,
        chunks_iterator,
        output_path: Path | str,
        batch_size: int = 1000,
    ) -> None:
        """
        Export chunks using streaming for large datasets.

        Args:
            chunks_iterator: Iterator of CodeChunk objects
            output_path: Path to output file
            batch_size: Number of chunks to process in each batch
        """
        output_path = Path(output_path)
        writer = None
        batch = []

        try:
            for chunk in chunks_iterator:
                batch.append(self._chunk_to_dict(chunk))

                if len(batch) >= batch_size:
                    # Process batch
                    if self.columns:
                        batch = [self._filter_columns(record) for record in batch]

                    table = pa.Table.from_pylist(batch, schema=self._schema)

                    if writer is None:
                        writer = pq.ParquetWriter(
                            str(output_path),
                            schema=table.schema,
                            compression=self.compression,
                        )

                    writer.write_table(table)
                    batch = []

            # Write remaining batch
            if batch:
                if self.columns:
                    batch = [self._filter_columns(record) for record in batch]

                table = pa.Table.from_pylist(batch, schema=self._schema)

                if writer is None:
                    writer = pq.ParquetWriter(
                        str(output_path),
                        schema=table.schema,
                        compression=self.compression,
                    )

                writer.write_table(table)

        finally:
            if writer:
                writer.close()
