"""Overlapping chunks implementation for fallback (non-Tree-sitter) files."""

import re
from dataclasses import dataclass
from typing import Literal

from chunker.interfaces.fallback_overlap import (
    OverlappingFallbackChunker as IOverlappingFallbackChunker,
)
from chunker.interfaces.fallback_overlap import OverlapStrategy
from chunker.types import CodeChunk

__all__ = ["OverlapConfig", "OverlapStrategy", "OverlappingFallbackChunker"]


@dataclass
class OverlapConfig:
    """Configuration for overlapping chunks."""

    chunk_size: int = 1000
    overlap_size: int = 200
    strategy: OverlapStrategy = OverlapStrategy.FIXED
    unit: Literal["lines", "characters"] = "characters"
    # For asymmetric overlap
    overlap_before: int | None = None
    overlap_after: int | None = None
    # For dynamic overlap
    min_overlap: int = 50
    max_overlap: int = 300


class OverlappingFallbackChunker(IOverlappingFallbackChunker):
    """
    Overlapping chunk implementation for fallback files.

    This chunker adds overlapping support to maintain context between chunks
    for files that don't have Tree-sitter support (text, markdown, logs, etc).
    """

    def __init__(self, config: OverlapConfig | None = None):
        """Initialize with overlap configuration."""
        super().__init__()
        self.overlap_config = config or OverlapConfig()

    def chunk_with_overlap(
        self,
        content: str,
        file_path: str,
        chunk_size: int = 1000,
        overlap_size: int = 200,
        strategy: OverlapStrategy = OverlapStrategy.FIXED,
        unit: Literal["lines", "characters"] = "characters",
    ) -> list[CodeChunk]:
        """
        Chunk content with overlapping windows.

        This method creates chunks that share content at their boundaries,
        helping maintain context when processing large files.
        """
        self.file_path = file_path

        if unit == "lines":
            return self._chunk_by_lines_with_overlap(
                content,
                chunk_size,
                overlap_size,
                strategy,
            )
        # characters
        return self._chunk_by_chars_with_overlap(
            content,
            chunk_size,
            overlap_size,
            strategy,
        )

    def chunk_with_asymmetric_overlap(
        self,
        content: str,
        file_path: str,
        chunk_size: int = 1000,
        overlap_before: int = 100,
        overlap_after: int = 200,
        unit: Literal["lines", "characters"] = "characters",
    ) -> list[CodeChunk]:
        """
        Chunk with different overlap sizes before and after.

        This is useful when forward context is more important than backward context,
        such as in log files or streaming data.
        """
        self.file_path = file_path

        if unit == "lines":
            return self._chunk_by_lines_asymmetric(
                content,
                chunk_size,
                overlap_before,
                overlap_after,
            )
        # characters
        return self._chunk_by_chars_asymmetric(
            content,
            chunk_size,
            overlap_before,
            overlap_after,
        )

    def chunk_with_dynamic_overlap(
        self,
        content: str,
        file_path: str,
        chunk_size: int = 1000,
        min_overlap: int = 50,
        max_overlap: int = 300,
        unit: Literal["lines", "characters"] = "characters",
    ) -> list[CodeChunk]:
        """
        Chunk with dynamically adjusted overlap based on content.

        This method looks for natural boundaries (paragraphs, sections) to
        determine optimal overlap sizes within the given constraints.
        """
        self.file_path = file_path

        if unit == "lines":
            return self._chunk_by_lines_dynamic(
                content,
                chunk_size,
                min_overlap,
                max_overlap,
            )
        # characters
        return self._chunk_by_chars_dynamic(
            content,
            chunk_size,
            min_overlap,
            max_overlap,
        )

    def find_natural_overlap_boundary(
        self,
        content: str,
        desired_position: int,
        search_window: int = 100,
    ) -> int:
        """
        Find a natural boundary for overlap near desired position.

        Looks for paragraph breaks, sentence ends, or other natural boundaries
        within the search window around the desired position.
        """
        # Define boundary patterns in order of preference
        boundary_patterns = [
            (r"\n\n+", "paragraph"),  # Paragraph break
            (r"\.\s+", "sentence"),  # Sentence end
            (r"[;:]\s+", "clause"),  # Clause boundary
            (r",\s+", "comma"),  # Comma
            (r"\n", "line"),  # Line break
            (r"\s+", "word"),  # Word boundary
        ]

        start = max(0, desired_position - search_window // 2)
        end = min(len(content), desired_position + search_window // 2)
        window_content = content[start:end]
        window_offset = start

        best_position = desired_position
        best_score = float("inf")

        for pattern, boundary_type in boundary_patterns:
            for match in re.finditer(pattern, window_content):
                # Position after the boundary
                pos = window_offset + match.end()
                distance = abs(pos - desired_position)

                # Score based on distance and boundary type preference
                # Lower index in patterns list = better boundary type
                type_score = boundary_patterns.index((pattern, boundary_type))
                score = distance + (type_score * 10)  # Weight boundary type

                if score < best_score:
                    best_score = score
                    best_position = pos

        return best_position

    def _chunk_by_lines_with_overlap(
        self,
        content: str,
        chunk_size: int,
        overlap_size: int,
        strategy: OverlapStrategy,
    ) -> list[CodeChunk]:
        """Chunk by lines with overlap."""
        lines = content.splitlines(keepends=True)
        chunks = []

        if strategy == OverlapStrategy.PERCENTAGE:
            overlap_size = int(chunk_size * (overlap_size / 100.0))

        i = 0
        chunk_num = 0

        while i < len(lines):
            # For first chunk, no backward overlap
            if i == 0:
                start_idx = 0
            else:
                # Include overlap from previous chunk
                start_idx = max(0, i - overlap_size)

            # End of chunk
            end_idx = min(i + chunk_size, len(lines))

            # For dynamic strategy, adjust overlap at boundaries
            if strategy == OverlapStrategy.DYNAMIC and i > 0:
                # Find natural boundary for start
                desired_line = start_idx
                start_idx = self._find_natural_line_boundary(
                    lines,
                    desired_line,
                    overlap_size // 2,
                )

            # Create chunk
            chunk_lines = lines[start_idx:end_idx]
            chunk_content = "".join(chunk_lines)

            # Calculate byte positions
            byte_start = sum(len(line) for line in lines[:start_idx])
            byte_end = byte_start + len(chunk_content)

            chunk = CodeChunk(
                language=self._detect_language(),
                file_path=self.file_path or "",
                node_type="fallback_overlap_lines",
                start_line=start_idx + 1,
                end_line=end_idx,
                byte_start=byte_start,
                byte_end=byte_end,
                parent_context=f"overlap_chunk_{chunk_num}",
                content=chunk_content,
            )
            chunks.append(chunk)

            # Move forward by chunk_size (not considering overlap)
            i += chunk_size
            chunk_num += 1

        return chunks

    def _chunk_by_chars_with_overlap(
        self,
        content: str,
        chunk_size: int,
        overlap_size: int,
        strategy: OverlapStrategy,
    ) -> list[CodeChunk]:
        """Chunk by characters with overlap."""
        chunks = []

        if strategy == OverlapStrategy.PERCENTAGE:
            overlap_size = int(chunk_size * (overlap_size / 100.0))

        i = 0
        chunk_num = 0

        while i < len(content):
            # Calculate start with overlap
            if i == 0:
                start = 0
            else:
                start = max(0, i - overlap_size)

            # Calculate end
            end = min(i + chunk_size, len(content))

            # For dynamic strategy, find natural boundaries
            if strategy == OverlapStrategy.DYNAMIC:
                if i > 0:
                    start = self.find_natural_overlap_boundary(
                        content,
                        start,
                        overlap_size // 2,
                    )
                if end < len(content):
                    end = self.find_natural_overlap_boundary(
                        content,
                        end,
                        overlap_size // 2,
                    )

            chunk_content = content[start:end]

            # Calculate line numbers
            start_line = content[:start].count("\n") + 1
            end_line = content[:end].count("\n") + 1

            chunk = CodeChunk(
                language=self._detect_language(),
                file_path=self.file_path or "",
                node_type="fallback_overlap_chars",
                start_line=start_line,
                end_line=end_line,
                byte_start=start,
                byte_end=end,
                parent_context=f"overlap_chunk_{chunk_num}",
                content=chunk_content,
            )
            chunks.append(chunk)

            # Move forward by chunk_size
            i += chunk_size
            chunk_num += 1

        return chunks

    def _chunk_by_lines_asymmetric(
        self,
        content: str,
        chunk_size: int,
        overlap_before: int,
        overlap_after: int,
    ) -> list[CodeChunk]:
        """Chunk by lines with asymmetric overlap."""
        lines = content.splitlines(keepends=True)
        chunks = []

        i = 0
        chunk_num = 0

        while i < len(lines):
            # Calculate start with backward overlap
            if i == 0:
                start_idx = 0
            else:
                start_idx = max(0, i - overlap_before)

            # Calculate end with forward overlap for next chunk
            # Current chunk extends beyond its base size to provide context for next
            if i + chunk_size < len(lines):
                end_idx = min(i + chunk_size + overlap_after, len(lines))
            else:
                end_idx = len(lines)

            # Create chunk
            chunk_lines = lines[start_idx:end_idx]
            chunk_content = "".join(chunk_lines)

            # Calculate byte positions
            byte_start = sum(len(line) for line in lines[:start_idx])
            byte_end = byte_start + len(chunk_content)

            chunk = CodeChunk(
                language=self._detect_language(),
                file_path=self.file_path or "",
                node_type="fallback_asymmetric_lines",
                start_line=start_idx + 1,
                end_line=end_idx,
                byte_start=byte_start,
                byte_end=byte_end,
                parent_context=f"asymmetric_chunk_{chunk_num}",
                content=chunk_content,
            )
            chunks.append(chunk)

            # Move forward by chunk_size
            i += chunk_size
            chunk_num += 1

        return chunks

    def _chunk_by_chars_asymmetric(
        self,
        content: str,
        chunk_size: int,
        overlap_before: int,
        overlap_after: int,
    ) -> list[CodeChunk]:
        """Chunk by characters with asymmetric overlap."""
        chunks = []

        i = 0
        chunk_num = 0

        while i < len(content):
            # Calculate start with backward overlap
            if i == 0:
                start = 0
            else:
                start = max(0, i - overlap_before)

            # Calculate end with forward overlap
            if i + chunk_size < len(content):
                end = min(i + chunk_size + overlap_after, len(content))
            else:
                end = len(content)

            chunk_content = content[start:end]

            # Calculate line numbers
            start_line = content[:start].count("\n") + 1
            end_line = content[:end].count("\n") + 1

            chunk = CodeChunk(
                language=self._detect_language(),
                file_path=self.file_path or "",
                node_type="fallback_asymmetric_chars",
                start_line=start_line,
                end_line=end_line,
                byte_start=start,
                byte_end=end,
                parent_context=f"asymmetric_chunk_{chunk_num}",
                content=chunk_content,
            )
            chunks.append(chunk)

            # Move forward by chunk_size
            i += chunk_size
            chunk_num += 1

        return chunks

    def _chunk_by_lines_dynamic(
        self,
        content: str,
        chunk_size: int,
        min_overlap: int,
        max_overlap: int,
    ) -> list[CodeChunk]:
        """Chunk by lines with dynamic overlap based on content."""
        lines = content.splitlines(keepends=True)
        chunks = []

        i = 0
        chunk_num = 0

        while i < len(lines):
            if i == 0:
                start_idx = 0
            else:
                # Calculate dynamic overlap based on content
                overlap = self._calculate_dynamic_overlap_lines(
                    lines,
                    i,
                    min_overlap,
                    max_overlap,
                )
                start_idx = max(0, i - overlap)

            end_idx = min(i + chunk_size, len(lines))

            # Create chunk
            chunk_lines = lines[start_idx:end_idx]
            chunk_content = "".join(chunk_lines)

            # Calculate byte positions
            byte_start = sum(len(line) for line in lines[:start_idx])
            byte_end = byte_start + len(chunk_content)

            chunk = CodeChunk(
                language=self._detect_language(),
                file_path=self.file_path or "",
                node_type="fallback_dynamic_lines",
                start_line=start_idx + 1,
                end_line=end_idx,
                byte_start=byte_start,
                byte_end=byte_end,
                parent_context=f"dynamic_chunk_{chunk_num}",
                content=chunk_content,
            )
            chunks.append(chunk)

            i += chunk_size
            chunk_num += 1

        return chunks

    def _chunk_by_chars_dynamic(
        self,
        content: str,
        chunk_size: int,
        min_overlap: int,
        max_overlap: int,
    ) -> list[CodeChunk]:
        """Chunk by characters with dynamic overlap based on content."""
        chunks = []

        i = 0
        chunk_num = 0

        while i < len(content):
            if i == 0:
                start = 0
            else:
                # Calculate dynamic overlap
                overlap = self._calculate_dynamic_overlap_chars(
                    content,
                    i,
                    min_overlap,
                    max_overlap,
                )
                desired_start = i - overlap
                # Find natural boundary
                start = self.find_natural_overlap_boundary(
                    content,
                    desired_start,
                    overlap // 2,
                )
                start = max(0, start)

            end = min(i + chunk_size, len(content))

            chunk_content = content[start:end]

            # Calculate line numbers
            start_line = content[:start].count("\n") + 1
            end_line = content[:end].count("\n") + 1

            chunk = CodeChunk(
                language=self._detect_language(),
                file_path=self.file_path or "",
                node_type="fallback_dynamic_chars",
                start_line=start_line,
                end_line=end_line,
                byte_start=start,
                byte_end=end,
                parent_context=f"dynamic_chunk_{chunk_num}",
                content=chunk_content,
            )
            chunks.append(chunk)

            i += chunk_size
            chunk_num += 1

        return chunks

    def _find_natural_line_boundary(
        self,
        lines: list[str],
        desired_line: int,
        search_window: int,
    ) -> int:
        """Find a natural boundary in lines (empty lines, headers, etc)."""
        start = max(0, desired_line - search_window)
        end = min(len(lines), desired_line + search_window)

        best_line = desired_line
        best_score = float("inf")

        for i in range(start, end):
            line = lines[i].strip() if i < len(lines) else ""

            # Score based on line characteristics
            score = abs(i - desired_line)  # Distance penalty

            # Prefer empty lines
            if not line:
                score -= 10
            # Prefer markdown headers
            elif line.startswith("#"):
                score -= 8
            # Prefer lines that look like section breaks
            elif all(c in "-=" for c in line) and len(line) > 3:
                score -= 6
            # Prefer lines starting with numbers (lists)
            elif re.match(r"^\d+\.", line):
                score -= 4

            if score < best_score:
                best_score = score
                best_line = i

        return best_line

    def _calculate_dynamic_overlap_lines(
        self,
        lines: list[str],
        position: int,
        min_overlap: int,
        max_overlap: int,
    ) -> int:
        """Calculate dynamic overlap size based on content density."""
        # Look at the previous chunk area
        look_back = min(position, 50)
        recent_lines = lines[max(0, position - look_back) : position]

        # Calculate content density metrics
        empty_lines = sum(1 for line in recent_lines if not line.strip())

        # Higher density = more overlap needed
        density_ratio = 1.0 - (empty_lines / len(recent_lines)) if recent_lines else 0.5

        # Scale overlap based on density
        overlap = int(min_overlap + (max_overlap - min_overlap) * density_ratio)

        return overlap

    def _calculate_dynamic_overlap_chars(
        self,
        content: str,
        position: int,
        min_overlap: int,
        max_overlap: int,
    ) -> int:
        """Calculate dynamic overlap size based on content characteristics."""
        # Look at the previous content
        look_back = min(position, 1000)
        recent_content = content[max(0, position - look_back) : position]

        # Calculate metrics
        paragraph_breaks = recent_content.count("\n\n")
        sentence_ends = len(re.findall(r"[.!?]\s+", recent_content))

        # More structure = less overlap needed
        structure_score = (
            (paragraph_breaks * 2 + sentence_ends) / (len(recent_content) / 100.0)
            if recent_content
            else 1.0
        )

        # Inverse relationship: more structure = less overlap
        overlap_ratio = max(0, 1.0 - (structure_score / 10.0))

        overlap = int(min_overlap + (max_overlap - min_overlap) * overlap_ratio)

        return overlap
