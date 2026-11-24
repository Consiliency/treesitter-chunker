"""Physical UTF-8 span and identity contracts for file-backed chunkers."""

from pathlib import Path

import pytest
import tiktoken

from chunker.chunker import chunk_file_with_token_limit
from chunker.core import chunk_file
from chunker.repo.processor import GitAwareRepoProcessor
from chunker.vfs import InMemoryFileSystem, LocalFileSystem
from chunker.vfs_chunker import VFSChunker


def assert_definitions(chunks, core, source, expected):
    for chunk, reference, literal in zip(chunks, core, expected, strict=True):
        start = source.index(literal)
        assert (chunk.byte_start, chunk.byte_end) == (start, start + len(literal))
        assert (
            source[chunk.byte_start : chunk.byte_end]
            == chunk.content.encode()
            == literal
        )
        assert chunk.node_id == reference.node_id
        assert chunk.parent_chunk_id == reference.parent_chunk_id


@pytest.mark.parametrize("newline", [b"\n", b"\r\n", b"\r"])
def test_token_file_offsets(tmp_path, newline):
    path = tmp_path / "a.py"
    body = b"def f():" + newline + b"    return 1"
    path.write_bytes(b"# comment" + newline + body + newline)
    assert_definitions(
        chunk_file_with_token_limit(path, "python", 100),
        chunk_file(path, "python"),
        path.read_bytes(),
        [body],
    )


@pytest.mark.parametrize(
    "reader", ["token", "vfs", "stream", "memory", "batch", "iterator"]
)
def test_nested_reader_offsets(tmp_path, reader):
    path = tmp_path / "pkg" / "a.py"
    path.parent.mkdir()
    method = "def f(self):\r\n        return 'é'".encode()
    outer = b"class A:\n    " + method
    path.write_bytes("# préface\r\n".encode() + outer)
    source = path.read_bytes()
    identity = "pkg/a.py"
    if reader == "token":
        identity = str(path)
        chunks = chunk_file_with_token_limit(path, "python", 100)
    elif reader in {"vfs", "stream", "memory"}:
        if reader == "memory":
            vfs = InMemoryFileSystem()
            identity = "virtual/member.py"
            vfs.add_file(identity, source, is_text=False)
        else:
            vfs = LocalFileSystem(tmp_path)
        chunks = list(
            VFSChunker(vfs).chunk_file(identity, "python", streaming=reader == "stream")
        )
    else:
        proc = GitAwareRepoProcessor(show_progress=False, max_workers=1)
        if reader == "batch":
            (result,) = proc.process_repository(
                str(tmp_path), incremental=False
            ).file_results
        else:
            (result,) = proc.process_files_iterator(str(tmp_path))
        assert result.file_path == identity
        chunks = result.chunks
        assert all(c.metadata["file_path"] == identity for c in chunks)
    core = chunk_file(path, "python", identity_path=identity)
    assert_definitions(chunks, core, source, [outer, method])
    assert chunks[1].parent_chunk_id == chunks[0].chunk_id


@pytest.mark.parametrize(
    "endings",
    [(b"\n",) * 4, (b"\r\n",) * 4, (b"\r",) * 4, (b"\r", b"\r\n", b"\n", b"\r")],
    ids=["lf", "crlf", "cr", "mixed"],
)
@pytest.mark.parametrize("budget", [7, 10])
def test_token_file_split_offsets(tmp_path, endings, budget):
    path = tmp_path / "split.py"
    lines = [
        b"def f():",
        "    # café".encode(),
        b"    apple = 1",
        b"    apple = 1",
        b"    return apple",
    ]
    prefix = "# préface".encode() + endings[0]
    physical_lines = [
        line + end for line, end in zip(lines, (*endings, b""), strict=True)
    ]
    body = b"".join(physical_lines)
    path.write_bytes(prefix + body + endings[-1])
    source = path.read_bytes()
    (parent,) = chunk_file(path, "python")
    parts = chunk_file_with_token_limit(path, "python", budget)
    assert len(parts) > 1
    # Every physical line fits the budget. A cut must be at a fixture line end.
    cursor = len(prefix)
    rows = {cursor: 2}
    for row, line in enumerate(physical_lines, start=2):
        cursor += len(line)
        rows[cursor] = row + int(line.endswith((b"\r", b"\n")))
    cursor = len(prefix)
    encoding = tiktoken.get_encoding("cl100k_base")
    for part in parts:
        content = part.content.encode()
        end = cursor + len(content)
        assert content == source[cursor:end]
        assert (part.byte_start, part.byte_end) == (cursor, end)
        assert (part.start_line, part.end_line) == (rows[cursor], rows[end])
        assert part.parent_chunk_id == parent.chunk_id
        assert (
            part.metadata["token_count"] == len(encoding.encode(part.content)) <= budget
        )
        cursor = end
    assert cursor == len(prefix) + len(body)


