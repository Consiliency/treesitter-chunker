def only_a():
    return 1


def only_b():
    return 2


def d(x):
    return only_a()


def d(x, y):
    return only_b()
