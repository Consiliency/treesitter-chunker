"""Token-aware chunking that enhances Tree-sitter chunks
with token information."""

import copy
import re
from bisect import bisect_left
from collections.abc import Iterable
from typing import Any

import tree_sitter

from chunker.core import _line_ending_offsets, _walk, chunk_file
from chunker.interfaces.token import TokenAwareChunker, TokenCounter
from chunker.packing import compute_pack_hint
from chunker.types import CodeChunk

from .counter import TiktokenCounter, _group_ranges


class TreeSitterTokenAwareChunker(TokenAwareChunker):
    """
    Enhance Tree-sitter chunks with token information and handle
    oversized chunks.

    This implementation:
    1. Uses Tree-sitter for semantic chunking
    2. Adds token count information to each chunk
    3. Splits oversized chunks while preserving structure when possible
    """

    def __init__(self, token_counter: TokenCounter | None = None):
        """
        Initialize the token-aware chunker.

        Args:
            token_counter: Token counter instance (defaults to TiktokenCounter)
        """
        self.token_counter = token_counter or TiktokenCounter()
        self.default_model = "gpt-4"

    @staticmethod
    def can_handle(_file_path: str, _language: str) -> bool:
        """Check if this strategy can handle the given file."""
        return True

    def configure(self, config: dict[str, Any]) -> None:
        """Configure the chunking strategy."""
        if "default_model" in config:
            self.default_model = config["default_model"]
        if "token_counter" in config:
            self.token_counter = config["token_counter"]

    def chunk(
        self,
        ast: tree_sitter.Node,
        source: bytes,
        file_path: str,
        language: str,
    ) -> list[CodeChunk]:
        """
        Perform chunking on the AST with token information.

        Args:
            ast: Root node of the parsed AST
            source: Original source code as bytes
            file_path: Path to the source file
            language: Language identifier

        Returns:
            List of code chunks with token information
        """
        chunks = _walk(ast, source, language)
        for chunk in chunks:
            chunk.file_path = file_path
        return self.add_token_info(chunks)

    def chunk_file(self, file_path: str, language: str) -> list[CodeChunk]:
        """
        Chunk a file and add token information.

        This is a convenience method that doesn't require an AST.

        Args:
            file_path: Path to the file to chunk
            language: Programming language

        Returns:
            List of chunks with token information
        """
        chunks = chunk_file(file_path, language)
        return self.add_token_info(chunks)

    def chunk_with_token_limit(
        self,
        file_path: str,
        language: str,
        max_tokens: int,
        model: str = "gpt-4",
    ) -> list[CodeChunk]:
        """
        Create chunks with token count information and optional splitting.

        This enhances existing Tree-sitter chunks with token counts and
        splits large chunks that exceed token limits while preserving
        semantic boundaries as much as possible. An over-budget Unicode scalar
        is emitted alone with token_limit_exceeded=True.

        Args:
            file_path: Path to the file to chunk
            language: Programming language
            max_tokens: Maximum tokens per chunk
            model: The tokenizer model to use

        Returns:
            List of chunks with token information in metadata
        """
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        chunks = chunk_file(file_path, language)
        chunks_with_tokens = self.add_token_info(chunks, model)
        final_chunks = []
        for chunk in chunks_with_tokens:
            token_count = chunk.metadata.get("token_count", 0)
            if token_count <= max_tokens:
                final_chunks.append(chunk)
            else:
                split_chunks = self._split_large_chunk(
                    chunk,
                    max_tokens,
                    model,
                )
                final_chunks.extend(split_chunks)
        return final_chunks

    def add_token_info(
        self,
        chunks: list[CodeChunk],
        model: str = "gpt-4",
    ) -> list[CodeChunk]:
        """
        Add token count information to existing chunks.

        Args:
            chunks: List of existing chunks
            model: The tokenizer model to use

        Returns:
            Chunks with token counts added to metadata
        """
        enhanced_chunks = []
        for chunk in chunks:
            enhanced_chunk = copy.deepcopy(chunk)
            token_count = self.token_counter.count_tokens(chunk.content, model)
            enhanced_chunk.metadata["token_count"] = token_count
            enhanced_chunk.metadata["tokenizer_model"] = model
            char_count = len(chunk.content)
            if char_count > 0:
                enhanced_chunk.metadata["chars_per_token"] = (
                    char_count / token_count if token_count else 0
                )
            # compute pack hint
            enhanced_chunk.metadata["pack_hint"] = compute_pack_hint(enhanced_chunk)
            enhanced_chunks.append(enhanced_chunk)
        return enhanced_chunks

    def _split_large_chunk(
        self,
        chunk: CodeChunk,
        max_tokens: int,
        model: str,
    ) -> list[CodeChunk]:
        """
        Split a chunk that exceeds the token limit.

        This method tries to preserve code structure by splitting at
        logical boundaries like method boundaries within a class, or
        line boundaries for functions.

        Args:
            chunk: The chunk to split
            max_tokens: Maximum tokens per chunk
            model: The tokenizer model

        Returns:
            List of smaller chunks
        """
        if chunk.node_type in {"class_definition", "class_declaration"}:
            return self._split_class_chunk(chunk, max_tokens, model)
        return self._split_by_lines(chunk, max_tokens, model)

    def _split_class_chunk(
        self,
        chunk: CodeChunk,
        max_tokens: int,
        model: str,
    ) -> list[CodeChunk]:
        """
        Split a class chunk by trying to separate methods.

        This is a simplified implementation that splits by line patterns.
        A more sophisticated version would re-parse with Tree-sitter.
        """
        content = chunk.content
        method_starts = []
        for match in re.finditer(r"[^\n]+", content):
            line = match.group()
            stripped = line.strip()
            if any(
                pattern in stripped
                for pattern in [
                    "def ",
                    "function ",
                    "func ",
                    "fn ",
                    "public ",
                    "private ",
                    "protected ",
                ]
            ) and (line.startswith((" ", "\t")) and not line.startswith("        ")):
                method_starts.append(match.start())
        if not method_starts:
            return self._split_by_lines(chunk, max_tokens, model)

        def fits(part: str) -> bool:
            return self.token_counter.count_tokens(part, model) <= max_tokens

        header = content[: method_starts[0]].removesuffix("\n")
        if not fits(header):
            # Avoid repeating an oversized preamble on every serialized part.
            first_line = header.partition("\n")[0]
            header = first_line if fits(first_line) else ""
        context = chunk.parent_context
        if header:
            context = f"{header}\n{context}" if context else header

        ends = [pos for pos in method_starts if pos] + [len(content)]
        parts = []
        for block, accepted in _group_ranges(content, ends, fits):
            if accepted:
                parts.append(block)
            else:
                parts.extend(
                    self.token_counter.split_text_by_tokens(block, max_tokens, model)
                )
        return self._materialize_parts(chunk, parts, max_tokens, model, context)

    def _split_by_lines(
        self, chunk: CodeChunk, max_tokens: int, model: str
    ) -> list[CodeChunk]:
        parts = self.token_counter.split_text_by_tokens(
            chunk.content, max_tokens, model
        )
        return self._materialize_parts(
            chunk, parts, max_tokens, model, chunk.parent_context
        )

    def _materialize_parts(
        self,
        parent: CodeChunk,
        parts: Iterable[str],
        max_tokens: int,
        model: str,
        context: str,
    ) -> list[CodeChunk]:
        """Validate the partition while advancing character, byte and line cursors."""
        chunks = []
        offset = 0
        byte_start = parent.byte_start
        start_line = parent.start_line
        # Index the parent so a cut between CR and LF advances the row only
        # after the LF. Offsets are relative to the parent's UTF-8 source.
        line_endings = _line_ending_offsets(parent.content.encode(), parent.language)
        if (
            parent.content.endswith("\r")
            and len(line_endings) > parent.end_line - start_line
        ):
            # A parser span may itself end between the CR and LF of a CRLF.
            line_endings.pop()
        for index, part in enumerate(parts, start=1):
            if not part or not parent.content.startswith(part, offset):
                raise ValueError(
                    "Token counter returned an empty or out-of-order source part"
                )
            count = self.token_counter.count_tokens(part, model)
            if count > max_tokens and len(part) != 1:
                raise ValueError(
                    "Token counter returned a divisible part over the token budget"
                )
            byte_end = byte_start + len(part.encode("utf-8"))
            end_line = parent.start_line + bisect_left(
                line_endings, byte_end - parent.byte_start
            )
            child = CodeChunk(
                language=parent.language,
                file_path=parent.file_path,
                node_type=f"{parent.node_type}_part_{index}",
                start_line=start_line,
                end_line=end_line,
                byte_start=byte_start,
                byte_end=byte_end,
                parent_context=context,
                content=part,
                parent_chunk_id=parent.chunk_id,
                references=parent.references.copy(),
                dependencies=parent.dependencies.copy(),
                metadata={
                    "token_count": count,
                    "tokenizer_model": model,
                    "is_split": True,
                    "split_index": index,
                    "original_chunk_id": parent.chunk_id,
                    "original_token_count": parent.metadata.get("token_count", 0),
                },
            )
            if count > max_tokens:
                child.metadata["token_limit_exceeded"] = True
            chunks.append(child)
            offset += len(part)
            byte_start = byte_end
            start_line = end_line
        if offset != len(parent.content):
            raise ValueError("Token counter returned an incomplete source partition")
        return chunks
