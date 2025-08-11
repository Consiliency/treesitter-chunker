from chunker.packing import compute_pack_hint
from chunker.types import CodeChunk


def make_chunk(
    token_count: int = 0,
    cyclomatic: int = 0,
    degree: int = 0,
) -> CodeChunk:
    return CodeChunk(
        language="python",
        file_path="/tmp/x.py",
        node_type="function_definition",
        start_line=1,
        end_line=3,
        byte_start=0,
        byte_end=10,
        parent_context="module",
        content="def f():\n  pass\n",
        metadata={
            "token_count": token_count,
            "complexity": {"cyclomatic": cyclomatic},
            "degree": degree,
        },
    )


def test_pack_hint_bounds():
    c = make_chunk(100, 5, 2)
    s = compute_pack_hint(c)
    assert 0.0 <= s <= 1.0


def test_pack_hint_monotonic_token_count():
    c_small = make_chunk(100, 5, 2)
    c_large = make_chunk(1500, 5, 2)
    s_small = compute_pack_hint(c_small)
    s_large = compute_pack_hint(c_large)
    assert s_small > s_large


def test_pack_hint_monotonic_degree():
    c_low = make_chunk(200, 3, 0)
    c_high = make_chunk(200, 3, 20)
    s_low = compute_pack_hint(c_low)
    s_high = compute_pack_hint(c_high)
    assert s_high > s_low
