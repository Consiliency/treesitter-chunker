"""Regression tests for the four panel-flagged COREFIX iteration-3 residuals.

Each test targets a defect the ≥3-agent merge panel found in the iteration-2
residual fixes:

1. class-split byte spans overshoot the parent + duplicate methods collapse
   to the first occurrence (no search_from threaded on the class path);
2. delimiter LINE accounting double-counts a multiline delimiter's newlines;
3. the identifier-index cache returns stale chunks on a same-length rechunk;
4. candidate selection is set-iteration-order dependent (non-deterministic).
"""

from chunker.fallback.base import FallbackChunker
from chunker.interfaces.fallback import ChunkingMethod, FallbackConfig
from chunker.smart_context import TreeSitterSmartContextProvider
from chunker.token.chunker import TreeSitterTokenAwareChunker
from chunker.types import CodeChunk


def _method(n: int) -> str:
    # A byte-identical method body (only the def name differs is NOT allowed —
    # we want truly identical text to exercise the collapse-to-first defect).
    body = "\n".join(f"        x{j} = {j} + compute(value)" for j in range(8))
    return f"    def run(self):\n{body}\n        return x0\n"


def test_class_split_spans_slice_back_and_disambiguate_identical_methods():
    """Class-split sub-chunk spans must slice back to their content (README
    token-split span contract), stay within the parent, and byte-identical
    methods must map to DISTINCT offsets (residual #1)."""
    m = _method(0)
    content = "class C:\n" + m + m  # two identical methods
    byte_start = 100
    original = CodeChunk(
        language="python",
        file_path="c.py",
        node_type="class_definition",
        start_line=1,
        end_line=1 + content.count("\n"),
        byte_start=byte_start,
        byte_end=byte_start + len(content.encode("utf-8")),
        parent_context="",
        content=content,
    )
    # Reconstruct the "file" so the parent's byte span slices back to its content.
    source = b"x" * byte_start + content.encode("utf-8")
    chunker = TreeSitterTokenAwareChunker()
    parts = chunker._split_class_chunk(original, max_tokens=40, model="gpt-4")
    # The split must actually separate the two methods.
    assert len(parts) >= 2, f"expected the two methods to split, got {len(parts)}"
    for p in parts:
        # Contract: slicing the source at the span reproduces the content exactly.
        assert (
            source[p.byte_start : p.byte_end].decode("utf-8") == p.content
        ), f"span {p.byte_start}:{p.byte_end} does not slice back to content"
        # And it stays within the parent's byte range (no overshoot).
        assert original.byte_start <= p.byte_start <= p.byte_end <= original.byte_end, (
            f"sub-chunk {p.byte_start}:{p.byte_end} escapes parent "
            f"{original.byte_start}:{original.byte_end}"
        )
        # The class header is preserved as context (not lost) even though it is
        # no longer prepended into the sliceable content.
        assert "class C:" in (
            p.parent_context or ""
        ), "class header context was dropped from parent_context"
    # Identical methods must land at DISTINCT byte offsets (no collapse-to-first).
    method_parts = [p for p in parts if "def run" in p.content]
    starts = [p.byte_start for p in method_parts]
    assert len(set(starts)) == len(
        starts
    ), f"identical methods collapsed to the same byte_start: {starts}"


def test_delimiter_line_numbers_multiline_delimiter():
    """A multiline delimiter with a blank interior part must not double-count
    the delimiter's newlines in the line accounting (residual #2)."""
    fc = FallbackChunker(FallbackConfig(method=ChunkingMethod.DELIMITER_BASED))
    fc.file_path = "d.txt"
    # "A\n\n\n\nB".split("\n\n") -> ["A", "", "B"]; B truly begins on line 5.
    chunks = fc.chunk_by_delimiter("A\n\n\n\nB", "\n\n", include_delimiter=True)
    b_chunk = next(c for c in chunks if c.content.strip() == "B")
    assert (
        b_chunk.start_line == 5
    ), f"B should start on line 5, got {b_chunk.start_line}"


def test_identifier_index_not_stale_on_same_length_rechunk():
    """The identifier index must not serve stale chunks when the file is
    rechunked to the SAME number of chunks with different content (residual #3)."""
    prov = TreeSitterSmartContextProvider()

    def mk(tok: str) -> CodeChunk:
        return CodeChunk(
            language="python",
            file_path="f.py",
            node_type="function_definition",
            start_line=1,
            end_line=2,
            byte_start=0,
            byte_end=10,
            parent_context="",
            content=f"def fn():\n    return {tok}\n",
            chunk_id=f"id-{tok}",
        )

    v1 = [mk("alpha_ident")]
    idx1 = prov._identifier_index("f.py", "python", v1)
    assert "alpha_ident" in idx1

    v2 = [mk("beta_ident")]  # same length (1), different content
    idx2 = prov._identifier_index("f.py", "python", v2)
    assert "beta_ident" in idx2, "index served STALE chunks after same-length rechunk"
    assert "alpha_ident" not in idx2


def test_candidate_subset_is_deterministic():
    """Candidate selection must be stable across calls regardless of set
    iteration order, even when the cap truncates (residual #4)."""
    prov = TreeSitterSmartContextProvider()
    cap = prov._MAX_CONTEXT_CANDIDATES
    n = cap * 2
    # Query shares MANY identifiers, each bucket large, so the cap truncates
    # and the selected subset depends on identifier iteration order.
    shared = " ".join(f"tok{i}" for i in range(n))
    chunks = [
        CodeChunk(
            language="python",
            file_path="f.py",
            node_type="function_definition",
            start_line=i,
            end_line=i,
            byte_start=i * 10,
            byte_end=i * 10 + 9,
            parent_context="",
            content=f"def fn{i}():\n    return {shared}\n",
            chunk_id=f"c{i}",
        )
        for i in range(n)
    ]
    query = chunks[0]
    qf = prov._features_for(query)
    a = [c.chunk_id for c in prov._candidate_subset(query, qf, chunks)]
    b = [c.chunk_id for c in prov._candidate_subset(query, qf, chunks)]
    assert a == b, "candidate subset is not stable across calls"
    # And the selection is a deterministic function of the input (sorted).
    assert a == sorted(a), "candidate subset is not in a deterministic order"
