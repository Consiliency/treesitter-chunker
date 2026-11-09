"""Parent-side executable selection for grammar operations."""

import os
import shutil


def resolve_tool(name: str) -> str | None:
    """Resolve one executable before choosing a child working directory."""
    found = shutil.which(name)
    return os.path.abspath(found) if found else None  # noqa: PTH100


def c_compiler() -> str | None:
    """Prefer gcc, consulting cc only when gcc is absent."""
    return resolve_tool("gcc") or resolve_tool("cc")


class ToolSelection:
    """One parent lookup per used tool within one public operation."""

    def __init__(self) -> None:
        self._paths: dict[str, str | None] = {}

    def optional(self, name: str) -> str | None:
        if name not in self._paths:
            self._paths[name] = resolve_tool(name)
        return self._paths[name]

    def require(self, name: str) -> str:
        selected = self.optional(name)
        if selected is None:
            raise FileNotFoundError(f"Executable not found: {name}")
        return selected
