"""Tests for exclusive and thread-local parser acquisition."""

from concurrent.futures import ThreadPoolExecutor
import logging
from pathlib import Path
from threading import Barrier

import pytest
from tree_sitter import Range

from chunker._internal.factory import ParserConfig, ParserFactory
from chunker._internal.registry import LanguageRegistry
from chunker.exceptions import ParserConfigError
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

    with factory.acquire_parser("python", ParserConfig()) as parser:
        first = parser
    with factory.acquire_parser("python") as parser:
        assert parser is not first


@pytest.mark.parametrize("leased", [False, True], ids=["public", "leased"])
@pytest.mark.parametrize(
    "config",
    [
        ParserConfig(timeout_ms=0),
        ParserConfig(timeout_ms=1),
        ParserConfig(logger=logging.getLogger("parser-config-contract")),
    ],
    ids=["timeout-zero", "timeout-positive", "logger"],
)
def test_unsupported_options_reject_actual_parser_requests(config, leased):
    fixture = Path(__file__).parent / "fixtures/boundary_ir/repos/python/app/service.py"
    source = fixture.read_bytes()
    baseline = get_parser("python").parse(source)
    assert baseline.root_node.child_count > 0 and not baseline.root_node.has_error
    factory = _factory()
    with pytest.raises(ParserConfigError, match="not support") as error:
        if leased:
            with factory.acquire_parser("python", config) as parser:
                parser.parse(source)
        else:
            get_parser("python", config).parse(source)
    option = "timeout_ms" if config.timeout_ms is not None else "logger"
    assert error.value.config_name == option
    assert error.value.value == getattr(config, option)
    assert (
        "omit" in error.value.reason
        if option == "timeout_ms"
        else "logging" in error.value.reason
    )
    tree = get_parser("python").parse(source)
    assert tree.root_node.child_count > 0
    assert not tree.root_node.has_error
    with factory.acquire_parser("python") as parser:
        restored = parser.parse(source)
    assert restored.root_node.child_count > 0 and not restored.root_node.has_error


def test_configured_range_parses_real_fixture():
    source = (
        Path(__file__).parent / "fixtures/boundary_ir/repos/python/app/service.py"
    ).read_bytes()
    selected = Range(
        start_point=(0, 0),
        end_point=(source.count(b"\n"), 0),
        start_byte=0,
        end_byte=len(source),
    )
    factory = _factory()
    with factory.acquire_parser(
        "python", ParserConfig(included_ranges=[selected])
    ) as parser:
        tree = parser.parse(source)
        assert parser.included_ranges == [selected]
    assert tree.root_node.child_count > 0 and not tree.root_node.has_error
    assert tree.root_node.text == source
