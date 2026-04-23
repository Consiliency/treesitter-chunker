from pathlib import Path

import pytest

from chunker.boundary import extract_boundary_ir


def test_fail_fast_parser_failure_raises(tmp_path: Path, monkeypatch):
    (tmp_path / "app.py").write_text("def ok():\n    return 1\n", encoding="utf-8")

    from chunker.boundary import adapter

    monkeypatch.setattr(
        adapter,
        "extract_symbol_graph",
        lambda *args, **kwargs: {"relationships": [], "errors": []},
    )
    monkeypatch.setattr(
        adapter,
        "chunk_file",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("parse boom")),
    )

    with pytest.raises(RuntimeError, match="parse boom"):
        extract_boundary_ir(tmp_path, "python", fail_fast=True)


def test_default_parser_failure_records_partial_ir(tmp_path: Path, monkeypatch):
    (tmp_path / "app.py").write_text("def ok():\n    return 1\n", encoding="utf-8")

    from chunker.boundary import adapter

    monkeypatch.setattr(
        adapter,
        "extract_symbol_graph",
        lambda *args, **kwargs: {"relationships": [], "errors": []},
    )
    monkeypatch.setattr(
        adapter,
        "chunk_file",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("parse boom")),
    )

    ir = extract_boundary_ir(tmp_path, "python")

    assert ir["files"][0]["status"] == "error"
    assert ir["metrics"]["parse_failures"] == 1


def test_fail_fast_metadata_failure_raises(tmp_path: Path, monkeypatch):
    (tmp_path / "app.py").write_text("def ok():\n    return 1\n", encoding="utf-8")

    from chunker.boundary import adapter

    monkeypatch.setattr(
        adapter,
        "_node_record",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("metadata boom")),
    )

    with pytest.raises(RuntimeError, match="metadata boom"):
        extract_boundary_ir(tmp_path, "python", fail_fast=True)


def test_fail_fast_graph_failure_raises(tmp_path: Path, monkeypatch):
    (tmp_path / "app.py").write_text("def ok():\n    return 1\n", encoding="utf-8")

    from chunker.boundary import adapter

    monkeypatch.setattr(
        adapter,
        "extract_symbol_graph",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("graph boom")),
    )

    with pytest.raises(RuntimeError, match="graph boom"):
        extract_boundary_ir(tmp_path, "python", fail_fast=True)


def test_fail_fast_serialization_failure_raises(tmp_path: Path, monkeypatch):
    (tmp_path / "app.py").write_text("def ok():\n    return 1\n", encoding="utf-8")

    from chunker.boundary import adapter

    monkeypatch.setattr(
        adapter,
        "canonicalize_boundary_ir",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("serialize boom")),
    )

    with pytest.raises(RuntimeError, match="serialize boom"):
        extract_boundary_ir(tmp_path, "python", fail_fast=True)
