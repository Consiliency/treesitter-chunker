package k

class K {
    fun run(xs: List<Int>): List<Int> = xs.map { it + 1 }
    val h: (Int) -> Int = { d -> d * 2 }
}

fun outer(xs: List<Int>): Int {
    val f = { y: Int -> y + 1 }
    val g = fun(z: Int): Int { return listOf(z).map { w -> w * z }.first() }
    return f(g(xs[0]))
}

val top = { a: Int -> a }
