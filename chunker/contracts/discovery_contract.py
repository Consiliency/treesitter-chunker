"""Define the boundary for grammar discovery service - Team: Grammar Discovery"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class GrammarInfo:
    """Information about a tree-sitter grammar"""

    name: str
    url: str
    version: str
    last_updated: datetime
    stars: int
    description: str
    supported_extensions: list[str]
    official: bool


@dataclass
class GrammarCompatibility:
    """Compatibility information for a grammar"""

    min_tree_sitter_version: str
    max_tree_sitter_version: str
    abi_version: int
    tested_python_versions: list[str]


class GrammarDiscoveryContract(ABC):
    """Abstract contract defining grammar discovery interface"""

    @staticmethod
    @abstractmethod
    def list_available_grammars(include_community: bool = False) -> list[GrammarInfo]:
        """List all available tree-sitter grammars

        Args:
            include_community: Include community grammars, not just official

        Returns:
            List of available grammars with metadata

        Preconditions:
            - Network connectivity available (or cached data exists)

        Postconditions:
            - Returns non-empty list if any grammars found
            - Each grammar has valid URL and name
        """

    @staticmethod
    @abstractmethod
    def get_grammar_info(language: str) -> GrammarInfo | None:
        """Get detailed information about a specific grammar

        Args:
            language: Language name (e.g., "python", "rust")

        Returns:
            Grammar information if found, None otherwise

        Preconditions:
            - language is a non-empty string

        Postconditions:
            - Returns valid GrammarInfo or None
            - Info includes all required fields
        """

    @staticmethod
    @abstractmethod
    def check_grammar_updates(
        installed_grammars: dict[str, str],
    ) -> dict[str, tuple[str, str]]:
        """Check for updates to installed grammars

        Args:
            installed_grammars: Dict of language -> current_version

        Returns:
            Dict of language -> (current_version, latest_version) for grammars with updates

        Preconditions:
            - installed_grammars contains valid version strings

        Postconditions:
            - Only returns grammars that have newer versions
            - Version strings are valid semver format
        """

    @staticmethod
    @abstractmethod
    def get_grammar_compatibility(
        language: str,
        version: str,
    ) -> GrammarCompatibility:
        """Get compatibility requirements for a grammar version

        Args:
            language: Language name
            version: Grammar version

        Returns:
            Compatibility information

        Preconditions:
            - Grammar exists and version is valid

        Postconditions:
            - Returns valid compatibility info
            - ABI version is positive integer
        """

    @staticmethod
    @abstractmethod
    def search_grammars(query: str) -> list[GrammarInfo]:
        """Search for grammars by name or description

        Args:
            query: Search query string

        Returns:
            List of matching grammars

        Preconditions:
            - query is non-empty string

        Postconditions:
            - Returns grammars that match query
            - Search is case-insensitive
        """

    @staticmethod
    @abstractmethod
    def refresh_cache() -> bool:
        """Refresh the grammar discovery cache

        Returns:
            True if refresh successful, False otherwise

        Preconditions:
            - Network connectivity available

        Postconditions:
            - Cache updated with latest data
            - Old cache preserved if refresh fails
        """
