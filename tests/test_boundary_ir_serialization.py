import json

from chunker.boundary import dumps_boundary_ir
from chunker.export import BoundaryIRExporter, write_boundary_ir


def _ir():
    return {
        "schema_version": "1.0",
        "source": {"kind": "repository", "path": "."},
        "files": [
            {
                "id": "file-b",
                "path": "b.py",
                "language": "python",
                "content_hash": "sha1:b",
                "parser": "tree-sitter-python",
                "status": "parsed",
                "diagnostics": [],
            },
            {
                "id": "file-a",
                "path": "a.py",
                "language": "python",
                "content_hash": "sha1:a",
                "parser": "tree-sitter-python",
                "status": "parsed",
                "diagnostics": [],
            },
        ],
        "nodes": [
            {
                "id": "node-b",
                "identity": {"source": "node_id", "value": "node-b"},
                "definition_id": None,
                "node_id": "node-b",
                "symbol_id": None,
                "file_id": "file-b",
                "path": "b.py",
                "language": "python",
                "kind": "function",
                "symbol": "b",
                "qualified_name": "b",
                "semantic_path": "b.py::b",
                "signature": None,
                "span": {
                    "start_line": 2,
                    "end_line": 2,
                    "byte_start": 0,
                    "byte_end": 1,
                },
                "parent": None,
                "relationships": [],
                "metadata": {},
                "provenance": {"extractor": "chunk_file"},
            },
            {
                "id": "node-a",
                "identity": {"source": "node_id", "value": "node-a"},
                "definition_id": None,
                "node_id": "node-a",
                "symbol_id": None,
                "file_id": "file-a",
                "path": "a.py",
                "language": "python",
                "kind": "function",
                "symbol": "a",
                "qualified_name": "a",
                "semantic_path": "a.py::a",
                "signature": None,
                "span": {
                    "start_line": 1,
                    "end_line": 1,
                    "byte_start": 0,
                    "byte_end": 1,
                },
                "parent": None,
                "relationships": [],
                "metadata": {},
                "provenance": {"extractor": "chunk_file"},
            },
        ],
        "edges": [
            {
                "id": "edge-b",
                "source": "node-b",
                "target": "node-a",
                "type": "calls",
                "resolution": "resolved",
                "reference": "a",
                "candidates": ["node-b", "node-a"],
                "location": {"start_line": 3, "end_line": 3},
                "provenance": {},
                "metadata": {},
            }
        ],
        "diagnostics": [],
        "metrics": {
            "files_total": 2,
            "files_parsed": 2,
            "files_skipped": 0,
            "nodes_total": 2,
            "edges_total": 1,
            "diagnostics_total": 0,
            "resolved_edges": 1,
            "ambiguous_edges": 0,
            "unresolved_edges": 0,
        },
        "run": {
            "tool": "treesitter-chunker",
            "tool_version": "test",
            "root": ".",
            "created_at": None,
            "canonical": True,
            "options": {},
        },
    }


def test_dumps_boundary_ir_compact_canonical_json():
    text = dumps_boundary_ir(_ir())

    assert text.endswith("\n")
    assert text.count("\n") == 1
    assert " " not in text
    assert text.startswith('{"diagnostics":[],"edges"')


def test_dumps_boundary_ir_orders_schema_lists_and_candidates():
    data = json.loads(dumps_boundary_ir(_ir()))

    assert [item["path"] for item in data["files"]] == ["a.py", "b.py"]
    assert [item["id"] for item in data["nodes"]] == ["node-a", "node-b"]
    assert data["edges"][0]["candidates"] == ["node-a", "node-b"]


def test_write_boundary_ir_uses_utf8_and_trailing_newline(tmp_path):
    output = tmp_path / "boundary.json"

    write_boundary_ir(_ir(), output)

    assert output.read_text(encoding="utf-8").endswith("\n")
    assert json.loads(output.read_text(encoding="utf-8"))["schema_version"] == "1.0"


def test_boundary_ir_exporter_to_string():
    text = BoundaryIRExporter().export_to_string(_ir(), pretty=True)

    assert text.endswith("\n")
    assert "\n  " in text
