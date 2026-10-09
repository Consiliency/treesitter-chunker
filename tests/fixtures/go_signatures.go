package signatures

type Gateway struct{}
type Box[T any] struct{}

func (g *Gateway) Dispatch(id string) (string, error) { return id, nil }
func (g Gateway) Ping() {}
func (g Gateway) Join(first, second string) string { return first + second }
func (g *Gateway) Collect(ids ...string) []string { return ids }
func (Gateway) Probe(string, int) (value string, err error) { return }
func (g Gateway) SingleNamed() (value string) { return }
func (b Box[T]) Value(value T) T { return value }
func (g Gateway) Callback(cb func(string) error) func(string) error { return cb }

func Greet(name string) string { return name }
func Zero() {}
