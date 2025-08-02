"""Parser module for tree-sitter chunker with dynamic language discovery."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from ._internal.factory import ParserConfig, ParserFactory
from ._internal.registry import LanguageMetadata, LanguageRegistry
from .exceptions import (
    LanguageNotFoundError,
    LibraryNotFoundError,
    ParserConfigError,
    ParserError,
)

if TYPE_CHECKING:
    from tree_sitter import Parser

# Module-level logger
logger = logging.getLogger(__name__)

# Singleton instances
_registry: LanguageRegistry | None = None
_factory: ParserFactory | None = None

# Default library path
_DEFAULT_LIBRARY_PATH = Path(__file__).parent.parent / "build" / "my-languages.so"


def _initialize(library_path: Path | None = None) -> None:
    """Lazy initialization of registry and factory.

    Args:
        library_path: Optional path to the compiled library
    """
    global _registry, _factory

    if _registry is None:
        path = library_path or _DEFAULT_LIBRARY_PATH
        if not path.exists():
            raise LibraryNotFoundError(path)

        _registry = LanguageRegistry(path)
        _factory = ParserFactory(_registry)

        # Log discovered languages
        languages = _registry.list_languages()
        logger.info(
            "Initialized parser with %d languages: %s",
            len(languages),
            ", ".join(languages),
        )


def get_parser(language: str, config: ParserConfig | None = None) -> Parser:
    """Get a parser for the specified language with optional configuration.

    Args:
        language: Language name (e.g., 'python', 'rust')
        config: Optional parser configuration

    Returns:
        Configured Parser instance

    Raises:
        LanguageNotFoundError: If language is not available
        ParserError: If parser initialization fails
    """
    _initialize()

    try:
        return _factory.get_parser(language, config)
    except LanguageNotFoundError:
        # Re-raise with available languages
        available = _registry.list_languages()
        raise LanguageNotFoundError(language, available)
    except ParserConfigError:
        # Re-raise config errors as-is
        raise
    except (IndexError, KeyError, SyntaxError) as e:
        logger.error("Failed to get parser for %s: %s", language, e)
        raise ParserError(f"Parser initialization failed: {e}")


def list_languages() -> list[str]:
    """List all available languages.

    Returns:
        Sorted list of language names
    """
    _initialize()
    return _registry.list_languages()


def get_language_info(language: str) -> LanguageMetadata:
    """Get metadata about a specific language.

    Args:
        language: Language name

    Returns:
        Language metadata

    Raises:
        LanguageNotFoundError: If language is not available
    """
    _initialize()
    return _registry.get_metadata(language)


def return_parser(language: str, parser: Parser) -> None:
    """Return a parser to the pool for reuse.

    This can improve performance by reusing parser instances.

    Args:
        language: Language name
        parser: Parser instance to return
    """
    _initialize()
    _factory.return_parser(language, parser)


def clear_cache() -> None:
    """Clear the parser cache.

    This forces recreation of parsers on next request.
    """
    _initialize()
    _factory.clear_cache()


# Maintain backward compatibility with old imports
# Users can still do: from chunker.parser import get_parser
# and it will work with the new implementation
__all__ = [
    "LanguageMetadata",
    "ParserConfig",
    "clear_cache",
    "get_language_info",
    "get_parser",
    "list_languages",
    "return_parser",
]
