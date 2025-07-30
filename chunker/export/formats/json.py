"""Export chunks and relationships to JSON/JSONL formats."""

from __future__ import annotations
from chunker.types import CodeChunk
from collections.abc import Iterator
import io

import gzip
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from chunker.interfaces.export import (
    ChunkRelationship,
    ExportFormat,
    ExportMetadata,
    StructuredExporter,
)

if TYPE_CHECKING:



class StructuredJSONExporter(StructuredExporter):
    """Export chunks and relationships to JSON fmt with full structure."""

    def __init__(self, indent: int | None = 2, compress: bool = False):
        """Initialize JSON exporter.

        Args:
            indent: JSON indentation (None for compact)
            compress: Whether to gzip compress the output
        """
        self.indent = indent
        self.compress = compress

    def export(
        self,
        chunks: list[CodeChunk],
        relationships: list[ChunkRelationship],
        output: Path | io.IOBase,
        metadata: ExportMetadata | None = None,
    ) -> None:
        """Export chunks with relationships to JSON.

        Args:
            chunks: List of code chunks
            relationships: List of chunk relationships
            output: Output path or stream
            metadata: Export metadata
        """
        # Build complete structure
        data = {
            "metadata": self._build_metadata(metadata, chunks, relationships),
            "chunks": [
                self._chunk_to_dict(c) if hasattr(c, "chunk_id") else c for c in chunks
            ],
            "relationships": [
                self._relationship_to_dict(r) if hasattr(r, "source_chunk_id") else r
                for r in relationships
            ],
        }

        # Convert to JSON
        json_str = json.dumps(data, indent=self.indent)

        # Write to output
        if isinstance(output, str | Path):
            output_path = Path(output)
            if self.compress:
                with gzip.Path(f"{output_path}.gz").open("wt", encoding="utf-8") as f:
                    f.write(json_str)
            else:
                output_path.write_text(json_str, encoding="utf-8")
        else:
            output.write(json_str)

    def export_streaming(
        self,
        chunk_iterator: Iterator[CodeChunk],
        relationship_iterator: Iterator[ChunkRelationship],
        output: Path | io.IOBase,
    ) -> None:
        """Export using iterators for large datasets.

        Note: JSON requires the full structure, so we collect all data
        before writing. For true streaming, use JSONL fmt.
        """
        # Collect all data
        chunks = list(chunk_iterator)
        relationships = list(relationship_iterator)

        # Export normally
        self.export(chunks, relationships, output)

    def supports_format(self, fmt: ExportFormat) -> bool:
        """Check if this exporter supports a fmt."""
        return fmt == ExportFormat.JSON

    def get_schema(self) -> dict[str, Any]:
        """Get the export schema."""
        return {
            "fmt": "json",
            "version": "1.0",
            "indent": self.indent,
            "compress": self.compress,
            "structure": {
                "metadata": "Export metadata object",
                "chunks": "Array of chunk objects",
                "relationships": "Array of relationship objects",
            },
        }

    def _build_metadata(
        self,
        metadata: ExportMetadata | None,
        chunks: list[CodeChunk],
        relationships: list[ChunkRelationship],
    ) -> dict[str, Any]:
        """Build metadata object."""
        if metadata:
            return {
                "fmt": metadata.fmt.value,
                "version": metadata.version,
                "created_at": metadata.created_at,
                "source_files": metadata.source_files,
                "chunk_count": metadata.chunk_count,
                "relationship_count": metadata.relationship_count,
                "options": metadata.options,
            }
        # Generate basic metadata
        source_files = list({c.file_path for c in chunks})
        return {
            "fmt": "json",
            "version": "1.0",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_files": source_files,
            "chunk_count": len(chunks),
            "relationship_count": len(relationships),
            "options": {
                "indent": self.indent,
                "compress": self.compress,
            },
        }

    def _chunk_to_dict(self, chunk: CodeChunk) -> dict[str, Any]:
        """Convert chunk to dictionary."""
        return {
            "chunk_id": chunk.chunk_id,
            "language": chunk.language,
            "file_path": chunk.file_path,
            "node_type": chunk.node_type,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "byte_start": chunk.byte_start,
            "byte_end": chunk.byte_end,
            "parent_context": chunk.parent_context,
            "content": chunk.content,
            "parent_chunk_id": chunk.parent_chunk_id,
            "references": chunk.references,
            "dependencies": chunk.dependencies,
        }

    def _relationship_to_dict(self, rel: ChunkRelationship) -> dict[str, Any]:
        """Convert relationship to dictionary."""
        return {
            "source_chunk_id": rel.source_chunk_id,
            "target_chunk_id": rel.target_chunk_id,
            "relationship_type": rel.relationship_type.value,
            "metadata": rel.metadata or {},
        }


