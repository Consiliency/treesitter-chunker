"""Line-based fallback chunking strategy."""

import logging
import re

from chunker.fallback.base import FallbackChunker
from chunker.fallback.offsets import TextPositionIndex
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
        offsets = TextPositionIndex(content)
        if not lines:
            return []
        chunks = []
        header = None
        data_start = 0
        if include_header and lines:
            header = lines[0]
            data_start = 1
        lines_per_chunk = lines_per_chunk or self.config.chunk_size
        # Running CHAR cursor over the source so each chunk's byte span is
        # derived in O(1), not by re-summing every preceding line (was O(n^2)).
        char_cursor = sum(len(line) for line in lines[:data_start])
        for i in range(data_start, len(lines), lines_per_chunk):
            chunk_end = min(i + lines_per_chunk, len(lines))
            # Content is the CONTIGUOUS data-row slice only. The CSV header is
            # NOT prepended into content — doing so made content non-contiguous
            # so byte_start:byte_end (which covers the data rows) no longer
            # sliced back to content (README universal slice-back contract,
            # incl. fallback chunks). The header is preserved out-of-band in
            # metadata + parent_context so retrieval still has it.
            chunk_content = "".join(lines[i:chunk_end])
            start_line = i + 1
            end_line = chunk_end
            metadata: dict = {}
            parent_context = f"csv_rows_{start_line}_{end_line}"
            if include_header and header:
                metadata["csv_header"] = header.rstrip("\n")
                parent_context = (
                    f"csv_header={header.rstrip()};rows_{start_line}_{end_line}"
                )
            chunk = CodeChunk(
                language="csv",
                file_path=self.file_path or "",
                node_type="csv_chunk",
                start_line=start_line,
                end_line=end_line,
                byte_start=offsets.byte_offset(char_cursor),
                byte_end=offsets.byte_offset(char_cursor + len(chunk_content)),
                parent_context=parent_context,
                content=chunk_content,
                metadata=metadata,
            )
            chunks.append(chunk)
            char_cursor += len(chunk_content)
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
            pattern = re.compile(section_pattern, re.MULTILINE)
            return self.chunk_by_pattern(content, pattern, include_match=True)
        return self.chunk_by_lines(content, self.config.chunk_size, self.config.overlap)

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
        offsets = TextPositionIndex(content)
        chunks = []
        current_chunk = []
        current_bytes = 0
        current_start = 1
        for i, line in enumerate(lines):
            line_bytes = len(line.encode("utf-8"))
            would_exceed_bytes = current_bytes + line_bytes > target_bytes
            would_exceed_lines = len(current_chunk) >= max_lines
            if (
                current_chunk
                and len(current_chunk) >= min_lines
                and (would_exceed_bytes or would_exceed_lines)
            ):
                chunk_content = "".join(current_chunk)
                chunk = CodeChunk(
                    language=self._detect_language(),
                    file_path=self.file_path or "",
                    node_type="adaptive_chunk",
                    start_line=current_start,
                    end_line=current_start + len(current_chunk) - 1,
                    byte_start=offsets.byte_offset(
                        sum(len(line) for line in lines[: current_start - 1])
                    ),
                    byte_end=offsets.byte_offset(
                        sum(
                            len(line)
                            for line in lines[: current_start - 1 + len(current_chunk)]
                        )
                    ),
                    parent_context=f"adaptive_{current_start}",
                    content=chunk_content,
                )
                chunks.append(chunk)
                current_chunk = []
                current_bytes = 0
                current_start = i + 2
            current_chunk.append(line)
            current_bytes += line_bytes
        if current_chunk:
            chunk_content = "".join(current_chunk)
            chunk = CodeChunk(
                language=self._detect_language(),
                file_path=self.file_path or "",
                node_type="adaptive_chunk",
                start_line=current_start,
                end_line=len(lines),
                byte_start=offsets.byte_offset(
                    sum(len(line) for line in lines[: current_start - 1])
                ),
                byte_end=len(content.encode("utf-8")),
                parent_context=f"adaptive_{current_start}",
                content=chunk_content,
            )
            chunks.append(chunk)
        return chunks
