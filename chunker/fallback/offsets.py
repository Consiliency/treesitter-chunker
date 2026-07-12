"""UTF-8 byte and line offset helpers for fallback chunkers."""

from bisect import bisect_right


class TextPositionIndex:
    """Index character positions once, then expose byte and line positions."""

    def __init__(self, content: str):
        self._byte_offsets = [0]
        self._line_starts = [0]
        for index, char in enumerate(content):
            self._byte_offsets.append(
                self._byte_offsets[-1] + len(char.encode("utf-8"))
            )
            if char == "\n":
                self._line_starts.append(index + 1)

    def byte_offset(self, char_offset: int) -> int:
        return self._byte_offsets[char_offset]

    def line_number(self, char_offset: int) -> int:
        return bisect_right(self._line_starts, char_offset)
