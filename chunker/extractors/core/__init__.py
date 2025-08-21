"""
Core extraction framework for Phase 2 call site extraction.

This module provides the foundational classes and utilities that all
language-specific extractors will inherit from and use.
"""

from .extraction_framework import (
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
