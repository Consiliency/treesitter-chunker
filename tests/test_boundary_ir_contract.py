from pathlib import Path

from chunker.boundary import (
    BOUNDARY_IR_SCHEMA_VERSION,
    dumps_boundary_ir,
    extract_boundary_ir,
)
from chunker.boundary.types import METRIC_KEYS, TOP_LEVEL_KEYS, TIMING_KEYS


def test_boundary_ir_contract_keys_and_metrics(tmp_path: Path):
    source = tmp_path / "app.py"
    source.write_text("def greet():\n    return 'hi'\n", encoding="utf-8")

    ir = extract_boundary_ir(tmp_path, "python")

    assert tuple(TOP_LEVEL_KEYS) == (
        "schema_version",
        "source",
        "files",
        "nodes",
        "edges",
        "diagnostics",
        "metrics",
        "run",
    )
    assert tuple(ir.keys()) == tuple(sorted(TOP_LEVEL_KEYS))
    assert ir["schema_version"] == BOUNDARY_IR_SCHEMA_VERSION
    assert set(METRIC_KEYS).issubset(ir["metrics"])
    assert tuple(ir["run"]["timings"].keys()) == tuple(sorted(TIMING_KEYS))
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

    assert isinstance(text, str)
    assert text.endswith("\n")
    assert "\n\n" not in text
