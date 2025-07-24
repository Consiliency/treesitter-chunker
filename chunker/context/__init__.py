"""Context extraction module for Tree-sitter chunker.

This module provides AST-based context extraction to preserve semantic
meaning when creating code chunks.
"""

from .extractor import BaseContextExtractor
from .factory import ContextFactory
from .filter import BaseContextFilter
from .scope_analyzer import BaseScopeAnalyzer
from .symbol_resolver import BaseSymbolResolver

__all__ = [
    "BaseContextExtractor",
    "BaseContextFilter",
    "BaseScopeAnalyzer",
    "BaseSymbolResolver",
    "ContextFactory",
]
