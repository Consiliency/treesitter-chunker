package app

class Widget(val count: Int) {
    fun render(): Int {
        return helper(count)
    }

    fun helper(value: Int): Int {
        return value + 1
    }
}

fun run(): Int {
    return Widget(1).render()
}
