import os


def t(v):
    return v


if os.name == "nt":
    def e(x):
        if x:
            def e(y): return t(y)
        return e(x)
else:
    def e(x): return t(x + 1)


def caller():
    return e(1)
