def helper():
    return 1


class K:
    def helper(self):
        return 2

    def meth(self):
        return helper()
