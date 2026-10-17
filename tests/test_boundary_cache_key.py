from types import SimpleNamespace

import pytest

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
        "tree-sitter-language-pack": "1.17.0",
        "tree-sitter": "0.26.0",
    }
    sources = {"python": "official:tree-sitter-python@0.25.0"}
    monkeypatch.setattr(adapter, "version", versions.__getitem__)
    monkeypatch.setattr(
        adapter,
        "get_language_info",
        lambda language: SimpleNamespace(
            capabilities={"grammar_source": sources[language]}
        ),
    )

    first = _payload()
    assert first["grammar_version"] == (
        "tree-sitter-python:source=official:tree-sitter-python@0.25.0:"
        "pack=1.17.0:runtime=0.26.0"
    )
    assert first["runtime_version"] == "0.26.0"
    assert adapter._build_boundary_cache_key(
        first
    ) == adapter._build_boundary_cache_key(_payload())

    versions["tree-sitter-language-pack"] = "1.17.1"
    pack_changed = _payload()
    assert adapter._build_boundary_cache_key(
        pack_changed
    ) != adapter._build_boundary_cache_key(first)

    versions["tree-sitter"] = "0.26.1"
    runtime_changed = _payload()
    assert adapter._build_boundary_cache_key(
        runtime_changed
    ) != adapter._build_boundary_cache_key(pack_changed)

    sources["python"] = "official:tree-sitter-python@0.25.1"
    official_version_changed = _payload()
    assert adapter._build_boundary_cache_key(
        official_version_changed
    ) != adapter._build_boundary_cache_key(runtime_changed)

    sources["python"] = "custom:sha256:" + "a" * 64
    selected_source_changed = _payload()
    assert adapter._build_boundary_cache_key(
        selected_source_changed
    ) != adapter._build_boundary_cache_key(official_version_changed)


def test_492_non_overridden_language_key_ignores_python_source(monkeypatch):
    versions = {
        "tree-sitter-language-pack": "1.20.0",
        "tree-sitter": "0.26.0",
    }
    monkeypatch.setattr(adapter, "version", versions.__getitem__)
    monkeypatch.setattr(
        adapter,
        "get_language_info",
        lambda language: pytest.fail(f"unexpected metadata lookup for {language}"),
    )

    payload = adapter._cache_key_payload(
        display_path="main.go",
        content_hash="sha1:content",
        language="go",
        resolution_mode="permissive",
        fail_fast=False,
    )
    assert payload["grammar_version"] == ("tree-sitter-go:pack=1.20.0:runtime=0.26.0")
