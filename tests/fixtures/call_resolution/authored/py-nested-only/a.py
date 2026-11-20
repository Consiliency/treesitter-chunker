def outer():
    def helper():
        return 1

    return helper()
