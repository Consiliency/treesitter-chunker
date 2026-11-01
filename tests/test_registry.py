"""Tests for LanguageRegistry component."""

import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from chunker._internal.registry import LanguageMetadata, LanguageRegistry
from chunker.exceptions import (
    LanguageNotFoundError,
    LibraryLoadError,
)


_LIB_EXT = (
    ".dll"
    if sys.platform == "win32"
    else ".dylib" if sys.platform == "darwin" else ".so"
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
    def test_get_language(cls, tmp_path):
        """An unpinned combined library is never mapped; official grammars serve."""
        lib_path = tmp_path / "my-languages.so"
        lib_path.write_bytes(b"unpinned combined library")
        registry = LanguageRegistry(lib_path)
        with patch(
            "chunker._internal.registry.ctypes.CDLL",
            side_effect=AssertionError("unpinned local library loaded"),
        ):
            python_lang = registry.get_language("python")
        assert python_lang is not None
        assert (
            registry.get_metadata("python")
            .capabilities["grammar_source"]
            .startswith("official:")
        )
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
        """A combined library that is not package-supplied is never mapped whole."""
        lib_path = tmp_path / "my-languages.so"
        lib_path.write_bytes(b"not a real shared library")
        registry = LanguageRegistry(lib_path)
        with pytest.raises(LibraryLoadError) as exc_info:
            registry._load_library()
        assert "not a package-supplied library" in str(exc_info.value)
        mock_cdll.assert_not_called()

    @staticmethod
    def test_discover_symbols_scans_validated_libraries(tmp_path):
        """Test symbol discovery scans validated per-language libraries."""
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        (build_dir / f"python{_LIB_EXT}").write_bytes(b"fake")
        (build_dir / f"javascript{_LIB_EXT}").write_bytes(b"fake")
        registry = LanguageRegistry(
            build_dir / f"my-languages{_LIB_EXT}",
            trusted_artifacts={
                "python": {"sha256": "0" * 64},
                "javascript": {"sha256": "1" * 64},
            },
        )

        with patch.object(registry, "_validate_language_library", return_value=True):
            symbols = registry._discover_symbols()

        assert ("python", "tree_sitter_python") in symbols
        assert ("javascript", "tree_sitter_javascript") in symbols

    @staticmethod
    def test_discover_symbols_ignores_failed_validation(tmp_path):
        """Test symbol discovery does not publish failed local grammars."""
        build_dir = tmp_path / "build"
        build_dir.mkdir()
        (build_dir / f"python{_LIB_EXT}").write_bytes(b"fake")
        registry = LanguageRegistry(
            build_dir / f"my-languages{_LIB_EXT}",
            trusted_artifacts={"python": {"sha256": "0" * 64}},
        )

        with patch.object(
            registry, "_validate_language_library", return_value=False
        ) as validate:
            symbols = registry._discover_symbols()
        validate.assert_called_once()

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
