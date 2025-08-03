"""Token-aware chunking that enhances Tree-sitter chunks with token information."""
import copy
from typing import Any

import tree_sitter

from chunker.core import _walk, chunk_file
from chunker.interfaces.token import TokenAwareChunker, TokenCounter
from chunker.types import CodeChunk

from .counter import TiktokenCounter


class TreeSitterTokenAwareChunker(TokenAwareChunker):
    """
    Enhance Tree-sitter chunks with token information and handle oversized chunks.

    This implementation:
    1. Uses Tree-sitter for semantic chunking
    2. Adds token count information to each chunk
    3. Splits oversized chunks while preserving structure when possible
    """

    def __init__(self, token_counter: (TokenCounter | None) = None):
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

    def chunk(self, ast: tree_sitter.Node, source: bytes, file_path: str,
        language: str) -> list[CodeChunk]:
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

    def chunk_with_token_limit(self, file_path: str, language: str,
        max_tokens: int, model: str = "gpt-4") -> list[CodeChunk]:
        """
        Create chunks with token count information and optional splitting.

        This enhances existing Tree-sitter chunks with token counts and
        splits large chunks that exceed token limits while preserving
        semantic boundaries as much as possible.

        Args:
            file_path: Path to the file to chunk
            language: Programming language
            max_tokens: Maximum tokens per chunk
            model: The tokenizer model to use

        Returns:
            List of chunks with token information in metadata
        """
        chunks = chunk_file(file_path, language)
        chunks_with_tokens = self.add_token_info(chunks, model)
        final_chunks = []
        for chunk in chunks_with_tokens:
            token_count = chunk.metadata.get("token_count", 0)
            if token_count <= max_tokens:
                final_chunks.append(chunk)
            else:
                split_chunks = self._split_large_chunk(chunk, max_tokens, model,
                    )
                final_chunks.extend(split_chunks)
        return final_chunks

    def add_token_info(self, chunks: list[CodeChunk], model: str = "gpt-4",
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
                enhanced_chunk.metadata["chars_per_token"
                    ] = char_count / token_count
            enhanced_chunks.append(enhanced_chunk)
        return enhanced_chunks

    def _split_large_chunk(self, chunk: CodeChunk, max_tokens: int, model: str,
        ) -> list[CodeChunk]:
        """
        Split a chunk that exceeds the token limit.

        This method tries to preserve code structure by splitting at logical boundaries
        like method boundaries within a class, or line boundaries for functions.

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

    def _split_class_chunk(self, chunk: CodeChunk, max_tokens: int, model: str,
        ) -> list[CodeChunk]:
        """
        Split a class chunk by trying to separate methods.

        This is a simplified implementation that splits by line patterns.
        A more sophisticated version would re-parse with Tree-sitter.
        """
        content = chunk.content
        lines = content.split("\n")
        method_starts = []
        for i, line in enumerate(lines):
            stripped = line.strip()
            if any(pattern in stripped for pattern in ["def ", "function ",
                "func ", "fn ", "public ", "private ", "protected "]) and (line
                .startswith((" ", "\t")) and not line.startswith("        ")):
                method_starts.append(i)
        if not method_starts:
            return self._split_by_lines(chunk, max_tokens, model)
        chunks = []
        current_part = []
        current_tokens = 0
        class_header_lines = lines[:method_starts[0]] if method_starts else []
        class_header = "\n".join(class_header_lines)
        header_tokens = self.token_counter.count_tokens(class_header, model)
        if header_tokens > max_tokens:
            return self._split_by_lines(chunk, max_tokens, model)
        current_part = class_header_lines.copy()
        current_tokens = header_tokens
        for i, start_idx in enumerate(method_starts):
            end_idx = method_starts[i + 1] if i + 1 < len(method_starts,
                ) else len(lines)
            method_lines = lines[start_idx:end_idx]
            method_content = "\n".join(method_lines)
            method_tokens = self.token_counter.count_tokens(method_content,
                model)
            if (current_tokens + method_tokens > max_tokens and
                current_part != class_header_lines):
                chunk_content = "\n".join(current_part)
                new_chunk = self._create_sub_chunk(chunk, chunk_content,
                    len(chunks))
                chunks.append(new_chunk)
                current_part = class_header_lines.copy()
                current_tokens = header_tokens
            current_part.extend(method_lines)
            current_tokens += method_tokens
        if current_part and current_part != class_header_lines:
            chunk_content = "\n".join(current_part)
            new_chunk = self._create_sub_chunk(chunk, chunk_content, len(
                chunks))
            chunks.append(new_chunk)
        return chunks if chunks else [chunk]

    def _split_by_lines(self, chunk: CodeChunk, max_tokens: int, model: str,
        ) -> list[CodeChunk]:
        """Split a chunk by lines while trying to preserve logical groups."""
        text_parts = self.token_counter.split_text_by_tokens(chunk.content,
            max_tokens, model)
        chunks = []
        for i, part in enumerate(text_parts):
            new_chunk = self._create_sub_chunk(chunk, part, i)
            chunks.append(new_chunk)
        return chunks

    def _create_sub_chunk(self, original_chunk: CodeChunk, content: str,
        index: int) -> CodeChunk:
        """Create a sub-chunk from an original chunk."""
        original_lines = original_chunk.content.split("\n")
        new_lines = content.split("\n")
        start_offset = 0
        for i, line in enumerate(original_lines):
            if new_lines and line.strip() == new_lines[0].strip():
                start_offset = i
                break
        new_chunk = CodeChunk(language=original_chunk.language, file_path=original_chunk.file_path, node_type=f"{original_chunk.node_type}_part_{index + 1}", start_line=original_chunk.start_line + start_offset, end_line=original_chunk.start_line + start_offset + len(new_lines) - 1,
            byte_start=original_chunk.byte_start, byte_end=original_chunk.
            byte_start + len(content.encode()), parent_context=original_chunk.parent_context, content=content, parent_chunk_id=original_chunk.chunk_id, references=original_chunk.references.
            copy(), dependencies=original_chunk.dependencies.copy(),
            metadata={"token_count": self.token_counter.count_tokens(
            content, original_chunk.metadata.get("tokenizer_model", "gpt-4",
            )), "tokenizer_model": original_chunk.metadata.get(
            "tokenizer_model", "gpt-4"), "is_split": True, "split_index":
            index + 1, "original_chunk_id": original_chunk.chunk_id,
            "original_token_count": original_chunk.metadata.get(
            "token_count", 0)})
        return new_chunk
