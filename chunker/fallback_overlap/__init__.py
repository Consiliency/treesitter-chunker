"""Overlapping fallback chunker module for non-Tree-sitter files."""

from .chunker import OverlappingFallbackChunker, OverlapStrategy, TreeSitterOverlapError

__all__ = ["OverlapStrategy", "OverlappingFallbackChunker", "TreeSitterOverlapError"]
