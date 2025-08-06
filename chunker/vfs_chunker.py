"""Chunker integration with Virtual File System support."""

from __future__ import annotations

import fnmatch
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from ._internal.gc_tuning import get_memory_optimizer, optimized_gc
from .chunker import chunk_text
from .streaming import StreamingChunker
from .vfs import (
    HTTPFileSystem,
    LocalFileSystem,
    VirtualFileSystem,
    ZipFileSystem,
    create_vfs,
)

if TYPE_CHECKING:
    from collections.abc import Iterator

    from .types import CodeChunk
logger = logging.getLogger(__name__)


class VFSChunker:
    """Chunker with Virtual File System support."""

    def __init__(self, vfs: VirtualFileSystem | None = None):
        """Initialize VFS chunker.

        Args:
            vfs: Virtual file system to use (defaults to LocalFileSystem)
        """
        self.vfs = vfs or LocalFileSystem()
        self._chunkers = {}
        self._memory_optimizer = get_memory_optimizer()

    def chunk_file(
        self,
        path: str,
        language: str | None = None,
        streaming: bool = False,
    ) -> list[CodeChunk] | Iterator[CodeChunk]:
        """Chunk a file from the virtual file system.

        Args:
            path: Path to file in the VFS
            language: Programming language (auto-detected if not specified)
            streaming: Whether to use streaming for large files

        Returns:
            List of chunks or iterator if streaming
        """
        if not self.vfs.exists(path):
            raise FileNotFoundError(f"File not found in VFS: {path}")
        if not self.vfs.is_file(path):
            raise ValueError(f"Path is not a file: {path}")
        if language is None:
            language = self._detect_language(path)
            if not language:
                raise ValueError(f"Could not detect language for: {path}")
        if streaming and language not in self._chunkers:
            self._chunkers[language] = StreamingChunker(language)
        file_size = self.vfs.get_size(path)
        if streaming or file_size > 10 * 1024 * 1024:
            if language not in self._chunkers:
                self._chunkers[language] = StreamingChunker(language)
            return self._chunk_file_streaming(path, language, self._chunkers[language])
        return self._chunk_file_standard(path, language)

    def _chunk_file_standard(self, path: str, language: str) -> list[CodeChunk]:
        """Standard chunking for smaller files."""
        content = self.vfs.read_text(path)
        with optimized_gc("batch"):
            return chunk_text(content, file_path=path, language=language)

    def _chunk_file_streaming(
        self,
        path: str,
        _language: str,
        chunker: StreamingChunker,
    ) -> Iterator[CodeChunk]:
        """Streaming chunking for large files."""
        with optimized_gc("streaming"), self.vfs.Path(path).open("rb") as f:
            chunk_size = 1024 * 1024
            content_buffer = b""
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                content_buffer += chunk
                if len(content_buffer) > chunk_size * 2:
                    tree = chunker.parser.parse(content_buffer)
                    for code_chunk in chunker._walk_streaming(
                        tree.root_node,
                        content_buffer,
                        path,
                    ):
                        yield code_chunk
                    content_buffer = content_buffer[-chunk_size:]
            if content_buffer:
                tree = chunker.parser.parse(content_buffer)
                for code_chunk in chunker._walk_streaming(
                    tree.root_node,
                    content_buffer,
                    path,
                ):
                    yield code_chunk

    def chunk_directory(
        self,
        directory: str,
        recursive: bool = True,
        file_patterns: list[str] | None = None,
        streaming: bool = False,
    ) -> Iterator[tuple[str, list[CodeChunk]]]:
        """Chunk all files in a directory.

        Args:
            directory: Directory path in VFS
            recursive: Whether to process subdirectories
            file_patterns: File patterns to include (e.g., ['*.py', '*.js'])
            streaming: Whether to use streaming for large files

        Yields:
            Tuples of (file_path, chunks)
        """
        if not self.vfs.is_dir(directory):
            raise ValueError(f"Path is not a directory: {directory}")
        files_to_process = []
        for vf in self._walk_directory(directory, recursive):
            if vf.is_dir:
                continue
            if file_patterns and not any(
                self._match_pattern(vf.path, pattern) for pattern in file_patterns
            ):
                continue
            if self._detect_language(vf.path):
                files_to_process.append(vf.path)
        self._memory_optimizer.optimize_for_file_processing(len(files_to_process))
        for batch in self._memory_optimizer.memory_efficient_batch(files_to_process):
            for file_path in batch:
                result = self._process_file_safe(file_path, streaming)
                if result is not None:
                    yield file_path, result

    def _process_file_safe(self, file_path: str, streaming: bool) -> list | None:
        """Process a file safely, returning None on error."""
        try:
            chunks = self.chunk_file(file_path, streaming=streaming)
            if streaming:
                chunks = list(chunks)
            return chunks
        except (FileNotFoundError, OSError) as e:
            logger.error("Error processing %s: %s", file_path, e)
            return None

    def _walk_directory(self, directory: str, recursive: bool) -> Iterator:
        """Walk directory tree in VFS."""
        for vf in self.vfs.list_dir(directory):
            yield vf
            if recursive and vf.is_dir:
                yield from self._walk_directory(vf.path, recursive)

    @classmethod
    def _detect_language(cls, path: str) -> str | None:
        """Detect language from file path/extension."""
        path_obj = Path(path)
        ext = path_obj.suffix.lower()
        language_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".c": "c",
            ".h": "c",
            ".cpp": "cpp",
            ".cc": "cpp",
            ".cxx": "cpp",
            ".hpp": "cpp",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
            ".rb": "ruby",
            ".php": "php",
            ".cs": "csharp",
            ".swift": "swift",
            ".kt": "kotlin",
            ".scala": "scala",
            ".r": "r",
            ".lua": "lua",
            ".dart": "dart",
            ".jl": "julia",
            ".ex": "elixir",
            ".exs": "elixir",
            ".clj": "clojure",
            ".hs": "haskell",
            ".ml": "ocaml",
            ".vim": "vim",
            ".sh": "bash",
            ".bash": "bash",
            ".zsh": "bash",
            ".fish": "bash",
            ".ps1": "powershell",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".toml": "toml",
            ".json": "json",
            ".xml": "xml",
            ".html": "html",
            ".htm": "html",
            ".css": "css",
            ".scss": "scss",
            ".sass": "sass",
            ".less": "less",
            ".sql": "sql",
            ".graphql": "graphql",
            ".proto": "protobuf",
            ".tf": "hcl",
            ".hcl": "hcl",
            ".dockerfile": "dockerfile",
            ".containerfile": "dockerfile",
        }
        if path_obj.name.lower() in {"dockerfile", "containerfile"}:
            return "dockerfile"
        return language_map.get(ext)

    @staticmethod
    def _match_pattern(path: str, pattern: str) -> bool:
        """Check if path matches a pattern."""
        return fnmatch.fnmatch(path, pattern)


