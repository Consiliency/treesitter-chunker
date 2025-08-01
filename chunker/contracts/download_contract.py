"""Define the boundary for grammar download and compilation - Team: Grammar Download"""
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path


@dataclass
class DownloadProgress:
    """Progress information for downloads"""
    bytes_downloaded: int
    total_bytes: int
    percent_complete: float
    current_file: str


@dataclass
class CompilationResult:
    """Result of grammar compilation"""
    success: bool
    output_path: Path | None
    error_message: str | None
    abi_version: int | None


class GrammarDownloadContract(ABC):
    """Abstract contract defining grammar download interface"""

    @staticmethod
    @abstractmethod
    def download_grammar(language: str, version: (str | None) = None,
        progress_callback: (Callable[[DownloadProgress], None] | None) = None,
        ) -> Path:
        """Download a grammar repository

        Args:
            language: Language name
            version: Specific version to download (latest if None)
            progress_callback: Called with DownloadProgress during download

        Returns:
            Path to downloaded grammar directory

        Preconditions:
            - Language grammar exists
            - Network connectivity available
            - Sufficient disk space

        Postconditions:
            - Grammar files downloaded to returned path
            - Directory contains valid grammar sources
        """

    @staticmethod
    @abstractmethod
    def compile_grammar(grammar_path: Path, output_dir: Path,
        ) -> CompilationResult:
        """Compile a grammar into a shared library

        Args:
            grammar_path: Path to grammar source directory
            output_dir: Directory for compiled output

        Returns:
            Compilation result with status and output path

        Preconditions:
            - grammar_path contains valid grammar sources
            - output_dir exists and is writable
            - Build tools available (cc/gcc)

        Postconditions:
            - Compiled .so file created if successful
            - Error message provided if failed
        """

    @staticmethod
    @abstractmethod
    def download_and_compile(language: str, version: (str | None) = None,
        ) -> tuple[bool, str]:
        """Download and compile a grammar in one step

        Args:
            language: Language name
            version: Specific version (latest if None)

        Returns:
            Tuple of (success, path_or_error_message)

        Preconditions:
            - Language grammar exists
            - Network and build tools available

        Postconditions:
            - Grammar downloaded and compiled if successful
            - Cached for future use
        """

    @staticmethod
    @abstractmethod
    def get_grammar_cache_dir() -> Path:
        """Get the directory where grammars are cached

        Returns:
            Path to grammar cache directory

        Postconditions:
            - Directory exists
            - Directory is writable
        """

    @staticmethod
    @abstractmethod
    def is_grammar_cached(language: str, version: (str | None) = None) -> bool:
        """Check if a grammar is already cached

        Args:
            language: Language name
            version: Specific version

        Returns:
            True if grammar is cached and valid

        Postconditions:
            - Returns True only if compiled .so exists
            - Validates cache integrity
        """

    @staticmethod
    @abstractmethod
    def clean_cache(keep_recent: int = 5) -> int:
        """Clean old cached grammars

        Args:
            keep_recent: Number of recent grammars to keep

        Returns:
            Number of grammars removed

        Postconditions:
            - Old/unused grammars removed
            - Most recent grammars preserved
        """

    @staticmethod
    @abstractmethod
    def validate_grammar(grammar_path: Path) -> tuple[bool, str | None]:
        """Validate a compiled grammar

        Args:
            grammar_path: Path to compiled .so file

        Returns:
            Tuple of (is_valid, error_message)

        Postconditions:
            - Checks ABI compatibility
            - Verifies grammar can be loaded
        """
