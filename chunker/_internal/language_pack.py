"""Wrapper for tree-sitter-language-pack integration.

This module provides a fallback source of pre-compiled grammars
via the tree-sitter-language-pack PyPI package. When installed,
it provides immediate access to 165+ languages without requiring
manual grammar compilation.

Resolution order in LanguageRegistry:
1. Compiled grammar in package data directory
2. Compiled grammar in user cache
3. tree-sitter-language-pack (this module)
4. Raise LanguageNotFoundError with guidance
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tree_sitter import Language

logger = logging.getLogger(__name__)

# Cached state to avoid repeated import attempts
_pack_available: bool | None = None
_pack_module: object | None = None


def is_language_pack_available() -> bool:
    """Check if tree-sitter-language-pack is installed and functional.

    Returns:
        True if the language pack is available for use
    """
    global _pack_available, _pack_module

    if _pack_available is not None:
        return _pack_available

    try:
        import tree_sitter_language_pack

        _pack_module = tree_sitter_language_pack
        _pack_available = True
        logger.debug("tree-sitter-language-pack is available")
    except ImportError:
        _pack_available = False
        logger.debug("tree-sitter-language-pack is not installed")

    return _pack_available


def get_language_from_pack(name: str) -> Language | None:
    """Get a language from the tree-sitter-language-pack.

    Args:
        name: Language name (e.g., "python", "typescript")

    Returns:
        tree_sitter.Language object if found, None otherwise
    """
    if not is_language_pack_available():
        return None

    try:
        import tree_sitter_language_pack

        # The pack uses lowercase names, but some have different conventions
        # Try the name as-is first, then try normalization
        lang = tree_sitter_language_pack.get_language(name)
        logger.debug("Loaded language '%s' from language pack", name)
        return lang
    except LookupError:
        # Language not found in the pack
        logger.debug("Language '%s' not found in language pack", name)
        return None
    except Exception as e:
        logger.warning("Error loading '%s' from language pack: %s", name, e)
        return None


def list_pack_languages() -> list[str]:
    """List all languages available in the tree-sitter-language-pack.

    Returns:
        List of available language names, empty if pack not available
    """
    if not is_language_pack_available():
        return []

    try:
        from typing import get_args

        import tree_sitter_language_pack

        # The package exposes SupportedLanguage as a Literal type with all language names
        if hasattr(tree_sitter_language_pack, "SupportedLanguage"):
            return list(get_args(tree_sitter_language_pack.SupportedLanguage))
        # Fallback: try to import and list from the internal module
        if hasattr(tree_sitter_language_pack, "LANGUAGES"):
            return list(tree_sitter_language_pack.LANGUAGES.keys())
        # If we can't list them, return empty list
        logger.debug("Cannot enumerate languages from pack, API not available")
        return []
    except Exception as e:
        logger.warning("Error listing languages from pack: %s", e)
        return []


class LanguagePackProvider:
    """Provider interface for tree-sitter-language-pack.

    This class wraps the language pack functionality to provide
    a consistent interface for the LanguageRegistry.
    """

    def __init__(self) -> None:
        """Initialize the provider."""
        self._available: bool | None = None

    def is_available(self) -> bool:
        """Check if the language pack is available.

        Returns:
            True if the language pack can be used
        """
        if self._available is None:
            self._available = is_language_pack_available()
        return self._available

    def get_language(self, name: str) -> Language | None:
        """Get a language from the pack.

        Args:
            name: Language name

        Returns:
            Language object if found, None otherwise
        """
        return get_language_from_pack(name)

    def list_languages(self) -> list[str]:
        """List available languages.

        Returns:
            List of language names
        """
        return list_pack_languages()
