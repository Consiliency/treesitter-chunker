fun onlyA(): Int = 1
fun onlyB(): Int = 2
fun f(a: Int): Int {
    return onlyA()
}
fun f(s: String): Int {
    return onlyB()
}
fun g(): Int { return f(1) }
