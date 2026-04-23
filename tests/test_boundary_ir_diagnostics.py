from pathlib import Path

from chunker.boundary import dumps_boundary_ir, extract_boundary_ir


def test_parse_failure_records_diagnostic_and_continues(tmp_path: Path, monkeypatch):
    good = tmp_path / "good.py"
    bad = tmp_path / "bad.py"
    good.write_text("def ok():\n    return 1\n", encoding="utf-8")
    bad.write_text("def broken():\n    return 2\n", encoding="utf-8")

    from chunker.boundary import adapter

    original_chunk_file = adapter.chunk_file

    def fail_one_file(file_path, *args, **kwargs):
        if Path(file_path).name == "bad.py":
            raise RuntimeError("forced parser failure")
        return original_chunk_file(file_path, *args, **kwargs)

    monkeypatch.setattr(adapter, "chunk_file", fail_one_file)

    first = extract_boundary_ir(tmp_path, "python")
    second = extract_boundary_ir(tmp_path, "python")

    assert dumps_boundary_ir(first) == dumps_boundary_ir(second)
    assert first["metrics"]["files_failed"] == 1
    assert first["metrics"]["parse_failures"] == 1
    assert first["metrics"]["failure_buckets"] == {"boundary.parse_error": 1}
    assert any(node["path"] == "good.py" for node in first["nodes"])

    failed_file = next(file for file in first["files"] if file["path"] == "bad.py")
    diagnostic = first["diagnostics"][0]
    assert failed_file["status"] == "error"
    assert failed_file["diagnostics"] == [diagnostic["id"]]
    assert diagnostic["stage"] == "parse"
    assert diagnostic["code"] == "boundary.parse_error"
    assert diagnostic["path"] == "bad.py"
    assert diagnostic["details"] == {"exception": "RuntimeError"}


def test_graph_errors_have_deterministic_diagnostic_ids(tmp_path: Path, monkeypatch):
    (tmp_path / "app.py").write_text("def ok():\n    return 1\n", encoding="utf-8")

    from chunker.boundary import adapter

    def graph_with_error(*args, **kwargs):
        return {
            "symbols": {"classes": [], "functions": [], "imports": []},
            "relationships": [],
            "metadata": {},
            "symbol_lookup": {},
            "errors": ["forced graph failure"],
        }

    monkeypatch.setattr(adapter, "extract_symbol_graph", graph_with_error)

    first = extract_boundary_ir(tmp_path, "python")
    second = extract_boundary_ir(tmp_path, "python")

    assert first["diagnostics"] == second["diagnostics"]
    assert first["metrics"]["graph_failures"] == 1
    assert first["metrics"]["failure_buckets"] == {"boundary.graph_error": 1}
    assert first["diagnostics"][0]["stage"] == "graph"
    assert first["diagnostics"][0]["code"] == "boundary.graph_error"
