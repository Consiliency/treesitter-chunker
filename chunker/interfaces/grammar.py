"""Grammar management interfaces.

Interfaces for managing Tree-sitter language grammars,
including fetching, building, and versioning.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class GrammarStatus(Enum):
    """Status of a grammar."""

    NOT_FOUND = "not_found"
    NOT_BUILT = "not_built"
    BUILDING = "building"
    READY = "ready"
    ERROR = "error"
    OUTDATED = "outdated"


@dataclass
class GrammarInfo:
    """Information about a language grammar.

    Attributes:
        name: Language name (e.g., 'python', 'javascript')
        repository_url: Git repository URL
        commit_hash: Specific commit to use
        abi_version: Tree-sitter ABI version required
        status: Current status of the grammar
        path: Path to compiled grammar file
        error: Error message if status is ERROR
    """

    name: str
    repository_url: str
    commit_hash: str | None = None
    abi_version: int | None = None
    status: GrammarStatus = GrammarStatus.NOT_FOUND
    path: Path | None = None
    error: str | None = None

    @property
    def is_available(self) -> bool:
        """Check if grammar is ready to use."""
        return self.status == GrammarStatus.READY


@dataclass
class NodeTypeInfo:
    """Information about a node type in a grammar.

    Attributes:
        name: Node type name (e.g., 'function_definition')
        is_named: Whether this is a named node type
        has_children: Whether this node type can have children
        fields: List of field names this node type has
        supertypes: Parent types in the grammar hierarchy
    """

    name: str
    is_named: bool
    has_children: bool
    fields: list[str]
    supertypes: list[str]


class GrammarManager(ABC):
    """Manages Tree-sitter language grammars."""

    @staticmethod
    @abstractmethod
    def add_grammar(
        name: str,
        repository_url: str,
        commit_hash: str | None = None,
    ) -> GrammarInfo:
        """Add a new grammar to manage.

        Args:
            name: Language name
            repository_url: Git repository URL
            commit_hash: Specific commit (None for latest)

        Returns:
            Grammar information
        """

    @staticmethod
    @abstractmethod
    def fetch_grammar(name: str) -> bool:
        """Fetch grammar source from repository.

        Args:
            name: Language name

        Returns:
            True if successful
        """

    @staticmethod
    @abstractmethod
    def build_grammar(name: str) -> bool:
        """Build grammar from source.

        Args:
            name: Language name

        Returns:
            True if successful
        """

    @staticmethod
    @abstractmethod
    def get_grammar_info(name: str) -> GrammarInfo | None:
        """Get information about a grammar.

        Args:
            name: Language name

        Returns:
            Grammar info or None if not found
        """

    @staticmethod
    @abstractmethod
    def list_grammars(status: GrammarStatus | None = None) -> list[GrammarInfo]:
        """List all managed grammars.

        Args:
            status: Filter by status (None for all)

        Returns:
            List of grammar information
        """

    @staticmethod
    @abstractmethod
    def update_grammar(name: str) -> bool:
        """Update grammar to latest version.

        Args:
            name: Language name

        Returns:
            True if updated
        """

    @staticmethod
    @abstractmethod
    def remove_grammar(name: str) -> bool:
        """Remove a grammar.

        Args:
            name: Language name

        Returns:
            True if removed
        """

    @staticmethod
    @abstractmethod
    def get_node_types(language: str) -> list[NodeTypeInfo]:
        """Get all node types for a language.

        Args:
            language: Language name

        Returns:
            List of node type information
        """

    @staticmethod
    @abstractmethod
    def validate_grammar(name: str) -> tuple[bool, str | None]:
        """Validate a grammar is working correctly.

        Args:
            name: Language name

        Returns:
            Tuple of (is_valid, error_message)
        """


class GrammarBuilder(ABC):
    """Builds Tree-sitter grammars from source."""

    @staticmethod
    @abstractmethod
    def set_build_directory(path: Path) -> None:
        """Set directory for build output.

        Args:
            path: Build output directory
        """

    @staticmethod
    @abstractmethod
    def set_source_directory(path: Path) -> None:
        """Set directory containing grammar sources.

        Args:
            path: Source directory
        """

    @staticmethod
    @abstractmethod
    def build(languages: list[str]) -> dict[str, bool]:
        """Build specified languages.

        Args:
            languages: List of language names

        Returns:
            Dictionary mapping language to build success
        """

    @staticmethod
    @abstractmethod
    def clean(language: str | None = None) -> None:
        """Clean build artifacts.

        Args:
            language: Specific language (None for all)
        """

    @staticmethod
    @abstractmethod
    def get_build_log(language: str) -> str | None:
        """Get build log for a language.

        Args:
            language: Language name

        Returns:
            Build log or None
        """


class GrammarRepository(ABC):
    """Repository of known grammar sources."""

    @staticmethod
    @abstractmethod
    def search(query: str) -> list[GrammarInfo]:
        """Search for grammars.

        Args:
            query: Search query

        Returns:
            List of matching grammars
        """

    @staticmethod
    @abstractmethod
    def get_popular_grammars(limit: int = 20) -> list[GrammarInfo]:
        """Get most popular grammars.

        Args:
            limit: Maximum number to return

        Returns:
            List of popular grammars
        """

    @staticmethod
    @abstractmethod
    def get_grammar_by_extension(extension: str) -> GrammarInfo | None:
        """Find grammar for a file extension.

        Args:
            extension: File extension (e.g., '.py')

        Returns:
            Grammar info or None
        """

    @staticmethod
    @abstractmethod
    def refresh_repository() -> bool:
        """Refresh repository data.

        Returns:
            True if successful
        """


class GrammarValidator(ABC):
    """Validates grammar compatibility and correctness."""

    @staticmethod
    @abstractmethod
    def check_abi_compatibility(grammar_path: Path) -> tuple[bool, str | None]:
        """Check if grammar ABI is compatible.

        Args:
            grammar_path: Path to compiled grammar

        Returns:
            Tuple of (is_compatible, error_message)
        """

    @staticmethod
    @abstractmethod
    def validate_node_types(language: str, expected_types: set[str]) -> list[str]:
        """Validate expected node types exist.

        Args:
            language: Language name
            expected_types: Set of expected node type names

        Returns:
            List of missing node types
        """

    @staticmethod
    @abstractmethod
    def test_parse(language: str, sample_code: str) -> tuple[bool, str | None]:
        """Test parsing with sample code.

        Args:
            language: Language name
            sample_code: Sample code to parse

        Returns:
            Tuple of (success, error_message)
        """
