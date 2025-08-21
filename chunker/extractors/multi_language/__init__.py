"""
Multi-language extractors for Phase 2 call site extraction.

This module provides extractors for Go, C, C++, Java, and other languages.
"""

from .multi_extractor import (
    CExtractor,
    CPatterns,
    CppExtractor,
    CppPatterns,
    GenericPatterns,
    GoExtractor,
    GoPatterns,
    JavaExtractor,
    JavaPatterns,
    OtherLanguagesExtractor,
)

__all__ = [
    "CExtractor",
    "CPatterns",
    "CppExtractor",
    "CppPatterns",
    "GenericPatterns",
    "GoExtractor",
    "GoPatterns",
    "JavaExtractor",
    "JavaPatterns",
    "OtherLanguagesExtractor",
]
