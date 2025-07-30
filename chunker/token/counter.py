"""Token counting implementation using tiktoken."""

from functools import lru_cache

import tiktoken

from chunker.interfaces.token import TokenCounter


class TiktokenCounter(TokenCounter):
    """Count tokens using OpenAI's tiktoken library."""

    # Model to encoding mapping
    MODEL_TO_ENCODING = {
        "gpt-4": "cl100k_base",
        "gpt-4-turbo": "cl100k_base",
        "gpt-3.5-turbo": "cl100k_base",
        "text-davinci-003": "p50k_base",
        "text-davinci-002": "p50k_base",
        "davinci": "r50k_base",
        "claude": "cl100k_base",  # Using similar encoding for Claude
        "claude-3": "cl100k_base",
        "llama": "cl100k_base",  # Using similar encoding for LLama
    }

    # Model token limits
    MODEL_LIMITS = {
        "gpt-4": 8192,
        "gpt-4-turbo": 128000,
        "gpt-3.5-turbo": 4096,
        "text-davinci-003": 4096,
        "text-davinci-002": 4096,
        "davinci": 2049,
        "claude": 100000,
        "claude-3": 200000,
        "llama": 4096,
    }

    def __init__(self):
        """Initialize the token counter with cached encodings."""
        self._encodings_cache: dict[str, tiktoken.Encoding] = {}

    @lru_cache(maxsize=128)
    def _get_encoding(self, model: str) -> tiktoken.Encoding:
        """Get the appropriate encoding for a model."""
        encoding_name = self.MODEL_TO_ENCODING.get(model, "cl100k_base")

        if encoding_name not in self._encodings_cache:
            self._encodings_cache[encoding_name] = tiktoken.get_encoding(encoding_name)

        return self._encodings_cache[encoding_name]

    def count_tokens(self, text: str, model: str = "gpt-4") -> int:
        """
        Count the number of tokens in the given text.

        Args:
            text: The text to count tokens for
            model: The tokenizer model to use (e.g., "gpt-4", "claude", "llama")

        Returns:
            Number of tokens in the text
        """
        if not text:
            return 0

        encoding = self._get_encoding(model)
        return len(encoding.encode(text))

    def get_token_limit(self, model: str) -> int:
        """
        Get the maximum token limit for a given model.

        Args:
            model: The model name

        Returns:
            Maximum number of tokens the model can handle
        """
        return self.MODEL_LIMITS.get(model, 4096)  # Default to 4096 if unknown

    def split_text_by_tokens(
        self,
        text: str,
        max_tokens: int,
        model: str = "gpt-4",
    ) -> list[str]:
        """
        Split text into chunks that don't exceed the token limit.

        This implementation tries to split on natural boundaries (lines, sentences)
        when possible to maintain readability.

        Args:
            text: The text to split
            max_tokens: Maximum tokens per chunk
            model: The tokenizer model to use

        Returns:
            List of text chunks
        """
        if not text:
            return []

        encoding = self._get_encoding(model)
        tokens = encoding.encode(text)

        if len(tokens) <= max_tokens:
            return [text]

        chunks = []
        current_chunk_tokens = []

        # Try to split on line boundaries first
        lines = text.split("\n")
        current_lines = []

        for line in lines:
            line_tokens = encoding.encode(line + "\n")

            # If a single line is too long, we need to split it
            if len(line_tokens) > max_tokens:
                # Add what we have so far
                if current_lines:
                    chunks.append("\n".join(current_lines))
                    current_lines = []
                    current_chunk_tokens = []

                # Split the long line
                line_chunks = self._split_long_line(line, max_tokens, encoding)
                chunks.extend(line_chunks[:-1])  # Add all but the last
                current_lines = [line_chunks[-1]] if line_chunks[-1] else []
                current_chunk_tokens = (
                    encoding.encode(line_chunks[-1]) if line_chunks[-1] else []
                )

            elif len(current_chunk_tokens) + len(line_tokens) > max_tokens:
                # This line would exceed the limit, start a new chunk
                if current_lines:
                    chunks.append("\n".join(current_lines))
                current_lines = [line]
                current_chunk_tokens = line_tokens
            else:
                # Add line to current chunk
                current_lines.append(line)
                current_chunk_tokens.extend(line_tokens)

        # Add any remaining content
        if current_lines:
            # Join with newlines but don't add trailing newline to final chunk
            chunks.append("\n".join(current_lines))

        return chunks

    def _split_long_line(
        self,
        line: str,
        max_tokens: int,
        encoding: tiktoken.Encoding,
    ) -> list[str]:
        """Split a single long line that exceeds token limit."""
        chunks = []

        # Try to split on sentence boundaries (periods followed by space)
        sentences = []
        current = []
        for char in line:
            current.append(char)
            if char in ".!?" and len(current) > 1:
                sentences.append("".join(current))
                current = []

        if current:
            sentences.append("".join(current))

        # Now group sentences into chunks
        current_chunk = []
        current_tokens = []

        for sentence in sentences:
            sentence_tokens = encoding.encode(sentence)

            if len(sentence_tokens) > max_tokens:
                # Single sentence is too long, split by words
                if current_chunk:
                    chunks.append("".join(current_chunk))
                    current_chunk = []
                    current_tokens = []

                # Split sentence by words
                word_chunks = self._split_sentence_by_words(
                    sentence,
                    max_tokens,
                    encoding,
                )
                chunks.extend(word_chunks[:-1])
                current_chunk = [word_chunks[-1]] if word_chunks[-1] else []
                current_tokens = (
                    encoding.encode(word_chunks[-1]) if word_chunks[-1] else []
                )

            elif len(current_tokens) + len(sentence_tokens) > max_tokens:
                if current_chunk:
                    chunks.append("".join(current_chunk))
                current_chunk = [sentence]
                current_tokens = sentence_tokens
            else:
                current_chunk.append(sentence)
                current_tokens.extend(sentence_tokens)

        if current_chunk:
            chunks.append("".join(current_chunk))

        return chunks

    def _split_sentence_by_words(
        self,
        sentence: str,
        max_tokens: int,
        encoding: tiktoken.Encoding,
    ) -> list[str]:
        """Split a sentence by words when it's too long."""
        words = sentence.split()
        chunks = []
        current_chunk = []
        current_tokens = []

        for word in words:
            word_with_space = word + " "
            word_tokens = encoding.encode(word_with_space)

            if len(word_tokens) > max_tokens:
                # Single word is too long, we have to break it
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    current_tokens = []

                # Just break the word arbitrarily
                chunks.append(word[: max_tokens * 3])  # Rough estimate
                continue

            if len(current_tokens) + len(word_tokens) > max_tokens:
                if current_chunk:
                    chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_tokens = word_tokens
            else:
                current_chunk.append(word)
                current_tokens.extend(word_tokens)

        if current_chunk:
            chunks.append(" ".join(current_chunk))

        return chunks
