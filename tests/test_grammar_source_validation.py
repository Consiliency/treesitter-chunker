"""Regression tests for grammar source validation."""

import pytest

from chunker.grammar.source_validation import validate_grammar_source


@pytest.mark.parametrize(
    "url",
    [
        "ext::sh -c id",
        "file::/etc",
        "-upload-pack=sh",
        "https://github.com.evil.example/tree-sitter/tree-sitter-python",
    ],
)
def test_rejects_untrusted_grammar_source(url):
    with pytest.raises(ValueError):
        validate_grammar_source(url)


def test_accepts_allowlisted_github_repository():
    assert (
        validate_grammar_source("https://github.com/tree-sitter/tree-sitter-python")
        == "https://github.com/tree-sitter/tree-sitter-python"
    )
