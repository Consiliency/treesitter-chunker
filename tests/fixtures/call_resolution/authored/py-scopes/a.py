def helper():
    return 1


def c_comp(xs):
    return [helper() for helper in xs]


def c_lambda():
    return (lambda helper: helper())(len)


def c_walrus():
    if (helper := mk()):
        return helper()


def c_nonlocal():
    helper = mk()

    def inner():
        nonlocal helper
        return helper()

    return inner


def c_del():
    helper = 1
    del helper
    return helper()


def c_with():
    with mk() as helper:
        return helper()


def c_for(xs):
    for helper in xs:
        return helper()


def c_match(v):
    match v:
        case helper:
            return helper()


def mk():
    return len
