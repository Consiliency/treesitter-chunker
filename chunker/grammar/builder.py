"""Tree-sitter grammar builder implementation."""

import logging
import platform
from pathlib import Path

from tree_sitter import Language

from chunker.exceptions import ChunkerError
from chunker.interfaces.grammar import GrammarBuilder

logger = logging.getLogger(__name__)


class BuildError(ChunkerError):
    """Error during grammar building."""


class TreeSitterGrammarBuilder(GrammarBuilder):
    """Builds Tree-sitter grammars from source."""

    def __init__(self):
        """Initialize grammar builder."""
        self._build_dir = Path("build")
        self._source_dir = Path("grammars")
        self._build_logs: dict[str, str] = {}

        # Platform-specific settings
        self._platform = platform.system()
        self._lib_extension = {
            "Linux": ".so",
            "Darwin": ".dylib",
            "Windows": ".dll",
        }.get(self._platform, ".so")

    def set_build_directory(self, path: Path) -> None:
        """Set directory for build output.

        Args:
            path: Build output directory
        """
        self._build_dir = path
        self._build_dir.mkdir(exist_ok=True)

    def set_source_directory(self, path: Path) -> None:
        """Set directory containing grammar sources.

        Args:
            path: Source directory
        """
        self._source_dir = path

    def build(self, languages: list[str]) -> dict[str, bool]:
        """Build specified languages.

        Args:
            languages: List of language names

        Returns:
            Dictionary mapping language to build success
        """
        results = {}

        # Prepare language paths
        language_paths = []
        for lang in languages:
            lang_path = self._source_dir / f"tree-sitter-{lang}"
            if not lang_path.exists():
                logger.error(f"Source directory for '{lang}' not found at {lang_path}")
                results[lang] = False
                self._build_logs[lang] = f"Source directory not found: {lang_path}"
                continue
            language_paths.append((lang, lang_path))

        if not language_paths:
            return results

        # Build all languages into a single library
        lib_path = self._build_dir / f"languages{self._lib_extension}"

        try:
            logger.info("Building %s languages...", len(language_paths))

            # Use tree-sitter Language.build_library
            Language.build_library(
                str(lib_path),
                [str(path) for _, path in language_paths],
            )

            # Verify the library was created
            if lib_path.exists():
                logger.info("Successfully built library at %s", lib_path)
                for lang, _ in language_paths:
                    results[lang] = True
                    self._build_logs[lang] = "Build successful"
            else:
                raise BuildError(f"Library file_path not created at {lib_path}")

        except (FileNotFoundError, IndexError, KeyError) as e:
            logger.error("Build failed: %s", e)
            for lang, _ in language_paths:
                if lang not in results:
                    results[lang] = False
                    self._build_logs[lang] = str(e)

        return results

    def build_individual(self, language: str) -> bool:
        """Build a single language as a separate library.

        Args:
            language: Language name

        Returns:
            True if successful
        """
        lang_path = self._source_dir / f"tree-sitter-{language}"
        if not lang_path.exists():
            logger.error(f"Source directory for '{language}' not found")
            self._build_logs[language] = "Source directory not found"
            return False

        lib_path = self._build_dir / f"{language}{self._lib_extension}"

        try:
            logger.info("Building %s...", language)

            # Gather C source files
            c_files = []
            src_dir = lang_path / "src"
            if src_dir.exists():
                for src in src_dir.glob("*.c"):
                    c_files.append(str(src))

            if not c_files:
                raise BuildError(f"No C source files found in {src_dir}")

            # Compile using gcc
            import subprocess

            cmd = ["gcc", "-shared", "-fPIC", "-o", str(lib_path), *c_files]

            result = subprocess.run(cmd, check=False, capture_output=True, text=True)
            if result.returncode != 0:
                raise BuildError(f"Compilation failed: {result.stderr}")

            if lib_path.exists():
                logger.info("Successfully built %s at %s", language, lib_path)
                self._build_logs[language] = "Build successful"
                return True
            raise BuildError(f"Library file_path not created at {lib_path}")

        except (FileNotFoundError, IndexError, KeyError) as e:
            logger.error("Failed to build %s: %s", language, e)
            self._build_logs[language] = str(e)
            return False

    def clean(self, language: str | None = None) -> None:
        """Clean build artifacts.

        Args:
            language: Specific language (None for all)
        """
        if language:
            # Clean specific language artifacts
            patterns = [
                f"{language}{self._lib_extension}",
                f"{language}.*{self._lib_extension}",
            ]
        else:
            # Clean all artifacts
            patterns = [
                f"*{self._lib_extension}",
                "*.o",
                "*.obj",
                "*.exp",
                "*.lib",
            ]

        cleaned = 0
        for pattern in patterns:
            for file_path in self._build_dir.glob(pattern):
                try:
                    file_path.unlink()
                    cleaned += 1
                    logger.debug("Removed %s", file_path)
                except (FileNotFoundError, OSError) as e:
                    logger.error("Failed to remove %s: %s", file_path, e)

        if cleaned > 0:
            logger.info("Cleaned %s build artifacts", cleaned)

    def get_build_log(self, language: str) -> str | None:
        """Get build log for a language.

        Args:
            language: Language name

        Returns:
            Build log or None
        """
        return self._build_logs.get(language)

    def compile_queries(self, language: str) -> bool:
        """Compile query files for a language.

        Args:
            language: Language name

        Returns:
            True if successful
        """
        lang_path = self._source_dir / f"tree-sitter-{language}"
        queries_dir = lang_path / "queries"

        if not queries_dir.exists():
            logger.debug("No queries directory for %s", language)
            return True

        # Copy query files to build directory
        target_dir = self._build_dir / "queries" / language
        target_dir.mkdir(parents=True, exist_ok=True)

        try:
            import shutil

            for query_file in queries_dir.glob("*.scm"):
                target_file = target_dir / query_file.name
                shutil.copy2(query_file, target_file)
                logger.debug("Copied %s for %s", query_file.name, language)

            return True

        except (FileNotFoundError, ImportError, ModuleNotFoundError) as e:
            logger.error("Failed to copy queries for %s: %s", language, e)
            return False


def build_language(name: str, source_path: str, build_path: str) -> bool:
    """Build a single language (helper function).

    Args:
        name: Language name
        source_path: Path to grammar source
        build_path: Path to build directory

    Returns:
        True if successful
    """
    builder = TreeSitterGrammarBuilder()
    builder.set_source_directory(Path(source_path).parent)
    builder.set_build_directory(Path(build_path))
    return builder.build_individual(name)
