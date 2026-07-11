"""Regression tests for PARSER convergence findings (codex panel).

Two segfault-adjacent paths survived the first PARSER pass and are fixed here:
1. Racy lazy initialization published `registry` before `factory`, so a cold-start
   thread could observe factory=None and raise "Parser factory not initialized".
2. Stored-parser holders (StreamingChunker, plugin instances cached globally)
   reused ONE Parser across threads, re-opening the shared-parser segfault path.
"""

from __future__ import annotations

import threading

import chunker  # noqa: F401  (ensure package import side effects)


def test_cold_start_init_race_no_exception() -> None:
    """8 threads racing the very first initialize() must all succeed."""
    from chunker import parser as P

    # Force a cold state so the race window is real.
    P._state.registry = None
    P._state.factory = None

    errors: list[Exception] = []
    barrier = threading.Barrier(8)

    def worker() -> None:
        try:
            barrier.wait()
            P.get_parser("python")
        except Exception as exc:  # pragma: no cover - failure path
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"cold-start init race produced errors: {errors!r}"


def test_streaming_chunker_parser_is_thread_local() -> None:
    """A StreamingChunker shared across threads must not hand one Parser to two."""
    from chunker.streaming import StreamingChunker

    sc = StreamingChunker("python")
    held: dict[int, int] = {}
    parsers: dict[int, object] = {}
    barrier = threading.Barrier(8)

    def worker() -> None:
        barrier.wait()
        p = sc.parser  # property -> thread-local get_parser
        parsers[threading.get_ident()] = p  # hold ref (GC-proof id)
        held[threading.get_ident()] = id(p)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(set(held.values())) == len(
        held
    ), "StreamingChunker.parser shared one Parser across threads"


def test_plugin_chunk_file_uses_thread_local_parser() -> None:
    """A globally-cached plugin instance must parse via a thread-local parser."""
    from chunker.plugin_manager import get_plugin_manager

    mgr = get_plugin_manager()
    try:
        inst = mgr.get_plugin("python")
    except Exception:
        import pytest

        pytest.skip("python plugin not available in this build")
    if inst is None or not hasattr(inst, "_thread_safe_parser"):
        import pytest

        pytest.skip("python plugin instance unavailable")
    parsers: dict[int, object] = {}
    ids: dict[int, int] = {}
    barrier = threading.Barrier(6)

    def worker() -> None:
        barrier.wait()
        p = inst._thread_safe_parser()
        parsers[threading.get_ident()] = p
        ids[threading.get_ident()] = id(p)

    threads = [threading.Thread(target=worker) for _ in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(set(ids.values())) == len(
        ids
    ), "plugin _thread_safe_parser shared one Parser across threads"


def test_lease_returned_on_parse_exception() -> None:
    """acquire_parser must return the parser to the pool even if parse() raises."""
    from chunker.parser import acquire_parser

    class _Boom(Exception):
        pass

    # The lease context must exit cleanly (returning the parser) despite an
    # exception raised inside the with-block.
    try:
        with acquire_parser("python") as parser:
            assert parser is not None
            raise _Boom
    except _Boom:
        pass

    # A subsequent lease still works — the pool/cache was not corrupted or drained
    # by the exceptional exit.
    with acquire_parser("python") as parser2:
        tree = parser2.parse(b"def f():\n    return 1\n")
        assert tree.root_node is not None


def test_plugin_failopen_does_not_share_under_failure(monkeypatch) -> None:
    """A get_parser failure must PROPAGATE, never fall open to a shared parser."""
    from chunker.plugin_manager import get_plugin_manager

    mgr = get_plugin_manager()
    try:
        inst = mgr.get_plugin("python")
    except Exception:
        import pytest

        pytest.skip("python plugin not available in this build")
    if inst is None or not hasattr(inst, "_thread_safe_parser"):
        import pytest

        pytest.skip("python plugin instance unavailable")

    import pytest

    if getattr(inst, "_parser_injected", False):
        pytest.skip("instance was injected (test-language plugin)")

    # Production instance is NOT injected -> a get_parser failure must PROPAGATE,
    # not fall open to a shared self._parser. _thread_safe_parser does
    # `from chunker.parser import get_parser`, so patch it on that module.
    import chunker.parser as P

    def _boom(_lang):
        raise RuntimeError("induced parser failure")

    monkeypatch.setattr(P, "get_parser", _boom)
    with pytest.raises(RuntimeError):
        inst._thread_safe_parser()
