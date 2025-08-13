import importlib
from pathlib import Path


def test_postgres_spec_exporter_generates_sql_file(tmp_path, monkeypatch):
    mod = importlib.import_module("chunker.export.postgres_spec_exporter")

    class DummyChunk:
        def __init__(self, nid: str, file_path: str, lang: str, kind: str):
            self.node_id = nid
            self.chunk_id = nid
            self.file_path = file_path
            self.language = lang
            self.node_type = kind
            self.symbol_id = None
            self.metadata = {"complexity": {"cyclomatic": 1}}
            self.byte_start = 0
            self.byte_end = 5
            self.file_id = "fid"

    # Avoid real parsing by stubbing collection and xref
    monkeypatch.setattr(
        mod,
        "_collect_chunks",
        lambda root: [
            DummyChunk("n1", str(tmp_path / "a.py"), "python", "function_definition"),
            DummyChunk("n2", str(tmp_path / "b.py"), "python", "function_definition"),
        ],
    )

    def fake_build_xref(chunks):
        nodes = [
            {
                "id": c.node_id,
                "file": c.file_path,
                "lang": c.language,
                "symbol": None,
                "kind": c.node_type,
                "attrs": c.metadata,
            }
            for c in chunks
        ]
        edges = [
            {
                "src": chunks[0].node_id,
                "dst": chunks[1].node_id,
                "type": "CALLS",
                "weight": 1.0,
            },
        ]
        return nodes, edges

    monkeypatch.setattr(mod, "build_xref", fake_build_xref)

    rows = mod.export(str(tmp_path), config={})
    # Should produce a SQL file
    sql_path = tmp_path / "chunker_export.sql"
    assert sql_path.exists()
    content = sql_path.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS nodes" in content
    assert "INSERT INTO nodes" in content
    assert "INSERT INTO spans" in content
    assert rows > 0
