"""Line-based fallback chunking strategy."""

import logging

from chunker.fallback.base import FallbackChunker
from chunker.interfaces.fallback import ChunkingMethod, FallbackConfig
from chunker.types import CodeChunk

logger = logging.getLogger(__name__)


class LineBasedChunker(FallbackChunker):
    """Simple line-based chunking for text files.

    This is the most basic fallback strategy, suitable for:
    - Plain text files
    - Configuration files
    - CSV files
    - Any text file without structure
    """

    def __init__(self, lines_per_chunk: int = 50, overlap: int = 5):
        """Initialize line-based chunker.

        Args:
            lines_per_chunk: Number of lines per chunk
            overlap: Number of lines to overlap between chunks
        """
        config = FallbackConfig(
            method=ChunkingMethod.LINE_BASED,
            chunk_size=lines_per_chunk,
            overlap=overlap,
        )
        super().__init__(config)

    def chunk_csv(
        self,
        content: str,
        include_header: bool = True,
        lines_per_chunk: int | None = None,
    ) -> list[CodeChunk]:
        """Special handling for CSV files.

        Args:
            content: CSV content
            include_header: Include header in each chunk
            lines_per_chunk: Override default lines per chunk

        Returns:
            List of chunks
        """
        lines = content.splitlines(keepends=True)
        if not lines:
            return []

        chunks = []
        header = None
        data_start = 0

        # Extract header if requested
        if include_header and lines:
            # Assume first line is header
            header = lines[0]
            data_start = 1

        lines_per_chunk = lines_per_chunk or self.config.chunk_size

        # Chunk the data rows
        for i in range(data_start, len(lines), lines_per_chunk):
            chunk_lines = []

            # Add header to each chunk (except the first which already has it)
            if include_header and header and i > data_start:
                chunk_lines.append(header)

            # Add data lines
            chunk_end = min(i + lines_per_chunk, len(lines))
            chunk_lines.extend(lines[i:chunk_end])

            # Create chunk
            chunk_content = "".join(chunk_lines)

            # Calculate positions
            # Note: line numbers should reflect actual file lines
            start_line = i + 1  # Convert 0-based to 1-based
            end_line = chunk_end

            chunk = CodeChunk(
                language="csv",
                file_path=self.file_path or "",
                node_type="csv_chunk",
                start_line=start_line,
                end_line=end_line,
                byte_start=sum(len(line) for line in lines[:i]),
                byte_end=sum(len(line) for line in lines[:chunk_end]),
                parent_context=f"csv_rows_{start_line}_{end_line}",
                content=chunk_content,
            )
            chunks.append(chunk)

        return chunks

    def chunk_config(
        self,
        content: str,
        section_pattern: str | None = None,
    ) -> list[CodeChunk]:
        """Special handling for config files.

        Args:
            content: Config file content
            section_pattern: Regex pattern for section headers

        Returns:
            List of chunks
        """
        if section_pattern:
            # Use pattern-based chunking for sections
            import re

            pattern = re.compile(section_pattern, re.MULTILINE)
            return self.chunk_by_pattern(content, pattern, include_match=True)
        # Fall back to regular line-based chunking
        return self.chunk_by_lines(
            content,
            self.config.chunk_size,
            self.config.overlap,
        )

    def adaptive_chunk(
        self,
        content: str,
        min_lines: int = 10,
        max_lines: int = 100,
        target_bytes: int = 4096,
    ) -> list[CodeChunk]:
        """Adaptively chunk based on content density.

        This method adjusts chunk size based on the content,
        useful for files with varying line lengths.

        Args:
            content: Content to chunk
            min_lines: Minimum lines per chunk
            max_lines: Maximum lines per chunk
            target_bytes: Target bytes per chunk

        Returns:
            List of chunks
        """
        lines = content.splitlines(keepends=True)
        chunks = []

        current_chunk = []
        current_bytes = 0
        current_start = 1

        for i, line in enumerate(lines):
            line_bytes = len(line.encode("utf-8"))

            # Check if adding this line would exceed limits
            would_exceed_bytes = current_bytes + line_bytes > target_bytes
            would_exceed_lines = len(current_chunk) >= max_lines

            # Create chunk if we hit limits (but respect minimum)
            if (
                current_chunk
                and len(current_chunk) >= min_lines
                and (would_exceed_bytes or would_exceed_lines)
            ):
                # Create chunk
                chunk_content = "".join(current_chunk)
                chunk = CodeChunk(
                    language=self._detect_language(),
                    file_path=self.file_path or "",
                    node_type="adaptive_chunk",
                    start_line=current_start,
                    end_line=current_start + len(current_chunk) - 1,
                    byte_start=sum(len(l) for l in lines[: current_start - 1]),
                    byte_end=sum(
                        len(l) for l in lines[: current_start - 1 + len(current_chunk)]
                    ),
                    parent_context=f"adaptive_{current_start}",
                    content=chunk_content,
                )
                chunks.append(chunk)

                # Reset for next chunk
                current_chunk = []
                current_bytes = 0
                current_start = i + 2  # Next line number (1-indexed)

            # Add line to current chunk
            current_chunk.append(line)
            current_bytes += line_bytes

        # Handle remaining lines
        if current_chunk:
            chunk_content = "".join(current_chunk)
            chunk = CodeChunk(
                language=self._detect_language(),
                file_path=self.file_path or "",
                node_type="adaptive_chunk",
                start_line=current_start,
                end_line=len(lines),
                byte_start=sum(len(l) for l in lines[: current_start - 1]),
                byte_end=len(content),
                parent_context=f"adaptive_{current_start}",
                content=chunk_content,
            )
            chunks.append(chunk)

        return chunks
