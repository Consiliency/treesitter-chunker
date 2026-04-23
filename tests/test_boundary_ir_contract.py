from pathlib import Path

from chunker.boundary import dumps_boundary_ir, extract_boundary_ir
from chunker.boundary.types import METRIC_KEYS, TOP_LEVEL_KEYS


def test_boundary_ir_contract_keys_and_metrics(tmp_path: Path):
    source = tmp_path / "app.py"
    source.write_text("def greet():\n    return 'hi'\n", encoding="utf-8")

    ir = extract_boundary_ir(tmp_path, "python")

    assert tuple(ir.keys()) == tuple(sorted(TOP_LEVEL_KEYS))
    assert ir["schema_version"] == "1.0"
    assert set(METRIC_KEYS).issubset(ir["metrics"])
    assert ir["files"][0].keys() == {
        "content_hash",
        "diagnostics",
        "id",
        "language",
        "parser",
        "path",
        "status",
    }
    assert ir["nodes"][0].keys() == {
        "definition_id",
        "file_id",
        "id",
        "identity",
        "kind",
        "language",
        "metadata",
        "node_id",
        "parent",
        "path",
        "provenance",
        "qualified_name",
        "relationships",
        "semantic_path",
        "signature",
        "span",
        "symbol",
        "symbol_id",
    }


def test_boundary_ir_canonical_output_has_stable_trailing_newline(tmp_path: Path):
    source = tmp_path / "app.py"
    source.write_text("def greet():\n    return 'hi'\n", encoding="utf-8")

    text = dumps_boundary_ir(extract_boundary_ir(tmp_path, "python"))

    assert text.endswith("\n")
    assert "\n\n" not in text
