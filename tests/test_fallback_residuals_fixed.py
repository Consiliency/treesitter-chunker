"""Regression tests for the 3 fallback-path residuals fixed at release (v4.0.0).

These were panel-found (COREFIX iter-3) and tracked in xfail-inventory; fixed
before the v4.0.0 publish so the fallback path is contract-consistent with the
class-split slice-back fix.
"""

from chunker.core import chunk_text
from chunker.fallback.base import FallbackChunker
from chunker.fallback.strategies.line_based import LineBasedChunker


def test_csv_chunk_slices_back_and_header_in_metadata():
    """CSV fallback chunks: content is a contiguous data-row slice that slices
    back to its byte span; the header is preserved in metadata, NOT prepended
    into content (which broke slice-back). Multibyte-safe."""
    content = "name,value\n" + "".join(f"row{i},{i}\n" for i in range(10))
    # Add a multibyte row so a char index != a byte offset.
    content = "náme,valüe\n" + "".join(f"rów{i},{i}\n" for i in range(10))
    src = content.encode("utf-8")
    chunks = LineBasedChunker(lines_per_chunk=3, overlap=0).chunk_csv(
        content, include_header=True
    )
    assert len(chunks) > 1
    for c in chunks:
        assert (
            src[c.byte_start : c.byte_end].decode("utf-8") == c.content
        ), "CSV chunk byte span must slice back to content"
        assert "náme,valüe" not in c.content, "header must not be inlined into content"
        assert (
            c.metadata.get("csv_header") == "náme,valüe"
        ), "header must be preserved in metadata"


def test_fallback_definition_ids_are_distinct():
    """Routeless fallback chunks must get DISTINCT definition_ids (an empty
    route collapsed them all into one, so incremental diff dropped chunks).

    Forces the fallback path via the RecursionError → SlidingWindowFallback
    branch by patching _walk to raise.
    """
    from unittest.mock import patch

    from chunker import core

    # Enough content to exceed the sliding window so multiple chunks are emitted.
    code = "\n".join(f"line {i} of plain text content here" for i in range(1000))
    with (
        patch.object(core, "_walk", side_effect=RecursionError("forced")),
        patch.object(
            core,
            "get_parser",
            lambda _l: type(
                "P",
                (),
                {"parse": lambda self, s: type("T", (), {"root_node": object()})()},
            )(),
        ),
    ):
        chunks = chunk_text(code, "python", file_path="big.py")
    assert len(chunks) > 1, "expected multiple fallback chunks"
    dids = [c.definition_id for c in chunks]
    assert len(set(dids)) == len(dids), f"fallback definition_ids collide: {dids}"
    # node_ids too (they always were distinct, but confirm).
    assert len({c.node_id for c in chunks}) == len(chunks)


def test_chunk_by_lines_offsets_correct_at_scale():
    """chunk_by_lines byte offsets slice back (the O(n^2) prefix rescan was
    replaced by a prefix array — verify correctness is preserved at scale)."""
    content = "".join(f"line {i} with some content\n" for i in range(500))
    fc = FallbackChunker()
    fc.file_path = "big.txt"
    src = content.encode("utf-8")
    chunks = fc.chunk_by_lines(content, lines_per_chunk=10, overlap_lines=0)
    assert len(chunks) == 50
    for c in chunks:
        assert src[c.byte_start : c.byte_end].decode("utf-8") == c.content
