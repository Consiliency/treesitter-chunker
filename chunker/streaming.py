from __future__ import annotations

import mmap
from pathlib import Path
from typing import TYPE_CHECKING

from .parser import get_parser
from .types import CodeChunk

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tree_sitter import Node


class StreamingChunker:
    """Process large files using memory-mapped I/O for efficient streaming."""

    def __init__(self, language: str):
        self.language = language
        self.parser = get_parser(language)

    def _walk_streaming(
        self,
        node: Node,
        mmap_data: mmap.mmap,
        file_path: str,
        parent_ctx: str | None = None,
    ) -> Iterator[CodeChunk]:
        """Yield chunks as they're found without building full list in memory."""
        CHUNK_TYPES = {"function_definition", "class_definition", "method_definition"}

        if node.type in CHUNK_TYPES:
            # Extract content from memory-mapped data
            text = mmap_data[node.start_byte : node.end_byte].decode(
                "utf-8",
                errors="replace",
            )
            yield CodeChunk(
                language=self.language,
                file_path=file_path,
                node_type=node.type,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                byte_start=node.start_byte,
                byte_end=node.end_byte,
                parent_context=parent_ctx or "",
                content=text,
            )
            parent_ctx = node.type

        for child in node.children:
            yield from self._walk_streaming(child, mmap_data, file_path, parent_ctx)

    def chunk_file_streaming(self, path: Path) -> Iterator[CodeChunk]:
        """Stream chunks from a file using memory-mapped I/O."""
        # Check if file is empty
        if path.stat().st_size == 0:
            return

        with (
            Path(path).open(
                "rb",
            ) as f,
            mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mmap_data,
        ):
            tree = self.parser.parse(mmap_data)
            yield from self._walk_streaming(tree.root_node, mmap_data, str(path))


def chunk_file_streaming(path: str | Path, language: str) -> Iterator[CodeChunk]:
    """Stream chunks from a file without loading everything into memory."""
    chunker = StreamingChunker(language)
    yield from chunker.chunk_file_streaming(Path(path))
