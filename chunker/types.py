"""Common types used across the chunker modules."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from typing import Any


def compute_text_hash16(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def compute_file_id(file_path: str) -> str:
    seed = f"file:{file_path}".encode()
    return hashlib.sha1(seed).hexdigest()


def compute_node_id(
    file_path: str,
    language: str,
    parent_route: list[str],
    content: str,
) -> str:
    route = "/".join(parent_route or [])
    text_hash16 = compute_text_hash16(content or "")
    to_hash = f"{file_path}|{language}|{route}|{text_hash16}".encode()
    return hashlib.sha1(to_hash).hexdigest()


def compute_symbol_id(language: str, file_path: str, symbol_name: str) -> str:
    seed = f"sym:{language}:{file_path}:{symbol_name}".encode()
    return hashlib.sha1(seed).hexdigest()


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
    metadata: dict[str, Any] = field(default_factory=dict)
    # New stable identity and hierarchy fields
    node_id: str = ""
    file_id: str = ""
    symbol_id: str | None = None
    parent_route: list[str] = field(default_factory=list)

    def generate_id(self) -> str:
        """Generate a stable ID using file/language/route/text hash."""
        return compute_node_id(
            self.file_path,
            self.language,
            self.parent_route,
            self.content,
        )

    def __post_init__(self):
        if not self.node_id:
            self.node_id = self.generate_id()
        if not self.chunk_id:
            self.chunk_id = self.node_id
        if not self.file_id and self.file_path:
            self.file_id = compute_file_id(self.file_path)
        # mirror spans in metadata for convenience if missing
        if "start_byte" not in self.metadata:
            self.metadata["start_byte"] = self.byte_start
        if "end_byte" not in self.metadata:
            self.metadata["end_byte"] = self.byte_end
        if self.parent_route and "parent_route" not in self.metadata:
            self.metadata["parent_route"] = list(self.parent_route)
