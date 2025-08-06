from abc import ABC, abstractmethod


class GrammarManagerContract(ABC):
    """Contract for managing tree-sitter grammar downloads and compilation"""

    @staticmethod
    @abstractmethod
    def add_grammar_source(language: str, repo_url: str) -> bool:
        """Add a new grammar source to be fetched

        Args:
            language: Language identifier
            repo_url: GitHub repository URL

        Returns:
            True if successfully added

        Preconditions:
            - repo_url must be valid GitHub URL
            - language must not already exist

        Postconditions:
            - Grammar source registered for fetching
        """

    @staticmethod
    @abstractmethod
    def fetch_grammars(languages: list[str] | None = None) -> dict[str, bool]:
        """Fetch grammar repositories

        Args:
            languages: Optional list of specific languages to fetch

        Returns:
            Dict mapping language to fetch success status

        Preconditions:
            - Grammar sources must be registered

        Postconditions:
            - Grammar repositories cloned to grammars/ directory
        """

    @staticmethod
    @abstractmethod
    def compile_grammars(languages: list[str] | None = None) -> dict[str, bool]:
        """Compile fetched grammars into shared library

        Args:
            languages: Optional list of specific languages to compile

        Returns:
            Dict mapping language to compilation success status

        Preconditions:
            - Grammars must be fetched first
            - Build tools must be available

        Postconditions:
            - Compiled .so file updated with new languages
        """

    @staticmethod
    @abstractmethod
    def get_available_languages() -> set[str]:
        """Get set of languages with compiled grammars

        Returns:
            Set of available language identifiers

        Preconditions:
            - None

        Postconditions:
            - No side effects
        """
