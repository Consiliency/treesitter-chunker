"""Language registry for dynamic discovery and management of tree-sitter languages."""

from __future__ import annotations

import ctypes
import logging
import re
import subprocess
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tree_sitter import Language, Parser

from chunker.exceptions import (
    LanguageNotFoundError,
    LibraryLoadError,
    LibraryNotFoundError,
)

if TYPE_CHECKING:
    from pathlib import Path
logger = logging.getLogger(__name__)


@dataclass
class LanguageMetadata:
    """Metadata about a tree-sitter language."""

    name: str
    version: str = "unknown"
    node_types_count: int = 0
    has_scanner: bool = False
    symbol_name: str = ""
    capabilities: dict[str, Any] = field(default_factory=dict)


class LanguageRegistry:
    """Registry for discovering and managing tree-sitter languages."""

    def __init__(self, library_path: Path):
        """Initialize the registry with a path to the compiled language library.

        Args:
            library_path: Path to the .so/.dll/.dylib file containing languages
        """
        self._library_path = library_path
        self._library: ctypes.CDLL | None = None
        self._languages: dict[str, tuple[Language, LanguageMetadata]] = {}
        self._discovered = False
        if not self._library_path.exists():
            raise LibraryNotFoundError(self._library_path)

    def _load_library(self) -> ctypes.CDLL:
        """Load the shared library."""
        if self._library is None:
            try:
                self._library = ctypes.CDLL(str(self._library_path))
                logger.info("Loaded library from %s", self._library_path)
            except OSError as e:
                raise LibraryLoadError(self._library_path, str(e)) from e
        return self._library

    def _discover_symbols(self) -> list[tuple[str, str]]:
        """Discover available language symbols in the library.

        Returns:
            List of (language_name, symbol_name) tuples
        """
        symbols = []
        try:
            result = subprocess.run(
                ["nm", "-D", str(self._library_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    match = re.match(r".*\s+T\s+(tree_sitter_(\w+))$", line)
                    if match:
                        symbol_name = match.group(1)
                        lang_name = match.group(2)
                        if not any(
                            suffix in symbol_name
                            for suffix in ["_external_scanner", "_serialization"]
                        ):
                            symbols.append((lang_name, symbol_name))
            else:
                logger.warning("nm command failed, using fallback language list")
                for lang in ["python", "rust", "javascript", "c", "cpp"]:
                    symbol_name = f"tree_sitter_{lang}"
                    symbols.append((lang, symbol_name))
        except FileNotFoundError:
            logger.warning(
                "nm command not found, using fallback language list",
            )
            for lang in ["python", "rust", "javascript", "c", "cpp"]:
                symbol_name = f"tree_sitter_{lang}"
                symbols.append((lang, symbol_name))
        return symbols

    def discover_languages(self) -> dict[str, LanguageMetadata]:
        """Dynamically discover all available languages in the library.

        Returns:
            Dictionary mapping language name to metadata
        """
        if self._discovered:
            return {lang_name: meta for lang_name, (_, meta) in self._languages.items()}
        lib = self._load_library()
        discovered = {}
        symbols = self._discover_symbols()
        logger.info("Discovered %s potential language symbols", len(symbols))
        for lang_name, symbol_name in symbols:
            try:
                func = getattr(lib, symbol_name)
                func.restype = ctypes.c_void_p
                lang_ptr = func()
                language = Language(lang_ptr)
                has_scanner = hasattr(lib, f"{symbol_name}_external_scanner_create")
                try:
                    test_parser = Parser()
                    test_parser.language = language
                    is_compatible = True
                    language_version = "14"
                except ValueError as e:
                    is_compatible = False
                    match = re.search(r"version (\\d+)", str(e))
                    language_version = match.group(1) if match else "unknown"
                metadata = LanguageMetadata(
                    name=lang_name,
                    symbol_name=symbol_name,
                    has_scanner=has_scanner,
                    version=language_version,
                    capabilities={
                        "external_scanner": has_scanner,
                        "compatible": is_compatible,
                        "language_version": language_version,
                    },
                )
                self._languages[lang_name] = language, metadata
                discovered[lang_name] = metadata

                logger.debug(
                    "Loaded language '%s' from symbol '%s'",
                    lang_name,
                    symbol_name,
                )
            except AttributeError as e:
                logger.warning("Failed to load symbol '%s': %s", symbol_name, e)
            except (IndexError, KeyError) as e:
                logger.error("Error loading language '%s': %s", lang_name, e)
        self._discovered = True
        logger.info("Successfully loaded %s languages", len(discovered))
        return discovered

    def get_language(self, name: str) -> Language:
        """Get a specific language, with lazy loading.

        Args:
            name: Language name (e.g., 'python', 'rust')

        Returns:
            Tree-sitter Language instance

        Raises:
            LanguageNotFoundError: If language is not available
            LanguageLoadError: If language fails to load
        """
        if not self._discovered:
            self.discover_languages()
        if name not in self._languages:
            available = list(self._languages.keys())
            raise LanguageNotFoundError(name, available)
        language, _ = self._languages[name]
        return language

    def list_languages(self) -> list[str]:
        """List all available language names.

        Returns:
            Sorted list of language names
        """
        if not self._discovered:
            self.discover_languages()
        return sorted(self._languages.keys())

    def get_metadata(self, name: str) -> LanguageMetadata:
        """Get metadata for a specific language.

        Args:
            name: Language name

        Returns:
            Language metadata

        Raises:
            LanguageNotFoundError: If language is not available
        """
        if not self._discovered:
            self.discover_languages()
        if name not in self._languages:
            available = list(self._languages.keys())
            raise LanguageNotFoundError(name, available)
        _, metadata = self._languages[name]
        return metadata

    def has_language(self, name: str) -> bool:
        """Check if a language is available.

        Args:
            name: Language name

        Returns:
            True if language is available
        """
        if not self._discovered:
            self.discover_languages()
        return name in self._languages

    def get_all_metadata(self) -> dict[str, LanguageMetadata]:
        """Get metadata for all available languages.

        Returns:
            Dictionary mapping language name to metadata
        """
        if not self._discovered:
            self.discover_languages()
        return {name: meta for name, (_, meta) in self._languages.items()}
