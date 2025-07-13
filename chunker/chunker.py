from __future__ import annotations
from pathlib import Path
from dataclasses import dataclass, field
from tree_sitter import Node
import hashlib

from .parser import get_parser
from .languages import language_config_registry

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
    
    def generate_id(self) -> str:
        """Generate a unique ID for this chunk based on its content and location."""
        id_string = f"{self.file_path}:{self.start_line}:{self.end_line}:{self.content}"
        return hashlib.sha256(id_string.encode()).hexdigest()[:16]
    
    def __post_init__(self):
        """Generate chunk ID if not provided."""
        if not self.chunk_id:
            self.chunk_id = self.generate_id()

def _walk(node: Node, source: bytes, language: str, parent_ctx: str | None = None,
          parent_chunk: CodeChunk | None = None) -> list[CodeChunk]:
    """Walk the AST and extract chunks based on language configuration."""
    # Get language configuration
    config = language_config_registry.get(language)
    if not config:
        # Fallback to hardcoded defaults for backward compatibility
        CHUNK_TYPES = {"function_definition", "class_definition", "method_definition"}
        should_chunk = lambda node_type: node_type in CHUNK_TYPES
        should_ignore = lambda node_type: False
    else:
        should_chunk = config.should_chunk_node
        should_ignore = config.should_ignore_node

    chunks: list[CodeChunk] = []
    current_chunk = None
    
    # Skip ignored nodes
    if should_ignore(node.type):
        return chunks
    
    # Check if this node should be a chunk
    if should_chunk(node.type):
        text = source[node.start_byte:node.end_byte].decode()
        current_chunk = CodeChunk(
            language=language,
            file_path="",
            node_type=node.type,
            start_line=node.start_point[0] + 1,
            end_line=node.end_point[0] + 1,
            byte_start=node.start_byte,
            byte_end=node.end_byte,
            parent_context=parent_ctx or "",
            content=text,
            parent_chunk_id=parent_chunk.chunk_id if parent_chunk else None,
        )
        chunks.append(current_chunk)
        parent_ctx = node.type  # nested functions, etc.
    
    # Walk children with current chunk as parent
    for child in node.children:
        chunks.extend(_walk(child, source, language, parent_ctx, current_chunk or parent_chunk))
    
    return chunks

def chunk_file(path: str | Path, language: str) -> list[CodeChunk]:
    """Parse the file and return a list of `CodeChunk`."""
    parser = get_parser(language)
    src = Path(path).read_bytes()
    tree = parser.parse(src)
    chunks = _walk(tree.root_node, src, language)
    for c in chunks:
        c.file_path = str(path)
    return chunks