"""Token counting implementation using tiktoken."""

import re
from collections.abc import Callable, Iterator
from typing import ClassVar

import tiktoken

from chunker.interfaces.token import TokenCounter


def _group_ranges(
    text: str, ends: list[int], fits: Callable[[str], bool]
) -> Iterator[tuple[str, bool]]:
    """Group contiguous ranges, or yield one oversized range for subdivision."""
    first = 0
    start = 0
    while first < len(ends):
        best = first
        probe = first + 1
        while fits(text[start : ends[probe - 1]]):
            best = probe
            if best == len(ends):
                break
            probe = min(len(ends), first + 2 * (best - first))

        # Refine a failed geometric probe. Only measured fits are accepted:
        # BPE counts need not increase monotonically as a range grows.
        while best > first and probe - best > 1:
            mid = (probe + best) // 2
            if fits(text[start : ends[mid - 1]]):
                best = mid
            else:
                probe = mid
        accepted = best > first
        first = best if accepted else first + 1
        end = ends[first - 1]
        yield text[start:end], accepted
        start = end


class TiktokenCounter(TokenCounter):
    """Count tokens using OpenAI's tiktoken library."""

    MODEL_TO_ENCODING: ClassVar[dict[str, str]] = {
        "gpt-4": "cl100k_base",
        "gpt-4-turbo": "cl100k_base",
        "gpt-3.5-turbo": "cl100k_base",
        "text-davinci-003": "p50k_base",
        "text-davinci-002": "p50k_base",
        "davinci": "r50k_base",
        "claude": "cl100k_base",
        "claude-3": "cl100k_base",
        "claude-3.5": "cl100k_base",
        "llama": "cl100k_base",
    }
    MODEL_LIMITS: ClassVar[dict[str, int]] = {
        "gpt-4": 8192,
        "gpt-4-turbo": 128000,
        "gpt-3.5-turbo": 4096,
        "text-davinci-003": 4096,
        "text-davinci-002": 4096,
        "davinci": 2049,
        "claude": 100000,
        "claude-3": 200000,
        "claude-3.5": 200000,
        "llama": 4096,
    }

    def __init__(self):
        """Initialize the token counter with cached encodings."""
        self._encodings_cache: dict[str, tiktoken.Encoding] = {}

    def _get_encoding(self, model: str) -> tiktoken.Encoding:
        """Get the appropriate encoding for a model."""
        encoding_name = self.MODEL_TO_ENCODING.get(
            model,
            "cl100k_base",
        )
        if encoding_name not in self._encodings_cache:
            self._encodings_cache[encoding_name] = tiktoken.get_encoding(
                encoding_name,
            )
        return self._encodings_cache[encoding_name]

    def count_tokens(self, text: str, model: str = "gpt-4") -> int:
        """
        Count the number of tokens in the given text.

        Args:
            text: The text to count tokens for
            model: The tokenizer model (e.g., "gpt-4", "claude", "llama")

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
        return self.MODEL_LIMITS.get(model, 4096)

    def split_text_by_tokens(
        self,
        text: str,
        max_tokens: int,
        model: str = "gpt-4",
    ) -> list[str]:
        """Partition text exactly, preferring whole LF-terminated lines.

        The budget must be positive. A single Unicode scalar whose encoding
        exceeds the budget is returned whole.
        """
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")
        if not text:
            return []

        def fits(part: str) -> bool:
            return self.count_tokens(part, model) <= max_tokens

        if fits(text):
            return [text]

        ends = [match.end() for match in re.finditer("\n", text)]
        if not ends or ends[-1] != len(text):
            ends.append(len(text))
        parts = []
        for block, accepted in _group_ranges(text, ends, fits):
            if accepted:
                parts.append(block)
            else:
                parts.extend(self._split_long_line(block, fits))
        return parts

    @staticmethod
    def _split_long_line(text: str, fits: Callable[[str], bool]) -> Iterator[str]:
        """Bisect a line at an interior boundary and retain both exact slices."""
        if len(text) == 1 or fits(text):
            yield text
            return
        mid = len(text) // 2
        # Keep cuts in the middle half so each recursive step makes progress.
        cut = mid
        for distance in range(len(text) // 4 + 1):
            for pos in (mid - distance, mid + distance):
                if 0 < pos < len(text) and (
                    text[pos - 1].isspace() or text[pos - 1] in ".,;:!?"
                ):
                    cut = pos
                    break
            else:
                continue
            break
        yield from TiktokenCounter._split_long_line(text[:cut], fits)
        yield from TiktokenCounter._split_long_line(text[cut:], fits)
