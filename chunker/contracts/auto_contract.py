"""Define the boundary for zero-configuration API - Team: Zero-Config API"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class AutoChunkResult:
    """Result of automatic chunking"""

    chunks: list[dict[str, Any]]
    language: str
    grammar_downloaded: bool
    fallback_used: bool
    metadata: dict[str, Any]


class ZeroConfigContract(ABC):
    """Abstract contract defining zero-configuration interface"""

    @abstractmethod
    def ensure_language(self, language: str, version: str | None = None) -> bool:
        """Ensure a language is available for use

        Args:
            language: Language name
            version: Specific version required

        Returns:
            True if language is ready to use

        Preconditions:
            - Language name is valid

        Postconditions:
            - Language grammar installed if needed
            - Parser available for language
        """

    @abstractmethod
    def auto_chunk_file(
        self,
        file_path: str | Path,
        language: str | None = None,
        token_limit: int | None = None,
    ) -> AutoChunkResult:
        """Automatically chunk a file with zero configuration

        Args:
            file_path: Path to file
            language: Override language detection
            token_limit: Optional token limit per chunk

        Returns:
            Chunking result with metadata

        Preconditions:
            - File exists and is readable

        Postconditions:
            - File chunked using best available method
            - Grammar downloaded if needed
            - Falls back to text chunking if needed
        """

    @abstractmethod
    def detect_language(self, file_path: str | Path) -> str | None:
        """Detect the language of a file

        Args:
            file_path: Path to file

        Returns:
            Detected language name or None

        Postconditions:
            - Uses file extension first
            - Checks shebang for scripts
            - Returns None if unknown
        """

    @abstractmethod
    def chunk_text(
        self,
        text: str,
        language: str,
        token_limit: int | None = None,
    ) -> AutoChunkResult:
        """Chunk text content with automatic setup

        Args:
            text: Text content to chunk
            language: Language of the text
            token_limit: Optional token limit

        Returns:
            Chunking result

        Preconditions:
            - Text is non-empty
            - Language is specified

        Postconditions:
            - Grammar downloaded if needed
            - Text chunked appropriately
        """

    @abstractmethod
    def list_supported_extensions(self) -> dict[str, list[str]]:
        """List all supported file extensions

        Returns:
            Dict mapping language to extensions

        Postconditions:
            - Includes all available languages
            - Extensions include dots (e.g., ".py")
        """

    @abstractmethod
    def get_chunker_for_language(
        self,
        language: str,
        auto_download: bool = True,
    ) -> Any:
        """Get a chunker instance for a specific language

        Args:
            language: Language name
            auto_download: Download grammar if needed

        Returns:
            Configured chunker instance

        Preconditions:
            - Language is valid

        Postconditions:
            - Chunker ready to use
            - Grammar downloaded if auto_download=True
        """

    @abstractmethod
    def preload_languages(self, languages: list[str]) -> dict[str, bool]:
        """Preload multiple language grammars

        Args:
            languages: List of languages to preload

        Returns:
            Dict of language -> success status

        Postconditions:
            - All requested grammars downloaded
            - Ready for offline use
        """
