"""Assignment-expression and default-expression scope for treesitter-chunker#278."""


def outer(values):
    result = [(captured := item) for item in values]
    nested = [[(deep := cell) for cell in row] for row in values]
    return captured, deep, result, nested


class Container:
    def method(self, value=(class_capture := 1)):
        return value


def defaults(param, key=lambda item: item, rows=(row for row in ())):
    body_local = 1
    return param, key, rows, body_local


def simple():
    if (plain := 1) > 0:
        return plain
    return 0
