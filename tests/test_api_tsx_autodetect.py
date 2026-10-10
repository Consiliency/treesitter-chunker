"""The API `/chunk/file` endpoint auto-detects languages with the canonical map.

It used to carry its own extension map that still resolved `.tsx` to
`typescript`, whose grammar cannot parse JSX.
"""

import pytest

pytest.importorskip("fastapi")

from fastapi.testclient import TestClient  # noqa: E402

from api import server  # noqa: E402
from chunker.auto import ZeroConfigAPI  # noqa: E402

TSX_SOURCE = """export const Badge = (props: { label: string }) => <b>{props.label}</b>;

export class Panel {
  render() {
    return <>{"panel"}</>;
  }
}
"""


def test_api_chunk_file_autodetects_tsx_as_tsx(tmp_path, monkeypatch):
    (tmp_path / "Card.tsx").write_text(TSX_SOURCE, encoding="utf-8")
    monkeypatch.setenv("TREE_SITTER_CHUNKER_API_ROOT", str(tmp_path))
    monkeypatch.setenv("TREE_SITTER_CHUNKER_API_TOKEN", "test-token")
    client = TestClient(server.app)

    response = client.post(
        "/chunk/file",
        json={"file_path": "Card.tsx"},
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["language"] == "tsx"
    node_types = {chunk["node_type"] for chunk in body["chunks"]}
    assert "class_declaration" in node_types


def test_api_only_extensions_never_override_the_canonical_map():
    assert not set(server._API_ONLY_EXTENSIONS) & set(ZeroConfigAPI.EXTENSION_MAP)
