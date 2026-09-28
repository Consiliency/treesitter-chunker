"""Adapter to provide Chunker interface for repo processor."""

from chunker.core import chunk_text
from chunker.types import CodeChunk


class Chunker:
    """Adapter class to provide the expected Chunker interface."""

    @classmethod
    def chunk(
        cls, content: str, language: str, identity_path: str = ""
    ) -> list[CodeChunk]:
        """Chunk content using the caller's stable logical file path."""
        return chunk_text(content, language, file_path=identity_path)
