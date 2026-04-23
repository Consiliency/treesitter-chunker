package conformance

import "strings"

type Widget struct {
	Name string
}

func Format(value string) string {
	return strings.TrimSpace(value)
}
