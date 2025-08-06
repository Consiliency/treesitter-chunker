"""Adapter to provide Chunker interface for repo processor."""

import tempfile
from pathlib import Path

from chunker.core import chunk_file
from chunker.types import CodeChunk


class Chunker:
    """Adapter class to provide the expected Chunker interface."""

    @classmethod
    def chunk(cls, content: str, language: str) -> list[CodeChunk]:
        """Chunk content by writing to temp file and using chunk_file."""
        with tempfile.NamedTemporaryFile(
            encoding="utf-8",
            mode="w",
            suffix=f".{language}",
            delete=False,
        ) as tf:
            tf.write(content)
            temp_path = Path(tf.name)
        try:
            chunks = chunk_file(temp_path, language)
            return chunks
        finally:
            temp_path.unlink(missing_ok=True)
