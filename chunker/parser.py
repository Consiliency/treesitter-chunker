"""Parser module for tree-sitter chunker with dynamic language discovery."""

from __future__ import annotations

import json
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
from .grammar.manager import TreeSitterGrammarManager

if TYPE_CHECKING:
    from tree_sitter import Parser
logger = logging.getLogger(__name__)


class _ParserState:
    """Singleton state holder for parser module."""

    def __init__(self) -> None:
        self.registry: LanguageRegistry | None = None
        self.factory: ParserFactory | None = None
        # Prefer in-package built artifacts when present (for wheels with prebuilt grammars)
        package_build = Path(__file__).parent / "data" / "grammars" / "build"
        combined_lib = package_build / "languages.so"
        self.default_library_path = (
            combined_lib
            if combined_lib.exists()
            else Path(__file__).parent.parent / "build" / "my-languages.so"
        )

    def initialize(self, library_path: Path | None = None) -> None:
        """Lazy initialization of registry and factory.

        Args:
            library_path: Optional path to the compiled library
        """
        if self.registry is None:
            path = library_path or self.default_library_path
            # If the compiled library doesn't exist or fails to load, initialize registry
            # with no shared library so that list_languages() can still function for tests
            # Always initialize the registry; it now tolerates missing combined library
            self.registry = LanguageRegistry(path)
            self.factory = ParserFactory(self.registry)
            languages = self.registry.list_languages()

            logger.info(
                "Initialized parser with %d languages: %s",
                len(languages),
                ", ".join(languages),
            )


_state = _ParserState()


def _initialize(library_path: Path | None = None) -> None:
    """Lazy initialization of registry and factory.

    Args:
        library_path: Optional path to the compiled library
    """
    _state.initialize(library_path)


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
    if _state.factory is None:
        raise ParserError("Parser factory not initialized")
    try:
        # Normalize common aliases
        alias_map = {
            "csharp": "c_sharp",
            "c_sharp": "c_sharp",
            "typescript": "typescript",
            "tsx": "tsx",
        }
        normalized = alias_map.get(language, language)
        return _state.factory.get_parser(normalized, config)
    except LanguageNotFoundError:
        # Attempt on-demand grammar fetch/build for missing language
        try:
            # Load repository URL from config
            sources_path = (
                Path(__file__).parent.parent / "config" / "grammar_sources.json"
            )
            repo_url: str | None = None
            if sources_path.exists():
                with sources_path.open("r", encoding="utf-8") as f:
                    sources = json.load(f)
                    # Handle common alias differences for repo lookup
                    repo_alias_map = {
                        "csharp": "csharp",
                        "c_sharp": "csharp",
                        "typescript": "typescript",
                    }
                    repo_key = repo_alias_map.get(language, language)
                    repo_url = sources.get(repo_key)
            if repo_url:
                gm = TreeSitterGrammarManager()
                if not gm.get_grammar_info(language):
                    gm.add_grammar(language, repo_url)
                # Fetch and build; ignore failures silently so we raise the original error
                if gm.fetch_grammar(language):
                    gm.build_grammar(language)
                    # After building, try again (factory will now be able to load individual lib
                    return _state.factory.get_parser(normalized, config)
        except Exception as e:
            # Fall back to raising the original error, but log for diagnostics in CI
            logger.debug("On-demand grammar build attempt failed: %s", e)
        available = _state.registry.list_languages() if _state.registry else []
        raise LanguageNotFoundError(normalized, available) from None
    except ParserConfigError:
        raise
    except (IndexError, KeyError, SyntaxError) as e:
        logger.error("Failed to get parser for %s: %s", language, e)
        raise ParserError(f"Parser initialization failed: {e}") from e


def list_languages() -> list[str]:
    """List all available languages.

    Returns:
        Sorted list of language names
    """
    _initialize()
    if _state.registry is None:
        raise ParserError("Language registry not initialized")
    return _state.registry.list_languages()


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
    if _state.registry is None:
        raise ParserError("Language registry not initialized")
    return _state.registry.get_metadata(language)


def return_parser(language: str, parser: Parser) -> None:
    """Return a parser to the pool for reuse.

    This can improve performance by reusing parser instances.

    Args:
        language: Language name
        parser: Parser instance to return
    """
    _initialize()
    if _state.factory is None:
        raise ParserError("Parser factory not initialized")
    _state.factory.return_parser(language, parser)


def clear_cache() -> None:
    """Clear the parser cache.

    This forces recreation of parsers on next request.
    """
    _initialize()
    if _state.factory is not None:
        _state.factory.clear_cache()


__all__ = [
    "LanguageMetadata",
    "ParserConfig",
    "clear_cache",
    "get_language_info",
    "get_parser",
    "list_languages",
    "return_parser",
]
