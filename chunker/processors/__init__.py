"""Specialized processors for different file types and content.

This module provides processors for handling various content types
that require specialized chunking strategies beyond basic tree-sitter parsing.
"""

from .base import ProcessorConfig, SpecializedProcessor, TextChunk
from .config import ConfigProcessor
from .logs import LogProcessor
from .markdown import MarkdownProcessor

# Import other processors if available
try:

    _has_markdown = True
except ImportError:
    _has_markdown = False

try:

    _has_logs = True
except ImportError:
    _has_logs = False

# Build __all__ dynamically
__all__ = ["ConfigProcessor", "ProcessorConfig", "SpecializedProcessor", "TextChunk"]
if _has_markdown:
    __all__.append("MarkdownProcessor")
if _has_logs:
    __all__.append("LogProcessor")
