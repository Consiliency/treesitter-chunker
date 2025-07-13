from __future__ import annotations
import hashlib
import mmap
from pathlib import Path
from typing import Iterator, Optional
from dataclasses import dataclass
from tree_sitter import Node, Parser

from .parser import get_parser
from .types import CodeChunk

@dataclass
class FileMetadata:
    path: Path
    size: int
    hash: str
    mtime: float

def compute_file_hash(file_path: Path, chunk_size: int = 8192) -> str:
    """Compute SHA256 hash of a file efficiently."""
    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        while chunk := f.read(chunk_size):
            hasher.update(chunk)
    return hasher.hexdigest()

def get_file_metadata(path: Path) -> FileMetadata:
    """Get file metadata including size, hash, and modification time."""
    stat = path.stat()
    return FileMetadata(
        path=path,
        size=stat.st_size,
        hash=compute_file_hash(path),
        mtime=stat.st_mtime
    )

class StreamingChunker:
    """Process large files using memory-mapped I/O for efficient streaming."""
    
    def __init__(self, language: str):
        self.language = language
        self.parser = get_parser(language)
    
    def _walk_streaming(self, node: Node, mmap_data: mmap.mmap, 
                       file_path: str, parent_ctx: str | None = None) -> Iterator[CodeChunk]:
        """Yield chunks as they're found without building full list in memory."""
        CHUNK_TYPES = {"function_definition", "class_definition", "method_definition"}
        
        if node.type in CHUNK_TYPES:
            # Extract content from memory-mapped data
            text = mmap_data[node.start_byte:node.end_byte].decode('utf-8', errors='replace')
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
        with open(path, 'rb') as f:
            # Memory-map the file for efficient access
            with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as mmap_data:
                tree = self.parser.parse(mmap_data[:])
                yield from self._walk_streaming(tree.root_node, mmap_data, str(path))

def chunk_file_streaming(path: str | Path, language: str) -> Iterator[CodeChunk]:
    """Stream chunks from a file without loading everything into memory."""
    chunker = StreamingChunker(language)
    yield from chunker.chunk_file_streaming(Path(path))