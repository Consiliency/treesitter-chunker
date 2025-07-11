def hello(name: str) -> None:
    print(f"Hello, {name}!")

class Greeter:
    def __init__(self, name: str) -> None:
        self.name = name

    def greet(self) -> None:
        hello(self.name)
