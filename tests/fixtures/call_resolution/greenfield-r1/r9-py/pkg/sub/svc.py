def helper(v):
    return v


def target(v):
    return v


class C:
    def a(self):
        return target(1)


class C:
    def b(self):
        return C()


def d(x):
    target(x)
    return helper(x)


def d(x, y):
    target(x)
    target(y)
    return helper(y)


def caller():
    d(1)
    unknown_thing(2)
    return target(3) + target(4)