@pytest.mark.parametrize("newline", [b"\n", b"\r", b"\r\n"], ids=["lf", "cr", "crlf"])
def test_class_parts_group_methods_at_physical_lines(tmp_path, newline):
    path = tmp_path / "c.py"
    prefix = "# préface".encode() + newline
    header = b"class C:" + newline
    first = b"    def a(self):" + newline + b"        return 1" + newline
    last = b"    def b(self):" + newline + b"        return 2"
    source = prefix + header + first + last + newline
    path.write_bytes(source)
    parts = [
        part
        for part in chunk_file_with_token_limit(path, "python", 12)
        if part.node_type.startswith("class_definition_part_")
    ]
    start = len(prefix)
    for part, expected, rows in zip(
        parts, (header, first, last), ((2, 3), (3, 5), (5, 6)), strict=True
    ):
        end = start + len(expected)
        assert (
            part.content.encode() == expected == source[part.byte_start : part.byte_end]
        )
        assert (part.byte_start, part.byte_end) == (start, end)
        assert (part.start_line, part.end_line) == rows
        assert part.parent_context == "class C:"
        start = end


@pytest.mark.parametrize("newline", ["\n", "\r", "\r\n"], ids=["lf", "cr", "crlf"])
def test_class_parts_oversized_preamble_first_physical_line(tmp_path, newline):
    path = tmp_path / "c.py"
    # U+2028 in a comment is ordinary source text on this physical line.
    header = "class C:  # one\u2028two"
    path.write_bytes(
        newline.join(
            [header, "    # " + "word " * 40, "    def a(self):", "        pass"]
        ).encode()
    )
    parts = [
        part
        for part in chunk_file_with_token_limit(path, "python", 12)
        if part.node_type.startswith("class_definition_part_")
    ]
    assert parts
    assert all(part.parent_context == header for part in parts)


