"""IFACE: the public ``chunker.chunk_text`` chunks in memory, deterministically.

The former implementation wrote ``text`` to a randomly-named temp file and
chunked that path, so the temp name fed ``compute_node_id`` and the returned
``node_id``/``chunk_id`` varied every call. The in-memory delegation to
``core.chunk_text`` makes identities stable and reproducible.
"""

from chunker import chunk_text


CODE = "def foo():\n    return 1\n\n\ndef bar():\n    return 2\n"


def test_public_chunk_text_returns_chunks():
    chunks = chunk_text(CODE, "python")
    assert chunks
    assert all(c.language == "python" for c in chunks)


def test_public_chunk_text_node_ids_are_deterministic_across_calls():
    a = chunk_text(CODE, "python")
    b = chunk_text(CODE, "python")
    assert [c.node_id for c in a] == [c.node_id for c in b], (
        "public chunk_text node_ids are not stable across calls "
        "(temp-file round-trip regressed?)"
    )
    assert [c.chunk_id for c in a] == [c.chunk_id for c in b]


def test_public_chunk_text_no_temp_file_path_leaks_into_chunks():
    # In-memory: default file_path is empty, not a /tmp/... temp name.
    chunks = chunk_text(CODE, "python")
    assert all(c.file_path == "" for c in chunks)


def test_public_chunk_text_respects_explicit_file_path():
    chunks = chunk_text(CODE, "python", file_path="module.py")
    assert chunks
    assert all(c.file_path == "module.py" for c in chunks)
    # A different file_path yields different (still deterministic) node_ids.
    other = chunk_text(CODE, "python", file_path="other.py")
    assert [c.node_id for c in chunks] != [c.node_id for c in other]
