from api import server

from fastapi.testclient import TestClient


def _auth_headers(monkeypatch):
    monkeypatch.setenv("TREE_SITTER_CHUNKER_API_TOKEN", "test-token")
    return {"Authorization": "Bearer test-token"}


def test_filesystem_endpoints_require_authentication(tmp_path):
    client = TestClient(server.app)
    requests = [
        ("/chunk/file", {"file_path": "file.py"}),
        ("/graph/xref", {"paths": ["file.py"]}),
        ("/export/postgres", {"repo_root": "."}),
    ]

    for path, payload in requests:
        response = client.post(path, json=payload)
        assert response.status_code == 401


def test_authenticated_filesystem_paths_are_root_confined(tmp_path, monkeypatch):
    client = TestClient(server.app)
    monkeypatch.setenv("TREE_SITTER_CHUNKER_API_ROOT", str(tmp_path))
    headers = _auth_headers(monkeypatch)

    response = client.post(
        "/chunk/file",
        json={"file_path": str(tmp_path / "file.py")},
        headers=headers,
    )
    assert response.status_code == 400
    response = client.post(
        "/graph/xref",
        json={"paths": ["../outside.py"]},
        headers=headers,
    )
    assert response.status_code == 400
    response = client.post(
        "/export/postgres",
        json={"repo_root": "../outside"},
        headers=headers,
    )
    assert response.status_code == 400


def test_cors_and_body_size_defaults_are_safe():
    client = TestClient(server.app)
    response = client.options(
        "/chunk/file",
        headers={
            "Origin": "https://untrusted.example",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.headers.get("access-control-allow-origin") != "*"
    assert response.headers.get("access-control-allow-credentials") != "true"

    response = client.post(
        "/chunk/text",
        json={
            "content": "x" * (server.MAX_REQUEST_BODY_BYTES + 1),
            "language": "python",
        },
    )
    assert response.status_code == 413


def test_server_binds_to_loopback_by_default():
    assert server.DEFAULT_HOST == "127.0.0.1"
