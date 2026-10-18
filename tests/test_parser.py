"""Tests for the refactored parser module."""

from unittest.mock import patch

import pytest
from tree_sitter import Parser

import chunker.parser
from chunker import (
    LanguageNotFoundError,
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
from tests.test_language_pack import (
    _UNICODE_492_CASES,
    _assert_unicode_492_tree,
    _isolate_default_492,
)


@pytest.mark.parametrize(
    ("language", "source", "case"),
    _UNICODE_492_CASES,
    ids=[item[2] for item in _UNICODE_492_CASES],
)
@pytest.mark.parametrize("leased", [False, True])
def test_492_public_unicode_grammar(
    monkeypatch, tmp_path, language, source, case, leased
):
    from chunker.parser import acquire_parser

    _isolate_default_492(monkeypatch, tmp_path)
    if leased:
        with acquire_parser(language) as parser:
            _assert_unicode_492_tree(parser.parse(source.encode("utf-8")), source)
    else:
        _assert_unicode_492_tree(
            get_parser(language).parse(source.encode("utf-8")), source
        )


class TestParserAPI:
    """Test the main parser API functions."""

    @staticmethod
    def test_get_parser_basic():
        """Test basic parser retrieval."""
        parser = get_parser("python")
        assert isinstance(parser, Parser)

    @staticmethod
    def test_get_parser_invalid_language():
        """Test error handling for invalid language."""
        with pytest.raises(LanguageNotFoundError) as exc_info:
            get_parser("nonexistent")
        assert "nonexistent" in str(exc_info.value)
        assert exc_info.value.language == "nonexistent"
        assert "python" in exc_info.value.available

    @staticmethod
    def test_list_languages():
        """Test listing available languages."""
        languages = list_languages()
        assert isinstance(languages, list)
        assert len(languages) > 0
        assert "python" in languages
        assert "rust" in languages
        assert all(isinstance(lang, str) for lang in languages)

    @staticmethod
    def test_get_language_info():
        """Test getting language metadata."""
        info = get_language_info("python")
        assert isinstance(info, LanguageMetadata)
        assert info.name == "python"
        assert info.symbol_name == "tree_sitter_python"
        assert isinstance(info.has_scanner, bool)

    @classmethod
    def test_parser_with_config(cls):
        """Test parser with configuration."""
        config = ParserConfig()
        parser = get_parser("python", config)
        assert isinstance(parser, Parser)

    @classmethod
    def test_invalid_config(cls):
        """Test invalid parser configuration."""
        config = ParserConfig(timeout_ms=-1)
        with pytest.raises(ParserConfigError):
            get_parser("python", config)

    @staticmethod
    def test_return_parser():
        """Test returning parser to pool."""
        parser = get_parser("python")
        return_parser("python", parser)

    @staticmethod
    def test_clear_cache():
        """Test clearing parser cache."""
        get_parser("python")
        clear_cache()
        parser2 = get_parser("python")
        assert isinstance(parser2, Parser)


class TestParserCaching:
    """Test parser caching behavior."""

    @staticmethod
    def test_parser_reuse():
        """Test that parsers are reused from cache."""
        parsers = [get_parser("python") for _ in range(3)]
        assert all(isinstance(p, Parser) for p in parsers)

    @staticmethod
    def test_multiple_languages():
        """Test caching with multiple languages."""
        languages = list_languages()
        successful = []
        for lang in ["python", "javascript", "rust", "c", "cpp"]:
            if lang in languages:
                try:
                    parser = get_parser(lang)
                    assert isinstance(parser, Parser)
                    successful.append(lang)
                except ParserError:
                    pass
        assert "python" in successful
        assert len(successful) >= 1


class TestBackwardCompatibility:
    """Test backward compatibility with old API."""

    @staticmethod
    def test_old_import_still_works():
        """Test that old import pattern still works."""
        parser = get_parser("python")
        assert isinstance(parser, Parser)

    @staticmethod
    def test_old_usage_pattern():
        """Test old usage pattern with 'lang' parameter."""
        parser = get_parser("python")
        assert isinstance(parser, Parser)


class TestErrorHandling:
    """Test error handling scenarios."""

    @staticmethod
    @patch("chunker.parser._state.default_library_path")
    def test_missing_library_uses_language_pack_fallback(mock_path):
        """Test missing combined library still allows language-pack fallback."""
        mock_path.exists.return_value = False
        mock_path.__str__.return_value = "/fake/path/lib.so"
        chunker.parser._state.registry = None
        chunker.parser._state.factory = None
        parser = get_parser("python")
        assert isinstance(parser, Parser)

    @staticmethod
    def test_language_metadata_not_found():
        """Test error when requesting metadata for invalid language."""
        with pytest.raises(LanguageNotFoundError):
            get_language_info("nonexistent")


class TestParserFactory:
    """Test ParserFactory functionality."""

    @staticmethod
    def test_factory_stats():
        """Test factory statistics."""
        chunker.parser._state.initialize()
        if chunker.parser._state.factory:
            stats = chunker.parser._state.factory.get_stats()
            assert "total_parsers_created" in stats
            assert "cache_size" in stats
            assert "pools" in stats


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
