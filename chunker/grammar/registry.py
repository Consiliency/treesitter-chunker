"""Universal Language Registry with auto-download capabilities."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import tree_sitter

from chunker.contracts.registry_contract import UniversalRegistryContract
from chunker.exceptions import LanguageNotFoundError
from chunker.registry import LanguageRegistry

if TYPE_CHECKING:
    from chunker.contracts.discovery_contract import GrammarDiscoveryContract
    from chunker.contracts.download_contract import GrammarDownloadContract

logger = logging.getLogger(__name__)


class UniversalLanguageRegistry(UniversalRegistryContract):
    """Enhanced language registry with auto-download capabilities."""

    def __init__(
        self,
        library_path: Path,
        discovery_service: GrammarDiscoveryContract,
        download_service: GrammarDownloadContract,
        cache_dir: Path | None = None,
    ):
        """Initialize the universal registry.

        Args:
            library_path: Path to the compiled language library
            discovery_service: Service for discovering available grammars
            download_service: Service for downloading and compiling grammars
            cache_dir: Directory for storing metadata (defaults to ~/.cache/treesitter-chunker)
        """
        self._base_registry = LanguageRegistry(library_path)
        self._discovery = discovery_service
        self._downloader = download_service

        # Set up metadata cache directory
        if cache_dir is None:
            cache_dir = Path.home() / ".cache" / "treesitter-chunker"
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)

        self._metadata_path = self._cache_dir / "registry_metadata.json"
        self._metadata = self._load_metadata()

        # Track auto-downloaded languages
        self._auto_downloaded: set[str] = set(self._metadata.get("auto_downloaded", []))

    def _load_metadata(self) -> dict[str, Any]:
        """Load metadata from cache."""
        if self._metadata_path.exists():
            try:
                with self._metadata_path.open() as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                logger.warning("Failed to load metadata: %s", e)
        return {"installed": {}, "auto_downloaded": []}

    def _save_metadata(self) -> None:
        """Save metadata to cache."""
        try:
            # Update auto_downloaded list
            self._metadata["auto_downloaded"] = list(self._auto_downloaded)

            with self._metadata_path.open(
                "w",
                "r",
            ) as f:
                json.dump(self._metadata, f, indent=2)
        except (OSError, json.JSONEncodeError) as e:
            logger.error("Failed to save metadata: %s", e)

    def get_parser(
        self,
        language: str,
        auto_download: bool = True,
    ) -> tree_sitter.Parser:
        """Get a parser for a language, downloading if needed.

        Args:
            language: Language name
            auto_download: Automatically download if not available

        Returns:
            Configured parser instance
        """
        # First try to get from base registry
        if self._base_registry.has_language(language):
            lang = self._base_registry.get_language(language)
            parser = tree_sitter.Parser()
            parser.language = lang
            return parser

        # If not available and auto_download is enabled
        if auto_download:
            # Check if language is available for download
            grammar_info = self._discovery.get_grammar_info(language)
            if grammar_info:
                # Download and compile
                success, path = self._downloader.download_and_compile(
                    language,
                    grammar_info.version,
                )

                if success:
                    # Mark as auto-downloaded
                    self._auto_downloaded.add(language)

                    # Update metadata
                    if "installed" not in self._metadata:
                        self._metadata["installed"] = {}

                    self._metadata["installed"][language] = {
                        "version": grammar_info.version,
                        "path": path,
                        "auto_downloaded": True,
                    }
                    self._save_metadata()

                    # Re-discover languages in base registry
                    self._base_registry._discovered = False
                    self._base_registry.discover_languages()

                    # Now get the parser
                    if self._base_registry.has_language(language):
                        lang = self._base_registry.get_language(language)
                        parser = tree_sitter.Parser()
                        parser.language = lang
                        return parser

        # Language not available
        available = self.list_available_languages()
        raise LanguageNotFoundError(language, available)

    def list_installed_languages(self) -> list[str]:
        """List all currently installed languages.

        Returns:
            List of installed language names
        """
        # Get languages from base registry
        base_languages = self._base_registry.list_languages()

        # Add any from metadata that might not be in the registry yet
        metadata_languages = list(self._metadata.get("installed", {}).keys())

        # Combine and sort
        all_installed = set(base_languages) | set(metadata_languages)
        return sorted(all_installed)

    def list_available_languages(self) -> list[str]:
        """List all available languages (installed + downloadable).

        Returns:
            List of all available language names
        """
        # Get installed languages
        installed = set(self.list_installed_languages())

        # Get downloadable languages from discovery service
        available_grammars = self._discovery.list_available_grammars()
        downloadable = {g.name for g in available_grammars}

        # Combine and sort
        all_available = installed | downloadable
        return sorted(all_available)

    def is_language_installed(self, language: str) -> bool:
        """Check if a language is installed.

        Args:
            language: Language name

        Returns:
            True if language is installed and ready
        """
        # Check base registry first
        if self._base_registry.has_language(language):
            return True

        # Check metadata
        return language in self._metadata.get("installed", {})

    def install_language(self, language: str, version: str | None = None) -> bool:
        """Install a language grammar.

        Args:
            language: Language name
            version: Specific version to install

        Returns:
            True if installation successful
        """
        # Check if already installed
        if self.is_language_installed(language):
            logger.info("Language %s is already installed", language)
            return True

        # Get grammar info
        grammar_info = self._discovery.get_grammar_info(language)
        if not grammar_info:
            logger.error("Language %s not found in available grammars", language)
            return False

        # Use specified version or default to latest
        install_version = version or grammar_info.version

        # Download and compile
        success, path = self._downloader.download_and_compile(language, install_version)

        if success:
            # Update metadata
            if "installed" not in self._metadata:
                self._metadata["installed"] = {}

            self._metadata["installed"][language] = {
                "version": install_version,
                "path": path,
                "auto_downloaded": False,  # Manually installed
            }
            self._save_metadata()

            # Re-discover languages
            self._base_registry._discovered = False
            self._base_registry.discover_languages()

            logger.info(
                "Successfully installed %s version %s",
                language,
                install_version,
            )
            return True

        logger.error("Failed to install %s", language)
        return False

    def uninstall_language(self, language: str) -> bool:
        """Uninstall a language grammar.

        Args:
            language: Language name

        Returns:
            True if uninstallation successful
        """
        if not self.is_language_installed(language):
            logger.warning("Language %s is not installed", language)
            return False

        # Remove from metadata
        if language in self._metadata.get("installed", {}):
            grammar_info = self._metadata["installed"][language]

            # Try to remove the compiled file
            if "path" in grammar_info:
                try:
                    grammar_path = Path(grammar_info["path"])
                    if grammar_path.exists():
                        grammar_path.unlink()
                except OSError as e:
                    logger.error("Failed to remove grammar file: %s", e)

            # Remove from metadata
            del self._metadata["installed"][language]

            # Remove from auto_downloaded if it was
            if language in self._auto_downloaded:
                self._auto_downloaded.remove(language)

            self._save_metadata()

            # Re-discover languages
            self._base_registry._discovered = False
            self._base_registry.discover_languages()

            logger.info("Successfully uninstalled %s", language)
            return True

        return False

    def get_language_version(self, language: str) -> str | None:
        """Get the installed version of a language.

        Args:
            language: Language name

        Returns:
            Version string if installed, None otherwise
        """
        if not self.is_language_installed(language):
            return None

        # Check metadata first
        if language in self._metadata.get("installed", {}):
            return self._metadata["installed"][language].get("version", "unknown")

        # Fall back to base registry metadata
        try:
            meta = self._base_registry.get_metadata(language)
            return meta.version
        except (AttributeError, KeyError):
            return None

    def update_language(self, language: str) -> tuple[bool, str]:
        """Update a language to latest version.

        Args:
            language: Language name

        Returns:
            Tuple of (success, message)
        """
        if not self.is_language_installed(language):
            return (False, f"Language {language} is not installed")

        # Get current version
        current_version = self.get_language_version(language)

        # Check for updates
        grammar_info = self._discovery.get_grammar_info(language)
        if not grammar_info:
            return (False, f"Language {language} not found in available grammars")

        latest_version = grammar_info.version

        if current_version == latest_version:
            return (
                True,
                f"Language {language} is already up to date (version {current_version})",
            )

        # Perform update
        success, path = self._downloader.download_and_compile(language, latest_version)

        if success:
            # Update metadata
            self._metadata["installed"][language]["version"] = latest_version
            self._metadata["installed"][language]["path"] = path
            self._save_metadata()

            # Re-discover languages
            self._base_registry._discovered = False
            self._base_registry.discover_languages()

            message = f"Updated {language} from {current_version} to {latest_version}"
            logger.info(message)
            return (True, message)

        return (False, f"Failed to update {language}")

    def get_language_metadata(self, language: str) -> dict[str, Any]:
        """Get metadata about an installed language.

        Args:
            language: Language name

        Returns:
            Metadata dictionary
        """
        if not self.is_language_installed(language):
            return {}

        metadata = {}

        # Get version
        version = self.get_language_version(language)
        if version:
            metadata["version"] = version

        # Get from base registry if available
        if self._base_registry.has_language(language):
            try:
                base_meta = self._base_registry.get_metadata(language)
                metadata["abi_version"] = base_meta.capabilities.get(
                    "language_version",
                    "14",
                )
                metadata["has_scanner"] = base_meta.has_scanner
            except (AttributeError, KeyError):
                logger.debug("Failed to get base metadata for %s", language)

        # Get file extensions from discovery service
        grammar_info = self._discovery.get_grammar_info(language)
        if grammar_info:
            metadata["file_extensions"] = grammar_info.supported_extensions

        # Add installation info
        if language in self._metadata.get("installed", {}):
            install_info = self._metadata["installed"][language]
            metadata["installed_path"] = install_info.get("path", "")
            metadata["auto_downloaded"] = install_info.get("auto_downloaded", False)

        return metadata
