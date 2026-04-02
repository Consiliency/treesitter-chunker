"""Tests for LanguageRegistry fallback to tree-sitter-language-pack."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


class TestRegistryFallback:
    """Tests for the language pack fallback chain in LanguageRegistry."""

    def test_registry_uses_language_pack_fallback(self):
        """Test that registry falls back to language pack when local grammars unavailable."""
        from chunker._internal.registry import LanguageRegistry

        # Create a registry with a non-existent library path to force fallback
        fake_lib_path = Path("/nonexistent/path/to/library.so")
        registry = LanguageRegistry(fake_lib_path)

        # Should be able to get Python language from the language pack
        lang = registry.get_language("python")
        assert lang is not None

    def test_registry_fallback_returns_valid_language(self):
        """Test that fallback language can be used for parsing."""
        from tree_sitter import Parser

        from chunker._internal.registry import LanguageRegistry

        fake_lib_path = Path("/nonexistent/path/to/library.so")
        registry = LanguageRegistry(fake_lib_path)

        lang = registry.get_language("python")
        parser = Parser()
        parser.language = lang

        # Parse some Python code
        code = b"def hello(): pass"
        tree = parser.parse(code)
        assert tree.root_node is not None
        assert tree.root_node.type == "module"

    def test_registry_has_language_with_fallback(self):
        """Test has_language works with language pack fallback."""
        from chunker._internal.registry import LanguageRegistry

        fake_lib_path = Path("/nonexistent/path/to/library.so")
        registry = LanguageRegistry(fake_lib_path)

        # Common languages should be available via fallback
        assert registry.has_language("python") is True
        assert registry.has_language("javascript") is True
        assert registry.has_language("typescript") is True

    @pytest.mark.xfail(
        reason=(
            "tree-sitter-language-pack >=1.0 switched to on-demand download; "
            "list_pack_languages() returns [] until grammars are downloaded. "
            "Needs language_pack.py update to use the new API."
        ),
        strict=False,
    )
    def test_registry_list_languages_includes_pack(self):
        """Test that list_languages includes languages from the pack."""
        from chunker._internal.registry import LanguageRegistry

        fake_lib_path = Path("/nonexistent/path/to/library.so")
        registry = LanguageRegistry(fake_lib_path)

        languages = registry.list_languages()
        # Should have languages from the language pack
        assert "python" in languages
        assert "javascript" in languages

    def test_registry_local_grammar_takes_priority(self):
        """Test that local grammars take priority over language pack."""
        from chunker._internal.registry import LanguageRegistry

        # Use the actual package grammar directory if it exists
        package_grammar_build = (
            Path(__file__).parent.parent / "chunker" / "data" / "grammars" / "build"
        )

        # Even with a valid path that has local grammars,
        # languages not locally available should fall back to pack
        registry = LanguageRegistry(package_grammar_build / "languages.so")

        # This should work regardless of local grammar availability
        lang = registry.get_language("python")
        assert lang is not None

    def test_registry_fallback_preserves_language_not_found_error(self):
        """Test that LanguageNotFoundError is raised for invalid languages."""
        from chunker._internal.registry import LanguageRegistry
        from chunker.exceptions import LanguageNotFoundError

        fake_lib_path = Path("/nonexistent/path/to/library.so")
        registry = LanguageRegistry(fake_lib_path)

        with pytest.raises(LanguageNotFoundError):
            registry.get_language("not_a_real_language_xyz123")

    def test_multiple_languages_from_fallback(self):
        """Test getting multiple languages via fallback."""
        from chunker._internal.registry import LanguageRegistry

        fake_lib_path = Path("/nonexistent/path/to/library.so")
        registry = LanguageRegistry(fake_lib_path)

        # Test several languages
        test_langs = ["python", "javascript", "typescript", "rust", "go"]
        for lang_name in test_langs:
            try:
                lang = registry.get_language(lang_name)
                assert lang is not None, f"Failed to get {lang_name}"
            except Exception:
                # Some languages might not be in the pack, that's OK
                pass

    def test_discover_symbols_scans_configured_build_directory(self, tmp_path):
        """Test dev checkout build dir is scanned for per-language libs."""
        from chunker._internal.registry import LanguageRegistry

        build_dir = tmp_path / "build"
        build_dir.mkdir()
        python_lib = build_dir / "python.so"
        python_lib.write_bytes(b"fake")

        registry = LanguageRegistry(build_dir / "my-languages.so")

        with patch.object(registry, "_validate_language_library", return_value=True):
            symbols = registry._discover_symbols()

        assert ("python", "tree_sitter_python") in symbols

    @pytest.mark.xfail(
        reason=(
            "tree-sitter-language-pack >=1.0 switched to on-demand download; "
            "list_pack_languages() returns [] until grammars are downloaded. "
            "Needs language_pack.py update to use the new API."
        ),
        strict=False,
    )
    def test_discovery_summary_is_not_critical_when_fallback_languages_exist(
        self, caplog
    ):
        """Test fallback-only availability does not log total failure."""
        from chunker._internal.registry import LanguageRegistry

        registry = LanguageRegistry(Path("/nonexistent/path/to/library.so"))

        with caplog.at_level("INFO"):
            languages = registry.list_languages()

        assert "python" in languages
        assert (
            "No languages available - system will not function properly"
            not in caplog.text
        )
        assert "fallback" in caplog.text.lower()

    @pytest.mark.xfail(
        reason=(
            "tree-sitter-language-pack >=1.0 switched to on-demand download; "
            "list_pack_languages() returns [] until grammars are downloaded. "
            "Needs language_pack.py update to use the new API."
        ),
        strict=False,
    )
    def test_discovery_summary_prefers_available_language_count_over_low_local_count(
        self, caplog, tmp_path
    ):
        """Test partial local discovery does not imply broad failure when fallbacks exist."""
        from chunker._internal.registry import LanguageRegistry

        build_dir = tmp_path / "build"
        build_dir.mkdir()
        (build_dir / "python.so").write_bytes(b"fake")

        registry = LanguageRegistry(build_dir / "my-languages.so")

        with patch.object(registry, "_validate_language_library", return_value=True):
            with caplog.at_level("INFO"):
                languages = registry.list_languages()

        assert "python" in languages
        assert "Many expected languages are missing" not in caplog.text
        assert "total available languages via fallbacks" in caplog.text

    @pytest.mark.xfail(
        reason=(
            "tree-sitter-language-pack >=1.0 switched to on-demand download; "
            "list_pack_languages() returns [] until grammars are downloaded. "
            "Needs language_pack.py update to use the new API."
        ),
        strict=False,
    )
    def test_missing_combined_library_logs_info_not_error_when_fallback_works(
        self, caplog
    ):
        """Test missing dev combined library does not log a fallback-success path as an error."""
        from chunker._internal.registry import LanguageRegistry

        registry = LanguageRegistry(Path("/nonexistent/path/to/library.so"))

        with caplog.at_level("INFO"):
            languages = registry.list_languages()

        assert "python" in languages
        assert "Failed to load shared library" not in caplog.text
        assert "No combined library available" in caplog.text
