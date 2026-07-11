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
    part = TreeSitterTokenAwareChunker()._create_sub_chunk(
        original,
        "    return 1\n",
        1,
    )
    source = b"x" * 40 + original.content.encode("utf-8")

    assert source[part.byte_start : part.byte_end].decode("utf-8") == part.content
    assert part.start_line == 11
