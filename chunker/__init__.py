"""
Tree‑sitter Chunker – top‑level package.
"""
__all__ = ["get_parser", "chunk_file"]
from .parser import get_parser
from .chunker import chunk_file
