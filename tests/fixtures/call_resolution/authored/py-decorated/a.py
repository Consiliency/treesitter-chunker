def helper():
    return 1


def register(x):
    return lambda f: f


@register(helper())
def f():
    return 0
