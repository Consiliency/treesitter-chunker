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
    # Enhanced chunking strategies
    "SemanticChunker",
    "HierarchicalChunker",
    "AdaptiveChunker",
    "CompositeChunker",
    # Analysis tools
    "ComplexityAnalyzer",
    "CouplingAnalyzer",
    "SemanticAnalyzer",
    # Configuration system
    "StrategyConfig",
    "ChunkingProfile",
    "get_profile",
    "list_profiles",
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

# Enhanced chunking strategies
from .strategies import (
    SemanticChunker,
    HierarchicalChunker,
    AdaptiveChunker,
    CompositeChunker
)

# Analysis tools
from .analysis import (
    ComplexityAnalyzer,
    CouplingAnalyzer,
    SemanticAnalyzer
)

# Configuration system for strategies
from .config.strategy_config import StrategyConfig
from .config.profiles import ChunkingProfile, get_profile, list_profiles
