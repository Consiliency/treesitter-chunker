"""
Tree-sitter Chunker Phase 2 - Call Site Extraction Framework.

This package contains the core extraction framework and language-specific
extractors for identifying and extracting function call sites from source code.

Key Components:
- BaseExtractor: Abstract base class for all language extractors
- CallSite: Standardized representation of function call locations
- ExtractionResult: Uniform result format across all extractors
- CommonPatterns: Shared pattern recognition utilities
- ExtractionUtils: Common utility functions

Phase 2 Implementation:
This framework provides the foundation for call site extraction across
multiple programming languages with consistent interfaces and error handling.
"""

from .core.extraction_framework import (
    BaseExtractor,
    CallSite,
    CommonPatterns,
    ExtractionResult,
    ExtractionUtils,
)

__all__ = [
    "BaseExtractor",
    "CallSite",
    "CommonPatterns",
    "ExtractionResult",
    "ExtractionUtils",
]
