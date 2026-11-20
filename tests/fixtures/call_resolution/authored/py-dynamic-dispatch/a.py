class A:
    def run(self):
        return 1

    def go(self):
        return self.run()


class B:
    def run(self):
        return 2


def go(x):
    return x.run()
