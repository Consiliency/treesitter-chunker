from chunker.core import chunk_text
from chunker.types import CodeChunk


SOURCE = """\
class First:
    def __init__(self): pass

class Second:
    def __init__(self): pass
"""


def test_duplicate_named_siblings_have_distinct_stable_chunk_ids():
    first = chunk_text(SOURCE, "python", "dupes.py")
    second = chunk_text(SOURCE, "python", "dupes.py")

    first_initializers = [
        chunk
        for chunk in first
        if chunk.qualified_route[-1] == "function_definition:__init__"
    ]

    assert len(first_initializers) == 2
    assert len({chunk.chunk_id for chunk in first_initializers}) == 2
    assert [chunk.chunk_id for chunk in first] == [chunk.chunk_id for chunk in second]
    assert all(chunk.chunk_id == chunk.node_id for chunk in first)
    assert all(len(chunk.node_id) == 40 for chunk in first)


def test_anonymous_siblings_at_different_offsets_have_distinct_ids():
    common = {
        "language": "python",
        "file_path": "dupes.py",
        "node_type": "function_definition",
        "start_line": 1,
        "end_line": 1,
        "byte_end": 20,
        "parent_context": "",
        "content": "lambda: None",
        "qualified_route": ["function_definition:anon"],
    }
    first = CodeChunk(byte_start=0, **common)
    second = CodeChunk(byte_start=10, **common)

    assert first.chunk_id != second.chunk_id
    assert first.chunk_id == first.node_id
    assert second.chunk_id == second.node_id


def test_boundary_node_ids_distinct_for_svelte_synthetic_chunks():
    """Byte-identical Svelte reactive/control-flow lines must get distinct chunk_ids
    (IDENTITY panel finding: synthetic chunks used byte_start=0 -> collision)."""
    from chunker import chunk_text

    code = "<script>\n$: a = 1\n$: a = 1\n</script>\n"
    chunks = chunk_text(code, "svelte")
    reactive = [c for c in chunks if c.node_type == "reactive_statement"]
    assert len(reactive) == 2
    assert len({c.chunk_id for c in reactive}) == 2, "identical $: lines collided"


def test_boundary_dedupe_disambiguates_colliding_node_identities():
    """Two Boundary nodes that would share a canonical id are disambiguated by node_id
    (IDENTITY panel finding: definition_id collapses same-name overloads)."""
    from chunker.boundary.adapter import _dedupe_node_identities

    records = [
        {"id": "same", "node_id": "aaaa", "identity": {"source": "definition_id", "value": "same"}},
        {"id": "same", "node_id": "bbbb", "identity": {"source": "definition_id", "value": "same"}},
        {"id": "other", "node_id": "cccc", "identity": {"source": "definition_id", "value": "other"}},
    ]
    _dedupe_node_identities(records)
    ids = [r["id"] for r in records]
    assert len(set(ids)) == 3, f"boundary node ids still collide: {ids}"
    # first occurrence keeps the base id; the colliding second is disambiguated
    assert records[0]["id"] == "same"
    assert records[1]["id"] == "same#1"
    assert records[2]["id"] == "other"


def test_svelte_reactive_distinct_across_script_blocks():
    """Identical `$:` lines in DIFFERENT <script> blocks must NOT collide
    (IDENTITY panel: body-relative offsets reset per block -> file-absolute now)."""
    from chunker import chunk_text

    code = '<script context="module">\n$: a = 1\n</script>\n<script>\n$: a = 1\n</script>\n'
    chunks = chunk_text(code, "svelte")
    reactive = [c for c in chunks if c.node_type == "reactive_statement"]
    assert len(reactive) == 2
    assert len({c.chunk_id for c in reactive}) == 2, "cross-block $: lines collided"


def test_dedupe_ordinal_is_position_independent():
    """Colliding boundary node ids are disambiguated by a STABLE ORDINAL (#1, #2),
    NOT the position-sensitive node_id (IDENTITY panel: no stability regression)."""
    from chunker.boundary.adapter import _dedupe_node_identities

    records = [
        {"id": "over", "node_id": "n_at_byte_100", "identity": {"source": "definition_id", "value": "over"}},
        {"id": "over", "node_id": "n_at_byte_200", "identity": {"source": "definition_id", "value": "over"}},
    ]
    _dedupe_node_identities(records)
    # Second is disambiguated by ordinal, independent of its node_id/byte position.
    assert records[0]["id"] == "over"
    assert records[1]["id"] == "over#1"


def test_boundary_edges_resolve_to_nodes_all_paths(tmp_path):
    """Every Boundary IR edge endpoint must be a real node id on the default,
    incremental-cold, and incremental-warm paths (IDENTITY panel: cold path had
    an empty symbol_index -> all edges resolved outside the node set)."""
    from chunker.boundary.adapter import extract_boundary_ir

    src = tmp_path / "a.js"
    src.write_text("function foo(){ bar(); }\nfunction bar(){ return 1; }\n")

    irs = {
        "default": extract_boundary_ir(str(tmp_path)),
        "incremental_cold": extract_boundary_ir(str(tmp_path), incremental=True),
        "incremental_warm": extract_boundary_ir(str(tmp_path), incremental=True),
    }
    for label, ir in irs.items():
        node_ids = {n["id"] for n in ir["nodes"]}
        edges = ir.get("edges", [])
        outside = [e for e in edges if e.get("source") not in node_ids]
        assert not outside, f"{label}: {len(outside)}/{len(edges)} edge sources outside node set"
