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
    # Plugin system
    "PluginManager",
    "get_plugin_manager",
    "LanguagePlugin",
    "PluginConfig",
    "ChunkerConfig",
    # Data classes
    "CodeChunk"
]

from .parser import (
    get_parser, list_languages, get_language_info, 
    return_parser, clear_cache
)
from .types import CodeChunk
from .chunker import chunk_file
from .factory import ParserConfig
from .exceptions import (
    ChunkerError, LanguageNotFoundError, 
    ParserError, LibraryNotFoundError
)
from .plugin_manager import PluginManager, get_plugin_manager
from .languages.base import PluginConfig
from .languages.plugin_base import LanguagePlugin
from .config import ChunkerConfig
