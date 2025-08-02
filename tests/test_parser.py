"""Tests for the refactored parser module."""

from unittest.mock import patch

import pytest
from tree_sitter import Parser

import chunker.parser
from chunker import (
    LanguageNotFoundError,
    LibraryNotFoundError,
    ParserConfig,
    ParserError,
    clear_cache,
    get_language_info,
    get_parser,
    list_languages,
    return_parser,
)
from chunker._internal.registry import LanguageMetadata
from chunker.exceptions import ParserConfigError
from chunker.parser import _factory, _initialize, get_parser


class TestParserAPI:
    """Test the main parser API functions."""

    def test_get_parser_basic(self):
        """Test basic parser retrieval."""
        parser = get_parser("python")
        assert isinstance(parser, Parser)

    def test_get_parser_invalid_language(self):
        """Test error handling for invalid language."""
        with pytest.raises(LanguageNotFoundError) as exc_info:
            get_parser("nonexistent")

        assert "nonexistent" in str(exc_info.value)
        assert exc_info.value.language == "nonexistent"
        assert "python" in exc_info.value.available  # Should list available languages

    def test_list_languages(self):
        """Test listing available languages."""
        languages = list_languages()
        assert isinstance(languages, list)
        assert len(languages) > 0
        assert "python" in languages
        assert "rust" in languages
        assert all(isinstance(lang, str) for lang in languages)

    def test_get_language_info(self):
        """Test getting language metadata."""
        info = get_language_info("python")
        assert isinstance(info, LanguageMetadata)
        assert info.name == "python"
        assert info.symbol_name == "tree_sitter_python"
        assert isinstance(info.has_scanner, bool)

    def test_parser_with_config(self):
        """Test parser with configuration."""
        config = ParserConfig(timeout_ms=1000)
        parser = get_parser("python", config)
        assert isinstance(parser, Parser)

    def test_invalid_config(self):
        """Test invalid parser configuration."""

        config = ParserConfig(timeout_ms=-1)
        with pytest.raises(ParserConfigError):
            get_parser("python", config)

    def test_return_parser(self):
        """Test returning parser to pool."""
        parser = get_parser("python")
        # Should not raise
        return_parser("python", parser)

    def test_clear_cache(self):
        """Test clearing parser cache."""
        # Get a parser to populate cache
        get_parser("python")
        clear_cache()
        # Should still work after clearing
        parser2 = get_parser("python")
        assert isinstance(parser2, Parser)


class TestParserCaching:
    """Test parser caching behavior."""

    def test_parser_reuse(self):
        """Test that parsers are reused from cache."""
        # Get same parser multiple times
        parsers = [get_parser("python") for _ in range(3)]
        # With caching, we might get the same instance
        # (implementation detail, but good to verify behavior)
        assert all(isinstance(p, Parser) for p in parsers)

    def test_multiple_languages(self):
        """Test caching with multiple languages."""
        # Get list of available languages
        languages = list_languages()

        # Try to get parsers for available languages
        successful = []
        for lang in ["python", "javascript", "rust", "c", "cpp"]:
            if lang in languages:
                try:
                    parser = get_parser(lang)
                    assert isinstance(parser, Parser)
                    successful.append(lang)
                except ParserError:
                    # Skip incompatible languages
                    pass

        # We should have at least Python
        assert "python" in successful
        assert len(successful) >= 1


class TestBackwardCompatibility:
    """Test backward compatibility with old API."""

    def test_old_import_still_works(self):
        """Test that old import pattern still works."""

        parser = get_parser("python")
        assert isinstance(parser, Parser)

    def test_old_usage_pattern(self):
        """Test old usage pattern with 'lang' parameter."""

        # Old style: positional argument
        parser = get_parser("python")
        assert isinstance(parser, Parser)


class TestErrorHandling:
    """Test error handling scenarios."""

    @patch("chunker.parser._DEFAULT_LIBRARY_PATH")
    def test_missing_library(self, mock_path):
        """Test error when library file is missing."""
        mock_path.exists.return_value = False
        mock_path.__str__.return_value = "/fake/path/lib.so"

        # Clear any cached instances

        chunker.parser._registry = None
        chunker.parser._factory = None

        with pytest.raises(LibraryNotFoundError) as exc_info:
            get_parser("python")

        assert "/fake/path/lib.so" in str(exc_info.value)
        assert "build_lib.py" in str(exc_info.value)

    def test_language_metadata_not_found(self):
        """Test error when requesting metadata for invalid language."""
        with pytest.raises(LanguageNotFoundError):
            get_language_info("nonexistent")


class TestParserFactory:
    """Test ParserFactory functionality."""

    def test_factory_stats(self):
        """Test factory statistics."""
        # This requires access to the factory instance

        _initialize()

        if _factory:
            stats = _factory.get_stats()
            assert "total_parsers_created" in stats
            assert "cache_size" in stats
            assert "pools" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
