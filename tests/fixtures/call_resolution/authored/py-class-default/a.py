def helper():
    return 1


class K:
    def helper():
        return 2

    def m(self, x=helper()):
        return x
