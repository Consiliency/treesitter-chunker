"""
Tree-sitter Chunker - top-level package.
"""

__version__ = "1.0.0"

__all__ = [
    # Core functions
    "get_parser",
    "chunk_file",
    "chunk_text_with_token_limit",
    "chunk_file_with_token_limit",
    "count_chunk_tokens",
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
    "TreeSitterTokenAwareChunker",
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
    # Intelligent fallback
    "IntelligentFallbackChunker",
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
    # Optimization (Phase 10)
    "ChunkOptimizer",
    "ChunkBoundaryAnalyzer",
    "OptimizationMetrics",
    "OptimizationConfig",
    "OptimizationStrategy",
    # Multi-language processing
    "MultiLanguageProcessor",
    "LanguageDetector",
    "ProjectAnalyzer",
    "LanguageRegion",
    "CrossLanguageReference",
    "EmbeddedLanguageType",
    "MultiLanguageProcessorImpl",
    "LanguageDetectorImpl",
    "ProjectAnalyzerImpl",
    # Incremental processing (Phase 10)
    "IncrementalProcessor",
    "ChunkCache",
    "ChangeDetector",
    "IncrementalIndex",
    "ChunkChange",
    "ChunkDiff",
    "CacheEntry",
    "ChangeType",
    "DefaultIncrementalProcessor",
    "DefaultChunkCache",
    "DefaultChangeDetector",
    "SimpleIncrementalIndex",
    # Virtual File System support
    "VirtualFileSystem",
    "LocalFileSystem",
    "InMemoryFileSystem",
    "ZipFileSystem",
    "HTTPFileSystem",
    "CompositeFileSystem",
    "VirtualFile",
    "create_vfs",
    "VFSChunker",
    "chunk_from_url",
    "chunk_from_zip",
    # Garbage Collection tuning
    "GCTuner",
    "MemoryOptimizer",
    "ObjectPool",
    "get_memory_optimizer",
    "tune_gc_for_batch",
    "tune_gc_for_streaming",
    "optimized_gc",
    "gc_disabled",
    # Zero-configuration API (Phase 14)
    "ZeroConfigAPI",
    "AutoChunkResult",
    # Grammar management (Phase 19)
    "GrammarManager",
]

# Analysis tools
from .analysis import ComplexityAnalyzer, CouplingAnalyzer, SemanticAnalyzer

# Zero-configuration API (Phase 14)
from .auto import ZeroConfigAPI
from .cache import ASTCache
from .chunker import (
    chunk_file,
    chunk_file_with_token_limit,
    chunk_text_with_token_limit,
    count_chunk_tokens,
)
from .chunker_config import ChunkerConfig
from .config.profiles import ChunkingProfile, get_profile, list_profiles

# Configuration system for strategies
from .config.strategy_config import StrategyConfig
from .contracts.auto_contract import AutoChunkResult

# Debug tools
from .debug import (
    ASTVisualizer,
    ChunkDebugger,
    NodeExplorer,
    QueryDebugger,
    highlight_chunk_boundaries,
    print_ast_tree,
    render_ast_graph,
    start_repl,
)
from .exceptions import (
    ChunkerError,
    LanguageNotFoundError,
    LibraryNotFoundError,
    ParserError,
)
from .factory import ParserConfig

# Intelligent fallback
from .fallback.intelligent_fallback import IntelligentFallbackChunker

# Overlapping fallback chunker
from .fallback.overlapping import (
    OverlapConfig,
    OverlappingFallbackChunker,
    OverlapStrategy,
)

# Garbage Collection tuning
from .gc_tuning import (
    GCTuner,
    MemoryOptimizer,
    ObjectPool,
    gc_disabled,
    get_memory_optimizer,
    optimized_gc,
    tune_gc_for_batch,
    tune_gc_for_streaming,
)

# Grammar management (Phase 19)
from .grammar_manager import GrammarManager

# Hierarchy features
from .hierarchy import ChunkHierarchyBuilder, HierarchyNavigator
from .incremental import (
    DefaultChangeDetector,
    DefaultChunkCache,
    DefaultIncrementalProcessor,
    SimpleIncrementalIndex,
)
from .interfaces.hierarchy import ChunkHierarchy

