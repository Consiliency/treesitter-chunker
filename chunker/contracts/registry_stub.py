"""Concrete stub implementation for testing - Grammar Registry"""

import tempfile
from typing import Any

import tree_sitter

from .registry_contract import UniversalRegistryContract


class UniversalRegistryStub(UniversalRegistryContract):
    """Stub implementation that can be instantiated and tested"""

    # Class-level state so static methods can operate without instance
    _installed = {"python", "rust", "javascript", "c", "cpp"}
    _available = _installed | {"go", "java", "ruby", "swift", "kotlin"}
    _versions = {
        "python": "0.20.0",
        "rust": "0.20.0",
        "javascript": "0.20.0",
        "c": "0.19.0",
        "cpp": "0.19.0",
    }

    @staticmethod
    def get_parser(
        language: str,
        auto_download: bool = True,
    ) -> tree_sitter.Parser:
        """Stub that returns a parser instance"""
        if language not in UniversalRegistryStub._installed:
            if auto_download and language in UniversalRegistryStub._available:
                UniversalRegistryStub._installed.add(language)
                UniversalRegistryStub._versions[language] = "0.20.0"
            else:
                raise ValueError(f"Language {language} not available")

        # Return a new parser instance
        return tree_sitter.Parser()

    @staticmethod
    def list_installed_languages() -> list[str]:
        """Stub that returns installed languages"""
        return sorted(UniversalRegistryStub._installed)

    @staticmethod
    def list_available_languages() -> list[str]:
        """Stub that returns all available languages"""
        return sorted(UniversalRegistryStub._available)

    @staticmethod
    def is_language_installed(language: str) -> bool:
        """Stub that checks installation"""
        return language in UniversalRegistryStub._installed

    @staticmethod
    def install_language(language: str, version: str | None = None) -> bool:
        """Stub that simulates installation"""
        if language not in UniversalRegistryStub._available:
            return False

        UniversalRegistryStub._installed.add(language)
        UniversalRegistryStub._versions[language] = version or "0.20.0"
        return True

    @staticmethod
    def uninstall_language(language: str) -> bool:
        """Stub that simulates uninstallation"""
        if language in UniversalRegistryStub._installed:
            UniversalRegistryStub._installed.remove(language)
            if language in UniversalRegistryStub._versions:
                del UniversalRegistryStub._versions[language]
            return True
        return False

    @staticmethod
    def get_language_version(language: str) -> str | None:
        """Stub that returns version info"""
        return UniversalRegistryStub._versions.get(language)

    @staticmethod
    def update_language(language: str) -> tuple[bool, str]:
        """Stub that simulates update"""
        if language not in UniversalRegistryStub._installed:
            return (False, f"Language {language} not installed")

        current = UniversalRegistryStub._versions.get(language, "0.19.0")
        if current < "0.20.0":
            UniversalRegistryStub._versions[language] = "0.20.0"
            return (True, f"Updated {language} from {current} to 0.20.0")
        return (True, f"Language {language} already up to date")

    @staticmethod
    def get_language_metadata(language: str) -> dict[str, Any]:
        """Stub that returns metadata"""
        if language not in UniversalRegistryStub._installed:
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
            "version": UniversalRegistryStub._versions.get(language, "unknown"),
            "abi_version": 14,
            "file_extensions": extension_map.get(language, []),
            "installed_path": f"{tempfile.gettempdir()}/grammar_cache_stub/{language}.so",
        }
