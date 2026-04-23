import pytest

from chunker.boundary import dumps_boundary_ir, extract_boundary_ir
from tests.boundary_ir_conformance import (
    P0_BOUNDARY_LANGUAGES,
    fixture_boundary_json_bytes,
)


@pytest.mark.parametrize("language", P0_BOUNDARY_LANGUAGES)
def test_fixture_boundary_ir_is_byte_identical_across_double_run(language: str):
    first = fixture_boundary_json_bytes(language)
    second = fixture_boundary_json_bytes(language)

    assert first == second


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
