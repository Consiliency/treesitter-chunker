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
from .base import ChunkingStrategy, ASTProcessor
from .query import QueryEngine, QueryBasedChunker, Query, QueryMatch
from .context import ContextExtractor, ContextItem
from .performance import CacheManager, IncrementalParser, ParseCache
from .export import StructuredExporter, RelationshipTracker, ExportFormat
from .grammar import GrammarManager, GrammarInfo
from .fallback import FallbackChunker, FallbackStrategy
from .debug import ASTVisualizer, QueryDebugger

__all__ = [
    # Base interfaces
    'ChunkingStrategy',
    'ASTProcessor',
    
    # Query interfaces
    'QueryEngine',
    'QueryBasedChunker',
    'Query',
    'QueryMatch',
    
    # Context interfaces
    'ContextExtractor',
    'ContextItem',
    
    # Performance interfaces
    'CacheManager',
    'IncrementalParser',
    'ParseCache',
    
    # Export interfaces
    'StructuredExporter',
    'RelationshipTracker',
    'ExportFormat',
    
    # Grammar interfaces
    'GrammarManager',
    'GrammarInfo',
    
    # Fallback interfaces
    'FallbackChunker',
    'FallbackStrategy',
    
    # Debug interfaces
    'ASTVisualizer',
    'QueryDebugger',
]