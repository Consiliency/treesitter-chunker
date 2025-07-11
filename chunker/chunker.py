from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass
from tree_sitter import Node

from .parser import get_parser

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

def _walk(node: Node, source: bytes, parent_ctx: str | None = None) -> list[CodeChunk]:
    """Yield chunks for function / class / method‑like nodes only (MVP)."""
    CHUNK_TYPES = {"function_definition", "class_definition", "method_definition"}

    chunks: list[CodeChunk] = []
    if node.type in CHUNK_TYPES:
        text = source[node.start_byte:node.end_byte].decode()
        chunks.append(
            CodeChunk(
                language="python",  # replaced by caller
                file_path="",
                node_type=node.type,
                start_line=node.start_point[0] + 1,
                end_line=node.end_point[0] + 1,
                byte_start=node.start_byte,
                byte_end=node.end_byte,
                parent_context=parent_ctx or "",
                content=text,
            )
        )
        parent_ctx = node.type  # nested functions, etc.
    for child in node.children:
        chunks.extend(_walk(child, source, parent_ctx))
    return chunks

def chunk_file(path: str | Path, language: str) -> list[CodeChunk]:
    """Parse the file and return a list of `CodeChunk`."""
    parser = get_parser(language)
    src = Path(path).read_bytes()
    tree = parser.parse(src)
    chunks = _walk(tree.root_node, src)
    for c in chunks:
        c.language = language
        c.file_path = str(path)
    return chunks
