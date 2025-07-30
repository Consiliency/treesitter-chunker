"""Chunker integration with Virtual File System support."""

from __future__ import annotations
from .types import CodeChunk
from collections.abc import Iterator
import fnmatch

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from .chunker import chunk_text
from .gc_tuning import get_memory_optimizer, optimized_gc
from .streaming import StreamingChunker
from .vfs import (
    HTTPFileSystem,
    LocalFileSystem,
    VirtualFileSystem,
    ZipFileSystem,
    create_vfs,
)

if TYPE_CHECKING:


logger = logging.getLogger(__name__)


class VFSChunker:
    """Chunker with Virtual File System support."""

    def __init__(self, vfs: VirtualFileSystem | None = None):
        """Initialize VFS chunker.

        Args:
            vfs: Virtual file system to use (defaults to LocalFileSystem)
        """
        self.vfs = vfs or LocalFileSystem()
        self._chunkers = {}  # Cache chunkers by language
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

        # Auto-detect language if not specified
        if language is None:
            language = self._detect_language(path)
            if not language:
                raise ValueError(f"Could not detect language for: {path}")

        # Get or create chunker for language
        if streaming and language not in self._chunkers:
            self._chunkers[language] = StreamingChunker(language)

        # Get file size for optimization decisions
        file_size = self.vfs.get_size(path)

        # Use streaming for large files
        if streaming or file_size > 10 * 1024 * 1024:  # 10MB
            if language not in self._chunkers:
                self._chunkers[language] = StreamingChunker(language)
            return self._chunk_file_streaming(path, language, self._chunkers[language])
        return self._chunk_file_standard(path, language)

    def _chunk_file_standard(self, path: str, language: str) -> list[CodeChunk]:
        """Standard chunking for smaller files."""
        # Read file content
        content = self.vfs.read_text(path)

        # Use optimized GC for processing
        with optimized_gc("batch"):
            # Process with standard chunker
            return chunk_text(content, file_path=path, language=language)

    def _chunk_file_streaming(
        self,
        path: str,
        _language: str,
        chunker: StreamingChunker,
    ) -> Iterator[CodeChunk]:
        """Streaming chunking for large files."""
        # For streaming from VFS, we need to adapt the approach
        # since we can't use mmap directly on VFS files

        with optimized_gc("streaming"), self.vfs.Path(path).open("rb") as f:
            # Read in chunks and process
            chunk_size = 1024 * 1024  # 1MB chunks
            content_buffer = b""

            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break

                content_buffer += chunk

                # Try to parse when we have enough content
                if len(content_buffer) > chunk_size * 2:
                    # Parse accumulated content
                    tree = chunker.parser.parse(content_buffer)

                    # Extract chunks from parsed tree
                    for code_chunk in chunker._walk_streaming(
                        tree.root_node,
                        content_buffer,
                        path,
                    ):
                        yield code_chunk

                    # Keep last chunk for context
                    content_buffer = content_buffer[-chunk_size:]

            # Process remaining content
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

        # Collect files to process
        files_to_process = []
        for vf in self._walk_directory(directory, recursive):
            if vf.is_dir:
                continue

            # Check file patterns
            if file_patterns and not any(
                self._match_pattern(vf.path, pattern) for pattern in file_patterns
            ):
                continue

            # Skip if language cannot be detected
            if self._detect_language(vf.path):
                files_to_process.append(vf.path)

        # Optimize GC for batch processing
        self._memory_optimizer.optimize_for_file_processing(len(files_to_process))

        # Process files
        for batch in self._memory_optimizer.memory_efficient_batch(files_to_process):
            for file_path in batch:
                try:
                    chunks = self.chunk_file(file_path, streaming=streaming)
                    if streaming:
                        # Convert iterator to list for consistency
                        chunks = list(chunks)
                    yield (file_path, chunks)
                except (FileNotFoundError, OSError) as e:
                    logger.error("Error processing %s: %s", file_path, e)
                    continue

    def _walk_directory(self, directory: str, recursive: bool) -> Iterator:
        """Walk directory tree in VFS."""
        for vf in self.vfs.list_dir(directory):
            yield vf
            if recursive and vf.is_dir:
                yield from self._walk_directory(vf.path, recursive)

    def _detect_language(self, path: str) -> str | None:
        """Detect language from file path/extension."""
        path_obj = Path(path)
        ext = path_obj.suffix.lower()

        # Language mapping
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

        # Check if it's a Dockerfile without extension
        if path_obj.name.lower() in ["dockerfile", "containerfile"]:
            return "dockerfile"

        return language_map.get(ext)

    def _match_pattern(self, path: str, pattern: str) -> bool:
        """Check if path matches a pattern."""

        return fnmatch.fnmatch(path, pattern)


# Convenience functions
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
