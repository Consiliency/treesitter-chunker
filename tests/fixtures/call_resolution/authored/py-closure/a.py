def helper():
    return 1


def outer():
    def helper():
        return 2

    def inner():
        return helper()

    return inner()
