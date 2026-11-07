"""CR-only Python parses with correct lines and raw byte spans (treesitter-chunker#471).

Each fixture is written to a real file and chunked with the locked Python
parser through the regular (``chunk_file``/``chunk_text``), streaming
(``chunk_file_streaming``) and VFS streaming entries; call-site locations are
checked in the symbol graph and Boundary IR. Expected byte offsets come from searching
the raw bytes, and expected lines from ``bytes.splitlines`` over the raw
prefix, which treats LF, CRLF and lone CR as line endings. Neither oracle uses
the product's parse copy.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from chunker import chunk_file, chunk_text, get_parser
from chunker.boundary import extract_boundary_ir
from chunker.core import _line_ending_offsets, _lone_cr_parse_copy
from chunker.streaming import chunk_file_streaming
from chunker.symbol_graph import extract_symbol_graph
from chunker.vfs import LocalFileSystem
from chunker.vfs_chunker import VFSChunker, chunk_file_from_vfs

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


# A multiline call whose lines are separated by each line-ending kind.
CALL_TEMPLATE = b"def alpha():\r    beta(\r        1)\r\rdef beta(x):\r    return x\r"
NEWLINES = {"lf": b"\n", "cr": b"\r", "crlf": b"\r\n"}


def call_oracle(raw: bytes) -> tuple[int, int, int, int]:
    """Raw span and physical lines of the ``beta(...)`` call in ``raw``."""
    start = raw.index(b"beta(")
    end = raw.index(b"1)", start) + len(b"1)")
    return start, end, physical_line(raw, start), physical_line(raw, end - 1)


@pytest.mark.parametrize("newline", sorted(NEWLINES))
def test_call_fact_lines_count_physical_lines(tmp_path: Path, newline: str):
    raw = CALL_TEMPLATE.replace(b"\r", NEWLINES[newline])
    path = tmp_path / "calls.py"
    path.write_bytes(raw)
    graph = extract_symbol_graph(path, "python", fail_fast=True)
    (row,) = [r for r in graph["relationships"] if r["type"] == "calls"]
    location = row["location"]
    observed = (
        location["byte_start"],
        location["byte_end"],
        location["start_line"],
        location["end_line"],
    )
    assert observed == call_oracle(raw)
    assert row["line"] == physical_line(raw, location["byte_start"])
    assert (observed[2], observed[3]) == (2, 3)


@pytest.mark.parametrize("newline", sorted(NEWLINES))
def test_boundary_ir_lines_count_physical_lines(tmp_path: Path, newline: str):
    raw = CALL_TEMPLATE.replace(b"\r", NEWLINES[newline])
    (tmp_path / "calls.py").write_bytes(raw)
    ir = extract_boundary_ir(tmp_path, "python")
    (edge,) = [e for e in ir["edges"] if e["type"] == "calls"]
    location = edge["location"]
    assert (
        location["byte_start"],
        location["byte_end"],
        location["start_line"],
        location["end_line"],
    ) == call_oracle(raw)
    nodes = {
        node["symbol"]: (
            node["span"]["byte_start"],
            node["span"]["byte_end"],
            node["span"]["start_line"],
            node["span"]["end_line"],
        )
        for node in ir["nodes"]
    }
    expected = {}
    for name, end_marker in (("alpha", b"1)"), ("beta", b"return x")):
        start = raw.index(b"def " + name.encode())
        end = raw.index(end_marker, start) + len(end_marker)
        expected[name] = (
            start,
            end,
            physical_line(raw, start),
            physical_line(raw, end),
        )
    assert nodes == expected


def test_boundary_ir_lines_match_across_line_endings(tmp_path: Path):
    def lines(newline: str):
        root = tmp_path / newline
        root.mkdir()
        (root / "calls.py").write_bytes(CALL_TEMPLATE.replace(b"\r", NEWLINES[newline]))
        ir = extract_boundary_ir(root, "python")
        spans = [node["span"] for node in ir["nodes"]]
        spans += [edge["location"] for edge in ir["edges"]]
        return sorted((span["start_line"], span["end_line"]) for span in spans)

    assert lines("cr") == lines("lf") == lines("crlf")


def test_vfs_streaming(fixture_file):
    path, raw, markers = fixture_file
    chunker = VFSChunker(LocalFileSystem(str(path.parent)))
    chunks = list(chunker.chunk_file(path.name, "python", streaming=True))
    assert_raw_contract(chunks, raw, markers)
    via_helper = chunk_file_from_vfs(
        path.name, LocalFileSystem(str(path.parent)), "python", streaming=True
    )
    assert definition_spans(list(via_helper)) == definition_spans(chunks)


@pytest.mark.parametrize(
    ("raw", "copied"),
    [
        (ISSUE_FIXTURE, True),
        (MIXED_FIXTURE, True),
        (ISSUE_FIXTURE.replace(b"\r", b"\r\n"), False),
        (ISSUE_FIXTURE.replace(b"\r", b"\n"), False),
    ],
)
def test_parse_copy_only_for_lone_cr(raw: bytes, copied: bool):
    copy = _lone_cr_parse_copy(raw, "python")
    if not copied:
        assert copy is None
        return
    assert copy is not None
    assert len(copy) == len(raw)
    assert b"\r" not in copy.replace(b"\r\n", b"")
    assert copy.replace(b"\n", b"\r") == raw.replace(b"\n", b"\r")
    # Every other language parses the raw bytes.
    assert _lone_cr_parse_copy(raw, "javascript") is None


# Other languages still parse raw bytes, so Tree-sitter rows count LF only;
# call-site lines must stay consistent with those chunk rows
# (treesitter-chunker#601 tracks changing them).
NON_PYTHON_CALLS = {
    "javascript": (
        "js",
        b"function alpha() {\r  beta(\r    1);\r}\r\rfunction beta(x) {\r"
        b"  return x;\r}\r",
    ),
    "c": (
        "c",
        b"int beta(int x) {\r  return x;\r}\r\rint alpha(void) {\r"
        b"  return beta(\r    1);\r}\r",
    ),
}


def lf_line(raw: bytes, offset: int) -> int:
    return raw[:offset].count(b"\n") + 1


@pytest.mark.parametrize("variant", ["cr", "mixed"])
@pytest.mark.parametrize("language", sorted(NON_PYTHON_CALLS))
def test_other_languages_count_only_lf(tmp_path: Path, language: str, variant: str):
    extension, raw = NON_PYTHON_CALLS[language]
    if variant == "mixed":
        # LF everywhere except a lone CR inside the multiline call.
        raw = raw.replace(b"\r", b"\n").replace(b"(\n", b"(\r")
    path = tmp_path / f"calls.{extension}"
    path.write_bytes(raw)
    assert _line_ending_offsets(raw, language) == [
        index for index, byte in enumerate(raw) if byte == 0x0A
    ]
    graph = extract_symbol_graph(path, language, fail_fast=True)
    (row,) = [r for r in graph["relationships"] if r["type"] == "calls"]
    start = raw.index(b"beta(\r")  # the call, not the C definition
    end = raw.index(b"1)", start) + len(b"1)")
    location = row["location"]
    assert (location["byte_start"], location["byte_end"]) == (start, end)
    assert (location["start_line"], location["end_line"]) == (
        lf_line(raw, start),
        lf_line(raw, end - 1),
    )
    (owner,) = [
        chunk
        for chunk in chunk_file(path, language)
        if chunk.byte_start <= start and end <= chunk.byte_end
    ]
    # The call lies within its chunk's (LF-only) rows.
    assert owner.start_line <= location["start_line"]
    assert location["end_line"] <= owner.end_line
