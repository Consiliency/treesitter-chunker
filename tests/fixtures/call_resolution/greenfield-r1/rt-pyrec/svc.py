def only_b():
    return 2


class C:
    def a(self):
        return 1


class C:
    def b(self):
        return self.c()

    def c(self):
        return only_b()


def d(x):
    return 1


def d(x, y):
    return d(x)


def uses_c2():
    return C().c()
