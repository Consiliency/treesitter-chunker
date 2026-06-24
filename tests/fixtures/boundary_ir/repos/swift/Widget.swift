class Widget {
    var count: Int = 0

    func render() -> Int {
        return helper(count)
    }

    func helper(_ value: Int) -> Int {
        return value + 1
    }
}

func run() -> Int {
    return Widget().render()
}
