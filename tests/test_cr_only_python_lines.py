"""CR-only Python parses with correct lines and raw byte spans (treesitter-chunker#471).

Each fixture is written to a real file and chunked with the locked Python
parser through the regular (``chunk_file``/``chunk_text``) and streaming
(``chunk_file_streaming``) entries. Expected byte offsets come from searching
the raw bytes, and expected lines from ``bytes.splitlines`` over the raw
prefix, which treats LF, CRLF and lone CR as line endings. Neither oracle uses
the product's parse copy.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chunker import chunk_file, chunk_text, get_parser
from chunker.streaming import chunk_file_streaming

ISSUE_FIXTURE = b"def alpha():\r    return 1\r\rdef beta():\r    return 2\r"
MIXED_FIXTURE = (
    b"def alpha():\n    return 1\r\n\rdef beta(x):\r"
    b'    """Doc\r    line."""\r\n    return x\n\r'
    b"class Gamma:\r    def delta(self):\r        return '\xc3\xa9'\r"
)
TRIPLE_FIXTURE = (
    b'def alpha():\r    text = """one\rtwo\r\nthree"""\r    return text\r\r'
    b"def beta():\r    return 2\r"
)
# (start marker, end marker) of every expected definition chunk, in order.
EXPECTED = {
    "issue": (
        ISSUE_FIXTURE,
        [(b"def alpha", b"return 1"), (b"def beta", b"return 2")],
    ),
    "mixed": (
        MIXED_FIXTURE,
        [
            (b"def alpha", b"return 1"),
            (b"def beta", b"return x"),
            (b"class Gamma", b"return '\xc3\xa9'"),
            (b"def delta", b"return '\xc3\xa9'"),
        ],
    ),
    "triple": (
        TRIPLE_FIXTURE,
        [(b"def alpha", b"return text"), (b"def beta", b"return 2")],
    ),
}


def physical_line(raw: bytes, offset: int) -> int:
    """1-based line of ``offset``: line endings in the raw prefix, plus one."""
    lines = raw[:offset].splitlines(keepends=True)
    return 1 + sum(1 for line in lines if line.endswith((b"\n", b"\r")))


def expected_spans(raw: bytes, markers):
    spans = []
    for start_marker, end_marker in markers:
        start = raw.index(start_marker)
        end = raw.index(end_marker, start) + len(end_marker)
        spans.append((start, end, physical_line(raw, start), physical_line(raw, end)))
    return spans


def definition_spans(chunks):
    return sorted(
        (chunk.byte_start, chunk.byte_end, chunk.start_line, chunk.end_line)
        for chunk in chunks
        if chunk.node_type in {"function_definition", "class_definition"}
    )


def assert_raw_contract(chunks, raw: bytes, markers) -> None:
    assert definition_spans(chunks) == sorted(expected_spans(raw, markers))
    for chunk in chunks:
        # Content is the physical bytes of the reported span.
        assert chunk.content.encode("utf-8") == raw[chunk.byte_start : chunk.byte_end]


@pytest.fixture(params=sorted(EXPECTED))
def fixture_file(request, tmp_path: Path):
    raw, markers = EXPECTED[request.param]
    path = tmp_path / f"{request.param}.py"
    path.write_bytes(raw)
    assert path.read_bytes() == raw
    return path, raw, markers


def test_oracle_matches_lf_translation():
    # Sanity: the line oracle agrees with an LF-only count after translation.
    for raw, _ in EXPECTED.values():
        lf = raw.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
        assert raw.count(b"\r") > 0
        assert physical_line(raw, len(raw)) == lf.count(b"\n") + 1


def test_raw_parser_limitation_is_real():
    # The locked grammar alone cannot parse CR-only source (the issue's evidence).
    tree = get_parser("python").parse(ISSUE_FIXTURE)
    assert tree.root_node.has_error


def test_regular_chunk_file(fixture_file):
    path, raw, markers = fixture_file
    assert_raw_contract(chunk_file(path, "python"), raw, markers)


def test_regular_chunk_text(fixture_file):
    path, raw, markers = fixture_file
    chunks = chunk_text(raw.decode("utf-8"), "python", str(path))
    assert_raw_contract(chunks, raw, markers)


def test_streaming(fixture_file):
    path, raw, markers = fixture_file
    assert_raw_contract(list(chunk_file_streaming(path, "python")), raw, markers)


def test_regular_and_streaming_agree(fixture_file):
    path, _, _ = fixture_file
    regular = chunk_file(path, "python")
    streaming = list(chunk_file_streaming(path, "python"))
    assert definition_spans(regular) == definition_spans(streaming)
    assert {c.node_id for c in regular if c.node_type == "function_definition"} == {
        c.node_id for c in streaming if c.node_type == "function_definition"
    }


@pytest.mark.parametrize("newline", [b"\n", b"\r\n"])
def test_lf_and_crlf_results_are_unchanged(tmp_path: Path, newline: bytes):
    raw = ISSUE_FIXTURE.replace(b"\r", newline)
    lone_cr = tmp_path / "lone_cr.py"
    lone_cr.write_bytes(ISSUE_FIXTURE)
    path = tmp_path / "translated.py"
    path.write_bytes(raw)
    markers = EXPECTED["issue"][1]
    for chunks in (chunk_file(path, "python"), chunk_file_streaming(path, "python")):
        chunks = list(chunks)
        assert_raw_contract(chunks, raw, markers)
    # Same lines as the CR-only file; only the physical newline bytes differ.
    assert [s[2:] for s in definition_spans(chunk_file(path, "python"))] == [
        s[2:] for s in definition_spans(chunk_file(lone_cr, "python"))
    ]
