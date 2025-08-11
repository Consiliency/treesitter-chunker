"""Base implementation for fallback chunking strategies."""

import logging
import warnings
from pathlib import Path
from re import Pattern
from typing import Any

from chunker.interfaces.fallback import (
    FALLBACK_WARNING_TEMPLATE,
    ChunkingMethod,
    FallbackConfig,
    FallbackReason,
)
from chunker.interfaces.fallback import FallbackChunker as IFallbackChunker
from chunker.types import CodeChunk

logger = logging.getLogger(__name__)


class FallbackWarning(UserWarning):
    """Warning issued when fallback chunking is used."""


class FallbackChunker(IFallbackChunker):
    """Base implementation for fallback chunking strategies.

    This class provides common functionality for all fallback chunkers
    and ensures warnings are properly emitted.
    """

    def __init__(self, config: FallbackConfig | None = None):
        """Initialize fallback chunker.

        Args:
            config: Configuration for fallback chunking
        """
        self.config = config or FallbackConfig(
            method=ChunkingMethod.LINE_BASED,
        )
        self.fallback_reason: FallbackReason | None = None
        self.file_path: str | None = None
        self._warning_emitted = False

    def set_fallback_reason(self, reason: FallbackReason) -> None:
        """Set the reason for using fallback.

        Args:
            reason: Why fallback is being used
        """
        self.fallback_reason = reason

    @staticmethod
    def can_handle(_file_path: str, _language: str) -> bool:
        """Check if this strategy can handle the given file.

        Fallback chunkers can handle any file type, but should only be used
        when Tree-sitter cannot parse the file.

        Args:
            file_path: Path to the file to chunk
            language: Language identifier

        Returns:
            True (fallback can handle any file)
        """
        return True

    def configure(self, config: dict[str, Any]) -> None:
        """Configure the chunking strategy.

        Args:
            config: Configuration dictionary
        """
        if "method" in config:
            self.config.method = ChunkingMethod(config["method"])
        if "chunk_size" in config:
            self.config.chunk_size = config["chunk_size"]
        if "overlap" in config:
            self.config.overlap = config["overlap"]
        if "delimiter" in config:
            self.config.delimiter = config["delimiter"]

    def chunk(
        self,
        _ast: Any,
        source: bytes,
        file_path: str,
        language: str,
    ) -> list[CodeChunk]:
        """Perform chunking - fallback version that works with text content.

        Since fallback chunking doesn't use AST, this method converts source
        to text and delegates to the text-based chunk method.

        Args:
            ast: Ignored for fallback chunking
            source: Source code as bytes
            file_path: Path to the source file
            language: Language identifier

        Returns:
            List of code chunks
        """
        try:
            content = source.decode("utf-8")
        except UnicodeDecodeError:
            content = source.decode("utf-8", errors="replace")
        return self.chunk_text(content, file_path, language)

    def chunk_text(
        self,
        content: str,
        file_path: str,
        _language: str | None = None,
    ) -> list[CodeChunk]:
        """Chunk content using fallback method.

        This method ensures warnings are emitted before chunking.

        Args:
            content: Content to chunk
            file_path: Path to the file
            language: Language hint (if available)

        Returns:
            List of chunks
        """
        self.file_path = file_path
        if not self._warning_emitted:
            warning_msg = self.emit_warning()
            warnings.warn(warning_msg, FallbackWarning, stacklevel=2)
            logger.warning(warning_msg)
            self._warning_emitted = True
        if self.config.method == ChunkingMethod.LINE_BASED:
            return self.chunk_by_lines(
                content,
                self.config.chunk_size,
                self.config.overlap,
            )
        if self.config.method == ChunkingMethod.DELIMITER_BASED:
            if not self.config.delimiter:
                raise ValueError("Delimiter required for delimiter-based chunking")
            return self.chunk_by_delimiter(content, self.config.delimiter)
        if self.config.method == ChunkingMethod.REGEX_BASED:
            if not self.config.pattern:
                # Graceful fallback to line-based when no pattern provided
                return self.chunk_by_lines(
                    content,
                    self.config.chunk_size,
                    self.config.overlap,
                )
            return self.chunk_by_pattern(
                content,
                self.config.pattern,
            )
        return self.chunk_by_lines(content, self.config.chunk_size)

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
        lines = content.splitlines(keepends=True)
        chunks = []
        i = 0
        while i < len(lines):
            start_idx = max(0, i - overlap_lines)
            end_idx = min(i + lines_per_chunk, len(lines))
            chunk_lines = lines[start_idx:end_idx]
            chunk_content = "".join(chunk_lines)
            byte_start = sum(len(line) for line in lines[:start_idx])
            byte_end = byte_start + len(chunk_content)
            chunk = CodeChunk(
                language=self._detect_language(),
                file_path=self.file_path or "",
                node_type="fallback_lines",
                start_line=start_idx + 1,
                end_line=end_idx,
                byte_start=byte_start,
                byte_end=byte_end,
                parent_context=f"lines_{start_idx + 1}_{end_idx}",
                content=chunk_content,
            )
            chunks.append(chunk)
            i += lines_per_chunk
        return chunks

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
        parts = content.split(delimiter)
        chunks = []
        current_byte = 0
        current_line = 1
        for i, part in enumerate(parts):
            if include_delimiter and i < len(parts) - 1:
                chunk_content = part + delimiter
            else:
                chunk_content = part
            if not chunk_content.strip():
                current_byte += len(chunk_content)
                current_line += chunk_content.count("\n")
                continue
            start_line = current_line
            end_line = start_line + chunk_content.count("\n")
            chunk = CodeChunk(
                language=self._detect_language(),
                file_path=self.file_path or "",
                node_type="fallback_delimiter",
                start_line=start_line,
                end_line=end_line,
                byte_start=current_byte,
                byte_end=current_byte + len(chunk_content),
                parent_context=f"delimiter_chunk_{i}",
                content=chunk_content,
            )
            chunks.append(chunk)
            current_byte += len(chunk_content)
            current_line = end_line + 1
        return chunks

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
        chunks = []
        last_end = 0
        current_line = 1
        for match in pattern.finditer(content):
            if match.start() > last_end:
                pre_content = content[last_end : match.start()]
                if pre_content.strip():
                    chunk = self._create_chunk_from_content(
                        pre_content,
                        last_end,
                        current_line,
                        "fallback_pattern_pre",
                    )
                    chunks.append(chunk)
                current_line += pre_content.count("\n")
            if include_match:
                match_content = match.group()
                if match_content.strip():
                    chunk = self._create_chunk_from_content(
                        match_content,
                        match.start(),
                        current_line,
                        "fallback_pattern_match",
                    )
                    chunks.append(chunk)
                current_line += match_content.count("\n")
            last_end = match.end()
        if last_end < len(content):
            remaining = content[last_end:]
            if remaining.strip():
                chunk = self._create_chunk_from_content(
                    remaining,
                    last_end,
                    current_line,
                    "fallback_pattern_post",
                )
                chunks.append(chunk)
        return chunks

    def emit_warning(self) -> str:
        """Emit a warning about fallback usage.

        Returns:
            Warning message to display to user
        """
        suggestion = self._get_grammar_suggestion()
        return FALLBACK_WARNING_TEMPLATE.format(
            file_path=self.file_path or "unknown",
            reason=self.fallback_reason.value if self.fallback_reason else "unknown",
            suggestion=suggestion,
            method=self.config.method.value,
        )

    def _detect_language(self) -> str:
        """Detect language from file path or return 'unknown'."""
        if not self.file_path:
            return "unknown"
        ext_map = {
            ".txt": "text",
            ".log": "log",
            ".md": "markdown",
            ".csv": "csv",
            ".json": "json",
            ".xml": "xml",
            ".yaml": "yaml",
            ".yml": "yaml",
            ".ini": "ini",
            ".cfg": "config",
            ".conf": "config",
        }
        ext = Path(self.file_path).suffix.lower()
        return ext_map.get(ext, "unknown")

    def _get_grammar_suggestion(self) -> str:
        """Get grammar suggestion based on file type."""
        lang = self._detect_language()
        suggestions = {
            "markdown": "https://github.com/tree-sitter-grammars/tree-sitter-markdown",
            "json": "https://github.com/tree-sitter/tree-sitter-json",
            "xml": "https://github.com/tree-sitter-grammars/tree-sitter-xml",
            "yaml": "https://github.com/tree-sitter-grammars/tree-sitter-yaml",
        }
        return suggestions.get(lang, "https://github.com/tree-sitter")

    def _create_chunk_from_content(
        self,
        content: str,
        byte_start: int,
        start_line: int,
        node_type: str,
    ) -> CodeChunk:
        """Helper to create a chunk from content."""
        line_count = content.count("\n")
        return CodeChunk(
            language=self._detect_language(),
            file_path=self.file_path or "",
            node_type=node_type,
            start_line=start_line,
            end_line=start_line + line_count,
            byte_start=byte_start,
            byte_end=byte_start + len(content),
            parent_context=f"{node_type}_{start_line}",
            content=content,
        )
