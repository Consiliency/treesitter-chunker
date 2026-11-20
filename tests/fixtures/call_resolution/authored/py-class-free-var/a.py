def helper():
    return 1


def f():
    def helper():
        return 2

    class K:
        x = helper()

    return K


class J:
    y = helper()
