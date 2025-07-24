"""JSON and JSONL export functionality with streaming support."""

import gzip
import json
from pathlib import Path
from typing import IO

from ..chunker import CodeChunk
from .formatters import SchemaType, get_formatter


class JSONExporter:
    """Export chunks to JSON format with customizable schemas."""

    def __init__(self, schema_type: SchemaType = SchemaType.FLAT):
        self.formatter = get_formatter(schema_type)

    def export(
        self,
        chunks: list[CodeChunk],
        output: str | Path | IO[str],
        compress: bool = False,
        indent: int | None = 2,
    ) -> None:
        """Export chunks to JSON format.

        Args:
            chunks: List of code chunks to export
            output: Output file path or file-like object
            compress: Whether to gzip compress the output
            indent: JSON indentation (None for compact)
        """
        formatted_data = self.formatter.format(chunks)
        json_str = json.dumps(formatted_data, indent=indent)

        if isinstance(output, (str, Path)):
            output_path = Path(output)
            if compress:
                with gzip.open(f"{output_path}.gz", "wt", encoding="utf-8") as f:
                    f.write(json_str)
            else:
                output_path.write_text(json_str, encoding="utf-8")
        else:
            output.write(json_str)

    def export_to_string(self, chunks: list[CodeChunk], indent: int | None = 2) -> str:
        """Export chunks to JSON string."""
        formatted_data = self.formatter.format(chunks)
        return json.dumps(formatted_data, indent=indent)


class JSONLExporter:
    """Export chunks to JSONL (JSON Lines) format with streaming support."""

    def __init__(self, schema_type: SchemaType = SchemaType.FLAT):
        self.formatter = get_formatter(schema_type)

    def export(
        self,
        chunks: list[CodeChunk],
        output: str | Path | IO[str],
        compress: bool = False,
    ) -> None:
        """Export chunks to JSONL format.

        Args:
            chunks: List of code chunks to export
            output: Output file path or file-like object
            compress: Whether to gzip compress the output
        """
        if isinstance(output, (str, Path)):
            output_path = Path(output)
            if compress:
                with gzip.open(f"{output_path}.gz", "wt", encoding="utf-8") as f:
                    self._write_jsonl(chunks, f)
            else:
                with open(output_path, "w", encoding="utf-8") as f:
                    self._write_jsonl(chunks, f)
        else:
            self._write_jsonl(chunks, output)

    def _write_jsonl(self, chunks: list[CodeChunk], file: IO[str]) -> None:
        """Write chunks as JSONL to file."""
        formatted_data = self.formatter.format(chunks)

        # Handle different formatter outputs
        if isinstance(formatted_data, list):
            for item in formatted_data:
                json.dump(item, file, separators=(",", ":"))
                file.write("\n")
        elif isinstance(formatted_data, dict):
            # For full formatter, write metadata first, then chunks
            if "metadata" in formatted_data:
                json.dump(
                    {"type": "metadata", "data": formatted_data["metadata"]},
                    file,
                )
                file.write("\n")

            if "chunks" in formatted_data:
                for chunk in formatted_data["chunks"]:
                    json.dump({"type": "chunk", "data": chunk}, file)
                    file.write("\n")

            if "relationships" in formatted_data:
                json.dump(
                    {"type": "relationships", "data": formatted_data["relationships"]},
                    file,
                )
                file.write("\n")
        else:
            # Single item
            json.dump(formatted_data, file)
            file.write("\n")

    def stream_export(
        self,
        chunks_generator,
        output: str | Path | IO[str],
        compress: bool = False,
    ) -> None:
        """Stream export chunks to JSONL format without loading all in memory.

        Args:
            chunks_generator: Generator or iterator yielding CodeChunk objects
            output: Output file path or file-like object
            compress: Whether to gzip compress the output
        """
        if isinstance(output, (str, Path)):
            output_path = Path(output)
            if compress:
                with gzip.open(f"{output_path}.gz", "wt", encoding="utf-8") as f:
                    self._stream_write_jsonl(chunks_generator, f)
            else:
                with open(output_path, "w", encoding="utf-8") as f:
                    self._stream_write_jsonl(chunks_generator, f)
        else:
            self._stream_write_jsonl(chunks_generator, output)

    def _stream_write_jsonl(self, chunks_generator, file: IO[str]) -> None:
        """Stream write chunks as JSONL to file."""
        for chunk in chunks_generator:
            # Format single chunk
            if hasattr(self.formatter, "_chunk_to_dict"):
                chunk_dict = self.formatter._chunk_to_dict(chunk)
            else:
                # Fallback for formatters without _chunk_to_dict
                formatted = self.formatter.format([chunk])
                chunk_dict = formatted[0] if isinstance(formatted, list) else formatted

            json.dump(chunk_dict, file, separators=(",", ":"))
            file.write("\n")
            file.flush()  # Ensure immediate write for streaming
