"""Text processors for specialized file formats.

This package contains processors for non-code text formats that require
specialized chunking logic beyond tree-sitter AST parsing.
"""

from .base import SpecializedProcessor, TextChunk
from .logs import LogProcessor

__all__ = [
    'SpecializedProcessor',
    'TextChunk',
    'LogProcessor',
]