from chunker.fallback.strategies.line_based import LineBasedChunker
from chunker.smart_context import TreeSitterSmartContextProvider
from chunker.types import CodeChunk


def _chunk(name: str, content: str) -> CodeChunk:
    return CodeChunk(
        language="python",
        file_path="example.py",
        node_type="function_definition",
        start_line=1,
        end_line=2,
        byte_start=0,
        byte_end=len(content.encode("utf-8")),
        parent_context="",
        content=content,
        chunk_id=name,
    )


def test_fallback_offsets_are_utf8_byte_offsets():
    content = "café\nnaïve\n"
    chunks = LineBasedChunker(lines_per_chunk=1, overlap=0).chunk_text(
        content, "notes.txt"
    )
    source = content.encode("utf-8")

    assert [source[c.byte_start : c.byte_end].decode("utf-8") for c in chunks] == [
        c.content for c in chunks
    ]


def test_context_cache_varies_with_candidate_set():
    target = _chunk("target", "def target():\n    return helper()\n")
    helper = _chunk("helper", "def helper():\n    return 1\n")
    other = _chunk("other", "def unrelated():\n    return 2\n")
    provider = TreeSitterSmartContextProvider()

    assert [
        chunk.chunk_id for chunk, _ in provider.get_dependency_context(target, [helper])
    ] == ["helper"]
    assert provider.get_dependency_context(target, [other]) == []


def test_chunker_token_limit_handles_invalid_utf8(tmp_path):
    """The token-limited file path must not crash on invalid UTF-8 (errors=replace)."""
    from chunker.chunker import chunk_file_with_token_limit

    f = tmp_path / "bad.py"
    f.write_bytes(b"def f():\n    x = '\xff\xfe invalid'\n    return x\n")
    chunks = chunk_file_with_token_limit(str(f), "python", max_tokens=1000)
    assert isinstance(chunks, list)  # no UnicodeDecodeError


def test_markdown_section_chunks_true_byte_offsets():
    """Markdown section chunks carry TRUE byte offsets (not byte_start=0 / char len)
    on multibyte content."""
    from chunker.fallback.strategies.markdown import MarkdownChunker

    content = "# Ttulo\n\nprrafo uno con acentos\n\n## Segundo\n\nms texto aqu\n"
    mc = MarkdownChunker()
    mc.file_path = "doc.md"
    chunks = mc.chunk_by_sections(content)
    src = content.encode("utf-8")
    for c in chunks:
        if c.node_type.startswith("markdown_"):
            # byte range must slice back to the chunk content
            assert (
                src[c.byte_start : c.byte_end].decode("utf-8") == c.content
            ), f"markdown section byte offsets wrong: {c.byte_start}:{c.byte_end}"


def test_smart_context_memoizes_features():
    """Semantic features are extracted ONCE per chunk across repeated requests
    (bounded O(n), not O(n^2) per-request extraction)."""
    from unittest.mock import patch

    from chunker.smart_context import TreeSitterSmartContextProvider
    from chunker import chunk_text

    code = "\n".join(f"def fn{i}():\n    return {i}\n" for i in range(6))
    chunks = chunk_text(code, "python")
    prov = TreeSitterSmartContextProvider()

    real = prov._extract_semantic_features
    calls = {"n": 0}

    def counting(chunk):
        calls["n"] += 1
        return real(chunk)

    with patch.object(type(prov), "_extract_semantic_features", staticmethod(counting)):
        prov._feature_cache.clear()
        for c in chunks:
            with patch.object(prov, "_get_file_chunks", return_value=chunks):
                prov.get_semantic_context(c)
    # Without memoization this would be O(n^2) ~ 36+; memoized it is O(n) ~ <= len(chunks)+few.
    assert (
        calls["n"] <= len(chunks) + 2
    ), f"features extracted {calls['n']}x (not memoized)"


def test_candidate_subset_is_bounded_at_scale():
    """The similarity scan is bounded to O(n * cap), not O(n^2).

    With all-unique identifiers every query falls through to the bounded
    fallback, which is capped at _MAX_CONTEXT_CANDIDATES. Above the cap the
    total candidate-comparisons must stay <= n * cap (was n*(n-1) all-pairs).
    """
    prov = TreeSitterSmartContextProvider()
    cap = prov._MAX_CONTEXT_CANDIDATES
    n = cap * 3
    chunks = [
        _chunk(f"c{i}", f"def fn{i}():\n    return unique_{i}\n") for i in range(n)
    ]
    total = sum(
        len(prov._candidate_subset(c, prov._features_for(c), chunks)) for c in chunks
    )
    assert total <= n * cap, f"unbounded: {total} > {n * cap}"
    # And it is a genuine reduction vs the former all-pairs pass.
    assert total < n * (n - 1)
