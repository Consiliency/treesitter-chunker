"""Context extraction module for Tree-sitter chunker.

This module provides AST-based context extraction to preserve semantic
meaning when creating code chunks.
"""

from .extractor import BaseContextExtractor
from .symbol_resolver import BaseSymbolResolver
from .scope_analyzer import BaseScopeAnalyzer
from .filter import BaseContextFilter
from .factory import ContextFactory

__all__ = [
    'BaseContextExtractor',
    'BaseSymbolResolver',
    'BaseScopeAnalyzer',
    'BaseContextFilter',
    'ContextFactory',
]