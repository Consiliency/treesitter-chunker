from __future__ import annotations

import hashlib
import mmap
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .parser import get_parser
from .types import CodeChunk, compute_node_id

if TYPE_CHECKING:
    from collections.abc import Iterator

    from tree_sitter import Node


@dataclass
class FileMetadata:
    path: str
    size: int
    hash: str
    mtime: float


def compute_file_hash(file_path: Path | str, chunk_size: int = 8192) -> str:
    """Compute SHA256 hash of a file.

    Args:
        file_path: Path to the file
        chunk_size: Size of chunks to read (default: 8192)
    """
    file_path = Path(file_path)
    hash_obj = hashlib.sha256()
    with file_path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hash_obj.update(chunk)
    return hash_obj.hexdigest()


def get_file_metadata(file_path: Path | str) -> FileMetadata:
    """Get metadata about a file."""
    file_path = Path(file_path)
    stat = file_path.stat()
    return FileMetadata(
        path=str(file_path),
        size=stat.st_size,
        hash=compute_file_hash(file_path),
        mtime=stat.st_mtime,
    )


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
        parent_chunk: CodeChunk | None = None,
        parent_route: list[str] | None = None,
    ) -> Iterator[CodeChunk]:
        """
        Yield chunks as they're found without building full list in memory.
        """
        chunk_types = {
            "function_definition",
            "class_definition",
            "method_definition",
        }

        parent_route = (parent_route or []).copy()

        if node.type in chunk_types:
            # Extract content from memory-mapped data
            text = mmap_data[node.start_byte : node.end_byte].decode(
                "utf-8",
                errors="replace",
            )
            current_route = [*parent_route, node.type]
            chunk = CodeChunk(
                language=self.language,
                file_path=file_path,
                node_type=node.type,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                byte_start=node.start_byte,
                byte_end=node.end_byte,
                parent_context=parent_ctx or "",
                content=text,
                parent_chunk_id=(parent_chunk.node_id if parent_chunk else None),
                parent_route=current_route,
            )
            # Ensure node_id reflects file path
            chunk.node_id = compute_node_id(
                file_path,
                chunk.language,
                chunk.parent_route,
                chunk.content,
            )
            yield chunk
            parent_ctx = node.type
            parent_chunk = chunk
            parent_route = current_route

        for child in node.children:
            yield from self._walk_streaming(
                child,
                mmap_data,
                file_path,
                parent_ctx,
                parent_chunk,
                parent_route,
            )

    def chunk_file_streaming(self, path: Path) -> Iterator[CodeChunk]:
        """Stream chunks from a file using memory-mapped I/O."""
        # Check if file is empty
        if path.stat().st_size == 0:
            return

        with (
            Path(path).open("rb") as f,
            mmap.mmap(
                f.fileno(),
                0,
                access=mmap.ACCESS_READ,
            ) as mmap_data,
        ):
            tree = self.parser.parse(mmap_data)
            root = tree.root_node
            yield from self._walk_streaming(
                root,
                mmap_data,
                str(path),
            )


def chunk_file_streaming(
    path: str | Path,
    language: str,
) -> Iterator[CodeChunk]:
    """Stream chunks from a file without loading everything into memory."""
    chunker = StreamingChunker(language)
    yield from chunker.chunk_file_streaming(Path(path))
