"""Streaming support for large file processing.

Streams ``CodeChunk`` objects from a file without materializing the full chunk
list. The lazy memory-mapped traversal yields each chunk as its node is visited
(so a >100MB file never holds all chunks in memory at once). Chunk *selection* —
which node types are chunkable — is delegated to the shared
``core.resolve_chunk_predicates`` so every language is chunked exactly as
non-streaming ``core.chunk_file`` would be. The module no longer hardcodes the
three Python node types (which silently yielded nothing for Rust/Go/JS/Java and
every other non-Python language).

Classes:
    StreamingChunker: Stream chunks from a file using memory-mapped I/O.
    FileMetadata: Metadata about a processed file.

Functions:
    chunk_file_streaming: Stream chunks from a file.
    compute_file_hash: Compute SHA256 hash of a file.
    get_file_metadata: Get metadata about a file.
"""

from __future__ import annotations

import hashlib
import mmap
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .core import (
    _build_retrieval_metadata,
    _extract_definition_name,
    resolve_chunk_predicates,
)
from .parser import get_parser
from .types import CodeChunk, compute_node_id

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator

    from tree_sitter import Node, Parser


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
    """Stream chunks from a file, yielding each as its node is visited.

    The former hand-rolled traversal hardcoded the three Python node types
    (``function_definition``/``class_definition``/``method_definition``), so
    streaming any other language silently yielded nothing. The traversal stays
    lazy (one chunk in flight at a time, memory-mapped source), but the
    chunkable-node PREDICATE is now derived per-language from
    ``core.resolve_chunk_predicates``. For mainstream languages
    (Python/Go/Rust/JS/TS/Java/C/C++/Ruby/C#) the selected node set matches
    non-streaming ``chunk_file`` exactly (spans + ids). Streaming does NOT yet
    replicate ``_walk``'s per-language span ADJUSTMENTS — Dart signature→body
    merge, R ``setClass`` force-chunk, Elixir ``call`` reinterpretation, Svelte
    control-flow — so for those four languages a streamed chunk's node_type/span
    (and therefore node_id) can differ from ``chunk_file``. This is a strict
    improvement over the prior silent-empty output and is tracked in
    ``docs/development/xfail-inventory.md`` (SCALE follow-up).
    """

    def __init__(self, language: str):
        self.language = language

    @property
    def parser(self) -> Parser:
        # Fetch the caller thread's own parser each access. get_parser() is
        # thread-local by construction (PARSER phase), so a StreamingChunker
        # instance shared across threads never hands one Parser to two threads.
        return get_parser(self.language)

    def _walk_streaming(
        self,
        node: Node,
        mmap_data: mmap.mmap | bytes,
        file_path: str,
        parent_ctx: str | None = None,
        parent_chunk: CodeChunk | None = None,
        parent_route: list[str] | None = None,
        parent_qualified_route: list[str] | None = None,
        include_retrieval_metadata: bool = False,
        should_chunk: Callable[[str], bool] | None = None,
    ) -> Iterator[CodeChunk]:
        """Yield chunks as they're found without building a full list in memory.

        ``mmap_data`` is the byte buffer ``node`` was parsed from (an ``mmap`` or
        a ``bytes`` object — ``vfs_chunker`` calls this directly as
        ``chunker._walk_streaming(root, content, path)``). ``should_chunk`` is
        the per-language predicate; it is resolved once at the top of the walk
        and threaded through the recursion so selection matches ``chunk_file``.
        """
        if should_chunk is None:
            should_chunk, _ = resolve_chunk_predicates(self.language)

        parent_route = (parent_route or []).copy()
        parent_qualified_route = (parent_qualified_route or []).copy()

        if should_chunk(node.type):
            # Extract content from the memory-mapped (or bytes) source.
            text = mmap_data[node.start_byte : node.end_byte].decode(
                "utf-8",
                errors="replace",
            )
            current_route = [*parent_route, node.type]
            start_line = node.start_point[0] + 1
            def_name = _extract_definition_name(node, mmap_data)
            if def_name:
                qualified_name = f"{node.type}:{def_name}"
            else:
                qualified_name = f"{node.type}:anon@{start_line}"
            current_qualified_route = [*parent_qualified_route, qualified_name]
            chunk = CodeChunk(
                language=self.language,
                file_path=file_path,
                node_type=node.type,
                start_line=start_line,
                end_line=node.end_point[0] + 1,
                byte_start=node.start_byte,
                byte_end=node.end_byte,
                parent_context=parent_ctx or "",
                content=text,
                parent_chunk_id=(parent_chunk.node_id if parent_chunk else None),
                parent_route=current_route,
                qualified_route=current_qualified_route,
            )
            # Ensure node_id reflects the real file path (streaming ids stay
            # byte-identical to chunk_file — the test_spans_roundtrip contract).
            chunk.node_id = compute_node_id(
                file_path,
                chunk.language,
                chunk.qualified_route or chunk.parent_route,
                chunk.byte_start,
                chunk.content,
            )
            chunk.chunk_id = chunk.node_id
            if include_retrieval_metadata:
                chunk.metadata = _build_retrieval_metadata(chunk)
            yield chunk
            # Pre-order: this chunk is the parent of its own descendants, so
            # parent links are resolved in a single pass (no second materialized
            # pass needed).
            parent_ctx = node.type
            parent_chunk = chunk
            parent_route = current_route
            parent_qualified_route = current_qualified_route

        for child in node.children:
            yield from self._walk_streaming(
                child,
                mmap_data,
                file_path,
                parent_ctx,
                parent_chunk,
                parent_route,
                parent_qualified_route,
                include_retrieval_metadata,
                should_chunk,
            )

    def chunk_file_streaming(
        self,
        path: Path,
        include_retrieval_metadata: bool = False,
    ) -> Iterator[CodeChunk]:
        """Stream chunks from a file using memory-mapped I/O.

        Unknown/unsupported languages raise ``LanguageNotFoundError`` (from the
        thread-local ``get_parser`` via ``self.parser``) — an explicit error,
        never a silent empty result.
        """
        # Check if file is empty
        if path.stat().st_size == 0:
            return

        should_chunk, _ = resolve_chunk_predicates(self.language)
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
                include_retrieval_metadata=include_retrieval_metadata,
                should_chunk=should_chunk,
            )


def chunk_file_streaming(
    path: str | Path,
    language: str,
    include_retrieval_metadata: bool = False,
) -> Iterator[CodeChunk]:
    """Stream chunks from a file without loading everything into memory."""
    chunker = StreamingChunker(language)
    yield from chunker.chunk_file_streaming(
        Path(path),
        include_retrieval_metadata=include_retrieval_metadata,
    )
