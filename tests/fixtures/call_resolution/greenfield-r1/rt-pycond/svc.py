import sys


def only_a():
    return 1


def only_b():
    return 2


if sys.platform == "x":
    def d(x):
        return only_a()
else:
    def d(x):
        return only_b()


def caller():
    return d(1)
