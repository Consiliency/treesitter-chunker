"""
Tree-sitter Chunker - Semantic code chunking for LLMs and embeddings.

Simple usage:
    from chunker import chunk_file, chunk_text, chunk_directory

    # Chunk a single file
    chunks = chunk_file("example.py", language="python")

    # Chunk raw text
    chunks = chunk_text(code_text, language="javascript")

    # Chunk entire directory
    results = chunk_directory("src/", language="python")
"""

__version__ = "1.0.0"

# Core functionality - these are the main APIs users need
from .core import chunk_file
from .parallel import chunk_directory_parallel as chunk_directory
from .streaming import chunk_file_streaming
from .types import CodeChunk


# Simple text chunking
def chunk_text(text: str, language: str, **kwargs):
    """Chunk text content directly without file I/O."""
    import tempfile
    from pathlib import Path

    # Write to temporary file and chunk it
    with tempfile.NamedTemporaryFile(
        encoding="utf-8", mode="w", suffix=".tmp", delete=False,
    ) as f:
        f.write(text)
        temp_path = f.name

    try:
        chunks = chunk_file(temp_path, language, **kwargs)
        return chunks
    finally:
        Path(temp_path).unlink(missing_ok=True)


# Export commonly used classes and functions
from ._internal.cache import ASTCache
from .chunker_config import ChunkerConfig
from .exceptions import LanguageNotFoundError, LibraryNotFoundError, ParserError
from .parser import (
    ParserConfig,
    clear_cache,
    get_language_info,
    get_parser,
    list_languages,
    return_parser,
)
from .plugin_manager import get_plugin_manager

# Convenient exports for common use cases
__all__ = [
    # Performance
    "ASTCache",
    # Configuration
    "ChunkerConfig",
    # Core types
    "CodeChunk",
    # Exceptions
    "LanguageNotFoundError",
    "LibraryNotFoundError",
    "ParserConfig",
    "ParserError"
    # Version
    "__version__",
    "chunk_directory",
    # Main functions
    "chunk_file",
    "chunk_file_streaming",
    "chunk_text",
    # Parser utilities
    "clear_cache",
    "get_language_info",
    "get_parser",
    "get_plugin_manager",
    # Language support
    "list_languages",
    "return_parser",
]
