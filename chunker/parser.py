"""Parser module for tree-sitter chunker with dynamic language discovery."""

from __future__ import annotations

import logging
import threading
from pathlib import Path
from typing import TYPE_CHECKING

from ._internal.factory import ParserConfig, ParserFactory, ParserLease
from ._internal.registry import (
    LanguageMetadata,
    LanguageRegistry,
    default_library_path,
)
from ._internal.trusted_artifacts import load_user_config_pins
from .exceptions import (
    LanguageNotFoundError,
    ParserConfigError,
    ParserError,
    ParserInitError,
    TrustedArtifactsError,
)

if TYPE_CHECKING:
    from tree_sitter import Parser

logger = logging.getLogger(__name__)

__all__ = [
    "ParserConfig",
    "ParserLease",
    "acquire_parser",
    "clear_cache",
    "get_language_info",
    "get_parser",
    "list_languages",
    "return_parser",
]


class _ParserState:
    """Singleton state holder for parser module."""

    def __init__(self) -> None:
        self.registry: LanguageRegistry | None = None
        self.factory: ParserFactory | None = None
        self._init_lock = threading.Lock()
        self._pin_warning_emitted = False
        # Prefer in-package built artifacts when present (for wheels with prebuilt grammars)
        self.default_library_path = default_library_path()

    def _user_config_pins(
        self, library_path: Path
    ) -> tuple[dict[str, dict[str, str]] | None, str | None]:
        """Read the user-config pin file once; a defective file grants no trust."""
        try:
            return load_user_config_pins(library_path=library_path), None
        except TrustedArtifactsError as error:
            if not self._pin_warning_emitted:
                self._pin_warning_emitted = True
                logger.warning(
                    "%s. It grants no local trust: package-supplied grammars "
                    "keep working and local grammars that need a pin are not used.",
                    error,
                )
            return None, str(error)

    def initialize(self, library_path: Path | None = None) -> None:
        """Lazy initialization of registry and factory.

        Args:
            library_path: Optional path to the compiled library
        """
        # Guard the whole init under a lock and use `factory` (set LAST) as the
        # initialized sentinel, so a concurrent cold-start thread can never observe
        # registry-set-but-factory-None and fail with "factory not initialized".
        if self.factory is not None:
            return
        with self._init_lock:
            # Double-checked locking: another thread may have initialized the
            # factory between the first check and acquiring the lock. mypy narrows
            # self.factory to None from the check above (it assumes single-thread)
            # and flags this re-check as unreachable — but it is load-bearing.
            if self.factory is not None:
                return  # type: ignore[unreachable]
            path = library_path or self.default_library_path
            # If the compiled library doesn't exist or fails to load, initialize registry
            # with no shared library so that list_languages() can still function for tests
            # Always initialize the registry; it now tolerates missing combined library
            # The parse path is the only reader of the user-config pin file;
            # it is read once, when this registry is built.
            pins, defect = self._user_config_pins(path)
            registry = LanguageRegistry(path, trusted_artifacts=pins)
            registry._pin_file_defect = defect
            factory = ParserFactory(registry)
            self.registry = registry
            self.factory = factory  # published last; the sentinel above gates on it
            languages = registry.list_languages()

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
        # Normalize common aliases - use "csharp" as canonical since tree-sitter-language-pack uses it
        alias_map = {
            "csharp": "csharp",
            "c_sharp": "csharp",
            "typescript": "typescript",
            "tsx": "tsx",
        }
        normalized = alias_map.get(language, language)
        return _state.factory.get_parser(normalized, config)
    except LanguageNotFoundError:
        if normalized in {"python", "javascript"}:
            raise ParserInitError(
                normalized,
                f"Required tree-sitter-{normalized}==0.25.0 is unavailable; reinstall the declared grammar distribution.",
            ) from None
        # On-demand fetch-and-build is retired (treesitter-chunker#362, F1):
        # a miss never clones or compiles a grammar.
        raise
    except ParserConfigError:
        raise
    except (IndexError, KeyError, SyntaxError) as e:
        logger.error("Failed to get parser for %s: %s", language, e)
        raise ParserError(f"Parser initialization failed: {e}") from e


def acquire_parser(language: str, config: ParserConfig | None = None) -> ParserLease:
    """Exclusively lease a parser for the duration of a context manager.

    The leased parser is not available to another lease until the context exits.
    Prefer this API for work that needs a parser only temporarily.
    """
    _initialize()
    if _state.factory is None:
        raise ParserError("Parser factory not initialized")
    alias_map = {
        "csharp": "csharp",
        "c_sharp": "csharp",
        "typescript": "typescript",
        "tsx": "tsx",
    }
    normalized = alias_map.get(language, language)
    try:
        return _state.factory.acquire_parser(normalized, config)
    except LanguageNotFoundError:
        if normalized in {"python", "javascript"}:
            raise ParserInitError(
                normalized,
                f"Required tree-sitter-{normalized}==0.25.0 is unavailable; reinstall the declared grammar distribution.",
            ) from None
        # On-demand fetch-and-build is retired (treesitter-chunker#362, F1).
        raise


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
    try:
        return _state.registry.get_metadata(language)
    except LanguageNotFoundError:
        if language in {"python", "javascript"}:
            raise ParserInitError(
                language,
                f"Required tree-sitter-{language}==0.25.0 is unavailable; reinstall the declared grammar distribution.",
            ) from None
        raise


def return_parser(language: str, parser: Parser) -> None:
    """Keep the legacy return call safe for thread-owned parser instances.

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
    "ParserLease",
    "acquire_parser",
    "clear_cache",
    "get_language_info",
    "get_parser",
    "list_languages",
    "return_parser",
]
