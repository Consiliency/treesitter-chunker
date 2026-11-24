from __future__ import annotations as feature

import os, sys  # noqa: E401, F401
from contextlib import nullcontext

x = [()]
left, (right, *tail) = (1, (2, 3))


def owner(cb=lambda: x, *x, **options):
    for item in x:
        print(item)
    with nullcontext(1) as (alias):
        print(alias)
    try:
        cb()
    except* ValueError as problem:
        print(problem)
    import json as local

    class Child((base := object)):
        marker = (hidden := 1)

    return (
        [(captured := val) for val in options],  # noqa: F841
        (lambda: x),
        local,
        base,  # noqa: F821
    )


class ModuleChild((parent_base := object)):
    marker = (private := 2)


items = [(lambda: x) for x in (lambda: x)() for y in (lambda: x)()]  # noqa: PLC3002


def typed(*args: int, **kwargs: str):
    return typed(*args, **kwargs)


def swap(a, b, values, obj, rows, index):
    a, b = (b, a)
    a, b = [b, a]
    [a, (b, *rest)] = values
    obj.field, a = values
    rows[index], b = values
    return a, b, rest


def enclosing():
    x = 2  # noqa: F841
    owned = 3

    def global_user():
        global x
        for x in ():
            pass

    class Intervening:
        owned = 4

        def method(self):
            nonlocal owned
            with nullcontext() as owned:
                pass

    return global_user, Intervening


def defaults(value=(from_default := 1)):
    return value


def first_match():
    for same in ():
        pass
    same = 1
    return same


def header_owner():
    header = object

    class Nested((lambda: header)()):  # noqa: PLC3002
        header = int

    return Nested


async def contexts(manager, rows):
    async with manager as one, manager as two:
        async for key, (*extra,) in rows:
            yield one, two, key, extra


def expressions(data):
    groups = [{(saved := item) for item in seq} for seq in data]
    mapping = {k: value for k, value in data}  # noqa: C416
    stream = (entry for entry in data)
    return groups, mapping, stream, saved


def sibling():
    return ()


item = alias = problem = local = options = captured = base = "outer"


def condition(source):
    if captured := source:
        return captured
    return None


def imported():
    import xml.etree
    from . import sibling as nearby
    from pathlib import (
        Path as PathType,
        PurePath,
    )

    return xml, nearby, PathType, PurePath
