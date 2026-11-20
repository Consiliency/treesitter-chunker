try:
    from fast import helper
except ImportError:
    from slow import helper


def go():
    return helper()
