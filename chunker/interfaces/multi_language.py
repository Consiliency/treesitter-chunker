"""Multi-language project processing interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from chunker.types import CodeChunk


class EmbeddedLanguageType(Enum):
    """Types of embedded languages."""

    TEMPLATE = "template"
    QUERY = "query"
    SCRIPT = "script"
    STYLE = "style"
    DOCUMENTATION = "documentation"
    CONFIGURATION = "configuration"


@dataclass
class LanguageRegion:
    """A region of code in a specific language."""

    language: str
    start_pos: int
    end_pos: int
    start_line: int
    end_line: int
    embedding_type: EmbeddedLanguageType | None = None
    parent_language: str | None = None


@dataclass
class CrossLanguageReference:
    """A reference between code in different languages."""

    source_chunk: CodeChunk
    target_chunk: CodeChunk
    reference_type: str
    confidence: float


class MultiLanguageProcessor(ABC):
    """Process projects with multiple languages."""

    @staticmethod
    @abstractmethod
    def detect_project_languages(project_path: str) -> dict[str, float]:
        """
        Detect languages used in project with confidence scores.

        This should analyze file extensions, shebang lines, and content
        to determine which languages are present.

        Args:
            project_path: Root path of the project

        Returns:
            Dict mapping language names to usage percentage (0-1)
        """

    @staticmethod
    @abstractmethod
    def identify_language_regions(file_path: str, content: str) -> list[LanguageRegion]:
        """
        Identify regions of different languages within a file.

        Args:
            file_path: Path to the file
            content: File content

        Returns:
            List of language regions in the file
        """

    @staticmethod
    @abstractmethod
    def process_mixed_file(
        file_path: str,
        primary_language: str,
        content: str | None = None,
    ) -> list[CodeChunk]:
        """
        Process files with embedded languages.

        Examples:
        - HTML files with embedded JS/CSS
        - JSX/TSX files with HTML-like syntax
        - Markdown with code blocks
        - Jupyter notebooks with multiple languages

        Args:
            file_path: Path to the file
            primary_language: Main language of the file
            content: Optional file content (will read if not provided)

        Returns:
            Chunks from all languages in the file
        """

    @staticmethod
    @abstractmethod
    def extract_embedded_code(
        content: str,
        host_language: str,
        target_language: str,
    ) -> list[tuple[str, int, int]]:
        """
        Extract embedded code snippets.

        Args:
            content: Content to search
            host_language: Language containing the embedded code
            target_language: Language to extract

        Returns:
            List of (code_snippet, start_pos, end_pos) tuples
        """

    @staticmethod
    @abstractmethod
    def cross_language_references(
        chunks: list[CodeChunk],
    ) -> list[CrossLanguageReference]:
        """
        Find references across language boundaries.

        Examples:
        - Python backend API called by JavaScript frontend
        - Shared types between TypeScript and Go
        - SQL queries referenced in application code

        Args:
            chunks: All chunks from the project

        Returns:
            List of cross-language references
        """

    @staticmethod
    @abstractmethod
    def group_by_feature(chunks: list[CodeChunk]) -> dict[str, list[CodeChunk]]:
        """
        Group chunks from different languages by feature.

        This attempts to identify chunks that implement the same feature
        across different languages (e.g., frontend and backend for user auth).

        Args:
            chunks: All chunks from the project

        Returns:
            Dict mapping feature names to related chunks
        """


class LanguageDetector(ABC):
    """Detect programming languages in files and content."""

    @staticmethod
    @abstractmethod
    def detect_from_file(file_path: str) -> tuple[str, float]:
        """
        Detect language from file path and content.

        Args:
            file_path: Path to the file

        Returns:
            Tuple of (language, confidence)
        """

    @staticmethod
    @abstractmethod
    def detect_from_content(content: str, hint: str | None = None) -> tuple[str, float]:
        """
        Detect language from content alone.

        Args:
            content: Code content
            hint: Optional hint about expected language

        Returns:
            Tuple of (language, confidence)
        """

    @staticmethod
    @abstractmethod
    def detect_multiple(content: str) -> list[tuple[str, float]]:
        """
        Detect multiple languages in content.

        Args:
            content: Content that may contain multiple languages

        Returns:
            List of (language, percentage) tuples
        """


class ProjectAnalyzer(ABC):
    """Analyze multi-language project structure."""

    @staticmethod
    @abstractmethod
    def analyze_structure(project_path: str) -> dict[str, Any]:
        """
        Analyze overall project structure.

        Returns information about:
        - Primary languages
        - Framework detection
        - Project type (web app, library, etc.)
        - Component boundaries

        Args:
            project_path: Root path of project

        Returns:
            Project analysis results
        """

    @staticmethod
    @abstractmethod
    def find_api_boundaries(chunks: list[CodeChunk]) -> list[dict[str, Any]]:
        """
        Find API boundaries between components.

        Args:
            chunks: All project chunks

        Returns:
            List of API boundary definitions
        """

    @staticmethod
    @abstractmethod
    def suggest_chunk_grouping(chunks: list[CodeChunk]) -> dict[str, list[CodeChunk]]:
        """
        Suggest how to group chunks for processing.

        Args:
            chunks: All project chunks

        Returns:
            Suggested groupings
        """
