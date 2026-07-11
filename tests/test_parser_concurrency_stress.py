"""Stress the public parser APIs under overlapping thread-pool parsing."""

from concurrent.futures import ThreadPoolExecutor

import pytest

from chunker.parser import acquire_parser, get_parser

SOURCE = b"def value():\n    return 1\n"
WORKERS = 16
PASSES_PER_WORKER = 200
REPEATS = 3


def _assert_well_formed(parser) -> None:
    tree = parser.parse(SOURCE)
    assert tree.root_node.type == "module"
    assert tree.root_node.child_count == 1
    assert not tree.root_node.has_error


@pytest.mark.parametrize("api", ["public", "lease"])
def test_concurrent_parsing_remains_well_formed(api: str) -> None:
    def parse_many() -> int:
        for _ in range(PASSES_PER_WORKER):
            if api == "public":
                _assert_well_formed(get_parser("python"))
            else:
                with acquire_parser("python") as parser:
                    _assert_well_formed(parser)
        return PASSES_PER_WORKER

    for _ in range(REPEATS):
        with ThreadPoolExecutor(max_workers=WORKERS) as executor:
            assert sum(executor.map(lambda _: parse_many(), range(WORKERS))) == (
                WORKERS * PASSES_PER_WORKER
            )
