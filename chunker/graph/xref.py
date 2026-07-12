from __future__ import annotations

from collections import defaultdict
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

    Resolution is index-based (single pass to build name/export indexes, then
    O(1) lookups per reference) rather than the previous O(n^2 * refs)
    all-pairs scan. Behaviour is preserved: the same edge types (DEFINES,
    IMPORTS, CALLS, INHERITS, REFERENCES) and weights are produced, edges are
    keyed on the frozen IF-0-IDENTITY-1 ``node_id`` (falling back to
    ``chunk_id``), and duplicate edges are removed. Reference sets are sorted
    before resolution so edge emission order is deterministic across processes.
    """
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    chunk_map: dict[str, CodeChunk] = {}

    def node_key(c: CodeChunk) -> str:
        # Edges key on the frozen IF-0-IDENTITY-1 node_id (content+position),
        # falling back to chunk_id for chunks without a node_id.
        return c.node_id or c.chunk_id

    def signature_name(c: CodeChunk) -> str | None:
        meta = c.metadata or {}
        sig = meta.get("signature") or {}
        return sig.get("name")

    def exports_of(c: CodeChunk) -> list[str]:
        meta = c.metadata or {}
        return meta.get("exports") or []

    # Build nodes
    for c in chunks:
        node = {
            "id": node_key(c),
            "file": c.file_path,
            "lang": c.language,
            "symbol": (c.symbol_id or None),
            "kind": c.node_type,
            "attrs": c.metadata or {},
        }
        nodes.append(node)
        chunk_map[node["id"]] = c

    # ------------------------------------------------------------------
    # Single-pass indexes (built once, in chunk order, then O(1) lookups).
    #   name_index[name]          -> chunks whose signature name == name
    #   import_target_index[name] -> chunks that export `name` OR are named `name`
    # Appending in chunk order preserves the target ordering of the old
    # all-pairs "for t in chunks" inner loops. Each chunk appears at most once
    # per index bucket.
    # ------------------------------------------------------------------
    id_lookup: dict[str, CodeChunk] = {node_key(c): c for c in chunks}
    name_index: dict[str, list[CodeChunk]] = defaultdict(list)
    import_target_index: dict[str, list[CodeChunk]] = defaultdict(list)

    for t in chunks:
        t_name = signature_name(t)
        if t_name:
            name_index[t_name].append(t)
        # An import resolves to a chunk if the imported name is one of that
        # chunk's exports OR equals the chunk's signature name.
        keys: set[str] = set(exports_of(t))
        if t_name:
            keys.add(t_name)
        for k in keys:
            if k:
                import_target_index[k].append(t)

    # Helper to add a de-duplicated edge.
    seen_edges: set[tuple[str, str, str, float]] = set()

    def add_edge(
        src: str,
        dst: str,
        rel_type: str,
        weight: float = 1.0,
    ) -> None:
        if not src or not dst:
            return
        key = (src, dst, rel_type, weight)
        if key in seen_edges:
            return
        seen_edges.add(key)
        edges.append(
            {"src": src, "dst": dst, "type": rel_type, "weight": weight},
        )

    # Parent-child (defines/contains)
    for c in chunks:
        if c.parent_chunk_id and c.parent_chunk_id in id_lookup:
            add_edge(
                c.parent_chunk_id,
                node_key(c),
                "DEFINES",
                1.0,
            )

    # Imports
    for c in chunks:
        imports: list[str] = []
        if c.metadata and isinstance(c.metadata, dict):
            imports = c.metadata.get("imports") or []
        for imp in imports:
            if not imp:
                continue
            for t in import_target_index.get(imp, ()):
                add_edge(
                    node_key(c),
                    node_key(t),
                    "IMPORTS",
                    1.0,
                )

    # Calls (if present in metadata)
    for c in chunks:
        calls: list[str] = []
        if c.metadata and isinstance(c.metadata, dict):
            calls = c.metadata.get("calls") or []
        for call in calls:
            if not call:
                continue
            for t in name_index.get(call, ()):
                add_edge(
                    node_key(c),
                    node_key(t),
                    "CALLS",
                    1.0,
                )

    # Inherits (basic heuristic using metadata)
    for c in chunks:
        inherits: list[str] = []
        if c.metadata and isinstance(c.metadata, dict):
            inherits = c.metadata.get("inherits") or []
        for base in inherits:
            if not base:
                continue
            for t in name_index.get(base, ()):
                add_edge(
                    node_key(c),
                    node_key(t),
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

        # Sort the reference set so edge emission order is deterministic across
        # processes (set iteration order is otherwise hash-randomised).
        for ref in sorted(refs):
            if not ref:
                continue
            for t in name_index.get(ref, ()):
                add_edge(
                    node_key(c),
                    node_key(t),
                    "REFERENCES",
                    0.5,
                )

    return nodes, edges
