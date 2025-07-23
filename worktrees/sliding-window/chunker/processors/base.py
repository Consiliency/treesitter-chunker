"""Base classes for processors."""

from dataclasses import dataclass
from typing import Any, Dict


@dataclass
class TextChunk:
    """Represents a chunk of text with metadata.
    
    Used by processors that handle non-code text formats.
    """
    content: str
    start_line: int
    end_line: int
    start_byte: int
    end_byte: int
    metadata: Dict[str, Any]
    chunk_type: str = "text"
    
    @property
    def line_count(self) -> int:
        """Number of lines in this chunk."""
        return self.end_line - self.start_line + 1
    
    @property
    def byte_size(self) -> int:
        """Size of chunk in bytes."""
        return self.end_byte - self.start_byte