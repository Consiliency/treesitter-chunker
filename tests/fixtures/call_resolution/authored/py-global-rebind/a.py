def helper():
    return 1


def patch():
    global helper
    helper = len


def use():
    return helper()
