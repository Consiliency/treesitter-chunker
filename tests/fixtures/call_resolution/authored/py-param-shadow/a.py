def helper():
    return 1


def use(helper):
    return helper()


def loc():
    helper = make()
    return helper()


def make():
    return len
