"""Specialized processors for different file types and content.

This module provides processors for handling various content types
that require specialized chunking strategies beyond basic tree-sitter parsing.
"""

from .base import SpecializedProcessor, ProcessorConfig
from .config import ConfigProcessor

# Import Markdown processor if available
try:
    from .markdown import MarkdownProcessor
    __all__ = ['SpecializedProcessor', 'ProcessorConfig', 'ConfigProcessor', 'MarkdownProcessor']
except ImportError:
    __all__ = ['SpecializedProcessor', 'ProcessorConfig', 'ConfigProcessor']