"""Markdown-specific fallback chunker."""

import logging
import re

from chunker.fallback.base import FallbackChunker
from chunker.interfaces.fallback import ChunkingMethod, FallbackConfig
from chunker.interfaces.fallback import MarkdownChunker as IMarkdownChunker
from chunker.types import CodeChunk

logger = logging.getLogger(__name__)


class MarkdownChunker(FallbackChunker, IMarkdownChunker):
    """Fallback chunker for Markdown without Tree-sitter.

    Note: This is a fallback implementation. Tree-sitter-markdown
    should be preferred when available as it provides proper AST-based
    parsing that handles edge cases better.
    """

    def __init__(self):
        """Initialize markdown chunker."""
        config = FallbackConfig(method=ChunkingMethod.REGEX_BASED)
        super().__init__(config)

        # Markdown patterns
        self.header_pattern = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
        self.code_block_pattern = re.compile(
            r"^```(\w*)\n(.*?)\n```$",
            re.MULTILINE | re.DOTALL,
        )
        self.list_pattern = re.compile(r"^(\s*)([-*+]|\d+\.)\s+", re.MULTILINE)
        self.link_pattern = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
        self.emphasis_pattern = re.compile(r"(\*\*|__|_|\*)(.*?)\1")

    def chunk_by_headers(self, content: str, max_level: int = 3) -> list[CodeChunk]:
        """Chunk by header hierarchy.

        Creates chunks based on markdown headers, with each chunk
        containing a header and its content up to the next header
        of the same or higher level.

        Args:
            content: Markdown content
            max_level: Maximum header level to chunk by (1-6)

        Returns:
            List of chunks
        """
        chunks = []
        lines = content.splitlines(keepends=True)

        # Find all headers with their positions
        headers: list[tuple[int, int, str, str]] = (
            []
        )  # (line_num, level, text, full_line)

        for i, line in enumerate(lines):
            match = self.header_pattern.match(line.rstrip())
            if match:
                level = len(match.group(1))
                if level <= max_level:
                    headers.append((i, level, match.group(2), line))

        if not headers:
            # No headers found, chunk the entire content
            return self.chunk_by_lines(content, 100, 10)

        # Create chunks based on headers
        for idx, (line_num, level, text, _header_line) in enumerate(headers):
            # Find the end of this section
            end_line_num = len(lines)

            # Look for next header of same or higher level
            for next_idx in range(idx + 1, len(headers)):
                next_line_num, next_level, _, _ = headers[next_idx]
                if next_level <= level:
                    end_line_num = next_line_num
                    break

            # Create chunk content
            chunk_lines = lines[line_num:end_line_num]
            chunk_content = "".join(chunk_lines)

            # Skip empty chunks
            if not chunk_content.strip():
                continue

            # Create chunk
            chunk = CodeChunk(
                language="markdown",
                file_path=self.file_path or "",
                node_type=f"markdown_h{level}",
                start_line=line_num + 1,
                end_line=end_line_num,
                byte_start=sum(len(line) for line in lines[:line_num]),
                byte_end=sum(len(line) for line in lines[:end_line_num]),
                parent_context=f"h{level}_{text[:30]}",
                content=chunk_content,
            )
            chunks.append(chunk)

        # Handle content before first header
        if headers and headers[0][0] > 0:
            pre_header_lines = lines[: headers[0][0]]
            if any(line.strip() for line in pre_header_lines):
                pre_content = "".join(pre_header_lines)
                chunk = CodeChunk(
                    language="markdown",
                    file_path=self.file_path or "",
                    node_type="markdown_preamble",
                    start_line=1,
                    end_line=headers[0][0],
                    byte_start=0,
                    byte_end=len(pre_content),
                    parent_context="preamble",
                    content=pre_content,
                )
                chunks.insert(0, chunk)

        return chunks

    def chunk_by_sections(
        self,
        content: str,
        include_code_blocks: bool = True,
    ) -> list[CodeChunk]:
        """Chunk by logical sections.

        This method tries to identify logical sections in markdown:
        - Headers and their content
        - Code blocks
        - Lists
        - Paragraphs

        Args:
            content: Markdown content
            include_code_blocks: Whether to include code blocks as separate chunks

        Returns:
            List of chunks
        """
        chunks = []
        lines = content.splitlines(keepends=True)

        # State tracking
        current_section_lines = []
        current_section_type = "paragraph"
        current_start_line = 1
        in_code_block = False
        code_block_lang = None
        in_list = False
        list_indent = 0

        for i, line in enumerate(lines):
            line_stripped = line.strip()

            # Check for code block
            if line_stripped.startswith("```"):
                if not in_code_block:
                    # Start of code block
                    # First, save current section
                    if current_section_lines and any(
                        line.strip() for line in current_section_lines
                    ):
                        chunk = self._create_section_chunk(
                            current_section_lines,
                            current_start_line,
                            i,
                            current_section_type,
                        )
                        chunks.append(chunk)

                    # Start code block
                    in_code_block = True
                    match = re.match(r"^```(\w*)", line_stripped)
                    code_block_lang = (
                        match.group(1) if match and match.group(1) else "unknown"
                    )
                    current_section_lines = [line]
                    current_section_type = f"code_block_{code_block_lang}"
                    current_start_line = i + 1
                else:
                    # End of code block
                    current_section_lines.append(line)
                    in_code_block = False

                    if include_code_blocks:
                        # Create separate chunk for code block
                        chunk = self._create_section_chunk(
                            current_section_lines,
                            current_start_line,
                            i + 1,
                            current_section_type,
                        )
                        chunks.append(chunk)

                    # Reset for next section
                    current_section_lines = []
                    current_section_type = "paragraph"
                    current_start_line = i + 2
                continue

            # If in code block, just accumulate
            if in_code_block:
                current_section_lines.append(line)
                continue

            # Check for header
            if self.header_pattern.match(line_stripped):
                # Save current section
                if current_section_lines and any(
                    line.strip() for line in current_section_lines
                ):
                    chunk = self._create_section_chunk(
                        current_section_lines,
                        current_start_line,
                        i,
                        current_section_type,
                    )
                    chunks.append(chunk)

                # Start new header section
                current_section_lines = [line]
                current_section_type = "header"
                current_start_line = i + 1
                in_list = False
                continue

            # Check for list item
            list_match = self.list_pattern.match(line)
            if list_match:
                indent = len(list_match.group(1))

                if not in_list or (in_list and abs(indent - list_indent) > 2):
                    # New list or significantly different indent
                    if current_section_lines and any(
                        line.strip() for line in current_section_lines
                    ):
                        chunk = self._create_section_chunk(
                            current_section_lines,
                            current_start_line,
                            i,
                            current_section_type,
                        )
                        chunks.append(chunk)

                    # Start new list
                    current_section_lines = [line]
                    current_section_type = "list"
                    current_start_line = i + 1
                    in_list = True
                    list_indent = indent
                else:
                    # Continue current list
                    current_section_lines.append(line)
                continue

            # Check for empty line (paragraph break)
            if not line_stripped:
                if in_list:
                    # Check if next non-empty line is also a list item
                    next_is_list = False
                    for j in range(i + 1, min(i + 3, len(lines))):
                        if lines[j].strip():
                            if self.list_pattern.match(lines[j]):
                                next_is_list = True
                            break

                    if not next_is_list:
                        # End of list
                        if current_section_lines:
                            chunk = self._create_section_chunk(
                                current_section_lines,
                                current_start_line,
                                i,
                                current_section_type,
                            )
                            chunks.append(chunk)

                        current_section_lines = []
                        current_section_type = "paragraph"
                        current_start_line = i + 2
                        in_list = False
                    else:
                        # List continues
                        current_section_lines.append(line)
                else:
                    # Paragraph break
                    if current_section_lines and any(
                        line.strip() for line in current_section_lines
                    ):
                        chunk = self._create_section_chunk(
                            current_section_lines,
                            current_start_line,
                            i,
                            current_section_type,
                        )
                        chunks.append(chunk)

                    current_section_lines = []
                    current_section_type = "paragraph"
                    current_start_line = i + 2
                continue

            # Regular content line
            current_section_lines.append(line)

        # Handle remaining lines
        if current_section_lines and any(
            line.strip() for line in current_section_lines
        ):
            chunk = self._create_section_chunk(
                current_section_lines,
                current_start_line,
                len(lines),
                current_section_type,
            )
            chunks.append(chunk)

        return chunks

    def extract_code_blocks(self, content: str) -> list[CodeChunk]:
        """Extract code blocks as separate chunks.

        Args:
            content: Markdown content

        Returns:
            List of code block chunks
        """
        chunks = []

        # Find all code blocks
        for match in self.code_block_pattern.finditer(content):
            language = match.group(1) or "unknown"
            code_content = match.group(2)

            # Calculate line numbers
            pre_match = content[: match.start()]
            start_line = pre_match.count("\n") + 1
            end_line = start_line + code_content.count("\n") + 2  # +2 for fence lines

            chunk = CodeChunk(
                language=language,
                file_path=self.file_path or "",
                node_type="code_block",
                start_line=start_line,
                end_line=end_line,
                byte_start=match.start(),
                byte_end=match.end(),
                parent_context=f"code_block_{language}",
                content=match.group(0),
            )
            chunks.append(chunk)

        return chunks

    def _create_section_chunk(
        self,
        lines: list[str],
        start_line: int,
        end_line: int,
        section_type: str,
    ) -> CodeChunk:
        """Create a chunk for a markdown section."""
        content = "".join(lines)

        return CodeChunk(
            language="markdown",
            file_path=self.file_path or "",
            node_type=f"markdown_{section_type}",
            start_line=start_line,
            end_line=end_line,
            byte_start=0,  # Would need full content to calculate
            byte_end=len(content),
            parent_context=section_type,
            content=content,
        )
