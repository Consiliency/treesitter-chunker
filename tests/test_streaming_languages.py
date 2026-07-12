"""Streaming must be per-language-correct, not Python-only.

Regression tests for the bug where ``chunker/streaming.py`` hardcoded the three
Python node types, so streaming a Rust/Go/JS/Java file silently yielded an empty
result. Streaming now derives chunkable node types from the same
language-config registry ``core._walk`` uses, so it must produce the same
chunks (spans + ids) as non-streaming ``chunk_file`` -- or raise an explicit
error for an unknown language, never a silent empty result.

Part (a) below FAILS on the pre-fix code (Rust/Go/JS stream to empty). Part (b)
already passes on pre-fix code (the parser raises), and is asserted here to lock
in the "explicit error, never silent empty" contract.
"""

from __future__ import annotations

import pytest

from chunker.core import chunk_file
from chunker.exceptions import LanguageNotFoundError
from chunker.streaming import chunk_file_streaming

RUST_SOURCE = """\
struct Point {
    x: i32,
    y: i32,
}

fn add(a: i32, b: i32) -> i32 {
    a + b
}

fn main() {
    let p = Point { x: 1, y: 2 };
    println!("{}", add(p.x, p.y));
}
"""

GO_SOURCE = """\
package main

type Point struct {
    X int
    Y int
}

func Add(a int, b int) int {
    return a + b
}

func main() {
    p := Point{X: 1, Y: 2}
    println(Add(p.X, p.Y))
}
"""

JS_SOURCE = """\
function add(a, b) {
    return a + b;
}

class Calculator {
    multiply(a, b) {
        return a * b;
    }
}

function main() {
    const c = new Calculator();
    return add(1, 2) + c.multiply(3, 4);
}
"""


def _spans(chunks):
    """Return the comparable (byte_start, byte_end, node_id) set for chunks."""
    return sorted((c.byte_start, c.byte_end, c.node_id) for c in chunks)


@pytest.mark.parametrize(
    ("language", "suffix", "source", "expected_node_types"),
    [
        ("rust", ".rs", RUST_SOURCE, {"function_item", "struct_item"}),
        ("go", ".go", GO_SOURCE, {"function_declaration"}),
        (
            "javascript",
            ".js",
            JS_SOURCE,
            {"function_declaration", "class_declaration", "method_definition"},
        ),
    ],
)
def test_streaming_matches_chunk_file_per_language(
    tmp_path, language, suffix, source, expected_node_types
):
    """Streaming a non-Python file yields the same chunks as chunk_file.

    On the pre-fix code streaming returned an empty list for every one of these
    languages, so ``stream_chunks`` was empty and this assertion failed.
    """
    fpath = tmp_path / f"sample{suffix}"
    fpath.write_text(source, encoding="utf-8")

    regular = chunk_file(str(fpath), language)
    stream = list(chunk_file_streaming(str(fpath), language))

    # Never silently empty: the file has real definitions to chunk.
    assert regular, f"chunk_file produced no chunks for {language}"
    assert stream, f"streaming produced no chunks for {language} (silent empty)"

    # Byte offsets are correct: each streamed chunk slices back to its content.
    file_bytes = fpath.read_bytes()
    for c in stream:
        assert file_bytes[c.byte_start : c.byte_end] == c.content.encode("utf-8")

    # Streaming spans + ids match non-streaming exactly (roundtrip contract).
    assert _spans(stream) == _spans(regular)

    # The expected declarations are actually present (guards against matching
    # two empties).
    streamed_types = {c.node_type for c in stream}
    assert expected_node_types & streamed_types, (
        f"expected one of {expected_node_types} in streamed node types, "
        f"got {streamed_types}"
    )


def test_streaming_unknown_language_raises_explicit_error(tmp_path):
    """An unknown language must raise, not silently yield nothing."""
    fpath = tmp_path / "sample.rs"
    fpath.write_text(RUST_SOURCE, encoding="utf-8")

    with pytest.raises(LanguageNotFoundError):
        # chunk_file_streaming is a generator; force evaluation to trigger the
        # thread-local get_parser() lookup that raises for unknown languages.
        list(chunk_file_streaming(str(fpath), "not_a_real_language"))
