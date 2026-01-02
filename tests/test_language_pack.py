"""Tests for the tree-sitter-language-pack integration."""

from __future__ import annotations

import pytest


class TestLanguagePackProvider:
    """Tests for LanguagePackProvider wrapper."""

    def test_is_language_pack_available(self):
        """Test that we can detect if language pack is installed."""
        from chunker._internal.language_pack import is_language_pack_available

        # Since we have tree-sitter-language-pack as a dependency, it should be available
        assert is_language_pack_available() is True

    def test_get_language_from_pack_python(self):
        """Test getting Python language from the language pack."""
        from chunker._internal.language_pack import get_language_from_pack

        lang = get_language_from_pack("python")
        assert lang is not None
        # Verify it's a valid Language object
        from tree_sitter import Language

        assert isinstance(lang, Language)

    def test_get_language_from_pack_javascript(self):
        """Test getting JavaScript language from the language pack."""
        from chunker._internal.language_pack import get_language_from_pack

        lang = get_language_from_pack("javascript")
        assert lang is not None
        from tree_sitter import Language

        assert isinstance(lang, Language)

    def test_get_language_from_pack_typescript(self):
        """Test getting TypeScript language from the language pack."""
        from chunker._internal.language_pack import get_language_from_pack

        lang = get_language_from_pack("typescript")
        assert lang is not None
        from tree_sitter import Language

        assert isinstance(lang, Language)

    def test_get_language_from_pack_invalid(self):
        """Test that invalid language returns None."""
        from chunker._internal.language_pack import get_language_from_pack

        lang = get_language_from_pack("not_a_real_language_xyz123")
        assert lang is None

    def test_list_available_languages(self):
        """Test listing all available languages from the pack."""
        from chunker._internal.language_pack import list_pack_languages

        languages = list_pack_languages()
        assert isinstance(languages, list)
        assert len(languages) > 0
        # Should have common languages
        assert "python" in languages
        assert "javascript" in languages

    def test_language_pack_provider_class(self):
        """Test the LanguagePackProvider class interface."""
        from chunker._internal.language_pack import LanguagePackProvider

        provider = LanguagePackProvider()
        assert provider.is_available() is True

        lang = provider.get_language("python")
        assert lang is not None

        languages = provider.list_languages()
        assert "python" in languages