class StructuredJSONLExporter(StructuredExporter):
    """Export chunks and relationships to JSONL fmt with streaming support."""

    def __init__(self, compress: bool = False):
        """Initialize JSONL exporter.

        Args:
            compress: Whether to gzip compress the output
        """
        self.compress = compress

    def export(
        self,
        chunks: list[CodeChunk],
        relationships: list[ChunkRelationship],
        output: Path | io.IOBase,
        metadata: ExportMetadata | None = None,
    ) -> None:
        """Export chunks with relationships to JSONL.

        Args:
            chunks: List of code chunks
            relationships: List of chunk relationships
            output: Output path or stream
            metadata: Export metadata
        """
        if isinstance(output, str | Path):
            output_path = Path(output)
            if self.compress:
                with gzip.Path(f"{output_path}.gz").open("wt", encoding="utf-8") as f:
                    self._write_jsonl(chunks, relationships, f, metadata)
            else:
                with Path(output_path).open("w", encoding="utf-8") as f:
                    self._write_jsonl(chunks, relationships, f, metadata)
        else:
            self._write_jsonl(chunks, relationships, output, metadata)

    def export_streaming(
        self,
        chunk_iterator: Iterator[CodeChunk],
        relationship_iterator: Iterator[ChunkRelationship],
        output: Path | io.IOBase,
    ) -> None:
        """Export using iterators for large datasets."""
        if isinstance(output, str | Path):
            output_path = Path(output)
            if self.compress:
                with gzip.Path(f"{output_path}.gz").open("wt", encoding="utf-8") as f:
                    self._stream_jsonl(chunk_iterator, relationship_iterator, f)
            else:
                with Path(output_path).open("w", encoding="utf-8") as f:
                    self._stream_jsonl(chunk_iterator, relationship_iterator, f)
        else:
            self._stream_jsonl(chunk_iterator, relationship_iterator, output)

    def supports_format(self, fmt: ExportFormat) -> bool:
        """Check if this exporter supports a fmt."""
        return fmt == ExportFormat.JSONL

    def get_schema(self) -> dict[str, Any]:
        """Get the export schema."""
        return {
            "fmt": "jsonl",
            "version": "1.0",
            "compress": self.compress,
            "record_types": [
                {"type": "metadata", "description": "Export metadata"},
                {"type": "chunk", "description": "Code chunk data"},
                {"type": "relationship", "description": "Chunk relationship"},
            ],
        }

    def _write_jsonl(
        self,
        chunks: list[CodeChunk],
        relationships: list[ChunkRelationship],
        file_path: io.IOBase,
        metadata: ExportMetadata | None,
    ) -> None:
        """Write data as JSONL to file_path."""
        # Write metadata first
        if metadata:
            meta_record = {
                "type": "metadata",
                "data": {
                    "fmt": metadata.fmt.value,
                    "version": metadata.version,
                    "created_at": metadata.created_at,
                    "source_files": metadata.source_files,
                    "chunk_count": metadata.chunk_count,
                    "relationship_count": metadata.relationship_count,
                    "options": metadata.options,
                },
            }
        else:
            # Generate basic metadata
            source_files = list({c.file_path for c in chunks})
            meta_record = {
                "type": "metadata",
                "data": {
                    "fmt": "jsonl",
                    "version": "1.0",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "source_files": source_files,
                    "chunk_count": len(chunks),
                    "relationship_count": len(relationships),
                    "options": {"compress": self.compress},
                },
            }

        json.dump(meta_record, file_path, separators=(",", ":"))
        file_path.write("\n")

        # Write chunks
        for chunk in chunks:
            record = {
                "type": "chunk",
                "data": self._chunk_to_dict(chunk),
            }
            json.dump(record, file_path, separators=(",", ":"))
            file_path.write("\n")

        # Write relationships
        for rel in relationships:
            record = {
                "type": "relationship",
                "data": self._relationship_to_dict(rel),
            }
            json.dump(record, file_path, separators=(",", ":"))
            file_path.write("\n")

    def _stream_jsonl(
        self,
        chunk_iterator: Iterator[CodeChunk],
        relationship_iterator: Iterator[ChunkRelationship],
        file_path: io.IOBase,
    ) -> None:
        """Stream data as JSONL to file_path."""
        # Write metadata header
        meta_record = {
            "type": "metadata",
            "data": {
                "fmt": "jsonl",
                "version": "1.0",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "streaming": True,
                "options": {"compress": self.compress},
            },
        }
        json.dump(meta_record, file_path, separators=(",", ":"))
        file_path.write("\n")
        file_path.flush()

        # Stream chunks
        for chunk in chunk_iterator:
            record = {
                "type": "chunk",
                "data": self._chunk_to_dict(chunk),
            }
            json.dump(record, file_path, separators=(",", ":"))
            file_path.write("\n")
            file_path.flush()

        # Stream relationships
        for rel in relationship_iterator:
            record = {
                "type": "relationship",
                "data": self._relationship_to_dict(rel),
            }
            json.dump(record, file_path, separators=(",", ":"))
            file_path.write("\n")
            file_path.flush()

    def _chunk_to_dict(self, chunk: CodeChunk) -> dict[str, Any]:
        """Convert chunk to dictionary."""
        return {
            "chunk_id": chunk.chunk_id,
            "language": chunk.language,
            "file_path": chunk.file_path,
            "node_type": chunk.node_type,
            "start_line": chunk.start_line,
            "end_line": chunk.end_line,
            "byte_start": chunk.byte_start,
            "byte_end": chunk.byte_end,
            "parent_context": chunk.parent_context,
            "content": chunk.content,
            "parent_chunk_id": chunk.parent_chunk_id,
            "references": chunk.references,
            "dependencies": chunk.dependencies,
        }

    def _relationship_to_dict(self, rel: ChunkRelationship) -> dict[str, Any]:
        """Convert relationship to dictionary."""
        return {
            "source_chunk_id": rel.source_chunk_id,
            "target_chunk_id": rel.target_chunk_id,
            "relationship_type": rel.relationship_type.value,
            "metadata": rel.metadata or {},
        }
