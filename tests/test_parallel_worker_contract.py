"""Capture CPU-bound sizing requests without starting process pools."""

import multiprocessing as mp
import os
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

from tests import test_parallel as parallel

ENV = "CHUNKER_PERF_ADMITTED_SCALING"


@pytest.fixture
def requested_workers(monkeypatch):
    """Replace the clock and chunker while running the real test bodies."""

    def record(module, cores):
        requests = []

        def chunker(language, *, num_workers):
            requests.append(num_workers)
            return SimpleNamespace(
                chunk_files_parallel=lambda paths: {path: [object()] for path in paths}
            )

        monkeypatch.setattr(mp, "cpu_count", lambda: cores)
        monkeypatch.setattr(os, "cpu_count", lambda: cores)
        monkeypatch.setattr(os, "process_cpu_count", lambda: cores)
        monkeypatch.setattr(module, "ParallelChunker", chunker)
        monkeypatch.setattr(module, "time", SimpleNamespace(time=lambda: 0.0))
        return requests

    return record


def check_ordinary(sizing, requests, tmp_path):
    sizing.test_cpu_bound_sizing(tmp_path)
    with pytest.raises(pytest.skip.Exception, match=f"{ENV}=1"):
        sizing.test_cpu_bound_sizing_four_workers(tmp_path)
    assert requests == [1, 2], f"ordinary sizing requested {requests}"


@pytest.mark.parametrize("cores", [2, 24, 64])
def test_ordinary_cpu_bound_sizing(cores, monkeypatch, tmp_path, requested_workers):
    monkeypatch.delenv(ENV, raising=False)
    requests = requested_workers(parallel, cores)
    check_ordinary(parallel.TestWorkerPoolSizing, requests, tmp_path)


@pytest.mark.parametrize("value", ["", "0", "true", "4"])
def test_only_exact_opt_in_admits(value, monkeypatch, tmp_path, requested_workers):
    monkeypatch.setenv(ENV, value)
    requests = requested_workers(parallel, 64)
    check_ordinary(parallel.TestWorkerPoolSizing, requests, tmp_path)


def test_admitted_cpu_bound_sizing(monkeypatch, tmp_path, requested_workers):
    monkeypatch.setenv(ENV, "1")
    requests = requested_workers(parallel, 64)
    sizing = parallel.TestWorkerPoolSizing
    sizing.test_cpu_bound_sizing(tmp_path)
    assert requests == [1, 2]
    sizing.test_cpu_bound_sizing_four_workers(tmp_path)
    assert requests == [1, 2, 4]


def test_restoring_cpu_count_sizing_breaks_contract(
    monkeypatch, tmp_path, requested_workers
):
    monkeypatch.delenv(ENV, raising=False)
    source_path = Path(parallel.__file__)
    source = source_path.read_text(encoding="utf-8")
    ordinary = "cls._check_cpu_bound_sizing(tmp_path, [1, 2])"
    assert source.count(ordinary) == 1
    source = source.replace(
        ordinary, "cls._check_cpu_bound_sizing(tmp_path, [1, 2, 4, mp.cpu_count()])"
    )
    mutant = ModuleType("parallel_cpu_count_mutant")
    exec(compile(source, str(source_path), "exec"), mutant.__dict__)  # noqa: S102

    requests = requested_workers(mutant, 24)
    with pytest.raises(
        AssertionError, match=r"ordinary sizing requested \[1, 2, 4, 24\]"
    ):
        check_ordinary(mutant.TestWorkerPoolSizing, requests, tmp_path)
