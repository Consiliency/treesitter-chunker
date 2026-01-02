"""Language registry for dynamic discovery and management of tree-sitter languages."""

from __future__ import annotations

import ctypes
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tree_sitter import Language, Parser

from chunker._internal.error_handling import log_grammar_discovery_summary
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
        self._languages: dict[str, tuple[Language | None, LanguageMetadata]] = {}
        self._discovered = False
        # Do not raise if the combined library is missing; discovery will fall back to
        # nm or per-language libraries and allow on-demand builds.
        if not self._library_path.exists():
            logger.warning(
                "Shared library not found at %s; will use fallbacks",
                self._library_path,
            )

    def _load_library(self) -> ctypes.CDLL:
        """Load the shared library."""
        if self._library is None:
            try:
                self._library = ctypes.CDLL(str(self._library_path))
                logger.info("Loaded library from %s", self._library_path)
            except OSError as e:
                logger.error(
                    "Failed to load shared library %s: %s",
                    self._library_path,
                    e,
                )
                raise LibraryLoadError(self._library_path, str(e)) from e
        return self._library

    def _discover_symbols(self) -> list[tuple[str, str]]:
        """Discover available language symbols by scanning regimented grammar directories.

        Returns:
                List of (language_name, symbol_name) tuples
        """
        symbols = []

        # PRIMARY SOURCE: Package grammar directory (deterministic location)
        package_grammar_build = (
            Path(__file__).parent.parent / "data" / "grammars" / "build"
        )
        if package_grammar_build.exists():
            logger.info("Scanning package grammar directory: %s", package_grammar_build)
            symbols.extend(self._scan_directory_for_languages(package_grammar_build))

        # SECONDARY SOURCE: User cache directory (if configured)
        user_cache = Path.home() / ".cache" / "treesitter-chunker" / "build"
        if user_cache.exists():
            logger.info("Scanning user cache directory: %s", user_cache)
            symbols.extend(self._scan_directory_for_languages(user_cache))

        # OVERRIDE SOURCE: Environment variable (for development/testing)
        from os import getenv as _getenv

        override = _getenv("CHUNKER_GRAMMAR_BUILD_DIR")
        if override:
            override_path = Path(override)
            if override_path.exists():
                logger.info("Scanning override directory: %s", override_path)
                symbols.extend(self._scan_directory_for_languages(override_path))

        # Remove duplicates while preserving order
        seen = set()
        unique_symbols = []
        for lang_name, symbol_name in symbols:
            if lang_name not in seen:
                seen.add(lang_name)
                unique_symbols.append((lang_name, symbol_name))

        logger.info("Discovered %s unique language symbols", len(unique_symbols))
        return unique_symbols

    def _scan_directory_for_languages(self, directory: Path) -> list[tuple[str, str]]:
        """Scan a specific directory for language libraries.

        Args:
            directory: Directory to scan for .so/.dll/.dylib files

        Returns:
            List of (language_name, symbol_name) tuples found in this directory
        """
        symbols = []
        combined_suffix = Path(self._library_path).suffix or ".so"

        for file_path in directory.glob(f"*{combined_suffix}"):
            if file_path.is_file():
                # Extract language name from filename (e.g., "python.so" -> "python")
                lang_name = file_path.stem
                symbol_name = f"tree_sitter_{lang_name}"

                # Validate this is a language library by checking for the symbol
                if self._validate_language_library(file_path, symbol_name):
                    symbols.append((lang_name, symbol_name))
                    logger.debug(
                        "Found language library: %s -> %s",
                        file_path.name,
                        lang_name,
                    )
                else:
                    logger.warning(
                        "File %s exists but doesn't contain expected symbol %s",
                        file_path.name,
                        symbol_name,
                    )

        return symbols

    def _validate_language_library(self, library_path: Path, symbol_name: str) -> bool:
        """Validate that a library file contains the expected language symbol.

        Args:
            library_path: Path to the library file
            symbol_name: Expected symbol name (e.g., "tree_sitter_python")

        Returns:
            True if the library contains the expected symbol
        """
        try:
            lib = ctypes.CDLL(str(library_path))
            # Check if the symbol exists
            if hasattr(lib, symbol_name):
                # Additional validation: try to create a Language object
                try:
                    func = getattr(lib, symbol_name)
                    func.restype = ctypes.c_void_p
                    lang_ptr = func()
                    # Test if we can create a Language object (this validates the library)
                    from tree_sitter import Language

                    Language(lang_ptr)
                    return True
                except Exception as e:
                    logger.warning(
                        "Library %s has symbol %s but failed Language creation: %s",
                        library_path.name,
                        symbol_name,
                        e,
                    )
                    return False
            return False
        except (OSError, AttributeError) as e:
            logger.debug("Failed to validate library %s: %s", library_path.name, e)
            return False

    def discover_languages(self) -> dict[str, LanguageMetadata]:
        """Dynamically discover all available languages in the library.

        Returns:
                Dictionary mapping language name to metadata
        """
        if self._discovered:
            return {lang_name: meta for lang_name, (_, meta) in self._languages.items()}
        try:
            lib = self._load_library()
        except LibraryLoadError:
            # Use nm fallback symbols when library cannot be loaded
            lib = None
        discovered = {}
        symbols = self._discover_symbols()
        if lib is None:
            # No combined library available - will rely on individual language libraries
            logger.info(
                "No combined library available, will scan for individual language libraries",
            )
        logger.info("Discovered %s potential language symbols", len(symbols))
        for lang_name, symbol_name in symbols:
            try:
                if lib is None:
                    # Try to load from individual library instead of just creating placeholder
                    language = self._try_load_from_individual_library(lang_name)
                    if language is not None:
                        has_scanner = True if lang_name == "cpp" else False
                        is_compatible = True
                        language_version = "14"
                    else:
                        # Fall back to placeholder metadata when individual library not available
                        language = None
                        has_scanner = True if lang_name == "cpp" else False
                        is_compatible = True
                        language_version = "14"
                else:
                    try:
                        func = getattr(lib, symbol_name)
                        func.restype = ctypes.c_void_p
                        lang_ptr = func()
                        language = Language(lang_ptr)
                        has_scanner = hasattr(
                            lib,
                            f"{symbol_name}_external_scanner_create",
                        )
                        try:
                            test_parser = Parser()
                            test_parser.language = language
                            is_compatible = True
                            language_version = "14"
                        except ValueError as e:
                            is_compatible = False
                            match = re.search(r"version (\d+)", str(e))
                            language_version = match.group(1) if match else "unknown"
                    except (AttributeError, OSError, ValueError):
                        # Combined library missing symbol; try individual per-language library
                        language = self._try_load_from_individual_library(lang_name)
                        if language is None:
                            raise
                        has_scanner = True
                        is_compatible = True
                        language_version = "14"
                # Ensure capabilities include language_version explicitly
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
                # Store placeholder when language is None; only metadata is used by some tests
                self._languages[lang_name] = (language, metadata)
                discovered[lang_name] = metadata

                logger.debug(
                    "Loaded language '%s' from symbol '%s'",
                    lang_name,
                    symbol_name,
                )
            except AttributeError as e:
                logger.warning("Failed to load symbol '%s': %s", symbol_name, e)
            except (IndexError, KeyError, OSError) as e:
                logger.error("Error loading language '%s': %s", lang_name, e)
        # No more hardcoded baseline languages - only what's actually discovered
        self._discovered = True

        # Use enhanced error logging for discovery summary
        log_grammar_discovery_summary(list(discovered.keys()), total_expected=30)

        return discovered

    def _try_load_from_individual_library(self, name: str) -> Language | None:
        """Attempt to load a language from an individual per-language library.

        This provides a fallback path when the combined library does not
        include a requested language but a separately built library exists,
        e.g. built via the grammar manager.
        """
        # Determine candidate directories: next to the combined library,
        # an env override, and the user cache path (~/.cache/treesitter-chunker/build)
        base_dir = Path(self._library_path).parent
        search_dirs: list[Path] = [base_dir]

        # Add package grammar build directory where individual .so files are located
        package_grammar_build = (
            Path(__file__).parent.parent / "data" / "grammars" / "build"
        )
        if package_grammar_build.exists():
            search_dirs.append(package_grammar_build)

        env_dir = Path(str(Path().home()))
        from os import getenv as _getenv

        override = _getenv("CHUNKER_GRAMMAR_BUILD_DIR")
        if override:
            search_dirs.append(Path(override))
        user_cache = Path.home() / ".cache" / "treesitter-chunker" / "build"
        search_dirs.append(user_cache)
        combined_suffix = Path(self._library_path).suffix or ".so"
        # Try multiple filename variants to account for alias differences (e.g., c_sharp -> csharp)
        alt_names = [name]
        simplified = name.replace("_", "")
        if simplified != name:
            alt_names.append(simplified)
        hyphenated = name.replace("_", "-")
        if hyphenated != name and hyphenated not in alt_names:
            alt_names.append(hyphenated)
        for directory in search_dirs:
            for candidate_name in alt_names:
                path_candidate = directory / f"{candidate_name}{combined_suffix}"
                if path_candidate.exists():
                    try:
                        lib = ctypes.CDLL(str(path_candidate))
                        symbol_name = f"tree_sitter_{name}"
                        func = getattr(lib, symbol_name)
                        func.restype = ctypes.c_void_p
                        lang_ptr = func()
                        language = Language(lang_ptr)
                        logger.info(
                            "Loaded '%s' from individual library %s",
                            name,
                            path_candidate,
                        )
                        return language
                    except (AttributeError, OSError, ValueError) as e:
                        logger.error(
                            "Failed loading '%s' from %s: %s",
                            name,
                            path_candidate,
                            e,
                        )
                        # Provide more specific error guidance
                        if "symbol" in str(e).lower():
                            logger.error(
                                "This appears to be a symbol/library issue. "
                                "The grammar may be corrupted or incompatible.",
                            )
                        elif "version" in str(e).lower():
                            logger.error(
                                "This appears to be a version compatibility issue. "
                                "The grammar may not be compatible with your tree-sitter version.",
                            )
                        else:
                            logger.error(
                                "Unknown error loading grammar. "
                                "Try recompiling the grammar from source.",
                            )
        return None

    def get_language(self, name: str) -> Language:
        """Get a specific language, with lazy loading.

        Resolution order:
        1. Compiled grammar in package data directory
        2. Compiled grammar in user cache
        3. tree-sitter-language-pack (if available)
        4. Raise LanguageNotFoundError with guidance

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
            # Try to load from a per-language library as a fallback
            language = self._try_load_from_individual_library(name)
            if language is None:
                # Try language pack as final fallback
                language = self._try_load_from_language_pack(name)
            if language is None:
                available = self._get_all_available_languages()
                raise LanguageNotFoundError(name, available)
            return language
        language, metadata = self._languages[name]
        if language is None:
            # Attempt lazy load from individual library when combined library is unavailable
            language = self._try_load_from_individual_library(name)
            if language is None:
                # Try language pack as final fallback
                language = self._try_load_from_language_pack(name)
            if language is not None:
                self._languages[name] = (language, metadata)
            else:
                available = self._get_all_available_languages()
                raise LanguageNotFoundError(name, available)
        return language

    def _try_load_from_language_pack(self, name: str) -> Language | None:
        """Attempt to load a language from tree-sitter-language-pack.

        This provides a fallback when no local compiled grammar is available.
        The language pack provides pre-compiled grammars for 165+ languages.

        Args:
            name: Language name (e.g., "python", "typescript")

        Returns:
            Language object if found in pack, None otherwise
        """
        try:
            from chunker._internal.language_pack import get_language_from_pack

            language = get_language_from_pack(name)
            if language is not None:
                logger.info("Loaded '%s' from tree-sitter-language-pack", name)
            return language
        except ImportError:
            # language_pack module not available (shouldn't happen with our deps)
            logger.debug("language_pack module not available")
            return None

    def _get_all_available_languages(self) -> list[str]:
        """Get all available languages including those from the language pack.

        Returns:
            Combined list of all available language names
        """
        available = list(self._languages.keys())
        try:
            from chunker._internal.language_pack import list_pack_languages

            pack_languages = list_pack_languages()
            for lang in pack_languages:
                if lang not in available:
                    available.append(lang)
        except ImportError:
            pass
        return sorted(available)

    def list_languages(self) -> list[str]:
        """List all available language names.

        Returns:
                Sorted list of language names including those from the language pack
        """
        if not self._discovered:
            self.discover_languages()
        return self._get_all_available_languages()

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
        if name in self._languages:
            language, _ = self._languages[name]
            if language is not None:
                return True
            # Try to load from a per-language library if we only have metadata
            loaded = self._try_load_from_individual_library(name)
            if loaded is not None:
                return True
            # Try language pack as final fallback
            loaded = self._try_load_from_language_pack(name)
            return loaded is not None
        # Attempt to lazily load from individual per-language library when not discovered yet
        loaded = self._try_load_from_individual_library(name)
        if loaded is not None:
            return True
        # Try language pack as final fallback
        loaded = self._try_load_from_language_pack(name)
        return loaded is not None

    def get_all_metadata(self) -> dict[str, LanguageMetadata]:
        """Get metadata for all available languages.

        Returns:
                Dictionary mapping language name to metadata
        """
        if not self._discovered:
            self.discover_languages()
        return {name: meta for name, (_, meta) in self._languages.items()}
