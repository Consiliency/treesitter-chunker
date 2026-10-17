"""Tests for the tree-sitter-language-pack integration."""

from __future__ import annotations

import ast

import pytest
from tree_sitter import Parser


_UNICODE_492_CASES = [
    (language, template.format(char=char), f"{kind}-{ord(char):04x}")
    for char in ("\u017f", "\u212a")
    for language, kind, template in (
        ("python", "python-comment", "# {char}\nx = 1\n"),
        ("python", "python-identifier", "{char} = 1\n"),
        ("python", "python-string", "x = '{char}'\n"),
        ("javascript", "js-comment", "// {char}\nconst x = 1;\n"),
        ("javascript", "js-string", "const x = '{char}';\n"),
        ("javascript", "js-identifier", "const {char} = 1;\n"),
        ("javascript", "js-regex", "const x = /{char}/;\n"),
        ("javascript", "jsx-attribute", 'const x = <p title="{char}" />;\n'),
        ("javascript", "jsx-text", "const x = <p>{char}</p>;\n"),
    )
] + [
    ("python", "# K\ns = 1\n", "python-ascii"),
    ("javascript", "// s\nconst x = 'K';\n", "js-ascii"),
    ("python", "# \u00e9\n\u03b1 = 1\n", "python-other-unicode"),
    ("javascript", "// \u00e9\nconst \u03b1 = '\u4e2d';\n", "js-other-unicode"),
]


def _isolate_default_492(monkeypatch, tmp_path):
    from chunker import parser
    from chunker._internal.registry import LanguageRegistry

    state = parser._ParserState()
    state.default_library_path = tmp_path / "missing" / "languages.so"
    original_discover = LanguageRegistry._discover_symbols
    original_load = LanguageRegistry._try_load_from_individual_library_safely
    monkeypatch.setattr(
        LanguageRegistry,
        "_discover_symbols",
        lambda self: (
            []
            if self._library_path == state.default_library_path
            else original_discover(self)
        ),
    )
    monkeypatch.setattr(
        LanguageRegistry,
        "_try_load_from_individual_library_safely",
        lambda self, name: (
            None
            if self._library_path == state.default_library_path
            and name in {"python", "javascript"}
            else original_load(self, name)
        ),
    )
    monkeypatch.setattr(parser, "_state", state)
    return state


def _assert_unicode_492_tree(tree, source):
    data = source.encode("utf-8")
    assert not tree.root_node.has_error
    assert tree.root_node.end_byte == len(data)
    assert tree.root_node.text == data
    pending = [tree.root_node]
    while pending:
        node = pending.pop()
        assert not node.is_error and not node.is_missing
        assert 0 <= node.start_byte <= node.end_byte <= len(data)
        assert node.text == data[node.start_byte : node.end_byte]
        node.text.decode("utf-8")
        pending.extend(node.children)


@pytest.mark.parametrize(
    ("language", "source", "case"),
    _UNICODE_492_CASES,
    ids=[item[2] for item in _UNICODE_492_CASES],
)
def test_492_unicode_grammar_bytes(language, source, case):
    from chunker._internal.language_pack import get_language_from_pack

    if language == "python":
        ast.parse(source)
    _assert_unicode_492_tree(
        Parser(get_language_from_pack(language)).parse(source.encode("utf-8")), source
    )


@pytest.mark.parametrize("language", ["python", "javascript"])
def test_492_default_provider_does_not_use_pack(monkeypatch, tmp_path, language):
    import tree_sitter_language_pack as pack

    from chunker.parser import get_language_info, get_parser

    _isolate_default_492(monkeypatch, tmp_path)
    monkeypatch.setattr(
        pack, "get_language", lambda *args, **kwargs: pytest.fail("pack language used")
    )
    monkeypatch.setattr(
        pack, "get_parser", lambda *args, **kwargs: pytest.fail("pack parser used")
    )
    assert not get_parser(language).parse(b"x").root_node.has_error
    assert (
        get_language_info(language).capabilities["grammar_source"]
        == f"official:tree-sitter-{language}@0.25.0"
    )


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
