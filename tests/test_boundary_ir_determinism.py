import pytest

from chunker.boundary import dumps_boundary_ir, extract_boundary_ir
from tests.boundary_ir_conformance import (
    P0_BOUNDARY_LANGUAGES,
    SUPPORTED_BOUNDARY_LANGUAGES,
    assert_extraction_nonempty,
    assert_grammar_runtime_pins,
    fixture_boundary_json_bytes,
)


@pytest.mark.parametrize("language", P0_BOUNDARY_LANGUAGES)
def test_fixture_boundary_ir_is_byte_identical_across_double_run(language: str):
    first = fixture_boundary_json_bytes(language)
    second = fixture_boundary_json_bytes(language)

    assert first == second


@pytest.mark.parametrize("language", SUPPORTED_BOUNDARY_LANGUAGES)
def test_extraction_nonempty(language: str):
    """Every supported language must extract at least one boundary node.

    Loud guard for the silent-``{}`` failure mode (a grammar that is "available"
    but emits nothing, e.g. an ABI mismatch). Without this, an empty IR could
    pass golden equality against an equally-empty golden.
    """
    assert_extraction_nonempty(language)


def test_grammar_runtime_pins_match():
    """The installed grammar/runtime versions must stay inside the pyproject pins.

    Fails closed on an unintended transitive bump (e.g. tree_sitter 0.24 -> 0.25)
    that would silently corrupt the Boundary IR.
    """
    assert_grammar_runtime_pins()


def test_diagnostic_boundary_ir_is_byte_identical_across_double_run(
    tmp_path,
    monkeypatch,
):
    (tmp_path / "app.py").write_text("def ok():\n    return 1\n", encoding="utf-8")

    from chunker.boundary import adapter

    def graph_with_error(*args, **kwargs):
        return {
            "symbols": {"classes": [], "functions": [], "imports": []},
            "relationships": [],
            "metadata": {},
            "symbol_lookup": {},
            "errors": ["stable graph error"],
        }

    monkeypatch.setattr(adapter, "extract_symbol_graph", graph_with_error)

    first = dumps_boundary_ir(extract_boundary_ir(tmp_path, "python"))
    second = dumps_boundary_ir(extract_boundary_ir(tmp_path, "python"))

    assert first == second
