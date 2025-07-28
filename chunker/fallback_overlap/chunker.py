"""Implementation of overlapping fallback chunker for non-Tree-sitter files only."""

import logging
import re
import warnings
from typing import Literal

from ..exceptions import ChunkerError
from ..fallback.base import FallbackWarning
from ..interfaces.fallback_overlap import (
    OverlappingFallbackChunker as IOverlappingFallbackChunker,
)
from ..interfaces.fallback_overlap import (
    OverlapStrategy,
)
from ..parser import list_languages
from ..types import CodeChunk

logger = logging.getLogger(__name__)


class TreeSitterOverlapError(ChunkerError):
    """Raised when overlapping is requested for a Tree-sitter supported language."""

    def __init__(self, language: str):
        super().__init__(
            f"Overlapping chunks requested for '{language}' which has Tree-sitter support. "
            f"Overlapping is ONLY for files without Tree-sitter parsers.",
        )
        self.language = language


class OverlappingFallbackChunker(IOverlappingFallbackChunker):
    """
    Overlapping fallback chunker for non-Tree-sitter files.

    This chunker adds overlapping support to fallback chunking strategies.
    It is specifically designed for text files, logs, and other content
    that doesn't have Tree-sitter grammar support.

    CRITICAL: This chunker will raise an error if used on files with
    Tree-sitter support. Use standard chunking for code files.
    """

    def __init__(self, *args, **kwargs):
        """Initialize overlapping fallback chunker."""
        super().__init__(*args, **kwargs)
        self._supported_languages: list[str] | None = None

    def _check_no_treesitter_support(self, file_path: str, language: str | None = None):
        """Ensure the file/language has NO Tree-sitter support.

        Args:
            file_path: Path to the file
            language: Language identifier (if provided)

        Raises:
            TreeSitterOverlapError: If Tree-sitter support exists
        """
        # Cache supported languages
        if self._supported_languages is None:
            self._supported_languages = list_languages()

        # Check if language is explicitly supported
        if language and language.lower() in self._supported_languages:
            raise TreeSitterOverlapError(language)

        # Infer language from file extension
        import os

        ext = os.path.splitext(file_path)[1].lower()

        # Map common extensions to Tree-sitter language names
        # These are the languages currently supported in the build
        ext_to_lang = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "javascript",
            ".tsx": "javascript",
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
            ".kt": "kotlin",
            ".cs": "c_sharp",
        }

        inferred_lang = ext_to_lang.get(ext)
        if inferred_lang and inferred_lang in self._supported_languages:
            raise TreeSitterOverlapError(inferred_lang)

    def chunk_with_overlap(
        self,
        content: str,
        file_path: str,
        chunk_size: int = 1000,
        overlap_size: int = 200,
        strategy: OverlapStrategy = OverlapStrategy.FIXED,
        unit: Literal["lines", "characters"] = "characters",
        language: str | None = None,
    ) -> list[CodeChunk]:
        """
        Chunk content with overlapping windows.

        This is ONLY for fallback files without Tree-sitter support.

        Args:
            content: Text content to chunk
            file_path: Path to source file
            chunk_size: Size of each chunk (lines or characters)
            overlap_size: Size of overlap (lines or characters)
            strategy: How to calculate overlap
            unit: Whether sizes are in lines or characters
            language: Optional language hint (will fail if has Tree-sitter support)

        Returns:
            List of overlapping chunks

        Raises:
            TreeSitterOverlapError: If file has Tree-sitter support
        """
        # Check that this file doesn't have Tree-sitter support
        self._check_no_treesitter_support(file_path, language)

        # Store file path for warning emissions
        self.file_path = file_path

        # Log warning about overlapping usage
        warning_msg = (
            f"Using overlapping fallback chunker for {file_path}. "
            f"This file has no Tree-sitter support. "
            f"Overlap strategy: {strategy.value}, size: {overlap_size} {unit}"
        )
        warnings.warn(warning_msg, FallbackWarning, stacklevel=2)
        logger.warning(warning_msg)

        # Calculate actual overlap based on strategy
        actual_overlap = self._calculate_overlap(chunk_size, overlap_size, strategy)

        if unit == "lines":
            return self._chunk_by_lines_with_overlap(
                content,
                chunk_size,
                actual_overlap,
            )
        return self._chunk_by_characters_with_overlap(
            content,
            chunk_size,
            actual_overlap,
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

        Useful when context before is less important than context after.

        Args:
            content: Text content to chunk
            file_path: Path to source file
            chunk_size: Size of each chunk
            overlap_before: Overlap size with previous chunk
            overlap_after: Overlap size with next chunk
            unit: Whether sizes are in lines or characters

        Returns:
            List of overlapping chunks
        """
        # Check that this file doesn't have Tree-sitter support
        self._check_no_treesitter_support(file_path)

        self.file_path = file_path

        warning_msg = (
            f"Using asymmetric overlapping fallback chunker for {file_path}. "
            f"Overlap before: {overlap_before}, after: {overlap_after} {unit}"
        )
        warnings.warn(warning_msg, FallbackWarning, stacklevel=2)
        logger.warning(warning_msg)

        if unit == "lines":
            return self._chunk_by_lines_asymmetric(
                content,
                chunk_size,
                overlap_before,
                overlap_after,
            )
        return self._chunk_by_characters_asymmetric(
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

        Adjusts overlap size based on natural boundaries (paragraphs, sections).

        Args:
            content: Text content to chunk
            file_path: Path to source file
            chunk_size: Size of each chunk
            min_overlap: Minimum overlap size
            max_overlap: Maximum overlap size
            unit: Whether sizes are in lines or characters

        Returns:
            List of overlapping chunks
        """
        # Check that this file doesn't have Tree-sitter support
        self._check_no_treesitter_support(file_path)

        self.file_path = file_path

        warning_msg = (
            f"Using dynamic overlapping fallback chunker for {file_path}. "
            f"Overlap range: {min_overlap}-{max_overlap} {unit}"
        )
        warnings.warn(warning_msg, FallbackWarning, stacklevel=2)
        logger.warning(warning_msg)

        if unit == "lines":
            return self._chunk_by_lines_dynamic(
                content,
                chunk_size,
                min_overlap,
                max_overlap,
            )
        return self._chunk_by_characters_dynamic(
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

        Looks for paragraph breaks, sentence ends, etc.

        Args:
            content: Text content
            desired_position: Where we want the overlap
            search_window: How far to search for natural boundary

        Returns:
            Best position for overlap boundary
        """
        # Ensure position is within bounds
        if desired_position <= 0:
            return 0
        if desired_position >= len(content):
            return len(content)

        # Define natural boundary patterns (in order of preference)
        boundary_patterns = [
            (r"\n\n+", "paragraph"),  # Paragraph breaks
            (r"\n", "line"),  # Line breaks
            (r"[.!?]\s+", "sentence"),  # Sentence ends
            (r"[,;:]\s+", "clause"),  # Clause boundaries
            (r"\s+", "word"),  # Word boundaries
        ]

        best_position = desired_position
        best_score = float("inf")

        # Search within window
        start = max(0, desired_position - search_window // 2)
        end = min(len(content), desired_position + search_window // 2)
        search_text = content[start:end]

        for pattern, boundary_type in boundary_patterns:
            for match in re.finditer(pattern, search_text):
                # Calculate absolute position
                abs_pos = start + match.end()
                distance = abs(abs_pos - desired_position)

                # Score based on distance and boundary type preference
                # Lower score is better
                type_weight = boundary_patterns.index((pattern, boundary_type))
                score = distance + (type_weight * 10)

                if score < best_score:
                    best_score = score
                    best_position = abs_pos

        return best_position

    def _calculate_overlap(
        self,
        chunk_size: int,
        overlap_size: int,
        strategy: OverlapStrategy,
    ) -> int:
        """Calculate actual overlap size based on strategy."""
        if strategy == OverlapStrategy.FIXED:
            return overlap_size
        if strategy == OverlapStrategy.PERCENTAGE:
            # overlap_size is treated as percentage (0-100)
            return int(chunk_size * (overlap_size / 100.0))
        # For dynamic/asymmetric, return as-is (handled elsewhere)
        return overlap_size

    def _chunk_by_lines_with_overlap(
        self,
        content: str,
        lines_per_chunk: int,
        overlap_lines: int,
    ) -> list[CodeChunk]:
        """Chunk by lines with overlap."""
        lines = content.splitlines(keepends=True)
        chunks = []

        # Calculate step size (how much to advance for each chunk)
        step_size = lines_per_chunk - overlap_lines
        if step_size <= 0:
            step_size = 1  # Ensure we always advance

        chunk_num = 0
        i = 0

        while i < len(lines):
            # Calculate chunk boundaries
            start_idx = i
            end_idx = min(i + lines_per_chunk, len(lines))

            # Get chunk content
            chunk_lines = lines[start_idx:end_idx]
            chunk_content = "".join(chunk_lines)

            # Calculate byte positions
            byte_start = sum(len(line) for line in lines[:start_idx])
            byte_end = byte_start + len(chunk_content)

            # Create chunk
            chunk = CodeChunk(
                language=self._detect_language(),
                file_path=self.file_path or "",
                node_type="fallback_overlapping_lines",
                start_line=start_idx + 1,
                end_line=end_idx,
                byte_start=byte_start,
                byte_end=byte_end,
                parent_context=f"overlapping_chunk_{chunk_num}",
                content=chunk_content,
            )
            chunks.append(chunk)

            # Move to next chunk position
            i += step_size
            chunk_num += 1

            # Stop if we've processed all lines
            if i >= len(lines):
                break

        return chunks

    def _chunk_by_characters_with_overlap(
        self,
        content: str,
        chars_per_chunk: int,
        overlap_chars: int,
    ) -> list[CodeChunk]:
        """Chunk by characters with overlap."""
        chunks = []

        # Calculate step size (how much to advance for each chunk)
        step_size = chars_per_chunk - overlap_chars
        if step_size <= 0:
            step_size = 1  # Ensure we always advance

        chunk_num = 0
        i = 0

        while i < len(content):
            # Calculate chunk boundaries
            start_idx = i
            end_idx = min(i + chars_per_chunk, len(content))

            # Get chunk content
            chunk_content = content[start_idx:end_idx]

            # Calculate line numbers
            start_line = content[:start_idx].count("\n") + 1
            end_line = content[:end_idx].count("\n") + 1

            # Create chunk
            chunk = CodeChunk(
                language=self._detect_language(),
                file_path=self.file_path or "",
                node_type="fallback_overlapping_chars",
                start_line=start_line,
                end_line=end_line,
                byte_start=start_idx,
                byte_end=end_idx,
                parent_context=f"overlapping_chunk_{chunk_num}",
                content=chunk_content,
            )
            chunks.append(chunk)

            # Move to next chunk position
            i += step_size
            chunk_num += 1

            # Stop if we've processed all content
            if i >= len(content):
                break

        return chunks

    def _chunk_by_lines_asymmetric(
        self,
        content: str,
        lines_per_chunk: int,
        overlap_before: int,
        overlap_after: int,
    ) -> list[CodeChunk]:
        """Chunk by lines with asymmetric overlap."""
        lines = content.splitlines(keepends=True)
        chunks = []

        i = 0
        chunk_num = 0

        while i < len(lines):
            # Calculate base chunk boundaries
            start_idx = i
            end_idx = min(i + lines_per_chunk, len(lines))

            # Add overlap from previous chunk
            if i > 0 and overlap_before > 0:
                overlap_start = max(0, i - overlap_before)
            else:
                overlap_start = start_idx

            # Add overlap for next chunk
            if end_idx < len(lines) and overlap_after > 0:
                overlap_end = min(end_idx + overlap_after, len(lines))
            else:
                overlap_end = end_idx

            chunk_lines = lines[overlap_start:overlap_end]
            chunk_content = "".join(chunk_lines)

            # Calculate byte positions
            byte_start = sum(len(line) for line in lines[:overlap_start])
            byte_end = byte_start + len(chunk_content)

            # Create chunk
            chunk = CodeChunk(
                language=self._detect_language(),
                file_path=self.file_path or "",
                node_type="fallback_asymmetric_lines",
                start_line=overlap_start + 1,
                end_line=overlap_end,
                byte_start=byte_start,
                byte_end=byte_end,
                parent_context=f"asymmetric_chunk_{chunk_num}",
                content=chunk_content,
            )
            chunks.append(chunk)

            # Move to next chunk
            i = end_idx
            chunk_num += 1

        return chunks

    def _chunk_by_characters_asymmetric(
        self,
        content: str,
        chars_per_chunk: int,
        overlap_before: int,
        overlap_after: int,
    ) -> list[CodeChunk]:
        """Chunk by characters with asymmetric overlap."""
        chunks = []
        i = 0
        chunk_num = 0

        while i < len(content):
            # Calculate base chunk boundaries
            start_idx = i
            end_idx = min(i + chars_per_chunk, len(content))

            # Add overlap from previous chunk
            if i > 0 and overlap_before > 0:
                overlap_start = max(0, i - overlap_before)
            else:
                overlap_start = start_idx

            # Add overlap for next chunk
            if end_idx < len(content) and overlap_after > 0:
                overlap_end = min(end_idx + overlap_after, len(content))
            else:
                overlap_end = end_idx

            chunk_content = content[overlap_start:overlap_end]

            # Calculate line numbers
            start_line = content[:overlap_start].count("\n") + 1
            end_line = content[:overlap_end].count("\n") + 1

            # Create chunk
            chunk = CodeChunk(
                language=self._detect_language(),
                file_path=self.file_path or "",
                node_type="fallback_asymmetric_chars",
                start_line=start_line,
                end_line=end_line,
                byte_start=overlap_start,
                byte_end=overlap_end,
                parent_context=f"asymmetric_chunk_{chunk_num}",
                content=chunk_content,
            )
            chunks.append(chunk)

            # Move to next chunk
            i = end_idx
            chunk_num += 1

        return chunks

    def _chunk_by_lines_dynamic(
        self,
        content: str,
        lines_per_chunk: int,
        min_overlap: int,
        max_overlap: int,
    ) -> list[CodeChunk]:
        """Chunk by lines with dynamic overlap based on content."""
        lines = content.splitlines(keepends=True)
        chunks = []

        i = 0
        chunk_num = 0

        while i < len(lines):
            # Calculate chunk boundaries
            start_idx = i
            end_idx = min(i + lines_per_chunk, len(lines))

            # Determine dynamic overlap for this chunk
            if i > 0:
                # Find natural boundary for overlap
                desired_overlap_lines = (min_overlap + max_overlap) // 2
                overlap_pos = max(0, i - desired_overlap_lines)

                # Look for natural boundary
                boundary_content = "".join(lines[overlap_pos:i])
                natural_pos = self.find_natural_overlap_boundary(
                    boundary_content,
                    len(boundary_content) // 2,
                )

                # Convert back to line index
                lines_before = boundary_content[:natural_pos].count("\n")
                actual_overlap_lines = min(max_overlap, max(min_overlap, lines_before))
                overlap_start = max(0, i - actual_overlap_lines)
            else:
                overlap_start = start_idx

            chunk_lines = lines[overlap_start:end_idx]
            chunk_content = "".join(chunk_lines)

            # Calculate byte positions
            byte_start = sum(len(line) for line in lines[:overlap_start])
            byte_end = byte_start + len(chunk_content)

            # Create chunk
            chunk = CodeChunk(
                language=self._detect_language(),
                file_path=self.file_path or "",
                node_type="fallback_dynamic_lines",
                start_line=overlap_start + 1,
                end_line=end_idx,
                byte_start=byte_start,
                byte_end=byte_end,
                parent_context=f"dynamic_chunk_{chunk_num}",
                content=chunk_content,
            )
            chunks.append(chunk)

            # Move to next chunk
            i = end_idx
            chunk_num += 1

        return chunks

    def _chunk_by_characters_dynamic(
        self,
        content: str,
        chars_per_chunk: int,
        min_overlap: int,
        max_overlap: int,
    ) -> list[CodeChunk]:
        """Chunk by characters with dynamic overlap based on content."""
        chunks = []
        i = 0
        chunk_num = 0

        while i < len(content):
            # Calculate chunk boundaries
            start_idx = i
            end_idx = min(i + chars_per_chunk, len(content))

            # Determine dynamic overlap for this chunk
            if i > 0:
                # Find natural boundary for overlap
                desired_overlap = (min_overlap + max_overlap) // 2
                desired_pos = max(0, i - desired_overlap)

                # Find best natural boundary
                natural_pos = self.find_natural_overlap_boundary(
                    content,
                    desired_pos,
                    max_overlap - min_overlap,
                )

                # Ensure within min/max bounds
                actual_overlap = i - natural_pos
                if actual_overlap < min_overlap:
                    overlap_start = max(0, i - min_overlap)
                elif actual_overlap > max_overlap:
                    overlap_start = max(0, i - max_overlap)
                else:
                    overlap_start = natural_pos
            else:
                overlap_start = start_idx

            chunk_content = content[overlap_start:end_idx]

            # Calculate line numbers
            start_line = content[:overlap_start].count("\n") + 1
            end_line = content[:end_idx].count("\n") + 1

            # Create chunk
            chunk = CodeChunk(
                language=self._detect_language(),
                file_path=self.file_path or "",
                node_type="fallback_dynamic_chars",
                start_line=start_line,
                end_line=end_line,
                byte_start=overlap_start,
                byte_end=end_idx,
                parent_context=f"dynamic_chunk_{chunk_num}",
                content=chunk_content,
            )
            chunks.append(chunk)

            # Move to next chunk
            i = end_idx
            chunk_num += 1

        return chunks
