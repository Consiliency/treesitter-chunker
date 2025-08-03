"""Main chunker module with token-aware chunking capabilities."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

# Import the core functions from the new module
from .core import chunk_text
from .token.chunker import TreeSitterTokenAwareChunker
from .token.counter import TiktokenCounter

if TYPE_CHECKING:
    from .types import CodeChunk


def chunk_text_with_token_limit(
    text: str,
    language: str,
    max_tokens: int,
    file_path: str = "",
    model: str = "gpt-4",
    extract_metadata: bool = True,
) -> list[CodeChunk]:
    """Parse text and return chunks that respect token limits.

    This function chunks code using tree-sitter and ensures no chunk exceeds
    the specified token limit. Large chunks are automatically split while
    preserving code structure when possible.

    Args:
        text: Source code text to chunk
        language: Programming language
        max_tokens: Maximum tokens per chunk
        file_path: Path to the file (optional)
        model: Tokenizer model to use (default: "gpt-4")
        extract_metadata: Whether to extract metadata (default: True)

    Returns:
        List of CodeChunk objects with token counts in metadata
    """
    # First get regular chunks
    chunks = chunk_text(text, language, file_path, extract_metadata)

    # Create token-aware chunker
    token_chunker = TreeSitterTokenAwareChunker()

    # Add token info and split if needed
    chunks_with_tokens = token_chunker.add_token_info(chunks, model)

    # Handle oversized chunks
    final_chunks = []
    for chunk in chunks_with_tokens:
        token_count = chunk.metadata.get("token_count", 0)

        if token_count <= max_tokens:
            final_chunks.append(chunk)
        else:
            # Split the oversized chunk
            split_chunks = token_chunker._split_large_chunk(chunk, max_tokens, model)
            final_chunks.extend(split_chunks)

    return final_chunks


def chunk_file_with_token_limit(
    path: str | Path,
    language: str,
    max_tokens: int,
    model: str = "gpt-4",
    extract_metadata: bool = True,
) -> list[CodeChunk]:
    """Parse file and return chunks that respect token limits.

    This function chunks a file using tree-sitter and ensures no chunk exceeds
    the specified token limit. Large chunks are automatically split while
    preserving code structure when possible.

    Args:
        path: Path to the file to chunk
        language: Programming language
        max_tokens: Maximum tokens per chunk
        model: Tokenizer model to use (default: "gpt-4")
        extract_metadata: Whether to extract metadata (default: True)

    Returns:
        List of CodeChunk objects with token counts in metadata
    """
    src = Path(path).read_text(encoding="utf-8")
    return chunk_text_with_token_limit(
        src,
        language,
        max_tokens,
        str(path),
        model,
        extract_metadata,
    )


def count_chunk_tokens(chunk: CodeChunk, model: str = "gpt-4") -> int:
    """Count tokens in a code chunk.

    Args:
        chunk: The CodeChunk to count tokens for
        model: Tokenizer model to use (default: "gpt-4")

    Returns:
        Number of tokens in the chunk
    """
    counter = TiktokenCounter()
    return counter.count_tokens(chunk.content, model)
