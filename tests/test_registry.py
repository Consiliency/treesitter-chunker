"""Tests for LanguageRegistry component."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from chunker._internal.registry import LanguageMetadata, LanguageRegistry
from chunker.exceptions import (
    LanguageNotFoundError,
    LibraryLoadError,
)


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

    @staticmethod
    def test_init_with_missing_library():
        """Test initialization tolerates a missing combined library."""
        fake_path = Path("/nonexistent/library.so")
        registry = LanguageRegistry(fake_path)
        assert registry._library_path == fake_path
        assert registry._library is None

    @classmethod
    @pytest.mark.filterwarnings("error::DeprecationWarning")
    def test_discover_languages(cls):
        """Test language discovery from library."""
        lib_path = Path(__file__).parent.parent / "build" / "my-languages.so"
        registry = LanguageRegistry(lib_path)
        languages = registry.discover_languages()
        assert isinstance(languages, dict)
        assert len(languages) >= 1
        assert "python" in languages
        for lang_name, metadata in languages.items():
            assert isinstance(metadata, LanguageMetadata)
            assert metadata.name == lang_name
            assert metadata.symbol_name == f"tree_sitter_{lang_name}"
            assert isinstance(metadata.has_scanner, bool)
            assert isinstance(metadata.capabilities, dict)
            assert "compatible" in metadata.capabilities
            assert "language_version" in metadata.capabilities

    @classmethod
    @pytest.mark.filterwarnings("error::DeprecationWarning")
    def test_get_language(cls):
        """Test getting a specific language."""
        lib_path = Path(__file__).parent.parent / "build" / "my-languages.so"
        registry = LanguageRegistry(lib_path)
        # NOTE: The following block mocks the underlying C library and Language construction
        # to ensure the test can pass in environments without a valid compiled shared library.
        # This is intentionally annotated so we remember it's a test-time mock.
        with (
            patch("ctypes.CDLL") as mock_cdll,
            patch(
                "chunker._internal.registry.Language",
            ) as MockLanguage,
            patch(
                "chunker._internal.registry.Parser",
            ) as MockParser,
        ):
            # Mock the CDLL to provide a callable symbol for python
            fake_lib = Mock()

            def fake_symbol():
                return 1  # non-null pointer value; used only by the mocked Language

            fake_lib.tree_sitter_python = fake_symbol
            mock_cdll.return_value = fake_lib
            # Make the mocked Language callable and return an instance
            lang_instance = MockLanguage()
            MockLanguage.return_value = lang_instance
            # Mock parser.language assignment to accept our mocked Language
            parser_instance = Mock()
            type(parser_instance).language = Mock()
            MockParser.return_value = parser_instance
            python_lang = registry.get_language("python")
            assert python_lang is lang_instance
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
    @pytest.mark.filterwarnings("error::DeprecationWarning")
    def test_has_language(cls):
        """Test checking language availability."""
        lib_path = Path(__file__).parent.parent / "build" / "my-languages.so"
        registry = LanguageRegistry(lib_path)
        assert registry.has_language("python") is True
        assert registry.has_language("nonexistent") is False

    @classmethod
    @pytest.mark.filterwarnings("error::DeprecationWarning")
    def test_get_all_metadata(cls):
        """Test getting all language metadata."""
        lib_path = Path(__file__).parent.parent / "build" / "my-languages.so"
        registry = LanguageRegistry(lib_path)
        all_metadata = registry.get_all_metadata()
        assert isinstance(all_metadata, dict)
        assert len(all_metadata) >= 1
        for lang_name, metadata in all_metadata.items():
            assert isinstance(metadata, LanguageMetadata)
            assert metadata.name == lang_name

    @staticmethod
    @patch("ctypes.CDLL")
    def test_library_load_error(mock_cdll, tmp_path):
        """Test handling of library load errors."""
        mock_cdll.side_effect = OSError("Cannot load library")
        lib_path = tmp_path / "my-languages.so"
        lib_path.write_bytes(b"not a real shared library")
        registry = LanguageRegistry(lib_path)
        with pytest.raises(LibraryLoadError) as exc_info:
            registry._load_library()
        assert "Cannot load library" in str(exc_info.value)

    @staticmethod
    def test_discover_symbols_scans_validated_libraries(tmp_path):
        """Test symbol discovery scans validated per-language libraries."""
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        (build_dir / "python.so").write_bytes(b"fake")
        (build_dir / "javascript.so").write_bytes(b"fake")
        registry = LanguageRegistry(build_dir / "my-languages.so")

        with patch.object(registry, "_validate_language_library", return_value=True):
            symbols = registry._discover_symbols()

        assert ("python", "tree_sitter_python") in symbols
        assert ("javascript", "tree_sitter_javascript") in symbols

    @staticmethod
    def test_discover_symbols_ignores_failed_validation(tmp_path):
        """Test symbol discovery does not publish failed local grammars."""
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        (build_dir / "python.so").write_bytes(b"fake")
        registry = LanguageRegistry(build_dir / "my-languages.so")

        with patch.object(registry, "_validate_language_library", return_value=False):
            symbols = registry._discover_symbols()

        assert ("python", "tree_sitter_python") not in symbols

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
    @pytest.mark.filterwarnings("error::DeprecationWarning")
    def test_scanner_detection(cls):
        """Test external scanner metadata for discovered languages."""
        lib_path = Path(__file__).parent.parent / "build" / "my-languages.so"
        registry = LanguageRegistry(lib_path)
        c_metadata = registry.get_metadata("c")
        assert c_metadata.has_scanner is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
