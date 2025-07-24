"""Define the boundary for enhanced grammar registry - Team: Grammar Registry"""

from abc import ABC, abstractmethod
from typing import Any

import tree_sitter


class UniversalRegistryContract(ABC):
    """Abstract contract defining universal language registry interface"""

    @abstractmethod
    def get_parser(
        self,
        language: str,
        auto_download: bool = True,
    ) -> tree_sitter.Parser:
        """Get a parser for a language, downloading if needed

        Args:
            language: Language name
            auto_download: Automatically download if not available

        Returns:
            Configured parser instance

        Preconditions:
            - language is a valid grammar name

        Postconditions:
            - Parser is configured with language
            - Grammar downloaded if auto_download=True
        """

    @abstractmethod
    def list_installed_languages(self) -> list[str]:
        """List all currently installed languages

        Returns:
            List of installed language names

        Postconditions:
            - Only returns languages with valid grammars
            - List is sorted alphabetically
        """

    @abstractmethod
    def list_available_languages(self) -> list[str]:
        """List all available languages (installed + downloadable)

        Returns:
            List of all available language names

        Postconditions:
            - Includes both installed and downloadable
            - List is sorted alphabetically
        """

    @abstractmethod
    def is_language_installed(self, language: str) -> bool:
        """Check if a language is installed

        Args:
            language: Language name

        Returns:
            True if language is installed and ready

        Postconditions:
            - Returns True only if grammar is loaded
            - Validates grammar compatibility
        """

    @abstractmethod
    def install_language(self, language: str, version: str | None = None) -> bool:
        """Install a language grammar

        Args:
            language: Language name
            version: Specific version to install

        Returns:
            True if installation successful

        Preconditions:
            - Language is available for download

        Postconditions:
            - Grammar downloaded and compiled
            - Language available for parsing
        """

    @abstractmethod
    def uninstall_language(self, language: str) -> bool:
        """Uninstall a language grammar

        Args:
            language: Language name

        Returns:
            True if uninstallation successful

        Postconditions:
            - Grammar files removed
            - Language no longer available
        """

    @abstractmethod
    def get_language_version(self, language: str) -> str | None:
        """Get the installed version of a language

        Args:
            language: Language name

        Returns:
            Version string if installed, None otherwise

        Postconditions:
            - Returns semver format version
            - None if not installed
        """

    @abstractmethod
    def update_language(self, language: str) -> tuple[bool, str]:
        """Update a language to latest version

        Args:
            language: Language name

        Returns:
            Tuple of (success, message)

        Preconditions:
            - Language is installed

        Postconditions:
            - Language updated if newer version exists
            - Old version preserved if update fails
        """

    @abstractmethod
    def get_language_metadata(self, language: str) -> dict[str, Any]:
        """Get metadata about an installed language

        Args:
            language: Language name

        Returns:
            Metadata dictionary

        Postconditions:
            - Includes version, ABI, file extensions
            - Empty dict if not installed
        """
