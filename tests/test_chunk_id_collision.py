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
        {
            "id": "same",
            "node_id": "aaaa",
            "identity": {"source": "definition_id", "value": "same"},
        },
        {
            "id": "same",
            "node_id": "bbbb",
            "identity": {"source": "definition_id", "value": "same"},
        },
        {
            "id": "other",
            "node_id": "cccc",
            "identity": {"source": "definition_id", "value": "other"},
        },
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
        {
            "id": "over",
            "node_id": "n_at_byte_100",
            "identity": {"source": "definition_id", "value": "over"},
        },
        {
            "id": "over",
            "node_id": "n_at_byte_200",
            "identity": {"source": "definition_id", "value": "over"},
        },
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
        assert (
            not outside
        ), f"{label}: {len(outside)}/{len(edges)} edge sources outside node set"


def test_496_anchor_duplicate_sources_keep_exact_relationship_membership(tmp_path):
    from chunker.boundary.adapter import extract_boundary_ir

    source = tmp_path / "dupes.py"
    source.write_text(
        "def same():\n    return alpha()\n\ndef same():\n    return beta()\n",
        encoding="utf-8",
    )
    cache_dir = tmp_path / ".boundary-cache"
    documents = (
        extract_boundary_ir(tmp_path, "python"),
        extract_boundary_ir(tmp_path, "python", incremental=True, cache_dir=cache_dir),
        extract_boundary_ir(tmp_path, "python", incremental=True, cache_dir=cache_dir),
    )

    for document in documents:
        same_nodes = sorted(
            (node for node in document["nodes"] if node["symbol"] == "same"),
            key=lambda node: node["span"]["start_line"],
        )
        assert len(same_nodes) == 2
        beta_edge = next(
            edge for edge in document["edges"] if edge["reference"] == "beta"
        )
        assert beta_edge["source"] == same_nodes[1]["id"]
        assert beta_edge["id"] in same_nodes[1]["relationships"]
        assert beta_edge["id"] not in same_nodes[0]["relationships"]


def test_496_anchor_exact_node_ids_precede_name_aliases():
    from chunker.boundary.adapter import _node_symbol_indexes

    indexes = _node_symbol_indexes(
        [
            {
                "id": "first-id",
                "definition_id": "first-definition",
                "node_id": "first-node",
                "symbol_id": None,
                "qualified_name": "later-exact-id",
                "symbol": "first",
                "path": "first.py",
            },
            {
                "id": "later-exact-id",
                "definition_id": "later-definition",
                "node_id": "later-node",
                "symbol_id": None,
                "qualified_name": "second",
                "symbol": "second",
                "path": "second.py",
            },
        ]
    )

    assert indexes["later-exact-id"] == "later-exact-id"


def test_496_anchor_alias_cannot_repair_a_missing_exact_source():
    from chunker.boundary.adapter import _edge_record

    relationship = {
        "from": "missing-exact-id",
        "to": "target-id",
        "type": "calls",
        "reference": "target",
        "file": "missing.py",
    }
    symbol_indexes = {
        "missing-exact-id": "other-file-id",
        "target-id": "target-id",
    }
    nodes_by_id = {
        "other-file-id": {"id": "other-file-id", "path": "other.py"},
        "target-id": {"id": "target-id", "path": "target.py"},
    }

    assert (
        _edge_record(
            relationship,
            symbol_indexes,
            nodes_by_id,
            "strict",
        )
        is None
    )
