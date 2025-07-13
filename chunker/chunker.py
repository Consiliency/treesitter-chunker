from __future__ import annotations
from pathlib import Path
from tree_sitter import Node

from .parser import get_parser
from .languages import language_config_registry
from .types import CodeChunk

def _walk(node: Node, source: bytes, language: str, parent_ctx: str | None = None) -> list[CodeChunk]:
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
    
    # Skip ignored nodes
    if should_ignore(node.type):
        return chunks
    
    # Check if this node should be a chunk
    if should_chunk(node.type):
        text = source[node.start_byte:node.end_byte].decode()
        chunks.append(
            CodeChunk(
                language=language,
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
    
    # Recursively process children
    for child in node.children:
        chunks.extend(_walk(child, source, language, parent_ctx))
    
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
