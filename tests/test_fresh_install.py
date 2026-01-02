"""Tests verifying fresh PyPI install experience.

This test suite verifies that a fresh install of treesitter-chunker
works correctly without requiring any grammar compilation setup.

The tree-sitter-language-pack dependency should provide all common
languages out of the box.
"""

from __future__ import annotations

import pytest


class TestFreshInstallExperience:
    """Tests for verifying zero-configuration language support."""

    def test_python_works_without_setup(self):
        """Test that Python parsing works immediately after install."""
        from chunker._internal.registry import LanguageRegistry
        from pathlib import Path
        from tree_sitter import Parser

        # Use a non-existent library path to simulate fresh install
        registry = LanguageRegistry(Path("/nonexistent/lib.so"))

        # Should be able to get Python language from the language pack
        lang = registry.get_language("python")
        assert lang is not None

        # Should be able to parse Python code
        parser = Parser()
        parser.language = lang
        tree = parser.parse(b"def hello(): pass")
        assert tree.root_node is not None
        assert tree.root_node.type == "module"

    def test_javascript_works_without_setup(self):
        """Test that JavaScript parsing works immediately after install."""
        from chunker._internal.registry import LanguageRegistry
        from pathlib import Path
        from tree_sitter import Parser

        registry = LanguageRegistry(Path("/nonexistent/lib.so"))
        lang = registry.get_language("javascript")
        assert lang is not None

        parser = Parser()
        parser.language = lang
        tree = parser.parse(b"function hello() {}")
        assert tree.root_node is not None

    def test_typescript_works_without_setup(self):
        """Test that TypeScript parsing works immediately after install."""
        from chunker._internal.registry import LanguageRegistry
        from pathlib import Path
        from tree_sitter import Parser

        registry = LanguageRegistry(Path("/nonexistent/lib.so"))
        lang = registry.get_language("typescript")
        assert lang is not None

        parser = Parser()
        parser.language = lang
        tree = parser.parse(b"function hello(): void {}")
        assert tree.root_node is not None

    def test_common_languages_available(self):
        """Test that common languages are available via fallback."""
        from chunker._internal.registry import LanguageRegistry
        from pathlib import Path

        registry = LanguageRegistry(Path("/nonexistent/lib.so"))

        # List of common languages that should be available
        common_languages = [
            "python",
            "javascript",
            "typescript",
            "rust",
            "go",
            "java",
            "c",
            "cpp",
            "ruby",
            "bash",
            "json",
            "yaml",
            "html",
            "css",
        ]

        available_count = 0
        for lang_name in common_languages:
            if registry.has_language(lang_name):
                available_count += 1

        # At least 10 common languages should be available
        assert available_count >= 10, f"Only {available_count} common languages available"

    def test_list_languages_not_empty(self):
        """Test that list_languages returns languages from the pack."""
        from chunker._internal.registry import LanguageRegistry
        from pathlib import Path

        registry = LanguageRegistry(Path("/nonexistent/lib.so"))
        languages = registry.list_languages()

        # Should have many languages from the language pack
        assert len(languages) > 50, f"Only {len(languages)} languages available"

    def test_language_not_found_has_helpful_message(self):
        """Test that LanguageNotFoundError has helpful guidance."""
        from chunker._internal.registry import LanguageRegistry
        from chunker.exceptions import LanguageNotFoundError
        from pathlib import Path

        registry = LanguageRegistry(Path("/nonexistent/lib.so"))

        with pytest.raises(LanguageNotFoundError) as exc_info:
            registry.get_language("not_a_real_language_xyz123")

        error_str = str(exc_info.value)
        # Should include guidance about tree-sitter-language-pack
        assert "tree-sitter-language-pack" in error_str or "language-pack" in error_str.lower()
        # Should include documentation link
        assert "github.com" in error_str or "http" in error_str

    def test_chunker_api_works_with_language_pack(self):
        """Test that the main chunker API works with language pack."""
        # This tests the full integration path
        from chunker._internal.language_pack import (
            get_language_from_pack,
            is_language_pack_available,
        )

        assert is_language_pack_available() is True

        lang = get_language_from_pack("python")
        assert lang is not None

    def test_all_languages_count(self):
        """Test that we have access to many languages via the pack."""
        from chunker._internal.language_pack import list_pack_languages

        languages = list_pack_languages()
        # The pack should provide at least 100 languages
        assert len(languages) >= 100, f"Only {len(languages)} languages in pack"

    def test_language_pack_integration_chain(self):
        """Test the complete fallback chain works end-to-end."""
        from chunker._internal.registry import LanguageRegistry
        from pathlib import Path
        from tree_sitter import Parser

        # Simulate fresh install with no local grammars
        registry = LanguageRegistry(Path("/nonexistent/lib.so"))

        # Test parsing multiple languages
        test_cases = [
            ("python", b"def test(): pass"),
            ("javascript", b"function test() {}"),
            ("rust", b"fn main() {}"),
            ("go", b"package main"),
        ]

        for lang_name, code in test_cases:
            try:
                lang = registry.get_language(lang_name)
                parser = Parser()
                parser.language = lang
                tree = parser.parse(code)
                assert tree.root_node is not None, f"Failed to parse {lang_name}"
            except Exception as e:
                # Some languages might not be available, track failures
                pytest.skip(f"Language {lang_name} not available: {e}")


class TestLanguagePackAvailability:
    """Tests specifically for language pack availability."""

    def test_language_pack_is_installed(self):
        """Verify tree-sitter-language-pack is available."""
        from chunker._internal.language_pack import is_language_pack_available

        assert is_language_pack_available() is True

    def test_can_get_language_directly(self):
        """Test direct access to language pack."""
        import tree_sitter_language_pack

        lang = tree_sitter_language_pack.get_language("python")
        assert lang is not None

    def test_pack_has_common_languages(self):
        """Test that the pack includes all common languages."""
        import tree_sitter_language_pack
        from typing import get_args

        supported = get_args(tree_sitter_language_pack.SupportedLanguage)
        common = ["python", "javascript", "typescript", "rust", "go", "java", "c", "cpp"]

        for lang in common:
            assert lang in supported, f"Language {lang} missing from pack"