def chunk_file_from_vfs(
    path: str,
    vfs: VirtualFileSystem | None = None,
    language: str | None = None,
    streaming: bool = False,
) -> list[CodeChunk] | Iterator[CodeChunk]:
    """Chunk a file from a virtual file system.

    Args:
        path: Path to file
        vfs: Virtual file system (auto-created based on path if not provided)
        language: Programming language (auto-detected if not specified)
        streaming: Whether to use streaming for large files

    Returns:
        List of chunks or iterator if streaming
    """
    if vfs is None:
        vfs = create_vfs(path)
    chunker = VFSChunker(vfs)
    return chunker.chunk_file(path, language, streaming)


def chunk_from_url(
    url: str,
    language: str | None = None,
    streaming: bool = False,
) -> list[CodeChunk] | Iterator[CodeChunk]:
    """Chunk a file from a URL.

    Args:
        url: URL to file
        language: Programming language (auto-detected if not specified)
        streaming: Whether to use streaming

    Returns:
        List of chunks or iterator if streaming
    """
    vfs = HTTPFileSystem(url)
    chunker = VFSChunker(vfs)
    return chunker.chunk_file(url, language, streaming)


def chunk_from_zip(
    zip_path: str,
    file_path: str,
    language: str | None = None,
    streaming: bool = False,
) -> list[CodeChunk] | Iterator[CodeChunk]:
    """Chunk a file from a ZIP archive.

    Args:
        zip_path: Path to ZIP file
        file_path: Path to file within ZIP
        language: Programming language (auto-detected if not specified)
        streaming: Whether to use streaming

    Returns:
        List of chunks or iterator if streaming
    """
    with ZipFileSystem(zip_path) as vfs:
        chunker = VFSChunker(vfs)
        return chunker.chunk_file(file_path, language, streaming)
