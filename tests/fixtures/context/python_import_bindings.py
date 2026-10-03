import os.path  # noqa: F401
import collections.abc as abc  # noqa: F401, PLR0402
from pathlib import Path
from typing import Iterable as Sequence, Mapping  # noqa: F401

first, second = (1, 2)


class Container:
    from math import sqrt as class_sqrt  # noqa: F401

    class_value = 1

    class Nested:
        from math import sqrt as nested_sqrt  # noqa: F401

        nested_value = 2

        def inner(self):
            local = Path("nested")
            return local

    def read(self, default=class_value, typed: int = class_value):
        read = Path("item")
        return read


def build():
    from math import sqrt as local_sqrt

    left, right = (1, 2)
    value = Container()
    return local_sqrt(left + right), value


def bindings(item, count: int, default=1, *args, **kwargs):
    for loop_left, loop_right in [(item, count)]:
        with Path("item").open() as handle:
            named = (captured := default)
            try:
                raise ValueError(named)
            except ValueError as error:
                return loop_left, loop_right, handle, captured, error, args, kwargs