# Captured from treesitter-chunker#766 (c593ce47) using the same relative paths.
@pytest.mark.parametrize(
    ("name", "source", "budget", "expected"),
    [
        (
            "f.py",
            "def f(): return a.b.c.d.e.f.g.h.i.j.k.l.m.n.o.p\n",
            8,
            [
                (
                    "def f(): return a.b.c.",
                    (0, 22),
                    "321a3528524df9880df6414660cd4a7b6b869c6a",
                    8,
                    (1, 1),
                ),
                (
                    "d.e.f.g.h.i.",
                    (22, 34),
                    "500f599fbb552e731df41b60f094037d76626bff",
                    7,
                    (1, 1),
                ),
                (
                    "j.k.l.m.n.o.p",
                    (34, 47),
                    "a0466dbcdcd803e417adfc856129bac667427ee8",
                    7,
                    (1, 1),
                ),
            ],
        ),
        (
            "f.py",
            "def f(a: a.b.c.d.e.f.g.h.i.j.k.l.m.n.o.p):\n    pass\n",
            8,
            [
                (
                    "def f(a: ",
                    (0, 9),
                    "599c387f0cdae9eb3e4efa2a8c03667da24256fa",
                    5,
                    (1, 1),
                ),
                (
                    "a.b.c.d.e.f.",
                    (9, 21),
                    "f3329bd81250963268089b4a3294abfbe37135c1",
                    7,
                    (1, 1),
                ),
                (
                    "g.h.i.j.k.",
                    (21, 31),
                    "ce58ab81aa8b9b275a3ca0305d1b5bc47f44f7e2",
                    6,
                    (1, 1),
                ),
                (
                    "l.m.n.o.p):\n",
                    (31, 43),
                    "cb288d9ace13f9cc58cbceecaf43055cc4cf2156",
                    6,
                    (1, 2),
                ),
                (
                    "    pass",
                    (43, 51),
                    "ca23277add22f72e891c6958549b284c2a11272e",
                    2,
                    (2, 2),
                ),
            ],
        ),
        (
            "f.py",
            "def f():\n    a = 1\n    b = 2\n    return a+b\n",
            8,
            [
                (
                    "def f():\n",
                    (0, 9),
                    "251dde2d6721bbab08ba78817a1ccd163030f05b",
                    3,
                    (1, 2),
                ),
                (
                    "    a = 1\n",
                    (9, 19),
                    "5fa897328ee1f3dd932871cfbfb46ee26b6da4d7",
                    6,
                    (2, 3),
                ),
                (
                    "    b = 2\n",
                    (19, 29),
                    "fd5526de94d4858afcc37d892837324ed1c9aa54",
                    6,
                    (3, 4),
                ),
                (
                    "    return a+b",
                    (29, 43),
                    "55d09ff1a9771ab3f530344b6bed7592dc5958a0",
                    4,
                    (4, 4),
                ),
            ],
        ),
        (
            "split.py",
            "# préface\ndef f():\n    # café\n    apple = 1\n    apple = 1\n    return apple\n",
            10,
            [
                (
                    "def f():\n    # café\n",
                    (11, 32),
                    "beb98ee46d3dd7523142dd2b111ca3d702441e87",
                    7,
                    (2, 4),
                ),
                (
                    "    apple = 1\n",
                    (32, 46),
                    "369ef74dddcb1ba06393db91bc1ffdb967358bb6",
                    6,
                    (4, 5),
                ),
                (
                    "    apple = 1\n    return apple",
                    (46, 76),
                    "3a1cb7f2993cb91af5bfa0cb82ef694213e6cc4a",
                    9,
                    (5, 6),
                ),
            ],
        ),
    ],
    ids=["one-line", "long-declaration", "line-groups", "repeated-assignment"],
)
def test_lf_split_matches_lossless_baseline(
    tmp_path, monkeypatch, name, source, budget, expected
):
    monkeypatch.chdir(tmp_path)
    path = Path(name)
    path.write_bytes(source.encode())
    parts = chunk_file_with_token_limit(path, "python", budget)
    assert [
        (
            p.content,
            (p.byte_start, p.byte_end),
            p.chunk_id,
            p.metadata["token_count"],
            (p.start_line, p.end_line),
        )
        for p in parts
    ] == expected
    assert all(p.node_id == p.chunk_id for p in parts)


def test_token_part_ending_inside_crlf(tmp_path):
    path = tmp_path / "tail.py"
    path.write_bytes(b"# head\r\ndef f():\r\n    return 1 # tail\r\n")
    *_, last = chunk_file_with_token_limit(path, "python", 1)
    assert last.content.endswith("\r")
    assert (last.start_line, last.end_line) == (3, 3)


@pytest.mark.parametrize("streaming", [False, True])
def test_vfs_span_ends_inside_crlf(tmp_path, streaming):
    path = tmp_path / "a.py"
    body = b"def f():\r\n    return 1 # tail\r"
    path.write_bytes(b"# head\r\n" + body + b"\n")
    chunks = VFSChunker(LocalFileSystem(tmp_path)).chunk_file(
        path.name, "python", streaming=streaming
    )
    assert_definitions(
        chunks,
        chunk_file(path, "python", identity_path=path.name),
        path.read_bytes(),
        [body],
    )


