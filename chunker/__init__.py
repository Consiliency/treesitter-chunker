"""
Tree‑sitter Chunker – top‑level package.
"""
__all__ = [
    # Core functions
    "get_parser", 
    "chunk_file",
    # New parser API
    "list_languages",
    "get_language_info",
    "return_parser",
    "clear_cache",
    # Configuration
    "ParserConfig",
    # Exceptions
    "ChunkerError",
    "LanguageNotFoundError",
    "ParserError",
    "LibraryNotFoundError",
    # Performance features
    "chunk_file_streaming",
    "chunk_files_parallel",
    "chunk_directory_parallel",
    "ASTCache",
    "StreamingChunker",
    "ParallelChunker",
    "CodeChunk",
]

from .parser import (
    get_parser, list_languages, get_language_info, 
    return_parser, clear_cache
)
from .chunker import chunk_file
from .types import CodeChunk
from .factory import ParserConfig
from .exceptions import (
    ChunkerError, LanguageNotFoundError, 
    ParserError, LibraryNotFoundError
)
from .streaming import chunk_file_streaming, StreamingChunker
from .parallel import chunk_files_parallel, chunk_directory_parallel, ParallelChunker
from .cache import ASTCache
