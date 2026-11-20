def helper():
    return 3


def go():
    return helper()


vars()["helper"] = len
