from typing import overload


@overload
def f(x: int) -> int: ...
@overload
def f(x: str) -> str: ...
def f(x):
    return x


def use():
    return f(1)
