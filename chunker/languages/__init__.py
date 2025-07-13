"""
Per‑language helpers live here (e.g. node‑type mappings, heuristics).
"""

from .base import (
    LanguageConfig,
    CompositeLanguageConfig,
    ChunkRule,
    LanguageConfigRegistry,
    language_config_registry,
    validate_language_config,
)

__all__ = [
    "LanguageConfig",
    "CompositeLanguageConfig",
    "ChunkRule",
    "LanguageConfigRegistry",
    "language_config_registry",
    "validate_language_config",
]

# Auto-import language configurations to register them
from . import python  # noqa: F401
