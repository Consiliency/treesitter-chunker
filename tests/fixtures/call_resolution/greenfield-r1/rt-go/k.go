package k

func onlyA() int { return 1 }
func onlyB() int { return 2 }

type T struct{}

func (t T) M() int {
	return onlyA()
}

type U struct{}

func (u U) M() int {
	return onlyB()
}
