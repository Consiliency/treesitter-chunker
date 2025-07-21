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
    # Plugin system
    "PluginManager",
    "ChunkerConfig",
    "LanguagePlugin",
    "PluginConfig",
    "get_plugin_manager",
    # Debug tools
    "ASTVisualizer",
    "QueryDebugger",
    "ChunkDebugger",
    "NodeExplorer",
    "start_repl",
    "render_ast_graph",
    "print_ast_tree",
    "highlight_chunk_boundaries",
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
from .plugin_manager import PluginManager, get_plugin_manager
from .config import ChunkerConfig
from .languages.plugin_base import LanguagePlugin, PluginConfig
from .debug import (
    ASTVisualizer,
    QueryDebugger,
    ChunkDebugger,
    NodeExplorer,
    start_repl,
    render_ast_graph,
    print_ast_tree,
    highlight_chunk_boundaries
)
