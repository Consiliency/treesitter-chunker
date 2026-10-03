import os.path  # noqa: F401
import collections.abc as abc  # noqa: F401, PLR0402
from pathlib import Path
from typing import Iterable as Sequence, Mapping  # noqa: F401

first, second = (1, 2)
type RootAlias = int


class Container:
    from math import sqrt as class_sqrt  # noqa: F401

    class_value = 1

    class Nested:
        from math import sqrt as nested_sqrt  # noqa: F401

        nested_value = 2

        def inner(self):
            local = Path("nested")
            return local

    def read(
        self,
        default=class_value,
        typed: int = class_value,
        hidden=(class_capture := 1),
    ):
        read = Path("item")
        return read


def build():
    from math import sqrt as local_sqrt

    type LocalAlias = int
    type GenericAlias[T] = list[T]

    left, right = (1, 2)
    value = Container()
    return local_sqrt(left + right), value, LocalAlias, GenericAlias


def make_lambda():
    return lambda x, y=first, *args, **kwargs: (x, y, args, kwargs)


def match_bindings(value):
    match value:
        case [head, tail]:
            return head, tail
        case {"key": mapped, **remaining}:
            return mapped, remaining
        case Container(read=method_value) as whole:
            return method_value, whole
        case _:
            return None


def wildcard_pattern(value):
    match value:
        case Container(read=_):
            return 1
        case _:
            return 0


def tuple_match(value):
    match value:
        case first_item, second_item:
            return first_item, second_item
        case _:
            return None


def bindings(item, count: int, default=1, *args: int, **kwargs: str):
    for loop_left, loop_right in [(item, count)]:
        with Path("item").open() as handle:
            named = default
            try:
                raise ValueError(named)
            except ValueError as error:
                return loop_left, loop_right, handle, error, args, kwargs
