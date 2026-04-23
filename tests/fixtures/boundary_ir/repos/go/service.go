package conformance

func Render(value string) string {
	cleaned := Format(value)
	duplicate := helper(cleaned)
	return Ghost(duplicate)
}
