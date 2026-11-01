"""Binding targets and expression uses for treesitter-chunker#294."""

from pathlib import Path

LIMIT = 3
FACTOR = 2


def collect(source, limit=LIMIT, *, factor: int = FACTOR):
    for item in source:
        print(item)
    for left, (right, extra) in source:
        print(left, right, extra)
    with Path(source).open() as handle:
        print(handle)
    with Path(source).open() as (stream, other):
        print(stream, other)
    try:
        print(source)
    except ValueError as error:
        print(error)
    ordered = sorted(source, key=lambda value, offset=limit: value * offset)
    squares = [entry * factor for entry in source]
    return ordered, squares
