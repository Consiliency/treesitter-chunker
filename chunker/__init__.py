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
    # Debug tools
    "ASTVisualizer",
    "QueryDebugger",
    "ChunkDebugger",
    "NodeExplorer",
    "start_repl",
    "render_ast_graph",
    "print_ast_tree",
    "highlight_chunk_boundaries",
    # Token counting integration
    "TiktokenCounter",
    "TokenAwareChunker",
    # Hierarchy features
    "ChunkHierarchyBuilder",
    "HierarchyNavigator",
    "ChunkHierarchy",
    # Custom rules
    "BaseCustomRule",
    "BaseRegexRule",
    "BaseCommentBlockRule",
    "MetadataRule",
    "DefaultRuleEngine",
    "TodoCommentRule",
    "CopyrightHeaderRule",
    "DocstringRule",
    "ImportBlockRule",
    "CustomMarkerRule",
    "SectionHeaderRule",
    "ConfigurationBlockRule",
    "LanguageSpecificCommentRule",
    "DebugStatementRule",
    "TestAnnotationRule",
    "get_builtin_rules",
    # Metadata extraction
    "BaseMetadataExtractor",
    "BaseComplexityAnalyzer",
    "PythonMetadataExtractor",
    "PythonComplexityAnalyzer",
    "JavaScriptMetadataExtractor",
    "JavaScriptComplexityAnalyzer",
    "SignatureInfo",
    "ComplexityMetrics",
    # Repository processing
    "RepoProcessor",
    "GitAwareProcessor",
    "RepoProcessorImpl",
    "GitAwareProcessorImpl",
    "FileChunkResult",
    "RepoChunkResult",
    "GitignoreMatcher",
    "load_gitignore_patterns",
    # Semantic merging
    "TreeSitterRelationshipAnalyzer",
    "TreeSitterSemanticMerger",
    "MergeConfig",
    # Overlapping fallback chunker
    "OverlappingFallbackChunker",
    "OverlapStrategy",
    "OverlapConfig",
    # Smart context (Phase 10)
    "SmartContextProvider",
    "TreeSitterSmartContextProvider",
    "ContextMetadata",
    "ContextStrategy",
    "RelevanceContextStrategy",
    "HybridContextStrategy",
    "ContextCache",
    "InMemoryContextCache",
    # Advanced query (Phase 10)
    "ChunkQueryAdvanced",
    "NaturalLanguageQueryEngine",
    "QueryIndexAdvanced",
    "AdvancedQueryIndex",
    "SmartQueryOptimizer",
    "QueryType",
    "QueryResult",
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
from .chunker_config import ChunkerConfig
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

# Debug tools
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

# Token counting integration
from .token import TiktokenCounter, TokenAwareChunker

# Hierarchy features
from .hierarchy import ChunkHierarchyBuilder, HierarchyNavigator
from .interfaces.hierarchy import ChunkHierarchy

# Custom rules
from .rules import (
    BaseCustomRule,
    BaseRegexRule,
    BaseCommentBlockRule,
    MetadataRule,
    DefaultRuleEngine,
    TodoCommentRule,
    CopyrightHeaderRule,
    DocstringRule,
    ImportBlockRule,
    CustomMarkerRule,
    SectionHeaderRule,
    ConfigurationBlockRule,
    LanguageSpecificCommentRule,
    DebugStatementRule,
    TestAnnotationRule,
    get_builtin_rules
)

# Metadata extraction
from .metadata import (
    BaseMetadataExtractor,
    BaseComplexityAnalyzer
)
from .metadata.languages import (
    PythonMetadataExtractor,
    PythonComplexityAnalyzer,
    JavaScriptMetadataExtractor,
    JavaScriptComplexityAnalyzer
)
from .interfaces.metadata import (
    SignatureInfo,
    ComplexityMetrics
)

# Repository processing
from .interfaces.repo import (
    RepoProcessor,
    GitAwareProcessor,
    FileChunkResult,
    RepoChunkResult
)
from .repo import (
    RepoProcessorImpl,
    GitAwareProcessorImpl,
    GitignoreMatcher,
    load_gitignore_patterns
)

# Semantic merging
from .semantic import (
    TreeSitterRelationshipAnalyzer,
    TreeSitterSemanticMerger,
    MergeConfig
)

# Overlapping fallback chunker
from .fallback.overlapping import (
    OverlappingFallbackChunker,
    OverlapStrategy,
    OverlapConfig
)

# Smart context (Phase 10)
from .interfaces.smart_context import (
    SmartContextProvider,
    ContextMetadata,
    ContextStrategy,
    ContextCache
)
from .smart_context import (
    TreeSitterSmartContextProvider,
    RelevanceContextStrategy,
    HybridContextStrategy,
    InMemoryContextCache
)

# Advanced query (Phase 10)
from .interfaces.query_advanced import (
    ChunkQueryAdvanced,
    QueryIndexAdvanced,
    QueryType,
    QueryResult
)
from .query_advanced import (
    NaturalLanguageQueryEngine,
    AdvancedQueryIndex,
    SmartQueryOptimizer
)
