"""Tests for LanguageRegistry component."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from tree_sitter import Language

from chunker._internal.registry import LanguageMetadata, LanguageRegistry
from chunker.exceptions import (
    LanguageNotFoundError,
    LibraryLoadError,
    LibraryNotFoundError,
)
from chunker.registry import LanguageMetadata, LanguageRegistry


class TestLanguageRegistry:
    """Test the LanguageRegistry class."""

    @classmethod
    def test_init_with_valid_path(cls):
        """Test initialization with valid library path."""
        lib_path = Path(__file__).parent.parent / "build" / "my-languages.so"
        registry = LanguageRegistry(lib_path)
        assert registry._library_path == lib_path
        assert registry._library is None
        assert not registry._discovered

    @classmethod
    def test_init_with_missing_library(cls):
        """Test initialization with non-existent library."""
        fake_path = Path("/nonexistent/library.so")
        with pytest.raises(LibraryNotFoundError) as exc_info:
            LanguageRegistry(fake_path)
        assert str(fake_path) in str(exc_info.value)

    @classmethod
    def test_discover_languages(cls):
        """Test language discovery from library."""
        lib_path = Path(__file__).parent.parent / "build" / "my-languages.so"
        registry = LanguageRegistry(lib_path)
        languages = registry.discover_languages()
        assert isinstance(languages, dict)
        assert len(languages) >= 5
        assert all(
            lang in languages for lang in ["python", "javascript", "c", "cpp", "rust"]
        )
        for lang_name, metadata in languages.items():
            assert isinstance(metadata, LanguageMetadata)
            assert metadata.name == lang_name
            assert metadata.symbol_name == f"tree_sitter_{lang_name}"
            assert isinstance(metadata.has_scanner, bool)
            assert isinstance(metadata.capabilities, dict)
            assert "compatible" in metadata.capabilities
            assert "language_version" in metadata.capabilities

    @classmethod
    def test_get_language(cls):
        """Test getting a specific language."""
        lib_path = Path(__file__).parent.parent / "build" / "my-languages.so"
        registry = LanguageRegistry(lib_path)
        python_lang = registry.get_language("python")
        assert isinstance(python_lang, Language)
        with pytest.raises(LanguageNotFoundError) as exc_info:
            registry.get_language("nonexistent")
        assert "nonexistent" in str(exc_info.value)
        assert "python" in exc_info.value.available

    @classmethod
    def test_list_languages(cls):
        """Test listing available languages."""
        lib_path = Path(__file__).parent.parent / "build" / "my-languages.so"
        registry = LanguageRegistry(lib_path)
        languages = registry.list_languages()
        assert isinstance(languages, list)
        assert languages == sorted(languages)
        assert "python" in languages
        assert "javascript" in languages

    @classmethod
    def test_get_metadata(cls):
        """Test getting language metadata."""
        lib_path = Path(__file__).parent.parent / "build" / "my-languages.so"
        registry = LanguageRegistry(lib_path)
        metadata = registry.get_metadata("python")
        assert isinstance(metadata, LanguageMetadata)
        assert metadata.name == "python"
        assert metadata.symbol_name == "tree_sitter_python"
        with pytest.raises(LanguageNotFoundError):
            registry.get_metadata("nonexistent")

    @classmethod
    def test_has_language(cls):
        """Test checking language availability."""
        lib_path = Path(__file__).parent.parent / "build" / "my-languages.so"
        registry = LanguageRegistry(lib_path)
        assert registry.has_language("python") is True
        assert registry.has_language("nonexistent") is False

    @classmethod
    def test_get_all_metadata(cls):
        """Test getting all language metadata."""
        lib_path = Path(__file__).parent.parent / "build" / "my-languages.so"
        registry = LanguageRegistry(lib_path)
        all_metadata = registry.get_all_metadata()
        assert isinstance(all_metadata, dict)
        assert len(all_metadata) >= 5
        for lang_name, metadata in all_metadata.items():
            assert isinstance(metadata, LanguageMetadata)
            assert metadata.name == lang_name

    @classmethod
    @patch("ctypes.CDLL")
    def test_library_load_error(cls, mock_cdll):
        """Test handling of library load errors."""
        mock_cdll.side_effect = OSError("Cannot load library")
        lib_path = Path(__file__).parent.parent / "build" / "my-languages.so"
        registry = LanguageRegistry(lib_path)
        with pytest.raises(LibraryLoadError) as exc_info:
            registry._load_library()
        assert "Cannot load library" in str(exc_info.value)

    @classmethod
    @patch("subprocess.run")
    def test_discover_symbols_with_nm(cls, mock_run):
        """Test symbol discovery using nm command."""
        mock_result = Mock()
        mock_result.returncode = 0
        mock_result.stdout = """
0000000000001234 T tree_sitter_python
0000000000002345 T tree_sitter_javascript
0000000000003456 T tree_sitter_python_external_scanner_create
"""
        mock_run.return_value = mock_result
        lib_path = Path(__file__).parent.parent / "build" / "my-languages.so"
        registry = LanguageRegistry(lib_path)
        symbols = registry._discover_symbols()
        assert len(symbols) == 2
        assert ("python", "tree_sitter_python") in symbols
        assert ("javascript", "tree_sitter_javascript") in symbols

    @classmethod
    @patch("subprocess.run")
    def test_discover_symbols_fallback(cls, mock_run):
        """Test symbol discovery fallback when nm fails."""
        mock_result = Mock()
        mock_result.returncode = 1
        mock_run.return_value = mock_result
        lib_path = Path(__file__).parent.parent / "build" / "my-languages.so"
        registry = LanguageRegistry(lib_path)
        symbols = registry._discover_symbols()
        assert len(symbols) == 5
        assert ("python", "tree_sitter_python") in symbols
        assert ("rust", "tree_sitter_rust") in symbols

    @classmethod
    def test_lazy_discovery(cls):
        """Test that discovery only happens once."""
        lib_path = Path(__file__).parent.parent / "build" / "my-languages.so"
        registry = LanguageRegistry(lib_path)
        languages1 = registry.list_languages()
        assert registry._discovered is True
        with patch.object(registry, "_discover_symbols") as mock_discover:
            languages2 = registry.list_languages()
            mock_discover.assert_not_called()
        assert languages1 == languages2

    @classmethod
    def test_scanner_detection(cls):
        """Test external scanner detection."""
        lib_path = Path(__file__).parent.parent / "build" / "my-languages.so"
        registry = LanguageRegistry(lib_path)
        c_metadata = registry.get_metadata("c")
        cpp_metadata = registry.get_metadata("cpp")
        assert c_metadata.has_scanner is False
        assert cpp_metadata.has_scanner is True
        assert cpp_metadata.capabilities["external_scanner"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
