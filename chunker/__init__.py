"""
Tree-sitter Chunker - top-level package.
"""

__version__ = "1.0.0"

__all__ = [
    "ASTCache",
    # Debug tools
    "ASTVisualizer",
    "AdaptiveChunker",
    "AdvancedQueryIndex",
    "AutoChunkResult",
    "BaseCommentBlockRule",
    "BaseComplexityAnalyzer",
    # Custom rules
    "BaseCustomRule",
    # Metadata extraction
    "BaseMetadataExtractor",
    "BaseRegexRule",
    "CacheEntry",
    "ChangeDetector",
    "ChangeType",
    "ChunkBoundaryAnalyzer",
    "ChunkCache",
    "ChunkChange",
    "ChunkDebugger",
    "ChunkDiff",
    "ChunkHierarchy",
    # Hierarchy features
    "ChunkHierarchyBuilder",
    # Optimization (Phase 10)
    "ChunkOptimizer",
    # Advanced query (Phase 10)
    "ChunkQueryAdvanced",
    "ChunkerConfig",
    # Exceptions
    "ChunkerError",
    "ChunkingProfile",
    "CodeChunk",
    # Analysis tools
    "ComplexityAnalyzer",
    "ComplexityMetrics",
    "CompositeChunker",
    "CompositeFileSystem",
    "ConfigurationBlockRule",
    "ContextCache",
    "ContextMetadata",
    "ContextStrategy",
    "CopyrightHeaderRule",
    "CouplingAnalyzer",
    "CrossLanguageReference",
    "CustomMarkerRule",
    "DebugStatementRule",
    "DefaultChangeDetector",
    "DefaultChunkCache",
    "DefaultIncrementalProcessor",
    "DefaultRuleEngine",
    "DocstringRule",
    "EmbeddedLanguageType",
    "FileChunkResult",
    # Garbage Collection tuning
    "GCTuner",
    "GitAwareProcessor",
    "GitAwareProcessorImpl",
    "GitignoreMatcher",
    # Phase 19 components
    "GrammarManager",
    "HTTPFileSystem",
    "HierarchicalChunker",
    "HierarchyNavigator",
    "HybridContextStrategy",
    "ImportBlockRule",
    "InMemoryContextCache",
    "InMemoryFileSystem",
    "IncrementalIndex",
    # Incremental processing (Phase 10)
    "IncrementalProcessor",
    # Intelligent fallback
    "IntelligentFallbackChunker",
    "JavaScriptComplexityAnalyzer",
    "JavaScriptMetadataExtractor",
    "LanguageDetector",
    "LanguageDetectorImpl",
    "LanguageNotFoundError",
    "LanguagePlugin",
    "LanguageRegion",
    "LanguageSpecificCommentRule",
    "LibraryNotFoundError",
    "LocalFileSystem",
    "MemoryOptimizer",
    "MergeConfig",
    "MetadataRule",
    # Multi-language processing
    "MultiLanguageProcessor",
    "MultiLanguageProcessorImpl",
    "NaturalLanguageQueryEngine",
    "NodeExplorer",
    "ObjectPool",
    "OptimizationConfig",
    "OptimizationMetrics",
    "OptimizationStrategy",
    "OverlapConfig",
    "OverlapStrategy",
    # Overlapping fallback chunker
    "OverlappingFallbackChunker",
    "ParallelChunker",
    # Configuration
    "ParserConfig",
    "ParserError",
    "PluginConfig",
    # Plugin system
    "PluginManager",
    "ProjectAnalyzer",
    "ProjectAnalyzerImpl",
    "PythonComplexityAnalyzer",
    "PythonMetadataExtractor",
    "QueryDebugger",
    "QueryIndexAdvanced",
    "QueryResult",
    "QueryType",
    "RelevanceContextStrategy",
    "RepoChunkResult",
    # Repository processing
    "RepoProcessor",
    "RepoProcessorImpl",
    "SectionHeaderRule",
    "SemanticAnalyzer",
    # Enhanced chunking strategies
    "SemanticChunker",
    "SignatureInfo",
    "SimpleIncrementalIndex",
    # Smart context (Phase 10)
    "SmartContextProvider",
    "SmartQueryOptimizer",
    # Configuration system
    "StrategyConfig",
    "StreamingChunker",
    "TemplateGenerator",
    "TestAnnotationRule",
    # Token counting integration
    "TiktokenCounter",
    "TodoCommentRule",
    "TokenAwareChunker",
    # Semantic merging
    "TreeSitterRelationshipAnalyzer",
    "TreeSitterSemanticMerger",
    "TreeSitterSmartContextProvider",
    "TreeSitterTokenAwareChunker",
    "VFSChunker",
    "VirtualFile",
    # Virtual File System support
    "VirtualFileSystem",
    # Zero-configuration API (Phase 14)
    "ZeroConfigAPI",
    "ZipFileSystem",
    "chunk_directory_parallel",
    "chunk_file",
    # Performance features
    "chunk_file_streaming",
    "chunk_file_with_token_limit",
    "chunk_files_parallel",
    "chunk_from_url",
    "chunk_from_zip",
    "chunk_text",
    "chunk_text_with_token_limit",
    "clear_cache",
    "count_chunk_tokens",
    "create_vfs",
    "gc_disabled",
    "get_builtin_rules",
    "get_language_info",
    "get_memory_optimizer",
    # Core functions
    "get_parser",
    "get_plugin_manager",
    "get_profile",
    "highlight_chunk_boundaries",
    # New parser API
    "list_languages",
    "list_profiles",
    "load_gitignore_patterns",
    "optimized_gc",
    "print_ast_tree",
    "render_ast_graph",
    "return_parser",
    "start_repl",
    "tune_gc_for_batch",
    "tune_gc_for_streaming",
]

# Analysis tools
from .analysis import ComplexityAnalyzer, CouplingAnalyzer, SemanticAnalyzer

# Zero-configuration API (Phase 14)
from .auto import ZeroConfigAPI
from .cache import ASTCache
from .chunker import (
    chunk_file,
    chunk_file_with_token_limit,
    chunk_text,
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

# Template Generator (Phase 19)
from .template_generator import TemplateGenerator

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
