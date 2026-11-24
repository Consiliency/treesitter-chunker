from pathlib import Path

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


@pytest.mark.parametrize("include_python", [False, True], ids=["jsx", "mixed"])
def test_graph_xref_detects_file_languages(tmp_path, monkeypatch, include_python):
    paths = ["View.JSX"]
    (tmp_path / "View.JSX").write_text(
        "function View() { return <div />; }", encoding="utf-8"
    )
    expected = {("View.JSX", "javascript", "function_declaration")}
    if include_python:
        paths.append("helper.py")
        (tmp_path / "helper.py").write_text("def helper(): pass", encoding="utf-8")
        expected.add(("helper.py", "python", "function_definition"))

    monkeypatch.setenv("TREE_SITTER_CHUNKER_API_ROOT", str(tmp_path))
    response = TestClient(app).post(
        "/graph/xref", json={"paths": paths}, headers=_auth_headers(monkeypatch)
    )
    assert response.status_code == 200, response.text
    assert {
        (Path(node["file"]).name, node["lang"], node["kind"])
        for node in response.json()["nodes"]
    } == expected


@pytest.mark.parametrize("paths", [["input.unknown"], ["helper.py", "input.unknown"]])
def test_graph_xref_rejects_unknown_extension(tmp_path, monkeypatch, paths):
    for path in paths:
        (tmp_path / path).write_text("def helper(): pass", encoding="utf-8")
    monkeypatch.setenv("TREE_SITTER_CHUNKER_API_ROOT", str(tmp_path))
    response = TestClient(app).post(
        "/graph/xref", json={"paths": paths}, headers=_auth_headers(monkeypatch)
    )
    assert response.status_code == 400
    assert "input.unknown" in response.json()["detail"]


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


@pytest.mark.parametrize(
    ("options", "expected_nodes"),
    [
        ({}, ["A", "B", "C"]),
        ({"params": None}, ["A", "B", "C"]),
        ({"params": {"radius": None, "budget": None}}, ["A", "B", "C"]),
        ({"params": {"radius": 0}}, ["A"]),
        ({"params": {"budget": 0}}, []),
        ({"params": {"radius": 1}}, ["A", "B"]),
        ({"params": {"radius": 3, "budget": 1}}, ["A"]),
    ],
)
def test_graph_cut_bounds(options, expected_nodes):
    edges = [{"src": src, "dst": dst} for src, dst in zip("ABC", "BCD")]
    response = TestClient(app).post(
        "/graph/cut",
        json={
            "seeds": ["A"],
            "nodes": [{"id": node} for node in "ABCD"],
            "edges": edges,
            **options,
        },
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "nodes": expected_nodes,
        "edges": edges[: max(0, len(expected_nodes) - 1)],
    }


@pytest.mark.parametrize("bound", ["radius", "budget"])
def test_graph_cut_rejects_negative_bounds(bound):
    response = TestClient(app).post(
        "/graph/cut",
        json={"seeds": [], "nodes": [], "edges": [], "params": {bound: -1}},
    )
    assert response.status_code == 422
    assert response.json()["detail"][0]["loc"] == ["body", "params", bound]
