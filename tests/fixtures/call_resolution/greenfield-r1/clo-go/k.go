package k

type K struct{}

func Outer(xs []int) int {
	f := func(y int) int { return y + 1 }
	g := func(z int) int {
		h := func(w int) int { return w * z }
		return h(z)
	}
	return f(g(xs[0]))
}

func (k K) Run(xs []int) int {
	cb := func(i int) int { return i + 1 }
	return cb(xs[0])
}

var Top = func(a int) int { return a }
