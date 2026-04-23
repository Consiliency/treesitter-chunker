import inspect
from pathlib import Path

import pytest

from chunker.boundary import dumps_boundary_ir, extract_boundary_ir


def test_incremental_false_keeps_default_options(tmp_path: Path):
    (tmp_path / "app.py").write_text("def ok():\n    return 1\n", encoding="utf-8")

    default = extract_boundary_ir(tmp_path, "python")
    explicit = extract_boundary_ir(tmp_path, "python", incremental=False)

    assert default == explicit
    assert "incremental" not in default["run"]["options"]
    assert "cache_dir" not in default["run"]["options"]


def test_incremental_signature_exposes_new_keyword_only_parameters():
    params = inspect.signature(extract_boundary_ir).parameters

    assert params["incremental"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["cache_dir"].default is None
    assert params["force_rebuild"].default is False


def test_cold_and_warm_incremental_runs_are_byte_identical(tmp_path: Path):
    cache_dir = tmp_path / ".boundary-cache"
    (tmp_path / "helper.py").write_text(
        "def helper():\n    return 1\n", encoding="utf-8"
    )
    (tmp_path / "service.py").write_text(
        """from helper import helper

def service():
    return helper()
""",
        encoding="utf-8",
    )

    cold = extract_boundary_ir(
        tmp_path, "python", incremental=True, cache_dir=cache_dir
    )
    warm = extract_boundary_ir(
        tmp_path, "python", incremental=True, cache_dir=cache_dir
    )

    assert dumps_boundary_ir(cold) == dumps_boundary_ir(warm)
    assert (cache_dir / "index.json").exists()


def test_incremental_warm_run_recomputes_changed_file_and_neighbors(
    tmp_path: Path, monkeypatch
):
    cache_dir = tmp_path / ".boundary-cache"
    helper = tmp_path / "helper.py"
    service = tmp_path / "service.py"
    unrelated = tmp_path / "unrelated.py"
    helper.write_text("def helper():\n    return 1\n", encoding="utf-8")
    service.write_text(
        """from helper import helper

def service():
    return helper()
""",
        encoding="utf-8",
    )
    unrelated.write_text("def other():\n    return 3\n", encoding="utf-8")
    extract_boundary_ir(tmp_path, "python", incremental=True, cache_dir=cache_dir)

    from chunker.boundary import adapter

    recomputed: list[str] = []
    original = adapter._extract_file_cache_record

    def spy(file_path, *args, **kwargs):
        recomputed.append(file_path.name)
        return original(file_path, *args, **kwargs)

    monkeypatch.setattr(adapter, "_extract_file_cache_record", spy)
    helper.write_text("def helper():\n    return 2\n", encoding="utf-8")

    extract_boundary_ir(tmp_path, "python", incremental=True, cache_dir=cache_dir)

    assert recomputed == ["helper.py", "service.py"]


def test_force_rebuild_refreshes_valid_cache_records(tmp_path: Path, monkeypatch):
    cache_dir = tmp_path / ".boundary-cache"
    (tmp_path / "app.py").write_text("def ok():\n    return 1\n", encoding="utf-8")
    extract_boundary_ir(tmp_path, "python", incremental=True, cache_dir=cache_dir)

    from chunker.boundary import adapter

    calls = 0
    original = adapter._extract_file_cache_record

    def spy(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(adapter, "_extract_file_cache_record", spy)
    extract_boundary_ir(
        tmp_path,
        "python",
        incremental=True,
        cache_dir=cache_dir,
        force_rebuild=True,
    )

    assert calls == 1


def test_incremental_fail_fast_parser_failure_raises(tmp_path: Path, monkeypatch):
    (tmp_path / "app.py").write_text("def ok():\n    return 1\n", encoding="utf-8")

    from chunker.boundary import adapter

    monkeypatch.setattr(
        adapter,
        "chunk_file",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("parse boom")),
    )

    with pytest.raises(RuntimeError, match="parse boom"):
        extract_boundary_ir(tmp_path, "python", incremental=True, fail_fast=True)
