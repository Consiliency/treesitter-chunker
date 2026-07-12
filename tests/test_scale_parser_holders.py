"""SCALE lane SL-1: cached-parser holders must hand thread-local parsers.

These tests encode the frozen IF-0-PARSER-1 invariant: a tree-sitter ``Parser``
is owned exclusively by the thread that obtained it and must never be shared
across threads via a cross-thread pool or a parser cached on ``self``.

They are written to FAIL on the pre-migration (parser-pooling / per-language
cached) code and PASS once every holder acquires per-thread via the thread-local
``get_parser`` API. The final test covers ``parallel.py``'s previously-dead
wall-clock timeout.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest


def _python_grammar_available() -> bool:
    try:
        from chunker.parser import get_parser

        get_parser("python")
        return True
    except Exception:
        return False


needs_python_grammar = pytest.mark.skipif(
    not _python_grammar_available(),
    reason="python tree-sitter grammar is not available in this environment",
)

_NUM_THREADS = 8


def _run_threads(target, count: int = _NUM_THREADS) -> None:
    threads = [
        threading.Thread(target=target, args=(i,), name=f"holder-{i}")
        for i in range(count)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()


# ---------------------------------------------------------------------------
# MemoryPool
# ---------------------------------------------------------------------------
@needs_python_grammar
def test_memory_pool_hands_distinct_parsers_to_distinct_threads():
    """>=8 threads each acquire and HOLD a parser; all identities are distinct."""
    from chunker.performance.optimization.memory_pool import MemoryPool

    pool = MemoryPool()
    barrier = threading.Barrier(_NUM_THREADS)
    held: list = []
    lock = threading.Lock()

    def worker(_i: int) -> None:
        barrier.wait()  # make all threads race for a parser at once
        parser = pool.acquire_parser("python")
        with lock:
            held.append(parser)  # hold the reference alive for the assertions

    _run_threads(worker)

    assert len(held) == _NUM_THREADS
    assert len({id(p) for p in held}) == _NUM_THREADS, (
        "MemoryPool handed the same parser object to multiple threads"
    )


@needs_python_grammar
def test_memory_pool_never_shares_a_parser_across_threads():
    """A parser acquired+released by one thread is never reused by another.

    Fails on the pooling implementation: released parsers migrate through the
    shared pool and get handed to a different thread on a later iteration.
    """
    from chunker.performance.optimization.memory_pool import MemoryPool

    pool = MemoryPool()
    iterations = 5
    barrier = threading.Barrier(_NUM_THREADS)
    seen: dict[int, set[str]] = {}
    held: list = []
    lock = threading.Lock()

    def worker(_i: int) -> None:
        name = threading.current_thread().name
        local_refs = []
        for _ in range(iterations):
            barrier.wait()
            parser = pool.acquire_parser("python")
            local_refs.append(parser)  # keep alive so id() cannot be recycled
            with lock:
                seen.setdefault(id(parser), set()).add(name)
            barrier.wait()
            pool.release_parser(parser, "python")
        with lock:
            held.extend(local_refs)

    _run_threads(worker)

    assert held  # references kept alive through the assertions below
    shared = {pid: names for pid, names in seen.items() if len(names) > 1}
    assert not shared, f"parser objects observed by more than one thread: {shared}"


# ---------------------------------------------------------------------------
# ASTRelationshipTracker
# ---------------------------------------------------------------------------
@needs_python_grammar
def test_tracker_hands_distinct_parsers_to_distinct_threads():
    """The tracker must not cache one parser per language shared across threads."""
    from chunker.export.relationships.tracker import ASTRelationshipTracker

    tracker = ASTRelationshipTracker()
    # Warm any legacy per-language cache in the main thread. On the unmigrated
    # code this populates a shared ``self._parsers`` so every worker below would
    # receive the *same* object; the migrated code ignores this entirely.
    tracker._get_parser("python")

    barrier = threading.Barrier(_NUM_THREADS)
    held: list = []
    lock = threading.Lock()

    def worker(_i: int) -> None:
        barrier.wait()
        parser = tracker._get_parser("python")
        with lock:
            held.append(parser)

    _run_threads(worker)

    assert len(held) == _NUM_THREADS
    assert len({id(p) for p in held}) == _NUM_THREADS, (
        "ASTRelationshipTracker shared one cached parser across threads"
    )


# ---------------------------------------------------------------------------
# Frozen primitive the batch / enhanced holders now rely on
# ---------------------------------------------------------------------------
@needs_python_grammar
def test_get_parser_is_thread_local_and_distinct():
    from chunker.parser import get_parser

    barrier = threading.Barrier(_NUM_THREADS)
    held: list = []
    lock = threading.Lock()

    def worker(_i: int) -> None:
        barrier.wait()
        parser = get_parser("python")
        with lock:
            held.append(parser)

    _run_threads(worker)

    assert len({id(p) for p in held}) == _NUM_THREADS


# ---------------------------------------------------------------------------
# BatchProcessor (ThreadPoolExecutor holder)
# ---------------------------------------------------------------------------
@needs_python_grammar
def test_batch_process_file_acquires_thread_local_parser(tmp_path, monkeypatch):
    """Each worker thread must obtain its own parser via the thread-local API.

    Records every parser handed out through the module-level ``get_parser``. On
    the unmigrated code ``_process_file`` pulls from the shared MemoryPool and
    never calls this symbol, so ``seen`` stays empty and the test fails.
    """
    import chunker.performance.optimization.batch as batch_mod
    from chunker.parser import get_parser as real_get_parser

    seen: dict[int, set[str]] = {}
    lock = threading.Lock()

    def recording_get_parser(language: str):
        parser = real_get_parser(language)
        with lock:
            seen.setdefault(id(parser), set()).add(threading.current_thread().name)
        return parser

    monkeypatch.setattr(batch_mod, "get_parser", recording_get_parser)

    files = []
    for i in range(_NUM_THREADS):
        f = tmp_path / f"mod{i}.py"
        f.write_text(f"def f{i}():\n    return {i}\n")
        files.append(str(f))

    processor = batch_mod.BatchProcessor(max_workers=_NUM_THREADS)
    for f in files:
        processor.add_file(f)
    results = processor.process_batch(batch_size=_NUM_THREADS, parallel=True)

    assert results, "batch produced no results"
    assert seen, "batch did not obtain a parser via the thread-local get_parser API"
    shared = {pid: names for pid, names in seen.items() if len(names) > 1}
    assert not shared, f"batch shared a parser across threads: {shared}"


# ---------------------------------------------------------------------------
# EnhancedChunker
# ---------------------------------------------------------------------------
@needs_python_grammar
def test_enhanced_parse_file_acquires_thread_local_parser(monkeypatch):
    """``_parse_file`` must acquire a per-thread parser, not a pooled one."""
    import chunker.performance.enhanced_chunker as ec_mod
    from chunker.parser import get_parser as real_get_parser

    seen: dict[int, set[str]] = {}
    lock = threading.Lock()

    def recording_get_parser(language: str):
        parser = real_get_parser(language)
        with lock:
            seen.setdefault(id(parser), set()).add(threading.current_thread().name)
        return parser

    monkeypatch.setattr(ec_mod, "get_parser", recording_get_parser)

    chunker = ec_mod.EnhancedChunker(enable_incremental=False)
    source = b"def f():\n    return 1\n"
    barrier = threading.Barrier(_NUM_THREADS)

    def worker(i: int) -> None:
        barrier.wait()
        chunker._parse_file(f"mem{i}.py", source, "python")

    _run_threads(worker)

    assert seen, "enhanced chunker did not obtain a parser via thread-local get_parser"
    shared = {pid: names for pid, names in seen.items() if len(names) > 1}
    assert not shared, f"enhanced chunker shared a parser across threads: {shared}"


# ---------------------------------------------------------------------------
# parallel.py wall-clock timeout
# ---------------------------------------------------------------------------
def test_parallel_timeout_stops_hung_worker(monkeypatch):
    """A worker that sleeps past the deadline is cancelled, not waited on.

    Substitutes a ThreadPoolExecutor so a hang can be injected in-process, then
    asserts the call returns well before the worker's own sleep would finish.
    Fails on the unmigrated code, whose un-bounded ``as_completed`` loop blocks
    until every worker completes.
    """
    import chunker.parallel as par

    monkeypatch.setattr(par, "ProcessPoolExecutor", ThreadPoolExecutor)

    pc = par.ParallelChunker(
        "python",
        num_workers=2,
        use_cache=False,
        timeout_seconds=0.5,
    )

    def hang(path):
        time.sleep(5.0)
        return path, []

    monkeypatch.setattr(pc, "_process_single_file", hang)

    paths = [Path("a.py"), Path("b.py")]
    box: dict = {}

    def run() -> None:
        box["result"] = pc.chunk_files_parallel(paths)

    runner = threading.Thread(target=run, daemon=True)
    start = time.monotonic()
    runner.start()
    runner.join(timeout=4.0)
    elapsed = time.monotonic() - start

    assert not runner.is_alive(), (
        "chunk_files_parallel hung past the deadline instead of timing out"
    )
    assert elapsed < 3.5, f"timeout was not enforced promptly (took {elapsed:.2f}s)"
    assert box["result"] == {Path("a.py"): [], Path("b.py"): []}
