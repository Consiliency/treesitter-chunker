"""Common types used across the chunker modules."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, Any
import hashlib


@dataclass
class CodeChunk:
    language: str
    file_path: str
    node_type: str
    start_line: int
    end_line: int
    byte_start: int
    byte_end: int
    parent_context: str
    content: str
    chunk_id: str = ""
    parent_chunk_id: str | None = None
    references: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def generate_id(self) -> str:
        """Generate a unique ID for this chunk based on its content and location."""
        id_string = f"{self.file_path}:{self.start_line}:{self.end_line}:{self.content}"
        return hashlib.sha256(id_string.encode()).hexdigest()[:16]
    
    def __post_init__(self):
        """Generate chunk ID if not provided."""
        if not self.chunk_id:
            self.chunk_id = self.generate_id()