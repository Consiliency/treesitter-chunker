"""Resolve the load-bearing tree-sitter language-pack pin."""

from __future__ import annotations

import tomllib
from pathlib import Path


def resolve_pack_pin() -> tuple[str, str]:
    """Return the lower and exclusive upper language-pack bounds from pyproject."""
    pyproject = Path(__file__).resolve().parents[2] / "pyproject.toml"
    dependencies = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"][
        "dependencies"
    ]
    requirement = next(
        dependency
        for dependency in dependencies
        if dependency.startswith("tree-sitter-language-pack")
    )

    lower = upper = None
    constraints = requirement.removeprefix("tree-sitter-language-pack")
    for constraint in constraints.split(";", maxsplit=1)[0].split(","):
        constraint = constraint.strip()
        if constraint.startswith(">="):
            lower = constraint.removeprefix(">=")
        elif constraint.startswith("<"):
            upper = constraint.removeprefix("<")

    if lower is None or upper is None:
        raise ValueError("tree-sitter-language-pack must declare >= and < bounds")
    return lower, upper
