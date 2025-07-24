"""Fallback chunking module for files without Tree-sitter support.

This module provides last-resort chunking strategies for files that cannot
be parsed by Tree-sitter. It should only be used when no grammar is available.

The module always emits warnings to encourage users to use Tree-sitter grammars
whenever possible.
"""

from .base import FallbackChunker, FallbackWarning
from .detection.file_type import FileTypeDetector
from .sliding_window_fallback import (
    GenericSlidingWindowProcessor,
    ProcessorChain,
    ProcessorInfo,
    ProcessorRegistry,
    ProcessorType,
    SlidingWindowFallback,
    TextProcessor,
)
from .strategies.line_based import LineBasedChunker
from .strategies.log_chunker import LogChunker
from .strategies.markdown import MarkdownChunker

__all__ = [
    "FallbackChunker",
    "FallbackWarning",
    "FileTypeDetector",
    "GenericSlidingWindowProcessor",
    "LineBasedChunker",
    "LogChunker",
    "MarkdownChunker",
    "ProcessorChain",
    "ProcessorInfo",
    "ProcessorRegistry",
    "ProcessorType",
    "SlidingWindowFallback",
    "TextProcessor",
]
