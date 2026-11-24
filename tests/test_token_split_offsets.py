from chunker.chunker import chunk_file_with_token_limit
from chunker.core import chunk_file
from chunker.token.chunker import TreeSitterTokenAwareChunker
from chunker.types import CodeChunk


def test_split_chunk_offsets_slice_the_original_utf8_content():
    original = CodeChunk(
        language="python",
        file_path="example.py",
        node_type="function_definition",
        start_line=10,
        end_line=12,
        byte_start=40,
        byte_end=40 + len("def café():\n    return 1\n".encode("utf-8")),
        parent_context="",
        content="def café():\n    return 1\n",
    )
    _, part = TreeSitterTokenAwareChunker()._split_large_chunk(original, 5, "gpt-4")
    source = b"x" * 40 + original.content.encode("utf-8")

    assert source[part.byte_start : part.byte_end].decode("utf-8") == part.content
    assert part.start_line == 11


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
