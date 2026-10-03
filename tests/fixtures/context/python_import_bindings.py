import os.path  # noqa: F401
import collections.abc as abc  # noqa: F401, PLR0402
from pathlib import Path
from typing import Iterable as Sequence, Mapping  # noqa: F401


class Container:
    def read(self):
        local = Path("item")
        return local


def build():
    from math import sqrt as local_sqrt

    value = Container()
    return local_sqrt(value)
