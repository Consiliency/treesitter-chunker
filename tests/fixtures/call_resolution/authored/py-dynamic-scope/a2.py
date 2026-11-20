def helper():
    return 2


def go():
    return helper()


globals()["helper"] = len
