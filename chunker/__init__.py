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
]

from .parser import (
    get_parser, list_languages, get_language_info, 
    return_parser, clear_cache
)
from .chunker import chunk_file
from .factory import ParserConfig
from .exceptions import (
    ChunkerError, LanguageNotFoundError, 
    ParserError, LibraryNotFoundError
)
