from app.formatting import format_name


class Renderer:
    def render(self, value: str) -> str:
        return format_name(value)


def render_report(value: str) -> str:
    from app.formatting import format_name

    cleaned = format_name(value)
    duplicate = helper(cleaned)
    return missing_call(duplicate)
