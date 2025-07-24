"""Unit tests for the UniversalLanguageRegistry."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from chunker.contracts.discovery_stub import GrammarDiscoveryStub
from chunker.contracts.download_stub import GrammarDownloadStub
from chunker.exceptions import LanguageNotFoundError
from chunker.grammar.registry import UniversalLanguageRegistry


class TestUniversalLanguageRegistry:
    """Test UniversalLanguageRegistry functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Create temporary directories
        self.temp_dir = tempfile.mkdtemp()
        self.cache_dir = Path(self.temp_dir) / "cache"
        self.lib_path = Path(self.temp_dir) / "test-languages.so"

        # Create a dummy library file
        self.lib_path.touch()

        # Create stub services
        self.discovery = GrammarDiscoveryStub()
        self.downloader = GrammarDownloadStub()

        # Mock the base registry
        with patch("chunker.grammar.registry.LanguageRegistry") as mock_registry_class:
            self.mock_base_registry = MagicMock()
            mock_registry_class.return_value = self.mock_base_registry

            # Create registry instance
            self.registry = UniversalLanguageRegistry(
                self.lib_path,
                self.discovery,
                self.downloader,
                self.cache_dir,
            )

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_initialization(self):
        """Test registry initialization."""
        assert self.registry._cache_dir == self.cache_dir
        assert self.registry._metadata_path == self.cache_dir / "registry_metadata.json"
        assert isinstance(self.registry._metadata, dict)
        assert self.cache_dir.exists()

    def test_get_parser_existing_language(self):
        """Test getting parser for already installed language."""
        # Mock base registry to have the language
        self.mock_base_registry.has_language.return_value = True

        # Mock tree_sitter.Parser to avoid actual language assignment
        with patch("chunker.grammar.registry.tree_sitter.Parser") as mock_parser_class:
            mock_parser = MagicMock()
            mock_parser_class.return_value = mock_parser

            # Get parser
            parser = self.registry.get_parser("python", auto_download=False)

            # Verify
            assert parser == mock_parser
            self.mock_base_registry.has_language.assert_called_with("python")
            self.mock_base_registry.get_language.assert_called_with("python")

    def test_get_parser_auto_download(self):
        """Test auto-downloading when language not available."""
        # Mock base registry to not have the language initially, then have it after download
        self.mock_base_registry.has_language.side_effect = [False, True]

        # Mock discovery to return info for go
        from datetime import datetime

        from chunker.contracts.discovery_contract import GrammarInfo

        go_info = GrammarInfo(
            name="go",
            url="https://github.com/tree-sitter/tree-sitter-go",
            version="0.20.0",
            last_updated=datetime(2023, 1, 1),
            stars=300,
            description="Go grammar for tree-sitter",
            supported_extensions=[".go"],
            official=True,
        )

        with (
            patch.object(self.discovery, "get_grammar_info", return_value=go_info),
            patch(
                "chunker.grammar.registry.tree_sitter.Parser",
            ) as mock_parser_class,
        ):
            mock_parser = MagicMock()
            mock_parser_class.return_value = mock_parser

            # Get parser with auto-download
            parser = self.registry.get_parser("go", auto_download=True)

            # Verify
            assert parser == mock_parser
            assert "go" in self.registry._auto_downloaded

            # Check metadata was saved
            assert self.registry._metadata_path.exists()
            with self.registry._metadata_path.open() as f:
                metadata = json.load(f)
                assert "go" in metadata["auto_downloaded"]
                assert "go" in metadata["installed"]

    def test_get_parser_no_auto_download(self):
        """Test error when language not available and auto-download disabled."""
        # Mock base registry to not have the language
        self.mock_base_registry.has_language.return_value = False
        self.mock_base_registry.list_languages.return_value = ["python", "rust"]

        # Mock discovery to not have go in available grammars
        with patch.object(self.discovery, "list_available_grammars", return_value=[]):
            # Should raise error
            with pytest.raises(LanguageNotFoundError) as exc_info:
                self.registry.get_parser("go", auto_download=False)

            assert "go" in str(exc_info.value)

    def test_list_installed_languages(self):
        """Test listing installed languages."""
        # Mock base registry languages
        self.mock_base_registry.list_languages.return_value = ["python", "rust"]

        # Add metadata for additional language
        self.registry._metadata["installed"] = {
            "go": {"version": "0.20.0", "path": str(self.cache_dir / "go.so")},
        }

        # Get installed languages
        languages = self.registry.list_installed_languages()

        # Verify
        assert sorted(languages) == ["go", "python", "rust"]

    def test_list_available_languages(self):
        """Test listing all available languages."""
        # Mock installed languages
        self.mock_base_registry.list_languages.return_value = ["python", "rust"]

        # Available languages include more from discovery
        languages = self.registry.list_available_languages()

        # Verify - should include both installed and discoverable
        assert "python" in languages
        assert "rust" in languages
        # The discovery stub only returns python and rust by default

    def test_is_language_installed(self):
        """Test checking if language is installed."""
        # Mock base registry
        self.mock_base_registry.has_language.side_effect = lambda x: x in [
            "python",
            "rust",
        ]

        # Add to metadata
        self.registry._metadata["installed"] = {
            "go": {"version": "0.20.0", "path": str(self.cache_dir / "go.so")},
        }

        # Test various languages
        assert self.registry.is_language_installed("python") is True
        assert self.registry.is_language_installed("rust") is True
        assert self.registry.is_language_installed("go") is True
        assert self.registry.is_language_installed("java") is False

    def test_install_language(self):
        """Test manual language installation."""
        # Mock that language is not installed
        self.mock_base_registry.has_language.return_value = False

        # Install language
        success = self.registry.install_language("python", "0.20.0")

        # Verify
        assert success is True
        assert "python" in self.registry._metadata["installed"]
        assert self.registry._metadata["installed"]["python"]["version"] == "0.20.0"
        assert (
            self.registry._metadata["installed"]["python"]["auto_downloaded"] is False
        )

    def test_install_language_already_installed(self):
        """Test installing already installed language."""
        # Mock that language is installed
        self.mock_base_registry.has_language.return_value = True

        # Install language
        success = self.registry.install_language("python")

        # Should succeed without doing anything
        assert success is True

    def test_uninstall_language(self):
        """Test uninstalling a language."""
        # Set up installed language in metadata
        self.registry._metadata["installed"] = {
            "go": {
                "version": "0.20.0",
                "path": str(self.cache_dir / "go.so"),
                "auto_downloaded": True,
            },
        }
        self.registry._auto_downloaded.add("go")

        # Create dummy file
        grammar_file = self.cache_dir / "go.so"
        grammar_file.parent.mkdir(parents=True, exist_ok=True)
        grammar_file.touch()

        # Uninstall
        success = self.registry.uninstall_language("go")

        # Verify
        assert success is True
        assert "go" not in self.registry._metadata["installed"]
        assert "go" not in self.registry._auto_downloaded
        assert not grammar_file.exists()

    def test_get_language_version(self):
        """Test getting language version."""
        # Set up metadata
        self.registry._metadata["installed"] = {
            "go": {"version": "0.20.0", "path": str(self.cache_dir / "go.so")},
        }

        # Mock base registry for python
        self.mock_base_registry.has_language.side_effect = lambda x: x == "python"
        mock_meta = Mock()
        mock_meta.version = "0.19.0"
        self.mock_base_registry.get_metadata.return_value = mock_meta

        # Test versions
        assert self.registry.get_language_version("go") == "0.20.0"
        assert self.registry.get_language_version("python") == "0.19.0"
        assert self.registry.get_language_version("java") is None

    def test_update_language(self):
        """Test updating a language."""
        # Set up installed language with old version
        self.registry._metadata["installed"] = {
            "python": {"version": "0.19.0", "path": str(self.cache_dir / "python.so")},
        }

        # Mock base registry
        self.mock_base_registry.has_language.return_value = True

        # Update language
        success, message = self.registry.update_language("python")

        # Verify
        assert success is True
        assert "0.19.0 to 0.20.0" in message
        assert self.registry._metadata["installed"]["python"]["version"] == "0.20.0"

    def test_update_language_already_latest(self):
        """Test updating language that's already latest."""
        # Set up installed language with latest version
        self.registry._metadata["installed"] = {
            "python": {"version": "0.20.0", "path": str(self.cache_dir / "python.so")},
        }

        # Update language
        success, message = self.registry.update_language("python")

        # Verify
        assert success is True
        assert "already up to date" in message

    def test_get_language_metadata(self):
        """Test getting language metadata."""
        # Set up metadata
        self.registry._metadata["installed"] = {
            "python": {
                "version": "0.20.0",
                "path": str(self.cache_dir / "python.so"),
                "auto_downloaded": True,
            },
        }

        # Mock base registry
        self.mock_base_registry.has_language.return_value = True
        mock_meta = Mock()
        mock_meta.has_scanner = True
        mock_meta.capabilities = {"language_version": "14"}
        self.mock_base_registry.get_metadata.return_value = mock_meta

        # Get metadata
        metadata = self.registry.get_language_metadata("python")

        # Verify
        assert metadata["version"] == "0.20.0"
        assert metadata["abi_version"] == "14"
        assert metadata["has_scanner"] is True
        assert metadata["auto_downloaded"] is True
        assert metadata["installed_path"] == str(self.cache_dir / "python.so")
        assert metadata["file_extensions"] == [".py", ".pyw"]

    def test_metadata_persistence(self):
        """Test that metadata persists across registry instances."""
        # Add some metadata
        self.registry._metadata["installed"] = {
            "go": {"version": "0.20.0", "path": str(self.cache_dir / "go.so")},
        }
        self.registry._auto_downloaded.add("go")
        self.registry._save_metadata()

        # Create new registry instance
        with patch("chunker.grammar.registry.LanguageRegistry"):
            new_registry = UniversalLanguageRegistry(
                self.lib_path,
                self.discovery,
                self.downloader,
                self.cache_dir,
            )

        # Verify metadata was loaded
        assert "go" in new_registry._metadata["installed"]
        assert "go" in new_registry._auto_downloaded
