"""Concrete stub implementation for testing - Grammar Registry"""

import tempfile
from typing import Any

import tree_sitter

from .registry_contract import UniversalRegistryContract


class UniversalRegistryStub(UniversalRegistryContract):
    """Stub implementation that can be instantiated and tested"""

    def __init__(self):
        self._installed = {"python", "rust", "javascript", "c", "cpp"}
        self._available = self._installed | {"go", "java", "ruby", "swift", "kotlin"}
        self._versions = {
            "python": "0.20.0",
            "rust": "0.20.0",
            "javascript": "0.20.0",
            "c": "0.19.0",
            "cpp": "0.19.0",
        }

    def get_parser(
        self,
        language: str,
        auto_download: bool = True,
    ) -> tree_sitter.Parser:
        """Stub that returns a parser instance"""
        if language not in self._installed:
            if auto_download and language in self._available:
                self._installed.add(language)
                self._versions[language] = "0.20.0"
            else:
                raise ValueError(f"Language {language} not available")

        # Return a new parser instance
        return tree_sitter.Parser()

    def list_installed_languages(self) -> list[str]:
        """Stub that returns installed languages"""
        return sorted(self._installed)

    def list_available_languages(self) -> list[str]:
        """Stub that returns all available languages"""
        return sorted(self._available)

    def is_language_installed(self, language: str) -> bool:
        """Stub that checks installation"""
        return language in self._installed

    def install_language(self, language: str, version: str | None = None) -> bool:
        """Stub that simulates installation"""
        if language not in self._available:
            return False

        self._installed.add(language)
        self._versions[language] = version or "0.20.0"
        return True

    def uninstall_language(self, language: str) -> bool:
        """Stub that simulates uninstallation"""
        if language in self._installed:
            self._installed.remove(language)
            if language in self._versions:
                del self._versions[language]
            return True
        return False

    def get_language_version(self, language: str) -> str | None:
        """Stub that returns version info"""
        return self._versions.get(language)

    def update_language(self, language: str) -> tuple[bool, str]:
        """Stub that simulates update"""
        if language not in self._installed:
            return (False, f"Language {language} not installed")

        current = self._versions.get(language, "0.19.0")
        if current < "0.20.0":
            self._versions[language] = "0.20.0"
            return (True, f"Updated {language} from {current} to 0.20.0")
        return (True, f"Language {language} already up to date")

    def get_language_metadata(self, language: str) -> dict[str, Any]:
        """Stub that returns metadata"""
        if language not in self._installed:
            return {}

        extension_map = {
            "python": [".py", ".pyw"],
            "rust": [".rs"],
            "javascript": [".js", ".jsx", ".mjs"],
            "c": [".c", ".h"],
            "cpp": [".cpp", ".cc", ".cxx", ".hpp", ".hh"],
            "go": [".go"],
            "java": [".java"],
            "ruby": [".rb"],
            "swift": [".swift"],
            "kotlin": [".kt", ".kts"],
        }

        return {
            "version": self._versions.get(language, "unknown"),
            "abi_version": 14,
            "file_extensions": extension_map.get(language, []),
            "installed_path": f"{tempfile.gettempdir()}/grammar_cache_stub/{language}.so",
        }
