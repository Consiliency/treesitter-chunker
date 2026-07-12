from chunker._internal.cache import CACHE_VERSION
from chunker.core import chunk_text
from chunker.graph.xref import build_xref


SOURCE = """\
class First:
    def __init__(self): pass

class Second:
    def __init__(self): pass
"""


def test_id_keyed_maps_preserve_duplicate_named_siblings_and_parent_links():
    chunks = chunk_text(SOURCE, "python", "dupes.py")
    chunk_by_id = {chunk.chunk_id: chunk for chunk in chunks}
    nodes, edges = build_xref(chunks)

    initializers = [
        chunk
        for chunk in chunks
        if chunk.qualified_route[-1] == "function_definition:__init__"
    ]
    classes = [chunk for chunk in chunks if chunk.node_type == "class_definition"]

    assert len(chunk_by_id) == len(chunks)
    assert len({node["id"] for node in nodes}) == len(chunks)
    assert len(initializers) == len(classes) == 2
    assert {chunk.parent_chunk_id for chunk in initializers} == {
        chunk.chunk_id for chunk in classes
    }
    assert {
        (edge["src"], edge["dst"]) for edge in edges if edge["type"] == "DEFINES"
    } == {(chunk.parent_chunk_id, chunk.chunk_id) for chunk in initializers}


def test_cache_version_invalidates_pre_identity_contract_entries():
    assert CACHE_VERSION == "2.0"
