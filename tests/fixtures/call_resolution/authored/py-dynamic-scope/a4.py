import sys


def helper():
    return 4


def go():
    return helper()


setattr(sys.modules[__name__], "helper", len)
