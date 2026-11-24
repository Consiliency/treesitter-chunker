"""Physical rows on the source buffer used by each parser entry."""

from itertools import accumulate
from pathlib import Path
from zipfile import ZipFile
from unittest.mock import Mock, patch

import pytest

from chunker import chunk_file, chunk_text, core, get_parser
from chunker.boundary import extract_boundary_ir
from chunker.streaming import StreamingChunker, chunk_file_streaming
from chunker.symbol_graph import _line_bounds, extract_symbol_graph
from chunker.vfs import InMemoryFileSystem, LocalFileSystem, ZipFileSystem
from chunker.vfs_chunker import VFSChunker, chunk_file_from_vfs


def row(source, cursor):
    segments = source.splitlines(keepends=True)
    return 1 + sum(
        end <= cursor and line.endswith((b"\r", b"\n"))
        for end, line in zip(accumulate(map(len, segments)), segments, strict=True)
    )


@pytest.mark.parametrize(
    "source", [b"", b"A\r\nB\r", b"\r\r\nx\n\r", "é\u2028\\r\r".encode()]
)
def test_complete_terminators_and_endpoint_conventions(source):
    offsets = core._line_ending_offsets(source)
    for i in range(len(source) + 1):
        assert core._physical_row(offsets, i) == row(source, i)
        assert _line_bounds(offsets, i, i) == (row(source, i), row(source, i))
        assert _line_bounds(offsets, 0, i) == (1, row(source, max(0, i - 1)))


def entries(path, language):
    fs = LocalFileSystem(str(path.parent))
    return [
        chunk_file(path, language),
        chunk_text(path.read_bytes().decode(), language, str(path)),
        list(chunk_file_streaming(path, language)),
        list(VFSChunker(fs).chunk_file(path.name, language, streaming=True)),
        list(chunk_file_from_vfs(path.name, fs, language, streaming=True)),
    ]


@pytest.mark.parametrize(
    ("language", "source", "marker", "node_type"),
    [
        (
            "javascript",
            b"function alpha() {\r beta(\r 1);\r}\r\rfunction beta(x) {\r return x;\r}\r",
            b"function beta",
            "function_declaration",
        ),
        (
            "c",
            b"int beta(int x) {\r return x;\r}\r\rint alpha(void) {\r return beta(\r 1);\r}\r",
            b"int alpha",
            "function_definition",
        ),
        (
            "ruby",
            b"def alpha();\r beta(\r 1);\rend;\r\rdef beta(x);\r x;\rend;\r",
            b"def beta",
            "method",
        ),
        ("rust", b"fn a() {}\r\rfn b() {}\r", b"fn b", "function_item"),
    ],
)
@pytest.mark.parametrize("mixed", [False, True])
def test_source_definitions_and_calls(
    tmp_path, language, source, marker, node_type, mixed
):
    if mixed:
        source = source.replace(b"\r\r", b"\r\n\n")
    extension = {"javascript": "js", "ruby": "rb", "rust": "rs", "c": "c"}[language]
    path = tmp_path / f"sample.{extension}"
    path.write_bytes(source)
    later = source.index(marker)
    expected_ends = (b"end", b"end") if language == "ruby" else (b"}", b"}")
    spans = [
        (start, source.index(close, start) + len(close))
        for start, close in zip((0, later), expected_ends, strict=True)
    ]
    for chunks in entries(path, language):
        assert [(c.node_type, c.byte_start, c.byte_end) for c in chunks] == [
            (node_type, lo, hi) for lo, hi in spans
        ]
        for chunk, (lo, hi) in zip(chunks, spans, strict=True):
            assert chunk.content.encode() == source[lo:hi]
            assert (chunk.start_line, chunk.end_line) == (
                row(source, lo),
                row(source, hi),
            )
    if language == "rust":
        return
    graph = extract_symbol_graph(path, language, fail_fast=True)
    ir = extract_boundary_ir(path, language, fail_fast=True)
    assert sorted(
        (n["span"]["start_line"], n["span"]["end_line"]) for n in ir["nodes"]
    ) == [(row(source, lo), row(source, hi)) for lo, hi in spans]
    if language == "ruby":
        assert graph["call_facts"] == []
        return
    start = source.index(b"beta(\r")
    end = source.index(b"1)", start) + 2
    expected = {
        "byte_start": start,
        "byte_end": end,
        "start_line": row(source, start),
        "end_line": row(source, end - 1),
    }
    (fact,) = graph["call_facts"]
    (relationship,) = [r for r in graph["relationships"] if r["type"] == "calls"]
    (edge,) = [e for e in ir["edges"] if e["type"] == "calls"]
    assert relationship["line"] == expected["start_line"]
    assert fact["location"] == relationship["location"] == edge["location"] == expected


