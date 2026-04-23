from pathlib import Path

from chunker.boundary import extract_boundary_ir


def test_incremental_warm_run_reprocesses_fewer_files(tmp_path: Path, monkeypatch):
    cache_dir = tmp_path / ".boundary-cache"
    for index in range(4):
        (tmp_path / f"file_{index}.py").write_text(
            f"def func_{index}():\n    return {index}\n",
            encoding="utf-8",
        )

    from chunker.boundary import adapter

    calls = 0
    original = adapter._extract_file_cache_record

    def spy(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(adapter, "_extract_file_cache_record", spy)
    extract_boundary_ir(tmp_path, "python", incremental=True, cache_dir=cache_dir)
    cold_calls = calls
    calls = 0
    extract_boundary_ir(tmp_path, "python", incremental=True, cache_dir=cache_dir)
    warm_calls = calls

    assert cold_calls == 4
    assert warm_calls == 0