# Incremental processing (Phase 10)
from .interfaces.incremental import (
    CacheEntry,
    ChangeDetector,
    ChangeType,
    ChunkCache,
    ChunkChange,
    ChunkDiff,
    IncrementalIndex,
    IncrementalProcessor,
)
from .interfaces.metadata import ComplexityMetrics, SignatureInfo

# Multi-language processing
from .interfaces.multi_language import (
    CrossLanguageReference,
    EmbeddedLanguageType,
    LanguageDetector,
    LanguageRegion,
    MultiLanguageProcessor,
    ProjectAnalyzer,
)

# Optimization (Phase 10)
from .interfaces.optimization import (
    OptimizationConfig,
    OptimizationMetrics,
    OptimizationStrategy,
)

# Advanced query (Phase 10)
from .interfaces.query_advanced import (
    ChunkQueryAdvanced,
    QueryIndexAdvanced,
    QueryResult,
    QueryType,
)

# Repository processing
from .interfaces.repo import (
    FileChunkResult,
    GitAwareProcessor,
    RepoChunkResult,
    RepoProcessor,
)

# Smart context (Phase 10)
from .interfaces.smart_context import (
    ContextCache,
    ContextMetadata,
    ContextStrategy,
    SmartContextProvider,
)
from .languages.plugin_base import LanguagePlugin, PluginConfig

# Metadata extraction
from .metadata import BaseComplexityAnalyzer, BaseMetadataExtractor
from .metadata.languages import (
    JavaScriptComplexityAnalyzer,
    JavaScriptMetadataExtractor,
    PythonComplexityAnalyzer,
    PythonMetadataExtractor,
)
from .multi_language import (
    LanguageDetectorImpl,
    MultiLanguageProcessorImpl,
    ProjectAnalyzerImpl,
)
from .optimization import ChunkBoundaryAnalyzer, ChunkOptimizer
from .parallel import ParallelChunker, chunk_directory_parallel, chunk_files_parallel
from .parser import (
    clear_cache,
    get_language_info,
    get_parser,
    list_languages,
    return_parser,
)
from .plugin_manager import PluginManager, get_plugin_manager
from .query_advanced import (
    AdvancedQueryIndex,
    NaturalLanguageQueryEngine,
    SmartQueryOptimizer,
)
from .repo import (
    GitAwareProcessorImpl,
    GitignoreMatcher,
    RepoProcessorImpl,
    load_gitignore_patterns,
)

# Custom rules
from .rules import (
    BaseCommentBlockRule,
    BaseCustomRule,
    BaseRegexRule,
    ConfigurationBlockRule,
    CopyrightHeaderRule,
    CustomMarkerRule,
    DebugStatementRule,
    DefaultRuleEngine,
    DocstringRule,
    ImportBlockRule,
    LanguageSpecificCommentRule,
    MetadataRule,
    SectionHeaderRule,
    TestAnnotationRule,
    TodoCommentRule,
    get_builtin_rules,
)

# Semantic merging
from .semantic import (
    MergeConfig,
    TreeSitterRelationshipAnalyzer,
    TreeSitterSemanticMerger,
)
from .smart_context import (
    HybridContextStrategy,
    InMemoryContextCache,
    RelevanceContextStrategy,
    TreeSitterSmartContextProvider,
)

# Enhanced chunking strategies
from .strategies import (
    AdaptiveChunker,
    CompositeChunker,
    HierarchicalChunker,
    SemanticChunker,
)
from .streaming import StreamingChunker, chunk_file_streaming

# Token counting integration
from .token import TiktokenCounter, TokenAwareChunker
from .token.chunker import TreeSitterTokenAwareChunker
from .types import CodeChunk

# Virtual File System support
from .vfs import (
    CompositeFileSystem,
    HTTPFileSystem,
    InMemoryFileSystem,
    LocalFileSystem,
    VirtualFile,
    VirtualFileSystem,
    ZipFileSystem,
    create_vfs,
)
from .vfs_chunker import VFSChunker, chunk_from_url, chunk_from_zip
