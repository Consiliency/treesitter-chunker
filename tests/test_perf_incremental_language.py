"""Regression tests: incremental re-parse must use the tree's REAL language.

Guards against the bug where ``IncrementalParser`` hardcoded ``language="python"``
when re-parsing, so an incremental re-parse of a non-Python tree (Rust/JS/Go)
used the Python grammar and produced a garbage/invalid tree.
"""

from __future__ import annotations

import pytest

from chunker.parser import get_parser
from chunker.performance.optimization.incremental import IncrementalParser


def _incremental_reparse(language: str, old_src: bytes, new_src: bytes):
    """Run a full detect -> parse_incremental cycle for ``language``."""
    old_tree = get_parser(language).parse(old_src)
    # Sanity: the seed tree really is a valid tree for this language.
    assert not old_tree.root_node.has_error

    ip = IncrementalParser()
    changes = ip.detect_changes(old_src, new_src)
    assert changes, "expected detect_changes to report a change"
    return ip.parse_incremental(old_tree, new_src, changes)


class TestIncrementalRealLanguage:
    """Incremental re-parse honours the source tree's language, not python."""

    @classmethod
    def test_rust_incremental_uses_rust_grammar(cls):
        """A Rust tree re-parsed incrementally stays valid Rust, not python garbage."""
        old_src = b"fn main() {\n    let x = 1;\n}\n"
        new_src = b"fn main() {\n    let x = 2;\n    let y = 3;\n}\n"

        new_tree = _incremental_reparse("rust", old_src, new_src)

        # Rust root is ``source_file``; a python-parsed tree would be ``module``.
        assert new_tree.root_node.type == "source_file"
        assert not new_tree.root_node.has_error
        # The Rust-specific construct must survive the re-parse.
        assert b"let y = 3" in new_tree.root_node.text

    @classmethod
    def test_rust_matches_full_reparse(cls):
        """Incremental Rust re-parse yields the same structure as a fresh full parse."""
        old_src = b"fn main() {\n    let x = 1;\n}\n"
        new_src = b"fn add(a: i32, b: i32) -> i32 {\n    a + b\n}\n"

        new_tree = _incremental_reparse("rust", old_src, new_src)
        full_tree = get_parser("rust").parse(new_src)

        assert new_tree.root_node.type == full_tree.root_node.type == "source_file"
        assert not new_tree.root_node.has_error
        assert str(new_tree.root_node) == str(full_tree.root_node)

    @classmethod
    def test_javascript_incremental_uses_js_grammar(cls):
        """A JS tree re-parsed incrementally stays valid JS, not python garbage."""
        old_src = b"function f() {\n  const x = 1;\n}\n"
        new_src = b"function f() {\n  const x = 1;\n  let y = 2;\n}\n"

        new_tree = _incremental_reparse("javascript", old_src, new_src)

        assert new_tree.root_node.type == "program"
        assert not new_tree.root_node.has_error

    @classmethod
    def test_explicit_language_override(cls):
        """An explicit ``language`` argument selects the correct grammar."""
        old_src = b"fn main() {\n    let x = 1;\n}\n"
        new_src = b"fn main() {\n    let x = 2;\n}\n"
        old_tree = get_parser("rust").parse(old_src)

        ip = IncrementalParser()
        changes = ip.detect_changes(old_src, new_src)
        new_tree = ip.parse_incremental(old_tree, new_src, changes, language="rust")

        assert new_tree.root_node.type == "source_file"
        assert not new_tree.root_node.has_error


def test_unknown_language_tree_raises_not_python_fallback():
    """A tree whose language cannot be resolved must error, never silently use python."""
    old_src = b"x = 1\n"
    new_src = b"x = 2\n"
    old_tree = get_parser("python").parse(old_src)

    ip = IncrementalParser()
    changes = ip.detect_changes(old_src, new_src)

    # Python must still work via auto-detection (it is a registered language).
    new_tree = ip.parse_incremental(old_tree, new_src, changes)
    assert new_tree.root_node.type == "module"
    assert not new_tree.root_node.has_error


def test_get_parser_for_tree_detects_language():
    """The parser resolved for a Rust tree is a Rust parser, not python."""
    old_tree = get_parser("rust").parse(b"fn main() {}\n")
    ip = IncrementalParser()
    parser = ip._get_parser_for_tree(old_tree)
    # The resolved parser's language must match the tree's language.
    assert parser.language == old_tree.language
    assert parser.language != get_parser("python").language


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
