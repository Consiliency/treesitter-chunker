"""Incremental parsing implementation using Tree-sitter's capabilities."""

import difflib
import logging

from tree_sitter import Parser, Tree

from chunker.interfaces.performance import (
    IncrementalParser as IncrementalParserInterface,
)
from chunker.parser import get_parser
from chunker.types import CodeChunk

logger = logging.getLogger(__name__)


class IncrementalParser(IncrementalParserInterface):
    """Support for incremental parsing of file changes using Tree-sitter."""

    def __init__(self):
        """Initialize incremental parser."""
        self._parser_cache = {}
        logger.info("Initialized IncrementalParser")

    def parse_incremental(
        self,
        old_tree: Tree,
        source: bytes,
        changed_ranges: list[tuple[int, int, int, int]],
    ) -> Tree:
        """Parse incrementally based on changes.

        Tree-sitter supports incremental parsing by providing edit information
        about what changed in the source code.

        Args:
            old_tree: Previous parse tree
            source: New source code
            changed_ranges: List of (start_byte, old_end_byte, new_end_byte, start_point)

        Returns:
            New parse tree
        """
        if not old_tree or not hasattr(old_tree, "root_node"):
            raise ValueError("Invalid old_tree provided")

        # Get language from the old tree

        # Get or create parser for this language
        parser = self._get_parser_for_tree(old_tree)

        # Apply edits to the tree
        for start_byte, old_end_byte, new_end_byte, start_point in changed_ranges:
            old_tree.edit(
                start_byte=start_byte,
                old_end_byte=old_end_byte,
                new_end_byte=new_end_byte,
                start_point=start_point,
                old_end_point=self._calculate_point(old_tree.text, old_end_byte),
                new_end_point=self._calculate_point(source, new_end_byte),
            )

        # Parse with the edited tree as the old tree
        new_tree = parser.parse(source, old_tree)

        logger.debug("Incremental parse completed. Changes: %s", len(changed_ranges))

        return new_tree

    def detect_changes(
        self,
        old_source: bytes,
        new_source: bytes,
    ) -> list[tuple[int, int, int, int]]:
        """Detect changed ranges between sources.

        Uses difflib to find the differences and converts them to Tree-sitter
        edit format.

        Args:
            old_source: Previous source code
            new_source: New source code

        Returns:
            List of changed ranges in Tree-sitter format
        """
        # Convert bytes to lines for diffing
        old_lines = old_source.decode("utf-8", errors="replace").splitlines(
            keepends=True,
        )
        new_lines = new_source.decode("utf-8", errors="replace").splitlines(
            keepends=True,
        )

        # Use difflib to find changes
        matcher = difflib.SequenceMatcher(None, old_lines, new_lines)
        changes = []

        for tag, old_start, old_end, new_start, new_end in matcher.get_opcodes():
            if tag == "equal":
                # No change, just update positions
                sum(len(line.encode("utf-8")) for line in old_lines[old_start:old_end])
                sum(len(line.encode("utf-8")) for line in new_lines[new_start:new_end])
            else:
                # Calculate byte positions
                start_byte = sum(
                    len(line.encode("utf-8")) for line in old_lines[:old_start]
                )
                old_end_byte = sum(
                    len(line.encode("utf-8")) for line in old_lines[:old_end]
                )
                new_end_byte = start_byte + sum(
                    len(line.encode("utf-8")) for line in new_lines[new_start:new_end]
                )

                # Calculate start point (row, column)
                start_point = self._calculate_point(old_source, start_byte)

                changes.append((start_byte, old_end_byte, new_end_byte, start_point))

        logger.debug("Detected %s change ranges", len(changes))
        return changes

    def update_chunks(
        self,
        old_chunks: list[CodeChunk],
        old_tree: Tree,
        new_tree: Tree,
        changed_ranges: list[tuple[int, int, int, int]],
    ) -> list[CodeChunk]:
        """Update chunks based on incremental changes.

        This method efficiently updates only the chunks that were affected
        by the changes.

        Args:
            old_chunks: Previous chunks
            old_tree: Previous parse tree
            new_tree: New parse tree
            changed_ranges: Ranges that changed

        Returns:
            Updated chunk list
        """
        if not changed_ranges:
            # No changes, return old chunks
            return old_chunks

        # Create a set of affected byte ranges
        affected_ranges = set()
        for start_byte, old_end_byte, _new_end_byte, _ in changed_ranges:
            affected_ranges.add((start_byte, old_end_byte))

        # Determine which chunks are affected
        affected_chunk_ids = set()

        for chunk in old_chunks:
            # Check if chunk overlaps with any changed range
            for start_byte, old_end_byte, _new_end_byte, _ in changed_ranges:
                if chunk.byte_start < old_end_byte and chunk.byte_end > start_byte:
                    affected_chunk_ids.add(chunk.chunk_id)
                    break

        logger.info(
            f"Incremental update: {len(affected_chunk_ids)} chunks affected out of {len(old_chunks)}",
        )

        # For now, we'll need to re-chunk the affected areas
        # In a full implementation, we would:
        # 1. Keep unaffected chunks
        # 2. Re-parse only affected areas
        # 3. Merge the results

        # This is a simplified version that marks which chunks need updating
        updated_chunks = []

        for chunk in old_chunks:
            if chunk.chunk_id not in affected_chunk_ids:
                # Chunk not affected, but may need byte offset adjustment
                updated_chunk = self._adjust_chunk_offsets(chunk, changed_ranges)
                updated_chunks.append(updated_chunk)
            else:
                # Chunk affected, would need re-parsing
                # For now, we'll skip it (in real implementation, re-parse this section)
                logger.debug("Chunk %s needs re-parsing", chunk.chunk_id)

        return updated_chunks

    def _get_parser_for_tree(self, tree: Tree) -> Parser:
        """Get or create a parser for the tree's language."""
        # This is a simplified version - in practice, we'd determine
        # the language from the tree metadata
        language = "python"  # Default for now

        if language not in self._parser_cache:
            self._parser_cache[language] = get_parser(language)

        return self._parser_cache[language]

    def _calculate_point(self, source: bytes, byte_offset: int) -> tuple[int, int]:
        """Calculate row and column from byte offset.

        Args:
            source: Source code
            byte_offset: Byte position

        Returns:
            Tuple of (row, column)
        """
        if byte_offset <= 0:
            return (0, 0)

        text = source[:byte_offset].decode("utf-8", errors="replace")
        lines = text.splitlines()

        row = len(lines) - 1
        if lines:
            column = len(lines[-1])
        else:
            column = 0

        return (row, column)

    def _adjust_chunk_offsets(
        self,
        chunk: CodeChunk,
        changed_ranges: list[tuple[int, int, int, int]],
    ) -> CodeChunk:
        """Adjust chunk byte offsets based on changes.

        Args:
            chunk: Original chunk
            changed_ranges: List of changes

        Returns:
            Chunk with adjusted offsets
        """
        # Calculate total byte offset from changes before this chunk
        byte_adjustment = 0

        for start_byte, old_end_byte, new_end_byte, _ in changed_ranges:
            if start_byte < chunk.byte_start:
                # Change is before this chunk
                byte_adjustment += new_end_byte - old_end_byte

        if byte_adjustment != 0:
            # Create a new chunk with adjusted offsets
            return CodeChunk(
                language=chunk.language,
                file_path=chunk.file_path,
                node_type=chunk.node_type,
                start_line=chunk.start_line,  # Line numbers would also need adjustment
                end_line=chunk.end_line,
                byte_start=chunk.byte_start + byte_adjustment,
                byte_end=chunk.byte_end + byte_adjustment,
                parent_context=chunk.parent_context,
                content=chunk.content,
                chunk_id=chunk.chunk_id,
                parent_chunk_id=chunk.parent_chunk_id,
                references=chunk.references,
                dependencies=chunk.dependencies,
            )

        return chunk
