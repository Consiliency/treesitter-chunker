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
        if not src or not dst:
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
        imports: list[str] = []
        if c.metadata and isinstance(c.metadata, dict):
            imports = c.metadata.get("imports") or []
        if not imports:
            continue
        # Match import name to target exports or signature name
        for imp in imports:
            if not imp:
                continue
            for t in chunks:
                t_exports = []
                t_sig = (t.metadata or {}).get("signature") or {}
                t_name = t_sig.get("name")
                if imp in ((t.metadata or {}).get("exports") or []) or (
                    t_name and imp == t_name
                ):
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

    # References - check both c.references attribute and c.dependencies
    # (REQ-TSC-008: reconcile dependencies vs references for REFERENCES edges)
    for c in chunks:
        # Collect references from multiple sources
        refs: set[str] = set()

        # 1. Direct references attribute on CodeChunk
        if c.references:
            refs.update(c.references)

        # 2. Dependencies attribute on CodeChunk (often contains external refs)
        if c.dependencies:
            refs.update(c.dependencies)

        # 3. Legacy: metadata["references"] for backwards compatibility
        if c.metadata and isinstance(c.metadata, dict):
            metadata_refs = c.metadata.get("references") or []
            refs.update(metadata_refs)
            # Also check metadata["dependencies"] for backwards compatibility
            metadata_deps = c.metadata.get("dependencies") or []
            refs.update(metadata_deps)

        for ref in refs:
            if not ref:
                continue
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
