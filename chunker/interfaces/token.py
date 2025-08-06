"""Token counting interfaces for enhancing Tree-sitter chunks with token information."""

from abc import ABC, abstractmethod

from chunker.interfaces.base import ChunkingStrategy
from chunker.types import CodeChunk


class TokenCounter(ABC):
    """Count tokens in text using various tokenizers."""

    @staticmethod
    @abstractmethod
    def count_tokens(text: str, model: str = "gpt-4") -> int:
        """
        Count the number of tokens in the given text.

        Args:
            text: The text to count tokens for
            model: The tokenizer model to use (e.g., "gpt-4", "claude", "llama")

        Returns:
            Number of tokens in the text
        """

    @staticmethod
    @abstractmethod
    def get_token_limit(model: str) -> int:
        """
        Get the maximum token limit for a given model.

        Args:
            model: The model name

        Returns:
            Maximum number of tokens the model can handle
        """

    @staticmethod
    @abstractmethod
    def split_text_by_tokens(
        text: str,
        max_tokens: int,
        model: str = "gpt-4",
    ) -> list[str]:
        """
        Split text into chunks that don't exceed the token limit.

        Args:
            text: The text to split
            max_tokens: Maximum tokens per chunk
            model: The tokenizer model to use

        Returns:
            List of text chunks
        """


class TokenAwareChunker(ChunkingStrategy):
    """Enhance chunks with token information while respecting Tree-sitter boundaries."""

    @staticmethod
    @abstractmethod
    def chunk_with_token_limit(
        file_path: str,
        language: str,
        max_tokens: int,
        model: str = "gpt-4",
    ) -> list[CodeChunk]:
        """
        Create chunks with token count information and optional splitting.

        This should enhance existing Tree-sitter chunks with token counts and
        optionally split large chunks that exceed token limits while preserving
        semantic boundaries as much as possible.

        Args:
            file_path: Path to the file to chunk
            language: Programming language
            max_tokens: Maximum tokens per chunk
            model: The tokenizer model to use

        Returns:
            List of chunks with token information in metadata
        """

    @staticmethod
    @abstractmethod
    def add_token_info(
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
