import pytest

pytest.importorskip("fastapi", reason="fastapi required for API tests")
pytest.importorskip("httpx", reason="httpx required for API tests")

from fastapi.testclient import TestClient

from api.server import app


def _auth_headers(monkeypatch):
    monkeypatch.setenv("TREE_SITTER_CHUNKER_API_TOKEN", "test-token")
    return {"Authorization": "Bearer test-token"}


def test_export_postgres_endpoint(tmp_path, monkeypatch):
    code = """
def w():
    return 1
""".lstrip()
    (tmp_path / "w.py").write_text(code, encoding="utf-8")
    client = TestClient(app)
    monkeypatch.setenv("TREE_SITTER_CHUNKER_API_ROOT", str(tmp_path))
    resp = client.post(
        "/export/postgres",
        json={"repo_root": ".", "config": {}},
        headers=_auth_headers(monkeypatch),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["rows_written"] > 0


def test_graph_xref_endpoint(tmp_path, monkeypatch):
    code = """
def a():
    return 2
""".lstrip()
    f = tmp_path / "a.py"
    f.write_text(code, encoding="utf-8")
    client = TestClient(app)
    monkeypatch.setenv("TREE_SITTER_CHUNKER_API_ROOT", str(tmp_path))
    resp = client.post(
        "/graph/xref",
        json={"paths": ["a.py"]},
        headers=_auth_headers(monkeypatch),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data.get("nodes"), list)
    assert isinstance(data.get("edges"), list)


def test_nearest_tests_endpoint(tmp_path, monkeypatch):
    (tmp_path / "tests").mkdir()
    t = tmp_path / "tests" / "test_calc.py"
    t.write_text("def test_calc(): pass", encoding="utf-8")
    monkeypatch.setenv("TREE_SITTER_CHUNKER_API_ROOT", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    client = TestClient(app)
    # Unauthenticated request is now rejected.
    assert client.post("/nearest-tests", json={"symbols": ["calc"]}).status_code == 401
    resp = client.post(
        "/nearest-tests",
        json={"symbols": ["calc"]},
        headers=_auth_headers(monkeypatch),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data.get("tests"), list)


def test_graph_cut_endpoint_uses_supplied_graph():
    client = TestClient(app)
    response = client.post(
        "/graph/cut",
        json={
            "seeds": ["A"],
            "nodes": [{"id": "A"}, {"id": "B"}],
            "edges": [{"src": "A", "dst": "B", "type": "CALLS"}],
        },
    )
    assert response.status_code == 200
    assert set(response.json()["nodes"]) == {"A", "B"}
