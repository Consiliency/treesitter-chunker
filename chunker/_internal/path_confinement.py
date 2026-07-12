"""Canonical path containment for filesystem-facing interfaces."""

from __future__ import annotations

from pathlib import Path


def resolve_within_root(candidate: str | Path, root: str | Path) -> Path:
    """Resolve *candidate* and reject paths that escape *root*.

    ``Path.resolve()`` follows existing symlinks and resolves symlinked parent
    directories for prospective output paths, so the containment check covers
    both reads and file creation.
    """
    candidate_path = Path(candidate)
    if ".." in candidate_path.parts:
        raise ValueError("Path traversal is not allowed")

    root_path = Path(root).resolve()
    resolved = (
        candidate_path.resolve()
        if candidate_path.is_absolute()
        else (root_path / candidate_path).resolve()
    )
    try:
        resolved.relative_to(root_path)
    except ValueError as exc:
        raise ValueError("Path escapes the configured root") from exc
    return resolved