@pytest.mark.parametrize("reader", ["token", "batch", "iterator", "memory", "vfs"])
def test_invalid_utf8_reader_policy(tmp_path, reader):
    path = tmp_path / "a.py"
    prefix = b"# \xff\r\n"
    function = b"def f():\r\n    return '\xff'"
    path.write_bytes(prefix + function + b"\r\n")
    if reader in {"vfs", "memory"}:
        if reader == "memory":
            vfs = InMemoryFileSystem()
            vfs.add_file(path.name, path.read_bytes(), is_text=False)
        else:
            vfs = LocalFileSystem(tmp_path)
        with pytest.raises(UnicodeDecodeError):
            VFSChunker(vfs).chunk_file(path.name, "python")
        return
    if reader == "token":
        (chunk,) = chunk_file_with_token_limit(path, "python", 100)
        codec, errors = "utf-8", "replace"
    else:
        proc = GitAwareRepoProcessor(show_progress=False, max_workers=1)
        if reader == "batch":
            (result,) = proc.process_repository(
                str(tmp_path), incremental=False
            ).file_results
        else:
            (result,) = proc.process_files_iterator(str(tmp_path))
        (chunk,) = result.chunks
        codec, errors = "latin-1", "strict"
    expected = function.decode(codec, errors)
    start = len(prefix.decode(codec, errors).encode())
    assert chunk.content == expected
    assert (chunk.byte_start, chunk.byte_end) == (start, start + len(expected.encode()))


def test_watch_physical_offsets_and_decode_error(tmp_path):
    path = tmp_path / "good.py"
    body = b"def f():\r\n    return 1"
    path.write_bytes(b"# comment\r\n" + body + b"\r\n")
    (tmp_path / "bad.py").write_bytes(b"def bad():\r\n    return '\xff'\r\n")
    updates = []
    GitAwareRepoProcessor(max_workers=1, show_progress=False).watch_repository(
        str(tmp_path), updates.append, max_iterations=1
    )
    (delta,) = updates
    (error,) = delta["errors"]
    assert (error["file"], error["type"]) == ("bad.py", "UnicodeDecodeError")
    (node,) = delta["nodes_added"]
    (core,) = chunk_file(path.resolve(), "python")
    assert node["id"] == core.node_id
    (span,) = delta["spans"]
    source = path.read_bytes()
    start = source.index(body)
    assert (span["start_byte"], span["end_byte"]) == (start, start + len(body))
    assert source[span["start_byte"] : span["end_byte"]] == body


def test_token_file_requires_utf8_for_baml(tmp_path):
    path = tmp_path / "broken.baml"
    path.write_bytes(b"function f() -> string { prompt: `\xff` }\r\n")
    with pytest.raises(UnicodeDecodeError):
        chunk_file_with_token_limit(path, "baml", 100)


def test_javascript_lone_cr_function_parts_use_physical_rows(tmp_path):
    source = b"\r\rfunction compute() {\r  doWork();\r  return 1 + 2;\r}\r"
    path = tmp_path / "example.js"
    path.write_bytes(source)
    (parent,) = chunk_file(path, "javascript")
    assert (parent.start_line, parent.end_line) == (3, 6)

    parts = chunk_file_with_token_limit(path, "javascript", 6)
    assert len(parts) > 1
    cursor = parent.byte_start
    for part in parts:
        assert part.parent_chunk_id == parent.chunk_id
        assert part.byte_start == cursor
        assert part.content.encode() == source[cursor : part.byte_end]
        assert part.start_line == 1 + source.count(b"\r", 0, cursor)
        cursor = part.byte_end
        assert part.end_line == 1 + source.count(b"\r", 0, cursor)
    assert cursor == parent.byte_end
    assert parts[-1].end_line == parent.end_line


def test_julia_parser_adjacent_comment_keeps_physical_gap_in_parts(tmp_path):
    source = "# NOTE\n\r\rfunction a()\n 1\nend"
    path = tmp_path / "example.jl"
    path.write_bytes(source.encode())
    (parent,) = chunk_file(path, "julia")
    assert parent.content == source
    assert (parent.start_line, parent.end_line) == (1, 6)
    assert (parent.byte_start, parent.byte_end) == (0, len(source))

    parts = chunk_file_with_token_limit(path, "julia", 3)
    assert len(parts) > 1
    assert "".join(part.content for part in parts) == source
    assert {part.parent_chunk_id for part in parts} == {parent.chunk_id}
    cursor = 0
    for part in parts:
        assert part.byte_start == cursor
        assert part.content == source[cursor : part.byte_end]
        assert part.start_line == 1 + source.count("\n", 0, cursor) + source.count(
            "\r", 0, cursor
        )
        cursor = part.byte_end
        assert part.end_line == 1 + source.count("\n", 0, cursor) + source.count(
            "\r", 0, cursor
        )
    assert (cursor, parts[-1].end_line) == (len(source), 6)
