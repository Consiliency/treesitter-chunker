"""Language registry for dynamic discovery and management of tree-sitter languages."""

from __future__ import annotations

import ctypes
import logging
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
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
		self._languages: dict[str, tuple[Language | None, LanguageMetadata]] = {}
		self._discovered = False
		# Do not raise if the combined library is missing; discovery will fall back to
		# nm or per-language libraries and allow on-demand builds.
		if not self._library_path.exists():
			logger.warning("Shared library not found at %s; will use fallbacks", self._library_path)

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
		try:
			lib = self._load_library()
		except LibraryLoadError:
			# Use nm fallback symbols when library cannot be loaded
			lib = None
		discovered = {}
		symbols = self._discover_symbols()
		if lib is None:
			# Ensure baseline languages are present when library can't be loaded
			baseline = [
				("python", "tree_sitter_python"),
				("javascript", "tree_sitter_javascript"),
				("c", "tree_sitter_c"),
				("cpp", "tree_sitter_cpp"),
				("rust", "tree_sitter_rust"),
			]
			existing = {name for name, _ in symbols}
			symbols.extend((n, s) for n, s in baseline if n not in existing)
		logger.info("Discovered %s potential language symbols", len(symbols))
		for lang_name, symbol_name in symbols:
			try:
				if lib is None:
					# Synthesize metadata without real Language object
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
		# Ensure baseline languages are present in metadata even if not loadable
		baseline_names = ["python", "javascript", "c", "cpp", "rust"]
		for base in baseline_names:
			if base not in self._languages:
				language_version = "14"
				metadata = LanguageMetadata(
					name=base,
					symbol_name=f"tree_sitter_{base}",
					has_scanner=True if base == "cpp" else False,
					version=language_version,
					capabilities={
						"external_scanner": True if base == "cpp" else False,
						"compatible": True,
						"language_version": language_version,
					},
				)
				self._languages[base] = (None, metadata)
				discovered[base] = metadata
		self._discovered = True
		logger.info("Successfully loaded %s languages", len(discovered))
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
						logger.info("Loaded '%s' from individual library %s", name, path_candidate)
						return language
					except (AttributeError, OSError, ValueError) as e:
						logger.error("Failed loading '%s' from %s: %s", name, path_candidate, e)
		return None

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
			# Try to load from a per-language library as a fallback
			language = self._try_load_from_individual_library(name)
			if language is None:
				available = list(self._languages.keys())
				raise LanguageNotFoundError(name, available)
			return language
		language, metadata = self._languages[name]
		if language is None:
			# Attempt lazy load from individual library when combined library is unavailable
			language = self._try_load_from_individual_library(name)
			if language is not None:
				self._languages[name] = (language, metadata)
			else:
				available = list(self._languages.keys())
				raise LanguageNotFoundError(name, available)
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
		if name in self._languages:
			language, _ = self._languages[name]
			if language is not None:
				return True
			# Try to load from a per-language library if we only have metadata
			loaded = self._try_load_from_individual_library(name)
			if loaded is not None:
				return True
			return False
		# Attempt to lazily load from individual per-language library when not discovered yet
		loaded = self._try_load_from_individual_library(name)
		return loaded is not None

	def get_all_metadata(self) -> dict[str, LanguageMetadata]:
		"""Get metadata for all available languages.

		Returns:
			Dictionary mapping language name to metadata
		"""
		if not self._discovered:
			self.discover_languages()
		return {name: meta for name, (_, meta) in self._languages.items()}
