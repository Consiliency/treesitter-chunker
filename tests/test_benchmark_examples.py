"""Legacy examples exercise supported imports and real isolated SQLite caches."""

import hashlib
import sqlite3
import tempfile
from contextlib import closing
from dataclasses import asdict
from pathlib import Path

import pytest

from chunker import ASTCache, chunk_file, get_parser


@pytest.fixture
def example_inputs(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    source = (
        Path(__file__).parent / "fixtures/boundary_ir/repos/python/app/service.py"
    ).read_bytes()
    tree = get_parser("python").parse(source)
    assert not tree.root_node.has_error and tree.root_node.named_child_count
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("USERPROFILE", str(home))
    path = tmp_path / "service.py"
    path.write_bytes(source)
    return path, tmp_path / "cache", home


def test_comprehensive_cache_observes_actual_population_and_preserves_other_input(
    example_inputs,
):
    from benchmarks.comprehensive_suite import ComprehensiveBenchmarkSuite

    path, cache_dir, home = example_inputs
    other = path.with_name("other.py")
    other.write_bytes(path.read_bytes())
    cache = ASTCache(cache_dir)
    other_chunks = chunk_file(other, "python")
    assert other_chunks
    cache.cache_chunks(other, "python", other_chunks)
    result = ComprehensiveBenchmarkSuite._benchmark_cache(
        {"test_file": path, "cache_dir": cache_dir}
    )
    assert result["cold_cache"]["cache_hits"] == 0
    assert result["cold_cache"]["cache_misses"] == 5
    assert result["warm_cache"]["cache_hits"] == 5
    assert result["warm_cache"]["cache_misses"] == 0
    assert result["partial_invalidation"]["cache_hits"] == 4
    assert result["partial_invalidation"]["cache_misses"] == 1
    expected = chunk_file(path, "python")
    assert expected
    assert all(phase["chunks"] == len(expected) for phase in result.values())
    reopened = ASTCache(cache_dir)
    assert [asdict(c) for c in reopened.get_cached_chunks(path, "python")] == [
        asdict(c) for c in expected
    ]
    assert [asdict(c) for c in reopened.get_cached_chunks(other, "python")] == [
        asdict(c) for c in other_chunks
    ]
    assert reopened.get_cache_stats()["total_files"] == 2
    with closing(sqlite3.connect(reopened.db_path)) as connection:
        assert connection.execute(
            "SELECT file_hash FROM file_cache WHERE file_path = ?", (str(path),)
        ).fetchone() == (hashlib.sha256(path.read_bytes()).hexdigest(),)
    assert not (home / ".cache" / "treesitter-chunker").exists()


def test_example_demo_reports_real_warm_lookup(example_inputs, capsys):
    from benchmarks.example_benchmark import demo_cached_chunking

    path, cache_dir, home = example_inputs
    source = path.read_bytes()
    result = demo_cached_chunking(test_file=path, cache_dir=cache_dir)
    expected = chunk_file(path, "python")
    assert expected
    assert result["chunks"] == len(expected)
    assert result["cache_hits"] == result["files_cached"] == 1
    assert [
        asdict(c) for c in ASTCache(cache_dir).get_cached_chunks(path, "python")
    ] == [asdict(c) for c in expected]
    assert path.read_bytes() == source
    assert "Cache hits: 1" in capsys.readouterr().out
    assert not (home / ".cache" / "treesitter-chunker").exists()


def test_default_example_caches_are_disposable(example_inputs, tmp_path, monkeypatch):
    from benchmarks.comprehensive_suite import ComprehensiveBenchmarkSuite
    from benchmarks.example_benchmark import demo_cached_chunking

    path, _, home = example_inputs
    scratch = tmp_path / "scratch"
    scratch.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(scratch))
    comprehensive = ComprehensiveBenchmarkSuite._benchmark_cache({"test_file": path})
    assert comprehensive["warm_cache"]["cache_hits"] == 5
    demo = demo_cached_chunking()
    assert demo["chunks"] > 0 and demo["cache_hits"] == 1
    assert list(scratch.iterdir()) == []
    assert path.is_file()
    assert not (home / ".cache" / "treesitter-chunker").exists()
