"""Tests for exclusive and thread-local parser acquisition."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

from chunker._internal.factory import ParserConfig, ParserFactory
from chunker._internal.registry import LanguageRegistry
from chunker.parser import get_parser


def _factory() -> ParserFactory:
    return ParserFactory(
        LanguageRegistry(Path(__file__).parent.parent / "build" / "my-languages.so")
    )


def test_lease_removes_parser_from_idle_containers() -> None:
    factory = _factory()

    with factory.acquire_parser("python") as parser:
        pool = factory._get_pool("python")
        assert parser not in factory._cache.cache.values()
        assert parser not in pool.pool.queue

    pool = factory._get_pool("python")
    idle_parsers = [*factory._cache.cache.values(), *pool.pool.queue]
    assert idle_parsers.count(parser) == 1


def test_public_get_parser_is_thread_local() -> None:
    same_thread_first = get_parser("python")
    same_thread_second = get_parser("python")
    assert same_thread_first is same_thread_second

    barrier = Barrier(3)

    def parser_from_worker():
        parser = get_parser("python")
        barrier.wait()
        return parser

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(parser_from_worker)
        second = executor.submit(parser_from_worker)
        barrier.wait()
        assert first.result() is not second.result()


def test_configured_lease_is_not_reused() -> None:
    factory = _factory()

    with factory.acquire_parser("python", ParserConfig(timeout_ms=1)) as parser:
        first = parser
    with factory.acquire_parser("python") as parser:
        assert parser is not first
