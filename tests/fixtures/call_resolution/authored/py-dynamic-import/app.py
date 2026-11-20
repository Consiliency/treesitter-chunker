import importlib


def go():
    m = importlib.import_module("a")
    return m.helper()
