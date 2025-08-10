from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from chunker.types import CodeChunk


def build_xref(
    chunks: list[CodeChunk],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Build cross-reference graph nodes and edges from chunks.

    Returns nodes and edges suitable for API/export:
      - nodes: { id, file, lang, symbol, kind, attrs }
      - edges: { src, dst, type, weight }
    """
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    chunk_map: dict[str, CodeChunk] = {}

    # Build nodes
    for c in chunks:
        node = {
            "id": c.node_id or c.chunk_id,
            "file": c.file_path,
            "lang": c.language,
            "symbol": (c.symbol_id or None),
            "kind": c.node_type,
            "attrs": c.metadata or {},
        }
        nodes.append(node)
        chunk_map[node["id"]] = c

    # Helper to add edge
    def add_edge(
        src: str,
        dst: str,
        rel_type: str,
        weight: float = 1.0,
    ) -> None:
        if not src or not dst or src == dst:
            return
        edges.append(
            {"src": src, "dst": dst, "type": rel_type, "weight": weight},
        )

    # Parent-child (defines/contains)
    id_lookup = {c.node_id or c.chunk_id: c for c in chunks}
    for c in chunks:
        if c.parent_chunk_id and c.parent_chunk_id in id_lookup:
            add_edge(
                c.parent_chunk_id,
                c.node_id or c.chunk_id,
                "DEFINES",
                1.0,
            )

    # Imports
    for c in chunks:
        imports = []
        if c.metadata and isinstance(c.metadata, dict):
            imports = c.metadata.get("imports") or []
        if not imports:
            continue
        # naive heuristic: match import name to any chunk whose content or
        # metadata suggests a module/name
        for imp in imports:
            for t in chunks:
                # simple name match fallback
                if imp and imp in (t.metadata.get("exports") or []):
                    add_edge(
                        c.node_id or c.chunk_id,
                        t.node_id or t.chunk_id,
                        "IMPORTS",
                        1.0,
                    )

    # Calls (if present in metadata)
    for c in chunks:
        calls = []
        if c.metadata and isinstance(c.metadata, dict):
            calls = c.metadata.get("calls") or []
        for call in calls:
            for t in chunks:
                sig = (t.metadata or {}).get("signature") or {}
                target_name = sig.get("name")
                if target_name and target_name == call:
                    add_edge(
                        c.node_id or c.chunk_id,
                        t.node_id or t.chunk_id,
                        "CALLS",
                        1.0,
                    )

    # Inherits (basic heuristic using metadata)
    for c in chunks:
        inherits = []
        if c.metadata and isinstance(c.metadata, dict):
            inherits = c.metadata.get("inherits") or []
        for base in inherits:
            for t in chunks:
                sig = (t.metadata or {}).get("signature") or {}
                target_name = sig.get("name")
                if target_name and target_name == base:
                    add_edge(
                        c.node_id or c.chunk_id,
                        t.node_id or t.chunk_id,
                        "INHERITS",
                        1.0,
                    )

    # References (optional, if precomputed in metadata)
    for c in chunks:
        refs = []
        if c.metadata and isinstance(c.metadata, dict):
            refs = c.metadata.get("references") or []
        for ref in refs:
            for t in chunks:
                sig = (t.metadata or {}).get("signature") or {}
                target_name = sig.get("name")
                if target_name and target_name == ref:
                    add_edge(
                        c.node_id or c.chunk_id,
                        t.node_id or t.chunk_id,
                        "REFERENCES",
                        0.5,
                    )

    return nodes, edges
