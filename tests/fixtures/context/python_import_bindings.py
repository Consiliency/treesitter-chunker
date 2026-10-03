import os.path  # noqa: F401
import collections.abc as abc  # noqa: F401, PLR0402
from pathlib import Path
from typing import Iterable as Sequence, Mapping  # noqa: F401

first, second = (1, 2)


class Container:
    from math import sqrt as class_sqrt  # noqa: F401

    class_value = 1

    class Nested:
        inherited = class_value  # noqa: F821

    def read(self):
        local = Path("item")
        return local


def build():
    from math import sqrt as local_sqrt

    left, right = (1, 2)
    value = Container()
    return local_sqrt(left + right), value
