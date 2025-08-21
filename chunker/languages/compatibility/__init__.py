"""Compatibility database system for Phase 1.7.

This package provides version compatibility management between:
- Language versions (Python 3.8, JavaScript ES2020, etc.)
- Tree-sitter grammar versions
- Breaking changes between versions
- Compatibility rules and constraints

Components:
- schema: Data models and validation
- grammar_analyzer: Analyzes compiled grammar files
- database: SQLite database for persistence and queries
"""

from .database import CompatibilityDatabase, DatabaseManager
from .grammar_analyzer import FeatureDetector, GrammarAnalyzer, GrammarMetadataExtractor
from .schema import (
    BreakingChange,
    CompatibilityLevel,
    CompatibilityRule,
    CompatibilitySchema,
    GrammarVersion,
    LanguageVersion,
    VersionConstraint,
)

__all__ = [
    "BreakingChange",
    # Database classes
    "CompatibilityDatabase",
    # Schema classes
    "CompatibilityLevel",
    "CompatibilityRule",
    "CompatibilitySchema",
    "DatabaseManager",
    "FeatureDetector",
    # Analyzer classes
    "GrammarAnalyzer",
    "GrammarMetadataExtractor",
    "GrammarVersion",
    "LanguageVersion",
    "VersionConstraint",
]

# Version of this module
__version__ = "1.0.0"
