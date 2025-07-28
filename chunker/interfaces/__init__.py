"""Interface definitions for tree-sitter chunker Phase 8 features.

This package contains abstract base classes that define contracts for
parallel development in separate worktrees. All implementations should
inherit from these interfaces to ensure compatibility.

Key Interfaces:
- ChunkingStrategy: Base for all chunking approaches
- QueryEngine: Tree-sitter query support
- ContextExtractor: AST-based context extraction
- CacheManager: Performance optimization
- StructuredExporter: Export with relationships
- GrammarManager: Language grammar management
- FallbackChunker: Non-AST fallback support
- ASTVisualizer: Debugging and visualization
"""

# Import all interfaces for easy access
from .base import ASTProcessor, ChunkingStrategy
from .context import ContextExtractor, ContextItem
from .debug import ASTVisualizer, QueryDebugger
from .export import ExportFormat, RelationshipTracker, StructuredExporter
from .fallback import FallbackChunker, FallbackStrategy
from .grammar import GrammarInfo, GrammarManager
from .performance import CacheManager, IncrementalParser, ParseCache
from .query import Query, QueryBasedChunker, QueryEngine, QueryMatch

__all__ = [
    "ASTProcessor",
    # Debug interfaces
    "ASTVisualizer",
    # Performance interfaces
    "CacheManager",
    # Base interfaces
    "ChunkingStrategy",
    # Context interfaces
    "ContextExtractor",
    "ContextItem",
    "ExportFormat",
    # Fallback interfaces
    "FallbackChunker",
    "FallbackStrategy",
    "GrammarInfo",
    # Grammar interfaces
    "GrammarManager",
    "IncrementalParser",
    "ParseCache",
    "Query",
    "QueryBasedChunker",
    "QueryDebugger",
    # Query interfaces
    "QueryEngine",
    "QueryMatch",
    "RelationshipTracker",
    # Export interfaces
    "StructuredExporter",
]
