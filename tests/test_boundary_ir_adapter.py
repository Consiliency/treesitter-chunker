from pathlib import Path

import pytest

from chunker.boundary import extract_boundary_ir
from chunker.parser import list_languages


def test_extract_boundary_ir_python_repo_is_deterministic(tmp_path: Path):
    source = tmp_path / "service.py"
    source.write_text(
        "def helper(name):\n"
        "    return name.upper()\n\n"
        "def greet(name):\n"
        "    return helper(name)\n",
        encoding="utf-8",
    )

    first = extract_boundary_ir(tmp_path, "python")
    second = extract_boundary_ir(tmp_path, "python")

    assert first == second
    assert list(first) == [
        "diagnostics",
        "edges",
        "files",
        "metrics",
        "nodes",
        "run",
        "schema_version",
        "source",
    ]
    assert first["schema_version"] == "1.0"
    assert first["files"][0]["path"] == "service.py"
    assert first["metrics"]["files_total"] == 1
    assert first["metrics"]["nodes_total"] >= 2
    assert first["run"]["created_at"] is None
    assert any(node["identity"]["source"] == "definition_id" for node in first["nodes"])


def test_extract_boundary_ir_records_unresolved_python_edge(tmp_path: Path):
    source = tmp_path / "service.py"
    source.write_text(
        "import missing_lib\n\n"
        "def use_missing():\n"
        "    return missing_lib.value\n",
        encoding="utf-8",
    )

    ir = extract_boundary_ir(tmp_path, "python")

    unresolved = [edge for edge in ir["edges"] if edge["resolution"] == "unresolved"]
    assert unresolved
    assert ir["metrics"]["unresolved_edges"] == len(unresolved)
    assert all(edge["candidates"] == [] for edge in unresolved)


def test_extract_boundary_ir_javascript_resolved_call(tmp_path: Path):
    (tmp_path / "helper.js").write_text(
        "export function helper(name) { return name; }\n",
        encoding="utf-8",
    )
    (tmp_path / "service.js").write_text(
        "import { helper } from './helper.js';\n"
        "export function greet(name) {\n"
        "  return helper(name);\n"
        "}\n",
        encoding="utf-8",
    )

    ir = extract_boundary_ir(tmp_path, "javascript")

    assert any(edge["resolution"] == "resolved" for edge in ir["edges"])
    assert ir["metrics"]["resolved_edges"] >= 1


def test_extract_boundary_ir_go_core_fields_when_grammar_available(tmp_path: Path):
    if "go" not in list_languages():
        pytest.skip("go grammar is not available")
    (tmp_path / "main.go").write_text(
        'package main\n\nfunc greet() string {\n\treturn "hi"\n}\n',
        encoding="utf-8",
    )

    ir = extract_boundary_ir(tmp_path, "go")

    assert ir["files"][0]["language"] == "go"
    assert ir["nodes"]
    assert ir["metrics"]["nodes_total"] == len(ir["nodes"])
