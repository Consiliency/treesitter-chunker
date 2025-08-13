from pathlib import Path

from fastapi.testclient import TestClient

from api.server import app


def test_export_postgres_endpoint(tmp_path):
    code = """
def w():
    return 1
""".lstrip()
    (tmp_path / "w.py").write_text(code, encoding="utf-8")
    client = TestClient(app)
    resp = client.post(
        "/export/postgres",
        json={"repo_root": str(tmp_path), "config": {}},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["rows_written"] > 0


def test_graph_xref_endpoint(tmp_path):
    code = """
def a():
    return 2
""".lstrip()
    f = tmp_path / "a.py"
    f.write_text(code, encoding="utf-8")
    client = TestClient(app)
    resp = client.post("/graph/xref", json={"paths": [str(f)]})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data.get("nodes"), list)
    assert isinstance(data.get("edges"), list)


def test_nearest_tests_endpoint(tmp_path):
    (tmp_path / "tests").mkdir()
    t = tmp_path / "tests" / "test_calc.py"
    t.write_text("def test_calc(): pass", encoding="utf-8")
    client = TestClient(app)
    resp = client.post(
        "/nearest-tests",
        json={"symbols": ["calc"]},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data.get("tests"), list)
