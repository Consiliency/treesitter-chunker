"""Grammar manager implementation for tree-sitter language support."""

import ctypes
import json
import logging
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

from .contracts.grammar_manager_contract import GrammarManagerContract
from .exceptions import ChunkerError

logger = logging.getLogger(__name__)


class GrammarManagerError(ChunkerError):
    """Base exception for grammar manager operations."""


class GrammarManager(GrammarManagerContract):
    """Manages tree-sitter grammar downloads and compilation."""

    def __init__(
        self,
        root_dir: Path | None = None,
        config_file: Path | None = None,
        max_workers: int = 4,
    ):
        """Initialize the grammar manager.

        Args:
            root_dir: Root directory for grammars (defaults to project root)
            config_file: Path to grammar sources config (defaults to config/grammar_sources.json)
            max_workers: Maximum parallel workers for fetch/compile operations
        """
        self._root_dir = root_dir or Path(__file__).parent.parent
        self._config_file = (
            config_file or self._root_dir / "config" / "grammar_sources.json"
        )
        self._grammars_dir = self._root_dir / "grammars"
        self._build_dir = self._root_dir / "build"
        self._lib_path = self._build_dir / "my-languages.so"
        self._max_workers = max_workers
        self._lock = threading.Lock()

        # Load grammar sources from config
        self._grammar_sources = self._load_config()

        # Create necessary directories
        self._grammars_dir.mkdir(parents=True, exist_ok=True)
        self._build_dir.mkdir(parents=True, exist_ok=True)

    def _load_config(self) -> dict[str, str]:
        """Load grammar sources from config file."""
        if not self._config_file.exists():
            logger.warning("Config file not found: %s", self._config_file)
            return {}

        try:
            with self._config_file.open() as f:
                return json.load(f)
        except (OSError, FileNotFoundError, IndexError) as e:
            logger.error("Failed to load config: %s", e)
            return {}

    def _save_config(self) -> None:
        """Save grammar sources to config file."""
        with self._lock:
            self._config_file.parent.mkdir(parents=True, exist_ok=True)
            with self._config_file.open("w") as f:
                json.dump(self._grammar_sources, f, indent=2, sort_keys=True)

    def add_grammar_source(self, language: str, repo_url: str) -> bool:
        """Add a new grammar source to be fetched.

        Args:
            language: Language identifier
            repo_url: GitHub repository URL

        Returns:
            True if successfully added

        Raises:
            GrammarManagerError: If URL is invalid or language already exists
        """
        # Validate GitHub URL
        parsed = urlparse(repo_url)
        if parsed.scheme not in ("http", "https") or "github.com" not in parsed.netloc:
            raise GrammarManagerError(f"Invalid GitHub URL: {repo_url}")

        # Check if language already exists
        if language in self._grammar_sources:
            logger.warning(
                f"Language '{language}' already exists with URL: {self._grammar_sources[language]}",
            )
            return False

        # Add source and save
        with self._lock:
            self._grammar_sources[language] = repo_url
            self._save_config()

        logger.info(f"Added grammar source for '{language}': {repo_url}")
        return True

    def fetch_grammars(self, languages: list[str] | None = None) -> dict[str, bool]:
        """Fetch grammar repositories.

        Args:
            languages: Optional list of specific languages to fetch

        Returns:
            Dict mapping language to fetch success status
        """
        # Determine which languages to fetch
        if languages is None:
            languages_to_fetch = list(self._grammar_sources.keys())
        else:
            # Validate requested languages
            missing = set(languages) - set(self._grammar_sources.keys())
            if missing:
                logger.warning("Unknown languages requested: %s", missing)
            languages_to_fetch = [
                lang for lang in languages if lang in self._grammar_sources
            ]

        if not languages_to_fetch:
            logger.warning("No languages to fetch")
            return {}

        results = {}

        def fetch_single(lang: str) -> tuple[str, bool]:
            """Fetch a single grammar repository."""
            repo_url = self._grammar_sources[lang]
            target_dir = self._grammars_dir / f"tree-sitter-{lang}"

            # Skip if already exists
            if target_dir.exists():
                logger.info("[skip] %s already present at %s", lang, target_dir)
                return lang, True

            try:
                logger.info("[clone] %s from %s", lang, repo_url)
                cmd = ["git", "clone", "--depth=1", repo_url, str(target_dir)]
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                logger.debug("Clone output for %s: %s", lang, result.stdout)
                return lang, True
            except subprocess.CalledProcessError as e:
                logger.error("Failed to clone %s: %s", lang, e.stderr)
                return lang, False
            except (OSError, IndexError, KeyError) as e:
                logger.error("Unexpected error cloning %s: %s", lang, e)
                return lang, False

        # Fetch in parallel
        with ThreadPoolExecutor(max_workers=self._max_workers) as executor:
            futures = {
                executor.submit(fetch_single, lang): lang for lang in languages_to_fetch
            }

            for future in as_completed(futures):
                lang, success = future.result()
                results[lang] = success

        # Log summary
        successful = sum(1 for s in results.values() if s)
        logger.info("Fetched %s/%s grammars successfully", successful, len(results))

        return results

    def compile_grammars(
        self,
        languages: list[str] | None = None,
    ) -> dict[str, bool]:
        """Compile fetched grammars into shared library.

        Args:
            languages: Optional list of specific languages to compile

        Returns:
            Dict mapping language to compilation success status
        """
        # Gather all available grammar directories
        available_grammars = {}
        for gram_dir in self._grammars_dir.glob("tree-sitter-*"):
            if gram_dir.is_dir():
                # Extract language name from directory
                lang_name = gram_dir.name.replace("tree-sitter-", "")
                available_grammars[lang_name] = gram_dir

        # Determine which languages to compile
        if languages is None:
            languages_to_compile = list(available_grammars.keys())
        else:
            # Validate requested languages
            missing = set(languages) - set(available_grammars.keys())
            if missing:
                logger.warning("Languages not fetched: %s", missing)
            languages_to_compile = [
                lang for lang in languages if lang in available_grammars
            ]

        if not languages_to_compile:
            logger.warning("No languages to compile")
            return {}

        # Gather C source files and include directories
        c_files = []
        include_dirs = set()
        results = {}

        for lang in languages_to_compile:
            gram_dir = available_grammars[lang]
            src_dir = gram_dir / "src"

            if not src_dir.exists():
                logger.warning("No src directory for %s at %s", lang, src_dir)
                results[lang] = False
                continue

            # Add include directory
            include_dirs.add(str(src_dir))

            # Collect C files
            lang_c_files = list(src_dir.glob("*.c"))
            if not lang_c_files:
                logger.warning("No C files found for %s in %s", lang, src_dir)
                results[lang] = False
            else:
                c_files.extend(str(f) for f in lang_c_files)
                results[lang] = True  # Will be updated if compilation fails

        if not c_files:
            logger.error("No C source files found to compile")
            return results

        # Build compilation command
        cmd = ["gcc", "-shared", "-fPIC"]
        for inc in sorted(include_dirs):
            cmd.extend(["-I", inc])
        cmd += ["-o", str(self._lib_path), *c_files]

        # Compile
        try:
            logger.info(
                f"Compiling {len(c_files)} C files from {len(languages_to_compile)} languages",
            )
            logger.debug(
                f"Compilation command: {' '.join(cmd[:10])}... ({len(cmd)} args total)",
            )

            subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info("✅ Successfully compiled to %s", self._lib_path)

            # Mark all as successful (they were already marked True if they had C files)
            return results

        except subprocess.CalledProcessError as e:
            logger.error("Compilation failed: %s", e.stderr)
            # Mark all as failed
            for lang in languages_to_compile:
                results[lang] = False
            return results
        except (OSError, FileNotFoundError, IndexError) as e:
            logger.error("Unexpected compilation error: %s", e)
            for lang in languages_to_compile:
                results[lang] = False
            return results

    def get_available_languages(self) -> set[str]:
        """Get set of languages with compiled grammars.

        Returns:
            Set of available language identifiers
        """
        # Check if library exists
        if not self._lib_path.exists():
            return set()

        # Try to dynamically discover languages from the compiled library
        try:

            # Load the library
            lib = ctypes.CDLL(str(self._lib_path))

            # Look for tree_sitter_<lang> symbols
            available = set()

            # Check known languages from our sources
            for lang in self._grammar_sources:
                symbol_name = f"tree_sitter_{lang}"
                try:
                    # Try to get the symbol
                    getattr(lib, symbol_name)
                    available.add(lang)
                except AttributeError:
                    # Symbol not found
                    pass

            # Also check for any fetched grammars that might be compiled
            for gram_dir in self._grammars_dir.glob("tree-sitter-*"):
                if gram_dir.is_dir():
                    lang = gram_dir.name.replace("tree-sitter-", "")
                    symbol_name = f"tree_sitter_{lang}"
                    try:
                        getattr(lib, symbol_name)
                        available.add(lang)
                    except AttributeError:
                        pass

            return available

        except AttributeError as e:
            logger.error("Error discovering available languages: %s", e)
            # Fallback: assume all fetched grammars are available
            available = set()
            for gram_dir in self._grammars_dir.glob("tree-sitter-*"):
                if gram_dir.is_dir():
                    lang = gram_dir.name.replace("tree-sitter-", "")
                    available.add(lang)
            return available
