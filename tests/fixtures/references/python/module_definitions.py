"""Module definitions and nested shadowing for treesitter-chunker#274."""

import functools


class Renderer:
    class_label = "renderer"

    def render(self, value):
        label = str(value)
        return label


def render_report(value):
    cleaned = str(value)

    def helper(item):
        return item

    return helper(cleaned)


def helper(item):
    return item


@functools.cache
def cached_report(value):
    return render_report(value)


THRESHOLD = 3


def uses_parameter(helper):
    return helper


SHADOW = sorted([], key=lambda helper: helper)