def test_replacement_decoding_and_physical_rows(tmp_path):
    raw = b"/*\xff\xff\xff*/\rfunction a(){\r b();\r}\r"
    source = raw.decode(errors="replace").encode()
    path = tmp_path / "app.js"
    path.write_bytes(raw)
    for buffer, chunks in [
        (source, chunk_file(path, "javascript")),
        (raw, chunk_file_streaming(path, "javascript")),
    ]:
        (chunk,) = chunks
        assert (chunk.byte_start, chunk.byte_end) == (
            buffer.index(b"function"),
            buffer.index(b"}") + 1,
        )
        assert (chunk.start_line, chunk.end_line) == (2, 4)
    (call,) = extract_symbol_graph(path, fail_fast=True)["call_facts"]
    (edge,) = [
        e
        for e in extract_boundary_ir(path, fail_fast=True)["edges"]
        if e["type"] == "calls"
    ]
    start = source.index(b"b()")
    assert start != raw.index(b"b()")
    assert (
        call["location"]
        == edge["location"]
        == {"byte_start": start, "byte_end": start + 3, "start_line": 3, "end_line": 3}
    )


def test_svelte_synthetic_source_rows_and_identity_offsets():
    source = '\r\n\r\n\r{#if ok}\r{/if}\r<script data-a="é">\r\n$: x=1;\r</script>'
    chunks = chunk_text(source, "svelte")
    (template,) = [c for c in chunks if c.parent_context == "template"]
    (reactive,) = [c for c in chunks if c.node_type == "reactive_statement"]
    assert (template.start_line, template.end_line, template.byte_start) == (4, 4, 3)
    assert (reactive.start_line, reactive.end_line, reactive.byte_start) == (7, 7, 40)


def test_matlab_script_ends_at_exclusive_cursor():
    (script,) = chunk_text("x=1;\r", "matlab")
    assert (script.node_type, script.byte_end, script.end_line) == ("script", 5, 2)


@pytest.mark.parametrize("ending", [b"\n", b"\r\n", b"\r"])
@pytest.mark.parametrize("entry", ["regular", "mmap", "vfs"])
def test_single_chunk_scan(tmp_path, ending, entry):
    path = tmp_path / "app.js"
    path.write_bytes(ending.join(f"function f{i}() {{}}".encode() for i in range(32)))
    guard = Mock(wraps=core._LONE_CR)
    with (
        patch.object(core, "_LONE_CR", guard),
        patch.object(
            core, "_line_ending_offsets", wraps=core._line_ending_offsets
        ) as build,
    ):
        if entry == "regular":
            chunks = chunk_file(path, "javascript")
        elif entry == "mmap":
            chunks = list(chunk_file_streaming(path, "javascript"))
        else:
            chunks = list(
                VFSChunker(LocalFileSystem(str(tmp_path))).chunk_file(
                    path.name, "javascript", streaming=True
                )
            )
    assert len(chunks) == 32
    assert guard.search.call_count == 1
    assert build.call_count == int(ending == b"\r")


@pytest.mark.parametrize("boundary", [4096, 1024 * 1024])
def test_interleaved_streams_across_crlf_boundary(tmp_path, boundary):
    first = tmp_path / "one.js"
    second = tmp_path / "two.js"
    prefix = b"function a(){/*"
    first.write_bytes(
        prefix + b"x" * (boundary - 1 - len(prefix)) + b"\r\n*/}\rfunction b(){}"
    )
    second.write_bytes(b"\r\rfunction x(){}\r\rfunction y(){}")
    chunker = StreamingChunker("javascript")
    a = chunker.chunk_file_streaming(first)
    b = chunker.chunk_file_streaming(second)
    try:
        assert next(a).end_line == 2
        assert next(b).start_line == 3
        assert [(c.start_line, c.byte_start) for c in a] == [(3, boundary + 5)]
        assert [c.start_line for c in b] == [5]
    finally:
        a.close()
        b.close()
    memory = InMemoryFileSystem()
    memory.add_file(first.name, first.read_bytes())
    archive = tmp_path / "source.zip"
    with ZipFile(archive, "w") as writer:
        writer.write(first, first.name)
    zipped = ZipFileSystem(archive)
    try:
        for vfs in (memory, zipped):
            chunks = VFSChunker(vfs).chunk_file(
                first.name, "javascript", streaming=True
            )
            assert [(c.start_line, c.byte_start) for c in chunks] == [
                (1, 0),
                (3, boundary + 5),
            ]
    finally:
        zipped.zip_file.close()
    fs = LocalFileSystem(str(tmp_path))
    with patch.object(fs, "get_size", return_value=11 * 1024 * 1024):
        assert [
            (c.start_line, c.end_line)
            for c in VFSChunker(fs).chunk_file(first.name, "javascript")
        ] == [(1, 2), (3, 3)]


def test_ruby_uses_raw_grammar():
    raw = b"def alpha\r  beta(\r    1)\rend\r\rdef beta(x)\r  x\rend\r"
    parser = get_parser("ruby")
    assert parser.parse(raw).root_node.has_error
    assert not parser.parse(raw.replace(b"\r", b"\n")).root_node.has_error
    with patch.object(core, "get_parser", return_value=Mock(wraps=parser)) as getter:
        chunk_text(raw.decode(), "ruby")
    getter.return_value.parse.assert_called_once_with(raw)


