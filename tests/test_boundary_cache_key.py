from chunker.boundary import adapter


def _payload() -> dict:
    return adapter._cache_key_payload(
        display_path="app.py",
        content_hash="sha1:content",
        language="python",
        resolution_mode="permissive",
        fail_fast=False,
    )


def test_boundary_cache_key_includes_pack_and_runtime_versions(monkeypatch):
    versions = {
        "tree-sitter-language-pack": "0.9.0",
        "tree-sitter": "0.25.2",
    }
    monkeypatch.setattr(adapter, "version", versions.__getitem__)

    first = _payload()
    assert first["grammar_version"] == "tree-sitter-python:pack=0.9.0:runtime=0.25.2"
    assert first["runtime_version"] == "0.25.2"
    assert adapter._build_boundary_cache_key(
        first
    ) == adapter._build_boundary_cache_key(_payload())

    versions["tree-sitter-language-pack"] = "0.9.1"
    pack_changed = _payload()
    assert adapter._build_boundary_cache_key(
        pack_changed
    ) != adapter._build_boundary_cache_key(first)

    versions["tree-sitter"] = "0.25.3"
    runtime_changed = _payload()
    assert adapter._build_boundary_cache_key(
        runtime_changed
    ) != adapter._build_boundary_cache_key(pack_changed)
