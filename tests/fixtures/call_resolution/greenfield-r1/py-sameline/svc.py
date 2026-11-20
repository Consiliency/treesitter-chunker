import os


def t(v):
    return v


def d(x): return t(x)
def d(x, y): return t(y)


if os.name == "nt":
    def e(x):
        if x:
            def e(y): return t(y)
        return t(x)
else:
    def e(x): return t(x + 1)