# Exercise real grammar-specific nodes, including languages outside Boundary IR.
# Prefix ordinary sample syntax with two physical rows (only one parser LF).
SAMPLES = Path(__file__).parent / "fixtures"


@pytest.mark.parametrize(
    ("language", "fixture", "node_type"),
    [
        ("csharp", "boundary_ir/repos/csharp/Widget.cs", "method_declaration"),
        ("cpp", "boundary_ir/repos/cpp/widget.cpp", "class_specifier"),
        ("go", "boundary_ir/repos/go/alpha.go", "function_declaration"),
        ("java", "boundary_ir/repos/java/Widget.java", "class_declaration"),
        ("kotlin", "boundary_ir/repos/kotlin/Widget.kt", "function_declaration"),
        ("php", "boundary_ir/repos/php/widget.php", "class_declaration"),
        ("swift", "boundary_ir/repos/swift/Widget.swift", "function_declaration"),
        ("typescript", "boundary_ir/repos/typescript/alpha.ts", "function_declaration"),
        ("tsx", "boundary_ir/repos/typescript/alpha.ts", "function_declaration"),
        ("clojure", "language_smoke/samples/sample.clj", "defn"),
        ("dart", "language_smoke/samples/sample.dart", "function_declaration"),
        ("elixir", "language_smoke/samples/sample.ex", "function_definition"),
        ("julia", "language_smoke/samples/sample.jl", "function_definition"),
        ("matlab", "language_smoke/samples/sample.m", "function_definition"),
        ("ocaml", "language_smoke/samples/sample.ml", "value_definition"),
        ("r", "language_smoke/samples/sample.r", "function_definition"),
        ("scala", "language_smoke/samples/sample.scala", "object_definition"),
        ("sql", "language_smoke/samples/sample.sql", "statement"),
        ("xml", "language_smoke/samples/sample.xml", "element"),
        ("yaml", "language_smoke/samples/sample.yaml", "block_mapping"),
        ("zig", "language_smoke/samples/sample.zig", "Decl"),
    ],
)
def test_language_fixture_rows(language, fixture, node_type):
    source = b"\r \n" + (SAMPLES / fixture).read_bytes()
    chunks = chunk_text(source.decode(), language)
    assert any(c.node_type == node_type and c.start_line >= 3 for c in chunks)
    for c in chunks:
        assert (c.start_line, c.end_line) == (
            row(source, c.byte_start),
            row(source, c.byte_end),
        )


@pytest.mark.parametrize(
    ("language", "text", "node_type"),
    [
        ("baml", "class Person {\n name string\n}\n", "class_declaration"),
        (
            "dockerfile",
            "FROM busybox\r\nRUN echo a \\\r\n && echo b\r\n",
            "run_instruction",
        ),
        ("haskell", "foo x = x + 1\n", "function"),
        ("toml", '[app]\nname = "foo"\n', "table"),
        ("vue", "<template><div>hi</div></template>\n", "template_element"),
    ],
)
def test_language_literals(language, text, node_type):
    source = b"\r \n" + text.encode()
    chunks = chunk_text(source.decode(), language)
    assert any(c.node_type == node_type and c.start_line >= 3 for c in chunks)
    for c in chunks:
        assert (c.start_line, c.end_line) == (
            row(source, c.byte_start),
            row(source, c.byte_end),
        )


@pytest.mark.parametrize("language", ["javascript", "typescript", "tsx"])
def test_multibyte_template_call(tmp_path, language):
    raw = "function alpha(){ const s = `é\rtext`;\r beta();\r}\rfunction beta(){}".encode()
    start = raw.index(b"beta()")
    path = (
        tmp_path
        / {"javascript": "app.js", "typescript": "app.ts", "tsx": "app.tsx"}[language]
    )
    path.write_bytes(raw)
    (call,) = extract_symbol_graph(path, language, fail_fast=True)["call_facts"]
    assert call["location"] == {
        "byte_start": start,
        "byte_end": start + 6,
        "start_line": 3,
        "end_line": 3,
    }


def test_anonymous_identity_keeps_parser_row(tmp_path):
    path = tmp_path / "app.c"
    path.write_bytes(b"\r\rint outer(){return 0;}")
    for (chunk,) in entries(path, "c"):
        assert chunk.start_line == 3
        assert chunk.qualified_route == ["function_definition:anon@1"]


@pytest.mark.parametrize(
    ("gap", "types"),
    [
        ("\n\r\r", ["function_definition"]),
        ("\n\r\r\n", ["line_comment", "function_definition"]),
    ],
)
def test_julia_grouping_uses_parser_rows(gap, types):
    source = "# NOTE" + gap + "function a()\n 1\nend"
    chunks = chunk_text(source, "julia")
    assert [c.node_type for c in chunks] == types
    for c in chunks:
        assert (c.start_line, c.end_line) == (
            row(source.encode(), c.byte_start),
            row(source.encode(), c.byte_end),
        )
