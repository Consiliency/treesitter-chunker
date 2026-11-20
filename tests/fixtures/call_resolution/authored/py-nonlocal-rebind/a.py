def outer():
    def helper():
        return 1

    def other():
        return 2

    def swap():
        nonlocal helper
        helper = other

    swap()

    return helper()
