"""Boundary IR identity helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from chunker.types import CodeChunk


def _metadata_text(metadata: dict[str, Any], key: str) -> str | None:
    value = metadata.get(key)
    if isinstance(value, str) and value:
        return value
    return None


def select_node_identity(
    chunk: CodeChunk, module_name: str | None = None
) -> dict[str, str]:
    """Select the canonical Boundary IR node identity for a chunk."""
    if chunk.definition_id:
        return {"source": "definition_id", "value": chunk.definition_id}

    metadata = chunk.metadata or {}
    module = module_name or _metadata_text(metadata, "module")
    qualified_name = _metadata_text(metadata, "qualified_name")
    if module and qualified_name:
        return {
            "source": "module + qualified_name",
            "value": f"{module}:{qualified_name}",
        }

    return {"source": "node_id", "value": chunk.node_id}
