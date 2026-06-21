"""Impacted-path analysis for incremental Boundary IR extraction."""

from __future__ import annotations

import posixpath
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .cache import BoundaryCacheIndex, BoundaryCacheRecord


def normalize_boundary_path(path: str) -> str:
    """Total path normalization for Boundary IR identity + serialization (BUG-4).

    Produces a single canonical repo-relative POSIX form so the same logical
    path yields identical bytes regardless of OS separator or redundant
    components -- cold and incremental extraction MUST funnel every path through
    this one function before computing any ID or emitting any serialized path.

    - POSIX-ify separators (Windows ``\\`` -> ``/``).
    - Collapse ``.`` / ``..`` / redundant ``//`` via posix normpath.
    - Empty / ``.`` -> ``""`` (the repo root display path), never ``"."``.

    It is idempotent: normalize(normalize(p)) == normalize(p).
    """
    if not path:
        return ""
    posix = path.replace("\\", "/")
    normalized = posixpath.normpath(posix)
    if normalized == ".":
        return ""
    return normalized


def detect_changed_paths(
    current_hashes: dict[str, str],
    index: BoundaryCacheIndex,
    *,
    invalid_paths: set[str] | None = None,
    force_rebuild: bool = False,
) -> tuple[list[str], list[str]]:
    """Return changed and deleted relative paths in deterministic order."""
    normalized_current = {
        normalize_boundary_path(path): value for path, value in current_hashes.items()
    }
    invalid = {normalize_boundary_path(path) for path in invalid_paths or set()}
    if force_rebuild:
        return sorted(normalized_current), sorted(
            set(index.records) - set(normalized_current)
        )
    changed = set(invalid)
    for path, content_hash in normalized_current.items():
        if index.content_hashes.get(path) != content_hash:
            changed.add(path)
    deleted = set(index.records) - set(normalized_current)
    return sorted(changed), sorted(deleted)


def compute_impacted_paths(
    changed_paths: list[str],
    deleted_paths: list[str],
    records: dict[str, BoundaryCacheRecord],
    *,
    current_summaries: dict[str, dict[str, Any]] | None = None,
) -> list[str]:
    """Compute paths that need recomputation because relationships may shift."""
    changed = {normalize_boundary_path(path) for path in changed_paths}
    deleted = {normalize_boundary_path(path) for path in deleted_paths}
    summaries = {path: record.dependency_summary for path, record in records.items()}
    summaries.update(current_summaries or {})
    impacted = set(changed)
    candidate_tokens: set[str] = set(changed | deleted)
    for path in changed | deleted:
        summary = summaries.get(path, {})
        candidate_tokens.update(str(item) for item in summary.get("exports", []))
        module = summary.get("module")
        if module:
            candidate_tokens.add(str(module))

    for path, summary in summaries.items():
        endpoints = {
            normalize_boundary_path(str(item))
            for item in summary.get("relationship_endpoints", [])
        }
        if endpoints & (changed | deleted):
            impacted.add(path)
            continue
        refs = {str(item) for item in summary.get("references", [])}
        if refs & candidate_tokens:
            impacted.add(path)

    return sorted(impacted)
