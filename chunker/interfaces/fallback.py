"""Fallback interfaces for non-AST chunking.

These interfaces are for files without Tree-sitter grammar support.
They should be used as a last resort - the primary goal is to have
Tree-sitter grammars for all file types.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from re import Pattern
from typing import Any

from chunker.types import CodeChunk

from .base import ChunkingStrategy


class FallbackReason(Enum):
    """Reasons for using fallback chunking."""

    NO_GRAMMAR = "no_grammar_available"
    GRAMMAR_ERROR = "grammar_error"
    BINARY_FILE = "binary_file"
    PARSE_FAILURE = "parse_failure"
    USER_REQUESTED = "user_requested"


class ChunkingMethod(Enum):
    """Fallback chunking methods."""

    LINE_BASED = "line_based"
    PARAGRAPH_BASED = "paragraph_based"
    REGEX_BASED = "regex_based"
    FIXED_SIZE = "fixed_size"
    DELIMITER_BASED = "delimiter_based"


@dataclass
class FallbackConfig:
    """Configuration for fallback chunking.

    Attributes:
        method: Chunking method to use
        chunk_size: Target chunk size (lines or characters)
        overlap: Overlap between chunks
        delimiter: Delimiter for delimiter-based chunking
        pattern: Regex pattern for pattern-based chunking
        min_chunk_size: Minimum chunk size to create
        max_chunk_size: Maximum chunk size allowed
    """

    method: ChunkingMethod
    chunk_size: int = 50
    overlap: int = 0
    delimiter: str | None = None
    pattern: Pattern | None = None
    min_chunk_size: int = 1
    max_chunk_size: int = 1000


class FallbackChunker(ChunkingStrategy):
    """Base interface for fallback chunking strategies.

    Important: This should emit warnings when used, encouraging
    users to request/contribute Tree-sitter grammar support.
    """

    @abstractmethod
    def set_fallback_reason(self, reason: FallbackReason) -> None:
        """Set the reason for using fallback.

        Args:
            reason: Why fallback is being used
        """

    @abstractmethod
    def chunk_by_lines(
        self,
        content: str,
        lines_per_chunk: int,
        overlap_lines: int = 0,
    ) -> list[CodeChunk]:
        """Chunk content by line count.

        Args:
            content: Text content to chunk
            lines_per_chunk: Number of lines per chunk
            overlap_lines: Lines to overlap between chunks

        Returns:
            List of chunks
        """

    @abstractmethod
    def chunk_by_delimiter(
        self,
        content: str,
        delimiter: str,
        include_delimiter: bool = True,
    ) -> list[CodeChunk]:
        """Chunk content by delimiter.

        Args:
            content: Text content to chunk
            delimiter: Delimiter to split on
            include_delimiter: Whether to include delimiter in chunks

        Returns:
            List of chunks
        """

    @abstractmethod
    def chunk_by_pattern(
        self,
        content: str,
        pattern: Pattern,
        include_match: bool = True,
    ) -> list[CodeChunk]:
        """Chunk content by regex pattern.

        Args:
            content: Text content to chunk
            pattern: Regex pattern to match chunk boundaries
            include_match: Whether to include matched text in chunks

        Returns:
            List of chunks
        """

    @abstractmethod
    def emit_warning(self) -> str:
        """Emit a warning about fallback usage.

        Returns:
            Warning message to display to user
        """


class FallbackStrategy(ABC):
    """Strategy for determining when to use fallback."""

    @abstractmethod
    def should_use_fallback(
        self,
        file_path: str,
        language: str | None = None,
    ) -> tuple[bool, FallbackReason]:
        """Determine if fallback should be used.

        Args:
            file_path: Path to file
            language: Language hint (if available)

        Returns:
            Tuple of (should_use_fallback, reason)
        """

    @abstractmethod
    def suggest_grammar(self, file_path: str) -> str | None:
        """Suggest a grammar that could handle this file.

        Args:
            file_path: Path to file

        Returns:
            Grammar repository URL or None
        """


class LogChunker(FallbackChunker):
    """Specialized chunker for log files."""

    @abstractmethod
    def chunk_by_timestamp(
        self,
        content: str,
        time_window_seconds: int,
    ) -> list[CodeChunk]:
        """Chunk logs by time window.

        Args:
            content: Log content
            time_window_seconds: Size of time window

        Returns:
            List of chunks grouped by time
        """

    @abstractmethod
    def chunk_by_severity(
        self,
        content: str,
        group_consecutive: bool = True,
    ) -> list[CodeChunk]:
        """Chunk logs by severity level.

        Args:
            content: Log content
            group_consecutive: Group consecutive same-severity entries

        Returns:
            List of chunks grouped by severity
        """


class MarkdownChunker(FallbackChunker):
    """Fallback chunker for Markdown without Tree-sitter.

    Note: Tree-sitter-markdown should be preferred when available.
    """

    @abstractmethod
    def chunk_by_headers(self, content: str, max_level: int = 3) -> list[CodeChunk]:
        """Chunk by header hierarchy.

        Args:
            content: Markdown content
            max_level: Maximum header level to chunk by

        Returns:
            List of chunks
        """

    @abstractmethod
    def chunk_by_sections(
        self,
        content: str,
        include_code_blocks: bool = True,
    ) -> list[CodeChunk]:
        """Chunk by logical sections.

        Args:
            content: Markdown content
            include_code_blocks: Whether to include code blocks

        Returns:
            List of chunks
        """


class BinaryFileHandler(ABC):
    """Handler for binary files (no chunking possible)."""

    @abstractmethod
    def extract_metadata(self, file_path: str) -> dict[str, Any]:
        """Extract metadata from binary file.

        Args:
            file_path: Path to binary file

        Returns:
            Metadata dictionary
        """

    @abstractmethod
    def create_placeholder_chunk(
        self,
        file_path: str,
        metadata: dict[str, Any],
    ) -> CodeChunk:
        """Create a placeholder chunk for binary file.

        Args:
            file_path: Path to binary file
            metadata: Extracted metadata

        Returns:
            Single chunk representing the file
        """


# Warning messages to encourage Tree-sitter usage
FALLBACK_WARNING_TEMPLATE = """
WARNING: Using fallback chunking for {file_path}
Reason: {reason}

Tree-sitter provides deterministic, AST-based chunking that preserves code structure.
Fallback methods may split code at inappropriate boundaries.

To improve chunking for this file type:
1. Check if a Tree-sitter grammar exists: {suggestion}
2. Request grammar support: https://github.com/tree-sitter
3. Use the 'more-grammars' feature to add support

Current fallback method: {method}
"""
