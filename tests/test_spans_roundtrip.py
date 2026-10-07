from dataclasses import asdict
from pathlib import Path

import pytest

from chunker.core import chunk_file, chunk_text
from chunker.parser import get_parser
from chunker.streaming import chunk_file_streaming


def test_spans_roundtrip_and_streaming_ids_match(tmp_path):
    # Create a simple Python file
    code = """
def alpha():
    return 1

class Beta:
    def method(self):
        return 2
""".lstrip()
    fpath = tmp_path / "sample.py"
    fpath.write_text(code, encoding="utf-8")

    # Non-streaming
    chunks = chunk_file(str(fpath), "python")
    file_bytes = fpath.read_bytes()
    for c in chunks:
        assert file_bytes[c.byte_start : c.byte_end] == c.content.encode("utf-8")

    # Streaming
    stream_chunks = list(chunk_file_streaming(str(fpath), "python"))

    # Compare IDs and spans between streaming and non-streaming
    # Sort by (start, end) to get deterministic order
    a = sorted([(c.byte_start, c.byte_end, c.node_id) for c in chunks])
    b = sorted([(c.byte_start, c.byte_end, c.node_id) for c in stream_chunks])
    assert a == b


@pytest.mark.parametrize("fixture", ["service", "same_span"])
@pytest.mark.parametrize("prefix", ["# source\n", "# café 信息\n"])
@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
@pytest.mark.parametrize("retrieval", [False, True], ids=["plain", "retrieval"])
def test_valid_utf8_file_preserves_raw_spans_and_api_identities(
    tmp_path, fixture, prefix, newline, retrieval
):
    fixtures = Path(__file__).parent / "fixtures"
    relative = {
        "service": "boundary_ir/repos/python/app/service.py",
        "same_span": "graph_same_span.py",
    }[fixture]
    fixture_text = (fixtures / relative).read_bytes().decode("utf-8")
    text = prefix + fixture_text.replace("\r\n", "\n")
    raw = text.replace("\n", newline).encode("utf-8")
    path = tmp_path / "sample.py"
    path.write_bytes(raw)
    tree = get_parser("python").parse(raw)
    assert not tree.root_node.has_error
    pending = [tree.root_node]
    declarations = {}
    while pending:
        node = pending.pop()
        if node.is_named and node.type in {
            "function_definition",
            "class_definition",
            "lambda",
        }:
            declarations[(node.type, node.start_byte, node.end_byte)] = raw[
                node.start_byte : node.end_byte
            ]
        pending.extend(node.children)
    assert declarations
    if fixture == "service":
        assert {node_type for node_type, _, _ in declarations} == {
            "class_definition",
            "function_definition",
        }
    else:
        assert sum(kind == "lambda" for kind, _, _ in declarations) == 2
        assert {
            content.split(b"(")[0]
            for (kind, _, _), content in declarations.items()
            if kind == "function_definition"
        } == {b"def f", b"def g"}

    regular = chunk_file(str(path), "python", include_retrieval_metadata=retrieval)
    streaming = list(
        chunk_file_streaming(str(path), "python", include_retrieval_metadata=retrieval)
    )
    assert regular and streaming
    for chunks in (regular, streaming):
        by_span = {(c.node_type, c.byte_start, c.byte_end): c for c in chunks}
        assert declarations.keys() <= by_span.keys()
        for span, content in declarations.items():
            assert by_span[span].content.encode("utf-8") == content
        for chunk in chunks:
            assert raw[chunk.byte_start : chunk.byte_end] == chunk.content.encode(
                "utf-8"
            )
        if fixture == "service":
            parent = next(c for c in chunks if c.node_type == "class_definition")
            method = next(c for c in chunks if c.content.startswith("def render("))
            assert method.parent_chunk_id == parent.chunk_id
            assert method.qualified_route[:-1] == parent.qualified_route

    def projection(chunks):
        return sorted(
            (
                c.node_type,
                c.start_line,
                c.end_line,
                c.byte_start,
                c.byte_end,
                c.content,
                c.node_id,
                c.chunk_id,
                c.parent_chunk_id,
                tuple(c.qualified_route),
            )
            for c in chunks
        )

    assert projection(regular) == projection(streaming)


@pytest.mark.parametrize("newline", ["\n", "\r\n"], ids=["lf", "crlf"])
@pytest.mark.parametrize("retrieval", [False, True], ids=["plain", "retrieval"])
def test_raw_file_newlines_preserve_explicit_identity_alias(
    tmp_path, newline, retrieval
):
    fixture = Path(__file__).parent / "fixtures/boundary_ir/repos/python/app/service.py"
    text = "# café 信息\n" + fixture.read_bytes().decode("utf-8").replace("\r\n", "\n")
    raw = text.replace("\n", newline).encode("utf-8")
    assert not get_parser("python").parse(raw).root_node.has_error
    alias = "app/service.py"
    expected = chunk_text(
        raw.decode("utf-8"),
        "python",
        file_path=alias,
        include_retrieval_metadata=retrieval,
    )
    assert expected
    actual = []
    for filename in ("first.py", "second.py"):
        path = tmp_path / filename
        path.write_bytes(raw)
        chunks = chunk_file(
            str(path),
            "python",
            identity_path=alias,
            include_retrieval_metadata=retrieval,
        )
        assert chunks
        assert [asdict(c) for c in chunks] == [asdict(c) for c in expected]
        actual.append(chunks)
    assert [c.node_id for c in actual[0]] == [c.node_id for c in actual[1]]
    assert any(c.parent_chunk_id for c in expected)


def test_invalid_utf8_file_retains_replacement_fallback(tmp_path):
    fixture = Path(__file__).parent / "fixtures/boundary_ir/repos/python/app/service.py"
    raw = b"# invalid: \xff\r\n" + fixture.read_bytes().replace(b"\r\n", b"\n").replace(
        b"\n", b"\r\n"
    )
    path = tmp_path / "replacement.py"
    path.write_bytes(raw)
    decoded = raw.decode("utf-8", errors="replace")
    assert "\ufffd" in decoded
    assert not get_parser("python").parse(decoded.encode("utf-8")).root_node.has_error
    expected = chunk_text(
        decoded, "python", file_path=str(path), include_retrieval_metadata=True
    )
    actual = chunk_file(str(path), "python", include_retrieval_metadata=True)
    assert actual
    assert [asdict(c) for c in actual] == [asdict(c) for c in expected]
